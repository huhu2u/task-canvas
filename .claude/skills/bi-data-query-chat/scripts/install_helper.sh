#!/bin/bash

# bi-data-query-chat 一键安装助手
# 适用于 CatClaw 沙箱环境和 CatPaw IDE 环境
# CatPaw Desk 用户使用 catdesk mcp add 命令配置

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测是否在 CatPaw IDE 环境（优先判断）
check_ide_environment() {
    local IDE_CONFIG=""
    for path in \
        "$HOME/Library/Application Support/CatPaw/User/globalStorage/mt-idekit.mt-idekit-code/settings/mcopilot_mcp_settings.json" \
        "$HOME/.config/CatPaw/User/globalStorage/mt-idekit.mt-idekit-code/settings/mcopilot_mcp_settings.json"
    do
        if [ -f "$path" ]; then
            IDE_CONFIG="$path"
            break
        fi
    done
    
    if [ -n "$IDE_CONFIG" ]; then
        echo -e "${GREEN}检测到 CatPaw IDE 环境${NC}"
        echo -e "配置文件: ${GREEN}$IDE_CONFIG${NC}"
        return 0
    fi
    return 1
}

# 检测是否在 CatPaw Desk 环境（无需此脚本，需在 IDE 检测之后）
check_desk_environment() {
    # CatPaw Desk: 检查 ~/.catpaw/mcp/servers.json 是否存在
    local DESK_CONFIG="$HOME/.catpaw/mcp/servers.json"
    
    # 如果检测到 Desk 配置，提示用户并退出
    if [ -f "$DESK_CONFIG" ]; then
        echo -e "${GREEN}============================================${NC}"
        echo -e "${GREEN}🎉 检测到 CatPaw Desk 环境${NC}"
        echo -e "${GREEN}============================================${NC}"
        echo ""
        echo -e "您无需运行此安装脚本！"
        echo ""
        echo -e "${BLUE}CatPaw Desk 环境${NC}："
        echo -e "  • 使用 catdesk mcp add 命令配置 MCP"
        echo -e "  • 认证通过 Desk SSO 自动完成"
        echo ""
        echo -e "${YELLOW}请直接在对话中使用本 Skill 即可${NC}"
        echo ""
        echo -e "检测到的配置文件: ${GREEN}$DESK_CONFIG${NC}"
        echo ""
        exit 0
    fi
}

# 检测环境
detect_environment() {
    echo -e "${BLUE}🔍 检测您的环境...${NC}"
    
    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS_NAME="macOS"
        echo -e "  🖥️  操作系统: ${GREEN}macOS${NC}"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        OS_NAME="Linux"
        echo -e "  🖥️  操作系统: ${GREEN}Linux${NC}"
    else
        OS_NAME="Unknown"
        echo -e "  🖥️  操作系统: ${YELLOW}Unknown ($OSTYPE)${NC}"
    fi
    
    # 检测用户目录
    USER_HOME="$HOME"
    USER_NAME="$(whoami)"
    echo -e "  👤 用户: ${GREEN}$USER_NAME${NC}"
    echo -e "  🏠 用户目录: ${GREEN}$USER_HOME${NC}"
    
    # 检测CatPaw/CatClaw
    CATPAW_PATH=""
    OPENCLAW_PATH=""
    INSTALL_TOOL=""
    
    # 检查CatPaw
    for path in "$HOME/.catpaw/skills" "$HOME/Library/Application Support/CatPaw/skills" "$HOME/.config/catpaw/skills"; do
        if [ -d "$path" ]; then
            CATPAW_PATH="$path"
            echo -e "  🐱 找到CatPaw: ${GREEN}$path${NC}"
            break
        fi
    done
    
    # 检查CatClaw
    for path in "$HOME/.catclaw/skills" "$HOME/Library/Application Support/CatClaw/skills" "$HOME/.config/catclaw/skills"; do
        if [ -d "$path" ]; then
            OPENCLAW_PATH="$path"
            echo -e "  🦁 找到CatClaw: ${GREEN}$path${NC}"
            break
        fi
    done
    
    # 确定安装工具
    if [ -n "$CATPAW_PATH" ]; then
        INSTALL_TOOL="CatPaw"
        INSTALL_PATH="$CATPAW_PATH/bi-data-query-chat"
    elif [ -n "$OPENCLAW_PATH" ]; then
        INSTALL_TOOL="CatClaw"
        INSTALL_PATH="$OPENCLAW_PATH/bi-data-query-chat"
    else
        INSTALL_TOOL="CatPaw"
        INSTALL_PATH="$HOME/.catpaw/skills/bi-data-query-chat"
        echo -e "  💡 未找到现有安装，将使用默认CatPaw路径"
    fi
    
    echo -e "  🎯 检测完成: ${GREEN}$OS_NAME + $INSTALL_TOOL${NC}"
    echo -e "  📁 安装路径: ${GREEN}$INSTALL_PATH${NC}"
    echo ""
}

