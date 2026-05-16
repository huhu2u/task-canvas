#!/usr/bin/env python3
"""
贝叶斯时序反事实分析脚本

功能：
  - 优先使用 CausalImpact 库（需安装 pycausalimpact）
  - 未安装时回退到 ARIMA 反事实预测
  - 输出实际值与反事实预测的差异、累积效应
  - 计算效应的置信区间和统计显著性

用法：
  python causal_impact.py <数据文件> \
    --time-col <时间列> --outcome-col <结果变量列> \
    --pre-start <干预前起始> --pre-end <干预前结束> \
    --post-start <干预后起始> --post-end <干预后结束> \
    [--covariates <协变量1> <协变量2> ...] \
    [--alpha 0.05] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
from scipy import stats


def load_data(file_path):
    """加载 CSV 或 Excel 文件"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    elif ext == '.csv':
        return pd.read_csv(file_path)
    else:
        try:
            return pd.read_csv(file_path)
        except Exception:
            return pd.read_excel(file_path)


def try_causal_impact(df, time_col, outcome_col, pre_period, post_period,
                      covariates=None, alpha=0.05):
    """
    尝试使用 pycausalimpact 库进行分析。

    返回：
      (result_dict, detail_df) 或 None（如果库未安装）
    """
    try:
        from causalimpact import CausalImpact
    except ImportError:
        return None

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).set_index(time_col)

    cols = [outcome_col]
    if covariates:
        valid_covs = [c for c in covariates if c in df.columns]
        cols.extend(valid_covs)

    data = df[cols].dropna()

    try:
        ci = CausalImpact(data, pre_period, post_period, alpha=alpha)
    except Exception as e:
        print(f"  [警告] CausalImpact 模型拟合失败: {e}")
        return None

    # 防御性检查：inferences 可能为 None（模型拟合静默失败）
    if ci.inferences is None:
        print("  [警告] CausalImpact 模型拟合未收敛（inferences 为空），回退到 ARIMA 方案")
        return None

    try:
        print(ci.summary())
        print(ci.summary(output='report'))
    except Exception as e:
        print(f"  [警告] CausalImpact summary 输出异常: {e}，继续提取核心结果")

    # 提取核心结果
    summary = ci.inferences
    post_mask = summary.index >= pd.to_datetime(post_period[0])
    post_data = summary[post_mask]

    avg_effect = post_data['point_effect'].mean()
    cum_effect = post_data['point_effect'].sum()
    avg_effect_lower = post_data['point_effect_lower'].mean()
    avg_effect_upper = post_data['point_effect_upper'].mean()

    # 统计显著性：检查累积效应置信区间是否包含0
    cum_lower = post_data['point_effect_lower'].sum()
    cum_upper = post_data['point_effect_upper'].sum()
    is_significant = not (cum_lower <= 0 <= cum_upper)

    result = {
        "方法": "CausalImpact（贝叶斯结构时序）",
        "平均效应": round(avg_effect, 4),
        "累积效应": round(cum_effect, 4),
        "平均效应CI下界": round(avg_effect_lower, 4),
        "平均效应CI上界": round(avg_effect_upper, 4),
        "累积效应CI下界": round(cum_lower, 4),
        "累积效应CI上界": round(cum_upper, 4),
        "显著性": "显著" if is_significant else "不显著"
    }

    detail_df = post_data[['point_pred', 'point_effect',
                           'point_effect_lower', 'point_effect_upper']].copy()
    detail_df.columns = ['反事实预测', '效应', '效应CI下界', '效应CI上界']
    detail_df['实际值'] = df.loc[post_data.index, outcome_col]
    detail_df['累积效应'] = detail_df['效应'].cumsum()

    return result, detail_df


