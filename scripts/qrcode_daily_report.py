#!/usr/bin/env python3
"""
粤闽浙城市群 线下码当日新增日报
逻辑：每天9:00拉取昨日月累计数据 → 与前日存档做差值 → 生成Excel → 发大象
每月1日起清零（不做差值，直接存档）

配置参数（已填好）：
  ORG_ID    = 20903327  (高线粤闽浙城市群)
  REPORT_ID = 478
  TABLE_ID  = 1200
  DX_UID    = user:3264994429
"""

import os, sys, json, subprocess, urllib.request, datetime, warnings
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
warnings.filterwarnings('ignore')

DATA_DIR  = os.path.expanduser('~/.openclaw/qrcode_data')
COOKIE_FILE = os.path.expanduser('~/.openclaw/workspace/scripts/.apollo_cookie')
os.makedirs(DATA_DIR, exist_ok=True)

ORG_ID    = 20903327
REPORT_ID = 478
TABLE_ID  = 1200
DX_UID    = 'user:3264994429'
ORG_NAME  = '粤闽浙城市群'
UID       = '23482986'

BASE_URL  = 'https://a.dper.com'

# 代运营商关键词（用于过滤 attribute_org_name）
ORG_KEYWORDS = ['巨浪', '柏万', '小花猫', '广通', '哲光', '汐洋']

# 代运营商简称映射
ORG_SHORT = {
    '惠州市巨浪': '惠州巨浪',
    '惠州市柏万': '惠州柏万',
    '泉州市小花猫': '泉州小花猫',
    '惠安广通': '惠安广通',
    '慈溪哲光': '慈溪哲光',
    '义乌市汐洋': '义乌汐洋',
}

# 代运营商颜色
ORG_COLORS = {
    '惠州巨浪':  'FFE6CC',
    '惠州柏万':  'D5E8D4',
    '泉州小花猫': 'DAE8FC',
    '惠安广通':  'FFF2CC',
    '慈溪哲光':  'F8CECC',
    '义乌汐洋':  'D0E0E3',
}

HEADER_BG  = '2F5597'
SUB_HDR_BG = '4472C4'

COLUMNS = [
    "shop_name", "shop_id", "employee_name", "employee_id",
    "attribute_org_name", "sale_grid_name",
    "cat0_name", "cat1_name", "front_city_name", "city_name",
    "qr_cullrisk_actual_pay_consume_gtv",
    "qr_cullrisk_consume_order_cnt",
    "qr_cullrisk_gtv_profit_amt",
    "qr_ground_cullrisk_actual_pay_consume_gtv",
    "qr_lkb_cullrisk_actual_pay_consume_gtv",
    "qr_cmpn_cullrisk_actual_pay_consume_gtv",
    "qr_technician_cullrisk_actual_pay_consume_gtv",
    "old_shop_qr_cullrisk_actual_pay_consume_gtv",
    "new_shop_qr_cullrisk_actual_pay_consume_gtv",
]

COL_MAP = {
    'shop_id':     '门店id',
    'shop_name':   '门店名称',
    'cat0_name':   '一级品类',
    'cat1_name':   '二级品类',
    'city_name':   '城市',
    'front_city_name': '前台城市',
    'employee_id': '销售ID',
    'employee_name': '销售姓名',
    'attribute_org_name': '代运营商',
    'sale_grid_name': '网格',
    'qr_cullrisk_consume_order_cnt':             '线下码订单数',
    'qr_cullrisk_actual_pay_consume_gtv':        '线下码GTV',
    'qr_cullrisk_gtv_profit_amt':                '线下码利润',
    'qr_ground_cullrisk_actual_pay_consume_gtv': '地推码GTV',
    'qr_lkb_cullrisk_actual_pay_consume_gtv':    '揽客宝GTV',
    'qr_cmpn_cullrisk_actual_pay_consume_gtv':   '活动码GTV',
    'qr_technician_cullrisk_actual_pay_consume_gtv': '技师码GTV',
    'old_shop_qr_cullrisk_actual_pay_consume_gtv': '存量门店GTV',
    'new_shop_qr_cullrisk_actual_pay_consume_gtv': '新门店GTV',
}

