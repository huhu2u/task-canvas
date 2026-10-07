#!/usr/bin/env python3
"""MEM断续约分析（状态列直接口径版，2026-09-09英杰定稿）
用法: python3 gen_mem_wmz_status.py <完整MEM明细(含已续约/已断约/待续约)> <输出.xlsx> <date>
口径：
- 续约率 = 已续约 / 参与计算（门店是否参与续约率计算==1）
- 状态三档：待续约/已续约/已断约（门店待续约状态名称）
- 紧急 = 剩余天数≤30且待续约；紧急7 = ≤7天且待续约
- 好店匹配：点评商户ID → haodian_pool.xlsx shopId
"""
import sys, warnings
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
warnings.filterwarnings('ignore')

INPUT, OUTPUT, DATE = sys.argv[1], sys.argv[2], sys.argv[3]
POOL = None if len(sys.argv) > 4 and sys.argv[4] == '--no-pool' else '/root/.openclaw/workspace/data/haodian_pool.xlsx'

ALL7 = {'知了':'南京知了','小花猫':'上海代优','代优':'上海代优','星企动':'绍兴星企动','哲光':'慈溪哲光','汐洋':'义乌汐洋','广通':'惠安广通','烁果':'仙居烁果'}
ORDER = ['南京知了','上海代优','绍兴星企动','慈溪哲光','义乌汐洋','惠安广通','仙居烁果']
BOSS = {'南京知了':'陈具礼','上海代优':'代永安','绍兴星企动':'李晓锋','慈溪哲光':'孙浩','义乌汐洋':'陈铨','惠安广通':'尤云生','仙居烁果':'邱伯达'}

df = pd.read_excel(INPUT)
df['op'] = df['销售9级组织名称'].apply(lambda o: next((v for k, v in ALL7.items() if k in str(o)), None))
d = df[df['op'].notna()].copy()
d['shop_id'] = d['点评商户ID'].apply(lambda x: str(int(x)) if isinstance(x, float) else str(x or ''))
d['days'] = pd.to_numeric(d['门店方案到期剩余天数'], errors='coerce')
_calc_col = '门店是否参与中小发续约率计算' if '门店是否参与中小发续约率计算' in d.columns else '门店是否参与续约率计算'
d['calc'] = d[_calc_col].astype(str).str.strip().isin(['1', '1.0'])
d['status'] = d['门店待续约状态名称'].astype(str)
d['本月拜访'] = pd.to_numeric(d['门店轮转组本月有效拜访次数'], errors='coerce').fillna(0)

# 好店匹配
hd_ids = set(pd.read_excel(POOL)['shopId'].astype(str)) if POOL else set()
d['好店'] = d['shop_id'].isin(hd_ids)

def urgent(sub, n):
    return len(sub[(sub['days'] <= n) & (sub['status'] == '待续约')])

rows = []
for op in ORDER:
    sub = d[d['op'] == op]
    calc = sub[sub['calc']]
    renewed = len(calc[calc['status'] == '已续约'])
    r = {
        '代运营商': op, '操盘手': BOSS[op], '到期门店总数': len(sub), '参与计算': len(calc),
        '已续约': renewed, '续约率': renewed / len(calc) if len(calc) else 0,
        '待续约': len(calc[calc['status'] == '待续约']), '已断约': len(calc[calc['status'] == '已断约']),
        '紧急≤7天': urgent(sub, 7), '紧急≤30天': urgent(sub, 30),
        '断约未拜访': len(sub[(sub['status'] == '已断约') & (sub['本月拜访'] == 0)]),
        '待续约未拜访': len(sub[(sub['status'] == '待续约') & (sub['本月拜访'] == 0)]),
        '全量未拜访': len(sub[sub['本月拜访'] == 0]),
        '全量拜访率': 1 - len(calc[calc['本月拜访'] == 0]) / len(calc) if len(calc) else 0,
        '_calc未拜访': len(calc[calc['本月拜访'] == 0]),
    }
    rows.append(r)
tot = {
    '代运营商': '合计', '操盘手': '胡英杰',
    '到期门店总数': sum(r['到期门店总数'] for r in rows), '参与计算': sum(r['参与计算'] for r in rows),
    '已续约': sum(r['已续约'] for r in rows),
    '续约率': sum(r['已续约'] for r in rows) / sum(r['参与计算'] for r in rows),
    '待续约': sum(r['待续约'] for r in rows), '已断约': sum(r['已断约'] for r in rows),
    '紧急≤7天': sum(r['紧急≤7天'] for r in rows), '紧急≤30天': sum(r['紧急≤30天'] for r in rows),
    '断约未拜访': sum(r['断约未拜访'] for r in rows),
    '待续约未拜访': sum(r['待续约未拜访'] for r in rows),
    '全量未拜访': sum(r['全量未拜访'] for r in rows),
    '全量拜访率': 1 - sum(r['_calc未拜访'] for r in rows) / sum(r['参与计算'] for r in rows),
}
rows.append(tot)

