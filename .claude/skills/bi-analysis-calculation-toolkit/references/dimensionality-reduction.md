---
name: dimensionality-reduction
description: 降维与结构发现 Skill，支持 PCA 主成分分析、t-SNE/UMAP 流形嵌入、综合指数构建，输出降维坐标和载荷矩阵。
---

# 降维与结构发现（dimensionality-reduction）

## Skill概述

在保留主要信息的前提下简化数据维度，用于特征压缩、综合指标构建和高维数据结构探索。包含三个子模块：PCA 主成分分析（线性降维）、t-SNE/UMAP 流形嵌入（非线性降维）、基于 PC1 的综合指数构建。所有结果以 CSV 结构化数据输出，不包含可视化图像。

## 输入

- **数据文件**：CSV 或 Excel 格式的数据集路径
- **特征列表**：用于降维的数值型特征列名（逗号分隔）
- 可选参数：
  - 目标方差解释比（PCA，默认 0.90）
  - 指定主成分数量（覆盖自动选择）
  - t-SNE perplexity（默认 30）
  - UMAP n_neighbors 和 min_dist
  - 颜色标注列（用于嵌入坐标的分组标记）
  - 随机种子（默认 42）

## 工作流程

### 第一步：PCA 主成分分析

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/pca_analysis.py" --input "<数据文件>" --features "<特征1>,<特征2>,..." [--variance-target 0.90] [--seed 42] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：
- 标准化所有特征（StandardScaler）
- 先执行全量 PCA 获取所有特征值和方差解释比
- 自动确定主成分数量，支持两种策略：
  - **累计方差阈值**（默认 90%）：保留解释 90% 方差所需的最少主成分数
  - **Kaiser 准则**：保留特征值 > 1 的主成分
  - **平行分析**：与随机数据的特征值分布对比，保留显著高于随机的主成分
- 输出主成分载荷矩阵（各原始特征对各主成分的贡献权重）
- 输出方差解释比表（各主成分单独和累计解释方差）
- 输出降维后的坐标数据（每个样本的 PC 值）

### 第二步：t-SNE / UMAP 流形嵌入

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/manifold_embedding.py" --input "<数据文件>" --features "<特征1>,<特征2>,..." [--method tsne] [--perplexity 30] [--n-neighbors 15] [--min-dist 0.1] [--seed 42] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：
- 标准化特征后执行非线性降维至 2D
- 高维数据（> 50 维）自动先 PCA 预降维至 50 维
- **t-SNE 模式**：
  - 支持指定 perplexity 参数
  - 可选 perplexity 敏感性检查：用多个 perplexity 值运行，输出各次嵌入坐标
- **UMAP 模式**：
  - 支持 n_neighbors 和 min_dist 参数
  - 文档说明参数对结果的影响
- 输出 2D 嵌入坐标 CSV（可用于下游分析）

### 第三步：综合指数构建

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/composite_index.py" --input "<数据文件>" --features "<特征1>,<特征2>,..." [--seed 42] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

功能说明：
- 基于 PCA 的 PC1 载荷构建加权综合评分
- 权重方案：PC1 载荷绝对值归一化
- 输出每个样本的综合指数得分
- 输出权重表和各特征的贡献

## 核心输出物

1. **方差解释比表**（CSV）：各主成分的特征值、方差解释比、累计方差解释比
2. **载荷矩阵**（CSV）：原始特征 x 主成分的载荷权重
3. **PCA 坐标数据**（CSV）：每个样本在各主成分上的得分
4. **组件选择建议**（CSV + 控制台）：三种准则的推荐主成分数
5. **嵌入坐标**（CSV）：t-SNE / UMAP 的 2D 坐标数据
6. **综合指数**（CSV）：每个样本的加权综合评分和权重表

## 质量检验标准

- PCA 累计方差解释比在选定主成分数后应达到目标（默认 >= 90%）
- 载荷矩阵各列正交（任意两列内积接近 0）
- Kaiser 准则和平行分析结果作为参考，与方差阈值结果对比
- t-SNE 输出注明：结果对随机种子和 perplexity 敏感，仅用于探索性分析
- UMAP 输出注明 n_neighbors 和 min_dist 的参数影响
- 综合指数的权重之和应为 1
