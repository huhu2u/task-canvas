#!/usr/bin/env python3
"""
购物篮关联规则挖掘脚本
方法：FP-Growth 频繁项集 + 关联规则
增强：确信度(conviction)和杠杆率(leverage)指标

用法：
    python basket_analysis.py -i data.csv --order-col order_id --item-col product -o rules.csv
    python basket_analysis.py -i data.xlsx --order-col tid --item-col item --min-support 0.02
"""

import argparse
import sys
import numpy as np
import pandas as pd


def basket_analysis(df, order_col, item_col, min_support=0.01, min_confidence=0.3,
                    min_lift=1.0, top_n=50):
    """
    购物篮关联规则挖掘。

    Args:
        df: pd.DataFrame，每行一个 (事务ID, 项目) 记录
        order_col: 事务ID列名
        item_col: 项目列名
        min_support: 最小支持度阈值
        min_confidence: 最小置信度阈值
        min_lift: 最小提升度阈值
        top_n: 输出Top N规则

    Returns:
        tuple: (rules_df, frequent_itemsets_df)
    """
    try:
        from mlxtend.frequent_patterns import fpgrowth, association_rules
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        print("[错误] 需要安装 mlxtend: pip install mlxtend")
        sys.exit(1)

    # 数据验证
    if order_col not in df.columns:
        print(f"[错误] 列 '{order_col}' 不存在")
        return None, None
    if item_col not in df.columns:
        print(f"[错误] 列 '{item_col}' 不存在")
        return None, None

    # 清理数据
    df = df[[order_col, item_col]].dropna()
    df[item_col] = df[item_col].astype(str).str.strip()
    df = df[df[item_col] != ""]

    n_transactions = df[order_col].nunique()
    n_items = df[item_col].nunique()
    print(f"[信息] 事务数: {n_transactions}, 唯一项目数: {n_items}")

    if n_transactions < 2:
        print("[错误] 事务数不足，至少需要2个事务")
        return None, None

    # 过滤低频项目（出现率 < 1%），减小矩阵维度
    item_counts = df[item_col].value_counts()
    min_count = max(1, int(n_transactions * 0.01))
    frequent_items = item_counts[item_counts >= min_count].index
    n_filtered = n_items - len(frequent_items)
    if n_filtered > 0:
        print(f"[信息] 过滤出现率 < 1% 的低频项目 {n_filtered} 个，保留 {len(frequent_items)} 个项目")
        df = df[df[item_col].isin(frequent_items)]
        n_items = df[item_col].nunique()

    # 构建事务列表
    transactions = df.groupby(order_col)[item_col].apply(list).tolist()

    # 过滤单项事务
    multi_item_txns = [t for t in transactions if len(t) > 1]
    single_item_txns = len(transactions) - len(multi_item_txns)
    if single_item_txns > 0:
        print(f"[信息] 单项事务 {single_item_txns} 个 (不产生关联规则)")

    if len(multi_item_txns) == 0:
        print("[警告] 所有事务均为单项，无法生成关联规则")
        return pd.DataFrame(), pd.DataFrame()

    # 矩阵规模检查
    matrix_size = n_transactions * n_items
    if matrix_size > 50_000_000:
        print(f"[警告] One-Hot 矩阵规模 ({n_transactions} × {n_items} = {matrix_size:,}) 超过5000万，可能占用大量内存")

    # One-Hot 编码（尝试使用 sparse 模式减少内存占用）
    te = TransactionEncoder()
    try:
        te_array = te.fit_transform(transactions, sparse=True)
        df_te = pd.DataFrame.sparse.from_spmatrix(te_array, columns=te.columns_)
    except TypeError:
        # mlxtend 版本不支持 sparse 参数，回退到密集矩阵
        te_array = te.fit_transform(transactions)
        df_te = pd.DataFrame(te_array, columns=te.columns_)

    # FP-Growth
    print(f"[信息] 运行 FP-Growth (min_support={min_support})...")
    frequent_itemsets = fpgrowth(df_te, min_support=min_support, use_colnames=True)

    if len(frequent_itemsets) == 0:
        print("[警告] 未发现频繁项集，尝试降低 min_support")
        return pd.DataFrame(), pd.DataFrame()

    frequent_itemsets["length"] = frequent_itemsets["itemsets"].apply(len)
    print(f"[信息] 发现 {len(frequent_itemsets)} 个频繁项集")

    # 生成关联规则
    multi_itemsets = frequent_itemsets[frequent_itemsets["length"] >= 2]
    if len(multi_itemsets) == 0:
        print("[警告] 无多项频繁项集，无法生成关联规则")
        return pd.DataFrame(), frequent_itemsets

    rules = association_rules(frequent_itemsets, metric="lift", min_threshold=min_lift)
    rules = rules[rules["confidence"] >= min_confidence]

    if len(rules) == 0:
        print("[警告] 在当前阈值下未发现关联规则，尝试降低 min_confidence 或 min_lift")
        return pd.DataFrame(), frequent_itemsets

    # === 计算额外指标 ===
    # Conviction（确信度）: (1 - support(consequent)) / (1 - confidence)
    # 值越大表示关联越强，inf表示完美关联
    rules["conviction"] = rules.apply(
        lambda r: (1 - r["consequent support"]) / (1 - r["confidence"])
        if r["confidence"] < 1 else np.inf,
        axis=1
    )

    # Leverage（杠杆率）: support - (support(antecedent) * support(consequent))
    # > 0 表示正关联
    rules["leverage"] = rules["support"] - (
        rules["antecedent support"] * rules["consequent support"]
    )

    # 排序
    rules = rules.sort_values("lift", ascending=False)

    # 格式化输出
    rules_display = rules.copy()
    rules_display["前项"] = rules_display["antecedents"].apply(lambda x: ", ".join(sorted(x)))
    rules_display["后项"] = rules_display["consequents"].apply(lambda x: ", ".join(sorted(x)))
    rules_display["支持度(%)"] = (rules_display["support"] * 100).round(3)
    rules_display["置信度(%)"] = (rules_display["confidence"] * 100).round(2)
    rules_display["提升度"] = rules_display["lift"].round(3)
    rules_display["确信度"] = rules_display["conviction"].apply(
        lambda x: "inf" if x == np.inf else f"{x:.3f}"
    )
    rules_display["杠杆率"] = rules_display["leverage"].round(5)

    output_cols = ["前项", "后项", "支持度(%)", "置信度(%)", "提升度", "确信度", "杠杆率"]
    top_rules = rules_display[output_cols].head(top_n)

    print(f"\n=== 关联规则挖掘结果 (Top {min(top_n, len(rules_display))}, 按提升度降序) ===")
    print(top_rules.to_string(index=False))
    print(f"\n共发现 {len(rules)} 条规则 "
          f"(support >= {min_support*100:.1f}%, "
          f"confidence >= {min_confidence*100:.0f}%, "
          f"lift >= {min_lift})")

    # 负相关规则警告
    neg_rules = rules[rules["lift"] < 1]
    if len(neg_rules) > 0:
        print(f"\n[信息] 发现 {len(neg_rules)} 条负相关规则 (lift < 1)，表示项目间互斥关系")

    return rules_display, frequent_itemsets


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="购物篮关联规则挖掘（FP-Growth）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python basket_analysis.py -i orders.csv --order-col order_id --item-col product_name
  python basket_analysis.py -i data.xlsx --order-col tid --item-col item --min-support 0.02
  python basket_analysis.py -i data.csv --order-col basket_id --item-col sku -o rules.csv --top-n 30
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--order-col", required=True, help="事务ID列名")
    parser.add_argument("--item-col", required=True, help="项目列名")
    parser.add_argument("-o", "--output", default="basket_rules.csv", help="输出CSV文件路径")
    parser.add_argument("--min-support", type=float, default=0.01, help="最小支持度 (默认: 0.01)")
    parser.add_argument("--min-confidence", type=float, default=0.3, help="最小置信度 (默认: 0.3)")
    parser.add_argument("--min-lift", type=float, default=1.0, help="最小提升度 (默认: 1.0)")
    parser.add_argument("--top-n", type=int, default=50, help="输出Top N规则 (默认: 50)")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    rules, itemsets = basket_analysis(
        df,
        order_col=args.order_col,
        item_col=args.item_col,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        min_lift=args.min_lift,
        top_n=args.top_n
    )

    if rules is not None and len(rules) > 0:
        output_cols = ["前项", "后项", "支持度(%)", "置信度(%)", "提升度", "确信度", "杠杆率"]
        rules[output_cols].to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
