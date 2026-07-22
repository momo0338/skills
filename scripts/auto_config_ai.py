#!/usr/bin/env python3
"""
Momo Skills — 自动检测本机 AI 工具并配置技能共享
自动扫描系统中的 Claude Code、Gemini/Antigravity、Codex、Cursor、Windsurf、OpenClaw 等 AI 助手配置，
将本 repo 中的技能自动挂载/配置到各大 AI 助手中，实现全平台 AI 技能统一管理。

Usage:
  python3 scripts/auto_config_ai.py              # 自动检测并配置所有已安装的 AI 助手
  python3 scripts/auto_config_ai.py --dry-run    # 仅检测并预览将要执行的操作
  python3 scripts/auto_config_ai.py --skills-dir /path/to/skills # 指定技能仓库路径
"""

import sys
import os
import json
import argparse
import shutil

# 获取根技能目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKILLS_DIR = os.path.dirname(SCRIPT_DIR)
HOME_DIR = os.path.expanduser("~")

# 支持自动配置的 AI 工具目标列表
AI_TARGETS = [
    {
        "name": "Claude Code / Claude Agent",
        "detect_paths": [os.path.join(HOME_DIR, ".claude"), os.path.join(HOME_DIR, ".claude.json.backup")],
        "skills_dir": os.path.join(HOME_DIR, ".claude", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Google Gemini / Antigravity Agent",
        "detect_paths": [os.path.join(HOME_DIR, ".gemini"), os.path.join(HOME_DIR, ".antigravity-ide")],
        "skills_config_json": os.path.join(HOME_DIR, ".gemini", "config", "skills.json"),
        "skills_dir": os.path.join(HOME_DIR, ".gemini", "config", "skills"),
        "type": "gemini_config",
    },
    {
        "name": "OpenAI Codex Agent",
        "detect_paths": [os.path.join(HOME_DIR, ".codex")],
        "skills_dir": os.path.join(HOME_DIR, ".codex", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Cursor IDE",
        "detect_paths": [os.path.join(HOME_DIR, ".cursor"), os.path.join(HOME_DIR, ".cursorrules")],
        "skills_dir": os.path.join(HOME_DIR, ".cursor", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Windsurf IDE",
        "detect_paths": [os.path.join(HOME_DIR, ".codeium"), os.path.join(HOME_DIR, ".windsurfrules")],
        "skills_dir": os.path.join(HOME_DIR, ".codeium", "windsurf", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "OpenClaw Agent",
        "detect_paths": [os.path.join(HOME_DIR, ".openclaw")],
        "skills_dir": os.path.join(HOME_DIR, ".openclaw", "skills"),
        "type": "symlink_dir",
    },
]

def discover_valid_skills(skills_root):
    """扫描技能根目录下包含 SKILL.md 的有效技能目录"""
    skills = []
    if not os.path.exists(skills_root):
        return skills
        
    for entry in sorted(os.listdir(skills_root)):
        if entry.startswith(".") or entry in ["scripts", "data", "node_modules"]:
            continue
        skill_path = os.path.join(skills_root, entry)
        if os.path.isdir(skill_path) and os.path.exists(os.path.join(skill_path, "SKILL.md")):
            skills.append((entry, skill_path))
    return skills

def is_target_installed(target):
    """检查某个 AI 工具是否存在于本机"""
    for p in target.get("detect_paths", []):
        if os.path.exists(p):
            return True
    return False

def configure_symlink_dir(target_name, target_skills_dir, valid_skills, dry_run=False):
    """创建软链接共享技能到 AI 工具的技能目录"""
    print(f"\n📦 配置 {target_name} -> 技能目录: {target_skills_dir}")
    
    if not dry_run:
        os.makedirs(target_skills_dir, exist_ok=True)
        
    linked_count = 0
    for skill_name, skill_path in valid_skills:
        link_target = os.path.join(target_skills_dir, skill_name)
        
        if os.path.islink(link_target):
            existing_src = os.readlink(link_target)
            if existing_src == skill_path:
                print(f"  ✓ {skill_name} 已完成链接")
                linked_count += 1
                continue
            else:
                print(f"  🔄 更新软链接: {skill_name} -> {skill_path}")
                if not dry_run:
                    os.unlink(link_target)
        elif os.path.exists(link_target):
            print(f"  ⚠️ 已存在同名物理目录/文件: {skill_name}，跳过覆盖")
            continue
            
        if dry_run:
            print(f"  [DryRun] 创建软链接: {link_target} -> {skill_path}")
        else:
            try:
                os.symlink(skill_path, link_target)
                print(f"  ✨ 成功链接技能: {skill_name}")
                linked_count += 1
            except Exception as e:
                print(f"  ❌ 链接失败 {skill_name}: {e}")
                
    return linked_count

def configure_gemini(target_name, skills_json_path, target_skills_dir, skills_root, valid_skills, dry_run=False):
    """配置 Gemini / Antigravity 专用的 skills.json 自动识别"""
    print(f"\n📦 配置 {target_name} -> {skills_json_path}")
    
    # 1. 链接技能到 skills 目录
    configure_symlink_dir(target_name, target_skills_dir, valid_skills, dry_run=dry_run)
    
    # 2. 写入或更新 skills.json
    skills_json_dir = os.path.dirname(skills_json_path)
    if not dry_run:
        os.makedirs(skills_json_dir, exist_ok=True)
        
    current_config = {"entries": []}
    if os.path.exists(skills_json_path):
        try:
            with open(skills_json_path, "r", encoding="utf-8") as f:
                current_config = json.load(f)
        except Exception:
            pass
            
    entries = current_config.get("entries", [])
    already_has_root = any(entry.get("path") == skills_root for entry in entries if isinstance(entry, dict))
    
    if not already_has_root:
        entries.append({"path": skills_root})
        current_config["entries"] = entries
        if dry_run:
            print(f"  [DryRun] 将路径 {skills_root} 添加至 {skills_json_path}")
        else:
            try:
                with open(skills_json_path, "w", encoding="utf-8") as f:
                    json.dump(current_config, f, indent=2, ensure_ascii=False)
                print(f"  ✨ 成功更新 {skills_json_path} (全局索引)")
            except Exception as e:
                print(f"  ❌ 写入 {skills_json_path} 失败: {e}")
    else:
        print(f"  ✓ {skills_json_path} 已包含全局路径索引")

def main():
    parser = argparse.ArgumentParser(description="自动检测本机 AI 工具并配置技能共享")
    parser.add_argument("--dry-run", action="store_true", help="仅预览将执行的操作，不实际写文件或创建软链接")
    parser.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR, help="技能仓库根目录路径")
    
    args = parser.parse_args()
    skills_root = os.path.abspath(args.skills_dir)
    
    print("=" * 60)
    print("🤖 Momo Skills — 本机 AI 助手技能自动配置工具")
    print(f"📍 技能仓库根目录: {skills_root}")
    if args.dry_run:
        print("⚠️ [Dry-Run 模式] 仅输出检测与拟操作项，不会修改系统")
    print("=" * 60)
    
    valid_skills = discover_valid_skills(skills_root)
    print(f"\n🔍 扫描到 {len(valid_skills)} 个有效技能:")
    for sname, _ in valid_skills:
        print(f"  • {sname}")
        
    if not valid_skills:
        print("❌ 未扫描到有效的 SKILL.md 技能，终止配置。", file=sys.stderr)
        sys.exit(1)
        
    detected_count = 0
    configured_count = 0
    
    print("\n🔍 正在扫描本机已安装的 AI 助手/IDE 配置...")
    for target in AI_TARGETS:
        tname = target["name"]
        installed = is_target_installed(target)
        
        if installed:
            detected_count += 1
            print(f"✅ 检测到已安装: {tname}")
            
            ttype = target["type"]
            if ttype == "gemini_config":
                configure_gemini(
                    tname,
                    target["skills_config_json"],
                    target["skills_dir"],
                    skills_root,
                    valid_skills,
                    dry_run=args.dry_run
                )
                configured_count += 1
            elif ttype == "symlink_dir":
                configure_symlink_dir(
                    tname,
                    target["skills_dir"],
                    valid_skills,
                    dry_run=args.dry_run
                )
                configured_count += 1
        else:
            print(f"⚪ 未检测到: {tname}")
            
    print("\n" + "=" * 60)
    print(f"🎉 配置完成！共检测到 {detected_count} 个 AI 工具，已成功配置 {configured_count} 个 AI 助手环境。")
    print("各大 AI 助手现已共享本 repo 中所有技能！")
    print("=" * 60)

if __name__ == "__main__":
    main()
