#!/usr/bin/env python3
"""
特征重要性分析脚本 - RandomForest + 置换重要性 + SHAP + 偏依赖

功能：
  - RandomForest 内置特征重要性（基于不纯度下降）
  - 置换重要性（permutation importance）
  - SHAP 值（基于 TreeExplainer）全局重要性
  - 偏依赖数据输出（Top 特征的边际效应数值表）
  - 5 折交叉验证评估模型质量

用法：
  python feature_importance.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--top-n 15] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


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


def feature_importance_analysis(df, target_col, feature_cols, top_n=15, max_samples=50000):
    """
    特征重要性综合分析。

    参数：
      df:           DataFrame
      target_col:   目标变量列名
      feature_cols: 特征列名列表
      top_n:        输出 Top N 特征
      max_samples:  大数据集训练抽样上限（默认 50000）

    返回：
      importance_df: 特征重要性汇总 DataFrame
      model:         训练好的模型
      shap_df:       SHAP 值 DataFrame（可能为 None）
      pd_df:         偏依赖数据 DataFrame（可能为 None）
    """
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance

    X = df[feature_cols].copy()
    y = df[target_col].copy()
    common_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X = X.loc[common_idx]
    y = y.loc[common_idx]

    # 缺失值填充
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols, index=X.index)

    # --- 数据规模分级 + 自适应参数 ---
    n_rows = len(X_imputed)
    if n_rows <= 10000:
        size_tier = "small"
        rf_n_jobs = -1
        rf_n_estimators = 200
        rf_max_depth = None
        cv_folds = 5
        perm_n_jobs = -1
    elif n_rows <= 100000:
        size_tier = "medium"
        rf_n_jobs = 2
        rf_n_estimators = 200
        rf_max_depth = 20
        cv_folds = 5
        perm_n_jobs = 2
    else:
        size_tier = "large"
        rf_n_jobs = 1
        rf_n_estimators = 100
        rf_max_depth = 15
        cv_folds = 3
        perm_n_jobs = 1

    print(f"\n数据规模: {n_rows} 行 × {len(feature_cols)} 特征 → 等级: {size_tier}")

    # 大数据集抽样训练
    X_train = X_imputed
    y_train = y
    if size_tier == "large" and n_rows > max_samples:
        sample_idx = X_imputed.sample(n=max_samples, random_state=42).index
        X_train = X_imputed.loc[sample_idx]
        y_train = y.loc[sample_idx]
        print(f"大数据集抽样: {n_rows} → {max_samples} 行用于模型训练")

    is_continuous = y.nunique() > 10
    ModelClass = RandomForestRegressor if is_continuous else RandomForestClassifier

    model = ModelClass(n_estimators=rf_n_estimators, random_state=42, n_jobs=rf_n_jobs,
                       max_features="sqrt", max_depth=rf_max_depth)
    model.fit(X_train, y_train)

    # 交叉验证
    scoring = "r2" if is_continuous else "accuracy"
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring=scoring,
                                n_jobs=rf_n_jobs)
    metric_name = "R2" if is_continuous else "Accuracy"
    print(f"\n模型评估（{cv_folds}折交叉验证）：{metric_name} = {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    if is_continuous and cv_scores.mean() < 0.1:
        print("警告：候选特征解释力不足（R2 < 0.1），建议补充其他因素")

    # 1. RF 内置特征重要性
    rf_importance = model.feature_importances_

    # 2. 置换重要性
    perm_result = permutation_importance(model, X_train, y_train, n_repeats=10,
                                          random_state=42, n_jobs=perm_n_jobs)
    perm_importance = perm_result.importances_mean

    # 3. SHAP 值
    shap_importance = np.zeros(len(feature_cols))
    shap_df = None
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        # 对大数据集抽样
        sample_size = min(1000, len(X_imputed))
        X_sample = X_imputed.sample(n=sample_size, random_state=42)
        shap_values = explainer.shap_values(X_sample)

        if isinstance(shap_values, list):
            shap_values = shap_values[-1]

        shap_importance = np.abs(shap_values).mean(axis=0)

        # 保存 SHAP 值矩阵
        shap_df = pd.DataFrame(shap_values, columns=feature_cols, index=X_sample.index)
        print("SHAP 值计算完成")
    except ImportError:
        print("提示：安装 shap 可获得 SHAP 特征重要性（pip install shap）")
    except Exception as e:
        print(f"SHAP 计算出错: {e}")

    # 汇总表
    importance_df = pd.DataFrame({
        "特征": feature_cols,
        "RF内置重要性": rf_importance,
        "置换重要性": perm_importance,
        "SHAP重要性": shap_importance
    })

    # 归一化以便比较
    for col in ["RF内置重要性", "置换重要性", "SHAP重要性"]:
        col_max = importance_df[col].max()
        if col_max > 0:
            importance_df[f"{col}_归一化"] = (importance_df[col] / col_max).round(4)
        else:
            importance_df[f"{col}_归一化"] = 0

    importance_df["综合重要性"] = (
        importance_df["RF内置重要性_归一化"] * 0.3 +
        importance_df["置换重要性_归一化"] * 0.3 +
        importance_df["SHAP重要性_归一化"] * 0.4
    ).round(4)

    importance_df = importance_df.sort_values("综合重要性", ascending=False)
    importance_df["累计综合重要性(%)"] = (
        importance_df["综合重要性"].cumsum() / importance_df["综合重要性"].sum() * 100
    ).round(1)

    print(f"\n{'='*70}")
    print(f"  特征重要性排名（Top {top_n}）")
    print(f"{'='*70}")
    display_cols = ["特征", "RF内置重要性", "置换重要性", "SHAP重要性", "综合重要性", "累计综合重要性(%)"]
    print(importance_df[display_cols].head(top_n).to_string(index=False))

    # 4. 偏依赖数据
    pd_df = None
    try:
        from sklearn.inspection import partial_dependence
        top_features = importance_df["特征"].head(min(5, top_n)).tolist()
        pd_rows = []

        # 大数据集对偏依赖计算抽样
        pd_max_samples = 5000
        if len(X_imputed) > pd_max_samples:
            X_pd = X_imputed.sample(n=pd_max_samples, random_state=42)
            print(f"偏依赖计算抽样: {len(X_imputed)} → {pd_max_samples} 行")
        else:
            X_pd = X_imputed

        for feat in top_features:
            feat_idx = feature_cols.index(feat)
            result = partial_dependence(model, X_pd, features=[feat_idx],
                                         grid_resolution=50)
            grid_values = result["grid_values"][0] if isinstance(result, dict) else result[1][0]
            avg_predictions = result["average"][0] if isinstance(result, dict) else result[0][0]

            for gv, ap in zip(grid_values, avg_predictions):
                pd_rows.append({
                    "特征": feat,
                    "特征值": round(float(gv), 4),
                    "偏依赖值": round(float(ap), 4)
                })

        pd_df = pd.DataFrame(pd_rows)
        print(f"\n偏依赖数据已计算（Top {len(top_features)} 特征）")
    except Exception as e:
        print(f"偏依赖计算出错: {e}")

    return importance_df, model, shap_df, pd_df


def main():
    parser = argparse.ArgumentParser(
        description="特征重要性分析（RF + 置换 + SHAP + 偏依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--top-n", type=int, default=15, help="输出 Top N 特征")
    parser.add_argument("--max-samples", type=int, default=50000,
                        help="大数据集训练抽样上限（默认 50000）")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    importance_df, model, shap_df, pd_df = feature_importance_analysis(
        df, args.target, args.features, args.top_n, args.max_samples
    )

    # 保存结果
    imp_path = os.path.join(args.output_dir, "feature_importance.csv")
    importance_df.to_csv(imp_path, index=False, encoding='utf-8-sig')
    print(f"\n特征重要性已保存至: {imp_path}")

    if shap_df is not None:
        shap_path = os.path.join(args.output_dir, "shap_values.csv")
        shap_df.to_csv(shap_path, index=False, encoding='utf-8-sig')
        print(f"SHAP 值矩阵已保存至: {shap_path}")

    if pd_df is not None:
        pd_path = os.path.join(args.output_dir, "partial_dependence.csv")
        pd_df.to_csv(pd_path, index=False, encoding='utf-8-sig')
        print(f"偏依赖数据已保存至: {pd_path}")


if __name__ == "__main__":
    main()
