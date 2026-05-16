#!/usr/bin/env python3
"""
多变量异常检测脚本
方法：Isolation Forest + LOF (Local Outlier Factor) 集成
增强：自适应污染率估计、归一化综合异常分数、边界情况处理

用法：
    python multivariate_anomaly.py -i data.csv -c col1 col2 col3 -o result.csv
    python multivariate_anomaly.py -i data.xlsx -c price quantity discount --contamination auto
"""

import argparse
import sys
import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


def _adaptive_n_jobs(n_samples):
    """
    根据数据规模自适应选择并行核数，避免大数据集下全核并行导致内存溢出。

    Args:
        n_samples: 样本数量

    Returns:
        int: n_jobs 参数值
    """
    if n_samples > 50000:
        return 1
    elif n_samples > 10000:
        return 2
    else:
        return -1


def estimate_contamination(X, method="iqr"):
    """
    自适应污染率估计：基于IQR方法对每个特征估计异常比例，取中位数。

    Args:
        X: np.ndarray，标准化后的特征矩阵
        method: 估计方法，目前支持 'iqr'

    Returns:
        float: 估计的污染率，限制在 [0.01, 0.15]
    """
    anomaly_rates = []
    for col_idx in range(X.shape[1]):
        col = X[:, col_idx]
        Q1 = np.percentile(col, 25)
        Q3 = np.percentile(col, 75)
        IQR = Q3 - Q1
        if IQR > 0:
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            rate = np.mean((col < lower) | (col > upper))
            anomaly_rates.append(rate)

    if len(anomaly_rates) == 0:
        return 0.05

    estimated = np.median(anomaly_rates)
    # 限制在合理范围内
    return max(0.01, min(0.15, estimated)) if estimated > 0 else 0.05


def normalize_scores(scores):
    """将分数归一化到 [0, 1] 区间，值越大越异常"""
    min_val = scores.min()
    max_val = scores.max()
    if max_val == min_val:
        return np.zeros_like(scores)
    return (scores - min_val) / (max_val - min_val)


