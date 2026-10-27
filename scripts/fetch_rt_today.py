#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_rt_today.py
从 Apollo 财收分析页面抓取今日实付验证GTV和今日CPC消耗额。

正确路径（已验证 2026-03-29）：
  时间 → 按日 → 选今天日期 → 查询
  → "实时数据"区域（每半小时更新一次）
  → 组织明细表格 col1=今日实付验证GTV, col6=今日CPC消耗额

代运营商顺序（与 BOARD_DATA.ops 一致）：
  0: 惠州巨浪, 1: 惠州柏万, 2: 泉州小花猫, 3: 惠安广通,
  4: 慈溪哲光, 5: 义乌汐洋
"""
import os
import subprocess, json, re, sys, os, datetime, base64, urllib.request
from pathlib import Path

def _gh_pat():
    v = os.environ.get("GH_PAT")
    if v:
        return v
    try:
        return open("/root/.openclaw/secrets/gh_pat").read().strip()
    except Exception:
        return ""
GH_TOKEN = _gh_pat()
GH_REPO  = "huhu2u/task-canvas"

AGENT_BROWSER = "/opt/nvm/versions/node/v24.14.0/bin/agent-browser"
CANVAS_PATH   = Path("/root/.openclaw/workspace/task-canvas.html")
SESSION       = "apollo"

APOLLO_URL = (
    "https://apollo.meituan.com/crm-platform"
    "?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLXBjLWRhdGEtYnVsbGV0aW4tYm9hcmQ"
    "lMkZzdHJhdGVneS1tYW5hZ2VtZW50JTJGaW5kZXguaHRtbCUyMyUyRmRhdGEtb3ZlcnZpZXclM0Zz"
    "dHJhdGVneUlkJTNENw%253D%253D&pageId=1721888474rcncbe"
)

ORG_KEYS = {
    '惠州市巨浪': '惠州巨浪',
    '惠州市柏万': '惠州柏万',
    '泉州市小花猫': '泉州小花猫',
    '惠安广通': '惠安广通',
    '慈溪哲光': '慈溪哲光',
    '义乌市汐洋': '义乌汐洋',
}
ORDER = ['惠州巨浪', '惠州柏万', '泉州小花猫', '惠安广通', '慈溪哲光', '义乌汐洋']

def ab_eval(js, timeout=30):
    cmd = [AGENT_BROWSER, "--session", SESSION, "eval", "--stdin"]
    r = subprocess.run(cmd, input=js, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def ab_run(*args, timeout=30):
    cmd = [AGENT_BROWSER, "--session", SESSION] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def ensure_daily_today(today_str):
    """
    切换财收分析到 按日+今天 视图并点查询。
    today_str: 'YYYY-MM-DD'
    """
    import time

    # 每次都确保导航到财收分析的"业绩结果"tab
    print("  → 导航到财收分析页面...")
    cur_url = ab_run("get", "url")
    if "apollo.meituan.com" not in cur_url:
        ab_run("open", APOLLO_URL)
        ab_run("wait", "--load", "networkidle")
        time.sleep(5)

    # 点左侧菜单"财收分析"
    nav_result = ab_eval("""(function(){
      function d(doc){
        try{
          const all=doc.querySelectorAll('span,a,li,.menu-item');
          for(const el of all){
            const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('');
            if(own==='财收分析'){el.click();return 'clicked 财收分析';}
          }
          const iframes=doc.querySelectorAll('iframe');
          for(const f of iframes){try{const r=d(f.contentDocument);if(r!=='nf')return r;}catch(e){}}
        }catch(e){return 'err:'+e.message;}
        return 'nf';
      }
      return d(document);
    })()""")
    print(f"    导航结果: {nav_result}")
    time.sleep(4)

    # 点"业绩结果"tab（确保不是门店明细）
    ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const all=[...f.contentDocument.querySelectorAll('*')];
          for(const el of all){
            const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('');
            if(own==='业绩结果'){el.click();return 'clicked 业绩结果';}
          }
        }catch(e){}
      }
    })()""")
    time.sleep(2)

    # 步骤1：打开时间类型下拉，点"按日"
    print("  → 切换到按日视图...")
    # 强制显示并点击 按日 option
    r = ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const fdoc=f.contentDocument;
          // 先强制显示 select popper
          const poppers=[...fdoc.querySelectorAll('.mtd-select-popper')];
          for(const p of poppers){
            if(p.textContent.includes('按日')&&p.textContent.includes('按月')){
              p.style.cssText='display:block!important;visibility:visible!important;opacity:1!important;z-index:9999!important;';
              const items=[...p.querySelectorAll('.mtd-dropdown-menu-item')];
              const daily=items.find(i=>i.textContent.trim()==='按日');
              if(daily){
                daily.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
                daily.click();
                return 'clicked 按日';
              }
            }
          }
          // 如果popper不可见，先点input打开下拉
          const inputs=[...fdoc.querySelectorAll('input')];
          const timeInp=inputs.find(i=>i.value==='按月'||i.value==='按日'||i.placeholder==='按月'||i.placeholder==='时间类型');
          if(timeInp){
            const parent=timeInp.closest('.mtd-select,.el-select');
            if(parent){parent.click();return 'opened select';}
            timeInp.click();return 'clicked input';
          }
        }catch(e){}
      }
      return 'nf';
    })()""")
    print(f"    按日切换: {r}")

    if r == 'opened select':
        time.sleep(0.8)
        # 再次尝试点按日
        r2 = ab_eval("""(function(){
          const iframes=document.querySelectorAll('iframe');
          for(const f of iframes){
            try{
              const fdoc=f.contentDocument;
              const poppers=[...fdoc.querySelectorAll('.mtd-select-popper')];
              for(const p of poppers){
                if(p.textContent.includes('按日')){
                  p.style.cssText='display:block!important;visibility:visible!important;opacity:1!important;z-index:9999!important;';
                  const items=[...p.querySelectorAll('.mtd-dropdown-menu-item')];
                  const daily=items.find(i=>i.textContent.trim()==='按日');
                  if(daily){daily.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));daily.click();return 'clicked 按日';}
                }
              }
            }catch(e){}
          }
          return 'nf2';
        })()""")
        print(f"    按日重试: {r2}")

    time.sleep(1)

    # 步骤2：点日期输入框，打开日历，选今天
    print(f"  → 选择日期 {today_str}...")
    today_day = str(int(today_str.split('-')[2]))  # 去掉前导零

    r3 = ab_eval(f"""(function(){{
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){{
        try{{
          const fdoc=f.contentDocument;
          const inputs=[...fdoc.querySelectorAll('input')];
          // 找日期输入框（值为YYYY-MM-DD格式或placeholder=选择时间）
          const dateInp=inputs.find(i=>/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(i.value)||i.placeholder==='选择时间');
          if(dateInp){{
            dateInp.dispatchEvent(new MouseEvent('click',{{bubbles:true}}));
            dateInp.dispatchEvent(new FocusEvent('focus',{{bubbles:true}}));
            return 'opened datepicker, val='+dateInp.value;
          }}
        }}catch(e){{}}
      }}
      return 'nf';
    }})()""")
    print(f"    打开日历: {r3}")
    time.sleep(1.2)

    # 点今天的日期数字
    r4 = ab_eval(f"""(function(){{
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){{
        try{{
          const fbody=f.contentDocument.body;
          // 日历弹出层是portal渲染在body下，找mtd-popper包含日历月份的
          const bodyChildren=[...fbody.children];
          for(const child of bodyChildren){{
            const cls=(child.className||'').toString();
            const txt=child.textContent;
            if(cls.includes('mtd-popper')&&txt.includes('月')){{
              // 找所有文本为today_day的元素（用childNodes精确匹配）
              const all=[...child.querySelectorAll('*')];
              for(const el of all){{
                const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('').trim();
                if(own==='{today_day}'){{
                  el.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,cancelable:true}}));
                  el.dispatchEvent(new MouseEvent('mouseup',{{bubbles:true,cancelable:true}}));
                  el.dispatchEvent(new MouseEvent('click',{{bubbles:true,cancelable:true}}));
                  return 'clicked ' + '{today_day}' + ' tag='+el.tagName;
                }}
              }}
            }}
          }}
        }}catch(e){{return 'err:'+e.message;}}
      }}
      return 'nf';
    }})()""")
    print(f"    选日期: {r4}")
    time.sleep(1)

    # 步骤3：点查询
    print("  → 点查询...")
    r5 = ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const btns=[...f.contentDocument.querySelectorAll('button')];
          const q=btns.find(b=>b.textContent.trim()==='查询'&&b.offsetParent!==null);
          if(q){q.click();return 'clicked 查询';}
        }catch(e){}
      }
      return 'nf';
    })()""")
    print(f"    查询: {r5}")
    time.sleep(5)

