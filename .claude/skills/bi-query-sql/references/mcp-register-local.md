# MCP Server 注册 — 非 CatClaw 本地环境（CatPaw Desk 等）

使用 `@mtfe/mcp-proxy` 作为 stdio 代理，它会自动处理 SSO 认证。

## 前置条件

- **内网 VPN 已连接**

## 步骤

### 1. 写入 mcporter 配置

将以下配置写入当前工作目录的`config/mcporter.json`：

```json
{
  "mcpServers": {
    "hive": {
      "command": "npx",
      "args": [
        "-y",
        "--registry=http://r.npm.sankuai.com",
        "@mtfe/mcp-proxy@latest",
        "http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141"
      ]
    }
  }
}
```

> **必须用 stdio 方式（`@mtfe/mcp-proxy`），不要用 `mcporter config add`**：后者只支持 HTTP URL，缺少 SSO 认证，所有 tool call 会返回空结果。

### 2. 验证

```bash
node <skill_dir>/scripts/bin/mcporter.js list hive
```

输出包含 tool 列表即注册成功。首次运行 `@mtfe/mcp-proxy` 会自动弹出浏览器完成 SSO 登录（在 CatPaw Desk 环境下会自动在内置浏览器中打开）。
