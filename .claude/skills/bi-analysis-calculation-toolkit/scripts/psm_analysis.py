#!/usr/bin/env python3
"""
倾向得分匹配（PSM）分析脚本

基于 Abadie & Imbens (2006) "Large Sample Properties of Matching Estimators
for Average Treatment Effects" (Econometrica, Vol. 74, No. 1) 实现。

功能：
  - 使用逻辑回归计算倾向得分
  - 支持 1:M 最近邻有放回匹配（matching with replacement），M 可配置
  - caliper 自动设定为 factor * SD(倾向得分)，默认 factor=0.2
  - 支持 ATE（平均处理效应）和 ATT（处理组平均处理效应）两种估计量
  - 偏差修正匹配估计器（Bias-Corrected Matching Estimator, Abadie & Imbens 2002）
  - Abadie-Imbens 方差估计器：基于同组匹配估计条件方差 σ²(x,w)，
    不依赖一致的非参数估计（Theorem 6 & 7）
  - KM(i) 匹配权重计算，用于正确估计方差
  - 匹配后平衡检验：计算各协变量的标准化均值差异（SMD）
  - 协变量维度偏差警告：当连续协变量维度 k≥2 时，匹配偏差可能不是 N^{-1/2} 阶
    （Theorem 1），建议启用偏差修正
  - Bootstrap 失效警告（Abadie & Imbens 2005）

用法：
  python psm_analysis.py <数据文件> \\
    --treat-col <处理标识列> --outcome-col <结果变量列> \\
    --covariates <协变量1> <协变量2> ... \\
    [--n-matches 1] [--caliper-factor 0.2] [--alpha 0.05] \\
    [--estimand ATE|ATT] [--bias-correction] [--output-dir <输出目录>]

参考文献：
  Abadie, A. and Imbens, G.W. (2006). "Large Sample Properties of Matching
  Estimators for Average Treatment Effects." Econometrica, 74(1), 235-267.
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


def compute_smd(treat_vals, control_vals):
    """计算标准化均值差异（SMD）"""
    mean_diff = treat_vals.mean() - control_vals.mean()
    pooled_std = np.sqrt((treat_vals.std()**2 + control_vals.std()**2) / 2)
    if pooled_std == 0:
        return 0.0
    return mean_diff / pooled_std


def _find_m_nearest_matches(ps_i, ps_pool, pool_indices, M, caliper):
    """
    为单个单元找到 M 个最近邻匹配（有放回）。

    参数：
      ps_i:          当前单元的倾向得分
      ps_pool:       候选匹配池的倾向得分数组
      pool_indices:  候选匹配池的原始索引列表
      M:             匹配数量
      caliper:       caliper 阈值，None 表示无限制

    返回：
      list — 匹配到的索引列表（长度 ≤ M）
    """
    distances = np.abs(ps_pool - ps_i)
    sorted_order = np.argsort(distances)

    matches = []
    for idx in sorted_order:
        if len(matches) >= M:
            break
        if caliper is not None and distances[idx] > caliper:
            break
        matches.append(pool_indices[idx])
    return matches


def _compute_km(matched_sets, N):
    """
    计算 KM(i)：每个单元被用作匹配的次数。

    基于 Abadie & Imbens (2006) 第240页定义：
    KM(i) = Σ_{l=1}^{N} 1{i ∈ JM(l)}

    参数：
      matched_sets: dict, 键为单元索引 i，值为其匹配集合 JM(i) 的索引列表
      N:            总样本量

    返回：
      dict — 每个单元的 KM(i) 值
    """
    km = {}
    # 初始化所有出现在匹配集合中的单元
    all_indices = set()
    for idx, match_list in matched_sets.items():
        all_indices.add(idx)
        for m_idx in match_list:
            all_indices.add(m_idx)

    for idx in all_indices:
        km[idx] = 0

    for idx, match_list in matched_sets.items():
        for m_idx in match_list:
            km[m_idx] = km.get(m_idx, 0) + 1

    return km


def _estimate_conditional_variance(df, outcome_col, treat, covariates, J=1):
    """
    使用同组最近邻匹配估计条件方差 σ²(Xi, Wi)。

    基于 Abadie & Imbens (2006) Theorem 6, 公式(14)：
    σ̂²(Xi, Wi) = (J/(J+1)) * (Yi - (1/J) Σ Y_{ℓ_j(i)})²

    不同于原始公式的精确形式，这里使用简化的匹配方差估计：
    对每个单元 i，在同组（Wi 相同的单元）中找到 J 个最近邻，
    用这 J+1 个观测值的方差作为条件方差的估计。

    参数：
      df:           DataFrame
      outcome_col:  结果变量列名
      treat:        处理变量 Series
      covariates:   协变量列名列表
      J:            同组匹配的邻居数量（默认1）

    返回：
      np.array — 每个单元的条件方差估计值
    """
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    X = df[covariates].values.astype(float)
    Y = df[outcome_col].values.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    sigma2_hat = np.zeros(len(df))

    for w in [0, 1]:
        mask = (treat == w).values
        if mask.sum() <= J:
            # 样本不足时使用组内方差
            sigma2_hat[mask] = np.var(Y[mask], ddof=1) if mask.sum() > 1 else 0
            continue

        X_w = X_scaled[mask]
        Y_w = Y[mask]
        indices_w = np.where(mask)[0]

        nn = NearestNeighbors(n_neighbors=J + 1, algorithm='auto')
        nn.fit(X_w)
        _, nn_indices = nn.kneighbors(X_w)

        for local_i in range(len(X_w)):
            # nn_indices[local_i] 包含自身（第0个），取第1到J个
            neighbor_local_indices = nn_indices[local_i, 1:J + 1]
            y_values = np.concatenate([[Y_w[local_i]], Y_w[neighbor_local_indices]])
            # σ̂²(Xi, Wi) 的无偏估计
            sigma2_hat[indices_w[local_i]] = np.var(y_values, ddof=1)

    return sigma2_hat


def psm_analysis(df, treat_col, outcome_col, covariates, n_matches=1,
                 caliper_factor=0.2, alpha=0.05, estimand='ATT',
                 bias_correction=False):
    """
    倾向得分匹配分析（基于 Abadie & Imbens 2006）。

    参数：
      df:              DataFrame
      treat_col:       处理标识列（1=处理组, 0=对照组）
      outcome_col:     结果变量列
      covariates:      协变量列名列表
      n_matches:       每个单元的匹配数量 M（默认1）
      caliper_factor:  caliper 系数（caliper = factor * SD(倾向得分)）
      alpha:           显著性水平
      estimand:        估计量类型，'ATE' 或 'ATT'
      bias_correction: 是否启用偏差修正（建议连续协变量 ≥2 时启用）

    返回：
      dict — PSM分析结果, DataFrame — 平衡检验结果
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    df = df.copy().reset_index(drop=True)
    df = df.dropna(subset=[treat_col, outcome_col] + covariates).reset_index(drop=True)

    # 数据规模检查
    if len(df) > 100000:
        print(f"[警告] 总样本量 ({len(df)}) 超过 100,000，PSM 匹配过程可能耗时较长且占用大量内存，"
              f"建议考虑对数据进行抽样后再分析")

    treat = df[treat_col].astype(int)
    X = df[covariates].astype(float)
    Y = df[outcome_col].astype(float).values
    N = len(df)
    N1 = treat.sum()
    N0 = N - N1
    k = len(covariates)  # 协变量维度

    print(f"\n{'='*70}")
    print(f"  倾向得分匹配（PSM）分析")
    print(f"  方法：Abadie & Imbens (2006) 匹配估计器")
    print(f"{'='*70}")
    print(f"  估计量: {estimand}")
    print(f"  匹配数 M: {n_matches}")
    print(f"  偏差修正: {'是' if bias_correction else '否'}")
    print(f"  处理组样本 (N1): {N1}")
    print(f"  对照组样本 (N0): {N0}")
    print(f"  协变量: {covariates}")
    print(f"  协变量维度 k: {k}")

    # ---- 协变量维度偏差警告（Theorem 1）----
    if k >= 2:
        print(f"\n  ⚠ 维度警告（Theorem 1, Abadie & Imbens 2006）：")
        print(f"    连续协变量维度 k={k} ≥ 2，匹配偏差的阶为 Op(N^{{-1/k}})，")
        print(f"    可能大于 N^{{-1/2}}，简单匹配估计器可能不是 √N-一致的。")
        if not bias_correction:
            print(f"    建议启用 --bias-correction 进行偏差修正。")

    # ---- Bootstrap 失效警告 ----
    print(f"\n  ⚠ Bootstrap 警告（Abadie & Imbens 2005）：")
    print(f"    标准 Bootstrap 对固定匹配数的匹配估计器无效，")
    print(f"    本脚本使用 Abadie-Imbens 解析方差估计器。")

    # ---- 计算倾向得分 ----
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_scaled, treat)
    ps = lr.predict_proba(X_scaled)[:, 1]
    df['propensity_score'] = ps

    print(f"\n  -- 倾向得分分布 --")
    print(f"  处理组: 均值={ps[treat==1].mean():.4f}, "
          f"标准差={ps[treat==1].std():.4f}")
    print(f"  对照组: 均值={ps[treat==0].mean():.4f}, "
          f"标准差={ps[treat==0].std():.4f}")

    # ---- 1:M 最近邻有放回匹配 ----
    caliper = caliper_factor * ps.std() if caliper_factor > 0 else None
    if caliper is not None:
        print(f"\n  Caliper = {caliper_factor} × SD(PS) = {caliper:.4f}")
    else:
        print(f"\n  Caliper: 无限制")

    # 确定需要匹配的单元
    if estimand == 'ATE':
        # ATE: 所有单元都需要匹配（处理组匹配对照组，对照组匹配处理组）
        units_to_match = list(range(N))
    else:
        # ATT: 仅处理组单元需要匹配
        units_to_match = list(df[treat == 1].index)

    # 构建匹配池
    treat_indices = np.where(treat == 1)[0]
    control_indices = np.where(treat == 0)[0]
    ps_treat = ps[treat_indices]
    ps_control = ps[control_indices]

    # 执行匹配
    matched_sets = {}  # {i: [matched indices]}
    unmatched_count = 0

    for i in units_to_match:
        w_i = treat.iloc[i]
        if w_i == 1:
            pool_indices = control_indices
            pool_ps = ps_control
        else:
            pool_indices = treat_indices
            pool_ps = ps_treat

        matches = _find_m_nearest_matches(ps[i], pool_ps, pool_indices,
                                          n_matches, caliper)
        if len(matches) > 0:
            matched_sets[i] = matches
        else:
            unmatched_count += 1

    matched_count = len(matched_sets)
    total_to_match = len(units_to_match)
    match_rate = matched_count / total_to_match * 100 if total_to_match > 0 else 0

    print(f"\n  匹配结果: {matched_count}/{total_to_match} 个单元完成匹配"
          f"（匹配率 {match_rate:.1f}%）")
    print(f"  未匹配单元: {unmatched_count}")

    if match_rate < 50:
        print(f"  ⚠ 警告: 匹配率低于 50%，结论可靠性受限")

    if matched_count == 0:
        print(f"  错误：无法完成匹配，请检查数据或放宽 caliper")
        return None, None

    # ---- 计算 KM(i) ----
    km = _compute_km(matched_sets, N)

    # ---- 匹配后平衡检验 ----
    print(f"\n  -- 匹配后平衡检验（SMD）--")

    # 获取匹配后的处理组和对照组索引（带权重）
    if estimand == 'ATT':
        treat_matched_idx = [i for i in matched_sets.keys()]
        # 对照组：所有被匹配到的对照单元（可能重复）
        control_matched_list = []
        for i in treat_matched_idx:
            control_matched_list.extend(matched_sets[i])
        control_matched_idx = list(set(control_matched_list))
    else:
        treat_matched_idx = [i for i in matched_sets.keys() if treat.iloc[i] == 1]
        control_matched_idx = [i for i in matched_sets.keys() if treat.iloc[i] == 0]
        # 补充被匹配到的对照和处理单元
        for i in matched_sets:
            for j in matched_sets[i]:
                if treat.iloc[j] == 0 and j not in control_matched_idx:
                    control_matched_idx.append(j)
                elif treat.iloc[j] == 1 and j not in treat_matched_idx:
                    treat_matched_idx.append(j)

    balance_results = []
    all_balanced = True

    for cov in covariates:
        smd_before = compute_smd(
            df.loc[treat == 1, cov],
            df.loc[treat == 0, cov]
        )
        smd_after = compute_smd(
            df.loc[treat_matched_idx, cov],
            df.loc[control_matched_idx, cov]
        )
        is_balanced = abs(smd_after) < 0.1
        if not is_balanced:
            all_balanced = False
        balance_results.append({
            "协变量": cov,
            "匹配前SMD": round(abs(smd_before), 4),
            "匹配后SMD": round(abs(smd_after), 4),
            "平衡": "是" if is_balanced else "否"
        })

    balance_df = pd.DataFrame(balance_results)
    print(balance_df.to_string(index=False))

    if all_balanced:
        print(f"  所有协变量 SMD < 0.1，匹配后平衡良好")
    else:
        unbalanced = balance_df[balance_df["平衡"] == "否"]["协变量"].tolist()
        print(f"  ⚠ 警告: 以下协变量 SMD > 0.1，匹配后仍不平衡: {unbalanced}")

    # ---- 偏差修正（Bias-Corrected Matching Estimator）----
    # 基于 Abadie & Imbens (2002) 工作论文中的偏差修正方法
    # 使用线性回归估计 μ_w(x)，用于修正匹配偏差
    bias_adjust = np.zeros(N)
    if bias_correction:
        print(f"\n  -- 偏差修正 --")
        from sklearn.linear_model import LinearRegression

        for w in [0, 1]:
            mask = (treat == w).values
            X_w = X.values[mask]
            Y_w = Y[mask]

            if len(X_w) > k + 1:
                reg = LinearRegression().fit(X_w, Y_w)
                # 对每个被匹配的单元计算偏差修正量
                for i in matched_sets:
                    if treat.iloc[i] != w:  # i 的对立组是 w
                        for j in matched_sets[i]:
                            # 修正量 = μ̂_w(Xi) - μ̂_w(Xj)
                            mu_xi = reg.predict(X.values[i:i+1])[0]
                            mu_xj = reg.predict(X.values[j:j+1])[0]
                            bias_adjust[i] += (mu_xi - mu_xj) / len(matched_sets[i])

        print(f"  偏差修正量: 均值={bias_adjust[list(matched_sets.keys())].mean():.6f}, "
              f"标准差={bias_adjust[list(matched_sets.keys())].std():.6f}")

    # ---- 计算处理效应 ----
    print(f"\n  -- {estimand} 估计 --")

    if estimand == 'ATT':
        # ATT 估计器（公式4）：
        # τ̂_M^t = (1/N1) Σ_i [Wi - (1-Wi)·KM(i)/M] · Yi
        att_sum = 0.0
        for i in range(N):
            w_i = treat.iloc[i]
            km_i = km.get(i, 0)
            att_sum += (w_i - (1 - w_i) * km_i / n_matches) * Y[i]
        tau_hat = att_sum / N1

        # 加入偏差修正
        if bias_correction:
            bc_sum = 0.0
            for i in matched_sets:
                bc_sum += bias_adjust[i]
            tau_hat += bc_sum / N1

        # ---- Abadie-Imbens 方差估计（Theorem 7 for ATT）----
        # V̂^t 的估计
        sigma2_hat = _estimate_conditional_variance(
            df, outcome_col, treat, covariates, J=min(n_matches, max(1, N0 // 10))
        )

        # 构造反事实估计 Ŷi(0)
        Y_hat_0 = np.zeros(N)
        for i in matched_sets:
            Y_hat_0[i] = np.mean(Y[matched_sets[i]])

        # 方法1：直接使用 Theorem 7 的 V^t 公式
        # V^t = (1/N1) Σ_i (Yi - Ŷi(0) - τ̂)² + (1/N1) Σ_i (1-Wi)·KM(i)·(KM(i)-1)/M² · σ̂²
        term1 = 0.0
        for i in matched_sets:
            diff = Y[i] - Y_hat_0[i] - tau_hat
            term1 += diff**2
        term1 /= N1

        term2 = 0.0
        for i in range(N):
            if treat.iloc[i] == 0:
                km_i = km.get(i, 0)
                term2 += km_i * (km_i - 1) / (n_matches**2) * sigma2_hat[i]
        term2 /= N1

        variance_hat = (term1 + term2) / N1
        se = np.sqrt(max(variance_hat, 1e-16))

    else:
        # ATE 估计器（公式3）：
        # τ̂_M = (1/N) Σ_i (2Wi-1)·(1 + KM(i)/M)·Yi
        ate_sum = 0.0
        for i in range(N):
            w_i = treat.iloc[i]
            km_i = km.get(i, 0)
            ate_sum += (2 * w_i - 1) * (1 + km_i / n_matches) * Y[i]
        tau_hat = ate_sum / N

        # 加入偏差修正
        if bias_correction:
            bc_sum = 0.0
            for i in matched_sets:
                w_i = treat.iloc[i]
                bc_sum += (2 * w_i - 1) * bias_adjust[i]
            tau_hat += bc_sum / N

        # ---- Abadie-Imbens 方差估计（Theorem 7 for ATE）----
        sigma2_hat = _estimate_conditional_variance(
            df, outcome_col, treat, covariates, J=min(n_matches, max(1, min(N0, N1) // 10))
        )

        # 构造反事实估计
        Y_hat_0 = np.zeros(N)
        Y_hat_1 = np.zeros(N)
        for i in matched_sets:
            match_mean = np.mean(Y[matched_sets[i]])
            if treat.iloc[i] == 1:
                Y_hat_1[i] = Y[i]
                Y_hat_0[i] = match_mean
            else:
                Y_hat_0[i] = Y[i]
                Y_hat_1[i] = match_mean

        # V̂ = (1/N) Σ_i (Ŷi(1) - Ŷi(0) - τ̂)²
        #    + (1/N) Σ_i ((KM(i)/M)² + (2M-1)/M · KM(i)/M) · σ̂²(Xi,Wi)
        term1 = 0.0
        for i in matched_sets:
            diff = Y_hat_1[i] - Y_hat_0[i] - tau_hat
            term1 += diff**2
        term1 /= N

        term2 = 0.0
        for i in range(N):
            km_i = km.get(i, 0)
            term2 += ((km_i / n_matches)**2
                      + (2 * n_matches - 1) / n_matches * km_i / n_matches) \
                     * sigma2_hat[i]
        term2 /= N

        variance_hat = (term1 + term2) / N
        se = np.sqrt(max(variance_hat, 1e-16))

    # ---- 统计推断 ----
    t_stat = tau_hat / se if se > 0 else 0
    # 使用正态近似（大样本）
    p_value = 2 * (1 - stats.norm.cdf(abs(t_stat)))
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci_low = tau_hat - z_crit * se
    ci_high = tau_hat + z_crit * se
    is_significant = p_value < alpha

    print(f"  {estimand}: {tau_hat:.4f}")
    print(f"  Abadie-Imbens 标准误: {se:.4f}")
    print(f"  z 统计量: {t_stat:.4f}")
    print(f"  P 值: {p_value:.6f}")
    print(f"  {int((1-alpha)*100)}% 置信区间: [{ci_low:.4f}, {ci_high:.4f}]")

    if is_significant:
        direction = "正向" if tau_hat > 0 else "负向"
        print(f"\n  结论: 处理效应统计显著（p < {alpha}），{direction}效应 {abs(tau_hat):.4f}")
    else:
        print(f"\n  结论: 处理效应不显著（p >= {alpha}）")

    # ---- KM(i) 分布摘要 ----
    km_values = [km.get(i, 0) for i in range(N) if treat.iloc[i] == 0]
    if km_values:
        km_arr = np.array(km_values)
        print(f"\n  -- KM(i) 匹配权重分布（对照组）--")
        print(f"  均值: {km_arr.mean():.2f}, 最大值: {km_arr.max()}, "
              f"标准差: {km_arr.std():.2f}")
        print(f"  从未被匹配的对照单元: {(km_arr == 0).sum()} / {len(km_arr)}")

    if estimand == 'ATE':
        km_values_t = [km.get(i, 0) for i in range(N) if treat.iloc[i] == 1]
        if km_values_t:
            km_arr_t = np.array(km_values_t)
            print(f"\n  -- KM(i) 匹配权重分布（处理组）--")
            print(f"  均值: {km_arr_t.mean():.2f}, 最大值: {km_arr_t.max()}, "
                  f"标准差: {km_arr_t.std():.2f}")
            print(f"  从未被匹配的处理单元: {(km_arr_t == 0).sum()} / {len(km_arr_t)}")

    # ---- 效率讨论（Theorem 5, 仅 k=1 时）----
    if k == 1 and estimand == 'ATE':
        eff_loss_bound = 1 / (2 * n_matches)
        print(f"\n  -- 效率参考（Theorem 5, k=1）--")
        print(f"  相对于半参数效率界的渐近方差损失上界: < {eff_loss_bound:.1%}")
        if n_matches == 1:
            print(f"  提示: M=1 时效率损失 < 50%；增加匹配数 M 可减少效率损失")

    # ---- 组装结果 ----
    result = {
        "估计量": estimand,
        f"{estimand}": round(tau_hat, 4),
        "AI标准误": round(se, 4),
        "z统计量": round(t_stat, 4),
        "P值": round(p_value, 6),
        "CI下界": round(ci_low, 4),
        "CI上界": round(ci_high, 4),
        "匹配数M": n_matches,
        "匹配单元数": matched_count,
        "匹配率": round(match_rate, 2),
        "偏差修正": "是" if bias_correction else "否",
        "显著性": "显著" if is_significant else "不显著",
        "所有协变量平衡": "是" if all_balanced else "否",
        "协变量维度k": k,
        "方差估计方法": "Abadie-Imbens (2006)"
    }

    return result, balance_df


def main():
    parser = argparse.ArgumentParser(
        description="倾向得分匹配（PSM）分析 — 基于 Abadie & Imbens (2006)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data_file", help="数据文件路径（CSV 或 Excel）")
    parser.add_argument("--treat-col", required=True, help="处理标识列（1=处理, 0=对照）")
    parser.add_argument("--outcome-col", required=True, help="结果变量列")
    parser.add_argument("--covariates", required=True, nargs="+", help="协变量列名列表")
    parser.add_argument("--n-matches", type=int, default=1,
                        help="每个单元的匹配数量 M（默认 1）")
    parser.add_argument("--caliper-factor", type=float, default=0.2,
                        help="Caliper 系数（默认 0.2，设为 0 表示无 caliper）")
    parser.add_argument("--alpha", type=float, default=0.05, help="显著性水平")
    parser.add_argument("--estimand", choices=['ATE', 'ATT'], default='ATT',
                        help="估计量类型：ATE（平均处理效应）或 ATT（处理组平均处理效应，默认）")
    parser.add_argument("--bias-correction", action='store_true',
                        help="启用偏差修正（建议协变量维度 ≥2 时使用）")
    parser.add_argument("--output-dir", default=".", help="输出目录")

    args = parser.parse_args()

    df = load_data(args.data_file)
    print(f"已加载数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    required_cols = [args.treat_col, args.outcome_col] + args.covariates
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误：以下列名不存在: {missing}")
        print(f"可用列名: {list(df.columns)}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    result, balance_df = psm_analysis(
        df, args.treat_col, args.outcome_col, args.covariates,
        n_matches=args.n_matches,
        caliper_factor=args.caliper_factor,
        alpha=args.alpha,
        estimand=args.estimand,
        bias_correction=args.bias_correction
    )

    if result is not None:
        result_df = pd.DataFrame([result])
        out_path = os.path.join(args.output_dir, "psm_result.csv")
        result_df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"\nPSM结果已保存至: {out_path}")

        balance_path = os.path.join(args.output_dir, "psm_balance.csv")
        balance_df.to_csv(balance_path, index=False, encoding='utf-8-sig')
        print(f"平衡检验结果已保存至: {balance_path}")


if __name__ == "__main__":
    main()
