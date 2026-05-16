#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集画像与质量体检脚本

全面扫描数据集：元数据、缺失值、唯一性、极值、重复行、常量列、
相关性冗余、类型推断质量、内存优化建议、字段质量评分。

用法示例:
    python data_profiling.py --input data.csv
    python data_profiling.py --input data.xlsx --columns col1,col2,col3 --corr-threshold 0.9
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def basic_metadata(df):
    """基础元数据概览。"""
    mem_mb = df.memory_usage(deep=True).sum() / 1024 ** 2
    dtype_counts = df.dtypes.apply(lambda x: x.name).value_counts().to_dict()

    meta = {
        "n_rows": df.shape[0],
        "n_cols": df.shape[1],
        "memory_mb": round(mem_mb, 2),
        "dtype_distribution": str(dtype_counts),
    }

    print("[结果] 数据概览:")
    print(f"  行数: {meta['n_rows']:,}")
    print(f"  列数: {meta['n_cols']}")
    print(f"  内存占用: {meta['memory_mb']:.2f} MB")
    print(f"  类型分布: {dtype_counts}")

    return meta


def uniqueness_analysis(df):
    """唯一性与基数分析，含类型推断。"""
    records = []
    n_rows = len(df)

    for col in df.columns:
        n_unique = df[col].nunique()
        cardinality_pct = n_unique / n_rows * 100 if n_rows > 0 else 0

        # 推断字段类型
        if cardinality_pct > 95:
            inferred_type = "ID类"
        elif n_unique <= 50:
            inferred_type = "分类变量"
        else:
            inferred_type = "连续/高基数"

        # 类型推断质量检查：object 列是否实际为数值
        dtype_issue = ""
        if df[col].dtype == "object":
            # 尝试转换为数值
            try:
                numeric_converted = pd.to_numeric(df[col].dropna(), errors="coerce")
                valid_ratio = numeric_converted.notna().sum() / max(df[col].notna().sum(), 1)
                if valid_ratio > 0.9:
                    dtype_issue = "疑似数值型存储为文本"
            except Exception:
                pass

        records.append({
            "column": col,
            "dtype": str(df[col].dtype),
            "n_unique": n_unique,
            "cardinality_pct": round(cardinality_pct, 2),
            "inferred_type": inferred_type,
            "dtype_issue": dtype_issue,
        })

    uniqueness_df = pd.DataFrame(records)
    print(f"\n[结果] 唯一性与基数分析:")
    print(uniqueness_df.to_string(index=False))

    # 类型问题汇总
    type_issues = uniqueness_df[uniqueness_df["dtype_issue"] != ""]
    if len(type_issues) > 0:
        print(f"\n[警告] 发现 {len(type_issues)} 个列存在类型推断问题:")
        for _, row in type_issues.iterrows():
            print(f"  {row['column']}: {row['dtype_issue']}")

    return uniqueness_df


def missing_analysis(df):
    """缺失值与零值分析。"""
    n_rows = len(df)
    records = []

    for col in df.columns:
        n_missing = df[col].isnull().sum()
        missing_pct = n_missing / n_rows * 100 if n_rows > 0 else 0

        # 零值统计（仅对数值列）
        n_zero = 0
        zero_pct = 0
        if df[col].dtype in ["int64", "int32", "float64", "float32"]:
            n_zero = (df[col] == 0).sum()
            zero_pct = n_zero / n_rows * 100 if n_rows > 0 else 0

        records.append({
            "column": col,
            "n_missing": n_missing,
            "missing_pct": round(missing_pct, 2),
            "n_zero": n_zero,
            "zero_pct": round(zero_pct, 2),
        })

    missing_df = pd.DataFrame(records).sort_values("missing_pct", ascending=False).reset_index(drop=True)

    has_missing = missing_df[missing_df["n_missing"] > 0]
    print(f"\n[结果] 缺失值分析:")
    if len(has_missing) > 0:
        print(has_missing.to_string(index=False))
    else:
        print("  无缺失值。")

    return missing_df


