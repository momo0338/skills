#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_poster.py — 将 JSON 配置与 GeoJSON 地图数据渲染为高清手机竖屏海报 (1080x2160)
"""

import os
import sys
import json
import argparse
import tempfile
from playwright.sync_api import sync_playwright

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
DATA_DIR = os.path.join(SKILL_DIR, "data")

sys.path.insert(0, SCRIPTS_DIR)
from fetch_geojson import get_geojson


def build_html(config_path: str) -> str:
    """读取配置 + GeoJSON，插值模板，返回完整的渲染用 HTML 字符串（不落盘）。"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    province = config.get("province", "")
    if not province:
        raise ValueError("配置文件必须指定 province 字段 (如 '安徽省', '河南省', '江苏省')")

    # 1. 确保 GeoJSON 存在
    geojson_path = get_geojson(province)
    with open(geojson_path, "r", encoding="utf-8") as f:
        geo_data_raw = f.read()

    # 2. 读取并插值模板
    template_path = os.path.join(TEMPLATE_DIR, "poster_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()

    pill_text = config.get("pill_text") or province
    pill_bg = config.get("pill_bg") or "#DDF32E"
    pill_color = config.get("pill_color") or "#0859A1"
    main_title = config.get("title") or "地图图说"
    sub_title = config.get("subtitle") or ""
    bg_gradient = config.get("bg_gradient") or "linear-gradient(180deg, #0972D3 0%, #0866C2 40%, #0653A0 100%)"
    watermark_text = config.get("watermark_text") or ""
    wm_color = config.get("watermark_color") or "rgba(8, 89, 161, 0.22)"
    brand_stamp = config.get("brand_stamp") or "满爸爱生活"

    # Logo dock HTML
    logos_html = ""
    logos = config.get("logos") or []
    for l in logos:
        icon_tag = f'<img src="{l["icon"]}" class="logo-icon" />' if l.get("icon") else ""
        sub_tag = f'<div class="logo-sub">{l["sub"]}</div>' if l.get("sub") else ""
        logos_html += f'''
        <div class="logo-item">
          {icon_tag}
          <div class="logo-name">{l.get("name", "")}</div>
          {sub_tag}
        </div>
        '''

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

    rendered_html = tpl
    for k, v in replacements.items():
        rendered_html = rendered_html.replace(k, v)
    return rendered_html


def render_poster(config_path: str, output_path: str = None, scale: int = 2) -> str:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    rendered_html = build_html(config_path)

    # 3. 写入临时 HTML
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=TEMPLATE_DIR, mode="w", encoding="utf-8") as tmp:
        tmp.write(rendered_html)
        tmp_html_path = tmp.name

    if not output_path:
        base_name = os.path.splitext(os.path.basename(config_path))[0]
        output_path = os.path.join(os.getcwd(), f"{base_name}_poster.png")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"正在通过无头浏览器渲染海报 (比例: 1080x2160, 缩放倍率: {scale}x)...")

    # 4. Playwright 截图
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            browser = p.chromium.launch(executable_path=chrome_path, headless=True)

        context = browser.new_context(
            viewport={"width": 1080, "height": 2160},
            device_scale_factor=scale
        )
        page = context.new_page()
        page.goto(f"file://{tmp_html_path}")
        page.wait_for_function("window.__RENDER_READY__ === true", timeout=15000)
        page.wait_for_timeout(500)

        page.screenshot(path=output_path, full_page=True)
        browser.close()

    # 清理临时文件
    try:
        os.remove(tmp_html_path)
    except Exception:
        pass

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"海报生成成功！")
    print(f"输出路径: {output_path} ({file_size_mb:.2f} MB)")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成地图图说信息图海报")
    parser.add_argument("--config", "-c", required=True, help="配置文件路径 (JSON)")
    parser.add_argument("--output", "-o", help="输出图片路径 (PNG)")
    parser.add_argument("--scale", "-s", type=int, default=2, help="截图清晰度倍数 (默认 2，即 2160x4320 超清 Retina)")
    args = parser.parse_args()

    try:
        render_poster(args.config, args.output, scale=args.scale)
    except Exception as e:
        print(f"生成失败: {e}", file=sys.stderr)
        sys.exit(1)
