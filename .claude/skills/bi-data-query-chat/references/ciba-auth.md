# CIBA 认证指南

本文档详细说明 bi-data-query-chat skill 的 CIBA 认证流程，适用于 CatPaw Desk 本地环境和 CatClaw 沙箱环境。

## 📋 认证概述

**系统已内置 friday-mcp，自动完成 CIBA 认证流程**

### 环境认证要求

| 环境 | 认证方式 | 说明 |
|------|----------|------|
| **CatPaw Desk 本地** | CIBA 认证 | 通过 friday-mcp 自动完成 |
| **CatClaw 沙箱** | CIBA 认证 | 通过 friday-mcp 自动完成 |

> ⚠️ **重要**: CatPaw Desk 和 CatClaw 两个环境都需要进行 CIBA 认证，系统会自动完成整个流程。

### CIBA 认证流程概览

1. **系统自动获取 clientId** → 2. **系统自动发起 CIBA 认证** → 3. **用户大象 App 确认** → 4. **系统自动获取 token** → 5. **系统自动配置 mcporter**

### 认证原理

CIBA (Client-Initiated Backchannel Authentication) 是一种无浏览器的认证方式：
- 用户只需在大象 App 中确认授权
- 无需弹出浏览器或 SSO 登录框
- 适合沙箱环境和命令行工具

## 🔐 详细认证步骤

### 步骤 1: 获取必要信息

**系统自动获取必要信息**

系统会自动：
- 使用 MCP Server clientId: `101955f4e4` (mtbi_ai 固定值)
- 获取您的美团 misId

无需手动配置

### 步骤 2: 发起 CIBA 认证

**系统已内置 friday-mcp，自动完成认证流程**

系统会自动：
1. 使用 clientId: `101955f4e4`
2. 结合您的 misId 发起 CIBA 认证请求
3. 生成 authReqId 并推送到大象 App

您只需要：
- 在大象 App 中确认授权请求

### 步骤 3: 大象 App 授权

1. 打开 **大象 App**
2. 查看待处理授权请求
3. 点击 **确认授权**
4. 等待认证完成

### 步骤 4: 获取 accessToken

**系统自动完成 token 获取和配置**

系统会自动：
1. 获取认证后的 accessToken
2. 保存到 `~/.mcporter/mtbi_token` 文件
3. 配置到 mcporter 的 Authorization header

响应示例：
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 3600,
  "tokenType": "Bearer"
}
```

### 步骤 5: 配置 mcporter

使用 `mcporter config add` 命令更新配置（自动找路径，只更新 mtbi_ai）：

```bash
mcporter config add mtbi_ai \
  --url "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940" \
  --header "Authorization=Bearer <你的accessToken>" \
  --scope project
```

> 该命令会自动检测配置文件路径，无需手动指定。

### 步骤 6: 重新配置 MCP

运行 bi-data-query-chat 安装脚本重新生成配置：

```bash
# 重新运行安装脚本
bash /mnt/catclaw/.catclaw/skills/bi-data-query-chat/scripts/install_helper.sh -y
```

脚本会自动检测 token 文件并生成带认证的 MCP 配置。

## 🔧 配置验证

### 检查配置文件

```bash
# 查看生成的 MCP 配置
cat ~/.mcporter/mcporter.json

# 预期输出（带token的配置）
{
  "mcpServers": {
    "mtbi_ai": {
      "command": "npx",
      "args": [
        "-y",
        "--registry=http://r.npm.sankuai.com",
        "@mtfe/mcp-proxy@latest",
        "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"
      ],
      "env": {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      }
    }
  }
}
```

### 测试连接

```bash
# 测试 mcporter 是否能正常连接
mcporter list

# 预期输出
mcporter 0.7.3 — Listing 1 server(s)
- mtbi_ai (4 tools, 2.1s)
✔ Listed 1 servers (1 healthy).
```

### 测试查询功能

```bash
# 执行测试查询
mcporter call mtbi_ai.mtbi_data_query_tool 'query="查询近一周订单量"' 'bizId=252' 'datasetIds=[]'
```

## ⚠️ 常见问题

### Q1: 认证失败怎么办？

**可能原因：**
- misId 格式错误
- clientId 不正确
- 网络连接问题

**解决方案：**
1. 确认 misId 格式正确（纯小写，无特殊字符）
2. 确认使用正确的 clientId: `101955f4e4`
3. 检查网络连接和 VPN 状态

### Q2: token 过期如何处理？

**现象：** 查询超时或返回 `50910` / `Authentication required` 错误

**解决方案：**
1. 调用 friday-mcp skill 换票（clientId: `101955f4e4`），等用户大象确认
2. 换票成功拿到 `FINAL_TOKEN` 后，执行：
```bash
mcporter config add mtbi_ai \
  --url "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940" \
  --header "Authorization=Bearer <FINAL_TOKEN>" \
  --scope project
```
3. 重试原来的查询

### Q3: 如何确认认证成功？

**验证方法：**
1. `mcporter list` 显示 mtbi_ai 服务状态为 healthy
2. 能正常执行查询命令
3. 查询响应时间正常（< 10秒）

## 🔄 认证维护

### Token 有效期管理

- **默认有效期**: 1小时 (3600秒)
- **建议刷新频率**: 每30分钟
- **自动刷新**: 可通过脚本定时刷新

### 自动刷新脚本

```bash
#!/bin/bash
# refresh_mtbi_token.sh

**系统自动完成以下操作**：

1. 自动获取您的 misId
2. 使用 clientId: `101955f4e4`
3. 自动获取 accessToken
4. 使用 `mcporter config add mtbi_ai --header "Authorization=Bearer <token>" --scope project` 更新配置

无需手动执行 curl 命令

echo "Token refreshed: $(date)"
```

### 定时任务设置

```bash
# 添加到 crontab，每30分钟刷新一次
*/30 * * * * /path/to/refresh_mtbi_token.sh
```

## 📞 技术支持

如遇认证问题，请联系：

- **MCP 技术支持**: #mcp-support
- **Friday 认证问题**: #friday-mcp
- **CatClaw 环境问题**: #catclaw-support

---

**最后更新**: 2026年3月20日  
**适用版本**: bi-data-query-chat v0.0.7+  
**环境**: CatClaw 沙盒环境 / CatPaw Desk