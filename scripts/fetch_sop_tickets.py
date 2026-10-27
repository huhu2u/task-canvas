#!/opt/pyenv/bin/python3
# -*- coding: utf-8 -*-
"""
fetch_sop_tickets.py — 通用工具(tpt.sankuai.com)MEM工单数据抓取 → wb库
2026-10-27英杰定稿v3：口径改成李俊报表口径（「MEM到期门店拜访」单任务进度）
  只统计 displayByTask 中 taskName 含「MEM到期门店拜访」的任务（每月任务名会变，关键词匹配）
  完成进度 = committed/valid（该任务内）
  v2口径（全量7任务处理率）已废弃
用法: fetch_sop_tickets.py [date=今天] [--preview]
依赖: agent-browser（已登录tpt页面）
入库: wmz_reports module='sop'（组织级聚合）+ wmz_sales_detail module='sop_sales'（销售级明细）
"""
import json, subprocess, sys, time, datetime, os
from collections import Counter, defaultdict

AB = '/opt/nvm/versions/node/v24.14.0/bin/agent-browser'
AB_DIR = '/root/.openclaw/workspace/tmp'
TPT_URL = 'https://tpt.sankuai.com/new-sop-client/frame.html#/worksheet/subordinate/list'
ORG_L8 = '20903327'   # 高线皖闽浙城市群
WS = '/root/.openclaw/workspace'
API = '/sop/api/v1/data/itemStatisticsSearch'

def sh(expr):
    r = subprocess.run([AB, 'eval', expr], capture_output=True, text=True, cwd=AB_DIR)
    out = (r.stdout or '').strip()
    if not out:
        out = (r.stderr or '').strip()
    return out

def ensure_page():
    on = sh("location.href.indexOf('tpt.sankuai.com')>=0?'onpage':'off'")
    if 'onpage' not in on:
        subprocess.run([AB, 'open', TPT_URL], capture_output=True, cwd=AB_DIR)
        time.sleep(8)
        on = sh("location.href.indexOf('tpt.sankuai.com')>=0?'onpage':'off'")
        if 'onpage' not in on:
            raise RuntimeError('agent-browser 不在 tpt 页面上（需人工登录）')

def fetch_stats(month, org_level='lowerOneLayer', task_ids=None):
    """调 itemStatisticsSearch，返回 rows 列表"""
    body = {"beginTime": f"{month}-01 00:00:00", "endTime": f"{month}-31 23:59:59",
            "orgId": ORG_L8, "orgIds": [f"o{ORG_L8}"], "dataType": "itemStatistics",
            "selectTimePrefix": "create", "orgIdType": "o", "queryType": 2, "taskIdList": task_ids or [],
            "displayByTask": False, "handleType": "", "feedbackQueryType": None,
            "dataPriority": "", "taskTagIdList": [], "timeType": "month",
            "pageOrgId": int(ORG_L8), "pageOrgIdType": "o", "pageOrgIds": [f"o{ORG_L8}"],
            "pageSize": None, "pageNum": None, "orgLevel": org_level}
    var = f'__sopStat{org_level}{"" if not task_ids else "T"}'
    expr = ("(function(){return fetch('" + API + "',{method:'POST',credentials:'include',"
            "headers:{'Content-Type':'application/json'},body:JSON.stringify(" +
            json.dumps(body) + ")}).then(function(r){return r.text()}).then(function(t){window." +
            var + "=t;return t.length})})()")
    sh(expr)
    time.sleep(0.5)
    raw = fetch_var(var)
    d = json.loads(raw)
    if not d.get('data') or not d['data'].get('datas'):
        raise RuntimeError(f'itemStatisticsSearch 无数据: {raw[:200]}')
    return d['data']['datas']

