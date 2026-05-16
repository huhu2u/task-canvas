#!/usr/bin/env python3
"""
周期性检测脚本

功能：
- ACF（自相关函数）分析，识别显著周期
- FFT（快速傅里叶变换）频域分析
- 综合周期判定

依赖：pip install statsmodels pandas numpy

用法：
    python periodicity_detection.py input.csv --time-col date --value-col metric \
        --max-lag 200 -o period_output.csv
"""

import argparse
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def acf_analysis(series: np.ndarray, max_lag: int = None,
                 alpha: float = 0.05) -> pd.DataFrame:
    """
    ACF分析，识别显著正相关的滞后阶

    参数：
        series: 时间序列值
        max_lag: 最大滞后阶数
        alpha: 显著性水平
    """
    from statsmodels.tsa.stattools import acf

    n = len(series)
    if max_lag is None:
        max_lag = min(n // 2, 200)

    acf_vals, confint = acf(series, nlags=max_lag, alpha=alpha)

    # 显著性阈值
    threshold = 1.96 / np.sqrt(n)

    # 构建结果表
    acf_df = pd.DataFrame({
        'Lag': range(len(acf_vals)),
        'ACF': np.round(acf_vals, 6),
        'CI_下界': np.round(confint[:, 0] - acf_vals, 6),
        'CI_上界': np.round(confint[:, 1] - acf_vals, 6),
        '显著': np.abs(acf_vals) > threshold
    })

    # 找显著的局部极大值（周期候选）
    significant_peaks = []
    for lag in range(2, len(acf_vals) - 1):
        if (acf_vals[lag] > acf_vals[lag - 1] and
                acf_vals[lag] > acf_vals[lag + 1] and
                acf_vals[lag] > threshold):
            significant_peaks.append({
                'Lag': lag,
                'ACF': round(acf_vals[lag], 6)
            })

    print(f"\n=== ACF 周期分析 ===")
    print(f"  数据长度: {n}")
    print(f"  最大滞后: {max_lag}")
    print(f"  显著性阈值: {threshold:.4f}")

    if significant_peaks:
        print(f"  发现 {len(significant_peaks)} 个显著ACF峰值:")
        for peak in significant_peaks[:10]:
            print(f"    Lag={peak['Lag']}, ACF={peak['ACF']}")
        print(f"  最强候选周期: {significant_peaks[0]['Lag']}")
    else:
        print(f"  未发现显著的周期性模式")

    return acf_df, significant_peaks


def fft_analysis(series: np.ndarray, top_n: int = 5) -> pd.DataFrame:
    """
    FFT频域分析

    参数：
        series: 时间序列值
        top_n: 返回前N个主频率
    """
    n = len(series)

    # 去均值
    centered = series - series.mean()

    # FFT
    fft_vals = np.fft.rfft(centered)
    fft_magnitude = np.abs(fft_vals)
    fft_power = fft_magnitude ** 2
    freqs = np.fft.rfftfreq(n)

    # 排除直流分量（freq=0）
    fft_df = pd.DataFrame({
        '频率': freqs[1:],
        '周期': [round(1 / f, 2) if f > 0 else np.inf for f in freqs[1:]],
        '幅值': np.round(fft_magnitude[1:], 4),
        '功率': np.round(fft_power[1:], 4)
    })
    fft_df = fft_df[fft_df['周期'] < len(series)]  # 排除超长周期
    fft_df = fft_df.sort_values('功率', ascending=False).reset_index(drop=True)

    print(f"\n=== FFT 频域分析 ===")
    print(f"  数据长度: {n}")
    top_results = fft_df.head(top_n)
    print(f"  Top-{top_n} 主要周期:")
    for _, row in top_results.iterrows():
        print(f"    周期={row['周期']:.1f}, 频率={row['频率']:.6f}, 功率={row['功率']:.2f}")

    # 总功率中的占比
    total_power = fft_df['功率'].sum()
    if total_power > 0:
        top_power_pct = top_results['功率'].sum() / total_power * 100
        print(f"  Top-{top_n} 周期占总功率: {top_power_pct:.1f}%")

    return fft_df


def periodicity_detection(df: pd.DataFrame, time_col: str, value_col: str,
                          max_lag: int = None) -> dict:
    """
    综合周期性检测

    参数：
        df: 输入数据
        time_col: 时间列
        value_col: 值列
        max_lag: ACF最大滞后
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    series = df[value_col].dropna().values

    print(f"\n=== 周期性检测 ===")
    print(f"  数据量: {len(series)} 个观测")

    # ACF分析
    acf_df, acf_peaks = acf_analysis(series, max_lag)

    # FFT分析
    fft_df = fft_analysis(series)

    # 综合判定
    print(f"\n=== 综合判定 ===")
    acf_periods = [p['Lag'] for p in acf_peaks[:5]] if acf_peaks else []
    fft_periods = fft_df.head(5)['周期'].tolist()

    if acf_periods:
        primary_period = acf_periods[0]
        print(f"  ACF主要候选周期: {acf_periods}")
        print(f"  FFT主要候选周期: {[round(p) for p in fft_periods]}")

        # 检查一致性
        consistent = False
        for fft_p in fft_periods:
            if abs(fft_p - primary_period) <= 1:
                consistent = True
                break

        if consistent:
            print(f"  ACF与FFT结果一致，主周期 = {primary_period}")
        else:
            print(f"  ACF与FFT结果不完全一致，建议以ACF结果为准")
        print(f"  推荐使用周期: {primary_period}")
    else:
        print(f"  未发现显著周期性")
        if fft_periods:
            print(f"  FFT建议周期（仅供参考）: {[round(p) for p in fft_periods[:3]]}")

    return {
        'acf_df': acf_df,
        'acf_peaks': acf_peaks,
        'fft_df': fft_df,
        'primary_period': acf_periods[0] if acf_periods else None
    }


def main():
    parser = argparse.ArgumentParser(description='周期性检测（ACF + FFT）')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--value-col', required=True, help='值列名')
    parser.add_argument('--max-lag', type=int, default=None, help='ACF最大滞后（默认: 自动）')
    parser.add_argument('-o', '--output', default='period_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.value_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            sys.exit(1)

    result = periodicity_detection(df, args.time_col, args.value_col, args.max_lag)

    # 保存ACF结果
    result['acf_df'].to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\nACF分析结果已保存至: {args.output}")

    # 保存FFT结果
    fft_path = args.output.replace('.csv', '_fft.csv')
    result['fft_df'].to_csv(fft_path, index=False, encoding='utf-8-sig')
    print(f"FFT分析结果已保存至: {fft_path}")


if __name__ == '__main__':
    main()
