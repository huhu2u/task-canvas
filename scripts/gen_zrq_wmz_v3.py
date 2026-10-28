#!/usr/bin/env python3
"""
gen_zrq_wmz_v3.py — 皖闽浙职人码分析表 v3
数据源改为「策略管理-PC-中小发-优惠码（组织明细）」（替代职人码组织明细，2026-10-15英杰确认）
新增4列：店转感知风控实付GTV / 店转感知风控率 / 店转实锤风控实付GTV / 店转实锤风控率
口径（全65行验证）：感知率 = 感知GTV/(剔风控GTV+实锤GTV)；实锤率 = 实锤GTV/(剔风控GTV+实锤GTV)
动销门店数/动销率：仍从职人码明细(zrq_api_detail)取（B方案混搭，2026-10-15英杰确认）
用法:
  python3 gen_zrq_wmz_v3.py --today <优惠码组织明细.xlsx> --zrq-detail <zrq_api_detail_日期.xlsx> \
      --base <优惠码基准.xlsx> --zrq-base <职人码基准> --base-label "10月1日" --out <输出.xlsx> [--date YYYY-MM-DD]
"""
import argparse
import json
import os
import re
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from datetime import datetime, timedelta

L2_MAP = {
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
    '惠安广通-晋江乐生活组': '惠安广通',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '泉州市小花猫-泉州乐生活组': '上海代优',
    '星企动-绍兴乐生活区县聚合组': '绍兴星企动',
    '星企动-绍兴乐生活组': '绍兴星企动',
    '星企动-绍兴柯桥区乐生活组': '绍兴星企动',
    '星企动-绍兴上虞区乐生活组': '绍兴星企动',
    '仙居烁果-台州乐生活组': '仙居烁果',
    '仙居烁果-台州温岭乐生活组': '仙居烁果',
    '南京知了-芜湖乐生活组': '芜湖知了',
    '上海代优-泉州乐生活组': '上海代优',
}
L3_MAP = {
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
    '上海代优-泉州乐生活组': '上海代优',
    '泉州市小花猫-泉州乐生活组': '上海代优',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '南京知了-芜湖乐生活组': '芜湖知了',
    '惠安广通-晋江乐生活组': '惠安广通',
    '仙居烁果-台州乐生活组': '仙居烁果',
    '星企动-绍兴乐生活组': '绍兴星企动',
    '仙居烁果-台州温岭乐生活组': '仙居烁果',
}
PARTNERS = ['绍兴星企动', '上海代优', '慈溪哲光', '义乌汐洋', '仙居烁果', '惠安广通', '芜湖知了']
CLUSTER_OWNER = '胡英杰'
BASE_LABEL = '10月1日'
MANAGER = {'上海代优': '代永安', '惠安广通': '尤云生', '慈溪哲光': '孙浩',
           '义乌汐洋': '陈铨', '绍兴星企动': '李晓锋', '仙居烁果': '邱伯达', '芜湖知了': '陈具礼'}

ARCHIVE_DIR = '/root/.openclaw/workspace/data/zrq_gtv_archive'

# 优惠码组织明细列名（2026-10-15格式）
C_STORES = '合作门店数'
C_BIND = '绑码门店数'
C_DZ_GTV = '店转实付验证GTV'          # = 店转GTV（与旧口径一致，已验证）
C_REAL_GTV = '实付验证GTV'            # = 周期内核销实付GTV
C_AOV = '店转订单均价'
C_GANZHI = '店转感知风控实付GTV'
C_SHICHUI = '店转实锤风控实付GTV'
C_TIFENG = '店转实付GTV（剔风控）'

# 职人码明细列名（动销两列从这里取）
Z_DONG = '职人码有效动销门店数'


def f(x, d=0.0):
    try:
        v = float(x)
        return d if pd.isna(v) else v
    except (TypeError, ValueError):
        return d


def _norm(df):
    """列名归一：职人码明细旧列名 → 优惠码新列名（基准文件是10-01职人码格式）"""
    ren = {'职人码绑码门店数': C_BIND}
    for k, v in ren.items():
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})
    return df


