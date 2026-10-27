#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_finance_data.py
从 Apollo 业绩看板-奖金指标-表格视图 抓取各代运营商财收指标：
  col0=组织名称, col1=MEM收款额, col13=CPC&QCPS消耗额（不含区县）
  col15=实付验证GTV, col16=交易收入（剔除风控+退款）, col18=GTV剔除率%
  注意：汇总数据从子行累加，不读胡英杰汇总行（td index错位）

操作流程：
  1. 打开业绩看板页面
  2. 点"奖金指标"tab
  3. 点"切换表格视图"
  4. 展开"高线粤闽浙城市群(胡英杰)"行
  5. 读取各代运营商分项数据（7行）
"""

import os
import subprocess, json, re, sys, os, datetime, base64, urllib.request, time
from pathlib import Path

def _gh_pat():
    v = os.environ.get("GH_PAT")
    if v:
        return v
    try:
        return open("/root/.openclaw/secrets/gh_pat").read().strip()
    except Exception:
        return ""
GH_TOKEN   = _gh_pat()
GH_REPO    = "huhu2u/task-canvas"
AGENT_BROWSER = "/opt/nvm/versions/node/v24.14.0/bin/agent-browser"
CANVAS_PATH   = Path("/root/.openclaw/workspace/task-canvas.html")
SESSION       = "apollo"
WORKSPACE     = Path("/root/.openclaw/workspace")
DATA_OUT      = WORKSPACE / "data" / "finance_data.json"

APOLLO_URL = (
    "https://apollo.meituan.com/crm-platform"
    "?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLWRhdGEtYnVsbGV0aW4tYm9hcmQ"
    "lMkZwZXJmb3JtYW5jZS1ib2FyZCUyRmluZGV4Lmh0bWwlMjMlMkZvcGVyYXRlU3RhdHVzJTJGYWRk"
    "&pageId=16971780020yjlco"
)

# 组织名匹配 → 显示名
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


def parse_num(s):
    s = str(s).replace(',', '').replace('%', '').strip()
    try: return float(s)
    except: return 0.0


def fetch_finance_by_agency():
    """
    从奖金指标表格视图读各代运营商财收指标（月度累计）
    返回 list[dict] 按 ORDER 排序
    """
    print("=== fetch_finance_data.py ===")
    print(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 导航到业绩看板卡片视图，先抓城市群汇总
    print("→ 导航到业绩看板卡片视图，抓城市群汇总...")
    ab_run("open", APOLLO_URL)
    time.sleep(8)

    card_summary = {}
    card_raw = ab_eval("""(function(){
      const iframe = document.querySelector('iframe');
      if(!iframe || !iframe.contentDocument) return '{}';
      const doc = iframe.contentDocument;
      const body = doc.body?.innerText || '';
      const extractNum = (keyword) => {
        const idx = body.indexOf(keyword);
        if(idx < 0) return null;
        const after = body.substring(idx + keyword.length, idx + keyword.length + 30);
        const m = after.match(/[\\d,]+/);
        return m ? m[0].replace(/,/g,'') : null;
      };
      const extractPct = (keyword) => {
        const idx = body.indexOf(keyword);
        if(idx < 0) return null;
        const after = body.substring(idx, idx+80);
        const m = after.match(/([\\d.]+)%/);
        return m ? m[1] : null;
      };
      return JSON.stringify({
        gtv:      extractNum('中小发_代运营高线城市_实付验证GTV（剔除风控+退款）\\n'),
        cpc_qcps: extractNum('中小发_代运营_CPC&QCPS消耗额（不含区县）\\n'),
        gtv_excl: extractPct('中小发_代运营_高线城市GTV剔除率'),
        cpc_new:  extractNum('中小发_代运营_CPC有效新签门店数\\n'),
      });
    })()""", timeout=15)
    try:
        _cd = card_raw
        if isinstance(_cd, str):
            _cd = json.loads(_cd)
        if isinstance(_cd, str):  # 双重嵌套时再解一次
            _cd = json.loads(_cd)
        if _cd and _cd.get('gtv'):
            card_summary = {
                'gtv_m':  int(_cd['gtv']),
                'cpc_m':  int(_cd.get('cpc_qcps') or 0),
                'excl_r': float(_cd.get('gtv_excl') or 0),
                'cpc_new': int(_cd.get('cpc_new') or 0),
            }
            print(f"✅ 卡片视图汇总: GTV={card_summary['gtv_m']:,}, CPC={card_summary['cpc_m']:,}, 剔除率={card_summary['excl_r']}%")
        else:
            print(f"⚠️ 卡片视图抓取失败: {card_raw}")
    except Exception as e:
        print(f"⚠️ 卡片视图解析异常: {e}")

    # 2a. 点"全部指标"按钮（从卡片视图切换到全部指标视图）
    r0 = ab_eval("""(function(){
      const iframes = document.querySelectorAll('iframe');
      for (const f of iframes) {
        try {
          const btns = [...f.contentDocument.querySelectorAll('button')];
          const btn = btns.find(b => b.textContent.trim() === '全部指标');
          if (btn) { btn.click(); return 'ok'; }
        } catch(e) {}
      }
      return 'nf';
    })()""", timeout=15)
    print(f"全部指标按钮: {r0}")
    time.sleep(4)

    # 2b. 点奖金指标 tab
    r = ab_eval("""(function(){
      const iframes = document.querySelectorAll('iframe');
      for (const f of iframes) {
        try {
          const all = [...f.contentDocument.querySelectorAll('*')];
          for (const el of all) {
            const own = Array.from(el.childNodes)
              .filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('');
            if (own === '奖金指标') { el.click(); return 'ok'; }
          }
        } catch(e) {}
      }
      return 'nf';
    })()""", timeout=15)
    print(f"奖金指标tab: {r}")
    time.sleep(2)

    # 3. 切换表格视图
    r2 = ab_eval("""(function(){
      const iframes = document.querySelectorAll('iframe');
      for (const f of iframes) {
        try {
          const btns = [...f.contentDocument.querySelectorAll('button.mtd-btn,button')];
          // 如果已在表格视图，按钮文字是"切换卡片视图"；若在卡片视图则是"切换表格视图"
          const btn = btns.find(b => b.textContent.includes('切换表格视图'));
          if (btn) { btn.click(); return 'ok'; }
          const alreadyTable = btns.find(b => b.textContent.includes('切换卡片视图'));
          if (alreadyTable) { return 'already_table'; }
        } catch(e) {}
      }
      return 'nf';
    })()""", timeout=15)
    print(f"切换表格视图: {r2}")
    if r2 not in ('ok', 'already_table'):
        print("⚠️ 切换表格视图失败，尝试继续...")
    time.sleep(6)  # 表格视图渲染需要更长时间

    # 4. 展开胡英杰行
    r3 = ab_eval("""(function(){
      const iframes = document.querySelectorAll('iframe');
      for (const f of iframes) {
        try {
          const rows = [...f.contentDocument.querySelectorAll('tbody tr')];
          for (const row of rows) {
            if (row.textContent.includes('胡英杰')) {
              const icon = row.querySelector('.mtd-table-tree-expand-icon');
              if (icon) { icon.click(); return 'ok'; }
            }
          }
        } catch(e) {}
      }
      return 'nf';
    })()""", timeout=15)
    print(f"展开胡英杰行: {r3}")
    time.sleep(4)

    # 5. 读取数据
    raw = ab_eval("""(function(){
      const iframes = document.querySelectorAll('iframe');
      for (const f of iframes) {
        try {
          const rows = [...f.contentDocument.querySelectorAll('tbody tr')];
          if (rows.length >= 8) {
            // 列定位策略（2026-04-06更新）：全部改为固定列索引
            // col1=MEM收款额, col2=MEM续约率-全产品, col5=MEM续约率-付费版（正确口径）
            return JSON.stringify(rows.slice(0,9).map(r => {
              const cells = [...r.querySelectorAll('td')];
              const tv = (i) => cells[i]?.textContent.trim().split('\\n')[0].split(' ')[0] || '';
              return {
                org:     tv(0),
                mem:     tv(1),   // MEM收款额，col1
                renewal: tv(5),   // MEM续约率（付费版）col5，2026-04-06英杰确认
                new_sgn: tv(10),  // col10=CPC有效新签
                cpc:     tv(12),  // col12=CPC&QCPS消耗额（不含区县）
                wpu:     tv(13),  // col13=旺铺通消耗额
                gtv:     tv(14),  // col14=中小发_代运营高线城市_实付验证GTV（剔除风控+退款）← 正确月GTV
                cps:     tv(15),  // col15=中小发代运营高线城市_交易收入（剔除风控+退款）= CPS收入
                excl:    tv(17),  // col17=GTV剔除率
              };
            }));
          }
        } catch(e) {}
      }
      return '[]';
    })()""", timeout=20)

    try:
        inner = json.loads(raw)
        rows_data = json.loads(inner) if isinstance(inner, str) else inner
    except Exception as e:
        print(f"⚠️ JSON解析失败: {e}")
        rows_data = []

    # 解析结果
    summary = {}   # 城市群汇总
    by_op = {}     # 各代运营商

    for row in rows_data:
        org = row.get('org', '')
        mem     = parse_num(row.get('mem', '0'))
        cpc     = parse_num(row.get('cpc', '0'))      # 月CPC&QCPS消耗额
        gtv     = parse_num(row.get('gtv', '0'))      # 月GTV（实付验证）
        cps     = parse_num(row.get('cps', '0'))      # 月CPS交易收入（剔除风控+退款）
        excl    = parse_num(row.get('excl', '0').replace('%',''))  # GTV剔除率%
        renewal = parse_num(row.get('renewal', '0').replace('%',''))  # MEM续约率%
        new_sgn = int(parse_num(row.get('new_sgn', '0')))  # CPC有效新签
        wpu     = parse_num(row.get('wpu', '0'))       # 旺铺通消耗额

        if '胡英杰' in org:
            # 胡英杰汇总行的td index与子行不同，跳过，改用子行累加
            pass
        else:
            # 匹配代运营商名
            for key, name in ORG_KEYS.items():
                if key in org:
                    fee_rate = round(cps / gtv * 100, 4) if gtv > 0 else 0
                    by_op[name] = {
                        'name':    name,
                        'mem':     mem,
                        'cpc':     cpc,
                        'gtv':     gtv,
                        'gtv_y':   0,   # 昨日GTV需从/add页面单独抓取，此处占位
                        'excl':    excl,
                        'renewal': renewal,
                        'new_sgn': new_sgn,
                        'wpu':     wpu,
                        'cps':     cps,  # col16=交易收入（剔除风控+退款）
                        'fee_rate': fee_rate,
                    }
                    print(f"  {name}: GTV={gtv:,.0f}, CPS={cps:,.0f}, CPC={cpc:,.0f}, MEM={mem:,.0f}, 剔除率={excl}%, 续约率={renewal}%, 新签={new_sgn}, 旺铺通={wpu:,.0f}")
                    break

    # 从子行累加得到城市群汇总（仅用于兜底和各家分项）
    if by_op and not summary:
        total_mem = sum(v['mem'] for v in by_op.values())
        total_cpc = sum(v['cpc'] for v in by_op.values())
        total_gtv = sum(v['gtv'] for v in by_op.values())
        # 剔除率用GTV加权平均
        weighted_excl = 0.0
        if total_gtv > 0:
            for v in by_op.values():
                if v['gtv'] > 0:
                    weighted_excl += v['excl'] * v['gtv']
            weighted_excl = weighted_excl / total_gtv
        total_cps = sum(v['cps'] for v in by_op.values())
        total_fee_rate = round(total_cps / total_gtv * 100, 4) if total_gtv > 0 else 0
        summary = {
            'mem_m':    total_mem,
            'cpc_m':    total_cpc,
            'gtv_m':    total_gtv,
            'cps_m':    total_cps,
            'fee_rate': total_fee_rate,
            'excl_r':   round(weighted_excl, 2),
        }
        print(f"\n城市群汇总(子行累加): CPC={total_cpc:,.0f}, CPS={total_cps:,.0f}, GTV={total_gtv:,.0f}, MEM={total_mem:,.0f}, 费率={total_fee_rate:.2f}%, 剔除率={weighted_excl:.2f}%")

    # ── 用开始时抓到的卡片视图汇总（官方口径）覆盖子行累加值 ──
    if card_summary and card_summary.get('gtv_m'):
        summary['gtv_m']  = card_summary['gtv_m']
        summary['cpc_m']  = card_summary['cpc_m']
        summary['excl_r'] = card_summary['excl_r']
        print(f"\n✅ 已用卡片视图官方汇总覆盖: GTV={summary['gtv_m']:,}, CPC={summary['cpc_m']:,}, 剔除率={summary['excl_r']}%")
    else:
        print("\n⚠️ 卡片视图汇总不可用，使用子行累加值")

    # ── 抓昨日GTV：跳转财收分析页，自定义日期选昨日，读实付验证GTV列 ──
    yesterday_str = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_day = str(int(yesterday_str.split('-')[2]))  # 去前导零，如"02"→"2"
    FINANCE_URL = (
        "https://apollo.meituan.com/crm-platform"
        "?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLXBjLWRhdGEtYnVsbGV0aW4tYm9hcmQ"
        "lMkZzdHJhdGVneS1tYW5hZ2VtZW50JTJGaW5kZXguaHRtbCUyMyUyRmRhdGEtb3ZlcnZpZXclM0Zz"
        "dHJhdGVneUlkJTNENw%253D%253D&pageId=1721888474rcncbe"
    )
    print(f"\n→ 抓昨日({yesterday_str})GTV：跳转财收分析...")
    ab_run("open", FINANCE_URL)
    ab_run("wait", "--load", "networkidle")
    time.sleep(6)

    # 点左侧"财收分析"菜单（有时已在该页面）
    ab_eval("""(function(){
      function d(doc){
        try{
          const all=doc.querySelectorAll('span,a,li,.menu-item');
          for(const el of all){
            const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('');
            if(own==='财收分析'){el.click();return 'ok';}
          }
          for(const f of doc.querySelectorAll('iframe')){try{const r=d(f.contentDocument);if(r==='ok')return r;}catch(e){}}
        }catch(e){}
        return 'nf';
      }
      return d(document);
    })()""")
    time.sleep(3)

    # 切换"按日"时间类型
    ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const fdoc=f.contentDocument;
          // 先强制弹出下拉
          const inp=Array.from(fdoc.querySelectorAll('input')).find(i=>i.value==='按月'||i.value==='按日'||i.placeholder==='时间类型');
          if(inp){
            const parent=inp.closest('.mtd-select,.el-select');
            if(parent) parent.click(); else inp.click();
          }
        }catch(e){}
      }
    })()""")
    time.sleep(0.8)
    ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const fdoc=f.contentDocument;
          const poppers=[...fdoc.querySelectorAll('.mtd-select-popper')];
          for(const p of poppers){
            if(p.textContent.includes('按日')){
              p.style.cssText='display:block!important;visibility:visible!important;opacity:1!important;z-index:9999!important;';
              const item=[...p.querySelectorAll('.mtd-dropdown-menu-item')].find(i=>i.textContent.trim()==='按日');
              if(item){item.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));item.click();return 'ok';}
            }
          }
        }catch(e){}
      }
    })()""")
    time.sleep(1)

    # 打开日期选择器，选昨日
    ab_eval(f"""(function(){{
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){{
        try{{
          const fdoc=f.contentDocument;
          const inp=[...fdoc.querySelectorAll('input')].find(i=>/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(i.value)||i.placeholder==='选择时间');
          if(inp){{inp.dispatchEvent(new MouseEvent('click',{{bubbles:true}}));inp.dispatchEvent(new FocusEvent('focus',{{bubbles:true}}));return;}}
        }}catch(e){{}}
      }}
    }})()""")
    time.sleep(1.2)

    ab_eval(f"""(function(){{
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){{
        try{{
          const fbody=f.contentDocument.body;
          for(const child of [...fbody.children]){{
            const cls=(child.className||'').toString();
            if(cls.includes('mtd-popper')&&child.textContent.includes('月')){{
              const all=[...child.querySelectorAll('*')];
              for(const el of all){{
                const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('').trim();
                if(own==='{yesterday_day}'){{
                  el.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,cancelable:true}}));
                  el.dispatchEvent(new MouseEvent('click',{{bubbles:true,cancelable:true}}));
                  return;
                }}
              }}
            }}
          }}
        }}catch(e){{}}
      }}
    }})()""")
    time.sleep(1)

    # 点查询
    ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const btn=[...f.contentDocument.querySelectorAll('button')].find(b=>b.textContent.trim()==='查询'&&b.offsetParent!==null);
          if(btn){btn.click();return;}
        }catch(e){}
      }
    })()""")
    time.sleep(5)

    # 读取昨日GTV
    raw_yday = ab_eval("""(function(){
      const iframes=document.querySelectorAll('iframe');
      for(const f of iframes){
        try{
          const rows=[...f.contentDocument.querySelectorAll('tbody tr')];
          if(rows.length<2) continue;
          const result=[];
          for(const r of rows){
            const cells=[...r.querySelectorAll('td')].map(td=>td.textContent.trim().split('\\n')[0]);
            // col0=组织名, col7=实付验证GTV(剔除风控+退款)
            if(cells.length>7) result.push({org:cells[0], gtv_y: cells[7]});
          }
          if(result.length>1) return JSON.stringify(result);
        }catch(e){}
      }
      return '[]';
    })()""", timeout=20)

    try:
        inner = json.loads(raw_yday)
        yday_rows = json.loads(inner) if isinstance(inner, str) else inner
    except Exception:
        yday_rows = []

    def parse_num_simple(s):
        try: return round(float(str(s).replace(',','').strip()))
        except: return 0

    for row in yday_rows:
        org = row.get('org', '')
        gtv_y = parse_num_simple(row.get('gtv_y', '0'))
        for key, name in ORG_KEYS.items():
            if key in org and name in by_op:
                by_op[name]['gtv_y'] = gtv_y
                print(f"  昨日GTV {name}: {gtv_y:,}")
                break

    print(f"✅ 昨日GTV抓取完成")

    # 按 ORDER 排序
    ops_list = [by_op.get(op, {'name': op, 'mem': 0, 'cpc': 0, 'gtv': 0, 'gtv_y': 0,
                               'cps': 0, 'excl': 0, 'fee_rate': 0, 'renewal': 0,
                               'new_sgn': 0, 'wpu': 0}) for op in ORDER]
    return summary, ops_list


