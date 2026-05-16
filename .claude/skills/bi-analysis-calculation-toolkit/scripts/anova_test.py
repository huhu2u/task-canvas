#!/usr/bin/env python3
"""
方差分析脚本 - ANOVA / Welch ANOVA / Kruskal-Wallis + Tukey HSD 事后检验

功能：
  - 自动检测正态性和方差齐性，选择合适的检验方法
  - 单因素 ANOVA（方差齐时）/ Welch ANOVA（方差不齐时）
  - Kruskal-Wallis 非参数检验（非正态时）
  - Tukey HSD 事后检验 + Bonferroni / Benjamini-Hochberg 多重比较校正
  - 结果输出到 CSV 和控制台

用法：
  python anova_test.py <数据文件> \
    --group-col <分组列> --target-col <目标列> \
    [--alpha 0.05] [--correction bonferroni] [--output-dir <输出目录>]
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


def apply_correction(p_values, method="bonferroni"):
    """
    多重比较校正。

    参数：
      p_values: P 值列表
      method:   "bonferroni" 或 "bh"（Benjamini-Hochberg）

    返回：
      校正后的 P 值列表
    """
    n = len(p_values)
    if method == "bonferroni":
        return [min(p * n, 1.0) for p in p_values]
    elif method in ("bh", "benjamini-hochberg"):
        # Benjamini-Hochberg
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]
        corrected = np.zeros(n)
        for i, idx in enumerate(sorted_indices):
            corrected[idx] = min(sorted_p[i] * n / (i + 1), 1.0)
        # 确保单调性
        for i in range(n - 2, -1, -1):
            corrected[sorted_indices[i]] = min(
                corrected[sorted_indices[i]],
                corrected[sorted_indices[i + 1]] if i + 1 < n else 1.0
            )
        return corrected.tolist()
    else:
        return list(p_values)


def anova_test(df, group_col, target_col, alpha=0.05, correction="bonferroni"):
    """
    多组比较检验。

    参数：
      df:           DataFrame
      group_col:    分组列名
      target_col:   目标变量列名
      alpha:        显著性水平
      correction:   多重比较校正方法

    返回：
      anova_result: dict — ANOVA 摘要
      posthoc_df:   DataFrame — 事后检验结果（若显著）
    """
    group_names = sorted(df[group_col].dropna().unique())
    groups = [df[df[group_col] == g][target_col].dropna().values for g in group_names]

    if len(group_names) < 3:
        print("警告：组数 < 3，建议使用双样本检验（two_sample_test.py）")

    # 描述性统计
    print(f"\n{'='*70}")
    print(f"  多组比较检验（alpha={alpha}）")
    print(f"{'='*70}")
    desc_rows = []
    for name, g in zip(group_names, groups):
        desc_rows.append({
            "组": name, "样本量": len(g),
            "均值": round(np.mean(g), 4), "标准差": round(np.std(g, ddof=1), 4),
            "中位数": round(np.median(g), 4)
        })
        print(f"  组 '{name}': n={len(g)}, 均值={np.mean(g):.4f}, "
              f"标准差={np.std(g, ddof=1):.4f}")

    # 正态性检验
    print(f"\n  -- 前提检验 --")
    all_normal = True
    for name, g in zip(group_names, groups):
        if len(g) < 3:
            print(f"  组 '{name}' 样本量过小，跳过正态性检验")
            all_normal = False
            continue
        if len(g) < 5000:
            _, p_norm = stats.shapiro(g)
            test_nm = "Shapiro-Wilk"
        else:
            _, p_norm = stats.normaltest(g)
            test_nm = "D'Agostino"
        is_normal = p_norm > 0.05
        if not is_normal:
            all_normal = False
        label = "近似正态" if is_normal else "非正态"
        print(f"  组 '{name}' 正态性（{test_nm}）: p={p_norm:.4f} -> {label}")

    # 方差齐性
    lev_stat, lev_p = stats.levene(*groups)
    equal_var = lev_p > 0.05
    print(f"  方差齐性（Levene）: p={lev_p:.4f} -> {'等方差' if equal_var else '不等方差'}")

    # 选择检验方法
    anova_result = {}
    print(f"\n  -- 检验结果 --")

    if all_normal and equal_var:
        # 标准 ANOVA
        f_stat, p_value = stats.f_oneway(*groups)
        test_name = "单因素 ANOVA"
        anova_result = {
            "检验方法": test_name, "统计量(F)": round(f_stat, 4),
            "P值": round(p_value, 6), "alpha": alpha,
            "显著性": "显著" if p_value < alpha else "不显著"
        }
        print(f"  方法: {test_name}")
        print(f"  F = {f_stat:.4f}, P = {p_value:.6f}")

    elif all_normal and not equal_var:
        # Welch ANOVA
        try:
            from scipy.stats import alexandergovern
            result = alexandergovern(*groups)
            test_name = "Welch ANOVA (Alexander-Govern)"
            anova_result = {
                "检验方法": test_name, "统计量": round(result.statistic, 4),
                "P值": round(result.pvalue, 6), "alpha": alpha,
                "显著性": "显著" if result.pvalue < alpha else "不显著"
            }
            p_value = result.pvalue
            print(f"  方法: {test_name}")
            print(f"  统计量 = {result.statistic:.4f}, P = {result.pvalue:.6f}")
        except (ImportError, AttributeError):
            # 回退到标准 ANOVA（加警告）
            f_stat, p_value = stats.f_oneway(*groups)
            test_name = "单因素 ANOVA（注意：方差不齐）"
            anova_result = {
                "检验方法": test_name, "统计量(F)": round(f_stat, 4),
                "P值": round(p_value, 6), "alpha": alpha,
                "显著性": "显著" if p_value < alpha else "不显著"
            }
            print(f"  方法: {test_name}")
            print(f"  F = {f_stat:.4f}, P = {p_value:.6f}")
            print(f"  警告：方差不齐，结果可能不够稳健")
    else:
        # Kruskal-Wallis 非参数检验
        h_stat, p_value = stats.kruskal(*groups)
        test_name = "Kruskal-Wallis 检验（非参数）"
        anova_result = {
            "检验方法": test_name, "统计量(H)": round(h_stat, 4),
            "P值": round(p_value, 6), "alpha": alpha,
            "显著性": "显著" if p_value < alpha else "不显著"
        }
        print(f"  方法: {test_name}")
        print(f"  H = {h_stat:.4f}, P = {p_value:.6f}")

    is_significant = p_value < alpha
    if is_significant:
        print(f"\n  结论: 各组均值存在显著差异（p < {alpha}）")
    else:
        print(f"\n  结论: 各组均值无显著差异（p >= {alpha}）")

    # 事后检验
    posthoc_df = pd.DataFrame()
    if is_significant and len(group_names) >= 3:
        print(f"\n  -- 事后检验 (Tukey HSD + {correction} 校正) --")
        try:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd
            all_data = df[[group_col, target_col]].dropna()
            tukey = pairwise_tukeyhsd(all_data[target_col], all_data[group_col], alpha=alpha)

            # 提取事后检验结果
            rows = []
            for i in range(len(tukey.summary().data) - 1):
                row_data = tukey.summary().data[i + 1]
                rows.append({
                    "组1": row_data[0],
                    "组2": row_data[1],
                    "均值差": round(float(row_data[2]), 4),
                    "P值_原始": round(float(row_data[3]), 6),
                    "CI下界": round(float(row_data[4]), 4),
                    "CI上界": round(float(row_data[5]), 4),
                    "原始显著": str(row_data[6])
                })

            posthoc_df = pd.DataFrame(rows)

            # 应用多重比较校正
            if not posthoc_df.empty:
                raw_p = posthoc_df["P值_原始"].tolist()
                corrected_p = apply_correction(raw_p, correction)
                posthoc_df[f"P值_{correction}校正"] = [round(p, 6) for p in corrected_p]
                posthoc_df[f"校正后显著"] = [
                    "是" if p < alpha else "否" for p in corrected_p
                ]

                print(posthoc_df.to_string(index=False))

        except ImportError:
            print("  提示：安装 statsmodels 以使用 Tukey HSD（pip install statsmodels）")
        except Exception as e:
            print(f"  事后检验出错: {e}")

    return anova_result, posthoc_df


def main():
    parser = argparse.ArgumentParser(
        description="方差分析（ANOVA/Welch/Kruskal-Wallis + 事后检验）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--group-col", required=True, help="分组列名")
    parser.add_argument("--target-col", required=True, help="目标变量列名")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--correction", default="bonferroni",
                        choices=["bonferroni", "bh", "benjamini-hochberg", "none"],
                        help="多重比较校正方法")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.group_col, args.target_col] if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    anova_result, posthoc_df = anova_test(
        df, args.group_col, args.target_col, args.alpha, args.correction
    )

    # 保存结果
    anova_df = pd.DataFrame([anova_result])
    anova_path = os.path.join(args.output_dir, "anova_results.csv")
    anova_df.to_csv(anova_path, index=False, encoding='utf-8-sig')
    print(f"\nANOVA 结果已保存至: {anova_path}")

    if not posthoc_df.empty:
        posthoc_path = os.path.join(args.output_dir, "posthoc_results.csv")
        posthoc_df.to_csv(posthoc_path, index=False, encoding='utf-8-sig')
        print(f"事后检验结果已保存至: {posthoc_path}")


if __name__ == "__main__":
    main()
