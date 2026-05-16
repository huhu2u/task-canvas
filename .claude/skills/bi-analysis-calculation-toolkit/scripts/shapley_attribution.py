#!/usr/bin/env python3
"""
Shapley Value 归因脚本
方法：精确Shapley + 蒙特卡洛采样近似
增强：渠道>8时自动切换蒙特卡洛、收敛诊断、归一化验证

用法：
    python shapley_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
    python shapley_attribution.py -i data.xlsx --user-col uid --channel-col source --time-col time --convert-col conv --n-samples 20000
"""

import argparse
import sys
import math
import random
import numpy as np
import pandas as pd
from itertools import combinations
from collections import defaultdict


def compute_coalition_values(path_df, max_path_length=15):
    """
    计算每个渠道联盟的转化率。

    Args:
        path_df: pd.DataFrame，包含 'path' (list) 和 'converted' (0/1) 列
        max_path_length: 单条路径最大触点数，超过时只保留最后 max_path_length 个触点

    Returns:
        dict: frozenset -> 转化率
    """
    coalition_values = defaultdict(lambda: {"converted": 0, "total": 0})
    _truncation_warned = False

    for _, row in path_df.iterrows():
        path = row["path"]
        if len(set(path)) > max_path_length:
            if not _truncation_warned:
                print(f"[警告] 存在路径触点数超过 {max_path_length}，将截断为最后 {max_path_length} 个触点")
                _truncation_warned = True
            path = path[-max_path_length:]
        path_set = frozenset(path)
        for r in range(1, len(path_set) + 1):
            for subset in combinations(path_set, r):
                key = frozenset(subset)
                coalition_values[key]["total"] += 1
                coalition_values[key]["converted"] += row["converted"]

    return {k: v["converted"] / v["total"] if v["total"] > 0 else 0
            for k, v in coalition_values.items()}


def exact_shapley(all_channels, coalition_rates):
    """
    精确计算Shapley值（适用于渠道数 <= 8）。

    Returns:
        dict: 渠道 -> Shapley值
    """
    n = len(all_channels)
    shapley_vals = {ch: 0.0 for ch in all_channels}

    for ch in all_channels:
        others = [c for c in all_channels if c != ch]
        for r in range(len(others) + 1):
            for subset in combinations(others, r):
                subset_with = frozenset(list(subset) + [ch])
                subset_without = frozenset(subset)
                v_with = coalition_rates.get(subset_with, 0)
                v_without = coalition_rates.get(subset_without, 0)
                marginal = v_with - v_without
                weight = (math.factorial(r) * math.factorial(n - r - 1)) / math.factorial(n)
                shapley_vals[ch] += weight * marginal

    return shapley_vals


def monte_carlo_shapley(all_channels, coalition_rates, n_samples=10000, seed=42):
    """
    蒙特卡洛采样近似Shapley值（适用于渠道数 > 8）。

    通过随机排列采样估计每个渠道的边际贡献。

    Returns:
        tuple: (shapley_vals, std_errors)
    """
    random.seed(seed)
    np.random.seed(seed)

    channels = list(all_channels)
    n = len(channels)
    contributions = {ch: [] for ch in channels}

    for _ in range(n_samples):
        perm = list(np.random.permutation(channels))
        for i, ch in enumerate(perm):
            subset_without = frozenset(perm[:i])
            subset_with = frozenset(perm[:i + 1])
            v_with = coalition_rates.get(subset_with, 0)
            v_without = coalition_rates.get(subset_without, 0)
            contributions[ch].append(v_with - v_without)

    shapley_vals = {ch: np.mean(contribs) for ch, contribs in contributions.items()}
    std_errors = {ch: np.std(contribs) / np.sqrt(len(contribs))
                  for ch, contribs in contributions.items()}

    return shapley_vals, std_errors


