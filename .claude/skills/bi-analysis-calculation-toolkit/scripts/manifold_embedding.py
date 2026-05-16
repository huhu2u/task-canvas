#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
t-SNE / UMAP 流形嵌入脚本

将高维数据映射到 2D 坐标，输出嵌入坐标 CSV。
支持 t-SNE perplexity 敏感性检查和 UMAP 参数控制。

用法示例:
    python manifold_embedding.py --input data.csv --features col1,col2,col3 --method tsne
    python manifold_embedding.py --input data.csv --features col1,col2 --method umap --n-neighbors 15
    python manifold_embedding.py --input data.csv --features col1,col2 --method tsne --perplexity-check
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

warnings.filterwarnings("ignore")

DEFAULT_MAX_SAMPLES = 20000


def _adaptive_n_jobs(n_samples, max_samples=DEFAULT_MAX_SAMPLES):
    """根据数据规模返回合理的并行度。"""
    return 2 if n_samples > max_samples else -1


def _downsample_if_needed(X, max_samples=DEFAULT_MAX_SAMPLES, random_state=42):
    """
    若样本数超过 max_samples，随机抽样并返回 (X_sampled, sample_indices)。
    否则返回原始数据和 None。
    """
    if max_samples is not None and len(X) > max_samples:
        rng = np.random.RandomState(random_state)
        indices = rng.choice(len(X), size=max_samples, replace=False)
        indices.sort()
        print(f"[警告] 数据量 ({len(X)}) 超过 max_samples ({max_samples})，已随机抽样至 {max_samples} 条以防止内存溢出。")
        return X[indices], indices
    return X, None


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def preprocess(df, feature_cols, pca_pre_dim=50):
    """预处理：填充、标准化、高维 PCA 预降维。"""
    X = df[feature_cols].copy()
    valid_idx = X.dropna(how="all").index
    X = X.loc[valid_idx]

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    if X_scaled.shape[1] > pca_pre_dim:
        pca = PCA(n_components=pca_pre_dim, random_state=42)
        X_scaled = pca.fit_transform(X_scaled)
        var_explained = pca.explained_variance_ratio_.sum()
        print(f"[信息] PCA 预降维: {len(feature_cols)} 维 -> {pca_pre_dim} 维 (保留方差 {var_explained*100:.1f}%)")

    return X_scaled, valid_idx


def run_tsne(X, perplexity=30, random_state=42, max_samples=DEFAULT_MAX_SAMPLES):
    """运行 t-SNE 降维到 2D。"""
    X_work, sample_idx = _downsample_if_needed(X, max_samples=max_samples, random_state=random_state)

    perplexity = min(perplexity, len(X_work) - 1)
    if perplexity < 5:
        perplexity = 5

    n_jobs = _adaptive_n_jobs(len(X_work), max_samples=max_samples)
    print(f"[信息] 运行 t-SNE (perplexity={perplexity}, n_jobs={n_jobs}) ...")
    tsne = TSNE(n_components=2, perplexity=perplexity, random_state=random_state, n_jobs=n_jobs)
    X_2d = tsne.fit_transform(X_work)

    print(f"[结果] t-SNE 完成: {X_work.shape[0]} 个样本映射到 2D")
    print(f"  KL 散度: {tsne.kl_divergence_:.4f}")

    return X_2d, sample_idx


def run_tsne_perplexity_check(X, perplexities=None, random_state=42, max_samples=DEFAULT_MAX_SAMPLES):
    """
    用多个 perplexity 值运行 t-SNE，用于敏感性分析。

    Returns
    -------
    results : dict[int, ndarray], perplexity -> 2D 坐标
    kl_divs : dict[int, float]
    sample_idx : ndarray or None, 抽样索引（未抽样时为 None）
    """
    X_work, sample_idx = _downsample_if_needed(X, max_samples=max_samples, random_state=random_state)

    if perplexities is None:
        perplexities = [p for p in [5, 10, 20, 30, 50] if p < len(X_work)]

    results = {}
    kl_divs = {}

    n_jobs = _adaptive_n_jobs(len(X_work), max_samples=max_samples)
    for perp in perplexities:
        print(f"[信息] t-SNE perplexity={perp} (n_jobs={n_jobs}) ...")
        tsne = TSNE(n_components=2, perplexity=perp, random_state=random_state, n_jobs=n_jobs)
        X_2d = tsne.fit_transform(X_work)
        results[perp] = X_2d
        kl_divs[perp] = tsne.kl_divergence_
        print(f"  KL 散度: {tsne.kl_divergence_:.4f}")

    return results, kl_divs, sample_idx


def run_umap(X, n_neighbors=15, min_dist=0.1, random_state=42, max_samples=DEFAULT_MAX_SAMPLES):
    """运行 UMAP 降维到 2D。"""
    try:
        import umap
    except ImportError:
        print("[错误] umap-learn 未安装。请运行: pip install umap-learn")
        return None, None

    X_work, sample_idx = _downsample_if_needed(X, max_samples=max_samples, random_state=random_state)

    print(f"[信息] 运行 UMAP (n_neighbors={n_neighbors}, min_dist={min_dist}) ...")
    reducer = umap.UMAP(n_components=2, n_neighbors=n_neighbors, min_dist=min_dist, random_state=random_state)
    X_2d = reducer.fit_transform(X_work)

    print(f"[结果] UMAP 完成: {X_work.shape[0]} 个样本映射到 2D")
    print(f"  参数说明:")
    print(f"    n_neighbors={n_neighbors}: 控制局部/全局结构平衡 (小值保留局部结构，大值保留全局结构)")
    print(f"    min_dist={min_dist}: 控制嵌入点的紧密程度 (小值更紧凑，大值更分散)")

    return X_2d, sample_idx


