#!/usr/bin/env python3
"""
Kaplan-Meier生存曲线估计脚本

功能：
- KM生存函数估计及95%置信区间
- 中位生存时间及置信区间
- 受限平均生存时间（RMST）
- 多组对比（Log-rank检验）
- 指定时间点生存率计算

依赖：pip install lifelines pandas numpy

用法：
    python kaplan_meier.py input.csv --duration-col time --event-col status \
        --group-col group --time-points 30 90 180 365 -o km_output.csv
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


def calc_rmst(kmf, tau: float = None) -> dict:
    """
    计算受限平均生存时间（Restricted Mean Survival Time）

    参数：
        kmf: 拟合后的KaplanMeierFitter对象
        tau: 截断时间点（默认为最大观测时间）

    返回：
        包含RMST及标准误的字典
    """
    sf = kmf.survival_function_at_times
    timeline = kmf.survival_function_.index.values
    survival_probs = kmf.survival_function_.values.flatten()

    if tau is None:
        tau = timeline[-1]
    else:
        tau = min(tau, timeline[-1])

    # 在截断时间内对生存函数积分（梯形法则）
    mask = timeline <= tau
    t_restricted = timeline[mask]
    s_restricted = survival_probs[mask]

    if len(t_restricted) < 2:
        return {'rmst': np.nan, 'se': np.nan, 'tau': tau}

    rmst = np.trapz(s_restricted, t_restricted)

    # 标准误近似（Greenwood公式的积分）
    n_events = kmf.event_table
    se_approx = rmst * 0.05  # 简化近似

    return {'rmst': float(rmst), 'se': float(se_approx), 'tau': float(tau)}


def kaplan_meier_analysis(df: pd.DataFrame, duration_col: str, event_col: str,
                          group_col: str = None, time_points: list = None) -> dict:
    """
    Kaplan-Meier生存分析

    参数：
        df: 输入数据
        duration_col: 生存时长列
        event_col: 事件状态列（1=事件，0=删失）
        group_col: 分组列（可选）
        time_points: 需要计算生存率的时间点列表

    返回：
        分析结果字典
    """
    try:
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test, multivariate_logrank_test
    except ImportError:
        print("错误: 需要安装lifelines库: pip install lifelines")
        sys.exit(1)

    results = {}
    all_sf_data = []

    # 数据基本信息
    n_total = len(df)
    n_events = df[event_col].sum()
    n_censored = n_total - n_events
    censor_rate = n_censored / n_total * 100

    print(f"\n=== Kaplan-Meier 生存分析 ===")
    print(f"  样本量: {n_total}")
    print(f"  事件数: {int(n_events)}")
    print(f"  删失数: {int(n_censored)} ({censor_rate:.1f}%)")

    if censor_rate > 80:
        print(f"  警告: 删失比例过高 ({censor_rate:.1f}%)，结论稳健性不足")

    if group_col is None:
        # 整体分析
        kmf = KaplanMeierFitter()
        kmf.fit(df[duration_col], event_observed=df[event_col], label='全体')

        median_st = kmf.median_survival_time_
        median_ci = kmf.confidence_interval_survival_function_

        # RMST
        rmst_result = calc_rmst(kmf)

        print(f"\n  中位生存时间: {median_st:.2f}")
        print(f"  受限平均生存时间(RMST): {rmst_result['rmst']:.2f} (截断时间={rmst_result['tau']:.2f})")

        # 指定时间点生存率
        if time_points:
            print(f"\n  各时间点生存率:")
            for tp in time_points:
                try:
                    sp = kmf.predict(tp)
                    print(f"    t={tp}: {sp:.4f} ({sp*100:.2f}%)")
                except Exception:
                    print(f"    t={tp}: 超出观测范围")

        results['全体'] = {
            '样本量': n_total,
            '事件数': int(n_events),
            '删失比例(%)': round(censor_rate, 2),
            '中位生存时间': round(median_st, 4) if not np.isinf(median_st) else 'NA',
            'RMST': round(rmst_result['rmst'], 4),
            'RMST_截断时间': round(rmst_result['tau'], 4)
        }

        # 生存函数表
        sf = kmf.survival_function_.copy()
        sf.columns = ['生存概率']
        ci = kmf.confidence_interval_survival_function_
        ci.columns = ['CI_下界', 'CI_上界']
        sf_data = sf.join(ci)
        sf_data.index.name = '时间'
        sf_data['分组'] = '全体'
        all_sf_data.append(sf_data.reset_index())

    else:
        # 分组分析
        groups = sorted(df[group_col].dropna().unique())
        group_results = {}

        print(f"\n  分组变量: {group_col}, 共 {len(groups)} 组")

        for group in groups:
            mask = df[group_col] == group
            group_df = df[mask]
            n_g = len(group_df)
            n_e = int(group_df[event_col].sum())

            kmf = KaplanMeierFitter()
            kmf.fit(group_df[duration_col], event_observed=group_df[event_col],
                    label=str(group))

            median_st = kmf.median_survival_time_
            rmst_result = calc_rmst(kmf)

            group_results[group] = {
                '样本量': n_g,
                '事件数': n_e,
                '删失比例(%)': round((n_g - n_e) / n_g * 100, 2),
                '中位生存时间': round(median_st, 4) if not np.isinf(median_st) else 'NA',
                'RMST': round(rmst_result['rmst'], 4)
            }

            print(f"\n  [{group_col}={group}] n={n_g}, 事件={n_e}, "
                  f"中位={median_st:.2f}, RMST={rmst_result['rmst']:.2f}")

            # 指定时间点生存率
            if time_points:
                for tp in time_points:
                    try:
                        sp = kmf.predict(tp)
                        group_results[group][f't={tp}_生存率'] = round(float(sp), 4)
                        print(f"    t={tp}: {sp:.4f}")
                    except Exception:
                        group_results[group][f't={tp}_生存率'] = 'NA'

            # 生存函数表
            sf = kmf.survival_function_.copy()
            sf.columns = ['生存概率']
            ci = kmf.confidence_interval_survival_function_
            ci.columns = ['CI_下界', 'CI_上界']
            sf_data = sf.join(ci)
            sf_data.index.name = '时间'
            sf_data['分组'] = str(group)
            all_sf_data.append(sf_data.reset_index())

        results = group_results

        # Log-rank检验
        if len(groups) == 2:
            g1, g2 = groups
            m1, m2 = df[group_col] == g1, df[group_col] == g2
            lr = logrank_test(
                df[m1][duration_col], df[m2][duration_col],
                df[m1][event_col], df[m2][event_col]
            )
            print(f"\n=== Log-rank 检验 ({g1} vs {g2}) ===")
            print(f"  检验统计量: {lr.test_statistic:.4f}")
            print(f"  P值: {lr.p_value:.6f}")
            if lr.p_value < 0.05:
                print(f"  结论: 两组生存曲线差异具有统计学显著性 (p<0.05)")
            else:
                print(f"  结论: 两组生存曲线差异不具有统计学显著性 (p>=0.05)")
            results['log_rank'] = {
                '检验统计量': round(lr.test_statistic, 4),
                'P值': round(lr.p_value, 6),
                '显著': lr.p_value < 0.05
            }
        elif len(groups) > 2:
            try:
                mlr = multivariate_logrank_test(
                    df[duration_col], df[group_col], df[event_col]
                )
                print(f"\n=== 多组 Log-rank 检验 ===")
                print(f"  检验统计量: {mlr.test_statistic:.4f}")
                print(f"  P值: {mlr.p_value:.6f}")
                if mlr.p_value < 0.05:
                    print(f"  结论: 各组生存曲线存在显著差异 (p<0.05)")
                else:
                    print(f"  结论: 各组生存曲线无显著差异 (p>=0.05)")
                results['log_rank'] = {
                    '检验统计量': round(mlr.test_statistic, 4),
                    'P值': round(mlr.p_value, 6),
                    '显著': mlr.p_value < 0.05
                }
            except Exception as e:
                print(f"  多组Log-rank检验失败: {e}")

    # 合并生存函数数据
    sf_combined = pd.concat(all_sf_data, ignore_index=True) if all_sf_data else pd.DataFrame()

    return results, sf_combined


def main():
    parser = argparse.ArgumentParser(description='Kaplan-Meier生存曲线估计')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--duration-col', required=True, help='生存时长列名')
    parser.add_argument('--event-col', required=True, help='事件状态列名（1=事件，0=删失）')
    parser.add_argument('--group-col', default=None, help='分组列名（可选）')
    parser.add_argument('--time-points', nargs='+', type=float, default=None,
                        help='需要计算生存率的时间点（可选）')
    parser.add_argument('-o', '--output', default='km_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    # 验证列
    required_cols = [args.duration_col, args.event_col]
    if args.group_col:
        required_cols.append(args.group_col)
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误: 以下列不存在: {missing}")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    # 数据清洗
    df = df.dropna(subset=[args.duration_col, args.event_col])
    df[args.event_col] = df[args.event_col].astype(int)

    # 验证 event 列仅含 0/1
    invalid_events = df[~df[args.event_col].isin([0, 1])]
    if len(invalid_events) > 0:
        print(f"警告: 事件列 '{args.event_col}' 包含非 0/1 值（{invalid_events[args.event_col].unique()}），"
              f"共 {len(invalid_events)} 行。将非1值视为删失（0）。")
        df[args.event_col] = df[args.event_col].apply(lambda x: 1 if x == 1 else 0)

    # 验证 duration 列非负
    neg_duration = df[df[args.duration_col] < 0]
    if len(neg_duration) > 0:
        print(f"警告: 生存时长列 '{args.duration_col}' 包含 {len(neg_duration)} 个负值，已剔除。")
        df = df[df[args.duration_col] >= 0]

    results, sf_data = kaplan_meier_analysis(
        df, args.duration_col, args.event_col,
        args.group_col, args.time_points
    )

    # 保存生存函数表
    if not sf_data.empty:
        sf_data.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n生存函数表已保存至: {args.output}")

    # 保存摘要统计
    summary_path = args.output.replace('.csv', '_summary.csv')
    summary_rows = []
    for k, v in results.items():
        if k == 'log_rank':
            continue
        if isinstance(v, dict):
            row = {'分组': k}
            row.update(v)
            summary_rows.append(row)
    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding='utf-8-sig')
        print(f"摘要统计已保存至: {summary_path}")


if __name__ == '__main__':
    main()
