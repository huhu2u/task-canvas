#!/usr/bin/env python3
"""
漏斗转化分析脚本
功能：多步骤漏斗转化率计算
增强：时间窗口约束、步骤间中位转化时间、边界处理

用法：
    python funnel_analysis.py -i data.csv --user-col uid --event-col action --time-col ts --steps "浏览,加购,下单,支付"
    python funnel_analysis.py -i data.xlsx --user-col user --event-col event --time-col time --steps "view,cart,order,pay" --window 7
"""

import argparse
import sys
import numpy as np
import pandas as pd


def funnel_analysis(df, user_col, event_col, time_col, steps, window_days=None):
    """
    多步骤漏斗转化分析。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        event_col: 事件列名
        time_col: 时间列名
        steps: 有序步骤列表
        window_days: 时间窗口天数（None表示不限制）

    Returns:
        pd.DataFrame: 漏斗分析结果
    """
    # 验证列
    for col in [user_col, event_col, time_col]:
        if col not in df.columns:
            print(f"[错误] 列 '{col}' 不存在")
            return pd.DataFrame()

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.dropna(subset=[user_col, event_col, time_col])
    df = df.sort_values([user_col, time_col])

    print(f"[信息] 用户数: {df[user_col].nunique()}, 记录数: {len(df)}")
    print(f"[信息] 漏斗步骤: {' -> '.join(steps)}")
    if window_days:
        print(f"[信息] 时间窗口: {window_days} 天")

    # 验证步骤在数据中存在
    existing_events = set(df[event_col].unique())
    missing_steps = [s for s in steps if s not in existing_events]
    if missing_steps:
        print(f"[警告] 以下步骤在数据中不存在: {missing_steps}")

    if window_days is None:
        # === 简单漏斗：不考虑时间顺序 ===
        results = []
        for i, step in enumerate(steps):
            step_users = set(df[df[event_col] == step][user_col].unique())
            results.append({
                "步骤序号": i + 1,
                "步骤名称": step,
                "用户数": len(step_users),
                "_users": step_users  # 内部使用
            })

        result_df = pd.DataFrame(results)
    else:
        # === 时间窗口漏斗：有序事件 + 时间约束 ===
        # 对每个用户，检查是否按顺序完成各步骤，且相邻步骤间隔 <= window_days
        user_step_times = {}

        for user_id, group in df.groupby(user_col):
            user_events = group[[event_col, time_col]].values.tolist()
            step_times = {}

            for step_idx, step in enumerate(steps):
                # 找到该步骤的最早发生时间（在前一步之后）
                prev_time = step_times.get(step_idx - 1) if step_idx > 0 else None

                for evt, t in user_events:
                    if evt != step:
                        continue
                    if prev_time is not None:
                        # 必须在前一步之后
                        if t < prev_time:
                            continue
                        # 时间窗口约束
                        delta = (t - prev_time).total_seconds() / 86400
                        if delta > window_days:
                            continue
                    step_times[step_idx] = t
                    break

                if step_idx not in step_times:
                    break  # 无法完成此步骤，后续也无法完成

            user_step_times[user_id] = step_times

        # 汇总
        results = []
        for i, step in enumerate(steps):
            step_users = set(uid for uid, st in user_step_times.items() if i in st)
            results.append({
                "步骤序号": i + 1,
                "步骤名称": step,
                "用户数": len(step_users),
                "_users": step_users
            })

        result_df = pd.DataFrame(results)

    # === 计算转化率 ===
    first_step_users = result_df["用户数"].iloc[0]

    result_df["逐步转化率(%)"] = 100.0
    for i in range(1, len(result_df)):
        prev = result_df["用户数"].iloc[i - 1]
        curr = result_df["用户数"].iloc[i]
        result_df.loc[result_df.index[i], "逐步转化率(%)"] = (
            round(curr / prev * 100, 1) if prev > 0 else 0
        )

    result_df["总体转化率(%)"] = (result_df["用户数"] / first_step_users * 100).round(1) \
        if first_step_users > 0 else 0

    result_df["流失用户数"] = result_df["用户数"].shift(1) - result_df["用户数"]
    result_df.loc[result_df.index[0], "流失用户数"] = 0

    # === 中位转化时间 ===
    if time_col in df.columns:
        # 用 groupby 建立 user -> events 的字典，避免循环内全表扫描
        user_events_dict = {}
        for user_id, group in df.groupby(user_col):
            user_events_dict[user_id] = group[[event_col, time_col]]

        median_times = []
        for i in range(len(steps)):
            if i == 0:
                median_times.append(None)
                continue

            # 计算完成了当前步骤和前一步的用户的间隔时间
            curr_step = steps[i]
            prev_step = steps[i - 1]

            curr_users = result_df["_users"].iloc[i]

            # 当用户数>100000时抽样计算中位时间
            sample_users = curr_users
            if len(curr_users) > 100000:
                print(f"[信息] 步骤'{curr_step}'用户数({len(curr_users)})超过100000，抽样100000用户计算中位转化时间")
                import random
                rng = random.Random(42)
                sample_users = set(rng.sample(list(curr_users), 100000))

            deltas = []

            for user_id in sample_users:
                user_data = user_events_dict.get(user_id)
                if user_data is None:
                    continue
                prev_times = user_data[user_data[event_col] == prev_step][time_col]
                curr_times = user_data[user_data[event_col] == curr_step][time_col]

                if len(prev_times) > 0 and len(curr_times) > 0:
                    earliest_prev = prev_times.min()
                    # 找到前一步之后最早的当前步骤时间
                    valid_curr = curr_times[curr_times >= earliest_prev]
                    if len(valid_curr) > 0:
                        delta_hours = (valid_curr.min() - earliest_prev).total_seconds() / 3600
                        if delta_hours >= 0:
                            deltas.append(delta_hours)

            if deltas:
                median_time = round(np.median(deltas), 1)
                median_times.append(median_time)
            else:
                median_times.append(None)

        result_df["中位转化时间(小时)"] = median_times

    # 清理内部列
    result_df = result_df.drop(columns=["_users"])

    # === 验证 ===
    # 检查单调递减
    for i in range(1, len(result_df)):
        if result_df["用户数"].iloc[i] > result_df["用户数"].iloc[i - 1]:
            print(f"[警告] 步骤 '{steps[i]}' 用户数 ({result_df['用户数'].iloc[i]}) > "
                  f"前一步 '{steps[i-1]}' ({result_df['用户数'].iloc[i-1]})，"
                  f"可能是数据问题或未使用时间窗口约束")

    # === 输出 ===
    print(f"\n=== 漏斗转化分析结果 ===")
    display_cols = [c for c in result_df.columns if not c.startswith("_")]
    print(result_df[display_cols].to_string(index=False))

    # 最大流失节点
    if len(result_df) > 1:
        loss_df = result_df.iloc[1:].copy()
        max_loss_idx = loss_df["流失用户数"].idxmax()
        max_loss_step = result_df.loc[max_loss_idx, "步骤名称"]
        max_loss_count = result_df.loc[max_loss_idx, "流失用户数"]
        max_loss_rate = result_df.loc[max_loss_idx, "逐步转化率(%)"]
        print(f"\n最大流失节点: {max_loss_step} (流失 {int(max_loss_count)} 人, 转化率 {max_loss_rate}%)")

    # 总体转化率
    overall = result_df["总体转化率(%)"].iloc[-1]
    print(f"总体转化率 (首步 -> 末步): {overall}%")

    return result_df


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="漏斗转化分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python funnel_analysis.py -i events.csv --user-col user_id --event-col action --time-col ts --steps "view,cart,order,pay"
  python funnel_analysis.py -i data.xlsx --user-col uid --event-col event --time-col time --steps "注册,浏览,下单" --window 7
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--event-col", required=True, help="事件列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--steps", required=True,
                        help="漏斗步骤，逗号分隔 (如: 'view,cart,order,pay')")
    parser.add_argument("-o", "--output", default="funnel_result.csv", help="输出CSV文件路径")
    parser.add_argument("--window", type=float, default=None,
                        help="时间窗口天数（默认: 不限制）")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    # 解析步骤
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    if len(steps) < 2:
        print("[错误] 至少需要2个漏斗步骤")
        sys.exit(1)

    result = funnel_analysis(
        df,
        user_col=args.user_col,
        event_col=args.event_col,
        time_col=args.time_col,
        steps=steps,
        window_days=args.window
    )

    if len(result) > 0:
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
