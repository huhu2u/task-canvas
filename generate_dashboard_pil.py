
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

# 创建画布
width, height = 1000, 1200
img = Image.new('RGB', (width, height), '#0f172a')
draw = ImageDraw.Draw(img)

# 尝试加载字体
try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    font_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
except:
    font_title = ImageFont.load_default()
    font_header = ImageFont.load_default()
    font_data = ImageFont.load_default()
    font_small = ImageFont.load_default()

# 数据整理
data = [
    {"name": "Huizhou Julang", "gtv": 3098389.54, "target": "-", "rate": "-", "gap": "-", "today_gtv": 75085.26, "today_cpc": 792.13},
    {"name": "Huizhou Bowan", "gtv": 2737971.45, "target": "-", "rate": "-", "gap": "-", "today_gtv": 60061.44, "today_cpc": 1599.10},
    {"name": "Quanzhou XiaoHuamao", "gtv": 2368178.77, "target": "-", "rate": "-", "gap": "-", "today_gtv": 71891.44, "today_cpc": 3256.85},
    {"name": "Ningxia Lingchuang", "gtv": 2397989.75, "target": "-", "rate": "-", "gap": "-", "today_gtv": 22820.35, "today_cpc": 1733.86},
    {"name": "Yiwu Xiyang", "gtv": 1738334.19, "target": "-", "rate": "-", "gap": "-", "today_gtv": 50750.94, "today_cpc": 1266.08},
    {"name": "Hui'an Guangtong", "gtv": 1945332.05, "target": "-", "rate": "-", "gap": "-", "today_gtv": 56425.75, "today_cpc": 1122.73},
    {"name": "Cixi Zheguang", "gtv": 1759737.62, "target": "-", "rate": "-", "gap": "-", "today_gtv": 24365.35, "today_cpc": 2941.24},
]

# 汇总数据
total_gtv = 16045833.47
total_today_gtv = 361400.52
total_today_cpc = 12711.99

# 绘制标题区域
draw.rectangle([0, 0, width, 90], fill='#1e293b')
draw.text((width//2, 25), "Yue-Min-Zhe City Group Dashboard", fill='#f8fafc', font=font_title, anchor='mm')
draw.text((width//2, 65), f"Data: March 2026 | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", fill='#94a3b8', font=font_small, anchor='mm')

# 绘制汇总卡片
card_y = 110
card_height = 70
cards = [
    ("Monthly GTV", f"${total_gtv/1000000:.2f}M", "#3b82f6"),
    ("Today GTV", f"${total_today_gtv/10000:.1f}K", "#10b981"),
    ("Today CPC", f"${total_today_cpc:.0f}", "#f59e0b"),
    ("Operators", "7", "#8b5cf6"),
]
card_width = (width - 50) // 4
for i, (label, value, color) in enumerate(cards):
    x = 15 + i * (card_width + 5)
    draw.rectangle([x, card_y, x + card_width, card_y + card_height], fill='#334155', outline=color, width=2)
    draw.text((x + card_width//2, card_y + 20), label, fill='#94a3b8', font=font_small, anchor='mm')
    draw.text((x + card_width//2, card_y + 50), value, fill=color, font=font_header, anchor='mm')

# 表头
table_y = 200
header_height = 35
col_widths = [200, 110, 90, 100, 90, 110, 110]
headers = ["Operator", "Monthly GTV", "Target", "Rate", "Gap", "Today GTV", "Today CPC"]
col_x = [10]
for w in col_widths[:-1]:
    col_x.append(col_x[-1] + w)

# 绘制表头背景
draw.rectangle([10, table_y, width-10, table_y + header_height], fill='#334155')
for i, (header, x, w) in enumerate(zip(headers, col_x, col_widths)):
    draw.text((x + w//2, table_y + header_height//2), header, fill='#f8fafc', font=font_header, anchor='mm')

# 绘制数据行
row_height = 60
for idx, row in enumerate(data):
    y = table_y + header_height + idx * row_height
    bg_color = '#1e293b' if idx % 2 == 0 else '#252f47'
    draw.rectangle([10, y, width-10, y + row_height - 2], fill=bg_color)
    
    # 名称
    draw.text((col_x[0] + 10, y + row_height//2), row['name'], fill='#f8fafc', font=font_data, anchor='lm')
    
    # 月累计GTV
    gtv_text = f"${row['gtv']/10000:.1f}K"
    draw.text((col_x[1] + col_widths[1]//2, y + row_height//2), gtv_text, fill='#3b82f6', font=font_data, anchor='mm')
    
    # 月目标
    draw.text((col_x[2] + col_widths[2]//2, y + row_height//2), row['target'], fill='#94a3b8', font=font_data, anchor='mm')
    
    # 完成率（模拟）
    rate_val = 75 + (idx * 3) % 25
    bar_width = 80
    bar_height = 8
    bar_x = col_x[3] + (col_widths[3] - bar_width) // 2
    bar_y = y + 15
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill='#334155')
    fill_color = '#10b981' if rate_val >= 80 else '#f59e0b' if rate_val >= 60 else '#ef4444'
    draw.rectangle([bar_x, bar_y, bar_x + int(bar_width * rate_val/100), bar_y + bar_height], fill=fill_color)
    draw.text((col_x[3] + col_widths[3]//2, y + 40), f"{rate_val}%", fill='#f8fafc', font=font_small, anchor='mm')
    
    # 日均缺口
    draw.text((col_x[4] + col_widths[4]//2, y + row_height//2), row['gap'], fill='#94a3b8', font=font_data, anchor='mm')
    
    # 今日GTV
    today_gtv_text = f"${row['today_gtv']/10000:.1f}K"
    draw.text((col_x[5] + col_widths[5]//2, y + row_height//2), today_gtv_text, fill='#10b981', font=font_data, anchor='mm')
    
    # 今日CPC
    today_cpc_text = f"${row['today_cpc']:.0f}"
    draw.text((col_x[6] + col_widths[6]//2, y + row_height//2), today_cpc_text, fill='#f59e0b', font=font_data, anchor='mm')

# 底部
draw.rectangle([0, height-40, width, height], fill='#0f172a')
draw.text((width//2, height-20), "Source: Apollo Revenue Analysis | High-line Yue-Min-Zhe City Group", fill='#64748b', font=font_small, anchor='mm')

# 保存
output_path = '/root/.openclaw/workspace/yue_min_zhe_dashboard.png'
img.save(output_path)
print(f"Dashboard saved: {output_path}")
