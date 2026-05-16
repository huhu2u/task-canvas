#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合统计摘要脚本

计算数值字段的集中趋势、离散程度、分布形态指标，输出统计摘要表 CSV。

用法示例:
    python stats_summary.py --input data.csv --columns col1,col2,col3
    python stats_summary.py --input data.csv --columns col1,col2 --output-dir output/
    python stats_summary.py --input data.csv  # 自动选择所有数值列
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def central_tendency(s):
    """
    计算集中趋势指标。

    Parameters
    ----------
    s : Series, 已去除 NaN 的数据序列

    Returns
    -------
    dict : 集中趋势指标字典
    """
    result = {
        "算术均值": round(float(s.mean()), 6),
        "中位数": round(float(s.median()), 6),
    }

    # 众数：取第一个
    mode_vals = s.mode()
    if len(mode_vals) > 0:
        result["众数"] = round(float(mode_vals.iloc[0]), 6)
    else:
        result["众数"] = None

    # 截尾均值（去掉上下各5%的极端值后的均值）
    if len(s) >= 20:
        result["截尾均值(5%)"] = round(float(stats.trim_mean(s, 0.05)), 6)
    else:
        # 样本太少时截尾均值不可靠，用普通均值替代
        result["截尾均值(5%)"] = round(float(s.mean()), 6)

    return result


def dispersion(s):
    """
    计算离散程度指标。

    Parameters
    ----------
    s : Series, 已去除 NaN 的数据序列

    Returns
    -------
    dict : 离散程度指标字典
    """
    mean_val = s.mean()
    std_val = s.std()

    result = {
        "方差": round(float(s.var()), 6),
        "标准差": round(float(std_val), 6),
    }

    # 变异系数：均值接近0时不适用
    if abs(mean_val) > 1e-10:
        result["变异系数CV(%)"] = round(float(std_val / abs(mean_val) * 100), 4)
    else:
        result["变异系数CV(%)"] = None  # 均值接近0，CV无意义

    # 平均绝对偏差 MAD
    result["平均绝对偏差MAD"] = round(float(np.mean(np.abs(s - mean_val))), 6)

    # 四分位距 IQR
    q75 = s.quantile(0.75)
    q25 = s.quantile(0.25)
    result["IQR"] = round(float(q75 - q25), 6)

    # 极差
    result["极差(Range)"] = round(float(s.max() - s.min()), 6)

    return result


def distribution_shape(s):
    """
    计算分布形态指标。

    Parameters
    ----------
    s : Series, 已去除 NaN 的数据序列

    Returns
    -------
    dict : 分布形态指标字典
    """
    result = {
        "偏度(Skewness)": round(float(s.skew()), 4),
        "峰度(Kurtosis)": round(float(s.kurtosis()), 4),
        "P5": round(float(s.quantile(0.05)), 6),
        "P25(Q1)": round(float(s.quantile(0.25)), 6),
        "P50(中位数)": round(float(s.quantile(0.50)), 6),
        "P75(Q3)": round(float(s.quantile(0.75)), 6),
        "P90": round(float(s.quantile(0.90)), 6),
        "P95": round(float(s.quantile(0.95)), 6),
        "P99": round(float(s.quantile(0.99)), 6),
        "最小值": round(float(s.min()), 6),
        "最大值": round(float(s.max()), 6),
    }

    # 偏度解读
    skew = result["偏度(Skewness)"]
    if skew > 1:
        result["偏度解读"] = "明显右偏(长尾在右)"
    elif skew > 0.5:
        result["偏度解读"] = "轻度右偏"
    elif skew >= -0.5:
        result["偏度解读"] = "近似对称"
    elif skew >= -1:
        result["偏度解读"] = "轻度左偏"
    else:
        result["偏度解读"] = "明显左偏(长尾在左)"

    # 峰度解读（pandas kurtosis 是超额峰度，正态=0）
    kurt = result["峰度(Kurtosis)"]
    if kurt > 0:
        result["峰度解读"] = "尖峰厚尾(比正态更集中)"
    elif kurt > -0.5:
        result["峰度解读"] = "近似正态"
    else:
        result["峰度解读"] = "平峰薄尾(数据更均匀)"

    return result


def full_stats_summary(df, cols):
    """
    对多个字段生成综合统计摘要。

    Parameters
    ----------
    df : DataFrame
    cols : list[str], 要分析的数值列名

    Returns
    -------
    DataFrame : 统计摘要表（每行一个字段）
    """
    rows = []
    for col in cols:
        s = df[col].dropna()

        if len(s) == 0:
            print(f"  [警告] 字段 '{col}' 全部为空，跳过。")
            continue

        row = {
            "字段": col,
            "样本量": int(len(s)),
            "缺失数": int(df[col].isnull().sum()),
            "缺失率(%)": round(float(df[col].isnull().sum() / len(df) * 100), 2),
        }
        row.update(central_tendency(s))
        row.update(dispersion(s))
        row.update(distribution_shape(s))
        rows.append(row)

    if not rows:
        print("[错误] 没有有效字段可供分析。")
        sys.exit(1)

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="综合统计摘要: 集中趋势 + 离散程度 + 分布形态"
    )
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument(
        "--columns", default=None,
        help="目标数值列名，逗号分隔 (默认自动选择所有数值列)"
    )
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
        # 自动选择所有数值列
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not cols:
            print("[错误] 数据中没有数值列。")
            sys.exit(1)
        print(f"[信息] 自动选择 {len(cols)} 个数值列: {cols}")

    # 计算统计摘要
    print(f"\n[信息] 开始计算 {len(cols)} 个字段的统计摘要...")
    summary_df = full_stats_summary(df, cols)

    # 控制台输出
    print(f"\n[结果] 综合统计摘要表:")
    # 转置显示更清晰
    display_df = summary_df.set_index("字段").T
    print(display_df.to_string())

    # 均值 vs 中位数一致性检查
    print(f"\n[检查] 均值-中位数一致性:")
    for _, row in summary_df.iterrows():
        field = row["字段"]
        mean_val = row["算术均值"]
        median_val = row["中位数"]
        skew_val = row["偏度(Skewness)"]
        if mean_val is not None and median_val is not None:
            if skew_val > 0.5 and mean_val > median_val:
                print(f"  {field}: 右偏 + 均值>中位数 -> 一致")
            elif skew_val < -0.5 and mean_val < median_val:
                print(f"  {field}: 左偏 + 均值<中位数 -> 一致")
            elif abs(skew_val) <= 0.5:
                print(f"  {field}: 近似对称 (偏度={skew_val:.4f})")
            else:
                print(f"  {field}: [注意] 偏度方向与均值-中位数关系不一致，请检查极端值")

    # CV 适用性检查
    for _, row in summary_df.iterrows():
        if row.get("变异系数CV(%)") is None:
            print(f"  [注意] 字段 '{row['字段']}' 的均值接近 0，变异系数 CV 不适用。")

    # 保存输出
    output_path = os.path.join(args.output_dir, "stats_summary.csv")
    summary_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] 统计摘要表已保存: {output_path}")

    print("\n[完成] 统计摘要分析完毕。")


if __name__ == "__main__":
    main()
