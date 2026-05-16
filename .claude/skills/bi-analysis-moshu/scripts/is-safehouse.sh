#!/bin/bash
# ─────────────────────────────────────────────────────────
#  is-safehouse.sh — 检测会话是否处于安全屋模式
#
#  用法:
#    ./is-safehouse.sh                # UI 当前显示的会话
#    ./is-safehouse.sh <session-id>   # 指定会话
#    ./is-safehouse.sh --all          # 列出所有会话的安全屋状态
#
#  判断逻辑（优先级从高到低）:
#    1. 传了 session-id  → 查那个会话
#    2. 没传参数          → uiGetCurrentSessionId()
#                           即 UI 侧边栏高亮的那个会话
#
#  退出码:  0 = 安全屋   1 = 普通模式   2 = 检测失败
# ─────────────────────────────────────────────────────────

PORT_FILE="$HOME/Library/Application Support/catpaw-desk/DevToolsActivePort"

G='\033[32m' Y='\033[33m' B='\033[1m' D='\033[2m' R='\033[0m'

port=$(head -1 "$PORT_FILE" 2>/dev/null | tr -d '[:space:]')
[ -z "$port" ] && { echo -e "${Y}⚠ CatPaw Desk 未运行${R}"; exit 2; }

ws_url=$(curl -s "http://127.0.0.1:${port}/json/list" 2>/dev/null \
  | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    if p.get('type')=='page' and 'Desk' in p.get('title',''):
        print(p['webSocketDebuggerUrl']); break
" 2>/dev/null)
[ -z "$ws_url" ] && { echo -e "${Y}⚠ 找不到页面${R}"; exit 2; }

# ── CDP 执行器 ────────────────────────────────────────────
cdp_eval() {
  node -e "
    const ws = new WebSocket('${ws_url}');
    let seq=1, done=false;
    setTimeout(()=>{if(!done)process.exit(2)},5000);
    ws.onopen=()=>{
      ws.send(JSON.stringify({id:seq++,method:'Runtime.enable'}));
      ws.send(JSON.stringify({id:seq++,method:'Runtime.evaluate',params:{
        returnByValue:true, awaitPromise:true,
        expression:\`$1\`
      }}));
    };
    ws.onmessage=(ev)=>{
      const m=JSON.parse(ev.data);
      if(m.id===2){done=true;console.log(m.result?.result?.value??'');ws.close();}
    };
  " 2>/dev/null
}

# ── --all 模式：列出所有会话 ──────────────────────────────
if [ "${1:-}" = "--all" ] || [ "${1:-}" = "-a" ]; then
  result=$(cdp_eval '
    (async function(){
      const api = window.electronAPI;
      const [sessions, currentId] = await Promise.all([
        api.getSessions(),
        api.uiGetCurrentSessionId()
      ]);
      return JSON.stringify(sessions.map(s => ({
        id: s.id,
        name: (s.title || s.name || "").slice(0,40),
        sandbox: !!(s.enableSafeHouse ?? s.sandboxMode),
        status: s.status,
        current: s.id === currentId
      })));
    })()
  ')
  echo ""
  echo "$result" | python3 -c "
import sys, json
sessions = json.load(sys.stdin)
safe = sum(1 for s in sessions if s['sandbox'])
print(f'  共 {len(sessions)} 个会话，{safe} 个安全屋\n')
for s in sessions:
    icon = '🛡' if s['sandbox'] else ' ○'
    cur = ' ◀' if s['current'] else ''
    name = s['name'] or '(未命名)'
    status = s['status']
    print(f'  {icon}  {name[:36]:<36}  {status:<8}{cur}')
print()
" 2>/dev/null
  exit 0
fi

# ── 单会话检测 ────────────────────────────────────────────
TARGET_ID="${1:-}"

result=$(cdp_eval "
  (async function(){
    const api = window.electronAPI;
    if(!api) return JSON.stringify({error:'no electronAPI'});

    const [sessions, uiCurrentId] = await Promise.all([
      api.getSessions(),
      api.uiGetCurrentSessionId()
    ]);

    const targetId = '${TARGET_ID}' || uiCurrentId;
    const target = sessions.find(s => s.id === targetId);

    if(!target) return JSON.stringify({error:'session not found: ' + targetId});

    const isUiCurrent = target.id === uiCurrentId;

    return JSON.stringify({
      id: target.id,
      name: (target.title || target.name || '').slice(0,50),
      sandboxMode: !!(target.enableSafeHouse ?? target.sandboxMode),
      status: target.status,
      isUiCurrent,
      total: sessions.length,
      safehouseCount: sessions.filter(s => s.enableSafeHouse ?? s.sandboxMode).length
    });
  })()
")

[ -z "$result" ] && { echo -e "${Y}⚠ 读取失败${R}"; exit 2; }

read_field() { echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

sandbox=$(read_field sandboxMode)
name=$(read_field name)
total=$(read_field total)
safe_count=$(read_field safehouseCount)
is_current=$(read_field isUiCurrent)
error=$(read_field error)

[ -n "$error" ] && [ "$error" != "" ] && { echo -e "${Y}⚠ $error${R}"; exit 2; }

label=""
if [ "$is_current" = "True" ]; then
  label="${D}（UI 当前显示）${R}"
fi

if [ "$sandbox" = "True" ]; then
  echo -e "${G}🛡${R}  安全屋: ${B}ON${R}  ${D}公司自部署模型 · 对话不出域${R}"
  [ -n "$name" ] && echo -e "   ${D}会话: ${name}${R} $label"
  echo -e "   ${D}${safe_count}/${total} 个会话为安全屋模式${R}"
  exit 0
else
  echo -e "○  安全屋: ${B}OFF${R}"
  [ -n "$name" ] && echo -e "   ${D}会话: ${name}${R} $label"
  echo -e "   ${D}${safe_count}/${total} 个会话为安全屋模式${R}"
  exit 1
fi
