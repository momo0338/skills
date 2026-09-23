#!/usr/bin/env bash
# 模板来源：满爸爱生活项目 工具/check_env.sh（真实可用样例，2026-09-23，0.87s 跑完）
# 使用时按项目替换第 2/3/7 节的检查项。硬要求：纯只读、10 秒内、不用 emoji、末尾给结论。

#!/usr/bin/env bash
# check_env.sh — 满爸爱生活工作区 · 环境自检
# 用途：任何 AI 接手本项目时的第一步。纯只读，10 秒内出结果。
# 用法：bash 工具/check_env.sh
# 输出：[OK] 正常 ｜ [WARN] 需注意（多半不影响离线任务）｜ [FAIL] 阻塞，必须先修

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$HOME/.workbuddy/skills"
SRC_SKILLS="$HOME/src/skills"
PY="/Users/zhugx/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

OK=0; WARN=0; FAIL=0
ok()   { printf '  [OK]   %s\n' "$1"; OK=$((OK+1)); }
warn() { printf '  [WARN] %s\n' "$1"; WARN=$((WARN+1)); }
fail() { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL+1)); }
head_() { printf '\n%s\n' "── $1 ──"; }

printf '满爸爱生活 · 环境自检\n'
printf '工作区: %s\n' "$ROOT"
printf '时间:   %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"

# ─────────────────────────────────────────────
head_ "1. 运行时"
if [ -x "$PY" ]; then
  ok "Python $("$PY" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null) → $PY"
else
  fail "托管 Python 不存在: $PY（见工作区 AGENTS.md 的运行时约定）"
fi

# ─────────────────────────────────────────────
head_ "2. 技能依赖（软链接 → src/skills 正本）"
for s in mp-ops mp-publish mp-html mp-search geomap guide-write competition-write job-write; do
  link="$SKILLS/$s"
  if [ -L "$link" ]; then
    tgt="$(readlink "$link")"
    if [ -e "$link" ]; then ok "$s → $tgt"; else fail "$s 软链接悬空 → $tgt（正本丢失）"; fi
  elif [ -d "$link" ]; then
    warn "$s 是真实目录而非软链接（约定应为 $SRC_SKILLS/$s 的软链接）"
  else
    fail "$s 未安装（应为 $SRC_SKILLS/$s 的软链接）"
  fi
done

# ─────────────────────────────────────────────
head_ "3. mp-ops 脚本完整性"
OPS="$SKILLS/mp-ops"
for f in refresh_publish_records publish_records_analysis search_analysis search_fetch \
         generate_report publish_archive_reconcile fetch_published_archive; do
  if [ -f "$OPS/scripts/$f.py" ]; then ok "$f.py"; else fail "$f.py 缺失"; fi
done
if [ -f "$OPS/assets/echarts.min.js" ]; then
  ok "echarts.min.js（报告图表必须内联，勿改 CDN）"
else
  fail "mp-ops/assets/echarts.min.js 缺失 → HTML 报告会整页空白"
fi

# ─────────────────────────────────────────────
head_ "4. 环境变量"
if [ -n "$GZH_WORK_DIR" ]; then
  if [ "$GZH_WORK_DIR" = "$ROOT" ]; then ok "GZH_WORK_DIR=$GZH_WORK_DIR"; else warn "GZH_WORK_DIR 指向别处: $GZH_WORK_DIR"; fi
else
  warn "GZH_WORK_DIR 未设置 → 跑 mp-ops 前请 export GZH_WORK_DIR=\"$ROOT\""
fi
if [ -n "$GZH_VAULT" ]; then ok "GZH_VAULT=$GZH_VAULT"; else warn "GZH_VAULT 未设置 → export GZH_VAULT=\"$HOME/codeup/obsidian\"（归档 git mv 需要）"; fi

# ─────────────────────────────────────────────
head_ "5. 微信凭据与登录态"
CFG="$HOME/.config/weixin"
if [ -f "$CFG/profiles.json" ]; then
  ok "profiles.json 存在"
  if [ -f "$CFG/profiles/manba/appid" ] && [ -f "$CFG/profiles/manba/appsecret" ]; then
    ok "manba（满爸爱生活）AppID/Secret 就位"
  else
    fail "manba profile 凭据不全（$CFG/profiles/manba/）"
  fi
  [ -f "$CFG/profiles/mashang/appid" ] && ok "mashang（码上职业）凭据就位" || warn "mashang profile 未配置（招聘号用）"
else
  warn "未找到 $CFG/profiles.json → 推草稿箱不可用；离线分析与写作不受影响"
fi

# ─────────────────────────────────────────────
head_ "6. 数据缓存"
CACHE="$HOME/.cache/weixin/publish_records"
if [ -d "$CACHE" ]; then
  n=$(ls "$CACHE" 2>/dev/null | wc -l | tr -d ' ')
  latest=$(ls -t "$CACHE" 2>/dev/null | head -1)
  ok "publish_records 缓存 $n 份，最新: $latest"
else
  warn "无 $CACHE → 首次跑 refresh_publish_records.py 会创建（需登录态）"
fi

# ─────────────────────────────────────────────
head_ "7. 关键文档"
for f in "AGENTS.md" "交接文档-满爸爱生活.md" "已发文章索引-满爸爱生活.md" \
         "运营/00-运营总览.md" "运营/运营日历-2026.md" "运营/数据结论与运营指引.md" \
         "运营/公众号平台规则与成稿规范-2026.md"; do
  if [ -f "$ROOT/$f" ]; then ok "$f"; else fail "$f 缺失"; fi
done
csv=$(ls -t "$ROOT"/发表记录*.csv 2>/dev/null | head -1)
if [ -n "$csv" ]; then ok "最新发表记录: $(basename "$csv")"; else fail "无 发表记录*.csv（分析脚本无从取数）"; fi

# ─────────────────────────────────────────────
head_ "8. 版本控制"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  dirty=$(git -C "$ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  branch=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
  toplevel=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null)
  ok "git 仓库（分支 $branch），未提交改动 $dirty 项"
  if [ "$toplevel" = "$ROOT" ]; then
    ok "本目录就是仓库根: $toplevel"
  else
    warn "仓库根是 $toplevel（本目录只是子目录）→ 索引路径需带 './' 前缀，且 status 会连带旁支改动（见 交接文档 §8.3）"
  fi
  [ "$dirty" -gt 50 ] && warn "未提交改动较多（$dirty）→ 动手前先确认工作区状态，避免覆盖他人产出"
else
  warn "非 git 仓库或 git 不可用 → 归档勾稽的 git mv 会失败"
fi

# 中秋窗口提醒（时效性），仅在有该稿时提示
if git -C "$ROOT" status --porcelain 2>/dev/null | grep -q "中秋"; then
  warn "检测到『中秋』相关文件有未提交/待处理状态 → 见 交接文档 §0 告警，中秋 9/25–27 窗口迫近"
fi

# ─────────────────────────────────────────────
printf '\n════════════════════════════════════\n'
printf '结论: %d 项正常, %d 项注意, %d 项阻塞\n' "$OK" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '→ 有阻塞项，先按上述 [FAIL] 修复。详见 交接文档 §12。\n'; exit 1
elif [ "$WARN" -gt 0 ]; then
  printf '→ 无阻塞。离线任务（分析/写作/排版）可直接开工；带登录态的任务需先补上 [WARN] 项。\n'; exit 0
else
  printf '→ 全绿，可以开工。\n'; exit 0
fi
