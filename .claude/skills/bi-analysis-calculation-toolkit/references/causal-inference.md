---
name: causal-inference
description: 因果推断 Skill，评估干预措施的真实效果。覆盖DID双重差分、贝叶斯时序反事实、PSM倾向得分匹配、价格弹性估计。
---

# 因果推断

## Skill概述

区分"相关"与"因果"，通过构造反事实来评估干预效果，提供四种方法：

1. **DID（双重差分）**：有实验组/对照组 + 干预前后时间对比，含平行趋势验证和事件研究分析
2. **CausalImpact（贝叶斯时序）**：仅有干预对象时，用时序预测构造反事实对照
3. **PSM（倾向得分匹配）**：基于 Abadie & Imbens (2006) 的匹配估计器，支持 ATE/ATT 估计、1:M 有放回匹配、Abadie-Imbens 方差估计、偏差修正，含 SMD 平衡检验
4. **价格弹性**：对数-对数回归估计弹性系数，含内生性警告和自相关检验

## 输入

- **DID**：实验组/对照组标识、时间列、结果变量、干预时间点
- **CausalImpact**：时间序列、干预前期间、干预后期间
- **PSM**：处理标识列、协变量列、结果变量列、[可选] 估计量类型(ATE/ATT)、匹配数M、是否偏差修正
- **价格弹性**：价格列、数量列、可选控制变量

## 工作流程

### 方法一：双重差分法（DID）

通过 Bash 工具执行以下命令（将 {SKILL_BASE_DIR} 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/did_analysis.py" <数据文件> \
  --group-col <分组列> --time-col <时间列> --outcome-col <结果变量列> \
  --treat-time <干预时间点> [--control-vars <控制变量>] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

- 构建DID回归模型（OLS + 异方差稳健标准误HC3）
- 自动验证平行趋势假设：输出干预前各期的组间差异
- 事件研究（Event Study）：计算干预前各期系数，检验是否显著异于0
- 输出ATT估计值、置信区间、p值
- 支持添加控制变量

### 方法二：贝叶斯时序反事实

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/causal_impact.py" <数据文件> \
  --time-col <时间列> --outcome-col <结果变量列> \
  --pre-start <干预前起始日期> --pre-end <干预前结束日期> \
  --post-start <干预后起始日期> --post-end <干预后结束日期> \
  [--covariates <协变量1> <协变量2>] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

- 优先使用CausalImpact库（需安装pycausalimpact）
- 未安装时回退到ARIMA反事实预测
- 输出实际值与反事实预测的差异、累积效应
- 计算效应的置信区间和统计显著性

### 方法三：倾向得分匹配（PSM）

通过 Bash 工具执行：

**核心功能：**
- 使用逻辑回归计算倾向得分
- **1:M 最近邻有放回匹配**（matching with replacement），M 可通过 `--n-matches` 配置（默认 M=1）
- caliper 自动设定为 factor × SD(倾向得分)，默认 factor=0.2，可通过 `--caliper-factor` 配置
- 支持 **ATE（平均处理效应）** 和 **ATT（处理组平均处理效应）** 两种估计量，通过 `--estimand` 选择
- **Abadie-Imbens 方差估计器**（Theorem 6 & 7）：基于同组最近邻匹配估计条件方差 σ²(x,w)，不依赖一致的非参数估计，替代简单配对 t 检验
- **KM(i) 匹配权重计算**：追踪每个单元被用作匹配的次数，用于正确估计方差
- **偏差修正匹配估计器**（Bias-Corrected Matching Estimator, Abadie & Imbens 2002）：通过 `--bias-correction` 启用，使用线性回归估计 μ_w(x) 修正匹配偏差

**平衡检验：**
- 匹配后计算各协变量的标准化均值差异（SMD）
- SMD > 0.1 的协变量标记为不平衡并警告

**理论性诊断警告：**
- **协变量维度偏差警告**（Theorem 1）：当连续协变量维度 k≥2 时，匹配偏差的阶为 Op(N^{-1/k})，可能大于 N^{-1/2}，简单匹配估计器可能不是 √N-一致的，建议启用偏差修正
- **Bootstrap 失效警告**（Abadie & Imbens 2005）：标准 Bootstrap 对固定匹配数的匹配估计器无效，本脚本使用解析方差估计器
- **效率参考**（Theorem 5, k=1 时）：报告相对于半参数效率界的渐近方差损失上界，M=1 时 < 50%，增大 M 可减小损失

**命令行参数：**
```bash
python3 "{SKILL_BASE_DIR}/scripts/psm_analysis.py" <数据文件> \
  --treat-col <处理标识列> --outcome-col <结果变量列> \
  --covariates <协变量1> <协变量2> ... \
  [--n-matches 1] [--caliper-factor 0.2] [--alpha 0.05] \
  [--estimand ATE|ATT] [--bias-correction] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

### 方法四：价格弹性估计

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/price_elasticity.py" <数据文件> \
  --price-col <价格列> --quantity-col <数量列> \
  [--control-cols <控制变量>] [--output-dir <输出目录>]
```
> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

- 对数-对数回归（ln(Q) ~ ln(P) + 控制变量）
- 异方差稳健标准误（HC3）
- Durbin-Watson检验自相关
- 内生性警告提示（价格可能与需求同时决定）
- 输出弹性系数、置信区间、弹性类型判定

## 核心输出物

1. **DID结果CSV**：ATT、置信区间、p值、事件研究系数表
2. **CausalImpact结果CSV**：各期实际值、预测值、效应、累积效应
3. **PSM结果CSV**：ATE/ATT估计值、Abadie-Imbens标准误、z统计量、P值、置信区间、匹配数M、偏差修正标记、协变量平衡检验表（含匹配前后SMD）、KM(i)匹配权重分布摘要
4. **弹性系数CSV**：弹性估计值、置信区间、诊断检验结果
5. **控制台摘要**：各方法核心结论

## 质量检验标准

- DID分析前验证平行趋势假设，不满足时在输出中明确说明局限性
- PSM匹配率 < 50% 时警告结论可靠性受限
- PSM匹配后所有协变量SMD < 0.1 才视为平衡良好
- PSM协变量维度 k≥2 时自动警告匹配偏差可能不是 √N-一致，建议启用偏差修正（Theorem 1）
- PSM使用 Abadie-Imbens 解析方差估计器，不使用标准 Bootstrap（Abadie & Imbens 2005 证明 Bootstrap 无效）
- PSM输出 KM(i) 匹配权重分布，用于评估匹配质量
- 价格弹性为正（需求随价格上涨）时标注异常现象警告
- Durbin-Watson统计量远离2时警告存在自相关
- 所有回归结果包含稳健标准误
