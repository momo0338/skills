#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_account.py —— 微信公众号多账号（profile）管理 CLI

一个 AppID/AppSecret 对应一个公众号。多账号通过 profile 别名切换，全部脚本
（wx_draft.py / wx_publish.py / wx_stats.py / wx_pipeline.py / wx_push_draft.py）
统一遵循同一套解析规则：

    命令行 --profile <alias>  >  环境变量 WX_PROFILE  >  profiles.json 的 default
    >  遗留 ~/.config/weixin/appid|appsecret

磁盘约定：
    ~/.config/weixin/
      appid / appsecret          遗留默认账号（保持向后兼容，不动）
      profiles.json              {"default": alias, "profiles": {alias: {name, appid, author}}}
      profiles/<alias>/appsecret 各账号密钥独立落盘（chmod 600），不写进 profiles.json

用法示例：
  python3 wx_account.py list                          # 列出所有账号
  python3 wx_account.py add mashang --name "码上职业" \\
      --appid wxfc6d3cbb4dec7cd2 --author "码上职业"    # 新增账号（交互式输入密钥）
  python3 wx_account.py add mashang --name "码上职业" --appid xxx --secret yyy
  python3 wx_account.py use mashang                   # 设为默认账号
  python3 wx_account.py check                         # 探测某账号的接口权限矩阵
  python3 wx_account.py check mashang
  python3 wx_account.py env mashang                   # 打印 export 语句，供 shell source
  python3 wx_account.py rm mashang                    # 移除账号（默认保留密钥文件，加 --purge 一并删）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    CRED_DIR, PROFILES_FILE, API_BASE, WxApiError, active_profile, api_call, die,
    fetch_token, list_profiles, profile_cache_dir, read_profiles_meta,
    resolve_creds, _profile_dir, write_profiles_meta,
)


def mask(s):
    """AppID 打码：保留前 6 后 4，便于人工核对又不会整串外泄。"""
    if not s:
        return "-"
    return s if len(s) <= 12 else f"{s[:6]}****{s[-4:]}"


# --------------------------------------------------------------------------- #
# list
# --------------------------------------------------------------------------- #
def cmd_list(args):
    registered = (read_profiles_meta().get("profiles") or {})
    default = read_profiles_meta().get("default", "")
    rows = []

    if registered:
        for alias, e in registered.items():
            rows.append((alias, e.get("name", ""), e.get("appid", ""), e.get("author", ""),
                         "注册", "★ 默认" if alias == default else ""))
    # 遗留账号：只有当 profiles.json 里没有指向它的别名时才单列
    legacy_appid, legacy_secret, _ = resolve_creds("default")
    if legacy_appid and not any((e.get("appid") == legacy_appid) for e in registered.values()):
        rows.append(("default", "遗留默认账号", legacy_appid, "", "遗留",
                     "★ 默认" if not default or default == "default" else ""))

    if not rows:
        print("尚未登记任何账号。用 `wx_account.py add <alias> --name ... --appid ...` 新增。")
        return

    w = [max(len(str(r[i])) for r in rows + [("alias", "名称", "AppID", "作者", "来源", "状态")])
         for i in range(6)]
    fmt = "  ".join(f"{{:<{x}}}" for x in w)
    print(fmt.format("alias", "名称", "AppID", "作者", "来源", "状态"))
    print("-" * (sum(w) + 12))
    for r in rows:
        print(fmt.format(r[0], r[1], mask(r[2]), r[3] or "-", r[4], r[5]))
    print()
    print(f"配置目录: {CRED_DIR}")
    resolved = active_profile() or "(遗留 default)"
    src_env = f"WX_PROFILE={os.environ['WX_PROFILE']}" if os.environ.get("WX_PROFILE") else "未设 WX_PROFILE"
    print(f"当前生效 profile: {resolved}   （{src_env}；profiles.json default={default or '-'}）")
    print()
    print("切换方式（任选其一）:")
    print("  · 单次命令行 :  <脚本> ... --profile mashang")
    print("  · 整个 shell :  export WX_PROFILE=mashang   （之后所有脚本默认走它）")
    print("  · 改默认账号 :  wx_account.py use mashang")


