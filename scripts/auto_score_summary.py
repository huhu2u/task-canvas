#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经营评分汇总自动化（2026-10-05 英杰要求打通）
从 score_stores(8x6q库, fetch_sihai_score.py 每日自动灌) 现算:
  1. wmz_reports module=score 7家汇总行（重点门店数/达标门店数/达标率/平均评分/≥70分占比/<30分门店/日新增达标/日掉标）
  2. wmz_sales_detail module=score 销售维度（门店数/平均评分/达标门店数/达标率/≥70分门店/≥70分占比）
口径: 达标=score≥70（与 gen_score_wmz.py 一致）; 池=score_stores 全量（私海可参与评分门店）
日新增/掉标: 与前一日 score_stores 对比（org+sales 聚合级，达标数差值）
用法: auto_score_summary.py [YYYY-MM-DD]  默认=score_stores 最新 stat_date
挂点: wb_fetch_daily.sh 在 fetch_sihai_score.py 成功后调用
"""
import sys, json, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

# 2026-10-22英杰定稿 → 23:50修正：经营评分档位水位线 = 9月全国代运营商分层「好店经营评分」区间实际最低分
# （初版误用区间平均分+1分，英杰发现P50档最低54.35即入档，修正为各区间最低分实算值）
# 9月分层文件实算（/tmp/9月分层.xlsx，好店经营评分区间×好店经营评分）：
#   P50:    138家  最低54.35（星企动-绍兴乐生活组）
#   P50-80:  81家  最低52.72（南昌吉运星照-无锡宜兴组）
#   P80-90:  27家  最低52.00（珠海市斗门区联联-福州福清组）
#   P90:     29家  最低49.44（无锡微芒智软-苏州张家港组）
SCORE_TIERS = [('P50', 54.35), ('P50-80', 52.72), ('P80-90', 52.0), ('P90', 49.44)]  # (档位, 水位线=9月该区间实际最低分)

def score_tier(avg):
    """按重点池平均分套档位；返回 (档位名, 距上一档还差几分, 低于P90线?)"""
    if avg is None or avg == '':
        return (None, None, False)
    avg = float(avg)
    for i, (name, line) in enumerate(SCORE_TIERS):
        if avg >= line:
            nxt = SCORE_TIERS[i - 1][1] if i > 0 else None  # 上一档水位线
            gap = round(nxt - avg, 1) if nxt is not None else 0.0
            return (name, gap, False)
    # 低于 P90 档水位线
    return ('低于P90', round(SCORE_TIERS[-1][1] - avg, 1), True)

WS = '/root/.openclaw/workspace'
KEY8 = open('/tmp/.supa_key').read().strip()
URL8 = 'https://dbcli-8x6qvevf5kpmur91.database.sankuai.com/rest/v1'
KEY = open('/tmp/.wb_key').read().strip()
URL = 'https://dbcli-el9byiqifrr7yh4c.database.sankuai.com/rest/v1'

def req(base, method, path, body=None):
    hdrs = {'apikey': KEY8 if base == URL8 else KEY,
            'Authorization': 'Bearer ' + (KEY8 if base == URL8 else KEY),
            'Content-Type': 'application/json'}
    r = urllib.request.Request(base + path, data=json.dumps(body).encode() if body else None,
                               headers=hdrs, method=method)
    return json.loads(urllib.request.urlopen(r, timeout=60).read() or b'[]')

def q8(path):
    # 2026-10-24修复：翻页必须加稳定排序，否则行漂移导致重复/漏行
    if 'order=' not in path:
        path = path + ('&order=shop_id.asc' if 'shop_id' in path else '&order=id.asc')
    rows, off = [], 0
    while True:
        b = req(URL8, 'GET', f'{path}&limit=1000&offset={off}')
        rows.extend(b)
        if len(b) < 1000: break
        off += 1000
    return rows

def orgfix(s):
    s = str(s or '').strip()
    if '代优' in s: return '上海代优'  # 2026-10-06英杰定稿:小花猫退场,展示为上海代优
    for k in ['义乌汐洋', '慈溪哲光', '上海代优', '惠安广通', '仙居烁果', '绍兴星企动']:
        if k in s: return k
    if '小花猫' in s: return '上海代优'
    if '汐洋' in s: return '义乌汐洋'
    if '哲光' in s: return '慈溪哲光'
    if '广通' in s: return '惠安广通'
    if '烁果' in s: return '仙居烁果'
    if '星企动' in s: return '绍兴星企动'
    if '知了' in s: return '芜湖知了'   # 皖闽浙内知了统一展示为芜湖知了(扬州知了归苏浙群)
    return None

SALES_ORG = {}  # sales_name -> org, 从 cpc_stores(8x6q) 或 cpc_daily_archive 建
def load_sales_map(date):
    # 优先 cpc_daily_archive（销售工号名称→业绩归属组织）
    import pandas as pd, os
    p = f'{WS}/data/cpc_daily_archive/{date}.xlsx'
    if not os.path.exists(p):
        # 回退最近一份
        import glob
        cands = sorted(glob.glob(f'{WS}/data/cpc_daily_archive/*.xlsx'))
        if cands: p = cands[-1]
    if os.path.exists(p):
        df = pd.read_excel(p)
        for _, r in df.iterrows():
            s = str(r.get('销售工号名称') or '').strip()
            o = orgfix(str(r.get('业绩归属组织名称') or '').split('-')[0])
            if s and o and s != 'nan': SALES_ORG[s] = o
    return len(SALES_ORG)

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        rows = q8('/score_stores?select=stat_date&order=stat_date.desc&limit=1')
        date = rows[0]['stat_date'] if rows else None
    if not date:
        print('no score_stores data'); sys.exit(1)
    print('score date:', date)
    prev_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')

    nmap = load_sales_map(date)
    print('sales map size:', nmap)

    rows = q8(f'/score_stores?stat_date=eq.{date}&select=shop_id,store_name,org_name,sales_name,score,is_target')
    print('score_stores rows:', len(rows))

    # 2026-10-27保护：Apollo评分源隔日刷新——若今日与昨日分数完全一致（源未刷新分），
    # 「昨日总分变化/日新增/日掉标/加减分明细」回退用最近一个有变化的日期对。
    # 主表（达标数/平均分/档位等）仍用今日真实数据。
    prows = q8(f'/score_stores?stat_date=eq.{prev_date}&select=shop_id,store_name,org_name,sales_name,score,is_target')
    # 2026-10-27英杰：本月总分变化（vs 当月1日基数；库里若没有1日就用最早有数据的日期）
    month_base_date = f"{date[:8]}01"
    mrows_chk = q8(f'/score_stores?stat_date=eq.{month_base_date}&select=shop_id&limit=1')
    if not mrows_chk:
        _alld = q8('/score_stores?select=stat_date&order=stat_date.asc&limit=1')
        if _alld and _alld[0]['stat_date'] >= month_base_date:
            month_base_date = _alld[0]['stat_date']
        else:
            month_base_date = None
    if month_base_date:
        mrows = q8(f'/score_stores?stat_date=eq.{month_base_date}&select=shop_id,store_name,org_name,sales_name,score,is_target')
        print(f'month base: {month_base_date} rows={len(mrows)}')
    else:
        mrows = []
        print('month base: none')
    _tm = {str(r.get('shop_id')): r.get('score') for r in rows}
    _same = all(_tm.get(str(r.get('shop_id'))) == r.get('score') for r in prows if str(r.get('shop_id')) in _tm) and prows
    _orig_prows = prows  # 真实昨日，growth/drop对比用（源未刷新时也无变化，保持一致）
    if _same:
        import datetime as _dt
        d_cur = _dt.datetime.strptime(prev_date, '%Y-%m-%d')
        for back in range(1, 10):
            d_p = (d_cur - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
            d_pp = (d_cur - _dt.timedelta(days=back + 1)).strftime('%Y-%m-%d')
            r_p = q8(f'/score_stores?stat_date=eq.{d_p}&select=shop_id,score&limit=20000')
            r_pp = q8(f'/score_stores?stat_date=eq.{d_pp}&select=shop_id,score&limit=20000')
            if not r_p or not r_pp: continue
            mp = {str(x.get('shop_id')): x.get('score') for x in r_p}
            if any(mp.get(str(x.get('shop_id'))) != x.get('score') for x in r_pp if str(x.get('shop_id')) in mp):
                prows = q8(f'/score_stores?stat_date=eq.{d_p}&select=shop_id,store_name,org_name,sales_name,score,is_target')
                print(f'source not refreshed; delta pair fallback: {d_pp} -> {d_p}')
                break
    # 2026-10-27英杰：昨日总分变化（门店级对比昨日快照，重点池口径）——看销售有没有做工
    prev_shop = {}
    for r in prows:
        prev_shop[str(r.get('shop_id'))] = r
    month_shop = {}
    for r in mrows:
        month_shop[str(r.get('shop_id'))] = r
    # 聚合 org 级 + (org,sales) 级 — 双口径：全量(all) + 重点门店池(key, is_target=1)（2026-10-05英杰口径）
    # 2026-10-22英杰：新增区间分布（≥70 / 50-70 / <50）双口径 + 重点池平均分档位（9月全国水位线+1分）
    org_agg = defaultdict(lambda: {'n': 0, 's': 0.0, 'ok': 0, 'low': 0, 'kn': 0, 'ks': 0.0, 'kok': 0, 'klow': 0,
                                   'r70': 0, 'r5070': 0, 'r50': 0, 'kr70': 0, 'kr5070': 0, 'kr50': 0, 'kdiff': 0.0, 'kmdiff': 0.0})
    sales_agg = defaultdict(lambda: {'n': 0, 's': 0.0, 'ok': 0, 'kn': 0, 'ks': 0.0, 'kok': 0,
                                     'r70': 0, 'r5070': 0, 'r50': 0, 'kr70': 0, 'kr5070': 0, 'kr50': 0, 'kdiff': 0.0, 'kmdiff': 0.0})
    has_key_flag = any(r.get('is_target') not in (None, '', 0, '0') for r in rows)
    for r in rows:
        sales = (r.get('sales_name') or '').strip()
        org = orgfix(r.get('org_name') or '') or SALES_ORG.get(sales)
        if not org: continue
        sc = float(r.get('score') or 0)
        is_key = r.get('is_target') in (1, '1', True)
        # 昨日分数（门店级，重点池口径计算总分变化）
        prev_sc = None
        pr = prev_shop.get(str(r.get('shop_id')))
        if pr is not None and pr.get('score') not in (None, ''):
            try: prev_sc = float(pr.get('score') or 0)
            except Exception: prev_sc = None
        a = org_agg[org]; a['n'] += 1; a['s'] += sc
        if sc >= 70: a['ok'] += 1
        if sc < 30: a['low'] += 1
        # 区间分布（全量口径）：≥70 / 50-70 / <50
        if sc >= 70: a['r70'] += 1
        elif sc >= 50: a['r5070'] += 1
        else: a['r50'] += 1
        mr = month_shop.get(str(r.get('shop_id')))
        msc = None
        if mr is not None and mr.get('score') not in (None, ''):
            try: msc = float(mr.get('score') or 0)
            except Exception: msc = None
        if is_key:
            a['kn'] += 1; a['ks'] += sc
            if prev_sc is not None: a['kdiff'] += sc - prev_sc
            if msc is not None: a['kmdiff'] += sc - msc
            if sc >= 70: a['kok'] += 1
            if sc < 30: a['klow'] += 1
            if sc >= 70: a['kr70'] += 1
            elif sc >= 50: a['kr5070'] += 1
            else: a['kr50'] += 1
        if sales:
            b = sales_agg[(org, sales)]; b['n'] += 1; b['s'] += sc
            if sc >= 70: b['ok'] += 1
            if sc >= 70: b['r70'] += 1
            elif sc >= 50: b['r5070'] += 1
            else: b['r50'] += 1
            if is_key:
                b['kn'] += 1; b['ks'] += sc
                if prev_sc is not None: b['kdiff'] += sc - prev_sc
                if msc is not None: b['kmdiff'] += sc - msc
                if sc >= 70: b['kok'] += 1
                if sc >= 70: b['kr70'] += 1
                elif sc >= 50: b['kr5070'] += 1
                else: b['kr50'] += 1

    # 前一日对比（org级达标数，双口径）
    prev = {}
    prev_key = {}
    for r in prows:
        sales = (r.get('sales_name') or '').strip()
        org = orgfix(r.get('org_name') or '') or SALES_ORG.get(sales)
        if not org: continue
        sc = float(r.get('score') or 0)
        if sc >= 70: prev[org] = prev.get(org, 0) + 1
        if r.get('is_target') in (1, '1', True) and sc >= 70:
            prev_key[org] = prev_key.get(org, 0) + 1
    have_prev = bool(prows)
    print('prev date rows:', len(prows))

    # org 汇总行 → wmz_reports（双口径：全量列 + 重点池列）
    out = []
    for org, a in org_agg.items():
        ok_today, ok_prev = a['ok'], prev.get(org, 0)
        kok_today, kok_prev = a['kok'], prev_key.get(org, 0)
        met = {'重点门店数': a['n'], '达标门店数': a['ok'],
               '达标率': round(a['ok'] / a['n'], 4) if a['n'] else 0,
               '平均评分': round(a['s'] / a['n'], 1) if a['n'] else 0,
               '≥70分占比': round(a['ok'] / a['n'], 4) if a['n'] else 0,
               '<30分门店': a['low'],
               '日新增达标': (a['ok'] - ok_prev) if have_prev else None,
               '日掉标': (ok_prev - a['ok']) if have_prev else None}
        if has_key_flag:
            kavg = round(a['ks'] / a['kn'], 1) if a['kn'] else None
            tier, tgap, below = score_tier(kavg)
            met.update({'重点池门店数': a['kn'], '重点池达标门店数': a['kok'],
                        '重点池达标率': round(a['kok'] / a['kn'], 4) if a['kn'] else 0,
                        '重点池平均评分': kavg,
                        '重点池评分档位': tier,
                        '距上一档': tgap,
                        '重点池日新增达标': (a['kok'] - kok_prev) if have_prev else None,
                        '重点池日掉标': (kok_prev - a['kok']) if have_prev else None,
                        '重点池昨日总分变化': round(a['kdiff'], 1) if have_prev else None,
                        '重点池本月总分变化': round(a['kmdiff'], 1) if month_shop else None})
        # 区间分布（全量口径，英杰 2026-10-22：双维度保留全量 + 重点主看平均分）
        met.update({'≥70分门店': a['r70'], '50-70分门店': a['r5070'], '50分以下门店': a['r50']})
        if has_key_flag:
            met.update({'重点池≥70分门店': a['kr70'], '重点池50-70分门店': a['kr5070'],
                        '重点池50分以下门店': a['kr50']})
        out.append({'date': date, 'module': 'score', 'org': org, 'metrics': met, 'user_id': ''})
    print('org rows:', len(out))
    for o in out:
        print(' ', o['org'], o['metrics']['达标门店数'], '/', o['metrics']['重点门店数'],
              '| 重点池:', o['metrics'].get('重点池达标门店数'), '/', o['metrics'].get('重点池门店数'))

    # 销售维度 → wmz_sales_detail
    srows = []
    for (org, sales), b in sales_agg.items():
        met = {'门店数': b['n'], '平均评分': round(b['s'] / b['n'], 1) if b['n'] else 0,
               '达标门店数': b['ok'], '达标率': round(b['ok'] / b['n'], 4) if b['n'] else 0,
               '≥70分门店': b['ok'], '≥70分占比': round(b['ok'] / b['n'], 4) if b['n'] else 0}
        if has_key_flag and b['kn']:
            kavg = round(b['ks'] / b['kn'], 1) if b['kn'] else None
            tier, tgap, below = score_tier(kavg)
            met.update({'重点池门店数': b['kn'], '重点池达标门店数': b['kok'],
                        '重点池达标率': round(b['kok'] / b['kn'], 4) if b['kn'] else 0,
                        '重点池平均评分': kavg,
                        '重点池评分档位': tier,
                        '距上一档': tgap,
                        '重点池昨日总分变化': round(b['kdiff'], 1) if have_prev else None,
                        '重点池本月总分变化': round(b['kmdiff'], 1) if month_shop else None})
        # 区间分布（销售维度，2026-10-22英杰：重点池主看平均分，下钻销售）
        met.update({'≥70分门店': b['r70'], '50-70分门店': b['r5070'], '50分以下门店': b['r50']})
        if has_key_flag and b['kn']:
            met.update({'重点池≥70分门店': b['kr70'], '重点池50-70分门店': b['kr5070'],
                        '重点池50分以下门店': b['kr50']})
        srows.append({'date': date, 'module': 'score', 'org': org, 'salesperson': sales,
                      'metrics': met, 'user_id': ''})
    print('sales rows:', len(srows))

    # 2026-10-22英杰：门店级明细（重点池三档：≥70 / 50-70 / <50），下钻代运营商→销售用
    # 入库 wmz_sales_detail module='score_shop'，salesperson=门店名，metrics含档位/销售/评分/shop_id
    sshop = []
    for r in rows:
        if r.get('is_target') not in (1, '1', True): continue
        sales = (r.get('sales_name') or '').strip()
        org = orgfix(r.get('org_name') or '') or SALES_ORG.get(sales)
        if not org: continue
        sc = float(r.get('score') or 0)
        band = '≥70分' if sc >= 70 else ('50-70分' if sc >= 50 else '50分以下')
        sshop.append({'date': date, 'module': 'score_shop', 'org': org,
                      'salesperson': r.get('store_name') or str(r.get('shop_id') or ''),
                      'metrics': {'band': band, 'score': round(sc, 1),
                                  'sales': sales, 'shop_id': r.get('shop_id'),
                                  'score_ok': sc >= 70},
                      'user_id': ''})
    print('score_shop rows:', len(sshop))

    # 2026-10-27英杰：加/减分门店明细（重点池，昨日→今日分数差≠0），入库 module='score_delta'
    # metrics: diff(正=加分,负=减分)/score/prev_score/sales/shop_id
    sdelta = []
    for r in rows:
        if r.get('is_target') not in (1, '1', True): continue
        pr = prev_shop.get(str(r.get('shop_id')))
        if pr is None or pr.get('score') in (None, ''): continue
        try: prev_sc = float(pr.get('score') or 0)
        except Exception: continue
        sales = (r.get('sales_name') or '').strip()
        org = orgfix(r.get('org_name') or '') or SALES_ORG.get(sales)
        if not org: continue
        sc = float(r.get('score') or 0)
        diff = round(sc - prev_sc, 1)
        if diff == 0: continue
        sdelta.append({'date': date, 'module': 'score_delta', 'org': org,
                       'salesperson': r.get('store_name') or str(r.get('shop_id') or ''),
                       'metrics': {'diff': diff, 'score': round(sc, 1), 'prev_score': round(prev_sc, 1),
                                   'sales': sales, 'shop_id': r.get('shop_id')},
                       'user_id': ''})
    sdelta.sort(key=lambda x: -x['metrics']['diff'])
    print('score_delta rows:', len(sdelta), '(up', sum(1 for x in sdelta if x['metrics']['diff'] > 0), '/ down', sum(1 for x in sdelta if x['metrics']['diff'] < 0), ')')

    # 2026-10-27英杰：加/减分销售维度聚合（module='score_delta_sales'）
    # 按代运营商+销售聚合：加分门店数/减分门店数/总变化分
    agg = {}
    for x in sdelta:
        sales = (x['metrics'].get('sales') or '').strip()
        if not sales: continue
        k2 = (x['org'], sales)
        a = agg.setdefault(k2, {'up': 0, 'down': 0, 'delta': 0.0})
        a['delta'] += x['metrics']['diff']
        if x['metrics']['diff'] > 0: a['up'] += 1
        elif x['metrics']['diff'] < 0: a['down'] += 1
    sdsales = []
    for (org, sales), a in agg.items():
        sdsales.append({'date': date, 'module': 'score_delta_sales', 'org': org,
                        'salesperson': sales,
                        'metrics': {'up': a['up'], 'down': a['down'],
                                    'delta': round(a['delta'], 1),
                                    'total': a['up'] + a['down']},
                        'user_id': ''})
    sdsales.sort(key=lambda x: -x['metrics']['delta'])
    print('score_delta_sales rows:', len(sdsales))

    # 写库（先删后插）
    req(URL, 'DELETE', f'/wmz_reports?date=eq.{date}&module=eq.score')
    for i in range(0, len(out), 10):
        req(URL, 'POST', '/wmz_reports', out[i:i+10])
    req(URL, 'DELETE', f'/wmz_sales_detail?date=eq.{date}&module=eq.score')
    for i in range(0, len(srows), 20):
        req(URL, 'POST', '/wmz_sales_detail', srows[i:i+20])
    req(URL, 'DELETE', f'/wmz_sales_detail?date=eq.{date}&module=eq.score_shop')
    for i in range(0, len(sshop), 50):
        req(URL, 'POST', '/wmz_sales_detail', sshop[i:i+50])
    # 2026-10-27保护：Apollo评分源隔日刷新，若当日两日分数无差异（delta=0），
    # 不清空已入库的delta行（保留上一个有变化日期的数据），避免看板加/减分面板变空
    if sdelta:
        req(URL, 'DELETE', f'/wmz_sales_detail?date=eq.{date}&module=eq.score_delta')
        for i in range(0, len(sdelta), 50):
            req(URL, 'POST', '/wmz_sales_detail', sdelta[i:i+50])
        req(URL, 'DELETE', f'/wmz_sales_detail?date=eq.{date}&module=eq.score_delta_sales')
        for i in range(0, len(sdsales), 50):
            req(URL, 'POST', '/wmz_sales_detail', sdsales[i:i+50])
    else:
        print('score_delta empty (source not refreshed), keep previous rows')
    print('DONE score summary', date, 'org', len(out), 'sales', len(srows), 'shop', len(sshop), 'delta', len(sdelta))

if __name__ == '__main__':
    main()
