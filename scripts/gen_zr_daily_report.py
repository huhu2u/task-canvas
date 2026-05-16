#!/usr/bin/env python3
"""
粤闽浙职人码日播报自动生成脚本
每天9点运行：下载Apollo职人码组织明细(T和T-1) → 生成日播报Excel → 发大象
"""
import subprocess, sys, time, os, json, re, datetime
from pathlib import Path

WORKSPACE = "/root/.openclaw/workspace"
DAXIANG_UID = "3264994429"
SESSION = "apollo"

# Apollo职人码策略管理页面
ZR_URL = "https://apollo.meituan.com/crm-platform?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLXBjLWRhdGEtYnVsbGV0aW4tYm9hcmQlMkZzdHJhdGVneS1tYW5hZ2VtZW50JTJGaW5kZXguaHRtbCUyMyUyRmRhdGEtb3ZlcnZpZXclM0ZzdHJhdGVneUlkJTNENw%253D%253D&pageId=1721888474rcncbe"

# 数据列索引（0-based，组织明细xlsx）
C_LEVEL = 0      # 层级 L2/L3
C_ORG_NAME = 7   # L3组织名称（代运营商主管所在行）
C_GTV_MONTH = 67 # 周期内核销实付GTV
C_ZT_GTV = 39    # 店转GTV
C_ZT_RATE = 41   # 店转GTV渗透率
C_ZT_ORD = 35    # 店转订单量
C_BIND_CNT = 23  # 职人码绑码商户数
C_STORE_CNT = 21 # 合作门店数

# 城市映射
CITY_MAP = {
    "\u6148\u6eaa\u54f2\u5149": "\u4e49\u4e4c",    # 慈溪哲光 → 义乌
    "\u60e0\u5dde\u5e02\u67cf\u4e07": "\u60e0\u9633", # 惠州市柏万 → 惠阳
    "\u60e0\u5dde\u5e02\u5de8\u6d6a": "\u60e0\u5dde", # 惠州市巨浪 → 惠州
    "\u60e0\u5b89\u5e7f\u901a": "\u664b\u6c5f",     # 惠安广通 → 晋江
    "\u4e49\u4e4c\u5e02\u6c50\u6d0b": "\u4e49\u4e4c", # 义乌市汐洋 → 义乌
    "\u6cc9\u5dde\u5e02\u5c0f\u82b1\u732b": "\u6cc9\u5dde", # 泉州市小花猫 → 泉州
    "\u5b81\u590f\u7075\u521b": "\u4e49\u4e4c",     # 宁夏灵创 → 义乌
}

# 代运营商简称映射
ORG_SHORT_MAP = {
    "\u6148\u6eaa\u54f2\u5149": "\u6148\u6eaa\u54f2\u5149",
    "\u60e0\u5dde\u5e02\u67cf\u4e07": "\u60e0\u5dde\u67cf\u4e07",
    "\u60e0\u5dde\u5e02\u5de8\u6d6a": "\u60e0\u5dde\u5de8\u6d6a",
    "\u60e0\u5b89\u5e7f\u901a": "\u60e0\u5b89\u5e7f\u901a",
    "\u4e49\u4e4c\u5e02\u6c50\u6d0b": "\u4e49\u4e4c\u6c50\u6d0b",
    "\u6cc9\u5dde\u5e02\u5c0f\u82b1\u732b": "\u6cc9\u5dde\u5c0f\u82b1\u732b",
    "\u5b81\u590f\u7075\u521b": "\u5b81\u590f\u7075\u521b",
}

# 代运营商排序（与模板一致）
ORG_ORDER = [
    "\u4e49\u4e4c\u5e02\u6c50\u6d0b",  # 义乌市汐洋
    "\u6148\u6eaa\u54f2\u5149",          # 慈溪哲光
    "\u5b81\u590f\u7075\u521b",          # 宁夏灵创
    "\u60e0\u5dde\u5e02\u5de8\u6d6a",   # 惠州市巨浪
    "\u60e0\u5dde\u5e02\u67cf\u4e07",   # 惠州市柏万
    "\u6cc9\u5dde\u5e02\u5c0f\u82b1\u732b", # 泉州市小花猫
    "\u60e0\u5b89\u5e7f\u901a",          # 惠安广通
]


def run_ab(cmd_args, stdin_data=None):
    kwargs = dict(capture_output=True, text=True, timeout=60)
    if stdin_data:
        kwargs['input'] = stdin_data
    r = subprocess.run(["agent-browser"] + cmd_args, **kwargs)
    return r.stdout.strip(), r.returncode


