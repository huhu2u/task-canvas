#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K-Means 聚类分析脚本

包含 Elbow Method、Silhouette Score、Gap Statistic、Davies-Bouldin Index
四项指标综合评估最优 K 值，输出分群标签和质量指标。

用法示例:
    python clustering_analysis.py --input data.csv --features col1,col2,col3
    python clustering_analysis.py --input data.csv --features col1,col2 --k-max 15 --output-dir results/
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def preprocess_features(df, feature_cols, pca_threshold=50, pca_variance=0.95):
    """
    特征预处理：填充缺失值、标准化、可选 PCA 预降维。

    Parameters
    ----------
    df : DataFrame
    feature_cols : list[str]
    pca_threshold : int, 特征数超过此值时自动 PCA 降维
    pca_variance : float, PCA 保留方差比例

    Returns
    -------
    X_scaled : ndarray
    scaler : StandardScaler
    pca_model : PCA or None
    valid_index : Index
    """
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
        print(f"[信息] PCA 预降维: {len(feature_cols)} 维 -> {X_scaled.shape[1]} 维 (保留 {pca_variance*100:.0f}% 方差)")

    print(f"[信息] 预处理完成: {X_scaled.shape[0]} 个样本, {X_scaled.shape[1]} 个特征维度")
    return X_scaled, scaler, pca_model, valid_idx


def _get_kmeans_estimator(n_samples, n_clusters, random_state=42, n_init=10):
    """
    根据数据规模选择 KMeans 或 MiniBatchKMeans。

    数据量 > 100000 时自动使用 MiniBatchKMeans 以降低内存和时间开销。
    """
    if n_samples > 100000:
        return MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=n_init,
            batch_size=min(10000, n_samples),
        )
    return KMeans(n_clusters=n_clusters, random_state=random_state, n_init=n_init)


def compute_gap_statistic(X, k_range, n_refs=10, random_state=42):
    """
    计算 Gap Statistic。

    Parameters
    ----------
    X : ndarray
    k_range : range
    n_refs : int, 随机参考数据集数量
    random_state : int

    Returns
    -------
    gaps : list[float]
    gap_errors : list[float]
    """
    rng = np.random.RandomState(random_state)
    n_samples = X.shape[0]

    # 大数据量时对数据抽样以降低内存开销
    GAP_SAMPLE_LIMIT = 50000
    if n_samples > GAP_SAMPLE_LIMIT:
        sample_idx = rng.choice(n_samples, size=GAP_SAMPLE_LIMIT, replace=False)
        X_gap = X[sample_idx]
        print(f"[信息] Gap Statistic: 数据量 {n_samples} > {GAP_SAMPLE_LIMIT}，抽样至 {GAP_SAMPLE_LIMIT} 行计算")
    else:
        X_gap = X

    # 大数据量时减少参考数据集数量
    if n_samples > 20000:
        n_refs = min(n_refs, 3)
        print(f"[信息] Gap Statistic: 数据量 > 20000，n_refs 降为 {n_refs}")

    gaps = []
    gap_errors = []

    for k in k_range:
        # 真实数据的 log(W_k)
        km = _get_kmeans_estimator(X_gap.shape[0], n_clusters=k, random_state=random_state)
        km.fit(X_gap)
        log_wk = np.log(km.inertia_) if km.inertia_ > 0 else 0

        # 随机参考数据集
        ref_log_wks = []
        for _ in range(n_refs):
            X_ref = rng.uniform(X_gap.min(axis=0), X_gap.max(axis=0), size=X_gap.shape)
            km_ref = _get_kmeans_estimator(X_ref.shape[0], n_clusters=k, random_state=random_state)
            km_ref.fit(X_ref)
            ref_log_wk = np.log(km_ref.inertia_) if km_ref.inertia_ > 0 else 0
            ref_log_wks.append(ref_log_wk)
            del X_ref  # 及时释放参考数据集内存

        ref_log_wks = np.array(ref_log_wks)
        gap = ref_log_wks.mean() - log_wk
        gap_se = ref_log_wks.std() * np.sqrt(1 + 1 / n_refs)

        gaps.append(gap)
        gap_errors.append(gap_se)

    return gaps, gap_errors


