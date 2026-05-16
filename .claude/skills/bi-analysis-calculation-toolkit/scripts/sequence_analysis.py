#!/usr/bin/env python3
"""
序列模式分析脚本
方法：马尔可夫链状态转移 + n-gram路径分析 + 可选PrefixSpan
增强：稳态分布计算、PrefixSpan回退、关键节点识别

用法：
    python sequence_analysis.py -i data.csv --user-col uid --event-col action --time-col ts
    python sequence_analysis.py -i log.csv --user-col user --event-col event --time-col time --top-n 15
"""

import argparse
import sys
import numpy as np
import pandas as pd
from collections import Counter


def compute_steady_state(transition_matrix):
    """
    计算马尔可夫链的稳态分布。

    Args:
        transition_matrix: pd.DataFrame，转移概率矩阵

    Returns:
        pd.Series: 稳态分布概率
    """
    try:
        P = transition_matrix.values
        n = P.shape[0]

        # 求解 πP = π, Σπ = 1
        # 等价于 (P^T - I)π = 0 加上 Σπ = 1
        A = P.T - np.eye(n)
        A[-1, :] = 1  # 替换最后一行为归一化约束
        b = np.zeros(n)
        b[-1] = 1

        try:
            pi = np.linalg.solve(A, b)
            # 验证非负
            if np.all(pi >= -1e-10):
                pi = np.maximum(pi, 0)
                pi = pi / pi.sum()
                return pd.Series(pi, index=transition_matrix.index)
        except np.linalg.LinAlgError:
            pass

        # 回退：幂迭代法
        pi = np.ones(n) / n
        for _ in range(1000):
            pi_new = pi @ P
            if np.allclose(pi, pi_new, atol=1e-10):
                break
            pi = pi_new
        return pd.Series(pi, index=transition_matrix.index)
    except Exception:
        return pd.Series(dtype=float)


def run_prefixspan(user_sequences, min_support_count=2, top_n=10):
    """
    尝试运行PrefixSpan序列模式挖掘。

    Returns:
        list or None: 序列模式列表，或None（未安装）
    """
    try:
        from prefixspan import PrefixSpan
        ps = PrefixSpan(user_sequences)
        ps.minlen = 2
        ps.maxlen = 5
        patterns = ps.topk(top_n, closed=True)
        return [(count, seq) for count, seq in patterns if count >= min_support_count]
    except ImportError:
        return None


