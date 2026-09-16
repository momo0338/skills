#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_draft.py —— 微信公众号「草稿箱」全能力 CLI

覆盖官方草稿管理全部接口：
  list           /cgi-bin/draft/batchget    获取草稿列表
  count          /cgi-bin/draft/count       获取草稿总数
  get            /cgi-bin/draft/get         获取草稿详情（自动落备份）
  add            /cgi-bin/draft/add         新增草稿（图文 news / 图片消息 newspic）
  update         /cgi-bin/draft/update      更新草稿（默认字段级合并，保护手改）
  delete         /cgi-bin/draft/delete      删除草稿（默认 dry-run，删前强制备份）
  switch         /cgi-bin/draft/switch      草稿箱开关（官方已废弃，保留只读探测）
  product-card   /channels/ec/service/product/getcardinfo  商品卡片 DOM/product_key
  backup         —— 拉档存档（不调写接口）
  diff           —— 平台版 vs 本地版一致性对比（标签/style/纯文本三重校验）
  restore        —— 从备份文件回写草稿

三条安全护栏（对应 SKILL.md 记录的历史事故）：
  1) 删除不可逆：`delete` 默认只演练，必须 --yes 才真删，且删前自动备份
  2) 回写丢手改：`update` 默认「拉平台版 → 只改你指定的字段 → 回写」，不整篇覆盖
  3) 微信清空 style：回写前自动把真实 style 属性内的 HTML 实体解码为裸字符

用法示例：
  python3 wx_draft.py count
  python3 wx_draft.py list --count 20
  python3 wx_draft.py get --media-id M9xxx --save-html
  python3 wx_draft.py update --media-id M9xxx --thumb-media-id NEW_THUMB
  python3 wx_draft.py update --media-id M9xxx --digest "新的SEO摘要"
  python3 wx_draft.py delete --media-id M9xxx            # 演练，不删
  python3 wx_draft.py delete --media-id M9xxx --yes      # 真删（先自动备份）
  python3 wx_draft.py diff --media-id M9xxx --vs 待发布/xxx-排版.html
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    WxApiError, api_call, die, dump_json, load_wx_creds, get_token,
)

BACKUP_DIR = os.path.expanduser("~/.cache/weixin/draft_backups")
MAX_CONTENT_CHARS = 20000   # 官方口径；实测 26843 字符可通过，超限只告警不阻断
MAX_TITLE_CHARS = 32
MAX_AUTHOR_CHARS = 16
MAX_DIGEST_CHARS = 120


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def ccount(s):
    """微信按「字数」计：非空白字符数（中英混排均按 1 计）。"""
    return sum(1 for c in unicodedata.normalize("NFC", s or "") if not c.isspace())


def decode_style_entities(html):
    """把真实 style="..." 属性内的 HTML 实体解码回裸字符。

    微信会把作者写在 style 里的 &#39; 视为非法并整段清空 style（退化成 style=""）。
    draft/get 读回的内容里，微信自己会把裸 ' 规范化成 &#39;，原样回写即触发清空。
    """
    def _f(m):
        v = m.group(1)
        for a, b in (("&#39;", "'"), ("&#34;", '"'), ("&quot;", '"'), ("&amp;", "&")):
            v = v.replace(a, b)
        return 'style="' + v + '"'
    return re.sub(r'style="([^"]*)"', _f, html)


