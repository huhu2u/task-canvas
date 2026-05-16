# 安装指南

## 依赖要求

| 依赖 | 版本要求 | 自动安装 | 说明 |
|------|----------|:--------:|------|
| Node.js | ≥18 | ❌ | JavaScript 运行时，需用户手动安装 |
| npm | 随 Node.js | ❌ | Node 包管理器 |
| jq | 最新版 | ✅ | JSON 处理工具 |
| mcporter | 最新版 | ✅ | MCP CLI 工具 |
| misId | - | ❌ | 美团工号，需用户提供 |

---

## 安装路径

根据您使用的工具选择对应路径：

| 工具 | Skills 路径 |
|------|-------------|
| CatPaw | `~/.catpaw/skills/` |
| CatClaw | `~/.catclaw/skills/` |

---

## 认证配置（美团内网）

CatPaw/CatClaw 在沙盒环境中运行，需要通过 CIBA 认证：

### CIBA 认证流程

1. **提供 misId**: 当提示需要认证时，提供您的美团工号（如 zhangsan）
2. **发起认证**: 系统自动发起 CIBA 认证
3. **确认授权**: 在大象 App 上点击确认授权
4. **完成认证**: 认证成功后即可正常使用

### 注意事项

- misId 是美团工号，不带 @meituan.com 后缀
- 认证有效期有限，过期需重新授权
- 如未收到推送，检查大象 App 通知设置

---

## Node.js 安装方式

### 方式1: 官方安装包（推荐非开发者）

访问 https://nodejs.org/ 下载 LTS 版本，双击安装。

### 方式2: nvm（推荐开发者，可管理多版本）

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.zshrc  # 或 source ~/.bashrc
nvm install --lts
```

### 方式3: fnm（快速，用 Rust 编写）

```bash
brew install fnm          # macOS
fnm install --lts
```

### 方式4: Homebrew

```bash
brew install node
```

### 方式5: Conda

```bash
conda install -c conda-forge nodejs
```

---

## mcporter 安装

```bash
npm install -g mcporter
```

---

## 配置文件位置

MCP 配置文件位于：`~/.mcporter/mcporter.json`

---

## 验证安装

```bash
node --version && jq --version && mcporter --version
```

---

## 踩坑记录（CatClaw 龙虾环境）

以下是在 CatClaw 龙虾环境中实际踩过的坑及解决方案：

### 常见问题

| 问题表现 | 原因 | 解决方案 |
|---------|------|---------|
| `No such file or directory` | 脚本路径不对 | CatPaw 用 `~/.catpaw`，CatClaw 用 `~/.catclaw` |
| mcporter 调用无输出（exit 0 但空结果） | 未认证或 server offline | 检查认证状态和服务器状态 |
| MOA 登录报 D-Bus 错误 | 沙箱环境限制，弹不出登录框 | 走 Friday MCP 流程认证 |
| install_helper.sh 测试超时（exit 124） | 未认证导致连接超时 | 跳过连接测试，装完依赖即可 |
| `tool config not found` | 工具名带前缀不对 | 用 `mcporter list <server> --schema` 确认实际工具名 |

### 关键教训

1. **跳过 skill 自带的连接测试**
   - 未认证时连接测试必然失败
   - 安装脚本装完依赖即可，不必等测试通过

2. **认证必须走 Friday MCP 流程**
   ```bash
   # 认证流程
   mcporter get-clientid          # 获取 client ID
   mcporter exchange-token        # 换取 token
   mcporter config add --bearer   # 添加 Bearer token
   ```

3. **Token 有时效**
   - 每次都要重新换票
   - Token 过期后需重新认证

4. **确认工具名**
   ```bash
   # 用 --schema 确认实际的工具名和参数格式
   mcporter list mtbi_ai --schema
   ```

### 快速检查环境

```bash
# CatPaw 用户
bash ~/.catpaw/skills/bi-data-query-chat/scripts/install_helper.sh -q

# CatClaw 用户
bash ~/.catclaw/skills/bi-data-query-chat/scripts/install_helper.sh -q
```

返回"✅ 环境就绪"表示依赖已安装（不测试连接）。