def find_optimal_k(k_range, sse_list, silhouette_list, gaps, gap_errors, db_list):
    """
    综合多项指标推荐最优 K。

    策略：
    1. Gap Statistic: gap(k) >= gap(k+1) - se(k+1) 时的最小 k
    2. Silhouette: 最大值对应的 k
    3. Elbow: 二阶差分最小点
    4. 综合：取三者的众数，若无众数则优先 Silhouette
    """
    k_list = list(k_range)

    # Elbow (二阶差分)
    if len(sse_list) > 2:
        diffs = np.diff(sse_list)
        diffs2 = np.diff(diffs)
        elbow_k = k_list[np.argmin(diffs2) + 1] if len(diffs2) > 0 else k_list[0]
    else:
        elbow_k = k_list[0]

    # Silhouette
    silhouette_k = k_list[np.argmax(silhouette_list)]

    # Gap Statistic
    gap_k = k_list[0]
    for i in range(len(gaps) - 1):
        if gaps[i] >= gaps[i + 1] - gap_errors[i + 1]:
            gap_k = k_list[i]
            break
    else:
        gap_k = k_list[np.argmax(gaps)]

    # 综合推荐
    candidates = [elbow_k, silhouette_k, gap_k]
    from collections import Counter
    counter = Counter(candidates)
    most_common = counter.most_common(1)[0]
    if most_common[1] >= 2:
        best_k = most_common[0]
    else:
        best_k = silhouette_k  # 无共识时优先 Silhouette

    print(f"\n[结果] K 值推荐:")
    print(f"  Elbow Method: K = {elbow_k}")
    print(f"  Silhouette Score: K = {silhouette_k}")
    print(f"  Gap Statistic: K = {gap_k}")
    print(f"  综合推荐: K = {best_k}")

    return best_k, {"elbow_k": elbow_k, "silhouette_k": silhouette_k, "gap_k": gap_k}


