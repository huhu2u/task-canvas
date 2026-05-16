#!/usr/bin/env python3
"""
生存时间统计摘要脚本

功能：
- 中位生存时间及95%置信区间
- 25%/50%/75%分位数生存时间
- 受限平均生存时间（RMST）及标准误
- 事件率与删失比例
- 分组统计

依赖：pip install lifelines pandas numpy

用法：
    python survival_summary.py input.csv --duration-col time --event-col status \
        --group-col group -o summary_output.csv
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


def calc_rmst(kmf, tau: float = None) -> dict:
    """计算受限平均生存时间"""
    timeline = kmf.survival_function_.index.values
    survival_probs = kmf.survival_function_.values.flatten()

    if tau is None:
        tau = timeline[-1]
    else:
        tau = min(tau, timeline[-1])

    mask = timeline <= tau
    t_restricted = timeline[mask]
    s_restricted = survival_probs[mask]

    if len(t_restricted) < 2:
        return {'rmst': np.nan, 'se': np.nan, 'tau': tau}

    rmst = np.trapz(s_restricted, t_restricted)

    # 方差近似（基于Greenwood公式积分的简化版本）
    n_at_risk = kmf.event_table['at_risk'].values
    n_events_table = kmf.event_table['observed'].values
    event_times = kmf.event_table.index.values

    # 简化标准误估计
    var_approx = 0
    for i, t_i in enumerate(event_times):
        if t_i > tau:
            break
        if n_at_risk[i] > 0 and n_at_risk[i] > n_events_table[i]:
            d_i = n_events_table[i]
            n_i = n_at_risk[i]
            # 计算t_i到tau的生存函数积分
            mask_after = (timeline >= t_i) & (timeline <= tau)
            if mask_after.sum() >= 2:
                area_after = np.trapz(survival_probs[mask_after], timeline[mask_after])
            else:
                area_after = 0
            var_approx += d_i / (n_i * (n_i - d_i)) * area_after ** 2 if n_i > d_i else 0

    se = np.sqrt(max(var_approx, 0))
    return {'rmst': float(rmst), 'se': float(se), 'tau': float(tau)}


def quantile_survival_time(kmf, q: float) -> float:
    """
    计算q分位数生存时间
    q: 0到1之间，例如0.5为中位数
    """
    sf = kmf.survival_function_.values.flatten()
    timeline = kmf.survival_function_.index.values

    # 找到生存概率首次降到1-q以下的时间点
    target = 1 - q
    below = sf <= target
    if below.any():
        return float(timeline[below][0])
    else:
        return np.inf


def survival_summary(df: pd.DataFrame, duration_col: str, event_col: str,
                     group_col: str = None) -> pd.DataFrame:
    """
    生存时间综合统计摘要

    参数：
        df: 输入数据
        duration_col: 生存时长列
        event_col: 事件状态列
        group_col: 分组列（可选）
    """
    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        print("错误: 需要安装lifelines库: pip install lifelines")
        sys.exit(1)

    groups_to_process = []
    if group_col is None:
        groups_to_process = [('全体', df)]
    else:
        for g in sorted(df[group_col].dropna().unique()):
            groups_to_process.append((str(g), df[df[group_col] == g]))

    summary_rows = []

    for group_name, group_df in groups_to_process:
        n_total = len(group_df)
        n_events = int(group_df[event_col].sum())
        n_censored = n_total - n_events
        censor_rate = n_censored / n_total * 100 if n_total > 0 else 0
        event_rate = n_events / n_total * 100 if n_total > 0 else 0

        # KM拟合
        kmf = KaplanMeierFitter()
        kmf.fit(group_df[duration_col], event_observed=group_df[event_col])

        # 中位生存时间
        median_st = kmf.median_survival_time_

        # 置信区间（通过KM方法）
        try:
            median_ci = kmf.confidence_interval_median_survival_time_
            median_ci_lower = float(median_ci.iloc[0, 0]) if not median_ci.empty else np.nan
            median_ci_upper = float(median_ci.iloc[0, 1]) if not median_ci.empty else np.nan
        except Exception:
            median_ci_lower = np.nan
            median_ci_upper = np.nan

        # 分位数
        q25 = quantile_survival_time(kmf, 0.25)
        q50 = quantile_survival_time(kmf, 0.50)
        q75 = quantile_survival_time(kmf, 0.75)

        # RMST
        rmst_result = calc_rmst(kmf)

        # 基本统计
        mean_duration = group_df[duration_col].mean()
        std_duration = group_df[duration_col].std()
        min_duration = group_df[duration_col].min()
        max_duration = group_df[duration_col].max()

        row = {
            '分组': group_name,
            '样本量': n_total,
            '事件数': n_events,
            '删失数': n_censored,
            '事件率(%)': round(event_rate, 2),
            '删失比例(%)': round(censor_rate, 2),
            '观察时间_均值': round(mean_duration, 4),
            '观察时间_标准差': round(std_duration, 4),
            '观察时间_最小值': round(min_duration, 4),
            '观察时间_最大值': round(max_duration, 4),
            '中位生存时间': round(median_st, 4) if not np.isinf(median_st) else 'NA',
            '中位_CI下界': round(median_ci_lower, 4) if not np.isnan(median_ci_lower) else 'NA',
            '中位_CI上界': round(median_ci_upper, 4) if not np.isnan(median_ci_upper) else 'NA',
            'Q25生存时间': round(q25, 4) if not np.isinf(q25) else 'NA',
            'Q50生存时间': round(q50, 4) if not np.isinf(q50) else 'NA',
            'Q75生存时间': round(q75, 4) if not np.isinf(q75) else 'NA',
            'RMST': round(rmst_result['rmst'], 4),
            'RMST_标准误': round(rmst_result['se'], 4),
            'RMST_截断时间': round(rmst_result['tau'], 4)
        }
        summary_rows.append(row)

    result = pd.DataFrame(summary_rows)

    print(f"\n=== 生存时间统计摘要 ===")
    print(result.to_string(index=False))

    # 警告
    for _, row in result.iterrows():
        if row['删失比例(%)'] > 80:
            print(f"\n  警告: [{row['分组']}] 删失比例为 {row['删失比例(%)']}%，超过80%，结论稳健性不足")

    return result


def main():
    parser = argparse.ArgumentParser(description='生存时间统计摘要')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--duration-col', required=True, help='生存时长列名')
    parser.add_argument('--event-col', required=True, help='事件状态列名（1=事件，0=删失）')
    parser.add_argument('--group-col', default=None, help='分组列名（可选）')
    parser.add_argument('-o', '--output', default='survival_summary.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    required_cols = [args.duration_col, args.event_col]
    if args.group_col:
        required_cols.append(args.group_col)
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误: 以下列不存在: {missing}")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    df = df.dropna(subset=[args.duration_col, args.event_col])
    df[args.event_col] = df[args.event_col].astype(int)

    result = survival_summary(df, args.duration_col, args.event_col, args.group_col)

    result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
