"""自建 ComfyUI 生成后端（generation/comfyui.py）单元测试。

覆盖确定性函数与请求编排；网络调用（上传/提交/轮询/下载）用 monkeypatch Mock，
不真实连接 ComfyUI（T4 纪律）。
"""

import json

import pytest

from dy_fanpai.config import Config
from dy_fanpai.generation import comfyui
from dy_fanpai.generation.comfyui import (
    PH_AUDIO,
    PH_DURATION,
    PH_IMAGE,
    PH_PROMPT,
    inject_placeholders,
    parse_history_out,
    parse_submit_out,
    submit,
    wait_download,
)


def _cfg(base="http://comfy:8188"):
    return Config(comfyui_base_url=base)


def test_inject_placeholders():
    wf = {
        "1": {"type": "LoadImage", "inputs": {"image": PH_IMAGE}},
        "2": {"type": "LoadAudio", "inputs": {"audio": PH_AUDIO}},
        "3": {"type": "Text", "inputs": {"text": f"prompt={PH_PROMPT} dur={PH_DURATION}"}},
        "4": {"type": "K", "inputs": {"nested": [{"x": PH_IMAGE}]}},
    }
    out = inject_placeholders(wf, {
        PH_IMAGE: "img.png", PH_AUDIO: "s.wav",
        PH_PROMPT: "展示产品", PH_DURATION: "5",
    })
    assert out["1"]["inputs"]["image"] == "img.png"
    assert out["2"]["inputs"]["audio"] == "s.wav"
    assert out["3"]["inputs"]["text"] == "prompt=展示产品 dur=5"
    assert out["4"]["inputs"]["nested"][0]["x"] == "img.png"
    # 原模板不被修改
    assert wf["1"]["inputs"]["image"] == PH_IMAGE


def test_inject_placeholders_keeps_missing():
    """未提供的占位符保持原样(便于发现模板缺参)。"""
    out = inject_placeholders({"n": {"v": f"{PH_PROMPT}"}}, {})
    assert out["n"]["v"] == PH_PROMPT


def test_parse_submit_out():
    assert parse_submit_out('{"prompt_id": "abc-123"}') == "abc-123"
    assert parse_submit_out('{"error": "x"}') is None
    assert parse_submit_out("bad") is None


def test_parse_history_out():
    # 完成且有视频输出
    out = json.dumps({
        "pid-1": {
            "status": {"status_str": "success", "completed": True},
            "outputs": {"5": {"gifs": [{"filename": "a.mp4", "subfolder": "", "type": "output"}]}},
        }
    })
    st, files = parse_history_out(out)
    assert st == "success" and files[0]["filename"] == "a.mp4"
    # 进行中
    st, _ = parse_history_out(json.dumps({
        "pid-1": {"status": {"status_str": "running", "completed": False}, "outputs": {}}}))
    assert st == "pending"
    # 失败
    st, _ = parse_history_out(json.dumps({
        "pid-1": {"status": {"status_str": "error", "completed": True}, "outputs": {}}}))
    assert st == "failed"


def test_submit_uploads_and_posts(monkeypatch, tmp_path):
    """全链路 Mock:上传图/音频 → 注入 → POST /prompt → 拿 prompt_id。"""
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    wav = tmp_path / "s.wav"
    wav.write_bytes(b"RIFF")
    tmpl = tmp_path / "i2v.json"
    tmpl.write_text(json.dumps({
        "1": {"type": "LoadImage", "inputs": {"image": PH_IMAGE}},
        "2": {"type": "LoadAudio", "inputs": {"audio": PH_AUDIO}},
    }), encoding="utf-8")

    calls = {"uploads": [], "posted": None}

    class FakeResp:
        status_code = 200
        text = ""

        def __init__(self, payload=None):
            self._p = payload or '{"prompt_id": "pid-1"}'
            self.text = self._p

        def json(self):
            return json.loads(self._p)

    def fake_post(url, **kw):
        if "/upload/" in url:
            calls["uploads"].append(url)
            name = "a.png" if "image" in url else "s.wav"
            return FakeResp(json.dumps({"name": name}))
        if url.endswith("/prompt"):
            calls["posted"] = kw.get("json")
            return FakeResp()
        raise AssertionError(f"意外 URL: {url}")

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://comfy:8188",
                 comfyui_workflow_i2v=str(tmpl))
    pid, err = submit("展示", cfg, first_frame=str(img), audio=str(wav), duration=5)
    assert pid == "pid-1"
    assert err == ""
    assert any("/upload/image" in u for u in calls["uploads"])
    assert any("/upload/audio" in u for u in calls["uploads"])
    # 注入后的工作流:图片/音频名已替换
    body = calls["posted"]
    nodes = body["prompt"]
    assert nodes["1"]["inputs"]["image"] == "a.png"
    assert nodes["2"]["inputs"]["audio"] == "s.wav"
    assert body["client_id"] == "dy-fanpai"


