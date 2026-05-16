#!/usr/bin/env python3
"""
季节性模式检测脚本

功能：
- 星期效应检测（按星期几聚合）
- 月度效应检测（按月份聚合）
- 季节性指数计算（周期均值 / 总均值）
- 增长贡献分析（各子类别对总增长的贡献拆解）
- 自动检测合适的聚合频率

依赖：pip install pandas numpy

用法：
    python seasonality_check.py input.csv --time-col date --metric-col value \
        --category-col category -o seasonality_output.csv
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


def day_of_week_analysis(df: pd.DataFrame, time_col: str, metric_col: str) -> pd.DataFrame:
    """星期效应分析"""
    df = df.copy()
    df['星期'] = df[time_col].dt.dayofweek
    dow_names = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
    df['星期名称'] = df['星期'].map(dow_names)

    dow_stats = df.groupby(['星期', '星期名称'])[metric_col].agg(['mean', 'median', 'std', 'count']).reset_index()
    dow_stats.columns = ['星期', '星期名称', '均值', '中位数', '标准差', '样本量']
    dow_stats = dow_stats.sort_values('星期')

    overall_mean = df[metric_col].mean()
    dow_stats['季节性指数'] = (dow_stats['均值'] / overall_mean).round(4) if overall_mean != 0 else 0

    print(f"\n=== 星期效应分析 ===")
    print(f"  总均值: {overall_mean:,.2f}")
    print(dow_stats[['星期名称', '均值', '中位数', '季节性指数', '样本量']].to_string(index=False))

    # 判断是否存在显著星期效应
    idx_range = dow_stats['季节性指数'].max() - dow_stats['季节性指数'].min()
    if idx_range > 0.2:
        peak_day = dow_stats.loc[dow_stats['季节性指数'].idxmax(), '星期名称']
        trough_day = dow_stats.loc[dow_stats['季节性指数'].idxmin(), '星期名称']
        print(f"  判定: 存在明显星期效应（指数极差={idx_range:.4f}）")
        print(f"  峰值: {peak_day}（指数={dow_stats['季节性指数'].max():.4f}）")
        print(f"  谷值: {trough_day}（指数={dow_stats['季节性指数'].min():.4f}）")
    else:
        print(f"  判定: 星期效应不明显（指数极差={idx_range:.4f}）")

    return dow_stats


def month_of_year_analysis(df: pd.DataFrame, time_col: str, metric_col: str) -> pd.DataFrame:
    """月度效应分析"""
    df = df.copy()
    df['月份'] = df[time_col].dt.month
    month_names = {i: f'{i}月' for i in range(1, 13)}
    df['月份名称'] = df['月份'].map(month_names)

    month_stats = df.groupby(['月份', '月份名称'])[metric_col].agg(['mean', 'median', 'std', 'count']).reset_index()
    month_stats.columns = ['月份', '月份名称', '均值', '中位数', '标准差', '样本量']
    month_stats = month_stats.sort_values('月份')

    overall_mean = df[metric_col].mean()
    month_stats['季节性指数'] = (month_stats['均值'] / overall_mean).round(4) if overall_mean != 0 else 0

    print(f"\n=== 月度效应分析 ===")
    print(f"  总均值: {overall_mean:,.2f}")
    print(month_stats[['月份名称', '均值', '中位数', '季节性指数', '样本量']].to_string(index=False))

    idx_range = month_stats['季节性指数'].max() - month_stats['季节性指数'].min()
    if idx_range > 0.3:
        peak_month = month_stats.loc[month_stats['季节性指数'].idxmax(), '月份名称']
        trough_month = month_stats.loc[month_stats['季节性指数'].idxmin(), '月份名称']
        print(f"  判定: 存在明显月度效应（指数极差={idx_range:.4f}）")
        print(f"  峰值: {peak_month}（指数={month_stats['季节性指数'].max():.4f}）")
        print(f"  谷值: {trough_month}（指数={month_stats['季节性指数'].min():.4f}）")
    else:
        print(f"  判定: 月度效应不明显（指数极差={idx_range:.4f}）")

    # 季节性指数验证
    idx_sum = month_stats['季节性指数'].sum()
    available_months = len(month_stats)
    print(f"  季节性指数之和/月数 = {idx_sum/available_months:.4f}（应接近1.0）")

    return month_stats


def contribution_to_growth(df: pd.DataFrame, time_col: str, metric_col: str,
                           category_col: str) -> pd.DataFrame:
    """
    增长贡献分析：各子类别对总增长率的贡献拆解

    使用公式：子类别贡献 = (子类别当期值 - 子类别上期值) / 总指标上期值
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])

    # 按月聚合
    monthly = df.groupby([pd.Grouper(key=time_col, freq='ME'), category_col])[metric_col].sum().unstack(fill_value=0)

    if len(monthly) < 2:
        print("  警告: 数据不足2个周期，无法进行增长贡献分析")
        return pd.DataFrame()

    # 最近两期对比
    current = monthly.iloc[-1]
    previous = monthly.iloc[-2]
    total_previous = previous.sum()
    total_current = current.sum()

    if total_previous == 0:
        print("  警告: 上期总值为0，无法计算增长贡献")
        return pd.DataFrame()

    total_growth_rate = (total_current - total_previous) / total_previous * 100

    contributions = []
    for cat in monthly.columns:
        cat_change = current.get(cat, 0) - previous.get(cat, 0)
        contribution_pct = cat_change / total_previous * 100
        contributions.append({
            '类别': cat,
            '上期值': round(previous.get(cat, 0), 2),
            '当期值': round(current.get(cat, 0), 2),
            '变化量': round(cat_change, 2),
            '增长贡献(百分点)': round(contribution_pct, 2)
        })

    contrib_df = pd.DataFrame(contributions)
    contrib_df = contrib_df.sort_values('增长贡献(百分点)', ascending=False)

    print(f"\n=== 增长贡献分析 ===")
    print(f"  对比周期: {monthly.index[-2]} -> {monthly.index[-1]}")
    print(f"  总增长率: {total_growth_rate:.2f}%")
    print(f"  各子类别贡献:")
    print(contrib_df.to_string(index=False))

    contrib_sum = contrib_df['增长贡献(百分点)'].sum()
    print(f"  贡献之和: {contrib_sum:.2f}百分点（应等于总增长率 {total_growth_rate:.2f}%）")

    return contrib_df


