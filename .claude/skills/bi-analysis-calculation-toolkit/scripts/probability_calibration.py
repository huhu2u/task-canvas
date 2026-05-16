#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
概率校准脚本

对已训练模型的概率输出进行校准（Platt Scaling / Isotonic Regression），
评估校准效果并输出分箱校准对照表。

用法示例:
    python probability_calibration.py --input data.csv --target label --features col1,col2,col3
    python probability_calibration.py --input data.csv --target y --features col1,col2 --method isotonic
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss, log_loss

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def calibrate_model(X_train, y_train, X_test, y_test, method="sigmoid", base_model=None, cv_folds=5, random_state=42):
    """
    训练基模型并进行概率校准。

    Parameters
    ----------
    X_train, y_train : 训练数据
    X_test, y_test : 测试数据
    method : str, 'sigmoid' (Platt Scaling) 或 'isotonic' (Isotonic Regression)
    base_model : sklearn estimator, 如果为 None 则使用 RandomForest
    cv_folds : int, 校准交叉验证折数
    random_state : int

    Returns
    -------
    calibrated_model, raw_probs, calibrated_probs, metrics_dict
    """
    # --- 数据规模分级，自适应调整参数以防止内存溢出 ---
    n_rows = len(X_train)
    if n_rows <= 10000:
        size_tier = "small"
        rf_n_jobs = -1
        rf_n_estimators = 200
        rf_max_depth = None
        adaptive_cv_folds = cv_folds
    elif n_rows <= 100000:
        size_tier = "medium"
        rf_n_jobs = 2
        rf_n_estimators = 200
        rf_max_depth = 20
        adaptive_cv_folds = cv_folds
    else:
        size_tier = "large"
        rf_n_jobs = 1
        rf_n_estimators = 100
        rf_max_depth = 15
        adaptive_cv_folds = min(cv_folds, 3)

    print(f"[信息] 训练数据规模: {n_rows} 行 → 等级: {size_tier}"
          f"（n_estimators={rf_n_estimators}, max_depth={rf_max_depth}, "
          f"n_jobs={rf_n_jobs}, cv={adaptive_cv_folds}）")

    if base_model is None:
        base_model = RandomForestClassifier(
            n_estimators=rf_n_estimators, max_depth=rf_max_depth,
            class_weight="balanced", random_state=random_state, n_jobs=rf_n_jobs
        )

    # 训练基模型
    base_model.fit(X_train, y_train)

    # 校准模型
    calibrated = CalibratedClassifierCV(base_model, cv=adaptive_cv_folds, method=method)
    calibrated.fit(X_train, y_train)

    # 获取概率
    y_prob_raw = base_model.predict_proba(X_test)[:, 1]
    y_prob_cal = calibrated.predict_proba(X_test)[:, 1]

    # 计算指标
    brier_raw = brier_score_loss(y_test, y_prob_raw)
    brier_cal = brier_score_loss(y_test, y_prob_cal)

    # 安全计算 log_loss
    eps = 1e-15
    logloss_raw = log_loss(y_test, np.clip(y_prob_raw, eps, 1 - eps))
    logloss_cal = log_loss(y_test, np.clip(y_prob_cal, eps, 1 - eps))

    metrics = {
        "brier_score_raw": round(brier_raw, 6),
        "brier_score_calibrated": round(brier_cal, 6),
        "brier_improvement": round(brier_raw - brier_cal, 6),
        "log_loss_raw": round(logloss_raw, 6),
        "log_loss_calibrated": round(logloss_cal, 6),
        "calibration_method": method,
        "calibration_effective": brier_cal < brier_raw,
    }

    print(f"\n[结果] 概率校准 ({method}):")
    print(f"  Brier Score (校准前): {brier_raw:.6f}")
    print(f"  Brier Score (校准后): {brier_cal:.6f}")
    print(f"  改善幅度: {brier_raw - brier_cal:.6f}")
    print(f"  Log Loss (校准前): {logloss_raw:.6f}")
    print(f"  Log Loss (校准后): {logloss_cal:.6f}")
    if brier_cal < brier_raw:
        print(f"  结论: 校准有效，概率输出更可靠。")
    else:
        print(f"  结论: 校准未改善，原始概率已较准确。")

    return calibrated, y_prob_raw, y_prob_cal, metrics


