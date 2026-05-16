---
name: time-series-forecast
description: 时间序列预测 Skill，基于历史时序数据预测未来走势。支持Prophet、SARIMA、VAR多变量预测、Holt-Winters指数平滑，提供回测框架、多模型组合及标准化评估指标（MAE/MAPE/SMAPE/RMSE）。
---

# 时间序列预测（time-series-forecast）

## Skill概述

基于历史时间序列数据推演未来数值趋势。核心能力包括：

- Prophet预测：自动处理趋势、季节性、节假日效应，支持外部回归变量和交叉验证
- SARIMA预测：自动参数搜索（auto-ARIMA），含ADF平稳性检验和Ljung-Box残差检验
- VAR多变量预测：向量自回归，支持Granger因果检验
- Holt-Winters指数平滑：轻量级替代方案，适用于趋势+季节性模式
- 预测评估：MAE/MAPE/SMAPE/RMSE，预测区间覆盖率，时间序列回测
- 多模型组合：多模型加权平均预测

## 输入

- 数据文件路径（CSV或Excel格式）
- 时间列名和数值列名
- 预测期数（如未来30天、12个月）
- 可选参数：外生变量列、节假日国家代码、预测频率、回测折数

## 工作流程

### 步骤一：Prophet预测

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

1. 读取数据，格式化为Prophet所需的ds/y格式
2. 配置模型参数（趋势灵活性、季节性、节假日）
3. 支持外部回归变量（通过 `--regressor-cols` 添加）
4. 拟合模型并生成预测（含95%预测区间）
5. 支持交叉验证（expanding window），评估历史预测精度
6. 输出预测表和模型评估指标到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/prophet_forecast.py" input.csv --time-col date --value-col sales \
    --periods 30 --freq D --country-holidays CN --regressor-cols promo_flag \
    --cross-validate --cv-horizon 30 -o prophet_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤二：SARIMA预测

通过 Bash 工具执行：

1. 读取数据并设置时间索引
2. 执行ADF（Augmented Dickey-Fuller）检验评估序列平稳性
3. 若序列非平稳，自动执行差分
4. 使用auto-ARIMA自动搜索最优(p,d,q)(P,D,Q,m)参数
5. 拟合模型并生成预测（含置信区间）
6. 执行Ljung-Box检验验证残差是否为白噪声
7. 支持Holt-Winters指数平滑作为轻量级替代
8. 输出预测表和诊断结果到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/sarima_forecast.py" input.csv --time-col date --value-col sales \
    --periods 12 --freq ME --holt-winters -o sarima_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤三：VAR多变量预测

通过 Bash 工具执行：

1. 读取数据，选取多个目标变量
2. ADF检验各序列平稳性，非平稳则差分
3. 自动选择最优滞后阶数（基于AIC）
4. 拟合VAR模型并生成多变量联合预测
5. 执行Granger因果检验，判断变量间是否存在因果关系
6. 差分预测结果还原为原始尺度
7. 输出预测表和因果关系矩阵到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/var_forecast.py" input.csv --time-col date \
    --target-cols sales advertising inventory \
    --periods 6 -o var_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 步骤四：预测评估与回测

通过 Bash 工具执行：

1. 基于实际值和预测值计算MAE/MAPE/SMAPE/RMSE
2. 时间序列回测（time series cross-validation）：expanding window方式
3. 预测区间覆盖率计算（实际值落在预测区间内的比例）
4. 多模型组合预测（简单平均或加权平均）
5. 输出评估指标汇总表到CSV

运行方式：
```
python3 "{SKILL_BASE_DIR}/scripts/forecast_evaluation.py" --actual-file actual.csv --forecast-file forecast.csv \
    --actual-col actual_value --forecast-col predicted_value \
    --lower-col lower_bound --upper-col upper_bound -o eval_output.csv
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

## 核心输出物

1. **预测值表**（CSV）：日期、预测值、95%预测区间上下界
2. **模型评估指标**（控制台+CSV）：MAE、MAPE、SMAPE、RMSE
3. **回测结果**（CSV）：各折的评估指标
4. **Granger因果矩阵**（CSV，VAR模型）：变量间因果关系P值
5. **诊断检验结果**（控制台）：ADF平稳性、Ljung-Box残差检验

## 质量检验标准

- 预测区间应随预测期延长而增宽（不确定性递增）
- MAPE>30%时须标注"预测精度较低，建议补充外生变量或人工判断"
- 预测值对于非负指标不应出现负值（需对数变换或下界截断）
- SARIMA模型残差应通过Ljung-Box白噪声检验（p>0.05）
- SMAPE指标在MAPE的基础上提供对称性评估，两者一并参考
- 回测的各折评估指标不应出现剧烈波动，否则提示模型稳定性不足
- 多模型组合预测的误差应不劣于最优单模型
