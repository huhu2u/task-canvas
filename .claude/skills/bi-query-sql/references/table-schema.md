# 表结构获取


## 1. 搜索表

```bash
node <skill_dir>/scripts/bin/mcporter.js call 'hive.search_table_with_keyword(q: "<关键词>", page_size: 10)'
```

带过滤条件（如只搜 Hive 表）：

```bash
node <skill_dir>/scripts/bin/mcporter.js call 'hive.search_table_with_keyword(q: "<关键词>", filters: {"engine_type_list": ["hive"]}, page_size: 10)'
```

**参数：**
- `q`：搜索关键词
- `filters`：二次过滤，如 `{"engine_type_list": ["hive"]}`
- `page_num`：页码，默认 1
- `page_size`：每页条数，默认 10

**返回数据解析：**

表级信息：
- `total`：匹配总数
- `list`：表列表，每个表包含 `id`、`tableSchema`（库名）、`tableName`、`fullName`、`engineType`、`tableComment`、`heat`（热度）、`ownerList`、`projectGroup`、`securityLevel`（表安全等级）、`layer`（数仓分层）

字段级信息（每个表的 `columnList`）：
- `columnName`：字段名
- `columnType`：字段类型
- `columnComment`：字段说明
- `columnPosition`：字段位置
- `isPartitionColumn`：是否分区字段（boolean）
- `securityLevel`：字段安全等级
- `heat`：字段热度
- `isImportant`：是否重要字段
- `isGrain`：是否粒度字段

> 注意：返回的 `tableName`、`fullName` 以及 `columnName` 中关键字会被 `[<>]` 高亮标记包裹（如 `[<query>]_id`），展示给用户时需去掉这些标记，还原为原始名称。

## 2. 多表确认

- 1 张表 → 直接展示字段结构
- 多张表 → **必须列出所有结果让用户选择，禁止自动选择**（包括按热度猜测）
- 原因：skill 面向全公司，不同团队对同名表需求不同，热度不代表用户真实意图

## 3. 展示格式

**必须使用 Markdown 表格**：

| 字段名 | 类型 | 说明 | 安全等级 |
|---|---|---|---|

规则：
- 先输出表元信息（表名、引擎、描述、表安全等级），再输出字段表格
- 字段按 `columnPosition` 排序，分区字段排在末尾
- 分区字段在说明列末尾标注 `⚡分区`
- 安全等级列显示 `C-{securityLevel}`（如 `C-2`、`C-3`、`C-4`）
- C-4 高敏字段额外标注 `🔒`（如 `🔒C-4`）
- 末尾汇总：共 X 个字段，其中 X 个分区字段