def test_submit_missing_template(tmp_path):
    cfg = Config(comfyui_base_url="http://comfy:8188",
                 comfyui_workflow_i2v=str(tmp_path / "nope.json"))
    with pytest.raises(RuntimeError, match="缺少工作流模板"):
        submit("x", cfg)


def test_submit_no_base_url():
    cfg = Config()  # comfyui_base_url 空
    with pytest.raises(Exception):
        submit("x", cfg)


def test_wait_download_success(monkeypatch, tmp_path):
    """轮询完成 → 从 /view 下载(robust_download mock,捕获其 URL)。"""
    hist = json.dumps({
        "pid-1": {
            "status": {"status_str": "success", "completed": True},
            "outputs": {"5": {"gifs": [{"filename": "v.mp4", "subfolder": "sub",
                                        "type": "output"}]}},
        }
    })

    class FakeResp:
        status_code = 200

        def __init__(self, payload):
            self.text = payload

    def fake_get(url, **kw):
        if "/history/" in url:
            return FakeResp(hist)
        raise AssertionError(f"view 不应走 requests.get: {url}")

    got_url = {}

    def fake_robust(url, dst, **kw):
        got_url["url"] = url
        open(dst, "wb").write(b"\x00" * 20000)
        return 20000

    monkeypatch.setattr(comfyui.requests, "get", fake_get)
    monkeypatch.setattr(comfyui, "robust_download", fake_robust)
    dst = tmp_path / "v.mp4"
    size = wait_download("pid-1", str(dst), _cfg(), tries=2, gap=0)
    assert size == 20000
    assert "/view?filename=v.mp4&subfolder=sub&type=output" in got_url["url"]
    assert dst.exists()


def test_wait_download_timeout(monkeypatch, tmp_path):
    class FakeResp:
        status_code = 200
        text = json.dumps({"pid-1": {"status": {"status_str": "running", "completed": False},
                                     "outputs": {}}})

    def fake_get(url, **kw):
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "get", fake_get)
    r = wait_download("pid-1", str(tmp_path / "v.mp4"), _cfg(), tries=2, gap=0)
    assert r is None, "超时未完成返回 None"


def test_service_backend_registered():
    from dy_fanpai.generation import service as S

    backends = S._default_backends()
    assert "comfyui" in backends


def test_frames_placeholder_injected(monkeypatch, tmp_path):
    """__FRAMES__ 应按时长×16fps 注入(5s → 80帧)。"""
    from dy_fanpai.generation.comfyui import PH_FRAMES, submit_i2v

    tmpl = tmp_path / "i2v.json"
    tmpl.write_text(json.dumps({
        "1": {"type": "X", "widgets_values": [PH_FRAMES]}}), encoding="utf-8")
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")

    seen = {}

    class FakeResp:
        status_code = 200
        text = '{"prompt_id": "p1"}'

        def json(self):
            return {"name": "a.png"}

    def fake_post(url, **kw):
        if "/upload/" in url:
            return FakeResp()
        seen["body"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://c:8188", comfyui_workflow_i2v=str(tmpl))
    pid = submit_i2v(str(img), "x", cfg, duration=5)
    assert pid == "p1"
    assert seen["body"]["prompt"]["1"]["widgets_values"][0] == str(5 * comfyui.FPS), \
        "5s 段应注入 80 帧"
