#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经营评分分析Excel生成（2026-10-06补齐数据源下载）：从 score_stores 复刻 auto_score_summary 口径 + gen_score_wmz 明细格式
输出：/tmp/经营评分分析_皖闽浙_<date>.xlsx 并 base64 入库 wmz_report_files (module=score)
Sheet: 组织汇总 / 销售维度 / ≥70分门店明细 / <30分门店明细
"""
import sys, json, base64, os, urllib.request, urllib.parse
from collections import defaultdict
import pandas as pd

# 2026-10-22英杰定稿 → 23:50修正：档位水位线 = 9月全国代运营商分层「好店经营评分」区间实际最低分
# （初版误用平均分+1分，英杰指出P50档最低54.35，修正为实算：P50=54.35 / P50-80=52.72 / P80-90=52.00 / P90=49.44）
SCORE_TIERS = [('P50', 54.35), ('P50-80', 52.72), ('P80-90', 52.0), ('P90', 49.44)]

def score_tier(avg):
    if avg is None or avg == '':
        return ('--', '--')
    avg = float(avg)
    for i, (name, line) in enumerate(SCORE_TIERS):
        if avg >= line:
            nxt = SCORE_TIERS[i - 1][1] if i > 0 else None
            return (name, round(nxt - avg, 1) if nxt is not None else 0)
    return ('低于P90', round(SCORE_TIERS[-1][1] - avg, 1))

WS = '/mnt/openclaw/.openclaw/workspace'
BASE = 'https://dbcli-el9byiqifrr7yh4c.database.sankuai.com/rest/v1'
URL8 = 'https://dbcli-8x6qvevf5kpmur91.database.sankuai.com/rest/v1'
key = open('/tmp/.wb_key').read().strip()
key8 = open('/tmp/.supa_key').read().strip() if os.path.exists('/tmp/.supa_key') else key

def orgfix(s):
    s = str(s or '').strip()
    if '代优' in s: return '上海代优'
    for k in ['义乌汐洋', '慈溪哲光', '上海代优', '惠安广通', '仙居烁果', '绍兴星企动']:
        if k in s: return k
    if '小花猫' in s: return '上海代优'
    if '汐洋' in s: return '义乌汐洋'
    if '哲光' in s: return '慈溪哲光'
    if '广通' in s: return '惠安广通'
    if '烁果' in s: return '仙居烁果'
    if '星企动' in s: return '绍兴星企动'
    if '知了' in s: return '芜湖知了'
    return None

MGR = {'绍兴星企动': '李晓锋', '上海代优': '代永安', '慈溪哲光': '孙浩', '义乌汐洋': '陈铨',
       '仙居烁果': '邱伯达', '惠安广通': '尤云生', '芜湖知了': '陈具礼', '泉州小花猫': '代永安'}
ORG_ORDER = ['上海代优', '慈溪哲光', '义乌汐洋', '惠安广通', '芜湖知了', '绍兴星企动', '仙居烁果']

def req(url, key_, path, method='GET', body=None):
    r = urllib.request.Request(url + path, data=json.dumps(body).encode() if body else None, method=method)
    r.add_header('apikey', key_); r.add_header('Authorization', 'Bearer ' + key_)
    r.add_header('Content-Type', 'application/json')
    return json.loads(urllib.request.urlopen(r, timeout=60).read() or b'[]')

def q8(path):
    # 2026-10-24修复：翻页必须加稳定排序，否则行漂移导致重复/漏行（3548明细出现769家重复即此因）
    if 'order=' not in path:
        path = path + '&order=shop_id.asc' if 'shop_id' in path else path + '&order=id.asc'
    rows, off = [], 0
    seen = set()
    while True:
        b = req(URL8, key8, f'{path}&limit=1000&offset={off}')
        before = len(rows)
        for r in b:
            k = str(r.get('shop_id', r.get('id', len(rows))))
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
        if len(b) < 1000: break
        off += 1000
    return rows

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else '2026-10-05'
    prev_date = (pd.Timestamp(date) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    SALES_ORG = {}
    p = f'{WS}/data/cpc_daily_archive/{date}.xlsx'
    if not os.path.exists(p):
        import glob
        cands = sorted(glob.glob(f'{WS}/data/cpc_daily_archive/*.xlsx'))
        p = cands[-1]
    df = pd.read_excel(p)
    for _, r in df.iterrows():
        s = str(r.get('销售工号名称') or '').strip()
        o = orgfix(str(r.get('业绩归属组织名称') or '').split('-')[0])
        if s and o and s != 'nan': SALES_ORG[s] = o

    rows = q8(f'/score_stores?stat_date=eq.{date}&select=shop_id,store_name,sales_name,score,is_target')
    prows = q8(f'/score_stores?stat_date=eq.{prev_date}&select=shop_id,store_name,sales_name,score,is_target')
    prev_shop = {str(r['shop_id']): r for r in prows}
    # 2026-10-27英杰：本月总分变化（vs 当月1日基数；库里没有1日用最早有数据的日期）
    month_base_date = f"{date[:8]}01"
    _mb_chk = q8(f'/score_stores?stat_date=eq.{month_base_date}&select=shop_id&limit=1')
    if not _mb_chk:
        _alld = q8('/score_stores?select=stat_date&order=stat_date.asc&limit=1')
        if _alld and _alld[0]['stat_date'] >= month_base_date:
            month_base_date = _alld[0]['stat_date']
        else:
            month_base_date = None
    if month_base_date:
        mrows = q8(f'/score_stores?stat_date=eq.{month_base_date}&select=shop_id,score')
        month_shop = {str(r['shop_id']): r for r in mrows}
        print('month base:', month_base_date, len(mrows))
    else:
        month_shop = {}
        print('month base: none')
    prev_ok = {str(r['shop_id']) for r in prows if float(r.get('score') or 0) >= 70}
    prev_ok_key = {str(r['shop_id']) for r in prows if r.get('is_target') in (1, '1', True) and float(r.get('score') or 0) >= 70}
    print('today rows:', len(rows), 'prev rows:', len(prows))

    _orig_prev_ok_key = prev_ok_key  # 真实昨日（26日）达标集合，日增长/日下滑专用
    # 2026-10-27保护：Apollo评分源隔日刷新——若今日与昨日全量分数完全一致（无变化），
    # 说明源未刷出新分。此时「昨日总分变化/加减分明细」回退到最近一个有变化的日期对：
    # 向前逐日找 prev2 使 prev2 与其前一日存在分数差异，用 (prev2, prev2的前一日) 作为变化对。
    _today_map = {str(r['shop_id']): r.get('score') for r in rows}
    _same = all(_today_map.get(str(r['shop_id'])) == r.get('score') for r in prows if str(r['shop_id']) in _today_map)
    delta_note = ''
    if _same and prows:
        # 找最近有变化日期对：从昨日往前找
        import datetime as _dt
        cand_prev = None
        d_cur = _dt.datetime.strptime(prev_date, '%Y-%m-%d')
        for back in range(1, 10):
            d_p = (d_cur - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
            d_pp = (d_cur - _dt.timedelta(days=back + 1)).strftime('%Y-%m-%d')
            r_p = q8(f'/score_stores?stat_date=eq.{d_p}&select=shop_id,score&limit=20000')
            r_pp = q8(f'/score_stores?stat_date=eq.{d_pp}&select=shop_id,score&limit=20000')
            if not r_p or not r_pp: continue
            mp = {str(x['shop_id']): x.get('score') for x in r_p}
            if any(mp.get(str(x['shop_id'])) != x.get('score') for x in r_pp if str(x['shop_id']) in mp):
                cand_prev = (d_p, d_pp, r_p)
                break
        if cand_prev:
            delta_note = f'（评分源{cand_prev[0]}快照，变化对 {cand_prev[1]}→{cand_prev[0]}）'
            print('source not refreshed; delta fallback pair:', cand_prev[1], '->', cand_prev[0])
            prows = cand_prev[2]
            prev_shop = {str(r['shop_id']): r for r in prows}
            prev_ok = {str(r['shop_id']) for r in prows if float(r.get('score') or 0) >= 70}
            prev_ok_key = {str(r['shop_id']) for r in prows if r.get('is_target') in (1, '1', True) and float(r.get('score') or 0) >= 70}

    recs = []
    for r in rows:
        sales = (r.get('sales_name') or '').strip()
        org = SALES_ORG.get(sales)
        if not org: continue
        sc = float(r.get('score') or 0)
        is_key = r.get('is_target') in (1, '1', True)
        recs.append(dict(shop_id=str(r['shop_id']), name=r.get('store_name') or '', sales=sales, org=org, score=sc, key=is_key))
    print('mapped recs:', len(recs))

    # --- Excel ---
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws0 = wb.active; ws0.title = '组织汇总'
    # 2026-10-23英杰：组织汇总只留重点池口径，全量分析列全删（看板同步删）
    hdr = ['代运营商', '操盘手', '重点池门店数', '重点池达标', '重点池平均评分', '重点池评分档位', '距上一档', '重点池≥70分', '重点池50-70分', '重点池<50分', '昨日总分变化', '本月总分变化']  # 2026-10-27英杰：加昨日总分变化（重点池Σ分差）
    # 2026-10-23英杰：样式按目标截图定稿（深蓝表头白字/数据行白底黑细边框/数值右对齐/档位纯文本/平均分绿-白-红色阶/合计行浅蓝加粗）
    THIN = Side(style='thin', color='000000')
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    ws0.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr))
    c = ws0.cell(row=1, column=1, value=f'皖闽浙经营评分分析（数据日期 {date}）')
    c.font = Font(bold=True, size=18); c.alignment = Alignment(horizontal='center', vertical='center')
    ws0.row_dimensions[1].height = 34
    for j, h in enumerate(hdr, 1):
        c = ws0.cell(row=2, column=j, value=h)
        c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
        c.alignment = Alignment(horizontal='center', vertical='center'); c.border = BORDER
    ws0.row_dimensions[2].height = 24
    org_agg = defaultdict(lambda: {'n': 0, 'ok': 0, 's': 0.0, 'low': 0, 'kn': 0, 'ks': 0.0, 'kok': 0,
                                   'new_ok': 0, 'lost': 0, 'kdiff': 0.0, 'kmdiff': 0.0,
                                   'r70': 0, 'r5070': 0, 'r50': 0, 'kr70': 0, 'kr5070': 0, 'kr50': 0})
    sales_agg = defaultdict(lambda: {'n': 0, 'ok': 0, 'kn': 0, 'kok': 0, 'ks': 0.0, 'new_ok': 0, 'lost': 0, 'kdiff': 0.0, 'kmdiff': 0.0,
                                     'r70': 0, 'r5070': 0, 'r50': 0, 'kr70': 0, 'kr5070': 0, 'kr50': 0})
    detail70, detail5070, detail50 = [], [], []
    shop_today = {}
    for rec in recs:
        shop_today[str(rec['shop_id'])] = rec
        a = org_agg[rec['org']]
        if rec['key']:
            a['kn'] += 1; a['ks'] += rec['score']
            pr = prev_shop.get(str(rec['shop_id']))
            if pr is not None and pr.get('score') not in (None, ''):
                try: a['kdiff'] += rec['score'] - float(pr.get('score') or 0)
                except Exception: pass
            mr = month_shop.get(str(rec['shop_id']))
            if mr is not None and mr.get('score') not in (None, ''):
                try: a['kmdiff'] += rec['score'] - float(mr.get('score') or 0)
                except Exception: pass
            if rec['score'] >= 70: a['kok'] += 1; a['kr70'] += 1
            elif rec['score'] >= 50: a['kr5070'] += 1
            else: a['kr50'] += 1
            if rec['score'] >= 70 and rec['shop_id'] not in prev_ok_key: a['new_ok'] += 1
            if rec['score'] < 70 and rec['shop_id'] in prev_ok_key: a['lost'] += 1
        b = sales_agg[(rec['org'], rec['sales'])]
        if rec['key']:
            b['kn'] += 1; b['ks'] += rec['score']
            pr = prev_shop.get(str(rec['shop_id']))
            if pr is not None and pr.get('score') not in (None, ''):
                try: b['kdiff'] += rec['score'] - float(pr.get('score') or 0)
                except Exception: pass
            mr = month_shop.get(str(rec['shop_id']))
            if mr is not None and mr.get('score') not in (None, ''):
                try: b['kmdiff'] += rec['score'] - float(mr.get('score') or 0)
                except Exception: pass
            if rec['score'] >= 70: b['kok'] += 1; b['kr70'] += 1
            elif rec['score'] >= 50: b['kr5070'] += 1
            else: b['kr50'] += 1
            if rec['score'] >= 70 and rec['shop_id'] not in prev_ok_key: b['new_ok'] += 1
            if rec['score'] < 70 and rec['shop_id'] in prev_ok_key: b['lost'] += 1
        row_item = (rec, '新增' if rec['score'] >= 70 and rec['shop_id'] not in prev_ok_key else ('掉标' if rec['score'] < 70 and rec['shop_id'] in prev_ok_key else ''))
        # 2026-10-22英杰：明细三档下钻改为 ≥70 / 50-70 / <50（重点池门店）
        if rec['key'] and rec['score'] >= 70: detail70.append(row_item)
        elif rec['key'] and rec['score'] >= 50: detail5070.append(row_item)
        elif rec['key'] and rec['score'] < 50: detail50.append(row_item)

    def wrow(ws, i, vals, bold=False, fill=None, avg_fill=None, numeric_from=3, tier_col=None):
        # 2026-10-23定稿样式：黑细边框/数值右对齐/档位列左对齐纯文本/平均分色阶底色由调用方传
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = Font(bold=bold)
            c.border = BORDER
            if fill: c.fill = PatternFill('solid', fgColor=fill)
            if avg_fill is not None and j == 5: c.fill = PatternFill('solid', fgColor=avg_fill)
            c.alignment = Alignment(horizontal='left' if (j < numeric_from or (tier_col and j == tier_col)) else 'right', vertical='center')
    # 2026-10-23英杰：平均评分列绿-白-红三色色阶（Excel内置 63BE7B/FFFFFF/F4696B）
    kavgs = [a['ks'] / a['kn'] for a in org_agg.values() if a['kn']]
    def avg_scale(v):
        if v is None or len(kavgs) < 2: return None
        lo, hi = min(kavgs), max(kavgs)
        if hi == lo: return None
        t = (v - lo) / (hi - lo)  # 0=最红 1=最绿
        def lerp(a, b): return int(a + (b - a) * t)
        if t >= 0.5:
            u = (t - 0.5) * 2; cols = [lerp(0xFF, 0x63), lerp(0xFF, 0xBE), lerp(0xFF, 0x7B)]  # 白→绿
        else:
            u = t * 2; cols = [lerp(0xFF, 0xF4), lerp(0xFF, 0x69), lerp(0xFF, 0x6B)]  # 白→红
        return f'{cols[0]:02X}{cols[1]:02X}{cols[2]:02X}'
    i = 3
    for org in ORG_ORDER:
        a = org_agg.get(org)
        if not a: continue
        kavg = round(a['ks'] / a['kn'], 1) if a['kn'] else None
        tier, tgap = score_tier(kavg)
        wrow(ws0, i, [org, MGR.get(org, ''), a['kn'], a['kok'],
                      kavg if kavg is not None else '-', tier, tgap,
                      a['kr70'], a['kr5070'], a['kr50'], round(a['kdiff'], 1), round(a['kmdiff'], 1)],
             bold=False, avg_fill=avg_scale(kavg), tier_col=6)
        # 昨日/本月总分变化列色：正=绿字 负=红字
        dc = ws0.cell(row=i, column=11)
        dc.font = Font(bold=True, color='137333' if a['kdiff'] > 0 else ('C5221F' if a['kdiff'] < 0 else '000000'))
        dc.number_format = '+0.0;-0.0;0'
        mc = ws0.cell(row=i, column=12)
        mc.font = Font(bold=True, color='137333' if a['kmdiff'] > 0 else ('C5221F' if a['kmdiff'] < 0 else '000000'))
        mc.number_format = '+0.0;-0.0;0'
        ws0.row_dimensions[i].height = 20
        i += 1
    tot = {k: sum(a[k] for a in org_agg.values()) for k in ['kn', 'kok', 'new_ok', 'lost', 'kr70', 'kr5070', 'kr50']}
    tot_kdiff = sum(a['kdiff'] for a in org_agg.values())
    tot_kmdiff = sum(a['kmdiff'] for a in org_agg.values())
    tot_ks = sum(a['ks'] for a in org_agg.values())
    kavg_t = round(tot_ks / tot['kn'], 1) if tot['kn'] else None
    tier_t, tgap_t = score_tier(kavg_t)
    wrow(ws0, i, ['皖闽浙合计', '', tot['kn'], tot['kok'],
                  kavg_t if kavg_t is not None else '-', tier_t, tgap_t,
                  tot['kr70'], tot['kr5070'], tot['kr50'], round(tot_kdiff, 1), round(tot_kmdiff, 1)],
         bold=True, fill='DCE6F1', tier_col=6)
    dc = ws0.cell(row=i, column=11)
    dc.font = Font(bold=True, color='137333' if tot_kdiff > 0 else ('C5221F' if tot_kdiff < 0 else '000000'))
    dc.number_format = '+0.0;-0.0;0'
    mc = ws0.cell(row=i, column=12)
    mc.font = Font(bold=True, color='137333' if tot_kmdiff > 0 else ('C5221F' if tot_kmdiff < 0 else '000000'))
    mc.number_format = '+0.0;-0.0;0'
    ws0.row_dimensions[i].height = 22
    for j, w in enumerate([14, 11, 14, 13, 16, 15, 11, 14, 15, 14, 13, 13], 1):
        ws0.column_dimensions[get_column_letter(j)].width = w

    # 销售维度（2026-10-23英杰：只留重点池口径；样式与组织汇总一致，按代运营商分组但用淡蓝组标题行）
    ws1 = wb.create_sheet('销售维度')
    hdr1 = ['代运营商', '销售姓名', '重点池门店数', '重点池达标', '重点池平均评分', '重点池评分档位', '距上一档', '重点池≥70分', '重点池50-70分', '重点池<50分', '昨日总分变化', '本月总分变化']  # 2026-10-27英杰：加昨日总分变化
    ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr1))
    c = ws1.cell(row=1, column=1, value=f'销售维度（数据日期 {date}）')
    c.font = Font(bold=True, size=18); c.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 34
    for j, h in enumerate(hdr1, 1):
        c = ws1.cell(row=2, column=j, value=h)
        c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
        c.alignment = Alignment(horizontal='center', vertical='center'); c.border = BORDER
    ws1.row_dimensions[2].height = 24
    i = 3
    for org in ORG_ORDER:
        items = sorted([(k[1], v) for k, v in sales_agg.items() if k[0] == org], key=lambda x: -(x[1]['ks'] / x[1]['kn'] if x[1]['kn'] else 0))
        if not items: continue
        wrow(ws1, i, [f'【{org}】'] + [''] * 11, bold=True, fill='DCE6F1', tier_col=6)
        ws1.row_dimensions[i].height = 20
        i += 1
        for sales, b in items:
            kavg = round(b['ks'] / b['kn'], 1) if b['kn'] else None
            tier, tgap = score_tier(kavg)
            wrow(ws1, i, [org, sales, b['kn'], b['kok'],
                          kavg if kavg is not None else '-', tier, tgap,
                          b['kr70'], b['kr5070'], b['kr50'], round(b['kdiff'], 1), round(b['kmdiff'], 1)], tier_col=6)
            dc = ws1.cell(row=i, column=11)
            dc.font = Font(bold=True, color='137333' if b['kdiff'] > 0 else ('C5221F' if b['kdiff'] < 0 else '000000'))
            dc.number_format = '+0.0;-0.0;0'
            mc = ws1.cell(row=i, column=12)
            mc.font = Font(bold=True, color='137333' if b['kmdiff'] > 0 else ('C5221F' if b['kmdiff'] < 0 else '000000'))
            mc.number_format = '+0.0;-0.0;0'
            i += 1
    for j, w in enumerate([14, 12, 14, 13, 16, 15, 11, 14, 15, 14, 13, 13], 1):
        ws1.column_dimensions[get_column_letter(j)].width = w

    # 明细 Sheet（2026-10-22英杰：三档改为 ≥70 / 50-70 / <50，重点池门店）
    for sheet_name, items in [('≥70分门店明细', detail70), ('50-70分门店明细', detail5070), ('50分以下门店明细', detail50)]:
        ws2 = wb.create_sheet(sheet_name)
        hdr2 = ['代运营商', '销售姓名', '门店ID', '门店名称', '品类' if False else '经营评分', '是否重点池', '状态']
        hdr2 = ['代运营商', '销售姓名', '门店ID', '门店名称', '经营评分', '是否重点池', '状态']
        ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr2))
        c = ws2.cell(row=1, column=1, value=f'{sheet_name}（数据日期 {date}，共{len(items)}家）')
        c.font = Font(bold=True, size=14); c.alignment = Alignment(horizontal='center')
        for j, h in enumerate(hdr2, 1):
            c = ws2.cell(row=2, column=j, value=h)
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
            c.alignment = Alignment(horizontal='center')
        for k, (rec, st) in enumerate(items, 3):
            wrow(ws2, k, [rec['org'], rec['sales'], str(rec['shop_id']), rec['name'], rec['score'], '是' if rec['key'] else '否', st or ''])
        for j, w in enumerate([14, 12, 14, 26, 10, 11, 8], 1):
            ws2.column_dimensions[get_column_letter(j)].width = w

    # ===== 2026-10-23英杰新增：全部重点门店经营评分明细 / 日增长明细 / 日下滑明细 =====
    def shop_extra_sheet(ws, title, rows_):
        hdr3 = ['代运营商', '销售姓名', '门店ID', '门店名称', '经营评分', '状态']
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr3))
        c = ws.cell(row=1, column=1, value=f'{title}（数据日期 {date}，共{len(rows_)}家）')
        c.font = Font(bold=True, size=14); c.alignment = Alignment(horizontal='center')
        for j, h in enumerate(hdr3, 1):
            c = ws.cell(row=2, column=j, value=h)
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
            c.alignment = Alignment(horizontal='center')
        for k, (rec, st) in enumerate(rows_, 3):
            wrow(ws, k, [rec['org'], rec['sales'], str(rec['shop_id']), rec['name'], rec['score'], st or ''])
        for j, w in enumerate([14, 12, 14, 26, 10, 10], 1):
            ws.column_dimensions[get_column_letter(j)].width = w

    all_key = sorted([(r, '') for r in recs if r['key']], key=lambda x: -x[0]['score'])
    # 2026-10-27修正：日增长/日下滑用真实昨日对比（_orig_prev_ok_key），delta回退不影响
    growth = [it for it in all_key if it[0]['shop_id'] not in _orig_prev_ok_key and it[0]['score'] >= 70]
    drop = [it for it in all_key if it[0]['shop_id'] in _orig_prev_ok_key and it[0]['score'] < 70]
    shop_extra_sheet(wb.create_sheet('全部重点门店明细'), '全部重点门店经营评分明细', all_key)
    shop_extra_sheet(wb.create_sheet('日增长明细'), '日增长明细（昨日新增达标门店）', growth)
    shop_extra_sheet(wb.create_sheet('日下滑明细'), '日下滑明细（昨日掉标门店）', drop)
    print('extra sheets: all_key=%d growth=%d drop=%d' % (len(all_key), len(growth), len(drop)))

    # ===== 2026-10-27英杰新增：加分门店 / 减分门店明细（重点池，昨日→今日分数差≠0）=====
    up_rows, down_rows = [], []
    for rec in recs:
        if not rec['key']: continue
        pr = prev_shop.get(str(rec['shop_id']))
        if pr is None or pr.get('score') in (None, ''): continue
        try: prev_sc = float(pr.get('score') or 0)
        except Exception: continue
        diff = round(rec['score'] - prev_sc, 1)
        if diff == 0: continue
        item = (dict(rec, prev_score=round(prev_sc, 1), diff=diff), '')
        (up_rows if diff > 0 else down_rows).append(item)
    up_rows.sort(key=lambda x: -x[0]['diff'])
    down_rows.sort(key=lambda x: x[0]['diff'])

    # 2026-10-27保护：Apollo评分源隔日刷新，当日无差异时从库里读最近一次delta行（不生成空Sheet）
    delta_note = ''
    if not up_rows and not down_rows:
        qs = urllib.parse.urlencode({'module': 'eq.score_delta', 'select': 'date,org,salesperson,metrics', 'order': 'date.desc', 'limit': '1'})
        rr = req(BASE, key, '/wmz_sales_detail?' + qs)
        last_d = rr[0]['date'] if rr else None
        if last_d:
            qs2 = urllib.parse.urlencode({'module': 'eq.score_delta', 'date': f'eq.{last_d}', 'select': 'date,org,salesperson,metrics', 'limit': '5000'})
            srows2 = req(BASE, key, '/wmz_sales_detail?' + qs2)
            up_rows, down_rows = [], []
            for r in srows2:
                m = r['metrics'] if isinstance(r['metrics'], dict) else json.loads(r['metrics'] or '{}')
                diff = m.get('diff')
                if diff is None: continue
                rec = dict(org=r['org'], sales=m.get('sales') or '', shop_id=m.get('shop_id'), name=r['salesperson'],
                           prev_score=m.get('prev_score'), score=m.get('score'), diff=diff)
                (up_rows if diff > 0 else down_rows).append((rec, ''))
            up_rows.sort(key=lambda x: -x[0]['diff'])
            down_rows.sort(key=lambda x: x[0]['diff'])
            delta_note = f'（评分源{last_d}快照）'
            print('delta fallback to', last_d, len(up_rows), len(down_rows))

    def delta_sheet(ws, title, rows_):
        hdr4 = ['代运营商', '销售姓名', '门店ID', '门店名称', '昨日评分', '今日评分', '分数变化']
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr4))
        c = ws.cell(row=1, column=1, value=f'{title}（数据日期 {date}，共{len(rows_)}家，昨日→今日分数变化≠0）{delta_note}')
        c.font = Font(bold=True, size=14); c.alignment = Alignment(horizontal='center')
        for j, h in enumerate(hdr4, 1):
            c = ws.cell(row=2, column=j, value=h)
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
            c.alignment = Alignment(horizontal='center'); c.border = BORDER
        for k, (rec, _st) in enumerate(rows_, 3):
            wrow(ws, k, [rec['org'], rec['sales'], str(rec['shop_id']), rec['name'],
                         rec['prev_score'], rec['score'], rec['diff']],
                 fill=avg_scale(rec['diff']) if False else None)
            # 分数变化列色阶：正=绿底 负=红底
            dc = ws.cell(row=k, column=7)
            dc.font = Font(bold=True, color='137333' if rec['diff'] > 0 else 'C5221F')
            dc.number_format = '+0.0;-0.0;0'
        for j, w in enumerate([14, 12, 14, 26, 10, 10, 11], 1):
            ws.column_dimensions[get_column_letter(j)].width = w

    delta_sheet(wb.create_sheet('加分门店'), '加分门店明细（昨日→今日分数上升）', up_rows)
    delta_sheet(wb.create_sheet('减分门店明细'), '减分门店明细（昨日→今日分数下降）', down_rows)
    print('delta sheets: up=%d down=%d' % (len(up_rows), len(down_rows)))

    # ===== 2026-10-27英杰新增：加/减分销售维度（按代运营商+销售聚合）=====
    sd_agg = {}
    for rec, _ in up_rows + down_rows:
        sales = (rec.get('sales') or '').strip()
        if not sales: continue
        k2 = (rec['org'], sales)
        a = sd_agg.setdefault(k2, {'up': 0, 'down': 0, 'delta': 0.0})
        a['delta'] += rec['diff']
        if rec['diff'] > 0: a['up'] += 1
        elif rec['diff'] < 0: a['down'] += 1

    def sd_sales_sheet(ws, rows_):
        hdr = ['代运营商', '销售姓名', '变分门店数', '加分门店', '减分门店', '总变化分']
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr))
        c = ws.cell(row=1, column=1, value=f'加/减分销售维度（数据日期 {date}，共{len(rows_)}人，总变化分={round(sum(r[2] for r in rows_), 1)}）')
        c.font = Font(bold=True, size=14); c.alignment = Alignment(horizontal='center')
        for j, h in enumerate(hdr, 1):
            c = ws.cell(row=2, column=j, value=h)
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
            c.alignment = Alignment(horizontal='center'); c.border = BORDER
        for k, r in enumerate(rows_, 3):
            org, sales, delta, up, down = r
            wrow(ws, k, [org, sales, up + down, up, down, delta])
            dc = ws.cell(row=k, column=6)
            dc.font = Font(bold=True, color='137333' if delta > 0 else ('C5221F' if delta < 0 else '000000'))
            dc.number_format = '+0.0;-0.0;0'
        for j, w in enumerate([14, 12, 12, 10, 10, 11], 1):
            ws.column_dimensions[get_column_letter(j)].width = w

    sd_rows = sorted([(org, sales, round(a['delta'], 1), a['up'], a['down']) for (org, sales), a in sd_agg.items()],
                     key=lambda x: -x[2])
    sd_sales_sheet(wb.create_sheet('加减分销售维度'), sd_rows)
    print('sd sales sheet rows=%d sum=%s' % (len(sd_rows), round(sum(r[2] for r in sd_rows), 1)))

    out = f'/tmp/经营评分分析_皖闽浙_{date}.xlsx'
    wb.save(out)
    print('saved', out, os.path.getsize(out), 'bytes')

    # 入库
    with open(out, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    def rest(path, method='GET', payload=None):
        r = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload else None, method=method)
        r.add_header('apikey', key); r.add_header('Authorization', 'Bearer ' + key)
        r.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(r, timeout=120) as rr:
            t = rr.read().decode()
            return (rr.status, json.loads(t) if t else None)
    qs = urllib.parse.urlencode({'date': f'eq.{date}', 'module': 'eq.score', 'select': 'file_name'})
    exist = rest('/wmz_report_files?' + qs)
    if exist and len(exist) > 0:
        reqd = urllib.request.Request(BASE + '/wmz_report_files?' + qs, method='DELETE')
        reqd.add_header('apikey', key); reqd.add_header('Authorization', 'Bearer ' + key)
        urllib.request.urlopen(reqd, timeout=30)
    payload = [{'date': date, 'module': 'score', 'file_name': f'经营评分分析_皖闽浙_{date}.xlsx',
                'file_path': None, 'file_size': os.path.getsize(out), 'content': content,
                'source': 'backfill_20261006', 'user_id': ''}]
    st, resp = rest('/wmz_report_files', 'POST', payload)
    print('INSERT score file →', st)

if __name__ == '__main__':
    main()
