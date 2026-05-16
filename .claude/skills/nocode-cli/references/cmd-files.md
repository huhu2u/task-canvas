# files 命令详细规则

## files list — 查看工程目录树

查看指定 chatId 工程的文件目录结构（当前层级，不递归）。

```bash
nocode files list <chatId> [path]              # 查看根目录（path 可选，默认根目录）
nocode files list <chatId> src                # 查看 src 子目录
nocode files list <chatId> src/components     # 逐层浏览
```

**流程：**
1. 获取文件读取锁（同一 chatId 互斥）
2. 获取对话详情（带本地缓存）→ 提取 ideId
3. 检查容器状态（自动冷启动，最长等待 5 分钟）
4. 调用 `/api/ide/files/tree` 获取当前层级目录
5. 释放锁
6. 输出结果

### 输出格式

```
✔ 容器就绪

请求路径：./src/

---TREE_START---
components/
contexts/
lib/
pages/
App.jsx
index.css
main.jsx
---TREE_END---
```

- 目录以 `/` 结尾，文件不带 `/`
- 仅返回当前层级，需要浏览子目录请指定路径逐层查看

### ⚠️ Agent 提取规则（强制）

1. 匹配 `---TREE_START---` 和 `---TREE_END---` 之间的内容
2. 按行 split，每行一个条目
3. 以 `/` 结尾的是目录，否则是文件
4. 提取后向用户展示目录结构，如需查看某个文件内容，使用 `nocode files get <chatId> <filePath>` 命令

## files get — 查看文件内容

查看指定 chatId 工程中某个文件的内容。每次只能读取一个文件。

```bash
nocode files get <chatId> <filePath>         # 查看文件内容
nocode files get <chatId> src/App.jsx        # 示例
nocode files get <chatId> package.json       # 示例
```

**流程：**
1. 获取文件读取锁（同一 chatId 互斥）
2. 获取对话详情（带本地缓存）→ 提取 ideId
3. 检查容器状态（自动冷启动，最长等待 5 分钟）
4. 调用 `/api/ide/files/content` 获取文件内容
5. 释放锁
6. 输出结果

### 输出格式

```
✔ 容器就绪
---FILE_CONTENT_START---
import { Toaster } from "@/components/ui/sonner";
...
export default App;
---FILE_CONTENT_END---
```

### ⚠️ Agent 提取规则（强制）

1. 匹配 `---FILE_CONTENT_START---` 和 `---FILE_CONTENT_END---` 之间的内容即为完整文件内容
2. 提取的内容可直接作为文件内容使用（已包含完整换行符）
3. 如输出包含 `文件内容为空`，说明该路径对应空文件或路径错误


## ⚠️ 调用命令前检查（强制，files list 和 files get 通用）

在对同一个 chatId 执行 `files list` 或 `files get` 之前：

- **建议**等待该 chatId 上正在执行的 `create` 或 `send` 完成（上一轮 poll 已收到 `done`），否则读到的可能是中间状态
- 同一 chatId 同一时刻只允许一个 `files list` 或 `files get` 请求执行
- `files get` 每次只能读取一个文件，**禁止并发多个 `nocode files get` 请求同一个 chatId**
- 多个命令必须串行执行，**不要并发**

**不同 chatId 之间互不影响。**

**禁止：** 同一 chatId 并发执行多个 files list/files get / 并发读取多个文件

## ⚠️ 调用命令后异常处理（强制，files list 和 files get 通用）

**一、输出包含 `busy` 相关错误（`当前有其他文件操作正在执行`）：**

CLI 检测到同一 chatId 已有 files 请求在执行时，会输出错误并退出：

```
✖ 当前有其他文件操作正在执行，请稍后再试
```

处理流程：

1. **检测到 busy 错误时**：
   - 向用户反馈："⏳ 当前有其他文件操作正在执行，请稍后再试"
   - 等待 3-5 秒后重试
2. **重试规则**：
   - 最多重试 2 次（共 3 次尝试）
   - 超过 2 次仍 busy → 向用户反馈："⚠️ 该对话文件操作繁忙，请稍后再试"
3. **不得无限重试**

**二、输出包含其他错误信息（非零退出码）：**

| 错误信息 | 处理方式 |
|---------|---------|
| `该作品尚未初始化 IDE 容器` | 提示用户先通过 `nocode send` 生成代码 |
| `容器启动等待超时` | 提示用户稍后重试 |
| `对话不存在或无权访问` | 检查 chatId 是否正确 |
| `获取文件内容失败` | 检查路径是否正确，先用 `nocode files list <chatId>` 确认文件存在 |
| `获取文件树失败` | 检查路径是否正确 |
| `未登录，请先执行 nocode login` | 执行 `nocode status` 按提示登录 |
| 其他错误 | 向用户反馈错误信息，第 1 次询问重试，第 2 次停止 |

**三、命令输出中无边界标记：**

输出中无 `---TREE_START---` 或 `---FILE_CONTENT_START---`，说明命令异常退出（如未登录、网络错误、容器超时），向用户反馈完整输出内容。

**禁止：** 错误时不向用户反馈 / 无限重试 / 忽略错误继续后续操作

## 💡 使用场景：问题定位

当与用户讨论页面存在问题时（如样式异常、功能不正常、报错等），可以通过 `files list` 和 `files get` 命令获取工程的文件目录结构及文件内容，以更准确地定位问题所在，而不是盲目猜测或让用户手动描述代码。

**推荐流程：**

1. 先用 `nocode files list <chatId>` 了解工程整体结构
2. 根据问题类型定位可能的文件（如样式问题看 CSS 文件，功能问题看组件文件）
3. 用 `nocode files get <chatId> <filePath>` 读取相关文件内容
4. 结合文件内容分析问题原因，给出精确的修改建议
5. 用 `nocode send <chatId> "具体修改指令"` 发送修改

**⚠️ 不建议通过 `nocode send` 获取文件内容：**

- ❌ 不推荐：`nocode send <chatId> "帮我看看 App.jsx 的内容"` — 浪费 AI 算力，返回结果不完整且不可靠
- ✅ 推荐：`nocode files get <chatId> src/App.jsx` — 直接读取完整文件内容，快速准确

