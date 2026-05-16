#!/bin/bash

# mtbi_query.sh - 魔数系统自然语言查询工具
# 用法: ./mtbi_query.sh "<自然语言query>" <bizId> "<datasetIds>"
# CatClaw 沙箱环境通过 mcporter 调用

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测当前环境
detect_environment() {
    # 优先检查 .openclaw 目录（CatClaw 沙箱的可靠标志）
    if [[ -d "$HOME/.openclaw" ]]; then
        echo "catclaw"
    # 其次检查 .catpaw 目录
    elif [[ -d "$HOME/.catpaw" ]]; then
        echo "catpaw"
    else
        echo "unknown"
    fi
}

# 帮助信息
show_help() {
    echo "用法: $0 \"<自然语言query>\" <bizId> \"<datasetIds>\""
    echo ""
    echo "参数:"
    echo "  自然语言query: 数据查询需求描述（用双引号包围）"
    echo "  bizId: 业务线ID（数字）"
    echo "  datasetIds: 数据集ID列表（JSON数组格式，如 \"[]\" 或 \"[\\\"ds1\\\",\\\"ds2\\\"]\"）"
    echo ""
    echo "示例:"
    echo "  $0 \"查询近一周的订单量\" 123 \"[]\""
    echo "  $0 \"查询上周各城市GMV\" 456 \"[\\\"dataset_001\\\"]\""
    echo ""
    echo "环境支持:"
    echo "  - CatClaw 沙箱环境：通过 mcporter 调用，Bearer Token 认证"
    echo "  - CatPaw 本地环境：通过 mcporter 调用，自动鉴权"
    echo ""
    echo "注意: 所有参数都需要用双引号包围"
    exit 0
}

# Bug3 修复：-h 判断提到参数个数检查之前
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
fi

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${RED}错误: 缺少参数${NC}"
    show_help
fi

if [ $# -lt 2 ]; then
    echo -e "${RED}错误: 需要至少2个参数${NC}"
    show_help
fi

# 获取参数
QUERY="$1"
BIZ_ID="$2"
DATASET_IDS="${3:-[]}"  # 默认为空数组

# 验证参数
if [ -z "$QUERY" ]; then
    echo -e "${RED}错误: 查询内容不能为空${NC}"
    exit 1
fi

if ! [[ "$BIZ_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}错误: bizId必须是数字${NC}"
    exit 1
fi

# 检查jq是否可用
if ! command -v jq &> /dev/null; then
    echo -e "${RED}错误: jq命令未找到，请确保已安装jq${NC}"
    echo -e "${YELLOW}安装方法:${NC}"
    echo "  macOS: brew install jq"
    echo "  Linux: apt-get install jq 或 yum install jq"
    exit 1
fi

# 检查mcporter是否可用
if ! command -v mcporter &> /dev/null; then
    echo -e "${RED}错误: mcporter命令未找到，请确保已安装mcporter${NC}"
    echo -e "${YELLOW}安装方法: npm install -g mcporter${NC}"
    exit 1
fi

# 显示查询信息
ENV=$(detect_environment)
echo -e "${GREEN}正在执行魔数查询...${NC}"
echo -e "当前环境: ${BLUE}$ENV${NC}"
echo -e "查询内容: ${YELLOW}$QUERY${NC}"
echo -e "业务线ID: ${YELLOW}$BIZ_ID${NC}"
echo -e "数据集ID: ${YELLOW}$DATASET_IDS${NC}"
echo ""

# 检查 CatClaw 环境是否配置了 token
if [[ "$ENV" == "catclaw" ]]; then
    TOKEN_FILE="$HOME/.mcporter/mtbi_token"
    if [ ! -f "$TOKEN_FILE" ]; then
        echo -e "${YELLOW}警告: CatClaw 沙箱环境需要配置认证 token${NC}"
        echo -e "请参考 references/ciba-auth.md 获取认证指南"
        echo ""
    fi
fi

# Bug4 修复：用 jq -Rs 处理 query，去掉外层引号后作为裸字符串传给 mcporter
# jq -R . 会输出 "xxx"（带引号），mcporter call 的 key=value 格式里 value 本身就需要带引号
ESCAPED_QUERY=$(echo "$QUERY" | jq -Rs '.[:-1]')
ESCAPED_DATASETS=$(echo "$DATASET_IDS" | jq -c .)

cmd=("mcporter" "call" "mtbi_ai.mtbi_data_query_tool" "query=$ESCAPED_QUERY" "bizId=$BIZ_ID" "datasetIds=$ESCAPED_DATASETS")

echo -e "${YELLOW}执行命令: ${cmd[*]}${NC}"
echo ""

# 执行命令
if "${cmd[@]}"; then
    echo -e "\n${GREEN}查询完成!${NC}"
else
    echo -e "\n${RED}查询失败!${NC}"
    # 提供环境相关的错误提示
    if [[ "$ENV" == "catclaw" ]]; then
        echo -e "${YELLOW}提示: CatClaw 环境请检查认证 token 是否有效${NC}"
        echo -e "参考: references/ciba-auth.md"
    elif [[ "$ENV" == "unknown" ]]; then
        echo -e "${YELLOW}提示: 未识别的环境，请确保 mcporter 配置正确${NC}"
    fi
    exit 1
fi
