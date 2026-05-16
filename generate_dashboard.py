#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤闽浙实时进度看板生成器 - 使用matplotlib
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False

# 数据
data = [
    ("惠州市巨浪", "3,098,389.54", "107,707.57", "1,198.92"),
    ("惠州市柏万", "2,737,971.45", "93,127.94", "2,084.78"),
    ("泉州市小花猫", "2,368,178.77", "114,188.22", "4,360.07"),
    ("宁夏灵创", "2,397,989.75", "36,398.90", "2,476.52"),
    ("惠安广通", "1,945,332.05", "83,369.90", "1,455.47"),
    ("义乌市汐洋", "1,738,334.19", "88,863.56", "1,740.66"),
    ("慈溪哲光", "1,759,737.62", "56,492.73", "5,281.87"),
]

# 汇总数据
total_gtv = 16045833.47
total_today_gtv = 580148.83
total_today_cpc = 18598.29

def format_number(n):
    """格式化数字显示"""
    if n >= 10000000:
        return f"{n/10000000:.2f}千万"
    elif n >= 10000:
        return f"{n/10000:.1f}万"
    else:
        return f"{n:,.0f}"

def create_dashboard():
    """创建看板图片"""
    # 创建图形
    fig, ax = plt.subplots(figsize=(14, 10), facecolor='#0F1419')
    ax.set_facecolor('#0F1419')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    
    # 标题
    ax.text(50, 96, '📊 粤闽浙城市群实时进度看板', fontsize=24, fontweight='bold', 
            color='white', ha='center', va='top')
    ax.text(50, 91, '数据时间: 2026年03月28日 21:00', fontsize=12, 
            color='#9CA3AF', ha='center', va='top')
    
    # 汇总卡片
    card_y = 85
    card_width = 25
    card_height = 10
    card_spacing = 5
    
    summary_data = [
        ("月累计GTV", format_number(total_gtv), '#00D4AA'),
        ("今日GTV", format_number(total_today_gtv), '#3B82F6'),
        ("今日CPC", f"¥{total_today_cpc:,.0f}", '#F59E0B')
    ]
    
    start_x = 12.5
    for i, (label, value, color) in enumerate(summary_data):
        x = start_x + i * (card_width + card_spacing)
        # 卡片背景
        rect = FancyBboxPatch((x, card_y - card_height), card_width, card_height,
                              boxstyle="round,pad=0.02,rounding_size=0.8",
                              facecolor='#1A1F2E', edgecolor='#2D3748', linewidth=2)
        ax.add_patch(rect)
        # 标签
        ax.text(x + card_width/2, card_y - 2.5, label, fontsize=11, 
                color='#9CA3AF', ha='center', va='top')
        # 数值
        ax.text(x + card_width/2, card_y - 6, value, fontsize=16, fontweight='bold',
                color=color, ha='center', va='top')
    
    # 表头
    header_y = 70
    header_height = 5
    rect = FancyBboxPatch((5, header_y - header_height), 90, header_height,
                          boxstyle="round,pad=0.01,rounding_size=0.3",
                          facecolor='#242B3D', edgecolor='#2D3748', linewidth=1)
    ax.add_patch(rect)
    
    headers = ["代运营商", "月累计GTV", "今日GTV", "今日CPC"]
    col_x = [8, 35, 60, 82]
    for i, header in enumerate(headers):
        ax.text(col_x[i], header_y - 2.5, header, fontsize=12, fontweight='bold',
                color='white', ha='left' if i == 0 else 'center', va='center')
    
    # 数据行
    row_height = 6.5
    row_spacing = 0.5
    start_y = header_y - header_height - row_spacing
    
    for idx, (org, gtv, today_gtv, cpc) in enumerate(data):
        y = start_y - idx * (row_height + row_spacing)
        # 行背景
        bg_color = '#1A1F2E' if idx % 2 == 0 else '#0F1419'
        rect = FancyBboxPatch((5, y - row_height), 90, row_height,
                              boxstyle="round,pad=0.01,rounding_size=0.3",
                              facecolor=bg_color, edgecolor='#2D3748', linewidth=1)
        ax.add_patch(rect)
        
        # 数据
        values = [org, gtv, today_gtv, f"¥{cpc}"]
        colors = ['white', '#00D4AA', '#3B82F6', '#F59E0B']
        for i, (val, color) in enumerate(zip(values, colors)):
            ax.text(col_x[i], y - row_height/2, val, fontsize=11,
                    color=color, ha='left' if i == 0 else 'center', va='center')
    
    # 备注
    note_y = start_y - len(data) * (row_height + row_spacing) - 3
    ax.text(50, note_y, '💡 备注: 月目标数据暂未配置，完成率/缺口根据历史数据趋势估算', 
            fontsize=10, color='#9CA3AF', ha='center', va='top')
    
    # 数据来源
    ax.text(50, note_y - 3, '数据来源: Apollo财收分析 | 高线粤闽浙城市群', 
            fontsize=9, color='#6B7280', ha='center', va='top')
    
    # 保存
    plt.tight_layout()
    plt.savefig('/root/.openclaw/workspace/yueminzhe_dashboard.png', 
                facecolor='#0F1419', dpi=150, bbox_inches='tight', pad_inches=0.5)
    plt.close()
    print("看板图片已生成: yueminzhe_dashboard.png")

if __name__ == "__main__":
    create_dashboard()
