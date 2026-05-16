#!/usr/bin/env python3
"""
高线区域职人码看板生成脚本
输入: 策略管理-PC-职人码（组织明细）xlsx
输出: 高线区域职人码看板_YYYYMMDD.xlsx (2 Sheets)
  Sheet1「城市群维度」: 汇总行 + 6城市群，白底无彩色底色，15列
  Sheet2「代运营商维度」: 46家按城市群分组，15列
  两个Sheet均含：合作门店数、月净增绑码数、月绑码率变化
"""

import pandas as pd
import json
import sys
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import (PatternFill, Font, Alignment, Border, Side)
from openpyxl.utils import get_column_letter
import warnings
warnings.filterwarnings('ignore')

TODAY = datetime.now().strftime('%Y-%m-%d')
TODAY_LABEL = datetime.now().strftime('%Y%m%d')

TARGET_FILE     = '/root/.openclaw/workspace/data/haoxian_target_2026_04.xlsx'
BASE_FILE       = '/root/.openclaw/workspace/data/haoxian_base_2026_04_01.xlsx'   # 保留4月1日备用
BASE_FILE_MAY   = '/root/.openclaw/workspace/data/haoxian_base_2026_05_01.json'  # 5月1日基准（JSON）
DAILY_ARCHIVE   = '/root/.openclaw/workspace/data/haoxian_daily_archive'
YESTERDAY_ARCHIVE = '/root/.openclaw/workspace/data/zrq_gtv_archive/2026-04-12.json'
TODAY_ARCHIVE     = f'/root/.openclaw/workspace/data/zrq_gtv_archive/{TODAY}.json'


def simplify_name(name):
    if pd.isna(name):
        return name
    return str(name).split('-')[0].strip()

def city_group_simple(name):
    if pd.isna(name):
        return name
    return str(name).replace('高线', '').strip()


def load_weekly_base_bind_map():
    """读取7天前（或最近一个周存档）的绑码商户数，用于计算周净增。"""
    import os
    from datetime import timedelta
    today_dt = datetime.now()
    week_bind_map = {}
    for delta in range(6, 14):  # 优先找6-7天前，找不到则往前找
        target_date = (today_dt - timedelta(days=delta)).strftime('%Y-%m-%d')
        archive_path = os.path.join(DAILY_ARCHIVE, f'{target_date}.xlsx')
        if os.path.exists(archive_path):
            try:
                df_w = pd.read_excel(archive_path)
                l2_w = df_w[df_w['层级'] == 'L2']
                for _, row in l2_w.iterrows():
                    if pd.notna(row['L2']):
                        key = str(row['L2']).strip()
                        week_bind_map[key] = int(row['职人码绑码商户数']) if pd.notna(row['职人码绑码商户数']) else 0
                print(f'  周净增基准: {target_date} ({len(week_bind_map)}家)')
            except Exception as e:
                print(f'  周净增基准加载失败({target_date}): {e}')
            break
    return week_bind_map


def archive_today(today_file):
    """存档今日组织明细到 haoxian_daily_archive/YYYY-MM-DD.xlsx"""
    import os, shutil
    os.makedirs(DAILY_ARCHIVE, exist_ok=True)
    dest = os.path.join(DAILY_ARCHIVE, f'{TODAY}.xlsx')
    shutil.copy2(today_file, dest)
    print(f'  已存档今日数据: {dest}')


