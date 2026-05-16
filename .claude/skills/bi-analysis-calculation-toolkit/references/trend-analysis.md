---
name: trend-analysis
description: 趋势识别与突变点检测 Skill。包含Mann-Kendall趋势检验（含季节性修正和预白化）、STL/MSTL时序分解、ACF/FFT周期检测、PELT/CUSUM/贝叶斯突变点检测，以及ADF平稳性检验。
---

# 趋势与突变识别（trend-analysis）

## Skill概述

在时间维度上识别数据的演变规律，回答"它是怎么变的、何时发生了转变"。核心能力包括：

- 趋势显著性检验：Mann-Kendall检验（含季节性MK检验、自相关预白化修正MK检验）、Sen斜率估计（含置信区间）
- 时序分解：STL分解（趋势+季节+残差）、MSTL多季节周期分解
- 周期性识别：ACF自相关检测、FFT频率域分析
- 突变点检测：PELT算法、CUSUM方法、贝叶斯在线突变点检测，含段内统计量输出
- 平稳性检验：ADF检验作为补充信息

## 输入

- 数据文件路径（CSV或Excel格式）
- 时间列名和数值列名
- 可选参数：预期周期长度、显著性水平（默认0.05）、突变点检测灵敏度

## 工作流程

### 步骤一：趋势检验

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

1. 读取数据并按时间排序
2. 执行标准Mann-Kendall检验：计算S统计量、Z值、P值，判断趋势方向和显著性
3. 若数据含季节性，执行季节性Mann-Kendall检验（Seasonal MK Test）
4. 若数据存在自相关，执行预白化修正MK检验（Modified MK Test），消除自相关对趋势判断的干扰
5. 计算Sen斜率估计值及其95%置信区间
6. 执行ADF（Augmented Dickey-Fuller）检验评估序列平稳性
7. 输出检验结果表到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/trend_test.py" input.csv --time-col date --value-col metric \
    --season-period 12 --alpha 0.05 -o trend_test_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤二：STL时序分解

通过 Bash 工具执行：

1. 读取数据，设置时间索引
2. 若未指定周期，利用ACF自动推断主周期
3. 执行STL分解，提取趋势项、季节项、残差项
4. 支持MSTL（多季节STL）分解，处理含多个季节周期的数据（如同时有周周期和年周期）
5. 计算趋势强度和季节性强度指标
6. 验证分解正确性（趋势+季节+残差=原序列）
7. 输出各分量到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/stl_decomposition.py" input.csv --time-col date --value-col metric \
    --period 7 --mstl-periods 7 365 -o stl_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤三：周期性检测

通过 Bash 工具执行：

1. 计算ACF（自相关函数），识别显著正相关的滞后阶
2. 执行FFT（快速傅里叶变换），从频域识别主要周期
3. 综合ACF和FFT结果，报告最可能的周期长度
4. 输出ACF值和FFT频率分析表到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/periodicity_detection.py" input.csv --time-col date --value-col metric \
    --max-lag 200 -o period_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤四：突变点检测

通过 Bash 工具执行：

1. 使用PELT算法检测均值/方差的结构变化点
2. CUSUM方法作为备选/互补
3. 支持贝叶斯在线突变点检测（Bayesian Online Changepoint Detection）
4. 对每个检测到的分段输出统计量（均值、标准差、样本量）
5. 突变点过多时自动调高惩罚参数
6. 输出突变点列表和段内统计量到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/changepoint_detection.py" input.csv --time-col date --value-col metric \
    --method pelt --penalty auto -o changepoint_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

## 核心输出物

1. **趋势检验报告**（CSV）：MK检验Z值/P值、季节性MK结果、修正MK结果、Sen斜率及CI、ADF结果
2. **STL分解表**（CSV）：各时间点的趋势项、季节项、残差项，以及强度指标
3. **周期检测结果**（CSV）：ACF显著滞后、FFT主要周期及对应能量
4. **突变点清单**（CSV）：突变时间点、段内均值/标准差/样本量对比

## 质量检验标准

- Mann-Kendall P值<0.05时声明"统计显著"，否则须注明"不能排除随机波动"
- STL分解后三项之和等于原始序列（误差<1e-10）
- 突变点数量通常不超过5个，过多时须提高惩罚参数
- 季节性MK检验须确认指定的季节周期与数据实际频率匹配
- 预白化MK检验的AR(1)系数须显著，否则回退到标准MK检验
- ADF检验与MK检验结果需综合解读（平稳性与趋势性并非互斥）
