#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正态性检验脚本

对数值字段执行 Shapiro-Wilk、D'Agostino-Pearson、Jarque-Bera 三种正态性检验，
综合判定是否服从正态分布，输出检验结果 CSV。

用法示例:
    python normality_test.py --input data.csv --columns col1,col2,col3
    python normality_test.py --input data.csv --columns col1 --alpha 0.01 --output-dir output/
    python normality_test.py --input data.csv  # 自动选择所有数值列
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def shapiro_wilk_test(s, alpha=0.05):
    """
    Shapiro-Wilk 正态性检验。

    适用于样本量 3~5000。超过5000时进行随机抽样。

    Parameters
    ----------
    s : array-like, 已去除 NaN 的数据
    alpha : float, 显著性水平

    Returns
    -------
    dict : 检验结果
    """
    n = len(s)
    sampled = False

    if n < 3:
        return {
            "Shapiro-Wilk统计量": None,
            "Shapiro-Wilk_p值": None,
            "Shapiro-Wilk结论": "样本不足(需>=3)",
            "Shapiro-Wilk采样": "否",
        }

    # Shapiro-Wilk 对大样本有限制，超过5000取随机子样本
    test_data = s
    if n > 5000:
        rng = np.random.RandomState(42)
        test_data = rng.choice(s, size=5000, replace=False)
        sampled = True

    try:
        stat, p_value = sp_stats.shapiro(test_data)
        conclusion = "正态" if p_value >= alpha else "非正态"
        return {
            "Shapiro-Wilk统计量": round(float(stat), 6),
            "Shapiro-Wilk_p值": round(float(p_value), 6),
            "Shapiro-Wilk结论": conclusion,
            "Shapiro-Wilk采样": f"是(从{n}中抽取5000)" if sampled else "否",
        }
    except Exception as e:
        return {
            "Shapiro-Wilk统计量": None,
            "Shapiro-Wilk_p值": None,
            "Shapiro-Wilk结论": f"计算失败: {str(e)[:50]}",
            "Shapiro-Wilk采样": "否",
        }


def dagostino_test(s, alpha=0.05):
    """
    D'Agostino-Pearson 正态性检验。

    基于偏度和峰度的联合检验，适用于样本量 >= 20。

    Parameters
    ----------
    s : array-like
    alpha : float

    Returns
    -------
    dict : 检验结果
    """
    n = len(s)

    if n < 20:
        return {
            "DAgostino统计量": None,
            "DAgostino_p值": None,
            "DAgostino结论": "样本不足(需>=20)",
        }

    try:
        stat, p_value = sp_stats.normaltest(s)
        conclusion = "正态" if p_value >= alpha else "非正态"
        return {
            "DAgostino统计量": round(float(stat), 6),
            "DAgostino_p值": round(float(p_value), 6),
            "DAgostino结论": conclusion,
        }
    except Exception as e:
        return {
            "DAgostino统计量": None,
            "DAgostino_p值": None,
            "DAgostino结论": f"计算失败: {str(e)[:50]}",
        }


def jarque_bera_test(s, alpha=0.05):
    """
    Jarque-Bera 正态性检验。

    基于偏度和峰度，适用于大样本（渐近分布）。

    Parameters
    ----------
    s : array-like
    alpha : float

    Returns
    -------
    dict : 检验结果
    """
    n = len(s)

    if n < 8:
        return {
            "Jarque-Bera统计量": None,
            "Jarque-Bera_p值": None,
            "Jarque-Bera结论": "样本不足(需>=8)",
        }

    try:
        stat, p_value = sp_stats.jarque_bera(s)
        conclusion = "正态" if p_value >= alpha else "非正态"
        return {
            "Jarque-Bera统计量": round(float(stat), 6),
            "Jarque-Bera_p值": round(float(p_value), 6),
            "Jarque-Bera结论": conclusion,
        }
    except Exception as e:
        return {
            "Jarque-Bera统计量": None,
            "Jarque-Bera_p值": None,
            "Jarque-Bera结论": f"计算失败: {str(e)[:50]}",
        }


