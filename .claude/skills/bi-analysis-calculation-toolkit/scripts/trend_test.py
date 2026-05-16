#!/usr/bin/env python3
"""
趋势检验脚本

功能：
- 标准Mann-Kendall趋势检验
- 季节性Mann-Kendall检验（Seasonal MK）
- 预白化修正Mann-Kendall检验（Modified MK，消除自相关影响）
- Sen斜率估计及95%置信区间
- ADF平稳性检验

依赖：pip install pandas numpy scipy statsmodels

用法：
    python trend_test.py input.csv --time-col date --value-col metric \
        --season-period 12 --alpha 0.05 -o trend_test_output.csv
"""

import argparse
import sys
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def _downsample_series(series: np.ndarray, max_n: int = 10000) -> np.ndarray:
    """
    等间隔降采样：当数据量超过 max_n 时，等间距取 max_n 个点。

    参数：
        series: 原始序列
        max_n: 降采样目标点数
    返回：
        降采样后的序列
    """
    n = len(series)
    if n <= max_n:
        return series
    indices = np.linspace(0, n - 1, max_n, dtype=int)
    return series[indices]


def _compute_s_statistic(series: np.ndarray) -> int:
    """
    向量化计算 Mann-Kendall S 统计量。

    按 i 的行索引分块，每块内：
    - 只与 j > i_start 的列做广播计算
    - 用上三角 mask 精确筛选 j > i 的配对
    全程无 Python 逐元素循环，纯 NumPy 向量化。
    """
    n = len(series)
    # chunk_size 控制每次处理的 i 行数
    # 内存峰值 ≈ chunk_size × (n - i_start) × 8 字节
    # chunk_size=2000, n=10000 → 最大约 160MB，可接受
    chunk_size = 2000
    S = 0
    for i_start in range(0, n - 1, chunk_size):
        i_end = min(i_start + chunk_size, n - 1)
        bi = i_end - i_start
        # j 的范围: [i_start + 1, n)  —— 只需要 j > i_start 的列
        j_start = i_start + 1
        bj = n - j_start
        if bj <= 0:
            break
        # 广播计算差值: shape (bi, bj)
        diff = series[j_start:n] - series[i_start:i_end, np.newaxis]
        signs = np.sign(diff)
        # 构建 mask: mask[r, c] = True 当 j > i
        # 全局 i = i_start + r, 全局 j = j_start + c = i_start + 1 + c
        # 条件 j > i  ⟺  i_start + 1 + c > i_start + r  ⟺  c > r - 1  ⟺  c >= r
        # 即 c >= r 时有效（注意 r 从0开始）
        row_idx = np.arange(bi)[:, np.newaxis]  # (bi, 1)
        col_idx = np.arange(bj)[np.newaxis, :]  # (1, bj)
        mask = col_idx >= row_idx  # (bi, bj)
        S += int((signs * mask).sum())
    return S


def mann_kendall_test(series: np.ndarray, alpha: float = 0.05) -> dict:
    """
    标准Mann-Kendall非参数趋势检验

    参数：
        series: 时间序列值数组
        alpha: 显著性水平
    """
    n = len(series)
    if n < 4:
        return {'S': 0, 'Z': 0, 'p_value': 1.0, 'direction': '数据不足', 'significant': False}

    # 大数据量自动降采样
    if n > 10000:
        print(f"  [mann_kendall_test] 数据量 n={n} 超过 10000，自动等间隔降采样到 10000 个点进行检验")
        series = _downsample_series(series, 10000)
        n = len(series)

    # 向量化计算S统计量
    S = _compute_s_statistic(series)

    # 处理并列值
    unique, counts = np.unique(series, return_counts=True)
    tied_groups = counts[counts > 1]

    # 方差（含并列修正）
    var_S = n * (n - 1) * (2 * n + 5)
    if len(tied_groups) > 0:
        for t in tied_groups:
            var_S -= t * (t - 1) * (2 * t + 5)
    var_S /= 18.0

    # Z统计量
    if S > 0:
        Z = (S - 1) / np.sqrt(var_S)
    elif S < 0:
        Z = (S + 1) / np.sqrt(var_S)
    else:
        Z = 0

    p_value = 2 * (1 - stats.norm.cdf(abs(Z)))

    if S > 0:
        direction = '上升趋势'
    elif S < 0:
        direction = '下降趋势'
    else:
        direction = '无趋势'

    significant = p_value < alpha

    return {
        'S': int(S),
        'Z': round(Z, 4),
        'p_value': round(p_value, 6),
        'direction': direction,
        'significant': significant,
        'Tau': round(2 * S / (n * (n - 1)), 4)  # Kendall's tau
    }


