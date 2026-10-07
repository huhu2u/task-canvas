#!/usr/bin/env python3
"""皖闽浙拜访门店覆盖率分析 - 按代运营商+销售维度下钻（2026-09-09首版）
覆盖率口径：本月拜访过（有效拜访）的池内门店数 / 私海重点池门店数（shopId匹配）
"""
import sys
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

VISIT_FILE = sys.argv[1]
POOL_FILE = '/root/.openclaw/workspace/data/haodian_pool.xlsx'
OUT = sys.argv[2]

ALL7 = {'知了': '芜湖知了', '小花猫': '上海代优', '星企动': '绍兴星企动', '哲光': '慈溪哲光',
        '汐洋': '义乌汐洋', '广通': '惠安广通', '烁果': '仙居烁果'}
BOSS = {'芜湖知了': '陈具礼', '上海代优': '代永安', '绍兴星企动': '李晓锋', '慈溪哲光': '孙浩',
        '义乌汐洋': '陈铨', '惠安广通': '尤云生', '仙居烁果': '邱伯达'}

# 2026-10-07英杰指令：上海代优拜访展示中删除泉州小花猫时期的8名老销售
# （池子 haodian_pool 跟进销售未更新，这些人的池内门店保留但不再展示为销售行）
LEGACY_SALES = {'刘洋', '黄伟', '李家兴', '朱玥杰', '郭俊峰', '曾鹏东', '兰思帆', '康子诚'}

pool = pd.read_excel(POOL_FILE)

# 2026-10-07 英杰指令：私海新归属已是最新对应关系——上海代优池内门店的跟进销售改用私海 score_stores 的 ownerSale
# （好店底表还是5月版，跟进销售还是小花猫老销售，已过时）
import json as _json, urllib.request as _ur, urllib.parse as _up
try:
    _key = open('/tmp/.supa_key').read().strip()
    _req = _ur.Request('https://dbcli-8x6qvevf5kpmur91.database.sankuai.com/rest/v1/score_stores?'
                       + _up.urlencode({'stat_date': 'eq.' + (pd.Timestamp('now') - pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
                                       'select': 'shop_id,sales_name', 'limit': '20000'}),
                       headers={'apikey': _key, 'Authorization': 'Bearer ' + _key})
    _si = {str(r['shop_id']): str(r['sales_name']).split('/')[0]
           for r in _json.loads(_ur.urlopen(_req, timeout=60).read()) if r.get('sales_name')}
    _col = next((c for c in pool.columns if '销售' in str(c)), None)
    if _col:
        _fixed = 0
        for _i in pool.index:
            if pool.at[_i, 'op'] == '上海代优' if 'op' in pool else False:
                pass
        # 针对小花猫/代优组织的行，用私海归属覆盖跟进销售
        _mask = pool['组织'].astype(str).str.contains('小花猫|代优')
        for _i in pool[_mask].index:
            _sid = str(pool.at[_i, 'shopId'])
            _new = _si.get(_sid)
            if _new and _new not in ('None', ''):
                pool.at[_i, _col] = _new
                _fixed += 1
        print(f'上海代优池内门店跟进销售已按私海覆盖: {_fixed} 家')
except Exception as _e:
    print('⚠️ 私海销售归属拉取失败，沿用底表跟进销售:', _e)
pool['op'] = pool['组织'].apply(lambda o: next((v for k, v in ALL7.items() if k in str(o)), None))
pp = pool[pool['op'].notna()].copy()
pool_map = dict(zip(pp['shopId'].astype(str), pp['op']))
print(f'私海池: {len(pp)}家')

df = pd.read_excel(VISIT_FILE)
df['shop_id'] = df['门店ID'].astype(str).str.strip()
df['emp'] = df['销售姓名'].astype(str)
df['valid'] = df['是否有效拜访'].apply(lambda x: 1 if x == 1 or x == '1' or x == '是' else 0)
df['signin'] = df['是否签到'].apply(lambda x: 1 if x == 1 or x == '1' or x == '是' else 0)
df['ivr'] = df['是否IVR电话拜访'].apply(lambda x: 1 if x == 1 or x == '1' or x == '是' else 0)
dmin, dmax = df['拜访日期'].astype(str).str[:10].min(), df['拜访日期'].astype(str).str[:10].max()

inpool = df[df['shop_id'].isin(pool_map)].copy()
inpool['op'] = inpool['shop_id'].map(pool_map)
print(f'拜访明细{len(df)}行，池内{len(inpool)}行，{dmin}~{dmax}')

# 有效拜访门店集合（去重）
valid_visits = inpool[inpool['valid'] == 1]
covered = set(valid_visits['shop_id'])
covered_org = valid_visits.groupby('shop_id')['op'].first().to_dict()
covered_emp = valid_visits.groupby('shop_id')['emp'].first().to_dict()

HF = PatternFill('solid', fgColor='1F3864'); HFont = Font(name='宋体', bold=True, color='FFFFFF', size=11)
BF = Font(name='宋体', size=11); TF = PatternFill('solid', fgColor='4D4D4D'); TFont = Font(name='宋体', bold=True, color='FFFFFF', size=11)
GF = PatternFill('solid', fgColor='E07B39'); GFont = Font(name='宋体', bold=True, color='FFFFFF', size=11)
WF = PatternFill('solid', fgColor='FFFFFF'); AF = PatternFill('solid', fgColor='F2F2F2')
BD = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
RC = ['C6EFCE', 'D5F5D5', 'E2F0D9', 'FFF2CC', 'FCE4D6', 'F4B084', 'FFC7CE']

def hdr(ws, n):
    ws.row_dimensions[1].height = 28
    for c in range(1, n + 1):
        cell = ws.cell(1, c); cell.fill = HF; cell.font = HFont
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True); cell.border = BD

