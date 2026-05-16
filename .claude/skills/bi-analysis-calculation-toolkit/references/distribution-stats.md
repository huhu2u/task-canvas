---
name: distribution-stats
description: 统计分布特征分析 Skill，覆盖集中趋势、离散程度、分布形态、正态性检验、分布拟合和分组对比，输出结构化统计报告。
---

# 统计分布特征分析（distribution-stats）

## Skill概述

用统计指标全面描述数据的分布特征，覆盖集中趋势、离散程度和分布形态三个维度。支持多种正态性检验方法、bootstrap 置信区间估计、参数分布拟合（含 AIC 模型比较），以及按分组列进行对比分析。所有结果以 CSV 和控制台文本形式输出。

## 输入

- **数据文件**：CSV 或 Excel 格式的数据集路径
- **目标列**：一个或多个数值型字段名（逗号分隔）
- 可选参数：
  - 分组列（按该列分组后分别计算统计量）
  - bootstrap 重采样次数（默认 1000）
  - 置信水平（默认 0.95）
  - 输出目录

## 工作流程

### 第一步：综合分布分析

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/distribution_analysis.py" --input "<数据文件>" --columns "<列1>,<列2>" [--group-by <分组列>] [--bootstrap-n 1000] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

对每个目标列计算：
- **集中趋势**：算术均值、中位数、众数、截尾均值（5%）
- **离散程度**：方差、标准差、变异系数 CV、平均绝对偏差 MAD、IQR
- **分布形态**：偏度、峰度（超额峰度）、分位数序列（P1/P5/P10/P25/P50/P75/P90/P95/P99）
- **正态性检验**：Shapiro-Wilk、Anderson-Darling、KS、Jarque-Bera 四种方法
- **Bootstrap 置信区间**：均值和中位数的 bootstrap CI
- **参数分布拟合**：Normal/Lognormal/Exponential/Gamma 的 AIC 比较

### 第二步：统计摘要

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/stats_summary.py" --input "<数据文件>" [--columns "<列1>,<列2>"] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

生成精简的统计摘要报告：
- 各列的核心统计量一览表（均值、中位数、标准差、偏度、峰度）
- 异常值检测统计（IQR 方法）
- 数据质量概览（缺失率、唯一值数）

### 第三步：正态性专项检验

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/normality_test.py" --input "<数据文件>" [--columns "<列1>,<列2>"] [--alpha 0.05] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

执行正态性深度检验：
- **Shapiro-Wilk 检验**：适合中小样本（N < 5000）
- **Anderson-Darling 检验**：对尾部偏离更敏感
- **Kolmogorov-Smirnov 检验**：与标准正态分布比较
- **Jarque-Bera 检验**：基于偏度和峰度
- 综合正态性判定（多数投票法）
- 大样本（>5000）自动抽样处理

### 第四步：分组对比分析

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/group_comparison.py" --input "<数据文件>" --columns "<列1>" --group-by <分组列> [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

当指定分组列时：
- 按组分别计算所有统计量
- 输出各组的统计对比表
- 标记组间差异最大的指标
- 自动选择检验方法（参数/非参数）

### 第五步：边界情况处理

所有脚本自动处理以下边界情况：
- 全部为 NaN 的列：跳过并警告
- 仅单一值的列：仅输出该值，跳过分布检验
- 极端离群值：报告 IQR 异常值数量和占比
- 样本量不足（< 8）：跳过 Shapiro-Wilk 等需要最小样本量的检验
- 大样本（> 5000）：自动抽样以加速计算

## 核心输出物

1. **统计摘要表**（CSV + 控制台）：每个字段的集中趋势 + 离散度 + 形态指标
2. **正态性检验结果**（CSV）：各检验方法的统计量、p 值、判断结论
3. **Bootstrap 置信区间**（CSV）：均值和中位数的区间估计
4. **分布拟合结果**（CSV）：各候选分布的参数和 AIC 排序
5. **分组对比表**（CSV，可选）：各组的统计量对比

## 质量检验标准

- 偏度方向与均值-中位数关系一致（右偏时均值 > 中位数）
- 变异系数 CV 在均值接近 0 时标记为不适用
- 正态性检验至少使用 2 种方法交叉验证
- Bootstrap 置信区间宽度应随样本量增大而缩窄
- 分布拟合的 AIC 比较基于相同数据子集
- 全 NaN 和单值列有明确的警告输出
