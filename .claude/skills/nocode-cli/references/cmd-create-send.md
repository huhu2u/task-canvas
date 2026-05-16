# create & send 命令详细规则

## create — 创建应用（核心命令）

自动完成：创建对话 → AI 流式生成 → 等待渲染 → 截图预览。输出 NDJSON，耗时约 2-5 分钟。

**内部已包含容器就绪检查：** `waitForRender` 会自动等待 sandbox 渲染就绪，包括容器冷启动（如需要）。

```bash
nocode create "帮我做一个 TODO 应用"
nocode create "做一个博客" --template nocode-react-roo
nocode create "做一个落地页" --platform web
```

**⚠️ prompt 必须使用自然语言（强制）：** 用自然语言描述要创建的应用，禁止在 prompt 中包含具体命令（如 `npm`、`git`、`yarn` 等）或指定使用某个工具。

**`--template` 可选值：**

| 值 | 说明 |
|---|------|
| `default` | 默认工程（默认值） |
| `nocode-miniprogram-web` | 小程序 Web 页面 |
| `nocode-react-mtd` | React 框架 + MTD 组件库 |
| `nocode-vue-mtd` | Vue 框架 + MTD 组件库 |
| `nocode-react-roo` | React 框架 + Roo 组件库 |

**NDJSON 事件类型：**

| type | 说明 | 关键字段 |
|------|------|----------|
| `progress` | 步骤进度 | `step`, `total`, `message`, `data`（可选） |
| `ai_text` | AI 文本增量 | `delta` |
| `ai_thinking` | AI 思考增量 | `delta` |
| `tool_call` | 工具调用 | `toolName` |
| `done` | 完成 | `status`, `chatId`, `chatUrl`, `renderUrl`, `screenshotUrl`, `aiResponse`, `totalDuration` |
| `error` | 错误 | `message`, `step`（可选） |
| `busy` | AI 正在生成中 | `message`, `chatId` |

