#!/usr/bin/env python3
"""
同期群留存分析脚本
功能：按注册时间分组，计算各期留存率矩阵
增强：灵活分组粒度、留存曲线指数衰减拟合、边界处理

用法：
    python cohort_retention.py -i data.csv --user-col user_id --signup-col reg_date --active-col active_date
    python cohort_retention.py -i data.xlsx --user-col uid --signup-col signup --active-col login --period W
"""

import argparse
import sys
import numpy as np
import pandas as pd


def fit_retention_curve(retention_series):
    """
    对留存率序列拟合指数衰减曲线: R(t) = a * exp(-b * t) + c

    Args:
        retention_series: pd.Series，索引为期数偏移，值为留存率(%)

    Returns:
        dict: 拟合参数 {'a', 'b', 'c', 'r_squared'} 或 None
    """
    try:
        from scipy.optimize import curve_fit
    except ImportError:
        return None

    # 过滤有效数据
    valid = retention_series.dropna()
    if len(valid) < 3:
        return None

    x = valid.index.astype(float).values
    y = valid.values / 100.0  # 转为0-1

    def exp_decay(t, a, b, c):
        return a * np.exp(-b * t) + c

    try:
        # 初始猜测
        p0 = [y[0] - y[-1] if len(y) > 1 else 0.5, 0.1, y[-1] if len(y) > 1 else 0.1]
        popt, _ = curve_fit(exp_decay, x, y, p0=p0, maxfev=5000,
                            bounds=([0, 0, 0], [1.5, 10, 1]))

        # R²
        y_pred = exp_decay(x, *popt)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return {
            "a": round(popt[0], 4),
            "b": round(popt[1], 4),
            "c": round(popt[2], 4),
            "r_squared": round(r_squared, 4)
        }
    except Exception:
        return None


def cohort_retention(df, user_col, signup_col, active_col, period="M",
                     fit_curve=False):
    """
    同期群留存分析。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        signup_col: 注册日期列名
        active_col: 活跃日期列名
        period: 分组粒度 ('M'=月, 'W'=周, 'Q'=季度)
        fit_curve: 是否拟合留存曲线

    Returns:
        pd.DataFrame: 留存率矩阵
    """
    df = df.copy()

    # 解析日期
    for col in [signup_col, active_col]:
        if col not in df.columns:
            print(f"[错误] 列 '{col}' 不存在")
            return pd.DataFrame()
        df[col] = pd.to_datetime(df[col])

    if user_col not in df.columns:
        print(f"[错误] 列 '{user_col}' 不存在")
        return pd.DataFrame()

    # 去除无效数据
    df = df.dropna(subset=[user_col, signup_col, active_col])

    # 每个用户的最早注册日期
    first_signup = df.groupby(user_col)[signup_col].min().reset_index()
    first_signup.columns = [user_col, "first_signup"]
    df = df.merge(first_signup, on=user_col, how="left")

    # 分组粒度映射
    period_map = {"M": "M", "W": "W", "Q": "Q"}
    freq = period_map.get(period, "M")
    period_label = {"M": "月", "W": "周", "Q": "季度"}.get(period, "月")

    # 分期
    df["cohort_period"] = df["first_signup"].dt.to_period(freq)
    df["active_period"] = df[active_col].dt.to_period(freq)

    # 期数偏移
    df["period_offset"] = (df["active_period"] - df["cohort_period"]).apply(
        lambda x: x.n if hasattr(x, 'n') else 0
    )

    # 过滤偏移为负的（活跃在注册前）
    invalid = (df["period_offset"] < 0).sum()
    if invalid > 0:
        print(f"[警告] {invalid} 条记录的活跃时间早于注册时间，已排除")
        df = df[df["period_offset"] >= 0]

    # 同期群大小（第0期的用户数）
    cohort_size = df[df["period_offset"] == 0].groupby("cohort_period")[user_col].nunique()

    # 各期活跃用户数
    retention = df.groupby(["cohort_period", "period_offset"])[user_col].nunique().unstack()

    # 留存率
    retention_rate = retention.divide(cohort_size, axis=0) * 100
    retention_rate = retention_rate.round(1)

    # 验证第0期
    if 0 in retention_rate.columns:
        period_0 = retention_rate[0]
        non_100 = period_0[period_0 != 100.0]
        if len(non_100) > 0:
            print(f"[警告] {len(non_100)} 个同期群的第0期留存率不为100%")

    n_cohorts = len(retention_rate)
    max_periods = retention_rate.columns.max() if len(retention_rate.columns) > 0 else 0

    print(f"\n=== 同期群留存分析结果 ===")
    print(f"分组粒度: {period_label}")
    print(f"同期群数量: {n_cohorts}")
    print(f"最大追踪期数: {max_periods}")
    print(f"总用户数: {cohort_size.sum()}")

    # 平均留存率
    avg_retention = retention_rate.mean().round(1)
    print(f"\n=== 各期平均留存率 ===")
    for period_idx, rate in avg_retention.items():
        if not np.isnan(rate):
            print(f"  第{period_idx}{period_label}: {rate}%")

    # 留存矩阵
    print(f"\n=== 留存率矩阵 (%) ===")
    print(retention_rate.to_string())

    # 留存曲线拟合
    if fit_curve:
        print(f"\n=== 留存曲线拟合 (指数衰减) ===")
        fit_result = fit_retention_curve(avg_retention)
        if fit_result:
            print(f"  模型: R(t) = {fit_result['a']} * exp(-{fit_result['b']} * t) + {fit_result['c']}")
            print(f"  R² = {fit_result['r_squared']}")
            # 预测长期留存率
            long_term = fit_result['c'] * 100
            print(f"  长期稳定留存率预估: {long_term:.1f}%")
        else:
            print("  [信息] 数据不足或无法拟合")

    return retention_rate


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="同期群留存分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cohort_retention.py -i users.csv --user-col user_id --signup-col reg_date --active-col active_date
  python cohort_retention.py -i data.xlsx --user-col uid --signup-col signup --active-col login --period W --fit-curve
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--signup-col", required=True, help="注册日期列名")
    parser.add_argument("--active-col", required=True, help="活跃日期列名")
    parser.add_argument("-o", "--output", default="cohort_retention.csv", help="输出CSV文件路径")
    parser.add_argument("--period", default="M", choices=["M", "W", "Q"],
                        help="分组粒度: M=月, W=周, Q=季度 (默认: M)")
    parser.add_argument("--fit-curve", action="store_true", help="拟合留存衰减曲线")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    retention_rate = cohort_retention(
        df,
        user_col=args.user_col,
        signup_col=args.signup_col,
        active_col=args.active_col,
        period=args.period,
        fit_curve=args.fit_curve
    )

    if len(retention_rate) > 0:
        retention_rate.to_csv(args.output, encoding="utf-8-sig")
        print(f"\n留存矩阵已保存至: {args.output}")


if __name__ == "__main__":
    main()
