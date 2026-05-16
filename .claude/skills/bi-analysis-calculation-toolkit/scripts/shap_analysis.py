#!/usr/bin/env python3
"""
SHAP 值分析脚本 - 全局特征重要性 + 局部单样本归因 + 特征交互值

功能：
  - 全局 SHAP 特征重要性（mean |SHAP|）
  - 单样本 SHAP 归因（指定样本索引）
  - 特征交互值：Top 特征对的 SHAP 交互效应
  - 大数据集自动抽样（>10k 行时默认抽样 5000 行）
  - SHAP 值矩阵输出

用法：
  python shap_analysis.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--sample-idx 0] [--max-samples 5000] [--output-dir <输出目录>]
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


def _adaptive_n_jobs(n_rows):
    """根据数据规模自适应选择 n_jobs，避免大数据集占满 CPU 导致内存溢出。"""
    if n_rows > 50000:
        return 1
    elif n_rows > 10000:
        return 2
    else:
        return -1


def shap_analysis(df, target_col, feature_cols, sample_idx=0, max_samples=5000):
    """
    SHAP 值分析主流程。

    返回：
      global_importance_df:   全局 SHAP 特征重要性
      shap_values_df:         SHAP 值矩阵
      interaction_df:         Top 特征对交互值
      local_explanation_df:   指定样本的局部 SHAP 归因
    """
    import shap
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import LabelEncoder

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    common_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X = X.loc[common_idx].reset_index(drop=True)
    y = y.loc[common_idx].reset_index(drop=True)

    # 缺失值填充
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    # 根据数据规模自适应 n_jobs
    n_jobs = _adaptive_n_jobs(len(X_imputed))

    # 判断分类/回归
    is_classifier = y.dtype == 'object' or y.nunique() <= 20
    le = None

    if is_classifier:
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        class_names = list(le.classes_.astype(str))
        print(f"\n任务类型：分类（{len(class_names)} 个类别）")

        model = RandomForestClassifier(
            n_estimators=200, max_depth=10,
            random_state=42, n_jobs=n_jobs
        )
        model.fit(X_imputed, y_encoded)
        train_acc = model.score(X_imputed, y_encoded)
        print(f"RandomForest 训练集准确率：{train_acc:.4f}")
    else:
        class_names = None
        print(f"\n任务类型：回归")
        model = RandomForestRegressor(
            n_estimators=200, max_depth=10,
            random_state=42, n_jobs=n_jobs
        )
        model.fit(X_imputed, y.values)
        from sklearn.metrics import r2_score
        y_pred = model.predict(X_imputed)
        r2 = r2_score(y.values, y_pred)
        print(f"RandomForest 训练集 R2：{r2:.4f}")

    # 大数据集抽样
    n_total = len(X_imputed)
    if n_total > 10000:
        print(f"\n数据量 {n_total} > 10000，抽样 {max_samples} 行用于 SHAP 计算")
        np.random.seed(42)
        sample_indices = np.random.choice(n_total, size=min(max_samples, n_total), replace=False)
        X_shap = X_imputed.iloc[sample_indices].reset_index(drop=True)
    else:
        X_shap = X_imputed.copy()
        sample_indices = np.arange(n_total)

    # 计算 SHAP 值
    print(f"\n{'='*70}")
    print(f"  SHAP 值计算（{len(X_shap)} 个样本）")
    print(f"{'='*70}")

    explainer = shap.TreeExplainer(model)
    shap_values_raw = explainer.shap_values(X_shap)

    # 处理分类任务的多输出 SHAP 值
    if is_classifier and isinstance(shap_values_raw, list):
        if len(shap_values_raw) == 2:
            # 二分类：使用正类（类别1）的 SHAP 值
            shap_values_matrix = np.array(shap_values_raw[1])
        else:
            # 多分类：使用所有类别 SHAP 值的绝对值均值
            shap_values_matrix = np.mean(np.abs(np.array(shap_values_raw)), axis=0)
    elif hasattr(shap_values_raw, 'values'):
        shap_values_matrix = shap_values_raw.values
    else:
        shap_values_matrix = np.array(shap_values_raw)

    # 确保维度正确
    if shap_values_matrix.ndim > 2:
        shap_values_matrix = np.mean(np.abs(shap_values_matrix), axis=-1)

    # 1. 全局 SHAP 特征重要性
    mean_abs_shap = np.mean(np.abs(shap_values_matrix), axis=0)
    global_importance_df = pd.DataFrame({
        "特征": feature_cols,
        "mean_abs_SHAP": mean_abs_shap.round(6),
        "重要性排名": pd.Series(mean_abs_shap).rank(ascending=False).astype(int).values
    }).sort_values("mean_abs_SHAP", ascending=False).reset_index(drop=True)

    global_importance_df["累计贡献(%)"] = (
        global_importance_df["mean_abs_SHAP"].cumsum() /
        global_importance_df["mean_abs_SHAP"].sum() * 100
    ).round(1)

    print(f"\n  -- 全局 SHAP 特征重要性 --")
    print(global_importance_df.to_string(index=False))

    # 2. SHAP 值矩阵
    shap_values_df = pd.DataFrame(
        shap_values_matrix,
        columns=[f"SHAP_{feat}" for feat in feature_cols]
    )

    # 3. 局部样本解释
    local_explanation_df = pd.DataFrame()

    if sample_idx < len(X_shap):
        local_shap = shap_values_matrix[sample_idx]
        local_feat_values = X_shap.iloc[sample_idx]

        local_explanation_df = pd.DataFrame({
            "特征": feature_cols,
            "特征值": local_feat_values.values.round(4),
            "SHAP值": local_shap.round(6),
            "abs_SHAP": np.abs(local_shap).round(6),
            "方向": ["正向推动" if s > 0 else ("负向推动" if s < 0 else "无影响") for s in local_shap]
        }).sort_values("abs_SHAP", ascending=False).reset_index(drop=True)

        print(f"\n  -- 样本 {sample_idx} 的 SHAP 局部归因 --")
        if is_classifier:
            pred = model.predict(X_shap.iloc[[sample_idx]])[0]
            pred_label = le.inverse_transform([pred])[0] if le else pred
            print(f"  预测类别：{pred_label}")
            proba = model.predict_proba(X_shap.iloc[[sample_idx]])[0]
            print(f"  预测概率：{dict(zip(class_names, proba.round(4)))}")
        else:
            pred = model.predict(X_shap.iloc[[sample_idx]])[0]
            print(f"  预测值：{pred:.4f}")
            print(f"  实际值：{y.iloc[sample_indices[sample_idx]]}")

        print(local_explanation_df.head(10).to_string(index=False))

        # SHAP 值方向一致性提示
        top_features = local_explanation_df.head(5)["特征"].tolist()
        print(f"\n  Top-5 驱动特征：{top_features}")
    else:
        print(f"\n  ⚠ 样本索引 {sample_idx} 超出范围（最大={len(X_shap)-1}），跳过局部解释")

    # 4. 特征交互值（Top 特征对）
    interaction_df = pd.DataFrame()
    try:
        top_n = min(5, len(feature_cols))
        top_feat_idx = np.argsort(mean_abs_shap)[-top_n:]

        print(f"\n  -- 特征交互值（Top {top_n} 特征对）--")

        n_interaction_samples = min(500, len(X_shap))

        interaction_rows = []

        for i in range(len(top_feat_idx)):
            for j in range(i + 1, len(top_feat_idx)):
                fi, fj = top_feat_idx[i], top_feat_idx[j]
                shap_i = shap_values_matrix[:n_interaction_samples, fi]
                shap_j = shap_values_matrix[:n_interaction_samples, fj]

                # 使用 SHAP 值的相关性作为交互度量
                if len(shap_i) > 1:
                    corr = np.corrcoef(shap_i, shap_j)[0, 1]
                else:
                    corr = 0.0

                # 交互强度：SHAP值乘积的均值
                interaction_strength = np.mean(shap_i * shap_j)

                interaction_rows.append({
                    "特征1": feature_cols[fi],
                    "特征2": feature_cols[fj],
                    "SHAP相关性": round(corr, 4) if not np.isnan(corr) else 0.0,
                    "交互强度": round(interaction_strength, 6),
                    "交互方向": "协同" if interaction_strength > 0 else "拮抗"
                })

        interaction_df = pd.DataFrame(interaction_rows)
        if not interaction_df.empty:
            interaction_df = interaction_df.sort_values(
                "交互强度", key=abs, ascending=False
            ).reset_index(drop=True)
            print(interaction_df.to_string(index=False))

    except Exception as e:
        print(f"  特征交互值计算出错：{e}")

    return global_importance_df, shap_values_df, interaction_df, local_explanation_df


def main():
    parser = argparse.ArgumentParser(
        description="SHAP 值分析（全局重要性 + 局部归因 + 特征交互）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--sample-idx", type=int, default=0,
                        help="需要局部解释的样本索引（默认0）")
    parser.add_argument("--max-samples", type=int, default=5000,
                        help="SHAP 计算最大样本数（默认5000）")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    global_imp_df, shap_values_df, interaction_df, local_df = shap_analysis(
        df, args.target, args.features,
        args.sample_idx, args.max_samples
    )

    # 保存全局重要性
    global_path = os.path.join(args.output_dir, "shap_global_importance.csv")
    global_imp_df.to_csv(global_path, index=False, encoding='utf-8-sig')
    print(f"\n全局 SHAP 重要性已保存至: {global_path}")

    # 保存 SHAP 值矩阵
    shap_path = os.path.join(args.output_dir, "shap_values.csv")
    shap_values_df.to_csv(shap_path, index=False, encoding='utf-8-sig')
    print(f"SHAP 值矩阵已保存至: {shap_path}")

    # 保存交互值
    if not interaction_df.empty:
        inter_path = os.path.join(args.output_dir, "shap_interaction.csv")
        interaction_df.to_csv(inter_path, index=False, encoding='utf-8-sig')
        print(f"特征交互值已保存至: {inter_path}")

    # 保存局部解释
    if not local_df.empty:
        local_path = os.path.join(args.output_dir, "shap_local_explanation.csv")
        local_df.to_csv(local_path, index=False, encoding='utf-8-sig')
        print(f"局部 SHAP 归因已保存至: {local_path}")


if __name__ == "__main__":
    main()
