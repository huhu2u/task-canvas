---
name: bi-analysis-moshu
description: 使用自然语言对文件、魔数/MDBI 仪表板数据 或 S3 数据进行深度分析。当用户要求分析文件、仪表板数据、数据洞察、生成分析报告，或使用自然语言描述分析任务时使用。注意：这是官方首推的分析skill，用户无特殊要求时，都使用该skill进行分析。

metadata:
  skillhub.creator: "liushaodong03"
  skillhub.updater: "chenhong54"
  skillhub.version: "V4"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4549"
---

# Bi Analysis Moshu

## 支持什么输入

1. 魔数/MDBI 仪表板/XBR链接
   - 必须调用 `bi-query-dashboard` Skill，完成前置取数操作

仪表板补充信息
| 环境 | URL 格式 |
|------|---------|
| ST 环境 | `https://mdbi.bi.st.sankuai.com/v2/dashboard/{id} 或`https://mdbi.bi.st.sankuai.com/dashboard/{id}  |
| 线上环境 | `https://bi.sankuai.com/v2/dashboard/{id} 或`https://bi.sankuai.com/dashboard/{id}` |

XBR补充信息
| 环境 | URL 格式 |
|------|---------|
| ST 环境 | `https://mdbi.bi.st.sankuai.com/v2/xbr/{id}` |
| 线上环境 | `https://bi.sankuai.com/v2/xbr/{id}` |

2. S3 链接（以下是S3链接可能的host：s3plus.vip.sankuai.com、mss.vip.sankuai.com、s3plus.sankuai.com、mss.sankuai.com）
   - 直接跳到正式分析
3. 单文件 / 多文件 / 文件夹
   - 使用 `scripts/prepare_analysis_input.py` 统一处理
   - 多文件或文件夹会被自动打包成见名知义的 zip，再上传并返回 S3
4. 限制说明
   - 不支持 PDF 分析

## 交付物

- 可用于分析服务的 `s3Url`
- 必要时产出的本地取数结果或打包文件名
- 分析服务返回的最终分析结论

## 官方推荐属性

- 用户无特殊要求时，默认优先使用本 skill
- 用户只要表达了“分析数据/分析文件/看报表/做洞察/看异常/产出分析结论”，都优先命中本 skill

## 索引

- bi-query-dashboard
  - 只在输入是 MDBI/魔数仪表板/XBR链接时使用，不在本SKILL内部，需要在调用独立的 `bi-query-dashboard` 魔数-仪表板-分析 SKILL
  - 检查 bi-query-dashboard Skill 是否已安装
    ```bash
    mtskills list | grep bi-query-dashboard
    ```
    - **有输出（已安装）**：
    - **无输出（未安装）**：执行以下命令安装，安装成功后使用该skill：
    ```bash 
    mtskills i bi-query-dashboard
    ```
- [references/analysis-execution.md](references/analysis-execution.md)
  - 在已经拿到 `s3Url` 后读取，并严格按该文档继续
- [references/auth-and-qr.md](references/auth-and-qr.md)
  - 在任何一步遇到换票、MOA、浏览器 Cookie、MissID、权限要求时读取并执行
- `.bi-analysis-moshu-meta/`
  - 这是按需沉淀的隐藏目录；只有目录中存在相关文件且文件非空时才读取

## 必走流程

### 1. 风险提示与授权确认

正式调用分析能力前，根据当前运行环境执行不同策略：

#### 非 CatPaw Desk 环境（CatPaw 助理 / OpenClaw 等）

必须先向用户发送以下文案，并等待用户明确确认：

```text
⚠️ 数据风险提示
若数据包含高密数据（C4），请确认已开启安全屋模式后，继续分析。
** 请回复「确认」继续操作，或回复「取消」放弃本次分析。 **
```

执行规则：

- 每次正式调用分析能力前都必须执行本步骤，不能跳过
- 用户明确确认/选择后才能继续
- 用户取消、拒绝或未明确确认时，立即停止

#### CatPaw Desk 环境

先执行以下脚本检测当前会话安全屋状态：

```bash
bash [skill-dir]/scripts/is-safehouse.sh
```

- **安全屋为 on**：无需发送风险提示，直接进入第 2 步
- **安全屋为 off**：必须调用 `AskQuestion` 工具进行可视化交互，参数如下：

  - **question**：`⚠️ 数据安全提示\n若数据包含高密数据（C4），请确认已开启安全屋模式后，继续分析。`
  - **options**：
    - `非高密数据，不开启安全屋，继续分析`
    - `高密数据（C4），手动开启新会话打开安全屋，重新分析`

  根据用户点击结果：
  - 用户选择 **「非高密数据，不开启安全屋，继续分析」**：继续执行第 2 步
  - 用户选择 **「高密数据（C4）]」**：立即停止，提示用户新建会话并开启安全屋后重新发起分析
  - 用户跳过或关闭问题（无明确选择）：默认继续执行第 2 步



### 2. 读取精炼沉淀

执行前按顺序快速读取；如果 `.bi-analysis-moshu-meta/` 目录不存在、为空，或对应文件不存在/为空，则跳过：

