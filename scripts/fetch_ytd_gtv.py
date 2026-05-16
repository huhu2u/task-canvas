#!/usr/bin/env python3
"""
单独抓取昨日GTV，只更新finance_data.json里的gtv_y字段
通过agent-browser apollo session读取财收分析页
"""
import subprocess, json, time, re
from datetime import datetime, timedelta, date
from pathlib import Path

AGENT_BROWSER = "/opt/nvm/versions/node/v24.14.0/bin/agent-browser"
SESSION = "apollo"
DATA_OUT = Path("/root/.openclaw/workspace/data/finance_data.json")

def ab_eval(js, timeout=30):
    cmd = [AGENT_BROWSER, "--session", SESSION, "eval", "--stdin"]
    r = subprocess.run(cmd, input=js, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def ab_navigate(url, timeout=30):
    cmd = [AGENT_BROWSER, "--session", SESSION, "navigate", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def parse_num(val):
    if not val: return 0
    val = str(val).replace(',', '').replace('%', '').strip()
    try: return float(val)
    except: return 0

ORG_KEYS = {
    '惠州市巨浪': '惠州巨浪',
    '惠州市柏万': '惠州柏万',
    '泉州市小花猫': '泉州小花猫',
    '惠安县广通': '惠安广通',
    '慈溪市哲光': '慈溪哲光',
    '义乌市汐洋': '义乌汐洋',
}

yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"[fetch_ytd_gtv] 抓取 {yesterday} 各家GTV...")

# 导航到财收分析页
FINANCE_URL = (
    "https://apollo.meituan.com/crm-platform"
    "?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLXBjLWRhdGEtYnVsbGV0aW4tYm9hcmQ"
    "lMkZwZXJmb3JtYW5jZS1ib2FyZCUyRmluZGV4Lmh0bWwlMjMlMkZvcGVyYXRlU3RhdHVzJTJGYWRk"
    "&pageId=16971780020yjlco"
)
r = ab_navigate(FINANCE_URL, timeout=30)
print(f"  导航: {r}")
time.sleep(6)

# 点"财收分析"菜单
r = ab_eval("""(function(){
  const iframes = document.querySelectorAll('iframe');
  for(const f of iframes) {
    try {
      const els = f.contentDocument.querySelectorAll('li, .menu-item, [class*=menu]');
      for(const el of els) {
        const own = el.textContent.trim();
        if(own === '财收分析'){el.click();return 'ok';}
      }
    } catch(e) {}
  }
  return 'nf';
})()""", timeout=15)
print(f"  财收分析菜单: {r}")
time.sleep(4)

# 切换到"按日"并选昨日
r = ab_eval(f"""(function(){{
  const iframes = document.querySelectorAll('iframe');
  for(const f of iframes) {{
    try {{
      // 点按日tab
      const tabs = f.contentDocument.querySelectorAll('.mtd-tabs-tab,[role=tab]');
      for(const t of tabs) {{ if(t.textContent.includes('按日')){{ t.click(); break; }} }}
      return 'tabs_clicked';
    }} catch(e) {{ return String(e); }}
  }}
  return 'nf';
}})()""", timeout=15)
print(f"  按日tab: {r}")
time.sleep(2)

r = ab_eval(f"""(function(){{
  const target = '{yesterday}';
  const iframes = document.querySelectorAll('iframe');
  for(const f of iframes) {{
    try {{
      // 找日期选择器并设置昨日
      const inputs = f.contentDocument.querySelectorAll('input[type=text],.mtd-input');
      for(const inp of inputs) {{
        if(inp.value && /\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(inp.value)) {{
          inp.value = target;
          inp.dispatchEvent(new Event('input', {{bubbles:true}}));
          inp.dispatchEvent(new Event('change', {{bubbles:true}}));
        }}
      }}
      // 点查询按钮
      const btns = f.contentDocument.querySelectorAll('button,.mtd-btn');
      for(const b of btns) {{ if(b.textContent.includes('查询')){{ b.click(); return 'query_clicked'; }} }}
      return 'no_query_btn';
    }} catch(e) {{ return String(e); }}
  }}
  return 'nf';
}})()""", timeout=15)
print(f"  日期设置: {r}")
time.sleep(5)

# 读取表格数据
raw = ab_eval("""(function(){
  const iframes = document.querySelectorAll('iframe');
  for(const f of iframes) {
    try {
      const rows = [...f.contentDocument.querySelectorAll('tbody tr')];
      if(rows.length >= 4) {
        return JSON.stringify(rows.slice(0,10).map(r => {
          const cells = [...r.querySelectorAll('td')];
          const tv = (i) => cells[i]?.textContent.trim().split('\\n')[0] || '';
          return {org: tv(0), col6: tv(6), col7: tv(7), all: cells.map((_,i)=>tv(i)).join('|')};
        }));
      }
    } catch(e) {}
  }
  return '[]';
})()""", timeout=20)

ytd_map = {}
try:
    rows = json.loads(raw.strip('"').replace('\\"','"')) if raw.startswith('"') else json.loads(raw)
    for row in rows:
        org = row.get('org','')
        for key, name in ORG_KEYS.items():
            if key in org:
                # 遍历所有列找GTV口径（实付验证GTV）
                all_cols = row.get('all','').split('|')
                # col6或col7通常是昨日GTV
                for ci in [6, 7, 5, 8]:
                    val = float(all_cols[ci].replace(',','')) if ci < len(all_cols) and all_cols[ci].replace(',','').replace('.','').isdigit() else 0
                    if 10000 < val < 500000:
                        ytd_map[name] = int(val)
                        print(f"  昨日GTV {name}: {int(val):,} (col{ci})")
                        break
except Exception as e:
    print(f"  解析失败: {e}, raw={raw[:200]}")

if not ytd_map:
    print("  ⚠️ 未抓到昨日GTV，保留原值")
else:
    # 更新finance_data.json
    d = json.loads(DATA_OUT.read_text())
    for op in d['ops']:
        if op['name'] in ytd_map:
            op['gtv_y'] = ytd_map[op['name']]
    DATA_OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    print(f"✅ 昨日GTV已写入 {DATA_OUT}")

