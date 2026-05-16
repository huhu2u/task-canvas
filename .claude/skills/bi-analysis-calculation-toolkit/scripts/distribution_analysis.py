#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分布特征分析脚本

覆盖集中趋势、离散程度、分布形态、正态性检验（Shapiro-Wilk, Anderson-Darling,
KS, Jarque-Bera）、Bootstrap 置信区间、参数分布拟合（AIC 比较）、分组对比。

用法示例:
    python distribution_analysis.py --input data.csv --columns col1,col2
    python distribution_analysis.py --input data.csv --columns col1 --group-by category
    python distribution_analysis.py --input data.csv --columns col1,col2 --bootstrap-n 5000
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")


def load_data(filepath):
    """加载 CSV 或 Excel 文件。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(filepath)
    return pd.read_csv(filepath)


def compute_descriptive_stats(s, col_name=""):
    """
    计算单个 Series 的完整描述统计量。

    Parameters
    ----------
    s : Series (已 dropna)
    col_name : str

    Returns
    -------
    dict
    """
    n = len(s)

    if n == 0:
        return {"column": col_name, "n": 0, "n_missing": 0, "status": "全部为NaN"}

    if s.nunique() == 1:
        return {
            "column": col_name,
            "n": n,
            "unique_value": s.iloc[0],
            "status": "单一值列",
        }

    mean_val = s.mean()
    median_val = s.median()

    # 众数
    mode_vals = s.mode()
    mode_val = mode_vals.iloc[0] if len(mode_vals) > 0 else np.nan

    # 截尾均值
    try:
        trimmed_mean = sp_stats.trim_mean(s.values, 0.05)
    except Exception:
        trimmed_mean = np.nan

    # 离散度
    std_val = s.std()
    var_val = s.var()
    cv = (std_val / abs(mean_val) * 100) if abs(mean_val) > 1e-10 else np.nan
    mad = np.mean(np.abs(s - mean_val))
    iqr = s.quantile(0.75) - s.quantile(0.25)

    # 形态
    skew = s.skew()
    kurt = s.kurtosis()  # 超额峰度 (excess kurtosis)

    # 分位数
    quantiles = {}
    for p in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
        quantiles[f"P{int(p*100)}"] = round(s.quantile(p), 6)

    # IQR 异常值
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr_val = q3 - q1
    lower_bound = q1 - 1.5 * iqr_val
    upper_bound = q3 + 1.5 * iqr_val
    n_outliers = ((s < lower_bound) | (s > upper_bound)).sum()

    result = {
        "column": col_name,
        "n": n,
        "mean": round(mean_val, 6),
        "median": round(median_val, 6),
        "mode": round(mode_val, 6) if pd.notna(mode_val) else np.nan,
        "trimmed_mean_5pct": round(trimmed_mean, 6),
        "variance": round(var_val, 6),
        "std": round(std_val, 6),
        "cv_pct": round(cv, 2) if pd.notna(cv) else "N/A (mean~0)",
        "mad": round(mad, 6),
        "iqr": round(iqr, 6),
        "skewness": round(skew, 4),
        "kurtosis_excess": round(kurt, 4),
        "n_iqr_outliers": int(n_outliers),
        "outlier_pct": round(n_outliers / n * 100, 2),
    }
    result.update(quantiles)

    return result


def normality_tests(s, col_name=""):
    """
    执行多种正态性检验。

    Parameters
    ----------
    s : Series (已 dropna，且 n >= 2)
    col_name : str

    Returns
    -------
    list[dict]
    """
    n = len(s)
    results = []

    # Shapiro-Wilk (n < 5000 效果好)
    if 8 <= n <= 5000:
        try:
            stat, p = sp_stats.shapiro(s.values)
            results.append({
                "column": col_name,
                "test": "Shapiro-Wilk",
                "statistic": round(stat, 6),
                "p_value": round(p, 6),
                "reject_h0_005": p < 0.05,
                "conclusion": "非正态" if p < 0.05 else "不能拒绝正态",
            })
        except Exception as e:
            results.append({"column": col_name, "test": "Shapiro-Wilk", "error": str(e)})
    elif n < 8:
        results.append({"column": col_name, "test": "Shapiro-Wilk", "error": f"样本量 {n} < 8，跳过"})

    # Anderson-Darling
    if n >= 8:
        try:
            ad_result = sp_stats.anderson(s.values, dist="norm")
            # 使用 5% 显著性水平
            idx_5pct = 2  # anderson 返回的 significance_level 通常为 [15, 10, 5, 2.5, 1]
            if len(ad_result.critical_values) > idx_5pct:
                reject = ad_result.statistic > ad_result.critical_values[idx_5pct]
                results.append({
                    "column": col_name,
                    "test": "Anderson-Darling",
                    "statistic": round(ad_result.statistic, 6),
                    "critical_value_5pct": round(ad_result.critical_values[idx_5pct], 6),
                    "reject_h0_005": reject,
                    "conclusion": "非正态" if reject else "不能拒绝正态",
                })
            else:
                results.append({
                    "column": col_name,
                    "test": "Anderson-Darling",
                    "statistic": round(ad_result.statistic, 6),
                    "conclusion": "临界值不可用",
                })
        except Exception as e:
            results.append({"column": col_name, "test": "Anderson-Darling", "error": str(e)})

    # Kolmogorov-Smirnov (与标准正态比较)
    if n >= 2:
        try:
            # 先标准化再比较
            z = (s - s.mean()) / s.std()
            stat, p = sp_stats.kstest(z.values, "norm")
            results.append({
                "column": col_name,
                "test": "Kolmogorov-Smirnov",
                "statistic": round(stat, 6),
                "p_value": round(p, 6),
                "reject_h0_005": p < 0.05,
                "conclusion": "非正态" if p < 0.05 else "不能拒绝正态",
            })
        except Exception as e:
            results.append({"column": col_name, "test": "Kolmogorov-Smirnov", "error": str(e)})

    # Jarque-Bera
    if n >= 8:
        try:
            stat, p = sp_stats.jarque_bera(s.values)
            results.append({
                "column": col_name,
                "test": "Jarque-Bera",
                "statistic": round(stat, 6),
                "p_value": round(p, 6),
                "reject_h0_005": p < 0.05,
                "conclusion": "非正态" if p < 0.05 else "不能拒绝正态",
            })
        except Exception as e:
            results.append({"column": col_name, "test": "Jarque-Bera", "error": str(e)})

    return results


def bootstrap_ci(s, n_bootstrap=1000, confidence=0.95, random_state=42):
    """
    Bootstrap 置信区间估计（均值和中位数）。

    Returns
    -------
    dict
    """
    rng = np.random.RandomState(random_state)
    values = s.values
    n = len(values)

    if n < 2:
        return {"mean_ci_lower": np.nan, "mean_ci_upper": np.nan,
                "median_ci_lower": np.nan, "median_ci_upper": np.nan}

    # 当样本量 > 50000 时，先抽样到 50000 以降低内存压力
    max_sample = 50000
    if n > max_sample:
        print(f"  [信息] 样本量 ({n}) 超过 {max_sample}，Bootstrap 前抽样至 {max_sample}")
        values = rng.choice(values, size=max_sample, replace=False)
        n = max_sample

    boot_means = np.zeros(n_bootstrap)
    boot_medians = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        sample = rng.choice(values, size=n, replace=True)
        boot_means[i] = sample.mean()
        boot_medians[i] = np.median(sample)

    alpha = 1 - confidence
    lower_pct = alpha / 2 * 100
    upper_pct = (1 - alpha / 2) * 100

    result = {
        "mean_estimate": round(values.mean(), 6),
        "mean_ci_lower": round(np.percentile(boot_means, lower_pct), 6),
        "mean_ci_upper": round(np.percentile(boot_means, upper_pct), 6),
        "mean_bootstrap_se": round(boot_means.std(), 6),
        "median_estimate": round(np.median(values), 6),
        "median_ci_lower": round(np.percentile(boot_medians, lower_pct), 6),
        "median_ci_upper": round(np.percentile(boot_medians, upper_pct), 6),
        "median_bootstrap_se": round(boot_medians.std(), 6),
        "confidence_level": confidence,
        "n_bootstrap": n_bootstrap,
    }

    return result


def fit_distributions(s, col_name=""):
    """
    尝试拟合多种参数分布并用 AIC 排序。

    Returns
    -------
    list[dict]
    """
    values = s.values
    n = len(values)

    if n < 10:
        return [{"column": col_name, "distribution": "N/A", "note": f"样本量 {n} 不足，跳过分布拟合"}]

    # 当样本量 > 50000 时，先抽样到 50000 以降低分布拟合计算量
    max_sample = 50000
    if n > max_sample:
        print(f"  [信息] 列 '{col_name}' 样本量 ({n}) 超过 {max_sample}，分布拟合前抽样至 {max_sample}")
        rng = np.random.RandomState(42)
        values = rng.choice(values, size=max_sample, replace=False)
        n = max_sample

    distributions = [
        ("norm", sp_stats.norm),
        ("lognorm", sp_stats.lognorm),
        ("expon", sp_stats.expon),
        ("gamma", sp_stats.gamma),
    ]

    results = []
    for dist_name, dist in distributions:
        try:
            # 对数正态和 gamma 需要正数据
            if dist_name in ("lognorm", "gamma", "expon"):
                if values.min() <= 0:
                    results.append({
                        "column": col_name,
                        "distribution": dist_name,
                        "aic": np.nan,
                        "note": "需要正值数据",
                    })
                    continue

            params = dist.fit(values)
            log_likelihood = np.sum(dist.logpdf(values, *params))

            # 处理无穷大的对数似然
            if not np.isfinite(log_likelihood):
                results.append({
                    "column": col_name,
                    "distribution": dist_name,
                    "aic": np.nan,
                    "note": "对数似然无穷大",
                })
                continue

            k = len(params)
            aic = 2 * k - 2 * log_likelihood

            # KS 检验拟合优度
            ks_stat, ks_p = sp_stats.kstest(values, dist_name, args=params)

            results.append({
                "column": col_name,
                "distribution": dist_name,
                "params": str({f"param_{i}": round(p, 6) for i, p in enumerate(params)}),
                "log_likelihood": round(log_likelihood, 4),
                "aic": round(aic, 4),
                "ks_statistic": round(ks_stat, 6),
                "ks_p_value": round(ks_p, 6),
            })
        except Exception as e:
            results.append({
                "column": col_name,
                "distribution": dist_name,
                "aic": np.nan,
                "note": str(e),
            })

    # 按 AIC 排序
    results = sorted(results, key=lambda x: x.get("aic", float("inf")) if pd.notna(x.get("aic")) else float("inf"))

    return results


def compute_grouped_stats(df, columns, group_col):
    """
    按分组列分别计算描述统计量。

    Returns
    -------
    DataFrame
    """
    records = []
    groups = df[group_col].unique()

    for group_val in sorted(groups, key=str):
        group_data = df[df[group_col] == group_val]
        for col in columns:
            s = group_data[col].dropna()
            if len(s) == 0:
                continue
            stats = compute_descriptive_stats(s, col_name=col)
            stats["group"] = group_val
            stats["group_n"] = len(s)
            records.append(stats)

    grouped_df = pd.DataFrame(records)
    # 把 group 列移到前面
    if "group" in grouped_df.columns:
        cols = ["group", "group_n"] + [c for c in grouped_df.columns if c not in ("group", "group_n")]
        grouped_df = grouped_df[cols]

    return grouped_df


def main():
    parser = argparse.ArgumentParser(description="统计分布特征分析: 描述统计 + 正态性检验 + Bootstrap CI + 分布拟合")
    parser.add_argument("--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("--columns", required=True, help="目标数值列名，逗号分隔")
    parser.add_argument("--group-by", default=None, help="分组列名 (可选)")
    parser.add_argument("--bootstrap-n", type=int, default=1000, help="Bootstrap 重采样次数 (默认 1000)")
    parser.add_argument("--confidence", type=float, default=0.95, help="置信水平 (默认 0.95)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    parser.add_argument("--output-dir", default=".", help="输出文件目录")

    args = parser.parse_args()
    columns = [c.strip() for c in args.columns.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    print(f"[信息] 加载数据: {args.input}")
    df = load_data(args.input)
    print(f"[信息] 数据规模: {df.shape[0]} 行, {df.shape[1]} 列")

    check_cols = columns + ([args.group_by] if args.group_by else [])
    missing_cols = [c for c in check_cols if c not in df.columns]
    if missing_cols:
        print(f"[错误] 以下列不存在: {missing_cols}")
        sys.exit(1)

    # === 1. 描述统计 ===
    desc_records = []
    for col in columns:
        s_full = df[col]
        s = s_full.dropna()
        n_missing = s_full.isnull().sum()

        if len(s) == 0:
            print(f"\n[警告] 列 '{col}' 全部为 NaN，跳过。")
            desc_records.append({"column": col, "n": 0, "n_missing": n_missing, "status": "全部为NaN"})
            continue

        stats = compute_descriptive_stats(s, col_name=col)
        stats["n_missing"] = n_missing
        desc_records.append(stats)

        print(f"\n[结果] '{col}' 描述统计:")
        for k, v in stats.items():
            if k != "column":
                print(f"  {k}: {v}")

    desc_df = pd.DataFrame(desc_records)
    desc_path = os.path.join(args.output_dir, "descriptive_stats.csv")
    desc_df.to_csv(desc_path, index=False)
    print(f"\n[输出] 描述统计表已保存: {desc_path}")

    # === 2. 正态性检验 ===
    normality_records = []
    for col in columns:
        s = df[col].dropna()
        if len(s) < 2 or s.nunique() == 1:
            normality_records.append({"column": col, "test": "ALL", "error": "样本量不足或单一值"})
            continue
        results = normality_tests(s, col_name=col)
        normality_records.extend(results)

    normality_df = pd.DataFrame(normality_records)
    normality_path = os.path.join(args.output_dir, "normality_tests.csv")
    normality_df.to_csv(normality_path, index=False)
    print(f"\n[结果] 正态性检验:")
    print(normality_df.to_string(index=False))
    print(f"[输出] 正态性检验结果已保存: {normality_path}")

    # === 3. Bootstrap 置信区间 ===
    bootstrap_records = []
    for col in columns:
        s = df[col].dropna()
        if len(s) < 2:
            continue
        ci = bootstrap_ci(s, n_bootstrap=args.bootstrap_n, confidence=args.confidence, random_state=args.seed)
        ci["column"] = col
        bootstrap_records.append(ci)

    if bootstrap_records:
        bootstrap_df = pd.DataFrame(bootstrap_records)
        # 重排列
        cols_order = ["column"] + [c for c in bootstrap_df.columns if c != "column"]
        bootstrap_df = bootstrap_df[cols_order]

        bootstrap_path = os.path.join(args.output_dir, "bootstrap_ci.csv")
        bootstrap_df.to_csv(bootstrap_path, index=False)
        print(f"\n[结果] Bootstrap {args.confidence*100:.0f}% 置信区间:")
        print(bootstrap_df.to_string(index=False))
        print(f"[输出] Bootstrap 置信区间已保存: {bootstrap_path}")

    # === 4. 分布拟合 ===
    fit_records = []
    for col in columns:
        s = df[col].dropna()
        if len(s) < 10 or s.nunique() == 1:
            continue
        results = fit_distributions(s, col_name=col)
        fit_records.extend(results)

    if fit_records:
        fit_df = pd.DataFrame(fit_records)
        fit_path = os.path.join(args.output_dir, "distribution_fit.csv")
        fit_df.to_csv(fit_path, index=False)
        print(f"\n[结果] 分布拟合 (按 AIC 排序):")
        print(fit_df.to_string(index=False))
        print(f"[输出] 分布拟合结果已保存: {fit_path}")

        # 打印每列的最佳拟合
        for col in columns:
            col_fits = [r for r in fit_records if r.get("column") == col and pd.notna(r.get("aic"))]
            if col_fits:
                best = min(col_fits, key=lambda x: x["aic"])
                print(f"  '{col}' 最佳拟合: {best['distribution']} (AIC = {best['aic']:.2f})")

    # === 5. 分组对比 ===
    if args.group_by:
        print(f"\n[信息] 按 '{args.group_by}' 分组对比...")
        grouped_df = compute_grouped_stats(df, columns, args.group_by)
        grouped_path = os.path.join(args.output_dir, "grouped_stats.csv")
        grouped_df.to_csv(grouped_path, index=False)
        print(f"\n[结果] 分组描述统计:")
        # 只打印关键列
        key_cols = [c for c in ["group", "group_n", "column", "mean", "median", "std", "skewness", "cv_pct"]
                    if c in grouped_df.columns]
        print(grouped_df[key_cols].to_string(index=False))
        print(f"[输出] 分组对比表已保存: {grouped_path}")

    print("\n[完成] 统计分布特征分析完毕。")


if __name__ == "__main__":
    main()