def comprehensive_normality_test(df, cols, alpha=0.05):
    """
    对多个字段执行综合正态性检验。

    Parameters
    ----------
    df : DataFrame
    cols : list[str]
    alpha : float

    Returns
    -------
    DataFrame : 正态性检验结果表
    """
    rows = []

    for col in cols:
        s = df[col].dropna().values
        n = len(s)

        if n == 0:
            print(f"  [警告] 字段 '{col}' 全部为空，跳过。")
            continue

        row = {
            "字段": col,
            "样本量": n,
            "偏度": round(float(pd.Series(s).skew()), 4) if n >= 3 else None,
            "峰度": round(float(pd.Series(s).kurtosis()), 4) if n >= 3 else None,
        }

        # 三种检验
        row.update(shapiro_wilk_test(s, alpha))
        row.update(dagostino_test(s, alpha))
        row.update(jarque_bera_test(s, alpha))

        # 综合判定：多数投票
        conclusions = []
        for key in ["Shapiro-Wilk结论", "DAgostino结论", "Jarque-Bera结论"]:
            val = row.get(key)
            if val in ("正态", "非正态"):
                conclusions.append(val)

        if not conclusions:
            row["综合判定"] = "无法判定"
            row["判定依据"] = "所有检验均不可用"
        else:
            normal_count = conclusions.count("正态")
            total = len(conclusions)
            if normal_count > total / 2:
                row["综合判定"] = "近似正态"
                row["判定依据"] = f"{normal_count}/{total}项检验支持正态"
            else:
                row["综合判定"] = "非正态"
                row["判定依据"] = f"{total - normal_count}/{total}项检验拒绝正态"

        # 大样本提醒
        if n > 1000:
            row["大样本提醒"] = "样本量>1000, 检验容易拒绝H0, 需结合偏度/峰度综合判断"
        else:
            row["大样本提醒"] = ""

        rows.append(row)

    if not rows:
        print("[错误] 没有有效字段可供检验。")
        sys.exit(1)

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="正态性检验: Shapiro-Wilk + D'Agostino + Jarque-Bera 综合判定"
    )
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument(
        "--columns", default=None,
        help="目标数值列名，逗号分隔 (默认自动选择所有数值列)"
    )
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平 (默认 0.05)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    try:
        df = load_data(args.input)
    except FileNotFoundError:
        print(f"[错误] 文件不存在: {args.input}")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] 文件读取失败: {e}")
        sys.exit(1)

    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    # 确定分析列
    if args.columns:
        cols = [c.strip() for c in args.columns.split(",")]
        missing_cols = [c for c in cols if c not in df.columns]
        if missing_cols:
            print(f"[错误] 以下列不存在: {missing_cols}")
            sys.exit(1)
    else:
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not cols:
            print("[错误] 数据中没有数值列。")
            sys.exit(1)
        print(f"[信息] 自动选择 {len(cols)} 个数值列: {cols}")

    # 正态性检验
    print(f"\n[信息] 开始正态性检验 (alpha={args.alpha})...")
    result_df = comprehensive_normality_test(df, cols, alpha=args.alpha)

    # 控制台输出
    print(f"\n[结果] 正态性检验汇总:")
    # 精简显示
    display_cols = ["字段", "样本量", "偏度", "峰度",
                    "Shapiro-Wilk_p值", "DAgostino_p值", "Jarque-Bera_p值",
                    "综合判定", "判定依据"]
    available_cols = [c for c in display_cols if c in result_df.columns]
    print(result_df[available_cols].to_string(index=False))

    # 汇总统计
    normal_fields = result_df[result_df["综合判定"] == "近似正态"]["字段"].tolist()
    nonnormal_fields = result_df[result_df["综合判定"] == "非正态"]["字段"].tolist()

    print(f"\n[汇总]")
    if normal_fields:
        print(f"  近似正态: {normal_fields}")
    if nonnormal_fields:
        print(f"  非正态: {nonnormal_fields}")

    # 大样本提醒
    large_n_fields = result_df[result_df["样本量"] > 1000]["字段"].tolist()
    if large_n_fields:
        print(f"\n[提醒] 以下字段样本量 > 1000，正态性检验统计功效很高，"
              f"容易拒绝零假设: {large_n_fields}")
        print("  建议同时参考偏度(|偏度|<0.5)和峰度(|峰度|<1)来辅助判断。")

    # 保存输出
    output_path = os.path.join(args.output_dir, "normality_test.csv")
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] 正态性检验结果已保存: {output_path}")

    print("\n[完成] 正态性检验完毕。")


if __name__ == "__main__":
    main()
