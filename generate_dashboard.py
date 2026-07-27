#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为Kindle KT2 (600x800, 灰阶) 生成天气+待办事项仪表盘图片
数据来源：
  - 天气：Open-Meteo（免费、无需API key）
  - 待办：读取你已有的 Cloudflare Worker /api/todos 接口
"""

import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from zoneinfo import ZoneInfo

# ========== 配置区，按需修改 ==========
WIDTH, HEIGHT = 600, 800          # 先用600x800，之后确认eips -i的真实分辨率再调
LAT, LON = 51.5074, -0.1278       # 伦敦坐标，按需改成你自己的城市坐标
TIMEZONE = ZoneInfo("Europe/London")  # 明确指定时区，避免GitHub Actions服务器用UTC导致时间不对
TODOS_API = "https://morning-leaf-4070.yunhan-li.workers.dev/api/todos"
OUTPUT_PATH = "output/dash.png"

# 字体路径（GitHub Actions里会通过apt安装Noto CJK字体，路径见workflow文件）
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_PATH_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

WEATHER_CODE_MAP = {
    0: "晴", 1: "大致晴朗", 2: "少云", 3: "多云",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    95: "雷雨",
}


def get_weather():
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"sunrise,sunset,uv_index_max,precipitation_probability_max"
        f"&timezone=auto&forecast_days=3"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def get_todos():
    try:
        r = requests.get(TODOS_API, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"获取待办事项失败: {e}")
        return []


def draw_dashboard():
    weather = get_weather()
    todos = get_todos()

    img = Image.new("L", (WIDTH, HEIGHT), color=255)  # L=灰度图，255=白色背景
    draw = ImageDraw.Draw(img)

    font_date = ImageFont.truetype(FONT_PATH, 40)
    font_weekday = ImageFont.truetype(FONT_PATH_REGULAR, 26)
    font_temp = ImageFont.truetype(FONT_PATH, 90)
    font_desc = ImageFont.truetype(FONT_PATH_REGULAR, 32)
    font_meta = ImageFont.truetype(FONT_PATH_REGULAR, 24)
    font_forecast_label = ImageFont.truetype(FONT_PATH_REGULAR, 24)
    font_forecast_temp = ImageFont.truetype(FONT_PATH_REGULAR, 22)
    font_section_title = ImageFont.truetype(FONT_PATH, 32)
    font_todo = ImageFont.truetype(FONT_PATH_REGULAR, 28)
    font_footer = ImageFont.truetype(FONT_PATH_REGULAR, 20)

    now = datetime.now(TIMEZONE)
    y = 30

    # ---- 日期（不再显示大时钟，因为图片是定时快照，不是实时钟表）----
    weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    draw.text((30, y), now.strftime("%m月%d日"), font=font_date, fill=0)
    y += 55
    draw.text((30, y), f"{now.strftime('%Y年')} {weekday_cn}", font=font_weekday, fill=0)
    y += 55

    draw.line((30, y, WIDTH - 30, y), fill=0, width=2)
    y += 25

    # ---- 当前天气 ----
    cur = weather["current"]
    daily = weather["daily"]
    code = cur["weather_code"]
    desc = WEATHER_CODE_MAP.get(code, "未知")
    draw.text((30, y), f"{desc}", font=font_desc, fill=0)
    y += 45
    draw.text((30, y), f"{round(cur['temperature_2m'])}°C", font=font_temp, fill=0)
    y += 100

    # 风速 + 湿度 同一行
    draw.text((30, y), f"风速 {round(cur['wind_speed_10m'], 1)} km/h", font=font_meta, fill=0)
    draw.text((320, y), f"湿度 {cur['relative_humidity_2m']}%", font=font_meta, fill=0)
    y += 35

    # 日出日落 + 紫外线指数
    sunrise = datetime.fromisoformat(daily["sunrise"][0]).strftime("%H:%M")
    sunset = datetime.fromisoformat(daily["sunset"][0]).strftime("%H:%M")
    uv_index = daily["uv_index_max"][0]
    draw.text((30, y), f"日出 {sunrise}  日落 {sunset}", font=font_meta, fill=0)
    y += 35
    draw.text((30, y), f"紫外线指数 {round(uv_index, 1)}", font=font_meta, fill=0)
    y += 45

    draw.line((30, y, WIDTH - 30, y), fill=0, width=2)
    y += 25

    # ---- 三天预报（含降水概率）----
    labels = ["今天", "明天", "后天"]
    col_width = (WIDTH - 60) // 3
    for i in range(3):
        cx = 30 + i * col_width
        draw.text((cx, y), labels[i], font=font_forecast_label, fill=0)
        tmax = round(daily["temperature_2m_max"][i])
        tmin = round(daily["temperature_2m_min"][i])
        draw.text((cx, y + 35), f"{tmin}° / {tmax}°", font=font_forecast_temp, fill=0)
        precip = daily["precipitation_probability_max"][i]
        draw.text((cx, y + 65), f"降水 {precip}%", font=font_forecast_temp, fill=0)
    y += 120

    draw.line((30, y, WIDTH - 30, y), fill=0, width=2)
    y += 25

    # ---- 待办事项 ----
    draw.text((30, y), "待办事项", font=font_section_title, fill=0)
    y += 50
    if todos:
        for todo in todos[:8]:  # 最多显示8条，避免溢出
            text = todo.get("text", "")
            done = todo.get("done", False)
            box = "☑" if done else "☐"
            draw.text((30, y), f"{box} {text}", font=font_todo, fill=0)
            y += 42
    else:
        draw.text((30, y), "（暂无待办事项）", font=font_todo, fill=128)

    # ---- 底部：最后更新时间戳 ----
    footer_text = f"最后更新 {now.strftime('%m月%d日 %H:%M')}"
    draw.text((30, HEIGHT - 35), footer_text, font=font_footer, fill=100)

    import os
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    img.save(OUTPUT_PATH)
    print(f"仪表盘已生成: {OUTPUT_PATH}")


if __name__ == "__main__":
    draw_dashboard()
