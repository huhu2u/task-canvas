---
name: root-cause
description: 根因分析与模型可解释性 Skill，利用决策树规则提取、SHAP值分析、LIME局部解释和反事实解释，反向解释已发生事件的原因。当用户需要解释预测结果的成因、提取分类规则或做单样本归因时触发此 Skill。
---

# 根因分析与模型可解释性

## Skill概述

利用机器学习模型反向解释已发生事件的原因，回答"为什么是这个结果"。覆盖以下模块：

1. **决策树规则提取**：训练浅层决策树，提取可读的 if-then 规则，支持低置信度规则剪枝，输出结构化 JSON 规则
2. **SHAP 值分析**：全局特征重要性 + 局部单样本归因 + 特征交互值，支持大数据集抽样加速
3. **LIME 局部解释**：对指定样本做局部线性近似解释，附带多次运行稳定性检查
4. **反事实解释**：给定一个预测结果，找出最少需要改变哪些特征才能得到不同预测

## 输入

- **数据集**（必选）：CSV 或 Excel 文件
- **目标变量**（必选）：分类型或连续型列
- **特征列表**（必选）：特征列名
- 需要解释的样本索引（LIME / 反事实时可选）
- 已训练模型（可选）：若未提供则自动训练 RandomForest

## 工作流程

### 步骤一：决策树规则提取

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

**脚本功能**：
- 训练浅层决策树（可控制深度和最小叶节点样本数）
- 提取所有叶节点的 if-then 规则
- 低置信度规则剪枝：移除置信度低于阈值的规则
- 输出规则列表为 CSV 和结构化 JSON 格式
- 输出特征重要性排名

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/decision_tree_rules.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--max-depth 4] [--min-confidence 0.6] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `tree_rules.csv`：规则列表（含条件、预测、置信度、样本数）
- `tree_rules.json`：结构化 JSON 规则
- `tree_feature_importance.csv`：特征重要性

### 步骤二：SHAP 值分析

通过 Bash 工具执行：

**脚本功能**：
- 全局 SHAP 特征重要性（mean |SHAP|）
- 单样本 SHAP 归因（指定样本索引）
- 特征交互值：Top 特征对的 SHAP 交互效应
- 大数据集自动抽样（>10k 行时默认抽样 5000 行）
- SHAP 值矩阵输出

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/shap_analysis.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--sample-idx 0] [--max-samples 5000] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `shap_global_importance.csv`：全局 SHAP 特征重要性
- `shap_values.csv`：SHAP 值矩阵
- `shap_interaction.csv`：Top 特征对交互值
- `shap_local_explanation.csv`：指定样本的局部 SHAP 归因

### 步骤三：LIME 局部解释 + 反事实解释

通过 Bash 工具执行：

> **注意**：反事实解释功能集成在 `lime_explanation.py` 中，作为 LIME 分析的延伸步骤自动执行，无需单独调用。

**脚本功能**：
- 对指定样本进行 LIME 局部线性近似
- 输出各特征对该预测的贡献权重
- 稳定性检查：多次运行（不同随机种子），检查特征排名一致性
- 输出局部 R2（近似质量指标）
- **反事实解释**：给定一个预测结果，找出最少需要改变哪些特征才能得到不同预测（贪心搜索策略）

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/lime_explanation.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  --sample-idx <样本索引> \
  [--n-stability-runs 5] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `lime_explanation.csv`：特征贡献权重
- `lime_stability.csv`：多次运行的稳定性报告
- `counterfactual.csv`：反事实解释（最小特征变更建议）

## 核心输出物

1. **决策树规则清单**：剪枝后的 if-then 规则表（CSV + JSON）
2. **SHAP 全局重要性表**：特征的平均绝对 SHAP 值排名（CSV）
3. **SHAP 交互值表**：Top 特征对的交互效应（CSV）
4. **LIME 局部解释表**：指定样本各特征的贡献权重（CSV）
5. **稳定性报告**：LIME 多次运行的一致性评估（CSV）
6. **反事实解释表**：改变预测所需的最小特征变更（CSV）
7. **文字根因总结**：自然语言描述导致该结果的主要特征条件

## 质量检验标准

- 决策树叶节点样本数 >= 10，避免过拟合的单样本规则
- 低置信度规则（< 设定阈值）已被剪枝
- SHAP 值正负方向应与相关性方向基本一致（可交叉验证）
- LIME 局部 R2 > 0.6，否则提示局部线性近似质量差
- LIME 稳定性检查中 Top 特征排名应在多次运行中保持一致
- 反事实解释中建议的特征变更幅度应在合理范围内
- 自检：按以上标准逐项验证输出结果
