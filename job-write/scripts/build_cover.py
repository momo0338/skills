#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「码上职业」封面生成器 —— 母版 + 左上角主体 Logo 胶囊（全专栏统一口径）

朱总 2026-09-17 定规：
  · **校招**（2027 届校园招聘 / A 线）→ 用 `标准校招封面母版.png`（主标题「2027 秋季校招开启」）
  · **社会招聘**（事业单位・高校编制招考 / B 线，以及企业社招）→ 用 `标准社招封面母版.png`（主标题「招聘通知」）

母版与胶囊规格（job-write §7.1~7.3，不得自创底版）：
  母版 900×383 ｜ 胶囊坐标 (40,32) ｜ 圆角 10 ｜ 内边距横 16 纵 8 ｜
  白底 rgba(255,255,255,240) ｜ 描边 1px #DCE6F2 ｜ logo 等比缩至高 42px（Lanczos）

用法：
  python3 build_cover.py --type 社招 --logo "../事业单位招考/素材/logos/njqxq.png" \\
                         --out  "../事业单位招考/待发布/xxx-封面.png"
"""
import argparse
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER_DIR = "/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/素材/封面母版"
local_master = os.path.normpath(os.path.join(HERE, "..", "素材", "封面母版"))
MASTER_DIR = local_master if os.path.exists(local_master) else DEFAULT_MASTER_DIR
MASTERS = {
    "校招": "标准校招封面母版.png",
    "社招": "标准社招封面母版.png",
}

CAP_X, CAP_Y = 40, 32
PAD_X, PAD_Y = 16, 8
RADIUS = 10
LOGO_H = 42
OUT_SIZE = (900, 383)


def build(kind, logo_path, out_path, master_path=None):
    master_path = master_path or os.path.join(MASTER_DIR, MASTERS[kind])
    master = Image.open(master_path).convert("RGBA")
    if master.size != OUT_SIZE:
        raise SystemExit(f"❌ 母版尺寸异常：{master.size}，应为 {OUT_SIZE}")

    out = master
    if logo_path:
        if not os.path.exists(logo_path):
            raise SystemExit(f"❌ logo 不存在：{logo_path}")
        logo = Image.open(logo_path).convert("RGBA")
        lw = int(round(LOGO_H * logo.width / logo.height))
        logo = logo.resize((lw, LOGO_H), Image.Resampling.LANCZOS)

        cap_w, cap_h = lw + PAD_X * 2, LOGO_H + PAD_Y * 2
        layer = Image.new("RGBA", master.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle([CAP_X, CAP_Y, CAP_X + cap_w, CAP_Y + cap_h],
                            radius=RADIUS, fill=(255, 255, 255, 240),
                            outline=(220, 230, 242, 255), width=1)
        layer.alpha_composite(logo, (CAP_X + PAD_X, CAP_Y + PAD_Y))
        out = Image.alpha_composite(master, layer)

    # ⚠️ 必须存 RGB：RGBA PNG 会在推草稿转 JPEG 时抛 cannot write mode RGBA as JPEG
    out.convert("RGB").save(out_path, "PNG")

    # 贴白底目检件：确认 logo 在浅底上不隐形（复盘踩过「纯白版 logo 贴白胶囊必隐形」）
    # 写到 /tmp，不污染稿件目录（待发布/ 只留交付三件套）
    prev = Image.new("RGB", OUT_SIZE, (255, 255, 255))
    prev.paste(out, (0, 0), out.split()[3])
    prev_path = os.path.join("/tmp", os.path.splitext(os.path.basename(out_path))[0] + "-白底目检.png")
    prev.save(prev_path)

    print(f"✅ 输出：{out_path}")
    print(f"   母版：{kind}（{os.path.basename(master_path)}）{OUT_SIZE}")
    if logo_path:
        print(f"   logo：{os.path.basename(logo_path)} → {lw}×{LOGO_H}｜"
              f"胶囊 ({CAP_X},{CAP_Y})-({CAP_X + cap_w},{CAP_Y + cap_h})｜"
              f"胶囊底 {(CAP_Y + cap_h) / OUT_SIZE[1] * 100:.0f}% 高度处")
    print(f"   目检件：{prev_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="码上职业封面生成器（母版 + Logo 胶囊）")
    ap.add_argument("--type", required=True, choices=list(MASTERS), help="校招 / 社招")
    ap.add_argument("--logo", default="", help="主体官方 logo PNG（可省，省则出纯母版）")
    ap.add_argument("--out", required=True, help="输出封面路径（.png）")
    ap.add_argument("--master", default="", help="自定义母版路径（一般不用）")
    a = ap.parse_args()
    build(a.type, a.logo, a.out, a.master or None)
