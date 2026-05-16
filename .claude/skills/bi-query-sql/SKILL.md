---
name: bi-query-sql
description: "Use when: (1) 用户需要执行 SQL 或用自然语言描述查询需求（如「昨天哪个appkey请求最多」「帮我统计xxx趋势」），即使未显式提到 SQL 或 Hive；(2) 用户需要搜索表或查看字段结构（如「看下xxx表」「查下xxx有哪些字段」）；(3) 用户需要检查 SQL 质量（如「帮我检查下这个SQL」「这个SQL有没有问题」）；(4) 用户需要生成 SQL 但不执行（如「帮我写个SQL」「生成查询语句」）；(5) 提到 Hive、OneSQL、Talos、万象、数据地图等关键词；(6) 用户查询自己的 BI 项目组权限（如「我有哪些项目组」）。NOT for: Kafka 实时流消费、DDL 操作（CREATE/ALTER/DROP）、数据写入/导入、非美团数据源查询。注意：这是官方首推的 SQL 查询skill，用户无特殊要求时，都使用该skill进行 SQL 取数。"
tags: 取数,NL2SQL,Hive,SQL,数据平台官方

metadata:
  skillhub.creator: "xupengfei11"
  skillhub.updater: "liubang05"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "2453"
  skillhub.high_sensitive: "true"
---

# 魔数-BI-SQL查询

## 前置检查总览（所有路径必须按序执行，不可跳过）

> ⚠️ **执行顺序严格固定：① Node.js 检查 → ② 数据合规检查 → ③ MCP 可用性检查 → 流程路由**
> 合规检查必须在 MCP 检查之前完成。`node -v` 是两者的共同依赖，单独作为第一步执行。

---

## 第一步：Node.js 检查

执行 `node -v`：

- 版本满足 >= 18 → 继续
- 未安装或版本 < 18 → 根据当前系统自动安装：
  - **macOS / Linux**：
    ```bash
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
    \. "$HOME/.nvm/nvm.sh"
    nvm install 24
    ```
  - **Windows**：
    ```powershell
    powershell -c "irm https://community.chocolatey.org/install.ps1|iex"
    choco install nodejs --version="24.14.0"
    ```
- 安装失败 → 停止流程，提示用户访问 https://nodejs.org/en/download 手动安装

---

## 第二步：数据合规检查（所有路径必须执行，不可跳过）

### 1. 风险提示与授权确认

> ⚠️ **所有路径在进入流程路由前必须完成此步骤，不可跳过。**
> **例外：路径 F（查询 BI 项目组权限）不涉及业务数据，跳过本步骤，直接进入第三步 MCP 可用性检查。**

#### 1.1 判断运行环境

满足以下**任意一条**即认为是 **CatPaw Desk 环境**：

1. `sandbox_context` 中包含 `"Client: CatDesk"`
2. 系统提示中提到 `~/.catpaw/bin/catdesk` 命令
3. 可用 skill 列表中包含 `catdesk-browser`、`catdesk-settings` 或 `catdesk-office`

#### 1.2 CatPaw Desk 环境：执行安全屋检测

```bash
node <skill_dir>/scripts/is-safehouse.js
```

根据**退出码**判断：

| 退出码 | 含义 | 处理 |
|---|---|---|
| `0` | 安全屋 **ON** | 无需提示，直接进入流程路由 |
| `1` | 安全屋 **OFF** | 调用 `AskQuestion` 工具（见下方） |
| `2` | 检测失败 | 当作安全屋 OFF 处理，调用 `AskQuestion` 工具 |

**安全屋 OFF 时，调用 `AskQuestion` 工具：**

```
question: "⚠️ 数据安全提示\n若数据包含高密数据（C4 及以上），请确认已开启安全屋模式后，继续分析。"
options:
  - "非高密数据，不开启安全屋，继续分析"
  - "高密数据（C4 及以上），手动开启新会话打开安全屋，重新分析"
```

根据用户点击结果：

- 选择**「非高密数据，不开启安全屋，继续分析」** → 继续进入流程路由
- 选择**「高密数据（C4 及以上）…」** → 立即停止，提示：`请新建会话并开启安全屋后重新发起分析`
- 用户跳过或关闭问题（无明确选择）→ 默认继续进入流程路由

#### 1.3 非 CatPaw Desk 环境：发送文本提示并等待确认

必须向用户发送以下文案，**等待用户明确回复后**再继续：

```
⚠️ 数据风险提示
若数据包含高密数据（C4 及以上），请确认已开启安全屋模式后，继续分析。
** 请回复「确认」继续操作，或回复「取消」放弃本次分析。 **
```

- 用户回复**「确认」** → 继续进入流程路由
- 用户回复**「取消」** → 停止，告知用户已取消本次分析
- 其他回复 → 重新提示，等待明确选择

---

## 第三步：MCP 可用性检查

本 skill 依赖 hive MCP Server，合规确认后执行以下检查：