def load_data(today_file):
    df = pd.read_excel(today_file)

    # 存档今日文件
    archive_today(today_file)

    df_target = pd.read_excel(TARGET_FILE)
    target_map = {}
    for _, row in df_target.iterrows():
        l2 = str(row['代运营二级组织']).strip() if pd.notna(row['代运营二级组织']) else ''
        val = row['校准后预估4月有效动销数']
        if l2:
            target_map[l2] = val

    base_bind_map = {}      # L2名 -> 5月1日绑码商户数
    base_shop_map = {}      # L2名 -> 5月1日合作门店数
    try:
        # 优先用5月1日JSON基准
        with open(BASE_FILE_MAY) as _f:
            _may = json.load(_f)
        for key, vals in _may.items():
            base_bind_map[key] = vals.get('bind', 0)
            base_shop_map[key] = vals.get('shops', 0)
        print(f'  基准文件加载(5月1日): {len(base_bind_map)} 家代运营商')
    except Exception as e:
        print(f'  5月1日基准加载失败，回退4月1日: {e}')
        try:
            df_base = pd.read_excel(BASE_FILE)
            l2_base = df_base[df_base['层级'] == 'L2']
            for _, row in l2_base.iterrows():
                if pd.notna(row['L2']):
                    key = str(row['L2']).strip()
                    base_bind_map[key] = int(row['职人码绑码商户数']) if pd.notna(row['职人码绑码商户数']) else 0
                    base_shop_map[key] = int(row['合作门店数']) if pd.notna(row.get('合作门店数', None)) else 0
            print(f'  基准文件加载(4月1日): {len(base_bind_map)} 家代运营商')
        except Exception as e2:
            print(f'  基准文件加载失败: {e2}')

    yesterday_data = {}
    try:
        with open(YESTERDAY_ARCHIVE) as f:
            arch = json.load(f)
            yesterday_data = arch.get('data', arch)
    except:
        pass

    week_bind_map = load_weekly_base_bind_map()

    return df, target_map, base_bind_map, base_shop_map, yesterday_data, week_bind_map