def validate_article(a):
    """推送前参数校验：把微信的限制在本地先拦一遍，避免白跑一次网络往返。"""
    problems, warns = [], []
    if not a.get("title"):
        problems.append("title 必填（≤32 字）")
    elif ccount(a["title"]) > MAX_TITLE_CHARS:
        problems.append(f"title {ccount(a['title'])} 字 > {MAX_TITLE_CHARS} 字上限")
    if a.get("author") and ccount(a["author"]) > MAX_AUTHOR_CHARS:
        problems.append(f"author {ccount(a['author'])} 字 > {MAX_AUTHOR_CHARS} 字上限")
    if a.get("digest") and ccount(a["digest"]) > MAX_DIGEST_CHARS:
        problems.append(f"digest {ccount(a['digest'])} 字 > {MAX_DIGEST_CHARS} 字上限")
    if a.get("article_type", "news") == "news":
        if not a.get("content"):
            problems.append("content 必填（图文消息）")
        if not a.get("thumb_media_id"):
            problems.append("thumb_media_id 必填（article_type=news 时）")
    c = a.get("content") or ""
    if ccount(c) > MAX_CONTENT_CHARS:
        warns.append(f"content {ccount(c)} 字 > 官方口径 {MAX_CONTENT_CHARS} 字（实测 26843 字可过，请留意）")
    if len(c.encode("utf-8")) > 1024 * 1024:
        problems.append("content 超过 1MB")
    if 'style=""' in c:
        problems.append('content 存在空 style 属性（style=""），微信会丢样式，请先修 HTML')
    if "<div" in c:
        warns.append("content 含 <div>（微信会溶解 div 并丢样式），块级容器请改 <section>")
    if re.search(r"<a\s+[^>]*href", c):
        warns.append("content 含 <a href>（微信会剥掉链接），外链请走 content_source_url")
    if re.search(r"position\s*:\s*(relative|absolute|fixed|sticky)", c):
        warns.append("content 含 position 定位（微信静默剥离），请改 flex")
    for w in warns:
        print(f"  [WARN] {w}")
    if problems:
        die("  [FAIL] 参数校验未通过：\n    - " + "\n    - ".join(problems))
    return True


