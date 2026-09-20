#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emit_briefing.py —— 从「公司主数据.csv」一行生成写稿用的 BRIEFING（给 AI 的投料单）

为什么要有这个脚本
==================
写稿提示词最大的 token 浪费与最大的质量风险来自同一件事：
  让模型去「找」硬信息。
  - 省 token 的角度：找 = 多轮工具调用 + 正文回流，一次找不全要重找。
  - 质量的角度：找不到时模型会「合理补全」——这正是 09-18 紫金稿翻车的机理
    （非官方口径 60 名 / 11-02 截止被当成事实写进正文）。

所以把「确定性部分」从提示词里拿走：由脚本从主档搬字段 + 显式标出缺口，
模型只做「表达转换」，不做信息检索，也不被允许推测。

用法
====
  # 按关键词出 briefing（打印到 stdout）
  /usr/local/bin/python3 工具/emit_briefing.py "江苏银行"

  # 写成本次写稿的投料单文件
  /usr/local/bin/python3 工具/emit_briefing.py "江苏银行" --out 工具/briefings/

  # 多条一起（批量开稿前先看缺口全景）
  /usr/local/bin/python3 工具/emit_briefing.py "江苏银行" "南京银行" --gap-only

  # 列出所有「硬信息已够、可以动笔」的单位（选题用）
  /usr/local/bin/python3 工具/emit_briefing.py --ready

字段可信度三档
==============
  OK     主档有确定值（含具体日期/具体人数）
  VAGUE  主档是软词（待核/预计/滚动/招满即止/暂无）→ 不得写进正文，必须回官方补
  EMPTY  主档为空

⛔ 改动主档的口径见 MEMORY.md §七：绝不手改 CSV，改 build_company_csv.constants.json 后重建。
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 主数据 CSV 是**项目资产**（obsidian vault），不是技能资产。
# 脚本本体可以被放进技能目录供任何会话调用，但数据源必须显式指向 vault，
# 否则换了位置就找不到主档。用 --master 覆盖可指向别的主档。
DEFAULT_MASTER = "/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/工具/公司主数据.csv"
MASTER_CSV = DEFAULT_MASTER

# ── 主档列 → briefing 字段 的映射（左=CSV列, 右=(briefing键, 展示名)）
FIELD_MAP = [
    ("公司/主体",     ("unit",           "单位全称")),
    ("线",           ("line",           "线(A校招/B编制)")),
    ("行业分组",       ("industry",       "行业分组")),
    ("性质",          ("nature",         "单位性质")),
    ("批次/说明",      ("batch",          "批次/说明")),
    ("校招岗位数",     ("hc_campus",      "校招岗位数")),
    ("社招岗位数",     ("hc_social",      "社招岗位数")),
    ("报名截止",       ("deadline",       "报名截止")),
    ("剩余天",         ("days_left",      "剩余天")),
    ("笔试",          ("written_exam",   "笔试")),
    ("公告发布日",     ("announce_date",  "公告发布日")),
    ("工作地点",       ("location",       "工作地点")),
    ("学历要求",       ("edu",            "学历要求")),
    ("用工性质",       ("employment",     "用工性质")),
    ("面向届别",       ("target_class",   "面向届别")),
    ("状态",          ("status",         "主档状态")),
    ("稿件",          ("draft_state",    "稿件进度")),
    ("备注",          ("note",           "备注")),
]

# 写稿「必填事实」：这 8 项缺一项就写不出不误导的招聘稿。
# key -> (展示名, csv 源列, 出现在哪一段)
REQUIRED = {
    "unit":         ("单位全称",      "公司/主体",     "段4 单位来头"),
    "deadline":     ("报名截止",      "报名截止",      "段3 宫格 / SEO摘要 / 钩子"),
    "written_exam": ("笔试时间",      "笔试",          "FAQ Q3"),
    "edu":          ("学历要求",      "学历要求",      "段5 岗位表 / FAQ"),
    "employment":   ("用工性质",      "用工性质",      "段4 解读四问①"),
    "target_class": ("面向届别",      "面向届别",      "段6 条件"),
    "location":     ("工作地点",      "工作地点",      "段5 岗位表"),
    "announce_date":("公告发布日",    "公告发布日",    "时效标注"),
}

# 软词：主档里出现这些 = 未核实，禁止当事实写进正文
VAGUE_PAT = re.compile(
    r"待核|待定|预计|暂无|滚动|招满即止|详见|另行通知|以.{0,6}为准|◐|—|-{2,}|^\s*$"
)
DATE_PAT = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日|\d{2}-\d{2}")
NUM_PAT = re.compile(r"\d")