def body(ws, nr, nc):
    for r in range(2, nr + 1):
        fill = WF if r % 2 == 0 else AF
        for c in range(1, nc + 1):
            cell = ws.cell(r, c)
            if cell.font.name == 'Calibri': cell.font = BF
            if cell.fill.fgColor.rgb == '00000000': cell.fill = fill
            cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = BD

def width(ws, nc, mx=30, mn=8):
    for c in range(1, nc + 1):
        L = get_column_letter(c); best = mn
        for row in ws.iter_rows(min_col=c, max_col=c, values_only=False):
            v = str(row[0].value or ''); ln = len(v.encode('gbk', 'replace'))
            if ln > best: best = ln
        ws.column_dimensions[L].width = min(best + 4, mx)

wb = Workbook()

# Sheet1 代运营商覆盖率
ws = wb.active; ws.title = '代运营商覆盖率'
h = ['代运营商', '操盘手', '重点池门店数', '已拜访门店数', '门店覆盖率', '覆盖率排名', '有效拜访人次', '人均覆盖门店数']
for c, x in enumerate(h, 1): ws.cell(1, c, x)
rows = []
for op in ALL7.values():
    shops = pp[pp['op'] == op]
    n = len(shops)
    cov = sum(1 for s in shops['shopId'].astype(str) if s in covered)
    visits = len(valid_visits[valid_visits['op'] == op])
    emps = valid_visits[valid_visits['op'] == op]['emp'].nunique()
    rows.append([op, BOSS[op], n, cov, cov / n if n else 0, '', visits, round(cov / emps, 1) if emps else 0])
rows.sort(key=lambda x: -x[4])
for i, r in enumerate(rows): r[5] = i + 1
tp, tc = sum(r[2] for r in rows), sum(r[3] for r in rows)
tot = ['合计', '胡英杰', tp, tc, tc / tp, '-', sum(r[6] for r in rows), '-']
for ri, row in enumerate(rows + [tot], 2):
    for ci, v in enumerate(row, 1): ws.cell(ri, ci, v)
nr = len(rows) + 2; nc = len(h)
hdr(ws, nc); body(ws, nr, nc); width(ws, nc)
for r in range(2, nr + 1):
    c5 = ws.cell(r, 5)
    if isinstance(c5.value, (int, float)): c5.number_format = '0.0%'
for rank, ri in enumerate(range(2, 2 + len(rows))):
    ws.cell(ri, 5).fill = PatternFill('solid', fgColor=RC[min(rank, 6)])
for c in range(1, nc + 1):
    ws.cell(nr, c).fill = TF; ws.cell(nr, c).font = TFont
ws.freeze_panes = 'A2'

