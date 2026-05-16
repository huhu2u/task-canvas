---
name: classification-forecast
description: 离散分类预测 Skill，支持二分类与多分类建模、概率校准、阈值优化，输出结构化评估指标。
---

# 离散分类预测（classification-forecast）

## Skill概述

对目标变量进行离散分类预测，支持二分类和多分类任务。自动处理类别不平衡、训练多模型对比、执行概率校准和阈值优化，输出结构化的评估指标（分类报告、混淆矩阵、特征重要性等），全部以CSV和控制台文本形式呈现。

## 输入

- **数据文件**：CSV 或 Excel 格式的数据集路径
- **目标变量**：分类型目标列名（二分类或多分类）
- **特征列表**：用于建模的特征列名（多个，逗号分隔）
- 可选参数：
  - 测试集比例（默认 0.2）
  - 交叉验证折数（默认 5）
  - 不平衡处理策略（auto / smote / class_weight / none）
  - 概率校准方法（sigmoid / isotonic）
  - 随机种子（默认 42）

## 工作流程

### 第一步：数据准备与不平衡检测

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/classification_train.py" --input "<数据文件>" --target <目标变量> --features "<特征1>,<特征2>,..." [--test-size 0.2] [--cv-folds 5] [--imbalance auto] [--seed 42] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

脚本自动完成：
- 加载数据，对目标变量进行标签编码（字符串类型自动转换）
- 缺失值中位数填充
- 计算类别分布和不平衡比率
- 不平衡比率 > 5 时，自动启用 SMOTE 过采样（仅训练集）或 class_weight='balanced'
- 使用分层抽样划分训练集/测试集

### 第二步：多模型训练与交叉验证

第一步执行的 `classification_train.py` 脚本同时完成多模型训练（无需重复执行），该脚本同时训练三个模型：
- **LogisticRegression**：带 class_weight='balanced'，L2 正则化
- **XGBoost**：自动计算 scale_pos_weight（二分类），支持 GPU
- **RandomForest**：带 class_weight='balanced'，200 棵树

每个模型使用 Stratified K-Fold 交叉验证评估，输出：
- 各模型 Accuracy / AUC-ROC（二分类）/ F1-weighted（多分类）
- 选出最优模型并输出详细分类报告
- 混淆矩阵以结构化数据输出到 CSV
- 通过 permutation importance 计算特征重要性并排序

### 第三步：阈值优化（二分类）

第一步执行的 `classification_train.py` 脚本同时完成阈值优化（无需重复执行），脚本自动执行阈值搜索：
- 计算所有阈值下的 F1 分数，找到最大 F1 对应阈值
- 计算 Youden's J = Sensitivity + Specificity - 1，找到最大 J 对应阈值
- 输出阈值-指标对照表到 CSV

### 第四步：概率校准

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/probability_calibration.py" --input "<数据文件>" --target <目标变量> --features "<特征1>,<特征2>,..." [--method sigmoid] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

- 支持 Platt Scaling（sigmoid）和 Isotonic Regression 两种方法
- 计算校准前后的 Brier Score
- 输出分箱校准对照表（预测概率区间 vs 实际正类频率）到 CSV
- 判断校准是否有效

## 核心输出物

1. **模型对比表**（CSV）：各模型在交叉验证和测试集上的性能指标
2. **分类报告**（CSV + 控制台）：Precision / Recall / F1 per class
3. **混淆矩阵**（CSV）：结构化矩阵数据
4. **特征重要性**（CSV）：基于 permutation importance 的排序
5. **阈值优化结果**（CSV）：阈值-F1-Youden's J 对照表
6. **概率校准报告**（CSV + 控制台）：Brier Score、分箱对照表

## 质量检验标准

- AUC < 0.6 时输出警告：模型近似随机猜测，需检查特征质量
- 类别不平衡场景下不单独使用 Accuracy，必须同时报告 AUC 和 F1
- 交叉验证各折标准差 > 0.1 时输出警告：模型稳定性不足
- Brier Score 校准后应小于校准前，否则提示原始概率已较准确
- 测试集任意类别样本量 < 10 时输出警告：评估结果可能不可靠
