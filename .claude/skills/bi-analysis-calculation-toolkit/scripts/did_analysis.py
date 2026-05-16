#!/usr/bin/env python3
"""
双重差分法（DID）分析脚本

功能：
  - 构建DID回归模型（OLS + 异方差稳健标准误HC3）
  - 自动验证平行趋势假设：输出干预前各期的组间差异
  - 事件研究（Event Study）：计算干预前各期系数，检验是否显著异于0
  - 输出ATT估计值、置信区间、p值
  - 支持添加控制变量

用法：
  python did_analysis.py <数据文件> \
    --group-col <组别列> --time-col <时间列> --outcome-col <结果变量列> \
    --treat-time <干预时间点> \
    [--control-cols <控制变量1> <控制变量2> ...] \
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


def did_regression(df, group_col, time_col, outcome_col, treat_time,
                   control_cols=None, alpha=0.05):
    """
    双重差分回归分析。

    参数：
      df:           DataFrame
      group_col:    组别列（实验组/对照组标识，1=实验组, 0=对照组）
      time_col:     时间列
      outcome_col:  结果变量列
      treat_time:   干预时间点
      control_cols: 控制变量列名列表
      alpha:        显著性水平

    返回：
      dict — DID分析结果
    """
    import statsmodels.api as sm

    df = df.copy()

    # 自动判断时间列类型：若为数值型则直接比较，否则转为 datetime
    time_is_numeric = pd.api.types.is_numeric_dtype(df[time_col])
    if time_is_numeric:
        treat_time_parsed = float(treat_time)
    else:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        treat_time_parsed = pd.to_datetime(treat_time)

    # 构建 Post 变量
    df['Post'] = (df[time_col] >= treat_time_parsed).astype(int)
    df['Treat'] = df[group_col].astype(int)
    df['Treat_x_Post'] = df['Treat'] * df['Post']

    print(f"\n{'='*70}")
    print(f"  双重差分法（DID）分析")
    print(f"{'='*70}")
    print(f"  组别列: {group_col}")
    print(f"  时间列: {time_col}")
    print(f"  结果变量: {outcome_col}")
    print(f"  干预时间: {treat_time}")
    print(f"  实验组样本: {df['Treat'].sum()}, 对照组样本: {(1-df['Treat']).sum()}")
    print(f"  干预前样本: {(1-df['Post']).sum()}, 干预后样本: {df['Post'].sum()}")

    # ---- 平行趋势验证 ----
    print(f"\n  -- 平行趋势验证 --")
    pre_data = df[df['Post'] == 0]
    if time_col in pre_data.columns:
        pre_periods = sorted(pre_data[time_col].unique())
        trend_results = []
        for t in pre_periods:
            period_data = pre_data[pre_data[time_col] == t]
            treat_vals = period_data[period_data['Treat'] == 1][outcome_col].dropna()
            control_vals = period_data[period_data['Treat'] == 0][outcome_col].dropna()
            if len(treat_vals) > 0 and len(control_vals) > 0:
                diff = treat_vals.mean() - control_vals.mean()
                trend_results.append({
                    "时间": str(t),
                    "实验组均值": round(treat_vals.mean(), 4),
                    "对照组均值": round(control_vals.mean(), 4),
                    "组间差异": round(diff, 4)
                })

        if trend_results:
            trend_df = pd.DataFrame(trend_results)
            print(trend_df.to_string(index=False))
            diffs = [r["组间差异"] for r in trend_results]
            diff_std = np.std(diffs) if len(diffs) > 1 else 0
            print(f"  组间差异标准差: {diff_std:.4f}")
            if diff_std < abs(np.mean(diffs)) * 0.5 and len(diffs) >= 2:
                print(f"  平行趋势假设: 初步满足（干预前组间差异较稳定）")
            else:
                print(f"  平行趋势假设: 需谨慎（干预前组间差异波动较大）")
        else:
            print(f"  干预前数据不足，无法验证平行趋势")

    # ---- DID 回归 ----
    print(f"\n  -- DID 回归 --")
    X_cols = ['Treat', 'Post', 'Treat_x_Post']
    if control_cols:
        valid_controls = [c for c in control_cols if c in df.columns]
        X_cols.extend(valid_controls)
        if len(valid_controls) < len(control_cols):
            missing = set(control_cols) - set(valid_controls)
            print(f"  警告：以下控制变量不存在: {missing}")

    X = sm.add_constant(df[X_cols].astype(float))
    y = df[outcome_col].astype(float)

    # 删除缺失值
    valid_mask = X.notna().all(axis=1) & y.notna()
    X = X[valid_mask]
    y = y[valid_mask]

    model = sm.OLS(y, X).fit(cov_type='HC3')

    att = model.params['Treat_x_Post']
    se = model.bse['Treat_x_Post']
    p_value = model.pvalues['Treat_x_Post']
    ci = model.conf_int(alpha=alpha).loc['Treat_x_Post']

    print(f"  ATT（平均处理效应）: {att:.4f}")
    print(f"  标准误（HC3）: {se:.4f}")
    print(f"  P 值: {p_value:.6f}")
    print(f"  {int((1-alpha)*100)}% 置信区间: [{ci[0]:.4f}, {ci[1]:.4f}]")
    print(f"  R²: {model.rsquared:.4f}")

    is_significant = p_value < alpha
    if is_significant:
        direction = "正向" if att > 0 else "负向"
        print(f"\n  结论: 干预效果统计显著（p < {alpha}），{direction}效应 {abs(att):.4f}")
    else:
        print(f"\n  结论: 干预效果不显著（p >= {alpha}）")

    # ---- 事件研究（Event Study）----
    print(f"\n  -- 事件研究（Event Study）--")
    all_periods = sorted(df[time_col].unique())
    try:
        treat_idx = list(all_periods).index(treat_time_parsed)
    except ValueError:
        treat_idx = None

    event_results = []
    if treat_idx is not None and treat_idx > 0:
        df['RelTime'] = None
        for i, t in enumerate(all_periods):
            df.loc[df[time_col] == t, 'RelTime'] = i - treat_idx

        df['RelTime'] = df['RelTime'].astype(float)
        rel_times = sorted(df['RelTime'].unique())

        # 基准期：干预前一期（-1）
        base_period = -1
        event_dummies = []
        for rt in rel_times:
            if rt != base_period:
                col_name = f'RT_{int(rt)}'
                df[col_name] = ((df['RelTime'] == rt) & (df['Treat'] == 1)).astype(int)
                event_dummies.append(col_name)

        if event_dummies:
            X_event = sm.add_constant(df[['Treat', 'Post'] + event_dummies].astype(float))
            valid_mask = X_event.notna().all(axis=1) & y.index.isin(X_event.index)
            X_ev = X_event[valid_mask]
            y_ev = df.loc[valid_mask.index[valid_mask], outcome_col].astype(float)

            if len(X_ev) > len(event_dummies) + 3:
                event_model = sm.OLS(y_ev, X_ev).fit(cov_type='HC3')
                for col in event_dummies:
                    rt_val = int(col.replace('RT_', ''))
                    coef = event_model.params.get(col, np.nan)
                    p_val = event_model.pvalues.get(col, np.nan)
                    event_results.append({
                        "相对时间": rt_val,
                        "系数": round(coef, 4) if not np.isnan(coef) else None,
                        "P值": round(p_val, 6) if not np.isnan(p_val) else None,
                        "显著": "是" if (not np.isnan(p_val) and p_val < alpha) else "否"
                    })

                event_df = pd.DataFrame(event_results)
                print(event_df.to_string(index=False))

                pre_sig = event_df[(event_df["相对时间"] < 0) & (event_df["显著"] == "是")]
                if len(pre_sig) > 0:
                    print(f"  警告：干预前有 {len(pre_sig)} 期系数显著异于0，平行趋势假设可能不满足")
                else:
                    print(f"  干预前各期系数均不显著异于0，支持平行趋势假设")
    else:
        print(f"  无法构建事件研究（干预时间点不在数据时间范围内或数据不足）")

    result = {
        "ATT": round(att, 4),
        "标准误_HC3": round(se, 4),
        "P值": round(p_value, 6),
        "CI下界": round(ci[0], 4),
        "CI上界": round(ci[1], 4),
        "R_squared": round(model.rsquared, 4),
        "显著性": "显著" if is_significant else "不显著",
        "实验组N": int(df['Treat'].sum()),
        "对照组N": int((1 - df['Treat']).sum()),
        "干预前N": int((1 - df['Post']).sum()),
        "干预后N": int(df['Post'].sum())
    }

    return result, event_results


def main():
    parser = argparse.ArgumentParser(
        description="双重差分法（DID）分析",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--group-col", required=True, help="组别列（1=实验组, 0=对照组）")
    parser.add_argument("--time-col", required=True, help="时间列")
    parser.add_argument("--outcome-col", required=True, help="结果变量列")
    parser.add_argument("--treat-time", required=True, help="干预时间点（如 2024-01-01）")
    parser.add_argument("--control-cols", nargs="*", default=None, help="控制变量列")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    required_cols = [args.group_col, args.time_col, args.outcome_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result, event_results = did_regression(
        df, args.group_col, args.time_col, args.outcome_col,
        args.treat_time, args.control_cols, args.alpha
    )

    # 保存主结果
    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "did_result.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\nDID结果已保存至: {out_path}")

    # 保存事件研究结果
    if event_results:
        event_df = pd.DataFrame(event_results)
        event_path = os.path.join(args.output_dir, "did_event_study.csv")
        event_df.to_csv(event_path, index=False, encoding='utf-8-sig')
        print(f"事件研究结果已保存至: {event_path}")


if __name__ == "__main__":
    main()
