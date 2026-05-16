#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预测评估与回测脚本
功能：标准化评估（MAE/MAPE/SMAPE/RMSE）、预测区间覆盖率、时间序列回测、多模型组合
输出：评估指标汇总表CSV
"""

import argparse
import sys
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


def load_evaluation_data(actual_file, forecast_file, actual_col, forecast_col,
                         lower_col=None, upper_col=None):
    """加载实际值和预测值数据"""
    try:
        if actual_file.endswith(".xlsx") or actual_file.endswith(".xls"):
            actual_df = pd.read_excel(actual_file)
        else:
            actual_df = pd.read_csv(actual_file)
    except Exception as e:
        print(f"[错误] 无法读取实际值文件 {actual_file}: {e}")
        sys.exit(1)

    try:
        if forecast_file.endswith(".xlsx") or forecast_file.endswith(".xls"):
            forecast_df = pd.read_excel(forecast_file)
        else:
            forecast_df = pd.read_csv(forecast_file)
    except Exception as e:
        print(f"[错误] 无法读取预测值文件 {forecast_file}: {e}")
        sys.exit(1)

    if actual_col not in actual_df.columns:
        print(f"[错误] 实际值列 '{actual_col}' 不存在于 {actual_file}。可用列: {list(actual_df.columns)}")
        sys.exit(1)
    if forecast_col not in forecast_df.columns:
        print(f"[错误] 预测值列 '{forecast_col}' 不存在于 {forecast_file}。可用列: {list(forecast_df.columns)}")
        sys.exit(1)

    actual = actual_df[actual_col].dropna().values.astype(float)
    predicted = forecast_df[forecast_col].dropna().values.astype(float)

    min_len = min(len(actual), len(predicted))
    if min_len == 0:
        print("[错误] 实际值或预测值为空")
        sys.exit(1)
    actual = actual[:min_len]
    predicted = predicted[:min_len]

    lower = None
    upper = None
    if lower_col and lower_col in forecast_df.columns:
        lower = forecast_df[lower_col].dropna().values.astype(float)[:min_len]
    if upper_col and upper_col in forecast_df.columns:
        upper = forecast_df[upper_col].dropna().values.astype(float)[:min_len]

    print(f"[信息] 评估数据: {min_len} 个对比点")
    return actual, predicted, lower, upper


def compute_metrics(actual, predicted, model_name="模型"):
    """计算标准评估指标"""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)

    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))

    # MAPE
    nonzero_mask = actual != 0
    mape = np.mean(np.abs((actual[nonzero_mask] - predicted[nonzero_mask]) / actual[nonzero_mask])) * 100 if nonzero_mask.any() else np.nan

    # SMAPE
    denom = np.abs(actual) + np.abs(predicted)
    smape_mask = denom > 0
    smape = np.mean(2 * np.abs(actual[smape_mask] - predicted[smape_mask]) / denom[smape_mask]) * 100 if smape_mask.any() else np.nan

    # R2
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    # MAPE 评级
    if np.isnan(mape):
        grade = "无法计算"
    elif mape < 5:
        grade = "优秀（<5%）"
    elif mape < 10:
        grade = "良好（5-10%）"
    elif mape < 20:
        grade = "一般（10-20%）"
    elif mape < 30:
        grade = "偏差较大（20-30%）"
    else:
        grade = "较差（>30%），建议补充外生变量或人工判断"

    metrics = {
        "模型": model_name,
        "MAE": round(mae, 4),
        "MAPE(%)": round(mape, 2) if not np.isnan(mape) else "NaN",
        "SMAPE(%)": round(smape, 2) if not np.isnan(smape) else "NaN",
        "RMSE": round(rmse, 4),
        "R2": round(r2, 4) if not np.isnan(r2) else "NaN",
        "MAPE评级": grade,
    }

    print(f"\n[评估] {model_name} 指标:")
    for k, v in metrics.items():
        if k != "模型":
            print(f"  {k} = {v}")

    return metrics


def coverage_rate(actual, lower, upper):
    """计算预测区间覆盖率"""
    if lower is None or upper is None:
        print("[信息] 未提供预测区间，跳过覆盖率计算")
        return None

    actual = np.array(actual, dtype=float)
    lower = np.array(lower, dtype=float)
    upper = np.array(upper, dtype=float)

    in_interval = (actual >= lower) & (actual <= upper)
    rate = np.mean(in_interval) * 100

    print(f"\n[评估] 预测区间覆盖率: {rate:.1f}%（{in_interval.sum()}/{len(actual)}）")
    if rate < 90:
        print("  [警告] 覆盖率低于90%，预测区间可能过窄")
    elif rate > 99:
        print("  [提示] 覆盖率过高，预测区间可能过宽")

    return rate


def time_series_backtest(file_path, time_col, value_col, n_folds=5, horizon=None, baseline="naive"):
    """时间序列回测（expanding window）"""
    try:
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[错误] 无法读取文件: {e}")
        sys.exit(1)

    if value_col not in df.columns:
        print(f"[错误] 数值列 '{value_col}' 不存在")
        sys.exit(1)

    series = df[value_col].dropna().values.astype(float)
    n = len(series)

    if horizon is None:
        horizon = max(1, n // (n_folds + 1))

    min_train = max(horizon * 2, n // 3)
    fold_metrics = []

    print(f"\n[回测] 时间序列回测: {n_folds} 折, horizon={horizon}, baseline={baseline}")

    for fold in range(n_folds):
        train_end = min_train + fold * horizon
        test_end = train_end + horizon
        if test_end > n:
            break

        train = series[:train_end]
        test_actual = series[train_end:test_end]

        if baseline == "naive":
            predicted = np.full(len(test_actual), train[-1])
        elif baseline == "mean":
            predicted = np.full(len(test_actual), np.mean(train))
        elif baseline == "drift":
            drift = (train[-1] - train[0]) / (len(train) - 1) if len(train) > 1 else 0
            predicted = train[-1] + drift * np.arange(1, len(test_actual) + 1)
        else:
            predicted = np.full(len(test_actual), train[-1])

        fold_mae = np.mean(np.abs(test_actual - predicted))
        nonzero = test_actual != 0
        fold_mape = np.mean(np.abs((test_actual[nonzero] - predicted[nonzero]) / test_actual[nonzero])) * 100 if nonzero.any() else np.nan
        fold_rmse = np.sqrt(np.mean((test_actual - predicted) ** 2))

        fold_metrics.append({
            "折数": fold + 1,
            "训练集大小": train_end,
            "测试集大小": min(horizon, n - train_end),
            "MAE": round(fold_mae, 4),
            "MAPE(%)": round(fold_mape, 2) if not np.isnan(fold_mape) else "NaN",
            "RMSE": round(fold_rmse, 4),
        })
        print(f"  Fold {fold+1}: MAE={fold_mae:.4f}, MAPE={fold_mape:.2f}%, RMSE={fold_rmse:.4f}")

    result_df = pd.DataFrame(fold_metrics)

    # 稳定性检查
    if len(result_df) > 1:
        mae_vals = [r["MAE"] for r in fold_metrics]
        mae_cv = np.std(mae_vals) / np.mean(mae_vals) if np.mean(mae_vals) > 0 else 0
        if mae_cv > 0.5:
            print(f"[警告] 回测各折MAE变异系数={mae_cv:.2f}，模型稳定性不足")

    return result_df


def ensemble_forecast(forecast_files, forecast_col, weights=None):
    """多模型组合预测"""
    forecasts = []
    for f in forecast_files:
        try:
            df = pd.read_excel(f) if f.endswith((".xlsx", ".xls")) else pd.read_csv(f)
            if forecast_col in df.columns:
                forecasts.append(df[forecast_col].dropna().values.astype(float))
            else:
                print(f"[警告] {f} 中不存在列 '{forecast_col}'，跳过")
        except Exception as e:
            print(f"[警告] 无法读取 {f}: {e}")

    if len(forecasts) == 0:
        print("[错误] 没有有效的预测数据")
        return None

    min_len = min(len(f) for f in forecasts)
    forecasts = [f[:min_len] for f in forecasts]
    forecast_array = np.array(forecasts)

    if weights is None or len(weights) != len(forecasts):
        if weights is not None and len(weights) != len(forecasts):
            print("[警告] 权重数量不匹配，使用等权")
        combined = np.mean(forecast_array, axis=0)
        print(f"[组合] 等权平均: {len(forecasts)} 个模型")
    else:
        w = np.array(weights) / np.sum(weights)
        combined = np.average(forecast_array, axis=0, weights=w)
        print(f"[组合] 加权平均: 权重={w.round(3).tolist()}")

    return pd.DataFrame({"期数": range(1, min_len + 1), "组合预测值": np.round(combined, 4)})


def main():
    parser = argparse.ArgumentParser(
        description="预测评估与回测：MAE/MAPE/SMAPE/RMSE、区间覆盖率、时间序列交叉验证、多模型组合"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # evaluate
    eval_p = subparsers.add_parser("evaluate", help="对比实际值与预测值")
    eval_p.add_argument("--actual-file", required=True, help="实际值文件")
    eval_p.add_argument("--forecast-file", required=True, help="预测值文件")
    eval_p.add_argument("--actual-col", required=True, help="实际值列名")
    eval_p.add_argument("--forecast-col", required=True, help="预测值列名")
    eval_p.add_argument("--lower-col", default=None, help="区间下界列名")
    eval_p.add_argument("--upper-col", default=None, help="区间上界列名")
    eval_p.add_argument("--model-name", default="预测模型", help="模型名称")
    eval_p.add_argument("-o", "--output", default="eval_output.csv", help="输出CSV")

    # backtest
    bt_p = subparsers.add_parser("backtest", help="时间序列回测")
    bt_p.add_argument("input", help="输入数据文件")
    bt_p.add_argument("--time-col", required=True, help="时间列名")
    bt_p.add_argument("--value-col", required=True, help="数值列名")
    bt_p.add_argument("--n-folds", type=int, default=5, help="回测折数（默认5）")
    bt_p.add_argument("--horizon", type=int, default=None, help="每折预测步长")
    bt_p.add_argument("--baseline", default="naive", choices=["naive", "mean", "drift"], help="基准模型")
    bt_p.add_argument("-o", "--output", default="backtest_output.csv", help="输出CSV")

    # ensemble
    ens_p = subparsers.add_parser("ensemble", help="多模型组合预测")
    ens_p.add_argument("--forecast-files", nargs="+", required=True, help="预测文件列表")
    ens_p.add_argument("--forecast-col", required=True, help="预测值列名")
    ens_p.add_argument("--weights", nargs="+", type=float, default=None, help="权重")
    ens_p.add_argument("-o", "--output", default="ensemble_output.csv", help="输出CSV")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "evaluate":
        actual, predicted, lower, upper = load_evaluation_data(
            args.actual_file, args.forecast_file, args.actual_col, args.forecast_col,
            lower_col=args.lower_col, upper_col=args.upper_col,
        )
        metrics = compute_metrics(actual, predicted, model_name=args.model_name)
        cov_rate = coverage_rate(actual, lower, upper)
        if cov_rate is not None:
            metrics["区间覆盖率(%)"] = round(cov_rate, 1)
        pd.DataFrame([metrics]).to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n[输出] 评估结果已保存: {args.output}")

    elif args.command == "backtest":
        bt_results = time_series_backtest(
            args.input, args.time_col, args.value_col,
            n_folds=args.n_folds, horizon=args.horizon, baseline=args.baseline
        )
        bt_results.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n[输出] 回测结果已保存: {args.output}")

    elif args.command == "ensemble":
        combined = ensemble_forecast(args.forecast_files, args.forecast_col, args.weights)
        if combined is not None:
            combined.to_csv(args.output, index=False, encoding="utf-8-sig")
            print(f"\n[输出] 组合预测已保存: {args.output}")


if __name__ == "__main__":
    main()
