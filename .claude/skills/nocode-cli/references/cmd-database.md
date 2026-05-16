# database 命令详细规则

## 概述

`nocode database` 命令组用于直接操作作品关联的数据库。所有数据操作统一通过后端 SQL 执行，所有输出为 JSON `{ action, status, data }` 格式。

> **说明**：NoCode 平台的数据库底层基于 Supabase（PostgreSQL），`nocode database` 命令操作的就是作品关联的 Supabase 数据库。文档中 "database" 和 "Supabase" 指的是同一个东西。

## database status — 查看数据库连接状态

```bash
nocode database status <chatId>
```

**输出示例（已连接且已确认）：**
```json
{
  "action": "status",
  "status": "success",
  "data": {
    "connected": true,
    "databaseType": "supabase_cloud",
    "isConfirmed": true,
    "url": "https://dbxxx.database.sankuai.com"
  }
}
```

**输出示例（有关联资源但未确认连接）：**
```json
{
  "action": "status",
  "status": "success",
  "data": {
    "connected": true,
    "databaseType": "supabase_cloud",
    "isConfirmed": false,
    "url": "https://dbxxx.database.sankuai.com"
  }
}
```

> ⚠️ `connected: true` 但 `isConfirmed: false` 表示对话有关联的 database 资源，但尚未完成连接确认。此时数据库**不可用**，需要通过 `create`（新建）或 `projects` + `connect`（复用既有）重新建立连接。

**输出示例（未连接）：**
```json
{
  "action": "status",
  "status": "success",
  "data": { "connected": false, "message": "该作品未关联数据库" }
}
```

- 只读操作，不加并发锁

## database create — 创建数据库实例

```bash
nocode database create <chatId>
```

**完整流程：**
1. 检查是否已连接且已确认 → 是则直接返回 `{ created: false }`（幂等）
2. 分配数据库资源（`/api/supabase/cloud/connect`）
3. 写入配置到容器（`/api/plugin/overwrite`）
4. 执行插件接入（`/api/plugin/access`，安装依赖、生成代码）
5. 设置 SQL 自动执行模式为 ALWAYS_ALLOW

**输出示例：**
```json
{ "action": "create", "status": "success", "data": { "created": true } }
```

**⚠️ 注意：**
- 该操作耗时较长（可能 30 秒以上），并发锁超时 5 分钟
- 作品必须已初始化（通过 `nocode create` 创建），否则会报 500 错误
- 幂等：重复调用不会重复创建
- 如需复用既有 database 而非新建，请使用 `projects` + `connect` 命令

## database projects — 列出既有 database 项目

```bash
nocode database projects <chatId>
```

列出当前用户名下所有的 database 项目（不暴露 anonKey）。

**输出示例：**
```json
{
  "action": "projects",
  "status": "success",
  "data": [
    { "name": "Supabase-xxx", "url": "https://db1.database.sankuai.com" },
    { "name": "Supabase-xxx", "url": "https://db2.database.sankuai.com" }
  ]
}
```

- 只读操作，不加并发锁
- 空列表说明用户没有既有资源，需要通过 `create` 新建

## database connect — 关联既有 database 项目

```bash
nocode database connect <chatId> --url <databaseUrl>
```

将既有的 database 项目关联到当前对话。`--url` 从 `projects` 命令的输出中获取。

**完整流程：**
1. 调 `/api/supabase/myprojects` 获取项目列表，匹配 `--url` 对应的 anonKey
2. 调 `/api/supabase/cloud/connect`，type=CONNECT
3. pluginOverwrite + accessPlugin + setSqlAutoExecute

**输出示例：**
```json
{ "action": "connect", "status": "success", "data": { "connected": true } }
```

**⚠️ 注意：**
- `--url` 必须是 `projects` 列表中存在的 URL，否则报错
- 关联后两个对话共享同一个数据库，数据同步

## database tables — 查看表结构

```bash
nocode database tables <chatId>                # 输出 JSON 表结构
nocode database tables <chatId> --ddl          # 输出 CREATE TABLE SQL
nocode database tables <chatId> --schema xxx   # 指定 schema（默认 public）
```

- 只读操作，不加并发锁