# --------------------------------------------------------------------------- #
# add
# --------------------------------------------------------------------------- #
def cmd_add(args):
    alias = args.alias.strip()
    if not alias or "/" in alias or alias.startswith("."):
        die("❌ alias 不合法：不能为空、不能含 '/'、不能以 '.' 开头")
    if alias == "default":
        die("❌ alias 不能用 'default'（该名保留给遗留凭据）")

    appid = args.appid.strip()
    if not appid:
        die("❌ 必须提供 --appid")

    secret = (args.secret or "").strip()
    if not secret:
        if not sys.stdin.isatty():
            die("❌ 未提供 --secret 且当前非交互终端：请加 --secret，"
                "或改走 `add` 后手动写 ~/.config/weixin/profiles/%s/appsecret" % alias)
        import getpass
        secret = getpass.getpass(f"请输入 {alias} ({args.name or appid}) 的 AppSecret: ").strip()
    if not secret:
        die("❌ AppSecret 为空，已中止")

    meta = read_profiles_meta()
    profiles = meta.setdefault("profiles", {})
    existed = alias in profiles

    prof_dir = _profile_dir(alias)
    os.makedirs(prof_dir, exist_ok=True)
    sec_path = os.path.join(prof_dir, "appsecret")
    with open(sec_path, "w", encoding="utf-8") as f:
        f.write(secret)
    os.chmod(sec_path, 0o600)
    # appid 也留一份在账号目录，便于 profile 目录自带自解释性
    with open(os.path.join(prof_dir, "appid"), "w", encoding="utf-8") as f:
        f.write(appid)
    os.chmod(os.path.join(prof_dir, "appid"), 0o600)

    profiles[alias] = {
        "name": args.name or alias,
        "appid": appid,
        "author": args.author or (profiles.get(alias, {}) or {}).get("author", "") or args.name or "",
    }
    if args.set_default or not meta.get("default"):
        meta["default"] = alias
    write_profiles_meta(meta)

    print(f"{'已更新' if existed else '已新增'}账号: {alias}")
    print(f"  名称   : {profiles[alias]['name']}")
    print(f"  AppID  : {mask(appid)}")
    print(f"  作者   : {profiles[alias]['author'] or '-'}")
    print(f"  密钥   : {sec_path} (chmod 600)")
    print(f"  默认   : {'是' if meta.get('default') == alias else '否（default=' + str(meta.get('default')) + '）'}")
    print()
    print(f">>> 自检: python3 {os.path.basename(__file__)} check {alias}")


# --------------------------------------------------------------------------- #
# use / rm / env
# --------------------------------------------------------------------------- #
def cmd_use(args):
    meta = read_profiles_meta()
    alias = args.alias.strip()
    known = set((meta.get("profiles") or {}).keys())
    if alias and alias != "default" and alias not in known:
        die(f"❌ 未登记账号 '{alias}'。已登记: {', '.join(sorted(known)) or '（无）'}")
    if alias == "default":
        meta.pop("default", None)
        write_profiles_meta(meta)
        print("已清除默认 profile → 回落遗留 ~/.config/weixin/appid|appsecret")
        return
    meta["default"] = alias
    write_profiles_meta(meta)
    print(f"默认账号已设为: {alias}")
    print(">>> 注意：此设置只影响「未显式指定 --profile / WX_PROFILE」时的解析结果。")


def cmd_rm(args):
    meta = read_profiles_meta()
    alias = args.alias.strip()
    profiles = meta.get("profiles") or {}
    if alias not in profiles:
        die(f"❌ 未登记账号 '{alias}'")
    was_default = meta.get("default") == alias
    profiles.pop(alias)
    if was_default:
        meta.pop("default", None)
    write_profiles_meta(meta)

    prof_dir = _profile_dir(alias)
    if args.purge:
        if os.path.isdir(prof_dir):
            shutil.rmtree(prof_dir)
        cache = profile_cache_dir(alias)
        if os.path.isdir(cache):
            shutil.rmtree(cache)
        print(f"已移除账号 {alias}，并删除密钥目录与缓存目录")
    else:
        print(f"已从 profiles.json 移除 {alias}；密钥文件保留在 {prof_dir}（加 --purge 可一并删除）")
    if was_default:
        print("⚠️ 原默认账号已被移除，default 已清空 → 回落遗留凭据")


def cmd_env(args):
    # 不传 alias → None → 走 active_profile()（环境变量 WX_PROFILE / default），
    # 传 "default" → 显式回落遗留 ~/.config/weixin/appid|appsecret
    alias = (args.alias or "").strip() or None
    appid, secret, src = resolve_creds(alias)
    if not appid:
        die(f"❌ 无法解析账号 '{alias or active_profile() or '(default)'}' 的凭据")
    print(f"# 来源: {src}")
    print(f'export WX_PROFILE="{alias or active_profile()}"')
    print(f'export WX_APPID="{appid}"')
    print(f'export WX_APPSECRET="{secret}"')


# --------------------------------------------------------------------------- #
# check —— 取 token + 探测接口权限矩阵
# --------------------------------------------------------------------------- #
PROBES = [
    ("草稿·总数",   "/cgi-bin/draft/count",        {}),
    ("草稿·列表",   "/cgi-bin/draft/batchget",     {"offset": 0, "count": 1, "no_content": 1}),
    ("素材·统计",   "/cgi-bin/material/get_materialcount", None),
    ("发布·列表",   "/cgi-bin/freepublish/batchget", {"offset": 0, "count": 1, "no_content": 1}),
    ("统计·用户",   "/datacube/getusersummary",    None),   # 需日期，单独处理
]