# 欢迎信息
show_welcome() {
    clear
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}    🚀 bi-data-query-chat 一键安装助手${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    echo -e "${GREEN}欢迎使用魔数查询工具！${NC}"
    echo ""
    echo "本助手将帮您完成以下工作："
    echo "  ✅ 智能检测您的环境"
    echo "  ✅ 自动识别使用工具"
    echo "  ✅ 检查并安装必要工具"
    echo "  ✅ 配置魔数连接"
    echo "  ✅ 测试功能是否正常"
    echo ""
    echo -e "${YELLOW}智能适配您的操作系统和使用工具！${NC}"
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo ""
}

# 通过多种方式安装jq (macOS)
install_jq_macos() {
    local JQ_VERSION="1.7.1"
    local JQ_URL="https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-macos-amd64"
    local JQ_PATH="/usr/local/bin/jq"
    
    echo "  方式1: 尝试通过 Homebrew 安装..."
    if command -v brew &> /dev/null; then
        if brew install jq 2>/dev/null; then
            echo -e "  ✅ ${GREEN}jq安装成功 (via Homebrew)${NC}"
            return 0
        fi
    fi
    
    echo "  方式2: 尝试直接下载二进制文件..."
    if command -v curl &> /dev/null; then
        if curl -fsSL "$JQ_URL" -o /tmp/jq && chmod +x /tmp/jq; then
            # 尝试移动到用户目录（不需要sudo）
            mkdir -p "$HOME/.local/bin"
            mv /tmp/jq "$HOME/.local/bin/jq"
            # 添加到PATH
            if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
                echo "  ⚠️  请将以下内容添加到 ~/.zshrc 或 ~/.bashrc:"
                echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
            fi
            echo -e "  ✅ ${GREEN}jq安装成功 (下载二进制) -> $HOME/.local/bin/jq${NC}"
            return 0
        fi
    fi
    
    echo "  方式3: 尝试通过 conda 安装..."
    if command -v conda &> /dev/null; then
        if conda install -y -c conda-forge jq 2>/dev/null; then
            echo -e "  ✅ ${GREEN}jq安装成功 (via Conda)${NC}"
            return 0
        fi
    fi
    
    return 1
}