**JSON 输出示例：**
```json
{
  "action": "tables",
  "status": "success",
  "data": [
    {
      "table_name": "todos",
      "table_comment": "",
      "columns": [
        { "columnName": "id", "dataType": "bigint", "primaryKey": true, "isNullable": "NO", "columnDefault": "nextval(...)" },
        { "columnName": "title", "dataType": "text", "primaryKey": false, "isNullable": "NO", "columnDefault": null },
        { "columnName": "done", "dataType": "boolean", "primaryKey": false, "isNullable": "YES", "columnDefault": "false" }
      ]
    }
  ]
}
```

**DDL 输出示例（--ddl）：**
```json
{
  "action": "tables",
  "status": "success",
  "data": "CREATE TABLE \"public\".\"todos\" (\n  \"id\" bigint NOT NULL DEFAULT nextval(...),\n  \"title\" text NOT NULL,\n  \"done\" boolean DEFAULT false,\n  PRIMARY KEY (\"id\")\n);"
}
```

## database select — 分页查询表数据

```bash
nocode database select <chatId> --table <name>
nocode database select <chatId> --table <name> --page 2 --size 20
nocode database select <chatId> --table <name> --schema myschema
```

**必需参数：** `--table`
**可选参数：** `--page`（默认 1）、`--size`（默认 50）、`--schema`（默认 public）

- 只读操作，不加并发锁

**输出示例：**
```json
{
  "action": "select",
  "status": "success",
  "data": {
    "totalRows": 100,
    "data": [{ "id": 1, "name": "test" }]
  }
}
```

## database insert — 插入数据

```bash
# 单条插入
nocode database insert <chatId> --table <name> --data '{"name":"test","age":18}'

# 批量插入（--data 传 JSON 数组）
nocode database insert <chatId> --table <name> --data '[{"name":"a"},{"name":"b"},{"name":"c"}]'

# 传入表结构跳过内部查询（可选优化）
nocode database insert <chatId> --table <name> --data '{...}' --table-schema '<tables 命令返回的单表 JSON>'
```

**必需参数：** `--table`、`--data`
**可选参数：** `--schema`（默认 public）、`--table-schema`（表结构 JSON，传入则跳过内部查询）

**输出：** 返回插入后的完整行数据（含自增 ID、默认值等）

```json
{
  "action": "insert",
  "status": "success",
  "data": [ { "id": 1, "name": "test", "age": 18, "created_at": "..." } ]
}
```

## database update — 更新数据

```bash
nocode database update <chatId> --table <name> --id <id> --data '{"name":"new_name"}'
nocode database update <chatId> --table <name> --id <id> --data '{"name":"new"}' --id-column uuid

# 传入表结构跳过内部查询（可选优化）
nocode database update <chatId> --table <name> --id <id> --data '{...}' --table-schema '<tables 命令返回的单表 JSON>'
```

**必需参数：** `--table`、`--id`、`--data`
**可选参数：** `--schema`（默认 public）、`--id-column`（主键列名，默认 id）、`--table-schema`（表结构 JSON）

- `--data` 必须是单个 JSON 对象（不支持批量更新）
- 返回更新后的完整行数据

## database delete — 删除数据

```bash
# 删除单条
nocode database delete <chatId> --table <name> --id 1

# 批量删除（逗号分隔）
nocode database delete <chatId> --table <name> --id 1,2,3

# 自定义主键列名
nocode database delete <chatId> --table <name> --id abc --id-column uuid

# 传入表结构跳过内部查询（可选优化）
nocode database delete <chatId> --table <name> --id 1 --table-schema '<tables 命令返回的单表 JSON>'
```

**必需参数：** `--table`、`--id`
**可选参数：** `--schema`（默认 public）、`--id-column`（主键列名，默认 id）、`--table-schema`（表结构 JSON）

- 返回被删除的行数据

## ⚠️ 调用规则（强制）

### 前置检查

- 操作数据前，先用 `nocode database status <chatId>` 确认数据库已连接
- 检查 status 返回值中的 `isConfirmed` 字段：
    - `connected: true` 且 `isConfirmed: true` → 数据库可用，可直接操作
    - `connected: true` 但 `isConfirmed: false` → 有关联资源但未确认，数据库**不可用**，需询问用户是新建（`create`）还是复用既有（`projects` + `connect`）
    - `connected: false` → 未连接，询问用户是新建（`create`）还是复用既有（`projects` + `connect`）
- 操作表数据前，可先用 `nocode database tables <chatId>` 确认表名和字段

### 写操作需确认

- 执行 `insert`、`update`、`delete` 前，**必须先向用户确认操作内容**（如表名、数据、ID 等），经用户同意后再执行