def update_canvas(summary, ops_list):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    fc_data = {
        'time':     now_str,
        'cps_m':    summary.get('cps_m', 0),
        'cpc_m':    summary.get('cpc_m', 0),
        'mem_m':    summary.get('mem_m', 0),
        'gtv_m':    summary.get('gtv_m', 0),
        'excl_r':   summary.get('excl_r', 0),
        'fee_rate': summary.get('fee_rate', 0),
        'ops':      ops_list,
    }

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_OUT, 'w', encoding='utf-8') as f:
        json.dump(fc_data, f, ensure_ascii=False, indent=2)
    print(f"\n→ 数据已存: {DATA_OUT}")

    html = CANVAS_PATH.read_text(encoding='utf-8')
    new_block = f"const FC_DATA = {json.dumps(fc_data, ensure_ascii=False)};"
    if 'const FC_DATA' in html:
        html = re.sub(r'const FC_DATA\s*=\s*\{[^;]*\};', new_block, html, flags=re.DOTALL)
    else:
        html = html.replace('const BOARD_DATA', new_block + '\nconst BOARD_DATA', 1)

    # 同步更新业绩进度表的 ops 数组（月GTV/CPC/MEM/剔除率）
    TARGET = {"惠州巨浪":3566000,"惠州柏万":3050000,"泉州小花猫":2809000,"惠安广通":2252000,"慈溪哲光":3537862,"义乌汐洋":3422691}
    CPC_T  = {"惠州巨浪":53400,"惠州柏万":80300,"泉州小花猫":112300,"惠安广通":46600,"慈溪哲光":143644,"义乌汐洋":129864}
    OWNERS = {"惠州巨浪":"肖立铭","惠州柏万":"林启梁","泉州小花猫":"康子诚","惠安广通":"尤云生","慈溪哲光":"贾凌姗","义乌汐洋":"陈铨"}
    ops_by_name = {o['name']: o for o in ops_list}
    updated_count = 0
    for name, owner in OWNERS.items():
        o = ops_by_name.get(name)
        if not o:
            continue
        gtv_m  = int(o['gtv'])
        gtv_y  = int(o.get('gtv_y', 0))   # 昨日GTV
        cpc_m  = int(o['cpc'])
        mem_m  = int(o['mem'])
        excl   = o['excl'] / 100.0
        # 格式: ['名称', '负责人', gtv_m, gtv_t, gtv_y, excl, cpc_m, cpc_t, cpc_y, new_done, new_tgt, wpu, mem_m, renewal, mom, wpu_y]
        # group(1)=开头含名称负责人, group(2)=gtv_m, group(3)=,gtv_t,, group(4)=gtv_y,
        # group(5)=,, group(6)=excl, group(7)=,, group(8)=cpc_m, group(9)=,cpc_t,cpc_y,new_done,new_tgt,wpu,
        # group(10)=mem_m, group(11)=,, group(12)=尾部含renewal/mom等,]
        row_pat = re.compile(
            r"(\['" + re.escape(name) + r"',\s*'" + re.escape(owner) + r"',\s*)"
            r"(\d+)"                          # gtv_m (2)
            r"(,\s*\d+,\s*)"                  # ,gtv_t, (3)
            r"(\d+)"                          # gtv_y (4)
            r"(,\s*)"                         # , (5)
            r"([\d.]+)"                       # excl (6)
            r"(,\s*)"                         # , (7)
            r"(\d+)"                          # cpc_m (8)
            r"(,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*)"  # ,cpc_t,cpc_y,new_done,new_tgt,wpu, (9)
            r"(\d+)"                          # mem_m (10)
            r"(,.*?\])"                       # 尾部 (11)
        )
        def _rep(m, gv=gtv_m, gy=gtv_y, cv=cpc_m, mv=mem_m, ev=excl):
            return (m.group(1)+str(gv)+m.group(3)+str(gy)+m.group(5)+
                    f"{ev:.4f}"+m.group(7)+str(cv)+m.group(9)+
                    str(mv)+m.group(11))
        html, n = row_pat.subn(_rep, html)
        if n > 0:
            updated_count += 1
    html = re.sub(r'// 数据更新：[\d\-: ]+', f"// 数据更新：{now_str}", html)
    print(f"→ 业绩进度表 ops 已同步 {updated_count}/7 家")

    CANVAS_PATH.write_text(html, encoding='utf-8')
    print(f"→ task-canvas.html FC_DATA 已更新")

    # ── 写入后校验：检查BOARD_DATA里gtv_m是否合理（应≥wpu，且不能是wpu的值） ──
    verify_html = CANVAS_PATH.read_text(encoding='utf-8')
    verify_errors = []
    for name, owner in OWNERS.items():
        o = ops_by_name.get(name)
        if not o:
            continue
        expected_gtv = int(o['gtv'])
        wpu_val = int(o.get('wpu', 0))
        # 从html里读取写入后的gtv_m值
        check_pat = re.compile(
            r"\['" + re.escape(name) + r"',\s*'" + re.escape(owner) + r"',\s*(\d+)"
        )
        cm = check_pat.search(verify_html)
        if cm:
            written_gtv = int(cm.group(1))
            if written_gtv == wpu_val and expected_gtv != wpu_val:
                verify_errors.append(f"  ⚠️ {name}: BOARD_DATA.gtv_m={written_gtv} == wpu，应为{expected_gtv:,}，写入可能有误！")
            elif written_gtv < expected_gtv * 0.1:
                verify_errors.append(f"  ⚠️ {name}: BOARD_DATA.gtv_m={written_gtv} 远小于期望{expected_gtv:,}，请检查！")
            else:
                print(f"  ✅ {name}: BOARD_DATA.gtv_m={written_gtv:,} 正常")
    if verify_errors:
        print("=== BOARD_DATA写入校验失败 ===")
        for e in verify_errors:
            print(e)
        print("尝试从finance_data.json强制修复BOARD_DATA...")
        for name, owner in OWNERS.items():
            o = ops_by_name.get(name)
            if not o:
                continue
            gtv_m2 = int(o['gtv'])
            gtv_y2 = int(o.get('gtv_y', 0))
            cpc_m2 = int(o['cpc'])
            mem_m2 = int(o['mem'])
            excl2  = o['excl'] / 100.0
            fix_pat = re.compile(
                r"(\['" + re.escape(name) + r"',\s*'" + re.escape(owner) + r"',\s*)"
                r"(\d+)(,\s*\d+,\s*)(\d+)(,\s*)([\d.]+)(,\s*)(\d+)"
                r"(,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*)(\d+)(,.*?\])"
            )
            def _fix(m, gv=gtv_m2, gy=gtv_y2, cv=cpc_m2, mv=mem_m2, ev=excl2):
                return (m.group(1)+str(gv)+m.group(3)+str(gy)+m.group(5)+
                        f"{ev:.4f}"+m.group(7)+str(cv)+m.group(9)+str(mv)+m.group(11))
            verify_html, _ = fix_pat.subn(_fix, verify_html)
        CANVAS_PATH.write_text(verify_html, encoding='utf-8')
        print("→ 强制修复完成")
    else:
        print("→ BOARD_DATA写入校验通过")

    return fc_data


def push_github(fc_data):
    print("\n=== 推送 GitHub ===")
    content = base64.b64encode(CANVAS_PATH.read_bytes()).decode()
    api = f"https://api.github.com/repos/{GH_REPO}/contents/index.html"
    headers = {'Authorization': f'token {GH_TOKEN}', 'User-Agent': 'curl',
               'Content-Type': 'application/json',
               'Accept': 'application/vnd.github.v3+json'}

    sha = json.loads(urllib.request.urlopen(
        urllib.request.Request(api, headers=headers)).read())['sha']

    body = json.dumps({
        'message': f"data: update finance_data {fc_data['time']}",
        'content': content, 'sha': sha
    }).encode()
    res = json.loads(urllib.request.urlopen(
        urllib.request.Request(api, data=body, method='PUT', headers=headers)).read())
    print(f"  commit: {res['commit']['sha'][:8]}")


def main():
    summary, ops_list = fetch_finance_by_agency()

    if not summary:
        print("⚠️ 未获取到城市群汇总数据，退出")
        sys.exit(1)

    fc_data = update_canvas(summary, ops_list)
    push_github(fc_data)
    print("\n✅ 完成")


if __name__ == '__main__':
    main()
