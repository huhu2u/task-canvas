#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DBSCAN 密度聚类分析脚本

自动估算 eps 参数，支持 HDBSCAN 回退，输出簇标签和噪声点标记。

用法示例:
    python dbscan_analysis.py --input data.csv --features col1,col2,col3
    python dbscan_analysis.py --input data.csv --features col1,col2 --eps 0.5 --min-samples 10
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import silhouette_score, davies_bouldin_score

warnings.filterwarnings("ignore")


def _adaptive_n_jobs(n_samples):
    """根据数据规模自适应选择 n_jobs，避免大数据集多进程内存复制。"""
    if n_samples > 50000:
        return 1
    elif n_samples > 10000:
        return 2
    return -1


def _downsample(X, max_samples, random_state=42):
    """对数据进行随机抽样，返回 (抽样后数据, 抽样索引)。"""
    rng = np.random.RandomState(random_state)
    indices = rng.choice(len(X), size=max_samples, replace=False)
    return X[indices], indices


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def preprocess_features(df, feature_cols, pca_threshold=50, pca_variance=0.95):
    """特征预处理：填充缺失值、标准化、可选 PCA 预降维。"""
    X = df[feature_cols].copy()
    valid_idx = X.dropna(how="all").index
    X = X.loc[valid_idx]

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    pca_model = None
    if X_scaled.shape[1] > pca_threshold:
        pca_model = PCA(n_components=pca_variance, random_state=42)
        X_scaled = pca_model.fit_transform(X_scaled)
        print(f"[信息] PCA 预降维: {len(feature_cols)} 维 -> {X_scaled.shape[1]} 维")

    return X_scaled, valid_idx


def estimate_eps(X, min_samples, max_samples=50000):
    """
    通过 K-距离图的拐点自动估算 DBSCAN 的 eps 参数。

    Parameters
    ----------
    X : ndarray
    min_samples : int
    max_samples : int
        NearestNeighbors 计算的最大样本数，超过时自动抽样以避免 O(n²) 内存。

    Returns
    -------
    eps : float
    """
    k = min_samples
    X_est = X
    if len(X) > max_samples:
        print(f"[信息] estimate_eps: 数据量 {len(X)} 超过 {max_samples}，抽样 {max_samples} 条估算 eps")
        X_est, _ = _downsample(X, max_samples)
    nbrs = NearestNeighbors(n_neighbors=k, n_jobs=_adaptive_n_jobs(len(X_est))).fit(X_est)
    distances, _ = nbrs.kneighbors(X_est)
    k_distances = np.sort(distances[:, k - 1])

    # 拐点检测：最大梯度变化点
    diffs = np.diff(k_distances)
    if len(diffs) == 0:
        return float(k_distances.mean())

    # 使用二阶差分找拐点
    if len(diffs) > 1:
        diffs2 = np.diff(diffs)
        idx = np.argmax(diffs2) + 1
    else:
        idx = 0

    eps = float(k_distances[idx])

    # 防止 eps 为 0 或过小
    if eps < 1e-10:
        eps = float(np.percentile(k_distances, 90))

    return eps


def run_dbscan(X, eps=None, min_samples=None, max_samples=50000):
    """
    执行 DBSCAN 聚类。

    Parameters
    ----------
    X : ndarray
    eps : float or None
    min_samples : int or None
    max_samples : int
        数据规模保护阈值。eps 自动估算时若超过此值将抽样计算。

    Returns
    -------
    labels : ndarray
    n_clusters : int
    n_noise : int
    params : dict
    """
    n_samples = len(X)

    if n_samples > max_samples:
        print(f"[信息] 数据量 {n_samples} 超过 max_samples={max_samples}，"
              f"将使用抽样子集估算参数后对全量数据聚类")

    if min_samples is None:
        min_samples = max(5, int(np.log(n_samples)))

    if eps is None:
        eps = estimate_eps(X, min_samples, max_samples=max_samples)
        print(f"[信息] 自动估算参数: eps = {eps:.4f}, min_samples = {min_samples}")
    else:
        print(f"[信息] 使用指定参数: eps = {eps:.4f}, min_samples = {min_samples}")

    n_jobs = _adaptive_n_jobs(n_samples)
    db = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=n_jobs)
    labels = db.fit_predict(X)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    noise_pct = n_noise / len(X) * 100

    print(f"\n[结果] DBSCAN 聚类结果:")
    print(f"  簇数量: {n_clusters}")
    print(f"  噪声点: {n_noise} ({noise_pct:.1f}%)")

    # 各簇样本量
    if n_clusters > 0:
        cluster_counts = pd.Series(labels[labels != -1]).value_counts().sort_index()
        for cls, cnt in cluster_counts.items():
            print(f"  簇 {cls}: {cnt} 个样本 ({cnt / len(X) * 100:.1f}%)")

    params = {"eps": eps, "min_samples": min_samples, "n_clusters": n_clusters, "n_noise": n_noise, "noise_pct": round(noise_pct, 2)}
    return labels, n_clusters, n_noise, params


