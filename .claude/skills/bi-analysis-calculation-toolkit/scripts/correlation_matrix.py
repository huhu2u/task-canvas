#!/usr/bin/env python3
"""
相关性矩阵分析脚本
方法：Pearson/Spearman/互信息 + 偏相关
增强：自动正态性检验选择方法、偏相关分析、奇异矩阵处理

用法：
    python correlation_matrix.py -i data.csv -o corr_result.csv
    python correlation_matrix.py -i data.xlsx -c col1 col2 col3 --method auto --threshold 0.7
"""

import argparse
import sys
import warnings
import numpy as np
import pandas as pd
from scipy import stats


def auto_select_method(X):
    """
    基于正态性检验自动选择相关系数方法。
    D'Agostino-Pearson检验，所有列都通过正态性检验时用Pearson，否则用Spearman。

    Args:
        X: pd.DataFrame

    Returns:
        str: 'pearson' 或 'spearman'
    """
    all_normal = True
    for col in X.columns:
        col_data = X[col].dropna()
        if len(col_data) < 20:
            # 样本太少，正态性检验不可靠
            all_normal = False
            break
        try:
            _, p_value = stats.normaltest(col_data)
            if p_value < 0.05:
                all_normal = False
                break
        except Exception:
            all_normal = False
            break

    method = "pearson" if all_normal else "spearman"
    print(f"[信息] 正态性检验 -> 自动选择: {method}")
    return method


def compute_mutual_information(X):
    """
    计算互信息矩阵。

    Args:
        X: pd.DataFrame，数值列

    Returns:
        pd.DataFrame: 互信息矩阵
    """
    try:
        from sklearn.feature_selection import mutual_info_regression
    except ImportError:
        print("[错误] 互信息计算需要 scikit-learn: pip install scikit-learn")
        return None

    cols = X.columns.tolist()
    n = len(cols)

    if n > 100:
        print(f"[警告] 特征数({n})超过100，互信息计算复杂度为 O(p²×n)，可能耗时较长")

    # 当数据行数>50000时抽样计算互信息
    if len(X) > 50000:
        print(f"[信息] 数据行数({len(X)})超过50000，抽样50000行计算互信息")
        X = X.sample(n=50000, random_state=42).reset_index(drop=True)

    mi_matrix = pd.DataFrame(np.zeros((n, n)), index=cols, columns=cols)

    for i, col in enumerate(cols):
        other_cols = [c for c in cols if c != col]
        if len(other_cols) == 0:
            continue
        X_other = X[other_cols].values
        y = X[col].values

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mi_scores = mutual_info_regression(X_other, y, random_state=42)

        for j, other_col in enumerate(other_cols):
            mi_matrix.loc[col, other_col] = mi_scores[j]
        mi_matrix.loc[col, col] = 1.0

    # 对称化（取两方向的平均）
    mi_matrix = (mi_matrix + mi_matrix.T) / 2
    np.fill_diagonal(mi_matrix.values, 1.0)

    return mi_matrix


def compute_partial_correlation(X):
    """
    计算偏相关矩阵：控制所有其他变量后两个变量的净相关。

    Args:
        X: pd.DataFrame

    Returns:
        pd.DataFrame or None: 偏相关矩阵
    """
    cols = X.columns.tolist()
    n = len(cols)

    if n < 3:
        print("[信息] 偏相关需要至少3个变量")
        return None

    # 计算相关矩阵
    corr = X.corr()

    # 求精度矩阵（相关矩阵的逆）
    try:
        corr_inv = np.linalg.inv(corr.values)
    except np.linalg.LinAlgError:
        print("[警告] 相关矩阵奇异，尝试使用伪逆计算偏相关")
        try:
            corr_inv = np.linalg.pinv(corr.values)
        except Exception:
            print("[错误] 无法计算偏相关矩阵")
            return None

    # 偏相关 = -P_ij / sqrt(P_ii * P_jj)
    d = np.sqrt(np.diag(corr_inv))
    d[d == 0] = 1  # 防止除零

    partial_corr = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                partial_corr[i, j] = 1.0
            else:
                partial_corr[i, j] = -corr_inv[i, j] / (d[i] * d[j])

    return pd.DataFrame(partial_corr, index=cols, columns=cols)


def find_strong_correlations(corr_matrix, threshold=0.7):
    """找出强相关字段对"""
    cols = corr_matrix.columns.tolist()
    strong_pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr_matrix.iloc[i, j]
            if abs(r) > threshold:
                if r > threshold:
                    strength = "强正相关"
                elif r < -threshold:
                    strength = "强负相关"
                else:
                    strength = "强相关"
                strong_pairs.append({
                    "字段A": cols[i],
                    "字段B": cols[j],
                    "相关系数": round(r, 4),
                    "强度": strength
                })
    return pd.DataFrame(strong_pairs)