def arima_fallback(df, time_col, outcome_col, pre_start, pre_end,
                   post_start, post_end, alpha=0.05):
    """
    ARIMA 回退方案：用干预前数据拟合 ARIMA，预测干预后作为反事实。

    返回：
      (result_dict, detail_df)
    """
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.stattools import adfuller

    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).set_index(time_col)

    pre_start_dt = pd.to_datetime(pre_start)
    pre_end_dt = pd.to_datetime(pre_end)
    post_start_dt = pd.to_datetime(post_start)
    post_end_dt = pd.to_datetime(post_end)

    pre_data = df[(df.index >= pre_start_dt) & (df.index <= pre_end_dt)][outcome_col].dropna()
    post_data = df[(df.index >= post_start_dt) & (df.index <= post_end_dt)][outcome_col].dropna()

    if len(pre_data) < 10:
        print("  错误：干预前数据不足（< 10 个观测），无法拟合 ARIMA")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  贝叶斯时序反事实分析（ARIMA 回退方案）")
    print(f"{'='*70}")
    print(f"  干预前期间: {pre_start} ~ {pre_end}（{len(pre_data)} 个观测）")
    print(f"  干预后期间: {post_start} ~ {post_end}（{len(post_data)} 个观测）")

    # ADF 平稳性检验
    adf_result = adfuller(pre_data)
    is_stationary = adf_result[1] < 0.05
    d = 0 if is_stationary else 1
    print(f"  ADF 检验 p值={adf_result[1]:.4f}，{'平稳' if is_stationary else '非平稳（取一阶差分）'}")

    # 自动选择 ARIMA 阶数
    best_aic = np.inf
    best_order = (1, d, 0)
    for p in range(0, 4):
        for q in range(0, 4):
            try:
                model = ARIMA(pre_data, order=(p, d, q))
                fitted = model.fit()
                if fitted.aic < best_aic:
                    best_aic = fitted.aic
                    best_order = (p, d, q)
            except Exception:
                continue

    print(f"  最优 ARIMA 阶数: {best_order}（AIC={best_aic:.2f}）")

    # 拟合最终模型并预测
    model = ARIMA(pre_data, order=best_order)
    fitted = model.fit()
    n_forecast = len(post_data)
    forecast_result = fitted.get_forecast(steps=n_forecast)
    forecast_mean = forecast_result.predicted_mean
    forecast_ci = forecast_result.conf_int(alpha=alpha)

    # 对齐索引
    forecast_mean.index = post_data.index[:len(forecast_mean)]
    forecast_ci.index = post_data.index[:len(forecast_ci)]

    # 计算效应
    actual = post_data.iloc[:len(forecast_mean)]
    effect = actual.values - forecast_mean.values
    cum_effect = np.cumsum(effect)

    ci_lower = actual.values - forecast_ci.iloc[:, 1].values
    ci_upper = actual.values - forecast_ci.iloc[:, 0].values

    avg_effect = np.mean(effect)
    total_cum = cum_effect[-1] if len(cum_effect) > 0 else 0

    # 显著性：bootstrap 或 t 检验
    se = np.std(effect, ddof=1) / np.sqrt(len(effect)) if len(effect) > 1 else 0
    if se > 0:
        t_stat = avg_effect / se
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=len(effect)-1))
    else:
        p_value = 1.0

    is_significant = p_value < alpha

    print(f"\n  -- 反事实分析结果 --")
    print(f"  平均效应: {avg_effect:.4f}")
    print(f"  累积效应: {total_cum:.4f}")
    print(f"  效应 P 值: {p_value:.6f}")
    print(f"  显著性: {'显著' if is_significant else '不显著'}")

    if is_significant:
        direction = "正向" if avg_effect > 0 else "负向"
        print(f"\n  结论: 干预产生了统计显著的{direction}效应，平均效应 {abs(avg_effect):.4f}")
    else:
        print(f"\n  结论: 未检测到统计显著的干预效应")

    result = {
        "方法": "ARIMA 反事实预测（回退方案）",
        "ARIMA阶数": str(best_order),
        "平均效应": round(avg_effect, 4),
        "累积效应": round(total_cum, 4),
        "效应P值": round(p_value, 6),
        "平均效应CI下界": round(np.mean(ci_lower), 4),
        "平均效应CI上界": round(np.mean(ci_upper), 4),
        "显著性": "显著" if is_significant else "不显著"
    }

    detail_rows = []
    for i in range(len(actual)):
        detail_rows.append({
            "时间": str(actual.index[i]),
            "实际值": round(actual.values[i], 4),
            "反事实预测": round(forecast_mean.values[i], 4),
            "效应": round(effect[i], 4),
            "累积效应": round(cum_effect[i], 4),
            "效应CI下界": round(ci_lower[i], 4),
            "效应CI上界": round(ci_upper[i], 4)
        })

    detail_df = pd.DataFrame(detail_rows)
    return result, detail_df


def main():
    parser = argparse.ArgumentParser(
        description="贝叶斯时序反事实分析（CausalImpact / ARIMA 回退）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--time-col", required=True, help="时间列")
    parser.add_argument("--outcome-col", required=True, help="结果变量列")
    parser.add_argument("--pre-start", required=True, help="干预前起始时间")
    parser.add_argument("--pre-end", required=True, help="干预前结束时间")
    parser.add_argument("--post-start", required=True, help="干预后起始时间")
    parser.add_argument("--post-end", required=True, help="干预后结束时间")
    parser.add_argument("--covariates", nargs="*", default=None, help="协变量列")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    required_cols = [args.time_col, args.outcome_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # 尝试 CausalImpact
    pre_period = [args.pre_start, args.pre_end]
    post_period = [args.post_start, args.post_end]
    ci_result = try_causal_impact(df, args.time_col, args.outcome_col,
                                  pre_period, post_period,
                                  args.covariates, args.alpha)

    if ci_result is not None:
        result, detail_df = ci_result
        print("  使用 CausalImpact 库完成分析")
    else:
        print("  CausalImpact 库未安装，回退到 ARIMA 反事实预测")
        result, detail_df = arima_fallback(
            df, args.time_col, args.outcome_col,
            args.pre_start, args.pre_end,
            args.post_start, args.post_end, args.alpha
        )

    # 保存结果
    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "causal_impact_result.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n主结果已保存至: {out_path}")

    detail_path = os.path.join(args.output_dir, "causal_impact_detail.csv")
    detail_df.to_csv(detail_path, index=False, encoding='utf-8-sig')
    print(f"逐期结果已保存至: {detail_path}")


if __name__ == "__main__":
    main()