def duplicate_detection(df):
    """重复行检测。"""
    n_duplicates = df.duplicated().sum()
    dup_pct = n_duplicates / len(df) * 100 if len(df) > 0 else 0

    print(f"\n[结果] 重复行检测:")
    print(f"  完全重复行数: {n_duplicates} ({dup_pct:.1f}%)")

    return {"n_duplicate_rows": int(n_duplicates), "duplicate_pct": round(dup_pct, 2)}


def constant_column_detection(df):
    """常量列（零方差列）和近常量列检测。"""
    constant_cols = []
    near_constant_cols = []

    for col in df.columns:
        n_unique = df[col].nunique(dropna=True)
        if n_unique <= 1:
            constant_cols.append(col)
        elif n_unique == 2:
            near_constant_cols.append(col)

    print(f"\n[结果] 常量列检测:")
    if constant_cols:
        print(f"  零方差列 (唯一值 <= 1): {constant_cols}")
    else:
        print("  无零方差列。")
    if near_constant_cols:
        print(f"  近常量列 (唯一值 = 2): {near_constant_cols}")

    return {"constant_columns": constant_cols, "near_constant_columns": near_constant_cols}


def extremes_analysis(df):
    """数值列极值与范围分析。"""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        print("\n[结果] 极值分析: 无数值列。")
        return pd.DataFrame()

    records = []
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) == 0:
            continue

        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        n_outliers = ((s < lower_bound) | (s > upper_bound)).sum()

        records.append({
            "column": col,
            "min": round(s.min(), 4),
            "Q1": round(q1, 4),
            "median": round(s.median(), 4),
            "Q3": round(q3, 4),
            "max": round(s.max(), 4),
            "range": round(s.max() - s.min(), 4),
            "IQR": round(iqr, 4),
            "n_iqr_outliers": int(n_outliers),
            "outlier_pct": round(n_outliers / len(s) * 100, 2),
        })

    extremes_df = pd.DataFrame(records)
    print(f"\n[结果] 数值列极值与范围:")
    print(extremes_df.to_string(index=False))

    return extremes_df


def correlation_redundancy(df, threshold=0.95):
    """相关性冗余检测。"""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        print(f"\n[结果] 相关性冗余检测: 数值列不足 2 列，跳过。")
        return pd.DataFrame()

    # 当数值列>100时只计算前100列的相关矩阵
    if len(numeric_cols) > 100:
        print(f"[信息] 数值列({len(numeric_cols)})超过100，仅计算前100列的相关矩阵")
        numeric_cols = numeric_cols[:100]

    # 当数据>500000行时对相关矩阵计算抽样50000行
    df_corr = df[numeric_cols]
    if len(df_corr) > 500000:
        print(f"[信息] 数据行数({len(df_corr)})超过500000，抽样50000行计算相关矩阵")
        df_corr = df_corr.sample(n=50000, random_state=42)

    corr_matrix = df_corr.corr()

    # 找到高相关对
    records = []
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            r = corr_matrix.iloc[i, j]
            if abs(r) >= threshold:
                records.append({
                    "feature_1": numeric_cols[i],
                    "feature_2": numeric_cols[j],
                    "correlation": round(r, 4),
                    "abs_correlation": round(abs(r), 4),
                })

    redundancy_df = pd.DataFrame(records)
    if len(redundancy_df) > 0:
        redundancy_df = redundancy_df.sort_values("abs_correlation", ascending=False).reset_index(drop=True)

    print(f"\n[结果] 相关性冗余检测 (|r| >= {threshold}):")
    if len(redundancy_df) > 0:
        print(redundancy_df.to_string(index=False))
    else:
        print(f"  未发现相关系数绝对值 >= {threshold} 的特征对。")

    return redundancy_df


