#!/usr/bin/env python3
"""
每天9点自动运行：
1. 从Apollo report 864抓取超价格带数据
2. 解析并更新task-canvas.html的price-band Tab
3. 推送到GitHub
"""

import requests
import json
import sys
import os
import re
import base64
from datetime import datetime, timedelta
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANVAS_FILE = os.path.join(SCRIPT_DIR, '..', 'task-canvas.html')
COOKIE_FILE = os.path.join(SCRIPT_DIR, '.apollo_cookie')
GH_TOKEN = ""
GH_REPO = "huhu2u/task-canvas"
GH_FILE = "index.html"

API_URL = "https://apollo.meituan.com/gw/__cascade__/SmartQuery.query"

THRESHOLDS = {300.0: 0.17, 500.0: 0.34, 1000.0: 0.06}
THRESHOLD_LABELS = {300.0: "A", 500.0: "B", 1000.0: "C"}

def get_cookie():
    with open(COOKIE_FILE) as f:
        return f.read().strip()

def fetch_all_data(date_str: str) -> list:
    cookie = get_cookie()
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Referer": "https://apollo.meituan.com/gw/smartreport/",
        "Origin": "https://apollo.meituan.com",
    }
    base_payload = [{
        "category": "query", "type": "SmartQuery",
        "params": {"dsl": {
            "date": date_str, "reportId": 864, "pageIndex": 1,
            "columns": ["hp_cal_dt","cat0_name","cat0_id","cat1_name","employee_name",
                        "actual_pay_share_amt_over_price","actual_pay_share_amt","shop_name",
                        "beyond_price","dp_shop_id","attribute_org_id","cat1_id","employee_id",
                        "actual_pay_share_amt_over_price_ratio","attribute_org_name"],
            "pageSize": 500, "tableId": 3469,
            "params": [
                {"field":"attribute_org_id","method":"in","id":36329,"transformType":1,"value":20903327},
                {"field":"employee_id","method":"=","id":36330},
                {"field":"employee_id","method":"=","id":36331},
                {"field":"dp_shop_id","method":"=","id":36332}
            ],
            "sorts": [{}]
        }},
        "as": "result", "children": []
    }]
    all_rows = []
    page = 1
    total = None
    while True:
        payload = json.loads(json.dumps(base_payload))
        payload[0]["params"]["dsl"]["pageIndex"] = page
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("data", {}).get("result", {})
        rows = result.get("data", [])
        if total is None:
            total = result.get("total", 0)
            print(f"  total={total}")
        all_rows.extend(rows)
        print(f"  page {page}: {len(rows)} rows, cumulative={len(all_rows)}")
        if len(all_rows) >= total or len(rows) == 0:
            break
        page += 1
    return all_rows

def analyze(rows: list) -> dict:
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(lambda: {"over": 0.0, "total": 0.0}))
    for row in rows:
        org = row.get("attribute_org_name", "未知")
        org_short = org.split("-")[0] if "-" in org else org
        bp = float(row.get("beyond_price", 0))
        over = float(row.get("actual_pay_share_amt_over_price", 0) or 0)
        total = float(row.get("actual_pay_share_amt", 0) or 0)
        if bp in THRESHOLDS:
            agg[org_short][bp]["over"] += over
            agg[org_short][bp]["total"] += total
    result = {}
    for org, price_bands in agg.items():
        if org in ("高线粤闽浙城市群",):
            continue
        result[org] = {}
        for bp, vals in price_bands.items():
            ratio = vals["over"] / vals["total"] if vals["total"] > 0 else 0.0
            result[org][bp] = {
                "ratio": ratio, "threshold": THRESHOLDS[bp],
                "diff": ratio - THRESHOLDS[bp],
            }
    return result

