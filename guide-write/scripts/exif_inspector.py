#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
exif_inspector.py: 批量提取实拍图片的 EXIF 真实拍摄日期（DateTimeOriginal）
用于写稿前核实真实实拍日，彻底防止把文件名中的导入日期当成拍摄日写入图注与导语。

支持格式: .jpg/.jpeg/.png/.webp（PIL 原生）
          .heic（iPhone 实拍常见，PIL 原生不识别，需额外安装 pillow-heif：
                 /Users/zhugx/.workbuddy/binaries/python/envs/default/bin/pip install pillow-heif
                 未安装时脚本会明确提示“需安装 pillow-heif”，不会误报“文件损坏”）
"""

import os
import sys
from pathlib import Path
from PIL import Image, ExifTags

# HEIC 依赖（iPhone 实拍常见格式，PIL 原生不识别）
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False


def get_exif_date(image_path: str) -> str:
    """提取单张图片的 EXIF DateTimeOriginal"""
    if os.path.splitext(image_path)[1].lower() == ".heic" and not HEIF_AVAILABLE:
        return "读取失败: HEIC 需安装 pillow-heif（pip install pillow-heif）后重试"
    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if not exif:
                return "无 EXIF (非自摄或已压缩)"
            
            # 找到 DateTimeOriginal 标签 (36867)
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag == "DateTimeOriginal":
                    return str(value)
                
            # 退而求其次取 DateTime (306)
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag == "DateTime":
                    return f"{value} (DateTime)"
                    
            return "无拍摄时间戳"
    except Exception as e:
        return f"读取失败: {e}"


def inspect_directory(dir_path: str):
    """遍历目录下所有图片文件并打印核验表"""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
    p = Path(dir_path)
    
    if not p.exists():
        print(f"❌ 目录不存在: {dir_path}", file=sys.stderr)
        sys.exit(1)
        
    image_files = sorted([f for f in p.iterdir() if f.suffix.lower() in exts])
    
    if not image_files:
        print(f"⚠️ 目录下未找到支持的图片文件: {dir_path}")
        return

    print("=" * 80)
    print(f"📸 EXIF 实拍日期批量审计: {dir_path} (共 {len(image_files)} 张)")
    print("=" * 80)
    print(f"{'文件名':<40} | {'EXIF 真实拍摄时间':<25} | {'判定建议'}")
    print("-" * 80)

    for img in image_files:
        date_str = get_exif_date(str(img))
        
        # 建议判断
        if "无 EXIF" in date_str:
            advice = "需标明图源（非自摄/网图）"
        elif "HEIC 需安装" in date_str:
            advice = "装 pillow-heif: pip install pillow-heif"
        elif "读取失败" in date_str:
            advice = "检查文件损坏"
        else:
            # 格式例如: 2026:04:18 14:40:22 -> 2026年4月18日
            clean_date = date_str.split()[0].replace(":", "-")
            advice = f"图注标准日期: {clean_date}"
            
        print(f"{img.name:<40} | {date_str:<25} | {advice}")
    print("=" * 80)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 exif_inspector.py <图片目录或文件路径>")
        sys.exit(1)
        
    target = sys.argv[1]
    if os.path.isfile(target):
        print(f"{os.path.basename(target)}: {get_exif_date(target)}")
    else:
        inspect_directory(target)


if __name__ == "__main__":
    main()