def memory_optimization_suggestions(df):
    """内存优化建议：dtype 降级。"""
    records = []
    current_mem = df.memory_usage(deep=True)

    for col in df.columns:
        current_dtype = str(df[col].dtype)
        suggested_dtype = current_dtype
        reason = ""

        if df[col].dtype == "float64":
            col_min = df[col].min()
            col_max = df[col].max()
            if pd.notna(col_min) and pd.notna(col_max):
                if np.finfo(np.float32).min <= col_min and col_max <= np.finfo(np.float32).max:
                    suggested_dtype = "float32"
                    reason = "值范围可容纳于 float32"

        elif df[col].dtype == "int64":
            col_min = df[col].min()
            col_max = df[col].max()
            if pd.notna(col_min) and pd.notna(col_max):
                if col_min >= np.iinfo(np.int8).min and col_max <= np.iinfo(np.int8).max:
                    suggested_dtype = "int8"
                    reason = "值范围可容纳于 int8"
                elif col_min >= np.iinfo(np.int16).min and col_max <= np.iinfo(np.int16).max:
                    suggested_dtype = "int16"
                    reason = "值范围可容纳于 int16"
                elif col_min >= np.iinfo(np.int32).min and col_max <= np.iinfo(np.int32).max:
                    suggested_dtype = "int32"
                    reason = "值范围可容纳于 int32"

        elif df[col].dtype == "object":
            n_unique = df[col].nunique()
            n_total = df[col].notna().sum()
            if n_unique / max(n_total, 1) < 0.5:
                suggested_dtype = "category"
                reason = f"唯一值比例低 ({n_unique}/{n_total})，适合 category 类型"

        if suggested_dtype != current_dtype:
            records.append({
                "column": col,
                "current_dtype": current_dtype,
                "suggested_dtype": suggested_dtype,
                "reason": reason,
            })

    mem_df = pd.DataFrame(records)

    # 估算节省比例
    total_current = current_mem.sum()
    estimated_saving = 0
    dtype_savings = {"float64->float32": 0.5, "int64->int8": 0.125, "int64->int16": 0.25, "int64->int32": 0.5}
    for _, row in mem_df.iterrows():
        key = f"{row['current_dtype']}->{row['suggested_dtype']}"
        ratio = dtype_savings.get(key, 0.5)
        estimated_saving += current_mem.get(row["column"], 0) * (1 - ratio)

    print(f"\n[结果] 内存优化建议:")
    if len(mem_df) > 0:
        print(mem_df.to_string(index=False))
        print(f"\n  当前总内存: {total_current / 1024 ** 2:.2f} MB")
        print(f"  预计可节省: {estimated_saving / 1024 ** 2:.2f} MB ({estimated_saving / max(total_current, 1) * 100:.1f}%)")
    else:
        print("  当前 dtype 已较合理，无明显优化空间。")

    return mem_df


def quality_scoring(missing_df, extremes_df, constant_info, uniqueness_df, df):
    """
    为每个字段生成质量评分。

    等级:
    - 健康: 缺失率 < 5%, 无明显极值异常, 非常量列
    - 需关注: 缺失率 5%-30%, 或有极值疑点, 或类型推断有问题
    - 问题严重: 缺失率 > 30%, 或全为零/常量
    """
    records = []

    for col in df.columns:
        issues = []

        # 缺失率
        miss_row = missing_df[missing_df["column"] == col]
        missing_pct = miss_row["missing_pct"].values[0] if len(miss_row) > 0 else 0

        if missing_pct > 30:
            issues.append(f"缺失率 {missing_pct:.1f}%")
        elif missing_pct > 5:
            issues.append(f"缺失率 {missing_pct:.1f}%")

        # 常量列
        if col in constant_info.get("constant_columns", []):
            issues.append("零方差常量列")

        # 极值异常
        if len(extremes_df) > 0:
            ext_row = extremes_df[extremes_df["column"] == col]
            if len(ext_row) > 0:
                outlier_pct = ext_row["outlier_pct"].values[0]
                if outlier_pct > 10:
                    issues.append(f"IQR 异常值 {outlier_pct:.1f}%")

        # 类型问题
        if len(uniqueness_df) > 0:
            uniq_row = uniqueness_df[uniqueness_df["column"] == col]
            if len(uniq_row) > 0 and uniq_row["dtype_issue"].values[0]:
                issues.append(uniq_row["dtype_issue"].values[0])

        # 评级
        if missing_pct > 30 or col in constant_info.get("constant_columns", []):
            level = "问题严重"
        elif missing_pct > 5 or any("异常值" in i for i in issues) or any("疑似" in i for i in issues):
            level = "需关注"
        else:
            level = "健康"

        records.append({
            "column": col,
            "quality_level": level,
            "missing_pct": missing_pct,
            "issues": "; ".join(issues) if issues else "",
        })

    quality_df = pd.DataFrame(records)

    # 统计
    level_counts = quality_df["quality_level"].value_counts()
    print(f"\n[结果] 字段质量评分:")
    print(f"  健康: {level_counts.get('健康', 0)} 个字段")
    print(f"  需关注: {level_counts.get('需关注', 0)} 个字段")
    print(f"  问题严重: {level_counts.get('问题严重', 0)} 个字段")

    problematic = quality_df[quality_df["quality_level"] != "健康"]
    if len(problematic) > 0:
        print(f"\n  非健康字段详情:")
        print(problematic.to_string(index=False))

    return quality_df


