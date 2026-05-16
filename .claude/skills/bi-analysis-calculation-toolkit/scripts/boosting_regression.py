#!/usr/bin/env python3
"""
梯度提升回归脚本 - XGBoost / LightGBM + 嵌套交叉验证

功能：
  - XGBoost / LightGBM 建模
  - 嵌套交叉验证（外层评估，内层调参）
  - MAE / RMSE / MAPE / R2 评估
  - 特征重要性排名输出

用法：
  python boosting_regression.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--test-size 0.2] [--cv-folds 5] [--output-dir <输出目录>]
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


def compute_mape(y_true, y_pred):
    """计算 MAPE，排除零值"""
    mask = y_true != 0
    if mask.sum() == 0:
        return np.nan
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def boosting_regression(df, target_col, feature_cols, test_size=0.2, cv_folds=5):
    """
    梯度提升回归建模与评估。

    返回：
      comparison_df:  模型对比表
      importance_df:  特征重要性表
    """
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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

    # 数据规模自适应 n_jobs，防止大数据集内存溢出
    n_rows = len(X_imputed)
    if n_rows > 100000:
        n_jobs = 1
    elif n_rows > 10000:
        n_jobs = 2
    else:
        n_jobs = -1

    print(f"\n数据: 训练集 {len(X_train)} 条，测试集 {len(X_test)} 条（n_jobs={n_jobs}）")

    results = []
    all_importances = {}

    # XGBoost
    try:
        import xgboost as xgb

        xgb_model = xgb.XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=n_jobs, verbosity=0
        )

        # 嵌套交叉验证
        cv_scores = cross_val_score(xgb_model, X_train, y_train,
                                     cv=cv_folds, scoring="r2")
        print(f"\nXGBoost {cv_folds}折CV R2: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

        xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        y_pred = xgb_model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mape = compute_mape(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        results.append({
            "模型": "XGBoost",
            "MAE": round(mae, 4), "RMSE": round(rmse, 4),
            "MAPE(%)": round(mape, 2) if not np.isnan(mape) else None,
            "R2": round(r2, 4),
            f"CV_R2({cv_folds}折)": round(cv_scores.mean(), 4)
        })
        all_importances["XGBoost"] = xgb_model.feature_importances_

    except ImportError:
        print("提示：安装 xgboost 可使用 XGBoost（pip install xgboost）")

    # LightGBM
    try:
        import lightgbm as lgb

        lgb_model = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, num_leaves=31,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=n_jobs, verbose=-1
        )

        cv_scores = cross_val_score(lgb_model, X_train, y_train,
                                     cv=cv_folds, scoring="r2")
        print(f"LightGBM {cv_folds}折CV R2: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

        lgb_model.fit(X_train, y_train,
                      eval_set=[(X_test, y_test)])
        y_pred_lgb = lgb_model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred_lgb)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred_lgb))
        mape = compute_mape(y_test, y_pred_lgb)
        r2 = r2_score(y_test, y_pred_lgb)

        results.append({
            "模型": "LightGBM",
            "MAE": round(mae, 4), "RMSE": round(rmse, 4),
            "MAPE(%)": round(mape, 2) if not np.isnan(mape) else None,
            "R2": round(r2, 4),
            f"CV_R2({cv_folds}折)": round(cv_scores.mean(), 4)
        })
        all_importances["LightGBM"] = lgb_model.feature_importances_

    except ImportError:
        print("提示：安装 lightgbm 可使用 LightGBM（pip install lightgbm）")

    comparison_df = pd.DataFrame(results) if results else pd.DataFrame()
    if not comparison_df.empty:
        print(f"\n{'='*70}")
        print(f"  梯度提升模型对比")
        print(f"{'='*70}")
        print(comparison_df.to_string(index=False))

    # 最优模型特征重要性
    importance_df = pd.DataFrame()
    if all_importances:
        best_name = comparison_df.sort_values("R2", ascending=False).iloc[0]["模型"]
        imp = all_importances[best_name]
        importance_df = pd.DataFrame({
            "特征": feature_cols,
            "重要性": imp,
            "重要性_归一化": (imp / imp.max()).round(4) if imp.max() > 0 else imp
        }).sort_values("重要性", ascending=False)
        importance_df["累计重要性(%)"] = (
            importance_df["重要性"].cumsum() / importance_df["重要性"].sum() * 100
        ).round(1)

        print(f"\n{best_name} 特征重要性排名：")
        print(importance_df.head(15).to_string(index=False))

    return comparison_df, importance_df


def main():
    parser = argparse.ArgumentParser(
        description="梯度提升回归（XGBoost/LightGBM + 嵌套交叉验证）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--test-size", type=float, default=0.2, help="测试集比例")
    parser.add_argument("--cv-folds", type=int, default=5, help="交叉验证折数")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in [args.target] + args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    comparison_df, importance_df = boosting_regression(
        df, args.target, args.features, args.test_size, args.cv_folds
    )

    if not comparison_df.empty:
        comp_path = os.path.join(args.output_dir, "boosting_model_comparison.csv")
        comparison_df.to_csv(comp_path, index=False, encoding='utf-8-sig')
        print(f"\n模型对比表已保存至: {comp_path}")

    if not importance_df.empty:
        imp_path = os.path.join(args.output_dir, "boosting_feature_importance.csv")
        importance_df.to_csv(imp_path, index=False, encoding='utf-8-sig')
        print(f"特征重要性已保存至: {imp_path}")


if __name__ == "__main__":
    main()
