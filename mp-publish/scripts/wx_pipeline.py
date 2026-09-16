
import os, sys, re, json, time, argparse, unicodedata, subprocess
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    active_profile, get_token as _common_get_token, load_wx_author, load_wx_creds,
    set_profile,
)

MAX_DIGEST = 120

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PREP_SCRIPT = os.path.join(SCRIPT_DIR, "wx_prep_content.py")
CHECK_SCRIPT = os.path.join(SCRIPT_DIR, "wx_dialect_check.py")
PUSH_SCRIPT = os.path.join(SCRIPT_DIR, "wx_push_draft.py")

# 凭据在多账号解析之后才落地（见 main() 里的 set_profile），故先占位
APPID, SECRET = "", ""


def log(tag, msg):
    print(f"[{tag}] {msg}")

def get_token():
    return _common_get_token(APPID, SECRET)


def _post_json(path, payload, token, timeout=20):
    """POST JSON 到微信接口，返回解析后的 dict（网络/解析异常返回 {'errcode': -1, ...}）。"""
    clean_env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
    url = f"https://api.weixin.qq.com{path}?access_token={token}"
    r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-X", "POST", url,
                        "--data-binary", json.dumps(payload, ensure_ascii=False),
                        "-H", "Content-Type: application/json; charset=utf-8"],
                       env=clean_env, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"errcode": -1, "errmsg": f"非 JSON 响应: {(r.stdout or r.stderr)[:200]}"}

def find_existing_draft(token, title):
    if not token or not title:
        return None, None
    clean_env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
    url = f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={token}"
    req = subprocess.run(["curl", "-s", "--max-time", "15", "-X", "POST", url, "-H", "Content-Type: application/json",
                          "-d", json.dumps({"offset": 0, "count": 20, "no_content": 1})],
                         env=clean_env, capture_output=True, text=True)
    try:
        data = json.loads(req.stdout)
        if data.get("errcode"):
            log("WARN", f"draft/batchget 报错 {data.get('errcode')} {data.get('errmsg')[:60]}"
                        f"（token 失效时请重跑，或直接指定 --update-media-id）")
            return None, None
        clean_title = re.sub(r'[^\w\u4e00-\u9fa5]', '', title)
        for item in data.get("item", []):
            m_id = item.get("media_id")
            news = item.get("content", {}).get("news_item", [{}])[0]
            existing_title = news.get("title", "")
            clean_existing = re.sub(r'[^\w\u4e00-\u9fa5]', '', existing_title)
            if clean_title and clean_existing:
                if clean_title == clean_existing or clean_title in clean_existing or clean_existing in clean_title:
                    return m_id, existing_title
    except Exception as e:
        log("WARN", f"查询已有草稿列表异常: {e}")
    return None, None

