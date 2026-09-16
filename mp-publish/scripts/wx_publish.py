#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_publish.py —— 微信公众号「发布能力」全能力 CLI

覆盖官方发布接口全部 5 个：
  submit      /cgi-bin/freepublish/submit        将草稿提交发布（异步，返回 publish_id）
  status      /cgi-bin/freepublish/get           查询发布任务状态（支持 --wait 轮询到终态）
  list        /cgi-bin/freepublish/batchget      获取已发布消息列表
  getarticle  /cgi-bin/freepublish/getarticle    获取已发布图文信息（含正文）
  delete      /cgi-bin/freepublish/delete        删除已发布文章（不可逆，默认演练）
  selftest    —— 权限与能力自检

⚠️ 权限现实（务必先读）：
  发布接口（freepublish/*）自 2025 年 7 月起，对「个人主体账号、企业主体未认证账号
  及不支持认证的账号」回收调用权限。本仓库主用的个人订阅号调用会返回 48001。
  遇到 48001 不是脚本问题，请改用后台网页路径（见 SKILL.md「已发布内容查询」章节）。

publish_status 取值（status 子命令会翻译成中文）：
  0 成功 / 1 发布中 / 2 原创失败 / 3 常规失败 / 4 平台审核不通过
  5 成功后用户删除所有文章 / 6 成功后系统封禁所有文章

用法示例：
  python3 wx_publish.py selftest
  python3 wx_publish.py submit --media-id M9xxx
  python3 wx_publish.py status --publish-id 100000001 --wait
  python3 wx_publish.py list --count 20 --search 遛娃
  python3 wx_publish.py getarticle --article-id ARTICLE_ID --save-html
  python3 wx_publish.py delete --article-id ARTICLE_ID            # 演练
  python3 wx_publish.py delete --article-id ARTICLE_ID --yes      # 真删（先备份）
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    WxApiError, api_call, die, dump_json, load_wx_creds,
    profile_data_dir, set_profile,
)

def backup_root():
    """发布稿备份目录（按账号隔离，避免跨号混放）。"""
    return os.path.join(profile_data_dir(), "publish_backups")


# 兼容旧引用：模块加载时按当前账号解析一次（脚本内所有写操作都先 set_profile）
BACKUP_DIR = backup_root()

PUBLISH_STATUS = {
    0: "成功",
    1: "发布中",
    2: "原创失败",
    3: "常规失败",
    4: "平台审核不通过",
    5: "成功后用户删除所有文章",
    6: "成功后系统封禁所有文章",
}

NO_PERMISSION_HELP = """
>>> 48001 = 当前账号未被授予 freepublish 接口权限。
    官方说明：2025 年 7 月起，个人主体账号、企业主体未认证账号及不支持认证的账号
    将被回收「发布能力」相关接口的调用权限。
    可行替代路径（无需接口权限）：
      1) 公众号后台「内容与互动 → 发表记录」查看/管理已发布文章
      2) 用 ego-browser 携带登录态访问后台（SKILL.md「已发布内容查询」小节有可用脚本）
      3) 草稿箱能力（draft/*）不受影响，可正常推草稿、后台手动群发
"""


# --------------------------------------------------------------------------- #
def cmd_submit(args):
    """提交草稿发布。注意：errcode=0 只代表「任务提交成功」，不代表已发布完成。"""
    r = api_call("/cgi-bin/freepublish/submit", {"media_id": args.media_id}, check=False)
    if r.get("errcode") == 48001:
        print("[FAIL] 提交发布失败：48001 api unauthorized")
        print(NO_PERMISSION_HELP)
        sys.exit(1)
    if r.get("errcode") != 0:
        print(f"[FAIL] 提交发布失败: {r.get('errcode')} {r.get('errmsg')}")
        sys.exit(1)
    pid = r.get("publish_id")
    print(f"[submit] 发布任务已提交 publish_id = {pid}")
    print("[submit] 注意：errcode=0 仅代表任务提交成功，发布可能异步完成，"
          "后续仍可能因原创声明失败/平台审核不通过而失败")
    print(f"[submit] 下一步: python3 wx_publish.py status --publish-id {pid} --wait")
    dump_json(r, args.json)
    return r


def cmd_status(args):
    """查询发布状态；--wait 时轮询到非「发布中」为止。"""
    deadline = time.time() + args.timeout
    last = None
    while True:
        r = api_call("/cgi-bin/freepublish/get", {"publish_id": args.publish_id}, check=False)
        if r.get("errcode") == 48001:
            print("[FAIL] 48001 api unauthorized")
            print(NO_PERMISSION_HELP)
            sys.exit(1)
        if r.get("errcode") not in (0, None):
            print(f"[FAIL] 查询失败: {r.get('errcode')} {r.get('errmsg')}")
            sys.exit(1)
        st = r.get("publish_status")
        last = r
        print(f"[status] publish_id={r.get('publish_id')} "
              f"publish_status={st}（{PUBLISH_STATUS.get(st, '未知')}）")
        if st == 0:
            ad = r.get("article_detail") or {}
            print(f"  成功发布 {ad.get('count')} 篇，article_id = {r.get('article_id')}")
            for it in ad.get("item") or []:
                print(f"    idx={it.get('idx')}  {it.get('article_url')}")
            break
        if st != 1:
            print(f"  失败文章编号 fail_idx = {r.get('fail_idx')}")
            print("  >>> 原创声明失败/审核不通过时，请到后台处理该篇内容后重新发布")
            break
        if not args.wait:
            break
        if time.time() > deadline:
            print(f"  [WARN] 等待超过 {args.timeout}s 仍处于「发布中」，稍后再查一次即可")
            break
        time.sleep(args.interval)
    dump_json(last, args.json)
    return last


def cmd_list(args):
    """获取已发布消息列表。"""
    payload = {"offset": args.offset, "count": args.count,
               "no_content": 0 if args.with_content else 1}
    r = api_call("/cgi-bin/freepublish/batchget", payload, check=False)
    if r.get("errcode") == 48001:
        print("[FAIL] 48001 api unauthorized —— 无法用接口枚举已发布文章")
        print(NO_PERMISSION_HELP)
        sys.exit(1)
    if r.get("errcode") not in (0, None):
        print(f"[FAIL] {r.get('errcode')} {r.get('errmsg')}")
        sys.exit(1)

    items = r.get("item") or []
    kw = (args.search or "").strip()
    print(f"[list] 已发布总数 {r.get('total_count')}，本次返回 {r.get('item_count')}"
          + (f"，关键词过滤后 {len([1 for i in items if kw in json.dumps(i, ensure_ascii=False)])} 篇" if kw else ""))
    print(f"{'#':<3} {'更新时间':<20} {'article_id':<46} 标题")
    print("-" * 120)
    for i, it in enumerate(items, start=args.offset):
        news = (it.get("content") or {}).get("news_item") or [{}]
        title = news[0].get("title", "")
        blob = json.dumps(it, ensure_ascii=False)
        if kw and kw not in blob:
            continue
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(it.get("update_time", 0)))
        mark = "  [已删除]" if news[0].get("is_deleted") else ""
        print(f"{i:<3} {ts:<20} {it.get('article_id',''):<46} {title}{mark}")
    dump_json(r, args.json)
    return r


def cmd_getarticle(args):
    """获取已发布图文信息（含正文 HTML）。"""
    r = api_call("/cgi-bin/freepublish/getarticle", {"article_id": args.article_id}, check=False)
    if r.get("errcode") == 48001:
        print("[FAIL] 48001 api unauthorized")
        print(NO_PERMISSION_HELP)
        sys.exit(1)
    if r.get("errcode") not in (0, None):
        print(f"[FAIL] {r.get('errcode')} {r.get('errmsg')}")
        sys.exit(1)
    for i, it in enumerate(r.get("news_item") or []):
        print(f"--- news_item[{i}] ---")
        for k in ("title", "author", "digest", "content_source_url",
                  "thumb_media_id", "thumb_url", "url", "is_deleted"):
            print(f"  {k:<19}: {it.get(k)}")
        print(f"  content            : {len(it.get('content') or '')} 字符")
    if args.save_html:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        for i, it in enumerate(r.get("news_item") or []):
            p = os.path.join(BACKUP_DIR, f"published_{args.article_id}_{ts}_idx{i}.html")
            with open(p, "w", encoding="utf-8") as f:
                f.write(it.get("content") or "")
            print(f"[save] 正文已存档 -> {p}")
    dump_json(r, args.json)
    return r


def cmd_delete(args):
    """删除已发布文章（不可逆）。默认演练；真删前自动备份正文。"""
    r = api_call("/cgi-bin/freepublish/getarticle", {"article_id": args.article_id}, check=False)
    if r.get("errcode") == 48001:
        print("[FAIL] 48001 api unauthorized")
        print(NO_PERMISSION_HELP)
        sys.exit(1)
    items = r.get("news_item") or []
    print(f"[delete] 目标 article_id = {args.article_id}")
    print(f"[delete] 共 {len(items)} 篇：{[it.get('title') for it in items]}")
    print(f"[delete] index={args.index}（不填或 0 = 删除全部文章）")
    print("[delete] ⚠️ 此操作不可逆，删除后读者将无法访问，且无法通过接口恢复")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(BACKUP_DIR, f"predelete_{args.article_id}_{ts}.json")
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"[delete] 已备份正文元数据 -> {bak}")

    if not args.yes:
        print("[delete] 当前为演练模式，未执行删除。确认无误后追加 --yes 真删。")
        return None
    payload = {"article_id": args.article_id}
    if args.index:
        payload["index"] = args.index
    rr = api_call("/cgi-bin/freepublish/delete", payload, check=False)
    if rr.get("errcode") == 0:
        print("[delete] 已删除")
    else:
        print(f"[FAIL] 删除失败: {rr.get('errcode')} {rr.get('errmsg')}")
    dump_json(rr, args.json)
    return rr


def cmd_selftest(args):
    print("=" * 64)
    print("发布模块能力自检（逐个探测 freepublish 接口权限）")
    print("=" * 64)
    load_wx_creds()
    probes = [
        ("freepublish/batchget", "/cgi-bin/freepublish/batchget",
         {"offset": 0, "count": 1, "no_content": 1}),
        # submit/get/delete 都会产生副作用或需要真实 ID，这里只用无副作用的 batchget 探测；
        # 权限是按「权限集 7」整体授予的，batchget 通过即代表整个发布模块可用。
    ]
    available = False
    for name, path, payload in probes:
        try:
            r = api_call(path, payload, check=False)
            if r.get("errcode") == 48001:
                print(f"  ✗ {name:<22} 48001 未授权")
            elif r.get("errcode") in (0, None):
                print(f"  ✓ {name:<22} 可用（已发布总数 {r.get('total_count')}）")
                available = True
            else:
                print(f"  ? {name:<22} {r.get('errcode')} {r.get('errmsg')}")
        except WxApiError as e:
            print(f"  ✗ {name:<22} {e.errcode} {e.errmsg}")
    print("-" * 64)
    if available:
        print("结论：发布接口可用 —— submit/status/getarticle/delete 均可正常调用。")
        print("      ⚠️ 但发布动作本身会推送给全部关注者，务必先确认草稿内容！")
    else:
        print("结论：发布接口不可用（本账号为个人订阅号，2025-07 起被回收该权限）。")
        print(NO_PERMISSION_HELP)
    return None


# --------------------------------------------------------------------------- #
def build_parser():

    # --json/--csv 用 parents 让每个子命令都能就近书写（例如 list --count 3 --json out.json）
    # default=SUPPRESS 保证「只写在顶层」或「只写在子命令」两种写法都不会被对方的默认值覆盖。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", default=argparse.SUPPRESS,
                        help="把原始返回写入该 JSON 文件；用 - 打印到标准输出")
    # 多账号：--profile <alias> 优先于环境变量 WX_PROFILE 与 profiles.json 的 default。
    # default=SUPPRESS 同样避免子命令层级互相覆盖。
    common.add_argument("--profile", default=argparse.SUPPRESS,
                        help="指定公众号账号别名（见 wx_account.py list）；缺省走 WX_PROFILE 或默认账号")

    p = argparse.ArgumentParser(
        prog="wx_publish.py",
        description="微信公众号发布能力全能力 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog=__doc__.split("用法示例：")[-1],
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("submit", help="将草稿提交发布", parents=[common])
    s.add_argument("--media-id", required=True, help="草稿 media_id")
    s.set_defaults(func=cmd_submit)

    s = sub.add_parser("status", help="查询发布任务状态", parents=[common])
    s.add_argument("--publish-id", required=True)
    s.add_argument("--wait", action="store_true", help="轮询直到非「发布中」")
    s.add_argument("--interval", type=int, default=5, help="轮询间隔秒，默认 5")
    s.add_argument("--timeout", type=int, default=120, help="最长等待秒，默认 120")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("list", help="获取已发布消息列表", parents=[common])
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--count", type=int, default=20, help="1~20")
    s.add_argument("--with-content", action="store_true")
    s.add_argument("--search", default="", help="按关键词本地过滤标题/正文")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("getarticle", help="获取已发布图文信息（含正文）", parents=[common])
    s.add_argument("--article-id", required=True)
    s.add_argument("--save-html", action="store_true", help="把正文 HTML 存档")
    s.set_defaults(func=cmd_getarticle)

    s = sub.add_parser("delete", help="删除已发布文章（默认演练）", parents=[common])
    s.add_argument("--article-id", required=True)
    s.add_argument("--index", type=int, default=0,
                   help="多图文中的第几篇（第一篇为 1）；0/不填 = 全部删除")
    s.add_argument("--yes", action="store_true", help="确认真删（不可逆）")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("selftest", help="发布模块能力自检", parents=[common])
    s.set_defaults(func=cmd_selftest)
    return p


def main():
    p = build_parser()
    args = p.parse_args()
    # parents 里用了 SUPPRESS，未指定时属性不存在，这里统一补默认值
    for _k, _dv in (("json", ""), ("csv", ""), ("profile", "")):
        if not hasattr(args, _k):
            setattr(args, _k, _dv)
    # 账号选择必须在任何凭据/token 读取之前生效（并写回环境变量，子进程继承）。
    # ⚠️ 只有显式传了 --profile 才覆盖；未传时保留环境变量 WX_PROFILE 的语义，
    #    否则 set_profile("") 会把 WX_PROFILE 清掉，导致 shell 层切换失效。
    _profile_arg = getattr(args, "profile", "") or ""
    if _profile_arg:
        set_profile(_profile_arg)
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