def multivariate_anomaly(df, feature_cols, contamination="auto", lof_threshold=10000,
                         min_neighbors=20):
    """
    多变量异常检测：Isolation Forest + LOF 集成。

    Args:
        df: pd.DataFrame
        feature_cols: list，特征列名列表
        contamination: 'auto' 表示自适应估计，或浮点数指定
        lof_threshold: LOF的样本量上限（超过时跳过LOF）
        min_neighbors: LOF的最小邻居数

    Returns:
        pd.DataFrame: 检测结果
    """
    # === 数据预处理 ===
    # 过滤常数列
    valid_cols = []
    for col in feature_cols:
        if col not in df.columns:
            print(f"[警告] 列 '{col}' 不存在，已跳过")
            continue
        if not np.issubdtype(df[col].dtype, np.number):
            print(f"[警告] 列 '{col}' 不是数值类型，已跳过")
            continue
        if df[col].dropna().nunique() <= 1:
            print(f"[警告] 列 '{col}' 为常数或全空，已跳过")
            continue
        valid_cols.append(col)

    if len(valid_cols) < 2:
        print(f"[错误] 有效数值列不足2个 (当前: {len(valid_cols)})，无法进行多变量检测")
        return pd.DataFrame()

    # 提取有效数据
    X_raw = df[valid_cols].copy()
    valid_mask = X_raw.notna().all(axis=1)
    n_dropped = (~valid_mask).sum()
    if n_dropped > 0:
        print(f"[信息] 因缺失值移除 {n_dropped} 行 (占 {n_dropped/len(df)*100:.1f}%)")

    X_clean = X_raw[valid_mask]

    if len(X_clean) < 10:
        print(f"[错误] 有效样本仅 {len(X_clean)} 行，样本量不足")
        return pd.DataFrame()

    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)

    # === 自适应污染率 ===
    if contamination == "auto":
        contamination_val = estimate_contamination(X_scaled)
        print(f"[信息] 自适应污染率估计: {contamination_val:.3f}")
    else:
        contamination_val = float(contamination)

    # === Isolation Forest ===
    n_samples = len(X_clean)
    n_jobs = _adaptive_n_jobs(n_samples)
    print(f"[信息] 运行 Isolation Forest (n={n_samples}, features={len(valid_cols)}, n_jobs={n_jobs})...")
    iso_kwargs = dict(
        contamination=contamination_val,
        random_state=42,
        n_jobs=n_jobs,
        n_estimators=200,
    )
    if n_samples > 100000:
        iso_kwargs["max_samples"] = 100000
        print(f"[信息] 样本量 {n_samples} > 100000，IsolationForest 使用 max_samples=100000 限制训练样本")
    iso = IsolationForest(**iso_kwargs)
    iso_pred = iso.fit_predict(X_scaled)
    iso_scores = iso.decision_function(X_scaled)
    # decision_function: 越小越异常，转换为越大越异常
    iso_anomaly_scores = -iso_scores

    # === LOF ===
    run_lof = len(X_clean) <= lof_threshold
    if not run_lof:
        print(f"[信息] 样本量 {len(X_clean)} > {lof_threshold}，跳过LOF以节省计算资源")
        lof_pred = np.ones(len(X_clean))
        lof_scores = np.zeros(len(X_clean))
    else:
        n_neighbors = min(min_neighbors, len(X_clean) - 1)
        if n_neighbors < 5:
            print(f"[警告] 邻居数过少 ({n_neighbors})，LOF结果可能不稳定")

        lof_n_jobs = _adaptive_n_jobs(n_samples)
        print(f"[信息] 运行 LOF (n_neighbors={n_neighbors}, n_jobs={lof_n_jobs})...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lof = LocalOutlierFactor(
                contamination=contamination_val,
                n_neighbors=n_neighbors,
                n_jobs=lof_n_jobs
            )
            lof_pred = lof.fit_predict(X_scaled)
            lof_scores = -lof.negative_outlier_factor_  # 越大越异常

    # === 结果整合 ===
    result = df.loc[X_clean.index].copy()
    result["IsoForest_异常"] = (iso_pred == -1)
    result["IsoForest_分数"] = normalize_scores(iso_anomaly_scores).round(4)

    if run_lof:
        result["LOF_异常"] = (lof_pred == -1)
        result["LOF_分数"] = normalize_scores(lof_scores).round(4)
        # 综合判定：两种方法都认为异常
        result["综合异常"] = result["IsoForest_异常"] & result["LOF_异常"]
        # 综合分数：两个归一化分数的平均
        result["综合异常分数"] = ((result["IsoForest_分数"] + result["LOF_分数"]) / 2).round(4)
    else:
        result["LOF_异常"] = False
        result["LOF_分数"] = 0.0
        result["综合异常"] = result["IsoForest_异常"]
        result["综合异常分数"] = result["IsoForest_分数"]

    # === 输出统计 ===
    n_iso = result["IsoForest_异常"].sum()
    n_lof = result["LOF_异常"].sum() if run_lof else 0
    n_combined = result["综合异常"].sum()

    print(f"\n=== 多变量异常检测结果 ===")
    print(f"使用特征: {valid_cols}")
    print(f"有效样本: {len(X_clean)}")
    print(f"污染率: {contamination_val:.3f}")
    print(f"Isolation Forest 异常: {n_iso} ({n_iso/len(X_clean)*100:.1f}%)")
    if run_lof:
        print(f"LOF 异常: {n_lof} ({n_lof/len(X_clean)*100:.1f}%)")
    print(f"综合异常 (交集): {n_combined} ({n_combined/len(X_clean)*100:.1f}%)")

    if n_combined > 0:
        anomalies = result[result["综合异常"]].sort_values("综合异常分数", ascending=False)
        print(f"\n异常点摘要 (Top 10):")
        display_cols = valid_cols + ["综合异常分数", "IsoForest_分数"]
        if run_lof:
            display_cols.append("LOF_分数")
        print(anomalies[display_cols].head(10).to_string())

    return result


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="多变量异常检测：Isolation Forest + LOF 集成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python multivariate_anomaly.py -i data.csv -c price quantity discount
  python multivariate_anomaly.py -i data.xlsx -c col1 col2 col3 --contamination auto
  python multivariate_anomaly.py -i data.csv -c f1 f2 f3 f4 --lof-threshold 5000 -o result.csv
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("-c", "--columns", nargs="+", required=True, help="特征列名列表（至少2个）")
    parser.add_argument("-o", "--output", default="multivariate_anomaly_result.csv", help="输出CSV文件路径")
    parser.add_argument("--contamination", default="auto",
                        help="污染率: 'auto' 自适应估计或浮点数 (默认: auto)")
    parser.add_argument("--lof-threshold", type=int, default=10000,
                        help="LOF的样本量上限 (默认: 10000)")
    parser.add_argument("--min-neighbors", type=int, default=20,
                        help="LOF最小邻居数 (默认: 20)")

    args = parser.parse_args()

    # 加载数据
    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    # 解析污染率
    contamination = args.contamination
    if contamination != "auto":
        try:
            contamination = float(contamination)
            if not (0 < contamination < 0.5):
                print("[错误] contamination 必须在 (0, 0.5) 之间")
                sys.exit(1)
        except ValueError:
            print("[错误] contamination 必须是 'auto' 或浮点数")
            sys.exit(1)

    # 执行检测
    result = multivariate_anomaly(
        df,
        feature_cols=args.columns,
        contamination=contamination,
        lof_threshold=args.lof_threshold,
        min_neighbors=args.min_neighbors
    )

    if len(result) > 0:
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
