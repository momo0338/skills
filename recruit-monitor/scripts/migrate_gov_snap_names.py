#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_gov_snap_names.py — gov 线快照 JSON 批量改名（可读命名）

背景（2026-09-30）：
  用户看到 `snapshots/gov/` 里全是 `a1b2c3d4e5f6.json` 这种 hash 名，人工完全无法辨识，
  要求改成「一眼能看出是哪个站」的命名。实测 181 个监测源：
    纯域名 → 153 唯一（25 组碰撞，⛔ 不可用）
    域名+完整路径 → 178 唯一（3 组碰撞）
    协议+域名+完整路径 → 180 唯一（1 组碰撞）
    ＋8 位 hash 后缀 → **181/181 全唯一**
  故定规则：`<协议>.<域名>.<路径各段>.<md5前8位>.json`（**域名保持原样，不拆点**，
  这样 `ls` 一眼能读出 `changshu.gov.cn` 这个域，而不是 `changshu_gov_cn`）
  例：`https.www.changshu.gov.cn.zgcs.c101275.list.shtml.0e4b3833.json`

  ⚽ 为何用点号而非下划线（2026-09-30 实测二选一，181 源全量对比）：
     唯一性 180/181 相同、最长文件名 98 bytes 相同、隐藏文件/连续点/结尾点风险均为 0，
     唯一差别是人眼可读性 —— 域名是否被拆散。选点号保留域名完整形态。

⛔ 关键纪律（照 §十一「改名必须带迁移」）：
  1. **按 JSON 内部 `url` 字段算新名**，⛔ 绝不按旧文件名算。
     实测存在 `丹阳市教育局.json` 里存着人社局 `dyrsj` 域名内容的历史错配。
  2. 同名目标已存在 → **跳过，不覆盖**（新格式那份更新，优先留）。
  3. **不删除任何文件**（只 copy 出新名；旧名保留由 --prune 显式控制，默认不删）。
  4. 必须支持 `--dry-run` 预览。
  5. 改完必须验证：181 个当前源全部能命中基线，且「本次新增」diff 恢复。

用法：
  python3 migrate_gov_snap_names.py --dry-run          # 只打印计划
  python3 migrate_gov_snap_names.py --apply            # 实际生成新名文件（旧名保留）
  python3 migrate_gov_snap_names.py --apply --prune    # 生成后删除旧名文件（⚠️ 需已验证）
  python3 migrate_gov_snap_names.py --verify           # 只校验当前源能否命中基线