# ===== 写Excel =====
C_HDR = PatternFill('solid', fgColor='1F4E79'); C_HDR_F = Font(color='FFFFFF', bold=True, size=10)
C_SUM = PatternFill('solid', fgColor='2E75B6'); C_ALT = PatternFill('solid', fgColor='DDEBF7')
THIN = Border(*[Side(style='thin', color='B0B0B0')] * 4)

wb = openpyxl.Workbook()
ws = wb.active; ws.title = '代运营商汇总'
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=14)
ws.cell(1, 1, f'皖闽浙MEM断续约分析（{DATE}）').font = Font(bold=True, size=12)
ws.cell(1, 1).alignment = Alignment(horizontal='center', vertical='center')
hdr = ['代运营商', '操盘手', '到期门店总数', '参与计算', '已续约', '续约率', '待续约', '已断约', '紧急≤7天', '紧急≤30天', '断约未拜访', '待续约未拜访', '全量未拜访', '全量拜访率']
for c, h in enumerate(hdr, 1):
    ws.cell(2, c, h).fill = C_HDR; ws.cell(2, c).font = C_HDR_F; ws.cell(2, c).alignment = Alignment(horizontal='center')
for r, row in enumerate(rows, 3):
    is_sum = row['代运营商'] == '合计'
    # 找到本次数据行区间（合计前为明细行）
    for c, h in enumerate(hdr, 1):
        v = row[h]
        if h in ('续约率', '全量拜访率') and isinstance(v, float): v = round(v, 4)
        cell = ws.cell(r, c, v)
        cell.border = THIN
        cell.alignment = Alignment(horizontal='center')
        if is_sum:
            cell.fill = C_SUM; cell.font = Font(bold=True, color='FFFFFF')
        else:
            cell.fill = C_ALT if r % 2 == 0 else PatternFill()
        if h in ('续约率', '全量拜访率') and isinstance(v, float):
            cell.number_format = '0.0%'
            if h == '续约率':
                good, mid = 0.3, 0.15
            else:
                good, mid = 0.8, 0.6
            if is_sum:
                # 合计行：保持蓝色底，用字体颜色区分档位
                cell.fill = C_SUM
                cell.font = Font(bold=True, color='FFFFFF' if v >= mid else 'FFD966')
            else:
                cell.fill = PatternFill('solid', fgColor='63BE7B' if v >= good else ('FFEB84' if v >= mid else 'F8696B'))

# 明细Sheet生成函数
DET_COLS = ['代运营商', '销售姓名', '门店ID', '门店名称', '品类', '到期产品', '剩余天数', '参与计算', '状态', '签回月份', '最近有效拜访', '本月拜访', '上月拜访', '上上月拜访']
def make_sheet(name, sub):
    s = wb.create_sheet(name)
    s.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(DET_COLS))
    s.cell(1, 1, f'{name}（共{len(sub)}家）').font = Font(bold=True, size=11)
    s.cell(1, 1).alignment = Alignment(horizontal='center', vertical='center')
    for c, h in enumerate(DET_COLS, 1):
        s.cell(2, c, h).fill = C_HDR; s.cell(2, c).font = C_HDR_F; s.cell(2, c).alignment = Alignment(horizontal='center')
    for r, (_, x) in enumerate(sub.iterrows(), 3):
        vals = [x['op'], x['销售工号名称'], x['shop_id'], x['门店名称'],
                x.get('商户后台一级类目名称', ''), x.get('到期MEM产品名称', ''),
                x['days'] if pd.notna(x['days']) else '',
                '是' if x['calc'] else '否', x['status'],
                x.get('续约方案签回月份', '') if pd.notna(x.get('续约方案签回月份', '')) else '',
                str(x.get('门店轮转组近一年最近有效拜访时间', '') or '')[:16],
                x.get('门店轮转组本月有效拜访次数', 0), x.get('门店轮转组上月有效拜访次数', 0),
                x.get('门店轮转组上上月有效拜访次数', 0)]
        for c, v in enumerate(vals, 1):
            s.cell(r, c, v).border = THIN
    for c, w in enumerate([13, 9, 12, 30, 10, 22, 8, 8, 8, 10, 17, 9, 9, 9], 1):
        s.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w

