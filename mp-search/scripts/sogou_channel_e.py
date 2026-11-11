#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MP-Search 通道 E：搜狗微信 -> 官方签名链 -> 正文 Markdown -> 公众号主体反查.

设计要点（均在 2026-11-09 实测验证）：
1. 自建 Cookie 会话，不使用任何硬编码 Cookie（搜狗 SNUID/SUV 与 IP 绑定）。
2. 搜狗跳转页用 `url += '...'` 片段拼接出文章链接，产出的是
   `src=11&timestamp=...&signature=...` 的动态签名链，**不是永久短链**，
   因此显式输出签名时刻、存活时长与过期风险，禁止当作可归档链接使用。
3. 微信新版文章页已移除 DOM 中的 `js_content`，正文改存于
   `window.cgiDataNew.content_noencode`；两路都做，自动兜底。
4. 公众号主体不从已失效的搜狗 type=1 获取，而从文章页的
   `bizuin` / `user_name` 等字段反查聚合。

仅依赖 requests + lxml；markdownify 存在时优先使用，否则用内置轻量转换器。
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from lxml import html as lxml_html

UA_PC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
UA_WX = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49(0x18003128) "
         "NetType/WIFI Language/zh_CN")

SOGOU_HOME = "https://weixin.sogou.com/"
SOGOU_SEARCH = "https://weixin.sogou.com/weixin"
TIMEOUT = 15
SIGNED_LINK_TTL_HOURS = 2.0  # 保守估计：超过该时长即标注为高风险


class AntiSpiderError(RuntimeError):
    """搜狗返回反爬验证页。"""


def _is_antispider(resp: requests.Response) -> bool:
    body = resp.text.lower()
    return ("antispider" in resp.url.lower()
            or "seccoderight" in body
            or "anti.min.css" in body)


def _decode_js_escapes(raw: str) -> str:
    """还原 JS 字符串里的 \\xHH 转义（\\x0a 换行、\\x26quot; 引号等）。"""
    raw = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), raw)
    raw = raw.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/")
    return html_lib.unescape(raw)