def grade(val: str) -> str:
    """判定字段可信度：OK / VAGUE / EMPTY"""
    v = (val or "").strip()
    if not v:
        return "EMPTY"
    if VAGUE_PAT.search(v) and not DATE_PAT.search(v):
        return "VAGUE"
    return "OK"


def pick_sources(row: dict) -> list:
    """挑出可用于回官方补数的 URL / 入口"""
    out = []
    for col in ("公告原文", "网申入口", "官网公告栏", "官网地址"):
        v = (row.get(col) or "").strip()
        if not v:
            continue
        # 「路径（⛔ 招聘(SPA)）」这类带注记的，把注记留着，写稿时要知道能不能抓
        out.append((col, v))
    return out


def clean_url(v: str) -> str:
    """把 'rsj.taizhou.gov.cn（通知公告栏）' 拆成 url + 注记"""
    m = re.match(r"^([^\s（(]+)\s*[（(]([^）)]*)[）)]", v)
    if m:
        return m.group(1), m.group(2)
    return v, ""


def build_briefing(row: dict, today: str) -> str:
    kname = (row.get("公司/主体") or "").strip()
    line = (row.get("线") or "").strip()
    L = []

    L.append(f"# BRIEFING · {kname}")
    L.append("")
    L.append(f"> 机器生成于 {today} ｜ 数据源：`工具/公司主数据.csv` ｜ **本文件不是核实结论，是核实起点**")
    L.append("")

    # ── A. 主档已有值
    L.append("## A. 主档硬信息（可直接引用，但需与官方公告逐字对照）")
    L.append("")
    L.append("| 字段 | 值 | 可信度 |")
    L.append("|---|---|---|")
    for col, (key, label) in FIELD_MAP:
        val = (row.get(col) or "").strip()
        if not val:
            continue
        g = {"OK": "✅ 确定", "VAGUE": "⚠️ 软词·未核", "EMPTY": "—"}[grade(val)]
        val_show = val.replace("|", "\\|").replace("\n", " ")[:80]
        L.append(f"| {label} | {val_show} | {g} |")
    L.append("")

    # ── B. 缺口：这才是提示词真正需要的部分
    L.append("## B. ⛔ 缺口清单（必回官方补；**禁止推测、禁止用转载号数字**）")
    L.append("")
    gaps = []
    for key, (label, col, where) in REQUIRED.items():
        val = (row.get(col) or "").strip()
        g = grade(val)
        if g == "OK":
            continue
        gaps.append((label, where, "主档为空" if g == "EMPTY" else f"主档为软词「{val[:30]}」"))
    if not gaps:
        L.append("✅ 八项必填事实主档均已确定，可直接开写（仍建议抽查 2 项复核）。")
    else:
        L.append("| 缺什么 | 用在哪一段 | 现状 |")
        L.append("|---|---|---|")
        for label, where, why in gaps:
            L.append(f"| **{label}** | {where} | {why} |")
        L.append("")
        L.append("**补数红线**：")
        L.append("- ⛔ 培训号/聚合站的日期与人数一律不采（已实证 yinhangzhaopin.com 六大行日期 6/6 全错）")
        L.append("- ✅ 认官方公告原文、报名站接口、政府网附件 xlsx；补完**回填主档**，不要只写进稿件")
        L.append("- ✅ 官方没写的（薪酬/食宿/经费渠道/专业明细）→ 正文写「**公告未披露**」，不代为断言")
    L.append("")

    # ── C. 回官方补数的入口
    srcs = pick_sources(row)
    L.append("## C. 官方源（回补入口 / `--source-url` 候选项）")
    L.append("")
    if srcs:
        L.append("| 类型 | 地址 | 注记 |")
        L.append("|---|---|---|")
        for col, v in srcs:
            url, note = clean_url(v)
            L.append(f"| {col} | {url} | {note or '—'} |")
        L.append("")
        L.append("⚠️ 「网络报名」≠ 在线系统：须回公告 §报名办法 逐字核（09-17 无锡实证：实为邮箱投递、以收件时间为准）。")
        L.append("⚠️ `--source-url` 优先级：网申系统 > 报名邮箱所在公告页 > 官网栏目页。")
    else:
        L.append("⛔ 主档无任何官方入口 —— 补数前先补这一列到主档。")
    L.append("")

    # ── D. 装配指令：机器算好的，别让模型猜
    L.append("## D. 装配指令（脚本已判定，不要再推理）")
    L.append("")
    dl = (row.get("报名截止") or "").strip()
    blocked = grade(dl) != "OK"
    L.append(f"- **封面母版**：`{'标准社招封面母版.png' if line.upper() == 'B' else '标准校招封面母版.png'}`"
             f"（判据：线={line or '未标'}；面向 2027 届应届生=校招，面向社会/编制=社招）")
    L.append("- **主色**：⛔ 必须先跑 `logo 众数色` 取色，**严禁沿用上一篇色板**（09-17 南京银行误用江苏银行蓝）")
    if blocked:
        L.append(f"- ⛔ **暂不可动笔**：报名截止仍是软词「{dl or '空'}」，定不了标题钩子与 SEO 摘要。先回官方钉死。")
    else:
        L.append(f"- ✅ 报名截止已确定（{dl}），可动笔；三宫格、摘要、标题钩子用这个值。")
    L.append("")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="从公司主数据生成写稿 BRIEFING")
    ap.add_argument("keywords", nargs="*", help="单位关键词，模糊匹配「公司/主体」")
    ap.add_argument("--master", default=DEFAULT_MASTER,
                    help="公司主数据 CSV 路径（默认指向码上职业 vault 主档）")
    ap.add_argument("--out", metavar="DIR", help="写到该目录（文件名=单位.md）；不传则打印到 stdout")
    ap.add_argument("--gap-only", action="store_true", help="只打印缺口一行式摘要")
    ap.add_argument("--ready", action="store_true", help="列出必填事实已齐的单位")
    ap.add_argument("--limit", type=int, default=3, help="每个关键词最多匹配几条，默认3")
    a = ap.parse_args()
    global MASTER_CSV
    MASTER_CSV = a.master

    if not os.path.exists(MASTER_CSV):
        sys.exit(f"找不到主档：{MASTER_CSV}\n用 --master <路径> 显式指定。")
    rows = list(csv.DictReader(open(MASTER_CSV, encoding="utf-8-sig")))
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    def hit(r, kw):
        blob = " ".join((r.get(c) or "") for c in ("公司/主体", "别名", "备注", "批次/说明"))
        return kw.strip() in blob

    if a.ready:
        ready = []
        for r in rows:
            if not (r.get("公司/主体") or "").strip():
                continue
            if any(grade(r.get(c, "")) != "OK" for _k, (_l, c, _w) in REQUIRED.items()):
                continue
            ready.append(((r.get("报名截止") or ""), (r.get("公司/主体") or ""), (r.get("稿件") or "")))
        ready.sort()
        print(f"必填八项已齐、可直接开笔的单位：{len(ready)} 条")
        for dl, name, ds in ready[:60]:
            print(f"  {dl or '—':<12} {name:<40} 稿件={ds or '未排'}")
        return

    if not a.keywords:
        ap.print_help()
        return

    if a.gap_only:
        print(f"{'单位':<40} {'缺':<6} 缺口")
        for kw in a.keywords:
            for r in [x for x in rows if hit(x, kw)][: a.limit]:
                miss = [lbl for k, (lbl, c, _w) in REQUIRED.items() if grade(r.get(c, "")) != "OK"]
                print(f"{(r.get('公司/主体') or '')[:38]:<40} {len(miss):<6} " + "、".join(miss))
        return

    for kw in a.keywords:
        hits = [x for x in rows if hit(x, kw)]
        if not hits:
            print(f"[miss] 主档无匹配：{kw}", file=sys.stderr)
            continue
        # ⚠️ 同一单位在主档常有重复行（有的行近乎全空）。
        # 直接丢给模型 → 它抓到空行就会开始编。这里按「缺口最少」挑最全的那条做主，其余告警。
        hits.sort(key=lambda r: sum(1 for _k, (_l, c, _w) in REQUIRED.items()
                                    if grade(r.get(c, "")) != "OK"))
        main_row, dupes = hits[0], hits[1:a.limit]
        if dupes:
            print(f"[dup] 「{kw}」在主档有 {len(hits)} 行重复登记，已自动取最全的一条；"
                  f"其余行的主数据建议合并/清理：", file=sys.stderr)
            for d in dupes:
                n_miss = sum(1 for _k, (_l, c, _w) in REQUIRED.items() if grade(d.get(c, "")) != "OK")
                print(f"        - {(d.get('公司/主体') or '')[:36]}  (缺 {n_miss} 项, "
                      f"批次={(d.get('批次/说明') or '')[:16]})", file=sys.stderr)
        r = main_row
        text = build_briefing(r, today)
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            safe = re.sub(r"[/\s]+", "_", (r.get("公司/主体") or kw))[:40]
            fp = os.path.join(a.out, f"{safe}.md")
            open(fp, "w", encoding="utf-8").write(text)
            print(f"[ok] {fp}")
        else:
            print(text)
            print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
