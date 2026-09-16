#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_common.py —— 微信公众号服务端 API 共享底座

被 wx_draft.py / wx_publish.py / wx_stats.py 复用，也供 wx_push_draft.py 等旧脚本按需引入。

职责：
  1) 凭据解析：环境变量 WX_APPID/WX_APPSECRET 优先，回退 ~/.config/weixin/{appid,appsecret}
  2) access_token：优先官方推荐的 stable_token（不会与其它系统互踢），失败回退 cgi-bin/token；
     带本地磁盘缓存，降低 token 接口调用次数（官方对 token 接口有频次限制）
  3) 统一 HTTP：走 curl 子进程并剥离代理环境变量（沙箱代理会改变出口 IP，导致 40164 误判）
  4) 统一错误翻译：把微信 errcode 翻译成「人话 + 处置建议」
  5) 输出助手：JSON 落盘、嵌套结构扁平化（供 CSV）

设计约束（沿用 mp-publish 既有约定）：
  - 绝不把 AppID/AppSecret 硬编码进仓库
  - 写操作（delete / submit / update）一律先备份、再执行
  - 参数校验前置，错误信息必须可直接照做
"""
import json
import os
import re
import subprocess
import sys
import time

API_BASE = "https://api.weixin.qq.com"
CRED_DIR = os.path.expanduser("~/.config/weixin")
CACHE_DIR = os.path.expanduser("~/.cache/weixin")
TOKEN_SAFETY_MARGIN = 300   # token 剩余有效期低于该秒数即视为过期，提前刷新

# --------------------------------------------------------------------------- #
# 多账号（profile）目录约定
# --------------------------------------------------------------------------- #
#   ~/.config/weixin/
#     appid / appsecret          # 遗留默认账号（= profiles.json 的 default），保持向后兼容
#     profiles.json              # {"default": "<alias>", "profiles": {alias: {name, appid, author}}}
#     profiles/<alias>/appsecret # 各账号密钥独立落盘（chmod 600），不进 profiles.json
#
#   ~/.cache/weixin/
#     token_<appid后8位>.json    # token 缓存天然按 appid 隔离
#     profiles/<alias>/draft_backups/   # 草稿备份按账号隔离（media_id 是账号内唯一，混放会误判）
PROFILES_FILE = os.path.join(CRED_DIR, "profiles.json")
PROFILES_SUBDIR = "profiles"

# 当前进程生效的账号别名。"" 表示走遗留的 ~/.config/weixin/appid|appsecret
_ACTIVE_PROFILE = None


def set_profile(alias):
    """设置当前进程的账号别名，并写回环境变量（子进程自动继承）。

    alias 为空/None 时清除，回落到遗留默认凭据。
    """
    global _ACTIVE_PROFILE
    alias = (alias or "").strip()
    _ACTIVE_PROFILE = alias
    if alias:
        os.environ["WX_PROFILE"] = alias
    else:
        os.environ.pop("WX_PROFILE", None)
    return alias


def active_profile():
    """返回当前生效的账号别名（显式设置 > 环境变量 > profiles.json 的 default）。"""
    if _ACTIVE_PROFILE:
        return _ACTIVE_PROFILE
    env = (os.environ.get("WX_PROFILE") or "").strip()
    if env:
        return env
    return read_profiles_meta().get("default", "") or ""


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}


def read_profiles_meta():
    """读取 profiles.json（缺失返回 {}）。"""
    d = _read_json(PROFILES_FILE)
    if not isinstance(d, dict):
        return {}
    d.setdefault("profiles", {})
    if not isinstance(d["profiles"], dict):
        d["profiles"] = {}
    return d


def write_profiles_meta(meta):
    os.makedirs(CRED_DIR, exist_ok=True)
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.chmod(PROFILES_FILE, 0o600)


def list_profiles():
    """返回 {alias: {"name":…, "appid":…, "author":…, "secret_path":…}}。

    同时把遗留默认凭据（~/.config/weixin/appid）作为一个特殊别名 "default" 暴露，
    方便 wx_account.py 直接列出/迁移。
    """
    meta = read_profiles_meta()
    out = dict(meta.get("profiles") or {})
    legacy_appid = _read_cred_file(os.path.join(CRED_DIR, "appid"))
    if legacy_appid:
        out.setdefault("default", {
            "name": "遗留默认账号（~/.config/weixin/appid）",
            "appid": legacy_appid,
            "author": "",
            "legacy": True,
        })
    return out


def _profile_dir(alias):
    return os.path.join(CRED_DIR, PROFILES_SUBDIR, alias)


def profile_cache_dir(alias=None):
    """账号专属缓存目录。遗留默认账号落在 ~/.cache/weixin/legacy_default。"""
    alias = alias if alias is not None else active_profile()
    key = alias or "legacy_default"
    return os.path.join(CACHE_DIR, PROFILES_SUBDIR, key)


def run_dir(create=True):
    """流水线中间产物目录（zj_wechat_content.html / zj_imgmap.json / zj_cover.jpg 等）。

    默认 /tmp（保持历史行为）。wx_pipeline.py 会按账号设 WX_RUN_DIR=/tmp/wxrun_<alias>，
    避免两个账号的流水线并发时**封面与正文串号**。
    """
    d = os.environ.get("WX_RUN_DIR") or "/tmp"
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def profile_data_dir(alias=None):
    """账号专属数据目录（草稿备份等持久产物）。

    特例：若该 profile 的 appid 与遗留 ~/.config/weixin/appid 一致（即同一个号，只是
    换了个别名来引用），沿用遗留路径 ~/.cache/weixin/，避免历史备份「换名字就找不到」。
    """
    alias = alias if alias is not None else active_profile()
    if not alias or alias == "default":
        return CACHE_DIR
    appid, _s, _src = resolve_creds(alias, quiet=True)
    legacy_appid = _read_cred_file(os.path.join(CRED_DIR, "appid"))
    if appid and legacy_appid and appid == legacy_appid:
        return CACHE_DIR
    return os.path.join(CACHE_DIR, PROFILES_SUBDIR, alias)


# --------------------------------------------------------------------------- #
# 错误翻译表
# --------------------------------------------------------------------------- #
ERRCODE_HINTS = {
    -1:     "系统繁忙，稍后重试（微信侧临时故障，非你的参数问题）",
    0:      "成功",
    40001:  "access_token 无效或非最新：检查 AppSecret；若刚刚手动刷新过 token，等 5 分钟后重试",
    40007:  "media_id 不合法/不存在：草稿可能已被删除（删除不可恢复），先 draft list 确认现存草稿",
    40114:  "index 取值不合法：单图文消息固定 index=0；多图文第一篇为 0",
    40164:  "出口 IP 不在白名单：按下方提示把该 IP 加入「设置与开发-基本配置-IP白名单」",
    41039:  "content_source_url 不合法",
    43002:  "要求 POST 请求：检查请求方法（少 -X POST 或少了 -F/-d）",
    45009:  "接口调用超过每日限额",
    45166:  "content 内容不合法：正文含被禁止的标签/结构，或超过 2 万字符、1M 体积",
    47001:  "数据格式错误：本接口必须用 JSON body（Content-Type: application/json）",
    48001:  "api unauthorized：当前账号未被授予该接口权限（发布/数据统计接口对个人订阅号普遍未开放）",
    53404:  "账号已被限制带货能力：删除商品信息后重试",
    53405:  "插入商品信息有误：检查 product_key 及商品状态",
    53406:  "请先开通带货能力",
    53503:  "该草稿未通过发布检查：检查草稿内容合规性",
    53504:  "需前往公众平台官网使用草稿：该草稿由人工在后台创建，API 不可直接发布",
    53505:  "请手动保存成功后再发表：草稿需在后台先手动保存一次",
    53600:  "Article ID 无效：article_id 来自 freepublish/submit 成功后的返回值",
    61500:  "日期格式错误，或日期范围超过该接口限制（见 --list 的跨度上限）",
    61501:  "日期跨度超过该接口上限：脚本会自动分段重试，或手动缩小 --begin/--end",
    61503:  "指定日期数据尚未生成：每天 8 点后才可查询前一天数据",
    88000:  "without comment privilege：该账号无留言/评论权限",
}


# 可重试的「伪失败」错误码：这类错误既可能是永久性的，也可能是服务端短暂未同步，
# 重试成本低而漏用代价高，故做有限次重试（最终仍失败时抛同一个错，不掩盖真问题）。
#   40007 invalid media_id —— 2026-09-16 多账号实测，确认有三种成因：
#         ① 没传 thumb_media_id（本账号实测：草稿必须带封面素材，缺了就是 40007）→ 永久失败
#         ② media_id 属于**另一个公众号**（跨账号串联残留 payload 所致）→ 永久失败
#         ③ 素材刚 add_material 上传、draft 服务尚未同步 → 数秒后自愈
#         ②③ 都是「重试或修正后能过」的，故纳入重试；重试耗尽仍抛原错，不掩盖 ①。
#         ⚠️ 关键：重试只治 ③。② 必须在源头消除（payload 落盘/读取用同一变量，
#            见 wx_push_draft.py 的 PAYLOAD_FILE）。40164/48001 等一律不重试。
#   -1    系统繁忙
RETRYABLE_ERRCODES = (40007, -1)


class WxApiError(Exception):
    """微信接口返回非 0 errcode 时抛出。"""

    def __init__(self, errcode, errmsg, raw=None, path=""):
        self.errcode = errcode
        self.errmsg = errmsg
        self.raw = raw or {}
        self.path = path
        super().__init__(f"[{errcode}] {errmsg}")

    def hint(self):
        h = ERRCODE_HINTS.get(self.errcode)
        if not h:
            return ""
        if self.errcode == 40164:
            m = re.search(r"invalid ip\s+([0-9a-fA-F:.]+)", self.errmsg or "")
            if m:
                h += f"\n    >>> 需添加的 IP: {m.group(1)}"
        return h


# --------------------------------------------------------------------------- #
# 凭据
# --------------------------------------------------------------------------- #
def _read_cred_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError):
        return ""


def resolve_creds(profile=None, quiet=True):
    """按账号别名解析 (appid, secret, source)。找不到返回 ("", "", "")，不退出。

    解析优先级（高 → 低）：
      1. 环境变量 WX_APPID / WX_APPSECRET（整对覆盖，用于临时/一次性调用）
      2. profiles.json + profiles/<alias>/appsecret
      3. 遗留 ~/.config/weixin/appid|appsecret
    """
    alias = profile if profile is not None else active_profile()
    appid = os.environ.get("WX_APPID") or ""
    secret = os.environ.get("WX_APPSECRET") or ""
    if appid and secret:
        return appid, secret, "环境变量"

    meta = read_profiles_meta()
    entry = (meta.get("profiles") or {}).get(alias) or {}
    if entry:
        appid = appid or entry.get("appid", "")
        secret = secret or _read_cred_file(os.path.join(_profile_dir(alias), "appsecret"))
        if appid and secret:
            return appid, secret, f"profile:{alias}"
    elif alias and alias != "default":
        # 未登记在 profiles.json，但也许有裸目录
        appid = appid or _read_cred_file(os.path.join(_profile_dir(alias), "appid"))
        secret = secret or _read_cred_file(os.path.join(_profile_dir(alias), "appsecret"))
        if appid and secret:
            return appid, secret, f"profile:{alias}(未登记)"

    if not alias or alias == "default":
        appid = appid or _read_cred_file(os.path.join(CRED_DIR, "appid"))
        secret = secret or _read_cred_file(os.path.join(CRED_DIR, "appsecret"))
        if appid and secret:
            return appid, secret, "legacy:" + CRED_DIR
    return "", "", ""


def load_wx_creds(quiet=False, profile=None):
    """环境变量 / profile / 遗留文件，三路解析。缺失则退出（exit code 2）。"""
    appid, secret, src = resolve_creds(profile, quiet=quiet)
    if not appid or not secret:
        alias = profile if profile is not None else active_profile()
        hint = f"（当前 profile=<{alias}>）" if alias else ""
        avail = ", ".join(sorted(list_profiles().keys())) or "（无）"
        sys.stderr.write(
            f"⚠️ 未配置微信凭据{hint}：请设置环境变量 WX_APPID/WX_APPSECRET，"
            f"或在 ~/.config/weixin/ 下放置 appid / appsecret 文件；"
            f"多账号可用 wx_account.py add <alias> 登记。已登记账号: {avail}\n"
        )
        sys.exit(2)
    if not quiet:
        print(f"[cred] profile={active_profile() or '-'} AppID={appid[:6]}****{appid[-4:]} 来源={src}")
    return appid, secret


def load_wx_author(default="满爸爱生活"):
    """取账号默认作者名（profiles.json 的 author 字段），未配置则用 default。"""
    alias = active_profile()
    entry = (read_profiles_meta().get("profiles") or {}).get(alias) or {}
    return entry.get("author") or default


# --------------------------------------------------------------------------- #
# 底层 HTTP（curl 子进程）
# --------------------------------------------------------------------------- #
def _clean_env():
    """剥离代理变量：沙箱代理会改变出口 IP，导致 40164 判断错位。"""
    return {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}


def curl_json(url, payload=None, method=None, timeout=60):
    """发一个请求并解析 JSON 返回。payload 为 dict 时走 JSON body（落临时文件，避免命令行转义）。"""
    env = _clean_env()
    cmd = ["curl", "-s", "--max-time", str(timeout)]
    tmp = None
    if payload is not None:
        tmp = os.path.join(CACHE_DIR, f"_payload_{os.getpid()}.tmp")
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        cmd += ["-X", method or "POST",
                "--data-binary", "@" + tmp,
                "-H", "Content-Type: application/json; charset=utf-8"]
    elif method and method.upper() != "GET":
        cmd += ["-X", method.upper()]
    cmd.append(url)

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    out = (proc.stdout or "").strip()
    if not out:
        raise WxApiError(-1, f"空响应（curl rc={proc.returncode}）: {proc.stderr[:200]}", path=url)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise WxApiError(-1, f"非 JSON 响应: {out[:300]}", path=url)


# --------------------------------------------------------------------------- #
# access_token（stable_token 优先 + 磁盘缓存）
# --------------------------------------------------------------------------- #
def _token_cache_path(appid):
    return os.path.join(CACHE_DIR, f"token_{appid[-8:]}.json")


def read_cached_token(appid):
    try:
        with open(_token_cache_path(appid), encoding="utf-8") as f:
            d = json.load(f)
        if d.get("token") and d.get("expire_at", 0) - TOKEN_SAFETY_MARGIN > time.time():
            return d["token"]
    except Exception:
        pass
    return None


def write_cached_token(appid, token, expires_in):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_token_cache_path(appid), "w", encoding="utf-8") as f:
            json.dump({"token": token, "expire_at": time.time() + int(expires_in or 7200)}, f)
        os.chmod(_token_cache_path(appid), 0o600)
    except Exception:
        pass


def fetch_token(appid, secret, force_refresh=False):
    """优先 stable_token（官方推荐，不会与其它系统互踢），失败回退 cgi-bin/token。"""
    try:
        d = curl_json(f"{API_BASE}/cgi-bin/stable_token",
                      payload={"grant_type": "client_credential", "appid": appid,
                               "secret": secret, "force_refresh": bool(force_refresh)})
        if d.get("access_token"):
            return d["access_token"], int(d.get("expires_in") or 7200), "stable_token"
    except WxApiError:
        pass
    d = curl_json(f"{API_BASE}/cgi-bin/token?grant_type=client_credential"
                  f"&appid={appid}&secret={secret}")
    if "access_token" not in d:
        err = WxApiError(d.get("errcode", -1), d.get("errmsg", str(d)), raw=d,
                         path="/cgi-bin/token")
        raise err
    return d["access_token"], int(d.get("expires_in") or 7200), "cgi-bin/token"


def get_token(appid=None, secret=None, force_refresh=False, quiet=True, profile=None):
    if not (appid and secret):
        _a, _s, _ = resolve_creds(profile, quiet=quiet)
        appid = appid or _a
        secret = secret or _s
    if not appid or not secret:
        load_wx_creds(quiet=False, profile=profile)   # 复用其报错与退出逻辑
    if not force_refresh:
        cached = read_cached_token(appid)
        if cached:
            if not quiet:
                print("[token] 命中本地缓存")
            return cached
    tok, exp, src = fetch_token(appid, secret, force_refresh=force_refresh)
    write_cached_token(appid, tok, exp)
    if not quiet:
        print(f"[token] 获取成功（{src}，有效期 {exp}s）")
    return tok


# --------------------------------------------------------------------------- #
# 统一接口调用
# --------------------------------------------------------------------------- #
def api_call(path, payload=None, method=None, token=None, appid=None, secret=None,
             check=True, timeout=60, retry=1, quiet=True):
    """调用任意微信服务端接口。

    path     : 例 '/cgi-bin/draft/count'、'/datacube/getusersummary'
    payload  : dict（JSON body）或 None
    check    : True 时 errcode!=0 抛 WxApiError；False 时原样返回
    retry    : token 失效（40001/42001）时强制刷新 token 的重试次数
    """
    tok = token or get_token(appid, secret, quiet=quiet)
    url = f"{API_BASE}{path}" + ("&" if "?" in path else "?") + f"access_token={tok}"
    data = curl_json(url, payload=payload, method=method, timeout=timeout)

    ec = data.get("errcode", 0)
    if check and ec not in (0, None):
        if ec in (40001, 42001, 40014) and retry > 0:
            if not quiet:
                print(f"[token] {ec} token 失效，强制刷新后重试…")
            new = get_token(appid, secret, force_refresh=True, quiet=quiet)
            return api_call(path, payload, method, new, appid, secret, check,
                            timeout, retry - 1, quiet)
        raise WxApiError(ec, data.get("errmsg", ""), raw=data, path=path)
    return data


def api_call_retry(path, payload=None, method=None, tries=3, delay=2.5, **kw):
    """带「伪失败」重试的 api_call。

    仅对 RETRYABLE_ERRCODES（40007 / -1）重试，退避 delay*1, delay*2 …；
    其它错误（含 40164、48001）立即抛出不浪费等待。最后一次仍失败则原样抛错。
    """
    last = None
    for i in range(max(1, tries)):
        try:
            return api_call(path, payload, method, **kw)
        except WxApiError as e:
            last = e
            if e.errcode not in RETRYABLE_ERRCODES or i == tries - 1:
                raise
            wait = delay * (i + 1)
            print(f"[retry] {e.errcode} {e.errmsg[:60]} —— {wait:.1f}s 后重试 ({i+1}/{tries-1})")
            time.sleep(wait)
    raise last


def probe_permission(path, payload=None):
    """权限探测：返回 (可用?, 说明)。用于 48001 这类「账号本身没权限」的判定。"""
    try:
        api_call(path, payload, check=True)
        return True, "可调用"
    except WxApiError as e:
        return False, f"{e.errcode} {e.errmsg}（{ERRCODE_HINTS.get(e.errcode, '')}）"


# --------------------------------------------------------------------------- #
# 输出助手
# --------------------------------------------------------------------------- #
def dump_json(obj, path=None, label="结果"):
    """落盘原始返回。

    path 语义：
      - 空 / None : 静默（不打印）—— 命令自身已打印关键信息，避免大块 JSON 噪音
      - '-'       : 打印到标准输出（需要看原始返回时用）
      - 其它路径   : 写文件并提示
    """
    txt = json.dumps(obj, ensure_ascii=False, indent=2)
    if path == "-":
        print(txt)
        return txt
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"[{label}] 已写入 {path}（{len(txt)} 字节）")
    return txt


def flatten(rows, prefix="", sep="."):
    """把嵌套 dict 拍平成单层，便于落 CSV（list 类字段序列化为 JSON 字符串）。"""
    out = {}
    for k, v in (rows or {}).items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key, sep))
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                out[key] = json.dumps(v, ensure_ascii=False)
            else:
                out[key] = ",".join(str(x) for x in v)
        else:
            out[key] = v
    return out


def write_csv(rows, path):
    """rows: list[dict]（自动取并集表头）。"""
    import csv
    if not rows:
        print("[csv] 无数据，跳过")
        return
    flat = [flatten(r) for r in rows]
    cols = []
    for r in flat:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in flat:
            w.writerow(r)
    print(f"[csv] 已写入 {path}（{len(flat)} 行 x {len(cols)} 列）")


def die(msg, code=1):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def human(n):
    """数字带千分位，None 显示为 '-'。"""
    if n is None:
        return "-"
    if isinstance(n, (int, float)):
        return f"{n:,}" if isinstance(n, int) else f"{n:,.4g}"
    return str(n)