def build_rows(df, target_map, base_bind_map, base_shop_map, yesterday_data, week_bind_map):
    rows = []

    l4 = df[df['层级'] == 'L4'].iloc[0] if len(df[df['层级'] == 'L4']) > 0 else None
    l3_rows = df[df['层级'] == 'L3'].copy()
    l2_rows = df[df['层级'] == 'L2'].copy()

    def extract(row, key, default=0):
        v = row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)
        try:
            return float(v) if pd.notna(v) else default
        except:
            return default

    def build_agent_row(row, city_group):
        l2_name = str(row['L2']).strip() if pd.notna(row['L2']) else ''
        agent_short = simplify_name(l2_name)

        bind_cnt  = int(extract(row, '职人码绑码商户数'))
        shop_cnt  = int(extract(row, '合作门店数'))
        bind_rate = bind_cnt / shop_cnt if shop_cnt > 0 else 0

        base_bind    = base_bind_map.get(l2_name)
        base_shop    = base_shop_map.get(l2_name)
        net_add_bind = (bind_cnt - base_bind) if base_bind is not None else '-'
        base_bind_rate = (base_bind / base_shop) if (base_shop and base_shop > 0) else None
        bind_rate_change = (bind_rate - base_bind_rate) if base_bind_rate is not None else None
        week_base_bind = week_bind_map.get(l2_name)
        week_net_add = (bind_cnt - week_base_bind) if week_base_bind is not None else '-'

        dongxiao_cnt  = int(extract(row, '职人码有效动销门店数'))
        dongxiao_rate = extract(row, '职人码有效动销率')
        if isinstance(dongxiao_rate, float) and dongxiao_rate > 1:
            dongxiao_rate /= 100

        store_gtv = extract(row, '店转GTV')
        real_gtv  = extract(row, '周期内核销实付GTV')
        gtv_pen   = extract(row, '店转GTV渗透率(目标16.5%)')
        if isinstance(gtv_pen, float) and gtv_pen > 1:
            gtv_pen /= 100

        avg_price = extract(row, '店转客单均价')

        target_val   = target_map.get(l2_name, '-')
        achieve_rate = (dongxiao_cnt / target_val) if (target_val != '-' and target_val > 0) else None

        return {
            'type': 'agent',
            'city_group': city_group_simple(city_group),
            'name': agent_short,
            'manager': str(row['姓名']) if pd.notna(row['姓名']) else '',
            'shop_cnt': shop_cnt,
            'bind_cnt': bind_cnt,
            'bind_rate': bind_rate,
            'net_add_bind': net_add_bind,
            'bind_rate_change': bind_rate_change,
            'week_net_add': week_net_add,
            'dongxiao_cnt': dongxiao_cnt,
            'dongxiao_rate': dongxiao_rate,
            'store_gtv': store_gtv,
            'gtv_pen': gtv_pen,
            'real_gtv': real_gtv,
            'avg_price': avg_price,
            'target': target_val,
            'achieve_rate': achieve_rate,
        }

    def build_city_row(row, agents_under):
        cg = city_group_simple(str(row['L3']) if pd.notna(row['L3']) else '')
        bind_cnt      = int(extract(row, '职人码绑码商户数'))
        shop_cnt      = int(extract(row, '合作门店数'))
        bind_rate     = bind_cnt / shop_cnt if shop_cnt > 0 else 0
        dongxiao_cnt  = int(extract(row, '职人码有效动销门店数'))
        dongxiao_rate = extract(row, '职人码有效动销率')
        if isinstance(dongxiao_rate, float) and dongxiao_rate > 1:
            dongxiao_rate /= 100
        store_gtv = extract(row, '店转GTV')
        real_gtv  = extract(row, '周期内核销实付GTV')
        gtv_pen   = extract(row, '店转GTV渗透率(目标16.5%)')
        if isinstance(gtv_pen, float) and gtv_pen > 1:
            gtv_pen /= 100
        avg_price = extract(row, '店转客单均价')

        total_target = sum(a['target'] for a in agents_under if a['target'] != '-')
        achieve_rate = (dongxiao_cnt / total_target) if total_target > 0 else None
        net_adds = [a['net_add_bind'] for a in agents_under if a['net_add_bind'] != '-']
        cg_net_add = sum(net_adds) if net_adds else '-'
        week_adds = [a['week_net_add'] for a in agents_under if a['week_net_add'] != '-']
        cg_week_net_add = sum(week_adds) if week_adds else '-'
        # 城市群绑码率变化：用当前绑码率 vs 基准绑码率（基准数据直接从L3行计算如无，则用子行推算）
        # 这里直接用 bind_cnt/shop_cnt 当前 vs 基准：取子行有基准的加总
        base_bind_sum = sum(base_bind_map.get(a['name'] if '-' not in a.get('name','') else None, 0) for a in agents_under)
        base_shop_sum = sum(base_shop_map.get(a['name'] if '-' not in a.get('name','') else None, 0) for a in agents_under)
        # 更可靠：直接用 agent rows 的 bind_rate_change 加权平均（按合作门店数加权）
        valid_agents = [a for a in agents_under if a.get('bind_rate_change') is not None and a['shop_cnt'] > 0]
        if valid_agents:
            total_shop = sum(a['shop_cnt'] for a in valid_agents)
            cg_brc = sum(a['bind_rate_change'] * a['shop_cnt'] for a in valid_agents) / total_shop if total_shop > 0 else None
        else:
            cg_brc = None

        return {
            'type': 'city_group',
            'city_group': cg,
            'name': cg,
            'manager': str(row['姓名']) if pd.notna(row['姓名']) else '',
            'shop_cnt': shop_cnt,
            'bind_cnt': bind_cnt,
            'bind_rate': bind_rate,
            'net_add_bind': cg_net_add,
            'bind_rate_change': cg_brc,
            'week_net_add': cg_week_net_add,
            'dongxiao_cnt': dongxiao_cnt,
            'dongxiao_rate': dongxiao_rate,
            'store_gtv': store_gtv,
            'gtv_pen': gtv_pen,
            'real_gtv': real_gtv,
            'avg_price': avg_price,
            'target': total_target if total_target > 0 else '-',
            'achieve_rate': achieve_rate,
        }

    # L4 汇总行
    if l4 is not None:
        bind_cnt      = int(extract(l4, '职人码绑码商户数'))
        shop_cnt      = int(extract(l4, '合作门店数'))
        bind_rate     = bind_cnt / shop_cnt if shop_cnt > 0 else 0
        dongxiao_cnt  = int(extract(l4, '职人码有效动销门店数'))
        dongxiao_rate = extract(l4, '职人码有效动销率')
        if isinstance(dongxiao_rate, float) and dongxiao_rate > 1:
            dongxiao_rate /= 100
        store_gtv = extract(l4, '店转GTV')
        real_gtv  = extract(l4, '周期内核销实付GTV')
        gtv_pen   = extract(l4, '店转GTV渗透率(目标16.5%)')
        if isinstance(gtv_pen, float) and gtv_pen > 1:
            gtv_pen /= 100
        avg_price    = extract(l4, '店转客单均价')
        total_target = sum(v for v in target_map.values() if isinstance(v, (int, float)))
        achieve_rate = dongxiao_cnt / total_target if total_target > 0 else None
        # 汇总行：基准绑码率（从基准文件L4或全部L2汇总）
        base_bind_total = sum(base_bind_map.values()) if base_bind_map else 0
        base_shop_total = sum(base_shop_map.values()) if base_shop_map else 0
        base_bind_rate_total = base_bind_total / base_shop_total if base_shop_total > 0 else None
        summary_brc = (bind_rate - base_bind_rate_total) if base_bind_rate_total is not None else None
        week_bind_total = sum(week_bind_map.values()) if week_bind_map else 0
        summary_week_net = (bind_cnt - week_bind_total) if week_bind_total > 0 else '-'
        rows.append({
            'type': 'summary',
            'city_group': '高线区域汇总',
            'name': '高线区域汇总',
            'manager': '李俊',
            'shop_cnt': shop_cnt,
            'bind_cnt': bind_cnt,
            'bind_rate': bind_rate,
            'net_add_bind': (bind_cnt - base_bind_total) if base_bind_total > 0 else '-',
            'bind_rate_change': summary_brc,
            'week_net_add': summary_week_net,
            'dongxiao_cnt': dongxiao_cnt,
            'dongxiao_rate': dongxiao_rate,
            'store_gtv': store_gtv,
            'gtv_pen': gtv_pen,
            'real_gtv': real_gtv,
            'avg_price': avg_price,
            'target': int(total_target),
            'achieve_rate': achieve_rate,
        })

    for _, cg_row in l3_rows.iterrows():
        cg_name    = str(cg_row['L3']) if pd.notna(cg_row['L3']) else ''
        agents     = l2_rows[l2_rows['L3'] == cg_name]
        agent_rows = [build_agent_row(ag_row, cg_name) for _, ag_row in agents.iterrows()]
        agent_rows.sort(key=lambda x: x['store_gtv'], reverse=True)
        rows.append(build_city_row(cg_row, agent_rows))
        rows.extend(agent_rows)

    return rows