def download_org_detail(date_str, out_path):
    """打开Apollo职人码页面，点击导出下载组织明细Excel"""
    print(f"  下载 {date_str} 组织明细...")

    # 先确认页面已打开
    url_out, _ = run_ab(["get", "url"])
    if "strategy-management" not in url_out:
        run_ab(["open", ZR_URL])
        time.sleep(8)

    # 点击「导出」按钮（Apollo页面上有导出Excel按钮）
    # 先找导出按钮
    find_export_js = """
    (function() {
        var iframe = document.querySelector('iframe');
        var iwin = iframe ? iframe.contentWindow : null;
        if (!iwin) return 'no_iframe';
        var btns = Array.from(iwin.document.querySelectorAll('button, .mtd-btn'));
        var exportBtn = btns.find(b => b.textContent.includes('导出') || b.textContent.includes('Export'));
        if (exportBtn) {
            return 'found:' + exportBtn.textContent.trim();
        }
        return 'not_found';
    })()
    """
    result, _ = run_ab(["eval", "--stdin"], stdin_data=find_export_js)
    print(f"  导出按钮: {result[:100]}")
    return None  # 返回None表示需要用备用方案


def safe_float(val):
    try:
        return float(str(val).replace(',', '').replace('%', '').strip() or 0)
    except:
        return 0.0


def safe_int(val):
    try:
        return int(float(str(val).replace(',', '').strip() or 0))
    except:
        return 0


def parse_org_detail(xlsx_path):
    """解析Apollo职人码组织明细xlsx，返回 {代运营商全名: {L3主管行, L2销售列表}}"""
    import pandas as pd
    df = pd.read_excel(xlsx_path, header=0)
    data = {}
    current_org = None

    for _, row in df.iterrows():
        row_list = list(row)
        if len(row_list) <= max(C_LEVEL, C_GTV_MONTH):
            continue
        level = str(row_list[C_LEVEL]).strip()
        if level == 'L3':
            # 代运营商主管行
            org_name_raw = str(row_list[C_ORG_NAME]).strip()
            # 取代运营商名（去掉"-乐生活组"等后缀）
            org_key = org_name_raw.split('-')[0].strip()
            current_org = org_key
            data[current_org] = {
                'L3': row_list,
                'L2': [],
                'org_name_raw': org_name_raw
            }
        elif level == 'L2' and current_org:
            data[current_org]['L2'].append(row_list)

    return data


