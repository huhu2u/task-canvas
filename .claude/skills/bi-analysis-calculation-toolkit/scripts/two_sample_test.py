#!/usr/bin/env python3
"""
双样本检验脚本 - t检验 / Mann-Whitney U 自动选择 + Bootstrap 置信区间

功能：
  - 自动检测正态性（Shapiro-Wilk / D'Agostino-Pearson）
  - 自动检测方差齐性（Levene）
  - 正态 + 等方差 -> t检验；正态 + 不等方差 -> Welch t；非正态 -> Mann-Whitney U
  - 计算效应量 Cohen's d
  - 参数置信区间 + Bootstrap 非参数置信区间
  - 结果输出到 CSV 和控制台

用法：
  python two_sample_test.py <数据文件> \
    --group-col <分组列> --target-col <目标列> \
    [--alpha 0.05] [--bootstrap-n 10000] [--output-dir <输出目录>]
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


def normality_test(data, name="样本"):
    """正态性检验：n < 5000 用 Shapiro-Wilk，否则用 D'Agostino-Pearson"""
    if len(data) < 3:
        print(f"  {name} 样本量过小（n={len(data)}），无法进行正态性检验")
        return False, None

    if len(data) < 5000:
        stat, p = stats.shapiro(data)
        test_name = "Shapiro-Wilk"
    else:
        stat, p = stats.normaltest(data)
        test_name = "D'Agostino-Pearson"

    is_normal = p > 0.05
    result = "近似正态" if is_normal else "非正态分布"
    print(f"  {name} 正态性检验（{test_name}）：p={p:.4f} -> {result}")
    return is_normal, p


def bootstrap_ci(group1, group2, n_bootstrap=10000, alpha=0.05):
    """Bootstrap 非参数置信区间（均值差）"""
    np.random.seed(42)

    # 当样本量 > 50000 时，先抽样到 50000 以降低内存压力
    max_sample = 50000
    if len(group1) > max_sample:
        print(f"  [信息] 组1 样本量 ({len(group1)}) 超过 {max_sample}，Bootstrap 前抽样至 {max_sample}")
        group1 = np.random.choice(group1, size=max_sample, replace=False)
    if len(group2) > max_sample:
        print(f"  [信息] 组2 样本量 ({len(group2)}) 超过 {max_sample}，Bootstrap 前抽样至 {max_sample}")
        group2 = np.random.choice(group2, size=max_sample, replace=False)

    boot_diffs = []
    for _ in range(n_bootstrap):
        b1 = np.random.choice(group1, size=len(group1), replace=True)
        b2 = np.random.choice(group2, size=len(group2), replace=True)
        boot_diffs.append(b1.mean() - b2.mean())

    boot_diffs = np.array(boot_diffs)
    ci_low = np.percentile(boot_diffs, alpha / 2 * 100)
    ci_high = np.percentile(boot_diffs, (1 - alpha / 2) * 100)
    return ci_low, ci_high