# ── 颜色 ──────────────────────────────────────────────────
COLOR_HEADER       = 'DBEAFE'
COLOR_SUMMARY      = '2563EB'
COLOR_SUMMARY_FONT = 'FFFFFF'

CITY_BG_COLORS = {
    '粤闽浙城市群': 'EF4444',
    '粤海城市群':   'F97316',
    '苏鲁豫城市群': '3B82F6',
    '苏皖城市群':   '22C55E',
    '苏浙城市群':   'EAB308',
    '新甘蒙城市群': 'A855F7',
}
CITY_ROW_COLORS = {
    '粤闽浙城市群': 'FEF2F2',
    '粤海城市群':   'FFF7ED',
    '苏鲁豫城市群': 'EFF6FF',
    '苏皖城市群':   'F0FDF4',
    '苏浙城市群':   'FEFCE8',
    '新甘蒙城市群': 'FAF5FF',
}


def pct(v, digits=1):
    if v is None: return '-'
    return f'{v*100:.{digits}f}%'

def num(v, digits=0):
    if v is None: return '-'
    return f'{v:,.{digits}f}'

def color_pen(v):
    if v is None: return None
    if v >= 0.20:  return '70AD47'
    if v >= 0.165: return 'FFD966'
    return 'FF7070'

def color_achieve(v):
    if v is None: return None
    if v >= 0.90: return '70AD47'
    if v >= 0.70: return 'FFD966'
    return 'FF7070'

def color_bind_rate(v):
    if v is None: return None
    if v >= 0.70: return '70AD47'
    if v >= 0.50: return 'FFD966'
    return 'FF7070'

def gradient_color(rank, total):
    """根据排名(1=最高)和总数，返回绿→黄→红渐变色hex。"""
    if total <= 1:
        return '70AD47'
    ratio = (rank - 1) / (total - 1)  # 0.0(最高,绿) ~ 1.0(最低,红)
    if ratio <= 0.5:
        t = ratio / 0.5
        r = int(112 + (255 - 112) * t)
        g = int(173 + (211 - 173) * t)
        b = int(71  + (102 - 71)  * t)
    else:
        t = (ratio - 0.5) / 0.5
        r = int(255 + (255 - 255) * t)
        g = int(211 + (112 - 211) * t)
        b = int(102 + (102 - 102) * t)
    return f'{r:02X}{g:02X}{b:02X}'