def seasonal_mann_kendall_test(series: np.ndarray, period: int,
                                alpha: float = 0.05) -> dict:
    """
    季节性Mann-Kendall检验

    对每个季节分别做MK检验，再合并S统计量
    """
    n = len(series)
    if n < period * 2:
        return {'S': 0, 'Z': 0, 'p_value': 1.0, 'direction': '数据不足（需至少2个完整周期）',
                'significant': False}

    total_S = 0
    total_var = 0

    for season in range(period):
        season_data = series[season::period]
        if len(season_data) < 4:
            continue
        result = mann_kendall_test(season_data, alpha)
        total_S += result['S']
        n_s = len(season_data)
        var_s = n_s * (n_s - 1) * (2 * n_s + 5) / 18.0
        total_var += var_s

    if total_var == 0:
        return {'S': 0, 'Z': 0, 'p_value': 1.0, 'direction': '无法计算', 'significant': False}

    if total_S > 0:
        Z = (total_S - 1) / np.sqrt(total_var)
    elif total_S < 0:
        Z = (total_S + 1) / np.sqrt(total_var)
    else:
        Z = 0

    p_value = 2 * (1 - stats.norm.cdf(abs(Z)))

    if total_S > 0:
        direction = '上升趋势'
    elif total_S < 0:
        direction = '下降趋势'
    else:
        direction = '无趋势'

    return {
        'S': int(total_S),
        'Z': round(Z, 4),
        'p_value': round(p_value, 6),
        'direction': direction,
        'significant': p_value < alpha
    }


def modified_mann_kendall_test(series: np.ndarray, alpha: float = 0.05) -> dict:
    """
    预白化修正Mann-Kendall检验

    消除一阶自相关对趋势检验的干扰
    """
    n = len(series)
    if n < 10:
        return mann_kendall_test(series, alpha)

    # 计算AR(1)系数
    from statsmodels.tsa.stattools import acf
    acf_vals = acf(series, nlags=1, fft=True)
    r1 = acf_vals[1]

    # 如果自相关不显著，直接使用标准MK
    # 自相关显著性阈值：1.96/sqrt(n)
    threshold = 1.96 / np.sqrt(n)
    if abs(r1) < threshold:
        result = mann_kendall_test(series, alpha)
        result['method'] = '标准MK（自相关不显著，无需预白化）'
        result['ar1'] = round(r1, 4)
        return result

    # 预白化：去除AR(1)成分
    # x_t' = x_t - r1 * x_{t-1}
    prewhitened = series[1:] - r1 * series[:-1]

    result = mann_kendall_test(prewhitened, alpha)
    result['method'] = '预白化修正MK'
    result['ar1'] = round(r1, 4)
    return result


