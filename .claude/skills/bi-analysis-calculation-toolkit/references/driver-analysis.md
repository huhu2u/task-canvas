---
name: driver-analysis
description: 驱动因子分析 Skill，找出影响目标指标的关键因素。覆盖相关性筛选、特征重要性排序、SHAP值解释、偏依赖数据、多重共线性诊断及自动特征选择。当用户需要识别关键驱动因子、做相关性分析或共线性诊断时触发此 Skill。
---

# 驱动因子分析

## Skill概述

在众多候选变量中找出与目标指标关系最紧密的关键因素，并量化其解释力度。覆盖以下分析模块：

1. **相关性筛选**：Pearson（线性）、Spearman（单调非线性）、互信息（任意非线性）三种方法综合评估，并检测非线性关系（Pearson vs Spearman 差异）
2. **特征重要性**：RandomForest 特征重要性 + 置换重要性 + SHAP 值，提供 Shapley 基础的特征贡献量化
3. **偏依赖数据**：输出特征与目标变量的偏依赖数据表（非图形），用于理解单特征边际效应
4. **多重共线性诊断**：VIF 方差膨胀因子检测，支持自动迭代剔除高 VIF 特征

## 输入

- **数据集**（必选）：CSV 或 Excel 文件
- **目标变量列名**（必选）：需要被解释的数值型或分类型指标
- **候选特征列表**（必选）：可能影响目标的特征列名
- 目标变量类型（可选）：连续型或分类型，默认自动检测
- VIF 阈值（可选）：默认 10

## 工作流程

### 步骤一：相关性筛选

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

**脚本功能**：
- 计算每个特征与目标变量的 Pearson r、Spearman rho、互信息 MI
- 生成综合重要性评分（加权组合三种指标）
- 检测非线性关系：当 |Spearman| - |Pearson| > 0.1 时标记为潜在非线性
- 按综合重要性排序输出

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/correlation_screening.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：`correlation_screening.csv`

### 步骤二：特征重要性分析

通过 Bash 工具执行：

**脚本功能**：
- 训练 RandomForest 模型，提取内置特征重要性
- 计算置换重要性（permutation importance），更稳健
- 计算 SHAP 值（基于 TreeExplainer），提供 Shapley 基础的全局重要性
- 输出偏依赖数据表（每个 Top 特征在不同取值下的偏依赖值）
- 5 折交叉验证评估模型拟合质量

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/feature_importance.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--top-n 15] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `feature_importance.csv`：三种重要性指标汇总表
- `partial_dependence.csv`：Top 特征的偏依赖数据
- `shap_values.csv`：各样本的 SHAP 值矩阵

### 步骤三：多重共线性诊断

通过 Bash 工具执行：

**脚本功能**：
- 计算所有候选特征的方差膨胀因子（VIF）
- 按 VIF 值降序排列，标注诊断等级（正常 / 中度 / 严重）
- 自动迭代剔除模式：反复移除 VIF 最高的特征，直至所有特征 VIF < 阈值
- 输出推荐保留的特征列表

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/vif_diagnosis.py" <数据文件> \
  --features <特征1> <特征2> ... \
  [--threshold 10] [--auto-drop] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `vif_diagnosis.csv`：所有特征的 VIF 诊断表
- `vif_auto_selection.csv`：自动迭代剔除后的保留特征（若开启 `--auto-drop`）

## 核心输出物

1. **相关性筛查表**：Pearson/Spearman/MI 三方法综合排名 + 非线性标记（CSV）
2. **特征重要性汇总表**：RF内置/置换/SHAP 三种重要性指标（CSV）
3. **偏依赖数据表**：Top 特征的边际效应数值表（CSV）
4. **VIF 诊断报告**：各特征共线性等级 + 自动特征选择推荐（CSV）
5. **文字结论**：Top 驱动因子说明、非线性关系提示、共线性风险及建模建议

## 质量检验标准

- RF 特征重要性之和 = 1.0（sklearn 自动归一化）
- VIF 计算包含截距项（否则结果偏低）
- 模型交叉验证 R2 < 0.1 时提示候选特征解释力不足
- SHAP 值正负方向应与 Pearson 相关性方向基本一致
- 自动迭代剔除 VIF 后保留的特征集应无严重共线性
- 自检：按以上标准逐项验证输出结果
