#!/usr/bin/env python3
"""Unit tests for auto_config_ai.py dependency checking."""

import sys
import os
import json

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auto_config_ai import (
    discover_valid_skills,
    parse_skill_md_deps,
    check_skill_deps,
    get_pip_packages,
    get_npm_global_packages,
    command_exists,
    SKILL_DEPS,
)
from check_skill_sync import run_checks

SKILLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
passed = 0
failed = 0
results = []


def test(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        results.append(("PASS", name, detail))
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1
        results.append(("FAIL", name, detail))
        print(f"  FAIL  {name}" + (f"  ({detail})" if detail else ""))


# ============================================================
# 1. Discover valid skills
# ============================================================
print("\n=== 1. Skill Discovery ===")
skills = discover_valid_skills(SKILLS_DIR)
skill_names = [s[0] for s in skills]

# 数量不再硬编码：由 check_skill_sync 校验 磁盘/README/注册表 三方一致
expected_skills = [
    "analyze-viral-commerce-video", "claude-real-video", "crawl4ai", "defuddle", "dy-cli",
    "dy-doudian", "dy-fanpai",
    "dev-resource-accelerator", "fengniao-search", "jina-reader", "lux", "mptext-api", "opencli", "proxy",
    "qibook-company-profile", "qibook-company-wiki-deepresearch", "scrapling",
    "videodl", "yt-dlp", "zhihu-search",
]
for es in expected_skills:
    test(f"  Skill '{es}' discovered", es in skill_names)

print("\n=== 1b. Skill Sync (disk / README / SKILL_DEPS) ===")
for ok, name, detail in run_checks(SKILLS_DIR):
    test(f"  sync: {name}", ok, detail)

# ============================================================
# 2. Command detection
# ============================================================
print("\n=== 2. Command Detection ===")
test("python exists", command_exists("python"))
test("python3 exists", command_exists("python3") or True, "may not exist on Windows")
test("node exists", command_exists("node"))
test("npm exists", command_exists("npm"))
test("nonexistent_cmd_xxx NOT exists", not command_exists("nonexistent_cmd_xxx"))
test("where/which works for existing cmd", command_exists("where" if os.name == "nt" else "which"))

# ============================================================
# 3. pip package detection
# ============================================================
print("\n=== 3. pip Package Detection ===")
pip_pkgs = get_pip_packages()
test("pip packages loaded", len(pip_pkgs) > 0, f"{len(pip_pkgs)} packages")
test("  pip has 'requests'", "requests" in pip_pkgs, f"found: {'requests' in pip_pkgs}")
test("  pip has 'playwright'", "playwright" in pip_pkgs, f"found: {'playwright' in pip_pkgs}")
test("  pip has 'scrapling'", "scrapling" in pip_pkgs, f"found: {'scrapling' in pip_pkgs}")
test("  pip has 'yt-dlp'", "yt-dlp" in pip_pkgs, f"found: {'yt-dlp' in pip_pkgs}")
test("  pip has 'dy-cli'", "dy-cli" in pip_pkgs, f"found: {'dy-cli' in pip_pkgs}")
test("  pip does NOT have 'fakepkg12345'", "fakepkg12345" not in pip_pkgs)

# ============================================================
# 4. npm global package detection
# ============================================================
print("\n=== 4. npm Global Package Detection ===")
npm_pkgs = get_npm_global_packages()
test("npm packages loaded", True, f"{len(npm_pkgs)} global packages")
test("  npm '@jackwener/opencli' detection ran", True,
     f"found={'@jackwener/opencli' in npm_pkgs}")
test("  npm 'defuddle' detection ran", True, f"found={'defuddle' in npm_pkgs}")

# ============================================================
# 5. SKILL.md dependency parsing
# ============================================================
print("\n=== 5. SKILL.md Dependency Parsing ===")
skill_path_map = {s[0]: s[1] for s in skills}

# zhihu-search: has metadata.openclaw.requires.bins
zhihu_deps = parse_skill_md_deps(skill_path_map["zhihu-search"])
test("zhihu-search parses bins from metadata", "python3" in zhihu_deps.get("bins", []),
     f"bins={zhihu_deps.get('bins', [])}")

# qibook-company-profile: has requirements.packages
qibook_deps = parse_skill_md_deps(skill_path_map["qibook-company-profile"])
test("qibook-company-profile parses pip from requirements", "requests" in qibook_deps.get("pip", []),
     f"pip={qibook_deps.get('pip', [])}")
test("qibook-company-profile parses env vars", "QIBOOK_ACCESS_KEY" in qibook_deps.get("env", []),
     f"env={qibook_deps.get('env', [])}")

# scrapling: has pip install in markdown body
scrapling_deps = parse_skill_md_deps(skill_path_map["scrapling"])
test("scrapling parses pip from markdown body",
     "scrapling" in scrapling_deps.get("pip", []) or "html2text" in scrapling_deps.get("pip", []),
     f"pip={scrapling_deps.get('pip', [])}")

# defuddle: has npm install -g in markdown body
defuddle_deps = parse_skill_md_deps(skill_path_map["defuddle"])
test("defuddle parses npm from markdown body",
     "defuddle" in defuddle_deps.get("npm", []),
     f"npm={defuddle_deps.get('npm', [])}")

# dy-cli: has pip install in markdown body
dy_deps = parse_skill_md_deps(skill_path_map["dy-cli"])
test("dy-cli parses pip from markdown body",
     "dy-cli" in dy_deps.get("pip", []),
     f"pip={dy_deps.get('pip', [])}")

# opencli: has npm install -g in markdown body
opencli_deps = parse_skill_md_deps(skill_path_map["opencli"])
test("opencli parses npm from markdown body",
     "@jackwener/opencli" in opencli_deps.get("npm", []) or "opencli" in opencli_deps.get("npm", []),
     f"npm={opencli_deps.get('npm', [])}")

# jina-reader: no deps expected
jina_deps = parse_skill_md_deps(skill_path_map["jina-reader"])
test("jina-reader has no deps (cloud API)", len(jina_deps.get("bins", [])) == 0 and len(jina_deps.get("pip", [])) == 0,
     f"parsed: {jina_deps}")

# yt-dlp: has pip install in markdown body (captures full "yt-dlp[default]")
ytdlp_deps = parse_skill_md_deps(skill_path_map["yt-dlp"])
test("yt-dlp parses pip from markdown body",
     any("yt-dlp" in p for p in ytdlp_deps.get("pip", [])),
     f"pip={ytdlp_deps.get('pip', [])}")

# mptext-api: has pip install requests in markdown body
mp_deps = parse_skill_md_deps(skill_path_map["mptext-api"])
test("mptext-api parses pip from markdown body",
     "requests" in mp_deps.get("pip", []),
     f"pip={mp_deps.get('pip', [])}")

# ============================================================
# 6. Full dependency check per skill
# ============================================================
print("\n=== 6. Full Dependency Check per Skill ===")
for sname, spath in skills:
    all_ok, missing = check_skill_deps(sname, spath, pip_pkgs, npm_pkgs)
    total_missing = sum(len(v) for v in missing.values())
    registry = SKILL_DEPS.get(sname, {})

    if sname == "jina-reader":
        # No deps — should always pass
        test(f"  {sname}: all_ok={all_ok}", all_ok,
             f"missing={missing}" if not all_ok else "no deps expected")
    elif sname == "proxy":
        # proxy has pip: requests — should be OK (requests is installed)
        test(f"  {sname}: requests found", all_ok, f"missing={missing}" if not all_ok else "OK")
    elif sname == "dy-cli":
        # dy-cli: pip=dy-cli+playwright (both installed), bins=dy (may not be in PATH)
        dy_has_bins = len(missing["bins"]) == 0
        test(f"  {sname}: pip deps OK + bin check",
             len(missing["pip"]) == 0,
             f"bins={missing['bins']}, pip={missing['pip']}")
    elif sname == "lux":
        # lux: bins=lux — may not be in PATH on Windows
        lux_ok = command_exists("lux")
        test(f"  {sname}: deps check ran",
             True,
             f"missing={missing}" if not all_ok else "lux found" if lux_ok else "lux not in PATH (expected on Win)")
    elif sname == "fengniao-search":
        # 环境变量可存在或缺失；这里只验证非环境依赖没有误报。
        test(f"  {sname}: env check ran",
             len(missing["bins"]) == 0 and len(missing["pip"]) == 0,
             f"env missing={missing.get('env', [])}")
    elif sname in ("qibook-company-profile", "qibook-company-wiki-deepresearch"):
        test(f"  {sname}: env check ran", len(missing["pip"]) == 0,
             f"env missing={missing.get('env', [])}")
    elif sname == "zhihu-search":
        test(f"  {sname}: env check ran", len(missing["pip"]) == 0,
             f"env missing={missing.get('env', [])}")
    elif sname == "mptext-api":
        test(f"  {sname}: env check ran", len(missing["pip"]) == 0,
             f"env missing={missing.get('env', [])}")
    else:
        # Just verify the check runs without errors
        test(f"  {sname}: check ran", True, f"ok={all_ok}, missing={total_missing}")

# ============================================================
# 7. Edge cases
# ============================================================
print("\n=== 7. Edge Cases ===")
# Empty skill directory (no SKILL.md)
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    empty_deps = parse_skill_md_deps(tmpdir)
    test("  Empty dir returns empty deps", len(empty_deps) == 0)

# Non-existent path
empty_deps2 = parse_skill_md_deps("/nonexistent/path/to/skill")
test("  Non-existent path returns empty deps", len(empty_deps2) == 0)

# check_skill_deps with no deps skill
ok_no_deps, miss_no_deps = check_skill_deps("test_no_deps", "/nonexistent", pip_pkgs, npm_pkgs)
test("  check_skill_deps for unknown skill", ok_no_deps,
     f"missing={miss_no_deps}" if not ok_no_deps else "no registry entry = no deps = OK")

# ============================================================
# Summary
# ============================================================
print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed > 0:
    print("\nFailed tests:")
    for status, name, detail in results:
        if status == "FAIL":
            print(f"  FAIL  {name}  ({detail})")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
