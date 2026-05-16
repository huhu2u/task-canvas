#!/usr/bin/env python3
"""
用户转化路径提取脚本
功能：按用户ID和时间排序，构建每个用户的触点序列，统计路径分布

用法：
    python extract_paths.py -i data.csv --user-col user_id --channel-col channel --time-col ts --convert-col converted
    python extract_paths.py -i data.xlsx --user-col uid --channel-col source --time-col time --convert-col is_convert -o paths.csv
"""

import argparse
import sys
import pandas as pd


def extract_paths(df, user_col, channel_col, time_col, convert_col):
    """
    提取每个用户的触点序列路径。

    Args:
        df: pd.DataFrame
        user_col: 用户ID列名
        channel_col: 渠道/触点列名
        time_col: 时间列名
        convert_col: 转化标识列名（0/1 或 True/False）

    Returns:
        pd.DataFrame: 路径汇总表
    """
    # 数据验证
    for col in [user_col, channel_col, time_col, convert_col]:
        if col not in df.columns:
            print(f"[错误] 列 '{col}' 不存在。可用列: {list(df.columns)}")
            return pd.DataFrame()

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([user_col, time_col])

    # 清理
    df = df.dropna(subset=[user_col, channel_col, time_col, convert_col])
    df[channel_col] = df[channel_col].astype(str).str.strip()

    n_users = df[user_col].nunique()
    n_channels = df[channel_col].nunique()
    print(f"[信息] 用户数: {n_users}, 渠道数: {n_channels}, 总记录数: {len(df)}")

    # 提取路径（使用 groupby + agg 替代逐用户循环，减少内存和耗时）
    grouped = df.groupby(user_col).agg(
        路径列表=(channel_col, list),
        是否转化=(convert_col, 'max'),
        首次触点时间=(time_col, 'min'),
        末次触点时间=(time_col, 'max'),
    ).reset_index()

    grouped["是否转化"] = grouped["是否转化"].astype(int)
    grouped["路径"] = grouped["路径列表"].apply(lambda x: " > ".join(x))
    grouped["路径长度"] = grouped["路径列表"].apply(len)
    grouped["唯一触点数"] = grouped["路径列表"].apply(lambda x: len(set(x)))
    grouped["路径时长(小时)"] = ((grouped["末次触点时间"] - grouped["首次触点时间"]).dt.total_seconds() / 3600).round(2)

    path_df = grouped.rename(columns={user_col: "用户ID"})

    # 统计
    n_converted = path_df["是否转化"].sum()
    conv_rate = n_converted / len(path_df) if len(path_df) > 0 else 0

    print(f"\n=== 路径提取结果 ===")
    print(f"总用户数: {len(path_df)}")
    print(f"转化用户: {n_converted} (转化率: {conv_rate:.2%})")
    print(f"平均路径长度: {path_df['路径长度'].mean():.1f}")
    print(f"平均唯一触点数: {path_df['唯一触点数'].mean():.1f}")

    # 高频路径
    print(f"\n=== 高频转化路径 (Top 10) ===")
    converted_paths = path_df[path_df["是否转化"] == 1]
    if len(converted_paths) > 0:
        top_paths = converted_paths["路径"].value_counts().head(10)
        for path, count in top_paths.items():
            print(f"  {path}: {count} 次")
    else:
        print("  无转化路径")

    print(f"\n=== 高频非转化路径 (Top 5) ===")
    non_converted_paths = path_df[path_df["是否转化"] == 0]
    if len(non_converted_paths) > 0:
        top_nc_paths = non_converted_paths["路径"].value_counts().head(5)
        for path, count in top_nc_paths.items():
            print(f"  {path}: {count} 次")

    # 渠道出现频率（使用原始 df 的 value_counts 替代列表展开，避免额外内存）
    channel_freq = df[channel_col].value_counts()
    print(f"\n=== 渠道出现频率 ===")
    for ch, freq in channel_freq.items():
        print(f"  {ch}: {freq} 次")

    return path_df


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="用户转化路径提取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python extract_paths.py -i touchpoints.csv --user-col user_id --channel-col channel --time-col timestamp --convert-col converted
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--user-col", required=True, help="用户ID列名")
    parser.add_argument("--channel-col", required=True, help="渠道/触点列名")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--convert-col", required=True, help="转化标识列名 (0/1)")
    parser.add_argument("-o", "--output", default="extracted_paths.csv", help="输出CSV文件路径")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    path_df = extract_paths(
        df,
        user_col=args.user_col,
        channel_col=args.channel_col,
        time_col=args.time_col,
        convert_col=args.convert_col
    )

    if len(path_df) > 0:
        # 输出时排除路径列表（不适合CSV）
        output_cols = [c for c in path_df.columns if c != "路径列表"]
        path_df[output_cols].to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