def sequence_analysis(df, user_col, event_col, time_col, top_n=10, use_prefixspan=True):
    """
    序列模式分析：n-gram路径 + 马尔可夫链转移矩阵。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        event_col: 事件列名
        time_col: 时间列名
        top_n: 输出Top N路径
        use_prefixspan: 是否尝试使用PrefixSpan

    Returns:
        dict: 包含转移矩阵、n-gram、稳态分布等
    """
    # 数据验证
    for col in [user_col, event_col, time_col]:
        if col not in df.columns:
            print(f"[错误] 列 '{col}' 不存在")
            return {}

    df = df[[user_col, event_col, time_col]].dropna()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([user_col, time_col])
    df[event_col] = df[event_col].astype(str).str.strip()

    n_users = df[user_col].nunique()
    n_events = df[event_col].nunique()
    print(f"[信息] 用户数: {n_users}, 事件类型数: {n_events}, 总记录数: {len(df)}")

    # 当事件类型 > 500 时，只保留频率 Top 500 的事件类型，其余归入"其他"
    if n_events > 500:
        print(f"[警告] 事件类型数 ({n_events}) 超过500，只保留频率Top 500的事件类型，其余归入'其他'类别")
        top_events = df[event_col].value_counts().head(500).index
        df[event_col] = df[event_col].where(df[event_col].isin(top_events), other="其他")
        n_events = df[event_col].nunique()
        print(f"[信息] 合并后事件类型数: {n_events}")

    # 构建用户行为序列
    user_sequences = df.groupby(user_col)[event_col].apply(list).tolist()

    # 用户序列超过100步时截断到最后100步
    user_sequences = [seq[-100:] if len(seq) > 100 else seq for seq in user_sequences]

    # 过滤长度 < 2 的序列
    valid_sequences = [seq for seq in user_sequences if len(seq) >= 2]
    print(f"[信息] 有效序列 (长度>=2): {len(valid_sequences)}/{len(user_sequences)}")

    if len(valid_sequences) == 0:
        print("[错误] 没有长度 >= 2 的用户序列")
        return {}

    # === n-gram 路径分析 ===
    bigrams = Counter()
    trigrams = Counter()
    for seq in valid_sequences:
        for i in range(len(seq) - 1):
            bigrams[(seq[i], seq[i + 1])] += 1
        for i in range(len(seq) - 2):
            trigrams[(seq[i], seq[i + 1], seq[i + 2])] += 1

    print(f"\n=== 高频二元转化路径 (Top {top_n}) ===")
    bigram_data = []
    for (a, b), count in bigrams.most_common(top_n):
        print(f"  {a} -> {b}: {count} 次")
        bigram_data.append({"起始": a, "目标": b, "次数": count})
    bigram_df = pd.DataFrame(bigram_data)

    if trigrams:
        print(f"\n=== 高频三元路径 (Top {min(top_n, len(trigrams))}) ===")
        trigram_data = []
        for (a, b, c), count in trigrams.most_common(top_n):
            print(f"  {a} -> {b} -> {c}: {count} 次")
            trigram_data.append({"步骤1": a, "步骤2": b, "步骤3": c, "次数": count})
        trigram_df = pd.DataFrame(trigram_data)
    else:
        trigram_df = pd.DataFrame()

    # === PrefixSpan 序列模式 ===
    if use_prefixspan:
        patterns = run_prefixspan(valid_sequences, top_n=top_n)
        if patterns is not None:
            print(f"\n=== PrefixSpan 序列模式 (Top {len(patterns)}) ===")
            for count, seq in patterns:
                print(f"  {' -> '.join(seq)}: {count} 次")
        else:
            print("\n[信息] PrefixSpan 未安装，使用 n-gram 分析 (pip install prefixspan)")

    # === 马尔可夫链状态转移矩阵 ===
    events = sorted(df[event_col].unique())
    transition = pd.DataFrame(0.0, index=events, columns=events)
    for seq in valid_sequences:
        for i in range(len(seq) - 1):
            transition.loc[seq[i], seq[i + 1]] += 1

    # 归一化为概率（直接从 transition 频次矩阵计算，避免额外拷贝）
    row_sums = transition.sum(axis=1)
    transition_prob = transition.div(row_sums, axis=0).fillna(0)

    # 验证行和为1
    row_sum_check = transition_prob.sum(axis=1)
    invalid_rows = row_sum_check[(row_sum_check - 1.0).abs() > 1e-10]
    if len(invalid_rows) > 0:
        print(f"\n[警告] 以下状态的转移概率行和不为1: {list(invalid_rows.index)}")

    print(f"\n=== 状态转移概率矩阵 ===")
    print(transition_prob.round(3).to_string())

    # === 稳态分布 ===
    steady = compute_steady_state(transition_prob)
    if len(steady) > 0:
        print(f"\n=== 稳态分布（长期各状态占比）===")
        for event, prob in steady.sort_values(ascending=False).items():
            print(f"  {event}: {prob:.4f} ({prob*100:.1f}%)")

    return {
        "transition_prob": transition_prob,
        "transition_counts": transition,
        "bigrams": bigram_df,
        "trigrams": trigram_df,
        "steady_state": steady
    }


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="序列模式分析：马尔可夫链 + n-gram + PrefixSpan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python sequence_analysis.py -i log.csv --user-col user_id --event-col action --time-col timestamp
  python sequence_analysis.py -i data.xlsx --user-col uid --event-col event --time-col ts --top-n 15
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--event-col", required=True, help="事件列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("-o", "--output-prefix", default="sequence", help="输出文件前缀 (默认: sequence)")
    parser.add_argument("--top-n", type=int, default=10, help="输出Top N路径 (默认: 10)")
    parser.add_argument("--no-prefixspan", action="store_true", help="禁用PrefixSpan")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    result = sequence_analysis(
        df,
        user_col=args.user_col,
        event_col=args.event_col,
        time_col=args.time_col,
        top_n=args.top_n,
        use_prefixspan=not args.no_prefixspan
    )

    if result:
        # 保存转移矩阵
        transition_file = f"{args.output_prefix}_transition_matrix.csv"
        result["transition_prob"].to_csv(transition_file, encoding="utf-8-sig")
        print(f"\n转移矩阵已保存至: {transition_file}")

        # 保存n-gram
        if len(result["bigrams"]) > 0:
            bigram_file = f"{args.output_prefix}_bigrams.csv"
            result["bigrams"].to_csv(bigram_file, index=False, encoding="utf-8-sig")
            print(f"二元路径已保存至: {bigram_file}")

        if len(result["trigrams"]) > 0:
            trigram_file = f"{args.output_prefix}_trigrams.csv"
            result["trigrams"].to_csv(trigram_file, index=False, encoding="utf-8-sig")
            print(f"三元路径已保存至: {trigram_file}")

        # 保存稳态分布
        if len(result["steady_state"]) > 0:
            steady_file = f"{args.output_prefix}_steady_state.csv"
            result["steady_state"].to_frame("稳态概率").to_csv(steady_file, encoding="utf-8-sig")
            print(f"稳态分布已保存至: {steady_file}")


if __name__ == "__main__":
    main()
