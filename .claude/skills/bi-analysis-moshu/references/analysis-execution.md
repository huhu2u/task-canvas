# Analysis Execution

在已经拿到分析输入 `s3Url` 之后，按本文件继续执行。

## 1. 确认输入已经可供分析服务使用

优先使用上一步已经准备好的 `s3Url`。

- 如果用户一开始就给了 `https://mss.vip.sankuai.com/...`, `s3plus.vip.sankuai.com`, `mss.vip.sankuai.com`, `s3plus.sankuai.com`, `mss.sankuai.com`，直接使用
- 如果 `s3Url` 来自 `scripts/prepare_analysis_input.py`，直接使用脚本输出
- 只有在明确还没有 `s3Url` 的兜底情况下，才回退到原始上传能力
- 上传请求头必须携带：`Gray-Cell: gray-release-apa-mdbi`

## 2. 整理调用参数

正式调用前，确保参数如下：

- `instruction`
  - 用户的自然语言分析指令
  - 尽量保留用户原意，不擅自扩写成业务结论
- `fileList`
  - 列表中的每一项至少包含 `s3Url`
  - `fileName` 可直接使用脚本返回值，或从 `s3Url` 中提取

示例：

```json
{
  "instruction": "分析这个销售数据文件，找出本月销量最高的产品，并说明主要原因。",
  "fileList": [
    {
      "s3Url": "https://mss.vip.sankuai.com/agent-manage/open-analysis/...",
      "fileName": "sales-pack-20260313.zip"
    }
  ]
}
```



## 3. 提交分析任务

先检查当前环境里的 server 名和连接状态，再调用对应 server 的 `data_analysis_submit_tool`（对应接口 `/analyze/mcp/submit`）：

- 若 `sdk-mtbi_ai` 已连接可用，优先使用 `sdk-mtbi_ai`
- 若 `sdk-mtbi_ai` 存在但报 `not connected` 或 `status: error`，视为不可用，不要调用
- 若 `sdk-mtbi_ai` 不可用，但 `mtbi_ai` 已连接可用，则使用 `mtbi_ai`
- 若二者都不存在，或都处于不可连接状态，停止调用，并提示当前环境未准备好该 MCP server

MCP Server 地址：

```text
http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940
```

调用方式（**CatPaw Desk 环境优先使用 CallMcpTool**）：

**CatPaw Desk 环境：**

使用 `CallMcpTool` 调用，示例参数：

```json
{
  "server": "sdk-mtbi_ai",
  "toolName": "data_analysis_submit_tool",
  "arguments": {
    "instruction": "分析销售数据，找出本月销量最高的产品",
    "fileList": [
      {
        "s3Url": "...",
        "fileName": "sales-data.zip"
      }
    ]
  }
}
```

**非 Desk 环境（CatPaw 助理 / OpenClaw 等）：**

```bash
mcporter call mtbi_ai.data_analysis_submit_tool
```

若当前环境使用 `sdk-mtbi_ai`，则对应为：

```bash
mcporter call sdk-mtbi_ai.data_analysis_submit_tool
```

若 `sdk-mtbi_ai` 报错示例为：

```text
Server "sdk-mtbi_ai" is not connected. Status: error
```

则不要继续重试该 server，应改为检查并尝试 `mtbi_ai`，或先完成环境修复后再调用。

调用时传入：

- `instruction`：用户的自然语言分析指令（必填）
- `fileList`：文件列表，每项包含 `s3Url` 和 `fileName`（必填）

返回内容重点关注：

- `taskId`：分析任务 ID，用于下一步轮询查询结果

## 4. 查询分析结果（轮询）

使用上一步返回的 `taskId` 调用 `data_analysis_result_tool`，持续轮询直到拿到最终分析结论。

根据环境选择调用方式：

**CatPaw Desk 环境（优先使用 CallMcpTool）：**

```json
{
  "tool": "CallMcpTool",
  "arguments": {
    "server": "sdk-mtbi_ai",
    "toolName": "data_analysis_result_tool",
    "arguments": {
      "taskId": "任务ID"
    }
  }
}
```

**非 Desk 环境（使用 mcporter）：**

```bash
mcporter call sdk-mtbi_ai.data_analysis_result_tool
```

调用时传入：

- `taskId`：第 3 步返回的任务 ID（必填）

返回内容为 Response 对象，重点关注：

- `code`：状态码，`0` 表示成功，`-1` 表示失败
- `data`：分析结论文本，仅当 `code=0` 时有值
- `msg`：错误信息，仅当 `code=-1` 时有值

轮询策略：
- 分析任务通常需要 3-5 分钟，在此期间需要持续轮询
- 轮询节奏建议使用固定序列：1 分钟、1 分钟、30 秒、30 秒、20 秒、20 秒、20 秒
- 若仍未结束，可继续按 15 秒间隔轮询，直到拿到最终结果或明确失败
- `code=0`：任务成功完成，`data` 中为最终分析结论，停止轮询
- `code=-1` 且 `msg` 包含“任务仍在执行中”：任务还在运行，继续等待并轮询
- `code=-1` 且 `msg` 包含“任务执行失败”：任务失败，停止轮询并提示用户错误信息
- `code=-1` 且其他错误信息：根据 `msg` 处理，例如无权限、任务不存在等
- 注意：不要使用cron/定时调度/任务 完成轮询，使用 shell+sleep 阻塞式判断即可

如果流程中出现换票、MOA、浏览器 Cookie、MissID、权限要求，立刻转到 [auth-and-qr.md](auth-and-qr.md)

若在 Catpaw Desk 环境中，`data_analysis_submit_tool` 或 `data_analysis_result_tool` 出现连接失败，或 MCP 调用失败，按以下顺序排查：

- 优先尝试直接重启 Catpaw Desk 环境，需要在 Dock 栏中彻底退出应用后再重新打开
- 或点击左下角头像 -> `mcp` -> “重启魔数智能服务”，然后开启一个新会话再发起分析
- 若重启后仍失败，再回到前面的 server 连接状态检查，确认 `sdk-mtbi_ai` 或 `mtbi_ai` 是否已恢复可用

## 5. 结果交付

- 轮询成功后，直接把分析服务返回的 `data` 展示给用户
- 不做二次改写，不补充未经验证的解释
- 若结果中包含表格，可用 Markdown 表格呈现

本步骤结束后：

- 若用户继续追问同一批数据的分析，可复用同一 `s3Url`
- 若用户提供了新数据，回到主 `SKILL.md` 的输入识别步骤重新开始