def _compute_slopes_chunked(series: np.ndarray, chunk_size: int = 2000) -> np.ndarray:
    """
    分块向量化计算所有 (j > i) 的斜率 (series[j] - series[i]) / (j - i)。

    将行索引分块，每块内用 np.subtract.outer 向量化计算，
    避免一次性生成完整 n×n 矩阵导致内存溢出。

    参数：
        series: 时间序列数组
        chunk_size: 每块处理的行数（控制内存峰值）
    返回：
        所有斜率组成的一维数组
    """
    n = len(series)
    indices = np.arange(n, dtype=np.float64)
    slope_chunks = []

    for i_start in range(0, n - 1, chunk_size):
        i_end = min(i_start + chunk_size, n - 1)
        # 对 i in [i_start, i_end)，j 的范围是 (i+1, n]
        # 为简化向量化，取 j 的列范围为 [i_start+1, n)
        j_start = i_start + 1
        vals_i = series[i_start:i_end]       # shape (bi,)
        vals_j = series[j_start:n]            # shape (bj,)
        idx_i = indices[i_start:i_end]
        idx_j = indices[j_start:n]

        # diff_val[r, c] = vals_j[c] - vals_i[r]
        diff_val = np.subtract.outer(vals_j, vals_i).T   # shape (bi, bj)
        diff_idx = np.subtract.outer(idx_j, idx_i).T     # shape (bi, bj)

        # 只保留 j > i 的上三角部分
        bi = i_end - i_start
        bj = n - j_start
        for local_i in range(bi):
            global_i = i_start + local_i
            # j 必须 > global_i，在 vals_j 中对应 index >= global_i + 1 - j_start
            col_start = max(0, global_i + 1 - j_start)
            if col_start < bj:
                s = diff_val[local_i, col_start:] / diff_idx[local_i, col_start:]
                slope_chunks.append(s)

    return np.concatenate(slope_chunks)


def sen_slope(series: np.ndarray) -> dict:
    """
    Sen斜率估计及95%置信区间

    非参数斜率估计，对异常值稳健
    """
    n = len(series)

    # 大数据量自动降采样
    if n > 10000:
        print(f"  [sen_slope] 数据量 n={n} 超过 10000，自动等间隔降采样到 10000 个点进行估计")
        series = _downsample_series(series, 10000)
        n = len(series)

    # 分块向量化计算斜率
    slopes = _compute_slopes_chunked(series)
    median_slope = np.median(slopes)

    # 置信区间（基于MK检验的S统计量方差）
    C_alpha = 1.96  # 95% CI
    var_S = n * (n - 1) * (2 * n + 5) / 18.0
    W = C_alpha * np.sqrt(var_S)

    sorted_slopes = np.sort(slopes)
    N_prime = len(sorted_slopes)
    lower_idx = max(0, int((N_prime - W) / 2))
    upper_idx = min(N_prime - 1, int((N_prime + W) / 2))

    ci_lower = sorted_slopes[lower_idx]
    ci_upper = sorted_slopes[upper_idx]

    return {
        'sen_slope': round(float(median_slope), 6),
        'ci_lower': round(float(ci_lower), 6),
        'ci_upper': round(float(ci_upper), 6),
        'n_slopes': len(slopes)
    }


def adf_test(series: np.ndarray) -> dict:
    """ADF平稳性检验"""
    from statsmodels.tsa.stattools import adfuller
    result = adfuller(series, autolag='AIC')
    return {
        'adf_stat': round(result[0], 4),
        'p_value': round(result[1], 6),
        'used_lag': result[2],
        'stationary': result[1] < 0.05
    }


