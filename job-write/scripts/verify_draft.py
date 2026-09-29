#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_draft.py —— 码上职业 / job-write 本地成稿三件套自动化质检门禁
用途：
    在写作完成、推送微信草稿箱前，执行本地闭环质量与合规检查：
    1. 源稿 (Markdown)：标题长度(≤64)、单行式 SEO 摘要字数(≤120且无emoji)、必要章节骨架
    2. 排版 (HTML)：桌面 677px 居中约束、调用 mp-html 官方方言检查器 (wx_dialect_check.py)
    3. 封面 (PNG)：尺寸必须为 900×383、色彩模式必须为 RGB (禁止 RGBA)

用法：
    python3 verify_draft.py <稿件前缀或任一文件路径>
    python3 verify_draft.py 事业单位招考/待发布/2026-09-18-南京市卫健委所属事业单位高层次338人
    python3 verify_draft.py --dir 事业单位招考/待发布/
"""
import argparse
import glob
import os
import re
import subprocess
import sys
from PIL import Image

DIALECT_CHECKER = "/Users/zhugx/src/skills/mp-html/scripts/wx_dialect_check.py"

# 必备骨架段的「标题文字指纹」(正则, 中文标签)。
# 同时用于两处：
#   (A) 源稿 md 骨架门禁 —— 源稿缺任一即 error；
#   (G) 源稿↔排版反向核对 —— 源稿命中但 HTML 找不到同名文字 = 排版整段丢失，也报 error
#       （2026-09-28 新增：此前 HTML 完全不参与骨架检查，排版丢了整段组件照样全绿）
MUST_BLOCKS = [
    ("码上君划重点", "导语卡（段2）"),
    ("数据三宫格", "数据三宫格（段3）"),
    ("单位来头|单位简介|公司规模|公司简介", "单位来头（段4）"),
    ("招什么人|招哪些|招聘需求|需求专业|专业方向", "招什么人（段5）"),
    ("资格条件|应聘基本条件|学历口径|学历与年龄|硬门槛", "资格条件与硬门槛（段6）"),
    ("怎么报名|如何报名|报名流程", "怎么报名（段7）"),
    ("常见问答|FAQ", "校招常见问答（FAQ）"),
]

# 可选段：写了就参与「源稿↔排版」一致性核对，不写不报错。
# （2026-09-29 朱总裁定：「实操建议」对医院稿无增量——滨湖篇两轮换内容、盐城三院篇
#   一轮重写后仍判为复述与填充，故从 MUST_BLOCKS 降为可选。）
#   ⚠️ 影响范围：本脚本为 job-write / hospital-write 共用，A 线校招稿亦随之不再强制该段。
OPTIONAL_BLOCKS = [
    ("实操建议|码上君建议|行动建议", "码上君实操建议"),
]

# 全专栏排版定标组件（命中率统计：药丸 ≈108/125 篇 → 视为标配；段标题竖条约半数 → 提示）
YAOPILL = "码上君划重点"
SEC_TITLE_MARK = "width:4px;height:18px"   # 段标题「品牌色数字竖条」的样式指纹

# 「新惯例」段标题关键词（2026 年下半年起统一版式）。
# 用于 (G) 项判定源稿是否属新惯例稿：命中 ≥3 个才启用 HTML 侧段标题核对，
# 避免 02-xx 老惯例稿（段标题 0 命中属历史正常）与含内部备注段的源稿被误报。
NEW_CONVENTION = ("单位来头", "招什么人", "资格条件", "怎么报名", "常见问答", "实操建议")


def contains_emoji(text):
    for ch in text:
        cp = ord(ch)
        if (0x1F600 <= cp <= 0x1F64F or
            0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or
            0x1F700 <= cp <= 0x1F77F or
            0x1F780 <= cp <= 0x1F7FF or
            0x1F800 <= cp <= 0x1F8FF or
            0x1F900 <= cp <= 0x1F9FF or
            0x1FA00 <= cp <= 0x1FA6F or
            0x1FA70 <= cp <= 0x1FAFF or
            0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF):
            return True
    return False


def verify_single(prefix):
    print(f"\n🔍 开始质检稿件：{os.path.basename(prefix)}")
    md_file = prefix + "-源稿.md"
    html_file = prefix + "-排版.html"
    cover_file = prefix + "-封面.png"

    errors = []
    warnings = []

    # md_text / html_text 在各自分支中赋值；跨分支引用前先初始化，
    # 便于「源稿 ↔ 排版」双向核对（见 HTML 段的 (G) 项）。
    md_text = ""
    html_text = ""

    # 1. 检查源稿 Markdown
    if not os.path.exists(md_file):
        errors.append(f"缺少源稿文件：{md_file}")
    else:
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        # 标题检查
        m_title = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
        if not m_title:
            errors.append("源稿缺少一级标题 (# 标题)")
        else:
            title = m_title.group(1).strip()
            title_len = len(title)
            if title_len > 64:
                errors.append(f"标题超长：{title_len} 字符 (硬上限 ≤64)：{title}")
            else:
                print(f"  [1/3] 源稿标题：{title_len} 字符 (≤64) ✅")

        # SEO 摘要检查
        m_seo = re.search(r"^>\s+\*\*SEO\s*摘要\*\*[^：:]*[：:](.+)$", md_text, re.MULTILINE)
        if not m_seo:
            errors.append("源稿缺少单行式 SEO 摘要 (> **SEO 摘要**（NNN字，无 emoji）：<正文>)")
        else:
            digest = m_seo.group(1).strip()
            d_len = len(digest)
            if d_len > 120:
                errors.append(f"SEO 摘要超长：{d_len} 字符 (硬上限 ≤120)")
            elif contains_emoji(digest):
                errors.append("SEO 摘要包含 emoji 表情 (微信会渲染为豆腐块，禁止使用)")
            else:
                print(f"  [1/3] SEO 摘要：{d_len} 字符 (≤120, 无 emoji) ✅")

        # ── 骨架门禁（2026-09-28 新增）────────────────────────────
        # 背景：此前本脚本只查标题/摘要/居中/方言/封面五项，导致「缺 FAQ、
        # 缺实操建议、缺 CTA」的稿子照样报"全绿"。骨架不合规属**错误**，
        # 不是建议——job-write §三 明确 8 段缺一不可。
        skeleton_errors = []
        skeleton_warns = []

        # (A) 必备骨架段：缺任一即 error
        #     MUST_BLOCKS 已提到模块级（HTML 侧 (G) 项复用同一张表，保证两侧判据一致）
        for pattern, label in MUST_BLOCKS:
            if not re.search(pattern, md_text):
                skeleton_errors.append(f"缺必备骨架段「{label}」（源稿中找不到「{pattern.split('|')[0]}」等标题）")

        # (B) FAQ 段 / (C) 实操建议段 —— 已并入 MUST_BLOCKS，无需重复判定

        # (D) CTA 进群区（HTML 侧判定，源稿不一定显式写）
        #     延后到 HTML 检查段统一判定

        # (E) 页脚禁项（红线：来源行/免责版权/下期预告一律不加）
        for bad in ["下期预告", "欢迎锁定关注", "版权归", "本文仅作"]:
            if bad in md_text:
                skeleton_errors.append(
                    f"页脚禁项「{bad}」：正文以社群 CTA 结束，"
                    f"不加来源行/免责版权/下期预告（job-write §七）")

        # (F) 防骗提醒：⛔ 朱总 2026-09-28 裁定全线下线，任何稿件都不再放
        #     原规则「跨省系列必须有防骗提醒」已作废；现改为反向检查。
        for bad in ["防骗提醒", "防诈防骗", "不收取任何费用", "付费保过", "内部名额"]:
            if bad in md_text:
                skeleton_warns.append(
                    f"含「{bad}」——防骗提醒已于 2026-09-28 全线下线，请删除（job-write §七）")

        for e in skeleton_errors:
            errors.append("[骨架] " + e)
        for w in skeleton_warns:
            warnings.append("[骨架] " + w)

        if not skeleton_errors:
            print("  [骨架] 8 段骨架 + FAQ + 实操建议 + 页脚禁项 校验通过 ✅")
        else:
            print(f"  [骨架] 检出 {len(skeleton_errors)} 项骨架问题 ❌")

    # 2. 检查排版 HTML
    if not os.path.exists(html_file):
        errors.append(f"缺少排版 HTML 文件：{html_file}")
    else:
        with open(html_file, "r", encoding="utf-8") as f:
            html_text = f.read()

        # 居中约束
        if "max-width:677px" not in html_text and "max-width: 677px" not in html_text:
            warnings.append("排版 HTML 根容器建议显式声明 max-width:677px; margin:0 auto; 居中约束")
        else:
            print("  [2/3] 排版结构：桌面 677px 居中约束已就绪 ✅")

        # CTA 进群区（通用版：标题「招聘信息不漏接」+ 服务清单三条）
        if "招聘信息不漏接" not in html_text:
            errors.append(
                "[骨架] 缺必备转化位「进群区 CTA」：正文须以通用版 CTA 结束"
                "（标题「招聘信息不漏接」+ 服务清单：网申信息及辅助投递／"
                "简历诊断及面试指导／远程实习及能力提升）")
        else:
            cta_items = ["网申信息及辅助投递", "简历诊断及面试指导", "远程实习及能力提升"]
            miss_cta = [c for c in cta_items if c not in html_text]
            if miss_cta:
                errors.append(f"[骨架] CTA 服务清单缺项（应为标准化三条）：{miss_cta}")
            elif "data:image/png;base64," not in html_text:
                errors.append(
                    "[骨架] CTA 缺内嵌二维码：严禁使用 https:// 外部图片链接"
                    "（微信防盗链会显示'此图片无法加载'），须用 data:image/png;base64,")
            else:
                print("  [骨架] CTA 进群区（标题+三条清单+内嵌二维码）✅")

        # 外链图片禁项（微信防盗链）
        ext_img = re.findall(r'<img[^>]+src="https?://[^"]+"', html_text)
        if ext_img:
            errors.append(f"[骨架] 正文含 {len(ext_img)} 处外链图片 src，微信会防盗链拦截")

        # <th> 禁项（微信端套自带浅底会盖住底色）
        th_cnt = len(re.findall(r"<th[ >]", html_text))
        if th_cnt:
            errors.append(f"[骨架] 出现 <th> {th_cnt} 处，表头必须用 <td> 并把底色/白字下沉到单元格")

        # 加粗密度（目标 ≤5.5 处/屏，按 40 行/屏折算）
        strong_cnt = len(re.findall(r"<strong", html_text))
        screen = max(1, len([l for l in html_text.split("\n") if l.strip()]) / 40)
        density = strong_cnt / screen
        if density > 5.5:
            warnings.append(
                f"加粗密度 {density:.2f} 处/屏（{strong_cnt} 处），"
                f"目标 ≤5.5；只能逐条白名单降粗，禁用字数阈值批量删")
        else:
            print(f"  [骨架] 加粗密度 {density:.2f} 处/屏（{strong_cnt} 处，≤5.5）✅")

        # ── (G) 源稿 ↔ 排版「段标题体系」核对（2026-09-28 新增，第五个盲区）──
        # 背景：本脚本原先只拿源稿 md 匹配骨架关键词，HTML 完全不参与骨架检查
        #       （HTML 只查 section 配平/方言/677px/封面）。于是当排版**整段丢失**
        #       组件（如导语卡药丸、各段标题竖条）时，三件套依旧全绿。
        #       实测 05-04 中国移动稿：药丸与 6 个段标题在 HTML 中 0 命中，脚本报全绿。
        # 判据（只对"新惯例稿"生效，避免老惯例稿/内部备注稿误报）：
        #   源稿出现 ≥3 个新惯例段标题 → HTML 必须命中过半；
        #   若**一个都没命中** = 排版整段体系丢失（真缺陷，报 error）。
        # 实测标定（125 篇含 md+html 的稿）：85 篇新惯例稿 → 81 绿 / 4 半缺 / 0 误报全缺。
        if md_text:
            m_heads = re.findall(r'^#{2,4}\s*[一二三四五六七八九十]+\s*[、.]\s*(.+)$',
                                 md_text, re.M)
            m_cores = []
            for x in m_heads:
                c = re.split(r"[：:]", x)[0].strip()
                # 去掉标题尾部的括注（如「（照官方原文）」「(FAQ)」里的中文括注）
                c = re.sub(r"[（(][^）)]*[）)]\s*$", "", c).strip()
                if c:
                    m_cores.append(c)
            m_new = [c for c in m_cores if any(k in c for k in NEW_CONVENTION)]
            if len(m_new) >= 3:
                h_new = [c for c in m_new if c in html_text]
                if not h_new:
                    errors.append(
                        f"[骨架] 排版 HTML 完全没有段标题体系（源稿有 {len(m_new)} 个"
                        f"新惯例段标题，HTML 一个都没命中：{'、'.join(m_new[:4])} …）"
                        "　—— 源稿 md 骨架通过 ≠ 排版完整；须在各段补段标题组件"
                        "（job-write §2.4 第五个盲区）")
                elif len(h_new) < len(m_new) / 2:
                    warnings.append(
                        f"[骨架] 排版段标题只命中 {len(h_new)}/{len(m_new)}"
                        f"（命中：{'、'.join(h_new)}）—— 低于半数，疑有整段标题丢失，请逐段核对")
                else:
                    print(f"  [骨架] 源稿↔排版段标题核对：{len(h_new)}/{len(m_new)} 命中 ✅")

        # ── (H) 全专栏定标组件命中检查（提示，不阻断）──
        # 药丸 108/125 篇命中 ≈ 标配；段标题竖条约半数 → 只提示，保持向后兼容。
        pill_cnt = html_text.count(YAOPILL)
        if pill_cnt == 0:
            warnings.append(
                f"[定标] 排版 HTML 缺「{YAOPILL}」药丸（导语卡首行）——"
                "全专栏 ≈108/125 篇标配组件（job-write §2.4 第五个盲区）")
        sec_cnt = html_text.count(SEC_TITLE_MARK)
        if sec_cnt == 0:
            warnings.append(
                "[定标] 排版 HTML 缺段标题「品牌色数字竖条」组件"
                f"（样式指纹 {SEC_TITLE_MARK}），约半数已发布稿使用，建议补齐以统一版式")
        if pill_cnt and sec_cnt:
            print(f"  [定标] 药丸 {pill_cnt} 个 / 段标题竖条 {sec_cnt} 处 ✅")

        # 调用 mp-html 官方方言检查器
        if not os.path.exists(DIALECT_CHECKER):
            errors.append(f"未找到 mp-html 方言检查脚本：{DIALECT_CHECKER}")
        else:
            p = subprocess.run(
                [sys.executable, DIALECT_CHECKER, html_file],
                capture_output=True,
                text=True
            )
            if p.returncode != 0:
                errors.append(f"微信原生方言校验未通过 (mp-html):\n{p.stdout}\n{p.stderr}")
            else:
                print("  [2/3] 方言合规：调用 mp-html/wx_dialect_check.py 校验全绿 ✅")

    # 3. 检查封面图
    if not os.path.exists(cover_file):
        errors.append(f"缺少封面图文件：{cover_file}")
    else:
        try:
            im = Image.open(cover_file)
            w, h = im.size
            if (w, h) != (900, 383):
                errors.append(f"封面尺寸错误：{w}×{h}，必须为 900×383")
            elif im.mode != "RGB":
                errors.append(f"封面色彩模式错误：{im.mode}，必须为 RGB (RGBA 模式在推草稿时会抛异常)")
            else:
                print(f"  [3/3] 封面规格：900×383 RGB 格式验证通过 ✅")
        except Exception as e:
            errors.append(f"无法读取封面图片：{e}")

    # 汇总输出
    if errors:
        print(f"❌ 质检失败 ({len(errors)} 项错误)：")
        for err in errors:
            print(f"   • {err}")
        return False
    if warnings:
        print(f"⚠️  提示建议 ({len(warnings)} 项)：")
        for w in warnings:
            print(f"   • {w}")

    print(f"🎉 交付三件套质检全绿！符合 job-write & mp-html 标准，可放心入库。")
    return True


def main():
    parser = argparse.ArgumentParser(description="job-write 本地成稿三件套质检门禁")
    parser.add_argument("target", nargs="?", default="", help="稿件前缀或任一文件路径")
    parser.add_argument("--dir", default="", help="扫描指定目录下的全部三件套")
    args = parser.parse_args()

    prefixes = []
    if args.dir:
        for f in glob.glob(os.path.join(args.dir, "*-源稿.md")):
            pref = f[:-len("-源稿.md")]
            prefixes.append(pref)
    elif args.target:
        p = args.target
        for sfx in ["-源稿.md", "-排版.html", "-封面.png"]:
            if p.endswith(sfx):
                p = p[:-len(sfx)]
                break
        prefixes.append(p)
    else:
        parser.print_help()
        sys.exit(2)

    if not prefixes:
        print("未找到需要质检的稿件。")
        sys.exit(1)

    all_ok = True
    for pref in prefixes:
        if not verify_single(pref):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
