#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 PCA PC1 的综合指数构建脚本

利用 PC1 的载荷权重构建加权综合评分，用于多维度指标合成。

用法示例:
    python composite_index.py --input data.csv --features col1,col2,col3
    python composite_index.py --input data.csv --features col1,col2,col3 --normalize minmax
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def build_composite_index(X_scaled, feature_cols, random_state=42):
    """
    构建基于 PC1 载荷的综合指数。

    Parameters
    ----------
    X_scaled : ndarray, 标准化后的数据
    feature_cols : list[str]
    random_state : int

    Returns
    -------
    weights : Series, 各特征的归一化权重
    scores : ndarray, 每个样本的综合指数得分
    pc1_variance_ratio : float, PC1 解释方差比
    loadings : Series, PC1 原始载荷
    """
    pca = PCA(n_components=1, random_state=random_state)
    pc1_scores = pca.fit_transform(X_scaled).ravel()

    loadings = pd.Series(pca.components_[0], index=feature_cols)
    pc1_variance_ratio = pca.explained_variance_ratio_[0]

    # 权重 = 载荷绝对值归一化
    abs_loadings = loadings.abs()
    weights = abs_loadings / abs_loadings.sum()

    # 综合得分 = 标准化数据 * 签名载荷（保留方向）
    scores = X_scaled @ loadings.values

    print(f"\n[结果] 综合指数构建 (基于 PC1):")
    print(f"  PC1 解释方差比: {pc1_variance_ratio*100:.1f}%")
    print(f"\n  PC1 载荷:")
    for feat, load in loadings.sort_values(ascending=False).items():
        direction = "+" if load > 0 else "-"
        print(f"    {feat}: {load:+.4f} (方向: {direction})")

    print(f"\n  归一化权重 (|载荷| / sum(|载荷|)):")
    for feat, w in weights.sort_values(ascending=False).items():
        print(f"    {feat}: {w:.4f} ({w*100:.1f}%)")

    print(f"\n  权重总和: {weights.sum():.4f}")

    return weights, scores, pc1_variance_ratio, loadings


def normalize_scores(scores, method="zscore"):
    """
    对综合指数得分进行标准化。

    Parameters
    ----------
    scores : ndarray
    method : str, 'zscore' 或 'minmax'

    Returns
    -------
    normalized : ndarray
    """
    if method == "minmax":
        s_min, s_max = scores.min(), scores.max()
        if s_max - s_min > 0:
            normalized = (scores - s_min) / (s_max - s_min) * 100
        else:
            normalized = np.full_like(scores, 50.0)
    else:  # zscore
        s_mean, s_std = scores.mean(), scores.std()
        if s_std > 0:
            normalized = (scores - s_mean) / s_std
        else:
            normalized = np.zeros_like(scores)

    return normalized


def main():
    parser = argparse.ArgumentParser(description="综合指数构建: 基于 PCA PC1 载荷的加权评分")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--normalize", default="zscore", choices=["zscore", "minmax"],
                        help="得分标准化方式 (默认 zscore，minmax 映射到 0-100)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    feature_cols = [c.strip() for c in args.features.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)
    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下列不存在: {missing_cols}")
        sys.exit(1)

    # 准备数据
    X = df[feature_cols].copy()
    valid_idx = X.dropna(how="all").index
    X = X.loc[valid_idx]

    if len(X) < 2:
        print("[错误] 有效样本不足。")
        sys.exit(1)

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    # 构建综合指数
    weights, scores, pc1_var, loadings = build_composite_index(
        X_scaled, feature_cols, random_state=args.seed
    )

    # 标准化得分
    normalized = normalize_scores(scores, method=args.normalize)

    # 得分统计
    print(f"\n[结果] 综合指数得分统计 ({args.normalize}):")
    print(f"  最小值: {normalized.min():.4f}")
    print(f"  中位数: {np.median(normalized):.4f}")
    print(f"  均值: {normalized.mean():.4f}")
    print(f"  最大值: {normalized.max():.4f}")
    print(f"  标准差: {normalized.std():.4f}")

    if pc1_var < 0.3:
        print(f"\n[警告] PC1 仅解释 {pc1_var*100:.1f}% 的方差，综合指数的代表性有限。")
        print("  建议检查各特征间的相关结构，或考虑使用多个主成分。")

    # 保存得分
    result_df = df.loc[valid_idx].copy()
    result_df["composite_score_raw"] = scores
    result_df[f"composite_score_{args.normalize}"] = normalized
    score_path = os.path.join(args.output_dir, "composite_index_scores.csv")
    result_df.to_csv(score_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] 综合指数得分已保存: {score_path}")

    # 保存权重表
    weight_df = pd.DataFrame({
        "feature": feature_cols,
        "pc1_loading": [round(loadings[f], 4) for f in feature_cols],
        "abs_loading": [round(abs(loadings[f]), 4) for f in feature_cols],
        "normalized_weight": [round(weights[f], 4) for f in feature_cols],
        "weight_pct": [round(weights[f] * 100, 1) for f in feature_cols],
    }).sort_values("normalized_weight", ascending=False).reset_index(drop=True)

    weight_path = os.path.join(args.output_dir, "composite_index_weights.csv")
    weight_df.to_csv(weight_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 权重表已保存: {weight_path}")

    # 保存元信息
    meta = {
        "pc1_variance_ratio": round(pc1_var, 4),
        "normalize_method": args.normalize,
        "n_features": len(feature_cols),
        "n_samples": len(valid_idx),
    }
    meta_df = pd.DataFrame([meta])
    meta_path = os.path.join(args.output_dir, "composite_index_meta.csv")
    meta_df.to_csv(meta_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 元信息已保存: {meta_path}")

    print("\n[完成] 综合指数构建完毕。")


if __name__ == "__main__":
    main()