"""
import argparse, glob, hashlib, json, os, re, shutil, sys
from collections import defaultdict
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(BASE, "snapshots", "gov")
XLSX = os.path.join(os.path.dirname(BASE), "单位与招聘信息总表.xlsx")

HASH_LEN = 8
# 允许：ASCII 字母数字、点、连字符、中文（便于「南京市」这类可读片段）
_UNSAFE = re.compile(r"[^0-9A-Za-z一-鿿._-]+")


def _clean_seg(s):
    """单个 URL 片段 → 文件名安全片段。⛔ 不动点（`index.shtml` 的点要保留，否则人眼读不出扩展名）。"""
    s = unquote(s)
    s = s.replace("%", "pct")
    s = _UNSAFE.sub("_", s)
    return re.sub(r"_{2,}", "_", s).strip("_")


def readable_name(url, hash_len=HASH_LEN):
    """URL → 可读快照文件名（不含 .json）。⛔ 必须与 gov_recruit_monitor.snap_path 逐字一致。"""
    p = urlparse(url)
    scheme = "http" if p.scheme == "http" else "https"
    host = p.netloc                      # 域名原样，保留点，人眼可读
    segs = [_clean_seg(x) for x in p.path.split("/") if x]
    path = ".".join(s for s in segs if s) or "root"
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:hash_len]
    return f"{scheme}.{host}.{path}.{h}"


def target_path(url, snap_dir=SNAP_DIR, hash_len=HASH_LEN):
    return os.path.join(snap_dir, readable_name(url, hash_len) + ".json")


def load_current_urls():
    """从 xlsx 读当前监测源 URL（与巡检脚本同一数据源，只读）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "govmon", os.path.join(BASE, "gov_recruit_monitor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return [t["url"] for t in m.TARGETS]


def collect(snap_dir=SNAP_DIR):
    """扫描现有快照 → [(旧路径, 内部 url, 新路径)]，跳过 url 缺失/损坏的文件。"""
    out, bad = [], []
    for p in sorted(glob.glob(os.path.join(snap_dir, "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            bad.append((p, "解析失败: %s" % e))
            continue
        u = d.get("url")
        if not u:
            bad.append((p, "无 url 字段"))
            continue
        out.append((p, u, target_path(u, snap_dir)))
    return out, bad


def _fetched_at(path):
    try:
        return json.load(open(path, encoding="utf-8")).get("fetched_at", "") or ""
    except Exception:
        return ""


def plan(snap_dir=SNAP_DIR):
    """产出迁移计划。

    🔴 判定必须分三类，⛔ 不可混为一谈（2026-09-30 实测：369 份文件只对应 188 个唯一 URL）：
      ① dup  —— 同一 URL 存在多份历史快照（09-29 中文名旧档 + 09-30 md5 新档并存），
                这是「改了命名规则没迁移存量」留下的冗余，保留 fetched_at 最新那份；
      ② real —— 同一新名下有【不同】URL = 真碰撞，⛔ 必须报错不处理；
      ③ rename —— 需要改名的文件。
    第一版把 ① 当 ② 报「174 组冲突」是误判 —— 真碰撞应为 0 组。
    """
    rows, bad = collect(snap_dir)
    by_new = defaultdict(list)
    for old, url, new in rows:
        by_new[new].append({"old": old, "url": url, "at": _fetched_at(old)})

    same = [r for r in rows if os.path.abspath(r[0]) == os.path.abspath(r[2])]
    rename = [r for r in rows if os.path.abspath(r[0]) != os.path.abspath(r[2])]

    dup_groups = {n: v for n, v in by_new.items() if len(v) > 1}
    real_coll = {n: v for n, v in dup_groups.items() if len({x["url"] for x in v}) > 1}
    stale = []
    for n, v in dup_groups.items():
        if len({x["url"] for x in v}) > 1:
            continue
        v2 = sorted(v, key=lambda x: x["at"])
        for x in v2[:-1]:
            stale.append((x["old"], n, x["at"]))
    exists_other = [(o, n) for o, u, n in rename if os.path.exists(n)]
    return {
        "total": len(rows), "same": same, "rename": rename,
        "conflict": real_coll, "dup_groups": dup_groups, "stale": stale,
        "exists_other": exists_other, "bad": bad,
    }


def cmd_dryrun(pl, verbose):
    urls_all = {u for o, u, n in pl["rename"]} | {u for o, u, n in pl["same"]}
    print("=== DRY-RUN：不会写任何文件 ===")
    print("扫描快照        ：%d 份" % pl["total"])
    print("唯一 URL        ：%d 个" % len(urls_all))
    print("已符合新命名    ：%d 份" % len(pl["same"]))
    print("需改名          ：%d 份" % len(pl["rename"]))
    print("目标已存在      ：%d 份（将跳过，不覆盖）" % len(pl["exists_other"]))
    print("真碰撞          ：%d 组  ⛔ 必须为 0" % len(pl["conflict"]))
    print("同 URL 多份遗留 ：%d 组（冗余 %d 份，取 fetched_at 最新）"
          % (len(pl["dup_groups"]) - len(pl["conflict"]), len(pl["stale"])))
    print("损坏/无 url     ：%d 份" % len(pl["bad"]))
    for p, why in pl["bad"]:
        print("   ⚠️  %s  ← %s" % (os.path.basename(p), why))
    for n, v in pl["conflict"].items():
        print("   ❌ 真碰撞 %s" % os.path.basename(n))
        for x in v:
            print("        ← %s  (%s)" % (os.path.basename(x["old"]), x["url"]))
    if verbose:
        print("\n--- 逐条改名计划（前 40 条）---")
        for old, url, new in pl["rename"][:40]:
            print("%-32s → %s" % (os.path.basename(old)[:32], os.path.basename(new)))
        if len(pl["rename"]) > 40:
            print("… 共 %d 条" % len(pl["rename"]))
    else:
        print("\n（加 --verbose 看逐条计划）")


def cmd_apply(pl, prune, snap_dir=SNAP_DIR):
    did, skipped, failed = 0, 0, []
    # 同 URL 多份时，只从 fetched_at 最新那份生成新名（⛔ 不用旧档，避免把过期基线写成现行基线）
    keep_path = {}
    for n, v in pl["dup_groups"].items():
        keep_path[n] = sorted(v, key=lambda x: x["at"])[-1]["old"]
    for old, url, new in pl["rename"]:
        src = keep_path.get(new, old)
        if os.path.abspath(src) != os.path.abspath(old):
            continue                      # 旧档，交给 stale 清理
        if os.path.exists(new):
            skipped += 1
            continue
        try:
            shutil.copy2(old, new)
            did += 1
        except Exception as e:
            failed.append((old, new, str(e)))
    print("=== APPLY ===")
    print("新生成          ：%d 份" % did)
    print("跳过(已存在)   ：%d 份" % skipped)
    print("旧档不生成      ：%d 份（同 URL 有更新份）" % (len(pl["rename"]) - did - skipped))
    print("失败            ：%d 份" % len(failed))
    for o, n, e in failed:
        print("   ❌ %s → %s : %s" % (os.path.basename(o), os.path.basename(n), e))

    if not prune:
        print("\n提示：旧名文件全部保留。跑 --verify 确认基线命中后再加 --prune 清理。")
        return
    if failed:
        print("--prune 已跳过：存在失败项，避免删旧留新不完整")
        return
    # ⛔ 删除前逐个校验：新名存在，且其内部 url 与被删文件内部 url 完全一致
    removed, guard = 0, 0
    stale_paths = {o for o, n, at in pl["stale"]}
    for old, url, new in pl["rename"]:
        if os.path.abspath(old) not in stale_paths:
            continue                      # 只删「同 URL 的过期份」，最新那份由 --prune 二次清理
        if not os.path.exists(new):
            guard += 1
            continue
        if json.load(open(new, encoding="utf-8")).get("url") != url:
            guard += 1
            continue
        os.remove(old)
        removed += 1
    print("--prune 删除同 URL 过期份：%d 份（跳过 %d 份：目标缺失或 url 不符）" % (removed, guard))
    left = len([o for o, u, n in pl["rename"]
                if os.path.exists(o) and os.path.exists(n) and
                   not os.path.samefile(o, n)])
    print("剩余待清理旧名：%d 份（最新档，暂留以便回滚）" % left)


def cmd_verify(snap_dir=SNAP_DIR, hash_len=HASH_LEN):
    """验收：当前 181 个源能否全部命中基线（新命名下）。"""
    urls = load_current_urls()
    hit = [u for u in urls if os.path.exists(target_path(u, snap_dir, hash_len))]
    miss = [u for u in urls if not os.path.exists(target_path(u, snap_dir, hash_len))]
    print("=== VERIFY（新命名下基线命中）===")
    print("当前源        ：%d" % len(urls))
    print("命中基线      ：%d" % len(hit))
    print("缺基线        ：%d" % len(miss))
    for u in miss:
        print("   ❌ %s  ← %s" % (os.path.basename(target_path(u, snap_dir, hash_len)), u))
    # 顺带核对：命中文件的内部 url 是否与源一致（防「文件名对、内容错配」）
    wrong = []
    for u in hit:
        d = json.load(open(target_path(u, snap_dir, hash_len), encoding="utf-8"))
        if d.get("url") != u:
            wrong.append((u, d.get("url")))
    print("内容错配      ：%d" % len(wrong))
    for u, got in wrong:
        print("   ❌ 期望 %s 实得 %s" % (u, got))
    ok = not miss and not wrong
    print("\n结论：%s" % ("✅ 全部命中且内容对应" if ok else "❌ 存在问题"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prune", action="store_true", help="生成新名后删除旧名（需内容校验一致）")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--snap-dir", default=SNAP_DIR)
    ap.add_argument("--hash-len", type=int, default=HASH_LEN)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.verify:
        sys.exit(cmd_verify(a.snap_dir, a.hash_len))

    pl = plan(a.snap_dir)
    if a.apply:
        cmd_apply(pl, a.prune, a.snap_dir)
        if not a.prune:
            print("\n提示：旧名文件仍保留。验证 --verify 通过后再考虑加 --prune 清理。")
    else:
        cmd_dryrun(pl, a.verbose)


if __name__ == "__main__":
    main()