d_sorted = d.sort_values(['op', 'days'], key=lambda s: s.map({o: i for i, o in enumerate(ORDER)}) if s.name == 'op' else s)
make_sheet('待续约明细', d_sorted[d_sorted['status'] == '待续约'])
make_sheet('已续约明细', d_sorted[d_sorted['status'] == '已续约'])
make_sheet('已断约明细', d_sorted[d_sorted['status'] == '已断约'])
make_sheet('全量明细', d_sorted)

for c, w in enumerate([13, 9, 11, 9, 8, 8, 8, 8, 10, 10, 11, 12, 11, 10], 1):
    ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w




from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
warnings.filterwarnings('ignore')





ws = wb.create_sheet('销售维度', 1)
C_HDR = PatternFill('solid', fgColor='1F4E79'); C_HDR_F = Font(color='FFFFFF', bold=True, size=10)
C_GRP = PatternFill('solid', fgColor='E07B39'); C_GRP_F = Font(color='FFFFFF', bold=True, size=10)
C_ALT = PatternFill('solid', fgColor='DDEBF7'); C_SUM = PatternFill('solid', fgColor='2E75B6')
THIN = Border(*[Side(style='thin', color='B0B0B0')] * 4)
hdr = ['销售姓名', '到期门店数', '参与计算', '已续约', '续约率', '待续约', '已断约', '紧急≤7天', '紧急≤30天']
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=9)
ws.cell(1, 1, '销售维度').font = Font(bold=True, size=12)
ws.cell(1, 1).alignment = Alignment(horizontal='center', vertical='center')
r = 2
for op in ORDER:
    sub = d[d['op'] == op]
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    c = ws.cell(r, 1, f'{op}'); c.fill = C_GRP; c.font = C_GRP_F
    r += 1
    for c2, h in enumerate(hdr, 1):
        cell = ws.cell(r, c2, h); cell.fill = C_HDR; cell.font = C_HDR_F; cell.alignment = Alignment(horizontal='center')
    r += 1
    sellers = sub.groupby('销售工号名称')
    srows = []
    for name, g in sellers:
        calc = g[g['calc']]
        renewed = int((calc['status'] == '已续约').sum())
        srows.append({
            'name': name, 'total': len(g), 'calc': len(calc), 'renewed': renewed,
            'rate': renewed / len(calc) if len(calc) else 0,
            'wait': int((calc['status'] == '待续约').sum()), 'lost': int((calc['status'] == '已断约').sum()),
            'u7': int(((g['days'] <= 7) & (g['status'] == '待续约')).sum()),
            'u30': int(((g['days'] <= 30) & (g['status'] == '待续约')).sum()),
        })
    srows.sort(key=lambda x: -x['rate'])
    for i, x in enumerate(srows):
        vals = [x['name'], x['total'], x['calc'], x['renewed'], round(x['rate'], 4), x['wait'], x['lost'], x['u7'], x['u30']]
        for c2, v in enumerate(vals, 1):
            cell = ws.cell(r, c2, v); cell.border = THIN
            if i % 2 == 1: cell.fill = C_ALT
            if c2 == 5 and isinstance(v, float):
                cell.number_format = '0.0%'
                cell.fill = PatternFill('solid', fgColor='63BE7B' if v >= 0.3 else ('FFEB84' if v >= 0.15 else 'F8696B')) if i % 2 == 0 else PatternFill('solid', fgColor='DDEBF7')
        r += 1
    # 组织小计
    calc_all = sub[sub['calc']]
    stot = [f'{op}小计', len(sub), len(calc_all), int((calc_all['status']=='已续约').sum()),
           round((calc_all['status']=='已续约').sum()/len(calc_all), 4) if len(calc_all) else 0,
           int((calc_all['status']=='待续约').sum()), int((calc_all['status']=='已断约').sum()),
           int(((sub['days']<=7)&(sub['status']=='待续约')).sum()), int(((sub['days']<=30)&(sub['status']=='待续约')).sum())]
    for c2, v in enumerate(stot, 1):
        cell = ws.cell(r, c2, v); cell.fill = C_SUM; cell.font = Font(bold=True, color='FFFFFF')
        if c2 == 5: cell.number_format = '0.0%'
    r += 2
for c2, w in enumerate([12, 11, 9, 8, 8, 8, 8, 10, 10], 1):
    ws.column_dimensions[openpyxl.utils.get_column_letter(c2)].width = w

wb.save(OUTPUT)
print(f'saved {OUTPUT}')
print(f"整体续约率: {tot['已续约']}/{tot['参与计算']} = {tot['续约率']:.1%}")
for r in rows[:-1]:
    print(f"{r['代运营商']}: {r['已续约']}/{r['参与计算']} = {r['续约率']:.1%} 紧急7:{r['紧急≤7天']} 紧急30:{r['紧急≤30天']}")
