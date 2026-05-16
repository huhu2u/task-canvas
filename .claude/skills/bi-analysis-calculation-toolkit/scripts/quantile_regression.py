#!/usr/bin/env python3
"""
分位数回归脚本 - P10/P50/P90 预测区间

功能：
  - 训练多个分位数模型，输出预测区间
  - 计算区间覆盖率（实际值落在区间内的比例）
  - 支持自定义分位点

用法：
  python quantile_regression.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--quantiles 0.1 0.5 0.9] [--output-dir <输出目录>]
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


def quantile_regression(df, target_col, feature_cols, quantiles=None, test_size=0.2):
    """
    分位数回归预测区间。

    返回：
      predictions_df: 预测结果表
      coverage_info:  区间覆盖率信息 dict
    """
    from sklearn.model_selection import train_test_split
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import mean_absolute_error, r2_score

    if quantiles is None:
        quantiles = [0.1, 0.5, 0.9]

    X = df[feature_cols].copy()
    y = df[target_col].copy()
    common_idx = X.dropna(how="all").index.intersection(y.dropna().index)
    X = X.loc[common_idx]
    y = y.loc[common_idx]

    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y.values, test_size=test_size, random_state=42
    )

    print(f"\n数据: 训练集 {len(X_train)} 条，测试集 {len(X_test)} 条")
    print(f"分位点: {quantiles}")

    # 尝试 LightGBM 分位数回归
    use_lgb = False
    try:
        import lightgbm as lgb
        use_lgb = True
    except ImportError:
        pass

    # 尝试 sklearn GradientBoosting 分位数回归
    use_gb = False
    if not use_lgb:
        try:
            from sklearn.ensemble import GradientBoostingRegressor
            use_gb = True
        except ImportError:
            pass

    if not use_lgb and not use_gb:
        print("错误：需要 lightgbm 或 sklearn 的 GradientBoostingRegressor")
        sys.exit(1)

    quantile_preds = {}

    for q in quantiles:
        if use_lgb:
            model = lgb.LGBMRegressor(
                objective="quantile", alpha=q,
                n_estimators=200, learning_rate=0.05,
                max_depth=8,
                random_state=42, verbose=-1
            )
        else:
            model = GradientBoostingRegressor(
                loss="quantile", alpha=q,
                n_estimators=200, learning_rate=0.05,
                random_state=42
            )

        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        quantile_preds[q] = preds

        mae = mean_absolute_error(y_test, preds)
        print(f"  P{int(q*100)}: MAE={mae:.4f}")

    # 构建预测结果表
    pred_dict = {"实际值": y_test}
    for q in quantiles:
        pred_dict[f"P{int(q*100)}"] = quantile_preds[q].round(4)

    predictions_df = pd.DataFrame(pred_dict)

    # 验证单调性：P_high >= P_low
    q_sorted = sorted(quantiles)
    monotonic_violations = 0
    if len(q_sorted) >= 2:
        for i in range(len(q_sorted) - 1):
            low_q = q_sorted[i]
            high_q = q_sorted[i + 1]
            violations = (quantile_preds[high_q] < quantile_preds[low_q]).sum()
            monotonic_violations += violations
            if violations > 0:
                print(f"  警告: P{int(high_q*100)} < P{int(low_q*100)} 的样本数: "
                      f"{violations}/{len(y_test)}")

    if monotonic_violations == 0:
        print("  分位数单调性验证通过")

    # 区间覆盖率
    coverage_info = {}
    if len(q_sorted) >= 2:
        low_q = q_sorted[0]
        high_q = q_sorted[-1]
        in_interval = ((y_test >= quantile_preds[low_q]) &
                       (y_test <= quantile_preds[high_q]))
        coverage = in_interval.mean() * 100
        expected_coverage = (high_q - low_q) * 100
        coverage_info = {
            "区间": f"P{int(low_q*100)}-P{int(high_q*100)}",
            "期望覆盖率(%)": expected_coverage,
            "实际覆盖率(%)": round(coverage, 2),
            "样本数": len(y_test)
        }

        print(f"\n{'='*70}")
        print(f"  区间覆盖率分析")
        print(f"{'='*70}")
        print(f"  P{int(low_q*100)}-P{int(high_q*100)} 区间:")
        print(f"  期望覆盖率: {expected_coverage:.0f}%")
        print(f"  实际覆盖率: {coverage:.2f}%")

        if abs(coverage - expected_coverage) > 10:
            print(f"  警告: 实际覆盖率与期望偏差 > 10%，模型校准可能需要调整")

    print(f"\n预测区间（前10行）：")
    print(predictions_df.head(10).to_string(index=False))

    return predictions_df, coverage_info


def main():
    parser = argparse.ArgumentParser(
        description="分位数回归（P10/P50/P90 预测区间）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.1, 0.5, 0.9],
                        help="分位点列表，默认 0.1 0.5 0.9")
    parser.add_argument("--test-size", type=float, default=0.2, help="测试集比例")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    predictions_df, coverage_info = quantile_regression(
        df, args.target, args.features, args.quantiles, args.test_size
    )

    out_path = os.path.join(args.output_dir, "quantile_predictions.csv")
    predictions_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n预测区间已保存至: {out_path}")

    if coverage_info:
        cov_path = os.path.join(args.output_dir, "coverage_analysis.csv")
        pd.DataFrame([coverage_info]).to_csv(cov_path, index=False, encoding='utf-8-sig')
        print(f"覆盖率分析已保存至: {cov_path}")


if __name__ == "__main__":
    main()
