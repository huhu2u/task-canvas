#!/usr/bin/env python3
"""
滚动指标计算脚本

功能：
- 简单移动平均（SMA）：自定义窗口
- 指数加权移动平均（EWMA）
- YTD（年初至今）累计
- 滚动求和
- 自动检测聚合频率

依赖：pip install pandas numpy

用法：
    python rolling_metrics.py input.csv --time-col date --metric-col value \
        --windows 7 30 --ewma-span 7 -o rolling_output.csv
"""

import argparse
import sys
import numpy as np
import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def detect_frequency(time_series: pd.Series) -> str:
    """自动检测时间序列粒度"""
    diffs = time_series.diff().dropna()
    median_diff = diffs.median()
    if median_diff <= pd.Timedelta('2D'):
        return 'D'
    elif median_diff <= pd.Timedelta('8D'):
        return 'W'
    elif median_diff <= pd.Timedelta('35D'):
        return 'ME'
    else:
        return 'YE'


def rolling_metrics(df: pd.DataFrame, time_col: str, metric_col: str,
                    windows: list = None, ewma_span: int = None) -> pd.DataFrame:
    """
    滚动指标计算

    参数：
        df: 输入数据
        time_col: 时间列
        metric_col: 指标列
        windows: 移动平均窗口列表（如 [7, 30]）
        ewma_span: EWMA 的 span 参数
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)

    # 检测频率
    freq = detect_frequency(df[time_col])
    freq_name = {'D': '日', 'W': '周', 'ME': '月', 'YE': '年'}.get(freq, freq)
    print(f"  时间粒度: {freq_name}")

    # 按频率聚合
    ts = df.set_index(time_col)[metric_col].resample(freq).sum()
    result = ts.reset_index()
    result.columns = ['日期', '指标值']

    # 默认窗口
    if windows is None:
        if freq == 'D':
            windows = [7, 30]
        elif freq == 'W':
            windows = [4, 12]
        elif freq == 'ME':
            windows = [3, 6]
        else:
            windows = [2, 3]

    # 简单移动平均（SMA）
    for w in windows:
        col_name = f'MA_{w}'
        result[col_name] = result['指标值'].rolling(w, min_periods=1).mean().round(4)
        print(f"  已计算 {col_name}（{w}期移动平均）")

    # 指数加权移动平均（EWMA）
    if ewma_span is None:
        ewma_span = windows[0] if windows else 7
    result[f'EWMA_{ewma_span}'] = result['指标值'].ewm(span=ewma_span, min_periods=1).mean().round(4)
    print(f"  已计算 EWMA_{ewma_span}（指数加权移动平均, span={ewma_span}）")

    # YTD累计
    result['年份'] = result['日期'].dt.year
    result['YTD累计'] = result.groupby('年份')['指标值'].cumsum()
    print(f"  已计算 YTD累计")

    # 滚动求和
    for w in windows:
        col_name = f'滚动{w}期合计'
        result[col_name] = result['指标值'].rolling(w, min_periods=1).sum().round(4)

    # 滚动标准差（波动率）
    for w in windows:
        col_name = f'滚动{w}期标准差'
        result[col_name] = result['指标值'].rolling(w, min_periods=2).std().round(4)

    # 清理临时列
    result = result.drop(columns=['年份'])

    # 摘要
    print(f"\n=== 滚动指标摘要 ===")
    print(f"  数据范围: {result['日期'].min()} ~ {result['日期'].max()}")
    print(f"  最新值: {result['指标值'].iloc[-1]:,.2f}")
    for w in windows:
        ma_val = result[f'MA_{w}'].iloc[-1]
        print(f"  最新 MA_{w}: {ma_val:,.4f}")
    print(f"  最新 EWMA_{ewma_span}: {result[f'EWMA_{ewma_span}'].iloc[-1]:,.4f}")
    print(f"  当年YTD累计: {result['YTD累计'].iloc[-1]:,.2f}")

    print(f"\n=== 滚动指标表（最近10期）===")
    print(result.tail(10).to_string(index=False))

    return result


def main():
    parser = argparse.ArgumentParser(description='滚动指标计算')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--metric-col', required=True, help='指标列名')
    parser.add_argument('--windows', nargs='+', type=int, default=None,
                        help='移动平均窗口（如: 7 30）')
    parser.add_argument('--ewma-span', type=int, default=None,
                        help='EWMA的span参数（默认等于第一个窗口）')
    parser.add_argument('-o', '--output', default='rolling_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.metric_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            print(f"可用列: {list(df.columns)}")
            sys.exit(1)

    result = rolling_metrics(df, args.time_col, args.metric_col,
                             args.windows, args.ewma_span)

    result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
