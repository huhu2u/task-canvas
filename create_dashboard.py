#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤闽浙实时进度看板图片生成器
"""

from PIL import Image, ImageDraw, ImageFont
import os

# 数据 - 来自Apollo实时抓取
data = {
    "城市群": {
        "name": "高线粤闽浙城市群",
        "month_gtv": 16812266.35,
        "month_target": None,  # 页面未显示
        "completion_rate": 0,
        "daily_gap": 0,
        "today_gtv": 769397.34,
        "today_cpc": 17954.26
    },
    "operators": [
        {"name": "惠州市巨浪-惠州", "month_gtv": 3245525.32, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 167569.30, "today_cpc": 993.40},
        {"name": "惠州市柏万-惠阳", "month_gtv": 2870252.04, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 125140.82, "today_cpc": 2094.20},
        {"name": "泉州市小花猫-泉州", "month_gtv": 2513046.01, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 131101.14, "today_cpc": 3579.68},
        {"name": "宁夏灵创-金华义乌", "month_gtv": 2446765.58, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 56485.20, "today_cpc": 2902.77},
        {"name": "义乌市汐洋-金华义乌", "month_gtv": 1846650.45, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 95571.77, "today_cpc": 2250.94},
        {"name": "惠安广通-晋江", "month_gtv": 2042765.32, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 84415.10, "today_cpc": 1201.76},
        {"name": "慈溪哲光-金华义乌", "month_gtv": 1847361.53, "month_target": None, "completion_rate": 0, "daily_gap": 0, "today_gtv": 109114.00, "today_cpc": 4931.51},
    ]
}

def format_money(value):
    """格式化金额"""
    if value is None:
        return "-"
    return f"{value/10000:.2f}万"

def format_money_wan(value):
    """格式化为万元"""
    if value is None:
        return "-"
    return f"{value/10000:.1f}"

def create_dashboard():
    # 画布尺寸
    width = 1200
    height = 1400
    
    # 创建画布
    img = Image.new('RGB', (width, height), color='#F5F7FA')
    draw = ImageDraw.Draw(img)
    
    # 尝试加载字体
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_number = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except:
        font_title = ImageFont.load_default()
        font_header = font_title
        font_text = font_title
        font_small = font_title
        font_number = font_title
    
    # 标题
    title = "🏆 粤闽浙实时进度看板"
    draw.text((width//2 - 250, 30), title, fill='#1A1A2E', font=font_title)
    
    # 时间信息
    time_info = "数据时间：2026年03月29日 23:10 | 来源：Apollo财收分析"
    draw.text((width//2 - 280, 85), time_info, fill='#666666', font=font_small)
    
    y_offset = 130
    
    # 城市群汇总卡片
    card_padding = 20
    card_height = 140
    draw.rounded_rectangle([30, y_offset, width-30, y_offset+card_height], radius=12, fill='#FFFFFF', outline='#E8ECF0')
    
    # 汇总标题
    draw.text((50, y_offset+15), "📊 高线粤闽浙城市群今日实时汇总", fill='#1A1A2E', font=font_header)
    
    # 汇总数据
    summary = data["城市群"]
    metrics = [
        ("月累计GTV", format_money(summary["month_gtv"])),
        ("今日GTV", format_money(summary["today_gtv"])),
        ("今日CPC", format_money(summary["today_cpc"])),
    ]
    
    x_start = 60
    for label, value in metrics:
        draw.text((x_start, y_offset+55), label, fill='#666666', font=font_small)
        draw.text((x_start, y_offset+80), value, fill='#FF6B35', font=font_number)
        x_start += 350
    
    y_offset += card_height + 30
    
    # 各代运营商详细数据表格
    draw.text((50, y_offset), "📈 各代运营商详细数据", fill='#1A1A2E', font=font_header)
    y_offset += 50
    
    # 表头
    header_bg = '#4A90E2'
    row_height = 65
    col_widths = [220, 130, 130, 140, 140, 140, 130]
    
    headers = ["代运营商", "月累计GTV", "月目标", "完成率", "日均缺口", "今日GTV", "今日CPC"]
    x_pos = 30
    
    # 绘制表头背景
    draw.rectangle([30, y_offset, width-30, y_offset+row_height], fill=header_bg)
    
    for i, (header, col_w) in enumerate(zip(headers, col_widths)):
        draw.text((x_pos + 10, y_offset + 18), header, fill='#FFFFFF', font=font_text)
        x_pos += col_w
    
    y_offset += row_height
    
    # 数据行
    colors = ['#FFFFFF', '#F8FAFC']
    for idx, op in enumerate(data["operators"]):
        row_bg = colors[idx % 2]
        draw.rectangle([30, y_offset, width-30, y_offset+row_height], fill=row_bg)
        
        x_pos = 30
        values = [
            op["name"],
            format_money(op["month_gtv"]),
            "-",  # 月目标未显示
            "-",  # 完成率
            "-",  # 日均缺口
            format_money(op["today_gtv"]),
            format_money(op["today_cpc"]),
        ]
        
        for i, (value, col_w) in enumerate(zip(values, col_widths)):
            text_color = '#333333' if i == 0 else '#666666'
            if i in [5, 6]:  # 今日GTV和CPC用橙色
                text_color = '#FF6B35'
            draw.text((x_pos + 10, y_offset + 20), value, fill=text_color, font=font_text)
            x_pos += col_w
        
        y_offset += row_height
    
    # 底部边框
    draw.line([(30, y_offset), (width-30, y_offset)], fill='#E8ECF0', width=1)
    
    # 备注
    y_offset += 30
    note = "📌 说明：月目标/完成率/日均缺口数据在Apollo页面未显示，建议通过门店明细或历史数据补充。"
    draw.text((50, y_offset), note, fill='#999999', font=font_small)
    
    # 保存
    output_path = "/root/.openclaw/workspace/粤闽浙实时进度看板_20260329.png"
    img.save(output_path, quality=95)
    print(f"看板图片已生成: {output_path}")
    return output_path

if __name__ == "__main__":
    create_dashboard()
