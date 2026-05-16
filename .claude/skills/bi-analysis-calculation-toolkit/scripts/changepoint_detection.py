#!/usr/bin/env python3
"""
突变点检测脚本

功能：
- PELT算法检测均值/方差结构变化
- CUSUM方法（备选/互补）
- 贝叶斯在线突变点检测（Bayesian Online CPD）
- 段内统计量输出（均值、标准差、样本量）
- 突变点过多时自动调高惩罚参数

依赖：pip install ruptures pandas numpy

用法：
    python changepoint_detection.py input.csv --time-col date --value-col metric \
        --method pelt --penalty auto -o changepoint_output.csv
"""

import argparse
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def pelt_detection(signal: np.ndarray, penalty: str = 'auto',
                   max_breakpoints: int = 10) -> list:
    """
    PELT算法突变点检测

    参数：
        signal: 时间序列值
        penalty: 惩罚参数（'auto'或数值）
        max_breakpoints: 最大允许突变点数
    """
    try:
        import ruptures as rpt
    except ImportError:
        print("  ruptures未安装，使用CUSUM替代")
        return cusum_detection(signal)

    # 自动惩罚参数
    if penalty == 'auto':
        pen = np.log(len(signal)) * signal.var()
    else:
        pen = float(penalty)

    print(f"  PELT参数: penalty={pen:.4f}")

    model = rpt.Pelt(model='rbf').fit(signal)
    breakpoints = model.predict(pen=pen)

    # ruptures总是包含序列末尾，需去掉
    breakpoints = [bp for bp in breakpoints if bp < len(signal)]

    # 突变点过多时自动调高惩罚
    attempts = 0
    while len(breakpoints) > max_breakpoints and attempts < 5:
        pen *= 2
        print(f"  突变点过多({len(breakpoints)}个)，提高惩罚参数至 {pen:.4f}")
        breakpoints = model.predict(pen=pen)
        breakpoints = [bp for bp in breakpoints if bp < len(signal)]
        attempts += 1

    return breakpoints


def cusum_detection(signal: np.ndarray, threshold_sigma: float = 3.0) -> list:
    """
    CUSUM突变点检测

    参数：
        signal: 时间序列值
        threshold_sigma: 阈值（标准差倍数）
    """
    mean_val = signal.mean()
    std_val = signal.std()
    cusum = np.cumsum(signal - mean_val)
    threshold = threshold_sigma * std_val * np.sqrt(len(signal))

    # 找超过阈值的位置
    above_threshold = np.where(np.abs(cusum) > threshold)[0]

    # 合并相邻位置（只保留每段的第一个）
    breakpoints = []
    if len(above_threshold) > 0:
        breakpoints.append(int(above_threshold[0]))
        for idx in above_threshold[1:]:
            if idx - breakpoints[-1] > len(signal) * 0.05:  # 间距至少5%数据长度
                breakpoints.append(int(idx))

    return breakpoints


