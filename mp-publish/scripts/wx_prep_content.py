#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML -> 微信公众号草稿正文预处理
1. 抽取 base64 图片 -> $WX_RUN_DIR/zj_img_N.jpg（默认 /tmp；按账号隔离，待上传微信素材）
2. CSS 类样式全部内联（微信正文过滤 <style>），展开 var(--x)
3. 时间轴 ::before 竖线伪元素 -> 真实 <span> 节点
4. 图片 src 替换为 {{IMGn}} 占位符，上传后回填
5. 用第一张实拍图裁 900x383 封面 -> $WX_RUN_DIR/zj_cover.jpg
输出: $WX_RUN_DIR/zj_wechat_content.html + $WX_RUN_DIR/zj_imgmap.json
"""
import re, json, io, base64, os, sys
from bs4 import BeautifulSoup, NavigableString
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import run_dir  # noqa: E402

RUN_DIR = run_dir()          # 默认 /tmp；wx_pipeline 会按账号注入 WX_RUN_DIR

if len(sys.argv) < 2:
    sys.exit("用法: python wx_prep_content.py <源HTML路径>")
SRC = sys.argv[1]   # 源 HTML 路径（必填，支持任意位置）

html = open(SRC, encoding="utf-8").read()
# 兼容全内联样式稿（无 <style> 块）：2026-09-12 修，避免 'NoneType' 崩溃
_m = re.search(r"<style[^>]*>(.*?)</style>", html, re.S)
css = _m.group(1) if _m else ""
css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)  # 剥离注释，防污染选择器

# ---------- 1. 抽取 base64 图片 ----------
# 2026-09-22 加固：允许包含换行/空格等空白字符，并在解码前清洗，防截断导致 broken data stream
b64_pattern = re.compile(r'data:image/(jpeg|jpg|png);base64,([A-Za-z0-9+/=\s]+)')
imgmap = []
idx = 0
def save_img(m):
    global idx
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else "png"
    path = os.path.join(RUN_DIR, f"zj_img_{idx}.{ext}")
    clean_b64 = re.sub(r'\s+', '', m.group(2))
    open(path, "wb").write(base64.b64decode(clean_b64))
    imgmap.append({"idx": idx, "path": path, "mime": f"image/{'jpeg' if ext=='jpg' else ext}"})
    idx += 1
    return f'{{{{IMG{idx-1}}}}}'
html2 = b64_pattern.sub(save_img, html)
print(f"[1] 抽取图片 {idx} 张")

# ---------- 2. 解析 CSS ----------
# 展开 :root 变量
varmap = dict(re.findall(r'--([\w-]+)\s*:\s*([^;]+);', css))
def expand_vars(decls):
    def rep(m):
        return varmap.get(m.group(1), m.group(0))
    prev = None
    while prev != decls:
        prev = decls
        decls = re.sub(r'var\(--([\w-]+)\)', rep, decls)
    return decls

rules = []  # (selector, decls, specificity)
for raw in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
    sels, decls = raw[0].strip(), raw[1].strip()
    if not decls or sels.startswith("@"):
        continue
    decls = expand_vars(decls)
    for sel in sels.split(","):
        sel = sel.strip()
        if not sel or "::" in sel or ":root" in sel or sel == "*":
            continue
        # specificity: (ids, classes+pseudo, elements)
        classes = len(re.findall(r'\.[\w-]+', sel))
        elems = len(re.findall(r'(?:^|[\s>+~])([a-zA-Z][\w-]*)', sel))
        rules.append((sel, decls, (0, classes, elems)))
# 按特异性+出现顺序排序，后者覆盖前者
rules.sort(key=lambda r: r[2])
print(f"[2] 解析 CSS 规则 {len(rules)} 条")

# ---------- 3. 选择器匹配 ----------
def match_simple(el, part):
    """匹配单个简单选择器，如 h2 / .badge / .badge.b / .t-item.pm"""
    part = part.strip()
    if not part:
        return False
    m = re.match(r'^([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)$', part)
    if not m:
        return False  # 含 :hover 等不处理
    tag, cls = m.group(1) or "", m.group(2)
    if tag and el.name != tag:
        return False
    if not (cls or tag):
        return False
    for c in re.findall(r'\.([\w-]+)', cls):
        if c not in (el.get("class") or []):
            return False
    return True

def match_selector(el, sel):
    parts = re.split(r'[\s>+~]+', sel.strip())
    if not match_simple(el, parts[-1]):
        return False
    # 祖先链（简化：只支持空格后代组合）
    anc = list(el.parents)
    ai = len(anc) - 1
    for p in reversed(parts[:-1]):
        found = False
        while ai >= 0:
            a = anc[ai]
            ai -= 1
            if hasattr(a, "name") and a.name and match_simple(a, p):
                found = True
                break
        if not found:
            return False
    return True

def parse_decls(decls):
    out = {}
    for d in decls.split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            out[k.strip()] = v.strip()
    return out

soup = BeautifulSoup(html2, "html.parser")
# 去掉 style 标签和 head
for t in soup.find_all("style"):
    t.decompose()
body = soup.body or soup

count_inlined = 0
for el in body.find_all(True):
    # 去掉编辑器注入的节点 id
    if "data-page-node-id" in el.attrs:
        del el.attrs["data-page-node-id"]
    merged = {}
    for sel, decls, _ in rules:
        if match_selector(el, sel):
            merged.update(parse_decls(decls))
    if not merged:
        continue
    if el.name in ("html", "head", "title", "meta", "link"):
        continue
    old = el.get("style", "")
    el["style"] = (merged_serial := ";".join(f"{k}:{v}" for k, v in merged.items()) + (";" + old if old else ""))
    count_inlined += 1
print(f"[3] 内联样式节点 {count_inlined} 个")

# ---------- 4. 伪元素 -> 真实节点（时间轴竖线） ----------
# .t-item{position:relative} 已内联；给非最后一个 t-item 注入竖线 span
t_items = body.select(".t-item")
for ti in t_items[:-1]:
    line = soup.new_tag("span")
    line["style"] = ("display:block;width:2px;background:#d8e6fa;"
                     "height:100%;flex-shrink:0;align-self:stretch;")
    ti.insert(0, line)
print(f"[4] 时间轴竖线注入 {max(0, len(t_items)-1)} 条")

# ---------- 4.5 微信方言转换（关键！） ----------
# 微信存储层会把 <div> 溶解成 p/span 并丢弃大量内联样式（实测 style 235->126）
# 必须先全部转成 <section>（微信原生方言）再推送
content0 = body.decode_contents().strip()
content0 = re.sub(r'<div\b', '<section', content0)
content0 = re.sub(r'</div>', '</section>', content0)
assert '<div' not in content0, "仍有 div 残留"

# ---------- 5. 输出正文 ----------
content = content0
# body 自身样式转成外层 section
content = ('<section style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\','
           '\'Hiragino Sans GB\',\'Microsoft YaHei\',sans-serif;font-size:16px;color:#333;'
           'line-height:1.85;">'   # 只做排版，不做布局 padding（避免与 .page 双重内边距）
           + content + "</section>")
# .page 容器还有一层自身 padding，先归一再写文件（水平清零实现"左右拉满"）
for v in ("padding:20px 14px 36px", "padding:28px 20px 48px"):
    content = content.replace("max-width:677px;margin:0 auto;background:#fff;" + v,
                              "max-width:100%;background:#fff;padding:8px 0px 40px")
open(os.path.join(RUN_DIR, "zj_wechat_content.html"), "w", encoding="utf-8").write(content)
print(f"[5] 正文输出 {len(content)} 字符 -> {os.path.join(RUN_DIR, 'zj_wechat_content.html')}")
json.dump(imgmap, open(os.path.join(RUN_DIR, "zj_imgmap.json"), "w"))

# ---------- 6. 封面 900x383（2.35:1 微信头条封面；cover 模式永无黑框） ----------
# 公众号封面规范：2.35:1 => 900x383（头条）；1:1 中心区为朋友圈/普通用户裁切安全区。
# 旧版缺陷(2026-09-05 实测修复)：选图用"最宽横图 max(aspect)"，但 16:9(1.78) 源图
#   仍小于 2.35 -> crop((left<0,...)) 越界，PIL 对越界区补纯黑 -> 封面左右黑框。
# 修复：
#   1) 选图：横图优先，比例 loss=|log2(aspect/2.35)| 最小者（越接近 2.35 裁得越少）
#   2) 裁剪：cover 模式 scale=max(900/w,383/h) 先等比放大再居中裁 -> 任意比例无黑框
#   3) 自检：边缘 6px 若整列/整行近纯黑则告警提示（防源图自带黑边/构图暗角）
import math
TARGET = 900.0 / 383.0
if not imgmap:
    print("[6] 无内嵌图，跳过封面生成（推送时用 --cover 指定）")
    sys.exit(0)   # 正文已写好，无需封面即退出（正文产物保留）

def _aspect(p):
    try:
        w, h = Image.open(p).size
        return w / h if w >= h else 0.0   # 竖图记为 0（淘汰）
    except Exception:
        return 0.0
_cands = [im_ for im_ in imgmap if _aspect(im_["path"]) > 0.0]
if not _cands:
    print("[6] 无横图候选，跳过封面生成（推送时用 --cover 指定）")
    sys.exit(0)
best = min(_cands, key=lambda im_: abs(math.log2(_aspect(im_["path"]) / TARGET)))
w, h = Image.open(best["path"]).size
im = Image.open(best["path"]).convert("RGB")
s = max(900.0 / w, 383.0 / h)                      # cover：至少一边充满目标框
nw, nh = int(round(w * s)), int(round(h * s))
im2 = im.resize((nw, nh), Image.LANCZOS)
left, top = (nw - 900) // 2, (nh - 383) // 2       # 居中裁（主体落 1:1 中央安全区）
im2.crop((left, top, left + 900, top + 383)).save(os.path.join(RUN_DIR, "zj_cover.jpg"), quality=90)
# 黑框自检：四边 6px 条带若平均亮度<12 且近零方差 -> 疑似黑边
_cv = Image.open(os.path.join(RUN_DIR, "zj_cover.jpg")).convert("L")
def _edge_dark(region):
    hist = region.histogram()
    n = sum(hist)
    avg = sum(i * c for i, c in enumerate(hist)) / n
    var = sum(c * (i - avg) ** 2 for i, c in enumerate(hist)) / n
    return avg < 12 and var < 30
for _name, _box in [("左右", (0, 0, 6, 383)), ("右", (894, 0, 900, 383)),
                    ("上", (0, 0, 900, 6)), ("下", (0, 377, 900, 383))]:
    if _edge_dark(_cv.crop(_box)):
        print(f"[6][WARN] 封面{_name}边缘疑似黑框，请人工检查 {os.path.join(RUN_DIR, 'zj_cover.jpg')} 或换源图")
print(f"[6] 封面 900x383(2.35:1) cover 裁剪 -> /tmp/zj_cover.jpg "
      f"(源图 zj_img_{best['idx']} {w}x{h}, 裁前放大 s={s:.3f}, 裁窗 {(left,top)}~({left+900},{top+383}))")
print("DONE")
