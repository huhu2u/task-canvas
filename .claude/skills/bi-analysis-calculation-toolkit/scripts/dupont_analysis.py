#!/usr/bin/env python3
"""
杜邦分析脚本（LMDI 对数差分分解法 + 敏感性分析）

功能：
  - 将乘法型复合指标分解为各因子的 LMDI 贡献度
  - 敏感性分析：模拟单因子变动 X% 时目标指标的变化
  - 结果保存为 CSV

用法：
  python dupont_analysis.py <数据文件路径> \
    --factors "因子名1:列名1" "因子名2:列名2" ... \
    [--time-col <时间列名>] \
    [--current-period <当前期值>] \
    [--base-period <基准期值>] \
    [--base-file <基准期数据文件>] \
    [--target-name <目标指标名称>] \
    [--sensitivity-pct 5 10 20] \
    [--output-dir <输出目录>]

输出：
  dupont_results.csv      — LMDI 因子分解详细结果
  dupont_sensitivity.csv  — 敏感性分析结果
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
from collections import OrderedDict


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


def parse_factors(factor_strings):
    """
    解析因子定义字符串列表。
    输入格式: ["显示名:列名", ...]
    返回: OrderedDict {显示名: 列名}
    """
    factors = OrderedDict()
    for s in factor_strings:
        if ':' not in s:
            print(f"错误：因子格式不正确 '{s}'，应为 '显示名:列名'")
            sys.exit(1)
        name, col = s.split(':', 1)
        factors[name.strip()] = col.strip()
    return factors


def dupont_analysis(df_current, df_base, metrics_dict, target_name="目标指标"):
    """
    杜邦分析：LMDI 对数差分分解法。

    参数：
      df_current:   当前期 DataFrame
      df_base:      基准期 DataFrame
      metrics_dict: OrderedDict {因子显示名: 列名}
      target_name:  目标复合指标名称

    返回：
      result_df: DataFrame — 各因子的分解结果
      factor_values: dict — {因子名: (基准值, 当前值)} 用于敏感性分析
      target_change_pct: float — 目标指标变化率
    """
    print(f"\n{'='*60}")
    print(f"  杜邦分析 - {target_name} LMDI 对数差分分解")
    print(f"{'='*60}")

    results = []
    log_changes = []
    factor_values = OrderedDict()

    for factor_name, col in metrics_dict.items():
        if col not in df_current.columns or col not in df_base.columns:
            print(f"警告：列 '{col}' 不存在，跳过因子 '{factor_name}'")
            continue

        v_curr = df_current[col].mean()
        v_base = df_base[col].mean()
        factor_values[factor_name] = (v_base, v_curr)

        if v_base > 0 and v_curr > 0:
            log_change = np.log(v_curr / v_base)
            change_pct = (v_curr / v_base - 1) * 100
        else:
            log_change = 0
            change_pct = None

        log_changes.append(log_change)
        results.append({
            "因子": factor_name,
            "基准期均值": round(v_base, 6),
            "当前期均值": round(v_curr, 6),
            "变化率(%)": round(change_pct, 2) if change_pct is not None else None,
            "对数变化": round(log_change, 6)
        })

    result_df = pd.DataFrame(results)

    # 计算 LMDI 贡献度
    total_log_change = sum(log_changes)
    if total_log_change != 0:
        result_df["LMDI贡献度(%)"] = result_df["对数变化"].apply(
            lambda x: round(x / total_log_change * 100, 2)
        )
    else:
        result_df["LMDI贡献度(%)"] = 0

    # 计算目标指标的整体变化
    product_curr = 1.0
    product_base = 1.0
    for factor_name, col in metrics_dict.items():
        if col in df_current.columns and col in df_base.columns:
            product_curr *= df_current[col].mean()
            product_base *= df_base[col].mean()

    target_change_pct = (product_curr / product_base - 1) * 100 if product_base != 0 else None

    print(f"\n{target_name} = {'  x  '.join(metrics_dict.keys())}")
    print(f"基准期 {target_name}: {product_base:.6f}")
    print(f"当前期 {target_name}: {product_curr:.6f}")
    if target_change_pct is not None:
        print(f"{target_name} 变化率: {target_change_pct:+.2f}%")
    print()
    print(result_df.to_string(index=False))

    return result_df, factor_values, target_change_pct


def sensitivity_analysis(factor_values, target_name="目标指标", sensitivity_pcts=None):
    """
    敏感性分析：模拟单因子变动 X% 时目标指标的变化。

    参数：
      factor_values:    OrderedDict {因子名: (基准值, 当前值)}
      target_name:      目标指标名称
      sensitivity_pcts: 变动幅度列表，如 [5, 10, 20]

    返回：
      DataFrame — 敏感性分析结果
    """
    if sensitivity_pcts is None:
        sensitivity_pcts = [5, 10, 20]

    # 当前期目标值
    current_target = 1.0
    for fname, (v_base, v_curr) in factor_values.items():
        current_target *= v_curr

    print(f"\n{'='*60}")
    print(f"  敏感性分析 - 单因子变动对 {target_name} 的影响")
    print(f"{'='*60}")
    print(f"当前 {target_name} = {current_target:.6f}")

    rows = []
    for factor_name, (v_base, v_curr) in factor_values.items():
        for pct in sensitivity_pcts:
            for direction in [1, -1]:
                delta = direction * pct
                # 模拟该因子变动 delta%，其他因子不变
                new_factor_val = v_curr * (1 + delta / 100)
                new_target = current_target / v_curr * new_factor_val
                target_delta_pct = (new_target / current_target - 1) * 100

                rows.append({
                    "因子": factor_name,
                    "因子当前值": round(v_curr, 6),
                    "假设变动(%)": f"{delta:+d}%",
                    "因子假设值": round(new_factor_val, 6),
                    f"{target_name}_新值": round(new_target, 6),
                    f"{target_name}_变化(%)": round(target_delta_pct, 2)
                })

    sensitivity_df = pd.DataFrame(rows)
    print()
    print(sensitivity_df.to_string(index=False))

    return sensitivity_df


def main():
    parser = argparse.ArgumentParser(
        description="杜邦分析（LMDI 对数差分分解法 + 敏感性分析）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--factors", required=True, nargs="+",
                        help='因子定义列表，格式为 "显示名:列名"')
    parser.add_argument("--base-file", help="基准期数据文件（独立文件模式）")
    parser.add_argument("--time-col", help="时间列名（同文件拆分模式）")
    parser.add_argument("--current-period", help="当前期值")
    parser.add_argument("--base-period", help="基准期值")
    parser.add_argument("--target-name", default="目标指标", help="目标复合指标名称")
    parser.add_argument("--sensitivity-pct", nargs="*", type=float, default=[5, 10, 20],
                        help="敏感性分析变动幅度列表（百分比），默认 5 10 20")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    # 加载数据
    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    # 解析因子
    metrics_dict = parse_factors(args.factors)
    print(f"分析因子: {' x '.join(metrics_dict.keys())}")

    # 验证列名
    missing_cols = [col for col in metrics_dict.values() if col not in df.columns]
    if missing_cols:
        print(f"错误：以下列名在数据中不存在: {missing_cols}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    # 拆分当前期和基准期
    if args.base_file:
        df_current = df
        df_base = load_data(args.base_file)
        print(f"已加载基准期数据: {df_base.shape[0]} 行 x {df_base.shape[1]} 列")
    elif args.time_col and args.current_period and args.base_period:
        if args.time_col not in df.columns:
            print(f"错误：时间列 '{args.time_col}' 不在数据中")
            sys.exit(1)
        df[args.time_col] = df[args.time_col].astype(str)
        df_current = df[df[args.time_col] == str(args.current_period)]
        df_base = df[df[args.time_col] == str(args.base_period)]
        if df_current.empty:
            print(f"错误：当前期 '{args.current_period}' 无匹配数据。"
                  f"可用值: {df[args.time_col].unique().tolist()}")
            sys.exit(1)
        if df_base.empty:
            print(f"错误：基准期 '{args.base_period}' 无匹配数据。"
                  f"可用值: {df[args.time_col].unique().tolist()}")
            sys.exit(1)
        print(f"当前期数据: {df_current.shape[0]} 行 | 基准期数据: {df_base.shape[0]} 行")
    else:
        print("错误：请指定 --base-file 或同时指定 --time-col、--current-period、--base-period")
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 执行杜邦分析
    result_df, factor_values, target_change_pct = dupont_analysis(
        df_current, df_base, metrics_dict, args.target_name
    )

    # 保存杜邦分解结果
    dupont_path = os.path.join(args.output_dir, "dupont_results.csv")
    result_df.to_csv(dupont_path, index=False, encoding='utf-8-sig')
    print(f"\n杜邦分解结果已保存至: {dupont_path}")

    # 执行敏感性分析
    sensitivity_df = sensitivity_analysis(
        factor_values, args.target_name, args.sensitivity_pct
    )

    # 保存敏感性分析结果
    sens_path = os.path.join(args.output_dir, "dupont_sensitivity.csv")
    sensitivity_df.to_csv(sens_path, index=False, encoding='utf-8-sig')
    print(f"敏感性分析结果已保存至: {sens_path}")


if __name__ == "__main__":
    main()
