# BI 项目组权限查询

## 说明

通过 `hive.search_tenant_projects` 工具查询当前用户所拥有的 BI 项目组权限。
该接口返回**当前认证用户**已加入的项目组列表（`isJoin: true`），无需额外传入用户标识。

---

## 执行步骤

### 1. 调用接口

分页拉取所有项目组（每页 50 条，直到取完为止）：

```bash
node <skill_dir>/scripts/bin/mcporter.js call 'hive.search_tenant_projects(page: 1, page_size: 50)'
```

- 若 `total > 50`，继续翻页（`page: 2`、`page: 3` …）直到取完
- 过滤条件：`isJoin === true`（接口本身只返回已加入的，但仍需确认字段）

### 2. 结果展示

以表格形式展示，包含以下字段：

| 列名 | 字段 | 说明 |
|---|---|---|
| 项目组名 | `name` | 英文标识，提交查询时 `doasGroup` 用此值 |
| 中文名 | `chName` | 中文描述 |
| 管理员 | `admin` | MIS 号 |
| 关联数据库 | config.db | 从 `config` JSON 字段中解析 |
| 引擎 | config.engine_type | 从 `config` JSON 字段中解析 |
| 描述 | `description` | 项目组用途说明 |

> `config` 字段是 JSON 字符串，需解析后取 `db`、`engine_type`。

### 3. 使用提示

展示结果后，补充以下说明：

> 💡 提交查询时，可通过 `doasGroup` 参数指定项目组，不同项目组对应不同的数据库权限和计算资源配额。

---

## 错误处理

| 场景 | 处理 |
|---|---|
| `items` 为空数组 | 提示用户当前账号暂无任何 BI 项目组权限，建议联系管理员申请 |
| MCP 不可用 | 提示连接 hive MCP Server，参考 SKILL.md 中的前置检查步骤 |
| `config` 字段解析失败 | 该字段显示为 `-`，不影响整体展示 |
