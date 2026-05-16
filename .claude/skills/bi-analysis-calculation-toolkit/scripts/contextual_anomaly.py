#!/usr/bin/env python3
"""
上下文异常检测脚本
方法：基于时间上下文的残差法，支持多种周期粒度
增强：自动检测时间粒度、基准组样本不足回退、多粒度支持

用法：
    python contextual_anomaly.py -i data.csv -t timestamp -v value -o result.csv
    python contextual_anomaly.py -i data.xlsx -t date -v sales --sigma 2.5 --granularity auto
"""

import argparse
import sys
import numpy as np
import pandas as pd


def detect_time_granularity(time_series):
    """
    自动检测时间序列的粒度。

    Returns:
        str: 'minutely', 'hourly', 'daily', 'weekly', 'monthly'
    """
    diffs = time_series.sort_values().diff().dropna()
    if len(diffs) == 0:
        return "daily"

    median_diff = diffs.median()
    total_seconds = median_diff.total_seconds()

    if total_seconds < 300:         # < 5分钟
        return "minutely"
    elif total_seconds < 7200:      # < 2小时
        return "hourly"
    elif total_seconds < 172800:    # < 2天
        return "daily"
    elif total_seconds < 1209600:   # < 14天
        return "weekly"
    else:
        return "monthly"


def build_context_features(df, time_col, granularity):
    """
    根据时间粒度构建上下文特征。

    Args:
        df: pd.DataFrame
        time_col: 时间列名
        granularity: 时间粒度

    Returns:
        list: 上下文特征列名列表
    """
    ctx_cols = []

    if granularity == "minutely":
        df["ctx_hour"] = df[time_col].dt.hour
        df["ctx_minute_bin"] = df[time_col].dt.minute // 15  # 15分钟一档
        df["ctx_weekday"] = df[time_col].dt.weekday
        ctx_cols = ["ctx_hour", "ctx_minute_bin", "ctx_weekday"]

    elif granularity == "hourly":
        df["ctx_hour"] = df[time_col].dt.hour
        df["ctx_weekday"] = df[time_col].dt.weekday
        ctx_cols = ["ctx_hour", "ctx_weekday"]

    elif granularity == "daily":
        df["ctx_weekday"] = df[time_col].dt.weekday
        df["ctx_month"] = df[time_col].dt.month
        ctx_cols = ["ctx_weekday", "ctx_month"]

    elif granularity == "weekly":
        df["ctx_month"] = df[time_col].dt.month
        df["ctx_weekofyear"] = df[time_col].dt.isocalendar().week.astype(int) % 4
        ctx_cols = ["ctx_month", "ctx_weekofyear"]

    elif granularity == "monthly":
        df["ctx_month"] = df[time_col].dt.month
        df["ctx_quarter"] = df[time_col].dt.quarter
        ctx_cols = ["ctx_month", "ctx_quarter"]

    return ctx_cols


