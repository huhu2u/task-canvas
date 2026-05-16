#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCA 主成分分析脚本

支持自动组件选择（累计方差阈值 / Kaiser 准则 / 平行分析），
输出载荷矩阵、方差解释比、降维坐标。

用法示例:
    python pca_analysis.py --input data.csv --features col1,col2,col3
    python pca_analysis.py --input data.csv --features col1,col2,col3 --variance-target 0.95
    python pca_analysis.py --input data.csv --features col1,col2 --n-components 3
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def parallel_analysis(X_scaled, n_iterations=100, percentile=95, random_state=42):
    """
    平行分析：生成随机数据并比较特征值，确定要保留的主成分数。

    Parameters
    ----------
    X_scaled : ndarray, 标准化后的数据
    n_iterations : int, 随机迭代次数
    percentile : int, 随机特征值的百分位阈值
    random_state : int

    Returns
    -------
    n_components : int, 建议保留的主成分数
    real_eigenvalues : ndarray
    random_eigenvalues : ndarray (百分位)
    """
    rng = np.random.RandomState(random_state)
    n_samples, n_features = X_scaled.shape

    # 真实数据特征值
    pca = PCA(random_state=random_state)
    pca.fit(X_scaled)
    real_eigenvalues = pca.explained_variance_

    # 随机数据特征值
    random_eigenvalues_all = np.zeros((n_iterations, n_features))
    for i in range(n_iterations):
        X_random = rng.normal(size=(n_samples, n_features))
        pca_random = PCA()
        pca_random.fit(X_random)
        random_eigenvalues_all[i] = pca_random.explained_variance_

    random_eigenvalues = np.percentile(random_eigenvalues_all, percentile, axis=0)

    # 保留真实特征值 > 随机特征值的主成分
    n_components = 0
    for i in range(n_features):
        if real_eigenvalues[i] > random_eigenvalues[i]:
            n_components += 1
        else:
            break

    n_components = max(1, n_components)
    return n_components, real_eigenvalues, random_eigenvalues


def run_pca_analysis(X_scaled, feature_cols, n_components=None, variance_target=0.90, random_state=42):
    """
    执行 PCA 分析。

    Returns
    -------
    pca_model : PCA
    loadings_df : DataFrame (特征 x 主成分)
    variance_df : DataFrame
    scores : ndarray (样本 x 主成分)
    component_selection : dict
    """
    n_features = X_scaled.shape[1]

    # 全量 PCA
    pca_full = PCA(random_state=random_state)
    pca_full.fit(X_scaled)

    eigenvalues = pca_full.explained_variance_
    cumvar = np.cumsum(pca_full.explained_variance_ratio_)

    # === 三种准则 ===
    # 1. 累计方差阈值
    variance_n = int(np.searchsorted(cumvar, variance_target) + 1)
    variance_n = min(variance_n, n_features)

    # 2. Kaiser 准则 (特征值 > 1)
    # 注意：标准化数据的特征值均值为 1，所以 Kaiser 准则 = 特征值 > 1
    kaiser_n = int((eigenvalues > 1.0).sum())
    kaiser_n = max(1, kaiser_n)

    # 3. 平行分析
    parallel_n, real_eig, random_eig = parallel_analysis(X_scaled, random_state=random_state)

    component_selection = {
        "variance_threshold": {"n_components": variance_n, "target": variance_target,
                               "actual_variance": round(float(cumvar[variance_n - 1]), 4)},
        "kaiser": {"n_components": kaiser_n, "criterion": "eigenvalue > 1"},
        "parallel_analysis": {"n_components": parallel_n},
    }

    print(f"\n[结果] 主成分数量选择:")
    print(f"  累计方差 >= {variance_target*100:.0f}%: 需要 {variance_n} 个主成分 (实际 {cumvar[variance_n-1]*100:.1f}%)")
    print(f"  Kaiser 准则 (特征值 > 1): {kaiser_n} 个主成分")
    print(f"  平行分析: {parallel_n} 个主成分")

    # 确定最终主成分数
    if n_components is not None:
        final_n = n_components
        print(f"  用户指定: {final_n} 个主成分")
    else:
        final_n = variance_n
        print(f"  最终选择 (基于方差阈值): {final_n} 个主成分")

    final_n = min(final_n, n_features, X_scaled.shape[0])

    # 正式 PCA
    pca_model = PCA(n_components=final_n, random_state=random_state)
    scores = pca_model.fit_transform(X_scaled)

    # 载荷矩阵
    loadings_df = pd.DataFrame(
        pca_model.components_.T,
        index=feature_cols,
        columns=[f"PC{i+1}" for i in range(final_n)]
    ).round(4)

    print(f"\n[结果] 主成分载荷矩阵:")
    print(loadings_df.to_string())

    # 方差解释比表
    variance_records = []
    for i in range(final_n):
        variance_records.append({
            "component": f"PC{i+1}",
            "eigenvalue": round(float(pca_model.explained_variance_[i]), 4),
            "variance_ratio_pct": round(float(pca_model.explained_variance_ratio_[i] * 100), 2),
            "cumulative_variance_pct": round(float(np.cumsum(pca_model.explained_variance_ratio_)[i] * 100), 2),
        })
    variance_df = pd.DataFrame(variance_records)

    print(f"\n[结果] 方差解释比:")
    print(variance_df.to_string(index=False))

    # 平行分析对照表
    pa_records = []
    for i in range(min(n_features, 10)):
        pa_records.append({
            "component": f"PC{i+1}",
            "real_eigenvalue": round(float(real_eig[i]), 4),
            "random_eigenvalue_p95": round(float(random_eig[i]), 4),
            "retain": "Y" if real_eig[i] > random_eig[i] else "N",
        })
    pa_df = pd.DataFrame(pa_records)

    return pca_model, loadings_df, variance_df, scores, component_selection, pa_df


