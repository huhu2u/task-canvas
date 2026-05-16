#!/usr/bin/env python3
"""
交叉透视分析脚本

功能：
- 双维度交叉透视表（pivot table）
- 支持多种聚合函数
- 行合计、列合计、总计
- 行占比和列占比计算

用法：
    python pivot_analysis.py input.csv --row-col dim1 --col-col dim2 \
        --value-col metric1 --agg-func sum -o pivot_output.csv
"""

import argparse
import sys
import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """读取CSV或Excel文件"""
    if filepath.endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def pivot_analysis(df: pd.DataFrame, row_col: str, col_col: str,
                   value_col: str, agg_func: str = 'sum') -> dict:
    """
    交叉透视分析

    参数：
        df: 输入数据
        row_col: 行维度列
        col_col: 列维度列
        value_col: 值字段
        agg_func: 聚合函数

    返回：
        包含透视表和占比表的字典
    """
    # 高基数检查：row_nunique × col_nunique 超过100万时，保留频率Top类别
    row_nunique = df[row_col].nunique()
    col_nunique = df[col_col].nunique()
    matrix_cells = row_nunique * col_nunique

    if matrix_cells > 1_000_000:
        print(f"[警告] 透视表规模 ({row_nunique} × {col_nunique} = {matrix_cells:,}) 超过100万，可能占用大量内存")
        # 计算行和列维度各自应保留的Top数量，使乘积 <= 100万
        import math
        ratio = row_nunique / max(col_nunique, 1)
        max_col = max(1, int(math.sqrt(1_000_000 / max(ratio, 0.001))))
        max_row = max(1, int(1_000_000 / max_col))
        top_rows = df[row_col].value_counts().head(max_row).index
        top_cols = df[col_col].value_counts().head(max_col).index
        df = df[df[row_col].isin(top_rows) & df[col_col].isin(top_cols)]
        print(f"[信息] 已截断为 Top {len(top_rows)} 行 × Top {len(top_cols)} 列")

    # 生成透视表（含边际合计）
    pivot = pd.pivot_table(
        df,
        values=value_col,
        index=row_col,
        columns=col_col,
        aggfunc=agg_func,
        fill_value=0,
        margins=True,
        margins_name='合计'
    )

    print(f"\n=== 交叉透视表（{agg_func}）===")
    print(f"  行维度: {row_col} ({pivot.shape[0] - 1} 个值)")
    print(f"  列维度: {col_col} ({pivot.shape[1] - 1} 个值)")
    print(f"  值字段: {value_col}")
    print(f"  聚合函数: {agg_func}")
    print()
    print(pivot.to_string())

    # 行占比（每行占该行合计的比例）
    row_total = pivot.loc[:, '合计']
    pivot_row_pct = pivot.div(row_total, axis=0) * 100
    pivot_row_pct = pivot_row_pct.round(2)

    print(f"\n=== 行占比（%）===")
    print(pivot_row_pct.to_string())

    # 列占比（每列占该列合计的比例）
    col_total = pivot.loc['合计', :]
    pivot_col_pct = pivot.div(col_total, axis=1) * 100
    pivot_col_pct = pivot_col_pct.round(2)

    print(f"\n=== 列占比（%）===")
    print(pivot_col_pct.to_string())

    return {
        'pivot': pivot,
        'row_pct': pivot_row_pct,
        'col_pct': pivot_col_pct
    }


def main():
    parser = argparse.ArgumentParser(description='交叉透视分析')
    parser.add_argument('input_file', help='输入数据文件路径（CSV或Excel）')
    parser.add_argument('--row-col', required=True, help='行维度列名')
    parser.add_argument('--col-col', required=True, help='列维度列名')
    parser.add_argument('--value-col', required=True, help='值字段列名')
    parser.add_argument('--agg-func', default='sum',
                        choices=['sum', 'mean', 'median', 'count', 'min', 'max'],
                        help='聚合函数（默认: sum）')
    parser.add_argument('-o', '--output', default='pivot_output.csv', help='输出文件路径')

    args = parser.parse_args()

    df = load_data(args.input_file)
    print(f"数据加载完成: {df.shape[0]} 行, {df.shape[1]} 列")

    for col in [args.row_col, args.col_col, args.value_col]:
        if col not in df.columns:
            print(f"错误: 列 '{col}' 不存在于数据中")
            print(f"可用列: {list(df.columns)}")
            sys.exit(1)

    results = pivot_analysis(df, args.row_col, args.col_col, args.value_col, args.agg_func)

    # 保存透视表
    results['pivot'].to_csv(args.output, encoding='utf-8-sig')
    print(f"\n透视表已保存至: {args.output}")

    # 保存占比表
    row_pct_path = args.output.replace('.csv', '_row_pct.csv')
    col_pct_path = args.output.replace('.csv', '_col_pct.csv')
    results['row_pct'].to_csv(row_pct_path, encoding='utf-8-sig')
    results['col_pct'].to_csv(col_pct_path, encoding='utf-8-sig')
    print(f"行占比表已保存至: {row_pct_path}")
    print(f"列占比表已保存至: {col_pct_path}")


if __name__ == '__main__':
    main()