def run_kmeans_search(X, k_max=10, random_state=42):
    """
    执行 K-Means 搜索：遍历 K 值，计算所有评估指标。

    Returns
    -------
    search_df : DataFrame, 各 K 值的指标
    best_k : int
    labels : ndarray, 最优 K 对应的簇标签
    """
    k_max = min(k_max, len(X) - 1)
    k_range = range(2, k_max + 1)

    if len(X) < 3:
        print("[错误] 样本量不足，至少需要 3 个样本。")
        sys.exit(1)

    print(f"[信息] 搜索 K = 2 ~ {k_max} ...")

    n_samples = len(X)

    # davies_bouldin_score 在大数据量时使用抽样子集
    DB_SAMPLE_LIMIT = 50000
    rng = np.random.RandomState(random_state)
    if n_samples > DB_SAMPLE_LIMIT:
        db_sample_idx = rng.choice(n_samples, size=DB_SAMPLE_LIMIT, replace=False)
        print(f"[信息] Davies-Bouldin: 数据量 {n_samples} > {DB_SAMPLE_LIMIT}，抽样至 {DB_SAMPLE_LIMIT} 行计算")
    else:
        db_sample_idx = None

    sse_list = []
    silhouette_list = []
    db_list = []

    for k in k_range:
        km = _get_kmeans_estimator(n_samples, n_clusters=k, random_state=random_state)
        labels_k = km.fit_predict(X)
        sse_list.append(km.inertia_)

        sil = silhouette_score(X, labels_k, sample_size=min(5000, n_samples), random_state=random_state)
        silhouette_list.append(sil)

        if db_sample_idx is not None:
            db = davies_bouldin_score(X[db_sample_idx], labels_k[db_sample_idx])
        else:
            db = davies_bouldin_score(X, labels_k)
        db_list.append(db)

    # Gap Statistic
    print("[信息] 计算 Gap Statistic ...")
    gaps, gap_errors = compute_gap_statistic(X, k_range, n_refs=10, random_state=random_state)

    # 综合推荐
    best_k, k_details = find_optimal_k(k_range, sse_list, silhouette_list, gaps, gap_errors, db_list)

    # 构建搜索结果表
    search_df = pd.DataFrame({
        "k": list(k_range),
        "sse": sse_list,
        "silhouette_score": [round(s, 4) for s in silhouette_list],
        "davies_bouldin_index": [round(d, 4) for d in db_list],
        "gap_statistic": [round(g, 4) for g in gaps],
        "gap_se": [round(e, 4) for e in gap_errors],
    })

    print(f"\n[结果] K 值搜索表:")
    print(search_df.to_string(index=False))

    # 使用最优 K 拟合
    final_km = _get_kmeans_estimator(n_samples, n_clusters=best_k, random_state=random_state)
    labels = final_km.fit_predict(X)

    best_sil = silhouette_score(X, labels, sample_size=min(5000, n_samples), random_state=random_state)
    if db_sample_idx is not None:
        best_db = davies_bouldin_score(X[db_sample_idx], labels[db_sample_idx])
    else:
        best_db = davies_bouldin_score(X, labels)

    print(f"\n[结果] 最优聚类 (K = {best_k}):")
    print(f"  Silhouette Score: {best_sil:.4f}", end="")
    if best_sil > 0.5:
        print(" (优秀)")
    elif best_sil > 0.25:
        print(" (合理)")
    else:
        print(" (较差，数据可能缺乏明显聚类结构)")
    print(f"  Davies-Bouldin Index: {best_db:.4f} (越接近 0 越好)")

    # 簇规模检查
    cluster_counts = pd.Series(labels).value_counts().sort_index()
    for cls, cnt in cluster_counts.items():
        pct = cnt / len(labels) * 100
        if pct < 1:
            print(f"[警告] 簇 {cls} 仅含 {cnt} 个样本 ({pct:.1f}%)，可能为噪声。")

    return search_df, best_k, labels, {"silhouette": best_sil, "davies_bouldin": best_db}


def main():
    parser = argparse.ArgumentParser(description="K-Means 聚类分析: Elbow + Silhouette + Gap Statistic + Davies-Bouldin")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--k-max", type=int, default=10, help="最大簇数 (默认 10)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录 (默认当前目录)")

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
    X_scaled, scaler, pca_model, valid_idx = preprocess_features(df, feature_cols)

    # K-Means 搜索
    search_df, best_k, labels, quality_metrics = run_kmeans_search(X_scaled, k_max=args.k_max, random_state=args.seed)

    # 保存 K 值搜索表
    search_path = os.path.join(args.output_dir, "k_search_results.csv")
    search_df.to_csv(search_path, index=False)
    print(f"\n[输出] K 值搜索表已保存: {search_path}")

    # 保存聚类标签
    label_df = df.loc[valid_idx].copy()
    label_df["cluster"] = labels
    label_path = os.path.join(args.output_dir, "cluster_labels.csv")
    label_df.to_csv(label_path, index=False)
    print(f"[输出] 聚类标签已保存: {label_path}")

    # 保存质量摘要
    summary = {
        "best_k": best_k,
        "silhouette_score": round(quality_metrics["silhouette"], 4),
        "davies_bouldin_index": round(quality_metrics["davies_bouldin"], 4),
        "n_samples": len(labels),
        "n_features": X_scaled.shape[1],
    }
    summary_df = pd.DataFrame([summary])
    summary_path = os.path.join(args.output_dir, "clustering_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"[输出] 聚类质量摘要已保存: {summary_path}")

    print("\n[完成] K-Means 聚类分析完毕。")


if __name__ == "__main__":
    main()
