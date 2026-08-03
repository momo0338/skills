"""MiniMax H3 生成后端（generation/minimax.py）单元测试。

覆盖确定性构造与解析；网络调用（_post/wait_download）用 monkeypatch Mock，
不真实调用 API（T4 纪律：未经审批不得 Live）。
"""

import pytest

from dy_fanpai.config import Config
from dy_fanpai.generation import minimax
from dy_fanpai.generation.minimax import (
    build_submit_body,
    parse_create_out,
    parse_query_out,
    submit,
    wait_download,
)


def test_build_body_t2v():
    """文生视频：仅 text,ratio 显式。"""
    body = build_submit_body("纯文本", 5, ratio="9:16")
    assert body["model"] == "MiniMax-H3"
    assert body["duration"] == 5
    assert body["resolution"] == "768P"
    assert body["ratio"] == "9:16"
    types = [c["type"] for c in body["content"]]
    assert types == ["text"]


def test_build_body_i2v_first_frame(tmp_path):
    """图生视频-首帧：1 张 first_frame + text,ratio=adaptive。"""
    img = tmp_path / "f.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    body = build_submit_body("产品展示", 6, first_frame=str(img))
    roles = [c.get("role") for c in body["content"]]
    assert "first_frame" in roles, "首帧图必须带 first_frame role"
    url = body["content"][0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,"), "图片以 base64 data URI 传入"
    assert body["content"][-1]["text"] == "产品展示"
    assert body["ratio"] == "adaptive", "图生视频 ratio 恒为 adaptive"


def test_build_body_mm_reference_audio(tmp_path):
    """多模态参考（口播）：参考图 reference_image + 段配音 reference_audio。"""
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    wav = tmp_path / "s.wav"
    wav.write_bytes(b"RIFF")
    body = build_submit_body("口播词", 10, images=[str(img)], audio=str(wav))
    roles = [c.get("role") for c in body["content"]]
    assert "reference_image" in roles
    assert "reference_audio" in roles, "口播段必须带 reference_audio"
    assert body["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["content"][1]["audio_url"]["url"].startswith("data:audio/wav;base64,")


def test_parse_create_out():
    assert parse_create_out('{"task_id": "t-123"}') == "t-123"
    assert parse_create_out('{"error": {"type": "x"}}') is None
    assert parse_create_out("not json") is None


def test_parse_query_out():
    st, url = parse_query_out(
        '{"task": {"status": "succeeded", "content": {"url": "https://cdn/x.mp4"}}}'
    )
    assert st == "success" and url == "https://cdn/x.mp4"
    st, fr = parse_query_out('{"task": {"status": "failed", "error": {"message": "内容违规"}}}')
    assert st == "fail" and "内容违规" in fr
    st, _ = parse_query_out('{"task": {"status": "running"}}')
    assert st == "pending"
    st, _ = parse_query_out("garbage")
    assert st == "pending"


def test_submit_request(monkeypatch, tmp_path):
    """Mock POST:验证 URL/密钥/NO_PROXY,返回 task_id。"""
    calls = {}

    class FakeResp:
        status_code = 200
        text = '{"task_id": "task-1"}'

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["proxies"] = proxies
        assert headers["Authorization"] == "Bearer k"
        assert proxies == {"http": None, "https": None}, "国内端点直连"
        return FakeResp()

    monkeypatch.setattr(minimax.requests, "post", fake_post)
    cfg = Config(minimax_api_key="k", minimax_base_url="https://api.minimaxi.com")
    tid, raw = submit("文字", cfg, duration=5)
    assert tid == "task-1"
    assert calls["url"] == "https://api.minimaxi.com/v2/video_generation"
    assert raw == '{"task_id": "task-1"}'


def test_submit_requires_key():
    cfg = Config()
    with pytest.raises(Exception, match="minimax_api_key"):
        submit("x", cfg)


def test_submit_fatal_no_retry(monkeypatch):
    """参数级错误(422 内容违规)不重试,直接抛。"""
    n = [0]

    class FakeResp:
        status_code = 422
        text = '{"type":"error"}'

    def fake_post(url, **kw):
        n[0] += 1
        return FakeResp()

    monkeypatch.setattr(minimax.requests, "post", fake_post)
    cfg = Config(minimax_api_key="k")
    with pytest.raises(RuntimeError, match="422"):
        submit("敏感内容", cfg, retries=3)
    assert n[0] == 1, "参数级错误不应重试"


def test_wait_download_success(monkeypatch, tmp_path):
    """轮询成功:从 content.url 下载(robust_download mock)。"""
    calls = {}

    class FakeResp:
        status_code = 200
        text = '{"task": {"status": "succeeded", "content": {"url": "https://cdn/v.mp4"}}}'

    def fake_get(url, headers=None, proxies=None, timeout=None):
        calls["url"] = url
        return FakeResp()

    def fake_robust(url, dst, **kw):
        open(dst, "wb").write(b"\x00" * 20000)
        return 20000

    monkeypatch.setattr(minimax.requests, "get", fake_get)
    monkeypatch.setattr(minimax, "robust_download", fake_robust)
    cfg = Config(minimax_api_key="k", minimax_base_url="https://api.minimaxi.com")
    dst = tmp_path / "v.mp4"
    size = wait_download("t-1", str(dst), cfg, tries=3, gap=0)
    assert size == 20000
    assert calls["url"] == "https://api.minimaxi.com/v2/query/video_generation/t-1"
    assert dst.exists()


def test_wait_download_fail(monkeypatch, tmp_path):
    class FakeResp:
        status_code = 200
        text = '{"task": {"status": "failed", "error": {"message": "内容违规"}}}'

    def fake_get(url, **kw):
        return FakeResp()

    monkeypatch.setattr(minimax.requests, "get", fake_get)
    cfg = Config(minimax_api_key="k")
    r = wait_download("t", str(tmp_path / "x.mp4"), cfg, tries=1, gap=0)
    assert isinstance(r, str) and r.startswith("FAIL:")


def test_service_backend_registered():
    """minimax 已注册进 _default_backends(供 --i2v-backend minimax 路由)。"""
    from dy_fanpai.generation import service as S

    backends = S._default_backends()
    assert "minimax" in backends
