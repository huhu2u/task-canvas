#!/usr/bin/env python3
"""
决策树规则提取脚本 - 浅层决策树 + if-then 规则提取 + 低置信度剪枝

功能：
  - 训练浅层决策树（可控制深度和最小叶节点样本数）
  - 提取所有叶节点的 if-then 规则
  - 低置信度规则剪枝：移除置信度低于阈值的规则
  - 输出规则列表为 CSV 和结构化 JSON 格式
  - 输出特征重要性排名

用法：
  python decision_tree_rules.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--max-depth 4] [--min-confidence 0.6] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import json
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


def extract_rules(tree, feature_names, class_names=None, is_classifier=True):
    """
    从决策树中递归提取所有叶节点的 if-then 规则。

    返回：
      规则列表，每条规则为 dict，包含条件、预测、置信度、样本数等信息。
    """
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != -2 else "undefined!"
        for i in tree_.feature
    ]

    rules = []

    def recurse(node, conditions):
        if tree_.feature[node] == -2:
            # 叶节点
            samples = int(tree_.n_node_samples[node])
            value = tree_.value[node][0]

            if is_classifier:
                predicted_class_idx = int(np.argmax(value))
                predicted_class = class_names[predicted_class_idx] if class_names else str(predicted_class_idx)
                confidence = round(float(value[predicted_class_idx] / value.sum()), 4)
                distribution = {
                    str(class_names[i] if class_names else i): int(v)
                    for i, v in enumerate(value)
                }
            else:
                predicted_class = round(float(tree_.value[node][0][0]), 4)
                confidence = None
                distribution = None

            # 构建规则文本
            if conditions:
                condition_text = " AND ".join(conditions)
            else:
                condition_text = "（无条件，根节点即叶节点）"

            rule = {
                "规则条件": condition_text,
                "预测": predicted_class,
                "置信度": confidence,
                "样本数": samples,
                "分布": distribution,
            }
            rules.append(rule)
            return

        feat = feature_name[node]
        threshold = round(float(tree_.threshold[node]), 4)

        # 左子树
        left_cond = conditions + [f"{feat} <= {threshold}"]
        recurse(tree_.children_left[node], left_cond)

        # 右子树
        right_cond = conditions + [f"{feat} > {threshold}"]
        recurse(tree_.children_right[node], right_cond)

    recurse(0, [])
    return rules


def decision_tree_rules(df, target_col, feature_cols, max_depth=4,
                        min_confidence=0.6, min_samples_leaf=10):
    """
    决策树规则提取主流程。

    返回：
      rules_df:      规则表 DataFrame
      rules_json:    规则结构化 JSON (list of dict)
      importance_df: 特征重要性 DataFrame
    """
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import LabelEncoder

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    # 去除缺失
    common_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X = X.loc[common_idx].reset_index(drop=True)
    y = y.loc[common_idx].reset_index(drop=True)

    # 缺失值填充
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    # 判断分类/回归
    is_classifier = y.dtype == 'object' or y.nunique() <= 20
    class_names = None
    le = None

    if is_classifier:
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        class_names = list(le.classes_.astype(str))
        print(f"\n任务类型：分类（{len(class_names)} 个类别：{class_names}）")

        model = DecisionTreeClassifier(
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=42
        )
        model.fit(X_imputed, y_encoded)
        train_acc = model.score(X_imputed, y_encoded)
        print(f"训练集准确率：{train_acc:.4f}")
    else:
        print(f"\n任务类型：回归")
        model = DecisionTreeRegressor(
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=42
        )
        model.fit(X_imputed, y.values)
        from sklearn.metrics import r2_score
        y_pred = model.predict(X_imputed)
        r2 = r2_score(y.values, y_pred)
        print(f"训练集 R2：{r2:.4f}")

    print(f"树深度：{model.get_depth()}, 叶节点数：{model.get_n_leaves()}")

    # 提取规则
    print(f"\n{'='*70}")
    print(f"  决策树规则提取")
    print(f"{'='*70}")

    all_rules = extract_rules(model, feature_cols, class_names, is_classifier)
    print(f"  提取到 {len(all_rules)} 条原始规则")

    # 低置信度规则剪枝（仅分类任务）
    if is_classifier and min_confidence > 0:
        pruned_rules = [r for r in all_rules if r["置信度"] >= min_confidence]
        removed = len(all_rules) - len(pruned_rules)
        print(f"  低置信度剪枝（阈值={min_confidence}）：移除 {removed} 条规则")
        if removed > 0:
            print(f"  剩余 {len(pruned_rules)} 条规则")
    else:
        pruned_rules = all_rules

    # 叶节点样本数警告
    small_leaf_rules = [r for r in pruned_rules if r["样本数"] < 10]
    if small_leaf_rules:
        print(f"  警告：有 {len(small_leaf_rules)} 条规则的叶节点样本数 < 10，可能过拟合")

    # 输出规则
    print(f"\n  -- 规则列表（按样本数排序）--")
    pruned_rules_sorted = sorted(pruned_rules, key=lambda r: r["样本数"], reverse=True)
    for i, rule in enumerate(pruned_rules_sorted[:20]):
        if is_classifier:
            print(f"  规则{i+1}: IF {rule['规则条件']}")
            print(f"         THEN 预测={rule['预测']}, 置信度={rule['置信度']}, "
                  f"样本数={rule['样本数']}")
        else:
            print(f"  规则{i+1}: IF {rule['规则条件']}")
            print(f"         THEN 预测值={rule['预测']}, 样本数={rule['样本数']}")

    if len(pruned_rules_sorted) > 20:
        print(f"  ...（共 {len(pruned_rules_sorted)} 条，仅显示前20条）")

    # 构建规则 DataFrame
    rules_rows = []
    for i, rule in enumerate(pruned_rules_sorted):
        row = {
            "规则编号": i + 1,
            "条件": rule["规则条件"],
            "预测": rule["预测"],
            "置信度": rule["置信度"],
            "样本数": rule["样本数"],
        }
        if rule.get("分布"):
            for cls, cnt in rule["分布"].items():
                row[f"类别_{cls}_样本数"] = cnt
        rules_rows.append(row)

    rules_df = pd.DataFrame(rules_rows)

    # 构建 JSON 规则
    rules_json = []
    for i, rule in enumerate(pruned_rules_sorted):
        json_rule = {
            "rule_id": i + 1,
            "conditions": rule["规则条件"].split(" AND ") if "AND" in rule["规则条件"] else [rule["规则条件"]],
            "prediction": rule["预测"],
            "confidence": rule["置信度"],
            "samples": rule["样本数"],
        }
        if rule.get("分布"):
            json_rule["class_distribution"] = rule["分布"]
        rules_json.append(json_rule)

    # 特征重要性
    importances = model.feature_importances_
    importance_df = pd.DataFrame({
        "特征": feature_cols,
        "重要性": importances.round(4),
        "重要性_归一化": (importances / importances.max()).round(4) if importances.max() > 0 else importances
    }).sort_values("重要性", ascending=False).reset_index(drop=True)

    importance_df["累计重要性(%)"] = (
        importance_df["重要性"].cumsum() / importance_df["重要性"].sum() * 100
    ).round(1)

    print(f"\n  -- 特征重要性 --")
    print(importance_df.to_string(index=False))

    return rules_df, rules_json, importance_df


def main():
    parser = argparse.ArgumentParser(
        description="决策树规则提取（浅层决策树 + if-then 规则 + 低置信度剪枝）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--max-depth", type=int, default=4, help="决策树最大深度（默认4）")
    parser.add_argument("--min-confidence", type=float, default=0.6,
                        help="最低置信度阈值，低于此值的规则将被剪枝（默认0.6）")
    parser.add_argument("--min-samples-leaf", type=int, default=10,
                        help="叶节点最小样本数（默认10）")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    rules_df, rules_json, importance_df = decision_tree_rules(
        df, args.target, args.features,
        args.max_depth, args.min_confidence, args.min_samples_leaf
    )

    # 保存规则 CSV
    rules_path = os.path.join(args.output_dir, "tree_rules.csv")
    rules_df.to_csv(rules_path, index=False, encoding='utf-8-sig')
    print(f"\n规则列表已保存至: {rules_path}")

    # 保存规则 JSON
    json_path = os.path.join(args.output_dir, "tree_rules.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(rules_json, f, ensure_ascii=False, indent=2)
    print(f"规则 JSON 已保存至: {json_path}")

    # 保存特征重要性
    imp_path = os.path.join(args.output_dir, "tree_feature_importance.csv")
    importance_df.to_csv(imp_path, index=False, encoding='utf-8-sig')
    print(f"特征重要性已保存至: {imp_path}")


if __name__ == "__main__":
    main()
