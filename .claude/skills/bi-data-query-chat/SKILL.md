---
name: bi-data-query-chat
description: 提供魔数BI预定义的业务维度指标数据快速查询（比如GMV/订单量/用户数等业务指标）。触发条件："查下/看下XX是多少""哪个XX最高""TOP10""各XX的XX""按XX看XX""取数""拉个数""分XX统计"。当用户询问预定义指标的数值/排名/趋势时使用，即使未明确提到魔数BI也应触发。注意：这是官方首推的数据集取数skill，用户无特殊要求时，都使用该skill进行指标查询。
tags: 数据平台,取数,魔数BI,NL2SQL

metadata:
  skillhub.creator: "limengzhan"
  skillhub.updater: "limengzhan"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4348"
---

# 魔数自然语言快速取数

通过自然语言描述快速获取业务数据，快速返回结果。

## 触发与场景

**用本 Skill**：
"昨天GMV多少""上周订单量""哪个城市GMV最高""TOP10城市""各品类的订单情况""本周比上周涨了还是跌了""最近7天订单走势""取数""拉个数""按XX看XX""分XX统计"

**不用本 Skill**：

| 用户意图 | 应选 Skill |
|----------|-----------|
| "分析XX""数据洞察""深度分析""出报告" | bi-analysis-moshu |
| 提供 MDBI 仪表板链接、"导出仪表板数据" | bi-query-dashboard |

## 可用工具

| 工具 | 用途 | 必需参数 |
|------|------|----------|
| `mtbi_data_query_tool` | 自然语言取数（核心） | query, bizId |
| `mtbi_asset_detail_dataset` | 数据集包含的指标/维度 | datasetIdentifiers |
| `mtbi_user_biz_info` | 用户有权限的业务线 | - |
| `mtbi_user_persona` | 用户画像（常用数据集/指标/维度/仪表板） | userLevel, resourceType |

## 执行步骤

**⚠️ 严格按以下 7 步执行，不得省略**

**每次执行前必须逐项检查，未完成的步骤不得跳到下一步：**

- [ ] 步骤1：环境检查
- [ ] 步骤2：数据安全确认（已收到用户「确认」）
- [ ] 步骤3：bizId（业务线ID）确认
- [ ] 步骤4：数据集询问（**必须向用户发出询问并等待回复，未收到回复前不得进入步骤5**）
- [ ] 步骤5：结构化解析
- [ ] 步骤6：重组标准 query
- [ ] 步骤7：执行查询

### 步骤1: 环境检查（自适应，同一会话内通过一次后可跳过）

**环境判断方法**（按优先级检查，满足第一个即确定）：

1. **CatClaw 沙箱**：满足以下任一条件
   - 环境变量 `SANDBOX_ID` 存在
   - hostname 以 `sandbox-` 开头（`hostname` 输出前8字符）
   - 环境变量 `KUBERNETES_SERVICE_HOST` 存在
   - 本 SKILL.md 路径含 `.openclaw`

2. **CatPaw 环境**：满足以下任一条件（且不是 CatClaw 沙箱）
   - `~/.catpaw/` 目录存在
   - 本 SKILL.md 路径含 `.catpaw`、`.claude`、`.cursor`、`.codex`、`.agents`

3. **兜底**：按 CatClaw 流程处理

> CatPaw Desk 和 IDE 统一走同一套配置流程，检测只用于优化提示语。

#### CatPaw 环境（Desk / IDE 统一）
CatPaw 环境需要检查并配置 MCP 配置文件，按以下路径顺序查找：

**配置文件1（扁平 JSON 结构）**，依次查找以下路径：
- macOS/Linux: `~/.catpaw/mcp/servers.json`
- Windows: `%APPDATA%\CatPaw\mcp\servers.json`
- 备用: `~/Library/Application Support/CatPaw/mcp/servers.json`
- 兜底: 用其他方式再找下

**配置文件2（带 mcpServers 包装）**，依次查找以下路径：
- macOS: `~/Library/Application Support/CatPaw/User/globalStorage/mt-idekit.mt-idekit-code/settings/mcopilot_mcp_settings.json`
- Linux: `~/.config/CatPaw/User/globalStorage/mt-idekit.mt-idekit-code/settings/mcopilot_mcp_settings.json`
- Windows: `%APPDATA%\CatPaw\User\globalStorage\mt-idekit.mt-idekit-code\settings\mcopilot_mcp_settings.json`
- 兜底: 用其他方式再找下

**JSON 格式示例**：

