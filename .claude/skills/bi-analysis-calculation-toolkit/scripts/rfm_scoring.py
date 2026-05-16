#!/usr/bin/env python3
"""
RFM量化评分脚本
功能：计算R/F/M维度并进行分位数分箱评分
增强：可配置分箱数、低基数自动降级、分布诊断

用法：
    python rfm_scoring.py -i data.csv --user-col user_id --date-col order_date --amount-col amount
    python rfm_scoring.py -i data.xlsx --user-col uid --date-col date --amount-col money --bins 4
"""

import argparse
import sys
import numpy as np
import pandas as pd


def safe_qcut(series, n_bins, labels=None, reverse=False):
    """
    安全的分位数分箱，处理低基数情况。

    Args:
        series: pd.Series
        n_bins: 分箱数
        labels: 标签列表
        reverse: 是否反向标签

    Returns:
        pd.Series: 分箱结果
    """
    n_unique = series.nunique()

    if n_unique < n_bins:
        actual_bins = n_unique
        print(f"  [警告] 列 '{series.name}' 唯一值仅 {n_unique} 个，自动降为 {actual_bins} 箱")
    else:
        actual_bins = n_bins

    if actual_bins <= 1:
        return pd.Series(1, index=series.index, name=series.name)

    if reverse:
        actual_labels = list(range(actual_bins, 0, -1))
    else:
        actual_labels = list(range(1, actual_bins + 1))

    try:
        result = pd.qcut(series.rank(method="first"), q=actual_bins, labels=actual_labels)
    except ValueError:
        # 回退到等距分箱
        try:
            result = pd.cut(series, bins=actual_bins, labels=actual_labels)
        except Exception:
            result = pd.Series(1, index=series.index, name=series.name)

    return result.astype(int)


def rfm_scoring(df, user_col, date_col, amount_col, reference_date=None,
                n_bins=5, freq_col=None):
    """
    RFM量化评分。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        date_col: 订单日期列名
        amount_col: 金额列名
        reference_date: 参考日期（默认: 数据最大日期+1天）
        n_bins: 分箱数（默认5，范围3-10）
        freq_col: 频次列名（可选，默认自动计算）

    Returns:
        pd.DataFrame: RFM评分表
    """
    # 验证列
    for col in [user_col, date_col, amount_col]:
        if col not in df.columns:
            print(f"[错误] 列 '{col}' 不存在")
            return pd.DataFrame()

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.dropna(subset=[user_col, date_col, amount_col])

    # 参考日期
    if reference_date is None:
        reference_date = df[date_col].max() + pd.Timedelta(days=1)
    else:
        reference_date = pd.to_datetime(reference_date)

    print(f"[信息] 参考日期: {reference_date.date()}")
    print(f"[信息] 用户数: {df[user_col].nunique()}, 记录数: {len(df)}")

    # 限制分箱数
    n_bins = max(3, min(10, n_bins))

    # 计算RFM
    agg_dict = {
        "Recency": (date_col, lambda x: (reference_date - x.max()).days),
        "Frequency": (date_col, "count"),
        "Monetary": (amount_col, "sum")
    }

    rfm = df.groupby(user_col).agg(**agg_dict).reset_index()

    # 基本统计
    print(f"\n=== RFM 原始值统计 ===")
    print(rfm[["Recency", "Frequency", "Monetary"]].describe().round(2).to_string())

    # 分箱评分
    rfm["R_score"] = safe_qcut(rfm["Recency"], n_bins, reverse=True)  # R越小分越高
    rfm["F_score"] = safe_qcut(rfm["Frequency"], n_bins, reverse=False)  # F越大分越高
    rfm["M_score"] = safe_qcut(rfm["Monetary"], n_bins, reverse=False)  # M越大分越高

    # 综合得分
    rfm["RFM_score"] = rfm[["R_score", "F_score", "M_score"]].sum(axis=1)

    # 分布诊断
    print(f"\n=== RFM 评分分布 ({n_bins}分制) ===")
    for dim in ["R_score", "F_score", "M_score"]:
        dist = rfm[dim].value_counts().sort_index()
        total = len(rfm)
        print(f"\n  {dim}:")
        for score, count in dist.items():
            bar = "#" * int(count / total * 50)
            print(f"    {score}: {count} ({count/total*100:.1f}%) {bar}")

        # 偏斜度检查
        skewness = rfm[dim].astype(float).skew()
        if abs(skewness) > 1:
            print(f"    [警告] 分布偏斜度 = {skewness:.2f}，分箱不均匀")

    # 综合得分分布
    print(f"\n=== 综合得分分布 (范围: {n_bins*3} - {n_bins*1*3}) ===")
    score_stats = rfm["RFM_score"].describe()
    print(f"  均值: {score_stats['mean']:.1f}")
    print(f"  中位数: {score_stats['50%']:.1f}")
    print(f"  标准差: {score_stats['std']:.1f}")

    # 各分组摘要
    print(f"\n=== RFM 评分结果 (前20行) ===")
    display_cols = [user_col, "Recency", "Frequency", "Monetary",
                    "R_score", "F_score", "M_score", "RFM_score"]
    print(rfm[display_cols].sort_values("RFM_score", ascending=False).head(20).to_string(index=False))

    return rfm


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="RFM量化评分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python rfm_scoring.py -i orders.csv --user-col customer_id --date-col order_date --amount-col total
  python rfm_scoring.py -i data.xlsx --user-col uid --date-col date --amount-col money --bins 4 -o rfm.csv
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--date-col", required=True, help="订单日期列名")
    parser.add_argument("--amount-col", required=True, help="金额列名")
    parser.add_argument("-o", "--output", default="rfm_scores.csv", help="输出CSV文件路径")
    parser.add_argument("--bins", type=int, default=5, help="分箱数 (3-10, 默认: 5)")
    parser.add_argument("--ref-date", default=None, help="参考日期 (默认: 数据最大日期+1)")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    rfm = rfm_scoring(
        df,
        user_col=args.user_col,
        date_col=args.date_col,
        amount_col=args.amount_col,
        reference_date=args.ref_date,
        n_bins=args.bins
    )

    if len(rfm) > 0:
        rfm.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\nRFM评分表已保存至: {args.output}")


if __name__ == "__main__":
    main()