def prep_l2(df):
    """组织明细 L2 行 → 按代运营商聚合"""
    df = _norm(df)
    l2 = df[df['层级'] == 'L2'].copy()
    l2['_p'] = l2['L2'].map(L2_MAP)
    l2.loc[l2['_p'].isna(), '_p'] = l2['L3'].map(L3_MAP)
    l2 = l2.dropna(subset=['_p'])
    return l2


def agg_l2(l2):
    """按代运营商聚合所有数值为字典 {partner: {...}}（职人码基准文件缺风控列时容呑0）"""
    def col(d, name):
        return d[name].tolist() if name in d.columns else []
    out = {}
    for p, g in l2.groupby('_p'):
        d = {}
        d[C_STORES] = sum(f(x) for x in col(g, C_STORES) or [])
        d[C_BIND] = sum(f(x) for x in col(g, C_BIND) or [])
        d[C_DZ_GTV] = sum(f(x) for x in col(g, C_DZ_GTV)) or sum(f(x) for x in col(g, '店转GTV'))
        d[C_REAL_GTV] = sum(f(x) for x in col(g, C_REAL_GTV)) or sum(f(x) for x in col(g, '周期内核销实付GTV'))
        d[C_GANZHI] = sum(f(x) for x in col(g, C_GANZHI) or [])
        d[C_SHICHUI] = sum(f(x) for x in col(g, C_SHICHUI) or [])
        d[C_TIFENG] = sum(f(x) for x in col(g, C_TIFENG) or [])
        orders = sum(f(x) for x in col(g, '店转核销订单量') or [])
        d[C_AOV] = d[C_DZ_GTV] / orders if orders > 0 else 0
        out[p] = d
    return out


def prep_zrq_l2(zpath):
    """职人码明细 L2 动销门店数"""
    df = pd.read_excel(zpath, header=0)
    l2 = df[df['层级'] == 'L2'].copy()
    l2['_p'] = l2['L2'].map(L2_MAP)
    l2.loc[l2['_p'].isna(), '_p'] = l2['L3'].map(L3_MAP)
    l2 = l2.dropna(subset=['_p'])
    return {p: sum(f(x) for x in g[Z_DONG]) for p, g in l2.groupby('_p')}


