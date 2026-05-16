---
name: survival-analysis
description: 生存分析 Skill，估计事件发生时间分布并识别风险因素。包含Kaplan-Meier生存曲线估计、Cox比例风险回归、加速失效时间（AFT）模型，输出生存函数估计、中位生存时间、危险比系数表及模型诊断结果。
---

# 生存分析（survival-analysis）

## Skill概述

对含删失（censoring）数据的事件时间进行统计建模与推断，回答"事件预计何时发生"和"哪些因素影响事件发生速度"。核心能力包括：

- Kaplan-Meier估计：非参数生存函数估计、多组对比（Log-rank检验）、受限平均生存时间（RMST）
- Cox比例风险回归：协变量危险比（HR）估计、Schoenfeld残差检验PH假设、C-index判别力评估
- 生存时间统计摘要：中位生存时间、分位数、受限平均生存时间
- AFT模型：当PH假设不满足时的替代建模方法

## 输入

- 数据文件路径（CSV或Excel格式）
- 生存时长列名（连续型，表示观察时间）
- 事件状态列名（1=事件发生，0=删失/截尾）
- 可选参数：分组列（用于KM多组对比）、协变量列（用于Cox/AFT回归）、预测时间点列表

## 工作流程

### 步骤一：Kaplan-Meier生存曲线估计

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/kaplan_meier.py" input.csv --duration-col time --event-col status \
    --group-col group --time-points 30 90 180 365 -o km_output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 读取数据，验证时长列和事件列的有效性
2. 拟合Kaplan-Meier生存函数，计算各时间点的生存概率及95%置信区间
3. 计算中位生存时间（及其置信区间）
4. 计算受限平均生存时间（RMST）作为中位数的补充（当中位数无法估计时尤其重要）
5. 若指定分组列，分组拟合KM曲线并执行Log-rank检验评估组间差异
6. 计算指定时间点的生存率
7. 输出生存函数表和摘要统计到CSV

### 步骤二：Cox比例风险回归

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/cox_regression.py" input.csv --duration-col time --event-col status \
    --covariate-cols age income plan_type -o cox_output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 准备数据，处理缺失值，对分类变量进行编码
2. 拟合Cox比例风险模型
3. 提取危险比（HR）、95%置信区间、P值
4. 执行Schoenfeld残差检验验证PH假设（自动化）
   - 若某协变量违反PH假设（p<0.05），给出警告并建议使用AFT模型或分层Cox
5. 计算C-index（一致性指数）评估模型判别力
6. 提供时变协变量支持的使用提示
7. 输出系数表和诊断结果到CSV

### 步骤三：生存时间统计摘要

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/survival_summary.py" input.csv --duration-col time --event-col status \
    --group-col group -o summary_output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 计算中位生存时间及其95%置信区间
2. 计算25%、50%、75%分位数生存时间
3. 计算受限平均生存时间（RMST）及标准误
4. 计算事件率（event rate）和删失比例
5. 若指定分组，按组输出以上所有统计量
6. 当删失比例>80%时发出警告

## 核心输出物

1. **KM生存函数表**（CSV）：各时间点的生存概率、95%置信区间、风险集大小
2. **中位生存时间与RMST**（控制台+CSV）：含置信区间
3. **Log-rank检验结果**（控制台）：检验统计量和P值
4. **Cox系数表**（CSV）：各协变量的HR、95%CI、P值、显著性判定
5. **PH假设检验结果**（控制台+CSV）：Schoenfeld残差检验各协变量的P值
6. **C-index**（控制台）：模型判别力指标
7. **生存时间分位数表**（CSV）：多分位数生存时间汇总

## 质量检验标准

- KM生存曲线单调不增（生存概率只降不升）
- Cox模型须通过PH假设检验（Schoenfeld检验各协变量p>0.05），否则需标注并建议替代方法
- 删失比例>80%时，须提示"删失比例过高，结论稳健性不足"
- C-index>0.7视为可接受的判别力，<0.6须警告
- 生存函数在t=0时为1.0
- RMST计算须明确截断时间点
