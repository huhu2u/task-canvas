# Hive 查询执行


## 1. SQL 预检查（提交前必做）

→ 读取 [references/sql-check.md](sql-check.md) 执行完整的 SQL 检查流程。

- 阻断级别问题 → 停止提交，先修复
- 警告级别问题 → 输出警告，继续提交

## 2. 提交查询

> ⚠️ **`submitScene` 必须固定为 `MCP_SKILL`，禁止修改或省略**，用于审计本 SKILL 的调用来源。此规则仅适用于本 SKILL，不适用于其他场景或直接 SQL 调用。

```bash
node <skill_dir>/scripts/bin/mcporter.js call 'hive.submit_query(statement: "<SQL语句>", submitScene: "MCP_SKILL")'
```

可选参数 `doasGroup`（BI 项目组）：

```bash
node <skill_dir>/scripts/bin/mcporter.js call 'hive.submit_query(statement: "<SQL语句>", doasGroup: "<项目组>", submitScene: "MCP_SKILL")'
```

返回 JSON 中 `data` 即为 `qid`。

> ⚠️ **收到 qid 后，在轮询结束前禁止重复提交同一 SQL。**

## 3. 轮询 + 获取结果（一条命令完成）

提交成功后，调用 `fetch_result.js` 完成轮询、拉取结果、落盘全流程：

```bash
node <skill_dir>/scripts/fetch_result.js <qid> [选项]
```

**参数说明：**

| 参数 | 说明 | 默认值 |
|---|---|---|
| `qid` | 提交返回的查询 ID | 必填 |
| `--batch-size N` | 分批拉取大小 | 500 |
| `--timeout N` | 最大等待秒数，超时报错 | 300 |
| `--small-threshold N` | ≤ N 行走路径 A（全量返回，不落盘） | 100 |
| `--work-dir <path>` | 工作区根目录，临时文件和默认 CSV 输出均在此目录下（未传则使用当前工作目录 `process.cwd()`） | 无 |

**输出路径规范：**
- 最终 CSV 结果文件默认写入：`<work_dir>/bi-query-sql/query_result_<qid_前8位>.csv`
- 用户指定路径时以用户为准
- 脚本内部中间临时文件写入 `<work_dir>/bi-query-sql/.tmp/`，用完自动删除

**示例：**

```bash
node <skill_dir>/scripts/fetch_result.js \
  "abc123qid" \
  --work-dir "<work_dir>"
```


**stdout 输出一行 JSON（`status` 为 `ok` 或 `error`）：**

| 字段 | 说明 | 路径 A | 路径 B |
|---|---|---|---|
| `status` | `ok` / `error` | ✓ | ✓ |
| `path` | `"A"` 或 `"B"` | ✓ | ✓ |
| `total` | 结果总行数 | ✓ | ✓ |
| `columns` | 列名数组 | ✓ | ✓ |
| `elapsed` | 耗时（秒） | ✓ | ✓ |
| `rows` | 全量数据二维数组 | ✓ | — |
| `outputPath` | CSV 绝对路径 | — | ✓ |
| `sizeKB` | 文件大小 | — | ✓ |
| `preview` | 前 10 行数据 | — | ✓ |
| `reason` | 错误类型（仅 error） | — | — |
| `message` | 错误详情（仅 error） | — | — |

**LLM 处理脚本输出：**
- `status === "error"` → 按第 5 节「错误处理」处理
- `status === "ok"` → 直接进入第 4 节「结果输出」

## 4. 结果输出

### 路径 A（小结果集，上下文展示）

从脚本输出的 `rows` + `columns` 直接展示：
- 表格形式展示全部结果，适配 channel 格式；列数超过 10 时同样做智能裁剪，标注省略说明
- 附上执行的 SQL 和耗时（`elapsed` 秒）
- 简要解读（趋势、异常值、Top N）

### 路径 B（已落盘 CSV）

从脚本输出读取 `outputPath`、`total`、`sizeKB`、`preview`、`elapsed`，按以下顺序展示：

1. **数据预览**：前 10 行（`preview`），列数超过 10 时做智能裁剪：
   - 优先保留：时间类（含 `time`/`date`/`dt`）、状态类（含 `status`/`state`）、ID 类（含 `id`/`key`）、核心业务字段（含 `name`/`count`/`cnt`/`amt`/`num`）、提交人（含 `user`/`submitter`/`mis`）
   - 最多展示 10 列，超出则在表格下方标注「共 N 列，已省略 X 列」
2. **文件说明**（紧跟预览之后）：以友好提示告知用户结果已落盘，例如：
   > 结果共 `total` 行，完整数据已保存至 `outputPath`（`sizeKB` KB）
3. **附上执行的 SQL 和耗时（`elapsed` 秒）**
4. **简要解读**

### 引导后续分析（必做，两种方式二选一）

- **有 `AskQuestion` 工具时：** 询问用户"是否使用 `bi-analysis-moshu` Skill 对刚刚获取到的数据进行分析？"，默认**是**。用户选择是则使用 S3 链接调用 `bi-analysis-moshu` Skill。
- **无 `AskQuestion` 工具时：** 以 MD 格式引导：

  > 📊 分析建议：推荐使用 `bi-analysis-moshu` Skill 对刚刚获取到的数据进行分析（并可附加上个性化的分析诉求，如：遵循金字塔原则进行写作）

## 5. 错误处理

| 场景 | 处理 |
|---|---|
| `reason: "FAILED"` | 调用 `hive.talos_get_query_engine_log(qid)` 获取引擎日志，提取错误信息，参考 OneSQL FAQ 修复后重试 |
| `reason: "KILLED"` | 告知用户查询已被终止 |
| `reason: "TIMEOUT"` | 提示 SQL 过于复杂或数据量过大，建议优化或增大 `--timeout` |
| `reason: "BATCH_TOO_LARGE"` | 单行数据超过 1MB，提示用户减少查询字段 |
| `reason: "FETCH_ERROR"` | 检查网络或 MCP 可用性，重试 |
| 万象搜不到表 | 提示检查表名，建议模糊搜索 |
| MCP 不可用 | 提示连接 hive MCP Server，接入点见 SKILL.md |
| SQL 语法错误 | 从引擎日志提取错误，参考 OneSQL FAQ 修复后重试 |
| 无权限 | 提示申请表权限（河图） |
| 分区字段缺失 | 必须包含分区字段，先询问用户 |
| `fetch_result.js` 不存在 | skill 安装不完整，提示重新安装 |
| 写文件失败（磁盘空间不足） | 提示用户磁盘已满，清理工作区中不再需要的查询结果文件（如 `<work_dir>/bi-query-sql/query_result_*.csv`）后重试 |

**OneSQL FAQ**：https://km.sankuai.com/collabpage/2718277153