def load_yesterday_archive(date_str):
    """读昨日 zrq_gtv_archive JSON（店转GTV/实付GTV），结构 {data:{p:{store_gtv,real_gtv}}, sales:{emp:{...}}}"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        yest_key = (d - timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError:
        return None, None
    ypath = os.path.join(ARCHIVE_DIR, f'{yest_key}.json')
    if os.path.exists(ypath):
        with open(ypath) as fp:
            return json.load(fp), yest_key
    # 回退：本月内最近存档
    import glob as _glob
    cands = [os.path.basename(p)[:-5] for p in _glob.glob(os.path.join(ARCHIVE_DIR, '????-??-??.json'))]
    cands = [c for c in cands if c < date_str and c[:7] == date_str[:7]]
    if cands:
        latest = sorted(cands)[-1]
        with open(os.path.join(ARCHIVE_DIR, f'{latest}.json')) as fp:
            return json.load(fp), f'{latest}(回退)'
    return None, None


def make_row(p, agg, agg_base, dong, yest_archive, is_total=False):
    def A(part):
        return agg.get(part, {})
    if is_total:
        stores = sum(A(x).get(C_STORES, 0) for x in PARTNERS)
        bind = sum(A(x).get(C_BIND, 0) for x in PARTNERS)
        bind_base = sum(agg_base.get(x, {}).get(C_BIND, 0) for x in PARTNERS)
        dong_count = sum(dong.get(x, 0) for x in PARTNERS)
        store_gtv = sum(A(x).get(C_DZ_GTV, 0) for x in PARTNERS)
        real_gtv = sum(A(x).get(C_REAL_GTV, 0) for x in PARTNERS)
        ganzhi = sum(A(x).get(C_GANZHI, 0) for x in PARTNERS)
        shichui = sum(A(x).get(C_SHICHUI, 0) for x in PARTNERS)
        tifeng = sum(A(x).get(C_TIFENG, 0) for x in PARTNERS)
        aov = store_gtv / dong_count if dong_count > 0 else 0
    else:
        a = A(p)
        stores = a.get(C_STORES, 0)
        bind = a.get(C_BIND, 0)
        bind_base = agg_base.get(p, {}).get(C_BIND, 0)
        dong_count = dong.get(p, 0)
        store_gtv = a.get(C_DZ_GTV, 0)
        real_gtv = a.get(C_REAL_GTV, 0)
        ganzhi = a.get(C_GANZHI, 0)
        shichui = a.get(C_SHICHUI, 0)
        tifeng = a.get(C_TIFENG, 0)
        aov = a.get(C_AOV, 0)

    bind_delta = bind - bind_base
    bind_rate = bind / stores if stores > 0 else 0
    dong_rate = dong_count / stores if stores > 0 else 0
    gtv_pen = store_gtv / real_gtv if real_gtv > 0 else 0
    fk_denom = tifeng + shichui
    gz_rate = ganzhi / fk_denom if fk_denom > 0 else 0
    sc_rate = shichui / fk_denom if fk_denom > 0 else 0

    # 昨日差分（存档口径：store_gtv/real_gtv = 月累计）
    if is_total:
        # 汇总行：7家求和（存档无TOTAL键时兼容旧格式）
        yd_all = [(yest_archive or {}).get('data', {}).get(x, {}) for x in PARTNERS]
        if any(yd_all):
            yst_g = sum(x.get('store_gtv', 0) for x in yd_all)
            yst_r = sum(x.get('real_gtv', 0) for x in yd_all)
            gtv_delta = store_gtv - yst_g
            yest_real_day = real_gtv - yst_r
        else:
            gtv_delta = store_gtv
            yest_real_day = real_gtv
    else:
        yd = (yest_archive or {}).get('data', {}).get(p, {}) if yest_archive else {}
        if yd:
            gtv_delta = store_gtv - yd.get('store_gtv', 0)
            yest_real_day = real_gtv - yd.get('real_gtv', 0)
        else:
            gtv_delta = store_gtv
            yest_real_day = real_gtv
    yest_pen = gtv_delta / yest_real_day if yest_real_day > 0 else gtv_pen

    return [p if not is_total else '皖闽浙汇总',
            CLUSTER_OWNER if is_total else MANAGER[p],
            int(stores), int(bind), bind_rate, bind_delta,
            int(dong_count), dong_rate, store_gtv, gtv_delta,
            gtv_pen, yest_pen, yest_real_day, real_gtv, aov,
            ganzhi, gz_rate, shichui, sc_rate]


def build_sales_rows(df_today, df_base, zrq_today, zrq_base, yest_archive):
    """销售维度：L1/L0 行，动销两列从职人码明细按工号匹配"""
    def prep(df):
        d = df[df['层级'].isin(['L1', 'L0'])].copy()
        d['_p'] = d['L2'].map(L2_MAP)
        d.loc[d['_p'].isna(), '_p'] = d['L3'].map(L3_MAP)
        return d.dropna(subset=['_p'])

    l1t = prep(df_today)
    l1b = prep(df_base)
    if '绑码门店数' not in df_base.columns and '职人码绑码门店数' in df_base.columns:
        l1b = l1b.rename(columns={'职人码绑码门店数': '绑码门店数'})

    # 昨日存档销售键兼容：工号 或 L2|姓名
    yest_sales = (yest_archive or {}).get('sales', {})

    def yget(r):
        e = str(r['工号']) if pd.notna(r['工号']) else ''
        nm = str(r['姓名']) if pd.notna(r['姓名']) else ''
        org = str(r['L2'] if pd.notna(r['L2']) else (r['L3'] if pd.notna(r['L3']) else ''))
        if e in yest_sales:
            return yest_sales[e]
        return yest_sales.get(f'{org}|{nm}')

    # 职人码明细：动销门店数 —— 键兼容工号 与 L2|姓名（明细的工号列实为「L2|姓名」）
    def zmap(zpath):
        if not zpath or not os.path.exists(zpath):
            return {}
        df = pd.read_excel(zpath, header=0)
        d = df[df['层级'].isin(['L1', 'L0'])].copy()
        out = {}
        for _, r in d.iterrows():
            v = f(r[Z_DONG])
            k1 = str(r['工号'])
            org = str(r['L2'] if pd.notna(r['L2']) else (r['L3'] if pd.notna(r['L3']) else ''))
            k2 = f"{org}|{r['姓名']}"
            out[k1] = v
            out[k2] = v
        return out

    zt = zmap(zrq_today)
    zb = zmap(zrq_base)

    rows = []
    for p in PARTNERS:
        g = l1t[l1t['_p'] == p]
        gb = l1b[l1b['_p'] == p]
        if g.empty:
            continue
        base_bind = {}
        if not gb.empty:
            base_bind = {str(r['工号']): f(r['绑码门店数']) for _, r in gb.iterrows()}
            # 兼容：基准有工号但今日文件工号可能全空（2026-10-28英杰报：销售维度月净增=绑码门店数）
            base_bind.update({f"{r['L2']}|{r['姓名']}": f(r['绑码门店数']) for _, r in gb.iterrows()})
        for _, r in g.iterrows():
            name = str(r['姓名']) if pd.notna(r['姓名']) else ''
            emp = str(r['工号']) if pd.notna(r['工号']) else ''
            org = str(r['L2'] if pd.notna(r['L2']) else (r['L3'] if pd.notna(r['L3']) else ''))
            legacy_key = f'{org}|{name}'
            stores = int(f(r['合作门店数']))
            bind = int(f(r['绑码门店数']))
            bind_delta = bind - int(base_bind.get(emp, base_bind.get(legacy_key, 0)))
            dong = int(zt.get(emp, zt.get(legacy_key, 0)))
            store_gtv = f(r[C_DZ_GTV])
            real_gtv = f(r[C_REAL_GTV])
            gtv_pen = store_gtv / real_gtv if real_gtv > 0 else 0
            ganzhi = f(r[C_GANZHI])
            shichui = f(r[C_SHICHUI])
            tifeng = f(r[C_TIFENG])
            fk_denom = tifeng + shichui
            gz_rate = ganzhi / fk_denom if fk_denom > 0 else 0
            sc_rate = shichui / fk_denom if fk_denom > 0 else 0
            # 昨日差分
            ys = yget(r) or {}
            if ys:
                gtv_delta = store_gtv - ys.get('store_gtv', 0)
                yest_real_day = real_gtv - ys.get('real_gtv', 0)
            else:
                gtv_delta = store_gtv
                yest_real_day = real_gtv
            yest_pen = gtv_delta / yest_real_day if yest_real_day > 0 else gtv_pen
            rows.append([p, MANAGER[p], name, emp, stores, bind, bind_delta, dong,
                         store_gtv, gtv_delta, gtv_pen, yest_pen, yest_real_day, real_gtv,
                         ganzhi, gz_rate, shichui, sc_rate])
    return rows


def build_excel(rows, sales_rows, out_path, date_str):
    C_TITLE = '003366'; C_HEADER = '1E3A5F'; C_TOTAL = '154360'
    C_ALT1 = 'FFFFFF'; C_ALT2 = 'F0F8FF'; C_BORDER = 'BDD7EE'
    C_NEW_HDR = 'B45309'; C_NEW_BG = 'FEF3C7'
    C_YEST_HDR = '0369A1'; C_YEST_BG = 'E0F2FE'
    C_FK_HDR = '7C2D12'; C_FK_BG = 'FFEDD5'   # 风控列（橙红系）

    def fill(c): return PatternFill('solid', fgColor=c)
    def bdr():
        s = Side(style='thin', color=C_BORDER)
        return Border(left=s, right=s, top=s, bottom=s)
    def aln(h='center', v='center', wrap=True):
        return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

    HEADERS = [
        '代运营商', '负责人',
        '合作门店数', '绑码门店数',
        '绑码率\n(绑码/合作门店)',
        f'月净增绑码数\n(vs {BASE_LABEL})',
        '有效动销门店数', '动销率',
        '店转GTV（元）', '昨日店转GTV',
        '店转GTV渗透率', '昨日店转渗透率', '昨日实付GTV',
        '实付GTV（元）', '店转客单均价',
        '店转感知风控\n实付GTV（元）', '店转感知风控率',
        '店转实锤风控\n实付GTV（元）', '店转实锤风控率',
    ]
    NCOLS = len(HEADERS)
    YEST_COLS = {10, 12, 13}
    NEW_COL = 6
    FK_COLS = {16, 17, 18, 19}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '皖闽浙职人码分析'
    ws.merge_cells(f'A1:{get_column_letter(NCOLS)}1')
    ws['A1'] = f'皖闽浙城市群职人码分析表（{date_str}）'
    ws['A1'].fill = fill(C_TITLE)
    ws['A1'].font = Font(bold=True, color='FFFFFF', size=13, name='微软雅黑')
    ws['A1'].alignment = aln()
    ws.row_dimensions[1].height = 30

    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(row=2, column=ci, value=h)
        if ci in YEST_COLS:
            c.fill = fill(C_YEST_HDR)
            c.font = Font(bold=True, color='D4EDDA', size=10, name='微软雅黑')
        elif ci == NEW_COL:
            c.fill = fill(C_NEW_HDR)
            c.font = Font(bold=True, color='FFE082', size=10, name='微软雅黑')
        elif ci in FK_COLS:
            c.fill = fill(C_FK_HDR)
            c.font = Font(bold=True, color='FFEDD5', size=10, name='微软雅黑')
        else:
            c.fill = fill(C_HEADER)
            c.font = Font(bold=True, color='FFFFFF', size=10, name='微软雅黑')
        c.alignment = aln()
        c.border = bdr()
    ws.row_dimensions[2].height = 40

    for ri, rd in enumerate(rows, 3):
        is_tot = (rd[0] == '皖闽浙汇总')
        bg = C_TOTAL if is_tot else (C_ALT1 if ri % 2 == 1 else C_ALT2)
        for ci, val in enumerate(rd, 1):
            c = ws.cell(row=ri, column=ci)
            c.border = bdr(); c.alignment = aln()
            if is_tot:
                c.fill = fill(bg)
                c.font = Font(bold=True, color='FFFFFF', size=10, name='微软雅黑')
            elif ci in YEST_COLS:
                c.fill = fill(C_YEST_BG)
                c.font = Font(size=10, name='微软雅黑', color='0C4A6E')
            elif ci == NEW_COL:
                c.fill = fill(C_NEW_BG)
                delta = val if isinstance(val, (int, float)) else 0
                color = '006400' if delta > 0 else 'CC0000' if delta < 0 else '555555'
                c.font = Font(bold=True, size=10, name='微软雅黑', color=color)
            elif ci in FK_COLS:
                c.fill = fill(C_FK_BG)
                c.font = Font(size=10, name='微软雅黑', color='7C2D12')
            else:
                c.fill = fill(bg)
                c.font = Font(size=10, name='微软雅黑', color='1A1A2E')

            if val is None:
                c.value = '-'
            elif ci in [3, 4, 7]:
                c.value = int(val); c.number_format = '#,##0'
            elif ci == NEW_COL:
                c.value = int(val); c.number_format = '+#,##0;-#,##0;0'
            elif ci in [5, 8, 11, 12]:
                c.value = val if isinstance(val, float) else 0
                c.number_format = '0.0%'
            elif ci in [17, 19]:
                c.value = val if isinstance(val, float) else 0
                c.number_format = '0.0%'
            elif ci == 10:
                if val is not None and isinstance(val, (int, float)):
                    c.value = round(float(val), 0)
                    c.number_format = '+#,##0;-#,##0;0'
                    if not is_tot:
                        color = '006400' if val > 0 else 'CC0000' if val < 0 else '555555'
                        c.font = Font(bold=True, size=10, name='微软雅黑', color=color)
                else:
                    c.value = '-'
            elif ci in [9, 13, 14, 15, 16, 18]:
                c.value = round(float(val), 0) if isinstance(val, (int, float)) else val
                c.number_format = '#,##0'
            else:
                c.value = val
        ws.row_dimensions[ri].height = 22

    for col, mid in [(5, 0.3), (11, 0.165), (12, 0.165), (17, 0.2), (19, 0.1)]:
        cl = get_column_letter(col)
        ws.conditional_formatting.add(f'{cl}4:{cl}{2+len(rows)}',
            ColorScaleRule(start_type='num', start_value=0, start_color='6BCB77',
                           mid_type='num', mid_value=mid, mid_color='FFD93D',
                           end_type='num', end_value=max(0.5, mid*2.5), end_color='FF6B6B'))

    for i, w in enumerate([14, 8, 11, 10, 12, 13, 12, 9, 13, 13, 11, 11, 13, 13, 12, 13, 11, 13, 11], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A3'

    # ===== Sheet2 销售维度 =====
    SH2_HEAD = ['代运营商', '负责人', '销售姓名', '工号', '合作门店数', '绑码门店数',
                f'月净增绑码(vs {BASE_LABEL})', '有效动销门店数',
                '店转GTV', '昨日店转GTV', '店转渗透率', '昨日渗透率', '昨日实付GTV', '实付GTV',
                '店转感知风控GTV', '店转感知风控率', '店转实锤风控GTV', '店转实锤风控率']
    ws2 = wb.create_sheet(title='销售维度')
    ws2.merge_cells(f'A1:{get_column_letter(len(SH2_HEAD))}1')
    ws2['A1'] = f'皖闽浙职人码分析表 - 销售维度（{date_str}）'
    ws2['A1'].fill = fill(C_TITLE)
    ws2['A1'].font = Font(bold=True, color='FFFFFF', size=13, name='微软雅黑')
    ws2['A1'].alignment = aln()
    ws2.row_dimensions[1].height = 28
    for ci, h in enumerate(SH2_HEAD, 1):
        c = ws2.cell(row=2, column=ci, value=h)
        c.fill = fill(C_HEADER if ci < 15 else C_FK_HDR)
        c.font = Font(bold=True, color='FFFFFF', size=10, name='微软雅黑')
        c.alignment = aln(); c.border = bdr()
    ws2.row_dimensions[2].height = 36
    ws2.freeze_panes = 'A3'

    for ri, row in enumerate(sales_rows, 3):
        bg = C_ALT1 if ri % 2 == 1 else C_ALT2
        for ci, val in enumerate(row, 1):
            c = ws2.cell(row=ri, column=ci, value=val)
            c.border = bdr(); c.alignment = aln()
            c.fill = fill(C_FK_BG if ci >= 15 else bg)
            c.font = Font(size=10, name='微软雅黑', color='7C2D12' if ci >= 15 else '1A1A2E')
            if ci in [5, 6, 8]:
                c.number_format = '#,##0'
            elif ci == 7:
                c.number_format = '+#,##0;-#,##0;0'
            elif ci in [11, 12, 16, 18]:
                c.number_format = '0.0%'
            elif ci in [9, 10, 13, 14, 15, 17]:
                c.number_format = '#,##0'
        ws2.row_dimensions[ri].height = 20
    for i, w in enumerate([14, 8, 10, 10, 11, 11, 13, 11, 12, 12, 11, 11, 12, 12, 13, 11, 13, 11], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    wb.save(out_path)
    print(f'已生成: {out_path}')


def main():
    global BASE_LABEL
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True, help='今日优惠码（组织明细）xlsx')
    ap.add_argument('--zrq-today', required=True, help='今日职人码明细（zrq_api_detail，取动销列）')
    ap.add_argument('--base', required=True, help='基准优惠码组织明细（月1日）')
    ap.add_argument('--zrq-base', default=None, help='基准职人码明细（月1日，取绑码基准）')
    ap.add_argument('--base-label', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--date', default=None)
    ap.add_argument('--yesterday', default=None, help='昨日存档JSON路径（默认自动查 zrq_gtv_archive/<昨日>.json）')
    args = ap.parse_args()

    if args.base_label:
        BASE_LABEL = args.base_label
    else:
        mm = re.search(r'(\d{4})[_-](\d{2})[_-](\d{2})', os.path.basename(args.base))
        if mm:
            BASE_LABEL = f'{int(mm.group(2))}月{int(mm.group(3))}日'

    if args.date:
        date_str = args.date
    else:
        mm = re.search(r'(\d{4})[_-](\d{2})[_-](\d{2})', os.path.basename(args.today))
        date_str = f'{mm.group(1)}-{mm.group(2)}-{mm.group(3)}' if mm else datetime.now().strftime('%Y-%m-%d')
    print(f'数据日期: {date_str} | 月净增绑码基准 vs {BASE_LABEL}')

    df_today = pd.read_excel(args.today, header=0)
    df_base = pd.read_excel(args.base, header=0)
    agg = agg_l2(prep_l2(df_today))
    agg_base = agg_l2(prep_l2(df_base))
    dong = prep_zrq_l2(args.zrq_today)

    if getattr(args, 'yesterday', None):
        import json as _json
        yest_archive = _json.load(open(args.yesterday))
        yest_note = args.yesterday
        print(f'读取昨日存档(手动指定): {yest_note}')
    else:
        yest_archive, yest_note = load_yesterday_archive(date_str)
        if yest_archive:
            print(f'读取昨日存档: {yest_note}')
        else:
            print('⚠️ 本月无更早存档（跨月），昨日GTV列=今日值（月初首日）')

    rows = [make_row(None, agg, agg_base, dong, yest_archive, is_total=True)] + \
           [make_row(p, agg, agg_base, dong, yest_archive) for p in PARTNERS]

    # 销售维度绑码基准：优惠码基准文件（若有zrq-base则其绑码列一致，直接用优惠码基准）
    l1t_src = _norm(df_today.copy())
    l1t_src['_p'] = l1t_src['L2'].map(L2_MAP)
    l1t_src.loc[l1t_src['_p'].isna(), '_p'] = l1t_src['L3'].map(L3_MAP)
    l1t_src = l1t_src[l1t_src['层级'].isin(['L1', 'L0'])].dropna(subset=['_p'])
    sales_rows = build_sales_rows(df_today, df_base, args.zrq_today, args.zrq_base, yest_archive)

    build_excel(rows, sales_rows, args.out, date_str)

    # 存档（供次日昨日差分）：店转GTV/实付GTV 用新口径
    arc = {'date': date_str, 'data': {}, 'sales': {}}
    total_g, total_r = 0.0, 0.0
    for p in PARTNERS + ['TOTAL']:
        if p == 'TOTAL':
            g_ = total_g; r_ = total_r
        else:
            g_ = agg.get(p, {}).get(C_DZ_GTV, 0)
            r_ = agg.get(p, {}).get(C_REAL_GTV, 0)
            total_g += g_; total_r += r_
        arc['data'][p] = {'store_gtv': g_, 'real_gtv': r_}
    # 销售维度存档：直接用 sales_rows（工号）+ 兼容旧「L2|姓名」键
    for row in sales_rows:
        emp = str(row[3])
        v = {'store_gtv': row[8], 'real_gtv': row[13]}
        arc['sales'][emp] = v
    # 兼容旧存档键：从原始今日文件补「L2|姓名」键
    for _, r in l1t_src.iterrows():
        org = str(r['L2'] if pd.notna(r['L2']) else (r['L3'] if pd.notna(r['L3']) else ''))
        key = f"{org}|{r['姓名']}"
        e = str(r['工号']) if pd.notna(r['工号']) else ''
        if e in arc['sales']:
            arc['sales'][key] = arc['sales'][e]
    apath = os.path.join(ARCHIVE_DIR, f'{date_str}.json')
    with open(apath, 'w') as fp:
        json.dump(arc, fp, ensure_ascii=False, indent=1)
    print(f'今日存档: {apath}')


if __name__ == '__main__':
    main()
