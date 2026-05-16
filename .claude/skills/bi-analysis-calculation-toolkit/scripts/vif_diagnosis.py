#!/usr/bin/env python3
"""
VIF 多重共线性诊断脚本

功能：
  - 计算所有特征的方差膨胀因子（VIF）
  - 诊断分级：VIF < 5 正常，5-10 中度，>= 10 严重
  - 自动迭代剔除模式：反复移除 VIF 最高的特征直至所有 VIF < 阈值
  - 输出推荐保留的特征列表

用法：
  python vif_diagnosis.py <数据文件> \
    --features <特征1> <特征2> ... \
    [--threshold 10] [--auto-drop] [--output-dir <输出目录>]
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np


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


def compute_vif(df, feature_cols):
    """
    计算 VIF，返回 DataFrame。

    参数：
      df:           DataFrame
      feature_cols: 特征列名列表

    返回：
      DataFrame — 各特征的 VIF 值和诊断等级
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from sklearn.impute import SimpleImputer

    # 当 n_rows>100000 时抽样50000行计算VIF
    if len(df) > 100000:
        print(f"[信息] 数据行数({len(df)})超过100000，抽样50000行计算VIF")
        df = df.sample(n=50000, random_state=42)

    X = df[feature_cols].copy()
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_cols)

    # 添加截距项
    X_with_const = X_imputed.copy()
    X_with_const.insert(0, "_截距_", 1)

    vif_data = pd.DataFrame({
        "特征": feature_cols,
        "VIF": [variance_inflation_factor(X_with_const.values, i + 1)
                for i in range(len(feature_cols))]
    })
    vif_data["VIF"] = vif_data["VIF"].round(2)
    vif_data["诊断"] = vif_data["VIF"].apply(
        lambda x: "正常" if x < 5 else ("中度共线" if x < 10 else "严重共线性")
    )
    vif_data = vif_data.sort_values("VIF", ascending=False)

    return vif_data


def auto_drop_vif(df, feature_cols, threshold=10, max_iterations=50):
    """
    自动迭代剔除高 VIF 特征，直至所有 VIF < 阈值。

    参数：
      df:              DataFrame
      feature_cols:    初始特征列名列表
      threshold:       VIF 阈值
      max_iterations:  最大迭代次数（默认50，防止无限循环）

    返回：
      remaining_features: 保留的特征列表
      drop_log:           剔除日志 DataFrame
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from sklearn.impute import SimpleImputer

    # 当 n_rows>100000 时抽样50000行计算VIF
    if len(df) > 100000:
        print(f"[信息] 数据行数({len(df)})超过100000，抽样50000行用于自动剔除VIF计算")
        df = df.sample(n=50000, random_state=42)

    remaining = list(feature_cols)
    drop_log = []
    iteration = 0

    while True:
        if len(remaining) < 2:
            break

        if iteration >= max_iterations:
            print(f"[警告] 已达到最大迭代次数({max_iterations})，停止迭代剔除")
            break

        X = df[remaining].copy()
        imputer = SimpleImputer(strategy="median")
        X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=remaining)
        X_with_const = X_imputed.copy()
        X_with_const.insert(0, "_截距_", 1)

        vifs = [variance_inflation_factor(X_with_const.values, i + 1)
                for i in range(len(remaining))]
        max_vif = max(vifs)
        max_idx = vifs.index(max_vif)

        if max_vif < threshold:
            break

        dropped_feat = remaining[max_idx]
        drop_log.append({
            "迭代轮次": iteration + 1,
            "剔除特征": dropped_feat,
            "VIF值": round(max_vif, 2),
            "剩余特征数": len(remaining) - 1
        })
        print(f"  迭代 {iteration + 1}: 剔除 '{dropped_feat}' (VIF={max_vif:.2f})，"
              f"剩余 {len(remaining) - 1} 个特征")
        remaining.remove(dropped_feat)
        iteration += 1

    return remaining, pd.DataFrame(drop_log) if drop_log else pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(
        description="VIF 多重共线性诊断（支持自动迭代剔除）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--features", required=True, nargs="+", help="特征列名列表")
    parser.add_argument("--threshold", type=float, default=10, help="VIF 阈值，默认 10")
    parser.add_argument("--auto-drop", action="store_true",
                        help="开启自动迭代剔除高 VIF 特征")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    missing = [c for c in args.features if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # 完整 VIF 诊断
    vif_df = compute_vif(df, args.features)
    severe = vif_df[vif_df["VIF"] >= args.threshold]

    print(f"\n{'='*70}")
    print(f"  VIF 多重共线性诊断（阈值={args.threshold}）")
    print(f"{'='*70}")
    print(vif_df.to_string(index=False))

    if len(severe) > 0:
        print(f"\n发现 {len(severe)} 个严重多重共线性变量（VIF >= {args.threshold}）：")
        print(severe[["特征", "VIF"]].to_string(index=False))
        print("建议：考虑删除或合并高共线性变量，或使用 Ridge/Lasso 正则化")
    else:
        print(f"\n所有特征 VIF < {args.threshold}，无严重多重共线性")

    vif_path = os.path.join(args.output_dir, "vif_diagnosis.csv")
    vif_df.to_csv(vif_path, index=False, encoding='utf-8-sig')
    print(f"\nVIF 诊断结果已保存至: {vif_path}")

    # 自动迭代剔除
    if args.auto_drop:
        print(f"\n{'='*70}")
        print(f"  自动迭代剔除（VIF 阈值={args.threshold}）")
        print(f"{'='*70}")

        remaining, drop_log = auto_drop_vif(df, args.features, args.threshold)

        print(f"\n迭代完成，保留 {len(remaining)} 个特征：")
        print(f"  {remaining}")

        # 保存迭代结果
        selection_df = pd.DataFrame({"保留特征": remaining})
        if not drop_log.empty:
            # 合并保留特征和剔除日志
            sel_path = os.path.join(args.output_dir, "vif_auto_selection.csv")
            selection_df.to_csv(sel_path, index=False, encoding='utf-8-sig')
            print(f"自动选择结果已保存至: {sel_path}")

            log_path = os.path.join(args.output_dir, "vif_drop_log.csv")
            drop_log.to_csv(log_path, index=False, encoding='utf-8-sig')
            print(f"剔除日志已保存至: {log_path}")
        else:
            print("无需剔除任何特征")


if __name__ == "__main__":
    main()
