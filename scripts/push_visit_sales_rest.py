#!/usr/bin/env python3
"""push_visit_sales_rest.py <date> <拜访分析xlsx>
「每日有效拜访数」Sheet 销售行 → wmz_sales_detail module='visit'（REST 带 date+module 过滤的 delete/insert）。
取“昨日”列 = Sheet 中最大日期列。组织列已是 7 家展示名（gen_visit_wmz map_wmz_org 产出）。
"""
import sys, json, math, urllib.request
import pandas as pd

KEY_FILE = '/tmp/.wb_key'
BASE = 'https://dbcli-el9byiqifrr7yh4c.database.sankuai.com/rest/v1'


def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    return o


def main():
    date, path = sys.argv[1], sys.argv[2]
    key = open(KEY_FILE).read().strip()
    hdr = {'apikey': key, 'Authorization': 'Bearer ' + key}
    x = pd.read_excel(path, sheet_name='每日有效拜访数')
    date_cols = sorted(set(c.split(' ')[0] for c in x.columns if ' 有效' in c))
    if not date_cols:
        raise SystemExit('「每日有效拜访数」无日期列')
    yd = date_cols[-1]
    k_v, k_h = f'{yd} 有效', f'{yd} 好店'
    rows = []
    for _, r in x.iterrows():
        org = str(r['代运营商']).strip()
        name = str(r['销售姓名'] or '').strip()
        if not name or not org or org in ('合计', '汇总'):
            continue
        met = {'昨日有效拜访': int(float(r.get(k_v) or 0)), '好店拜访': int(float(r.get(k_h) or 0))}
        rows.append({'date': date, 'module': 'visit', 'org': org, 'salesperson': name,
                     'metrics': clean(met), 'user_id': ''})
    print(f'visit sales rows: {len(rows)} (昨日列 {k_v})，orgs: {sorted(set(r["org"] for r in rows))}')
    # delete with filters
    req = urllib.request.Request(f"{BASE}/wmz_sales_detail?date=eq.{date}&module=eq.visit",
                                 headers=hdr, method='DELETE')
    req.add_header('Prefer', 'return=representation')
    with urllib.request.urlopen(req, timeout=60) as resp:
        print('deleted old rows:', len(json.loads(resp.read().decode() or '[]')))
    ok = 0
    for i in range(0, len(rows), 20):
        batch = rows[i:i+20]
        req = urllib.request.Request(BASE + '/wmz_sales_detail',
                                     data=json.dumps(batch).encode(),
                                     headers={**hdr, 'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
                                     method='POST')
        try:
            urllib.request.urlopen(req, timeout=60)
            ok += len(batch)
        except Exception as e:
            print('batch fail', i, str(e)[:150])
    print(f'visit sales inserted: {ok}/{len(rows)}')
    if ok < len(rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