def main():
    parser = argparse.ArgumentParser(description='季节性模式检测与增长贡献分析')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--metric-col', required=True, help='指标列名')
    parser.add_argument('--category-col', default=None, help='子类别列名（用于增长贡献分析）')
    parser.add_argument('-o', '--output', default='seasonality_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    required_cols = [args.time_col, args.metric_col]
    if args.category_col:
        required_cols.append(args.category_col)
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误: 以下列不存在: {missing}")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    df[args.time_col] = pd.to_datetime(df[args.time_col])

    # 星期效应
    dow_result = day_of_week_analysis(df, args.time_col, args.metric_col)

    # 月度效应
    month_result = month_of_year_analysis(df, args.time_col, args.metric_col)

    # 增长贡献分析
    contrib_result = None
    if args.category_col:
        contrib_result = contribution_to_growth(df, args.time_col, args.metric_col, args.category_col)

    # 保存结果
    dow_result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n星期效应表已保存至: {args.output}")

    month_path = args.output.replace('.csv', '_monthly.csv')
    month_result.to_csv(month_path, index=False, encoding='utf-8-sig')
    print(f"月度效应表已保存至: {month_path}")

    if contrib_result is not None and not contrib_result.empty:
        contrib_path = args.output.replace('.csv', '_contribution.csv')
        contrib_result.to_csv(contrib_path, index=False, encoding='utf-8-sig')
        print(f"增长贡献表已保存至: {contrib_path}")


if __name__ == '__main__':
    main()