def _html_to_markdown(fragment: str) -> str:
    """把微信正文 HTML 片段转成 Markdown（无第三方依赖的轻量实现）。"""
    try:
        from markdownify import markdownify  # type: ignore
        return re.sub(r"\n{3,}", "\n\n", markdownify(fragment, heading_style="ATX")).strip()
    except ImportError:
        pass

    BLOCK = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6",
             "ul", "ol", "blockquote", "pre", "table", "tr", "article", "br"}
    SKIP = {"script", "style", "noscript"}

    def render(node) -> str:
        if isinstance(node, str):
            return node
        tag = (node.tag or "").lower() if hasattr(node, "tag") else ""
        if tag in SKIP:
            return ""
        if tag == "img":
            src = node.get("data-src") or node.get("src") or ""
            alt = node.get("alt") or ""
            return f"\n![{alt}]({src})\n" if src else ""
        if tag == "br":
            return "\n"

        inner = (node.text or "") + "".join(render(c) for c in node)
        tail = node.tail or ""
        inner = inner.strip()

        if tag == "a":
            href = node.get("href") or ""
            out = f"[{inner}]({href})" if href and inner else inner
        elif tag in ("strong", "b"):
            out = f"**{inner}**" if inner else ""
        elif tag in ("em", "i"):
            out = f"*{inner}*" if inner else ""
        elif tag == "code":
            out = f"`{inner}`" if inner else ""
        elif tag == "li":
            out = f"- {inner}" if inner else ""
        elif re.fullmatch(r"h[1-6]", tag or ""):
            out = f"{'#' * int(tag[1])} {inner}" if inner else ""
        elif tag == "blockquote":
            out = "\n".join("> " + x for x in inner.splitlines()) if inner else ""
        else:
            out = inner

        if tag in BLOCK and out:
            out += "\n\n"
        return out + tail

    try:
        wrapper = lxml_html.fragment_fromstring(fragment, create_parent="div")
        # 必须带上 wrapper.text：正文常是「一大段纯文本 + 末尾若干标签」，
        # 只遍历子元素会丢掉首段文本。
        md = (wrapper.text or "") + "".join(render(c) for c in wrapper)
        if not md.strip():
            md = wrapper.text_content()
    except Exception:
        md = re.sub(r"<[^>]+>", " ", fragment)
        md = html_lib.unescape(md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _extract(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else default


class ChannelE:
    """通道 E 会话：所有网络请求集中在此，自带频控与反爬检测。"""

    def __init__(self, delay: float = 1.2, warmup: bool = True, verbose: bool = True):
        self.delay = delay
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA_PC,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        if warmup:
            self._warmup()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[通道E] {msg}", file=sys.stderr)

    def _warmup(self) -> None:
        """访问搜狗首页，让服务端下发属于当前 IP 的 ABTEST/SUID/SNUID。"""
        try:
            r = self.session.get(SOGOU_HOME, timeout=TIMEOUT)
            self._log(f"会话预热完成，Cookie: {','.join(self.session.cookies.keys()) or '(空)'}")
            if _is_antispider(r):
                raise AntiSpiderError("预热即触发反爬，建议稍后重试或更换网络出口")
        except requests.RequestException as e:
            raise RuntimeError(f"搜狗首页不可达: {e}") from e

    def _get(self, url: str, *, referer: str = "", ua: str = "",
             params: dict | None = None, strict: bool = True):
        headers = {}
        if referer:
            headers["Referer"] = referer
        if ua:
            headers["User-Agent"] = ua
        time.sleep(self.delay)
        r = self.session.get(url, params=params, headers=headers, timeout=TIMEOUT)
        if _is_antispider(r):
            if strict:
                raise AntiSpiderError("搜狗/微信返回反爬验证页；请降低频率或稍后重试")
            return None
        r.raise_for_status()
        return r

    # ---------- 1. 文章搜索 ----------
    def search_articles(self, query: str, page: int = 1, limit: int = 10) -> list[dict]:
        r = self._get(SOGOU_SEARCH, referer=SOGOU_HOME, params={
            "type": "2", "s_from": "input", "query": query,
            "ie": "utf8", "page": page, "_sug_": "n", "_sug_type_": "",
        })
        tree = lxml_html.fromstring(r.text)
        boxes = tree.xpath("//li[contains(@id,'sogou_vr_11002601_box_')]")
        items = []
        for box in boxes[:limit]:
            a = box.xpath(".//a[contains(@id,'sogou_vr_11002601_title_')]")
            if not a:
                continue
            a = a[0]
            href = a.get("href") or ""
            if href.startswith("/"):
                href = SOGOU_HOME.rstrip("/") + href
            acc = box.xpath(".//span[@class='all-time-y2']/text()")
            ts = _extract(r"timeConvert\('(\d+)'\)", box.xpath("string(.//div[@class='s-p'])"))
            pub, age_days = "", None
            if ts:
                dt = datetime.fromtimestamp(int(ts))
                pub = dt.strftime("%Y-%m-%d %H:%M")
                age_days = (datetime.now() - dt).days
            summary = box.xpath("string(.//p[@class='txt-info'])").strip()
            items.append({
                "title": a.text_content().strip(),
                "account": (acc[0].strip() if acc else ""),
                "publish_time": pub,
                "age_days": age_days,
                "freshness": ("fresh" if age_days is not None and age_days <= 90
                              else "old" if age_days is not None and age_days > 365
                              else "normal" if age_days is not None else "unknown"),
                "summary": re.sub(r"\s+", " ", summary)[:200],
                "sogou_link": href,
            })
        self._log(f"搜索「{query}」第 {page} 页命中 {len(items)} 条")
        return items

    # ---------- 2. 跳转链解析 ----------
    def resolve_real_url(self, sogou_link: str) -> dict:
        out = {"real_url": "", "kind": "none", "signed_at": "",
               "age_hours": None, "expires_at": "", "archivable": False,
               "expiry_risk": "", "note": ""}
        if not sogou_link:
            out["note"] = "缺少搜狗跳转链接"
            return out
        r = self._get(sogou_link, referer=SOGOU_HOME, strict=True)
        text, parts, idx = r.text, [], r.text.find("url += '") + len("url += '")
        while True:
            st = text.find("url += '", idx)
            if st == -1:
                break
            ed = text.find("'", st + len("url += '"))
            if ed == -1:
                break
            parts.append(text[st + len("url += '"):ed])
            idx = ed + 1
        full = "".join(parts).replace("@", "")
        if not full:
            out["note"] = "未找到 url += 片段，可能是验证码/失效页"
            return out
        url = "https://mp." + full if full.startswith("weixin.qq.com") else full
        out["real_url"] = url
        out["kind"] = "signed_temporary" if "signature=" in url else "permanent_short"
        out["stable_short_link"] = out["kind"] == "permanent_short"
        out["segments"] = len(parts)
        ts = _extract(r"timestamp=(\d+)", url)
        if ts:
            dt = datetime.fromtimestamp(int(ts))
            age = (datetime.now() - dt).total_seconds() / 3600
            exp = datetime.fromtimestamp(int(ts) + int(SIGNED_LINK_TTL_HOURS * 3600))
            out["signed_at"] = dt.strftime("%Y-%m-%d %H:%M")
            out["expires_at"] = exp.strftime("%Y-%m-%d %H:%M")
            out["usable_hours"] = round(SIGNED_LINK_TTL_HOURS, 1)
            out["age_hours"] = round(age, 3)
            if age > SIGNED_LINK_TTL_HOURS:
                out["expiry_risk"] = "high"
                out["note"] = f"签名已生成 {age:.1f} 小时，可能已过期"
            elif age > 1:
                out["expiry_risk"] = "medium"
                out["note"] = f"动态签名链，约 {exp:%H:%M} 后过期，不可归档"
            else:
                out["expiry_risk"] = "low"
                out["note"] = f"动态签名链，约 {exp:%H:%M} 后过期，不可归档长期引用"
        if out["kind"] == "permanent_short":
            out["archivable"] = True
            out["expires_at"] = ""
            out["note"] = "官方永久短链，可归档"
        return out

    # ---------- 3. 正文 + 主体字段 ----------
    @staticmethod
    def _parse_article_page(text: str) -> dict:
        tree = lxml_html.fromstring(text)
        info = {
            "title": _extract(r"msg_title\s*=\s*window\.title\s*=\s*'([^']*)'", text),
            "bizuin": _extract(r"bizuin:\s*'([^']*)'", text),
            "user_name": _extract(r"user_name:\s*'([^']*)'", text),
            "avatar": _extract(r"round_head_img:\s*'([^']*)'", text),
            "nickname": (_extract(r"nick_name:\s*'([^']*)'", text)
                        or _extract(r"nickname:\s*'([^']*)'", text)
                        or _extract(r"var\s+nickname\s*=\s*'([^']*)'", text)
                        or _extract(r"window\.nickname\s*=\s*'([^']*)'", text)),
        }
        nodes = tree.xpath("//div[@id='js_content']")
        source, frag = "", ""
        if nodes and (nodes[0].text_content() or "").strip():
            from lxml import etree
            frag = (nodes[0].text or "") + "".join(
                etree.tostring(c, encoding="unicode") for c in nodes[0])
            source = "js_content"
        if not frag:
            m = re.search(r"content_noencode:\s*'((?:[^'\\]|\\.)*)'", text)
            if m:
                frag = _decode_js_escapes(m.group(1))
                source = "cgiDataNew.content_noencode"
        info["body_source"] = source
        info["markdown"] = _html_to_markdown(frag) if frag else ""
        info["ok"] = bool(info["markdown"])
        return info

    def fetch_article(self, real_url: str, referer: str = "") -> dict:
        if not real_url:
            return {"ok": False, "error": "缺少真实链接", "markdown": ""}
        r = self._get(real_url, referer=referer or SOGOU_HOME, ua=UA_WX, strict=True)
        return self._parse_article_page(r.text)

    # ---------- 4. 公众号主体反查 ----------
    def discover_accounts(self, query: str, limit: int = 5, probe: int = 6) -> list[dict]:
        """搜狗 type=1 已全域失效，改由文章页反查 bizuin / user_name 聚合主体。"""
        arts = self.search_articles(query, limit=probe)
        found: dict[str, dict] = {}
        for a in arts:
            try:
                link = self.resolve_real_url(a["sogou_link"])
                if not link["real_url"]:
                    continue
                art = self.fetch_article(link["real_url"], a["sogou_link"])
            except (AntiSpiderError, requests.RequestException) as e:
                self._log(f"跳过一篇（{type(e).__name__}: {e}）")
                continue
            key = art.get("user_name") or art.get("bizuin") or art.get("nickname")
            if not key:
                continue
            if key not in found:
                found[key] = {
                    "nickname": art.get("nickname") or a.get("account") or "",
                    "user_name": art.get("user_name") or "",
                    "bizuin": art.get("bizuin") or "",
                    "avatar": art.get("avatar") or "",
                    "sample_articles": [],
                    "discovered_by": "channel_e_reverse_lookup",
                }
            found[key]["sample_articles"].append({
                "title": a["title"], "publish_time": a["publish_time"],
                "real_url": link["real_url"], "expiry_risk": link["expiry_risk"],
            })
        return list(found.values())[:limit]


def _to_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _md_table(items: list[dict], cols: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(c[1] for c in cols) + " |"
    sep = "| " + " | ".join(":---" for _ in cols) + " |"
    lines = [head, sep]
    for it in items:
        lines.append("| " + " | ".join(str(it.get(k, "") or "-").replace("|", "\\|")[:120]
                                       for k, _ in cols) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MP-Search 通道 E（搜狗→真实链→正文→主体反查）")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="搜索文章并解析为官方签名链")
    s.add_argument("keyword")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.add_argument("-p", "--page", type=int, default=1)
    s.add_argument("--with-body", action="store_true", help="同时抓取正文 Markdown")
    s.add_argument("--body-limit", type=int, default=3)
    s.add_argument("--delay", type=float, default=1.2)
    s.add_argument("-o", "--output")
    s.add_argument("--format-md")

    a = sub.add_parser("accounts", help="按关键词反查公众号主体（替代失效的搜狗 type=1）")
    a.add_argument("keyword")
    a.add_argument("-n", "--limit", type=int, default=5)
    a.add_argument("--probe", type=int, default=6, help="探测文章数（默认 6）")
    a.add_argument("--delay", type=float, default=1.2)
    a.add_argument("-o", "--output")
    a.add_argument("--format-md")

    c = sub.add_parser("content", help="直接抓取一篇微信文章的正文 Markdown")
    c.add_argument("url")
    c.add_argument("--referer", default="")
    c.add_argument("-o", "--output")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 1

    try:
        ch = ChannelE(delay=getattr(args, "delay", 0.0))
        if args.cmd == "content":
            out = ch.fetch_article(args.url, args.referer)
            text = out.get("markdown") or _to_json(out)
            print(text)
            if args.output:
                open(args.output, "w", encoding="utf-8").write(_to_json(out))
            return 0 if out.get("ok") else 2

        if args.cmd == "accounts":
            out = ch.discover_accounts(args.keyword, limit=args.limit, probe=args.probe)
            rows = [{"nickname": x["nickname"], "user_name": x["user_name"],
                     "bizuin": x["bizuin"], "samples": len(x["sample_articles"])}
                    for x in out]
            md = _md_table(rows, [("nickname", "公众号"), ("user_name", "微信号"),
                                  ("bizuin", "__biz"), ("samples", "命中文章数")])
        else:
            out = ch.search_articles(args.keyword, page=args.page, limit=args.limit)
            for i, it in enumerate(out):
                try:
                    link = ch.resolve_real_url(it["sogou_link"])
                    it.update({k: link[k] for k in ("real_url", "kind", "signed_at",
                                                    "expires_at", "archivable",
                                                    "expiry_risk", "note")})
                    if args.with_body and i < args.body_limit and link["real_url"]:
                        art = ch.fetch_article(link["real_url"], it["sogou_link"])
                        it["body_source"] = art.get("body_source", "")
                        it["markdown"] = art.get("markdown", "")
                        it["body_ok"] = art.get("ok", False)
                except (AntiSpiderError, requests.RequestException) as e:
                    it["resolve_error"] = f"{type(e).__name__}: {e}"
            md = _md_table(out, [("title", "标题"), ("account", "公众号"),
                                 ("publish_time", "发布时间"), ("freshness", "时效"),
                                 ("expires_at", "签名失效(约)"), ("expiry_risk", "风险")])

        print(md)
        if args.output:
            open(args.output, "w", encoding="utf-8").write(_to_json(out))
        if getattr(args, "format_md", None):
            open(args.format_md, "w", encoding="utf-8").write(md + "\n")
        return 0
    except (AntiSpiderError, RuntimeError, requests.RequestException) as e:
        print(f"[通道E] 失败: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