def trend_analysis(df: pd.DataFrame, time_col: str, value_col: str,
                   season_period: int = None, alpha: float = 0.05) -> pd.DataFrame:
    """
    综合趋势分析

    参数：
        df: 输入数据
        time_col: 时间列
        value_col: 值列
        season_period: 季节周期（可选）
        alpha: 显著性水平
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    series = df[value_col].dropna().values

    print(f"\n=== 趋势分析 ===")
    print(f"  数据量: {len(series)} 个观测")
    print(f"  数据范围: {df[time_col].min()} ~ {df[time_col].max()}")
    print(f"  显著性水平: {alpha}")

    results = []

    # 1. 标准Mann-Kendall检验
    mk_result = mann_kendall_test(series, alpha)
    print(f"\n  [标准Mann-Kendall检验]")
    print(f"    S = {mk_result['S']}, Z = {mk_result['Z']}, p = {mk_result['p_value']}")
    print(f"    Kendall tau = {mk_result['Tau']}")
    print(f"    方向: {mk_result['direction']}")
    print(f"    结论: {'趋势统计显著' if mk_result['significant'] else '不能排除随机波动'}")
    results.append({'检验方法': '标准MK', **mk_result})

    # 2. 季节性Mann-Kendall检验
    if season_period and season_period > 1:
        smk_result = seasonal_mann_kendall_test(series, season_period, alpha)
        print(f"\n  [季节性Mann-Kendall检验 (周期={season_period})]")
        print(f"    S = {smk_result['S']}, Z = {smk_result['Z']}, p = {smk_result['p_value']}")
        print(f"    方向: {smk_result['direction']}")
        print(f"    结论: {'趋势统计显著' if smk_result['significant'] else '不能排除随机波动'}")
        results.append({'检验方法': f'季节性MK(T={season_period})', **smk_result})

    # 3. 预白化修正MK检验
    mmk_result = modified_mann_kendall_test(series, alpha)
    print(f"\n  [预白化修正Mann-Kendall检验]")
    print(f"    方法: {mmk_result.get('method', '预白化MK')}")
    print(f"    AR(1)系数: {mmk_result.get('ar1', 'N/A')}")
    print(f"    S = {mmk_result['S']}, Z = {mmk_result['Z']}, p = {mmk_result['p_value']}")
    print(f"    方向: {mmk_result['direction']}")
    print(f"    结论: {'趋势统计显著' if mmk_result['significant'] else '不能排除随机波动'}")
    results.append({'检验方法': '预白化修正MK', **mmk_result})

    # 4. Sen斜率
    sen_result = sen_slope(series)
    print(f"\n  [Sen斜率估计]")
    print(f"    斜率: {sen_result['sen_slope']}")
    print(f"    95%置信区间: [{sen_result['ci_lower']}, {sen_result['ci_upper']}]")

    # 5. ADF检验
    adf_result = adf_test(series)
    print(f"\n  [ADF平稳性检验]")
    print(f"    ADF统计量: {adf_result['adf_stat']}")
    print(f"    p值: {adf_result['p_value']}")
    print(f"    结论: {'序列平稳' if adf_result['stationary'] else '序列非平稳'}")

    # 综合解读
    print(f"\n=== 综合解读 ===")
    if mk_result['significant'] and not adf_result['stationary']:
        print(f"  序列非平稳且存在显著趋势，趋势方向为{mk_result['direction']}")
    elif mk_result['significant'] and adf_result['stationary']:
        print(f"  序列平稳但MK检验显示显著趋势，可能存在确定性趋势成分")
    elif not mk_result['significant'] and not adf_result['stationary']:
        print(f"  序列非平稳但趋势不显著，可能存在随机游走或结构变化")
    else:
        print(f"  序列平稳且无显著趋势")

    # 汇总结果
    summary = pd.DataFrame(results)
    summary['Sen斜率'] = sen_result['sen_slope']
    summary['Sen_CI_下'] = sen_result['ci_lower']
    summary['Sen_CI_上'] = sen_result['ci_upper']
    summary['ADF_p值'] = adf_result['p_value']
    summary['ADF_平稳'] = adf_result['stationary']

    return summary


def main():
    parser = argparse.ArgumentParser(description='趋势显著性检验')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--value-col', required=True, help='值列名')
    parser.add_argument('--season-period', type=int, default=None,
                        help='季节周期（如7=周周期, 12=月周期）')
    parser.add_argument('--alpha', type=float, default=0.05, help='显著性水平（默认: 0.05）')
    parser.add_argument('-o', '--output', default='trend_test_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.value_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            sys.exit(1)

    result = trend_analysis(df, args.time_col, args.value_col,
                            args.season_period, args.alpha)

    result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
