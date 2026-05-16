# NoCode Agent 能力说明

## 什么是 NoCode Agent

NoCode Agent 是运行在 NoCode 平台云端 IDE 容器中的 AI，通过 `nocode create` 和 `nocode send` 命令触发。它能自动生成和修改前端代码，还能通过内置的 Skill 调用云数据库等后端能力。

## NoCode Agent 内置 Skill

通过 `nocode send` 发送相关需求时会自动触发对应 Skill：

| Skill | 能力 | 触发场景 |
|-------|------|---------|
| **nocode-cloud** | Supabase 云数据库 + 文件存储 | 建表、改表、SQL 执行、文件上传下载、存储桶管理 |

### nocode-cloud — 云数据库与存储

- **数据库**：Supabase PostgreSQL，支持建表、改表、SQL 执行、表结构查询
- **存储**：文件上传下载、存储桶管理
- **前端集成**：通过 `import { supabase } from "@/integrations/supabase/client"` 在代码中调用
- **适用场景**：需要持久化数据存储的应用（用户数据、配置、文件等）

## 对外部 Agent 的意义

通过 `nocode send` 向 NoCode Agent 发送需求时，可以包含以下类型的请求：

1. **纯前端**：修改页面样式、布局、交互、添加组件
2. **前端 + 数据库**：创建带数据存储的应用（如待办事项、数据管理）

**示例：**

```bash
# 纯前端修改
nocode send <chatId> "把标题改成红色"

# 建表（推荐通过 Agent 完成，会自动处理 SQL 和代码集成）
nocode send <chatId> "创建一个 todos 表，包含 id、title、done 字段"
```

NoCode Agent 会根据需求自动判断是否需要调用 cloud 等 Skill，外部 Agent 无需关心具体的 MCP 工具调用细节。

## NoCode Agent 与 CLI database 命令的分工

| 操作 | 推荐方式 | 说明 |
|------|---------|------|
| 创建数据库实例 | `nocode database create <chatId>` | CLI 直接调用 API |
| 建表、改表、加字段 | `nocode send <chatId> "..."` | 让 Agent 处理 DDL + 代码集成 |
| 查看表结构 | `nocode database tables <chatId>` | CLI 直接查询，JSON 输出 |
| 查看建表 SQL | `nocode database tables <chatId> --ddl` | CLI 直接输出 DDL |
| 查询数据 | `nocode database select <chatId> --table <name>` | CLI 直接查询 |
| 插入/更新/删除数据 | `nocode database insert/update/delete ...` | CLI 直接操作 |
| 判断是否已连接数据库 | `nocode database status <chatId>` | CLI 直接查询 |

**核心原则：结构变更（DDL）交给 Agent，数据操作（DML）用 CLI database 命令。**