# 检查并安装jq
check_and_install_jq() {
    echo -e "${BLUE}检查jq工具...${NC}"
    
    if command -v jq &> /dev/null; then
        echo -e "  ✅ jq已安装: ${GREEN}$(jq --version)${NC}"
        return 0
    fi
    
    echo -e "  ${YELLOW}jq未安装，正在尝试自动安装...${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - 多种安装方式
        if install_jq_macos; then
            return 0
        else
            echo -e "  ❌ ${RED}自动安装失败，请手动安装jq${NC}"
            echo "  💡 安装方式："
            echo "     - brew install jq"
            echo "     - conda install -c conda-forge jq"
            echo "     - 下载: https://github.com/jqlang/jq/releases"
            return 1
        fi
    elif [[ "$OSTYPE" == "linux"* ]]; then
        # Linux - 尝试多种包管理器
        if command -v apt-get &> /dev/null; then
            echo "  尝试通过 apt 安装..."
            if sudo apt-get update -qq && sudo apt-get install -y -qq jq; then
                echo -e "  ✅ ${GREEN}jq安装成功${NC}"
                return 0
            fi
        fi
        if command -v yum &> /dev/null; then
            echo "  尝试通过 yum 安装..."
            if sudo yum install -y -q jq; then
                echo -e "  ✅ ${GREEN}jq安装成功${NC}"
                return 0
            fi
        fi
        if command -v dnf &> /dev/null; then
            echo "  尝试通过 dnf 安装..."
            if sudo dnf install -y -q jq; then
                echo -e "  ✅ ${GREEN}jq安装成功${NC}"
                return 0
            fi
        fi
        if command -v pacman &> /dev/null; then
            echo "  尝试通过 pacman 安装..."
            if sudo pacman -S --noconfirm jq; then
                echo -e "  ✅ ${GREEN}jq安装成功${NC}"
                return 0
            fi
        fi
        if command -v conda &> /dev/null; then
            echo "  尝试通过 conda 安装..."
            if conda install -y -c conda-forge jq 2>/dev/null; then
                echo -e "  ✅ ${GREEN}jq安装成功${NC}"
                return 0
            fi
        fi
        echo -e "  ❌ ${RED}无法自动安装jq，请手动安装${NC}"
        return 1
    fi
    
    return 1
}

# 检查Node.js版本是否>=18
check_node_version() {
    local version=$(node --version 2>/dev/null)
    if [ -z "$version" ]; then
        return 1
    fi
    
    local major_version=$(echo "$version" | sed 's/v//; s/\..*//')
    if [ "$major_version" -ge 18 ]; then
        return 0
    else
        return 1
    fi
}

# 检查工具
check_tools() {
    echo -e "${BLUE}步骤1: 检查必要工具...${NC}"
    echo ""
    
    # 检查Node.js
    if command -v node &> /dev/null; then
        node_version=$(node --version)
        if check_node_version; then
            echo -e "  ✅ Node.js已安装: ${GREEN}${node_version}${NC} (>=18 ✓)"
        else
            echo -e "  ⚠️  ${YELLOW}Node.js版本过低: ${node_version}${NC}"
            echo "  💡 建议升级到 Node.js 18 或更高版本"
        fi
    else
        echo -e "  ❌ ${RED}Node.js未安装${NC}"
        echo "  💡 请先安装Node.js 18或更高版本:"
        echo ""
        echo "  安装方式（任选一种）："
        echo "  ┌─────────────────────────────────────────────────────────┐"
        echo "  │ 1. 官方安装包（推荐）                                    │"
        echo "  │    访问: https://nodejs.org/ 下载 LTS 版本              │"
        echo "  │                                                         │"
        echo "  │ 2. Homebrew (macOS)                                     │"
        echo "  │    brew install node                                    │"
        echo "  │                                                         │"
        echo "  │ 3. nvm (Node版本管理器，推荐开发者使用)                   │"
        echo "  │    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
        echo "  │    source ~/.zshrc                                      │"
        echo "  │    nvm install --lts                                    │"
        echo "  │                                                         │"
        echo "  │ 4. fnm (快速Node版本管理器)                              │"
        echo "  │    brew install fnm          # macOS                    │"
        echo "  │    fnm install --lts                                    │"
        echo "  │                                                         │"
        echo "  │ 5. Conda                                                │"
        echo "  │    conda install -c conda-forge nodejs                  │"
        echo "  └─────────────────────────────────────────────────────────┘"
        echo ""
        exit 1
    fi
    
    # 检查npm
    if command -v npm &> /dev/null; then
        npm_version=$(npm --version)
        echo -e "  ✅ npm已安装: ${GREEN}${npm_version}${NC}"
    else
        echo -e "  ❌ ${RED}npm未安装${NC}"
        echo "  💡 npm通常随Node.js一起安装，请重新安装Node.js"
        exit 1
    fi
    
    # 检查并安装jq
    check_and_install_jq || exit 1
    
    echo ""
}

