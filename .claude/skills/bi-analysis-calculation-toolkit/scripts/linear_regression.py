#!/usr/bin/env python3
"""
线性/正则化回归脚本 - OLS / Ridge / Lasso / ElasticNet + Lasso 路径

功能：
  - 训练 OLS / Ridge / Lasso / ElasticNet 四种模型
  - MAE / RMSE / MAPE / R2 横向对比
  - 输出最优模型特征系数
  - Lasso 路径分析（不同正则化强度下的系数变化）

用法：
  python linear_regression.py <数据文件> \
    --target <目标变量> --features <特征1> <特征2> ... \
    [--test-size 0.2] [--output-dir <输出目录>]
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


def linear_regression(df, target_col, feature_cols, test_size=0.2):
    """
    线性回归建模与评估。

    返回：
      comparison_df: 模型对比表
      coef_df:       最优模型系数
      lasso_path_df: Lasso 路径数据
    """
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
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

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"\n数据: 训练集 {len(X_train)} 条，测试集 {len(X_test)} 条")
    print(f"目标变量 {target_col}: 均值={y.mean():.4f}, "
          f"范围=[{y.min():.2f}, {y.max():.2f}]")

    models = {
        "OLS": LinearRegression(),
        "Ridge(L2)": Ridge(alpha=1.0),
        "Lasso(L1)": Lasso(alpha=0.1, max_iter=10000),
        "ElasticNet": ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=10000)
    }

    results = []
    best_model_info = None
    best_r2 = -np.inf

    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mape = compute_mape(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        results.append({
            "模型": name,
            "MAE": round(mae, 4),
            "RMSE": round(rmse, 4),
            "MAPE(%)": round(mape, 2) if not np.isnan(mape) else None,
            "R2": round(r2, 4)
        })

        if r2 > best_r2:
            best_r2 = r2
            best_model_info = (name, model)

    comparison_df = pd.DataFrame(results)
    print(f"\n{'='*70}")
    print(f"  线性模型对比")
    print(f"{'='*70}")
    print(comparison_df.to_string(index=False))

    if best_r2 < 0.3:
        print(f"\n警告：最优模型 R2 = {best_r2:.4f} < 0.3，模型解释力弱")

    # 最优模型系数
    coef_df = pd.DataFrame()
    if best_model_info is not None:
        name, model = best_model_info
        if hasattr(model, "coef_"):
            coef_df = pd.DataFrame({
                "特征": feature_cols,
                "系数": model.coef_,
                "绝对值": np.abs(model.coef_)
            }).sort_values("绝对值", ascending=False)
            coef_df = coef_df.drop(columns=["绝对值"])

            print(f"\n{name} 特征系数（按重要性排序）：")
            print(coef_df.round(6).to_string(index=False))

    # Lasso 路径
    lasso_path_df = pd.DataFrame()
    try:
        from sklearn.linear_model import lasso_path as sklearn_lasso_path
        alphas, coefs, _ = sklearn_lasso_path(X_train_scaled, y_train, n_alphas=100)
        path_rows = []
        for i, alpha_val in enumerate(alphas):
            for j, feat in enumerate(feature_cols):
                path_rows.append({
                    "alpha": round(alpha_val, 6),
                    "log_alpha": round(np.log10(alpha_val), 4),
                    "特征": feat,
                    "系数": round(coefs[j, i], 6)
                })
        lasso_path_df = pd.DataFrame(path_rows)
        print(f"\nLasso 路径已计算（{len(alphas)} 个 alpha 值）")

        # 特征选择建议
        last_coefs = coefs[:, -1]
        selected = [f for f, c in zip(feature_cols, last_coefs) if abs(c) > 1e-6]
        dropped = [f for f, c in zip(feature_cols, last_coefs) if abs(c) <= 1e-6]
        if dropped:
            print(f"  Lasso 建议剔除特征（系数=0）: {dropped}")
            print(f"  Lasso 保留特征: {selected}")
    except Exception as e:
        print(f"Lasso 路径计算出错: {e}")

    return comparison_df, coef_df, lasso_path_df


def main():
    parser = argparse.ArgumentParser(
        description="线性/正则化回归（OLS/Ridge/Lasso/ElasticNet + Lasso路径）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--target", required=True, help="目标变量列名")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
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

    comparison_df, coef_df, lasso_path_df = linear_regression(
        df, args.target, args.features, args.test_size
    )

    # 保存结果
    comp_path = os.path.join(args.output_dir, "linear_model_comparison.csv")
    comparison_df.to_csv(comp_path, index=False, encoding='utf-8-sig')
    print(f"\n模型对比表已保存至: {comp_path}")

    if not coef_df.empty:
        coef_path = os.path.join(args.output_dir, "linear_coefficients.csv")
        coef_df.to_csv(coef_path, index=False, encoding='utf-8-sig')
        print(f"特征系数已保存至: {coef_path}")

    if not lasso_path_df.empty:
        lp_path = os.path.join(args.output_dir, "lasso_path.csv")
        lasso_path_df.to_csv(lp_path, index=False, encoding='utf-8-sig')
        print(f"Lasso 路径已保存至: {lp_path}")


if __name__ == "__main__":
    main()
