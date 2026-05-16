# SQL 生成

## 1. 解析用户需求

从自然语言描述中提取：
- **目标表**：表名或关键字
- **时间范围**：昨天、最近7天、某个日期等
- **查询意图**：聚合方式（COUNT/SUM/AVG）、分组字段、筛选条件、排序
- **输出要求**：TOP N、格式偏好

## 2. 生成规则

**语法标准**：OneSQL（基本与 Presto 语法一致）

**OneSQL 参考文档**（查询报错或写 SQL 时使用）：
- 函数手册：https://km.sankuai.com/collabpage/2720165452
- 语法文档：https://km.sankuai.com/collabpage/2726847319
- SET 指令跳过 UDF 解析：https://km.sankuai.com/collabpage/2728624688
- 查询问题 FAQ（报错时优先检索）：https://km.sankuai.com/collabpage/2718277153

**必须遵守**：
- WHERE 条件必须包含分区字段限制（通常是日期分区 `dt`）
- 日期格式通常为 `yyyyMMdd`（如 `20260309`），注意字段类型，int 用数字，string 用字符串
- 使用 `date_format(date_add(current_date(), -1), 'yyyyMMdd')` 表示"昨天"，根据分区字段类型做 CAST
- JOIN 必须有明确的 ON 条件
- 避免 SELECT *，只选需要的字段
- 大表查询加 LIMIT 防止结果集过大

## 3. SQL 标准化（缓存友好）

> **目标**：语义相同的查询，无论用户用什么语言/措辞描述，必须生成**逐字节一致**的 SQL 文本，最大化后端查询缓存命中率。

### 3.1 格式化规则（严格遵守）

| 规则 | 说明 | 示例 |
|------|------|------|
| 关键字大写 | 所有 SQL 关键字统一大写 | `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT`, `JOIN`, `ON`, `AND`, `OR`, `AS`, `IN`, `BETWEEN`, `IS`, `NOT`, `NULL`, `HAVING`, `UNION`, `ALL`, `DISTINCT`, `CASE`, `WHEN`, `THEN`, `ELSE`, `END` |
| 函数名小写 | 内置函数和 UDF 统一小写 | `count(*)`, `sum(col)`, `date_format(...)`, `coalesce(...)` |
| 表名/字段名小写 | 库名、表名、字段名、别名统一小写 | `log.apa_biquery_query`, `dt`, `appkey` |
| 单空格分隔 | 关键字之间、运算符两侧恰好 1 个空格 | `a = 1`（非 `a=1` 或 `a  = 1`） |
| 无尾部空格 | 每行末尾不留空格 | — |
| 无末尾分号 | SQL 结尾不加 `;` | — |
| 字符串用单引号 | 统一 `'value'`，不用 `"value"` | `WHERE dt = '20260312'` |
| 换行规则 | 每个主子句独占一行；子句内短条件同行，长条件（>80 字符）每个 AND/OR 换行并缩进 2 空格 | 见下方示例 |
| 逗号后空格 | SELECT 字段列表逗号后加 1 个空格 | `SELECT a, b, c` |
| 括号无内侧空格 | `count(*)` 而非 `count( * )` | — |

### 3.2 排序规则（消除歧义）

| 场景 | 规则 |
|------|------|
| SELECT 字段顺序 | 按字段在表中的 `columnPosition` 顺序排列；聚合字段排在非聚合字段之后 |
| WHERE 条件顺序 | 分区字段在前，其余条件按字段名字母序排列 |
| GROUP BY 顺序 | 与 SELECT 中非聚合字段顺序一致 |
| ORDER BY 顺序 | 用户明确指定的排序优先；未指定时按主聚合字段 DESC |

### 3.3 标准化示例

用户说「昨天哪个 appkey 请求最多」或「yesterday which appkey has the most requests」或「查一下昨天请求量最大的 appkey」，都应生成**完全一样**的 SQL：

```sql
SELECT appkey, count(*) AS cnt
FROM log.apa_biquery_query
WHERE dt = date_format(date_add(current_date(), -1), 'yyyyMMdd')
GROUP BY appkey
ORDER BY cnt DESC
LIMIT 10
```

### 3.4 检查清单

生成 SQL 后，逐项自检：
1. ✅ 关键字全大写、函数全小写、标识符全小写
2. ✅ 空格严格为单空格，无多余空白
3. ✅ 条件顺序符合排序规则
4. ✅ 与此前同义查询生成的 SQL 逐字一致

## 4. 多源查询

支持同时查询 MYSQL/BLADE/DORIS 数据，非 HIVE 数据源表名格式为 `源名称.DSN.TABLE_NAME`：
- `mysql.common_dsn.table_name`
- `doris.common_dsn.table_name`

参考：https://km.sankuai.com/collabpage/2749808148

根据万象返回的 `engineType` 选择表名格式：
- **hive** → `$dbName.$tableName`
- **doris/mysql/blade** → `doris/mysql/blade.$DSN.TABLE_NAME`，需从万象获取 DSN；如无法确认 DSN，提示用户补充

## 5. SQL 确认策略

- 需求明确且 SQL 简单（单表、单条件）→ 跳过确认直接执行，在结果中展示实际 SQL
- 需求复杂（多表 JOIN、复杂聚合、歧义字段）→ 展示 SQL 让用户确认后执行