#!/usr/bin/env python3
"""
回归诊断脚本 - 残差分析 / 异方差 / 自相关 / Cook距离 / VIF

功能：
  - Breusch-Pagan 异方差检验
  - Durbin-Watson 自相关检验
  - Cook距离识别强影响点
  - 残差正态性检验
  - VIF 多重共线性检查
  - 输出诊断汇总报告

用法：
  python regression_diagnostics.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


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


def regression_diagnostics(df, target_col, feature_cols):
    """
    回归诊断全套检验。

    返回：
      diagnostics_df:   诊断摘要表
      influential_df:   强影响点表
      residuals_df:     残差数据
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.impute import SimpleImputer
    from scipy import stats
    import statsmodels.api as sm
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.stats.outliers_influence import variance_inflation_factor, OLSInfluence

    X = df[feature_cols].copy()
    y = df[target_col].copy()
    common_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X = X.loc[common_idx].reset_index(drop=True)
    y = y.loc[common_idx].reset_index(drop=True)

    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    # OLS 回归（statsmodels）
    X_const = sm.add_constant(X_imputed)
    ols_model = sm.OLS(y, X_const).fit()
    y_pred = ols_model.predict(X_const)
    residuals = y.values - y_pred

    print(f"\n{'='*70}")
    print(f"  回归诊断报告")
    print(f"{'='*70}")
    print(f"  样本量: {len(y)}, 特征数: {len(feature_cols)}")
    print(f"  R2 = {ols_model.rsquared:.4f}, Adj R2 = {ols_model.rsquared_adj:.4f}")

    diagnostics = []

    # 1. Breusch-Pagan 异方差检验
    try:
        bp_stat, bp_p, bp_f, bp_fp = het_breuschpagan(residuals, X_const)
        bp_result = "存在异方差" if bp_p < 0.05 else "方差齐性"
        diagnostics.append({
            "检验项目": "Breusch-Pagan 异方差检验",
            "统计量": round(bp_stat, 4),
            "P值": round(bp_p, 6),
            "诊断结果": bp_result,
            "建议": "考虑加权回归或变量变换" if bp_p < 0.05 else "无需处理"
        })
        print(f"\n  Breusch-Pagan 异方差检验: stat={bp_stat:.4f}, p={bp_p:.6f} -> {bp_result}")
    except Exception as e:
        print(f"  Breusch-Pagan 检验出错: {e}")

    # 2. Durbin-Watson 自相关检验
    try:
        dw_stat = durbin_watson(residuals)
        if dw_stat < 1.5:
            dw_result = "正自相关"
            dw_advice = "数据可能存在时序依赖，考虑加入滞后项"
        elif dw_stat > 2.5:
            dw_result = "负自相关"
            dw_advice = "检查数据排序是否合理"
        else:
            dw_result = "无显著自相关"
            dw_advice = "无需处理"
        diagnostics.append({
            "检验项目": "Durbin-Watson 自相关检验",
            "统计量": round(dw_stat, 4),
            "P值": None,
            "诊断结果": dw_result,
            "建议": dw_advice
        })
        print(f"  Durbin-Watson 自相关检验: DW={dw_stat:.4f} -> {dw_result}")
    except Exception as e:
        print(f"  Durbin-Watson 检验出错: {e}")

    # 3. 残差正态性检验
    try:
        if len(residuals) < 5000:
            norm_stat, norm_p = stats.shapiro(residuals)
            norm_test = "Shapiro-Wilk"
        else:
            norm_stat, norm_p = stats.normaltest(residuals)
            norm_test = "D'Agostino-Pearson"
        norm_result = "近似正态" if norm_p > 0.05 else "非正态"
        diagnostics.append({
            "检验项目": f"残差正态性（{norm_test}）",
            "统计量": round(norm_stat, 4),
            "P值": round(norm_p, 6),
            "诊断结果": norm_result,
            "建议": "无需处理" if norm_p > 0.05 else "考虑 Box-Cox 变换或稳健回归"
        })
        print(f"  残差正态性（{norm_test}）: stat={norm_stat:.4f}, p={norm_p:.6f} -> {norm_result}")
    except Exception as e:
        print(f"  残差正态性检验出错: {e}")

    # 4. VIF 多重共线性
    try:
        vif_vals = []
        for i in range(len(feature_cols)):
            vif = variance_inflation_factor(X_const.values, i + 1)  # +1 跳过截距
            vif_vals.append(round(vif, 2))

        max_vif = max(vif_vals)
        max_vif_feat = feature_cols[vif_vals.index(max_vif)]
        vif_result = "严重共线性" if max_vif >= 10 else ("中度共线" if max_vif >= 5 else "无共线性")
        diagnostics.append({
            "检验项目": "VIF 共线性检查",
            "统计量": max_vif,
            "P值": None,
            "诊断结果": f"{vif_result}（最大VIF={max_vif}, 特征={max_vif_feat}）",
            "建议": "考虑正则化或特征剔除" if max_vif >= 10 else "无需处理"
        })
        print(f"  VIF 共线性: 最大VIF={max_vif}（{max_vif_feat}）-> {vif_result}")
    except Exception as e:
        print(f"  VIF 计算出错: {e}")

    # 5. Cook距离
    influential_df = pd.DataFrame()
    if len(y) > 50000:
        print(f"  Cook距离: 样本量({len(y)})超过50000，OLSInfluence内存消耗过大，已跳过计算")
        diagnostics.append({
            "检验项目": "Cook距离",
            "统计量": np.nan,
            "P值": None,
            "诊断结果": f"样本量过大({len(y)})，已跳过",
            "建议": "可抽样后单独计算Cook距离"
        })
    else:
        try:
            influence = OLSInfluence(ols_model)
            cooks_d = influence.cooks_distance[0]
            threshold = 4.0 / len(y)

            influential_idx = np.where(cooks_d > threshold)[0]
            n_influential = len(influential_idx)

            diagnostics.append({
                "检验项目": f"Cook距离（阈值={threshold:.4f}）",
                "统计量": round(cooks_d.max(), 4),
                "P值": None,
                "诊断结果": f"发现 {n_influential} 个强影响点" if n_influential > 0 else "无强影响点",
                "建议": "审查强影响观测是否为异常数据" if n_influential > 0 else "无需处理"
            })
            print(f"  Cook距离: 最大={cooks_d.max():.4f}, "
                  f"强影响点（>{threshold:.4f}）: {n_influential} 个")

            if n_influential > 0:
                influential_df = pd.DataFrame({
                    "样本索引": influential_idx,
                    "Cook_D": cooks_d[influential_idx].round(4),
                    "实际值": y.iloc[influential_idx].values,
                    "预测值": y_pred[influential_idx].round(4),
                    "残差": residuals[influential_idx].round(4)
                }).sort_values("Cook_D", ascending=False)
        except Exception as e:
            print(f"  Cook距离计算出错: {e}")

    diagnostics_df = pd.DataFrame(diagnostics)
    print(f"\n{'='*70}")
    print(f"  诊断汇总")
    print(f"{'='*70}")
    print(diagnostics_df.to_string(index=False))

    # 残差数据
    residuals_df = pd.DataFrame({
        "实际值": y.values,
        "预测值": y_pred.round(4),
        "残差": residuals.round(4),
        "标准化残差": ((residuals - residuals.mean()) / residuals.std()).round(4)
    })

    return diagnostics_df, influential_df, residuals_df


def main():
    parser = argparse.ArgumentParser(
        description="回归诊断（异方差/自相关/Cook距离/VIF/正态性）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    diagnostics_df, influential_df, residuals_df = regression_diagnostics(
        df, args.target, args.features
    )

    # 保存结果
    diag_path = os.path.join(args.output_dir, "diagnostics_summary.csv")
    diagnostics_df.to_csv(diag_path, index=False, encoding='utf-8-sig')
    print(f"\n诊断汇总已保存至: {diag_path}")

    if not influential_df.empty:
        inf_path = os.path.join(args.output_dir, "influential_points.csv")
        influential_df.to_csv(inf_path, index=False, encoding='utf-8-sig')
        print(f"强影响点已保存至: {inf_path}")

    res_path = os.path.join(args.output_dir, "residuals.csv")
    residuals_df.to_csv(res_path, index=False, encoding='utf-8-sig')
    print(f"残差数据已保存至: {res_path}")


if __name__ == "__main__":
    main()
