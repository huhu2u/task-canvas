#!/usr/bin/env python3
"""
相关性筛选脚本 - Pearson/Spearman/互信息三方法综合评估

功能：
  - 计算每个特征与目标变量的 Pearson r、Spearman rho、互信息 MI
  - 综合加权评分排序
  - 检测非线性关系（|Spearman| - |Pearson| > 0.1 时标记）
  - 结果输出到 CSV 和控制台

用法：
  python correlation_screening.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
from scipy import stats


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


def correlation_screening(df, target_col, feature_cols):
    """
    三种相关性方法综合评估。

    参数：
      df:           DataFrame
      target_col:   目标变量列名
      feature_cols: 候选特征列名列表

    返回：
      DataFrame — 相关性筛查结果，按综合重要性降序排列
    """
    from sklearn.feature_selection import mutual_info_regression, mutual_info_classif

    target = df[target_col].dropna()
    is_continuous = target.nunique() > 10
    results = []

    for col in feature_cols:
        if col not in df.columns:
            print(f"警告：特征 '{col}' 不在数据中，跳过")
            continue

        feature = df[col].dropna()
        common_idx = target.index.intersection(feature.index)
        if len(common_idx) < 10:
            print(f"警告：特征 '{col}' 与目标变量的有效样本数不足（{len(common_idx)}），跳过")
            continue

        t = target.loc[common_idx]
        f = feature.loc[common_idx]

        row = {"特征": col}

        # Pearson 相关（线性）
        try:
            pearson_r, pearson_p = stats.pearsonr(f, t)
            row["Pearson_r"] = round(pearson_r, 4)
            row["Pearson_p"] = round(pearson_p, 6)
        except Exception:
            row["Pearson_r"] = None
            row["Pearson_p"] = None

        # Spearman 相关（秩相关，捕获单调非线性）
        try:
            spearman_r, spearman_p = stats.spearmanr(f, t)
            row["Spearman_r"] = round(spearman_r, 4)
            row["Spearman_p"] = round(spearman_p, 6)
        except Exception:
            row["Spearman_r"] = None
            row["Spearman_p"] = None

        # 互信息（任意关系，包括非线性）
        try:
            X_single = f.values.reshape(-1, 1)
            mi_func = mutual_info_regression if is_continuous else mutual_info_classif
            mi_score = mi_func(X_single, t.values, random_state=42)[0]
            row["MI"] = round(mi_score, 4)
        except Exception:
            row["MI"] = None

        # 非线性关系检测
        abs_pearson = abs(row["Pearson_r"]) if row["Pearson_r"] is not None else 0
        abs_spearman = abs(row["Spearman_r"]) if row["Spearman_r"] is not None else 0
        gap = abs_spearman - abs_pearson
        row["Spearman-Pearson差"] = round(gap, 4)
        row["非线性标记"] = "是" if gap > 0.1 else "否"

        results.append(row)

    corr_df = pd.DataFrame(results)

    if corr_df.empty:
        print("错误：没有有效的特征可供分析")
        return corr_df

    # 综合重要性评分
    mi_max = corr_df["MI"].max() if corr_df["MI"].max() > 0 else 1
    corr_df["综合重要性"] = (
        corr_df["Pearson_r"].abs().fillna(0) * 0.3 +
        corr_df["Spearman_r"].abs().fillna(0) * 0.3 +
        corr_df["MI"].fillna(0) / mi_max * 0.4
    ).round(4)
    corr_df = corr_df.sort_values("综合重要性", ascending=False)

    print(f"\n{'='*70}")
    print(f"  相关性筛查结果（按综合重要性排序）")
    print(f"{'='*70}")
    print(corr_df.to_string(index=False))

    # 非线性关系提示
    nonlinear = corr_df[corr_df["非线性标记"] == "是"]
    if len(nonlinear) > 0:
        print(f"\n检测到 {len(nonlinear)} 个潜在非线性关系特征：")
        for _, r in nonlinear.iterrows():
            print(f"  - {r['特征']}: |Spearman|-|Pearson| = {r['Spearman-Pearson差']:.4f}")

    return corr_df


def main():
    parser = argparse.ArgumentParser(
        description="Pearson/Spearman/互信息 三方法相关性筛选",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="候选特征列名列表")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    # 验证列名
    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    corr_df = correlation_screening(df, args.target, args.features)

    if not corr_df.empty:
        out_path = os.path.join(args.output_dir, "correlation_screening.csv")
        corr_df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"\n结果已保存至: {out_path}")


if __name__ == "__main__":
    main()