NUM_COLS = ['线下码GTV', '线下码订单数', '地推码GTV', '揽客宝GTV', '存量门店GTV', '新门店GTV']


def get_cookie():
    with open(COOKIE_FILE) as f:
        return f.read().strip()


def fetch_day(date_str, cookie):
    """拉取指定日期的月累计线下码数据（分页，最多500条/页）"""
    all_rows = []
    page = 1
    while True:
        payload = json.dumps([{
            "category": "query", "type": "SmartQuery",
            "params": {"dsl": {
                "date": date_str,
                "reportId": REPORT_ID,
                "tableId": TABLE_ID,
                "pageIndex": page,
                "pageSize": 500,
                "columns": COLUMNS,
                "params": [
                    {"field": "attribute_org_id", "method": "in",
                     "id": 35231, "transformType": 1, "value": ORG_ID}
                ],
                "sorts": []
            }}, "as": "result", "children": []
        }]).encode()

        req = urllib.request.Request(
            f'{BASE_URL}/gw/__cascade__/SmartQuery.query',
            data=payload,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Referer': f'{BASE_URL}/gw/smartreport/',
                'Cookie': cookie,
            })
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
        except Exception as e:
            print(f"[ERROR] 请求失败 page={page}: {e}")
            break

        result = resp.get('data', {}).get('result', {})
        if not isinstance(result, dict):
            print(f"[WARN] 返回异常: {str(result)[:100]}")
            break

        rows = result.get('data', [])
        total = result.get('total', 0)
        if not rows:
            break
        # 字段名映射
        mapped = [{COL_MAP.get(k, k): v for k, v in row.items()} for row in rows]
        all_rows.extend(mapped)
        print(f"  [page {page}] {len(rows)}条，累计{len(all_rows)}/{total}")
        if len(all_rows) >= total:
            break
        page += 1

    return all_rows


def archive_path(date_str):
    return os.path.join(DATA_DIR, 'data_' + date_str.replace('-', '') + '.json')


def load_archive(date_str):
    p = archive_path(date_str)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        records = json.load(f)
    # 兼容：若存档是原始英文字段名，自动映射为中文
    if records and 'shop_id' in records[0]:
        records = [{COL_MAP.get(k, k): v for k, v in row.items()} for row in records]
    return records


def save_archive(date_str, records):
    with open(archive_path(date_str), 'w') as f:
        json.dump(records, f, ensure_ascii=False, default=str)


def cleanup_old_archives(days=7):
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    removed = 0
    for fname in os.listdir(DATA_DIR):
        if fname.startswith('data_') and fname.endswith('.json'):
            date_str = fname[5:13]
            try:
                fd = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
                if fd < cutoff:
                    os.remove(os.path.join(DATA_DIR, fname))
                    removed += 1
            except Exception:
                pass
    if removed:
        print(f"[INFO] 清理 {removed} 个过期存档")


def to_df(records):
    df = pd.DataFrame(records)
    if '门店id' in df.columns:
        df['门店id'] = df['门店id'].astype(str).str.strip()
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0
    return df


def get_org_short(org_name):
    """从代运营商全名提取简称"""
    if not org_name:
        return '未知'
    org_name = str(org_name)
    for full, short in ORG_SHORT.items():
        if full in org_name:
            return short
    # 去掉后缀"-乐生活组"等
    base = org_name.split('-')[0].strip()
    return base


