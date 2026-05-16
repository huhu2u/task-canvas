#!/usr/bin/env python3
"""
增长率计算脚本

功能：
- 环比增长率（MoM/WoW，相邻周期变化）
- 同比增长率（YoY，去年同期变化）
- CAGR（复合年增长率）
- 几何平均增长率（适用于波动序列）
- 基期为0时优雅处理（标记N/A）
- 自动检测时间粒度

依赖：pip install pandas numpy

用法：
    python growth_rate.py input.csv --time-col date --metric-col value \
        --freq auto -o growth_output.csv
"""

import argparse
import sys
import numpy as np
import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def detect_frequency(time_series: pd.Series) -> str:
    """自动检测时间序列粒度"""
    diffs = time_series.diff().dropna()
    median_diff = diffs.median()

    if median_diff <= pd.Timedelta('2D'):
        return 'D'
    elif median_diff <= pd.Timedelta('8D'):
        return 'W'
    elif median_diff <= pd.Timedelta('35D'):
        return 'ME'
    elif median_diff <= pd.Timedelta('100D'):
        return 'QE'
    else:
        return 'YE'


def safe_pct_change(current, previous):
    """安全计算百分比变化，基期为0时返回NaN"""
    if previous == 0 or pd.isna(previous) or pd.isna(current):
        return np.nan
    return (current - previous) / abs(previous) * 100


def calc_cagr(start_val: float, end_val: float, n_years: float) -> float:
    """计算复合年增长率"""
    if start_val <= 0 or end_val <= 0 or n_years <= 0:
        return np.nan
    return ((end_val / start_val) ** (1 / n_years) - 1) * 100


def calc_geometric_mean_growth(series: pd.Series) -> float:
    """
    计算几何平均增长率（适用于波动较大的序列）
    基于各期增长因子的几何平均
    """
    # 计算增长因子（1 + 增长率）
    growth_factors = []
    for i in range(1, len(series)):
        if series.iloc[i - 1] > 0 and series.iloc[i] > 0:
            growth_factors.append(series.iloc[i] / series.iloc[i - 1])

    if not growth_factors:
        return np.nan

    # 几何平均
    log_factors = [np.log(f) for f in growth_factors if f > 0]
    if not log_factors:
        return np.nan

    geo_mean_factor = np.exp(np.mean(log_factors))
    return (geo_mean_factor - 1) * 100


