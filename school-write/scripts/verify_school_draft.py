#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_school_draft.py —— school-write / 教育系统 本地成稿质量门禁

为什么单独一个脚本：
    school-write 采用**合同专属的教育招聘 7 段骨架**（朱总 2026-09-29 拍板「另设骨架」），
    与 job-write 的 8 段骨架段名不同 → job-write/scripts/verify_draft.py 会误报「缺必备骨架段」。
    ⛔ 不要去改 job-write 的脚本（它是 A/B 线与 hospital-write 共用的活资产）。

校验四道门禁：
    1. 源稿 (Markdown)：标题 ≤64 字符；单行式 SEO 摘要 ≤120 字符且无 emoji；教育招聘 7 段骨架关键词齐全
    2. 排版 (HTML)：677px 居中约束；调用 mp-html 官方方言检查器；<section> 配平
    3. 封面 (PNG)：900×383 且色彩模式必须 RGB（禁 RGBA）
    4. 🔴 数字门禁（本赛道专属）：速览段必须同时出现岗位数与人数；长期招聘形态必须出现「招满即止」

用法：
    python3 verify_school_draft.py "教育系统/待发布/2026-09-30-南京特殊教育师范学院第二批"
    python3 verify_school_draft.py --dir "教育系统/待发布/"
"""
import argparse
import glob
import os
import re
import subprocess
import sys

# 方言检查器：按候选项依次探测，避免硬编码单一绝对路径。
# ⚠️ 刻意排除了"当前工作目录相对路径"——本技能会从任意 cwd 调用。
_DIALECT_CANDIDATES = [
    os.path.expanduser("~/.workbuddy/skills/mp-html/scripts/wx_dialect_check.py"),
    os.path.expanduser("~/src/skills/mp-html/scripts/wx_dialect_check.py"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "..", "mp-html", "scripts", "wx_dialect_check.py"),
]


def _find_dialect_checker():
    for p in _DIALECT_CANDIDATES:
        p = os.path.normpath(p)
        if os.path.exists(p):
            return p
    return None

# 教育招聘 7 段骨架的「标题文字指纹」。命中任一形式即通过。
# ⚠️ 这些段名是 school-write 合同的一部分，改动须同步 SKILL.md §四 与已发布稿。
MUST_BLOCKS = [
    ("码上君划重点", "导语卡（段1）"),
    ("招聘速览|关键信息速览|招聘概要", "招聘速览（段2）"),
    ("单位与岗位性质|单位来头|单位简介|学校简介", "单位与岗位性质（段3）"),
    ("招什么人|招哪些|招聘需求|岗位明细|岗位表", "招什么人（段4）"),
    ("报考条件|应聘基本条件|资格条件|报考资格|硬门槛", "报考条件与禁报（段5）"),
    ("怎么报名|如何报名|报名流程|报名方式", "怎么报名（段6）"),
    ("考核|体检|公示|服务期", "考核·体检·公示·服务期（段7）"),
    ("常见问答|FAQ", "常见问答（FAQ）"),
]

OPTIONAL_BLOCKS = [
    ("实操建议|码上君建议|行动建议", "码上君实操建议"),
]

# ⚠️ 本赛道最常见的漏项（instances.md §12）：速览/规模格不填数字
SCALE_MARKERS = ("招聘速览", "关键信息速览", "招聘概要", "数据三宫格")

# ---- 🔴 红线词反向检查（2026-09-29 立）----
# 来源：迁移 3 篇存量稿时实测发现**三篇全都含「防骗提醒」红框**，而防骗提醒已由朱总 2026-09-28
# 裁定**全线下线**（job-write §七）。此前本脚本**完全没有这一项** —— 属门禁缺口。
# ⛔ 命中即告警/报错，绝不静默通过。老骨架存量稿降级为告警（对齐既有豁免惯例）。
REDLINE_WORDS = ("防骗提醒", "防骗声明", "谨防诈骗", "警惕诈骗",
                 "本文仅作", "版权所有", "下期预告", "免责声明")

# ---- 老骨架存量稿豁免（2026-09-29 立）----
# 背景：`教育系统/待发布/` 里有 3 篇 2026-09-24 用 **job-write 8 段骨架**写的存量稿
# （南师大 / 南信大 / 南大工程管理）。它们天然没有「招聘速览」段，按新骨架门禁会**永远红灯**＝噪音。
# 对齐 job-write 对「老惯例稿（02-xx）」的既有豁免惯例，改为**显式 frontmatter 标记 + 降级告警**。
# ⛔ 刻意**不用自动探测**（如"含数据三宫格即判老稿"）——那样新稿写错段名会被误豁免 = 漏网。
# ⛔ 新稿**禁止**带此标记。
LEGACY_SKELETON_RE = re.compile(r"^骨架:\s*(?:job-write|老|legacy)", re.M)
LEGACY_EXEMPT_BLOCKS = ("招聘速览（段2）",)   # 老骨架没有的段，缺失不报错


def contains_emoji(text):
    for ch in text:
        cp = ord(ch)
        if (0x1F600 <= cp <= 0x1F64F or 0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or 0x1F700 <= cp <= 0x1F77F or
            0x1F780 <= cp <= 0x1F7FF or 0x1F800 <= cp <= 0x1F8FF or
            0x1F900 <= cp <= 0x1F9FF or 0x1FA00 <= cp <= 0x1FA6F or
            0x1FA70 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF):
            return True
    return False


# ---- 段标记行提取 ----
# 🔴 为什么必须只在「段标记行」上做骨架匹配（2026-09-29 实测立规）：
#   早期版本拿**整篇正文**匹配指纹，而段7 的指纹含「考核」——源稿速览表的表头
#   `| 岗位数·人数 | 编制性质 | 考核方式 | 报名窗口 |` 里就有"考核"二字，
#   于是**删掉整个段7 标题后依然报"8/8 全齐"**（反例对照实测）。
#   ⇒ 骨架判定只认「markdown 标题行」与「独立成行的加粗短语」，正文/表格一律不参与。
_HEADING_RE = re.compile(r"^#{1,6}\s*(\S.*)$")
_STANDALONE_BOLD_RE = re.compile(r"^\*\*(.{2,40}?)\*\*[：:]?\s*$")


def extract_section_markers(md_text):
    """返回源稿里的段标记行文本列表（已剥离 # 与 ** 包裹）。"""
    marks = []
    for line in md_text.split("\n"):
        s = line.strip()
        if s.startswith(">"):          # 引用块（SEO 摘要）不参与
            continue
        m = _HEADING_RE.match(s)
        if m:
            marks.append(m.group(1).strip())
            continue
        m = _STANDALONE_BOLD_RE.match(s)
        if m:
            marks.append(m.group(1).strip())
    return marks