# Sheet2 销售维度覆盖率
ws = wb.create_sheet('销售维度覆盖率')
h = ['代运营商', '销售姓名', '池内门店数', '已拜访门店数', '门店覆盖率', '有效拜访人次', '上门拜访', 'IVR电话拜访', '人均单量(次/店)']
for c, x in enumerate(h, 1): ws.cell(1, c, x)
ri = 2
for op in ALL7.values():
    op_shops = pp[pp['op'] == op]
    opd = valid_visits[valid_visits['op'] == op]
    if opd.empty and op_shops.empty: continue
    for c in range(1, len(h) + 1):
        cell = ws.cell(ri, c, op if c == 1 else '')
        cell.fill = GF; cell.font = GFont
        cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = BD
    ri += 1
    # 池内门店归属销售：从私海池"跟进销售"字段
    shop_sales = {}
    col = next((c for c in op_shops.columns if '销售' in str(c)), None)
    if col:
        shop_sales = dict(zip(op_shops['shopId'].astype(str),
                              op_shops[col].astype(str).apply(lambda x: str(x).split('/')[0])))
    all_emps = (set(shop_sales.values()) | set(opd['emp'])) - {'', 'nan', 'None'}
    # 2026-10-07英杰指令：剔除小花猫时期老销售（池子跟进销售未更新）
    all_emps -= LEGACY_SALES
    stats = []
    for s in all_emps:
        if s in ('', 'nan'): continue
        own = [sid for sid, e in shop_sales.items() if e == s]
        n = len(own)
        cov = sum(1 for sid in own if sid in covered)
        sd = opd[opd['emp'] == s]
        visits = len(sd)
        onsite = int((sd['signin'] == 1).sum())
        ivrn = int((sd['ivr'] == 1).sum())
        stats.append([op, s, n, cov, cov / n if n else 0, visits, onsite, ivrn,
                      round(visits / n, 2) if n else 0])
    stats.sort(key=lambda x: -x[4])
    for row in stats:
        for ci, v in enumerate(row, 1):
            cell = ws.cell(ri, ci, v); cell.font = BF
            cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = BD
        ws.cell(ri, 5).number_format = '0.0%'
        ri += 1
hdr(ws, len(h)); width(ws, len(h)); ws.freeze_panes = 'A2'

# Sheet3 未拜访门店明细
ws = wb.create_sheet('未拜访门店明细')
h = ['代运营商', '跟进销售', '门店ID', '商户名', '城市', '星级', '品类']
for c, x in enumerate(h, 1): ws.cell(1, c, x)
uncov = pp[~pp['shopId'].astype(str).isin(covered)].copy()
sales_col = next((c for c in uncov.columns if '销售' in str(c)), None)
sub = uncov.sort_values('op')
for ri, (_, row) in enumerate(sub.iterrows(), 2):
    sn = str(row[sales_col]).split('/')[0] if sales_col else ''
    for ci, v in enumerate([row['op'], sn, row['shopId'], row.get('商户名', '-'),
                            row.get('城市', '-'), row.get('星级', '-'), row.get('品类', '-')], 1):
        ws.cell(ri, ci, v)
hdr(ws, len(h)); body(ws, len(sub) + 1, len(h)); width(ws, len(h), mx=32); ws.freeze_panes = 'A2'

# Sheet4 已拜访门店明细
ws = wb.create_sheet('已拜访门店明细')
h = ['代运营商', '拜访销售', '门店ID', '商户名', '有效拜访次数', '最近拜访日期']
for c, x in enumerate(h, 1): ws.cell(1, c, x)
cov_df = pp[pp['shopId'].astype(str).isin(covered)].copy()
vcount = valid_visits.groupby('shop_id').size().to_dict()
vlast = valid_visits.assign(d=valid_visits['拜访日期'].astype(str).str[:10]).groupby('shop_id')['d'].max().to_dict()
sub = cov_df.sort_values('op')
for ri, (_, row) in enumerate(sub.iterrows(), 2):
    sid = str(row['shopId'])
    for ci, v in enumerate([row['op'], covered_emp.get(sid, '-'), sid, row.get('商户名', '-'),
                            vcount.get(sid, 0), vlast.get(sid, '-')], 1):
        ws.cell(ri, ci, v)
hdr(ws, len(h)); body(ws, len(sub) + 1, len(h)); width(ws, len(h), mx=32); ws.freeze_panes = 'A2'

wb.save(OUT)
print('saved', OUT)
print(f'覆盖 {len(covered)}/{len(pp)} = {len(covered)/len(pp):.1%}')
