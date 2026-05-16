#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VAR 多变量时间序列联合预测脚本
功能：向量自回归模型，支持ADF平稳性检验、Granger因果检验、差分还原
输出：多变量预测表CSV + Granger因果矩阵CSV
"""

import argparse
import sys
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


def load_data(file_path, time_col, target_cols):
    """加载并预处理多变量数据"""
    try:
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[错误] 无法读取文件 {file_path}: {e}")
        sys.exit(1)

    if time_col not in df.columns:
        print(f"[错误] 时间列 '{time_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)
    missing_cols = [c for c in target_cols if c not in df.columns]
    if missing_cols:
        print(f"[错误] 目标列 {missing_cols} 不存在。可用列: {list(df.columns)}")
        sys.exit(1)
    if len(target_cols) < 2:
        print("[错误] VAR 模型至少需要2个目标变量")
        sys.exit(1)

    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col] + target_cols).sort_values(time_col)
    df = df.set_index(time_col)[target_cols].astype(float)

    if len(df) < 20:
        print(f"[错误] 有效数据不足（仅 {len(df)} 行），VAR 模型需要至少20行")
        sys.exit(1)

    print(f"[信息] 数据加载完成: {len(df)} 行, {len(target_cols)} 个变量")
    print(f"[信息] 变量: {target_cols}")
    print(f"[信息] 时间范围: {df.index.min()} ~ {df.index.max()}")
    return df


def check_stationarity(df):
    """ADF 检验各列平稳性"""
    from statsmodels.tsa.stattools import adfuller

    print("\n[诊断] ADF 平稳性检验:")
    need_diff = False
    results = {}
    for col in df.columns:
        adf_result = adfuller(df[col].dropna(), autolag="AIC")
        p_val = adf_result[1]
        is_stat = p_val < 0.05
        status = "平稳" if is_stat else "非平稳"
        print(f"  {col}: ADF={adf_result[0]:.4f}, P值={p_val:.4f} -> {status}")
        if not is_stat:
            need_diff = True
        results[col] = {"ADF": round(adf_result[0], 4), "P值": round(p_val, 4), "平稳": is_stat}
    return need_diff, results


def granger_causality_test(df, max_lag=4):
    """Granger 因果检验"""
    from statsmodels.tsa.stattools import grangercausalitytests

    cols = df.columns.tolist()
    n = len(cols)
    granger_matrix = pd.DataFrame(np.ones((n, n)), columns=cols, index=cols)

    print(f"\n[诊断] Granger 因果检验（最大滞后={max_lag}）:")
    for i, target in enumerate(cols):
        for j, cause in enumerate(cols):
            if i == j:
                continue
            try:
                test_data = df[[target, cause]].dropna()
                if len(test_data) < max_lag * 3:
                    continue
                result = grangercausalitytests(test_data, maxlag=max_lag, verbose=False)
                min_p = min(result[lag][0]["ssr_ftest"][1] for lag in range(1, max_lag + 1))
                granger_matrix.loc[target, cause] = round(min_p, 4)
                if min_p < 0.05:
                    print(f"  {cause} -> {target}: P值={min_p:.4f} (显著)")
            except Exception:
                granger_matrix.loc[target, cause] = np.nan

    return granger_matrix


def run_var(df, periods, max_lags):
    """运行 VAR 预测"""
    from statsmodels.tsa.vector_ar.var_model import VAR

    target_cols = df.columns.tolist()

    # 检验平稳性
    need_diff, adf_results = check_stationarity(df)

    diff_order = 0
    if need_diff:
        print("[信息] 存在非平稳序列，进行一阶差分...")
        df_model = df.diff().dropna()
        diff_order = 1
    else:
        df_model = df.copy()

    # 选择最优滞后阶数
    max_possible_lag = min(max_lags, len(df_model) // 4)
    if max_possible_lag < 1:
        print("[错误] 数据量不足以估计VAR模型")
        sys.exit(1)

    model = VAR(df_model)
    try:
        lag_result = model.select_order(maxlags=max_possible_lag)
        optimal_lag = lag_result.selected_orders.get("aic", 2)
        if optimal_lag == 0:
            optimal_lag = 1
    except Exception:
        optimal_lag = min(2, max_possible_lag)

    print(f"\n[信息] VAR 最优滞后阶数（AIC）= {optimal_lag}")

    # 拟合模型
    results = model.fit(optimal_lag)

    # 预测
    forecast_input = df_model.values[-optimal_lag:]
    forecast_vals = results.forecast(forecast_input, steps=periods)
    forecast_df = pd.DataFrame(forecast_vals, columns=target_cols)

    # 差分还原
    if diff_order > 0:
        last_vals = df.iloc[-1]
        for col in target_cols:
            forecast_df[col] = forecast_df[col].cumsum() + last_vals[col]

    forecast_df = forecast_df.round(4)

    # 生成未来日期索引
    last_date = df.index[-1]
    try:
        freq = pd.infer_freq(df.index)
        if freq:
            future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]
            forecast_df.insert(0, "日期", future_dates)
        else:
            forecast_df.insert(0, "期数", range(1, periods + 1))
    except Exception:
        forecast_df.insert(0, "期数", range(1, periods + 1))

    # 非负检查
    for col in target_cols:
        if df[col].min() >= 0 and forecast_df[col].min() < 0:
            print(f"[警告] {col} 的预测值出现负值，但历史数据均为非负")

    print(f"\n[预测] VAR 多变量预测（未来 {periods} 期）:")
    print(forecast_df.to_string(index=False))

    # Granger 因果检验
    granger_df = granger_causality_test(df, max_lag=min(optimal_lag, 4))

    return forecast_df, granger_df, adf_results


def main():
    parser = argparse.ArgumentParser(
        description="VAR 多变量时间序列联合预测：支持ADF检验、Granger因果检验"
    )
    parser.add_argument("input", help="输入数据文件路径（CSV或Excel）")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--target-cols", nargs="+", required=True, help="目标变量列名（至少2个）")
    parser.add_argument("--periods", type=int, default=6, help="预测期数（默认6）")
    parser.add_argument("--max-lags", type=int, default=12, help="最大滞后阶数（默认12）")
    parser.add_argument("-o", "--output", default="var_output.csv", help="输出CSV文件路径")

    args = parser.parse_args()

    # 加载数据
    df = load_data(args.input, args.time_col, args.target_cols)

    # 运行 VAR 预测
    forecast_df, granger_df, adf_results = run_var(df, args.periods, args.max_lags)

    # 保存预测结果
    forecast_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n[输出] VAR 预测结果已保存: {args.output}")

    # 保存 Granger 因果矩阵
    granger_path = args.output.replace(".csv", "_granger.csv")
    granger_df.to_csv(granger_path, encoding="utf-8-sig")
    print(f"[输出] Granger 因果矩阵已保存: {granger_path}")

    # 保存 ADF 检验结果
    adf_path = args.output.replace(".csv", "_adf.csv")
    adf_df = pd.DataFrame(adf_results).T
    adf_df.index.name = "变量"
    adf_df.to_csv(adf_path, encoding="utf-8-sig")
    print(f"[输出] ADF 检验结果已保存: {adf_path}")


if __name__ == "__main__":
    main()
