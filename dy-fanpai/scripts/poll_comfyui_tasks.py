#!/usr/bin/env python3
"""ComfyUI 生成任务轮询下载工具（dy-fanpai 配套）。

用法:
  python poll_comfyui_tasks.py <workspace> [--interval 900] [--timeout 14400]
      [--segments S1,S2] [--id-only]

说明:
  - 读 workspace/clips/*.meta.json 里的 task_id（提交时写入）；
  - 每 --interval 秒查一次 ComfyUI /history/{id}，出片自动下载 clips/{seg}.mp4；
  - 已存在的 clips/{seg}.mp4 自动跳过（断点续传）；
  - --id-only：只打印 task 清单（segment→prompt_id），不轮询。

★ 经验（2026-08-05/06）：
  - outputs 结构是 {"15": {"images": [ {filename, subfolder, type} ]}}，
    正确遍历是 o.get('images', []) 列表（不是 o.items() 的 dict 值）；
  - 扁平模板提交时 prompt_id 可能被 ComfyUI 重写，/history 需同时查
    提交 id 与队列实际 id（--id-only 显示的 id 如查不到，看队列里的 id）。
"""
import argparse
import json
import os
import ssl
import time
import urllib.request

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from dy_fanpai.config import Config  # noqa: E402


def _ctx() -> ssl.SSLContext:
    # trycloudflare 证书链 urllib 不认，绕过校验（curl 认系统 CA 所以 curl 可用）
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def load_tasks(clips_dir: str) -> list[tuple[str, str]]:
    """读 clips/*.meta.json → [(segment, task_id)]"""
    tasks = []
    if not os.path.isdir(clips_dir):
        return tasks
    for fn in sorted(os.listdir(clips_dir)):
        if not fn.endswith(".meta.json"):
            continue
        p = os.path.join(clips_dir, fn)
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        seg = m.get("segment") or fn[: -len(".meta.json")]
        tid = m.get("task_id") or m.get("submit_id")
        if tid:
            tasks.append((seg, tid))
    return tasks


def fetch_history(base: str, pid: str, ctx) -> dict:
    with urllib.request.urlopen(f"{base}/history/{pid}", timeout=20, context=ctx) as r:
        return json.loads(r.read().decode())


def try_download(base: str, pid: str, dst: str, ctx) -> bool:
    """查 history 并下载输出；返回 True 表示该任务已完结（成功/失败）。"""
    try:
        h = fetch_history(base, pid, ctx)
    except Exception:
        return False
    if pid not in h:
        return False
    e = h[pid]
    st = e.get("status")
    if isinstance(st, dict):
        st = st.get("status_str")
    if st not in ("success", "error"):
        return False
    if st == "error":
        print(f"[{time.strftime('%H:%M:%S')}] {os.path.basename(dst)} ERROR "
              f"{json.dumps(e, ensure_ascii=False)[:200]}", flush=True)
        return True
    # success：遍历 outputs.images 列表
    for nid, o in (e.get("outputs") or {}).items():
        for img in o.get("images", []) or []:
            if img.get("type") == "output":
                url = (f"{base}/view?filename={img.get('filename')}"
                       f"&subfolder={img.get('subfolder', '')}&type=output")
                with urllib.request.urlopen(url, timeout=180, context=ctx) as r:
                    data = r.read()
                with open(dst, "wb") as f:
                    f.write(data)
                print(f"[{time.strftime('%H:%M:%S')}] {os.path.basename(dst)} "
                      f"SUCCESS {len(data) // 1024}KB ← {img.get('filename')}", flush=True)
                return True
    print(f"[{time.strftime('%H:%M:%S')}] {os.path.basename(dst)} success 但无输出文件", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--interval", type=int, default=900)
    ap.add_argument("--timeout", type=int, default=14400)
    ap.add_argument("--segments", default=None, help="逗号分隔，默认全部")
    ap.add_argument("--id-only", action="store_true")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    clips_dir = os.path.join(ws, "clips")
    cfg = Config.load()
    base = cfg.comfyui_base_url.rstrip("/")
    if not base:
        print("❌ 未配置 comfyui_base_url", file=sys.stderr)
        return 1

    tasks = load_tasks(clips_dir)
    if args.segments:
        want = set(args.segments.split(","))
        tasks = [(s, t) for s, t in tasks if s in want]
    if not tasks:
        print("clips/ 无 meta 任务文件（先提交生成并写 meta）")
        return 1

    print(f"任务清单 ({len(tasks)}):")
    for seg, tid in tasks:
        print(f"  {seg} → {tid}")

    if args.id_only:
        return 0

    print(f"轮询 {base} 每 {args.interval}s（上限 {args.timeout // 3600}h）…")
    ctx = _ctx()
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        remaining = [t for t in tasks if not os.path.exists(os.path.join(clips_dir, t[0] + ".mp4"))]
        if not remaining:
            print(f"[{time.strftime('%H:%M:%S')}] 全部完成 ✓")
            return 0
        for seg, tid in remaining:
            try_download(base, tid, os.path.join(clips_dir, f"{seg}.mp4"), ctx)
        # 双 id 兜底：队列里的实际执行 id 可能不同
        try:
            with urllib.request.urlopen(f"{base}/queue", timeout=10, context=ctx) as r:
                q = json.loads(r.read().decode())
            for item in q.get("queue_running", []) + q.get("queue_pending", []):
                qpid = item[1]
                for seg, tid in remaining:
                    if qpid != tid:
                        try_download(base, qpid, os.path.join(clips_dir, f"{seg}.mp4"), ctx)
        except Exception:
            pass
        done = sum(1 for t in tasks if os.path.exists(os.path.join(clips_dir, t[0] + ".mp4")))
        print(f"[{time.strftime('%H:%M:%S')}] {done}/{len(tasks)} 完成，"
              f"下次 {args.interval // 60} 分钟后", flush=True)
        time.sleep(args.interval)
    print("TIMEOUT", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
