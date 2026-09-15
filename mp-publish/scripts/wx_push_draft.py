#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号文章 -> 草稿箱 一键推送（摘要自动处理版）
通用流水线，每篇文章只用改命令行参数；DIGEST(摘要) 规则见下方 resolve_digest。

用法:
  python wx_push_draft.py \
      --title "南京出发20分钟高铁！镇江一天刷两馆，全免费" \
      --author "满爸爱生活" \
      --digest "（可选，SEO摘要≤120字；不传则自动从正文开头提炼）" \
      [--content-file /tmp/wx_wechat_content.html] \
      [--imgmap /tmp/wx_imgmap.json] \
      [--cover /tmp/wx_cover.jpg] \
      [--update-media-id <已有草稿media_id>]   # 传了就 draft/update 就地改，不新增草稿

前置: wx_prep_content.py 已产出 --content-file(含{{IMGn}}占位)/--imgmap/--cover
流程: access_token -> media/uploadimg(正文图) -> 回填URL -> add_material(封面) -> draft/add|update
"""
import json, os, re, subprocess, sys, argparse, unicodedata

def _read_cred_file(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def load_wx_creds():
    """从环境变量或 ~/.config/weixin/ 文件读取 AppID/AppSecret，绝不硬编码到仓库。"""
    appid = os.environ.get("WX_APPID") or _read_cred_file(os.path.expanduser("~/.config/weixin/appid"))
    secret = os.environ.get("WX_APPSECRET") or _read_cred_file(os.path.expanduser("~/.config/weixin/appsecret"))
    if not appid or not secret:
        sys.stderr.write("⚠️ 未配置微信凭据：请设置环境变量 WX_APPID/WX_APPSECRET，"
                         "或在 ~/.config/weixin/ 下放置 appid / appsecret 文件\n")
        sys.exit(2)
    return appid, secret

APPID, SECRET = load_wx_creds()
MAX_DIGEST = 120  # 微信摘要上限（字符）

ap = argparse.ArgumentParser()
ap.add_argument("--title", required=True)
ap.add_argument("--author", default="满爸爱生活")
ap.add_argument("--digest", default="", help="SEO 摘要，≤%d 字符；为空则自动生成" % MAX_DIGEST)
ap.add_argument("--content-file", default="/tmp/zj_wechat_content.html")
ap.add_argument("--imgmap", default="/tmp/zj_imgmap.json")
ap.add_argument("--cover", default="/tmp/zj_cover.jpg")
ap.add_argument("--source-url", default="", help="原文链接/活动页地址，正文禁<a>时靠它外链")
ap.add_argument("--update-media-id", default="",
                help="就地更新已有草稿（draft/update，不新增草稿）；留空则新建（draft/add）")
args = ap.parse_args()

def ccount(s):
    """中英混排字符数（微信按字数计，英数每字符算1）"""
    return sum(1 for c in unicodedata.normalize("NFC", s) if not c.isspace())

def curl_json(url, extra=None):
    import os
    clean_env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
    cmd = ["curl", "-s", "--max-time", "60", url] + (extra or [])
    r = subprocess.run(cmd, env=clean_env, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        print("[ERR] 非JSON响应:", r.stdout[:300], r.stderr[:200])
        sys.exit(1)

# ---------- 摘要（digest）解析：显式 > 自动 ----------
def resolve_digest():
    if args.digest.strip():
        d = args.digest.strip()
        if ccount(d) > MAX_DIGEST:
            print(f"[WARN] 手动摘要 {ccount(d)} 字符超限，已截断到 {MAX_DIGEST}")
            d = d[:MAX_DIGEST]
        return d, "手动"
    # 自动生成：取正文纯文本开头（SEO 兜底；公众号后台可再手改）
    raw = open(args.content_file, encoding="utf-8").read()
    txt = re.sub(r"<[^>]+>", " ", raw)          # 去标签
    txt = re.sub(r"\{\{IMG\d+\}\}", "", txt)      # 去图片占位
    txt = re.sub(r"\s+", " ", txt).strip()
    d = txt[:MAX_DIGEST - 4].rstrip("，。、；:： ") + "……"
    return d, "自动(正文开头兜底)"

DIGEST, digest_src = resolve_digest()
print(f"[0] 摘要({digest_src}) {ccount(DIGEST)}字符: {DIGEST}")
assert ccount(DIGEST) <= MAX_DIGEST, "摘要超 120 字符"
if digest_src.startswith("自动"):
    print(">>> 建议: 按 SEO 摘要规范（SKILL.md「摘要规范」）手动写 --digest 以最大化长尾流量")

# ---------- 1. access_token ----------
tok = curl_json(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}")
if "access_token" not in tok:
    print("[FAIL] 获取 token 失败:", tok)
    if tok.get("errcode") == 40164:
        m = re.search(r"invalid ip ([\d.]+)", tok.get("errmsg", ""))
        print(f">>> 请在公众号后台「设置与开发-基本配置-IP白名单」添加: {m.group(1) if m else '见errmsg'}")
    sys.exit(1)
T = tok["access_token"]
print("[1] access_token 获取成功")

# ---------- 2. 上传正文图片 ----------
imgmap = json.load(open(args.imgmap))
urls = {}
for im in imgmap:
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={T}",
                  extra=["-F", "media=@" + im["path"]])
    if "url" not in r:
        print(f"[FAIL] 图{im['idx']} 上传失败:", r); sys.exit(1)
    urls["{{IMG%d}}" % im["idx"]] = r["url"]
    print(f"    图{im['idx']} -> {r['url'][:70]}")
print("[2] 正文图片上传完成")

# ---------- 3. 组装正文 ----------
content = open(args.content_file, encoding="utf-8").read()
for k, v in urls.items():
    content = content.replace(k, v)
assert "{{IMG" not in content, "存在未回填占位符"
content = re.sub(r'\s*class="[^"]*"', "", content)
content = re.sub(r'>\s+<', "><", content)

# 防御：真实 style="..." 属性内的 HTML 实体必须解码回裸字符。
# 微信把 style 里作者写的 &#39; 视为非法 → 会整段清空成 style=""（2026-09-14 实测：
# draft/get 读回的内容回写时踩过，外层 font-family 全丢）。
def _decode_style(m):
    v = m.group(1)
    for a, b in (("&#39;", "'"), ("&#34;", '"'), ("&quot;", '"'), ("&amp;", "&")):
        v = v.replace(a, b)
    return 'style="' + v + '"'
content = re.sub(r'style="([^"]*)"', _decode_style, content)
_n_empty = content.count('style=""')
print(f"[3.1] 归一化完成；style= {content.count('style=')} 处，style=\"\" {_n_empty} 处")
if _n_empty:
    print("[FAIL] 正文存在空 style 属性，推送会丢样式，请检查输入 HTML")
    sys.exit(1)
print(f"[3] 正文组装完成 {len(content)} 字符")

# ---------- 4. 封面 ----------
cov = curl_json(f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={T}&type=image",
                extra=["-F", "media=@" + args.cover])
if "media_id" not in cov:
    print("[FAIL] 封面上传失败:", cov); sys.exit(1)
thumb = cov["media_id"]
print(f"[4] 封面 thumb_media_id: {thumb}")

# ---------- 5. draft/add 或 draft/update ----------
article = {
    "title": args.title,
    "author": args.author,
    "digest": DIGEST,
    "content": content,
    "thumb_media_id": thumb,
    "content_source_url": args.source_url,
    "need_open_comment": 1,
    "only_fans_can_comment": 0,
}
if args.update_media_id:
    # 就地增量更新：不删旧稿、不新增草稿（2026-09-14 立规，优先 update）
    payload = {"media_id": args.update_media_id, "index": 0, "articles": article}
    open("/tmp/wx_draft_payload.json", "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/draft/update?access_token={T}",
                  extra=["--data-binary", "@/tmp/wx_draft_payload.json",
                         "-H", "Content-Type: application/json; charset=utf-8"])
    if r.get("errcode") == 0:
        print(f"[5] 草稿就地更新成功! draft media_id: {args.update_media_id}")
        print(">>> 请在公众号后台「内容与互动-草稿箱」确认排版与图片、摘要")
    else:
        print("[FAIL] draft/update 失败:", r)
        sys.exit(1)
else:
    payload = {"articles": [article]}
    open("/tmp/wx_draft_payload.json", "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={T}",
                  extra=["--data-binary", "@/tmp/wx_draft_payload.json",
                         "-H", "Content-Type: application/json; charset=utf-8"])
    if "media_id" in r:
        print(f"[5] 草稿推送成功! draft media_id: {r['media_id']}")
        print(">>> 请在公众号后台「内容与互动-草稿箱」查看确认排版与图片、摘要")
    else:
        print("[FAIL] draft/add 失败:", r)
        sys.exit(1)
