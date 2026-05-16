#!/usr/bin/env python3
"""
维度下钻与贡献度分析脚本

功能：
  - 逐层下钻，将总指标波动定位到具体维度
  - 计算各维度的绝对变化、增长率、贡献度、百分点拉动
  - 支持多级交叉维度下钻（如维度A x 维度B），计算交叉组合贡献

用法：
  python dimension_drilldown.py <数据文件路径> \
    --metric <目标指标列名> \
    --dims <维度列1> <维度列2> ... \
    [--cross-dims <交叉维度1> <交叉维度2>] \
    [--base-file <基准期数据文件>] \
    [--time-col <时间列名>] \
    [--current-period <当前期值>] \
    [--base-period <基准期值>] \
    [--output-dir <输出目录>]

输出：
  drilldown_results.csv       — 各单维度的详细分析结果
  cross_drilldown_results.csv — 交叉维度分析结果（若指定 --cross-dims）
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np


def load_data(file_path):
    """加载 CSV 或 Excel 文件"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    elif ext == '.csv':
        return pd.read_csv(file_path)
    else:
        try:
            return pd.read_csv(file_path)
        except Exception:
            return pd.read_excel(file_path)


def dimension_drilldown(df_current, df_base, dim_cols, metric_col):
    """
    逐层下钻：按维度列表依次聚合，计算各维度的绝对变化、增长率、贡献度和百分点拉动。

    参数：
      df_current: 当前期 DataFrame
      df_base:    基准期 DataFrame
      dim_cols:   下钻维度列名列表，按层级顺序排列
      metric_col: 目标指标列名

    返回：
      dict[str, DataFrame] — 各维度的分析结果
    """
    results = {}

    # 计算总量用于百分点拉动
    total_base = df_base[metric_col].sum()
    total_current = df_current[metric_col].sum()
    total_change = total_current - total_base

    print(f"\n指标总览: 基准期={total_base:,.2f}, 当前期={total_current:,.2f}, "
          f"总变化={total_change:+,.2f}")

    for i, dim in enumerate(dim_cols):
        curr_agg = df_current.groupby(dim)[metric_col].sum().reset_index()
        base_agg = df_base.groupby(dim)[metric_col].sum().reset_index()

        merged = curr_agg.merge(
            base_agg, on=dim, suffixes=("_当前", "_基准"), how="outer"
        ).fillna(0)

        merged["绝对变化"] = merged[f"{metric_col}_当前"] - merged[f"{metric_col}_基准"]
        merged["增长率(%)"] = np.where(
            merged[f"{metric_col}_基准"] != 0,
            (merged["绝对变化"] / merged[f"{metric_col}_基准"] * 100).round(2),
            np.nan
        )
        merged = merged.sort_values("绝对变化")

        # 贡献度（占总变化的百分比）
        if total_change != 0:
            merged["贡献度(%)"] = (merged["绝对变化"] / abs(total_change) * 100).round(2)
        else:
            merged["贡献度(%)"] = 0

        # 百分点拉动（各维度绝对变化占基准期总量的百分点）
        if total_base != 0:
            merged["百分点拉动(pp)"] = (merged["绝对变化"] / abs(total_base) * 100).round(2)
        else:
            merged["百分点拉动(pp)"] = 0

        results[dim] = merged

        print(f"\n{'='*70}")
        print(f"  {dim} 维度拆解（总变化：{total_change:+,.2f}）")
        print(f"{'='*70}")
        display_cols = [dim, f"{metric_col}_基准", f"{metric_col}_当前",
                        "绝对变化", "增长率(%)", "贡献度(%)", "百分点拉动(pp)"]
        print(merged[display_cols].to_string(index=False))

    return results


