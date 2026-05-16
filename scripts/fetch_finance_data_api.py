#!/usr/bin/env python3
"""
从 Apollo one_dashboard API 直接抓取业绩数据（无需浏览器）
Cookie 存在 /root/.openclaw/workspace/data/apollo_cookies.txt
"""
import subprocess, json, re
from datetime import datetime
from pathlib import Path

COOKIE_FILE = Path("/root/.openclaw/workspace/data/apollo_cookies.txt")
OUTPUT_FILE = Path("/root/.openclaw/workspace/data/finance_data.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"

# 代运营商配置（排除宁夏灵创）
ORGS = {
    "20898759": {"name": "惠州巨浪", "mgr": "肖立铭", "gtv_target": 3922600, "cpc_target": 58740},
    "20898758": {"name": "惠州柏万", "mgr": "林启梁", "gtv_target": 3355000, "cpc_target": 88330},
    "20898779": {"name": "泉州小花猫", "mgr": "康子诚", "gtv_target": 3089900, "cpc_target": 123530},
    "20898777": {"name": "惠安广通", "mgr": "尤云生", "gtv_target": 2477200, "cpc_target": 51260},
    "20262600": {"name": "慈溪哲光", "mgr": "贾凌姗", "gtv_target": 3891648, "cpc_target": 158008},
    "20921277": {"name": "义乌汐洋", "mgr": "陈铨", "gtv_target": 3764960, "cpc_target": 139466},
}

# indicatorKey 映射
KEY_MAP = {
    'sale4_expand_operation_hc_capped_cullrisk_gtv_amt': 'gtv',
    'cpc_publish_amt_expand_operation': 'cpc',
    'mem_receive_amt': 'mem',
    'expand_operation_eliminate_rate_new': 'excl',
    'sale4_expand_operation_cpc_valid_newsign_shop_cnt': 'new_sgn',
    'wpt_revenue_amt': 'wpu',
    'sale4_expand_operation_hc_capped_cullrisk_profit_amt': 'cps',
}

def parse_num(val):
    """解析数字字符串，如 '821,984' -> 821984, '2.83%' -> 2.83"""
    if val is None:
        return 0
    val = str(val).replace(',', '').replace('%', '').strip()
    try:
        return float(val)
    except:
        return 0

def fetch_org(cookie, orgid, month_str):
    body = json.dumps({
        "tenantId": 1,
        "dates": [month_str],
        "moduleId": 335,
        "dateType": "month",
        "extendMap": {"org_id_l9": [orgid]},
        "pageNo": 1,
        "pageSize": 50
    })
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://apollo.meituan.com/one_dashboard/performance/query',
        '-H', 'Content-Type: application/json',
        '-H', f'Cookie: {cookie}',
        '-H', 'Referer: https://apollo.meituan.com/crm-data-bulletin-board/performance-board/index.html',
        '-H', 'Origin: https://apollo.meituan.com',
        '-H', f'User-Agent: {UA}',
        '-d', body
    ], capture_output=True, text=True, timeout=20)
    d = json.loads(r.stdout)
    if d.get('code') != 200:
        raise Exception(f"API error: {d.get('msg')} for org {orgid}")
    result = {}
    for ind in d.get('data', {}).get('indicatorInfos', []):
        k = ind['indicatorKey']
        if k in KEY_MAP:
            result[KEY_MAP[k]] = parse_num(ind['indicator'])
    return result

def main():
    cookie = COOKIE_FILE.read_text().strip()
    today = datetime.now()
    month_str = today.strftime("%Y-%m")
    day_of_month = today.day
    days_in_month = 30  # 4月
    days_remaining = max(1, days_in_month - day_of_month + 1)

    ops = []
    for orgid, cfg in ORGS.items():
        print(f"  抓取 {cfg['name']}...", end=" ", flush=True)
        try:
            data = fetch_org(cookie, orgid, month_str)
            gtv = int(data.get('gtv', 0))
            cpc = int(data.get('cpc', 0))
            gtv_gap = round((cfg['gtv_target'] - gtv) / days_remaining)
            cpc_gap = round((cfg['cpc_target'] - cpc) / days_remaining)
            ops.append({
                "name": cfg['name'],
                "mgr": cfg['mgr'],
                "gtv": gtv,
                "gtv_target": cfg['gtv_target'],
                "gtv_y": 0,
                "excl": data.get('excl', 0),
                "cpc": cpc,
                "cpc_target": cfg['cpc_target'],
                "new_sgn": int(data.get('new_sgn', 0)),
                "wpu": int(data.get('wpu', 0)),
                "mem": int(data.get('mem', 0)),
                "cps": int(data.get('cps', 0)),
                "gtv_gap_daily": gtv_gap,
                "cpc_gap_daily": cpc_gap,
            })
            print(f"GTV={gtv:,} CPC={cpc:,}")
        except Exception as e:
            print(f"❌ 失败: {e}")

    finance_data = {
        "updated_at": today.strftime("%Y-%m-%d %H:%M:%S"),
        "date": today.strftime("%Y-%m-%d"),
        "ops": ops
    }
    OUTPUT_FILE.write_text(json.dumps(finance_data, ensure_ascii=False, indent=2))
    print(f"\n✅ 已写入 {OUTPUT_FILE}")
    return finance_data

if __name__ == '__main__':
    print(f"[fetch_finance_data_api] 开始抓取 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main()