def contextual_anomaly(df, time_col, value_col, threshold_sigma=3, granularity="auto",
                       min_group_size=3):
    """
    上下文异常检测：基于时间上下文计算"期望值"，检测实际值与期望值的偏离。

    Args:
        df: pd.DataFrame
        time_col: 时间列名
        value_col: 数值列名
        threshold_sigma: 标准化残差阈值
        granularity: 时间粒度 ('auto', 'minutely', 'hourly', 'daily', 'weekly', 'monthly')
        min_group_size: 上下文分组最小样本量

    Returns:
        pd.DataFrame: 检测结果
    """
    df = df.copy()

    # 解析时间
    try:
        df[time_col] = pd.to_datetime(df[time_col])
    except Exception as e:
        print(f"[错误] 时间列解析失败: {e}")
        return pd.DataFrame()

    # 验证数值列
    if not np.issubdtype(df[value_col].dtype, np.number):
        print(f"[错误] 列 '{value_col}' 不是数值类型")
        return pd.DataFrame()

    # 排序并去除NaN
    df = df.sort_values(time_col).reset_index(drop=True)
    valid_mask = df[value_col].notna()
    n_nan = (~valid_mask).sum()
    if n_nan > 0:
        print(f"[信息] 值列有 {n_nan} 个缺失值，已排除")

    if valid_mask.sum() < 10:
        print(f"[错误] 有效样本仅 {valid_mask.sum()} 个，样本量不足")
        return pd.DataFrame()

    # 自动检测粒度
    if granularity == "auto":
        granularity = detect_time_granularity(df[time_col])
        print(f"[信息] 自动检测时间粒度: {granularity}")

    # 构建上下文特征
    ctx_cols = build_context_features(df, time_col, granularity)
    print(f"[信息] 上下文特征: {ctx_cols}")

    # 计算上下文统计量
    ctx_stats = df[valid_mask].groupby(ctx_cols)[value_col].agg(["mean", "std", "count"]).reset_index()
    ctx_stats.columns = ctx_cols + ["ctx_mean", "ctx_std", "ctx_count"]

    # 合并
    df = df.merge(ctx_stats, on=ctx_cols, how="left")

    # === 回退处理：样本不足的分组 ===
    small_groups = df["ctx_count"] < min_group_size
    n_small = small_groups.sum()

    if n_small > 0:
        print(f"[信息] {n_small} 行所属分组样本 < {min_group_size}，使用全局统计作为回退基准")
        global_mean = df[value_col].mean()
        global_std = df[value_col].std(ddof=1)
        df.loc[small_groups, "ctx_mean"] = global_mean
        df.loc[small_groups, "ctx_std"] = global_std

    # 处理std=0的情况
    df["ctx_std"] = df["ctx_std"].replace(0, np.nan)
    zero_std_mask = df["ctx_std"].isna()
    if zero_std_mask.sum() > 0:
        # 使用全局std作为回退
        fallback_std = df[value_col].std(ddof=1)
        if fallback_std > 0:
            df.loc[zero_std_mask, "ctx_std"] = fallback_std
        else:
            df.loc[zero_std_mask, "ctx_std"] = 1.0  # 极端情况

    # === 计算残差 ===
    df["残差"] = df[value_col] - df["ctx_mean"]
    df["标准化残差"] = df["残差"] / df["ctx_std"]
    df["上下文异常"] = df["标准化残差"].abs() > threshold_sigma

    # 异常方向
    df["异常方向"] = "正常"
    df.loc[(df["上下文异常"]) & (df["标准化残差"] > 0), "异常方向"] = "高于预期"
    df.loc[(df["上下文异常"]) & (df["标准化残差"] < 0), "异常方向"] = "低于预期"

    # 归一化异常分数
    max_abs_resid = df["标准化残差"].abs().max()
    if max_abs_resid > 0:
        df["异常分数"] = (df["标准化残差"].abs() / max_abs_resid).round(4)
    else:
        df["异常分数"] = 0.0

    # === 输出统计 ===
    n_anomaly = df["上下文异常"].sum()
    n_total = len(df)

    print(f"\n=== 上下文异常检测结果 ===")
    print(f"时间粒度: {granularity}")
    print(f"标准化残差阈值: ±{threshold_sigma}")
    print(f"总样本数: {n_total}")
    print(f"异常点数: {n_anomaly} (占比: {n_anomaly/n_total*100:.1f}%)")

    if n_anomaly > 0:
        anomalies = df[df["上下文异常"]].sort_values("标准化残差", key=abs, ascending=False)

        # 按方向统计
        dir_counts = anomalies["异常方向"].value_counts()
        for direction, count in dir_counts.items():
            print(f"  {direction}: {count}")

        print(f"\n异常点摘要 (Top 10):")
        display_cols = [time_col, value_col, "ctx_mean", "标准化残差", "异常方向", "异常分数"]
        print(anomalies[display_cols].head(10).to_string(index=False))

    return df


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="上下文异常检测：基于时间周期的残差法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python contextual_anomaly.py -i traffic.csv -t timestamp -v pageviews
  python contextual_anomaly.py -i sensor.csv -t time -v temperature --sigma 2.5
  python contextual_anomaly.py -i sales.csv -t date -v revenue --granularity daily -o result.csv
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("-t", "--time-col", required=True, help="时间列名")
    parser.add_argument("-v", "--value-col", required=True, help="数值列名")
    parser.add_argument("-o", "--output", default="contextual_anomaly_result.csv", help="输出CSV文件路径")
    parser.add_argument("--sigma", type=float, default=3.0, help="标准化残差阈值 (默认: 3.0)")
    parser.add_argument("--granularity", default="auto",
                        choices=["auto", "minutely", "hourly", "daily", "weekly", "monthly"],
                        help="时间粒度 (默认: auto)")
    parser.add_argument("--min-group-size", type=int, default=3,
                        help="分组最小样本量，不足时使用全局统计 (默认: 3)")

    args = parser.parse_args()

    # 加载数据
    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    if args.time_col not in df.columns:
        print(f"[错误] 时间列 '{args.time_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)

    if args.value_col not in df.columns:
        print(f"[错误] 数值列 '{args.value_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)

    # 执行检测
    result = contextual_anomaly(
        df,
        time_col=args.time_col,
        value_col=args.value_col,
        threshold_sigma=args.sigma,
        granularity=args.granularity,
        min_group_size=args.min_group_size
    )

    if len(result) > 0:
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