def make_excel(result_df, yesterday_str, today_str, out_path):
    """生成代运营商维度差值Excel（两个sheet）"""
    thin = Side(style='thin', color='CCCCCC')
    bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)

    def hcell(ws, row, col, val, bg=HEADER_BG, fg='FFFFFF', bold=True):
        c = ws.cell(row=row, column=col, value=val)
        c.fill = PatternFill('solid', fgColor=bg)
        c.font = Font(bold=bold, color=fg, size=10)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = bdr
        return c

    def dcell(ws, row, col, val, bg=None, fmt=None, bold=False):
        c = ws.cell(row=row, column=col, value=val)
        if bg:
            c.fill = PatternFill('solid', fgColor=bg)
        c.font = Font(bold=bold, size=10)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = bdr
        if fmt:
            c.number_format = fmt
        return c

    wb = Workbook()
    wb.remove(wb.active)

    # ── Sheet1: 代运营商汇总 ─────────────────────────────────
    ws1 = wb.create_sheet(f'代运营商汇总_{today_str.replace("-", "")}')

    # 大标题
    ws1.merge_cells(f'A1:K1')
    t = ws1.cell(row=1, column=1, value=f'{ORG_NAME} 线下码当日新增（{today_str}）')
    t.fill = PatternFill('solid', fgColor=HEADER_BG)
    t.font = Font(bold=True, color='FFFFFF', size=13)
    t.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 30

    # 列头
    SUMCOLS = [
        '代运营商',
        f'前日GTV({yesterday_str[5:]})',
        f'昨日GTV({today_str[5:]})',
        '当日新增GTV',
        f'前日订单({yesterday_str[5:]})',
        f'昨日订单({today_str[5:]})',
        '当日新增订单',
        '新增地推码GTV',
        '新增揽客宝GTV',
        '门店数',
        '月累计GTV变化',
    ]
    for ci, h in enumerate(SUMCOLS, 1):
        hcell(ws1, 2, ci, h, bg=SUB_HDR_BG)
    ws1.row_dimensions[2].height = 36

    # 按代运营商分组
    result_df['代运营商简称'] = result_df['代运营商'].apply(get_org_short)
    summary_rows = []
    for org_short, grp in result_df.groupby('代运营商简称'):
        summary_rows.append({
            '代运营商': org_short,
            '前日GTV':    grp['线下码GTV_前'].sum(),
            '昨日GTV':    grp['线下码GTV_后'].sum(),
            '新增GTV':    grp['线下码GTV_新增'].sum(),
            '前日订单':   grp['线下码订单数_前'].sum(),
            '昨日订单':   grp['线下码订单数_后'].sum(),
            '新增订单':   grp['线下码订单数_新增'].sum(),
            '新增地推':   grp['地推码GTV_新增'].sum(),
            '新增揽客宝': grp['揽客宝GTV_新增'].sum(),
            '门店数':     len(grp),
            '累计变化':   f"{grp['线下码GTV_前'].sum():.0f}→{grp['线下码GTV_后'].sum():.0f}",
        })
    summary_rows.sort(key=lambda x: -x['新增GTV'])

    for ri, r in enumerate(summary_rows, 3):
        bg = ORG_COLORS.get(r['代运营商'], 'FFFFFF')
        dcell(ws1, ri, 1,  r['代运营商'],  bg=bg, bold=True)
        dcell(ws1, ri, 2,  r['前日GTV'],   bg=bg, fmt='#,##0.00')
        dcell(ws1, ri, 3,  r['昨日GTV'],   bg=bg, fmt='#,##0.00')
        dcell(ws1, ri, 4,  r['新增GTV'],   bg=bg, fmt='#,##0.00', bold=True)
        dcell(ws1, ri, 5,  r['前日订单'],  bg=bg, fmt='#,##0')
        dcell(ws1, ri, 6,  r['昨日订单'],  bg=bg, fmt='#,##0')
        dcell(ws1, ri, 7,  r['新增订单'],  bg=bg, fmt='#,##0', bold=True)
        dcell(ws1, ri, 8,  r['新增地推'],  bg=bg, fmt='#,##0.00')
        dcell(ws1, ri, 9,  r['新增揽客宝'],bg=bg, fmt='#,##0.00')
        dcell(ws1, ri, 10, r['门店数'],    bg=bg)
        dcell(ws1, ri, 11, r['累计变化'],  bg=bg)

    # 合计行
    tr = len(summary_rows) + 3
    total_bg = 'F2F2F2'
    dcell(ws1, tr, 1,  '合计', bg=total_bg, bold=True)
    dcell(ws1, tr, 2,  result_df['线下码GTV_前'].sum(),    bg=total_bg, bold=True, fmt='#,##0.00')
    dcell(ws1, tr, 3,  result_df['线下码GTV_后'].sum(),    bg=total_bg, bold=True, fmt='#,##0.00')
    dcell(ws1, tr, 4,  result_df['线下码GTV_新增'].sum(),  bg=total_bg, bold=True, fmt='#,##0.00')
    dcell(ws1, tr, 5,  result_df['线下码订单数_前'].sum(), bg=total_bg, bold=True, fmt='#,##0')
    dcell(ws1, tr, 6,  result_df['线下码订单数_后'].sum(), bg=total_bg, bold=True, fmt='#,##0')
    dcell(ws1, tr, 7,  result_df['线下码订单数_新增'].sum(), bg=total_bg, bold=True, fmt='#,##0')
    dcell(ws1, tr, 8,  result_df['地推码GTV_新增'].sum(),  bg=total_bg, bold=True, fmt='#,##0.00')
    dcell(ws1, tr, 9,  result_df['揽客宝GTV_新增'].sum(),  bg=total_bg, bold=True, fmt='#,##0.00')
    dcell(ws1, tr, 10, len(result_df),                     bg=total_bg, bold=True)
    dcell(ws1, tr, 11, '', bg=total_bg)

    for i, w in enumerate([14, 14, 14, 14, 12, 12, 12, 14, 14, 8, 22], 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    # ── Sheet2: 门店明细 ─────────────────────────────────────
    ws2 = wb.create_sheet(f'门店明细_{today_str.replace("-", "")}')
    DCOLS = [
        ('代运营商', '代运营商简称'),
        ('门店名称', '门店名称'),
        ('品类', '一级品类'),
        ('城市', '城市'),
        ('销售姓名', '销售姓名'),
        (f'前日GTV({yesterday_str[5:]})', '线下码GTV_前'),
        (f'昨日GTV({today_str[5:]})',     '线下码GTV_后'),
        ('当日新增GTV', '线下码GTV_新增'),
        (f'前日订单({yesterday_str[5:]})', '线下码订单数_前'),
        (f'昨日订单({today_str[5:]})',     '线下码订单数_后'),
        ('当日新增订单', '线下码订单数_新增'),
        ('新增地推码GTV', '地推码GTV_新增'),
        ('新增揽客宝GTV', '揽客宝GTV_新增'),
    ]

    ws2.merge_cells(f'A1:{get_column_letter(len(DCOLS))}1')
    t2 = ws2.cell(row=1, column=1, value=f'{ORG_NAME} 线下码门店明细（{today_str}）')
    t2.fill = PatternFill('solid', fgColor=HEADER_BG)
    t2.font = Font(bold=True, color='FFFFFF', size=13)
    t2.alignment = Alignment(horizontal='center', vertical='center')
    ws2.row_dimensions[1].height = 30

    for ci, (h, _) in enumerate(DCOLS, 1):
        hcell(ws2, 2, ci, h, bg=SUB_HDR_BG)

    detail_df = result_df.sort_values(['代运营商简称', '线下码GTV_新增'], ascending=[True, False])
    for ri, (_, row) in enumerate(detail_df.iterrows(), 3):
        org = str(row.get('代运营商简称', ''))
        bg = ORG_COLORS.get(org, 'FFFFFF')
        for ci, (_, col) in enumerate(DCOLS, 1):
            val = row.get(col, '')
            if pd.isna(val):
                val = ''
            fmt = '#,##0.00' if 'GTV' in col else ('#,##0' if '订单' in col else None)
            dcell(ws2, ri, ci, val, bg=bg, fmt=fmt)

    for i, w in enumerate([12, 24, 8, 8, 8, 13, 13, 13, 11, 11, 11, 13, 13], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    ws2.freeze_panes = 'A3'
    ws1.freeze_panes = 'A3'
    wb.save(out_path)
    print(f"[INFO] Excel已保存: {out_path}")


def send_daxiang(file_path, msg):
    cmd = ['openclaw', 'message', 'send',
           '--channel', 'daxiang',
           '--target', DX_UID,
           '--message', msg]
    if file_path and os.path.exists(file_path):
        cmd += ['--media', file_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"[WARN] 发送失败: {r.stderr[:200]}")
    else:
        print("[INFO] 大象消息已发送")


def main():
    cleanup_old_archives(days=7)

    now       = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today     = now.date()
    yesterday = today - datetime.timedelta(days=1)
    day_before = today - datetime.timedelta(days=2)

    y_str  = yesterday.strftime('%Y-%m-%d')
    db_str = day_before.strftime('%Y-%m-%d')

    print(f"[INFO] 运行日期: {today}，报告日期: {y_str}，基准日: {db_str}")

    cookie = get_cookie()
    print(f"[INFO] 拉取 {y_str} 数据...")
    records_y = fetch_day(y_str, cookie)
    if not records_y:
        print(f"[ERROR] {y_str} 无数据，退出")
        sys.exit(1)
    print(f"[INFO] 共 {len(records_y)} 条")

    save_archive(y_str, records_y)
    print(f"[INFO] 已存档 {y_str}")

    records_db = load_archive(db_str)

    # 无前日存档时只存档不做差值（月初第一天有数据时仍可做差值）
    if records_db is None:
        reason = f"无 {db_str} 存档"
        print(f"[INFO] {reason}，只存档不发差值报告")
        send_daxiang('', f'📦 已存档 {y_str} 线下码数据（{len(records_y)}条）\n⚠️ {reason}，今日不输出差值报告')
        return

    # 计算差值
    df_y  = to_df(records_y)
    df_db = to_df(records_db)

    merged = df_y.merge(
        df_db[['门店id'] + NUM_COLS],
        on='门店id', how='outer', suffixes=('_后', '_前')
    )
    for col in NUM_COLS:
        merged[f'{col}_后']   = merged[f'{col}_后'].fillna(0)
        merged[f'{col}_前']   = merged[f'{col}_前'].fillna(0)
        merged[f'{col}_新增'] = merged[f'{col}_后'] - merged[f'{col}_前']

    # 补门店信息（outer join后部分字段可能为NaN）
    info_cols = ['门店id', '门店名称', '销售姓名', '代运营商', '一级品类', '城市']
    info_db = df_db[[c for c in info_cols if c in df_db.columns]].add_suffix('_db').rename(columns={'门店id_db': '门店id'})
    merged = merged.merge(info_db, on='门店id', how='left')
    for col in ['门店名称', '销售姓名', '代运营商', '一级品类', '城市']:
        if col in merged.columns and f'{col}_db' in merged.columns:
            merged[col] = merged[col].fillna(merged[f'{col}_db'])

    merged['代运营商简称'] = merged['代运营商'].apply(get_org_short)
    merged = merged.sort_values('代运营商简称')

    total_new = merged['线下码GTV_新增'].sum()
    print(f"[INFO] 当日新增总GTV: {total_new:.2f}")

    # 生成Excel
    os.makedirs('/tmp/files', exist_ok=True)
    out_file = f'/tmp/files/{ORG_NAME}_线下码当日新增_{y_str.replace("-","")}.xlsx'
    make_excel(merged, db_str, y_str, out_file)

    # 代运营商排行
    org_summary = merged.groupby('代运营商简称')['线下码GTV_新增'].sum().sort_values(ascending=False)
    medal = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣']
    bd_lines = '\n'.join(
        f'{medal[i]} {org}：¥{v:,.0f}' for i, (org, v) in enumerate(org_summary.items())
    )

    msg = (
        f'📊 {ORG_NAME} 线下码当日新增报告（{y_str}）\n\n'
        f'💰 当日新增总GTV：¥{total_new:,.0f}\n\n'
        f'**代运营商排行**\n{bd_lines}\n\n'
        f'含代运营商汇总+门店明细两个sheet 👆'
    )

    send_daxiang(out_file, msg)
    print("[INFO] 完成")


if __name__ == '__main__':
    main()