def crop_to_cover(src_path, out_path):
    im = Image.open(src_path)
    w, h = im.size
    target_w, target_h = 900, 383
    scale = max(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    cropped = im_resized.crop((left, top, left + target_w, top + target_h))
    cropped.save(out_path, quality=95)
    log("COVER", f"封面居中裁剪完成: {src_path} ({w}x{h}) -> {out_path} ({target_w}x{target_h})")

def extract_meta_from_files(html_path):
    title, digest, cover = "", "", ""
    try:
        html_content = open(html_path, "r", encoding="utf-8").read()
        m_t = re.search(r"<title>(.*?)</title>", html_content)
        if m_t:
            title = m_t.group(1).strip()
    except Exception:
        pass

    dir_name = os.path.dirname(html_path)
    base_name = os.path.basename(html_path).replace("-排版.html", "").replace(".html", "")
    possible_mds = [
        os.path.join(dir_name, base_name + ".md"),
        os.path.join(dir_name, base_name.replace("-发布版", "") + ".md")
    ]
    for md_p in possible_mds:
        if os.path.exists(md_p):
            try:
                md_text = open(md_p, "r", encoding="utf-8").read()
                if not title:
                    m_title = re.search(r"^title:\s*(.*)$", md_text, re.M)
                    if m_title:
                        title = m_title.group(1).strip()
                m_digest = re.search(r"> \*\*SEO 摘要\*\*[^\n]*\n>\s*([^\n]+)", md_text)
                if m_digest:
                    digest = m_digest.group(1).strip()
                break
            except Exception:
                pass

    possible_covers = [
        os.path.join(dir_name, base_name + "-封面.jpg"),
        os.path.join(dir_name, base_name + "-封面.png"),
        os.path.join(dir_name, base_name.split("-")[0] + "-封面.jpg"),
        os.path.join(dir_name, "南京大学鼓楼校区-明城墙砖砌的百年钟楼-封面.jpg")
    ]
    for c_p in possible_covers:
        if os.path.exists(c_p):
            cover = c_p
            break

    return title, digest, cover

def main():
    parser = argparse.ArgumentParser(description="公众号文章一键自动化流水线 (Single-Call)")
    parser.add_argument("--html", required=True, help="源排版 HTML 文件路径")
    parser.add_argument("--profile", default="",
                        help="公众号账号别名（见 wx_account.py list）；缺省走 WX_PROFILE 或默认账号")
    parser.add_argument("--title", default="", help="文章标题（默认从 HTML/MD 自动提取）")
    parser.add_argument("--digest", default="", help="SEO 摘要（默认从同级 MD 自动提取）")
    parser.add_argument("--cover", default="", help="指定封面原图路径（默认自动匹配同级 *-封面.jpg）")
    parser.add_argument("--author", default="", help="作者名称（缺省取该账号 profiles.json 的 author）")
    parser.add_argument("--update-media-id", default="", help="指定就地更新的历史草稿 media_id")
    parser.add_argument("--update-auto", action="store_true", help="自动检测草稿箱同名/同主题草稿并执行就地更新")
    parser.add_argument("--source-url", default="", help="原文/官网/招聘站链接，写入草稿 content_source_url（发文后底部『阅读原文』跳转）")
    parser.add_argument("--delete-old-media-id", default="", help="需要清理的历史废弃草稿 media_id")
    args = parser.parse_args()

    # —— 账号选择必须早于任何凭据/token 读取；set_profile 会把 WX_PROFILE 写回环境变量，
    #    下面 spawn 的 wx_prep_content / wx_dialect_check / wx_push_draft 子进程自动继承同一账号。
    #    只有显式传了 --profile 才覆盖，未传时保留环境变量 WX_PROFILE 的语义。
    if args.profile:
        set_profile(args.profile)
    global APPID, SECRET
    APPID, SECRET = load_wx_creds(quiet=True)
    final_author = args.author or load_wx_author("满爸爱生活")

    html_path = os.path.abspath(args.html)
    if not os.path.exists(html_path):
        print(f"❌ 错误: HTML 文件不存在: {html_path}")
        sys.exit(1)

    auto_title, auto_digest, auto_cover = extract_meta_from_files(html_path)
    final_title = args.title or auto_title
    final_digest = args.digest or auto_digest
    final_cover = args.cover or auto_cover

    if not final_title:
        print("❌ 错误: 未能提取到文章标题，请通过 --title 显式指定")
        sys.exit(1)

    # 中间产物按账号隔离，避免并发时封面/正文串号（默认 /tmp，此处显式指定）
    os.environ["WX_RUN_DIR"] = os.path.join("/tmp", f"wxrun_{active_profile() or 'default'}")
    os.makedirs(os.environ["WX_RUN_DIR"], exist_ok=True)

    print("=" * 60)
    print("🚀 启动微信公众号图文一键发布与验收流水线 (Single-Call)")
    print(f"📌 目标账号: {active_profile() or '(默认/遗留)'}  AppID={APPID[:6]}****{APPID[-4:]}")
    print(f"📌 目标文件: {os.path.basename(html_path)}")
    print(f"📌 文章标题: {final_title}")
    print(f"📌 作者名称: {final_author}")
    if final_digest:
        print(f"📌 SEO 摘要: {final_digest[:60]}... ({len(final_digest)}字)")
    if final_cover:
        print(f"📌 匹配封面: {os.path.basename(final_cover)}")
    print("=" * 60)

    log("STEP 1", "执行 HTML 预处理 (wx_prep_content.py)...")
    res = subprocess.run([sys.executable, PREP_SCRIPT, html_path], capture_output=True, text=True)
    if res.returncode != 0:
        print("❌ 预处理失败:", res.stderr or res.stdout)
        sys.exit(1)
    print(res.stdout.strip())

    cover_file = os.path.join(os.environ["WX_RUN_DIR"], "zj_cover.jpg")
    if final_cover and os.path.exists(final_cover):
        crop_to_cover(final_cover, cover_file)
    else:
        log("WARN", "未指定专用封面，使用 prep 默认提取的封面图")

    log("STEP 2", "执行微信排版原生方言合规校验 (wx_dialect_check.py)...")
    content_file = os.path.join(os.environ["WX_RUN_DIR"], "zj_wechat_content.html")
    res = subprocess.run([sys.executable, CHECK_SCRIPT, content_file], capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print("❌ 微信方言校验未通过，已紧急终止推送！请按提示修复 HTML 结构后再试。")
        sys.exit(1)

    target_update_id = args.update_media_id
    token = get_token()
    if not target_update_id and args.update_auto and token:
        log("DISCOVER", "正在检测草稿箱是否存在同名已有草稿...")
        found_id, found_title = find_existing_draft(token, final_title)
        if found_id:
            target_update_id = found_id
            log("DISCOVER", f"匹配到已有草稿: media_id={found_id} (原标题: {found_title})，将自动就地增量更新！")

    log("STEP 3", f"执行推送 (wx_push_draft.py, 账号={active_profile() or 'default'})...")
    push_cmd = [
        sys.executable, PUSH_SCRIPT,
        "--profile", active_profile(),
        "--title", final_title,
        "--author", final_author,
        "--digest", final_digest,
        "--content-file", content_file,
        "--imgmap", os.path.join(os.environ["WX_RUN_DIR"], "zj_imgmap.json"),
        "--cover", cover_file
    ]
    if target_update_id:
        push_cmd.extend(["--update-media-id", target_update_id])
    if args.source_url:
        push_cmd.extend(["--source-url", args.source_url])

    res = subprocess.run(push_cmd, capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print("❌ 推送失败:", res.stderr)
        sys.exit(1)

    resolved_media_id = target_update_id
    if not resolved_media_id:
        m = re.search(r"draft media_id:\s*([A-Za-z0-9_-]+)", res.stdout)
        if m:
            resolved_media_id = m.group(1)

    log("STEP 4", f"执行服务端全量回读验收 (draft/get: {resolved_media_id})...")
    if not resolved_media_id:
        print("❌ 未能从推送输出解析出 draft media_id，无法回读验收")
        sys.exit(1)
    # ⚠️ 必须重新取 token：STEP 3 的子进程可能因 40001 刷新过 token，父进程手里的旧 token 已作废，
    #    直接用旧 token 回读会拿到空结果，进而「假通过」。
    verify_ok = False
    for _attempt in range(2):
        token = get_token()
        if not token:
            break
        ret_data = _post_json("/cgi-bin/draft/get", {"media_id": resolved_media_id}, token)
        if ret_data.get("errcode") in (40001, 40014, 42001):
            print(f"[retry] 回读 token 失效（{ret_data.get('errcode')}），强制刷新后重试…")
            continue
        if ret_data.get("errcode"):
            print(f"❌ draft/get 报错 {ret_data.get('errcode')} {ret_data.get('errmsg')}")
            break
        items = ret_data.get("news_item") or []
        if not items:
            print("❌ draft/get 未返回 news_item —— 无法确认内容已入库")
            break
        news = items[0]
        content = news.get("content", "") or ""
        img_count = content.count("<img")
        section_count = content.count("<section")
        empty_styles = content.count('style=""')
        div_count = content.count("<div")
        log("VERIFY", f"微信服务端确认: 标题='{news.get('title')}', 作者='{news.get('author')}', "
                      f"正文={len(content)}字符, 图片={img_count}张, 容器={section_count}个, 空样式={empty_styles}")
        # —— 硬性验收：任何一项不达标都判失败，绝不假通过 ——
        problems = []
        if len(content) < 200:
            problems.append(f"正文仅 {len(content)} 字符，明显未入库")
        if section_count == 0:
            problems.append("正文无 <section> 容器")
        if empty_styles > 0:
            problems.append(f"{empty_styles} 处空 style（推送会丢样式）")
        if div_count > 0:
            problems.append(f"{div_count} 处残留 <div>（微信会溶解样式）")
        if problems:
            print("❌ draft/get 质量验收未通过：")
            for p in problems:
                print(f"    · {p}")
            sys.exit(1)
        log("VERIFY", f"✅ draft/get 质量验收通过（标题/正文/容器/样式四项硬校验）")
        verify_ok = True
        break
    if not verify_ok:
        print("❌ 服务端回读验收失败，草稿是否可用需人工到后台确认")
        sys.exit(1)

    if args.delete_old_media_id:
        log("STEP 5", f"清理指定的历史旧草稿 ({args.delete_old_media_id})...")
        del_res = _post_json("/cgi-bin/draft/delete", {"media_id": args.delete_old_media_id}, token)
        log("CLEAN", f"旧草稿删除结果: {del_res}")

    print("=" * 60)
    print(f"🎉 全流程一键发布与验收完成！目标账号: {active_profile() or '(默认)'}")
    print(">>> 请在公众号后台「内容与互动-草稿箱」确认排版、封面与摘要后手动群发。")
    print("=" * 60)

if __name__ == "__main__":
    main()