# 安装mcporter
install_mcporter() {
    echo -e "${BLUE}步骤2: 安装mcporter工具...${NC}"
    echo ""
    
    if command -v mcporter &> /dev/null; then
        echo -e "  ✅ mcporter已安装: ${GREEN}$(which mcporter)${NC}"
        echo ""
        return 0
    fi
    
    echo "  正在安装mcporter..."
    echo "  (这可能需要几十秒，请耐心等待)"
    
    # 使用超时机制（60秒）
    if command -v timeout &> /dev/null; then
        if timeout 60 npm install -g mcporter 2>&1; then
            echo -e "  ✅ ${GREEN}mcporter安装成功${NC}"
            echo ""
            return 0
        else
            echo -e "  ❌ ${RED}mcporter安装失败或超时${NC}"
            exit 1
        fi
    else
        # macOS 没有 timeout 命令，直接安装
        if npm install -g mcporter 2>&1; then
            echo -e "  ✅ ${GREEN}mcporter安装成功${NC}"
            echo ""
            return 0
        else
            echo -e "  ❌ ${RED}mcporter安装失败${NC}"
            exit 1
        fi
    fi
}

# 配置MCP（合并写入，不覆盖已有配置）
configure_mcp() {
    echo -e "${BLUE}步骤3: 配置魔数连接...${NC}"
    echo ""
    
    # mcporter 默认查找 ~/.mcporter/mcporter.json
    CONFIG_DIR="${HOME}/.mcporter"
    CONFIG_FILE="${CONFIG_DIR}/mcporter.json"
    
    # 创建配置目录
    mkdir -p "$CONFIG_DIR"
    
    # 构造 mtbi_ai 的 server 配置（方案B：jq -n 原生构建，安全处理特殊字符）
    local NEW_SERVER
    local MCP_BASE_URL="http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"
    local MCP_NPM_PKG="@mtfe/mcp-proxy@latest"
    local MCP_NPM_REG="http://r.npm.sankuai.com"
    
    # 检查是否有认证token文件（CatClaw沙盒环境）
    TOKEN_FILE="$CONFIG_DIR/mtbi_token"
    if [ -f "$TOKEN_FILE" ]; then
        MCP_TOKEN=$(cat "$TOKEN_FILE" 2>/dev/null | tr -d '[:space:]')
        if [ -n "$MCP_TOKEN" ]; then
            # jq --arg 安全注入 token，完全避免 shell 字符串插值破坏 JSON
            NEW_SERVER=$(jq -n \
                --arg token "Bearer $MCP_TOKEN" \
                --arg pkg "$MCP_NPM_PKG" \
                --arg reg "$MCP_NPM_REG" \
                --arg url "$MCP_BASE_URL" \
                '{"command":"npx","args":["-y",("--registry="+$reg),$pkg,$url],"env":{"Authorization":$token}}')
            echo -e "  🔑 认证方式: ${GREEN}Friday MCP Bearer Token${NC}"
        fi
    fi
    
    # 无 token 时构建基础配置
    if [ -z "$NEW_SERVER" ]; then
        NEW_SERVER=$(jq -n \
            --arg pkg "$MCP_NPM_PKG" \
            --arg reg "$MCP_NPM_REG" \
            --arg url "$MCP_BASE_URL" \
            '{"command":"npx","args":["-y",("--registry="+$reg),$pkg,$url]}')
    fi
    
    # 合并写入：已有配置则追加 mtbi_ai，无配置则新建
    if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
        # 文件存在且是有效 JSON
        
        # 备份原配置文件（便于回滚）
        cp "$CONFIG_FILE" "${CONFIG_FILE}.bak" 2>/dev/null
        
        # 检查是否存在 mcpServers 字段
        if jq -e '.mcpServers' "$CONFIG_FILE" >/dev/null 2>&1; then
            # mcpServers 存在，直接合并
            if jq --argjson new "$NEW_SERVER" '.mcpServers.mtbi_ai = $new' \
                "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" 2>/dev/null \
                && [ -s "${CONFIG_FILE}.tmp" ] \
                && jq empty "${CONFIG_FILE}.tmp" 2>/dev/null; then
                mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
                echo -e "  ✅ ${GREEN}mtbi_ai 已追加到现有配置（保留其他 MCP Server）${NC}"
            else
                rm -f "${CONFIG_FILE}.tmp"
                echo -e "  ⚠️  ${YELLOW}合并失败，恢复原配置${NC}"
                mv "${CONFIG_FILE}.bak" "$CONFIG_FILE" 2>/dev/null
                _create_mcp_config "$NEW_SERVER"
            fi
        else
            # mcpServers 不存在，需要添加该字段
            echo -e "  ℹ️  ${YELLOW}现有配置缺少 mcpServers 字段，正在添加...${NC}"
            if jq --argjson new "$NEW_SERVER" '. + {"mcpServers": {"mtbi_ai": $new}}' \
                "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" 2>/dev/null \
                && [ -s "${CONFIG_FILE}.tmp" ] \
                && jq empty "${CONFIG_FILE}.tmp" 2>/dev/null; then
                mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
                echo -e "  ✅ ${GREEN}mtbi_ai 已添加到配置文件${NC}"
            else
                rm -f "${CONFIG_FILE}.tmp"
                echo -e "  ⚠️  ${YELLOW}添加字段失败，恢复原配置${NC}"
                mv "${CONFIG_FILE}.bak" "$CONFIG_FILE" 2>/dev/null
                _create_mcp_config "$NEW_SERVER"
            fi
        fi
        
        # 清理备份文件（成功后）
        rm -f "${CONFIG_FILE}.bak" 2>/dev/null
    else
        # 文件不存在或不是有效 JSON → 新建
        _create_mcp_config "$NEW_SERVER"
    fi
    
    echo "  配置文件: $CONFIG_FILE"
    echo ""
}

