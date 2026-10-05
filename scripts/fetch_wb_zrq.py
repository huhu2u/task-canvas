#!/usr/bin/env python3
"""fetch_wb_zrq.py — 职人码自动拉取（Apollo strategy-management datafetcher API）
用法: fetch_wb_zrq.py [YYYY-MM-DD]  (默认 T-1)
产出:
  1. /tmp/zrq_org_日期.xlsx   — 组织明细(L2/L1/L0 三级, 模拟英杰导出格式)
  2. 跑 gen_zrq_wmz.py 生成分析表
  3. ingest_one_workbench.py zrq 入库工作台
数据链: datafetcher/component/table/query → org_id_l8 全量(组织级) + 各 l9/l10 下钻(销售级 login_id)
"""
import requests, json, sys, datetime, subprocess, math
import pandas as pd

WS = '/root/.openclaw/workspace'
cookie = open(f'{WS}/scripts/.apollo_cookie').read().strip()
H = {"Content-Type": "application/json", "Cookie": cookie,
     "Origin": "https://apollo.meituan.com",
     "Referer": "https://apollo.meituan.com/crm-pc-data-bulletin-board/strategy-management/index.html",
     "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
URL = "https://apollo.meituan.com/datafetcher/component/table/query"

# 组织名 → 7家代运营商（与 ORG_MAP 一致的口径）
ORG_MAP = {
    '星企动-绍兴乐生活区县聚合组': '绍兴星企动', '星企动-绍兴乐生活组': '绍兴星企动',
    '星企动-绍兴柯桥区乐生活组': '绍兴星企动', '星企动-绍兴上虞区乐生活组': '绍兴星企动',
    '上海代优-泉州乐生活组': '泉州小花猫', '泉州市小花猫-泉州乐生活组': '泉州小花猫',
    '南京知了-芜湖乐生活组': '芜湖知了',
    '惠安广通-晋江乐生活组': '惠安广通',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
    '仙居烁果-台州乐生活组': '仙居烁果', '仙居烁果-台州温岭乐生活组': '仙居烁果',
}

IND = ["qr_coop_shop_cnt", "tech_shop_cnt", "valid_tech_shop_cnt", "dx_tech_shop_cnt",
       "dx_tech_shop_cnt_rate", "real_qr_consm_gtv_contain_risk",
       "real_qr_consm_order_cnt_contain_risk",
       "qr_cullrisk_actual_pay_consume_gtv_m_v2", "qr_cullrisk_actual_pay_consume_gtv_m_rate",
       "qr_cullrisk_actual_pay_consume_gtv_m_v2_order_per", "cullrisk_actual_pay_consume_gtv"]

def query(params):
    body = {"tenantId": 1, "dateType": "daily",
            "params": {**params, "partition_date": [DATE], "indicator_value_filter": []},
            "sortBy": "real_qr_consm_gtv_contain_risk", "sortType": "desc",
            "indicatorList": IND, "moduleCode": "3D643815"}
    r = requests.post(URL, headers=H, json=body, timeout=60)
    d = r.json()['data']['indicatorDisplay']
    return d

def num(x):
    if x is None: return 0
    try:
        t = str(x).replace(',', '').replace('%', '')
        v = float(t)
        return 0 if math.isnan(v) else v
    except Exception:
        return 0

def main():
    global DATE
    DATE = sys.argv[1] if len(sys.argv) > 1 else (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    # 1) 全量组织级（org_id_l8 树, 含 l9 层）
    top = query({"org_id_l8": 20903327})
    orgs = []   # (partner, orgName, orgId, metrics dict)
    sales = []  # (partner, orgName, saleName, metrics dict)
    root = top[0]
    for l9 in root.get('children') or []:
        name = l9['selfOrgName']
        partner = ORG_MAP.get(name)
        m = {k: num(l9.get(k)) for k in IND}
        if partner:
            orgs.append((partner, name, l9.get('selfOrgId'), m))
        # 2) 下钻: l9 → 若出现 l10 组织层则继续下钻到销售(login_id)
        stack = [l9]
        while stack:
            node = stack.pop(0)
            sub = query({f"{node['dimName']}": node['selfOrgId']})
            for it in sub:
                for ch in it.get('children') or []:
                    lvl = ch.get('selfOrgLevel') or ch.get('dimName')
                    cm = {k: num(ch.get(k)) for k in IND}
                    if lvl and lvl.startswith('org_id'):
                        # l10 组织节点: 不重复计入 orgs（l9 聚合行已覆盖），仅继续下钻销售
                        stack.append(ch)
                    else:
                        sales.append((partner, name, ch['selfOrgName'], cm))
    # 汇总校验
    tot_bind = sum(o[3]['tech_shop_cnt'] for o in orgs)
    tot_dx = sum(o[3]['dx_tech_shop_cnt'] for o in orgs)
    print(f'[{DATE}] 组织 {len(orgs)} 家, 销售 {len(sales)} 人; 绑码合计 {tot_bind:.0f}, 动销合计 {tot_dx:.0f}')
    json.dump({'date': DATE, 'orgs': [(p, n, i, m) for p, n, i, m in orgs],
               'sales': [(p, n, s, m) for p, n, s, m in sales]},
              open(f'/tmp/zrq_api_{DATE}.json', 'w'), ensure_ascii=False)
    # 3) 生成「职人码组织明细」等效 xlsx（L2 组织行 + L1 销售行）
    rows = []
    for p, n, i, m in orgs:
        rows.append({'层级': 'L2', 'L2': n if '区县聚合' in n else '', 'L3': '' if '区县聚合' in n else n,
                     '姓名': '', '工号': '',
                     '合作门店数（老）': m['qr_coop_shop_cnt'], '职人码绑码门店数': m['tech_shop_cnt'],
                     '职人码有效物料铺设门店数': m['valid_tech_shop_cnt'], '职人码有效动销门店数': m['dx_tech_shop_cnt'],
                     '今日优惠码实付验证GTV': m['real_qr_consm_gtv_contain_risk'],
                     '今日优惠码核销订单量': m['real_qr_consm_order_cnt_contain_risk'],
                     '店转GTV': m['qr_cullrisk_actual_pay_consume_gtv_m_v2'],
                     '店转GTV渗透率(目标16.5%)': m['qr_cullrisk_actual_pay_consume_gtv_m_rate'] / 100,
                     '店转客单均价': m['qr_cullrisk_actual_pay_consume_gtv_m_v2_order_per'],
                     '周期内核销实付GTV': m['cullrisk_actual_pay_consume_gtv'],
                     '职人码有效动销率': m['dx_tech_shop_cnt_rate']})
    for p, n, s, m in sales:
        emp = f'{n}|{s}'  # 工号字段用「组织|姓名」唯一键（API无真实工号），供销售级昨日存档对比
        rows.append({'层级': 'L1', 'L2': '' if '区县聚合' not in n else n, 'L3': '' if '区县聚合' in n else n,
                     '姓名': s, '工号': emp,
                     '合作门店数（老）': m['qr_coop_shop_cnt'], '职人码绑码门店数': m['tech_shop_cnt'],
                     '职人码有效物料铺设门店数': m['valid_tech_shop_cnt'], '职人码有效动销门店数': m['dx_tech_shop_cnt'],
                     '今日优惠码实付验证GTV': m['real_qr_consm_gtv_contain_risk'],
                     '今日优惠码核销订单量': m['real_qr_consm_order_cnt_contain_risk'],
                     '店转GTV': m['qr_cullrisk_actual_pay_consume_gtv_m_v2'],
                     '店转GTV渗透率(目标16.5%)': m['qr_cullrisk_actual_pay_consume_gtv_m_rate'] / 100,
                     '店转客单均价': m['qr_cullrisk_actual_pay_consume_gtv_m_v2_order_per'],
                     '周期内核销实付GTV': m['cullrisk_actual_pay_consume_gtv'],
                     '职人码有效动销率': m['dx_tech_shop_cnt_rate']})
    df = pd.DataFrame(rows)
    out = f'/tmp/zrq_api_detail_{DATE}.xlsx'
    df.to_excel(out, index=False)
    print('saved', out, len(df), 'rows')
    return out

if __name__ == '__main__':
    main()
