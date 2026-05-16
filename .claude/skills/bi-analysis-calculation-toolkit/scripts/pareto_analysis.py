#!/usr/bin/env python3
"""
帕累托（80/20）分析脚本

功能：
- 按指定维度和度量进行帕累托排序
- 计算各分组占比和累计占比
- 标记贡献阈值（默认80%）的分界点
- 计算集中度比
- 输出帕累托分析表

用法：
    python pareto_analysis.py input.csv --group-col col1 --metric-col metric1 \
        --threshold 80 -o pareto_output.csv
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


def calc_hhi(shares: pd.Series) -> float:
    """计算HHI指数"""
    return float((shares ** 2).sum())


def calc_gini(values: pd.Series) -> float:
    """计算基尼系数"""
    values = np.sort(values.values.astype(float))
    n = len(values)
    if n == 0 or values.sum() == 0:
        return 0.0
    index = np.arange(1, n + 1)
    gini = (2.0 * np.sum(index * values) / (n * values.sum())) - (n + 1) / n
    return max(0.0, min(1.0, float(gini)))


def pareto_analysis(df: pd.DataFrame, group_col: str, metric_col: str,
                    threshold: float = 80.0) -> pd.DataFrame:
    """
    帕累托分析

    参数：
        df: 输入数据
        group_col: 分组维度列
        metric_col: 度量指标列
        threshold: 累计占比阈值（默认80%）

    返回：
        帕累托分析结果DataFrame
    """
    # 分组汇总
    grouped = df.groupby(group_col)[metric_col].sum().reset_index()
    grouped = grouped.sort_values(metric_col, ascending=False).reset_index(drop=True)

    total = grouped[metric_col].sum()
    if total == 0:
        print("警告: 度量指标合计为0，无法进行帕累托分析")
        return grouped

    # 计算占比和累计占比
    grouped['占比(%)'] = (grouped[metric_col] / total * 100).round(4)
    grouped['累计占比(%)'] = grouped['占比(%)'].cumsum().round(4)
    grouped['排名'] = range(1, len(grouped) + 1)

    # 标记阈值分界
    grouped['阈值内'] = grouped['累计占比(%)'] <= threshold
    cutoff_count = grouped['阈值内'].sum()
    # 如果没有一个分组就超过阈值，至少包含第一个
    if cutoff_count == 0:
        cutoff_count = 1

    # 实际可能需要多一个分组才刚好超过阈值
    if cutoff_count < len(grouped):
        cutoff_count += 1
    cutoff_count = min(cutoff_count, len(grouped))

    # 集中度指标
    shares = grouped[metric_col] / total * 100
    hhi = calc_hhi(shares)
    gini = calc_gini(grouped[metric_col])

    # 输出摘要
    print(f"\n=== 帕累托分析结果 ===")
    print(f"  分组维度: {group_col}")
    print(f"  度量指标: {metric_col}")
    print(f"  总计: {total:,.2f}")
    print(f"  分组数量: {len(grouped)}")
    print(f"  阈值设定: {threshold}%")
    print(f"  贡献 {threshold}% 的分组数: {cutoff_count}")
    print(f"  集中度比: {cutoff_count/len(grouped)*100:.1f}% 的分组贡献了 {threshold}% 的价值")
    print(f"  HHI指数: {hhi:.2f}")
    print(f"  基尼系数: {gini:.4f}")

    # 头部摘要
    print(f"\n=== 头部分组（Top-5）===")
    top5 = grouped.head(5)
    for _, row in top5.iterrows():
        print(f"  排名{int(row['排名'])}: {row[group_col]} = {row[metric_col]:,.2f} "
              f"({row['占比(%)']:.2f}%, 累计{row['累计占比(%)']:.2f}%)")

    # 尾部摘要
    if len(grouped) > 5:
        tail_groups = grouped.iloc[cutoff_count:]
        if len(tail_groups) > 0:
            tail_total = tail_groups[metric_col].sum()
            tail_pct = tail_total / total * 100
            print(f"\n=== 尾部分析 ===")
            print(f"  阈值外分组数: {len(tail_groups)}")
            print(f"  阈值外合计贡献: {tail_pct:.2f}%")

    print(f"\n=== 完整帕累托表 ===")
    print(grouped.to_string(index=False))

    return grouped


def main():
    parser = argparse.ArgumentParser(description='帕累托（80/20）分析')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--group-col', required=True, help='分组维度列名')
    parser.add_argument('--metric-col', required=True, help='度量指标列名')
    parser.add_argument('--threshold', type=float, default=80.0,
                        help='累计占比阈值（默认: 80）')
    parser.add_argument('-o', '--output', default='pareto_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    # 验证列
    for col in [args.group_col, args.metric_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在于数据中")
            print(f"可用列: {list(df.columns)}")
            sys.exit(1)

    result = pareto_analysis(df, args.group_col, args.metric_col, args.threshold)

    result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
