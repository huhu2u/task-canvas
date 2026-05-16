---
name: nocode-cli
description: 通过 NoCode CLI 操作美团 NoCode 零代码平台。当用户要求创建/修改零代码应用、截图预览、部署上线、管理项目、查看工程文件、操作数据库，或提及 "nocode"、"零代码"、"NoCode" 时使用。

metadata:
  skillhub.creator: "zhaomenghuan02"
  skillhub.updater: "wanghongzhou03"
  skillhub.version: "V4"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "2981"
  skillhub.high_sensitive: "false"
---

# NoCode CLI Skill

## ⛔ 核心约束

1. **严禁使用 fetch / web_fetch / curl / HTTP 请求等方式直接请求 NoCode API 接口。** 所有操作必须且只能通过 `nocode` CLI 命令完成。
2. **向 NoCode Agent 发送命令时（`nocode create` / `nocode send`），必须使用自然语言描述需求。** 严禁在 prompt 中包含以下内容：
   - ❌ 执行具体命令（如 `git commit`、`npm build`、`yarn build`、`npm install`、`pnpm run`、`pip install` 等）
   - ❌ 指定使用某个工具或 MCP 工具（如 "使用 xxx 工具"、"调用 xxx MCP" 等）
   - ❌ 发送 shell 脚本、代码片段让 Agent 执行
   - ✅ 正确做法：用自然语言描述你想要的结果，例如 "把标题颜色改成红色"、"添加一个用户注册表单"、"创建一个 todos 表包含 id、title、done 字段"
   - ✅ 例外：可以在自然语言中附带 SQL 语句，例如 "帮我执行以下 SQL 建表：CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT)"
   - ✅ 例外：定位到问题后，可以在自然语言中附带相关代码片段供 Agent 参考，例如 "这段代码有问题，请修复：`const data = fetch('/api')`，应该加上 await"
