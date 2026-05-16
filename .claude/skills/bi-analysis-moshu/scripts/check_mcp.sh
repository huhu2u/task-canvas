#!/bin/bash
# check_mcp.sh
# 检测本地是否配置了 mtbi-ai MCP Server（魔数智能服务）
# 逻辑：
#   1. 若 ~/.catpaw 不存在 → 云端环境，跳过检测
#   2. 若存在 → 本地环境，检查 ~/.catpaw/mcp/servers.json 是否含 "魔数智能服务"
#      - 不含或文件不存在 → 提醒用户安装 mtbi-ai MCP Server
#      - 含有 → 无需提示

CATPAW_DIR="$HOME/.catpaw"
MCP_SERVERS_FILE="$CATPAW_DIR/mcp/servers.json"

# 若 ~/.catpaw 不存在，说明是云端运行的 OpenClaw，不做提示
if [ ! -d "$CATPAW_DIR" ]; then
  exit 0
fi

# 本地环境：检测 servers.json 是否存在且包含 "魔数智能服务"
if [ ! -f "$MCP_SERVERS_FILE" ] || ! grep -q "魔数智能服务" "$MCP_SERVERS_FILE" 2>/dev/null; then
  echo ""
  echo "⚠️  检测到你尚未配置 mtbi-ai MCP Server（魔数智能服务）。"
  echo ""
  echo "   此 Skill 依赖魔数 MCP Server 进行数据查询，请先完成安装："
  echo ""
  echo "   👉 在 CatPaw 中搜索并安装 「mtbi-ai」 MCP Server"
  echo "      或参考文档：https://km.sankuai.com/collabpage/2826096"
  echo ""
fi
