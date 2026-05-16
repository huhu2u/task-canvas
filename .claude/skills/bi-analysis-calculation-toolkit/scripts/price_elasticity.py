#!/usr/bin/env python3
"""
价格弹性估计脚本

功能：
  - 对数-对数回归（ln(Q) ~ ln(P) + 控制变量）
  - 异方差稳健标准误（HC3）
  - Durbin-Watson检验自相关
  - 内生性警告提示（价格可能与需求同时决定）
  - 输出弹性系数、置信区间、弹性类型判定

用法：
  python price_elasticity.py <数据文件> \
    --price-col <价格列> --quantity-col <数量列> \
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


def price_elasticity(df, price_col, quantity_col, control_cols=None, alpha=0.05):
    """
    价格弹性估计。

    参数：
      df:            DataFrame
      price_col:     价格列
      quantity_col:  数量列
      control_cols:  控制变量列名列表
      alpha:         显著性水平

    返回：
      dict — 弹性估计结果
    """
    import statsmodels.api as sm
    from statsmodels.stats.stattools import durbin_watson

    df = df.copy()

    # 过滤非正值（对数变换要求正值）
    mask = (df[price_col] > 0) & (df[quantity_col] > 0)
    invalid_count = (~mask).sum()
    if invalid_count > 0:
        print(f"  警告：{invalid_count} 行数据因价格或数量非正值被剔除")
    df = df[mask].copy()

    if len(df) < 10:
        print("  错误：有效数据不足（< 10 行），无法进行回归")
        sys.exit(1)

    # 对数变换
    df['ln_P'] = np.log(df[price_col])
    df['ln_Q'] = np.log(df[quantity_col])

    print(f"\n{'='*70}")
    print(f"  价格弹性估计（对数-对数回归）")
    print(f"{'='*70}")
    print(f"  价格列: {price_col}")
    print(f"  数量列: {quantity_col}")
    print(f"  有效样本: {len(df)}")
    print(f"  价格范围: [{df[price_col].min():.2f}, {df[price_col].max():.2f}]")
    print(f"  数量范围: [{df[quantity_col].min():.2f}, {df[quantity_col].max():.2f}]")

    # 构建回归
    X_cols = ['ln_P']
    if control_cols:
        valid_controls = [c for c in control_cols if c in df.columns]
        # 对数变换控制变量（仅对正值连续变量）
        for c in valid_controls:
            if df[c].dtype in ['float64', 'int64'] and (df[c] > 0).all():
                df[f'ln_{c}'] = np.log(df[c])
                X_cols.append(f'ln_{c}')
            else:
                X_cols.append(c)
        if len(valid_controls) < len(control_cols):
            missing = set(control_cols) - set(valid_controls)
            print(f"  警告：以下控制变量不存在: {missing}")

    X = sm.add_constant(df[X_cols].astype(float))
    y = df['ln_Q'].astype(float)

    # 删除缺失值
    valid_mask = X.notna().all(axis=1) & y.notna()
    X = X[valid_mask]
    y = y[valid_mask]

    model = sm.OLS(y, X).fit(cov_type='HC3')

    elasticity = model.params['ln_P']
    se = model.bse['ln_P']
    p_value = model.pvalues['ln_P']
    ci = model.conf_int(alpha=alpha).loc['ln_P']

    # Durbin-Watson 检验
    dw_stat = durbin_watson(model.resid)

    print(f"\n  -- 回归结果 --")
    print(f"  弹性系数 (β): {elasticity:.4f}")
    print(f"  标准误 (HC3): {se:.4f}")
    print(f"  P 值: {p_value:.6f}")
    print(f"  {int((1-alpha)*100)}% 置信区间: [{ci[0]:.4f}, {ci[1]:.4f}]")
    print(f"  R²: {model.rsquared:.4f}")
    print(f"  调整 R²: {model.rsquared_adj:.4f}")
    print(f"  Durbin-Watson: {dw_stat:.4f}")

    # 弹性类型判定
    abs_e = abs(elasticity)
    if abs_e > 1:
        elasticity_type = "富有弹性"
    elif abs_e == 1:
        elasticity_type = "单位弹性"
    else:
        elasticity_type = "缺乏弹性"

    print(f"\n  -- 弹性解读 --")
    print(f"  弹性类型: {elasticity_type}（|ε| = {abs_e:.4f}）")
    print(f"  含义: 价格每上升 1%，需求量变化约 {elasticity:.2f}%")

    # 内生性警告
    print(f"\n  -- 诊断检验 --")
    print(f"  内生性警告: 价格可能与需求同时决定（内生性问题），")
    print(f"  建议使用工具变量法（IV/2SLS）进行稳健性检验。")
    print(f"  当前结果假设价格为外生变量，请谨慎解读。")

    # Durbin-Watson 解读
    if dw_stat < 1.5:
        dw_conclusion = "存在正自相关，估计可能偏误"
        print(f"  Durbin-Watson = {dw_stat:.4f}：{dw_conclusion}")
    elif dw_stat > 2.5:
        dw_conclusion = "存在负自相关，估计可能偏误"
        print(f"  Durbin-Watson = {dw_stat:.4f}：{dw_conclusion}")
    else:
        dw_conclusion = "无显著自相关"
        print(f"  Durbin-Watson = {dw_stat:.4f}：{dw_conclusion}")

    # 弹性为正的异常警告
    if elasticity > 0:
        print(f"\n  异常警告: 价格弹性为正（{elasticity:.4f}），")
        print(f"  即价格上升需求也上升，这不符合一般经济学规律。")
        print(f"  可能原因：(1) 吉芬商品/韦伯伦商品 (2) 遗漏变量偏误 "
              f"(3) 逆向因果 (4) 数据异常")

    is_significant = p_value < alpha

    if is_significant:
        print(f"\n  结论: 价格弹性统计显著（p < {alpha}），{elasticity_type}，"
              f"ε = {elasticity:.4f}")
    else:
        print(f"\n  结论: 价格弹性不显著（p >= {alpha}），无法确定价格对需求的影响")

    result = {
        "弹性系数": round(elasticity, 4),
        "标准误_HC3": round(se, 4),
        "P值": round(p_value, 6),
        "CI下界": round(ci[0], 4),
        "CI上界": round(ci[1], 4),
        "弹性类型": elasticity_type,
        "R_squared": round(model.rsquared, 4),
        "Adj_R_squared": round(model.rsquared_adj, 4),
        "Durbin_Watson": round(dw_stat, 4),
        "DW结论": dw_conclusion,
        "弹性为正异常": "是" if elasticity > 0 else "否",
        "显著性": "显著" if is_significant else "不显著",
        "样本量": len(y)
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="价格弹性估计（对数-对数回归 + HC3 稳健标准误）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--price-col", required=True, help="价格列名")
    parser.add_argument("--quantity-col", required=True, help="数量列名")
    parser.add_argument("--control-cols", nargs="*", default=None, help="控制变量列名")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    required_cols = [args.price_col, args.quantity_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result = price_elasticity(df, args.price_col, args.quantity_col,
                              args.control_cols, args.alpha)

    result_df = pd.DataFrame([result])
    out_path = os.path.join(args.output_dir, "price_elasticity.csv")
    result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {out_path}")


if __name__ == "__main__":
    main()
