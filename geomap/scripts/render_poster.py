#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_poster.py — 将 JSON 配置与 GeoJSON 地图数据渲染为高清手机竖屏海报、标准政区图或 9:16 短视频
支持主题：
  1. classic_poster: 经典晴空蓝海报 (1080x2160), 胶囊主标, 运营排行榜, 亚克力 Logo 墙
  2. short_video: 自媒体爆款短视频全屏 (1080x1920), 黄底黑框三行告示牌, 浮动描边大字
  3. city_night: 城市夜景大片风 (1080x2160), 底部真实城市航拍羽化, 顶部多指标 KPI 药丸, 全色阶填充
  4. district: 地级市辖区县级经济图 (1080x1920), 米白纸质感, 三行指标
  5. national: 全国省级宏观分布图 (1080x1920), 顶部深蓝横幅, 南海诸岛插框, 蓝海白底
  6. official_standard: 官方标准行政地图 (1440x1080), 双层图廓, 铅灰晕圈, 莫兰迪五色, 图例比例尺, 设区市同心圆
"""

import os
import sys
import json
import argparse
import tempfile
import base64
import subprocess
from playwright.sync_api import sync_playwright

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
DATA_DIR = os.path.join(SKILL_DIR, "data")
ASSETS_DIR = os.path.join(SKILL_DIR, "assets")

sys.path.insert(0, SCRIPTS_DIR)
from fetch_geojson import get_geojson


def detect_theme(config: dict) -> str:
    theme = config.get("theme", "").lower()
    if theme in ["official", "official_standard", "standard", "standard_map"]:
        return "official_standard"
    if theme in ["national", "country", "china"] or config.get("region") in ["全国", "中国", "100000"]:
        return "national"
    if theme in ["short_video", "billboard", "shortvideo"]:
        return "short_video"
    if theme in ["city_night", "night_kpi", "night"]:
        return "city_night"
    if theme in ["district", "district_paper", "county"]:
        return "district"
    if config.get("header_lines") or config.get("aspect_ratio") in ["9:16", "short_video"]:
        return "short_video"
    if config.get("kpis") or config.get("bg_city"):
        return "city_night"
    if config.get("districts"):
        return "district"
    return "classic_poster"


def build_html(config_path: str) -> tuple[str, str, dict]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    region = config.get("region") or config.get("province") or config.get("city") or ""
    if not region:
        raise ValueError("配置文件必须指定 region 或 province 字段 (如 '江苏省', '安徽省', '扬州市', '100000')")

    geojson_path = get_geojson(region)
    with open(geojson_path, "r", encoding="utf-8") as f:
        geo_data_raw = f.read()

    theme = detect_theme(config)
    d3_path = os.path.join(TEMPLATE_DIR, "d3.v7.min.js")
    with open(d3_path, "r", encoding="utf-8") as f:
        d3_code = f.read()

    viewport = {"width": 1080, "height": 2160}

    if theme == "official_standard":
        tpl_path = os.path.join(TEMPLATE_DIR, "template_official_standard.html")
        viewport = {"width": 1440, "height": 1080}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()

        main_title = config.get("title") or f"{region}地图"
        audit_no = config.get("audit_no") or "苏S(2026)86号"
        supervisor = config.get("supervisor") or f"{region}自然资源厅 监制"

        html = tpl.replace("__TITLE__", main_title)\
                  .replace("__MAIN_TITLE__", main_title)\
                  .replace("__AUDIT_NO__", audit_no)\
                  .replace("__SUPERVISOR__", supervisor)\
                  .replace("__D3_CODE__", d3_code)\
                  .replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))\
                  .replace("__GEO_JSON__", geo_data_raw)
        return html, theme, viewport

    elif theme == "national":
        tpl_path = os.path.join(TEMPLATE_DIR, "template_national.html")
        viewport = {"width": 1080, "height": 1920}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()

        main_title = config.get("title") or "全国分布图"
        sub_title = config.get("subtitle") or "截止2026年9月统计"
        brand_stamp = config.get("brand_stamp") or "满爸爱生活"
        banner_bg = config.get("banner_bg") or "#0052D9"
        bg_color = config.get("bg_color") or "#C6DCFD"

        html = tpl.replace("__TITLE__", main_title)\
                  .replace("__MAIN_TITLE__", main_title)\
                  .replace("__SUB_TITLE__", sub_title)\
                  .replace("__BANNER_BG__", banner_bg)\
                  .replace("__BG_COLOR__", bg_color)\
                  .replace("__BRAND_STAMP__", brand_stamp)\
                  .replace("__D3_CODE__", d3_code)\
                  .replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))\
                  .replace("__GEO_JSON__", geo_data_raw)
        return html, theme, viewport

    elif theme == "short_video":
        tpl_path = os.path.join(TEMPLATE_DIR, "template_shortvideo.html")
        viewport = {"width": 1080, "height": 1920}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()
        
        h_lines = config.get("header_lines") or [
            config.get("pill_text") or "2026年",
            config.get("title") or region + "已开通",
            config.get("subtitle") or "轨道交通的城市"
        ]
        while len(h_lines) < 3:
            h_lines.append("")

        bg_style = config.get("bg_style") or "linear-gradient(135deg, #362955 0%, #463467 35%, #5e365b 70%, #75414d 100%)"
        watermark = config.get("watermark_text") or config.get("brand_stamp") or ""

        html = tpl.replace("__TITLE__", f"{region} - {h_lines[1]}")\
                  .replace("__BG_STYLE__", bg_style)\
                  .replace("__LINE_1__", h_lines[0])\
                  .replace("__LINE_2__", h_lines[1])\
                  .replace("__LINE_3__", h_lines[2])\
                  .replace("__WATERMARK__", watermark)\
                  .replace("__D3_CODE__", d3_code)\
                  .replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))\
                  .replace("__GEO_JSON__", geo_data_raw)
        return html, theme, viewport

    elif theme == "city_night":
        tpl_path = os.path.join(TEMPLATE_DIR, "template_city_night.html")
        viewport = {"width": 1080, "height": 2160}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()

        bg_city = (config.get("bg_city") or "").lower()
        city_mapping = {
            "shanghai": "shanghai_night.png", "上海": "shanghai_night.png",
            "nanjing": "nanjing_night.png", "南京": "nanjing_night.png", "江苏": "nanjing_night.png", "江苏省": "nanjing_night.png"
        }
        matched_filename = city_mapping.get(bg_city) or city_mapping.get(region) or "shanghai_night.png"
        default_asset_path = os.path.join(ASSETS_DIR, "backgrounds", matched_filename)
        bg_city_file = config.get("bg_city_image") or default_asset_path
        if not os.path.exists(bg_city_file):
            bg_city_file = os.path.join(ASSETS_DIR, "backgrounds", "nanjing_night.png")

        bg_b64 = ""
        if os.path.exists(bg_city_file):
            with open(bg_city_file, "rb") as bf:
                bg_b64 = "data:image/png;base64," + base64.b64encode(bf.read()).decode("ascii")

        kpis = config.get("kpis") or []
        kpis_html = "".join([f'<span class="kpi-item">{k.get("label", "")}:{k.get("value", "")}</span>' for k in kpis])

        main_title = config.get("title") or f"{region}经济大盘"
        sub_title = config.get("subtitle") or ""
        watermark = config.get("watermark_text") or config.get("brand_stamp") or ""

        html = tpl.replace("__TITLE__", main_title)\
                  .replace("__BG_COLOR__", config.get("bg_color") or "#0672C4")\
                  .replace("__NIGHT_BG_DATA__", bg_b64)\
                  .replace("__MAIN_TITLE__", main_title)\
                  .replace("__SUB_TITLE__", sub_title)\
                  .replace("__KPIS_HTML__", kpis_html)\
                  .replace("__WATERMARK__", watermark)\
                  .replace("__D3_CODE__", d3_code)\
                  .replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))\
                  .replace("__GEO_JSON__", geo_data_raw)
        return html, theme, viewport

    elif theme == "district":
        tpl_path = os.path.join(TEMPLATE_DIR, "template_district.html")
        viewport = {"width": 1080, "height": 1920}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()

        main_title = config.get("title") or f"{region}各区县发展格局"
        sub_title = config.get("subtitle") or "单位:亿元"
        footer_note = config.get("source_note") or config.get("footer_note") or ""

        html = tpl.replace("__TITLE__", main_title)\
                  .replace("__BG_COLOR__", config.get("bg_color") or "#F3F1ED")\
                  .replace("__MAIN_TITLE__", main_title.replace("\n", "<br>"))\
                  .replace("__SUB_TITLE__", sub_title)\
                  .replace("__FOOTER_NOTE__", footer_note)\
                  .replace("__D3_CODE__", d3_code)\
                  .replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))\
                  .replace("__GEO_JSON__", geo_data_raw)
        return html, theme, viewport

    else:
        tpl_path = os.path.join(TEMPLATE_DIR, "poster_template.html")
        viewport = {"width": 1080, "height": 2160}
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl = f.read()

        pill_text = config.get("pill_text") or region
        pill_bg = config.get("pill_bg") or "#DDF32E"
        pill_color = config.get("pill_color") or "#0859A1"
        main_title = config.get("title") or "地图图说"
        sub_title = config.get("subtitle") or ""
        bg_gradient = config.get("bg_gradient") or "linear-gradient(180deg, #0972D3 0%, #0866C2 40%, #0653A0 100%)"
        wm_color = config.get("watermark_color") or "rgba(8, 89, 161, 0.22)"
        brand_stamp = config.get("brand_stamp") or "满爸爱生活"

        logos_html = ""
        for l in config.get("logos") or []:
            icon_tag = f'<img src="{l["icon"]}" class="logo-icon" />' if l.get("icon") else ""
            sub_tag = f'<div class="logo-sub">{l["sub"]}</div>' if l.get("sub") else ""
            logos_html += f'<div class="logo-item">{icon_tag}<div class="logo-name">{l.get("name", "")}</div>{sub_tag}</div>'

        replacements = {
            "__TITLE__": f"{pill_text} - {main_title}",
            "__BG_GRADIENT__": bg_gradient,
            "__PILL_BG__": pill_bg,
            "__PILL_COLOR__": pill_color,
            "__PILL_TEXT__": pill_text,
            "__MAIN_TITLE__": main_title,
            "__SUB_TITLE__": sub_title,
            "__WM_COLOR__": wm_color,
            "__BRAND_STAMP__": brand_stamp,
            "__LOGOS_HTML__": logos_html,
            "__CONFIG_JSON__": json.dumps(config, ensure_ascii=False),
            "__GEO_JSON__": geo_data_raw
        }
        rendered = tpl
        for k, v in replacements.items():
            rendered = rendered.replace(k, v)
        return rendered, theme, viewport


def render_poster(config_path: str, output_path: str = None, scale: int = 2, make_video: bool = False) -> str:
    rendered_html, theme, viewport = build_html(config_path)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=TEMPLATE_DIR, mode="w", encoding="utf-8") as tmp:
        tmp.write(rendered_html)
        tmp_html_path = tmp.name

    if not output_path:
        base_name = os.path.splitext(os.path.basename(config_path))[0]
        output_path = os.path.join(os.getcwd(), f"{base_name}_poster.png")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    w, h = viewport["width"], viewport["height"]
    print(f"[{theme}] 正在渲染海报 (尺寸: {w}x{h}, 缩放: {scale}x)...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            browser = p.chromium.launch(executable_path=chrome_path, headless=True)

        context = browser.new_context(
            viewport={"width": w, "height": h},
            device_scale_factor=scale
        )
        page = context.new_page()
        page.goto(f"file://{tmp_html_path}")
        page.wait_for_function("window.__RENDER_READY__ === true", timeout=15000)
        page.wait_for_timeout(500)

        page.screenshot(path=output_path, full_page=True)
        browser.close()

    try:
        os.remove(tmp_html_path)
    except Exception:
        pass

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✓ 海报生成成功: {output_path} ({file_size_mb:.2f} MB)")

    if make_video:
        video_path = os.path.splitext(output_path)[0] + ".mp4"
        print(f"正在生成 7秒 自媒体推进动效短视频: {video_path}...")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", output_path,
            "-vf", f"scale=8000:-1,zoompan=z='min(zoom+0.00025,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=210:s={w}x{h}:fps=30",
            "-c:v", "libx264", "-t", "7", "-pix_fmt", "yuv420p",
            video_path
        ]
        res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            v_size = os.path.getsize(video_path) / (1024 * 1024)
            print(f"✓ 短视频生成成功: {video_path} ({v_size:.2f} MB)")
        else:
            print("ffmpeg 动效视频生成失败，请检查 ffmpeg 安装与参数", file=sys.stderr)

    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成地图图说信息图海报与自媒体短视频")
    parser.add_argument("--config", "-c", required=True, help="配置文件路径 (JSON)")
    parser.add_argument("--output", "-o", help="输出图片路径 (PNG)")
    parser.add_argument("--scale", "-s", type=int, default=2, help="清晰度倍数 (默认 2)")
    parser.add_argument("--video", "-v", action="store_true", help="一键同步导出 7秒 呼吸推进短视频 (.mp4)")
    args = parser.parse_args()

    try:
        render_poster(args.config, args.output, scale=args.scale, make_video=args.video)
    except Exception as e:
        print(f"生成失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