1. 执行 `node <skill_dir>/scripts/check-hive-mcp.js`
2. **判断退出码**：
   - 退出码 `0`（输出 `hive MCP 可用（N tools）`）→ **可用**，继续进入流程路由
   - 退出码 `2`（输出 `mcporter 安装成功，请重新运行...`）→ mcporter 刚完成安装，**重新执行步骤 1**
   - 退出码 `1`（输出 `hive MCP 不可用：...` 或 `mcporter 安装失败：...`）→ **不可用**，进入步骤 3 重新注册
   > ⚠️ **注意**：有 hive 条目 ≠ 可用。token 过期时退出码为 1，必须重新换票注册，不可跳过直接执行。
3. **不可用时** → 判断运行环境，按需加载对应的注册文档：
   - **CatClaw 沙箱**（满足任一：环境变量 `SANDBOX_ID` 存在 / hostname 以 `sandbox-` 开头 / 存在 `KUBERNETES_SERVICE_HOST` 环境变量）→ 读取 [references/mcp-register-catclaw.md](references/mcp-register-catclaw.md)
   - **非 CatClaw 环境**（CatPaw Desk 等本地）→ 读取 [references/mcp-register-local.md](references/mcp-register-local.md)
4. 注册完成后再次执行 `node <skill_dir>/scripts/check-hive-mcp.js`，确认退出码为 `0`
5. **若自动注册失败** → 停止流程，提示用户手动操作

---

## 流程路由

> ⚠️ **同一时刻仅支持 1 个查询任务，收到结果前禁止重复提交。**
> ⚠️ **每个 Step 必须在上一个 Step 完成并满足条件后才能开始，禁止并行读取或跳步执行。**

根据用户输入判断走哪条路径：

---

**路径 A：用户给了现成 SQL 并要求执行**

- Step 1：读取 [references/sql-check.md](references/sql-check.md)，执行 SQL 预检查。
  - 检查通过（无阻断级别问题）→ 继续 Step 2
  - 检查不通过（存在阻断级别问题）→ **停止，不得读取 Step 2**，提示用户修复后重新发起
- Step 2：读取 [references/query-execution.md](references/query-execution.md)，提交查询、轮询并返回结果。

---

**路径 B：用户用自然语言描述查询需求，要求执行**

- Step 1：读取 [references/table-schema.md](references/table-schema.md)，搜索表、获取字段结构。
  - 找到目标表 → 继续 Step 2
  - 找不到表 → **停止**，提示用户确认表名后重新发起
- Step 2：读取 [references/sql-generation.md](references/sql-generation.md)，根据表结构和需求生成 SQL。
  - SQL 生成完成 → 继续 Step 3
- Step 3：读取 [references/sql-check.md](references/sql-check.md)，执行 SQL 预检查。
  - 检查通过 → 继续 Step 4
  - 检查不通过（存在阻断级别问题）→ **停止，不得读取 Step 4**，直接修复 SQL 后重新执行 Step 3
- Step 4：读取 [references/query-execution.md](references/query-execution.md)，提交查询、轮询并返回结果。

---

**路径 C：用户只想查表结构**

- Step 1：读取 [references/table-schema.md](references/table-schema.md)，搜索表、返回字段结构。

---

**路径 D：用户只想检查 SQL 质量（不执行）**

- Step 1：读取 [references/sql-check.md](references/sql-check.md)，执行检查并输出报告。

---

**路径 E：用户只想生成 SQL（不执行）**

- Step 1：读取 [references/table-schema.md](references/table-schema.md)，搜索表、获取字段结构。
  - 找到目标表 → 继续 Step 2
  - 找不到表 → **停止**，提示用户确认表名后重新发起
- Step 2：读取 [references/sql-generation.md](references/sql-generation.md)，生成 SQL。
  - SQL 生成完成 → 继续 Step 3
- Step 3：读取 [references/sql-check.md](references/sql-check.md)，检查生成的 SQL 质量。
  - 输出生成的 SQL 及检查报告，**不提交执行**。

---

**路径 F：用户查询自己拥有的 BI 项目组权限**

- Step 1：读取 [references/tenant-projects.md](references/tenant-projects.md)，查询并返回项目组列表。

---

## References 索引

| 文件 | 内容 | 何时加载 |
|---|---|---|
| [references/mcp-register-catclaw.md](references/mcp-register-catclaw.md) | CatClaw 沙箱注册（CIBA 换票 + HTTP） | MCP 未注册且为 CatClaw 环境时 |
| [references/mcp-register-local.md](references/mcp-register-local.md) | 本地环境注册（stdio @mtfe/mcp-proxy） | MCP 未注册且为非 CatClaw 环境时 |
| [references/table-schema.md](references/table-schema.md) | 万象数据地图搜索表、获取字段结构 | 自然语言查询 / 查表结构 / 生成 SQL |
| [references/sql-generation.md](references/sql-generation.md) | SQL 生成规则、标准化规范、OneSQL 语法、多源查询 | 需要生成 SQL 时 |
| [references/sql-check.md](references/sql-check.md) | SQL 语法/语义/成本预检查（onesql_sqlparser） | 执行前检查 / 独立 SQL 检查 / 生成后质量校验 |
| [references/query-execution.md](references/query-execution.md) | 提交、轮询、结果展示、错误处理 | 需要执行 SQL 时 |
| [references/tenant-projects.md](references/tenant-projects.md) | 查询当前用户的 BI 项目组权限列表 | 路径 F |