def shapley_attribution(df, user_col, channel_col, time_col, convert_col,
                         n_samples=10000, mc_threshold=8, max_paths=100000):
    """
    Shapley Value 归因。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        channel_col: 渠道列名
        time_col: 时间列名
        convert_col: 转化列名
        n_samples: 蒙特卡洛采样次数
        mc_threshold: 切换蒙特卡洛的渠道数阈值
        max_paths: 最大路径数量，超过时随机抽样

    Returns:
        pd.DataFrame: Shapley归因结果
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([user_col, time_col])

    # 构建路径
    paths = []
    for user_id, group in df.groupby(user_col):
        channels = list(group[channel_col])
        converted = int(group[convert_col].max())
        paths.append({"path": channels, "converted": converted})

    path_df = pd.DataFrame(paths)

    # 路径数量过多时随机抽样
    if len(path_df) > max_paths:
        print(f"[警告] 路径数量 {len(path_df)} 超过上限 {max_paths}，随机抽样 {max_paths} 条路径")
        path_df = path_df.sample(n=max_paths, random_state=42).reset_index(drop=True)

    # 收集所有渠道
    all_channels = sorted(set(ch for path in path_df["path"] for ch in path))
    n_channels = len(all_channels)

    print(f"[信息] 渠道数: {n_channels}, 用户数: {len(path_df)}")

    if n_channels == 0:
        print("[错误] 没有发现渠道")
        return pd.DataFrame()

    # 计算联盟价值
    print("[信息] 计算联盟价值...")
    coalition_rates = compute_coalition_values(path_df)

    # 选择方法
    use_mc = n_channels > mc_threshold
    if use_mc:
        print(f"[信息] 渠道数 {n_channels} > {mc_threshold}，使用蒙特卡洛采样 (n={n_samples})")
        shapley_vals, std_errors = monte_carlo_shapley(
            all_channels, coalition_rates, n_samples=n_samples
        )
    else:
        print(f"[信息] 渠道数 {n_channels} <= {mc_threshold}，使用精确计算")
        shapley_vals = exact_shapley(all_channels, coalition_rates)
        std_errors = {ch: 0.0 for ch in all_channels}

    # 归一化为百分比
    total = sum(abs(v) for v in shapley_vals.values())
    if total > 0:
        shapley_pct = {ch: abs(v) / total * 100 for ch, v in shapley_vals.items()}
    else:
        shapley_pct = {ch: 0.0 for ch in all_channels}

    # 构建结果
    results = []
    for ch in sorted(all_channels, key=lambda x: -shapley_pct.get(x, 0)):
        row = {
            "渠道": ch,
            "Shapley值": round(shapley_vals[ch], 6),
            "归因占比(%)": round(shapley_pct[ch], 2)
        }
        if use_mc:
            row["标准误"] = round(std_errors[ch], 6)
            row["相对误差(%)"] = round(
                std_errors[ch] / abs(shapley_vals[ch]) * 100, 2
            ) if shapley_vals[ch] != 0 else 0.0
        results.append(row)

    result_df = pd.DataFrame(results)

    # 验证总和
    total_pct = result_df["归因占比(%)"].sum()
    if abs(total_pct - 100) > 0.1:
        print(f"[警告] 归因占比总和 = {total_pct:.2f}%，偏差超过0.1%")

    # 检查归因为0但存在于路径中的渠道
    zero_channels = result_df[result_df["归因占比(%)"] == 0]["渠道"].tolist()
    converted_channels = set()
    for _, row in path_df[path_df["converted"] == 1].iterrows():
        converted_channels.update(row["path"])
    for ch in zero_channels:
        if ch in converted_channels:
            print(f"[警告] 渠道 '{ch}' 存在于转化路径中但归因为0")

    # 输出
    print(f"\n=== Shapley Value 归因结果 ===")
    print(f"计算方法: {'蒙特卡洛采样' if use_mc else '精确计算'}")
    if use_mc:
        max_rel_err = max(r.get("相对误差(%)", 0) for r in results)
        print(f"最大相对误差: {max_rel_err:.2f}%")
        if max_rel_err > 5:
            print(f"[建议] 相对误差较大，建议增加采样次数 (当前: {n_samples})")
    print(result_df.to_string(index=False))

    return result_df


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="Shapley Value 归因：精确计算 + 蒙特卡洛近似",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python shapley_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
  python shapley_attribution.py -i data.xlsx --user-col uid --channel-col source --time-col time --convert-col conv --n-samples 20000
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--channel-col", required=True, help="渠道列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--convert-col", required=True, help="转化标识列名 (0/1)")
    parser.add_argument("-o", "--output", default="shapley_attribution.csv", help="输出CSV文件路径")
    parser.add_argument("--n-samples", type=int, default=10000,
                        help="蒙特卡洛采样次数 (默认: 10000)")
    parser.add_argument("--mc-threshold", type=int, default=8,
                        help="切换蒙特卡洛的渠道数阈值 (默认: 8)")
    parser.add_argument("--max-paths", type=int, default=100000,
                        help="最大路径数量，超过时随机抽样 (默认: 100000)")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    result = shapley_attribution(
        df,
        user_col=args.user_col,
        channel_col=args.channel_col,
        time_col=args.time_col,
        convert_col=args.convert_col,
        n_samples=args.n_samples,
        mc_threshold=args.mc_threshold,
        max_paths=args.max_paths
    )

    if len(result) > 0:
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
