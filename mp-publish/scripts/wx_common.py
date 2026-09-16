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


def load_wx_creds(quiet=False):
    """环境变量优先，回退 ~/.config/weixin/。缺失则退出（exit code 2）。"""
    appid = os.environ.get("WX_APPID") or _read_cred_file(os.path.join(CRED_DIR, "appid"))
    secret = os.environ.get("WX_APPSECRET") or _read_cred_file(os.path.join(CRED_DIR, "appsecret"))
    if not appid or not secret:
        sys.stderr.write(
            "⚠️ 未配置微信凭据：请设置环境变量 WX_APPID/WX_APPSECRET，"
            "或在 ~/.config/weixin/ 下放置 appid / appsecret 文件\n"
        )
        sys.exit(2)
    if not quiet:
        print(f"[cred] AppID={appid[:6]}****{appid[-4:]} 凭据来源={'环境变量' if os.environ.get('WX_APPID') else CRED_DIR}")
    return appid, secret


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
        tmp = os.path.join(CACHE_DIR, "_payload.tmp")
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


def get_token(appid=None, secret=None, force_refresh=False, quiet=True):
    appid = appid or os.environ.get("WX_APPID") or _read_cred_file(os.path.join(CRED_DIR, "appid"))
    secret = secret or os.environ.get("WX_APPSECRET") or _read_cred_file(os.path.join(CRED_DIR, "appsecret"))
    if not appid or not secret:
        load_wx_creds(quiet=False)   # 复用其报错与退出逻辑
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