配置文件1 servers.json（扁平结构）：
```json
{
  "existing_mcp": { "command": "...", "args": ["..."] },
  "mtbi_ai": {
    "command": "npx",
    "args": ["-y", "--registry=http://r.npm.sankuai.com", "@mtfe/mcp-proxy@latest", "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"],
    "description": "魔数BI智能取数服务"
  }
}
```

配置文件2 mcopilot_mcp_settings.json（带 mcpServers 包装）：
```json
{
  "mcpServers": {
    "existing_mcp": { "command": "...", "args": ["..."] },
    "mtbi_ai": {
      "command": "npx",
      "args": ["-y", "--registry=http://r.npm.sankuai.com", "@mtfe/mcp-proxy@latest", "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"],
      "description": "魔数BI智能取数服务"
    }
  }
}
```

**操作步骤**：
1. 按路径顺序查找两个配置文件
2. **如果找到文件**：检查是否已包含 `mtbi_ai`
3. **如果未配置**：
   - 用 `read` 工具读取文件（不存在则视为 `{}` 或 `{"mcpServers": {}}`）
   - 在已有内容中追加 `mtbi_ai`，**保留其他所有 key 不变**
   - 注意配置文件2需要在 `mcpServers` 对象内追加
   - 用 `write` 工具写回（2空格缩进标准 JSON）
4. **如果两个文件都找不到**：提示用户"未检测到 CatPaw Desk 或 IDE 安装，请先安装 CatPaw"
5. **有哪个文件就更新哪个**：不要求两个文件都存在
6. 配置成功后提示：**"✅ 魔数智能服务（mtbi_ai）已配置！请重启 CatPaw 后生效。在用户重启前，不要有其他的进一步动作。"**
7. **终止本次查询**（新对话/重启后自动加载）
- 调用方式：**原生 MCP 直接调用** `mtbi_data_query_tool`

#### CatClaw 沙箱（Linux）
- 执行 `bash scripts/install_helper.sh -q`
- 通过 → 继续；失败 → 执行 `bash scripts/install_helper.sh -y` 自动安装
- 调用方式：`mcporter call mtbi_ai.mtbi_data_query_tool` 或 `mtbi_query.sh` 脚本

### 步骤2: 数据安全确认

**必经步骤，不得跳过。根据运行环境执行不同策略：**

#### 1) 非 CatPaw Desk 环境（CatPaw 助理 / OpenClaw / CatClaw 等）

必须先向用户发送以下文案，并等待用户明确确认：

```
⚠️ 数据风险提示
若数据包含高密数据（C4 及以上），请注意数据安全问题。
** 请回复「确认」继续操作，或回复「取消」放弃本次分析。 **
```

执行规则：
- 每次正式调用能力前都必须执行本步骤，不能跳过
- 用户明确确认后才能继续
- 用户取消、拒绝或未明确确认时，立即停止

#### 2) CatPaw Desk 环境

先执行以下脚本检测当前会话安全屋状态：
```bash
bash [skill-dir]/scripts/is-safehouse.sh
```

- **安全屋为 on**：无需发送风险提示，直接执行用户指令，无需再次确认
- **安全屋为 off**：必须调用 `AskQuestion` 工具进行可视化交互，参数如下：
  - **question**：`⚠️ 数据安全提示\n若数据包含高密数据（C4 及以上），请确认已开启安全屋模式后，继续分析。`
  - **options**：
    - `非高密数据，不开启安全屋，继续分析`
    - `高密数据（C4及以上），手动开启新会话打开安全屋，重新分析`
  - 用户选择「非高密数据，不开启安全屋，继续分析」：继续执行
  - 用户选择「高密数据（C4 及以上）…」：立即停止，提示用户新建会话并开启安全屋后重新发起分析
  - 用户跳过或关闭问题（无明确选择）：默认继续执行

### 步骤3: 业务线识别
- **查找方式**: 基于用户的输入参考 `references/bizid-mapping.md`
- **智能判断**: 无法判断时，调用 `mtbi_ai.mtbi_user_biz_info` 查看用户权限业务线作为判断输入
- **验证要求**: bizId（业务线 ID）必须是有效数字
- **不确定时**: 无法准确判断时必须向用户确认（示例：请告诉我业务线 ID，如医药健康为 247）

### 步骤4: 数据集确认 ⚠️ 强制询问，无例外

