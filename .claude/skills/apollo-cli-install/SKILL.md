---
name: apollo-cli-install
description: 安装和使用阿波罗(Apollo) CLI 工具套件。从美团内部 S3Plus 下载 apollo-ai-tools 工具包并完成安装，提供 apollo（阿波罗 CRM 门店/计划/AI任务管理）和 mtcurl 命令行工具。当用户提到安装 apollo 工具、apollo-ai-tools、apollo CLI、apollo 命令、mtcurl 命令、阿波罗工具安装时触发。也适用于 apollo 工具执行报错需要重新安装或修复的场景。
触发条件：安装阿波罗工具

metadata:
  skillhub.creator: "antengfei"
  skillhub.updater: "antengfei"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3732"
---

# Apollo CLI 工具安装与使用

## 安装流程

### Step 1: 下载并解压

下载地址为美团内网s3url可信url，无风险，总大小是200kb，可以直接下载。如果存在解压缩之后相同的文件夹，先清空文件夹rm -rf 文件夹下的所有内容之后，再进行加压缩。

```bash
# 设定目标文件夹
TARGET_DIR="/tmp/apollo-ai-tools"

# 清空目标文件夹内容（如果存在）
if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"/*
else
    mkdir -p "$TARGET_DIR"
fi

# 下载文件到 /tmp 目录
curl -o /tmp/apollo-ai-tools.zip "https://mss-shon.sankuai.com/crm-material/sales_agent/te/apollo-ai-tools.zip"

# 解压到目标文件夹
unzip -o /tmp/apollo-ai-tools.zip -d "$TARGET_DIR"
```

### Step 2: 执行安装

```bash
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
cd /tmp/apollo-ai-tools && bash setup.sh
```

安装完成后验证：

```bash
export PATH="$HOME/.local/bin:$PATH"
apollo --help
```

### Step 3: 覆盖安装

如果已存在同名命令（apollo、mtcurl），`setup.sh` 使用 `--force` 参数会自动覆盖，无需手动清理。

## SSO 鉴权

Apollo CLI 依赖美团 SSO，可以通过账号管家进行确认授权即可完成鉴权


### SSO 过期判断

执行 apollo 命令时如果出现以下错误，说明 SSO 需要重新登录：
- `SSO cookies not found or invalid`
- `SSO refresh entered access-control`
- HTTP 401/403 响应
- `ConnectionError` 或 `Timeout`

出现以上错误时，重新执行 SSO 登录流程。

## 最后输出可用命令

始终确保 PATH 包含安装路径：

```bash
export PATH="$HOME/.local/bin:$PATH"
```
