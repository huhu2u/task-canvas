---
name: regression-forecast
description: 连续值回归预测 Skill，覆盖线性/正则化回归、梯度提升树、分位数回归、残差诊断。支持嵌套交叉验证调参、Lasso 路径特征选择、残差异方差/自相关检验、Cook距离异常点检测。
---

# 连续值回归预测

## Skill概述

预测连续数值，提供从简单线性关系到复杂非线性关系的完整建模流程，并量化预测不确定性。覆盖以下模块：

1. **线性/正则化回归**：OLS、Ridge（L2）、Lasso（L1）、ElasticNet，附带 Lasso 路径用于特征选择
2. **梯度提升回归**：XGBoost / LightGBM，支持嵌套交叉验证超参调优
3. **分位数回归**：P10/P50/P90 预测区间，量化预测不确定性
4. **残差诊断**：Breusch-Pagan 异方差检验、Durbin-Watson 自相关检验、Cook距离异常点识别

## 输入

- **数据集**（必选）：CSV 或 Excel 文件
- **目标变量列名**（必选）：连续数值型列
- **特征列表**（必选）：用于建模的特征列名
- 测试集比例（可选）：默认 0.2
- 交叉验证折数（可选）：默认 5

## 工作流程

### 步骤一：线性/正则化回归

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

**脚本功能**：
- 训练 OLS / Ridge / Lasso / ElasticNet 四种模型
- 计算 MAE / RMSE / MAPE / R2 评估指标并横向对比
- 输出最优模型的特征系数
- Lasso 路径分析：不同正则化强度下各特征系数的变化轨迹，用于特征选择

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/linear_regression.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--test-size 0.2] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `linear_model_comparison.csv`：模型评估对比表
- `linear_coefficients.csv`：最优模型系数
- `lasso_path.csv`：Lasso 路径数据

### 步骤二：梯度提升回归

通过 Bash 工具执行：

**脚本功能**：
- 训练 XGBoost / LightGBM
- 嵌套交叉验证调参（外层评估，内层调参）
- 计算 MAE / RMSE / MAPE / R2 并与线性模型对比
- 输出特征重要性排名

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/boosting_regression.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--test-size 0.2] [--cv-folds 5] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `boosting_model_comparison.csv`：模型评估对比表
- `boosting_feature_importance.csv`：特征重要性

### 步骤三：分位数回归

通过 Bash 工具执行：

**脚本功能**：
- 训练 P10 / P50 / P90 三个分位数模型
- 输出每个测试样本的预测区间
- 计算区间覆盖率（实际值落在 P10-P90 区间内的比例）

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/quantile_regression.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--quantiles 0.1 0.5 0.9] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：`quantile_predictions.csv`

### 步骤四：残差诊断

通过 Bash 工具执行：

**脚本功能**：
- Breusch-Pagan 异方差检验
- Durbin-Watson 自相关检验
- Cook距离计算，识别强影响点（Cook's D > 4/n）
- 残差正态性检验
- VIF 多重共线性检查
- 输出诊断汇总报告

**调用方式**：
```bash
python3 "{SKILL_BASE_DIR}/scripts/regression_diagnostics.py" <数据文件> \
  --target <目标变量> --features <特征1> <特征2> ... \
  [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

**输出文件**：
- `diagnostics_summary.csv`：诊断检验汇总
- `influential_points.csv`：强影响点列表
- `residuals.csv`：残差数据

## 核心输出物

1. **模型对比表**：多种模型的 MAE / RMSE / MAPE / R2 横向比较（CSV）
2. **预测区间表**：P10/P50/P90 预测及区间覆盖率（CSV）
3. **特征系数/重要性表**：线性模型系数 + 提升模型重要性（CSV）
4. **残差诊断报告**：异方差/自相关/强影响点/共线性检验结果（CSV）
5. **文字结论**：最优模型推荐、关键预测因子、诊断问题及改进建议

## 质量检验标准

- R2 < 0.3 时提示模型解释力弱，建议补充特征或检查数据质量
- 分位数预测区间满足 P90 >= P50 >= P10 对所有样本成立
- Breusch-Pagan 显著（p<0.05）时提示异方差问题，建议加权回归或变量变换
- Durbin-Watson 偏离 2.0 时提示自相关，需注意时序数据建模方式
- Cook's D > 4/n 的观测点需审查是否为异常数据
- MAPE 在不同模型间的排序应与 RMSE/R2 一致
- 自检：按以上标准逐项验证输出结果