def main():
    parser = argparse.ArgumentParser(description="PCA 主成分分析: 载荷矩阵 + 方差解释 + 自动组件选择")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--n-components", type=int, default=None, help="指定主成分数 (默认自动选择)")
    parser.add_argument("--variance-target", type=float, default=0.90, help="目标累计方差比 (默认 0.90)")
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
        print("[错误] 有效样本不足 (需要至少 2 个)。")
        sys.exit(1)

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    print(f"[信息] 有效样本: {X_scaled.shape[0]}, 特征维度: {X_scaled.shape[1]}")

    # PCA 分析
    pca_model, loadings_df, variance_df, scores, selection, pa_df = run_pca_analysis(
        X_scaled, feature_cols, n_components=args.n_components,
        variance_target=args.variance_target, random_state=args.seed
    )

    # 保存载荷矩阵
    loadings_path = os.path.join(args.output_dir, "pca_loadings.csv")
    loadings_df.to_csv(loadings_path, encoding='utf-8-sig')
    print(f"\n[输出] 载荷矩阵已保存: {loadings_path}")

    # 保存方差解释比
    variance_path = os.path.join(args.output_dir, "pca_variance.csv")
    variance_df.to_csv(variance_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 方差解释比已保存: {variance_path}")

    # 保存降维坐标
    n_components = scores.shape[1]
    scores_df = df.loc[valid_idx].copy()
    for i in range(n_components):
        scores_df[f"PC{i+1}"] = scores[:, i]
    scores_path = os.path.join(args.output_dir, "pca_scores.csv")
    scores_df.to_csv(scores_path, index=False, encoding='utf-8-sig')
    print(f"[输出] PCA 坐标数据已保存: {scores_path}")

    # 保存组件选择建议
    selection_records = []
    for method, info in selection.items():
        row = {"method": method}
        row.update(info)
        selection_records.append(row)
    selection_df = pd.DataFrame(selection_records)
    selection_path = os.path.join(args.output_dir, "component_selection.csv")
    selection_df.to_csv(selection_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 组件选择建议已保存: {selection_path}")

    # 保存平行分析对照表
    pa_path = os.path.join(args.output_dir, "parallel_analysis.csv")
    pa_df.to_csv(pa_path, index=False, encoding='utf-8-sig')
    print(f"[输出] 平行分析对照表已保存: {pa_path}")
    print(f"\n[结果] 平行分析对照:")
    print(pa_df.to_string(index=False))

    print("\n[完成] PCA 分析完毕。")


if __name__ == "__main__":
    main()