3. **遇到渲染异常、部署异常等平台侧异常时，严禁自行尝试解决。** 必须立即停止操作，引导用户联系 NoCode 研发排查处理。详见 [异常处理规则](#-异常处理规则)

## 前置准备

### 版本检查（每次执行前必须）

```bash
nocode --version
npm view @nocode/nocode-cli version --registry=http://r.npm.sankuai.com
```

- 未安装 → `npm install -g @nocode/nocode-cli --registry=http://r.npm.sankuai.com`
- 本地版本 < 最新版本 → 重新安装升级
- 已是最新 → 继续

### 登录状态检查（版本检查后必须执行）

执行 `nocode status` 检查环境和登录状态：
- 已登录 → 继续（会显示当前登录方式：CIBA / SSO OIDC / token）
- 未登录 → `nocode status` 会根据运行环境推荐登录命令，按提示执行即可：
  - **CatClaw 环境**：推荐 `nocode login --mis <mis>`，提示 **"请在大象 App 确认登录"**
  - **非 CatClaw 环境**：推荐 `nocode login --sso`（SSO OIDC 浏览器登录），备选 `nocode login --token <access-token>`
- 如登录仍存在问题，请联系 NoCode 研发。**不推荐直接使用浏览器操作 NoCode 平台。**
- 输出包含 `⚠️  发现新版本` → **应该暂停后续操作内容，询问用户是否更新 CLI 和 Skill版本**

**获取 MIS 号**：先读 `~/.openclaw/openclaw.json` 中的 `X-User-Id`，读不到再问用户。不要猜测。

**⚠️ Token 过期自动续期（执行 API 类命令时可能触发）：**

执行 `create`、`send`、`deploy`、`list`、`screenshot`、`files list`、`files get` 等需要调用 API 的命令时，如果检测到 Token 过期，CLI 会根据登录方式自动续期：
- **SSO OIDC 登录**：自动静默续期
- **CIBA 登录**：自动重新换票

## 关键概念

- **NoCode Agent**：运行在云端 IDE 容器中的 AI，通过 `nocode create` / `nocode send` 命令触发，能自动生成代码、建表、安装依赖等。详见 [NoCode Agent 能力说明](references/nocode-agent-capabilities.md)
- **环境切换**：所有命令支持 `--env prod`（默认）/ `--env test`

## ⚠️ 强制约束

- **send 必须串行**：同一 chatId 不得同时执行多个 `nocode send`，必须等上一个完成（收到 `done`）后再执行下一个
- **严禁展示 renderUrl**（形如 `https://xxx.sandbox.nocode.sankuai.com`），仅供内部截图使用
- **chatId 链接格式**：向用户展示时必须使用 Markdown 格式 `[{chatId}]({chatUrl})`（可同时展示纯文本 chatId 供复制）
- **部署地址链接格式**：向用户展示时必须使用 Markdown 链接格式 `[{externalUrl}]({externalUrl})`
- 禁止以纯文本输出 URL，所有面向用户的链接必须可点击
- **打开页面用 `chatUrl`**（`https://nocode.sankuai.com/#/chat?pageId=xxx`），不要用 renderUrl
- **禁止拉取工程代码本地迭代**：不推荐拉取 NoCode 对话工程代码到本地的方式迭代作品，该方式 NoCode 官方 Skill 暂不支持。所有修改必须通过 `nocode send` 命令发送给 NoCode Agent 完成

## 💡 最佳实践

- **合理拆分 send 内容**：复杂需求拆分为多个小步骤分次发送，禁止一次性塞入过多内容
- **查看文件用 files 命令**：`nocode files list` / `nocode files get`，不推荐通过 `nocode send` 获取文件内容
- **建表/改表用 NoCode Agent**：CLI `database` 命令仅支持数据 CRUD，DDL 操作推荐 `nocode send <chatId> "创建一个 xxx 表..."`
- **数据库状态判断**：`database status` 返回 `isConfirmed: false` 时，即使 `connected: true`，数据库也不可用，需通过 `create`（新建）或 `projects` + `connect`（复用既有）重新建立连接
- **数据库 SQL 自动执行**：CLI 创建的数据库默认自动执行 SQL。非 CLI 创建的需在主站将 SQL 执行模式调为"始终允许"

## 命令速查

**⚠️ 强制规则：执行有"详细规则"链接的命令前，必须先读取对应的 references 文件，按其中的规则执行。不可跳过。**

| 命令 | 用途 | 详细规则（执行前必读） |
|------|------|---------|
| `nocode create "<prompt>"` | 创建应用 | ⚠️ [必读](references/cmd-create-send.md) |
| `nocode send <chatId> "<msg>"` | 发送修改 | ⚠️ [必读](references/cmd-create-send.md) |
| `nocode files list <chatId> [path]` | 查看目录树 | ⚠️ [必读](references/cmd-files.md) |
| `nocode files get <chatId> <path>` | 查看文件内容 | ⚠️ [必读](references/cmd-files.md) |
| `nocode screenshot <chatId>` | 截图预览 | ⚠️ [必读](references/cmd-screenshot.md) |
| `nocode deploy <chatId>` | 部署上线 | ⚠️ [必读](references/cmd-deploy.md) |
| `nocode list` | 项目列表 | `--page N --size N --json` |
| `nocode detail <chatId>` | 查看详情 | JSON 输出 |
| `nocode versions <chatId>` | 版本列表 | — |
| `nocode delete <chatId> --confirm` | 删除项目 | — |
| `nocode database <action> <chatId>` | 数据库操作（status/create/connect/projects/tables/select/insert/update/delete） | ⚠️ [必读](references/cmd-database.md) |

## 命令概要

| 命令 | 一句话说明 |
|------|-----------|
| **create / send** | NDJSON 流式输出，需后台执行 + poll。调用前确认上一轮 poll 已收到 `done` |
| **files list** | 输出 `---TREE_START---` / `---TREE_END---` 边界标记，目录以 `/` 结尾，按行 split 提取。讨论页面问题时先查目录定位文件 |
| **files get** | 输出 `---FILE_CONTENT_START---` / `---FILE_CONTENT_END---` 边界标记，单文件串行读取。读取代码内容辅助精确定位问题 |
| **screenshot** | 返回 S3 URL，截图失败不阻塞流程 |
| **deploy** | 自动使用最新版本部署，渲染失败会拦截 |
| **database** | 所有子命令统一输出 JSON `{ action, status, data }`。支持批量插入（--data 传数组）和批量删除（--id 1,2,3） |

## 典型工作流

```bash
# 1. 登录
nocode login --mis <mis>

# 2. 创建（NDJSON 流式输出，done 事件包含 chatId）
nocode create "做一个宣传页面"

# 3. 修改
nocode send <chatId> "把主色调改成深蓝色"

# 4. 截图确认
nocode screenshot <chatId>

# 5. 部署
nocode deploy <chatId>

# 6. 遇到问题时：先查代码再精确修改（禁止用 send 获取文件内容）
nocode files list <chatId>                        # 查看工程目录结构
nocode files list <chatId> src                    # 浏览子目录
nocode files get <chatId> src/App.jsx             # 读取相关文件内容
# → 分析代码，定位问题原因
nocode send <chatId> "具体的修改指令"        # 发送精确修改
nocode screenshot <chatId>                  # 截图确认修改效果
```

## 容器状态检查机制

**概述：** `screenshot`、`send`、`files list`、`files get` 命令执行前会自动检查容器状态。

**检查流程：**
1. 调用 `/api/chat/getRenderUrlInfo` 获取容器信息
2. 如容器已停止，自动触发冷启动
3. 轮询等待容器就绪（默认超时 5 分钟，轮询间隔 3 秒）
4. 验证渲染 URL 可用性

**返回值：**
- `renderUrl`: 渲染 URL
- `coldStart`: 是否经历了冷启动
- `skipUrlCheck`: 是否跳过 URL 可用性检查

## 常见错误速查

| 错误信息 | 解决方案 |
|----------|---------|
| `未登录，请先执行 nocode login` | 执行 `nocode status` 按提示登录 |
| `busy` 事件 | 等待上一轮 `done`，经用户确认后重试 |
| `Agent 处理失败` | 第 1 次询问重试，第 2 次停止并联系研发 |
| `容器启动等待超时` | 检查网络或稍后重试 |
| `该作品尚未初始化 IDE 容器` | 先通过 `nocode send` 生成代码 |
| `当前有其他文件操作正在执行` | 等几秒后重试，最多 2 次 |
| `暂无可部署版本` | 先创建或修改生成代码 |
| `最新版本渲染失败，无法部署` | **⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查处理 |
| `获取文件内容失败` | 检查路径，先用 `nocode files list <chatId>` 确认文件存在 |
| 截图显示页面白屏 / 渲染异常 | **⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查处理 |
| 部署后页面无法访问 / 显示异常 | **⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查处理 |

## 🚨 异常处理规则

**核心原则：遇到平台侧异常时，严禁自行尝试解决，必须立即引导用户联系 NoCode 研发排查。**

### 必须立即停止并引导用户联系研发的场景

以下异常属于平台侧问题，**禁止自行尝试修复、重试或绕过**：

| 异常类型 | 典型表现 | 处理方式 |
|---------|---------|---------|
| **渲染异常** | 截图显示白屏、页面无法正常渲染、渲染状态为失败 | 停止操作，告知用户："⚠️ 页面渲染出现异常，请联系 NoCode 研发排查处理" |
| **部署异常** | 部署失败、部署后页面无法访问、部署后显示异常 | 停止操作，告知用户："⚠️ 部署出现异常，请联系 NoCode 研发排查处理" |
| **容器异常** | 容器启动超时、容器反复崩溃、容器状态异常 | 停止操作，告知用户："⚠️ 容器环境出现异常，请联系 NoCode 研发排查处理" |
| **Agent 连续失败** | 同一 chatId 连续 2 次 `error` 事件 | 停止操作，告知用户："⚠️ 该对话已连续失败 2 次，请联系 NoCode 研发排查" |
| **其他平台异常** | CLI 返回非预期错误、API 调用异常、数据不一致等 | 停止操作，向用户反馈错误信息并建议联系 NoCode 研发 |

### 禁止的处理方式

- ❌ 尝试通过 `nocode send` 让 Agent 修复渲染问题（如 "修复页面白屏"、"解决渲染报错"）
- ❌ 反复重试部署命令期望异常自行恢复
- ❌ 尝试通过修改代码绕过渲染/部署异常
- ❌ 猜测异常原因并自行实施修复方案
- ❌ 在不告知用户异常情况的前提下静默重试

### 正确的处理模板

```
⚠️ [操作类型]出现异常：[具体错误信息]

该问题属于平台侧异常，建议联系 NoCode 研发排查处理。
```
