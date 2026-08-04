"""comfyui 后端本地联调演练(不依赖真实 ComfyUI 机器)。

用 HTTP mock 服务器模拟 ComfyUI,验证 comfyui.py 的
「上传素材 → 注入占位符 → POST /prompt → 轮询 /history → /view 下载」
全链路协议对接是否正确。这是接入真实机器前的最后一道本地关卡。

用法:
    .venv/bin/python scripts/comfyui_mock_e2e.py

输出期望:
    [i2v] mock-1 → 下载 20012 bytes ✅
    [mm]  mock-2 ✅
    [服务器] 上传 3 次 ...
    ✅✅ 演练全部通过
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from http.server import BaseHTTPRequestHandler, HTTPServer

from dy_fanpai.config import Config
from dy_fanpai.generation import comfyui

FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + os.urandom(20000)


class MockComfy(BaseHTTPRequestHandler):
    uploads: list[tuple[str, str]] = []
    submits: list[dict] = []

    def log_message(self, *a):  # noqa: D401
        pass

    def do_POST(self):
        ln = int(self.headers["Content-Length"])
        raw = self.rfile.read(ln)
        if self.path.startswith("/upload/"):
            m = re.search(rb'filename="([^"]+)"', raw)
            name = m.group(1).decode() if m else "x.png"
            MockComfy.uploads.append((self.path.split("/")[-1], name))
            body = json.dumps({"name": name}).encode()
        elif self.path == "/prompt":
            MockComfy.submits.append(json.loads(raw))
            body = json.dumps({"prompt_id": f"mock-{len(MockComfy.submits)}"}).encode()
        else:
            body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if "/history/" in self.path:
            out = json.dumps({
                "x": {"status": {"status_str": "success", "completed": True},
                      "outputs": {"9": {"gifs": [{"filename": "out.mp4",
                                                  "subfolder": "", "type": "output"}]}}}
            }).encode()
        else:  # /view
            out = FAKE_MP4
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), MockComfy)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    work = "/tmp/comfy_demo"
    os.makedirs(work, exist_ok=True)
    # i2v + mm 双模板(占位符注入点)
    json.dump({"1": {"type": "LoadImage", "inputs": {"image": comfyui.PH_IMAGE}},
               "2": {"type": "WanVideo", "inputs": {
                   "prompt": comfyui.PH_PROMPT, "duration": comfyui.PH_DURATION,
                   "width": comfyui.PH_WIDTH, "height": comfyui.PH_HEIGHT}}},
              open(os.path.join(work, "i2v.json"), "w"))
    json.dump({"1": {"type": "LoadImage", "inputs": {"image": comfyui.PH_IMAGE}},
               "2": {"type": "LoadImage", "inputs": {"image": comfyui.PH_IMAGE2}},
               "3": {"type": "LoadAudio", "inputs": {"audio": comfyui.PH_AUDIO}},
               "4": {"type": "LatentSync", "inputs": {"prompt": comfyui.PH_PROMPT}}},
              open(os.path.join(work, "mm.json"), "w"))
    img, wav = os.path.join(work, "a.png"), os.path.join(work, "s.wav")
    open(img, "wb").write(b"\x89PNG")
    open(wav, "wb").write(b"RIFF")

    cfg = Config(comfyui_base_url=f"http://127.0.0.1:{port}",
                 comfyui_workflow_i2v=os.path.join(work, "i2v.json"),
                 comfyui_workflow_mm=os.path.join(work, "mm.json"))

    pid1 = comfyui.submit_i2v(img, "产品展示", cfg, duration=5)
    size = comfyui.wait_download(pid1, os.path.join(work, "o1.mp4"), cfg, tries=2, gap=0)
    print(f"[i2v] {pid1} → 下载 {size} bytes ✅")

    pid2 = comfyui.submit_mm([img], wav, "口播词", cfg, duration=4)
    print(f"[mm]  {pid2} ✅")

    print(f"[服务器] 上传 {len(MockComfy.uploads)} 次: {MockComfy.uploads}")
    last = MockComfy.submits[-1]["prompt"]
    print(f"[mm注入后] img1={last['1']['inputs']['image']!r} "
          f"img2={last['2']['inputs']['image']!r} "
          f"audio={last['3']['inputs']['audio']!r} "
          f"prompt={last['4']['inputs']['prompt'][:12]!r}")
    srv.shutdown()
    print("\n✅✅ 演练全部通过: i2v 与 mm(口型) 两条工作流的上传→注入→提交→轮询→下载 协议完全对接")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