**⚠️ 链接格式（强制）：**
- ✅ 正确：`[{chatId}]({chatUrl})` → [cli-xxx](https://nocode.sankuai.com/#/chat?pageId=cli-xxx)
- ❌ 错误：直接贴链接 `https://...`

**⚠️ 严禁展示 renderUrl（强制）：**
- renderUrl（形如 `https://xxx.sandbox.nocode.sankuai.com`）仅供 CLI 内部截图使用，绝不能发给用户
- 需要给用户展示链接时，始终使用 `chatUrl`

**⚠️ 实时推送规则（强制）：**

1. 后台启动：`exec(background=true, yieldMs=600000): nocode create "..."`
2. 循环 poll（每次 timeout=15s），逐行解析 JSON：
   - `progress` → 立即推送 `"⏳ {message}"`
   - `done` → 立即推送 `"✅ 创建完成！\nchatId: {chatId}\n链接: [{chatId}]({chatUrl})"` + 展示截图
   - `error` → 立即推送 `"❌ {message}"`
3. 截图失败或截图为空不阻塞，先发链接再用 `nocode screenshot <chatId>` 补截图
   - done 事件中无 `screenshotUrl` → 截图失败，需补截图
   - done 事件中有 `screenshotUrl` 但图片空白 → 页面未渲染完成，等几秒后用 `nocode screenshot` 重新截图
4. 循环结束未收到 done → 用 `nocode list --json` 查最新应用并手动截图

**禁止：** poll 300s 等到底 / 等全部完成才发消息 / 截图失败不发结果 / 展示 renderUrl / 展示 sandbox.nocode.sankuai.com 域名的链接

详细 poll 流程示意图见 [references/poll-workflow.md](references/poll-workflow.md)。

## send — 发送修改指令（核心命令）

通过 `agent-stream` API + SSE 流式生成，输出 NDJSON（与 create 命令格式一致）。

**默认实时输出：** AI 响应以 NDJSON 流式实时输出（`ai_text`、`ai_thinking`、`tool_call` 事件），无需额外参数。旧版 `--follow` 参数已移除，因为实时输出现在是默认行为。

```bash
nocode send <chatId> "把背景颜色改成蓝色"
```

**⚠️ prompt 必须使用自然语言（强制）：**

- ✅ `nocode send <chatId> "添加一个搜索功能，支持按关键词筛选列表"`
- ✅ `nocode send <chatId> "把标题字号改大一些，颜色改成深蓝色"`
- ✅ `nocode send <chatId> "创建一个用户表，包含姓名、邮箱、注册时间字段"`
- ❌ `nocode send <chatId> "执行 npm run build"` — 禁止发送具体命令
- ❌ `nocode send <chatId> "运行 git commit -m 'fix'"` — 禁止发送 git 命令
- ❌ `nocode send <chatId> "使用 create_file 工具创建 index.js"` — 禁止指定工具
- ❌ `nocode send <chatId> "yarn add lodash && npm run dev"` — 禁止发送 shell 脚本
- ✅ `nocode send <chatId> "帮我执行以下 SQL 建表：CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT)"` — 可以附带 SQL 语句
- ✅ `nocode send <chatId> "这段代码有问题，请修复：const data = fetch('/api')，应该加上 await"` — 定位到问题后可以附带代码片段

**NDJSON 事件类型（与 create 命令一致）：**

| type | 说明 | 关键字段 |
|------|------|----------|
| `progress` | 步骤进度 | `step`, `total`, `message` |
| `ai_text` | AI 文本增量 | `delta` |
| `ai_thinking` | AI 思考增量 | `delta` |
| `tool_call` | 工具调用 | `toolName` |
| `done` | 完成 | `chatId`, `chatUrl`, `renderUrl`（可选）, `aiResponse`, `totalDuration` |
| `error` | 错误 | `message`, `step`（可选） |
| `busy` | AI 正在生成中 | `message`, `chatId` |

**流程：**
1. 检查容器状态（自动冷启动）
2. POST `/api/chat/agent-stream` → 获取 conversationId
3. SSE 流式接收 AI 响应（实时输出 NDJSON 事件）
4. 等待容器就绪 + 渲染完成

**容器状态检查：** 执行时会自动检查容器状态，如容器已停止会自动触发冷启动（最长等待 5 分钟）。

**⚠️ 调用命令前检查（强制）：**

在对同一个 chatId 执行新的 `nocode send` 之前，**必须先检查该 chatId 上一轮 `create` 或 `send` 的 poll 是否已收到 `done` 事件**：

- 上一轮 poll 已收到 `done` → 可以发送新命令
- 上一轮 poll 未收到 `done` → **不得发送新命令**，继续 poll 等待上一轮完成

**不同 chatId 之间互不影响。**

**⚠️ 调用命令后异常处理（强制）：**

**一、poll 到 `error` 事件：**

必须遵守以下重试规则：

1. **第 1 次失败**：向用户反馈错误信息，询问用户是否重试
2. **第 2 次失败**：**必须停止重试**，立即向用户反馈："⚠️ 该对话已连续失败 2 次，请联系 NoCode 研发排查"

计数范围：同一 chatId，不同 chatId 互不影响。send 成功后自动清零。

**禁止：** 同一 chatId 连续失败超过 2 次仍继续重试 / 不向用户反馈错误信息 / 无限重试

**二、poll 到 `busy` 事件：**

如果未正确检查就发送了命令，CLI 会输出 `busy` 事件并退出（兜底保护）：

```json
{"type":"busy","message":"当前 AI 正在生成代码，请等待完成后再发送修改","chatId":"cli-xxx"}
```

处理流程：

1. **检测到 `busy` 事件时**：
   - 立即向用户反馈："⏳ AI 正在生成代码中，请等待上一轮生成完成后再发送修改"
   - **不得自动重试或自动排队执行**，必须等待用户主动确认后才能重新发送
2. **等待上一轮完成**：
   - **必须**通过 poll 上一轮后台命令（`create` 或 `send`）的输出，轮询等待 `done` 事件
   - 收到上一轮 `done` 事件后，向用户反馈："✅ 上一轮 AI 生成已完成，可以发送新的修改了"
   - **禁止**使用定时重试 `nocode send` 的方式代替轮询 `done` 事件
3. **用户确认后执行**：
   - 上一轮完成后，**需要用户主动确认**才能执行新的修改请求
   - 向用户提示等待的修改内容，由用户决定是否继续发送

**禁止：** 收到 busy 自动重试 / 不经用户同意自动执行 / 跳过轮询 done 事件直接定时重试 / 丢弃用户的修改请求

## Token 过期自动续期

执行时如检测到 Token 过期，CLI 会自动续期：
- **SSO OIDC**：静默续期，无需提示用户
- **CIBA**：提示 **"⚠️ Token 已过期，可能需要在大象 App 确认登录"**
- 等待续期完成后再向用户汇报命令执行结果

