#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mp_download.py — 微信公众号文章/长图自动识别与高清下载工具
(集成长图智能切段、多卡片海报与标准长文自适应路由)

用法：
    python3 mp_download.py "<微信文章URL>" [--out-dir DIR] [--mode {auto,standard,long,multi}]
    
核心能力：
    1. 自适应形态探测（auto）：
       - long_image（长图/海报）：自动按 2000px 切段 + 60px 重叠防断字
       - multi_card（多卡片海报）：多卡顺序提取并排版
       - standard_article（标准图文）：正文 HTML 转 Markdown，本地高清图插值替换
    2. 免登录与穿透：锁死 iPhone MicroMessenger UA，跟随 302 重定向
    3. 全路径图片发现：支持 <img>、<svg background>、xlink:href 三路覆盖
    4. 原图通道：自动替换 /640? 为 /0? 抓取最高清原图，自动过滤无效 GIF 装饰图
    5. 发布源防坑校验：识别中介引流黑名单与高校转发号
"""

import argparse
import base64
import datetime
import html as H
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse, parse_qs

# 移动端原生 MicroMessenger UA（自动穿透 302 重定向与免登录态）
UA_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49(0x18003128) NetType/WIFI Language/zh_CN"
)

# 发布号 biz 安全字典
BLOCKED_BIZ = {
    'MzkxMTU4OTY2Ng==': '求职汇（中介引流号：带水印与过期个人引流码，正文无官方硬信息，不当源）',
}
REFERENCE_BIZ = {
    'MzkzNDU4MjU4Mw==': '东林就业招聘简讯平台（高校就业转发号，非官方源，建议回企业自有官号）',
    'MjM5MTE5MTY4Mw==': '中国人民大学就业创业指导中心（高校就业转发号，非官方源，建议回企业自有官号）',
}

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def sanitize_filename(name):
    """去除文件名中的非法字符"""
    clean = re.sub(r'[\/:*?"<>|]', '_', name or '').strip()
    return clean[:80] if clean else 'untitled_article'

def parse_biz(url):
    m = re.search(r'[?&]__biz=([^&#]+)', url or '')
    return m.group(1) if m else None

def decode_biz(biz):
    try:
        return base64.b64decode(biz + '==').decode()
    except Exception:
        return biz

def html_to_markdown(html_text):
    """简易正文 HTML 转 Markdown（保留段落、标题、列表、加粗）"""
    t = html_text
    # 移除脚本和样式
    t = re.sub(r'<script.*?</script>', '', t, flags=re.S)
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    
    # 标题处理
    t = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n\n# \1\n\n', t, flags=re.S)
    t = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', t, flags=re.S)
    t = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n\n### \1\n\n', t, flags=re.S)
    t = re.sub(r'<h[4-6][^>]*>(.*?)</h[4-6]>', r'\n\n#### \1\n\n', t, flags=re.S)
    
    # 加粗与强调
    t = re.sub(r'<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>', r'**\1**', t, flags=re.S)
    t = re.sub(r'<(?:em|i)[^>]*>(.*?)</(?:em|i)>', r'*\1*', t, flags=re.S)
    
    # 换行与段落
    t = re.sub(r'<br\s*/?>', '\n', t)
    t = re.sub(r'</p>', '\n\n', t)
    t = re.sub(r'</li>', '\n', t)
    t = re.sub(r'<li[^>]*>', '- ', t)
    t = re.sub(r'</(section|div|tr)>', '\n', t)
    
    # 剥除剩余标签（包括未闭合的不完整标签）
    t = re.sub(r'<[^>]*>', '', t)
    t = re.sub(r'<[^>]*$', '', t)
    t = H.unescape(t)

    # 微信系统噪音过滤
    noise_patterns = [
        r'预览时标签不可点',
        r'轻点两下取消赞',
        r'轻点两下点赞',
        r'微信扫一扫关注该公众号',
        r'微信扫一扫赞赏作者',
    ]
    for np in noise_patterns:
        t = re.sub(np, '', t)

    # 清理残留的空加粗符号
    t = re.sub(r'\*\*\s*\*\*', '', t)
    
    # 规范化连续空行
    lines = [line.strip() for line in t.split('\n')]
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if line:
            cleaned_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append('')
            prev_empty = True
    return '\n'.join(cleaned_lines).strip()

class WeChatDownloader:
    def __init__(self, url, out_dir=None, mode='auto', step=2000, overlap=60):
        self.url = url
        self.out_dir = out_dir
        self.mode = mode  # auto, standard, long, multi
        self.step = step
        self.overlap = overlap
        self.meta = {}
        self.content_images = []
        self.html_raw = ""
        self.body_html = ""
        self.detected_form = "standard_article"

    def fetch_and_parse(self):
        """第 1 步：抓取页面并提取核心元数据与图片链接"""
        biz = parse_biz(self.url)
        if biz in BLOCKED_BIZ:
            print(f"[WARN] ⚠️ 发布号 biz={biz}（{decode_biz(biz)}）命中黑名单：「{BLOCKED_BIZ[biz]}」")
        if biz in REFERENCE_BIZ:
            print(f"[NOTICE] ℹ️ 发布号 biz={biz}（{decode_biz(biz)}）为转发号：「{REFERENCE_BIZ[biz]}」，建议后续回企业官网核实。")

        # 抓取页面
        tmp_html = f"/tmp/wx_art_{os.getpid()}.html"
        r = sh(f'curl -sL "{self.url}" -A "{UA_IPHONE}" --max-time 30 -o "{tmp_html}"')
        if not os.path.exists(tmp_html) or os.path.getsize(tmp_html) < 2000:
            if os.path.exists(tmp_html): os.remove(tmp_html)
            raise RuntimeError(f"页面抓取失败或内容过小，可能被安全验证拦截: {self.url}")
        
        with open(tmp_html, 'r', encoding='utf-8', errors='ignore') as f:
            self.html_raw = f.read()
        os.remove(tmp_html)

        # 提取 Meta
        m_title = re.search(r'<meta property="og:title" content="([^"]*)"', self.html_raw)
        title = H.unescape(m_title.group(1)) if m_title else "未命名文章"
        
        # 提取发布者（支持 htmlDecode 包装）
        m_nick = re.search(r'var nickname = (?:htmlDecode\()?"([^"]*)"', self.html_raw)
        publisher = m_nick.group(1).strip() if m_nick else ""

        # 提取发布时间
        m_ct = re.search(r'var ct = "(\d+)"', self.html_raw) or re.search(r"var createTime = '([^']*)'", self.html_raw)
        publish_time = ""
        if m_ct:
            val = m_ct.group(1)
            if val.isdigit() and len(val) == 10:
                publish_time = datetime.datetime.fromtimestamp(int(val)).strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_time = val

        # 提取阅读原文
        m_src = re.search(r'var msg_source_url = .([^;\']*)', self.html_raw)
        source_url_field = m_src.group(1) if m_src else ""

        self.meta = {
            "title": title,
            "publisher": publisher,
            "publish_time": publish_time,
            "source_url": self.url,
            "original_read_more": source_url_field,
            "biz": biz,
        }

        # 定位正文范围
        idx_start = self.html_raw.find('id="js_content"')
        if idx_start < 0:
            raise RuntimeError("未在页面中找到 id=\"js_content\"（可能已被删除或需要微信客户端登录）")
        
        # 找到标签闭合处，剥除开头的 <div id="js_content" ...> 残留
        gt_pos = self.html_raw.find('>', idx_start)
        body = self.html_raw[gt_pos + 1:] if gt_pos > 0 else self.html_raw[idx_start:]
        idx_end = body.find('rich_media_area_extra')
        if idx_end > 0:
            body = body[:idx_end]
        self.body_html = body

        # 全路径提取图片：<img> + <svg background> + xlink:href
        found_urls = []
        for m in re.finditer(r'data-src=["\']([^"\']+)["\']', body):
            found_urls.append((m.start(), m.group(1)))
        for m in re.finditer(r'url\(\\?["\']?(https?://(?:mmbiz|mmecoa)\.qpic\.cn/[^\s"\'<>)\\]+)\\?["\']?\)', body):
            found_urls.append((m.start(), m.group(1)))
        for m in re.finditer(r'(?:xlink:)?href=["\'](https?://(?:mmbiz|mmecoa)\.qpic\.cn/[^"\']+)["\']', body):
            found_urls.append((m.start(), m.group(1)))
        
        found_urls.sort(key=lambda x: x[0])
        
        # 去重并清洗为高清原图链接（/640? 替换为 /0?）
        seen = set()
        cleaned_urls = []
        for pos, u in found_urls:
            u_clean = u.replace('&amp;', '&').replace('\\x26amp;', '&')
            u_clean = u_clean.split('#')[0]
            # 升级为高清原图
            u_clean = re.sub(r'/\d+(\?wx_fmt=)', r'/0\1', u_clean)
            if u_clean not in seen:
                seen.add(u_clean)
                cleaned_urls.append(u_clean)

        self.raw_img_urls = cleaned_urls
        print(f"[fetch] 抓取完成: 《{title}》 | 发布者: {publisher} | 抽取图片数: {len(cleaned_urls)}")

    def download_and_analyze_images(self, work_dir):
        """第 2 步：下载图片并使用 PIL 测算长宽与长图形态"""
        try:
            from PIL import Image
        except ImportError:
            sys.exit("[FATAL] 需要 PIL 库支持图片处理，请先安装 Pillow: pip install Pillow")

        img_dir = os.path.join(work_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        content_imgs = []
        has_long_img = False

        for idx, u in enumerate(self.raw_img_urls):
            if 'readtemplate' in u or 'mpvideo' in u:
                continue
            
            local_path = os.path.join(img_dir, f"img_{idx+1:02d}.png")
            # 带 Referer 下载防盗链
            sh(f'curl -sL "{u}" -A "{UA_IPHONE}" -e "https://mp.weixin.qq.com/" -o "{local_path}"')
            
            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                continue

            try:
                with Image.open(local_path) as im:
                    # 过滤极小图标（如 1x1 占位或小装饰图标）
                    if im.width < 80 and im.height < 80:
                        os.remove(local_path)
                        continue
                    # 动图智能处理：若是小尺寸表情包/点赞动效（<350x350）则过滤；
                    # 若是大尺寸海报/长图带微动效，提取第0帧静态化为高质量 PNG，保留正文内容
                    if getattr(im, 'is_animated', False):
                        if im.width < 350 and im.height < 350:
                            os.remove(local_path)
                            continue
                        im.seek(0)
                        frame0 = im.convert('RGB')
                        frame0.save(local_path, 'PNG')
                        im = frame0
                    w, h = im.size
                    ratio = h / max(1, w)
                    # 判定长图：尺寸宽≥800且高≥2500，或比例高长比≥2.5且高度≥2000
                    is_long = (w >= 800 and h >= 2500) or (ratio >= 2.5 and h >= 2000)
                    if is_long:
                        has_long_img = True
                    content_imgs.append({
                        "idx": idx + 1,
                        "url": u,
                        "path": local_path,
                        "rel_path": os.path.relpath(local_path, work_dir),
                        "width": w,
                        "height": h,
                        "ratio": round(ratio, 2),
                        "is_long": is_long
                    })
            except Exception as e:
                # 遇到损坏文件则移除
                if os.path.exists(local_path): os.remove(local_path)
                continue

        self.content_images = content_imgs
        self.has_long_img = has_long_img
        print(f"[images] 有效内容图: {len(content_imgs)} 张 | 包含长图海报: {'是' if has_long_img else '否'}")

    def route_best_path(self):
        """第 3 步：根据文字与图片形态自适应选择最佳路径"""
        # 统计正文文本
        plain_text = html_to_markdown(self.body_html)
        text_lines = [l for l in plain_text.split('\n') if l.strip()]
        line_count = len(text_lines)
        char_count = len(plain_text)

        self.meta["text_lines"] = line_count
        self.meta["text_chars"] = char_count
        self.plain_text = plain_text

        # 模式判定
        if self.mode != 'auto':
            self.detected_form = self.mode
        else:
            if self.has_long_img:
                self.detected_form = "long_image"
            elif line_count <= 25 and len(self.content_images) >= 3:
                self.detected_form = "multi_card"
            elif char_count >= 300 or line_count > 25:
                self.detected_form = "standard_article"
            else:
                self.detected_form = "standard_article"

        self.meta["detected_form"] = self.detected_form
        print(f"[routing] 最佳路径决策: 【{self.detected_form}】（正文行数: {line_count}, 字数: {char_count}, 图片数: {len(self.content_images)}）")

    def process_and_export(self, work_dir):
        """第 4 步：执行对应路径的处理与文件导出"""
        from PIL import Image

        segs_info = []
        # 如果是长图模式，执行切段（带 60px 重叠防断字）
        if self.detected_form == "long_image":
            segs_dir = os.path.join(work_dir, "images", "segs")
            os.makedirs(segs_dir, exist_ok=True)
            for c in self.content_images:
                if not c["is_long"]:
                    continue
                im = Image.open(c["path"]).convert("RGB")
                W, H_total = im.size
                k = 0
                while k * self.step < H_total:
                    seg_name = f"seg_{c['idx']:02d}_{k+1:02d}.png"
                    seg_path = os.path.join(segs_dir, seg_name)
                    # 步长裁切并向后多切 overlap 像素
                    y_start = k * self.step
                    y_end = min(H_total, (k + 1) * self.step + self.overlap)
                    im.crop((0, y_start, W, y_end)).save(seg_path)
                    segs_info.append({
                        "parent_img": c["idx"],
                        "seg_name": seg_name,
                        "abs_path": seg_path,
                        "rel_path": os.path.relpath(seg_path, work_dir),
                        "crop_range": [y_start, y_end]
                    })
                    k += 1
            print(f"[segs] 长图已自动切分: 产出 {len(segs_info)} 个 2000px 切片（带 {self.overlap}px 重叠）")

        # 生成 Markdown 文件
        md_lines = []
        md_lines.append("---")
        md_lines.append(f'title: "{self.meta["title"]}"')
        md_lines.append(f'publisher: "{self.meta["publisher"]}"')
        md_lines.append(f'publish_time: "{self.meta["publish_time"]}"')
        md_lines.append(f'source_url: "{self.meta["source_url"]}"')
        md_lines.append(f'form: "{self.detected_form}"')
        md_lines.append(f'image_count: {len(self.content_images)}')
        md_lines.append(f'has_long_image: {str(self.has_long_img).lower()}')
        md_lines.append("tags:")
        md_lines.append("  - 微信公众号")
        if self.detected_form == "long_image":
            md_lines.append("  - 招聘长图")
            md_lines.append("  - 海报切片")
        elif self.detected_form == "multi_card":
            md_lines.append("  - 多卡片推文")
        else:
            md_lines.append("  - 图文归档")
        md_lines.append("---\n")

        # 标题与元数据
        md_lines.append(f"# {self.meta['title']}\n")
        meta_desc = f"> **发布方**：{self.meta['publisher']} ｜ **发布时间**：{self.meta['publish_time']} ｜ **原文形态**：`{self.detected_form}`"
        if self.meta.get('original_read_more'):
            meta_desc += f" ｜ [阅读原文]({self.meta['original_read_more']})"
        md_lines.append(meta_desc + "\n")

        # 根据不同形态组织正文
        if self.detected_form == "long_image":
            md_lines.append("## 📌 长图公告概览\n")
            if self.plain_text.strip():
                md_lines.append("### 原文附随文字\n")
                md_lines.append(self.plain_text + "\n")
            
            md_lines.append("### 🖼️ 长图切片索引（已做 2000px 切段 + 重叠防断字，供 OCR 与精读）\n")
            for seg in segs_info:
                md_lines.append(f"![切片 {seg['seg_name']}]({seg['rel_path']})")
                md_lines.append(f"*切片位置: Y轴 {seg['crop_range'][0]}px ~ {seg['crop_range'][1]}px*\n")
            
            md_lines.append("### 完整长图原文\n")
            for img in self.content_images:
                md_lines.append(f"![完整海报 {img['idx']}]({img['rel_path']})\n")

        elif self.detected_form == "multi_card":
            md_lines.append("## 🗂️ 多卡片内容图集\n")
            if self.plain_text.strip():
                md_lines.append(self.plain_text + "\n")
            for img in self.content_images:
                md_lines.append(f"![卡片 {img['idx']}]({img['rel_path']})\n")

        else: # standard_article
            md_lines.append("## 📖 正文内容\n")
            md_lines.append(self.plain_text + "\n")
            if self.content_images:
                md_lines.append("## 🖼️ 文中配图汇总\n")
                for img in self.content_images:
                    md_lines.append(f"![配图 {img['idx']}]({img['rel_path']})\n")

        # 输出文件保存
        clean_title = sanitize_filename(self.meta["title"])
        md_file = os.path.join(work_dir, f"{clean_title}.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        # 保存 meta.json 与兼容字段
        form_map = {'long_image': 'long', 'multi_card': 'multi', 'standard_article': 'text'}
        self.meta["title_official"] = self.meta["title"]
        self.meta["source_url_field"] = self.meta.get("original_read_more")
        self.meta["form"] = form_map.get(self.detected_form, self.detected_form)
        self.meta["images"] = self.content_images
        self.meta["segs_info"] = segs_info
        self.meta["segs"] = [s["abs_path"] for s in segs_info]
        json_file = os.path.join(work_dir, "meta.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)

        print(f"\n🎉 交付完毕！")
        print(f"📄 Markdown 文档: {md_file}")
        print(f"📊 元数据清单: {json_file}")
        print(f"📁 资源存储目录: {work_dir}")
        return md_file

    def run(self):
        self.fetch_and_parse()
        
        # 确定保存工作目录
        if not self.out_dir:
            clean_title = sanitize_filename(self.meta["title"])
            self.out_dir = os.path.join(os.getcwd(), clean_title)
        os.makedirs(self.out_dir, exist_ok=True)

        self.download_and_analyze_images(self.out_dir)
        self.route_best_path()
        return self.process_and_export(self.out_dir)

def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章/长图自动识别与高清下载工具 (mp-save)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="微信文章完整 URL (mp.weixin.qq.com/s/...)")
    parser.add_argument("--out-dir", "-o", default=None, help="输出目录（缺省自动以文章标题建目录）")
    parser.add_argument("--mode", "-m", choices=["auto", "standard", "long", "multi"], default="auto",
                        help="运行模式：auto（自动探测最佳路径，默认）、standard（强制标准图文）、long（强制长图切段）、multi（强制多卡）")
    parser.add_argument("--step", type=int, default=2000, help="长图切片步长高度（默认 2000px）")
    parser.add_argument("--overlap", type=int, default=60, help="长图切片重叠高度（默认 60px）")

    args = parser.parse_args()
    downloader = WeChatDownloader(
        url=args.url,
        out_dir=args.out_dir,
        mode=args.mode,
        step=args.step,
        overlap=args.overlap
    )
    downloader.run()

MpArticleDownloader = WeChatDownloader

if __name__ == "__main__":
    main()
