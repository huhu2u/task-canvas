#!/usr/bin/env python3
"""
统计功效与样本量分析脚本

功能：
  - 给定效应量 + alpha + 样本量 -> 计算功效（power）
  - 给定效应量 + alpha + 目标功效 -> 计算所需样本量
  - 支持 t 检验、ANOVA、卡方检验三种场景
  - 输出功效曲线数据（样本量 vs 功效）

用法：
  python power_analysis.py \
    --test-type ttest --effect-size 0.5 --alpha 0.05 \
    [--power 0.8] [--n-per-group 50] [--n-groups 2] \
    [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np


def load_power_module():
    """加载 statsmodels 功效分析模块"""
    try:
        from statsmodels.stats.power import (
            TTestIndPower, FTestAnovaPower, GofChisquarePower
        )
        return TTestIndPower, FTestAnovaPower, GofChisquarePower
    except ImportError:
        print("错误：需要 statsmodels 库（pip install statsmodels）")
        sys.exit(1)


def power_analysis(test_type, effect_size, alpha=0.05, power=None,
                   n_per_group=None, n_groups=2):
    """
    统计功效分析。

    参数：
      test_type:    检验类型 ("ttest", "anova", "chisquare")
      effect_size:  效应量（Cohen's d / Cohen's f / Cohen's w）
      alpha:        显著性水平
      power:        目标功效（与 n_per_group 二选一）
      n_per_group:  每组样本量（与 power 二选一）
      n_groups:     组数（ANOVA 用）

    返回：
      result: dict — 分析结果
      curve_df: DataFrame — 功效曲线数据
    """
    TTestIndPower, FTestAnovaPower, GofChisquarePower = load_power_module()

    result = {
        "检验类型": test_type,
        "效应量": effect_size,
        "alpha": alpha,
        "组数": n_groups
    }

    print(f"\n{'='*70}")
    print(f"  统计功效分析")
    print(f"{'='*70}")
    print(f"  检验类型: {test_type}")
    print(f"  效应量: {effect_size}")
    print(f"  显著性水平 alpha: {alpha}")

    if test_type == "ttest":
        analyzer = TTestIndPower()
        if n_per_group is not None and power is None:
            # 计算功效
            computed_power = analyzer.solve_power(
                effect_size=effect_size, nobs1=n_per_group, alpha=alpha,
                ratio=1.0, alternative='two-sided'
            )
            result["每组样本量"] = n_per_group
            result["功效(power)"] = round(computed_power, 4)
            print(f"  每组样本量: {n_per_group}")
            print(f"  计算得功效: {computed_power:.4f}")
            if computed_power < 0.8:
                print(f"  警告: 功效 < 0.8，样本量可能不足")
        elif power is not None:
            # 计算所需样本量
            required_n = analyzer.solve_power(
                effect_size=effect_size, power=power, alpha=alpha,
                ratio=1.0, alternative='two-sided'
            )
            result["目标功效"] = power
            result["所需每组样本量"] = int(np.ceil(required_n))
            print(f"  目标功效: {power}")
            print(f"  所需每组样本量: {int(np.ceil(required_n))}")
            print(f"  总样本量: {int(np.ceil(required_n)) * 2}")

    elif test_type == "anova":
        analyzer = FTestAnovaPower()
        if n_per_group is not None and power is None:
            computed_power = analyzer.solve_power(
                effect_size=effect_size, nobs=n_per_group,
                alpha=alpha, k_groups=n_groups
            )
            result["每组样本量"] = n_per_group
            result["功效(power)"] = round(computed_power, 4)
            print(f"  组数: {n_groups}")
            print(f"  每组样本量: {n_per_group}")
            print(f"  计算得功效: {computed_power:.4f}")
            if computed_power < 0.8:
                print(f"  警告: 功效 < 0.8，样本量可能不足")
        elif power is not None:
            required_n = analyzer.solve_power(
                effect_size=effect_size, power=power,
                alpha=alpha, k_groups=n_groups
            )
            result["目标功效"] = power
            result["所需每组样本量"] = int(np.ceil(required_n))
            print(f"  组数: {n_groups}")
            print(f"  目标功效: {power}")
            print(f"  所需每组样本量: {int(np.ceil(required_n))}")
            print(f"  总样本量: {int(np.ceil(required_n)) * n_groups}")

    elif test_type == "chisquare":
        analyzer = GofChisquarePower()
        # 自由度 = (rows-1)*(cols-1)，简化为 n_groups-1
        n_bins = max(n_groups, 2)
        if n_per_group is not None and power is None:
            total_n = n_per_group * n_groups
            computed_power = analyzer.solve_power(
                effect_size=effect_size, nobs=total_n,
                alpha=alpha, n_bins=n_bins
            )
            result["总样本量"] = total_n
            result["功效(power)"] = round(computed_power, 4)
            print(f"  总样本量: {total_n}")
            print(f"  计算得功效: {computed_power:.4f}")
            if computed_power < 0.8:
                print(f"  警告: 功效 < 0.8，样本量可能不足")
        elif power is not None:
            required_n = analyzer.solve_power(
                effect_size=effect_size, power=power,
                alpha=alpha, n_bins=n_bins
            )
            result["目标功效"] = power
            result["所需总样本量"] = int(np.ceil(required_n))
            print(f"  目标功效: {power}")
            print(f"  所需总样本量: {int(np.ceil(required_n))}")

    # 功效曲线数据
    print(f"\n  -- 功效曲线数据 --")
    curve_rows = []
    n_range = list(range(10, 501, 10))

    for n in n_range:
        try:
            if test_type == "ttest":
                pw = analyzer.solve_power(
                    effect_size=effect_size, nobs1=n, alpha=alpha,
                    ratio=1.0, alternative='two-sided'
                )
            elif test_type == "anova":
                pw = analyzer.solve_power(
                    effect_size=effect_size, nobs=n,
                    alpha=alpha, k_groups=n_groups
                )
            elif test_type == "chisquare":
                pw = analyzer.solve_power(
                    effect_size=effect_size, nobs=n * n_groups,
                    alpha=alpha, n_bins=n_bins
                )
            else:
                pw = None

            if pw is not None:
                curve_rows.append({
                    "每组样本量": n,
                    "功效(power)": round(pw, 4)
                })
        except Exception:
            continue

    curve_df = pd.DataFrame(curve_rows)
    if not curve_df.empty:
        # 找到 power >= 0.8 的最小样本量
        sufficient = curve_df[curve_df["功效(power)"] >= 0.8]
        if not sufficient.empty:
            min_n = sufficient.iloc[0]["每组样本量"]
            print(f"  达到 80% 功效所需最小每组样本量: {int(min_n)}")
        else:
            print(f"  在 n=10~500 范围内无法达到 80% 功效，"
                  f"请增大效应量或放宽 alpha")

    return result, curve_df


def main():
    parser = argparse.ArgumentParser(
        description="统计功效与样本量分析",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--test-type", required=True,
                        choices=["ttest", "anova", "chisquare"],
                        help="检验类型")
    parser.add_argument("--effect-size", type=float, required=True,
                        help="效应量（ttest: Cohen's d, anova: Cohen's f, "
                             "chisquare: Cohen's w）")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--power", type=float, default=None,
                        help="目标功效（计算所需样本量时使用）")
    parser.add_argument("--n-per-group", type=int, default=None,
                        help="每组样本量（计算功效时使用）")
    parser.add_argument("--n-groups", type=int, default=2, help="组数")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    if args.power is None and args.n_per_group is None:
        print("错误：请指定 --power（计算样本量）或 --n-per-group（计算功效）之一")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result, curve_df = power_analysis(
        args.test_type, args.effect_size, args.alpha,
        args.power, args.n_per_group, args.n_groups
    )

    # 保存结果
    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "power_analysis.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n功效分析结果已保存至: {out_path}")

    if not curve_df.empty:
        curve_path = os.path.join(args.output_dir, "power_curve.csv")
        curve_df.to_csv(curve_path, index=False, encoding='utf-8-sig')
        print(f"功效曲线数据已保存至: {curve_path}")


if __name__ == "__main__":
    main()