def main():
    parser = argparse.ArgumentParser(description="数据集画像与质量体检")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--columns", default=None, help="重点关注的列名 (逗号分隔，默认全部)")
    parser.add_argument("--corr-threshold", type=float, default=0.95, help="相关性冗余阈值 (默认 0.95)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)

    if args.columns:
        focus_cols = [c.strip() for c in args.columns.split(",")]
        missing_cols = [c for c in focus_cols if c not in df.columns]
        if missing_cols:
            print(f"[警告] 以下指定列不存在，将被忽略: {missing_cols}")
        df = df[[c for c in focus_cols if c in df.columns]]

    # 1. 元数据
    meta = basic_metadata(df)

    # 2. 唯一性分析
    uniqueness_df = uniqueness_analysis(df)

    # 3. 缺失值分析
    missing_df = missing_analysis(df)

    # 4. 重复行检测
    dup_info = duplicate_detection(df)

    # 5. 常量列检测
    constant_info = constant_column_detection(df)

    # 6. 极值分析
    extremes_df = extremes_analysis(df)

    # 7. 相关性冗余
    redundancy_df = correlation_redundancy(df, threshold=args.corr_threshold)

    # 8. 内存优化建议
    mem_df = memory_optimization_suggestions(df)

    # 9. 字段质量评分
    quality_df = quality_scoring(missing_df, extremes_df, constant_info, uniqueness_df, df)

    # === 保存所有输出 ===

    # 数据概览摘要
    overview = {**meta, **dup_info}
    overview["constant_columns"] = str(constant_info.get("constant_columns", []))
    overview["near_constant_columns"] = str(constant_info.get("near_constant_columns", []))
    overview_df = pd.DataFrame([overview])
    overview_path = os.path.join(args.output_dir, "data_overview.csv")
    overview_df.to_csv(overview_path, index=False)
    print(f"\n[输出] 数据概览已保存: {overview_path}")

    # 字段质量清单
    # 合并 uniqueness 和 missing 信息
    field_report = quality_df.merge(
        uniqueness_df[["column", "dtype", "n_unique", "cardinality_pct", "inferred_type"]],
        on="column", how="left"
    ).merge(
        missing_df[["column", "n_missing", "missing_pct", "n_zero", "zero_pct"]],
        on="column", how="left"
    )
    field_path = os.path.join(args.output_dir, "field_quality_report.csv")
    field_report.to_csv(field_path, index=False)
    print(f"[输出] 字段质量清单已保存: {field_path}")

    # 极值范围
    if len(extremes_df) > 0:
        extremes_path = os.path.join(args.output_dir, "extremes_analysis.csv")
        extremes_df.to_csv(extremes_path, index=False)
        print(f"[输出] 极值范围表已保存: {extremes_path}")

    # 冗余特征
    if len(redundancy_df) > 0:
        redundancy_path = os.path.join(args.output_dir, "redundant_features.csv")
        redundancy_df.to_csv(redundancy_path, index=False)
        print(f"[输出] 冗余特征对已保存: {redundancy_path}")

    # 内存优化
    if len(mem_df) > 0:
        mem_path = os.path.join(args.output_dir, "memory_optimization.csv")
        mem_df.to_csv(mem_path, index=False)
        print(f"[输出] 内存优化建议已保存: {mem_path}")

    print("\n[完成] 数据集画像与质量体检完毕。")


if __name__ == "__main__":
    main()