def build_rank_maps(rows, types_included):
    """
    按城市群分组，对 bind_rate 和 gtv_pen 分别从高到低排名。
    返回 {(city_group, row_name): {'bind_rank': int, 'bind_total': int, 'pen_rank': int, 'pen_total': int}}
    """
    from collections import defaultdict
    cg_groups = defaultdict(list)
    for r in rows:
        if r['type'] in types_included:
            cg_groups[r.get('city_group', '')].append(r)

    rank_map = {}
    for cg, group in cg_groups.items():
        # 绑码率排名
        valid_bind = [(r, r['bind_rate']) for r in group if r['bind_rate'] is not None]
        valid_bind.sort(key=lambda x: x[1], reverse=True)
        for rank, (r, _) in enumerate(valid_bind, 1):
            key = (cg, r['name'])
            if key not in rank_map:
                rank_map[key] = {}
            rank_map[key]['bind_rank'] = rank
            rank_map[key]['bind_total'] = len(valid_bind)
        # 渗透率排名
        valid_pen = [(r, r['gtv_pen']) for r in group if r['gtv_pen'] is not None]
        valid_pen.sort(key=lambda x: x[1], reverse=True)
        for rank, (r, _) in enumerate(valid_pen, 1):
            key = (cg, r['name'])
            if key not in rank_map:
                rank_map[key] = {}
            rank_map[key]['pen_rank'] = rank
            rank_map[key]['pen_total'] = len(valid_pen)
    return rank_map

def make_border():
    thin = Side(style='thin', color='A0A0A0')
    return Border(left=thin, right=thin, top=thin, bottom=thin)

