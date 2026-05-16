#!/usr/bin/env python3
"""
STL时序分解脚本

功能：
- STL分解（趋势 + 季节 + 残差）
- MSTL多季节周期分解
- 趋势强度与季节性强度计算
- 自动周期推断（基于ACF）
- 分解正确性验证

依赖：pip install statsmodels pandas numpy

用法：
    python stl_decomposition.py input.csv --time-col date --value-col metric \
        --period 7 --mstl-periods 7 365 -o stl_output.csv
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


def auto_detect_period(series: np.ndarray, max_lag: int = None) -> int:
    """利用ACF自动推断主周期"""
    from statsmodels.tsa.stattools import acf

    n = len(series)
    if max_lag is None:
        max_lag = min(n // 2, 200)

    acf_vals = acf(series, nlags=max_lag, fft=True)

    # 找第一个局部极大值（排除lag=0和lag=1）
    for lag in range(2, len(acf_vals) - 1):
        if acf_vals[lag] > acf_vals[lag - 1] and acf_vals[lag] > acf_vals[lag + 1]:
            if acf_vals[lag] > 1.96 / np.sqrt(n):  # 显著性检验
                return lag

    return 7  # 默认周周期


def stl_decompose(series: pd.Series, period: int = None, robust: bool = True) -> dict:
    """
    STL分解

    参数：
        series: 时间序列（带时间索引）
        period: 季节周期
        robust: 是否使用鲁棒估计
    """
    from statsmodels.tsa.seasonal import STL

    values = series.dropna()

    if period is None:
        period = auto_detect_period(values.values)
        print(f"  自动检测周期: {period}")
    else:
        print(f"  指定周期: {period}")

    if len(values) < period * 2:
        print(f"  警告: 数据长度({len(values)})不足两个完整周期({period*2})，分解结果可能不可靠")

    stl = STL(values, period=period, robust=robust)
    result = stl.fit()

    # 趋势强度和季节性强度
    resid_var = result.resid.var()
    trend_plus_resid_var = (result.resid + result.trend).var()
    season_plus_resid_var = (result.resid + result.seasonal).var()

    trend_strength = max(0, 1 - resid_var / trend_plus_resid_var) if trend_plus_resid_var > 0 else 0
    seasonal_strength = max(0, 1 - resid_var / season_plus_resid_var) if season_plus_resid_var > 0 else 0

    print(f"\n=== STL 分解结果 ===")
    print(f"  周期: {period}")
    print(f"  趋势强度: {trend_strength:.4f} (>0.6 表示明显趋势)")
    print(f"  季节性强度: {seasonal_strength:.4f} (>0.6 表示明显周期)")

    # 验证分解正确性
    reconstruction = result.trend + result.seasonal + result.resid
    max_error = np.abs(values.values - reconstruction.values).max()
    print(f"  分解还原误差: {max_error:.2e} ({'通过' if max_error < 1e-10 else '警告: 误差偏大'})")

    # 趋势变化摘要
    trend_vals = result.trend.values
    trend_change = trend_vals[-1] - trend_vals[0]
    trend_change_pct = trend_change / abs(trend_vals[0]) * 100 if trend_vals[0] != 0 else np.nan

    print(f"  趋势起始值: {trend_vals[0]:.4f}")
    print(f"  趋势终止值: {trend_vals[-1]:.4f}")
    print(f"  趋势总变化: {trend_change:.4f}")
    if not np.isnan(trend_change_pct):
        print(f"  趋势变化率: {trend_change_pct:.2f}%")

    # 残差统计
    print(f"  残差均值: {result.resid.mean():.6f}")
    print(f"  残差标准差: {result.resid.std():.4f}")

    return {
        'result': result,
        'period': period,
        'trend_strength': round(trend_strength, 4),
        'seasonal_strength': round(seasonal_strength, 4),
        'max_error': max_error
    }


def mstl_decompose(series: pd.Series, periods: list = None) -> dict:
    """
    MSTL多季节周期分解

    参数：
        series: 时间序列
        periods: 多个季节周期列表（如 [7, 365]）
    """
    try:
        from statsmodels.tsa.seasonal import MSTL
    except ImportError:
        print("  MSTL不可用（需要statsmodels>=0.14），回退到STL")
        return stl_decompose(series, periods[0] if periods else None)

    values = series.dropna()

    if periods is None or len(periods) == 0:
        periods = [auto_detect_period(values.values)]

    print(f"\n=== MSTL 多季节分解 ===")
    print(f"  季节周期: {periods}")

    try:
        mstl = MSTL(values, periods=periods)
        result = mstl.fit()

        print(f"  分解成分:")
        print(f"    趋势项: {result.trend.shape}")
        print(f"    季节项: {result.seasonal.shape}")
        print(f"    残差项: {result.resid.shape}")

        return {
            'result': result,
            'periods': periods,
            'trend': result.trend,
            'seasonal': result.seasonal,
            'resid': result.resid
        }
    except Exception as e:
        print(f"  MSTL分解失败: {e}")
        print(f"  回退到STL，使用第一个周期: {periods[0]}")
        return stl_decompose(series, periods[0])


def main():
    parser = argparse.ArgumentParser(description='STL/MSTL时序分解')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--time-col', required=True, help='时间列名')
    parser.add_argument('--value-col', required=True, help='值列名')
    parser.add_argument('--period', type=int, default=None, help='季节周期（默认自动检测）')
    parser.add_argument('--mstl-periods', nargs='+', type=int, default=None,
                        help='MSTL多季节周期（如: 7 365）')
    parser.add_argument('--no-robust', dest='robust', action='store_false',
                        help='禁用鲁棒估计（默认启用）')
    parser.set_defaults(robust=True)
    parser.add_argument('-o', '--output', default='stl_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.time_col, args.value_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在")
            sys.exit(1)

    df[args.time_col] = pd.to_datetime(df[args.time_col])
    ts = df.set_index(args.time_col)[args.value_col].sort_index()

    # STL分解
    stl_result = stl_decompose(ts, args.period, args.robust)

    # 输出
    output_df = pd.DataFrame({
        '时间': ts.dropna().index,
        '原始值': ts.dropna().values,
        '趋势项': stl_result['result'].trend.values,
        '季节项': stl_result['result'].seasonal.values,
        '残差项': stl_result['result'].resid.values
    })
    output_df.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\nSTL分解结果已保存至: {args.output}")

    # MSTL分解
    if args.mstl_periods:
        mstl_result = mstl_decompose(ts, args.mstl_periods)
        mstl_path = args.output.replace('.csv', '_mstl.csv')
        try:
            mstl_df = pd.DataFrame({
                '时间': ts.dropna().index,
                '原始值': ts.dropna().values,
                '趋势项': mstl_result['trend'].values
            })
            # MSTL的seasonal可能是多列
            seasonal = mstl_result.get('seasonal')
            if seasonal is not None:
                if seasonal.ndim == 1:
                    mstl_df['季节项'] = seasonal.values
                else:
                    for i in range(seasonal.shape[1]):
                        mstl_df[f'季节项_{args.mstl_periods[i]}'] = seasonal.iloc[:, i].values
            mstl_df['残差项'] = mstl_result['resid'].values
            mstl_df.to_csv(mstl_path, index=False, encoding='utf-8-sig')
            print(f"MSTL分解结果已保存至: {mstl_path}")
        except Exception as e:
            print(f"MSTL结果保存失败: {e}")


if __name__ == '__main__':
    main()