def bayesian_online_cpd(signal: np.ndarray, hazard: float = 250) -> list:
    """
    贝叶斯在线突变点检测（简化实现）

    基于Bayesian Online Changepoint Detection (Adams & MacKay, 2007)

    参数：
        signal: 时间序列值
        hazard: 风险率参数（越大对变化越不敏感）
    """
    n = len(signal)

    # 数据量过大时自动降采样，防止 O(n²) 矩阵导致内存溢出
    MAX_SAMPLES = 5000
    if n > MAX_SAMPLES:
        print(f"  [降采样] 数据量 {n} 超过阈值 {MAX_SAMPLES}，自动等间隔降采样到 {MAX_SAMPLES} 个点")
        downsample_indices = np.linspace(0, n - 1, MAX_SAMPLES).astype(int)
        signal = signal[downsample_indices]
        n = len(signal)

    max_run = n + 1

    # 运行长度概率矩阵
    R = np.zeros((max_run, n + 1))
    R[0, 0] = 1.0

    # 充分统计量
    mean_vals = np.zeros(max_run)
    var_vals = np.ones(max_run)
    count_vals = np.zeros(max_run)

    # 先验参数
    mu0 = signal.mean()
    kappa0 = 1.0
    alpha0 = 1.0
    beta0 = signal.var()

    changepoint_probs = np.zeros(n)

    for t in range(n):
        x = signal[t]

        # 预测概率（正态-逆伽马共轭先验）
        pred_probs = np.zeros(t + 1)
        for r in range(t + 1):
            if count_vals[r] > 0:
                mu_n = (kappa0 * mu0 + count_vals[r] * mean_vals[r]) / (kappa0 + count_vals[r])
                kappa_n = kappa0 + count_vals[r]
                alpha_n = alpha0 + count_vals[r] / 2
                beta_n = beta0 + 0.5 * count_vals[r] * var_vals[r]
            else:
                mu_n, kappa_n, alpha_n, beta_n = mu0, kappa0, alpha0, beta0

            pred_var = beta_n * (kappa_n + 1) / (alpha_n * kappa_n)
            pred_var = max(pred_var, 1e-10)
            pred_probs[r] = np.exp(-0.5 * (x - mu_n) ** 2 / pred_var) / np.sqrt(2 * np.pi * pred_var)

        # 增长概率
        growth_prob = R[:t + 1, t] * pred_probs * (1 - 1.0 / hazard)
        # 突变概率
        cp_prob = np.sum(R[:t + 1, t] * pred_probs * (1.0 / hazard))

        R[1:t + 2, t + 1] = growth_prob
        R[0, t + 1] = cp_prob

        # 归一化
        total = R[:t + 2, t + 1].sum()
        if total > 0:
            R[:t + 2, t + 1] /= total

        changepoint_probs[t] = R[0, t + 1]

        # 更新充分统计量
        for r in range(t + 1, 0, -1):
            if count_vals[r - 1] == 0:
                mean_vals[r] = x
                var_vals[r] = 0
                count_vals[r] = 1
            else:
                old_mean = mean_vals[r - 1]
                old_count = count_vals[r - 1]
                new_count = old_count + 1
                new_mean = old_mean + (x - old_mean) / new_count
                new_var = ((old_count - 1) * var_vals[r - 1] + (x - old_mean) * (x - new_mean)) / max(new_count - 1, 1)
                mean_vals[r] = new_mean
                var_vals[r] = new_var
                count_vals[r] = new_count
        mean_vals[0] = 0
        var_vals[0] = 0
        count_vals[0] = 0

    # 从突变概率中提取突变点
    threshold = np.mean(changepoint_probs) + 2 * np.std(changepoint_probs)
    threshold = max(threshold, 0.1)

    candidates = np.where(changepoint_probs > threshold)[0]
    breakpoints = []
    if len(candidates) > 0:
        breakpoints.append(int(candidates[0]))
        for idx in candidates[1:]:
            if idx - breakpoints[-1] > len(signal) * 0.05:
                breakpoints.append(int(idx))

    return breakpoints, changepoint_probs


def segment_statistics(signal: np.ndarray, breakpoints: list,
                       time_index=None) -> pd.DataFrame:
    """
    计算各段的统计量

    参数：
        signal: 时间序列值
        breakpoints: 突变点索引列表
        time_index: 时间索引（可选）
    """
    segments = []
    all_points = [0] + sorted(breakpoints) + [len(signal)]

    for i in range(len(all_points) - 1):
        start = all_points[i]
        end = all_points[i + 1]
        segment_data = signal[start:end]

        seg_info = {
            '段序号': i + 1,
            '起始索引': start,
            '结束索引': end - 1,
            '样本量': len(segment_data),
            '均值': round(np.mean(segment_data), 4),
            '标准差': round(np.std(segment_data, ddof=1), 4) if len(segment_data) > 1 else 0,
            '中位数': round(np.median(segment_data), 4),
            '最小值': round(np.min(segment_data), 4),
            '最大值': round(np.max(segment_data), 4)
        }

        if time_index is not None and len(time_index) > start:
            seg_info['起始时间'] = str(time_index[start])
            seg_info['结束时间'] = str(time_index[min(end - 1, len(time_index) - 1)])

        segments.append(seg_info)

    seg_df = pd.DataFrame(segments)

    # 计算段间变化
    if len(segments) > 1:
        print(f"\n  段间变化:")
        for i in range(1, len(segments)):
            prev_mean = segments[i - 1]['均值']
            curr_mean = segments[i]['均值']
            change = curr_mean - prev_mean
            pct_change = change / abs(prev_mean) * 100 if prev_mean != 0 else np.nan
            print(f"    段{i} -> 段{i + 1}: 均值变化 = {change:+.4f}", end='')
            if not np.isnan(pct_change):
                print(f" ({pct_change:+.2f}%)")
            else:
                print()

    return seg_df