def backup_draft(media_id, news, save_html=False, tag="backup"):
    """把平台当前版本完整存档。任何写操作前都应先跑这个。"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(BACKUP_DIR, f"{tag}_{media_id}_{ts}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    made = [base + ".json"]
    if save_html:
        for i, it in enumerate(news):
            hp = f"{base}_idx{i}.html"
            with open(hp, "w", encoding="utf-8") as f:
                f.write(it.get("content", "") or "")
            made.append(hp)
    print(f"[backup] 平台版已存档 -> {base}.(json{'+html' if save_html else ''})")
    return base


def fetch_draft(media_id):
    r = api_call("/cgi-bin/draft/get", {"media_id": media_id})
    items = r.get("news_item") or []
    if not items:
        die(f"[FAIL] draft/get 未返回 news_item（media_id={media_id}）")
    return items


def text_of(html):
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html or ""))


# --------------------------------------------------------------------------- #
# 子命令实现
# --------------------------------------------------------------------------- #
def cmd_count(args):
    r = api_call("/cgi-bin/draft/count")
    print(f"[count] 草稿总数: {r.get('total_count')}")
    dump_json(r, args.json)
    return r


def cmd_list(args):
    payload = {"offset": args.offset, "count": args.count,
               "no_content": 0 if args.with_content else 1}
    r = api_call("/cgi-bin/draft/batchget", payload)
    print(f"[list] 共 {r.get('total_count')} 篇草稿，本次返回 {r.get('item_count')} 篇"
          f"（offset={args.offset}, count={args.count}）")
    print(f"{'#':<3} {'更新时间':<20} {'media_id':<52} 标题")
    print("-" * 120)
    for i, it in enumerate(r.get("item") or [], start=args.offset):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(it.get("update_time", 0)))
        news = (it.get("content") or {}).get("news_item") or [{}]
        title = news[0].get("title", "")
        extra = ""
        if len(news) > 1:
            extra = f"  [多图文 x{len(news)}]"
        print(f"{i:<3} {ts:<20} {it.get('media_id',''):<52} {title}{extra}")
    dump_json(r, args.json)
    return r


def cmd_get(args):
    items = fetch_draft(args.media_id)
    for i, it in enumerate(items):
        print(f"--- news_item[{i}] ---")
        print(f"  title            : {it.get('title')}")
        print(f"  author           : {it.get('author')}")
        print(f"  digest({ccount(it.get('digest'))}字)     : {it.get('digest')}")
        print(f"  article_type     : {it.get('article_type', 'news')}")
        print(f"  content_source_url: {it.get('content_source_url')}")
        print(f"  thumb_media_id   : {it.get('thumb_media_id')}")
        print(f"  评论开关          : need_open_comment={it.get('need_open_comment')}, "
              f"only_fans_can_comment={it.get('only_fans_can_comment')}")
        c = it.get("content") or ""
        print(f"  content          : {ccount(c)} 字, img={c.count('<img')}, "
              f"section={c.count('<section')}, style={c.count('style=')}, "
              f"空style={c.count('style=\"\"')}, div={c.count('<div')}")
        print(f"  临时链接          : {it.get('url')}")
    backup_draft(args.media_id, items, save_html=True, tag="get")
    dump_json({"news_item": items}, args.json)
    return items


def cmd_backup(args):
    items = fetch_draft(args.media_id)
    backup_draft(args.media_id, items, save_html=True, tag="manual")
    return items


def cmd_add(args):
    if args.article_file:
        with open(args.article_file, encoding="utf-8") as f:
            art = json.load(f)
        art = art.get("articles", [art])[0] if isinstance(art, dict) else art[0]
    elif args.from_draft:
        art = fetch_draft(args.from_draft)[args.index]
        print(f"[add] 从草稿 {args.from_draft} 克隆第 {args.index} 篇作为新草稿")
    else:
        if not args.title:
            die("[FAIL] 新增草稿需要 --title（或 --article-file / --from-draft）")
        art = {
            "article_type": args.article_type,
            "title": args.title,
            "author": args.author,
            "digest": args.digest,
            "content": open(args.content_file, encoding="utf-8").read() if args.content_file else "",
            "content_source_url": args.source_url,
            "thumb_media_id": args.thumb_media_id,
            "need_open_comment": args.need_open_comment,
            "only_fans_can_comment": args.only_fans_can_comment,
        }
        if args.article_type == "newspic" and args.image_media_id:
            art["image_info"] = {"image_list": [{"image_media_id": m} for m in args.image_media_id]}
        if args.crop:
            art["cover_info"] = {"crop_percent_list": [parse_crop(x) for x in args.crop]}
        if args.product_key:
            art["product_info"] = {"footer_product_info": {"product_key": args.product_key}}

    art = {k: v for k, v in art.items() if v not in (None, "")}
    if art.get("content"):
        art["content"] = decode_style_entities(art["content"])
    validate_article(art)

    if args.dry_run:
        print("[dry-run] 将提交 draft/add 的 payload：")
        print(json.dumps({"articles": [art]}, ensure_ascii=False)[:2000])
        return None
    r = api_call("/cgi-bin/draft/add", {"articles": [art]})
    print(f"[add] 新增草稿成功！media_id = {r.get('media_id')}")
    print(">>> 请到公众号后台「内容与互动-草稿箱」确认排版/图片/摘要")
    dump_json(r, args.json)
    return r


def parse_crop(spec):
    """--crop "2.35_1=0.1945,0,1,0.5236" -> dict"""
    ratio, _, coords = spec.partition("=")
    xy = [c.strip() for c in coords.split(",")]
    if len(xy) != 4:
        die(f"[FAIL] --crop 格式应为 ratio=x1,y1,x2,y2，收到: {spec}")
    return {"ratio": ratio.strip(), "x1": xy[0], "y1": xy[1], "x2": xy[2], "y2": xy[3]}


def cmd_update(args):
    """默认「字段级合并」：拉平台版 -> 覆盖你显式指定的字段 -> 回写。"""
    items = fetch_draft(args.media_id)
    if args.index >= len(items):
        die(f"[FAIL] index={args.index} 超出范围（该草稿共 {len(items)} 篇）")
    base = json.loads(json.dumps(items[args.index]))   # 深拷贝平台版

    if args.article_file:
        if not args.replace_all:
            die("[FAIL] --article-file 会整篇覆盖，可能丢失用户后台手改。"
                "确认要整篇替换请再加 --replace-all")
        with open(args.article_file, encoding="utf-8") as f:
            new = json.load(f)
        new = new.get("articles", [new])[0] if isinstance(new, dict) else new[0]
        changed = sorted(new.keys())
        merged = new
    else:
        merged = dict(base)
        changed = []
        pairs = [
            ("title", args.title), ("author", args.author), ("digest", args.digest),
            ("thumb_media_id", args.thumb_media_id), ("content_source_url", args.source_url),
            ("article_type", args.article_type),
        ]
        for k, v in pairs:
            if v is not None and v != "":
                merged[k] = v
                changed.append(k)
        if args.content_file:
            merged["content"] = open(args.content_file, encoding="utf-8").read()
            changed.append("content")
        if args.need_open_comment is not None:
            merged["need_open_comment"] = args.need_open_comment
            changed.append("need_open_comment")
        if args.only_fans_can_comment is not None:
            merged["only_fans_can_comment"] = args.only_fans_can_comment
            changed.append("only_fans_can_comment")
        if args.crop:
            merged["cover_info"] = {"crop_percent_list": [parse_crop(x) for x in args.crop]}
            changed.append("cover_info")

    if not changed:
        die("[FAIL] 未指定任何要修改的字段。可用：--title/--digest/--content-file/--thumb-media-id/"
            "--source-url/--need-open-comment/--only-fans-can-comment/--crop")

    # 写前必备份（红线：动用户可能手改过的草稿前先拉档；放在字段校验之后，避免无效备份）
    if not args.no_backup:
        backup_draft(args.media_id, items, save_html=True, tag="pre-update")

    if merged.get("content"):
        merged["content"] = decode_style_entities(merged["content"])

    # 只对图文消息做严格校验（图片消息字段不同）
    if merged.get("article_type", "news") == "news":
        validate_article(merged)

    print(f"[update] 目标 media_id={args.media_id} index={args.index}")
    print(f"[update] 本次改动字段: {', '.join(changed)}")
    print(f"[update] 其余字段沿用平台当前版本（保护后台手改）")

    if args.dry_run:
        print("[dry-run] 未提交。将写回的字段预览：")
        for k in changed:
            v = merged.get(k)
            v = v if not isinstance(v, str) or len(v) <= 120 else v[:120] + "…"
            print(f"    {k} = {v}")
        return None

    payload = {"media_id": args.media_id, "index": args.index, "articles": merged}
    try:
        r = api_call("/cgi-bin/draft/update", payload)
    except WxApiError as e:
        print(f"[FAIL] draft/update 失败: {e}")
        if e.hint():
            print("    " + e.hint())
        die("")
    print(f"[update] 就地更新成功（errcode={r.get('errcode')}）")

    # 回读验收：确认 style 未被清空
    after = fetch_draft(args.media_id)[args.index]
    ac, bc = after.get("content") or "", base.get("content") or ""
    print("[verify] 回读对比（平台版更新前 -> 更新后）:")
    print(f"    style=      {bc.count('style=')} -> {ac.count('style=')}"
          f"   （应相等或按改动增加）")
    print(f"    空 style=   {bc.count('style=\"\"')} -> {ac.count('style=\"\"')}"
          f"   （必须为 0）")
    print(f"    纯文本一致  : {text_of(ac) == text_of(bc) if not args.content_file else '已改正文，跳过'}")
    if ac.count('style=""') > 0:
        print("    [WARN] 出现空 style，说明回写被微信清空了样式，请立即用备份回滚")
    backup_draft(args.media_id, [after], save_html=True, tag="post-update")
    dump_json(r, args.json)
    return r


def cmd_delete(args):
    """删除草稿。默认演练；真删前强制备份（删除不可恢复，微信无回收站）。"""
    items = fetch_draft(args.media_id)   # 顺便验证 media_id 有效
    titles = [it.get("title", "") for it in items]
    print(f"[delete] 目标 media_id = {args.media_id}")
    print(f"[delete] 含 {len(items)} 篇：{titles}")
    print("[delete] ⚠️ 微信官方：草稿删除后不可恢复、无回收站；用户在该草稿上的手工改动将一并丢失")

    if not args.yes:
        backup_draft(args.media_id, items, save_html=True, tag="dryrun")
        print("[delete] 当前为演练模式，未执行删除。确认无误后追加 --yes 真删。")
        return None

    backup_draft(args.media_id, items, save_html=True, tag="pre-delete")
    r = api_call("/cgi-bin/draft/delete", {"media_id": args.media_id})
    print(f"[delete] 已删除（errcode={r.get('errcode')}）；备份见上方路径，如需恢复用 restore")
    dump_json(r, args.json)
    return r


def cmd_restore(args):
    """从备份 JSON 回写：用于误删后重建（media_id 会变，原 ID 不可复活）。"""
    with open(args.backup, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("news_item", data if isinstance(data, list) else [data])
    art = items[args.index]
    art = {k: v for k, v in art.items() if k not in ("url",)}
    if art.get("content"):
        art["content"] = decode_style_entities(art["content"])
    if args.dry_run:
        print(f"[dry-run] 将从备份重建草稿: {art.get('title')}")
        return None
    if args.media_id:
        r = api_call("/cgi-bin/draft/update",
                     {"media_id": args.media_id, "index": args.index, "articles": art})
        print(f"[restore] 已回写到 {args.media_id}（errcode={r.get('errcode')}）")
    else:
        r = api_call("/cgi-bin/draft/add", {"articles": [art]})
        print(f"[restore] 已重建为新草稿 media_id = {r.get('media_id')}"
              f"（注意：与原 media_id 不同，原 ID 不可复活）")
    dump_json(r, args.json)
    return r


def cmd_diff(args):
    """平台版 vs 本地版一致性对比：定位「用户后台手改」或「本地变更」的差异。"""
    items = fetch_draft(args.media_id)
    it = items[args.index]
    platform = it.get("content") or ""
    local = open(args.vs, encoding="utf-8").read() if args.vs else ""

    def stat(h):
        return {
            "字符": ccount(h),
            "section": h.count("<section"),
            "div": h.count("<div"),
            "img": h.count("<img"),
            "table": h.count("<table"),
            "style=": h.count("style="),
            "空style": h.count('style=""'),
        }

    ps, ls = stat(platform), stat(local)
    print(f"{'指标':<12}{'平台版':>10}{'本地版':>10}   判定")
    print("-" * 48)
    for k in ps:
        same = ps[k] == ls[k]
        print(f"{k:<12}{ps[k]:>10}{ls[k]:>10}   {'一致' if same else '★不同'}")
    print("-" * 48)
    print(f"标题  平台={it.get('title')!r}")
    if local:
        m = re.search(r"<title>(.*?)</title>", local)
        if m:
            print(f"标题  本地={m.group(1).strip()!r}")
    tp, tl = text_of(platform), text_of(local)
    print(f"纯文本平台 {len(tp)} 字 / 本地 {len(tl)} 字 -> "
          f"{'完全一致（未改字）' if tp == tl else '★文本不一致（有改字或改结构）'}")
    if tp != tl and local:
        for i, (a, b) in enumerate(zip(tp, tl)):
            if a != b:
                print(f"    首个差异在第 {i} 字：平台 …{tp[max(0,i-25):i+25]}… / 本地 …{tl[max(0,i-25):i+25]}…")
                break
    if ps["空style"] or ls["空style"]:
        print("[WARN] 存在空 style 属性，样式会被微信清空，需修复")
    return {"platform": ps, "local": ls, "text_same": tp == tl}


def cmd_switch(args):
    r = api_call("/cgi-bin/draft/switch" + ("&checkonly=1" if args.check_only else ""),
                 check=False)
    print("[switch] 官方说明：该接口已废弃，草稿箱与发布功能已全量开放，无需再设置开关")
    print(f"[switch] 返回: {r}")
    return r


def cmd_product_card(args):
    r = api_call("/channels/ec/service/product/getcardinfo", {
        "product_id": args.product_id,
        "article_type": args.article_type,
        "card_type": args.card_type,
    }, check=False, method="POST")
    print(f"[product-card] errcode={r.get('errcode')} errmsg={r.get('errmsg')}")
    if r.get("product_key"):
        print(f"  product_key = {r['product_key']}   （图片消息/部分类型用它插入卡片）")
    if r.get("DOM"):
        print(f"  DOM 长度 = {len(r['DOM'])}   （图文消息把该 DOM 贴进 content 即插入卡片）")
        if args.save_dom:
            with open(args.save_dom, "w", encoding="utf-8") as f:
                f.write(r["DOM"])
            print(f"  DOM 已写入 {args.save_dom}")
    dump_json(r, args.json)
    return r


def cmd_selftest(args):
    print("=" * 64)
    print("草稿模块能力自检")
    print("=" * 64)
    try:
        load_wx_creds()
    except SystemExit:
        return
    for name, path, payload in [
        ("draft/count", "/cgi-bin/draft/count", None),
        ("draft/batchget", "/cgi-bin/draft/batchget", {"offset": 0, "count": 1, "no_content": 1}),
    ]:
        try:
            r = api_call(path, payload)
            if name == "draft/count":
                print(f"  ✓ {name:<18} 可用（草稿总数 {r.get('total_count')}）")
            else:
                print(f"  ✓ {name:<18} 可用（总数 {r.get('total_count')}）")
        except WxApiError as e:
            print(f"  ✗ {name:<18} {e.errcode} {e.errmsg}")
            if e.hint():
                print(f"      {e.hint()}")
    try:
        r = api_call("/channels/ec/service/product/getcardinfo",
                     {"product_id": "0", "article_type": "news", "card_type": 0}, check=False)
        ok = r.get("errcode") in (0, 10170001)   # 10170001=商品ID不合法 => 接口本身有权限
        print(f"  {'✓' if ok else '✗'} product-card        "
              f"{'可用（仅商品ID无效，说明接口已授权）' if ok else str(r.get('errcode')) + ' ' + str(r.get('errmsg'))}")
    except WxApiError as e:
        print(f"  ✗ product-card        {e.errcode} {e.errmsg}")
    return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser():

    # --json/--csv 用 parents 让每个子命令都能就近书写（例如 list --count 3 --json out.json）
    # default=SUPPRESS 保证「只写在顶层」或「只写在子命令」两种写法都不会被对方的默认值覆盖。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", default=argparse.SUPPRESS,
                        help="把原始返回写入该 JSON 文件；用 - 打印到标准输出")

    p = argparse.ArgumentParser(
        prog="wx_draft.py",
        description="微信公众号草稿箱全能力 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog=__doc__.split("用法示例：")[-1],
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("count", help="获取草稿总数", parents=[common])
    s.set_defaults(func=cmd_count)

    s = sub.add_parser("list", help="获取草稿列表（batchget）", parents=[common])
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--count", type=int, default=20, help="1~20，默认 20")
    s.add_argument("--with-content", action="store_true", help="返回 content 字段（体积大）")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", help="获取草稿详情并自动备份", parents=[common])
    s.add_argument("--media-id", required=True)
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("backup", help="仅拉档存档，不调写接口", parents=[common])
    s.add_argument("--media-id", required=True)
    s.set_defaults(func=cmd_backup)

    s = sub.add_parser("add", help="新增草稿", parents=[common])
    s.add_argument("--article-file", default="", help="完整 articles 对象 JSON（优先级最高）")
    s.add_argument("--from-draft", default="", help="克隆指定草稿为新草稿")
    s.add_argument("--index", type=int, default=0)
    s.add_argument("--article-type", default="news", choices=["news", "newspic"])
    s.add_argument("--title", default="")
    s.add_argument("--author", default="满爸爱生活")
    s.add_argument("--digest", default="", help="≤120 字；不填微信默认抓正文前 54 字")
    s.add_argument("--content-file", default="", help="正文 HTML 文件")
    s.add_argument("--thumb-media-id", default="", help="封面永久素材 ID")
    s.add_argument("--source-url", default="", help="原文链接（阅读原文跳转）")
    s.add_argument("--need-open-comment", type=int, default=1, choices=[0, 1])
    s.add_argument("--only-fans-can-comment", type=int, default=0, choices=[0, 1])
    s.add_argument("--image-media-id", action="append", default=[],
                   help="图片消息(newspic)的图片永久素材 ID，可重复")
    s.add_argument("--crop", action="append", default=[],
                   help='封面裁剪： "2.35_1=0.1945,0,1,0.5236"，可重复')
    s.add_argument("--product-key", default="", help="文末插入商品")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("update", help="更新草稿（默认字段级合并，保护后台手改）", parents=[common])
    s.add_argument("--media-id", required=True)
    s.add_argument("--index", type=int, default=0)
    s.add_argument("--title", default="")
    s.add_argument("--author", default="")
    s.add_argument("--digest", default="")
    s.add_argument("--content-file", default="")
    s.add_argument("--thumb-media-id", default="")
    s.add_argument("--source-url", default="")
    s.add_argument("--article-type", default="")
    s.add_argument("--need-open-comment", type=int, choices=[0, 1])
    s.add_argument("--only-fans-can-comment", type=int, choices=[0, 1])
    s.add_argument("--crop", action="append", default=[])
    s.add_argument("--article-file", default="", help="整篇替换（需同时 --replace-all）")
    s.add_argument("--replace-all", action="store_true", help="确认整篇覆盖")
    s.add_argument("--no-backup", action="store_true", help="跳过写前备份（不推荐）")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("delete", help="删除草稿（默认演练，--yes 才真删）", parents=[common])
    s.add_argument("--media-id", required=True)
    s.add_argument("--yes", action="store_true", help="确认真删（不可恢复）")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("restore", help="从备份 JSON 回写草稿", parents=[common])
    s.add_argument("--backup", required=True, help="备份 JSON 路径")
    s.add_argument("--media-id", default="", help="给了则回写到该草稿，否则新建")
    s.add_argument("--index", type=int, default=0)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_restore)

    s = sub.add_parser("diff", help="平台版 vs 本地 HTML 一致性对比", parents=[common])
    s.add_argument("--media-id", required=True)
    s.add_argument("--index", type=int, default=0)
    s.add_argument("--vs", default="", help="本地 HTML 路径；不给则只报平台版指标")
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("switch", help="草稿箱开关（官方已废弃）", parents=[common])
    s.add_argument("--check-only", action="store_true")
    s.set_defaults(func=cmd_switch)

    s = sub.add_parser("product-card", help="获取商品卡片 DOM/product_key", parents=[common])
    s.add_argument("--product-id", required=True)
    s.add_argument("--article-type", default="news", choices=["news", "newspic"])
    s.add_argument("--card-type", type=int, default=2, help="0大卡 1小卡 2文字链接 3条卡")
    s.add_argument("--save-dom", default="", help="把返回的 DOM 写入该文件")
    s.set_defaults(func=cmd_product_card)

    s = sub.add_parser("selftest", help="草稿模块能力自检", parents=[common])
    s.set_defaults(func=cmd_selftest)
    return p


def main():
    p = build_parser()
    args = p.parse_args()
    # parents 里用了 SUPPRESS，未指定时属性不存在，这里统一补默认值
    for _k, _dv in (("json", ""), ("csv", "")):
        if not hasattr(args, _k):
            setattr(args, _k, _dv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return
    try:
        args.func(args)
    except WxApiError as e:
        print(f"[FAIL] 接口报错 {e.errcode}: {e.errmsg}  ({e.path})")
        if e.hint():
            print("    " + e.hint())
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
