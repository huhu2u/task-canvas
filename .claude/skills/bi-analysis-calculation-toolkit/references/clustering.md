---
name: clustering
description: 聚类分群 Skill，支持 K-Means / DBSCAN / HDBSCAN 自动分群，输出分群标签、聚类质量指标和群体特征画像。
---

# 聚类分群（clustering）

## Skill概述

自动发现数据中的自然分组结构，将样本划分为若干具有内部相似性的群体。支持多种聚类算法，自动确定最优簇数，并输出每个群体的特征画像。所有结果以结构化数据（CSV）形式输出，不包含可视化图像。

## 输入

- **数据文件**：CSV 或 Excel 格式的数据集路径
- **特征列表**：用于聚类的数值型特征列名（逗号分隔）
- 可选参数：
  - 最大簇数上限（默认 10）
  - 指定算法（kmeans / dbscan / auto，默认 auto）
  - DBSCAN 参数：eps、min_samples
  - 是否启用 PCA 预降维（高维数据自动启用）
  - 随机种子（默认 42）

## 工作流程

### 第一步：特征预处理

由各脚本内部自动完成：
- 缺失值中位数填充
- StandardScaler 标准化（聚类对量纲敏感）
- 特征维度 > 50 时自动 PCA 预降维至保留 95% 方差的维度

### 第二步：K-Means 聚类与最优 K 选择

通过 Bash 工具执行以下命令（将 `{SKILL_BASE_DIR}` 替换为系统注入的 Base directory）：

```bash
python3 "{SKILL_BASE_DIR}/scripts/clustering_analysis.py" --input "<数据文件>" --features "<特征1>,<特征2>,..." [--k-max 10] [--seed 42] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。必须通过 Bash 工具执行上述命令。

- 遍历 K=2 到 K_max，计算三项指标：
  - **Elbow Method (SSE)**：惯性下降的二阶差分找拐点
  - **Silhouette Score**：簇间分离度与簇内紧密度的平衡
  - **Gap Statistic**：与随机均匀分布对比的统计量
- 额外计算 **Davies-Bouldin Index**（越小越好）
- 综合三项指标推荐最优 K
- 使用最优 K 拟合并输出簇标签

### 第三步：DBSCAN 密度聚类

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/dbscan_analysis.py" --input "<数据文件>" --features "<特征1>,<特征2>,..." [--eps <值>] [--min-samples <值>] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

- 自动估算 eps：基于 K-距离图的拐点检测
- 默认 min_samples = max(5, log(N))
- 输出簇标签（含噪声点标记 -1）
- 当 DBSCAN 结果不理想（噪声点 > 30% 或仅 1 个簇）时，自动尝试 HDBSCAN

### 第四步：群体特征画像

通过 Bash 工具执行：

```bash
python3 "{SKILL_BASE_DIR}/scripts/cluster_profiling.py" --input "<含cluster列的数据文件>" --features "<特征1>,<特征2>,..." [--cluster-col cluster] [--output-dir <输出目录>]
```

> ⚠️ 禁止手写代码替代此脚本。

- 计算每个簇在各特征上的均值、标准差、中位数
- 计算每个簇的特征均值相对全局均值的 z-score（标准化偏差）
- 输出簇规模和占比
- 标记每个簇的显著特征（z-score 绝对值 > 1 的特征）

## 核心输出物

1. **K 值搜索表**（CSV）：各 K 下的 SSE、Silhouette、Gap Statistic、Davies-Bouldin
2. **聚类标签**（CSV）：每个样本的簇分配结果
3. **聚类质量摘要**（CSV + 控制台）：最优 K、Silhouette Score、Davies-Bouldin Index
4. **DBSCAN 结果**（CSV）：簇标签、噪声点标记、簇数和噪声比例
5. **群体画像表**（CSV）：各簇的特征均值、标准差、z-score 偏差

## 质量检验标准

- Silhouette Score > 0.5 为优秀，0.25-0.5 为合理，< 0.25 提示聚类结构不明显
- 每个簇的样本量应 > 总样本的 1%，否则警告该簇可能为噪声
- DBSCAN 噪声点占比 > 30% 时提示参数可能需要调整
- Gap Statistic 标准误检验：gap(k) >= gap(k+1) - se(k+1) 时 k 为最优
- Davies-Bouldin Index 越接近 0 越好