def fetch_task_ids(month):
    """找当月「MEM到期门店拜访」任务的 taskId（displayByTask全量任务列表里关键词匹配）"""
    body = {"beginTime": f"{month}-01 00:00:00", "endTime": f"{month}-31 23:59:59",
            "orgId": ORG_L8, "orgIds": [f"o{ORG_L8}"], "dataType": "itemStatistics",
            "selectTimePrefix": "create", "orgIdType": "o", "queryType": 2, "taskIdList": [],
            "displayByTask": True, "handleType": "", "feedbackQueryType": None,
            "dataPriority": "", "taskTagIdList": [], "timeType": "month",
            "pageOrgId": int(ORG_L8), "pageOrgIdType": "o", "pageOrgIds": [f"o{ORG_L8}"],
            "pageSize": None, "pageNum": None, "orgLevel": ""}
    expr = ("(function(){return fetch('" + API + "',{method:'POST',credentials:'include',"
            "headers:{'Content-Type':'application/json'},body:JSON.stringify(" +
            json.dumps(body) + ")}).then(function(r){return r.text()}).then(function(t){window.__sopTasks=t;return t.length})})()")
    sh(expr)
    time.sleep(0.5)
    raw = fetch_var('__sopTasks')
    d = json.loads(raw)
    rows = d['data']['datas'] or []
    ids = list({r['taskId'] for r in rows if 'MEM到期门店拜访' in (r.get('taskName') or '')})
    names = [r.get('taskName') for r in rows if 'MEM到期门店拜访' in (r.get('taskName') or '')]
    return ids, names

def fetch_var(fn):
    total = int(json.loads(sh(f'JSON.stringify({fn}.length)')))
    chunks = []
    off = 0
    while off < total:
        end = min(off + 4000, total)
        seg_raw = sh(f'JSON.stringify({fn}.slice({off},{end}))')
        seg = json.loads(seg_raw)
        if isinstance(seg, str):
            seg = json.loads(seg)
        chunks.append(seg)
        off = end
    return ''.join(chunks)

# 子组名 → 看板代运营商（与 ORG_MAP 口径一致：花猫已汰并入上海代优）
GROUP_MAP = [
    ('小花猫', '上海代优'), ('代优', '上海代优'),            # 泉州两组合并上海代优
    ('广通', '惠安广通'), ('哲光', '慈溪哲光'), ('汐洋', '义乌汐洋'),
    ('烁果', '仙居烁果'), ('星企动', '绍兴星企动'), ('知了', '芜湖知了'),
]
def groupfix(name):
    if not name: return None
    for k, v in GROUP_MAP:
        if k in name: return v
    return None

ORG_ORDER = ['上海代优', '慈溪哲光', '义乌汐洋', '惠安广通', '芜湖知了', '绍兴星企动', '仙居烁果']

