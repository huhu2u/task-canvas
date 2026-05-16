#!/usr/bin/env python3
"""
单变量异常检测脚本
方法：3-Sigma (Z-Score) + IQR + MAD 三方法投票
增强：小样本Grubbs检验、归一化综合异常分数、边界情况处理

用法：
    python univariate_anomaly.py -i data.csv -c value_column -o result.csv
    python univariate_anomaly.py -i data.xlsx -c sales --threshold 2 --contamination 0.05
"""

import argparse
import sys
import numpy as np
import pandas as pd
from scipy import stats


def grubbs_test(series, alpha=0.05):
    """
    Grubbs检验：适用于小样本（n < 30）的单个离群值检测。
    迭代执行直到没有离群值或样本量不足。

    Returns:
        pd.Series: 布尔序列，True表示异常
    """
    s = series.copy()
    is_outlier = pd.Series(False, index=series.index)

    while len(s.dropna()) >= 7:  # Grubbs检验最少需要7个样本
        clean = s.dropna()
        n = len(clean)
        mean_val = clean.mean()
        std_val = clean.std(ddof=1)

        if std_val == 0:
            break

        # 找到偏离均值最远的点
        abs_devs = (clean - mean_val).abs()
        max_idx = abs_devs.idxmax()
        G = abs_devs[max_idx] / std_val

        # 计算临界值
        t_crit = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        G_crit = ((n - 1) / np.sqrt(n)) * np.sqrt(t_crit**2 / (n - 2 + t_crit**2))

        if G > G_crit:
            is_outlier[max_idx] = True
            s[max_idx] = np.nan  # 移除该点继续检验
        else:
            break

    return is_outlier


def normalize_scores(scores):
    """将分数归一化到 [0, 1] 区间"""
    min_val = scores.min()
    max_val = scores.max()
    if max_val == min_val:
        return pd.Series(0.0, index=scores.index)
    return (scores - min_val) / (max_val - min_val)