# 创建基础MCP配置（内部函数，新建文件）
_create_mcp_config() {
    CONFIG_DIR="${HOME}/.mcporter"
    CONFIG_FILE="${CONFIG_DIR}/mcporter.json"
    local SERVER_JSON="$1"
    if [ -z "$SERVER_JSON" ]; then
        SERVER_JSON=$(jq -n \
            --arg pkg "@mtfe/mcp-proxy@latest" \
            --arg reg "http://r.npm.sankuai.com" \
            --arg url "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940" \
            '{"command":"npx","args":["-y",("--registry="+\$reg),\$pkg,\$url]}')
    fi
    
    # 如果原文件存在但无效，备份它
    if [ -f "$CONFIG_FILE" ]; then
        mv "$CONFIG_FILE" "${CONFIG_FILE}.invalid.bak" 2>/dev/null
        echo -e "  ℹ️  ${YELLOW}原配置文件无效，已备份为 .invalid.bak${NC}"
    fi
    
    # 写入新配置
    jq -n --argjson server "$SERVER_JSON" '{"mcpServers":{"mtbi_ai":$server}}' > "$CONFIG_FILE"
    
    # 验证写入成功
    if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
        echo -e "  ✅ ${GREEN}MCP配置创建成功${NC}"
    else
        echo -e "  ❌ ${RED}MCP配置创建失败${NC}"
        return 1
    fi
    
    echo -e "  💡 ${YELLOW}CatClaw沙盒用户需要额外认证token"
    echo "     请参考认证流程获取并配置MCP token${NC}"
}

# 测试连接
test_connection() {
    echo -e "${BLUE}步骤4: 测试连接...${NC}"
    echo ""
    
    echo "  正在测试MCP服务器连接..."
    echo "  (超时时间: 30秒)"
    
    local result
    if command -v timeout &> /dev/null; then
        result=$(timeout 30 mcporter list mtbi_ai 2>&1)
    else
        # macOS 使用 gtimeout 或直接执行
        result=$(mcporter list mtbi_ai 2>&1)
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "  ✅ ${GREEN}服务器连接成功${NC}"
        echo ""
        return 0
    else
        echo -e "  ❌ ${RED}服务器连接失败${NC}"
        echo "  💡 请检查网络连接或联系技术支持"
        if [ -n "$result" ]; then
            echo "  错误信息: $result"
        fi
        exit 1
    fi
}