def parse_daily_table():
    """
    从按日视图的组织明细表格读取各代运营商今日GTV和CPC。
    已验证列结构（按日+今天视图）：
      col0=组织名
      col1=今日实付验证GTV（剔除风控+退款）
      col6=今日CPC消耗额
    """
    js = """(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const rows=[...f.contentDocument.querySelectorAll('tbody tr')];
          if(rows.length>1){
            const result=[];
            for(const row of rows){
              const cells=[...row.querySelectorAll('td')];
              const texts=cells.map(c=>c.textContent.trim().replace(/\\s+/g,' ').substring(0,25));
              if(texts.length>2) result.push(texts);
            }
            return JSON.stringify(result.slice(0,9));
          }
        }catch(e){}
      }
      return '[]';
    })()"""
    raw = ab_eval(js, timeout=30)
    # raw is a JSON string returned as a quoted string from agent-browser
    # need to parse twice: once to get the string, once to get the array
    try:
        # agent-browser wraps JSON output in quotes, so raw = '"[[...]]"'
        inner = json.loads(raw)      # → '[[...]]'  (string)
        if isinstance(inner, str):
            rows = json.loads(inner) # → [[...]]    (list)
        else:
            rows = inner
    except Exception as e:
        print(f"  ⚠️  JSON解析失败: {e}, raw={raw[:200]}")
        return {}, {}

    gtv_today = {}
    cpc_today = {}

    def parse_num(s):
        s = str(s).replace(',', '').strip()
        if not s or s == '-':
            return 0
        try:
            return round(float(s))
        except:
            return 0

    for row in rows:
        if not row or len(row) < 7:
            continue
        org_raw = row[0].strip()
        matched = None
        for key, name in ORG_KEYS.items():
            if key in org_raw:
                matched = name
                break
        if not matched:
            continue

        # col1=今日实付验证GTV, col6=今日CPC消耗额（按日视图已验证）
        gtv_val = parse_num(row[1]) if len(row) > 1 else 0
        cpc_val = parse_num(row[6]) if len(row) > 6 else 0

        gtv_today[matched] = gtv_val
        cpc_today[matched] = cpc_val
        print(f"  {matched}: GTV={gtv_val:,}, CPC={cpc_val:,}")

    return gtv_today, cpc_today

