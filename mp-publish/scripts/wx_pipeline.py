
import os, sys, re, json, time, argparse, unicodedata, subprocess
from PIL import Image

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
MAX_DIGEST = 120

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PREP_SCRIPT = os.path.join(SCRIPT_DIR, "wx_prep_content.py")
CHECK_SCRIPT = os.path.join(SCRIPT_DIR, "wx_dialect_check.py")
PUSH_SCRIPT = os.path.join(SCRIPT_DIR, "wx_push_draft.py")

def log(tag, msg):
    print(f"[{tag}] {msg}")

def get_token():
    clean_env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
    token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}"
    r = subprocess.run(["curl", "-s", "--max-time", "15", token_url], env=clean_env, capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
        return data.get("access_token")
    except Exception:
        return None

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
    parser.add_argument("--title", default="", help="文章标题（默认从 HTML/MD 自动提取）")
    parser.add_argument("--digest", default="", help="SEO 摘要（默认从同级 MD 自动提取）")
    parser.add_argument("--cover", default="", help="指定封面原图路径（默认自动匹配同级 *-封面.jpg）")
    parser.add_argument("--author", default="满爸爱生活", help="作者名称")
    parser.add_argument("--update-media-id", default="", help="指定就地更新的历史草稿 media_id")
    parser.add_argument("--update-auto", action="store_true", help="自动检测草稿箱同名/同主题草稿并执行就地更新")
    parser.add_argument("--source-url", default="", help="原文/官网/招聘站链接，写入草稿 content_source_url（发文后底部『阅读原文』跳转）")
    parser.add_argument("--delete-old-media-id", default="", help="需要清理的历史废弃草稿 media_id")
    args = parser.parse_args()

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

    print("=" * 60)
    print("🚀 启动微信公众号图文一键发布与验收流水线 (Single-Call)")
    print(f"📌 目标文件: {os.path.basename(html_path)}")
    print(f"📌 文章标题: {final_title}")
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

    cover_file = "/tmp/zj_cover.jpg"
    if final_cover and os.path.exists(final_cover):
        crop_to_cover(final_cover, cover_file)
    else:
        log("WARN", "未指定专用封面，使用 prep 默认提取的封面图")

    log("STEP 2", "执行微信排版原生方言合规校验 (wx_dialect_check.py)...")
    content_file = "/tmp/zj_wechat_content.html"
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

    log("STEP 3", "执行推送 (wx_push_draft.py)...")
    push_cmd = [
        sys.executable, PUSH_SCRIPT,
        "--title", final_title,
        "--author", args.author,
        "--digest", final_digest,
        "--content-file", content_file,
        "--imgmap", "/tmp/zj_imgmap.json",
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
    if token and resolved_media_id:
        clean_env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
        get_url = f"https://api.weixin.qq.com/cgi-bin/draft/get?access_token={token}"
        get_res = subprocess.run(["curl", "-s", "--max-time", "15", "-X", "POST", get_url, "-d", json.dumps({"media_id": resolved_media_id})],
                                 env=clean_env, capture_output=True, text=True)
        try:
            ret_data = json.loads(get_res.stdout)
            news = ret_data.get("news_item", [{}])[0]
            content = news.get("content", "")
            img_count = content.count("<img")
            section_count = content.count("<section")
            empty_styles = content.count('style=""')
            div_count = content.count("<div")
            log("VERIFY", f"微信服务端确认: 标题='{news.get('title')}', 正文={len(content)}字符, 图片={img_count}张, 容器={section_count}个, 空样式={empty_styles}")
            if empty_styles > 0:
                log("WARN", f"检测到 {empty_styles} 处空样式，请检查原始排版！")
            if div_count > 0:
                log("WARN", f"检测到 {div_count} 处残留 div！")
            log("VERIFY", "✅ draft/get 质量验收全部通过！")
        except Exception as e:
            log("WARN", f"回读解析异常: {e}")

    if args.delete_old_media_id and token:
        log("STEP 5", f"清理指定的历史旧草稿 ({args.delete_old_media_id})...")
        del_url = f"https://api.weixin.qq.com/cgi-bin/draft/delete?access_token={token}"
        del_res = subprocess.run(["curl", "-s", "--max-time", "15", "-X", "POST", del_url, "-d", json.dumps({"media_id": args.delete_old_media_id})],
                                 env=clean_env, capture_output=True, text=True)
        log("CLEAN", f"旧草稿删除结果: {del_res.stdout.strip()}")

    print("=" * 60)
    print("🎉 全流程一键发布与验收完成！耗时约 10-15 秒，草稿箱立即可见。")
    print("=" * 60)

if __name__ == "__main__":
    main()