# 测试功能
test_function() {
    echo -e "${BLUE}步骤5: 测试魔数查询功能...${NC}"
    echo ""
    
    echo "  正在测试自然语言查询功能..."
    echo "  (查询示例: 查询近一周的订单量)"
    
    local result
    if command -v timeout &> /dev/null; then
        result=$(timeout 30 mcporter call mtbi_ai.mtbi_data_query_tool 'query="查询近一周的订单量"' 'bizId=123' 'datasetIds=[]' 2>&1)
    else
        result=$(mcporter call mtbi_ai.mtbi_data_query_tool 'query="查询近一周的订单量"' 'bizId=123' 'datasetIds=[]' 2>&1)
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "  ✅ ${GREEN}魔数查询功能测试成功${NC}"
        echo ""
        return 0
    else
        echo -e "  ⚠️  ${YELLOW}魔数查询功能测试失败（可能缺少权限或参数）${NC}"
        echo "  💡 请确认业务线ID和访问权限"
        if [ -n "$result" ]; then
            echo "  错误信息: $result"
        fi
        echo "  ⚠️  基础环境已配置完成，查询功能需要有效权限"
        echo ""
        return 0  # 不退出，因为可能是权限问题
    fi
}

# 完成信息
show_completion() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${GREEN}🎉 恭喜！安装完成！${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    echo -e "${GREEN}📊 安装总结：${NC}"
    echo "  ✅ Node.js: $(node --version)"
    echo "  ✅ jq: $(jq --version 2>/dev/null || echo '已安装')"
    echo "  ✅ mcporter: $(mcporter --version 2>/dev/null || echo '已安装')"
    echo "  ✅ MCP配置: $HOME/.mcporter/mcporter.json"
    echo ""
    echo -e "${GREEN}魔数查询工具已经准备就绪！${NC}"
    echo ""
    
    # 显示安装的工具类型
    if [ -n "$INSTALL_TOOL" ]; then
        if [ "$INSTALL_TOOL" = "CatPaw" ]; then
            echo -e "🐱 ${GREEN}CatPaw用户：重启IDE即可使用新skill${NC}"
        else
            echo -e "🦁 ${GREEN}CatClaw用户：重启IDE即可使用新skill${NC}"
        fi
        echo ""
    fi
    
    echo "现在您可以这样使用："
    echo ""
    echo -e "${YELLOW}方式1: 自然语言${NC}"
    echo '  "帮我查询近一周的订单量"'
    echo '  "查看上周各城市的GMV数据"'
    echo ""
    echo -e "${YELLOW}方式2: 简单命令${NC}"
    echo '  mtbi_query "查询近一周的订单量" 123 "[]"'
    echo '  mtbi_query "查询上周各城市GMV" 456 "[\"dataset_001\"]"'
    echo ""
    echo -e "${YELLOW}方式3: 使用脚本${NC}"
    echo "  ~/.catpaw/skills/bi-data-query-chat/scripts/mtbi_query.sh \"查询近一周的订单量\" 123 \"[]\""
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${GREEN}祝您使用愉快！${NC}"
    echo -e "${BLUE}==========================================${NC}"
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -q, --quick    快速检查环境是否就绪（不安装、不测试）"
    echo "  -y, --yes      跳过确认，非交互模式运行（完整安装）"
    echo "  -i, --interactive  交互模式"
    echo "  -h, --help     显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -q          # 快速检查（推荐每次查询前使用）"
    echo "  $0 -y          # 完整安装"
    echo "  $0             # 交互模式"
    exit 0
}

