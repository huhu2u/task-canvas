#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分类模型训练脚本

支持 LogisticRegression / XGBoost / RandomForest 多模型训练对比，
自动处理类别不平衡，使用 Stratified K-Fold 交叉验证，
输出分类报告、混淆矩阵、特征重要性、阈值优化结果。

用法示例:
    python classification_train.py --input data.csv --target label --features col1,col2,col3
    python classification_train.py --input data.xlsx --target y --features col1,col2 --cv-folds 10
"""

import argparse
import sys
import warnings
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    f1_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.inspection import permutation_importance

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    elif ext == ".csv":
        return pd.read_csv(filepath)
    else:
        # 尝试 CSV
        return pd.read_csv(filepath)


def prepare_data(df, feature_cols, target_col, test_size=0.2, imbalance_strategy="auto", random_state=42):
    """
    数据准备：编码、填充、不平衡处理、分层划分。

    Parameters
    ----------
    df : DataFrame
    feature_cols : list[str]
    target_col : str
    test_size : float
    imbalance_strategy : str, one of 'auto', 'smote', 'class_weight', 'none'
    random_state : int

    Returns
    -------
    X_train, X_test, y_train, y_test, label_encoder, feature_names, imbalance_info
    """
    X = df[feature_cols].copy()
    y = df[target_col].copy()

    # 去除目标变量或全部特征为 NaN 的行
    valid_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X, y = X.loc[valid_idx], y.loc[valid_idx]

    if len(X) == 0:
        raise ValueError("有效样本量为 0，请检查数据和列名。")

    # 标签编码
    le = None
    if y.dtype == "object" or y.dtype.name == "category":
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        print(f"[信息] 标签编码映射: {dict(zip(le.classes_, le.transform(le.classes_)))}")
    else:
        y_encoded = y.values.astype(int)

    # 类别分布
    value_counts = pd.Series(y_encoded).value_counts().sort_index()
    imbalance_ratio = value_counts.max() / value_counts.min() if value_counts.min() > 0 else float("inf")
    print(f"\n[信息] 类别分布:")
    for cls, cnt in value_counts.items():
        print(f"  类别 {cls}: {cnt} 个样本 ({cnt / len(y_encoded) * 100:.1f}%)")
    print(f"  不平衡比率: {imbalance_ratio:.1f}:1")

    imbalance_info = {"ratio": imbalance_ratio, "strategy_used": "none"}

    # 缺失值填充
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols, index=X.index)

    # 分层划分
    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y_encoded, test_size=test_size, random_state=random_state, stratify=y_encoded
    )

    # 不平衡处理
    use_smote = False
    if imbalance_strategy == "auto":
        if imbalance_ratio > 5:
            use_smote = True
        elif imbalance_ratio > 2:
            imbalance_info["strategy_used"] = "class_weight"
    elif imbalance_strategy == "smote":
        use_smote = True
    elif imbalance_strategy == "class_weight":
        imbalance_info["strategy_used"] = "class_weight"

    if use_smote:
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(random_state=random_state)
            X_train_arr, y_train = smote.fit_resample(X_train, y_train)
            X_train = pd.DataFrame(X_train_arr, columns=feature_cols)
            imbalance_info["strategy_used"] = "smote"
            print(f"[信息] SMOTE 过采样后训练集分布: {dict(pd.Series(y_train).value_counts().sort_index())}")
        except ImportError:
            print("[警告] imbalanced-learn 未安装，退回使用 class_weight='balanced'")
            imbalance_info["strategy_used"] = "class_weight"

    return X_train, X_test, y_train, y_test, le, feature_cols, imbalance_info


def _adaptive_params(n_rows):
    """根据数据规模返回自适应的模型参数。"""
    if n_rows <= 10000:
        return {"n_jobs": -1, "rf_n_estimators": 200, "rf_max_depth": None, "cv_folds_cap": 10}
    elif n_rows <= 100000:
        return {"n_jobs": 2, "rf_n_estimators": 200, "rf_max_depth": 20, "cv_folds_cap": 5}
    else:
        return {"n_jobs": 1, "rf_n_estimators": 100, "rf_max_depth": 15, "cv_folds_cap": 3}


def train_models(X_train, X_test, y_train, y_test, feature_cols, cv_folds=5, imbalance_info=None, random_state=42):
    """
    训练多个分类器，使用 Stratified K-Fold 交叉验证评估。

    Returns
    -------
    models : dict[str, estimator]
    results : list[dict]
    best_model_name : str
    best_model : estimator
    """
    is_binary = len(np.unique(y_train)) == 2
    use_balanced = imbalance_info and imbalance_info.get("strategy_used") == "class_weight"

    # --- 数据规模自适应参数 ---
    ap = _adaptive_params(len(X_train))
    actual_cv = min(cv_folds, ap["cv_folds_cap"])
    n_jobs = ap["n_jobs"]
    print(f"[信息] 训练集规模: {len(X_train)} 行, n_jobs={n_jobs}, cv={actual_cv}")

    skf = StratifiedKFold(n_splits=actual_cv, shuffle=True, random_state=random_state)
    scoring = "roc_auc" if is_binary else "f1_weighted"

    models = {}
    results = []

    # 标准化（对 LR 有帮助）
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 1. LogisticRegression
    lr = LogisticRegression(
        class_weight="balanced" if use_balanced else None,
        random_state=random_state,
        max_iter=2000,
        n_jobs=n_jobs,
    )
    cv_scores = cross_val_score(lr, X_train_scaled, y_train, cv=skf, scoring=scoring, n_jobs=1)
    lr.fit(X_train_scaled, y_train)
    models["LogisticRegression"] = {"model": lr, "uses_scaled": True, "scaler": scaler}

    result_lr = _evaluate_model("LogisticRegression", lr, X_test_scaled, y_test, is_binary, cv_scores)
    results.append(result_lr)

    # 2. XGBoost
    try:
        import xgboost as xgb
        xgb_params = {
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 5,
            "random_state": random_state,
            "n_jobs": n_jobs,
            "eval_metric": "logloss",
            "verbosity": 0,
        }
        if is_binary and imbalance_info:
            neg_count = (y_train == 0).sum()
            pos_count = (y_train == 1).sum()
            if pos_count > 0:
                xgb_params["scale_pos_weight"] = neg_count / pos_count

        xgb_clf = xgb.XGBClassifier(**xgb_params)
        cv_scores_xgb = cross_val_score(xgb_clf, X_train, y_train, cv=skf, scoring=scoring, n_jobs=1)
        xgb_clf.fit(X_train, y_train)
        models["XGBoost"] = {"model": xgb_clf, "uses_scaled": False}

        result_xgb = _evaluate_model("XGBoost", xgb_clf, X_test, y_test, is_binary, cv_scores_xgb)
        results.append(result_xgb)
    except ImportError:
        print("[警告] xgboost 未安装，跳过 XGBoost 模型。")

    # 3. RandomForest
    rf = RandomForestClassifier(
        class_weight="balanced" if use_balanced else None,
        n_estimators=ap["rf_n_estimators"],
        max_depth=ap["rf_max_depth"],
        max_features="sqrt",
        random_state=random_state,
        n_jobs=n_jobs,
    )
    cv_scores_rf = cross_val_score(rf, X_train, y_train, cv=skf, scoring=scoring, n_jobs=1)
    rf.fit(X_train, y_train)
    models["RandomForest"] = {"model": rf, "uses_scaled": False}

    result_rf = _evaluate_model("RandomForest", rf, X_test, y_test, is_binary, cv_scores_rf)
    results.append(result_rf)

    # 汇总
    results_df = pd.DataFrame(results)
    print("\n[结果] 模型性能对比:")
    print(results_df.to_string(index=False))

    # 选择最优模型
    if is_binary:
        sort_key = "test_auc"
    else:
        sort_key = "test_f1_weighted"
    best_idx = results_df[sort_key].idxmax()
    best_name = results_df.loc[best_idx, "model"]
    best_entry = models[best_name]

    print(f"\n[结果] 最优模型: {best_name}")

    # 交叉验证稳定性检查
    for r in results:
        if r.get("cv_std", 0) > 0.1:
            print(f"[警告] {r['model']} 交叉验证标准差 = {r['cv_std']:.3f} > 0.1，模型稳定性不足。")

    # AUC 检查
    if is_binary:
        for r in results:
            if r.get("test_auc", 1.0) < 0.6:
                print(f"[警告] {r['model']} AUC = {r['test_auc']:.3f} < 0.6，近似随机猜测。")

    return models, results_df, best_name, best_entry


def _evaluate_model(name, model, X_test, y_test, is_binary, cv_scores):
    """评估单个模型。"""
    y_pred = model.predict(X_test)
    acc = (y_pred == y_test).mean()

    result = {
        "model": name,
        "test_accuracy": round(acc, 4),
        "cv_mean": round(cv_scores.mean(), 4),
        "cv_std": round(cv_scores.std(), 4),
    }

    if is_binary:
        y_prob = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_prob)
        ap = average_precision_score(y_test, y_prob)
        result["test_auc"] = round(auc, 4)
        result["test_ap"] = round(ap, 4)
    else:
        f1 = f1_score(y_test, y_pred, average="weighted")
        result["test_f1_weighted"] = round(f1, 4)

    return result


def get_classification_report_df(model, X_test, y_test, label_encoder=None):
    """以 DataFrame 形式返回分类报告。"""
    y_pred = model.predict(X_test)
    report_dict = classification_report(y_test, y_pred, output_dict=True)
    report_df = pd.DataFrame(report_dict).T
    report_df.index.name = "class"
    report_df = report_df.reset_index()

    if label_encoder is not None:
        # 用原始标签名替换数字
        mapping = {str(i): str(c) for i, c in enumerate(label_encoder.classes_)}
        report_df["class"] = report_df["class"].map(lambda x: mapping.get(x, x))

    return report_df


def get_confusion_matrix_df(model, X_test, y_test, label_encoder=None):
    """以 DataFrame 形式返回混淆矩阵。"""
    y_pred = model.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)
    labels = label_encoder.classes_ if label_encoder else sorted(np.unique(y_test))
    cm_df = pd.DataFrame(cm, index=[f"actual_{l}" for l in labels], columns=[f"pred_{l}" for l in labels])
    return cm_df


def compute_feature_importance(model, X_test, y_test, feature_cols, n_repeats=10, random_state=42):
    """使用 permutation importance 计算特征重要性。"""
    perm_n_jobs = min(2, os.cpu_count() or 1) if len(X_test) > 10000 else -1
    result = permutation_importance(model, X_test, y_test, n_repeats=n_repeats, random_state=random_state, n_jobs=perm_n_jobs)
    imp_df = pd.DataFrame({
        "feature": feature_cols,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False).reset_index(drop=True)
    return imp_df


def optimize_threshold(model, X_test, y_test):
    """
    二分类阈值优化：最大 F1 和最大 Youden's J。

    Returns
    -------
    threshold_df : DataFrame with columns [threshold, f1, youden_j, sensitivity, specificity]
    best_f1_threshold : float
    best_youden_threshold : float
    """
    y_prob = model.predict_proba(X_test)[:, 1]

    thresholds = np.linspace(0.01, 0.99, 99)
    records = []
    for t in thresholds:
        y_pred_t = (y_prob >= t).astype(int)
        tp = ((y_pred_t == 1) & (y_test == 1)).sum()
        tn = ((y_pred_t == 0) & (y_test == 0)).sum()
        fp = ((y_pred_t == 1) & (y_test == 0)).sum()
        fn = ((y_pred_t == 0) & (y_test == 1)).sum()

        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = sensitivity
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        youden_j = sensitivity + specificity - 1

        records.append({
            "threshold": round(t, 2),
            "f1": round(f1, 4),
            "youden_j": round(youden_j, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "precision": round(precision, 4),
        })

    threshold_df = pd.DataFrame(records)
    best_f1_idx = threshold_df["f1"].idxmax()
    best_youden_idx = threshold_df["youden_j"].idxmax()

    best_f1_t = threshold_df.loc[best_f1_idx, "threshold"]
    best_youden_t = threshold_df.loc[best_youden_idx, "threshold"]

    print(f"\n[结果] 阈值优化:")
    print(f"  最大 F1 阈值: {best_f1_t:.2f} (F1 = {threshold_df.loc[best_f1_idx, 'f1']:.4f})")
    print(f"  最大 Youden's J 阈值: {best_youden_t:.2f} (J = {threshold_df.loc[best_youden_idx, 'youden_j']:.4f})")

    return threshold_df, best_f1_t, best_youden_t


def main():
    parser = argparse.ArgumentParser(description="分类模型训练：多模型对比 + 交叉验证 + 阈值优化")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, help="特征列名，逗号分隔")
    parser.add_argument("--test-size", type=float, default=0.2, help="测试集比例 (默认 0.2)")
    parser.add_argument("--cv-folds", type=int, default=5, help="交叉验证折数 (默认 5)")
    parser.add_argument("--imbalance", default="auto", choices=["auto", "smote", "class_weight", "none"],
                        help="不平衡处理策略 (默认 auto)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录 (默认当前目录)")

    args = parser.parse_args()
    feature_cols = [c.strip() for c in args.features.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)
    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    # 检查列是否存在
    missing_cols = [c for c in feature_cols + [args.target] if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下列不存在: {missing_cols}")
        print(f"[信息] 可用列: {list(df.columns)}")
        sys.exit(1)

    # 数据准备
    X_train, X_test, y_train, y_test, le, feature_cols, imbalance_info = prepare_data(
        df, feature_cols, args.target, args.test_size, args.imbalance, args.seed
    )

    # 训练模型
    models, results_df, best_name, best_entry = train_models(
        X_train, X_test, y_train, y_test, feature_cols,
        cv_folds=args.cv_folds, imbalance_info=imbalance_info, random_state=args.seed
    )

    # 保存模型对比结果
    results_path = os.path.join(args.output_dir, "model_comparison.csv")
    results_df.to_csv(results_path, index=False)
    print(f"\n[输出] 模型对比表已保存: {results_path}")

    # 获取最优模型和对应测试数据
    best_model = best_entry["model"]
    if best_entry.get("uses_scaled"):
        X_test_eval = best_entry["scaler"].transform(X_test)
    else:
        X_test_eval = X_test

    # 分类报告
    report_df = get_classification_report_df(best_model, X_test_eval, y_test, le)
    report_path = os.path.join(args.output_dir, "classification_report.csv")
    report_df.to_csv(report_path, index=False)
    print(f"\n[结果] {best_name} 分类报告:")
    print(report_df.to_string(index=False))
    print(f"[输出] 分类报告已保存: {report_path}")

    # 混淆矩阵
    cm_df = get_confusion_matrix_df(best_model, X_test_eval, y_test, le)
    cm_path = os.path.join(args.output_dir, "confusion_matrix.csv")
    cm_df.to_csv(cm_path)
    print(f"\n[结果] 混淆矩阵:")
    print(cm_df.to_string())
    print(f"[输出] 混淆矩阵已保存: {cm_path}")

    # 特征重要性（使用原始尺度的数据）
    # 对 LR 使用 scaled 数据，其他用原始数据
    fi_df = compute_feature_importance(best_model, X_test_eval, y_test, feature_cols)
    fi_path = os.path.join(args.output_dir, "feature_importance.csv")
    fi_df.to_csv(fi_path, index=False)
    print(f"\n[结果] 特征重要性 (permutation importance):")
    print(fi_df.to_string(index=False))
    print(f"[输出] 特征重要性已保存: {fi_path}")

    # 阈值优化（仅二分类）
    is_binary = len(np.unique(y_train)) == 2
    if is_binary:
        threshold_df, best_f1_t, best_youden_t = optimize_threshold(best_model, X_test_eval, y_test)
        threshold_path = os.path.join(args.output_dir, "threshold_optimization.csv")
        threshold_df.to_csv(threshold_path, index=False)
        print(f"[输出] 阈值优化表已保存: {threshold_path}")

    # 测试集小类别样本检查
    test_counts = pd.Series(y_test).value_counts()
    for cls, cnt in test_counts.items():
        if cnt < 10:
            print(f"[警告] 测试集类别 {cls} 仅有 {cnt} 个样本，评估结果可能不可靠。")

    print("\n[完成] 分类模型训练与评估完毕。")


if __name__ == "__main__":
    main()