def growth_rate_analysis(df: pd.DataFrame, time_col: str, metric_col: str,
                         freq: str = 'auto') -> pd.DataFrame:
    """
    增长率综合分析

    参数：
        df: 输入数据
        time_col: 时间列名
        metric_col: 指标列名
        freq: 时间粒度（auto/D/W/ME/QE/YE）
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)

    # 检测频率
    if freq == 'auto':
        freq = detect_frequency(df[time_col])
    freq_name = {'D': '日', 'W': '周', 'ME': '月', 'QE': '季', 'YE': '年'}.get(freq, freq)
    print(f"  时间粒度: {freq_name} ({freq})")

    # 按频率聚合
    ts = df.set_index(time_col)[metric_col].resample(freq).sum()
    ts_df = ts.reset_index()
    ts_df.columns = ['日期', '指标值']

    # 环比增长率
    ts_df['环比增长率(%)'] = [np.nan] + [
        safe_pct_change(ts_df['指标值'].iloc[i], ts_df['指标值'].iloc[i - 1])
        for i in range(1, len(ts_df))
    ]

    # 同比增长率（使用 DateOffset 处理闰年等日历问题）
    yoy_offset_map = {
        'D': pd.DateOffset(years=1),
        'W': pd.DateOffset(weeks=52),
        'ME': pd.DateOffset(months=12),
        'QE': pd.DateOffset(months=12),
        'YE': pd.DateOffset(years=1)
    }
    yoy_offset = yoy_offset_map.get(freq, pd.DateOffset(months=12))
    yoy_shift = {'D': 365, 'W': 52, 'ME': 12, 'QE': 4, 'YE': 1}.get(freq, 12)

    if len(ts_df) > yoy_shift:
        yoy_values = []
        for i in range(len(ts_df)):
            target_date = ts_df['日期'].iloc[i] - yoy_offset
            # 在历史数据中查找最接近的日期
            past_mask = ts_df['日期'] <= target_date + pd.Timedelta(days=3)
            past_mask = past_mask & (ts_df['日期'] >= target_date - pd.Timedelta(days=3))
            matched = ts_df[past_mask]
            if len(matched) > 0:
                # 取最接近的一条
                closest_idx = (matched['日期'] - target_date).abs().idxmin()
                yoy_values.append(safe_pct_change(ts_df['指标值'].iloc[i], ts_df.loc[closest_idx, '指标值']))
            else:
                yoy_values.append(np.nan)
        ts_df['同比增长率(%)'] = yoy_values
    else:
        ts_df['同比增长率(%)'] = np.nan
        print(f"  提示: 数据周期不足{yoy_shift}期，无法计算同比增长率")

    # 标记N/A
    ts_df['环比增长率(%)'] = ts_df['环比增长率(%)'].round(2)
    if '同比增长率(%)' in ts_df.columns:
        ts_df['同比增长率(%)'] = ts_df['同比增长率(%)'].round(2)

    # CAGR
    annual = ts.resample('YE').sum()
    cagr = np.nan
    if len(annual) >= 2:
        n_years = (annual.index[-1] - annual.index[0]).days / 365.25
        if n_years > 0:
            cagr = calc_cagr(annual.iloc[0], annual.iloc[-1], n_years)

    # 几何平均增长率
    geo_mean = calc_geometric_mean_growth(ts_df['指标值'])

    # 摘要
    print(f"\n=== 增长率分析结果 ===")
    print(f"  数据范围: {ts_df['日期'].min()} ~ {ts_df['日期'].max()}")
    print(f"  共 {len(ts_df)} 个周期")

    # 最近期环比
    recent_mom = ts_df['环比增长率(%)'].dropna()
    if len(recent_mom) > 0:
        print(f"  最近一期环比增长率: {recent_mom.iloc[-1]:.2f}%")
        print(f"  环比均值: {recent_mom.mean():.2f}%")

    if not np.isnan(cagr):
        print(f"  CAGR（复合年增长率）: {cagr:.2f}%")
    else:
        print(f"  CAGR: 数据不足或存在非正值，无法计算")

    if not np.isnan(geo_mean):
        print(f"  几何平均增长率: {geo_mean:.2f}%（逐期）")

    # 异常增长率警告
    extreme_mom = ts_df[ts_df['环比增长率(%)'].abs() > 500]
    if len(extreme_mom) > 0:
        print(f"\n  警告: 存在 {len(extreme_mom)} 期环比增长率超过500%，可能存在数据异常")
        for _, row in extreme_mom.iterrows():
            print(f"    {row['日期']}: {row['环比增长率(%)']:.2f}%")

    # 添加汇总信息行
    ts_df.loc[len(ts_df)] = ['--- 汇总 ---', ts_df['指标值'].sum(), np.nan, np.nan]

    print(f"\n=== 增长率数据表（最近12期）===")
    display_df = ts_df.tail(13).head(12)  # 不显示汇总行
    print(display_df.to_string(index=False))

    return ts_df, {'cagr': cagr, 'geo_mean_growth': geo_mean}


def main():
    parser = argparse.ArgumentParser(description='增长率计算')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--metric-col', required=True, help='指标列名')
    parser.add_argument('--freq', default='auto',
                        choices=['auto', 'D', 'W', 'ME', 'QE', 'YE'],
                        help='时间粒度（默认: auto自动检测）')
    parser.add_argument('-o', '--output', default='growth_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.metric_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            print(f"可用列: {list(df.columns)}")
            sys.exit(1)

    result_df, summary = growth_rate_analysis(df, args.time_col, args.metric_col, args.freq)

    result_df.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