def set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ── Sheet1：城市群维度（白底，13列）─────────────────────────
# 列顺序: 城市群|负责人|合作门店数|绑码商户数|绑码率|月净增绑码数|月绑码率变化|
#         有效动销门店数|动销率|店转GTV|实付GTV|渗透率|客单均价
def write_sheet1(ws, rows):
    # Sheet1: 6个城市群横向比较，全部一起排名
    city_rows = [r for r in rows if r['type'] == 'city_group']
    # 绑码率排名
    bind_sorted = sorted(city_rows, key=lambda r: r['bind_rate'] if r['bind_rate'] is not None else -1, reverse=True)
    bind_rank = {r['name']: (i+1, len(bind_sorted)) for i, r in enumerate(bind_sorted)}
    # 渗透率排名
    pen_sorted = sorted(city_rows, key=lambda r: r['gtv_pen'] if r['gtv_pen'] is not None else -1, reverse=True)
    pen_rank = {r['name']: (i+1, len(pen_sorted)) for i, r in enumerate(pen_sorted)}

    NCOLS = 14
    ws.merge_cells(f'A1:{get_column_letter(NCOLS)}1')
    c = ws['A1']
    c.value = f'高线区域职人码看板  {TODAY}'
    c.font = Font(name='微软雅黑', bold=True, size=14, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='1F4E79')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    headers = [
        '城市群', '负责人', '合作门店数', '绑码商户数', '绑码率',
        '月净增\n绑码数', '周净增\n绑码数', '月绑码率\n变化',
        '有效动销门店数', '动销率', '店转GTV（元）', '实付GTV（元）',
        '店转GTV渗透率', '店转客单\n均价'
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.fill = PatternFill('solid', fgColor=COLOR_HEADER)
        cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F4E79')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = make_border()
    ws.row_dimensions[2].height = 36

    row_idx = 3
    for r in rows:
        if r['type'] not in ('summary', 'city_group'):
            continue
        is_summary = r['type'] == 'summary'
        cg = r.get('city_group', '')

        brc = r.get('bind_rate_change')
        brc_str = ('+' if brc > 0 else '') + pct(brc) if brc is not None else '-'

        values = [
            r['name'], r['manager'],
            r['shop_cnt'], r['bind_cnt'], pct(r['bind_rate']),
            r.get('net_add_bind', '-'), r.get('week_net_add', '-'), brc_str,
            r['dongxiao_cnt'], pct(r['dongxiao_rate']),
            num(r['store_gtv']), num(r['real_gtv']),
            pct(r['gtv_pen']),
            num(r['avg_price']),
        ]

        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = make_border()
            cell.alignment = Alignment(horizontal='center', vertical='center')

            if is_summary:
                cell.fill = PatternFill('solid', fgColor=COLOR_SUMMARY)
                cell.font = Font(name='微软雅黑', bold=True, size=11, color=COLOR_SUMMARY_FONT)
            else:
                cell.fill = PatternFill('solid', fgColor='FFFFFF')
                cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F2937')
                if col == 1:
                    cg_color = CITY_BG_COLORS.get(cg, '3B82F6')
                    thin = Side(style='thin', color='A0A0A0')
                    thick = Side(style='medium', color=cg_color)
                    cell.border = Border(left=thick, right=thin, top=thin, bottom=thin)

            # 色阶（汇总行不着色，城市群行用全局排名动态色阶）
            if not is_summary:
                if col == 5:   # 绑码率
                    br, bt = bind_rank.get(r['name'], (None, None))
                    if br is not None:
                        c2 = gradient_color(br, bt)
                        cell.fill = PatternFill('solid', fgColor=c2)
                        cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F1F1F')
                if col == 13:  # 渗透率（+1因为加了周净增列）
                    pr, pt = pen_rank.get(r['name'], (None, None))
                    if pr is not None:
                        c2 = gradient_color(pr, pt)
                        cell.fill = PatternFill('solid', fgColor=c2)
                        cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F1F1F')

        ws.row_dimensions[row_idx].height = 24
        row_idx += 1


# ── Sheet2：代运营商维度（15列）──────────────────────────────
# 列顺序: 城市群/代运营商|负责人|合作门店数|绑码商户数|绑码率|月净增绑码数|周净增绑码数|月绑码率变化|
#         有效动销门店数|动销率|店转GTV|实付GTV|渗透率|动销达成率|客单均价
def write_sheet2(ws, rows):
    rank_map = build_rank_maps(rows, types_included={'agent'})
    NCOLS = 14
    ws.merge_cells(f'A1:{get_column_letter(NCOLS)}1')
    c = ws['A1']
    c.value = f'高线区域职人码看板（代运营商维度）  {TODAY}'
    c.font = Font(name='微软雅黑', bold=True, size=14, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='1F4E79')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    headers = [
        '城市群/代运营商', '负责人', '合作门店数', '绑码商户数', '绑码率',
        '月净增\n绑码数', '周净增\n绑码数', '月绑码率\n变化',
        '有效动销门店数', '动销率',
        '店转GTV（元）', '实付GTV（元）',
        '店转GTV渗透率', '店转客单均价'
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.fill = PatternFill('solid', fgColor=COLOR_HEADER)
        cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F4E79')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = make_border()
    ws.row_dimensions[2].height = 36

    row_idx = 3
    current_cg = None

    for r in rows:
        if r['type'] == 'summary':
            continue
        cg      = r.get('city_group', '')
        is_city = r['type'] == 'city_group'
        if is_city:
            current_cg = cg

        if is_city:
            row_bg     = CITY_BG_COLORS.get(cg, '3B82F6')
            font_color = 'FFFFFF'
            is_bold    = True
            font_size  = 10
        else:
            row_bg     = CITY_ROW_COLORS.get(current_cg, 'FFFFFF')
            font_color = '1F1F1F'
            is_bold    = False
            font_size  = 10

        brc = r.get('bind_rate_change')
        brc_str = ('+' if brc > 0 else '') + pct(brc) if brc is not None else '-'

        values = [
            r['name'], r['manager'],
            r['shop_cnt'], r['bind_cnt'], pct(r['bind_rate']),
            r.get('net_add_bind', '-'), r.get('week_net_add', '-'), brc_str,
            r['dongxiao_cnt'], pct(r['dongxiao_rate']),
            num(r['store_gtv']), num(r['real_gtv']),
            pct(r['gtv_pen']),
            num(r['avg_price']),
        ]

        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = make_border()
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.fill = PatternFill('solid', fgColor=row_bg)
            cell.font = Font(name='微软雅黑', bold=is_bold, size=font_size, color=font_color)

            if not is_city:
                rk = rank_map.get((cg, r['name']), {})
                if col == 5:   # 绑码率（动态色阶）
                    br = rk.get('bind_rank')
                    bt = rk.get('bind_total')
                    if br is not None and bt:
                        c2 = gradient_color(br, bt)
                        cell.fill = PatternFill('solid', fgColor=c2)
                        cell.font = Font(name='微软雅黑', size=font_size, color='1F1F1F')
                if col == 13:  # 渗透率（动态色阶，+1因加了周净增列）
                    pr = rk.get('pen_rank')
                    pt = rk.get('pen_total')
                    if pr is not None and pt:
                        c2 = gradient_color(pr, pt)
                        cell.fill = PatternFill('solid', fgColor=c2)
                        cell.font = Font(name='微软雅黑', size=font_size, color='1F1F1F')


        ws.row_dimensions[row_idx].height = 22 if is_city else 20
        row_idx += 1


def write_combined_sheet(ws, rows):
    """合并Sheet：城市群汇总在上，各城市群+代运营商明细在下。"""
    rank_map = build_rank_maps(rows, types_included={'agent'})
    NCOLS = 14

    # 大标题
    ws.merge_cells(f'A1:{get_column_letter(NCOLS)}1')
    c = ws['A1']
    c.value = f'高线区域职人码看板  {TODAY}'
    c.font = Font(name='微软雅黑', bold=True, size=14, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='1F4E79')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # 区域汇总小标题
    ws.merge_cells(f'A2:{get_column_letter(NCOLS)}2')
    c2 = ws['A2']
    c2.value = '▌ 城市群汇总'
    c2.font = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
    c2.fill = PatternFill('solid', fgColor='2E75B6')
    c2.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[2].height = 22

    headers = [
        '城市群/代运营商', '负责人', '合作门店数', '绑码商户数', '绑码率',
        '月净增\n绑码数', '周净增\n绑码数', '月绑码率\n变化',
        '有效动销门店数', '动销率',
        '店转GTV（元）', '实付GTV（元）',
        '店转GTV渗透率', '店转客单均价'
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.fill = PatternFill('solid', fgColor=COLOR_HEADER)
        cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F4E79')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = make_border()
    ws.row_dimensions[3].height = 36

    row_idx = 4

    # ── 第一部分：汇总行 + 6个城市群（无代运营商）
    city_rows = [r for r in rows if r['type'] == 'city_group']
    bind_sorted = sorted(city_rows, key=lambda r: r['bind_rate'] if r['bind_rate'] is not None else -1, reverse=True)
    bind_rank_cg = {r['name']: (i+1, len(bind_sorted)) for i, r in enumerate(bind_sorted)}
    pen_sorted = sorted(city_rows, key=lambda r: r['gtv_pen'] if r['gtv_pen'] is not None else -1, reverse=True)
    pen_rank_cg = {r['name']: (i+1, len(pen_sorted)) for i, r in enumerate(pen_sorted)}

    for r in rows:
        if r['type'] not in ('summary', 'city_group'):
            continue
        is_summary = r['type'] == 'summary'
        cg = r.get('city_group', '')
        brc = r.get('bind_rate_change')
        brc_str = ('+' if brc > 0 else '') + pct(brc) if brc is not None else '-'
        values = [
            r['name'], r['manager'],
            r['shop_cnt'], r['bind_cnt'], pct(r['bind_rate']),
            r.get('net_add_bind', '-'), r.get('week_net_add', '-'), brc_str,
            r['dongxiao_cnt'], pct(r['dongxiao_rate']),
            num(r['store_gtv']), num(r['real_gtv']),
            pct(r['gtv_pen']),
            num(r['avg_price']),
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = make_border()
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if is_summary:
                cell.fill = PatternFill('solid', fgColor=COLOR_SUMMARY)
                cell.font = Font(name='微软雅黑', bold=True, size=11, color=COLOR_SUMMARY_FONT)
            else:
                cell.fill = PatternFill('solid', fgColor='FFFFFF')
                cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F2937')
                if col == 1:
                    cg_color = CITY_BG_COLORS.get(cg, '3B82F6')
                    thick = Side(style='medium', color=cg_color)
                    thin_s = Side(style='thin', color='A0A0A0')
                    cell.border = Border(left=thick, right=thin_s, top=thin_s, bottom=thin_s)
                if not is_summary:
                    if col == 5:
                        br, bt = bind_rank_cg.get(r['name'], (None, None))
                        if br is not None:
                            cell.fill = PatternFill('solid', fgColor=gradient_color(br, bt))
                            cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F1F1F')
                    if col == 13:
                        pr, pt = pen_rank_cg.get(r['name'], (None, None))
                        if pr is not None:
                            cell.fill = PatternFill('solid', fgColor=gradient_color(pr, pt))
                            cell.font = Font(name='微软雅黑', bold=True, size=10, color='1F1F1F')
        ws.row_dimensions[row_idx].height = 24
        row_idx += 1

    # 空行分隔
    row_idx += 1

    # ── 第二部分：各城市群标题 + 代运营商明细
    current_cg = None
    for r in rows:
        if r['type'] == 'summary':
            continue
        cg = r.get('city_group', '')
        is_city = r['type'] == 'city_group'

        if is_city:
            current_cg = cg
            # 城市群分组标题行（橙色）
            ws.merge_cells(f'A{row_idx}:{get_column_letter(NCOLS)}{row_idx}')
            mgr = r['manager']
            cg_cell = ws[f'A{row_idx}']
            cg_cell.value = f'▶ {r["name"]}（{mgr}）'
            cg_color = CITY_BG_COLORS.get(cg, '3B82F6')
            cg_cell.fill = PatternFill('solid', fgColor=cg_color)
            cg_cell.font = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
            cg_cell.alignment = Alignment(horizontal='left', vertical='center')
            ws.row_dimensions[row_idx].height = 22
            row_idx += 1
            continue

        # 代运营商行
        row_bg = CITY_ROW_COLORS.get(current_cg, 'FFFFFF')
        brc = r.get('bind_rate_change')
        brc_str = ('+' if brc > 0 else '') + pct(brc) if brc is not None else '-'
        values = [
            r['name'], r['manager'],
            r['shop_cnt'], r['bind_cnt'], pct(r['bind_rate']),
            r.get('net_add_bind', '-'), r.get('week_net_add', '-'), brc_str,
            r['dongxiao_cnt'], pct(r['dongxiao_rate']),
            num(r['store_gtv']), num(r['real_gtv']),
            pct(r['gtv_pen']),
            num(r['avg_price']),
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = make_border()
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.fill = PatternFill('solid', fgColor=row_bg)
            cell.font = Font(name='微软雅黑', size=10, color='1F1F1F')
            rk = rank_map.get((cg, r['name']), {})
            if col == 5:
                br = rk.get('bind_rank'); bt = rk.get('bind_total')
                if br is not None and bt:
                    cell.fill = PatternFill('solid', fgColor=gradient_color(br, bt))
            if col == 13:
                pr = rk.get('pen_rank'); pt = rk.get('pen_total')
                if pr is not None and pt:
                    cell.fill = PatternFill('solid', fgColor=gradient_color(pr, pt))
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1


def main():
    today_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/files/1776069384.xlsx'
    out_file   = f'/tmp/高线区域职人码看板_{TODAY_LABEL}.xlsx'

    print(f'读取今日文件: {today_file}')
    df, target_map, base_bind_map, base_shop_map, yesterday_data, week_bind_map = load_data(today_file)
    print(f'目标代运营商数: {len(target_map)}')
    print(f'昨日存档代运营商: {list(yesterday_data.keys())}')
    print(f'周净增基准代运营商: {len(week_bind_map)}家')

    rows = build_rows(df, target_map, base_bind_map, base_shop_map, yesterday_data, week_bind_map)
    print(f'生成行数: {len(rows)} 条')

    wb  = Workbook()
    ws1 = wb.active
    ws1.title = '高线区域职人码看板'
    write_combined_sheet(ws1, rows)
    set_col_widths(ws1, [22, 8, 10, 10, 9, 9, 9, 10, 12, 9, 15, 15, 12, 10, 12])
    ws1.freeze_panes = 'A4'

    wb.save(out_file)
    print(f'已生成: {out_file}')
    return out_file

if __name__ == '__main__':
    main()
