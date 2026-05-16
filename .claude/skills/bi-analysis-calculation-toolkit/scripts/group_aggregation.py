#!/usr/bin/env python3
"""
多维分组聚合脚本

功能：
- 按指定维度进行 groupby 聚合（支持 sum/mean/median/count/std 等）
- 加权聚合支持
- 计算各分组占比与排名
- HHI（赫芬达尔-赫希曼指数）集中度计算
- 基尼系数计算
- Top-N 提取，其余合并为"其他"
- 多指标同时聚合

用法：
    python group_aggregation.py input.csv --group-cols col1 col2 \
        --metric-cols metric1 metric2 --agg-func sum --top-n 10 -o output.csv
"""

import argparse
import sys
import numpy as np
import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def calc_hhi(shares: pd.Series) -> float:
    """
    计算HHI指数（Herfindahl-Hirschman Index）
    shares: 各分组的份额（百分比形式，0-100）
    返回值范围 [0, 10000]
    """
    return float((shares ** 2).sum())


def calc_gini(values: pd.Series) -> float:
    """
    计算基尼系数
    values: 各分组的度量值（非负）
    返回值范围 [0, 1]
    """
    values = values.sort_values().values.astype(float)
    n = len(values)
    if n == 0 or values.sum() == 0:
        return 0.0
    cumvals = np.cumsum(values)
    gini = (2.0 * np.sum((np.arange(1, n + 1) * values)) / (n * values.sum())) - (n + 1) / n
    return max(0.0, min(1.0, float(gini)))


def weighted_agg(df: pd.DataFrame, group_cols: list, metric_col: str,
                 weight_col: str) -> pd.DataFrame:
    """加权聚合：计算加权和与加权均值"""
    df = df.copy()
    df['_weighted_value'] = df[metric_col] * df[weight_col]
    grouped = df.groupby(group_cols).agg(
        weighted_sum=('_weighted_value', 'sum'),
        weight_total=(weight_col, 'sum'),
        count=(metric_col, 'count')
    ).reset_index()
    grouped['weighted_mean'] = grouped['weighted_sum'] / grouped['weight_total'].replace(0, np.nan)
    grouped = grouped.rename(columns={
        'weighted_sum': f'{metric_col}_加权和',
        'weighted_mean': f'{metric_col}_加权均值',
        'weight_total': f'{weight_col}_合计',
        'count': '记录数'
    })
    return grouped


def group_aggregation(df: pd.DataFrame, group_cols: list, metric_cols: list,
                      agg_func: str = 'sum', top_n: int = 10,
                      weight_col: str = None) -> pd.DataFrame:
    """
    多维分组聚合主函数

    参数：
        df: 输入数据
        group_cols: 分组维度列
        metric_cols: 度量指标列
        agg_func: 聚合函数（sum/mean/median/count/std）
        top_n: Top-N 取值
        weight_col: 权重列（可选）
    """
    # 加权聚合模式
    if weight_col:
        results = []
        for mc in metric_cols:
            res = weighted_agg(df, group_cols, mc, weight_col)
            results.append(res)
        # 合并多指标结果
        if len(results) == 1:
            result = results[0]
        else:
            result = results[0]
            for r in results[1:]:
                extra_cols = [c for c in r.columns if c not in group_cols and c not in result.columns]
                result = result.merge(r[group_cols + extra_cols], on=group_cols, how='outer')
        sort_col = f'{metric_cols[0]}_加权和'
        result = result.sort_values(sort_col, ascending=False).reset_index(drop=True)
        return result

    # 标准聚合模式
    agg_dict = {mc: agg_func for mc in metric_cols}
    result = df.groupby(group_cols).agg(agg_dict).reset_index()

    # 主排序指标
    primary_metric = metric_cols[0]
    result = result.sort_values(primary_metric, ascending=False).reset_index(drop=True)

    # 为每个指标计算占比和排名
    for mc in metric_cols:
        total = result[mc].sum()
        if total != 0:
            result[f'{mc}_占比(%)'] = (result[mc] / total * 100).round(2)
        else:
            result[f'{mc}_占比(%)'] = 0.0
        result[f'{mc}_排名'] = result[mc].rank(method='dense', ascending=False).astype(int)

    # 集中度指标（基于主指标）
    primary_total = result[primary_metric].sum()
    if primary_total > 0:
        shares = result[primary_metric] / primary_total * 100
        hhi = calc_hhi(shares)
        gini = calc_gini(result[primary_metric])

        print(f"\n=== 集中度指标（基于 {primary_metric}）===")
        print(f"  分组数量: {len(result)}")
        print(f"  HHI指数: {hhi:.2f} (0=完全分散, 10000=完全集中)")
        if hhi < 1500:
            print(f"  HHI判定: 低集中度（竞争性分布）")
        elif hhi < 2500:
            print(f"  HHI判定: 中等集中度")
        else:
            print(f"  HHI判定: 高集中度")
        print(f"  基尼系数: {gini:.4f} (0=完全均等, 1=完全不均等)")

        # CR-N
        top_n_actual = min(top_n, len(result))
        cr_n = result[f'{primary_metric}_占比(%)'].head(top_n_actual).sum()
        print(f"  CR-{top_n_actual}: {cr_n:.2f}% (前{top_n_actual}名集中度)")

    # Top-N + 其他
    if len(result) > top_n:
        top_part = result.head(top_n).copy()
        others = result.iloc[top_n:]
        others_row = {}
        for col in group_cols:
            others_row[col] = '其他'
        for mc in metric_cols:
            others_row[mc] = others[mc].sum()
            total_mc = result[mc].sum()
            others_row[f'{mc}_占比(%)'] = round(others[mc].sum() / total_mc * 100, 2) if total_mc else 0
            others_row[f'{mc}_排名'] = top_n + 1
        others_df = pd.DataFrame([others_row])
        result_topn = pd.concat([top_part, others_df], ignore_index=True)

        print(f"\n=== Top-{top_n} + 其他 汇总 ===")
        print(result_topn.to_string(index=False))
    else:
        result_topn = result
        print(f"\n=== 分组汇总（共{len(result)}组）===")
        print(result.to_string(index=False))

    return result_topn


def main():
    parser = argparse.ArgumentParser(description='多维分组聚合分析')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--group-cols', nargs='+', required=True, help='分组维度列名')
    parser.add_argument('--metric-cols', nargs='+', required=True, help='度量指标列名')
    parser.add_argument('--agg-func', default='sum',
                        choices=['sum', 'mean', 'median', 'count', 'std', 'min', 'max'],
                        help='聚合函数（默认: sum）')
    parser.add_argument('--top-n', type=int, default=10, help='Top-N取值（默认: 10）')
    parser.add_argument('--weight-col', default=None, help='权重列（启用加权聚合）')
    parser.add_argument('-o', '--output', default='group_aggregation_output.csv', help='输出文件路径')

    args = parser.parse_args()

    # 读取数据
    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    # 验证列存在性
    all_cols = args.group_cols + args.metric_cols
    if args.weight_col:
        all_cols.append(args.weight_col)
    missing = [c for c in all_cols if c not in df.columns]
    if missing:
        print(f"错误: 以下列不存在于数据中: {missing}")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    # 执行聚合
    result = group_aggregation(
        df=df,
        group_cols=args.group_cols,
        metric_cols=args.metric_cols,
        agg_func=args.agg_func,
        top_n=args.top_n,
        weight_col=args.weight_col
    )

    # 保存结果
    result.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {args.output}")


if __name__ == '__main__':
    main()