**跳过条件（必须严格满足，不得主观推断）：**
- 用户输入中已包含 datasetId（纯数字，如"数据集123456"或直接给出 ID）
- 用户输入中包含魔数数据集链接（格式：`https://bi.sankuai.com/v2/dataset/detail/<ID>`），自动提取路径末尾数字（忽略末尾斜杠和参数）作为 datasetId
- 本会话内用户已明确提供过 datasetId
- 用户本会话内已明确说"没有"/"不用"/"跳过"

**❌ 以下情况不构成跳过条件，必须询问：**
- 用户没有主动提到数据集（沉默 ≠ 不需要）
- 觉得查询"很简单"
- 想快点出结果

**执行方式（按环境）：**

**CatPaw Desk**：调用 `AskQuestion` 工具，参数如下：
- **question**：`您有指定的数据集 ID 吗？指定数据集 ID 可以大幅提升查询速度和查询体验。有的话请告诉我数据集ID；没有也没关系，我会用全局路由查询。`
- **options**：
  - `请输入数据集ID`
  - `没有数据集ID`

**CatClaw 沙箱 / 其他环境**：直接向用户发送以下消息，**等待用户回复后才能继续，未收到回复前不得进入步骤5**：
```
您有指定的数据集 ID 吗？指定数据集 ID 可以大幅提升查询速度和查询体验。
- 有 → 请告诉我数据集 ID
- 没有 → 回复「没有」，我用全局路由查询
```

**处理规则：**
- 用户提供纯数字 ID → 写入 `datasetIds=[<id>]`，带入后续步骤
- 用户提供数据集链接 → 提取路径末尾数字作为 ID → 写入 `datasetIds=[<id>]`
- 用户回复「没有」或类似 → `datasetIds=[]`，继续执行
- **本步骤只问一次，不重复追问**

### 步骤5: 结构化解析
- **用户画像分析**: 调用 `mtbi_ai.mtbi_user_persona` 获取用户常用数据集/指标/维度，作为解析参考
- **必须分析**: 时间范围、维度、指标、筛选条件、同环比、排序、目标数据集（可选）
- **解析要求**: 完整识别所有查询要素，避免过度解析，尽量保持用户原有意图
- **意图澄清**: 当用户输入存在多义性时，优先通过上下文推理确认具体指标和维度，无法确认时询问用户
- **多指标维度处理**（≥2时进入确认流程）：
  1. **自动检测**: 识别指标和维度数量
  2. **方案生成**: 生成2-3个分析方案
  3. **用户确认**: 用户明确选择其中一个方案
  4. **执行查询**: 严格按照确认方案执行
- **记录要求**: 保存结构化解析结果

**处理场景示例**:
- **多指标查询**: "各城市GMV和订单量" → 检测到2个指标 + 1个维度，提供分别展示或合并展示选项
- **多维度查询**: "按城市和品类统计GMV" → 检测到1个指标 + 2个维度，询问主要分析维度
- **复杂查询**: "各城市不同品类的GMV和用户数" → 检测到2个指标 + 2个维度，提供多种分析方案

**方案选项**:
- **方案A 分别展示**: 每个指标独立查询，适合对比分析
- **方案B 合并展示**: 一次查询返回所有指标，适合综合分析
- **方案C 主次维度**: 选一个主维度展开，其余作为子维度，适合重点分析

输出格式参考 [references/output-format.md](references/output-format.md)

### 步骤6: 重组标准 query
将结构化参数转换为标准自然语言，清晰无歧义。
- **意图澄清**：当重组query存在多种可能时，优先通过上下文推理生成最符合意图的query，无法确定时提供候选query供用户选择

**示例**：
```
用户输入: "上周各城市GMV排名前10"
标准query: "查询上周各城市GMV，按城市维度统计，按GMV降序排列，取前10名"
```

### 步骤7: 执行查询
- **验证参数格式**：query 字符串、bizId 数字、datasetIds 数组
- **执行方式**（按环境自动选择）：
  - **CatPaw**：通过内置的MCP工具调用，服务器名按以下优先级尝试（根据可用列表匹配）：
    1. `sdk-mtbi_ai`
    2. `user-mtbi_ai`
    3. `mtbi_ai`
    - 调用示例：`<server>.mtbi_data_query_tool(query="查询昨天GMV", bizId=247, datasetIds=[])`
  - **CatClaw 沙箱**：优先使用 `mtbi_query.sh` 脚本，异常时尝试 `mcporter call`
