#!/bin/bash
# check_mcp_assistant.sh
# 检测 CatPaw 助理是否配置了 mtbi-ai MCP Server（魔数智能服务）
# 若未配置，则自动添加到 mcopilot_mcp_settings.json

MCP_SETTINGS_FILE="$HOME/Library/Application Support/CatPaw/User/globalStorage/mt-idekit.mt-idekit-code/settings/mcopilot_mcp_settings.json"

# 确保目录存在
mkdir -p "$(dirname "$MCP_SETTINGS_FILE")"

# 检测是否包含 "mtbi_ai"（带引号，避免和 mtbi_ai_env_st 混淆）
if [ -f "$MCP_SETTINGS_FILE" ] && grep -q '"mtbi_ai"' "$MCP_SETTINGS_FILE" 2>/dev/null; then
  # 已配置，静默退出
  exit 0
fi

echo ""
echo "⚠️  检测到你尚未在 CatPaw 助理中配置 mtbi-ai MCP Server。"
echo "   正在自动添加配置..."
echo ""

# 用 awk/shell 插入配置（不依赖 jq）
insert_with_shell() {
  local file="$1"
  local new_entry
  new_entry="    \"mtbi_ai\": {
      \"url\": \"http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940\"
    }"

  local content
  content=$(cat "$file")

  # 如果 mcpServers 是空对象 {}，直接写入
  if echo "$content" | grep -qE '"mcpServers"[[:space:]]*:[[:space:]]*\{[[:space:]]*\}'; then
    # 用 sed 替换空的 mcpServers: {} 为带内容的版本
    printf '%s' "$content" | sed 's/"mcpServers"[[:space:]]*:[[:space:]]*{[[:space:]]*}/"mcpServers": {\n'"$(echo "$new_entry" | sed 's/\//\\\//g')"'\n    }/' > "$file.tmp" && mv "$file.tmp" "$file"
  else
    # 在 mcpServers 的最后一个 } 前插入，用 awk 找到 mcpServers 块的最后一个 }
    awk -v entry="$new_entry" '
      { lines[NR] = $0 }
      END {
        # 找 "mcpServers" 起始行
        mcp_start = 0
        for (i = 1; i <= NR; i++) {
          if (lines[i] ~ /"mcpServers"/) { mcp_start = i; break }
        }
        # 从 mcp_start 开始，找对应的结束 }（深度计数）
        depth = 0; mcp_end = 0
        for (i = mcp_start; i <= NR; i++) {
          n = split(lines[i], chars, "")
          for (j = 1; j <= n; j++) {
            if (chars[j] == "{") depth++
            if (chars[j] == "}") { depth--; if (depth == 0) { mcp_end = i; break } }
          }
          if (mcp_end > 0) break
        }
        # 在 mcp_end 前找最后一个非空行，加逗号
        for (i = mcp_end - 1; i >= mcp_start; i--) {
          if (lines[i] !~ /^[[:space:]]*$/) {
            lines[i] = lines[i] ","
            break
          }
        }
        # 输出：在 mcp_end 前插入新条目
        for (i = 1; i < mcp_end; i++) print lines[i]
        print entry
        for (i = mcp_end; i <= NR; i++) print lines[i]
      }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
  fi
}

# 如果文件不存在或为空，创建新文件
if [ ! -f "$MCP_SETTINGS_FILE" ] || [ ! -s "$MCP_SETTINGS_FILE" ]; then
  cat > "$MCP_SETTINGS_FILE" << 'EOF'
{
  "mcpServers": {
    "mtbi_ai": {
      "url": "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"
    }
  }
}
EOF
  echo "✅ 已成功添加 mtbi-ai 配置到 $MCP_SETTINGS_FILE"
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
     '.mcpServers.mtbi_ai = {"url": $url}' \
     "$MCP_SETTINGS_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$MCP_SETTINGS_FILE"
else
  # jq 不可用，使用纯 shell 方式插入
  insert_with_shell "$MCP_SETTINGS_FILE"
fi

echo "✅ 已成功添加 mtbi-ai 配置到 $MCP_SETTINGS_FILE"
echo ""
echo "   重启 CatPaw 助理后配置生效。"
echo ""

exit 0
