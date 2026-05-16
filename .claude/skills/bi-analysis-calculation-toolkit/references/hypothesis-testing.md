---
name: hypothesis-testing
description: 假设检验 Skill，严格验证差异是否真实存在。覆盖双样本检验（t/Mann-Whitney自动选择）、方差分析（ANOVA/Welch/Kruskal-Wallis + 事后检验）、独立性检验（卡方/Fisher）、统计功效与样本量计算。支持多重比较校正和 Bootstrap 置信区间。
---

# 假设检验

## Skill概述

用统计学方法严格回答"差异是真实的，还是随机误差"，支持以下检验模块：

1. **双样本检验**：自动根据正态性和方差齐性选择 t 检验或 Mann-Whitney U 检验，计算效应量和置信区间，附带 Bootstrap 置信区间作为非参数替代
2. **方差分析（ANOVA）**：单因素 ANOVA + Tukey HSD 事后检验，支持 Welch ANOVA（方差不齐时）和 Kruskal-Wallis（非参数替代），多重比较自动校正（Bonferroni / Benjamini-Hochberg）
3. **独立性检验**：卡方检验 / Fisher 精确检验，计算 Cramer's V 关联强度
4. **统计功效分析**：给定效应量和显著性水平，计算所需样本量；给定样本量计算检验功效

## 输入

- **数据集**（必选）：CSV 或 Excel 文件
- **分组变量**（必选）：用于分组的列名
- **结果变量**（必选）：数值型或分类型列名
- 显著性水平 alpha（可选）：默认 0.05
- 检验方向（可选）：双尾/单尾，默认双尾

## 工作流程

### 步骤一：双样本检验

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

**脚本功能**：
- 自动检测正态性（Shapiro-Wilk / D'Agostino-Pearson）
- 自动检测方差齐性（Levene 检验）
- 正态 + 等方差 -> 独立样本 t 检验；正态 + 不等方差 -> Welch t 检验；非正态 -> Mann-Whitney U
- 计算效应量 Cohen's d
- 计算均值差的参数置信区间和 Bootstrap 置信区间（非参数）
- 输出完整检验报告

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/two_sample_test.py" <数据文件> \
  --group-col <分组列> --target-col <目标列> \
  [--alpha 0.05] [--bootstrap-n 10000] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：`two_sample_test.csv`

### 步骤二：方差分析

通过 Bash 工具执行：

**脚本功能**：
- 单因素 ANOVA（方差齐时）或 Welch ANOVA（方差不齐时）
- Kruskal-Wallis 非参数检验（非正态时）
- Tukey HSD 事后检验（定位具体差异组对）
- 支持 Bonferroni 和 Benjamini-Hochberg 多重比较校正

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/anova_test.py" <数据文件> \
  --group-col <分组列> --target-col <目标列> \
  [--alpha 0.05] [--correction bonferroni] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `anova_results.csv`：ANOVA 检验摘要
- `posthoc_results.csv`：事后检验成对比较结果

### 步骤三：独立性检验

通过 Bash 工具执行：

**脚本功能**：
- 自动选择卡方检验或 Fisher 精确检验（期望频数 < 5 且为 2x2 表时）
- 计算 Cramer's V 关联强度
- 输出交叉表及行/列百分比

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/independence_test.py" <数据文件> \
  --var1 <变量1> --var2 <变量2> \
  [--alpha 0.05] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：`independence_test.csv`

### 步骤四：统计功效与样本量分析

通过 Bash 工具执行：

**脚本功能**：
- 给定效应量 + alpha + 样本量 -> 计算功效（power）
- 给定效应量 + alpha + 目标功效 -> 计算所需样本量
- 支持 t 检验、ANOVA、卡方检验三种场景
- 输出功效曲线数据（样本量 vs 功效的数值表）

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/power_analysis.py" \
  --test-type ttest --effect-size 0.5 --alpha 0.05 \
  [--power 0.8] [--n-per-group 50] [--n-groups 2] \
  [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：`power_analysis.csv`

## 核心输出物

1. **检验报告**：检验方法、统计量、P 值、置信区间、效应量（CSV + 控制台）
2. **事后检验表**：成对比较结果 + 校正后 P 值（CSV）
3. **功效分析表**：所需样本量或当前功效（CSV）
4. **文字结论**：显著性判定 + 效应大小评估 + 实际意义解读

## 质量检验标准

- 样本量 < 30 时自动切换非参数检验，并注明结论需谨慎
- 多重比较时使用 Bonferroni 或 BH 校正，防止假阳性膨胀
- P 值显著但效应量极小（Cohen's d < 0.1）时注明统计显著但实际意义有限
- Bootstrap 置信区间与参数置信区间应大致一致（差异过大需警示）
- 功效分析中 power < 0.8 时提示样本量不足风险
- 自检：按以上标准逐项验证输出结果