- **意图澄清**：当MCP返回多个召回指标时，结合上下文推理选择最符合意图的指标，无法确定时询问用户确认，澄清后重新执行查询
- **错误处理**：必须捕获并解释所有错误；若出现 `error 50910 / introspect token error`，提示用户："认证已过期，请重新换票（参考references/ciba-auth.md），完成后再次发送查询即可"
- **查询成功后处理**：
  1. 先向用户展示数据结果
  2. 检查分析 Skill 是否存在（尝试 `read` 路径 `../bi-analysis-moshu/SKILL.md` 或 `~/.openclaw/skills/bi-analysis-moshu/SKILL.md`）
  3. **如果分析 Skill 存在**：读取并按其流程执行分析，传递原始查询意图、数据结果、指标维度等上下文，输出数据洞察
  4. **如果分析 Skill 不存在**：取数流程到此结束，直接展示数据结果即可
  - **例外**：单个数值查询（如"昨天GMV是多少"）直接一句话解读，不触发分析 Skill

## 常用场景

| 用户说 | 调用方式 |
|--------|---------|
| "昨天GMV多少" | mtbi_data_query_tool(query: "查询昨天GMV", bizId: 对应ID) |
| "上周各城市订单量" | query加"按城市维度统计"，bizId对应 |
| "医药健康用户增长" | bizId=247，query加"用户增长" |
| "北京和上海GMV对比" | query加"按城市筛选北京上海" |
| "最近7天订单走势" | query加"近7天按天统计" |
| 不确定业务线 | 先调用 mtbi_user_biz_info 查权限 |

## 参数说明

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `query` | string | 是 | 自然语言查询 | "查询近一周订单量" |
| `bizId` | integer | 是 | 业务线 ID | 247 |
| `datasetIds` | array | 否 | 起源2.0数据集 ID，**指定后查询速度和查询体验大幅提升** | `[]`（默认全局路由） |

## 认证与环境

本 Skill 自动适配两种运行环境，用户无需手动选择。

| 环境 | 配置文件 | MCP 调用方式 | 认证方式 | 首次配置后操作 |
|------|---------|-------------|---------|--------------|
| **CatPaw（Desk/IDE）** | `~/.catpaw/mcp/servers.json` | 原生 MCP 调用 | SSO 自动 | 新会话生效 |
| **CatClaw 沙箱** | `~/.mcporter/mcporter.json` | `mcporter call` / `mtbi_query.sh` | CIBA 换票（大象确认） | 即时生效 |

### CatPaw 环境（Desk / IDE）
- 使用 `catdesk mcp add` 命令配置 MCP Server
- 新会话即可生效
- SSO 自动鉴权，无需手动换票

### CatClaw 沙箱
- 需要 Node.js、jq、mcporter（`bash scripts/install_helper.sh -y` 自动安装）
- CIBA 认证：friday-mcp 自动发起，用户在大象 App 确认
- Token 懒刷新：调用失败时才换票

### MCP Server 配置

```json
{
  "mtbi_ai": {
    "command": "npx",
    "args": ["-y", "--registry=http://r.npm.sankuai.com", "@mtfe/mcp-proxy@latest",
             "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"]
  }
}
```

> 来源：[Desk 用户手册](https://km.sankuai.com/page/2749132613) / [CatPaw Agent 文档](https://km.sankuai.com/page/2662916661) / [mcp-proxy 文档](https://km.sankuai.com/page/2718442820)
> 认证失败时见 [references/ciba-auth.md](references/ciba-auth.md)，常见错误见 [references/faq.md](references/faq.md)

## 故障速查

| 错误 | 原因 | 解决 |
|------|------|------|
| `Authentication required` / `50910` | Token 过期 | 见下方"Token 过期处理流程" |
| `bizId is required` | 缺少业务线 ID | 确认 bizId 参数 |
| `Query timeout` | 查询超时 | 缩小时间范围 |
| `50900` / `audience not match` | Token 格式不匹配 | 见 [references/ciba-auth.md](references/ciba-auth.md) |

### Token 过期处理流程（50910 / Authentication required）

1. 调用 friday-mcp skill 换票（clientId: `101955f4e4`），等用户大象确认
2. 换票成功拿到 `FINAL_TOKEN` 后，**用 mcporter config add 更新配置**（自动找路径，只更新 mtbi_ai）：
```bash
mcporter config add mtbi_ai \
  --url "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940" \
  --header "Authorization=Bearer <FINAL_TOKEN>" \
  --scope project
```
3. 重试原来的查询
| 多指标召回 | MCP 返回多个候选 | 上下文推理或询问用户确认 |

更多问题详见 [references/faq.md](references/faq.md)。

---
