---
name: association-mining
description: 关联规则与序列模式挖掘 Skill，包含购物篮分析、序列模式挖掘、相关性矩阵分析。输出关联规则表、状态转移矩阵和相关性分析结果。
---

# 关联与序列模式挖掘

## Skill概述

发现变量或事件之间的共现关系、先后顺序模式和统计关联强度，提供三种分析方法：

1. **购物篮分析**：基于FP-Growth的关联规则挖掘，含提升度、确信度、杠杆率等完整指标
2. **序列模式挖掘**：马尔可夫链状态转移 + n-gram路径分析，可选PrefixSpan序列模式挖掘
3. **相关性矩阵**：Pearson/Spearman/互信息多方法分析，支持偏相关计算

## 输入

- **购物篮分析**：事务型数据（事务ID列 + 项目列，每行一个项目）
- **序列分析**：行为日志数据（用户ID列 + 事件列 + 时间列）
- **相关性分析**：包含多个数值列的宽表数据

## 工作流程

### 方法一：购物篮关联规则

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/basket_analysis.py" -i "<数据文件>" --order-col <事务ID列> --item-col <项目列> [--min-support 0.01] [--min-confidence 0.5] [--min-lift 1.0] [-o <输出文件>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

- 使用FP-Growth算法挖掘频繁项集（比Apriori更高效）
- 生成关联规则，计算支持度、置信度、提升度、确信度（conviction）和杠杆率（leverage）
- 支持自定义最小支持度、置信度和提升度阈值
- 输出按提升度排序的Top-N规则

### 方法二：序列模式分析

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/sequence_analysis.py" -i "<数据文件>" --user-col <用户ID列> --event-col <事件列> --time-col <时间列> [-o <输出前缀>]
```

> ⚠️ 禁止手写代码替代此脚本。

- 构建用户行为序列，提取高频n-gram路径（2-gram和3-gram）
- 构建马尔可夫链状态转移概率矩阵
- 可选启用PrefixSpan序列模式挖掘（需安装prefixspan库，未安装时自动回退到n-gram）
- 计算稳态分布，识别关键节点

### 方法三：相关性分析

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/correlation_matrix.py" -i "<数据文件>" --columns <字段1> <字段2> ... [--partial] [--mi] [-o <输出文件>]
```

> ⚠️ 禁止手写代码替代此脚本。

- 自动正态性检验（D'Agostino-Pearson检验）决定使用Pearson或Spearman
- 支持互信息（Mutual Information）非线性关联检测
- 支持偏相关分析（控制混淆变量后的净相关）
- 识别并输出强相关字段对（|r| > 阈值）

## 核心输出物

1. **关联规则表CSV**：包含前项、后项、支持度、置信度、提升度、确信度、杠杆率
2. **状态转移矩阵CSV**：行为间的转移概率，含稳态分布
3. **相关性矩阵CSV**：完整相关矩阵 + 强相关对列表
4. **控制台摘要**：核心规则和关键发现的文字输出

## 质量检验标准

- 关联规则中提升度 < 1 的规则标记为负相关（非推荐依据）
- 转移矩阵每行概率之和 = 1.0（误差 < 1e-10）
- 相关矩阵对角线全为1.0，且关于对角线对称
- 偏相关计算时自动检测并处理奇异矩阵
- 空事务、单项事务等边界情况正确处理
