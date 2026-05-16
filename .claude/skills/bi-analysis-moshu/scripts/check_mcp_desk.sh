#!/bin/bash
# check_mcp_desk.sh
# 检测 CatPaw Desk 是否配置了 mtbi-ai MCP Server（魔数智能服务）
# 若未配置，则自动添加到 ~/.catpaw/mcp/servers.json

MCP_SERVERS_FILE="$HOME/.catpaw/mcp/servers.json"

# 确保目录存在
mkdir -p "$(dirname "$MCP_SERVERS_FILE")"

# 检测是否包含 "mtbi_ai"（带引号，避免和 mtbi_ai_env_st 混淆）
if [ -f "$MCP_SERVERS_FILE" ] && grep -q '"mtbi_ai"' "$MCP_SERVERS_FILE" 2>/dev/null; then
  # 已配置，静默退出
  exit 0
fi

echo ""
echo "⚠️  检测到你尚未在 CatPaw Desk 中配置 mtbi-ai MCP Server。"
echo "   正在自动添加配置..."
echo ""

# 用 sed/shell 插入配置（不依赖 jq）
insert_with_shell() {
  local file="$1"
  local ts
  ts=$(date +%s)000
  local new_entry
  new_entry="  \"mtbi_ai\": {
    \"source\": \"market\",
    \"url\": \"http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940\",
    \"type\": \"streamable-http\",
    \"description\": \"魔数智能服务\",
    \"alias\": \"魔数智能服务\",
    \"icon\": \"\",
    \"installedAt\": $ts,
    \"timeout\": 600000
  }"

  local content
  content=$(cat "$file")

  # 如果只有 {}（空对象），直接写入
  if echo "$content" | grep -qE '^\{[[:space:]]*\}$'; then
    printf '{\n%s\n}\n' "$new_entry" > "$file"
  else
    # 在最后一个 } 前插入，并在前一行末尾加逗号
    # 用 awk：找到最后一个非空行（即最后的 } 前），在其末尾加逗号，再插入新配置
    awk -v entry="$new_entry" '
      { lines[NR] = $0 }
      END {
        # 找最后一个 } 的行号
        last_brace = 0
        for (i = NR; i >= 1; i--) {
          if (lines[i] ~ /^}/) { last_brace = i; break }
        }
        # 找 last_brace 前最后一个非空行，加逗号
        for (i = last_brace - 1; i >= 1; i--) {
          if (lines[i] !~ /^[[:space:]]*$/) {
            lines[i] = lines[i] ","
            break
          }
        }
        # 输出所有行，在 last_brace 前插入新配置
        for (i = 1; i < last_brace; i++) print lines[i]
        print entry
        print lines[last_brace]
      }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
  fi
}

# 如果文件不存在或为空，创建新文件
if [ ! -f "$MCP_SERVERS_FILE" ] || [ ! -s "$MCP_SERVERS_FILE" ]; then
  TS=$(date +%s)000
  cat > "$MCP_SERVERS_FILE" << EOF
{
  "mtbi_ai": {
    "source": "market",
    "url": "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940",
    "type": "streamable-http",
    "description": "魔数智能服务",
    "alias": "魔数智能服务",
    "icon": "",
    "installedAt": $TS
  }
}
EOF
  echo "✅ 已成功添加 mtbi-ai 配置到 $MCP_SERVERS_FILE"
  exit 0
fi

# 文件存在且非空，需要合并
# 优先用 jq（更稳健）；jq 不可用则尝试安装；最终 fallback 到纯 shell
if ! command -v jq &> /dev/null; then
  echo "⚙️  检测到缺少 jq，正在尝试安装..."
  if command -v brew &> /dev/null; then
    brew install jq &> /dev/null && echo "✅ jq 安装成功" || echo "⚠️  jq 安装失败，将使用备用方式写入"
  else
    echo "⚠️  未检测到 Homebrew，将使用备用方式写入"
  fi
fi

if command -v jq &> /dev/null; then
  TMP_FILE=$(mktemp)
  jq --arg url "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940" \
     --argjson ts "$(date +%s)000" \
     '.mtbi_ai = {
       "source": "market",
       "url": $url,
       "type": "streamable-http",
       "description": "魔数智能服务",
       "alias": "魔数智能服务",
       "icon": "",
       "installedAt": $ts
     }' "$MCP_SERVERS_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$MCP_SERVERS_FILE"
else
  # jq 不可用，使用纯 shell 方式插入
  insert_with_shell "$MCP_SERVERS_FILE"
fi

echo "✅ 已成功添加 mtbi-ai 配置到 $MCP_SERVERS_FILE"
echo ""
echo "   重启 CatPaw Desk 后配置生效。"
echo ""

exit 0