def changepoint_analysis(df: pd.DataFrame, time_col: str, value_col: str,
                         method: str = 'pelt', penalty: str = 'auto') -> dict:
    """
    突变点综合分析

    参数：
        df: 输入数据
        time_col: 时间列
        value_col: 值列
        method: 检测方法（pelt/cusum/bayesian/all）
        penalty: PELT惩罚参数
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    signal = df[value_col].dropna().values
    time_index = df[time_col].values

    print(f"\n=== 突变点检测 ===")
    print(f"  数据量: {len(signal)} 个观测")
    print(f"  检测方法: {method}")

    results = {}

    # PELT
    if method in ('pelt', 'all'):
        print(f"\n  --- PELT算法 ---")
        pelt_bps = pelt_detection(signal, penalty)
        print(f"  检测到 {len(pelt_bps)} 个突变点")
        if pelt_bps:
            for bp in pelt_bps:
                if bp < len(time_index):
                    print(f"    索引={bp}, 时间={time_index[bp]}")
        results['pelt'] = pelt_bps

        # 段统计
        seg_df = segment_statistics(signal, pelt_bps, time_index)
        print(f"\n  段统计:")
        print(seg_df.to_string(index=False))
        results['pelt_segments'] = seg_df

    # CUSUM
    if method in ('cusum', 'all'):
        print(f"\n  --- CUSUM方法 ---")
        cusum_bps = cusum_detection(signal)
        print(f"  检测到 {len(cusum_bps)} 个突变点")
        if cusum_bps:
            for bp in cusum_bps:
                if bp < len(time_index):
                    print(f"    索引={bp}, 时间={time_index[bp]}")
        results['cusum'] = cusum_bps

        seg_df = segment_statistics(signal, cusum_bps, time_index)
        results['cusum_segments'] = seg_df

    # Bayesian
    if method in ('bayesian', 'all'):
        print(f"\n  --- 贝叶斯在线突变点检测 ---")
        if len(signal) > 10000:
            print(f"  警告: 数据量较大（{len(signal)}），贝叶斯在线CPD为O(n²)复杂度，"
                  f"可能消耗大量内存和时间。建议对数据进行降采样或使用PELT方法。")
        bayes_bps, cp_probs = bayesian_online_cpd(signal)
        print(f"  检测到 {len(bayes_bps)} 个突变点")
        if bayes_bps:
            for bp in bayes_bps:
                if bp < len(time_index):
                    print(f"    索引={bp}, 时间={time_index[bp]}, 概率={cp_probs[bp]:.4f}")
        results['bayesian'] = bayes_bps
        results['bayesian_probs'] = cp_probs

        seg_df = segment_statistics(signal, bayes_bps, time_index)
        results['bayesian_segments'] = seg_df

    return results


def main():
    parser = argparse.ArgumentParser(description='突变点检测')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--value-col', required=True, help='值列名')
    parser.add_argument('--method', default='pelt',
                        choices=['pelt', 'cusum', 'bayesian', 'all'],
                        help='检测方法（默认: pelt）')
    parser.add_argument('--penalty', default='auto',
                        help='PELT惩罚参数（auto或数值，默认: auto）')
    parser.add_argument('-o', '--output', default='changepoint_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.value_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            sys.exit(1)

    results = changepoint_analysis(df, args.time_col, args.value_col,
                                   args.method, args.penalty)

    # 保存段统计
    for method_key in ['pelt_segments', 'cusum_segments', 'bayesian_segments']:
        if method_key in results:
            if method_key == 'pelt_segments':
                output_path = args.output
            else:
                output_path = args.output.replace('.csv', f'_{method_key.split("_")[0]}.csv')
            results[method_key].to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"\n{method_key}已保存至: {output_path}")


if __name__ == '__main__':
    main()