def build_html_table(analysis: dict, date_str: str) -> dict:
    """生成task-canvas price-band Tab的HTML内容，返回 {'tbody': ..., 'summary': ...}
    浅色背景风格：超标=浅红、临近=浅黄、达标=浅绿，文字深色"""

    def text_color(diff):
        if diff > 0: return "#b91c1c"      # 深红文字
        elif diff > -0.03: return "#92400e" # 深棕文字
        else: return "#166534"              # 深绿文字

    def bg_color(diff):
        if diff > 0: return "#fee2e2"       # 浅红背景
        elif diff > -0.03: return "#fef9c3" # 浅黄背景
        else: return "#dcfce7"              # 浅绿背景

    def diff_color(diff):
        if diff > 0: return "#ef4444"       # 红色偏差
        elif diff > -0.03: return "#f59e0b" # 橙色偏差
        else: return "#22c55e"              # 绿色偏差

    def max_diff(d):
        return max([v["diff"] for v in d.values()], default=-999)

    # 生成 tbody rows
    rows_html = ""
    for i, org in enumerate(sorted(analysis.keys(), key=lambda o: max_diff(analysis[o]), reverse=True)):
        bands = analysis[org]
        row_bg = "#f9fafb" if i % 2 == 0 else "#ffffff"
        cells = f'<td style="padding:8px 12px;background:{row_bg};color:#111827;font-weight:600;border-bottom:1px solid #e5e7eb;">{org}</td>'
        for bp in [300.0, 500.0, 1000.0]:
            if bp in bands:
                b = bands[bp]
                d = b["diff"]
                sign = "+" if d > 0 else ""
                tc = text_color(d)
                bg_c = bg_color(d)
                dc = diff_color(d)
                cells += (f'<td style="padding:8px 10px;text-align:center;background:{bg_c};'
                          f'border-bottom:1px solid #e5e7eb;border-left:1px solid #e5e7eb;">'
                          f'<span style="font-size:14px;font-weight:700;color:{tc};">{b["ratio"]*100:.1f}%</span>'
                          f'<br><span style="font-size:11px;color:{dc};">{sign}{d*100:.1f}pp</span></td>')
            else:
                cells += '<td style="padding:8px 10px;text-align:center;color:#9ca3af;border-bottom:1px solid #e5e7eb;border-left:1px solid #e5e7eb;">—</td>'
        rows_html += f'<tr>{cells}</tr>\n'

    # 归因摘要
    alerts = []
    for org, bands in sorted(analysis.items(), key=lambda x: max_diff(x[1]), reverse=True):
        for bp, b in bands.items():
            if b["diff"] > 0:
                lbl = THRESHOLD_LABELS[bp]
                alerts.append(f"<li style='color:#374151;'>❌ <b>{org}</b> 品类{lbl}(≤{int(bp)}元) <span style='color:#dc2626;font-weight:600;'>超标{b['diff']*100:+.1f}pp</span>（实际{b['ratio']*100:.1f}% vs 阈值{b['threshold']*100:.0f}%）</li>")
    for org, bands in sorted(analysis.items(), key=lambda x: max_diff(x[1]), reverse=True):
        for bp, b in bands.items():
            if -0.03 < b["diff"] <= 0:
                lbl = THRESHOLD_LABELS[bp]
                alerts.append(f"<li style='color:#374151;'>⚠️ <b>{org}</b> 品类{lbl}(≤{int(bp)}元) 余量仅剩<span style='color:#d97706;font-weight:600;'>{abs(b['diff'])*100:.1f}pp</span></li>")

    if not alerts:
        alerts_html = "<li style='color:#166534;'>✅ 粤闽浙全部代运营商三价格带全面达标</li>"
    else:
        alerts_html = "\n".join(alerts)

    summary_html = f'''<div style="font-weight:700;color:#1e40af;margin-bottom:8px;">📋 整体归因（{date_str}）</div>
    <ul style="margin:0;padding-left:16px;list-style:none;line-height:2;">
{alerts_html}
    </ul>'''

    return {'tbody': rows_html, 'summary': summary_html}

def update_canvas(html_content: str, date_str: str):
    """更新task-canvas.html的price-band section（基于HTML标记，可靠替换）"""
    with open(CANVAS_FILE, 'r') as f:
        canvas = f.read()

    updated = canvas

    # 1. 更新 tbody 内容（表格行）
    tbody_start = '<!-- PRICE_BAND_TBODY_START -->'
    tbody_end   = '<!-- PRICE_BAND_TBODY_END -->'
    if tbody_start in updated and tbody_end in updated:
        s = updated.index(tbody_start) + len(tbody_start)
        e = updated.index(tbody_end)
        updated = updated[:s] + '\n' + html_content['tbody'] + '\n' + updated[e:]
        print("  PRICE_BAND_TBODY replaced")
    else:
        print("ERROR: PRICE_BAND_TBODY markers not found in canvas")
        return False

    # 2. 更新归因摘要
    sum_start = '<!-- PRICE_BAND_SUMMARY_START -->'
    sum_end   = '<!-- PRICE_BAND_SUMMARY_END -->'
    if sum_start in updated and sum_end in updated:
        s = updated.index(sum_start) + len(sum_start)
        e = updated.index(sum_end)
        updated = updated[:s] + '\n    ' + html_content['summary'] + '\n    ' + updated[e:]
        print("  PRICE_BAND_SUMMARY replaced")

    # 3. 更新右上角日期
    import re
    updated = re.sub(
        r'数据截止：\d{4}-\d{2}-\d{2}',
        f'数据截止：{date_str}',
        updated
    )

    with open(CANVAS_FILE, 'w') as f:
        f.write(updated)
    print("Canvas updated successfully")
    return True

def push_to_github(date_str: str):
    """Push to GitHub"""
    import urllib.request
    with open(CANVAS_FILE, 'rb') as f:
        content_b64 = base64.b64encode(f.read()).decode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}",
        headers={"Authorization": f"token {GH_TOKEN}", "User-Agent": "python"})
    with urllib.request.urlopen(req) as r:
        sha = json.loads(r.read())['sha']
    payload = json.dumps({
        "message": f"auto: 超价格带分析更新 {date_str}",
        "content": content_b64, "sha": sha
    }).encode()
    req2 = urllib.request.Request(
        f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}",
        data=payload, method="PUT",
        headers={"Authorization": f"token {GH_TOKEN}", "Content-Type": "application/json", "User-Agent": "python"})
    with urllib.request.urlopen(req2) as r:
        result = json.loads(r.read())
        commit_sha = result.get('commit', {}).get('sha', '')[:12]
        print(f"GitHub push: {commit_sha}")
        return commit_sha

if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"=== 超价格带自动更新 date={date_str} ===")
    
    print("1. Fetching data from Apollo...")
    rows = fetch_all_data(date_str)
    print(f"   Fetched {len(rows)} rows")
    
    print("2. Analyzing...")
    analysis = analyze(rows)
    
    print("3. Building HTML...")
    html = build_html_table(analysis, date_str)
    
    print("4. Updating canvas...")
    update_canvas(html, date_str)
    
    print("5. Pushing to GitHub...")
    sha = push_to_github(date_str)
    
    print(f"\n✅ Done! Commit: {sha}")
    print(f"   https://huhu2u.github.io/task-canvas/")