def main():
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M")
    today_str = now.strftime("%Y-%m-%d")
    print(f"[fetch_rt_today] 开始抓取 {time_str}")

    # 1. 切换到按日+今天视图
    ensure_daily_today(today_str)

    # 2. 解析表格
    print("  → 解析表格数据...")
    gtv_today, cpc_today = parse_daily_table()

    # 3. 按ops顺序排列
    gtv_list = [gtv_today.get(org, 0) for org in ORDER]
    cpc_list = [cpc_today.get(org, 0) for org in ORDER]

    print(f"\n  GTV: {gtv_list}")
    print(f"  CPC: {cpc_list}")

    if all(v == 0 for v in gtv_list):
        print("  ⚠️  GTV全为0，数据抓取失败，放弃更新")
        sys.exit(1)

    # 4. 更新 task-canvas.html 中的 RT_TODAY
    html = CANVAS_PATH.read_text(encoding='utf-8')

    gtv_str = ', '.join(str(v) for v in gtv_list)
    cpc_str = ', '.join(str(v) for v in cpc_list)

    new_rt = f"""// 数据来源：Apollo财收分析 - 今日实付验证GTV
const RT_TODAY = {{
  time: '{time_str}',
  // [代运营商, GTV今日, CPC今日]  — 与 BOARD_DATA.ops 顺序对应
  gtv:  [{gtv_str}],
  cpc:  [{cpc_str}],
}};"""

    pattern = re.compile(
        r'// 数据来源：Apollo财收分析 - 今日实付验证GTV\nconst RT_TODAY = \{.*?\};',
        re.DOTALL
    )
    count = len(pattern.findall(html))
    html_new = pattern.sub(new_rt, html)
    print(f"  → 替换 RT_TODAY x{count}")

    CANVAS_PATH.write_text(html_new, encoding='utf-8')

    # 5. 推送 GitHub
    print("  → 推送GitHub...")
    _push_via_api(html_new, time_str)

    print(f"\n✅ 完成！GTV={gtv_list}, CPC={cpc_list}")
    return gtv_list, cpc_list

def _push_via_api(content, time_str):
    api_base = f"https://api.github.com/repos/{GH_REPO}/contents/index.html"
    headers = {
        'Authorization': f'token {GH_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    req = urllib.request.Request(api_base, headers=headers)
    resp = urllib.request.urlopen(req, timeout=30)
    sha = json.loads(resp.read())['sha']

    encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
    data = json.dumps({
        'message': f'auto: update RT_TODAY {time_str}',
        'content': encoded,
        'sha': sha
    }).encode('utf-8')

    req2 = urllib.request.Request(api_base, data=data, method='PUT', headers={
        **headers, 'Content-Type': 'application/json'
    })
    urllib.request.urlopen(req2, timeout=30)
    print(f"  ✅ GitHub API推送成功")

if __name__ == '__main__':
    main()
