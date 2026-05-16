#!/usr/bin/env python3
"""
独立性检验脚本 - 卡方检验 / Fisher 精确检验

功能：
  - 自动选择卡方检验或 Fisher 精确检验（期望频数 < 5 且 2x2 表时）
  - 计算 Cramer's V 关联强度
  - 输出交叉表及行/列百分比
  - 结果输出到 CSV 和控制台

用法：
  python independence_test.py <数据文件> \
    --var1 <变量1> --var2 <变量2> \
    [--alpha 0.05] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
from scipy import stats


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


def independence_test(df, var1, var2, alpha=0.05):
    """
    独立性检验。

    参数：
      df:    DataFrame
      var1:  变量1 列名
      var2:  变量2 列名
      alpha: 显著性水平

    返回：
      result: dict — 检验结果摘要
    """
    contingency = pd.crosstab(df[var1], df[var2])
    n = contingency.values.sum()

    # 卡方检验
    chi2_stat, p_chi2, dof, expected = stats.chi2_contingency(contingency)
    min_expected = expected.min()

    print(f"\n{'='*70}")
    print(f"  独立性检验: {var1} vs {var2}")
    print(f"{'='*70}")
    print(f"  交叉表维度: {contingency.shape[0]} x {contingency.shape[1]}")
    print(f"  总样本量: {n}")
    print(f"  最小期望频数: {min_expected:.1f}")

    result = {
        "变量1": var1,
        "变量2": var2,
        "交叉表行数": contingency.shape[0],
        "交叉表列数": contingency.shape[1],
        "总样本量": n,
        "最小期望频数": round(min_expected, 2),
        "alpha": alpha
    }

    # 选择检验方法
    if min_expected < 5 and contingency.shape == (2, 2):
        odds_ratio, p_value = stats.fisher_exact(contingency)
        test_name = "Fisher 精确检验"
        stat_val = odds_ratio
        result.update({
            "检验方法": test_name,
            "统计量(OR)": round(odds_ratio, 4),
            "P值": round(p_value, 6)
        })
        print(f"\n  方法: {test_name}（最小期望频数 < 5）")
        print(f"  比值比 OR = {odds_ratio:.4f}")
        print(f"  P 值 = {p_value:.6f}")
    else:
        test_name = "卡方检验"
        stat_val = chi2_stat
        p_value = p_chi2
        result.update({
            "检验方法": test_name,
            "统计量(Chi2)": round(chi2_stat, 4),
            "自由度": dof,
            "P值": round(p_value, 6)
        })
        print(f"\n  方法: {test_name}（df={dof}）")
        print(f"  Chi2 = {chi2_stat:.4f}")
        print(f"  P 值 = {p_value:.6f}")

        if min_expected < 5:
            print(f"  警告：存在期望频数 < 5 的单元格，卡方检验可能不够准确")

    # Cramer's V
    min_dim = min(contingency.shape) - 1
    cramers_v = np.sqrt(chi2_stat / (n * min_dim)) if min_dim > 0 and n > 0 else 0
    strength = "弱" if cramers_v < 0.1 else "中" if cramers_v < 0.3 else "强"
    result["Cramers_V"] = round(cramers_v, 4)
    result["关联强度"] = strength
    print(f"  Cramer's V = {cramers_v:.4f}（{strength}关联）")

    # 显著性判定
    is_significant = p_value < alpha
    result["显著性"] = "显著" if is_significant else "不显著"

    if is_significant:
        print(f"\n  结论: {var1} 与 {var2} 存在显著关联（p < {alpha}）")
    else:
        print(f"\n  结论: {var1} 与 {var2} 无显著关联（p >= {alpha}）")

    # 交叉表百分比
    print(f"\n  交叉表（频数）：")
    print(contingency.to_string())
    row_pct = pd.crosstab(df[var1], df[var2], normalize="index").round(4)
    print(f"\n  交叉表（行百分比）：")
    print(row_pct.to_string())

    return result, contingency, row_pct


def main():
    parser = argparse.ArgumentParser(
        description="独立性检验（卡方 / Fisher 精确检验）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--var1", required=True, help="分类变量1")
    parser.add_argument("--var2", required=True, help="分类变量2")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.var1, args.var2] if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result, contingency, row_pct = independence_test(df, args.var1, args.var2, args.alpha)

    # 保存结果
    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "independence_test.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n检验结果已保存至: {out_path}")

    # 保存交叉表
    ct_path = os.path.join(args.output_dir, "contingency_table.csv")
    contingency.to_csv(ct_path, encoding='utf-8-sig')
    print(f"交叉表已保存至: {ct_path}")


if __name__ == "__main__":
    main()
