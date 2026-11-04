#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""job_poster_pipeline.py — 微信公众号招聘长图稿一键流水线（2026-10-14 固化，依据 10-13 七篇实测定型打法）

把 AI 的人工介入压缩到唯一一步：读图 → 填 facts.json。其余全部零 token 脚本。

子命令：
  fetch <url> [--dir DIR]     抓文→meta→下图→切段→形态判断（产出 work/meta.json + segs/）
  preflight <关键词>          db drafts/articles 查重（true=已写过）
  facts-check <facts.json>    必填字段/长度/溯源断言（机检）
  gen <facts.json>            组版 HTML（layout_kit；断言 section 配平/CTA 唯一/表头纯文本）
  cover <img> [--top A --bottom B --out O]  裁长图顶部做封面（默认 0~460→900x383）
  push <facts.json>           wx_pipeline --profile mashang（digest/title 取自 facts，推送前自动 facts-check）
  postprocess <facts.json>    对账同步＋当日日志追加

典型 AI 使用序列（每篇）：
  fetch → preflight → （AI 读 segs/ 填 facts.json）→ facts-check → gen → cover → push → postprocess
纪律：source-url 永指官方；中介转载号三步核源（mmbiz 比对/搜官方原文/网申连通）后才可写；
     截止时间原文没有＝"公告未披露"严禁推演；--profile mashang 固化。