def verify_single(prefix):
    print(f"\n🔍 开始质检（教育系统）：{os.path.basename(prefix)}")
    md_file = prefix + "-源稿.md"
    html_file = prefix + "-排版.html"
    cover_file = prefix + "-封面.png"
    dialect = _find_dialect_checker()

    errors, warnings = [], []
    md_text = ""
    html_text = ""

    # ---------- 1. 源稿 ----------
    if not os.path.exists(md_file):
        errors.append(f"缺少源稿文件：{md_file}")
    else:
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        # 老骨架存量稿判定（见 LEGACY_SKELETON_RE 注释）
        m_fm = re.search(r"^---\n(.*?)\n---", md_text, re.S)
        is_legacy = bool(LEGACY_SKELETON_RE.search(m_fm.group(1) if m_fm else ""))
        if is_legacy:
            warnings.append(
                "**老骨架存量稿**（frontmatter 带 `骨架:` 标记）：未按教育线 7 段骨架成稿，"
                "骨架段与数字门禁均降级为告警。⛔ 若本篇要发布，须按 school-write 骨架重写并删除该标记。"
            )

        m_title = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
        if not m_title:
            errors.append("源稿缺少一级标题 (# 标题)")
        else:
            title = m_title.group(1).strip()
            n = len(title)
            if n > 64:
                errors.append(f"标题超长：{n} 字符（硬上限 ≤64）：{title}")
            else:
                print(f"  [1/4] 源稿标题：{n} 字符（≤64）✅")

        m_seo = re.search(r"^>\s+\*\*SEO\s*摘要\*\*[^：:]*[：:](.+)$", md_text, re.MULTILINE)
        if not m_seo:
            errors.append("源稿缺少单行式 SEO 摘要（> **SEO 摘要**（NNN字，无 emoji）：<正文>）")
        else:
            digest = m_seo.group(1).strip()
            d = len(digest)
            if d > 120:
                errors.append(f"SEO 摘要超长：{d} 字符（硬上限 ≤120）")
            elif contains_emoji(digest):
                errors.append("SEO 摘要含 emoji（微信会渲染成豆腐块，禁止）")
            else:
                print(f"  [1/4] SEO 摘要：{d} 字符（≤120，无 emoji）✅")

        # ---- 骨架段判定：只在段标记行上匹配（见 extract_section_markers 注释）----
        marks = extract_section_markers(md_text)
        marks_blob = "\n".join(marks)
        missing, hit_names, body_only = [], [], []
        for pat, label in MUST_BLOCKS:
            if re.search(pat, marks_blob):
                hit_names.append(label)
            else:
                missing.append(label)
                if re.search(pat, md_text):       # 正文里有、但没做成段标题
                    body_only.append(label)
        if missing:
            # 老骨架稿豁免的段不报错（其余段仍照报）
            hard_missing = [m for m in missing if not (is_legacy and m in LEGACY_EXEMPT_BLOCKS)]
            soft_missing = [m for m in missing if m not in hard_missing]
            if soft_missing:
                warnings.append("老骨架存量稿豁免的缺段（本骨架无此段）：" + "、".join(soft_missing))
            if hard_missing:
                errors.append("源稿缺必备骨架段：" + "、".join(hard_missing)
                              + ("（其中 " + "、".join(body_only) + " 的内容出现在正文，但未做成段标题行）"
                                 if body_only else ""))
        else:
            print(f"  [1/4] 骨架段：{len(hit_names)}/{len(MUST_BLOCKS)} 全齐（按段标记行判定）✅")

        # 段标题体系（源稿 → 排版反向核对用）
        new_conv = ("招聘速览", "单位与岗位性质", "招什么人", "报考条件", "怎么报名")
        md_new_conv = sum(1 for k in new_conv if k in marks_blob)

        # ---------- 4. 数字门禁（本赛道专属） ----------
        # (a) 速览段必须同时出现岗位数与人数
        scale_hit = next((m for m in SCALE_MARKERS if m in md_text), None)
        if scale_hit:
            seg_start = md_text.index(scale_hit)
            seg = md_text[seg_start:seg_start + 700]
            has_job = re.search(r"\d+\s*个?岗", seg) is not None
            has_cnt = re.search(r"\d+\s*人", seg) is not None
            if not (has_job and has_cnt):
                _msg = (
                    f"【数字门禁】「{scale_hit}」段未同时出现岗位数与人数"
                    f"（岗位={'有' if has_job else '缺'}、人数={'有' if has_cnt else '缺'}）"
                    "——实例教训：09-24 南信大稿「招聘规模」格写'教学科研岗｜仅面试考核'，无任何数字"
                )
                # 老骨架稿降级为告警（该缺陷是真实存在的，仍要看见；但不阻塞存量稿）
                (warnings if is_legacy else errors).append(_msg)
            else:
                print(f"  [4/4] 数字门禁：「{scale_hit}」含岗位数＋人数 ✅")
        else:
            warnings.append("未找到速览/概览段（招聘速览 / 关键信息速览 / 招聘概要 / 数据三宫格），跳过数字门禁")

        # (b) 长期招聘形态必须出现「招满即止」
        if any(k in md_text for k in ("长期招聘", "不设开考比例")):
            if "招满即止" not in md_text:
                (warnings if is_legacy else errors).append(
                    "【数字门禁】源稿出现「长期招聘/不设开考比例」，但未写「招满即止」"
                    "——本条为窗口形态硬约束（instances.md §5）"
                )
            else:
                print("  [4/4] 数字门禁：长期招聘形态已带「招满即止」✅")
        else:
            print("  [4/4] 数字门禁：非长期招聘形态（无「招满即止」要求）✅")

    # ---------- 2. 排版 ----------
    if not os.path.exists(html_file):
        errors.append(f"缺少排版文件：{html_file}")
    else:
        with open(html_file, "r", encoding="utf-8") as f:
            html_text = f.read()

        if "max-width:677px" not in html_text.replace(" ", ""):
            errors.append("排版 HTML 缺桌面 677px 居中约束（首层根 section 需 max-width:677px; margin:0 auto）")
        else:
            print("  [2/4] 排版 677px 居中约束 ✅")

        opens = html_text.lower().count("<section")
        closes = html_text.lower().count("</section")
        if opens != closes:
            errors.append(f"<section> 开闭不配平：开 {opens} / 闭 {closes}（verify 查不出的经典污染）")
        else:
            print(f"  [2/4] <section> 配平：{opens}/{closes} ✅")

        if os.path.exists(dialect):
            r = subprocess.run([sys.executable, dialect, html_file],
                               capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            if "方言校验通过" in out:
                print("  [2/4] 微信原生方言校验 ✅")
            else:
                errors.append("微信原生方言校验未通过：\n" + out.strip()[:600])
        else:
            warnings.append("未找到 mp-html 方言检查器，跳过方言校验")

        # (G) 源稿 ↔ 排版 反向核对：源稿属新惯例稿但 HTML 无段标题体系 = 整段丢失
        if md_text and md_new_conv >= 3:
            html_new_conv = sum(1 for k in new_conv if k in html_text)
            if html_new_conv == 0:
                errors.append("【骨架】源稿有段标题体系，但排版 HTML 一个都没命中 → 疑整段组件丢失")
            elif html_new_conv < md_new_conv:
                warnings.append(f"排版 HTML 段标题命中 {html_new_conv} < 源稿 {md_new_conv}，疑有整段标题丢失")

        # ---------- 5. 红线词反向检查（源稿 + 排版都查） ----------
        hay = md_text + "\n" + re.sub(r"<[^>]+>", "", html_text)
        hit = [k for k in REDLINE_WORDS if k in hay]
        if hit:
            _m = ("【红线】命中已下线内容：" + "、".join(hit)
                  + "（防骗提醒/防骗声明/免责版权/下期预告 均已于 2026-09-28 全线下线，"
                    "见 job-write §七）")
            (warnings if is_legacy else errors).append(_m)
        else:
            print("  [红线] 反向检查：无命中 ✅")

    # ---------- 3. 封面 ----------
    if not os.path.exists(cover_file):
        errors.append(f"缺少封面文件：{cover_file}")
    else:
        try:
            from PIL import Image
            with Image.open(cover_file) as im:
                size, mode = im.size, im.mode
            if size != (900, 383):
                errors.append(f"封面尺寸应为 900×383，实测 {size[0]}×{size[1]}")
            elif mode != "RGB":
                errors.append(f"封面色彩模式应为 RGB，实测 {mode}（RGBA 推草稿会崩）")
            else:
                print("  [3/4] 封面 900×383 RGB ✅")
        except ImportError:
            warnings.append("未安装 Pillow，跳过封面校验（须用 venv python：~/workbuddy/binaries/python/envs/default/bin/python3）")
        except Exception as e:
            errors.append(f"封面读取失败：{e}")

    # ---------- 汇总 ----------
    for w in warnings:
        print(f"  ⚠️  {w}")
    if errors:
        print(f"\n❌ 未通过（{len(errors)} 项）：")
        for e in errors:
            print(f"  - {e}")
        return False
    print("\n✅ 四道门禁全绿。")
    print("⚠️  全绿 ≠ 可发：脚本不核事实。推前仍须人工做官方事实点覆盖率复核，"
          "并回官方原文逐条 count 检索正文每条硬信息（job-write §2.4 第六盲区）。")
    return True


def main():
    ap = argparse.ArgumentParser(description="school-write 教育系统成稿四门禁质检")
    ap.add_argument("target", nargs="?", help="稿件前缀或任一文件路径")
    ap.add_argument("--dir", dest="dir_", help="批量质检整个目录")
    args = ap.parse_args()

    prefixes = []
    if args.dir_:
        for f in sorted(glob.glob(os.path.join(args.dir_, "*-源稿.md"))):
            prefixes.append(f[: -len("-源稿.md")])
        if not prefixes:
            print(f"❌ 目录内未找到 *-源稿.md：{args.dir_}")
            return 2
    elif args.target:
        p = args.target
        for suf in ("-源稿.md", "-排版.html", "-封面.png"):
            if p.endswith(suf):
                p = p[: -len(suf)]
                break
        prefixes = [p]
    else:
        ap.print_help()
        return 2

    results = [verify_single(p) for p in prefixes]
    ok = sum(1 for r in results if r)
    print(f"\n{'='*56}\n合计 {len(results)} 篇：通过 {ok} / 未通过 {len(results)-ok}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
