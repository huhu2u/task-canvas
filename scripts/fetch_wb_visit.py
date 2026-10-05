#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作台 visit2/visit3 自动取数：Apollo 478 拉月内拜访明细 → 生成分析文件 → ingest_visit2 → embed
visit2 = 拜访分析「月度汇总」（复用 fetch_visit_analysis.py 的逻辑已含）
visit3 = 拜访覆盖率（gen_visit_cov_wmz.py 吃月明细）
链路:
  1. SmartQuery 478 拉当日明细(date=昨日) → /tmp/wb_visit_<date>/detail.xlsx
  2. 拉月内全量明细(月初~昨日) → gen_visit_wmz.py 生成拜访分析xlsx(含月度汇总Sheet)
     —— 注意: fetch_visit_analysis.py 是9:00的独立cron(直接发文件给英杰), 我们复用它的输出
  3. gen_visit_cov_wmz.py 吃月明细 → 拜访覆盖率xlsx
  4. ingest_visit2.py <拜访分析> <拜访覆盖率>
用法: fetch_wb_visit.py <date YYYY-MM-DD>  (默认昨日)
"""
import sys, os, json, time, math, subprocess
from datetime import datetime, timedelta
import requests
import pandas as pd

WS = '/root/.openclaw/workspace'
sys.path.insert(0, f'{WS}/scripts')
COOKIE = open(f'{WS}/scripts/.apollo_cookie').read().strip()
H = {"Content-Type": "application/json", "Cookie": COOKIE,
     "Referer": "https://a.dper.com/gw/smartreport/", "User-Agent": "Mozilla/5.0"}

COLUMNS = ["attribute_org_id", "attribute_org_name", "employee_id", "employee_name",
           "visit_date", "is_valid", "is_signin", "is_ivr_call", "visit_form",
           "visit_form_name", "distance", "is_500m", "sign_in_time", "start_time",
           "end_time", "shop_id", "shop_name", "org_name_l8"]

def fetch_page(page, date, page_size=200):
    body = [{"category": "query", "type": "SmartQuery", "params": {"dsl": {
        "date": date, "reportId": 478, "pageIndex": str(page), "pageSize": str(page_size),
        "tableId": 995,
        "params": [{"field": "attribute_org_id", "method": "in", "id": 35231, "transformType": 1, "value": 20903327}],
        "columns": COLUMNS, "sorts": [{}]
    }}, "as": "result"}]
    r = requests.post("https://a.dper.com/gw/__cascade__/SmartQuery.query", json=body, headers=H, timeout=120)
    r.raise_for_status()
    result = r.json()["data"]["result"]
    return result["data"], result["total"]

def fetch_month_detail(date):
    """拉 date 所在月初~date 的全量拜访明细（478 的 date 参数返回月内累计）"""
    all_rows = []
    page = 1
    _, total = fetch_page(1, date)
    if not total: return all_rows
    total_pages = math.ceil(total / 200)
    for p in range(1, total_pages + 1):
        rows, _ = fetch_page(p, date)
        all_rows.extend(rows)
        time.sleep(0.1)
    return all_rows

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    out_dir = f'/tmp/wb_visit_{date}'
    os.makedirs(out_dir, exist_ok=True)
    print(f"[visit] 拉取 478 明细 {date} ...", flush=True)
    rows = fetch_month_detail(date)
    print(f"[visit] 478: {len(rows)} 行", flush=True)
    if not rows:
        raise RuntimeError('478 返回 0 行（cookie过期或无数据）')
    json.dump(rows, open(f'{out_dir}/detail.json', 'w'), ensure_ascii=False)

    # 转成 gen_visit_cov_wmz 需要的明细格式
    # 2026-10-05 修复：org_name_l8 只有「高线皖闽浙城市群」无 L9，改用 attribute_org_name 映射 7 家展示名
    from fix_visit_split import ORG_L9_MAP
    df = pd.DataFrame(rows)
    df['org'] = df['attribute_org_name'].apply(lambda n: ORG_L9_MAP.get(str(n).strip()))
    unmapped = df[df['org'].isna()]['attribute_org_name'].value_counts()
    if len(unmapped):
        print('⚠️ 未映射的 attribute_org_name:'); print(unmapped.to_string())
        raise RuntimeError('存在未映射组织，终止入库（补充 fix_visit_split.ORG_L9_MAP）')
    out = pd.DataFrame({
        '拜访日期': df['visit_date'].astype(str).str[:10],
        '门店ID': df['shop_id'], '门店名': df['shop_name'],
        '销售姓名': df['employee_name'], '销售ID': df['employee_id'],
        '是否有效拜访': df['is_valid'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否签到': df['is_signin'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否IVR电话拜访': df['is_ivr_call'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否500米内': df['is_500m'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '签到距离': df['distance'],
        '签到时间': df['sign_in_time'],
        '拜访开始时间': df['start_time'], '拜访结束时间': df['end_time'],
        '拜访形式': df['visit_form_name'],
        '销售业绩归属组织': df['org'],
    })
    detail_x = f'{out_dir}/拜访明细_{date}.xlsx'
    out.to_excel(detail_x, index=False)
    print(f"[visit] 明细xlsx: {len(out)} 行 -> {detail_x}", flush=True)

    # visit3: 覆盖率
    cov_x = f'{out_dir}/拜访覆盖率分析_{date.replace("-","")}.xlsx'
    r = subprocess.run(['python3', f'{WS}/scripts/gen_visit_cov_wmz.py', detail_x, cov_x],
                       capture_output=True, text=True, timeout=600)
    print(r.stdout[-500:], r.stderr[-200:] if r.returncode else '', flush=True)
    if r.returncode != 0: raise RuntimeError('gen_visit_cov_wmz 失败: ' + r.stderr[-200:])

    # visit2: 拜访分析（gen_visit_wmz.py 吃明细出含月度汇总的3Sheet）
    vis_x = f'{out_dir}/拜访分析_皖闽浙_{date.replace("-","")}.xlsx'
    r = subprocess.run(['python3', f'{WS}/scripts/gen_visit_wmz.py', detail_x, vis_x],
                       capture_output=True, text=True, timeout=600)
    print(r.stdout[-500:], r.stderr[-200:] if r.returncode else '', flush=True)
    if r.returncode != 0: raise RuntimeError('gen_visit_wmz 失败: ' + r.stderr[-200:])

    # ingest
    r = subprocess.run(['python3', f'{WS}/scripts/ingest_visit2.py', vis_x, cov_x],
                       capture_output=True, text=True, timeout=600)
    print(r.stdout[-500:], r.stderr[-300:] if r.returncode else '', flush=True)
    if r.returncode != 0: raise RuntimeError('ingest_visit2 失败: ' + r.stderr[-200:])

    # embed
    for mod, f in [('visit2', vis_x), ('visit3', cov_x)]:
        r = subprocess.run(['python3', f'{WS}/scripts/embed_workbench_reports.py', date, mod, f],
                           capture_output=True, text=True, timeout=600)
        print(mod, r.stdout[-200:], flush=True)
    print('[visit] 全链路成功', flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
