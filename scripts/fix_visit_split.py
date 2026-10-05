#!/usr/bin/env python3
"""2026-10-05: 修复 wb_visit 链路——478 明细按 attribute_org_name 拆到7家代运营商
连线：478 明细 JSON（/tmp/wb_visit_<date>/detail.json）→ 拜访明细xlsx（加"销售业绩归属组织"按 attribute_org_name 映射）
     → gen_visit_wmz / gen_visit_cov_wmz / ingest_visit2 原有链路不变。
改法：detail.json 的 org_name_l8 全是"高线皖闽浙城市群"，不可用；
     attribute_org_name 形如 "上海代优-泉州乐生活组"，用 ORG_L9_MAP 映射到7家展示名。
用法: fix_visit_split.py <date>   (默认 2026-10-04)
"""
import sys, os, json, subprocess
from collections import Counter
import pandas as pd

WS = '/root/.openclaw/workspace'

# attribute_org_name(L9) → 7家代运营商展示名（与 gen_zrq_wmz.py ORG_MAP 一致）
ORG_L9_MAP = {
    '星企动-绍兴乐生活区县聚合组': '绍兴星企动',
    '星企动-绍兴乐生活组': '绍兴星企动',
    '星企动-绍兴柯桥区乐生活组': '绍兴星企动',
    '星企动-绍兴上虞区乐生活组': '绍兴星企动',
    '上海代优-泉州乐生活组': '泉州小花猫',
    '泉州市小花猫-泉州乐生活组': '泉州小花猫',
    '南京知了-芜湖乐生活组': '芜湖知了',
    '惠安广通-晋江乐生活组': '惠安广通',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
    '仙居烁果-台州乐生活组': '仙居烁果',
    '仙居烁果-台州温岭乐生活组': '仙居烁果',
}


def build_detail_xlsx(date, out_dir):
    """从 478 明细 JSON 重新生成拜访明细 xlsx：组织列用 attribute_org_name 映射后的 7 家名"""
    src = f'{out_dir}/detail.json'
    rows = json.load(open(src))
    df = pd.DataFrame(rows)
    def map_org(name):
        return ORG_L9_MAP.get(str(name).strip())
    df['org'] = df['attribute_org_name'].apply(map_org)
    unmapped = df[df['org'].isna()]['attribute_org_name'].value_counts()
    if len(unmapped):
        print('⚠️ 无法映射的 attribute_org_name:')
        print(unmapped.to_string())
        raise SystemExit('存在未映射组织，终止（请人工确认映射后补充 ORG_L9_MAP）')
    out = pd.DataFrame({
        '拜访日期': df['visit_date'].astype(str).str[:10],
        '门店ID': df['shop_id'], '门店名': df['shop_name'],
        '销售姓名': df['employee_name'], '销售ID': df['employee_id'],
        '是否有效拜访': df['is_valid'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否签到': df['is_signin'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否IVR电话拜访': df['is_ivr_call'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '是否500米内': df['is_500m'].apply(lambda x: 1 if x == 1 or x == '1' else 0),
        '签到距离': df['distance'],
        '签到时间': df['sign_in_time'],
        '拜访开始时间': df['start_time'], '拜访结束时间': df['end_time'],
        '拜访形式': df['visit_form_name'],
        '销售业绩归属组织': df['org'],
    })
    detail_x = f'{out_dir}/拜访明细_{date}.xlsx'
    out.to_excel(detail_x, index=False)
    print(f'明细xlsx: {len(out)} 行 -> {detail_x}')
    print('组织分布:', dict(Counter(out['销售业绩归属组织'])))
    return detail_x


def rerun_gen(date, out_dir, detail_x):
    cov_x = f'{out_dir}/拜访覆盖率分析_{date.replace("-", "")}.xlsx'
    r = subprocess.run(['python3', f'{WS}/scripts/gen_visit_cov_wmz.py', detail_x, cov_x],
                       capture_output=True, text=True, timeout=1200)
    print(r.stdout[-600:], r.stderr[-300:] if r.returncode else '', flush=True)
    if r.returncode: raise SystemExit('gen_visit_cov_wmz 失败')

    vis_x = f'{out_dir}/拜访分析_皖闽浙_{date.replace("-", "")}.xlsx'
    r = subprocess.run(['python3', f'{WS}/scripts/gen_visit_wmz.py', detail_x, vis_x],
                       capture_output=True, text=True, timeout=1200)
    print(r.stdout[-600:], r.stderr[-300:] if r.returncode else '', flush=True)
    if r.returncode: raise SystemExit('gen_visit_wmz 失败')
    return vis_x, cov_x


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else '2026-10-04'
    out_dir = f'/tmp/wb_visit_{date}'
    if not os.path.exists(f'{out_dir}/detail.json'):
        raise SystemExit(f'缺少 {out_dir}/detail.json（请先 fetch_wb_visit.py {date}）')
    detail_x = build_detail_xlsx(date, out_dir)
    vis_x, cov_x = rerun_gen(date, out_dir, detail_x)

    # ingest（visit2/visit3 会先 delete 当日旧数据，包括原来的城市群汇总行）
    r = subprocess.run(['python3', f'{WS}/scripts/ingest_visit2.py', vis_x, cov_x],
                       capture_output=True, text=True, timeout=1200)
    print(r.stdout[-800:], r.stderr[-400:] if r.returncode else '', flush=True)
    if r.returncode: raise SystemExit('ingest_visit2 失败')

    # visit(每日有效拜访) 模块也重灌
    r = subprocess.run(['python3', f'{WS}/scripts/ingest_one_workbench.py', 'visit', vis_x],
                       capture_output=True, text=True, timeout=1200)
    print(r.stdout[-500:], r.stderr[-300:] if r.returncode else '', flush=True)
    if r.returncode: raise SystemExit('ingest_one_workbench visit 失败')

    # 销售行（每日有效拜访数 Sheet）→ wmz_sales_detail module='visit'（REST，逐行过滤写入）
    r = subprocess.run(['python3', f'{WS}/scripts/push_visit_sales_rest.py', date, vis_x],
                       capture_output=True, text=True, timeout=1200)
    print(r.stdout[-400:], r.stderr[-300:] if r.returncode else '', flush=True)
    if r.returncode: raise SystemExit('push_visit_sales_rest 失败')

    # embed 报表文件
    for mod, f in [('visit2', vis_x), ('visit3', cov_x)]:
        r = subprocess.run(['python3', f'{WS}/scripts/embed_workbench_reports.py', date, mod, f],
                           capture_output=True, text=True, timeout=1200)
        print(mod, r.stdout[-200:], r.stderr[-200:] if r.returncode else '', flush=True)
    print(f'✅ {date} visit 拆分重灌完成')


if __name__ == '__main__':
    main()