def univariate_anomaly(series, contamination=0.05, vote_threshold=2, grubbs_alpha=0.05):
    """
    单变量异常检测：3-Sigma + IQR + MAD 投票，小样本自动启用Grubbs检验。

    Args:
        series: pd.Series，待检测的数值序列
        contamination: 预期异常比例上限（仅用于报告）
        vote_threshold: 投票阈值（默认2/3方法认定为异常）
        grubbs_alpha: Grubbs检验的显著性水平

    Returns:
        pd.DataFrame: 检测结果，包含各方法判定和综合异常分数
    """
    s = series.copy()
    n_total = len(s)
    n_valid = s.notna().sum()

    # 边界情况处理
    if n_valid == 0:
        print("[警告] 序列全部为NaN，无法检测异常")
        return pd.DataFrame()

    if n_valid < 3:
        print(f"[警告] 有效样本仅{n_valid}个，样本量不足，跳过检测")
        return pd.DataFrame()

    # 检查常数序列
    if s.dropna().nunique() == 1:
        print("[警告] 序列为常数，所有值相同，无异常点")
        result = pd.DataFrame({"原始值": s})
        result["是否异常"] = False
        result["综合异常分数"] = 0.0
        return result

    result = pd.DataFrame({"原始值": s})

    # === 方法1：3-Sigma (Z-Score) ===
    clean = s.dropna()
    use_grubbs = n_valid < 30

    if use_grubbs:
        print(f"[信息] 样本量={n_valid} < 30，使用Grubbs检验替代3-Sigma")
        result["Grubbs异常"] = grubbs_test(s, alpha=grubbs_alpha)
        result["方法1_异常"] = result["Grubbs异常"]
        # 用偏差作为分数
        mean_val = clean.mean()
        std_val = clean.std(ddof=1)
        if std_val > 0:
            result["方法1_分数"] = normalize_scores(((s - mean_val) / std_val).abs().fillna(0))
        else:
            result["方法1_分数"] = 0.0
    else:
        z_scores = pd.Series(np.nan, index=s.index)
        z_vals = np.abs(stats.zscore(clean))
        z_scores.loc[clean.index] = z_vals
        result["Z_Score"] = z_scores
        result["3Sigma异常"] = z_scores > 3
        result["方法1_异常"] = result["3Sigma异常"]
        result["方法1_分数"] = normalize_scores(z_scores.fillna(0))

    # === 方法2：IQR 箱线图规则 ===
    Q1 = clean.quantile(0.25)
    Q3 = clean.quantile(0.75)
    IQR = Q3 - Q1

    if IQR == 0:
        print("[警告] IQR=0，分位数区间无差异，IQR方法可能不适用")
        result["IQR异常"] = False
        result["方法2_分数"] = 0.0
    else:
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        result["IQR异常"] = (s < lower) | (s > upper)
        # IQR距离分数
        iqr_dist = pd.Series(0.0, index=s.index)
        iqr_dist[s < lower] = (lower - s[s < lower]) / IQR
        iqr_dist[s > upper] = (s[s > upper] - upper) / IQR
        result["方法2_分数"] = normalize_scores(iqr_dist.fillna(0))

    result["方法2_异常"] = result["IQR异常"]

    # === 方法3：MAD (Median Absolute Deviation) ===
    median = clean.median()
    mad = np.median(np.abs(clean - median))

    if mad == 0:
        print("[警告] MAD=0，中位数绝对偏差为零，MAD方法不适用")
        result["MAD异常"] = False
        result["方法3_异常"] = False
        result["方法3_分数"] = 0.0
    else:
        modified_z = 0.6745 * (s - median) / mad
        result["MAD_Modified_Z"] = modified_z
        result["MAD异常"] = modified_z.abs() > 3.5
        result["方法3_异常"] = result["MAD异常"]
        result["方法3_分数"] = normalize_scores(modified_z.abs().fillna(0))

    # === 投票汇总 ===
    vote_cols = ["方法1_异常", "方法2_异常", "方法3_异常"]
    result["投票数"] = result[vote_cols].sum(axis=1)
    result["是否异常"] = result["投票数"] >= vote_threshold

    # === 综合异常分数（归一化平均） ===
    score_cols = ["方法1_分数", "方法2_分数", "方法3_分数"]
    result["综合异常分数"] = result[score_cols].mean(axis=1).round(4)

    # === 统计特征 ===
    result["偏离均值倍数"] = ((s - clean.mean()) / clean.std(ddof=1)).round(3) if clean.std(ddof=1) > 0 else 0
    result["分位数"] = s.rank(pct=True).round(4)

    # 输出统计
    n_anomaly = result["是否异常"].sum()
    pct = n_anomaly / n_valid * 100 if n_valid > 0 else 0
    print(f"\n=== 单变量异常检测结果 ===")
    print(f"总样本数: {n_total} (有效: {n_valid})")
    print(f"异常点数: {n_anomaly} (占比: {pct:.1f}%)")
    print(f"使用方法: {'Grubbs' if use_grubbs else '3-Sigma'} + IQR + MAD")
    print(f"投票阈值: >={vote_threshold}/3")

    if n_anomaly > 0:
        anomalies = result[result["是否异常"]].sort_values("综合异常分数", ascending=False)
        print(f"\n异常点摘要 (Top 10):")
        display_cols = ["原始值", "投票数", "综合异常分数", "偏离均值倍数", "分位数"]
        print(anomalies[display_cols].head(10).to_string())

    if pct > contamination * 100:
        print(f"\n[警告] 异常占比 {pct:.1f}% 超过预期上限 {contamination*100:.1f}%，建议检查数据质量或调整阈值")

    return result


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="单变量异常检测：3-Sigma + IQR + MAD投票法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python univariate_anomaly.py -i sales.csv -c revenue
  python univariate_anomaly.py -i data.xlsx -c temperature --threshold 2 -o anomalies.csv
  python univariate_anomaly.py -i data.csv -c value --contamination 0.03 --grubbs-alpha 0.01
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("-c", "--column", required=True, help="待检测的数值列名")
    parser.add_argument("-o", "--output", default="univariate_anomaly_result.csv", help="输出CSV文件路径")
    parser.add_argument("--threshold", type=int, default=2, help="投票阈值，>=该值判定为异常 (默认: 2)")
    parser.add_argument("--contamination", type=float, default=0.05, help="预期异常比例上限 (默认: 0.05)")
    parser.add_argument("--grubbs-alpha", type=float, default=0.05, help="Grubbs检验显著性水平 (默认: 0.05)")

    args = parser.parse_args()

    # 加载数据
    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    if args.column not in df.columns:
        print(f"[错误] 列 '{args.column}' 不存在。可用列: {list(df.columns)}")
        sys.exit(1)

    if not np.issubdtype(df[args.column].dtype, np.number):
        print(f"[错误] 列 '{args.column}' 不是数值类型 (当前: {df[args.column].dtype})")
        sys.exit(1)

    # 执行检测
    result = univariate_anomaly(
        df[args.column],
        contamination=args.contamination,
        vote_threshold=args.threshold,
        grubbs_alpha=args.grubbs_alpha
    )

    if len(result) > 0:
        # 合并原始数据
        output = df.copy()
        for col in ["是否异常", "综合异常分数", "投票数", "偏离均值倍数", "分位数"]:
            if col in result.columns:
                output[col] = result[col]

        output.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    main()