# 快速检查环境是否就绪（用于每次查询前的检测）
quick_check() {
    local missing=()
    local warnings=()
    
    # 检查必要工具是否存在
    command -v node &> /dev/null || missing+=("Node.js")
    command -v jq &> /dev/null || missing+=("jq")
    command -v mcporter &> /dev/null || missing+=("mcporter")
    
    # 检查配置文件是否存在
    [ -f "$HOME/.mcporter/mcporter.json" ] || missing+=("MCP配置文件")
    
    # 检查 Node.js 版本
    if command -v node &> /dev/null; then
        local version=$(node --version 2>/dev/null | sed 's/v//; s/\..*//')
        [ "$version" -ge 18 ] 2>/dev/null || missing+=("Node.js版本过低(需要≥18)")
    fi
    
    # 检查 CatClaw 环境是否需要 token
    if [[ "$OSTYPE" == "linux"* ]] && [[ "$HOME" == /mnt/catclaw* ]]; then
        if [ ! -f "$HOME/.mcporter/mtbi_token" ]; then
            warnings+=("CatClaw沙盒环境建议配置MCP认证token")
        else
            local token=$(cat "$HOME/.mcporter/mtbi_token" 2>/dev/null | tr -d '[:space:]')
            if [ -z "$token" ]; then
                warnings+=("MCP token文件为空，请配置有效token")
            fi
        fi
    fi
    
    # 如果有缺失，给出提示
    if [ ${#missing[@]} -gt 0 ]; then
        echo "⚠️ 环境未就绪，缺少以下组件:"
        for item in "${missing[@]}"; do
            echo "   - $item"
        done
        echo ""
        echo "请运行: $0 -y 安装缺失的依赖"
        return 1
    fi
    
    # 显示警告信息
    if [ ${#warnings[@]} -gt 0 ]; then
        echo "✅ 基础环境就绪，但有以下建议:"
        for warning in "${warnings[@]}"; do
            echo "   - $warning"
        done
        echo ""
        echo "💡 参考: references/ciba-auth.md 获取认证指南"
        echo ""
    fi
    
    return 0
}

# 自动检测 Skills 路径
detect_skills_path() {
    # 优先检查 CatPaw
    for path in "$HOME/.catpaw/skills" "$HOME/Library/Application Support/CatPaw/skills"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # 其次检查 CatClaw
    for path in "$HOME/.catclaw/skills" "$HOME/Library/Application Support/CatClaw/skills"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # 默认返回 CatPaw 路径
    echo "$HOME/.catpaw/skills"
    return 1
}

# 解析参数
# 默认非交互模式（直接安装，不需要确认）
NON_INTERACTIVE=true
QUICK_CHECK=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            NON_INTERACTIVE=true
            shift
            ;;
        -i|--interactive)
            NON_INTERACTIVE=false
            shift
            ;;
        -q|--quick)
            QUICK_CHECK=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "未知参数: $1"
            show_help
            ;;
    esac
done

# 快速检查模式：只检测环境是否就绪，不做任何安装或测试
if [ "$QUICK_CHECK" = true ]; then
    if quick_check; then
        echo "✅ 环境就绪"
        exit 0
    else
        echo "⚠️ 环境未就绪，需要安装"
        exit 1
    fi
fi

# 主函数
main() {
    # 首先检测是否在 CatPaw IDE 环境（优先判断）
    IS_IDE_ENV=false
    if check_ide_environment; then
        IS_IDE_ENV=true
        echo ""
    fi
    
    # 如果不是 IDE 环境，检测是否在 CatPaw Desk 环境（无需此脚本）
    if [ "$IS_IDE_ENV" = false ]; then
        check_desk_environment
    fi
    
    show_welcome
    
    # 自动检测 Skills 路径
    SKILLS_PATH=$(detect_skills_path || true)
    echo -e "${GREEN}检测到 Skills 路径: $SKILLS_PATH${NC}"
    echo ""
    
    if [ "$NON_INTERACTIVE" = false ]; then
        echo -e "${YELLOW}按回车键开始安装...${NC}"
        read
    else
        echo -e "${GREEN}非交互模式，自动开始安装...${NC}"
        echo ""
    fi
    
    detect_environment
    check_tools
    install_mcporter
    configure_mcp
    
    # 跳过连接测试（未认证时会失败），安装完依赖即可
    echo -e "${YELLOW}⏭️ 跳过连接测试（认证完成后会自动生效）${NC}"
    echo ""
    
    show_completion
}

# 运行主函数
main