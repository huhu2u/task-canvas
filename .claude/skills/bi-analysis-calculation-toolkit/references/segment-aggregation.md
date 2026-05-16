---
name: segment-aggregation
description: 多维分组聚合与结构占比分析 Skill。对数据按指定维度进行分组汇总、交叉透视、帕累托分析，计算集中度指标（HHI、基尼系数），揭示数据结构特征。
---

# 多维聚合与结构占比分析（segment-aggregation）

## Skill概述

按指定维度对数据进行多维切片与重组，量化各分组的贡献与集中度。核心能力包括：

- 多维分组汇总：支持多聚合函数（sum/mean/median/count等）、加权聚合
- 交叉透视分析：双维度透视表（pivot table）
- 帕累托分析：80/20法则验证、累计份额计算
- 集中度度量：HHI指数、基尼系数
- Top-N分析：头部分组提取，尾部合并为"其他"

## 输入

- 数据文件路径（CSV或Excel格式）
- 分组维度字段名（一个或多个）
- 度量指标字段名（一个或多个）
- 可选参数：Top-N取值（默认10）、聚合函数类型、权重列、是否做透视分析及透视的行列字段

## 工作流程

### 步骤一：多维分组聚合

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/group_aggregation.py" "<数据文件>" --group-cols 维度A --metric-cols 指标1 指标2 --agg-func sum --top-n 10 [--weight-col 权重列] -o output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 读取数据，验证分组列和度量列存在性
2. 按指定维度执行 groupby 聚合，支持 sum/mean/median/count/std 等多种聚合函数
3. 支持加权聚合（通过 `--weight-col` 指定权重列）
4. 计算各分组的占比（%）和排名
5. 计算集中度指标：
   - HHI（Herfindahl-Hirschman Index）：各分组份额的平方和，范围 [0, 10000]，越高越集中
   - 基尼系数：衡量分布不均等程度，范围 [0, 1]，越高越不均等
6. Top-N 提取，其余合并为"其他"组
7. 支持多指标同时聚合（`--metric-cols` 传入多个字段）

### 步骤二：帕累托分析

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/pareto_analysis.py" input.csv --group-col 维度A --metric-col 指标1 --threshold 80 -o pareto_output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 按指定维度和度量进行分组汇总
2. 按度量值降序排列
3. 计算各分组占比和累计占比
4. 标记80%贡献的分界点（可自定义阈值）
5. 计算集中度比（贡献80%的分组占总分组数的比例）
6. 输出帕累托分析表

### 步骤三：交叉透视分析

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/pivot_analysis.py" input.csv --row-col 维度A --col-col 维度B --value-col 指标1 --agg-func sum -o pivot_output.csv
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：

1. 指定行维度、列维度和值字段
2. 生成透视表，支持多种聚合函数
3. 计算行合计、列合计和总计（margins）
4. 计算行占比和列占比
5. 输出透视表到CSV

## 核心输出物

1. **分组汇总表**（CSV）：各维度的聚合值、占比、排名、Top-N与"其他"合并结果
2. **集中度指标**（控制台输出）：HHI指数、基尼系数、CR-N（前N名集中度比）
3. **帕累托分析表**（CSV）：各分组占比、累计占比、80%贡献分界点标记
4. **交叉透视表**（CSV）：双维度交叉汇总，含行列合计和占比

## 质量检验标准

- 所有分组占比之和 = 100%（误差 < 0.1%）
- 累计占比单调递增且最终到达100%
- Top-N排名与帕累托排序一致
- HHI范围在 [0, 10000] 之内，基尼系数在 [0, 1] 之内
- 加权聚合时权重列无负值
- 透视表行列合计与分组汇总结果一致
