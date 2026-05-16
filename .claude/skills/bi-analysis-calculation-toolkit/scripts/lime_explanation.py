#!/usr/bin/env python3
"""
LIME 局部解释 + 稳定性检查 + 反事实解释脚本

功能：
  - 对指定样本进行 LIME 局部线性近似
  - 输出各特征对该预测的贡献权重
  - 稳定性检查：多次运行（不同随机种子），检查特征排名一致性
  - 输出局部 R2（近似质量指标）
  - 反事实解释：找出最少需要改变哪些特征才能得到不同预测

用法：
  python lime_explanation.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    --sample-idx <样本索引> \
    [--n-stability-runs 5] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import warnings
import pandas as pd
import numpy as np
from collections import Counter

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


def generate_counterfactual(model, X_data, sample, sample_idx,
                            feature_cols, is_classifier, le, class_names):
    """
    生成反事实解释：找出最少需要改变哪些特征才能改变预测结果。

    使用贪心搜索策略：每次改变一个特征的值，寻找使预测变化最大的修改。
    """
    if is_classifier:
        original_pred = model.predict(sample.reshape(1, -1))[0]
        original_label = le.inverse_transform([original_pred])[0] if le else original_pred
        original_proba = model.predict_proba(sample.reshape(1, -1))[0]
        print(f"  原始预测：{original_label}，概率={original_proba.round(4)}")

        changes = []
        for i, feat in enumerate(feature_cols):
            candidates = np.percentile(X_data[feat], [10, 25, 50, 75, 90])

            best_change = None
            best_proba_shift = 0

            for val in candidates:
                if abs(val - sample[i]) < 1e-10:
                    continue

                test_sample = sample.copy()
                test_sample[i] = val
                new_proba = model.predict_proba(test_sample.reshape(1, -1))[0]
                new_pred = model.predict(test_sample.reshape(1, -1))[0]

                proba_shift = abs(new_proba[original_pred] - original_proba[original_pred])

                if new_pred != original_pred and (best_change is None or proba_shift > best_proba_shift):
                    best_change = {
                        "特征": feat,
                        "原始值": round(float(sample[i]), 4),
                        "建议值": round(float(val), 4),
                        "变化幅度": round(float(val - sample[i]), 4),
                        "变化百分比(%)": round(float((val - sample[i]) / (abs(sample[i]) + 1e-10) * 100), 2),
                        "新预测": le.inverse_transform([new_pred])[0] if le else str(new_pred),
                        "概率变化": round(float(proba_shift), 4)
                    }
                    best_proba_shift = proba_shift
                elif best_change is None and proba_shift > best_proba_shift:
                    best_change = {
                        "特征": feat,
                        "原始值": round(float(sample[i]), 4),
                        "建议值": round(float(val), 4),
                        "变化幅度": round(float(val - sample[i]), 4),
                        "变化百分比(%)": round(float((val - sample[i]) / (abs(sample[i]) + 1e-10) * 100), 2),
                        "新预测": le.inverse_transform([new_pred])[0] if le else str(new_pred),
                        "概率变化": round(float(proba_shift), 4)
                    }
                    best_proba_shift = proba_shift

            if best_change:
                changes.append(best_change)

        changes = sorted(changes, key=lambda x: x["概率变化"], reverse=True)

    else:
        original_pred = model.predict(sample.reshape(1, -1))[0]
        print(f"  原始预测值：{original_pred:.4f}")

        changes = []
        for i, feat in enumerate(feature_cols):
            candidates = np.percentile(X_data[feat], [10, 25, 50, 75, 90])

            best_change = None
            best_impact = 0

            for val in candidates:
                if abs(val - sample[i]) < 1e-10:
                    continue

                test_sample = sample.copy()
                test_sample[i] = val
                new_pred = model.predict(test_sample.reshape(1, -1))[0]
                impact = abs(new_pred - original_pred)

                if impact > best_impact:
                    best_impact = impact
                    best_change = {
                        "特征": feat,
                        "原始值": round(float(sample[i]), 4),
                        "建议值": round(float(val), 4),
                        "变化幅度": round(float(val - sample[i]), 4),
                        "变化百分比(%)": round(float((val - sample[i]) / (abs(sample[i]) + 1e-10) * 100), 2),
                        "新预测值": round(float(new_pred), 4),
                        "预测变化": round(float(new_pred - original_pred), 4)
                    }

            if best_change:
                changes.append(best_change)

        changes = sorted(changes, key=lambda x: abs(x.get("预测变化", 0)), reverse=True)

    counterfactual_df = pd.DataFrame(changes[:10]) if changes else pd.DataFrame()

    if not counterfactual_df.empty:
        print(f"  找到 {len(changes)} 个可改变预测的特征修改方案（显示 Top 10）：")
        print(counterfactual_df.to_string(index=False))

        # 合理性检查
        for _, row in counterfactual_df.iterrows():
            pct = abs(row.get("变化百分比(%)", 0))
            if pct > 500:
                print(f"  ⚠ 特征 '{row['特征']}' 变化幅度较大（{pct:.0f}%），需审查可行性")
    else:
        print(f"  未找到可改变预测的特征修改方案")

    return counterfactual_df


def _adaptive_n_jobs(n_rows):
    """根据数据规模自适应选择 n_jobs，避免大数据集占满 CPU 导致内存溢出。"""
    if n_rows > 50000:
        return 1
    elif n_rows > 10000:
        return 2
    else:
        return -1


def lime_explanation(df, target_col, feature_cols, sample_idx=0,
                     n_stability_runs=5):
    """
    LIME 局部解释 + 稳定性检查主流程。

    返回：
      explanation_df:   特征贡献权重
      stability_df:     稳定性报告
      counterfactual_df: 反事实解释
    """
    try:
        import lime
        import lime.lime_tabular
    except ImportError:
        print("错误: 需要安装 lime 库: pip install lime")
        sys.exit(1)

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
    class_names = None

    if is_classifier:
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        class_names = list(le.classes_.astype(str))
        print(f"\n任务类型：分类（{len(class_names)} 个类别：{class_names}）")

        model = RandomForestClassifier(
            n_estimators=200, max_depth=10,
            random_state=42, n_jobs=n_jobs
        )
        model.fit(X_imputed, y_encoded)
    else:
        print(f"\n任务类型：回归")
        model = RandomForestRegressor(
            n_estimators=200, max_depth=10,
            random_state=42, n_jobs=n_jobs
        )
        model.fit(X_imputed, y.values)

    # 检查样本索引
    if sample_idx >= len(X_imputed):
        print(f"错误：样本索引 {sample_idx} 超出范围（最大 {len(X_imputed)-1}）")
        sys.exit(1)

    sample = X_imputed.iloc[sample_idx].values
    actual_value = y.iloc[sample_idx]

    print(f"\n{'='*70}")
    print(f"  LIME 局部解释 - 样本 {sample_idx}")
    print(f"{'='*70}")
    print(f"  实际值：{actual_value}")
    if is_classifier:
        pred_class = model.predict(sample.reshape(1, -1))[0]
        pred_label = le.inverse_transform([pred_class])[0] if le else pred_class
        pred_proba = model.predict_proba(sample.reshape(1, -1))[0]
        print(f"  预测类别：{pred_label}")
        print(f"  预测概率：{dict(zip(class_names, pred_proba.round(4)))}")
    else:
        pred_value = model.predict(sample.reshape(1, -1))[0]
        print(f"  预测值：{pred_value:.4f}")

    # 构建 LIME 解释器（LIME 仅用 training_data 估计特征分布，大数据集抽样即可）
    _LIME_MAX_ROWS = 10000
    if len(X_imputed) > _LIME_MAX_ROWS:
        _rng = np.random.RandomState(42)
        _lime_idx = _rng.choice(len(X_imputed), size=_LIME_MAX_ROWS, replace=False)
        _lime_training_data = X_imputed.values[_lime_idx]
    else:
        _lime_training_data = X_imputed.values

    if is_classifier:
        explainer = lime.lime_tabular.LimeTabularExplainer(
            training_data=_lime_training_data,
            feature_names=feature_cols,
            class_names=class_names,
            mode='classification',
            random_state=42
        )
    else:
        explainer = lime.lime_tabular.LimeTabularExplainer(
            training_data=_lime_training_data,
            feature_names=feature_cols,
            mode='regression',
            random_state=42
        )

    # 单次 LIME 解释
    print(f"\n  -- LIME 局部解释 --")
    if is_classifier:
        explanation = explainer.explain_instance(
            sample, model.predict_proba,
            num_features=len(feature_cols),
            num_samples=5000
        )
    else:
        explanation = explainer.explain_instance(
            sample, model.predict,
            num_features=len(feature_cols),
            num_samples=5000
        )

    # 提取特征贡献
    local_r2 = explanation.score

    explanation_rows = []
    for feat_desc, weight in explanation.as_list():
        explanation_rows.append({
            "特征描述": feat_desc,
            "贡献权重": round(weight, 6),
            "贡献方向": "正向" if weight > 0 else ("负向" if weight < 0 else "无"),
            "绝对贡献": round(abs(weight), 6)
        })

    explanation_df = pd.DataFrame(explanation_rows)
    explanation_df = explanation_df.sort_values("绝对贡献", ascending=False).reset_index(drop=True)
    explanation_df["局部R2"] = round(local_r2, 4)

    print(f"  局部 R2（近似质量）：{local_r2:.4f}")
    if local_r2 < 0.6:
        print(f"  ⚠ 局部 R2 < 0.6，LIME 线性近似质量较差，解释结果需谨慎")
    print(explanation_df[["特征描述", "贡献权重", "贡献方向"]].to_string(index=False))

    # 稳定性检查
    print(f"\n  -- 稳定性检查（{n_stability_runs} 次运行）--")
    all_rankings = []

    for run_i in range(n_stability_runs):
        seed = 42 + run_i * 7
        # 使用不同随机种子重新构造解释器（复用抽样后的训练数据）
        exp_local = lime.lime_tabular.LimeTabularExplainer(
            training_data=_lime_training_data,
            feature_names=feature_cols,
            class_names=class_names if is_classifier else None,
            mode='classification' if is_classifier else 'regression',
            random_state=seed
        )

        if is_classifier:
            exp_run = exp_local.explain_instance(
                sample, model.predict_proba,
                num_features=len(feature_cols),
                num_samples=5000
            )
        else:
            exp_run = exp_local.explain_instance(
                sample, model.predict,
                num_features=len(feature_cols),
                num_samples=5000
            )

        run_weights = sorted(exp_run.as_list(), key=lambda x: abs(x[1]), reverse=True)
        ranking = [desc for desc, _ in run_weights]
        all_rankings.append(ranking)

    # 计算稳定性指标
    stability_rows = []
    n_features_check = min(5, len(feature_cols))

    for rank_pos in range(n_features_check):
        features_at_pos = [r[rank_pos] if rank_pos < len(r) else None for r in all_rankings]
        counter = Counter(features_at_pos)
        most_common_feat, most_common_count = counter.most_common(1)[0]
        consistency = round(most_common_count / n_stability_runs, 2)

        stability_rows.append({
            "排名位置": rank_pos + 1,
            "最频繁特征": most_common_feat,
            "出现次数": most_common_count,
            f"一致性({n_stability_runs}次)": consistency,
            "所有特征": str(dict(counter))
        })

    stability_df = pd.DataFrame(stability_rows)

    # 总体稳定性评估
    consistency_col = f"一致性({n_stability_runs}次)"
    top3_consistency = stability_df.head(3)[consistency_col].mean()
    print(f"  Top-3 特征排名一致性：{top3_consistency:.2f}")
    if top3_consistency >= 0.8:
        print(f"  ✓ 稳定性良好")
    elif top3_consistency >= 0.6:
        print(f"  ⚠ 稳定性中等，结果仅供参考")
    else:
        print(f"  ✗ 稳定性较差，LIME 解释不可靠")
    print(stability_df.to_string(index=False))

    # 反事实解释
    print(f"\n  -- 反事实解释 --")
    counterfactual_df = generate_counterfactual(
        model, X_imputed, sample, sample_idx,
        feature_cols, is_classifier, le, class_names
    )

    return explanation_df, stability_df, counterfactual_df


def main():
    parser = argparse.ArgumentParser(
        description="LIME 局部解释 + 稳定性检查 + 反事实解释",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--sample-idx", type=int, required=True,
                        help="需要解释的样本索引")
    parser.add_argument("--n-stability-runs", type=int, default=5,
                        help="LIME 稳定性检查运行次数（默认5）")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    explanation_df, stability_df, counterfactual_df = lime_explanation(
        df, args.target, args.features,
        args.sample_idx, args.n_stability_runs
    )

    # 保存 LIME 解释
    exp_path = os.path.join(args.output_dir, "lime_explanation.csv")
    explanation_df.to_csv(exp_path, index=False, encoding='utf-8-sig')
    print(f"\nLIME 解释已保存至: {exp_path}")

    # 保存稳定性报告
    stab_path = os.path.join(args.output_dir, "lime_stability.csv")
    stability_df.to_csv(stab_path, index=False, encoding='utf-8-sig')
    print(f"稳定性报告已保存至: {stab_path}")

    # 保存反事实解释
    if not counterfactual_df.empty:
        cf_path = os.path.join(args.output_dir, "counterfactual.csv")
        counterfactual_df.to_csv(cf_path, index=False, encoding='utf-8-sig')
        print(f"反事实解释已保存至: {cf_path}")


if __name__ == "__main__":
    main()
