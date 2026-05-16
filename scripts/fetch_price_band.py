#!/usr/bin/env python3
"""
超价格带数据自动抓取脚本
API: apollo.meituan.com/gw/__cascade__/SmartQuery.query
reportId=864, tableId=3469
org=粤闽浙城市群 (value=20903327)
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta

COOKIE_FILE = os.path.join(os.path.dirname(__file__), '.apollo_cookie')
API_URL = "https://apollo.meituan.com/gw/__cascade__/SmartQuery.query"

# 价格带阈值（品类code → 阈值）
# 品类A: cat0_id=1(美食) beyond_price=300, 阈值17%
# 品类B: cat0_id=2(丽人) beyond_price=500, 阈值34%
# 品类C: cat0_id=... beyond_price=1000, 阈值6%
# 实际阈值从MEMORY.md: A(≤300元)17% | B(≤500元)34% | C(≤1000元)6%
THRESHOLDS = {
    300: 0.17,   # 品类A
    500: 0.34,   # 品类B
    1000: 0.06,  # 品类C
}

def get_cookie():
    with open(COOKIE_FILE) as f:
        return f.read().strip()

def fetch_all_data(date_str: str) -> list:
    """分页抓取所有数据，返回所有行"""
    cookie = get_cookie()
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Referer": "https://apollo.meituan.com/gw/smartreport/",
        "Origin": "https://apollo.meituan.com",
    }
    
    base_payload = [{
        "category": "query",
        "type": "SmartQuery",
        "params": {
            "dsl": {
                "date": date_str,
                "reportId": 864,
                "pageIndex": 1,
                "columns": [
                    "hp_cal_dt", "cat0_name", "cat0_id", "cat1_name",
                    "employee_name", "actual_pay_share_amt_over_price",
                    "actual_pay_share_amt", "shop_name", "beyond_price",
                    "dp_shop_id", "attribute_org_id", "cat1_id",
                    "employee_id", "actual_pay_share_amt_over_price_ratio",
                    "attribute_org_name"
                ],
                "pageSize": 500,
                "tableId": 3469,
                "params": [
                    {"field": "attribute_org_id", "method": "in", "id": 36329,
                     "transformType": 1, "value": 20903327},
                    {"field": "employee_id", "method": "=", "id": 36330},
                    {"field": "employee_id", "method": "=", "id": 36331},
                    {"field": "dp_shop_id", "method": "=", "id": 36332}
                ],
                "sorts": [{}]
            }
        },
        "as": "result",
        "children": []
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
            print(f"Total rows: {total}")
        
        all_rows.extend(rows)
        print(f"  Page {page}: fetched {len(rows)} rows, total so far: {len(all_rows)}")
        
        if len(all_rows) >= total or len(rows) == 0:
            break
        page += 1
    
    return all_rows


def analyze(rows: list, date_str: str) -> dict:
    """
    按代运营商+价格带分组，计算超价格带占比
    返回结构: {org_name: {300: ratio, 500: ratio, 1000: ratio}}
    """
    # Group by org + beyond_price
    from collections import defaultdict
    
    # {org_name: {beyond_price: {"over": sum, "total": sum}}}
    agg = defaultdict(lambda: defaultdict(lambda: {"over": 0.0, "total": 0.0}))
    
    for row in rows:
        org = row.get("attribute_org_name", "未知")
        # 去掉组名后缀，只取代运营商名
        # e.g. "宁夏灵创-金华义乌乐生活组" -> "宁夏灵创"
        org_short = org.split("-")[0] if "-" in org else org
        
        bp = float(row.get("beyond_price", 0))
        over = float(row.get("actual_pay_share_amt_over_price", 0) or 0)
        total = float(row.get("actual_pay_share_amt", 0) or 0)
        
        if bp in THRESHOLDS:
            agg[org_short][bp]["over"] += over
            agg[org_short][bp]["total"] += total
    
    # 计算占比
    result = {}
    for org, price_bands in agg.items():
        result[org] = {}
        for bp, vals in price_bands.items():
            if vals["total"] > 0:
                ratio = vals["over"] / vals["total"]
            else:
                ratio = 0.0
            result[org][bp] = {
                "ratio": ratio,
                "over_amt": vals["over"],
                "total_amt": vals["total"],
                "threshold": THRESHOLDS[bp],
                "diff": ratio - THRESHOLDS[bp],  # 正数=超标，负数=有余量
            }
    
    return result


def format_summary(analysis: dict, date_str: str) -> str:
    """生成汇总文本"""
    lines = [f"# 超价格带分析 {date_str}\n"]
    lines.append("| 代运营商 | 品类A(≤300) | vs阈值17% | 品类B(≤500) | vs阈值34% | 品类C(≤1000) | vs阈值6% |")
    lines.append("|---|---|---|---|---|---|---|")
    
    # 排序：超标最严重的排前面
    def max_diff(d):
        diffs = [v["diff"] for v in d.values()]
        return max(diffs) if diffs else -999
    
    for org in sorted(analysis.keys(), key=lambda o: max_diff(analysis[o]), reverse=True):
        bands = analysis[org]
        row_parts = [org]
        for bp in [300, 500, 1000]:
            if bp in bands:
                b = bands[bp]
                pct = f"{b['ratio']*100:.1f}%"
                diff = b['diff']*100
                sign = "+" if diff > 0 else ""
                diff_str = f"{sign}{diff:.1f}pp"
                flag = "🔴" if diff > 0 else ("🟡" if diff > -0.03 else "🟢")
                row_parts.append(f"{flag}{pct}")
                row_parts.append(diff_str)
            else:
                row_parts.extend(["—", "—"])
        lines.append("| " + " | ".join(row_parts) + " |")
    
    return "\n".join(lines)


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Fetching report 864 for date: {date_str}")
    
    rows = fetch_all_data(date_str)
    print(f"\nTotal rows fetched: {len(rows)}")
    
    analysis = analyze(rows, date_str)
    
    print("\n=== Analysis ===")
    for org, bands in sorted(analysis.items()):
        for bp, b in sorted(bands.items()):
            flag = "🔴超标" if b["diff"] > 0 else "✅达标"
            print(f"  {org} 品类{bp}: {b['ratio']*100:.1f}% (阈值{b['threshold']*100:.0f}%) diff={b['diff']*100:+.1f}pp {flag}")
    
    summary = format_summary(analysis, date_str)
    print("\n=== Summary Table ===")
    print(summary)
    
    # Save analysis JSON
    out_file = f"/tmp/price_band_{date_str.replace('-','')}.json"
    out_file2 = f"/tmp/price_band_{date_str}.json"
    payload = {"date": date_str, "total_rows": len(rows), "analysis": analysis, "rows": rows}
    with open(out_file, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(out_file2, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_file}")