def build_report(t_data, t1_data, report_date, yesterday_date):
    """根据T和T-1数据生成播报数据结构"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "\u804c\u4eba\u7801\u6570\u636e"  # 职人码数据

    # 颜色定义
    BLUE_BG = "1d4ed8"
    WHITE = "FFFFFF"
    YELLOW_BG = "FFF9C4"
    ORG_COLORS = ["E3F2FD", "E8F5E9", "FFF3E0", "FCE4EC", "F3E5F5", "E0F7FA", "FFF8E1"]
    HEADER_FONT = Font(name='Arial', bold=True, color=WHITE, size=10)
    TITLE_FONT = Font(name='Arial', bold=True, size=12)

    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def set_header(cell, val, bg=BLUE_BG):
        cell.value = val
        cell.font = Font(name='Arial', bold=True, color=WHITE, size=9)
        cell.fill = PatternFill('solid', start_color=bg)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border

    def set_cell(cell, val, bg=None, bold=False, fmt=None, align='center'):
        cell.value = val
        cell.font = Font(name='Arial', bold=bold, size=9)
        if bg:
            cell.fill = PatternFill('solid', start_color=bg)
        cell.alignment = Alignment(horizontal=align, vertical='center')
        cell.border = border
        if fmt:
            cell.number_format = fmt

    # 列宽
    col_widths = [6, 10, 16, 14, 13, 8, 9, 10, 9, 12, 10, 12, 13, 7, 7, 8]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 36

    # 第1行：大标题
    ws.merge_cells('A1:P1')
    title_cell = ws['A1']
    title_cell.value = f"\u7ca4\u95fd\u6d59\u57ce\u5e02\u7fa4\u804c\u4eba\u7801\u6570\u636e\u8868\uff08{yesterday_date}\uff09"
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    title_cell.fill = PatternFill('solid', start_color='EFF6FF')

    # 第2行：列标题
    headers = [
        "\u57ce\u5e02", "\u4ee3\u8fd0\u8425\u5546", "\u4e3b\u7ba1/\u9500\u552e",
        f"\u6708\u8fbe\u6210GTV\n(\u6838\u9500)",
        f"\u6628\u65e5GTV\n({yesterday_date})",
        "\u65b0\u589e\n\u7ed1\u7801\u6570",
        "\u6708\u804c\u4eba\u7801\n\u7ed1\u7801",
        "\u6708\u804c\u4eba\u7801\n\u7ed1\u7801\u7387",
        "\u6628\u65e5\u5e97\u8f6c\n\u8ba2\u5355\u6570",
        "\u6628\u65e5\n\u5e97\u8f6c GTV",
        "\u6628\u65e5\u5e97\u8f6c\n\u6e17\u900f\u7387",
        "\u5168\u6708\n\u5e97\u8f6c GTV",
        "\u5168\u6708\u5e97\u8f6c\nGTV\u6e17\u900f\u7387",
        "\u7ed1\u7801 T-1",
        "\u7ed1\u7801 T-2",
        "\u5408\u4f5c\n\u95e8\u5e97\u6570"
    ]
    for col, h in enumerate(headers, 1):
        set_header(ws.cell(row=2, column=col), h)

    # 第3行：城市组汇总标题
    ws.merge_cells('A3:P3')
    grp = ws['A3']
    grp.value = "\u25b6 \u57ce\u5e02\u7ec4\u6c47\u603b"
    grp.font = Font(name='Arial', bold=True, size=10)
    grp.fill = PatternFill('solid', start_color='DBEAFE')
    grp.alignment = Alignment(horizontal='left', vertical='center')

    # 构建代运营商汇总数据
    def get_org_data(org_key, t_data, t1_data):
        t = t_data.get(org_key, {})
        t1 = t1_data.get(org_key, {})
        if not t:
            return None
        t_l3 = t.get('L3', [])
        t1_l3 = t1.get('L3', []) if t1 else []

        def g(row, col): return safe_float(row[col]) if len(row) > col else 0.0
        def gi(row, col): return safe_int(row[col]) if len(row) > col else 0

        gtv_month = g(t_l3, C_GTV_MONTH)
        zt_gtv_month = g(t_l3, C_ZT_GTV)
        zt_ord_month = gi(t_l3, C_ZT_ORD)
        bind_cnt = gi(t_l3, C_BIND_CNT)
        store_cnt = gi(t_l3, C_STORE_CNT)

        # 昨日增量 = T - T-1
        zt_gtv_t1 = g(t1_l3, C_ZT_GTV) if t1_l3 else 0
        zt_ord_t1 = gi(t1_l3, C_ZT_ORD) if t1_l3 else 0
        bind_t1 = gi(t1_l3, C_BIND_CNT) if t1_l3 else bind_cnt
        gtv_t1 = g(t1_l3, C_GTV_MONTH) if t1_l3 else 0  # T-1月累计GTV

        # 昨日GTV = T月累计 - T-1月累计
        yest_gtv = gtv_month - gtv_t1 if gtv_t1 > 0 else 0
        yest_zt_gtv = zt_gtv_month - zt_gtv_t1
        yest_zt_ord = zt_ord_month - zt_ord_t1
        yest_bind_inc = bind_cnt - bind_t1

        bind_rate = bind_cnt / store_cnt if store_cnt > 0 else 0
        zt_month_rate = zt_gtv_month / gtv_month if gtv_month > 0 else 0
        yest_zt_rate = yest_zt_gtv / yest_gtv if yest_gtv > 0 else 0

        return {
            'gtv_month': gtv_month,
            'yest_gtv': yest_gtv,
            'bind_inc': yest_bind_inc,
            'bind_cnt': bind_cnt,
            'bind_rate': bind_rate,
            'yest_zt_ord': yest_zt_ord,
            'yest_zt_gtv': yest_zt_gtv,
            'yest_zt_rate': yest_zt_rate,
            'zt_gtv_month': zt_gtv_month,
            'zt_month_rate': zt_month_rate,
            'bind_t1': bind_cnt,       # T日绑码=T-1
            'bind_t2': bind_t1,         # T-1日绑码=T-2
            'store_cnt': store_cnt,
        }

    # 计算合计行
    total_rows = []
    org_data_list = []
    for org_key in ORG_ORDER:
        d = get_org_data(org_key, t_data, t1_data)
        if d:
            org_data_list.append((org_key, d))
            total_rows.append(d)

    def sum_field(f): return sum(d[f] for d in total_rows)

    total_gtv = sum_field('gtv_month')
    total_yest_gtv = sum_field('yest_gtv')
    total_bind_inc = sum_field('bind_inc')
    total_bind = sum_field('bind_cnt')
    total_store = sum_field('store_cnt')
    total_zt_gtv_m = sum_field('zt_gtv_month')
    total_yest_zt_gtv = sum_field('yest_zt_gtv')
    total_yest_zt_ord = sum_field('yest_zt_ord')

    # 第4行：合计
    row = 4
    cells_data = [
        "\u5408\u8ba1",  # 合计
        "\u7ca4\u95fd\u6d59\u5408\u8ba1",  # 粤闽浙合计
        "",
        total_gtv, total_yest_gtv, total_bind_inc, total_bind,
        total_bind / total_store if total_store else 0,
        total_yest_zt_ord, total_yest_zt_gtv,
        total_yest_zt_gtv / total_yest_gtv if total_yest_gtv else 0,
        total_zt_gtv_m,
        total_zt_gtv_m / total_gtv if total_gtv else 0,
        total_bind, sum_field('bind_t2'), total_store
    ]
    fmts = [None, None, None, '#,##0.00', '#,##0.00', None, None, '0.0%', None, '#,##0.00', '0.0%', '#,##0.00', '0.0%', None, None, None]
    for col, (val, fmt) in enumerate(zip(cells_data, fmts), 1):
        set_cell(ws.cell(row=row, column=col), val, bg=YELLOW_BG, bold=True, fmt=fmt)

    # 第5-11行：各代运营商汇总
    for org_idx, (org_key, d) in enumerate(org_data_list):
        row += 1
        city = CITY_MAP.get(org_key, "")
        short = ORG_SHORT_MAP.get(org_key, org_key)
        # 找代运营商主管名
        t_l2 = t_data.get(org_key, {}).get('L2', [])
        manager = ""
        if t_l2:
            manager_col = 3  # 通常L2行第3列是姓名
            for l2r in t_l2:
                if len(l2r) > manager_col and str(l2r[C_LEVEL]).strip() == 'L3':
                    manager = str(l2r[manager_col]).strip()
                    break
        # 用代运营商全名显示
        t_l3 = t_data.get(org_key, {}).get('org_name_raw', org_key)

        bg = ORG_COLORS[org_idx % len(ORG_COLORS)]
        cells_data = [
            city, short, "",
            d['gtv_month'], d['yest_gtv'], d['bind_inc'], d['bind_cnt'],
            d['bind_rate'], d['yest_zt_ord'], d['yest_zt_gtv'], d['yest_zt_rate'],
            d['zt_gtv_month'], d['zt_month_rate'],
            d['bind_t1'], d['bind_t2'], d['store_cnt']
        ]
        fmts = [None, None, None, '#,##0.00', '#,##0.00', None, None, '0.0%', None, '#,##0.00', '0.0%', '#,##0.00', '0.0%', None, None, None]
        for col, (val, fmt) in enumerate(zip(cells_data, fmts), 1):
            set_cell(ws.cell(row=row, column=col), val, bg=bg, fmt=fmt)

    # 空行
    row += 1
    ws.row_dimensions[row].height = 6

    # 销售明细标题
    row += 1
    ws.merge_cells(f'A{row}:P{row}')
    det = ws[f'A{row}']
    det.value = "\u25b6 \u9500\u552e\u660e\u7ec6"
    det.font = Font(name='Arial', bold=True, size=10)
    det.fill = PatternFill('solid', start_color='DBEAFE')
    det.alignment = Alignment(horizontal='left', vertical='center')

    # 各代运营商销售明细
    for org_idx, (org_key, d_summary) in enumerate(org_data_list):
        t_l2_list = t_data.get(org_key, {}).get('L2', [])
        t1_dict = {}
        for l2r in t1_data.get(org_key, {}).get('L2', []) if t1_data.get(org_key) else []:
            name_col = 3
            if len(l2r) > name_col:
                t1_dict[str(l2r[name_col]).strip()] = l2r

        if not t_l2_list:
            continue

        # 代运营商小标题
        row += 1
        short = ORG_SHORT_MAP.get(org_key, org_key)
        ws.merge_cells(f'A{row}:P{row}')
        stitle = ws[f'A{row}']
        org_raw = t_data.get(org_key, {}).get('org_name_raw', org_key)
        stitle.value = f"{short}\uff08{org_raw}\uff09"
        stitle.font = Font(name='Arial', bold=True, size=9)
        bg = ORG_COLORS[org_idx % len(ORG_COLORS)]
        stitle.fill = PatternFill('solid', start_color=bg)
        stitle.alignment = Alignment(horizontal='left', vertical='center')

        city = CITY_MAP.get(org_key, "")

        for l2r in t_l2_list:
            row += 1
            name_col = 3
            name = str(l2r[name_col]).strip() if len(l2r) > name_col else ""
            t1r = t1_dict.get(name, [])

            def gv(r, c): return safe_float(r[c]) if len(r) > c else 0.0
            def gvi(r, c): return safe_int(r[c]) if len(r) > c else 0

            gtv_month = gv(l2r, C_GTV_MONTH)
            zt_gtv = gv(l2r, C_ZT_GTV)
            zt_ord = gvi(l2r, C_ZT_ORD)
            bind = gvi(l2r, C_BIND_CNT)
            store = gvi(l2r, C_STORE_CNT)

            gtv_t1 = gv(t1r, C_GTV_MONTH) if t1r else 0
            zt_gtv_t1 = gv(t1r, C_ZT_GTV) if t1r else 0
            zt_ord_t1 = gvi(t1r, C_ZT_ORD) if t1r else 0
            bind_t1 = gvi(t1r, C_BIND_CNT) if t1r else bind

            yest_gtv = gtv_month - gtv_t1 if gtv_t1 > 0 else 0
            yest_zt_gtv = zt_gtv - zt_gtv_t1
            yest_zt_ord = zt_ord - zt_ord_t1
            bind_inc = bind - bind_t1

            bind_rate = bind / store if store > 0 else 0
            zt_month_rate = zt_gtv / gtv_month if gtv_month > 0 else 0
            yest_zt_rate = yest_zt_gtv / yest_gtv if yest_gtv > 0 else 0

            cells_data = [
                city, short, name,
                gtv_month, yest_gtv, bind_inc, bind,
                bind_rate, yest_zt_ord, yest_zt_gtv, yest_zt_rate,
                zt_gtv, zt_month_rate, bind, bind_t1, store
            ]
            fmts = [None, None, None, '#,##0.00', '#,##0.00', None, None, '0.0%', None, '#,##0.00', '0.0%', '#,##0.00', '0.0%', None, None, None]
            for col, (val, fmt) in enumerate(zip(cells_data, fmts), 1):
                set_cell(ws.cell(row=row, column=col), val, fmt=fmt)

    # 冻结首行
    ws.freeze_panes = 'A3'
    return wb


def download_via_browser(date_str):
    """尝试通过agent-browser点击Apollo导出按钮下载组织明细"""
    # 实现：打开Apollo页面→找到「导出」按钮→点击→等待下载完成→返回文件路径
    # 当前跳过，使用备用方案
    return None


def get_existing_file(date_str):
    """查找已有的当日组织明细文件"""
    # 从data目录或/tmp/files查找
    candidates = list(Path("/tmp/files").glob(f"*{date_str}*职人码*组织明细*.xlsx")) + \
                 list(Path("/tmp/files").glob(f"*{date_str}*策略管理*.xlsx"))
    if candidates:
        return str(candidates[0])
    return None


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    today_label = now.strftime("%m\u6708%d\u65e5")  # 如 03月30日
    yesterday_label = (now - datetime.timedelta(days=1)).strftime("%m\u6708%d\u65e5")

    print(f"=== 职人码日播报 {today} ===")
    print(f"  数据日期: {yesterday_label}（T-1）")

    # 1. 获取T（今天）和T-1（昨天）的组织明细文件
    t_file = get_existing_file(today)
    t1_file = get_existing_file(yesterday)

    if not t_file:
        # 尝试用browser下载
        print("  未找到今日组织明细，尝试browser下载...")
        t_file = download_via_browser(today)

    if not t_file or not t1__file:
        print(f"  ⚠️ 缺少数据文件: today={t_file}, yesterday={t1_file}")
        print("  请先从Apollo下载组织明细文件到 /tmp/files/")
        sys.exit(1)

    print(f"  今日文件: {t_file}")
    print(f"  昨日文件: {t1_file}")

    # 2. 生成Excel
    wb = build_excel(t_file, t1_file, today_label, yesterday_label)
    out_path = f"/tmp/files/职人码日播报_{today}.xlsx"
    Path("/tmp/files").mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"  ✅ 已生成: {out_path}")

    # 3. 发大象
    cmd = ["openclaw", "send", "--channel", "daxiang", "--target", DAXIANG_UID,
           "--file", out_path, "--caption", f"职人码日播报 {yesterday_label}（数据截至今日）"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✅ 已发送大象")
    else:
        print(f"  ⚠️ 发送失败: {r.stderr}")


if __name__ == '__main__':
    main()