def cross_dimension_drilldown(df_current, df_base, cross_dims, metric_col):
    """
    交叉维度下钻：按多个维度的组合聚合，计算交叉组合的贡献度。

    参数：
      df_current: 当前期 DataFrame
      df_base:    基准期 DataFrame
      cross_dims: 交叉维度列名列表（如 ["维度A", "维度B"]）
      metric_col: 目标指标列名

    返回：
      DataFrame — 交叉维度分析结果
    """
    total_base = df_base[metric_col].sum()
    total_current = df_current[metric_col].sum()
    total_change = total_current - total_base

    curr_agg = df_current.groupby(cross_dims)[metric_col].sum().reset_index()
    base_agg = df_base.groupby(cross_dims)[metric_col].sum().reset_index()

    merged = curr_agg.merge(
        base_agg, on=cross_dims, suffixes=("_当前", "_基准"), how="outer"
    ).fillna(0)

    merged["绝对变化"] = merged[f"{metric_col}_当前"] - merged[f"{metric_col}_基准"]
    merged["增长率(%)"] = np.where(
        merged[f"{metric_col}_基准"] != 0,
        (merged["绝对变化"] / merged[f"{metric_col}_基准"] * 100).round(2),
        np.nan
    )

    if total_change != 0:
        merged["贡献度(%)"] = (merged["绝对变化"] / abs(total_change) * 100).round(2)
    else:
        merged["贡献度(%)"] = 0

    if total_base != 0:
        merged["百分点拉动(pp)"] = (merged["绝对变化"] / abs(total_base) * 100).round(2)
    else:
        merged["百分点拉动(pp)"] = 0

    merged = merged.sort_values("绝对变化")

    cross_label = " x ".join(cross_dims)
    print(f"\n{'='*70}")
    print(f"  交叉维度下钻: {cross_label}（总变化：{total_change:+,.2f}）")
    print(f"{'='*70}")
    display_cols = cross_dims + [f"{metric_col}_基准", f"{metric_col}_当前",
                                  "绝对变化", "增长率(%)", "贡献度(%)", "百分点拉动(pp)"]
    print(merged[display_cols].to_string(index=False))

    return merged


def save_results(results, metric_col, output_path):
    """将所有单维度分析结果保存为 CSV"""
    all_dfs = []
    for dim, df in results.items():
        df_out = df.copy()
        df_out.insert(0, "维度名称", dim)
        df_out = df_out.rename(columns={dim: "维度值"})
        all_dfs.append(df_out)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n单维度分析结果已保存至: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="维度下钻与贡献度分析",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--metric", required=True, help="目标指标列名")
    parser.add_argument("--dims", required=True, nargs="+", help="下钻维度列名列表")
    parser.add_argument("--cross-dims", nargs="+", default=None,
                        help="交叉维度列名列表（如 维度A 维度B）")
    parser.add_argument("--base-file", help="基准期数据文件（独立文件模式）")
    parser.add_argument("--time-col", help="时间列名（同文件拆分模式）")
    parser.add_argument("--current-period", help="当前期值")
    parser.add_argument("--base-period", help="基准期值")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    # 加载数据
    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    # 验证列名
    all_dims = args.dims + (args.cross_dims if args.cross_dims else [])
    missing_cols = [c for c in [args.metric] + all_dims if c not in df.columns]
    if missing_cols:
        print(f"错误：以下列名在数据中不存在: {missing_cols}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    # 拆分当前期和基准期
    if args.base_file:
        df_current = df
        df_base = load_data(args.base_file)
        print(f"已加载基准期数据: {df_base.shape[0]} 行 x {df_base.shape[1]} 列")
    elif args.time_col and args.current_period and args.base_period:
        if args.time_col not in df.columns:
            print(f"错误：时间列 '{args.time_col}' 不在数据中")
            sys.exit(1)
        df[args.time_col] = df[args.time_col].astype(str)
        df_current = df[df[args.time_col] == str(args.current_period)]
        df_base = df[df[args.time_col] == str(args.base_period)]
        if df_current.empty:
            print(f"错误：当前期 '{args.current_period}' 无匹配数据。"
                  f"可用值: {df[args.time_col].unique().tolist()}")
            sys.exit(1)
        if df_base.empty:
            print(f"错误：基准期 '{args.base_period}' 无匹配数据。"
                  f"可用值: {df[args.time_col].unique().tolist()}")
            sys.exit(1)
        print(f"当前期数据: {df_current.shape[0]} 行 | 基准期数据: {df_base.shape[0]} 行")
    else:
        print("错误：请指定 --base-file 或同时指定 --time-col、--current-period、--base-period")
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 执行单维度下钻分析
    results = dimension_drilldown(df_current, df_base, args.dims, args.metric)

    # 保存单维度结果
    csv_path = os.path.join(args.output_dir, "drilldown_results.csv")
    save_results(results, args.metric, csv_path)

    # 执行交叉维度下钻（若指定）
    if args.cross_dims and len(args.cross_dims) >= 2:
        cross_result = cross_dimension_drilldown(
            df_current, df_base, args.cross_dims, args.metric
        )
        cross_path = os.path.join(args.output_dir, "cross_drilldown_results.csv")
        cross_result.to_csv(cross_path, index=False, encoding='utf-8-sig')
        print(f"交叉维度分析结果已保存至: {cross_path}")


if __name__ == "__main__":
    main()
