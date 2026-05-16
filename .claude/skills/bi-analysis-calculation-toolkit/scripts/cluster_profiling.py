#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚类群体特征画像脚本

读取带有聚类标签的数据，计算各簇的特征统计量和 z-score 偏差，
识别各簇的显著特征。

用法示例:
    python cluster_profiling.py --input cluster_labels.csv --features col1,col2,col3 --cluster-col cluster
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def compute_cluster_profile(df, feature_cols, cluster_col="cluster"):
    """
    计算各簇的特征画像。

    Parameters
    ----------
    df : DataFrame
    feature_cols : list[str]
    cluster_col : str

    Returns
    -------
    profile_df : DataFrame, 各簇各特征的统计量
    zscore_df : DataFrame, 各簇各特征相对全局均值的 z-score
    """
    if cluster_col not in df.columns:
        raise ValueError(f"聚类标签列 '{cluster_col}' 不存在。")

    # 排除噪声点
    df_valid = df[df[cluster_col] != -1].copy()
    if len(df_valid) == 0:
        raise ValueError("无有效聚类数据（全为噪声点）。")

    # 全局统计
    global_mean = df_valid[feature_cols].mean()
    global_std = df_valid[feature_cols].std()

    # 各簇统计
    records = []
    zscore_records = []

    clusters = sorted(df_valid[cluster_col].unique())
    total_n = len(df_valid)

    for cls in clusters:
        cluster_data = df_valid[df_valid[cluster_col] == cls][feature_cols]
        n = len(cluster_data)
        pct = n / total_n * 100

        row = {"cluster": cls, "sample_count": n, "percentage": round(pct, 1)}
        zscore_row = {"cluster": cls}

        for col in feature_cols:
            col_data = cluster_data[col].dropna()
            row[f"{col}_mean"] = round(col_data.mean(), 4) if len(col_data) > 0 else np.nan
            row[f"{col}_std"] = round(col_data.std(), 4) if len(col_data) > 1 else np.nan
            row[f"{col}_median"] = round(col_data.median(), 4) if len(col_data) > 0 else np.nan

            # z-score: (簇均值 - 全局均值) / 全局标准差
            if global_std[col] > 0 and len(col_data) > 0:
                z = (col_data.mean() - global_mean[col]) / global_std[col]
                zscore_row[col] = round(z, 4)
            else:
                zscore_row[col] = 0.0

        records.append(row)
        zscore_records.append(zscore_row)

    profile_df = pd.DataFrame(records)
    zscore_df = pd.DataFrame(zscore_records)

    return profile_df, zscore_df


def identify_significant_features(zscore_df, feature_cols, threshold=1.0):
    """
    标记每个簇的显著特征（z-score 绝对值 > threshold）。

    Returns
    -------
    sig_df : DataFrame, 每个簇的显著特征列表
    """
    records = []
    for _, row in zscore_df.iterrows():
        cluster_id = row["cluster"]
        sig_features = []
        for col in feature_cols:
            z = row.get(col, 0)
            if abs(z) > threshold:
                direction = "高" if z > 0 else "低"
                sig_features.append(f"{col}({direction}, z={z:.2f})")
        records.append({
            "cluster": cluster_id,
            "significant_features": "; ".join(sig_features) if sig_features else "无显著偏离",
            "n_significant": len(sig_features),
        })

    sig_df = pd.DataFrame(records)
    return sig_df


def compute_cluster_size_stats(df, cluster_col="cluster"):
    """计算簇规模统计。"""
    counts = df[df[cluster_col] != -1][cluster_col].value_counts().sort_index()
    total = counts.sum()
    noise_n = (df[cluster_col] == -1).sum()

    size_df = pd.DataFrame({
        "cluster": counts.index,
        "sample_count": counts.values,
        "percentage": (counts.values / total * 100).round(1),
    })

    if noise_n > 0:
        noise_row = pd.DataFrame([{
            "cluster": -1,
            "sample_count": noise_n,
            "percentage": round(noise_n / len(df) * 100, 1),
        }])
        size_df = pd.concat([size_df, noise_row], ignore_index=True)

    return size_df


def main():
    parser = argparse.ArgumentParser(description="聚类群体特征画像与 z-score 偏差分析")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (需含聚类标签列)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--cluster-col", default="cluster", help="聚类标签列名 (默认 cluster)")
    parser.add_argument("--z-threshold", type=float, default=1.0, help="显著特征 z-score 阈值 (默认 1.0)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    feature_cols = [c.strip() for c in args.features.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)
    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    missing_cols = [c for c in feature_cols + [args.cluster_col] if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下列不存在: {missing_cols}")
        sys.exit(1)

    # 簇规模统计
    size_df = compute_cluster_size_stats(df, args.cluster_col)
    print(f"\n[结果] 簇规模统计:")
    print(size_df.to_string(index=False))

    # 特征画像
    profile_df, zscore_df = compute_cluster_profile(df, feature_cols, args.cluster_col)

    print(f"\n[结果] 各簇特征均值画像:")
    mean_cols = ["cluster", "sample_count", "percentage"] + [f"{c}_mean" for c in feature_cols]
    available_cols = [c for c in mean_cols if c in profile_df.columns]
    print(profile_df[available_cols].to_string(index=False))

    print(f"\n[结果] 各簇 z-score 偏差 (相对全局均值):")
    print(zscore_df.to_string(index=False))

    # 显著特征
    sig_df = identify_significant_features(zscore_df, feature_cols, threshold=args.z_threshold)
    print(f"\n[结果] 各簇显著特征 (|z-score| > {args.z_threshold}):")
    print(sig_df.to_string(index=False))

    # 保存
    profile_path = os.path.join(args.output_dir, "cluster_profile.csv")
    profile_df.to_csv(profile_path, index=False)
    print(f"\n[输出] 特征画像已保存: {profile_path}")

    zscore_path = os.path.join(args.output_dir, "cluster_zscore.csv")
    zscore_df.to_csv(zscore_path, index=False)
    print(f"[输出] z-score 偏差表已保存: {zscore_path}")

    sig_path = os.path.join(args.output_dir, "cluster_significant_features.csv")
    sig_df.to_csv(sig_path, index=False)
    print(f"[输出] 显著特征表已保存: {sig_path}")

    size_path = os.path.join(args.output_dir, "cluster_sizes.csv")
    size_df.to_csv(size_path, index=False)
    print(f"[输出] 簇规模表已保存: {size_path}")

    print("\n[完成] 聚类群体画像分析完毕。")


if __name__ == "__main__":
    main()
