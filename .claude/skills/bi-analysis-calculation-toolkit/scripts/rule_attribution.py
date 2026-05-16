#!/usr/bin/env python3
"""
规则归因脚本
方法：首次触点、末次触点、线性归因、时间衰减归因
增强：验证归因总和=100%、数据驱动的逻辑回归归因

用法：
    python rule_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
    python rule_attribution.py -i data.xlsx --user-col uid --channel-col source --time-col time --convert-col is_convert --logistic
"""

import argparse
import sys
import numpy as np
import pandas as pd


def rule_based_attribution(df, user_col, channel_col, time_col, convert_col):
    """
    四种规则归因方法。

    Args:
        df: pd.DataFrame，原始触点数据
        user_col: 用户ID列名
        channel_col: 渠道列名
        time_col: 时间列名
        convert_col: 转化标识列名

    Returns:
        pd.DataFrame: 各渠道四种归因方法的占比
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([user_col, time_col])

    # 构建用户路径（使用 groupby + agg 替代逐用户 iterrows）
    path_df = df.groupby(user_col).agg(
        path=(channel_col, list),
        converted=(convert_col, 'max'),
    ).reset_index()
    path_df["converted"] = path_df["converted"].astype(int)
    path_df = path_df.rename(columns={user_col: "user_id"})

    converted_paths = path_df[path_df["converted"] == 1]

    if len(converted_paths) == 0:
        print("[警告] 没有转化用户，无法计算归因")
        return pd.DataFrame()

    # 收集所有渠道
    all_channels = sorted(df[channel_col].unique())

    # 初始化归因
    attribution = {ch: {"首次触点": 0.0, "末次触点": 0.0, "线性归因": 0.0, "时间衰减": 0.0}
                   for ch in all_channels}

    for _, row in converted_paths.iterrows():
        path = row["path"]
        n = len(path)

        if n == 0:
            continue

        # 首次触点
        attribution[path[0]]["首次触点"] += 1

        # 末次触点
        attribution[path[-1]]["末次触点"] += 1

        # 线性归因
        for ch in path:
            attribution[ch]["线性归因"] += 1.0 / n

        # 时间衰减（指数权重，越靠后越大）
        weights = [2 ** i for i in range(n)]
        total_weight = sum(weights)
        for ch, w in zip(path, weights):
            attribution[ch]["时间衰减"] += w / total_weight

    # 转为DataFrame
    result = pd.DataFrame(attribution).T
    result.index.name = "渠道"

    # 归一化为百分比
    for col in result.columns:
        col_sum = result[col].sum()
        if col_sum > 0:
            result[col] = (result[col] / col_sum * 100).round(2)

    result = result.reset_index()

    # 验证总和
    for col in ["首次触点", "末次触点", "线性归因", "时间衰减"]:
        total = result[col].sum()
        if abs(total - 100) > 0.1:
            print(f"[警告] {col} 归因总和 = {total:.2f}%，偏差超过0.1%")

    print(f"\n=== 规则归因结果 (%) ===")
    print(result.to_string(index=False))
    print(f"\n转化路径数: {len(converted_paths)}")

    return result


def logistic_attribution(df, user_col, channel_col, time_col, convert_col):
    """
    数据驱动归因：基于逻辑回归的多触点归因。
    构建二元特征（该渠道是否出现在路径中），用逻辑回归的系数作为归因权重。

    Returns:
        pd.DataFrame: 逻辑回归归因结果
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("[错误] 逻辑回归归因需要 scikit-learn: pip install scikit-learn")
        return pd.DataFrame()

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([user_col, time_col])

    # 构建用户路径（使用 groupby + agg 替代逐用户 iterrows）
    path_df = df.groupby(user_col).agg(
        path=(channel_col, list),
        converted=(convert_col, 'max'),
    ).reset_index()
    path_df["converted"] = path_df["converted"].astype(int)
    path_df = path_df.rename(columns={user_col: "user_id"})

    # 收集所有渠道
    all_channels = sorted(df[channel_col].unique())

    # 构建特征矩阵（渠道是否出现）
    X = pd.DataFrame(0, index=range(len(path_df)), columns=all_channels)
    for i, path in enumerate(path_df["path"]):
        for ch in set(path):
            X.loc[i, ch] = 1

    y = path_df["converted"].values

    # 检查类别平衡
    if y.sum() == 0 or y.sum() == len(y):
        print("[警告] 转化标签没有变异性，无法训练逻辑回归")
        return pd.DataFrame()

    # 逻辑回归
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(random_state=42, max_iter=1000, penalty="l2", C=1.0)
    lr.fit(X_scaled, y)

    # 系数作为归因权重
    coefs = pd.Series(lr.coef_[0], index=all_channels)
    # 使用softmax转换为正权重
    exp_coefs = np.exp(coefs)
    weights = (exp_coefs / exp_coefs.sum() * 100).round(2)

    result = pd.DataFrame({
        "渠道": all_channels,
        "逻辑回归系数": coefs.round(4).values,
        "逻辑回归归因(%)": weights.values
    }).sort_values("逻辑回归归因(%)", ascending=False)

    # 验证总和
    total = result["逻辑回归归因(%)"].sum()
    if abs(total - 100) > 0.1:
        print(f"[警告] 逻辑回归归因总和 = {total:.2f}%")

    print(f"\n=== 数据驱动归因 (逻辑回归) ===")
    print(result.to_string(index=False))

    return result


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="规则归因：首次/末次/线性/时间衰减 + 可选逻辑回归归因",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python rule_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col timestamp --convert-col converted
  python rule_attribution.py -i data.csv --user-col uid --channel-col source --time-col ts --convert-col conv --logistic
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--channel-col", required=True, help="渠道列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--convert-col", required=True, help="转化标识列名 (0/1)")
    parser.add_argument("-o", "--output", default="rule_attribution.csv", help="输出CSV文件路径")
    parser.add_argument("--logistic", action="store_true", help="额外计算逻辑回归归因")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    # 规则归因
    rule_result = rule_based_attribution(
        df,
        user_col=args.user_col,
        channel_col=args.channel_col,
        time_col=args.time_col,
        convert_col=args.convert_col
    )

    if len(rule_result) > 0:
        rule_result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n规则归因结果已保存至: {args.output}")

    # 逻辑回归归因
    if args.logistic:
        lr_result = logistic_attribution(
            df,
            user_col=args.user_col,
            channel_col=args.channel_col,
            time_col=args.time_col,
            convert_col=args.convert_col
        )
        if len(lr_result) > 0:
            lr_file = args.output.replace(".csv", "_logistic.csv")
            lr_result.to_csv(lr_file, index=False, encoding="utf-8-sig")
            print(f"逻辑回归归因结果已保存至: {lr_file}")


if __name__ == "__main__":
    main()