def run_hdbscan_fallback(X, min_cluster_size=None, max_samples=50000):
    """
    当 DBSCAN 结果不理想时，使用 HDBSCAN 作为回退方案。

    Parameters
    ----------
    X : ndarray
    min_cluster_size : int or None
    max_samples : int
        数据规模保护阈值。超过时抽样聚类后用最近邻将标签映射回全量数据。

    Returns
    -------
    labels : ndarray or None
    n_clusters : int
    params : dict
    """
    try:
        import hdbscan
    except ImportError:
        print("[警告] hdbscan 未安装 (pip install hdbscan)，无法使用 HDBSCAN 回退。")
        return None, 0, {}

    n_samples = len(X)
    sampled = False

    if n_samples > max_samples:
        print(f"[信息] HDBSCAN: 数据量 {n_samples} 超过 {max_samples}，"
              f"抽样 {max_samples} 条聚类后映射全量标签")
        X_sub, sub_idx = _downsample(X, max_samples)
        sampled = True
    else:
        X_sub = X

    if min_cluster_size is None:
        min_cluster_size = max(5, int(len(X_sub) * 0.01))

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=False)
    sub_labels = clusterer.fit_predict(X_sub)

    if sampled:
        # 用抽样子集的聚类结果，通过最近邻将标签映射回全量数据
        nbrs = NearestNeighbors(n_neighbors=1, n_jobs=_adaptive_n_jobs(n_samples)).fit(X_sub)
        _, indices = nbrs.kneighbors(X)
        labels = sub_labels[indices.ravel()]
    else:
        labels = sub_labels

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    noise_pct = n_noise / len(X) * 100

    print(f"\n[结果] HDBSCAN 回退结果:")
    print(f"  簇数量: {n_clusters}")
    print(f"  噪声点: {n_noise} ({noise_pct:.1f}%)")
    print(f"  min_cluster_size: {min_cluster_size}")

    params = {"algorithm": "hdbscan", "min_cluster_size": min_cluster_size,
              "n_clusters": n_clusters, "n_noise": n_noise, "noise_pct": round(noise_pct, 2)}
    return labels, n_clusters, params


def evaluate_clustering(X, labels):
    """计算聚类质量指标（仅对有效簇计算）。"""
    valid_mask = labels != -1
    if valid_mask.sum() < 2 or len(set(labels[valid_mask])) < 2:
        print("[警告] 有效簇不足，无法计算质量指标。")
        return {}

    sil = silhouette_score(X[valid_mask], labels[valid_mask], sample_size=min(5000, valid_mask.sum()))
    db = davies_bouldin_score(X[valid_mask], labels[valid_mask])

    print(f"\n[结果] 聚类质量指标 (排除噪声点):")
    print(f"  Silhouette Score: {sil:.4f}", end="")
    if sil > 0.5:
        print(" (优秀)")
    elif sil > 0.25:
        print(" (合理)")
    else:
        print(" (较差)")
    print(f"  Davies-Bouldin Index: {db:.4f}")

    return {"silhouette_score": round(sil, 4), "davies_bouldin_index": round(db, 4)}


def main():
    parser = argparse.ArgumentParser(description="DBSCAN 密度聚类分析 (含 HDBSCAN 回退)")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--eps", type=float, default=None, help="DBSCAN eps 参数 (默认自动估算)")
    parser.add_argument("--min-samples", type=int, default=None, help="DBSCAN min_samples (默认 max(5, log(N)))")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--max-samples", type=int, default=50000,
                        help="大数据保护阈值，超过时自动抽样 (默认 50000)")
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

    # 预处理
    X_scaled, valid_idx = preprocess_features(df, feature_cols)

    # DBSCAN
    labels, n_clusters, n_noise, params = run_dbscan(
        X_scaled, eps=args.eps, min_samples=args.min_samples,
        max_samples=args.max_samples)

    # 检查是否需要 HDBSCAN 回退
    noise_pct = n_noise / len(X_scaled) * 100
    use_hdbscan = False
    if noise_pct > 30:
        print(f"\n[警告] 噪声点占比 {noise_pct:.1f}% > 30%，尝试 HDBSCAN 回退...")
        use_hdbscan = True
    elif n_clusters <= 1:
        print(f"\n[警告] DBSCAN 仅发现 {n_clusters} 个簇，尝试 HDBSCAN 回退...")
        use_hdbscan = True

    if use_hdbscan:
        hdb_labels, hdb_n_clusters, hdb_params = run_hdbscan_fallback(
            X_scaled, max_samples=args.max_samples)
        if hdb_labels is not None and hdb_n_clusters > n_clusters:
            print("[信息] 采用 HDBSCAN 结果（簇数更多）。")
            labels = hdb_labels
            n_clusters = hdb_n_clusters
            params.update(hdb_params)
            params["fallback_used"] = True

    # 评估
    quality = evaluate_clustering(X_scaled, labels)
    params.update(quality)

    # 保存结果
    label_df = df.loc[valid_idx].copy()
    label_df["cluster"] = labels
    label_path = os.path.join(args.output_dir, "dbscan_labels.csv")
    label_df.to_csv(label_path, index=False)
    print(f"\n[输出] DBSCAN 聚类标签已保存: {label_path}")

    # 保存参数和指标摘要
    params_df = pd.DataFrame([params])
    params_path = os.path.join(args.output_dir, "dbscan_summary.csv")
    params_df.to_csv(params_path, index=False)
    print(f"[输出] DBSCAN 摘要已保存: {params_path}")

    print("\n[完成] DBSCAN 聚类分析完毕。")


if __name__ == "__main__":
    main()
