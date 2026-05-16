#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prophet 时间序列预测脚本
功能：基于 Prophet 模型预测未来趋势，支持节假日效应、外部回归变量和交叉验证
输出：预测值表CSV + 模型评估指标CSV
"""

import argparse
import sys
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


def load_data(file_path, time_col, value_col, regressor_cols=None):
    """加载并预处理数据"""
    try:
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[错误] 无法读取文件 {file_path}: {e}")
        sys.exit(1)

    # 检查必需列
    if time_col not in df.columns:
        print(f"[错误] 时间列 '{time_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)
    if value_col not in df.columns:
        print(f"[错误] 数值列 '{value_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)

    # 构建 Prophet 格式
    prophet_df = df[[time_col, value_col]].copy()
    prophet_df.columns = ["ds", "y"]
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"], errors="coerce")
    prophet_df = prophet_df.dropna(subset=["ds", "y"]).sort_values("ds").reset_index(drop=True)

    if len(prophet_df) < 10:
        print(f"[错误] 有效数据不足（仅 {len(prophet_df)} 行），需要至少10行")
        sys.exit(1)

    # 处理外部回归变量
    valid_regressors = []
    if regressor_cols:
        missing_regs = [c for c in regressor_cols if c not in df.columns]
        if missing_regs:
            print(f"[警告] 回归变量列 {missing_regs} 不存在，将忽略")
        valid_regressors = [c for c in regressor_cols if c in df.columns]
        if valid_regressors:
            for col in valid_regressors:
                prophet_df[col] = df[col].values[:len(prophet_df)]

    print(f"[信息] 数据加载完成: {len(prophet_df)} 行, 时间范围 {prophet_df['ds'].min()} ~ {prophet_df['ds'].max()}")
    return prophet_df, valid_regressors


def run_prophet(prophet_df, periods, freq, country_holidays, changepoint_prior,
                regressor_cols, cross_validate, cv_horizon):
    """运行 Prophet 预测"""
    try:
        from prophet import Prophet
    except ImportError:
        print("[错误] Prophet 未安装，请执行: pip install prophet")
        sys.exit(1)

    # 构建模型
    model = Prophet(
        changepoint_prior_scale=changepoint_prior,
        yearly_seasonality="auto",
        weekly_seasonality="auto",
        daily_seasonality="auto",
        uncertainty_samples=500,
    )

    # 添加节假日
    if country_holidays:
        model.add_country_holidays(country_name=country_holidays)
        print(f"[信息] 已添加 {country_holidays} 节假日效应")

    # 添加外部回归变量
    for col in regressor_cols:
        model.add_regressor(col)
        print(f"[信息] 已添加回归变量: {col}")

    # 拟合模型
    print("[信息] 正在拟合 Prophet 模型...")
    model.fit(prophet_df)

    # 生成未来时间框架
    future = model.make_future_dataframe(periods=periods, freq=freq)

    # 回归变量需要在 future 中也有值，用最后已知值填充
    for col in regressor_cols:
        if col in prophet_df.columns:
            last_val = prophet_df[col].iloc[-1]
            future[col] = last_val
            mask = future["ds"].isin(prophet_df["ds"])
            future.loc[mask, col] = prophet_df.set_index("ds")[col].reindex(future.loc[mask, "ds"]).values

    # 预测
    forecast = model.predict(future)

    # 计算历史期评估指标
    hist_mask = forecast["ds"].isin(prophet_df["ds"])
    historical = forecast[hist_mask].set_index("ds")["yhat"]
    actuals = prophet_df.set_index("ds")["y"]
    common_idx = actuals.index.intersection(historical.index)

    if len(common_idx) > 0:
        actual_vals = actuals[common_idx].values
        pred_vals = historical[common_idx].values
        mae = np.mean(np.abs(actual_vals - pred_vals))
        nonzero_mask = actual_vals != 0
        if nonzero_mask.any():
            mape = np.mean(np.abs((actual_vals[nonzero_mask] - pred_vals[nonzero_mask]) / actual_vals[nonzero_mask])) * 100
        else:
            mape = np.nan
        smape = np.mean(2 * np.abs(actual_vals - pred_vals) / (np.abs(actual_vals) + np.abs(pred_vals) + 1e-10)) * 100
        rmse = np.sqrt(np.mean((actual_vals - pred_vals) ** 2))
    else:
        mae = mape = smape = rmse = np.nan

    metrics = {"MAE": mae, "MAPE(%)": mape, "SMAPE(%)": smape, "RMSE": rmse}
    print(f"\n[评估] Prophet 模型历史期指标:")
    print(f"  MAE   = {mae:.4f}")
    print(f"  MAPE  = {mape:.2f}%")
    print(f"  SMAPE = {smape:.2f}%")
    print(f"  RMSE  = {rmse:.4f}")

    if not np.isnan(mape) and mape > 30:
        print("  [警告] MAPE > 30%，预测精度较低，建议补充外生变量或人工判断")

    # 提取未来预测部分
    future_mask = forecast["ds"] > prophet_df["ds"].max()
    future_forecast = forecast[future_mask][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    future_forecast.columns = ["日期", "预测值", "95%置信下界", "95%置信上界"]
    future_forecast["预测值"] = future_forecast["预测值"].round(4)
    future_forecast["95%置信下界"] = future_forecast["95%置信下界"].round(4)
    future_forecast["95%置信上界"] = future_forecast["95%置信上界"].round(4)

    # 检查置信区间是否递增
    widths = (future_forecast["95%置信上界"] - future_forecast["95%置信下界"]).values
    if len(widths) > 1 and widths[-1] < widths[0]:
        print("  [警告] 置信区间未随预测期递增，模型不确定性估计可能异常")

    print(f"\n[预测] 未来 {periods} 期预测结果（前10行）:")
    print(future_forecast.head(10).to_string(index=False))

    # 交叉验证
    cv_metrics = None
    if cross_validate:
        try:
            from prophet.diagnostics import cross_validation, performance_metrics
            total_days = (prophet_df["ds"].max() - prophet_df["ds"].min()).days
            initial_days = max(total_days // 2, 30)
            print(f"\n[信息] 正在执行交叉验证（initial={initial_days}天, horizon={cv_horizon}天）...")
            cv_results = cross_validation(
                model,
                initial=f"{initial_days} days",
                period=f"{max(cv_horizon // 2, 1)} days",
                horizon=f"{cv_horizon} days",
            )
            cv_perf = performance_metrics(cv_results)
            cv_metrics = cv_perf[["horizon", "mae", "mape", "rmse"]].copy()
            cv_metrics.columns = ["预测步长", "MAE", "MAPE", "RMSE"]
            print("[交叉验证] 各步长评估指标:")
            print(cv_metrics.to_string(index=False))
        except Exception as e:
            print(f"[警告] 交叉验证失败: {e}")

    return future_forecast, metrics, cv_metrics


def main():
    parser = argparse.ArgumentParser(
        description="Prophet 时间序列预测：支持节假日效应、外部回归变量和交叉验证"
    )
    parser.add_argument("input", help="输入数据文件路径（CSV或Excel）")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--value-col", required=True, help="数值列名")
    parser.add_argument("--periods", type=int, default=30, help="预测期数（默认30）")
    parser.add_argument("--freq", default="D", help="预测频率，如 D(天)/W(周)/ME(月末)（默认D）")
    parser.add_argument("--country-holidays", default=None, help="节假日国家代码，如 CN/US")
    parser.add_argument("--changepoint-prior", type=float, default=0.05,
                        help="趋势灵活性参数（默认0.05，越大越灵活）")
    parser.add_argument("--regressor-cols", nargs="+", default=None,
                        help="外部回归变量列名（可多个）")
    parser.add_argument("--cross-validate", action="store_true", help="是否执行交叉验证")
    parser.add_argument("--cv-horizon", type=int, default=30, help="交叉验证预测步长（天，默认30）")
    parser.add_argument("-o", "--output", default="prophet_output.csv", help="输出CSV文件路径")

    args = parser.parse_args()

    # 加载数据
    prophet_df, regressor_cols = load_data(
        args.input, args.time_col, args.value_col, args.regressor_cols
    )

    # 运行预测
    future_forecast, metrics, cv_metrics = run_prophet(
        prophet_df, args.periods, args.freq, args.country_holidays,
        args.changepoint_prior, regressor_cols, args.cross_validate, args.cv_horizon
    )

    # 保存预测结果
    future_forecast.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n[输出] 预测结果已保存: {args.output}")

    # 保存评估指标
    metrics_path = args.output.replace(".csv", "_metrics.csv")
    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    print(f"[输出] 评估指标已保存: {metrics_path}")

    # 保存交叉验证结果
    if cv_metrics is not None:
        cv_path = args.output.replace(".csv", "_cv.csv")
        cv_metrics.to_csv(cv_path, index=False, encoding="utf-8-sig")
        print(f"[输出] 交叉验证结果已保存: {cv_path}")


if __name__ == "__main__":
    main()
