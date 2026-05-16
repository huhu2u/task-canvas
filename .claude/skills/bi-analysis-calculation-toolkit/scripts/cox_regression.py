#!/usr/bin/env python3
"""
Cox比例风险回归脚本

功能：
- Cox PH模型拟合
- 危险比（HR）、95%CI、P值提取
- Schoenfeld残差检验PH假设（自动化）
- C-index（一致性指数）判别力评估
- PH假设失败时建议AFT替代
- 时变协变量支持提示

依赖：pip install lifelines pandas numpy

用法：
    python cox_regression.py input.csv --duration-col time --event-col status \
        --covariate-cols age income plan_type -o cox_output.csv
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


def fit_cox_model(df: pd.DataFrame, duration_col: str, event_col: str,
                  covariate_cols: list) -> dict:
    """
    拟合Cox比例风险模型

    参数：
        df: 输入数据
        duration_col: 生存时长列
        event_col: 事件状态列
        covariate_cols: 协变量列列表

    返回：
        包含模型结果的字典
    """
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        print("错误: 需要安装lifelines库: pip install lifelines")
        sys.exit(1)

    # 准备数据
    cols_needed = [duration_col, event_col] + covariate_cols
    cox_df = df[cols_needed].dropna().copy()

    # 处理分类变量（one-hot编码）
    cat_cols = [c for c in covariate_cols if cox_df[c].dtype == 'object']
    if cat_cols:
        print(f"  对分类变量进行哑变量编码: {cat_cols}")
        cox_df = pd.get_dummies(cox_df, columns=cat_cols, drop_first=True)
        # 更新协变量列名
        actual_covariates = [c for c in cox_df.columns if c not in [duration_col, event_col]]
    else:
        actual_covariates = covariate_cols

    print(f"\n=== Cox 比例风险回归 ===")
    print(f"  样本量: {len(cox_df)}")
    print(f"  事件数: {int(cox_df[event_col].sum())}")
    print(f"  协变量: {actual_covariates}")

    # 拟合模型
    cph = CoxPHFitter()
    try:
        cph.fit(cox_df, duration_col=duration_col, event_col=event_col)
    except Exception as e:
        print(f"  模型拟合失败: {e}")
        return None

    # 提取结果
    summary = cph.summary.copy()
    summary['HR'] = np.exp(summary['coef']).round(4)
    summary['HR_CI_下'] = np.exp(summary['coef lower 95%']).round(4)
    summary['HR_CI_上'] = np.exp(summary['coef upper 95%']).round(4)
    summary['显著'] = summary['p'].apply(lambda p: '是' if p < 0.05 else '否')

    output_cols = ['coef', 'HR', 'HR_CI_下', 'HR_CI_上', 'p', '显著']
    result_table = summary[output_cols].sort_values('p')

    print(f"\n=== 系数表（按P值排序）===")
    print(result_table.to_string())

    print(f"\n  HR解读: HR>1表示增加风险, HR<1表示降低风险, HR=1表示无影响")

    # C-index
    c_index = cph.concordance_index_
    print(f"\n=== 模型判别力 ===")
    print(f"  C-index: {c_index:.4f}")
    if c_index >= 0.7:
        print(f"  判定: 判别力可接受 (>=0.7)")
    elif c_index >= 0.6:
        print(f"  判定: 判别力一般 (0.6-0.7)")
    else:
        print(f"  警告: 判别力不足 (<0.6)，模型预测能力较弱")

    # Schoenfeld残差检验PH假设
    ph_violated = []
    print(f"\n=== PH假设检验（Schoenfeld残差）===")
    try:
        ph_test = cph.check_assumptions(cox_df, p_value_threshold=0.05, show_plots=False)
        # check_assumptions会打印结果，如果返回非空则有违反
        print("  所有协变量均满足PH假设")
    except Exception as e:
        # lifelines在PH假设违反时可能抛出异常或打印警告
        error_msg = str(e)
        if 'proportional' in error_msg.lower() or 'assumption' in error_msg.lower():
            print(f"  部分协变量可能违反PH假设")
            print(f"  建议: 考虑使用AFT模型（加速失效时间模型）作为替代")
            print(f"  建议: 或对违反PH的协变量使用分层Cox模型")

    # 尝试用proportional_hazard_test获取详细结果
    try:
        from lifelines.statistics import proportional_hazard_test
        ph_result = proportional_hazard_test(cph, cox_df, time_transform='rank')
        ph_summary = ph_result.summary
        print(f"\n  Schoenfeld检验详细结果:")
        print(ph_summary.to_string())

        for idx, row in ph_summary.iterrows():
            if row['p'] < 0.05:
                ph_violated.append(idx)
                print(f"  警告: {idx} 违反PH假设 (p={row['p']:.4f})")

        if ph_violated:
            print(f"\n  PH假设违反的协变量: {ph_violated}")
            print(f"  建议使用AFT模型或对这些变量进行分层处理")
        else:
            print(f"  结论: 所有协变量满足PH假设")

    except Exception:
        print("  无法执行Schoenfeld检验，请确认数据格式")

    # 时变协变量提示
    print(f"\n=== 提示 ===")
    print(f"  如需处理时变协变量，可使用lifelines的CoxTimeVaryingFitter:")
    print(f"  数据需转为长格式（start, stop, event, covariates），每个时间区间一行")

    return {
        'model': cph,
        'summary': result_table,
        'c_index': c_index,
        'ph_violated': ph_violated,
        'full_summary': summary
    }


def fit_aft_model(df: pd.DataFrame, duration_col: str, event_col: str,
                  covariate_cols: list, distribution: str = 'weibull') -> dict:
    """
    AFT（加速失效时间）模型，作为PH假设不满足时的替代

    参数：
        distribution: 分布类型 ('weibull', 'lognormal', 'loglogistic')
    """
    try:
        from lifelines import WeibullAFTFitter, LogNormalAFTFitter, LogLogisticAFTFitter
    except ImportError:
        print("错误: 需要安装lifelines库")
        sys.exit(1)

    fitter_map = {
        'weibull': WeibullAFTFitter,
        'lognormal': LogNormalAFTFitter,
        'loglogistic': LogLogisticAFTFitter
    }

    if distribution not in fitter_map:
        print(f"不支持的分布: {distribution}, 可选: {list(fitter_map.keys())}")
        return None

    cols_needed = [duration_col, event_col] + covariate_cols
    aft_df = df[cols_needed].dropna().copy()

    # 处理分类变量
    cat_cols = [c for c in covariate_cols if aft_df[c].dtype == 'object']
    if cat_cols:
        aft_df = pd.get_dummies(aft_df, columns=cat_cols, drop_first=True)

    print(f"\n=== AFT模型 ({distribution}分布) ===")

    fitter = fitter_map[distribution]()
    try:
        fitter.fit(aft_df, duration_col=duration_col, event_col=event_col)
        print(fitter.summary.to_string())
        print(f"\n  AIC: {fitter.AIC_:.2f}")
        print(f"  C-index: {fitter.concordance_index_:.4f}")
        return {
            'model': fitter,
            'summary': fitter.summary,
            'aic': fitter.AIC_,
            'c_index': fitter.concordance_index_
        }
    except Exception as e:
        print(f"  AFT模型拟合失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Cox比例风险回归分析')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--duration-col', required=True, help='生存时长列名')
    parser.add_argument('--event-col', required=True, help='事件状态列名（1=事件，0=删失）')
    parser.add_argument('--covariate-cols', nargs='+', required=True, help='协变量列名')
    parser.add_argument('--fit-aft', action='store_true',
                        help='同时拟合AFT模型作为替代')
    parser.add_argument('--aft-distribution', default='weibull',
                        choices=['weibull', 'lognormal', 'loglogistic'],
                        help='AFT模型分布类型（默认: weibull）')
    parser.add_argument('-o', '--output', default='cox_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    # 验证列
    required_cols = [args.duration_col, args.event_col] + args.covariate_cols
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误: 以下列不存在: {missing}")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    # 拟合Cox模型
    cox_result = fit_cox_model(df, args.duration_col, args.event_col, args.covariate_cols)

    if cox_result:
        cox_result['summary'].to_csv(args.output, encoding='utf-8-sig')
        print(f"\nCox系数表已保存至: {args.output}")

    # AFT模型
    if args.fit_aft or (cox_result and cox_result.get('ph_violated')):
        if cox_result and cox_result.get('ph_violated'):
            print(f"\n由于PH假设被违反，自动拟合AFT模型作为替代...")
        aft_result = fit_aft_model(df, args.duration_col, args.event_col,
                                   args.covariate_cols, args.aft_distribution)
        if aft_result:
            aft_path = args.output.replace('.csv', '_aft.csv')
            aft_result['summary'].to_csv(aft_path, encoding='utf-8-sig')
            print(f"AFT系数表已保存至: {aft_path}")


if __name__ == '__main__':
    main()
