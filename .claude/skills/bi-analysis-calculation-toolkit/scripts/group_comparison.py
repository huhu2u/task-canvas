#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分组对比分析脚本

按分类字段分组，对每个组内分别计算统计指标，输出分组统计对比表 CSV。

用法示例:
    python group_comparison.py --input data.csv --columns col1,col2 --group-by category
    python group_comparison.py --input data.csv --columns col1 --group-by region --output-dir output/
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def compute_group_stats(series):
    """
    为一个分组的数据序列计算全套统计指标。

    Parameters
    ----------
    series : Series, 已去除 NaN 的数据序列

    Returns
    -------
    dict : 统计指标字典
    """
    s = series.dropna()
    n = len(s)

    if n == 0:
        return {"样本量": 0}

    mean_val = float(s.mean())
    std_val = float(s.std()) if n > 1 else 0.0

    result = {
        "样本量": n,
        "均值": round(mean_val, 6),
        "中位数": round(float(s.median()), 6),
        "标准差": round(std_val, 6),
    }

    # 变异系数
    if abs(mean_val) > 1e-10:
        result["变异系数CV(%)"] = round(std_val / abs(mean_val) * 100, 4)
    else:
        result["变异系数CV(%)"] = None

    # 分位数
    result["P25(Q1)"] = round(float(s.quantile(0.25)), 6)
    result["P75(Q3)"] = round(float(s.quantile(0.75)), 6)
    result["IQR"] = round(float(s.quantile(0.75) - s.quantile(0.25)), 6)
    result["最小值"] = round(float(s.min()), 6)
    result["最大值"] = round(float(s.max()), 6)

    # 偏度和峰度（需要至少3个样本）
    if n >= 3:
        result["偏度"] = round(float(s.skew()), 4)
        result["峰度"] = round(float(s.kurtosis()), 4)
    else:
        result["偏度"] = None
        result["峰度"] = None

    # 截尾均值
    if n >= 20:
        result["截尾均值(5%)"] = round(float(stats.trim_mean(s, 0.05)), 6)
    else:
        result["截尾均值(5%)"] = round(mean_val, 6)

    return result


def group_comparison(df, cols, group_col):
    """
    按分组字段对多个数值列进行统计对比。

    Parameters
    ----------
    df : DataFrame
    cols : list[str], 数值列名列表
    group_col : str, 分组字段名

    Returns
    -------
    DataFrame : 分组统计对比表
    """
    groups = df[group_col].dropna().unique()
    groups = sorted(groups, key=str)

    print(f"[信息] 分组字段 '{group_col}' 共有 {len(groups)} 个组: {list(groups)}")

    rows = []
    for col in cols:
        for grp in groups:
            mask = df[group_col] == grp
            s = df.loc[mask, col]

            row = {
                "字段": col,
                "分组": str(grp),
            }
            row.update(compute_group_stats(s))
            rows.append(row)

    return pd.DataFrame(rows)


def compute_overall_comparison(df, cols, group_col):
    """
    计算组间差异汇总：每个字段的各组关键指标对比。

    Returns
    -------
    DataFrame : 组间差异汇总表
    """
    groups = sorted(df[group_col].dropna().unique(), key=str)
    rows = []

    for col in cols:
        row = {"字段": col}

        # 各组均值
        group_means = {}
        group_data = []
        for grp in groups:
            s = df.loc[df[group_col] == grp, col].dropna()
            group_means[f"均值_{grp}"] = round(float(s.mean()), 6) if len(s) > 0 else None
            if len(s) > 0:
                group_data.append(s.values)

        row.update(group_means)

        # 组间均值差距
        mean_vals = [v for v in group_means.values() if v is not None]
        if len(mean_vals) >= 2:
            row["均值极差"] = round(max(mean_vals) - min(mean_vals), 6)
        else:
            row["均值极差"] = None

        # Kruskal-Wallis 检验（非参数 ANOVA，适用性更广）
        if len(group_data) >= 2 and all(len(g) >= 2 for g in group_data):
            try:
                stat, p_value = stats.kruskal(*group_data)
                row["Kruskal-Wallis统计量"] = round(float(stat), 4)
                row["Kruskal-Wallis_p值"] = round(float(p_value), 6)
                row["组间差异显著"] = "是" if p_value < 0.05 else "否"
            except Exception:
                row["Kruskal-Wallis统计量"] = None
                row["Kruskal-Wallis_p值"] = None
                row["组间差异显著"] = "无法计算"
        else:
            row["Kruskal-Wallis统计量"] = None
            row["Kruskal-Wallis_p值"] = None
            row["组间差异显著"] = "样本不足"

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="分组对比分析: 按分类字段分组计算统计指标并对比"
    )
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--columns", required=True, help="目标数值列名，逗号分隔")
    parser.add_argument("--group-by", required=True, help="分组字段名（分类变量）")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    cols = [c.strip() for c in args.columns.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    try:
        df = load_data(args.input)
    except FileNotFoundError:
        print(f"[错误] 文件不存在: {args.input}")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] 文件读取失败: {e}")
        sys.exit(1)

    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    # 验证列
    missing_cols = [c for c in cols if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下数值列不存在: {missing_cols}")
        sys.exit(1)

    if args.group_by not in df.columns:
        print(f"[错误] 分组字段不存在: '{args.group_by}'")
        sys.exit(1)

    group_col = args.group_by

    # 检查分组字段
    n_groups = df[group_col].nunique()
    if n_groups < 2:
        print(f"[错误] 分组字段 '{group_col}' 只有 {n_groups} 个唯一值，至少需要2个组。")
        sys.exit(1)

    if n_groups > 50:
        print(f"[警告] 分组字段 '{group_col}' 有 {n_groups} 个唯一值，分组过多可能影响结果可读性。")

    # 分组统计
    print(f"\n[信息] 开始分组统计...")
    group_stats_df = group_comparison(df, cols, group_col)

    # 控制台输出
    print(f"\n[结果] 分组统计对比表:")
    print(group_stats_df.to_string(index=False))

    # 保存分组统计
    group_path = os.path.join(args.output_dir, "group_comparison.csv")
    group_stats_df.to_csv(group_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] 分组统计表已保存: {group_path}")

    # 组间差异汇总
    print(f"\n[信息] 计算组间差异汇总...")
    comparison_df = compute_overall_comparison(df, cols, group_col)
    print(f"\n[结果] 组间差异汇总:")
    print(comparison_df.to_string(index=False))

    comparison_path = os.path.join(args.output_dir, "group_comparison_summary.csv")
    comparison_df.to_csv(comparison_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 组间差异汇总已保存: {comparison_path}")

    # 显著性结论
    sig_fields = comparison_df[comparison_df.get("组间差异显著") == "是"]["字段"].tolist()
    nonsig_fields = comparison_df[comparison_df.get("组间差异显著") == "否"]["字段"].tolist()

    if sig_fields:
        print(f"\n[结论] 以下字段在组间存在显著差异 (p<0.05): {sig_fields}")
    if nonsig_fields:
        print(f"[结论] 以下字段在组间无显著差异 (p>=0.05): {nonsig_fields}")

    print("\n[完成] 分组对比分析完毕。")


if __name__ == "__main__":
    main()