def two_sample_test(df, group_col, target_col, alpha=0.05, bootstrap_n=10000):
    """
    双样本检验：自动选择检验方法。

    参数：
      df:           DataFrame
      group_col:    分组列名
      target_col:   目标变量列名
      alpha:        显著性水平
      bootstrap_n:  Bootstrap 重抽样次数

    返回：
      dict — 检验结果摘要
    """
    groups = df[group_col].dropna().unique()
    if len(groups) != 2:
        print(f"错误：分组变量需恰好有 2 个组，当前有 {len(groups)} 个: {groups}")
        sys.exit(1)

    g1_data = df[df[group_col] == groups[0]][target_col].dropna().values
    g2_data = df[df[group_col] == groups[1]][target_col].dropna().values

    print(f"\n{'='*70}")
    print(f"  双样本检验（alpha={alpha}）")
    print(f"{'='*70}")
    print(f"  组 '{groups[0]}': n={len(g1_data)}, 均值={g1_data.mean():.4f}, "
          f"标准差={g1_data.std():.4f}, 中位数={np.median(g1_data):.4f}")
    print(f"  组 '{groups[1]}': n={len(g2_data)}, 均值={g2_data.mean():.4f}, "
          f"标准差={g2_data.std():.4f}, 中位数={np.median(g2_data):.4f}")

    # 小样本警告
    if len(g1_data) < 30 or len(g2_data) < 30:
        print(f"  注意：小样本（n<30），结论需谨慎")

    # 前提检验
    print(f"\n  -- 前提检验 --")
    is_normal_1, _ = normality_test(g1_data, f"组 '{groups[0]}'")
    is_normal_2, _ = normality_test(g2_data, f"组 '{groups[1]}'")

    mean_diff = g1_data.mean() - g2_data.mean()
    result = {
        "组1": str(groups[0]),
        "组2": str(groups[1]),
        "组1_n": len(g1_data),
        "组2_n": len(g2_data),
        "组1_均值": round(g1_data.mean(), 4),
        "组2_均值": round(g2_data.mean(), 4),
        "均值差": round(mean_diff, 4),
        "alpha": alpha
    }

    if is_normal_1 and is_normal_2:
        # 方差齐性检验
        lev_stat, lev_p = stats.levene(g1_data, g2_data)
        equal_var = lev_p > 0.05
        var_label = "等方差" if equal_var else "不等方差(Welch)"
        print(f"  方差齐性检验（Levene）：p={lev_p:.4f} -> {var_label}")

        # t 检验
        t_stat, p_value = stats.ttest_ind(g1_data, g2_data, equal_var=equal_var)
        test_name = f"独立样本 t 检验（{var_label}）"

        # Cohen's d
        pooled_std = np.sqrt(
            (g1_data.std(ddof=1)**2 * (len(g1_data)-1) +
             g2_data.std(ddof=1)**2 * (len(g2_data)-1)) /
            (len(g1_data) + len(g2_data) - 2)
        )
        cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
        effect_label = "小" if abs(cohens_d) < 0.2 else "中" if abs(cohens_d) < 0.5 else "大"

        # 参数置信区间
        se = np.sqrt(g1_data.std(ddof=1)**2/len(g1_data) +
                     g2_data.std(ddof=1)**2/len(g2_data))
        t_crit = stats.t.ppf(1 - alpha/2, df=len(g1_data)+len(g2_data)-2)
        ci_low_param = mean_diff - t_crit * se
        ci_high_param = mean_diff + t_crit * se

        result.update({
            "检验方法": test_name,
            "统计量": round(t_stat, 4),
            "P值": round(p_value, 6),
            "Cohen_d": round(cohens_d, 4),
            "效应大小": effect_label,
            "参数CI下界": round(ci_low_param, 4),
            "参数CI上界": round(ci_high_param, 4)
        })
    else:
        # Mann-Whitney U 非参数检验
        u_stat, p_value = stats.mannwhitneyu(g1_data, g2_data, alternative="two-sided")
        test_name = "Mann-Whitney U 检验（非参数）"

        # rank-biserial 效应量
        n1, n2 = len(g1_data), len(g2_data)
        r_effect = 1 - 2 * u_stat / (n1 * n2)
        effect_label = "小" if abs(r_effect) < 0.1 else "中" if abs(r_effect) < 0.3 else "大"

        result.update({
            "检验方法": test_name,
            "统计量": round(u_stat, 4),
            "P值": round(p_value, 6),
            "rank_biserial_r": round(r_effect, 4),
            "效应大小": effect_label,
            "参数CI下界": None,
            "参数CI上界": None
        })

    # Bootstrap 置信区间
    print(f"\n  计算 Bootstrap 置信区间（n={bootstrap_n}）...")
    boot_ci_low, boot_ci_high = bootstrap_ci(g1_data, g2_data, bootstrap_n, alpha)
    result["Bootstrap_CI下界"] = round(boot_ci_low, 4)
    result["Bootstrap_CI上界"] = round(boot_ci_high, 4)

    # 输出结论
    is_significant = p_value < alpha
    result["显著性"] = "显著" if is_significant else "不显著"

    print(f"\n  -- 检验结果 --")
    print(f"  检验方法: {result['检验方法']}")
    print(f"  统计量 = {result['统计量']}")
    print(f"  P 值 = {result['P值']}")
    if result.get("参数CI下界") is not None:
        print(f"  参数置信区间: [{result['参数CI下界']}, {result['参数CI上界']}]")
    print(f"  Bootstrap 置信区间: [{result['Bootstrap_CI下界']}, {result['Bootstrap_CI上界']}]")
    print(f"  效应大小: {result['效应大小']}")

    if is_significant:
        print(f"\n  结论: 两组存在统计显著差异（p < {alpha}，拒绝 H0）")
        if result['效应大小'] == '小':
            print(f"  注意: 统计显著但效应量较小，实际意义可能有限")
    else:
        print(f"\n  结论: 两组无统计显著差异（p >= {alpha}，不能拒绝 H0）")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="双样本检验（t检验/Mann-Whitney U 自动选择 + Bootstrap CI）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--group-col", required=True, help="分组列名")
    parser.add_argument("--target-col", required=True, help="目标变量列名")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--bootstrap-n", type=int, default=10000, help="Bootstrap 重抽样次数")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.group_col, args.target_col] if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result = two_sample_test(df, args.group_col, args.target_col,
                              args.alpha, args.bootstrap_n)

    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "two_sample_test.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {out_path}")


if __name__ == "__main__":
    main()