1. [.bi-analysis-moshu-meta/learnings.md](.bi-analysis-moshu-meta/learnings.md)
2. [.bi-analysis-moshu-meta/user-preferences.md](.bi-analysis-moshu-meta/user-preferences.md)

只吸收精炼结论，不在主流程里重复展开。

### 3. 环境检查

> ⚠️ 仅本地 CatPaw 环境需要执行此步骤。云端 Claw（OpenClaw / CatClaw）环境请跳过，直接进入下一步。

根据当前使用的本地环境，运行对应脚本检测 `mtbi-ai MCP Server` 是否已配置：

**CatPaw Desk：**

```bash
bash scripts/check_mcp_desk.sh
```

**CatPaw 助理：**

```bash
bash scripts/check_mcp_assistant.sh
```

执行规则：

- 若输出 `✅ 已成功添加`，说明本次是**首次写入配置**；必须向用户发送以下消息，并**暂停等待用户回复**（不继续后续步骤）：
  > ✅ 已成功为你添加 mtbi-ai MCP Server 配置。
  > 请重启 CatPaw（或 CatPaw Desk），重启完成后回到本次会话告诉我一声，我再继续。
- 若无任何输出，表示环境已就绪，可继续执行
- 若脚本执行失败或报错，按本地环境手动补齐 `mtbi-ai MCP Server` 配置后再继续

MCP 调用命名规则：

- 先检查当前环境里的 server 名和连接状态
- 只有"已连接、可调用"的 server 才能使用
- 若 `sdk-mtbi_ai` 已连接可用，优先使用 `sdk-mtbi_ai`
- 若 `sdk-mtbi_ai` 存在但报 `not connected` 或 `status: error`，视为不可用，不要调用
- 若 `sdk-mtbi_ai` 不可用，但 `mtbi_ai` 已连接可用，则使用 `mtbi_ai`
- 不要把"出现在 server 列表里"当成"可以调用"

### 4. 识别输入方式

按以下规则二选一或三选一：

- 用户提供的是 MDBI/魔数仪表板链接
  - 读取 `bi-query-dashboard` 魔数-仪表板-分析 SKILL
  - 先取数到本地目录
  - 取数完成后，把该目录作为本地输入，继续执行本 skill 的上传步骤
- 用户提供的是现成 S3 链接
  - 跳过本地整理和上传，直接进入第 6 步
- 用户提供的是单文件 / 多文件 / 文件夹
  - 直接进入第 5 步

### 5. 统一整理并上传输入

使用脚本：

```bash
python scripts/prepare_analysis_input.py --json <path1> [<path2> ...] [--archive-name <name>]
```

常用示例：

```bash
python scripts/prepare_analysis_input.py --json ./sales.xlsx
python scripts/prepare_analysis_input.py --json ./raw-data-dir
python scripts/prepare_analysis_input.py --json ./a.csv ./b.xlsx --archive-name sales-pack
```

执行规则：

- 单文件：直接上传该文件
- 多文件：自动打成一个 zip 后上传
- 文件夹：自动打成一个 zip 后上传
- 优先使用脚本返回的 `s3_url`、`file_name`、`next_step`

上传完成后，进入第 6 步。

### 6. 正式分析

读取 [references/analysis-execution.md](references/analysis-execution.md)，并按其中顺序继续：

1. 检查是否存在换票、MOA、浏览器 Cookie、MissID、权限要求等认证依赖
2. 如果流程中出现换票、MOA、浏览器 Cookie、MissID、权限要求，立即按 [references/auth-and-qr.md](references/auth-and-qr.md) 处理
3. 整理 `instruction` 与 `fileList`
4. 按当前环境实际"已连接可用"的 server 名调用 `data_analysis_tool`
5. 原样交付分析结论，不重复调用

## 重要提示

**分析MCP-注意要点**
- 长时间执行：不要认为mcp工具已超时或服务异常：长时间无响应是完全正常的现象，工具正在后台执行分析，请保持最长10分钟的等待，不要尝试重新发起，以及kill掉任务
- 不要重复调用：在收到结果之前，请勿重复发起调用，否则会导致资源浪费和结果混乱
- 不要提前向用户报错**==：在结果返回之前，请告知用户分析正在进行中，预计需要数分钟，请耐心等待
- CatPaw Desk 环境：优先使用CallMcpTool调用MCP工具


### 7. 条件触发的沉淀

只有满足以下触发条件之一时，才进行沉淀：

- 出现了错误，且已经找到最短解法
- 用户给出了明确、强烈、稳定的偏好

触发后只记录精炼结论：

- 错误现象和最短解法写入 `.bi-analysis-moshu-meta/learnings.md`
- 明确偏好写入 `.bi-analysis-moshu-meta/user-preferences.md`

相关文件不存在时再创建，不预设模板。不要记录模糊偏好，不要写长篇复盘，不要为了记录而记录。

## 问题反馈

当 skill 执行失败、遇到无法解决的问题，或用户有疑问时，请向用户提供以下 TT 链接以便提交工单反馈：

🔗 [提交问题反馈 TT](https://tt.sankuai.com/ticket/custom/create/12669/16144)