def cmd_check(args):
    alias = (args.alias or "").strip() or None
    appid, secret, src = resolve_creds(alias)
    if not appid:
        avail = ", ".join(sorted(list_profiles().keys())) or "（无）"
        die(f"❌ 无法解析账号 '{alias or active_profile() or '(default)'}' 的凭据。已登记: {avail}")
    shown = alias or active_profile() or "(default/遗留)"

    print("=" * 62)
    print(f"账号自检: {shown}   AppID={mask(appid)}")
    print(f"凭据来源: {src}")
    print(f"缓存目录: {profile_cache_dir(alias)}")
    print("=" * 62)

    # 1) token
    try:
        tok, exp, tsrc = fetch_token(appid, secret, force_refresh=True)
    except WxApiError as e:
        print(f"❌ access_token 获取失败: [{e.errcode}] {e.errmsg}")
        if e.hint():
            print("    " + e.hint())
        sys.exit(1)
    print(f"✅ access_token 获取成功（{tsrc}，有效期 {exp}s）")

    # 2) 权限矩阵
    print()
    print(f"{'能力':<12}{'接口':<40}{'结果'}")
    print("-" * 62)
    ok_cnt = 0
    for label, path, payload in PROBES:
        probe_payload = payload
        if path == "/datacube/getusersummary":
            probe_payload = {"begin_date": "2026-09-14", "end_date": "2026-09-15"}
        try:
            if probe_payload is None:
                # GET 型接口：api_call 用 payload=None 会走 GET
                data = api_call(path, token=tok, check=True)
            else:
                data = api_call(path, probe_payload, token=tok, check=True)
            detail = ""
            if path == "/cgi-bin/draft/count":
                detail = f"（现有草稿 {data.get('total_count')} 篇）"
            elif path == "/cgi-bin/material/get_materialcount":
                detail = f"（图片素材 {data.get('image_count', 0)} 个）"
            elif path == "/datacube/getusersummary":
                detail = f"（返回 {len(data.get('list') or [])} 条）"
            print(f"{label:<12}{path:<40}✅ 可用 {detail}")
            ok_cnt += 1
        except WxApiError as e:
            extra = ""
            if e.errcode == 48001:
                extra = " ← 账号未认证，个人订阅号无此权限（预期）"
            print(f"{label:<12}{path:<40}❌ {e.errcode} {e.errmsg[:28]}{extra}")
    print("-" * 62)
    print(f"可用 {ok_cnt}/{len(PROBES)}")
    print()
    print("提示：本账号能否推草稿取决于「草稿·总数/列表」是否 ✅；")
    print("      发布(freepublish) 与 数据统计(datacube) 对个人订阅号普遍 48001，属账号类型限制。")


# --------------------------------------------------------------------------- #
def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", default=argparse.SUPPRESS,
                        help="把原始返回写入该 JSON 文件；用 - 打印到标准输出")

    p = argparse.ArgumentParser(
        prog="wx_account.py",
        description="微信公众号多账号（profile）管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("用法示例：")[-1],
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("list", help="列出所有已登记账号", parents=[common])
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("add", help="新增/更新账号", parents=[common])
    s.add_argument("alias", help="账号别名（脚本里用 --profile <alias> 引用）")
    s.add_argument("--name", default="", help="账号中文名，如『码上职业』")
    s.add_argument("--appid", required=True)
    s.add_argument("--secret", default="", help="AppSecret；不传则交互式输入（更安全，不进 shell history）")
    s.add_argument("--author", default="", help="该号图文默认作者名，如『码上职业』")
    s.add_argument("--set-default", action="store_true", help="同时设为默认账号")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("use", help="设置默认账号", parents=[common])
    s.add_argument("alias")
    s.set_defaults(func=cmd_use)

    s = sub.add_parser("rm", help="移除账号", parents=[common])
    s.add_argument("alias")
    s.add_argument("--purge", action="store_true", help="连同密钥目录与缓存目录一起删除")
    s.set_defaults(func=cmd_rm)

    s = sub.add_parser("env", help="打印某账号的 export 语句（供 shell source）", parents=[common])
    s.add_argument("alias", nargs="?", default="")
    s.set_defaults(func=cmd_env)

    s = sub.add_parser("check", help="探测账号的接口权限矩阵", parents=[common])
    s.add_argument("alias", nargs="?", default="")
    s.set_defaults(func=cmd_check)

    return p


def main():
    p = build_parser()
    args = p.parse_args()
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
        print("\n已中止")
        sys.exit(130)


if __name__ == "__main__":
    main()
