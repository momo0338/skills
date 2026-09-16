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
import json, os, re, subprocess, sys, argparse, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    active_profile, get_token, load_wx_author, load_wx_creds, run_dir, set_profile,
)

MAX_DIGEST = 120  # 微信摘要上限（字符）

ap = argparse.ArgumentParser()
ap.add_argument("--profile", default="",
                help="公众号账号别名（见 wx_account.py list）；缺省走 WX_PROFILE 或默认账号")
ap.add_argument("--title", required=True)
ap.add_argument("--author", default="", help="作者名；缺省取该账号 profiles.json 的 author")
ap.add_argument("--digest", default="", help="SEO 摘要，≤%d 字符；为空则自动生成" % MAX_DIGEST)
ap.add_argument("--content-file", default="", help="缺省 $WX_RUN_DIR/zj_wechat_content.html")
ap.add_argument("--imgmap", default="", help="缺省 $WX_RUN_DIR/zj_imgmap.json")
ap.add_argument("--cover", default="", help="缺省 $WX_RUN_DIR/zj_cover.jpg")
ap.add_argument("--source-url", default="", help="原文链接/活动页地址，正文禁<a>时靠它外链")
ap.add_argument("--update-media-id", default="",
                help="就地更新已有草稿（draft/update，不新增草稿）；留空则新建（draft/add）")
args = ap.parse_args()

# 账号选择必须早于任何凭据读取；只有显式传了 --profile 才覆盖 WX_PROFILE 的语义。
if args.profile:
    set_profile(args.profile)
APPID, SECRET = load_wx_creds(quiet=True)
args.author = args.author or load_wx_author("满爸爱生活")

RUN_DIR = run_dir()
args.content_file = args.content_file or os.path.join(RUN_DIR, "zj_wechat_content.html")
args.imgmap = args.imgmap or os.path.join(RUN_DIR, "zj_imgmap.json")
args.cover = args.cover or os.path.join(RUN_DIR, "zj_cover.jpg")
print(f"[cred] 目标账号 profile={active_profile() or '(默认)'} AppID={APPID[:6]}****{APPID[-4:]}")

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

TOKEN_ERRCODES = (40001, 40014, 42001)

def wx_api(path, extra=None, tries=2):
    """带 token 自愈的请求：path 支持自带 query（如 '...add_material?type=image'）。

    40001/40014/42001 均为「token 失效」——常见于稳定 token 被其它系统顶掉，或本机
    磁盘缓存过期。此时强制刷新 token 重试一次；其它错误原样返回交调用方判断。
    本脚本的 uploadimg / add_material / draft.* 三处全走这里，避免某一处漏掉自愈。
    """
    global T
    last = {}
    for i in range(max(1, tries)):
        sep = "&" if "?" in path else "?"
        last = curl_json(f"https://api.weixin.qq.com{path}{sep}access_token={T}", extra=extra)
        if last.get("errcode") in TOKEN_ERRCODES and i < tries - 1:
            print(f"[retry] {last.get('errcode')} token 失效，强制刷新后重试…")
            T = get_token(APPID, SECRET, force_refresh=True)
            continue
        return last
    return last

# 草稿写操作的 payload 落盘路径：**必须与 curl 实际读取的路径是同一个变量**。
# 2026-09-16 踩坑记录：曾出现「payload 写到按账号隔离的新路径、curl 仍读硬编码 /tmp 旧路径」，
# 结果把上一个账号残留的 payload 发出去 → 40007 invalid media_id（封面 media_id 属于另一个号）。
# 多账号下这种串稿是静默的，必须靠单一变量消除。
PAYLOAD_FILE = os.path.join(RUN_DIR, "wx_draft_payload.json")
DRAFT_RETRY_ERRCODES = (40007, -1)   # 40007 亦可能是「素材刚上传未同步」，重试一次成本极低

def draft_write(action, payload, tries=3, delay=2.5, done=""):
    """提交 draft/add 或 draft/update：落盘 -> 发送 -> 校验 -> 失败重试。

    action: "add" | "update"
    """
    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    last = {}
    for i in range(tries):
        last = wx_api(f"/cgi-bin/draft/{action}",
                      extra=["--data-binary", "@" + PAYLOAD_FILE,
                             "-H", "Content-Type: application/json; charset=utf-8"])
        ok = ("media_id" in last) if action == "add" else (last.get("errcode") == 0)
        if ok:
            if action == "add":
                print(f"[5] 草稿推送成功! draft media_id: {last['media_id']}")
            else:
                print(f"[5] {done}")
            print(">>> 请在公众号后台「内容与互动-草稿箱」查看确认排版与图片、摘要")
            return last
        if last.get("errcode") in DRAFT_RETRY_ERRCODES and i < tries - 1:
            wait = delay * (i + 1)
            print(f"[retry] draft/{action} 返回 {last.get('errcode')} {last.get('errmsg','')[:60]}"
                  f" —— {wait:.1f}s 后重试 ({i+1}/{tries-1})")
            time.sleep(wait)
            continue
        break
    print(f"[FAIL] draft/{action} 失败:", last)
    # 40007 的高频真因是 thumb_media_id 缺失或不属于本账号，直接把线索打出来
    if last.get("errcode") == 40007:
        print(">>> 40007 排查顺序：① 本账号 thumb_media_id 是否为空（草稿必须有封面素材）；")
        print("    ② 该媒体素材是否属于当前账号（跨账号 media_id 一律无效）；")
        print("    ③ 素材刚 add_material 上传、尚未同步 —— 等几秒重试即可。")
        print(f"    本次发送的 thumb_media_id: {payload.get('articles',[{}])[0].get('thumb_media_id','(空)')}")
        print(f"    实际发送的 payload 文件: {PAYLOAD_FILE}")
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

# ---------- 1. access_token（走 wx_common：stable_token 优先 + 按 appid 磁盘缓存） ----------
try:
    T = get_token(APPID, SECRET)
except Exception as _e:  # WxApiError 等
    print("[FAIL] 获取 token 失败:", _e)
    sys.exit(1)
if not T:
    print("[FAIL] 获取 token 失败（返回空）")
    sys.exit(1)
print("[1] access_token 获取成功")

# ---------- 2. 上传正文图片 ----------
imgmap = json.load(open(args.imgmap))
urls = {}
for im in imgmap:
    r = wx_api("/cgi-bin/media/uploadimg", extra=["-F", "media=@" + im["path"]])
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
cov = wx_api("/cgi-bin/material/add_material?type=image",
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
    r = draft_write("update", payload,
                    done=f"草稿就地更新成功! draft media_id: {args.update_media_id}")
else:
    payload = {"articles": [article]}
    r = draft_write("add", payload)