### 并发控制

- 只读操作（`status`、`projects`、`tables`、`select`）不加锁，可并发执行
- 写操作（`create`、`connect`、`insert`、`update`、`delete`）加锁，同一 chatId 同一时刻只允许一个
- 收到 `当前有其他数据库操作正在执行` 错误时，等 3-5 秒后重试
- `create` 和 `connect` 操作耗时较长，不要超时中断

### 输出解析

所有命令统一输出 JSON：
- `status === 'success'` → 操作成功，数据在 `data` 字段
- `status === 'error'` → 操作失败，错误信息在 `message` 字段

## ⚠️ 异常处理

| 错误信息 | 处理方式 |
|---------|---------|
| `当前有其他数据库操作正在执行` | 等 3-5 秒重试，最多 2 次 |
| `创建数据库实例失败` | 检查作品是否已通过 `nocode create` 初始化 |
| `SQL 执行失败` | 检查表名、字段名、数据格式是否正确 |
| `该作品未关联数据库` 或 `isConfirmed: false` | 询问用户：① 创建新的 → `nocode database create <chatId>`；② 复用既有的 → `nocode database projects <chatId>` 查看可用项目，然后 `nocode database connect <chatId> --url <url>` |
| `未找到该 database 项目` | 检查 `--url` 是否正确，先用 `projects` 确认可用列表 |
| `--data 格式错误` | 确保传入合法 JSON 字符串 |
| `--table 参数缺失` | select/insert/update/delete 必须指定 --table |

## 💡 典型使用场景

### 场景 1：为新作品创建数据库并建表

```bash
nocode database create <chatId>                    # 创建数据库
nocode send <chatId> "创建一个 todos 表，包含 id、title、done 字段"  # 让 Agent 建表
nocode database tables <chatId>                    # 确认表结构
```

### 场景 2：复用既有 database

```bash
nocode database projects <chatId>                                    # 列出既有项目
nocode database connect <chatId> --url "https://dbxxx.database.sankuai.com"  # 关联选中的项目
nocode database tables <chatId>                                      # 确认表结构
```

### 场景 3：查询和修改数据

```bash
nocode database tables <chatId>                    # 先看有哪些表
nocode database select <chatId> --table todos      # 查询数据
nocode database insert <chatId> --table todos --data '{"title":"买菜","done":false}'  # 插入
nocode database update <chatId> --table todos --id 1 --data '{"done":true}'  # 更新
nocode database delete <chatId> --table todos --id 1  # 删除
```

### 场景 4：批量操作

```bash
# 批量插入
nocode database insert <chatId> --table todos --data '[{"title":"买菜","done":false},{"title":"写代码","done":false}]'

# 批量删除
nocode database delete <chatId> --table todos --id 1,2,3
```

### 场景 5：传入表结构优化性能

```bash
# 1. 先获取表结构
nocode database tables <chatId>
# 从返回的 data 数组中取出目标表的 JSON 对象

# 2. 后续 insert/update/delete 通过 --table-schema 传入，跳过内部重复查询
nocode database insert <chatId> --table todos --data '{...}' --table-schema '<单表结构 JSON>'
nocode database update <chatId> --table todos --id 1 --data '{...}' --table-schema '<单表结构 JSON>'
nocode database delete <chatId> --table todos --id 1 --table-schema '<单表结构 JSON>'
```

> ℹ️ `--table-schema` 为可选优化，不传时内部会自动查询表结构。传入后可避免每次写操作额外的一次表结构查询，适合连续多次操作同一张表的场景。

## ℹ️ 空字符串处理规则

insert/update 时，空字符串 `""` 的处理会根据字段类型自动区分：

| 字段类型 | 空字符串处理 | 示例 |
|---------|------------|------|
| text / varchar / char | 保留为 `''` | `"bio": ""` → SQL `''` |
| integer / numeric / bigint | 转为 `NULL` | `"age": ""` → SQL `NULL` |
| timestamp / date / time | 转为 `NULL` | `"created_at": ""` → SQL `NULL` |
| boolean | 按布尔处理 | `"done": false` → SQL `false` |
| json / jsonb | 按 JSON 处理 | `"meta": "{}"` → SQL `'{}'::jsonb` |

> 此行为与 NoCode 主站前端保持一致。如未获取到表结构信息（降级场景），所有空字符串会统一转为 `NULL`。