def main():
    date = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        date = sys.argv[1]
    preview = '--preview' in sys.argv
    if not date:
        date = datetime.date.today().isoformat()
    month = date[:7]

    ensure_page()
    print(f'== 抓取 {month} 皖闽浙 MEM拜访任务进度（李俊口径 v3）==')

    # 0) 找 MEM到期门店拜访 任务 taskId
    task_ids, task_names = fetch_task_ids(month)
    if not task_ids:
        raise RuntimeError('未找到「MEM到期门店拜访」任务（displayByTask 里无匹配）')
    print(f'  任务: {task_names} taskId={task_ids}')

    # 组织级：10个子组（lowerOneLayer，限任务内）
    org_rows_raw = fetch_stats(month, 'lowerOneLayer', task_ids)
    print(f'  子组数: {len(org_rows_raw)}')
    # 销售级（lowerTwoLayer，限任务内）
    sales_rows_raw = fetch_stats(month, 'lowerTwoLayer', task_ids)
    print(f'  销售数: {len(sales_rows_raw)}')

    # 销售名 → 子组映射（销售行的 orgNameList[6] 是直属子组全路径最后一级）
    # 销售行没有直属子组字段，但 orgNameList 是全路径 [..., 高线区域, 城市群, 子组]；销售挂在子组下时路径含子组
    # 实测 lowerTwoLayer 行 orgName 是销售本人，orgNameList 倒数第2层=所属子组
    def parent_group(r):
        path = r.get('orgNameList') or []
        # 从后往前找第一个能 map 到代运营商的层
        for seg in reversed(path):
            g = groupfix(seg)
            if g:
                return g
        return None

    # ===== 组织级聚合（10子组 → 7家代运营商）=====
    org_agg = defaultdict(lambda: Counter())
    group_detail = defaultdict(list)  # 代运营商 -> 子组raw行（保留子组名）
    for r in org_rows_raw:
        g = groupfix(r['orgName'])
        if not g:
            print(f'  ⚠️ 子组未映射: {r["orgName"]}')
            continue
        org_agg[g]['total'] += r['total']
        org_agg[g]['valid'] += r['valid']
        org_agg[g]['committed'] += r['committed']
        org_agg[g]['pending'] += r['pending']
        org_agg[g]['uncommit'] += r['uncommit']
        org_agg[g]['expire'] += r['expire']
        org_agg[g]['checkSuccess'] += r['checkSuccess']
        group_detail[g].append(r)

    # 时间进度：当月已过天数比例
    d = datetime.date.fromisoformat(date)
    ndays = (datetime.date(d.year, 12 if d.month == 12 else d.month + 1, 1) - datetime.date(d.year, d.month, 1)).days
    tprog = d.day / ndays * 100

    rows = []
    tot = Counter()
    for org in ORG_ORDER:
        c = org_agg.get(org)
        if not c:
            c = Counter()
        tot.update(c)
        valid = c['valid']
        rate = c['committed'] / valid * 100 if valid else None
        m = {'有效工单': valid, '已处理': c['committed'], '处理率': round(rate, 1) if rate is not None else None,
             '待处理': c['pending'], '未提交': c['uncommit'], '已过期': c['expire'],
             '工单总数': c['total'], '时间进度': round(tprog, 1),
             '处理率vs时间进度': round((rate or 0) - tprog, 1)}
        rows.append((org, m))
    valid_t = tot['valid']
    m = {'有效工单': valid_t, '已处理': tot['committed'],
         '处理率': round(tot['committed'] / valid_t * 100, 1) if valid_t else None,
         '待处理': tot['pending'], '未提交': tot['uncommit'], '已过期': tot['expire'],
         '工单总数': tot['total'], '时间进度': round(tprog, 1),
         '处理率vs时间进度': round(tot['committed'] / max(1, valid_t) * 100 - tprog, 1)}
    rows.append(('皖闽浙合计', m))

    print(f"{'代运营商':<8} 总数 有效 已处理 完成率% 待处理 未提交 已过期")
    for org, m in rows:
        print(f"{org:<8} {m['工单总数']:>4} {m['有效工单']:>4} {m['已处理']:>4} {str(m['处理率']):>6} {m['待处理']:>4} {m['未提交']:>4} {m['已过期']:>4}")

    if preview:
        return

    # ===== 销售级明细 =====
    sales_rows = []
    unmapped = Counter()
    for r in sales_rows_raw:
        g = parent_group(r)
        if not g:
            unmapped[r['orgName']] += 1
            continue
        valid = r['valid']
        sales_rows.append({'org': g, 'salesperson': r['orgName'], 'metrics': {
            '有效工单': valid, '已处理': r['committed'],
            '处理率': round(r['committed'] / valid * 100, 1) if valid else None,
            '待处理': r['pending'], '未提交': r['uncommit'], '已过期': r['expire'], '工单总数': r['total']}})
    if unmapped:
        print('  ⚠️ 销售未映射子组:', dict(unmapped))

    # ===== 入库 =====
    key = None
    for p in ['/tmp/.wb_key', f'{WS}/scripts/.wb_key']:
        if os.path.exists(p):
            key = open(p).read().strip(); break
    if not key:
        print('无 wb_key，跳过入库'); return
    import urllib.request

    def post(table, payload):
        url = f'https://dbcli-el9byiqifrr7yh4c.database.sankuai.com/rest/v1/{table}'
        r = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST')
        r.add_header('apikey', key); r.add_header('Authorization', 'Bearer ' + key)
        r.add_header('Content-Type', 'application/json'); r.add_header('Prefer', 'return=minimal')
        urllib.request.urlopen(r, timeout=60)

    def delete_module(table, module):
        url = f'https://dbcli-el9byiqifrr7yh4c.database.sankuai.com/rest/v1/{table}?date=eq.{date}&module=eq.{module}'
        rq = urllib.request.Request(url, method='DELETE')
        rq.add_header('apikey', key); rq.add_header('Authorization', 'Bearer ' + key)
        rq.add_header('Prefer', 'return=minimal')
        urllib.request.urlopen(rq, timeout=60)

    # 组织级
    delete_module('wmz_reports', 'sop')
    post('wmz_reports', [{'date': date, 'module': 'sop', 'org': org, 'metrics': m} for org, m in rows if org != '皖闽浙合计'])
    post('wmz_reports', [{'date': date, 'module': 'sop', 'org': '皖闽浙城市群', 'metrics': m} for org, m in rows if org == '皖闽浙合计'])
    # 销售级
    delete_module('wmz_sales_detail', 'sop_sales')
    if sales_rows:
        post('wmz_sales_detail', [{'date': date, 'module': 'sop_sales', **s} for s in sales_rows])
    print(f'入库完成: wmz_reports sop {len(rows)-1}家+合计 | wmz_sales_detail sop_sales {len(sales_rows)}销售')

if __name__ == '__main__':
    main()