def build_calibration_table(y_test, y_prob_raw, y_prob_cal, n_bins=10):
    """
    构建分箱校准对照表。

    Returns
    -------
    DataFrame: 各概率区间的预测概率均值、实际正类频率、样本数
    """
    records = []

    for prob_arr, label in [(y_prob_raw, "raw"), (y_prob_cal, "calibrated")]:
        try:
            fraction_of_positives, mean_predicted_value = calibration_curve(
                y_test, prob_arr, n_bins=n_bins, strategy="uniform"
            )
        except ValueError:
            # 如果数据太少，减少 bins
            fraction_of_positives, mean_predicted_value = calibration_curve(
                y_test, prob_arr, n_bins=min(5, n_bins), strategy="uniform"
            )

        for i in range(len(fraction_of_positives)):
            records.append({
                "source": label,
                "bin_index": i + 1,
                "mean_predicted_prob": round(mean_predicted_value[i], 4),
                "actual_positive_rate": round(fraction_of_positives[i], 4),
                "calibration_error": round(abs(mean_predicted_value[i] - fraction_of_positives[i]), 4),
            })

    # 补充每个 bin 的样本数量
    bin_edges = np.linspace(0, 1, n_bins + 1)
    for source, prob_arr in [("raw", y_prob_raw), ("calibrated", y_prob_cal)]:
        for i in range(n_bins):
            mask = (prob_arr >= bin_edges[i]) & (prob_arr < bin_edges[i + 1])
            if i == n_bins - 1:
                mask = (prob_arr >= bin_edges[i]) & (prob_arr <= bin_edges[i + 1])
            count = mask.sum()
            # 查找对应记录
            for rec in records:
                if rec["source"] == source and rec["bin_index"] == i + 1:
                    rec["sample_count"] = int(count)
                    break

    cal_df = pd.DataFrame(records)
    return cal_df


def run_both_methods(X_train, y_train, X_test, y_test, random_state=42):
    """
    同时运行 sigmoid 和 isotonic 两种校准方法并对比。

    Returns
    -------
    comparison_df : DataFrame
    """
    results = []
    for method in ["sigmoid", "isotonic"]:
        try:
            _, _, _, metrics = calibrate_model(
                X_train, y_train, X_test, y_test, method=method, random_state=random_state
            )
            results.append(metrics)
        except Exception as e:
            print(f"[警告] {method} 校准失败: {e}")

    if results:
        comparison_df = pd.DataFrame(results)
        print("\n[结果] 两种校准方法对比:")
        print(comparison_df.to_string(index=False))
        return comparison_df
    return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="概率校准：Platt Scaling / Isotonic Regression")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--target", required=True, help="目标变量列名 (二分类)")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--method", default="both", choices=["sigmoid", "isotonic", "both"],
                        help="校准方法 (默认 both)")
    parser.add_argument("--n-bins", type=int, default=10, help="校准曲线分箱数 (默认 10)")
    parser.add_argument("--test-size", type=float, default=0.2, help="测试集比例 (默认 0.2)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录 (默认当前目录)")

    args = parser.parse_args()
    feature_cols = [c.strip() for c in args.features.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)
    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    # 检查列
    missing_cols = [c for c in feature_cols + [args.target] if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下列不存在: {missing_cols}")
        sys.exit(1)

    # 准备数据
    X = df[feature_cols].copy()
    y = df[args.target].copy()
    valid_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X, y = X.loc[valid_idx], y.loc[valid_idx]

    le = None
    if y.dtype == "object" or y.dtype.name == "category":
        le = LabelEncoder()
        y_vals = le.fit_transform(y)
    else:
        y_vals = y.values.astype(int)

    n_classes = len(np.unique(y_vals))
    if n_classes != 2:
        print(f"[错误] 概率校准当前仅支持二分类，检测到 {n_classes} 个类别。")
        sys.exit(1)

    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y_vals, test_size=args.test_size, random_state=args.seed, stratify=y_vals
    )

    # 执行校准
    if args.method == "both":
        comparison_df = run_both_methods(X_train, y_train, X_test, y_test, random_state=args.seed)
        comp_path = os.path.join(args.output_dir, "calibration_comparison.csv")
        comparison_df.to_csv(comp_path, index=False)
        print(f"[输出] 校准方法对比已保存: {comp_path}")

        # 用两种方法中更好的构建详细表
        best_method = "sigmoid"
        if len(comparison_df) == 2:
            if comparison_df.iloc[1]["brier_score_calibrated"] < comparison_df.iloc[0]["brier_score_calibrated"]:
                best_method = "isotonic"
        calibrated, y_prob_raw, y_prob_cal, metrics = calibrate_model(
            X_train, y_train, X_test, y_test, method=best_method, random_state=args.seed
        )
    else:
        calibrated, y_prob_raw, y_prob_cal, metrics = calibrate_model(
            X_train, y_train, X_test, y_test, method=args.method, random_state=args.seed
        )

    # 校准指标
    metrics_df = pd.DataFrame([metrics])
    metrics_path = os.path.join(args.output_dir, "calibration_metrics.csv")
    metrics_df.to_csv(metrics_path, index=False)
    print(f"[输出] 校准指标已保存: {metrics_path}")

    # 分箱校准对照表
    cal_table = build_calibration_table(y_test, y_prob_raw, y_prob_cal, n_bins=args.n_bins)
    cal_table_path = os.path.join(args.output_dir, "calibration_table.csv")
    cal_table.to_csv(cal_table_path, index=False)
    print(f"\n[结果] 分箱校准对照表:")
    print(cal_table.to_string(index=False))
    print(f"[输出] 校准对照表已保存: {cal_table_path}")

    print("\n[完成] 概率校准分析完毕。")


if __name__ == "__main__":
    main()
