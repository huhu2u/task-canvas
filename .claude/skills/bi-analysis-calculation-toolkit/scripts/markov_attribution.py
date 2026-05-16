#!/usr/bin/env python3
"""
马尔可夫链归因脚本
方法：移除效应（Removal Effect）
增强：构建转移概率矩阵、吸收态转化概率计算

用法：
    python markov_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
"""

import argparse
import sys
import numpy as np
import pandas as pd


def build_transition_matrix(path_df):
    """
    构建包含起始态和终止态（转化/未转化）的转移频次矩阵。

    Args:
        path_df: pd.DataFrame，包含 'path' (list) 和 'converted' (0/1)

    Returns:
        pd.DataFrame: 转移概率矩阵
    """
    from collections import defaultdict

    transitions = defaultdict(lambda: defaultdict(int))

    for _, row in path_df.iterrows():
        path = row["path"]
        converted = row["converted"]

        if len(path) == 0:
            continue

        # 起始 -> 第一个渠道
        transitions["(起始)"][path[0]] += 1

        # 渠道间转移
        for i in range(len(path) - 1):
            transitions[path[i]][path[i + 1]] += 1

        # 最后一个渠道 -> 终止态
        if converted:
            transitions[path[-1]]["(转化)"] += 1
        else:
            transitions[path[-1]]["(未转化)"] += 1

    # 所有状态
    all_states = set()
    for src, dsts in transitions.items():
        all_states.add(src)
        all_states.update(dsts.keys())

    all_states = sorted(all_states)

    # 构建矩阵
    matrix = pd.DataFrame(0.0, index=all_states, columns=all_states)
    for src, dsts in transitions.items():
        for dst, count in dsts.items():
            matrix.loc[src, dst] = count

    # 归一化
    row_sums = matrix.sum(axis=1)
    prob_matrix = matrix.div(row_sums, axis=0).fillna(0)

    # 吸收态保持自身
    for absorb in ["(转化)", "(未转化)"]:
        if absorb in prob_matrix.index:
            prob_matrix.loc[absorb] = 0
            prob_matrix.loc[absorb, absorb] = 1.0

    return prob_matrix


def compute_conversion_rate(prob_matrix):
    """
    使用吸收马尔可夫链计算从起始态到转化态的总概率。

    Returns:
        float: 转化概率
    """
    if "(起始)" not in prob_matrix.index or "(转化)" not in prob_matrix.columns:
        return 0.0

    # 提取瞬态和吸收态
    absorbing = ["(转化)", "(未转化)"]
    transient = [s for s in prob_matrix.index if s not in absorbing]

    if len(transient) == 0:
        return 0.0

    # Q 矩阵（瞬态到瞬态）
    Q = prob_matrix.loc[transient, transient].values
    # R 矩阵（瞬态到吸收态）
    R = prob_matrix.loc[transient, [a for a in absorbing if a in prob_matrix.columns]].values

    # 基本矩阵 N = (I - Q)^{-1}
    n = len(transient)
    try:
        N = np.linalg.inv(np.eye(n) - Q)
    except np.linalg.LinAlgError:
        # 伪逆回退
        N = np.linalg.pinv(np.eye(n) - Q)

    # 吸收概率 B = N * R
    B = N @ R

    # 从起始态出发的转化概率
    start_idx = transient.index("(起始)") if "(起始)" in transient else 0
    conv_idx = 0  # (转化) 在吸收态中的索引

    return B[start_idx, conv_idx]


def markov_attribution(df, user_col, channel_col, time_col, convert_col):
    """
    马尔可夫链归因：基于移除效应。

    Args:
        df: pd.DataFrame
        user_col, channel_col, time_col, convert_col: 列名

    Returns:
        pd.DataFrame: 各渠道的移除效应和归因占比
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

    # 当路径数>100000时抽样100000条路径
    if len(path_df) > 100000:
        print(f"[信息] 路径数({len(path_df)})超过100000，抽样100000条路径进行归因计算")
        path_df = path_df.sample(n=100000, random_state=42).reset_index(drop=True)

    # 所有渠道（不含特殊状态）
    all_channels = sorted(set(ch for path in path_df["path"] for ch in path))
    print(f"[信息] 渠道数: {len(all_channels)}, 用户数: {len(path_df)}")

    # 基准转移矩阵和转化率
    base_matrix = build_transition_matrix(path_df)
    base_conv_rate = compute_conversion_rate(base_matrix)
    print(f"[信息] 基准转化率: {base_conv_rate:.4f} ({base_conv_rate*100:.2f}%)")

    if base_conv_rate == 0:
        print("[警告] 基准转化率为0，无法计算移除效应")
        return pd.DataFrame()

    # 逐一移除每个渠道，计算移除后的转化率
    removal_effects = {}
    for ch in all_channels:
        # 构建移除该渠道后的路径
        modified_paths = []
        for _, row in path_df.iterrows():
            new_path = [c for c in row["path"] if c != ch]
            if len(new_path) == 0:
                # 路径为空，视为不转化
                modified_paths.append({"path": [], "converted": 0})
            else:
                modified_paths.append({"path": new_path, "converted": row["converted"]})

        mod_path_df = pd.DataFrame(modified_paths)

        # 计算移除后的转化率
        mod_matrix = build_transition_matrix(mod_path_df)
        mod_conv_rate = compute_conversion_rate(mod_matrix)

        removal_effect = base_conv_rate - mod_conv_rate
        removal_effects[ch] = {
            "移除后转化率": mod_conv_rate,
            "移除效应": removal_effect,
            "转化率下降(%)": removal_effect / base_conv_rate * 100 if base_conv_rate > 0 else 0
        }

    # 归一化为归因占比
    total_removal = sum(v["移除效应"] for v in removal_effects.values())

    results = []
    for ch in sorted(all_channels, key=lambda x: -removal_effects[x]["移除效应"]):
        re = removal_effects[ch]
        attr_pct = (re["移除效应"] / total_removal * 100) if total_removal > 0 else 0
        results.append({
            "渠道": ch,
            "移除效应": round(re["移除效应"], 6),
            "转化率下降(%)": round(re["转化率下降(%)"], 2),
            "马尔可夫归因(%)": round(attr_pct, 2)
        })

    result_df = pd.DataFrame(results)

    # 验证总和
    total_pct = result_df["马尔可夫归因(%)"].sum()
    if abs(total_pct - 100) > 0.1:
        print(f"[警告] 归因占比总和 = {total_pct:.2f}%")

    print(f"\n=== 马尔可夫链归因结果 ===")
    print(f"基准转化率: {base_conv_rate:.4f}")
    print(result_df.to_string(index=False))

    # 输出转移矩阵摘要
    print(f"\n=== 转移概率矩阵 (摘要) ===")
    # 只显示渠道间的转移
    channel_states = [s for s in base_matrix.index if s not in ["(起始)", "(转化)", "(未转化)"]]
    if len(channel_states) <= 10:
        print(base_matrix.loc[channel_states, channel_states].round(3).to_string())

    return result_df


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="马尔可夫链归因：移除效应法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python markov_attribution.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--channel-col", required=True, help="渠道列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--convert-col", required=True, help="转化标识列名 (0/1)")
    parser.add_argument("-o", "--output", default="markov_attribution.csv", help="输出CSV文件路径")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    result = markov_attribution(
        df,
        user_col=args.user_col,
        channel_col=args.channel_col,
        time_col=args.time_col,
        convert_col=args.convert_col
    )

    if len(result) > 0:
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