"""
import argparse, json, os, re, sys, subprocess, html as H
from datetime import date

CWD = os.path.abspath(os.getcwd())
UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42'
UA_PC = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

def find_skill_file(skill_name, rel_path):
    """跨环境动态查找系统技能文件：优先同级技能库 -> ~/.workbuddy/skills -> ~/src/skills"""
    parent_skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cands = [
        os.path.join(parent_skills_dir, skill_name, rel_path),
        os.path.expanduser(f'~/.workbuddy/skills/{skill_name}/{rel_path}'),
        os.path.expanduser(f'~/src/skills/{skill_name}/{rel_path}')
    ]
    for c in cands:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None

# ─────────────────────────── fetch ───────────────────────────

# 发布号 biz 识别与合规过滤
# BLOCKED_BIZ：中介引流/营销拉黑号，命中即拦截、不取稿（严控源头质量，中介号不当源）
# REFERENCE_BIZ：高校就业转发等二次转载号，命中时提醒回官方号锚定真源
import base64 as _b64
def _biz_id(biz):
    try: return _b64.b64decode(biz + '==').decode()
    except Exception: return biz
BLOCKED_BIZ = {
    'MzkxMTU4OTY2Ng==': '求职汇（中介引流号：带水印+过期群码+个人导流码，正文无官方硬信息，不当源）',
}
REFERENCE_BIZ = {
    'MzkzNDU4MjU4Mw==': '东林就业招聘简讯平台（高校就业转发号，不当源，须回企业自有官方号锚定真源）',
    'MjM5MTE5MTY4Mw==': '中国人民大学就业创业指导中心「岗位速递」（高校就业转发号，不当源，须回企业自有官方号锚定真源）',
}
def _biz_of(url):
    m = re.search(r'[?&]__biz=([^&#]+)', url or '')
    return m.group(1) if m else None

def cmd_fetch(args):
    url, out = args.url, args.dir
    os.makedirs(out, exist_ok=True)

    # 优先复用通用底层能力：mp-save 技能中的自适应下载与切图引擎
    mp_dl_script = find_skill_file('mp-save', 'scripts/mp_download.py')
    if mp_dl_script:
        mp_script_dir = os.path.dirname(mp_dl_script)
        if mp_script_dir not in sys.path:
            sys.path.insert(0, mp_script_dir)
        try:
            from mp_download import MpArticleDownloader
            print(f"[fetch] 🚀 调度底层通用引擎: {mp_dl_script}")
            downloader = MpArticleDownloader(url=url, out_dir=out, mode='auto')
            downloader.run()
            meta = downloader.meta
            print(f"[fetch] form={meta.get('form')} imgs={len(meta.get('images', []))} segs={len(meta.get('segs', []))}")
            print(f"[fetch] title: {meta.get('title_official') or meta.get('title')}")
            print(f"[fetch] publisher: {meta.get('publisher')} | publish: {meta.get('publish_time')} | source_url_field: {meta.get('source_url_field')}")
            print(f"[fetch] AI 下一步：读 images/ 与 images/segs/ 切片，提取硬信息后填 facts.json")
            print(f"[fetch] facts 模板字段见: {os.path.abspath(__file__)} --facts-help")
            return
        except Exception as e:
            print(f"[fetch] ⚠️ 底层引擎调用异常 ({e})，回退到内置备用抓取流程...")

    biz = _biz_of(url)
    if biz in BLOCKED_BIZ:
        sys.exit(f"[BLOCKED] biz={biz}（{_biz_id(biz)}）命中拉黑号「{BLOCKED_BIZ[biz]}」\n"
                 f"  依据源头质量合规要求（中介号不当源），终止流水线。\n"
                 f"  如需解除，请在 job-poster-write 技能的 BLOCKED_BIZ 中调整配置。")
    if biz in REFERENCE_BIZ:
        print(f"[NOTICE] biz={biz}（{_biz_id(biz)}）为「{REFERENCE_BIZ[biz]}」\n"
              f"  该号为二次转载号，后续须回企业自有官方号取干净原图。本 fetch 仍取图，但请注意核源。")
    os.makedirs(out, exist_ok=True)
    htmlp = os.path.join(out, 'article.html')
    r = sh(f'curl -sL "{url}" -A "{UA_IPHONE}" --max-time 25 -o "{htmlp}"')
    s = open(htmlp, encoding='utf-8', errors='ignore').read()
    if len(s) < 10000:
        sys.exit(f'[FATAL] 页面过小({len(s)}B)，可能被拦：{url}')
    meta = {}
    m = re.search(r'<meta property="og:title" content="([^"]*)"', s)
    meta['title_official'] = H.unescape(m.group(1)) if m else None
    m = re.search(r"var createTime = '([^']*)'", s)
    meta['publish_time'] = m.group(1) if m else None
    m = re.search(r'var nickname = "([^"]*)"', s)
    meta['publisher'] = (m.group(1) if m and m.group(1) else '').strip() or None
    m = re.search(r'var msg_source_url = .([^;\']*)', s)
    meta['source_url_field'] = m.group(1) if m else None
    meta['url'] = url

    i = s.find('id="js_content"')
    if i < 0:
        sys.exit('[FATAL] 找不到 js_content（可能是转载被删/需登录）')
    body = s[i:]
    j = body.find('rich_media_area_extra')
    if j > 0:
        body = body[:j]
    n_img = len(re.findall(r'<img', body))
    # 全面提取图片URL：支持 <img> data-src、<svg>/标签的 background/background-image url(...)、以及 xlink:href
    # 2026-10-16 朱总反馈中国华电排版漏图排查出：华电将多张海报及岗位表嵌在 <svg style="background: url(...)"> 中
    found_urls = []
    for m in re.finditer(r'data-src=["\']([^"\']+)["\']', body):
        found_urls.append((m.start(), m.group(1).replace('&amp;', '&').replace('\\x26amp;', '&')))
    for m in re.finditer(r'url\(\\?["\']?(https?://(?:mmbiz|mmecoa)\.qpic\.cn/[^\s"\'<>)\\]+)\\?["\']?\)', body):
        found_urls.append((m.start(), m.group(1).replace('&amp;', '&').replace('\\x26amp;', '&')))
    for m in re.finditer(r'(?:xlink:)?href=["\'](https?://(?:mmbiz|mmecoa)\.qpic\.cn/[^"\']+)["\']', body):
        found_urls.append((m.start(), m.group(1).replace('&amp;', '&').replace('\\x26amp;', '&')))
    found_urls.sort(key=lambda x: x[0])
    seen_urls = set()
    urls = []
    for pos, u in found_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            urls.append(u)
    meta['n_img_tags'] = n_img
    meta['n_data_src'] = len(urls)

    # 文本形态判断
    t = re.sub(r'<script.*?</script>', '', body, flags=re.S)
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<br\s*/?>', '\n', t)
    t = re.sub(r'</(p|section|div|li|h\d|td|tr)>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = H.unescape(t)
    lines = [l.strip() for l in t.split('\n') if l.strip() and l.strip() != 'id="js_content"']
    meta['text_lines'] = len(lines)
    open(os.path.join(out, 'text.txt'), 'w').write('\n'.join(lines))

    # 下载内容图（跳过 gif 装饰与视频模板页）
    content = []
    for n, u in enumerate(urls):
        if 'readtemplate' in u or 'mpvideo' in u:
            continue  # 视频型文章：视频占位不下载
        p = os.path.join(out, f'img{n}.png')
        sh(f'curl -sL "{u}" -A "{UA_IPHONE}" -e "https://mp.weixin.qq.com/" -o "{p}"')
        try:
            from PIL import Image
            im = Image.open(p)
            kind = 'gif' if getattr(im, 'is_animated', False) or u.endswith(('gif', 'webp')) and 'wx_fmt=gif' in u else 'img'
        except Exception as e:
            sys.exit(f'[FATAL] 图{n} 损坏: {e}')
        if kind == 'gif':
            os.remove(p); continue
        w, hgt = im.size
        if w >= 900 and hgt >= 3000:
            kind = 'long'
        content.append({'idx': n, 'url': u, 'path': p, 'size': [w, hgt], 'kind': kind})
    meta['images'] = content
    meta['form'] = ('text' if len(lines) > 30 else
                    'multi' if sum(1 for c in content if c['kind'] == 'img') > 3 else
                    'long' if any(c['kind'] == 'long' for c in content) else 'short')

    # 长图切段（2000px + 60 重叠）
    segs = []
    for c in content:
        if c['kind'] != 'long':
            continue
        from PIL import Image
        im = Image.open(c['path']).convert('RGB')
        W, Hh = im.size
        step = 2000
        k = 0
        while k * step < Hh:
            sp = os.path.join(out, f"seg{c['idx']}_{k}.png")
            im.crop((0, k * step, W, min(Hh, (k + 1) * step + 60))).save(sp)
            segs.append(sp); k += 1
    meta['segs'] = segs
    json.dump(meta, open(os.path.join(out, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
    print(f"[fetch] form={meta['form']} imgs={len(content)}(long={sum(1 for c in content if c['kind']=='long')}) "
          f"segs={len(segs)} text_lines={meta['text_lines']}")
    print(f"[fetch] title: {meta['title_official']}")
    print(f"[fetch] publisher: {meta['publisher']} | publish: {meta['publish_time']} | source_url_field: {meta['source_url_field']}")
    print(f"[fetch] AI 下一步：读 segs/*.png 与 img*.png（非 long 的按序直读），提取硬信息后填 facts.json")
    print(f"[fetch] facts 模板字段见: {os.path.abspath(__file__)} --facts-help")

# ─────────────────────────── preflight ───────────────────────────

def cmd_preflight(args):
    db_path = getattr(args, 'db', None) or os.environ.get('PIPELINE_DB')
    if not db_path or not os.path.exists(db_path):
        print(f"[preflight] ℹ️ 未指定或未找到有效数据库（--db 或 PIPELINE_DB），跳过本地数据库查重。")
        print(f"[preflight] 请调用方根据业务需要确认「{args.keyword}」是否已成稿或发布。")
        return
    import sqlite3
    k = f"%{args.keyword}%"
    con = sqlite3.connect(db_path)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    drafts = list(con.execute("SELECT id,title,status FROM drafts WHERE title LIKE ?", (k,))) if 'drafts' in tables else []
    articles = list(con.execute("SELECT id,published_title,publish_type FROM articles WHERE published_title LIKE ?", (k,))) if 'articles' in tables else []
    print("drafts:", drafts)
    print("articles:", articles)
    dup = bool(drafts or articles)
    if dup:
        print(f"[preflight] ⛔ 数据库已存在「{args.keyword}」相关草稿/文章——确认是否同公告，重复＝不写")
    else:
        print(f"[preflight] ✅ 未在数据库中查到「{args.keyword}」，可写")

# ─────────────────────────── facts-check ───────────────────────────

REQUIRED = ['source_url', 'publisher', 'company', 'line_dir', 'brand', 'deadline',
            'audience', 'positions', 'locations', 'apply', 'title', 'digest',
            'highlight_items', 'grid', 'body_imgs', 'raw_evidence']

def cmd_facts_check(args):
    f = json.load(open(args.facts))
    miss = [k for k in REQUIRED if k not in f or f[k] in (None, '', [])]
    # 单张长图稿：正文图由 stack_b64_imgs 承载，body_imgs 允许为空
    if 'body_imgs' in miss and f.get('stack_b64_imgs'):
        miss.remove('body_imgs')
    if miss:
        sys.exit(f'[FATAL] facts 缺必填字段: {miss}')
    assert len(f['title']) <= 64, f"title {len(f['title'])}>64"
    assert len(f['digest']) <= 120, f"digest {len(f['digest'])}>120"
    # 回源纪律：source_kind=official_account（官方系账号推文即原文，如国资小新）可作源；
    # 其余（聚合号/中介号/高校网转发）推文链接一律不当源，须改指官网公告页/官方投递平台
    if 'mp.weixin.qq.com' in f['source_url'] and f.get('source_kind') != 'official_account':
        sys.exit(f"[FATAL] source_url 违反回源纪律: {f['source_url']}\n"
                 f"  publisher={f.get('publisher')}——非官方系账号推文不当源，须回源至官网公告页/官方投递平台；\n"
                 f"  若确为官方系账号（如国资小新/母公司官号），在 facts.json 加 \"source_kind\": \"official_account\"")
    for it in f['highlight_items']:
        for bad in ['最高', '最多', '第一', '唯一', '正式编制', '直签', '落户', '食堂']:
            if bad in it and bad not in f['raw_evidence']:
                sys.exit(f"[FATAL] 划重点含敏感词「{bad}」且 raw_evidence 无出处：{it[:50]}")
    if f['deadline'] not in ('公告未披露',) and not re.search(r'20\d{2}', str(f['deadline'])):
        sys.exit(f"[FATAL] deadline 非常规格式（用 2026-11-13 或 '公告未披露'）：{f['deadline']}")
    print(f"[facts-check] ✅ 全部通过（title {len(f['title'])} / digest {len(f['digest'])} / 划重点 {len(f['highlight_items'])} 条）")

# ─────────────────────────── gen ───────────────────────────

def cmd_gen(args):
    kit_script = find_skill_file('mp-html', 'scripts/layout_kit.py')
    if kit_script:
        sys.path.insert(0, os.path.dirname(kit_script))
    else:
        sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
    from layout_kit import Layout
    f = json.load(open(args.facts))
    L = Layout(brand=f['brand'], brand_dark=f.get('brand_dark', f['brand']),
               bg_light=f.get('bg_light', '#f0f6fd'), border_light=f.get('border_light', '#d8e4f5'),
               faq_bg=f.get('faq_bg', '#f5f9fd'), faq_border=f.get('border_light', '#d8e4f5'))
    h = L.doc_open(f"<title>{f['title']}</title>")
    brand_label = f.get('account_brand') or f.get('account_name') or '码上职业'
    intro_prefix = f.get('intro', '')
    title_official = f.get('title_official', f.get('title', ''))
    intro = (intro_prefix + '依据：' + f.get('publisher', '') + ' ' + f.get('publish_date', '') + '《' +
             title_official + f'》原文，{brand_label}仅做排版整理，未改动原文表述。')
    h += L.highlight_card(sub=f['highlight_sub'], intro=intro,
                          items=f['highlight_items'], numbers=[f'{i}.' for i in range(1, len(f['highlight_items']) + 1)])
    h += L.quad_grid([tuple(g) for g in f['grid']])
    for sec in f.get('sections', []):
        h += L.sec_title(sec['title'])
        if sec.get('table'):
            t = sec['table']
            assert isinstance(t['headers'], list) and all(isinstance(x, str) for x in t['headers']), '表头必须纯文本列表'
            h += L.table(t['headers'], t['rows'], t['widths'])
        if sec.get('items'):
            h += L.ul(sec['items'], numbers=[f'{i}.' for i in range(1, len(sec['items']) + 1)] if sec.get('numbered', True) else None)
        if sec.get('paras'):
            for p in sec['paras']:
                h += L.note(p) if sec.get('as_note') else L.p(p)
    work = f['work_dir']
    meta = json.load(open(os.path.join(work, 'meta.json')))
    url_by_idx = {c['idx']: c['url'] for c in meta['images']}
    h += L.sec_title(f.get('original_title', '官方招聘海报原文'))
    h += L.note(f.get('original_note', '以下为官方发布原文，原样收录、未作改动；长图较长，可点击放大逐段查看。'))
    for n in f['body_imgs']:
        u = url_by_idx[n]
        h += ('<section style="text-align:center;margin:0 0 14px;">'
              f'<img src="{u}" style="max-width:100%;height:auto;border-radius:6px;" '
              f'alt="{f["company"]}官方海报{n}"/></section>')
    segs = f.get('stack_b64_imgs', [])
    if segs:
        # 长图切片拼合铁律：全部段落并入同一 section，段间 -1px 负 margin 抵消亚像素缝隙，
        # line-height:0;font-size:0;display:block 去行高，禁 border-radius（圆角会在接缝露底）
        h += '<section style="text-align:center;margin:0;">'
        for i, p in enumerate(segs):
            # 2026-10-20：按扩展名定 MIME。星空/实景类长图存 PNG 单张 3MB+（4 段 14MB），
            # 改存 JPEG q86 后 4 段共 1.9MB，微信图床单图更安全；.png 行为不变。
            _ext = os.path.splitext(p)[1].lower()
            _mime = 'image/jpeg' if _ext in ('.jpg', '.jpeg') else 'image/png'
            b = f'data:{_mime};base64,' + __import__('base64').b64encode(open(p, 'rb').read()).decode()
            mb = '0 auto -1px' if i < len(segs) - 1 else '0 auto'
            h += (f'<img src="{b}" style="display:block;margin:{mb};line-height:0;font-size:0;'
                  f'max-width:100%;height:auto;" alt="{f["company"]}官方海报切片{i + 1}"/>')
        h += '</section>'
    cta_html = L.cta()
    h += cta_html
    h += L.note(f['source_note'])
    h += ''.join(L.doc_close())
    full = h
    o, c = full.count('<section'), full.count('</section>')
    assert o == c, f'section 配平 {o}/{c}'
    assert cta_html in full and full.count(cta_html.strip()[:60]) == 1, 'CTA 组件重复或缺失'
    assert "('', '" not in full, '表头元组泄漏'
    target_dir = os.path.join(CWD, f['line_dir']) if not os.path.isabs(f['line_dir']) else f['line_dir']
    os.makedirs(target_dir, exist_ok=True)
    out = os.path.join(target_dir, f"{f['date_tag']}-{f['slug']}-长图转排版.html")
    open(out, 'w', encoding='utf-8').write(full)
    print(f"[gen] OK {out}\n[gen] section {o}/{c} | <strong> {full.count('<strong>')} | {round(len(full)/1048576,2)}MB")

# ─────────────────────────── cover ───────────────────────────

def cmd_cover(args):
    import glob
    from PIL import Image
    src = args.img
    slug = args.slug
    line_dir = args.line_dir
    date_tag = ''

    # 智能识别：支持直接传 facts.json，自动对齐 slug、line_dir 和首张源图，避免路径分裂
    if src.endswith('.json') and os.path.exists(src):
        try:
            f = json.load(open(src))
            slug = args.slug if args.slug != 'tmp' else f.get('slug', 'tmp')
            line_dir = args.line_dir if args.line_dir is not None else f.get('line_dir', '.')
            date_tag = f.get('date_tag', '')
            work_dir = f.get('work_dir', '')
            cands = []
            if f.get('stack_b64_imgs'):
                cands.extend(f['stack_b64_imgs'])
            if work_dir:
                cands.append(os.path.join(work_dir, 'images', 'img0.png'))
                cands.append(os.path.join(work_dir, 'images', 'img0.jpg'))
                cands.append(os.path.join(work_dir, 'images', 'img0.jpeg'))
                cands.append(os.path.join(work_dir, 'segs', 'seg_000.png'))
                cands.extend(glob.glob(os.path.join(work_dir, 'images', '*')))
            found_img = next((c for c in cands if os.path.exists(c)), None)
            if not found_img:
                sys.exit(f"[FATAL] 从 {src} 未能找到可裁剪的封面源图，请显式传图片路径（尝试过: {cands[:3]}）")
            src = found_img
            print(f"[cover] 💡 从 facts.json 自动提取: 源图={src}, slug={slug}, line_dir={line_dir}")
        except Exception as e:
            sys.exit(f"[FATAL] 解析 facts.json 出错: {e}")
    else:
        line_dir = line_dir or '.'

    im = Image.open(src).convert('RGB')
    crop = im.crop((0, args.top, im.width, args.bottom)).resize((900, 383), Image.LANCZOS)
    if args.out:
        out = args.out
    else:
        target_dir = os.path.join(CWD, line_dir) if not os.path.isabs(line_dir) else line_dir
        os.makedirs(target_dir, exist_ok=True)
        prefix = f"{date_tag}-" if date_tag else ""
        out = os.path.join(target_dir, f"{prefix}{slug}-长图转排版-封面.png")
    crop.save(out)
    print(f'[cover] OK {out} ({crop.size[0]}x{crop.size[1]} ← 源 {src} y{args.top}~{args.bottom})')

# ─────────────────────────── push ───────────────────────────

def cmd_push(args):
    f = json.load(open(args.facts))
    cmd_facts_check(args)
    target_dir = os.path.join(CWD, f['line_dir']) if not os.path.isabs(f['line_dir']) else f['line_dir']
    htmlp = os.path.join(target_dir, f"{f['date_tag']}-{f['slug']}-长图转排版.html")
    # 封面两种命名都认：cover 子命令存无 date_tag 前缀名，gen/先例也常用带前缀名
    cands = [os.path.join(target_dir, f"{f['date_tag']}-{f['slug']}-长图转排版-封面.png"),
             os.path.join(target_dir, f"{f['slug']}-长图转排版-封面.png")]
    coverp = next((c for c in cands if os.path.exists(c)), cands[0])
    assert os.path.exists(htmlp) and os.path.exists(coverp), f'先跑 gen + cover（试过: {cands}）'
    # 回源纪律（与 facts-check 同口径）：非官方系账号的推文链接不当源
    if 'mp.weixin.qq.com' in f['source_url'] and f.get('source_kind') != 'official_account':
        sys.exit(f"[FATAL] source_url 违反回源纪律: {f['source_url']}（publisher={f.get('publisher')}）")
    profile = getattr(args, 'profile', None) or f.get('profile', 'mashang')
    publish_script = find_skill_file('mp-publish', 'scripts/wx_pipeline.py') or os.path.expanduser('~/src/skills/mp-publish/scripts/wx_pipeline.py')
    cmd = (f"{sys.executable} '{publish_script}' --profile '{profile}' "
           f"--html '{htmlp}' --cover '{coverp}' --source-url '{f['source_url']}' "
           f"--digest '{f['digest']}'")
    r = subprocess.run(cmd, shell=True)
    sys.exit(r.returncode)

# ─────────────────────────── postprocess ───────────────────────────

def cmd_postprocess(args):
    f = json.load(open(args.facts))
    facts_dir = os.path.dirname(os.path.abspath(args.facts))

    summary = {
        'company': f['company'],
        'title': f['title'],
        'source_url': f['source_url'],
        'publisher': f.get('publisher', ''),
        'deadline': f['deadline'],
        'audience': f['audience'],
        'line_dir': f['line_dir'],
        'date_tag': f.get('date_tag', ''),
        'slug': f['slug'],
        'timestamp': date.today().isoformat()
    }

    summary_path = os.path.join(facts_dir, 'pipeline_summary.json')
    try:
        json.dump(summary, open(summary_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception:
        pass

    log_path = getattr(args, 'log', None)
    if log_path:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        line = (f"\n## {f['company']}（job-poster-write 流水线）\n"
                f"**源**：{f['source_url']}（{f.get('publisher','')}）｜**截止**：{f['deadline']}｜**对象**：{f['audience']}\n"
                f"**交付**：`{f['line_dir']}/{f.get('date_tag','')}-{f['slug']}-长图转排版-*.html/png`｜facts：`{os.path.abspath(args.facts)}`\n")
        open(log_path, 'a', encoding='utf-8').write(line)
        print(f"[postprocess] 日志已追加到: {log_path}")

    print("\n" + "="*50)
    print("🎉 [postprocess] 流水线执行完毕，交付概要：")
    print(f"  单位名称: {f['company']}")
    print(f"  成稿标题: {f['title']}")
    print(f"  官方源URL: {f['source_url']} ({f.get('publisher','')})")
    print(f"  报名截止: {f['deadline']}")
    print(f"  目标受众: {f['audience']}")
    print(f"  交付目录: {f['line_dir']}")
    print("="*50 + "\n")

# ─────────────────────────── main ───────────────────────────

FACTS_HELP = '''
facts.json 必填字段（AI 读图后填写的唯一交付物）：
  source_url      官方原文链接（中介转载号核源后指官方）
  publisher       发布方（如"国聘"/"中江国际人才招聘"）
  title_official  官方原标题      publish_date 发布日期
  company         单位简称（标题用）company_full 总称（可空）
  line_dir        落点目录（默认 事业单位/待发布）
  brand/brand_dark 品牌色（取长图众数色）  date_tag/slug  文件名两段
  deadline        "2026-11-13" 或 "公告未披露"（严禁推演）
  audience/positions/locations/apply  对象/岗位/地点/报名方式（一句话口径）
  title           成稿标题 ≤64 前21字带钩子    digest ≤120（四必含：截止/门槛/入口/差异）
  highlight_sub   划重点卡副题   highlight_items 4-5条（关键数字包<strong>）
  grid            三宫格 [[大字,小字]×3]
  sections        可选扩展节 [{title, table:{headers纯文本,rows,widths} | items, numbered}]
  body_imgs       原文收录图 idx 列表（fetch 产物 img{n}.url）
  stack_b64_imgs  可选，软内容拼图本地路径（base64 内嵌换图床）
  raw_evidence    图中原文关键句摘录（溯源比对用，机检查敏感词出处）
  source_note     尾部来源小字（含"码上职业仅做排版整理，未改动原文表述"）
'''

def main():
    if '--facts-help' in sys.argv:
        print(FACTS_HELP)
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('fetch'); p.add_argument('url'); p.add_argument('--dir', default='/tmp/wxwork'); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser('preflight'); p.add_argument('keyword'); p.add_argument('--db', default=None, help='可选：SQLite 数据库路径用于查重'); p.set_defaults(fn=cmd_preflight)
    p = sub.add_parser('facts-check'); p.add_argument('facts'); p.set_defaults(fn=cmd_facts_check)
    p = sub.add_parser('gen'); p.add_argument('facts'); p.set_defaults(fn=cmd_gen)
    p = sub.add_parser('cover', help='裁长图做封面（支持直接传 facts.json 自动提取配置与源图）')
    p.add_argument('img', help='长图文件路径 或 facts.json 路径')
    p.add_argument('--top', type=int, default=0)
    p.add_argument('--bottom', type=int, default=460)
    p.add_argument('--slug', default='tmp')
    p.add_argument('--line-dir', dest='line_dir', default=None, help='落点目录（默认当前目录 . 或自动取自 facts.json）')
    p.add_argument('--out', default=None)
    p.set_defaults(fn=cmd_cover)
    p = sub.add_parser('push'); p.add_argument('facts'); p.add_argument('--profile', default=None, help='公众号配置文件名（默认从 facts 读取或 fallback 到 mashang）'); p.set_defaults(fn=cmd_push)
    p = sub.add_parser('postprocess'); p.add_argument('facts'); p.add_argument('--log', default=None, help='可选：追加记录发布日志的文件路径'); p.set_defaults(fn=cmd_postprocess)
    ap.add_argument('--facts-help', action='store_true')
    args = ap.parse_args()
    args.fn(args)

if __name__ == '__main__':
    main()
