#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SARIMA / Holt-Winters 时间序列预测脚本
功能：自动参数搜索(auto-ARIMA)，ADF平稳性检验，Ljung-Box残差检验，Holt-Winters指数平滑
输出：预测值表CSV + 诊断结果CSV
"""

import argparse
import sys
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


def load_data(file_path, time_col, value_col):
    """加载并预处理数据"""
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
    if value_col not in df.columns:
        print(f"[错误] 数值列 '{value_col}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)

    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col, value_col]).sort_values(time_col).reset_index(drop=True)
    series = df.set_index(time_col)[value_col].astype(float)

    if len(series) < 10:
        print(f"[错误] 有效数据不足（仅 {len(series)} 行），需要至少10行")
        sys.exit(1)

    print(f"[信息] 数据加载完成: {len(series)} 行, 时间范围 {series.index.min()} ~ {series.index.max()}")
    return series


def adf_test(series):
    """ADF 平稳性检验"""
    from statsmodels.tsa.stattools import adfuller

    result = adfuller(series.dropna(), autolag="AIC")
    adf_stat, p_value, used_lag = result[0], result[1], result[2]

    is_stationary = p_value < 0.05
    print(f"\n[诊断] ADF 平稳性检验:")
    print(f"  ADF统计量 = {adf_stat:.4f}")
    print(f"  P值       = {p_value:.4f}")
    print(f"  使用滞后   = {used_lag}")
    print(f"  结论: {'平稳（无需差分）' if is_stationary else '非平稳（建议差分）'}")

    return {"ADF统计量": round(adf_stat, 4), "P值": round(p_value, 4),
            "滞后阶数": used_lag, "是否平稳": is_stationary}


def ljung_box_test(residuals, lags=10):
    """Ljung-Box 残差白噪声检验"""
    from statsmodels.stats.diagnostic import acorr_ljungbox

    lb_result = acorr_ljungbox(residuals.dropna(), lags=lags, return_df=True)
    min_p = lb_result["lb_pvalue"].min()

    is_white_noise = min_p > 0.05
    print(f"\n[诊断] Ljung-Box 残差检验:")
    print(f"  最小P值 = {min_p:.4f}")
    print(f"  结论: {'残差为白噪声（模型充分提取信息）' if is_white_noise else '残差有自相关（模型可能欠拟合）'}")

    return {"最小P值": round(min_p, 4), "是否白噪声": is_white_noise}


def run_sarima(series, periods, freq, seasonal_period):
    """SARIMA 预测"""
    freq_map = {"D": "D", "W": "W", "ME": "ME", "MS": "MS", "QE": "QE", "YE": "YE"}
    pd_freq = freq_map.get(freq, freq)

    try:
        import pmdarima as pm
    except ImportError:
        print("[警告] pmdarima 未安装，回退到手动 SARIMA(1,1,1)(1,1,1,m)")
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        m = seasonal_period
        try:
            model = SARIMAX(series, order=(1, 1, 1), seasonal_order=(1, 1, 1, m))
            result = model.fit(disp=False)
            fcast = result.get_forecast(steps=periods)
            pred_mean = fcast.predicted_mean
            conf_int = fcast.conf_int()

            forecast_df = pd.DataFrame({
                "日期": pred_mean.index,
                "预测值": pred_mean.round(4).values,
                "95%置信下界": conf_int.iloc[:, 0].round(4).values,
                "95%置信上界": conf_int.iloc[:, 1].round(4).values,
            })
            lb_info = ljung_box_test(pd.Series(result.resid))
            return forecast_df, {"order": "(1,1,1)", "seasonal_order": f"(1,1,1,{m})", "AIC": round(result.aic, 2)}, lb_info
        except Exception as e:
            print(f"[错误] SARIMA 拟合失败: {e}")
            sys.exit(1)

    print(f"[信息] 正在自动搜索最优 ARIMA 参数（auto-ARIMA）...")
    m = seasonal_period
    auto_model = pm.auto_arima(
        series,
        seasonal=m > 1,
        m=m,
        stepwise=True,
        information_criterion="aic",
        suppress_warnings=True,
        error_action="ignore",
    )

    order = auto_model.order
    seasonal_order = auto_model.seasonal_order
    aic = auto_model.aic()
    print(f"[信息] 最优参数: ARIMA{order} x {seasonal_order}")
    print(f"[信息] AIC = {aic:.2f}")

    # 预测
    forecast_vals, conf_int = auto_model.predict(n_periods=periods, return_conf_int=True, alpha=0.05)

    # 生成未来日期索引
    last_date = series.index[-1]
    try:
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=pd_freq)[1:]
    except Exception:
        future_dates = [f"T+{i}" for i in range(1, periods + 1)]

    forecast_df = pd.DataFrame({
        "日期": future_dates,
        "预测值": np.round(forecast_vals, 4),
        "95%置信下界": np.round(conf_int[:, 0], 4),
        "95%置信上界": np.round(conf_int[:, 1], 4),
    })

    # 残差诊断
    residuals = pd.Series(auto_model.resid())
    lb_info = ljung_box_test(residuals)

    model_info = {"order": str(order), "seasonal_order": str(seasonal_order), "AIC": round(aic, 2)}
    return forecast_df, model_info, lb_info


def run_holt_winters(series, periods, seasonal_period, trend_type="add", seasonal_type="add"):
    """Holt-Winters 指数平滑"""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    print(f"\n[信息] 正在拟合 Holt-Winters 模型（trend={trend_type}, seasonal={seasonal_type}, period={seasonal_period}）...")

    try:
        model = ExponentialSmoothing(
            series,
            trend=trend_type,
            seasonal=seasonal_type,
            seasonal_periods=seasonal_period,
        ).fit(optimized=True)
    except Exception as e:
        print(f"[警告] Holt-Winters 拟合失败（{e}），尝试无季节性模型...")
        try:
            model = ExponentialSmoothing(
                series, trend=trend_type, seasonal=None
            ).fit(optimized=True)
        except Exception as e2:
            print(f"[错误] Holt-Winters 完全失败: {e2}")
            return None

    forecast_vals = model.forecast(periods)

    forecast_df = pd.DataFrame({
        "日期": forecast_vals.index,
        "预测值": forecast_vals.round(4).values,
    })

    # 计算历史拟合误差
    fitted = model.fittedvalues
    common_idx = series.index.intersection(fitted.index)
    if len(common_idx) > 0:
        actual = series[common_idx].values
        pred = fitted[common_idx].values
        mae = np.mean(np.abs(actual - pred))
        nonzero = actual != 0
        mape = np.mean(np.abs((actual[nonzero] - pred[nonzero]) / actual[nonzero])) * 100 if nonzero.any() else np.nan
        print(f"[评估] Holt-Winters 历史拟合: MAE={mae:.4f}, MAPE={mape:.2f}%")

    print(f"[预测] Holt-Winters 未来 {periods} 期预测（前10行）:")
    print(forecast_df.head(10).to_string(index=False))

    return forecast_df


def main():
    parser = argparse.ArgumentParser(
        description="SARIMA/Holt-Winters 时间序列预测：自动参数搜索、平稳性检验、残差诊断"
    )
    parser.add_argument("input", help="输入数据文件路径（CSV或Excel）")
    parser.add_argument("--time-col", required=True, help="时间列名")
    parser.add_argument("--value-col", required=True, help="数值列名")
    parser.add_argument("--periods", type=int, default=12, help="预测期数（默认12）")
    parser.add_argument("--freq", default="ME", help="预测频率，如 D/W/ME/QE/YE（默认ME）")
    parser.add_argument("--seasonal-period", type=int, default=12,
                        help="季节性周期长度（默认12，如月度数据的年周期）")
    parser.add_argument("--holt-winters", action="store_true", help="同时运行 Holt-Winters 指数平滑")
    parser.add_argument("-o", "--output", default="sarima_output.csv", help="输出CSV文件路径")

    args = parser.parse_args()

    # 加载数据
    series = load_data(args.input, args.time_col, args.value_col)

    # ADF 平稳性检验
    adf_info = adf_test(series)

    # SARIMA 预测
    forecast_df, model_info, lb_info = run_sarima(series, args.periods, args.freq, args.seasonal_period)

    print(f"\n[预测] SARIMA 未来 {args.periods} 期预测（前10行）:")
    print(forecast_df.head(10).to_string(index=False))

    if forecast_df["预测值"].min() < 0 and series.min() >= 0:
        print("[警告] 预测值出现负值，但原始数据均为非负。建议使用对数变换或下界截断")

    # 保存 SARIMA 预测结果
    forecast_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n[输出] SARIMA 预测结果已保存: {args.output}")

    # 保存诊断结果
    diag_path = args.output.replace(".csv", "_diagnostics.csv")
    diag_records = [
        {"检验项目": "ADF平稳性检验", "统计量": adf_info["ADF统计量"],
         "P值": adf_info["P值"], "结论": "平稳" if adf_info["是否平稳"] else "非平稳"},
        {"检验项目": "Ljung-Box残差检验", "统计量": lb_info["最小P值"],
         "P值": lb_info["最小P值"], "结论": "白噪声" if lb_info["是否白噪声"] else "存在自相关"},
        {"检验项目": "模型参数", "统计量": model_info.get("AIC", ""),
         "P值": "", "结论": f"order={model_info['order']}, seasonal={model_info['seasonal_order']}"},
    ]
    diag_df = pd.DataFrame(diag_records)
    diag_df.to_csv(diag_path, index=False, encoding="utf-8-sig")
    print(f"[输出] 诊断结果已保存: {diag_path}")

    # Holt-Winters（可选）
    if args.holt_winters:
        hw_forecast = run_holt_winters(series, args.periods, args.seasonal_period)
        if hw_forecast is not None:
            hw_path = args.output.replace(".csv", "_holtwinters.csv")
            hw_forecast.to_csv(hw_path, index=False, encoding="utf-8-sig")
            print(f"[输出] Holt-Winters 预测结果已保存: {hw_path}")


if __name__ == "__main__":
    main()