def correlation_analysis(df, numeric_cols=None, method="auto", threshold=0.7,
                         compute_partial=False, compute_mi=False):
    """
    相关性矩阵分析。

    Args:
        df: pd.DataFrame
        numeric_cols: 指定的数值列（None则自动选择）
        method: 'auto', 'pearson', 'spearman', 'mutual_info'
        threshold: 强相关阈值
        compute_partial: 是否计算偏相关
        compute_mi: 是否计算互信息

    Returns:
        dict: 包含各种相关矩阵和强相关对
    """
    # 选择数值列
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()

    if len(numeric_cols) < 2:
        print(f"[错误] 数值列不足2个 (当前: {len(numeric_cols)})")
        return {}

    # 验证列存在
    missing = [c for c in numeric_cols if c not in df.columns]
    if missing:
        print(f"[错误] 以下列不存在: {missing}")
        return {}

    X = df[numeric_cols].dropna()
    n_dropped = len(df) - len(X)
    if n_dropped > 0:
        print(f"[信息] 因缺失值移除 {n_dropped} 行")

    if len(X) < 5:
        print(f"[错误] 有效样本仅 {len(X)} 行，不足以计算相关性")
        return {}

    # 当数据行数>100000时抽样50000行用于相关矩阵计算
    if len(X) > 100000:
        print(f"[信息] 数据行数({len(X)})超过100000，抽样50000行用于相关矩阵计算")
        X = X.sample(n=50000, random_state=42).reset_index(drop=True)

    print(f"[信息] 分析 {len(numeric_cols)} 个数值列, {len(X)} 行有效数据")

    results = {}

    # === 主相关矩阵 ===
    if method == "mutual_info":
        corr_matrix = compute_mutual_information(X)
        if corr_matrix is None:
            return {}
        actual_method = "mutual_info"
    else:
        if method == "auto":
            actual_method = auto_select_method(X)
        else:
            actual_method = method
        corr_matrix = X.corr(method=actual_method)

    results["correlation_matrix"] = corr_matrix
    results["method"] = actual_method

    print(f"\n=== 相关性矩阵 ({actual_method}) ===")
    print(corr_matrix.round(3).to_string())

    # 验证对称性和对角线
    diag_check = np.allclose(np.diag(corr_matrix.values), 1.0, atol=1e-10)
    sym_check = np.allclose(corr_matrix.values, corr_matrix.values.T, atol=1e-10)
    if not diag_check:
        print("[警告] 对角线元素不全为1.0")
    if not sym_check:
        print("[警告] 矩阵不完全对称")

    # === 强相关对 ===
    strong_pairs = find_strong_correlations(corr_matrix, threshold)
    results["strong_pairs"] = strong_pairs

    if len(strong_pairs) > 0:
        print(f"\n=== 强相关字段对 (|r| > {threshold}) ===")
        print(strong_pairs.to_string(index=False))
    else:
        print(f"\n[信息] 未发现强相关字段对 (|r| > {threshold})")

    # === 偏相关 ===
    if compute_partial:
        print(f"\n=== 偏相关矩阵 ===")
        partial = compute_partial_correlation(X)
        if partial is not None:
            results["partial_correlation"] = partial
            print(partial.round(3).to_string())

            # 偏相关与普通相关的差异
            diff = (corr_matrix - partial).abs()
            max_diff_idx = np.unravel_index(np.argmax(diff.values * (1 - np.eye(len(diff)))),
                                            diff.shape)
            r1 = diff.index[max_diff_idx[0]]
            r2 = diff.columns[max_diff_idx[1]]
            print(f"\n[信息] 偏相关与普通相关差异最大的字段对: {r1} - {r2} "
                  f"(差异: {diff.iloc[max_diff_idx[0], max_diff_idx[1]]:.4f})")

    # === 互信息 ===
    if compute_mi and method != "mutual_info":
        print(f"\n=== 互信息矩阵 ===")
        mi_matrix = compute_mutual_information(X)
        if mi_matrix is not None:
            results["mutual_information"] = mi_matrix
            print(mi_matrix.round(3).to_string())

    return results


def load_data(file_path):
    """加载CSV或Excel数据文件"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    else:
        return pd.read_csv(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="相关性矩阵分析：Pearson/Spearman/互信息/偏相关",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python correlation_matrix.py -i data.csv
  python correlation_matrix.py -i data.xlsx -c price quantity rating --method auto
  python correlation_matrix.py -i data.csv --method spearman --partial --mi --threshold 0.6
        """
    )
    parser.add_argument("-i", "--input", required=True, help="输入数据文件路径 (CSV/Excel)")
    parser.add_argument("-c", "--columns", nargs="+", default=None, help="数值列名（默认: 所有数值列）")
    parser.add_argument("-o", "--output", default="correlation_result.csv", help="输出CSV文件路径")
    parser.add_argument("--method", default="auto",
                        choices=["auto", "pearson", "spearman", "mutual_info"],
                        help="相关系数方法 (默认: auto)")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="强相关判定阈值 (默认: 0.7)")
    parser.add_argument("--partial", action="store_true", help="计算偏相关矩阵")
    parser.add_argument("--mi", action="store_true", help="额外计算互信息矩阵")

    args = parser.parse_args()

    try:
        df = load_data(args.input)
    except Exception as e:
        print(f"[错误] 无法加载文件: {e}")
        sys.exit(1)

    results = correlation_analysis(
        df,
        numeric_cols=args.columns,
        method=args.method,
        threshold=args.threshold,
        compute_partial=args.partial,
        compute_mi=args.mi
    )

    if results:
        # 保存主相关矩阵
        results["correlation_matrix"].to_csv(args.output, encoding="utf-8-sig")
        print(f"\n相关矩阵已保存至: {args.output}")

        # 保存强相关对
        if len(results.get("strong_pairs", pd.DataFrame())) > 0:
            pairs_file = args.output.replace(".csv", "_strong_pairs.csv")
            results["strong_pairs"].to_csv(pairs_file, index=False, encoding="utf-8-sig")
            print(f"强相关对已保存至: {pairs_file}")

        # 保存偏相关矩阵
        if "partial_correlation" in results:
            partial_file = args.output.replace(".csv", "_partial.csv")
            results["partial_correlation"].to_csv(partial_file, encoding="utf-8-sig")
            print(f"偏相关矩阵已保存至: {partial_file}")

        # 保存互信息矩阵
        if "mutual_information" in results:
            mi_file = args.output.replace(".csv", "_mi.csv")
            results["mutual_information"].to_csv(mi_file, encoding="utf-8-sig")
            print(f"互信息矩阵已保存至: {mi_file}")


if __name__ == "__main__":
    main()