def main():
    parser = argparse.ArgumentParser(description="t-SNE / UMAP 流形嵌入: 高维数据 -> 2D 坐标")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--method", default="tsne", choices=["tsne", "umap"], help="降维方法 (默认 tsne)")
    parser.add_argument("--perplexity", type=int, default=30, help="t-SNE perplexity (默认 30)")
    parser.add_argument("--perplexity-check", action="store_true", help="运行多个 perplexity 的敏感性检查")
    parser.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors (默认 15)")
    parser.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist (默认 0.1)")
    parser.add_argument("--color-col", default=None, help="颜色标注列名 (附加到输出)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--max-samples", type=int, default=DEFAULT_MAX_SAMPLES,
                        help=f"最大样本数，超过时自动抽样 (默认 {DEFAULT_MAX_SAMPLES}，设为 0 禁用)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    max_samples = args.max_samples if args.max_samples > 0 else None
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
    X_scaled, valid_idx = preprocess(df, feature_cols)
    print(f"[信息] 有效样本: {X_scaled.shape[0]}, 处理后维度: {X_scaled.shape[1]}")

    if X_scaled.shape[0] < 3:
        print("[错误] 有效样本不足 (需要至少 3 个)。")
        sys.exit(1)

    # 嵌入
    if args.method == "tsne":
        if args.perplexity_check:
            # 敏感性检查
            results, kl_divs, sample_idx = run_tsne_perplexity_check(
                X_scaled, random_state=args.seed, max_samples=max_samples
            )

            # 抽样后使用对应子集的原始行索引
            out_idx = valid_idx[sample_idx] if sample_idx is not None else valid_idx

            # 保存每个 perplexity 的结果
            for perp, coords in results.items():
                embed_df = df.loc[out_idx].copy()
                embed_df[f"tsne_dim1_perp{perp}"] = coords[:, 0]
                embed_df[f"tsne_dim2_perp{perp}"] = coords[:, 1]
                path = os.path.join(args.output_dir, f"tsne_embedding_perp{perp}.csv")
                embed_df.to_csv(path, index=False, encoding='utf-8-sig')
                print(f"[输出] t-SNE (perplexity={perp}) 坐标已保存: {path}")

            # 保存 KL 散度对比
            kl_df = pd.DataFrame([{"perplexity": k, "kl_divergence": round(v, 4)} for k, v in kl_divs.items()])
            kl_path = os.path.join(args.output_dir, "tsne_perplexity_comparison.csv")
            kl_df.to_csv(kl_path, index=False, encoding='utf-8-sig')
            print(f"\n[结果] Perplexity 敏感性对比:")
            print(kl_df.to_string(index=False))
            print(f"[输出] 对比表已保存: {kl_path}")
            print("[提示] t-SNE 结果对 perplexity 敏感，应比较不同设置下的结构是否稳定。")

        else:
            X_2d, sample_idx = run_tsne(
                X_scaled, perplexity=args.perplexity, random_state=args.seed, max_samples=max_samples
            )
            out_idx = valid_idx[sample_idx] if sample_idx is not None else valid_idx

            embed_df = df.loc[out_idx].copy()
            embed_df["tsne_dim1"] = X_2d[:, 0]
            embed_df["tsne_dim2"] = X_2d[:, 1]

            if args.color_col and args.color_col in df.columns:
                embed_df[args.color_col] = df.loc[out_idx, args.color_col].values

            path = os.path.join(args.output_dir, "tsne_embedding.csv")
            embed_df.to_csv(path, index=False, encoding='utf-8-sig')
            print(f"[输出] t-SNE 嵌入坐标已保存: {path}")
            print("[提示] t-SNE 结果仅用于探索性可视化，不适合定量距离比较。")

    elif args.method == "umap":
        X_2d, sample_idx = run_umap(
            X_scaled, n_neighbors=args.n_neighbors, min_dist=args.min_dist,
            random_state=args.seed, max_samples=max_samples
        )
        if X_2d is not None:
            out_idx = valid_idx[sample_idx] if sample_idx is not None else valid_idx

            embed_df = df.loc[out_idx].copy()
            embed_df["umap_dim1"] = X_2d[:, 0]
            embed_df["umap_dim2"] = X_2d[:, 1]

            if args.color_col and args.color_col in df.columns:
                embed_df[args.color_col] = df.loc[out_idx, args.color_col].values

            path = os.path.join(args.output_dir, "umap_embedding.csv")
            embed_df.to_csv(path, index=False, encoding='utf-8-sig')
            print(f"[输出] UMAP 嵌入坐标已保存: {path}")

    print("\n[完成] 流形嵌入分析完毕。")


if __name__ == "__main__":
    main()
