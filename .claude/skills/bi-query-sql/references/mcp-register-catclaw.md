# MCP Server 注册 — CatClaw 沙箱环境

依赖 `friday-mcp` skill 完成 CIBA 换票 + HTTP 注册。

## 步骤

### 1. 获取 clientId

```bash
bash /app/skills/friday-mcp/scripts/get-clientid.sh "http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141"
```

取输出中的 `CLIENT_ID`。

### 2. 确认 MOA 已登录并获取 misId

```bash
bash /app/skills/friday-mcp/scripts/get-misid.sh
```

失败则走 `moa-login` skill 完成登录后重试。

### 3. 换票

```bash
bash /app/skills/friday-mcp/scripts/exchange-token.sh "<misId>" "<CLIENT_ID>"
```

**以 `background=false`（同步）方式运行脚本，等待其完成，不要用 `background=true` + `yieldMs` 提前返回。**

观察脚本输出，根据实际状态决定下一步：

| 输出特征 | 处理方式 |
|---|---|
| 看到 `✅ accessToken 获取成功` 且脚本已退出 | 无需通知用户，直接取 `FINAL_TOKEN` 进入步骤 4 |
| 看到 `⏳ 请在大象 App 中确认认证请求...` 且轮询超过 10 秒仍未完成 | 通知用户：「请打开大象 App 点击授权」 |
| 超过 3 分钟未完成 | 告知用户超时，引导重新执行 |

### 4. 注册到 mcporter（HTTP 方式）

```bash
mcporter config add hive http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141 \
  --header "Authorization=Bearer <FINAL_TOKEN>" \
  --allow-http
```

### 5. 验证

```bash
mcporter list hive
```

输出包含 tool 列表即注册成功。

## 注意事项

- **不可用 stdio `@mtfe/mcp-proxy` 方式**：OAuth 回调无法在沙箱中正常工作
- **每次调用前重新换票**，不复用旧 token
