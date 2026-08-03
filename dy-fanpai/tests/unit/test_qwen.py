"""Qwen 反推腿（reverse/qwen.py）单元测试。

覆盖确定性函数与请求构造；网络调用（qwen_call）用 monkeypatch Mock，
不真实调用 API（T4 纪律：未经审批不得 Live）。
"""

import os

import pytest

from dy_fanpai.config import Config
from dy_fanpai.reverse import qwen
from dy_fanpai.reverse.qwen import (
    build_prompt,
    build_request_body,
    qwen_call,
    reverse,
)


def test_build_prompt_segments():
    """Prompt 必须按硬切边界生成镜头段,且只输出 JSON。"""
    p = build_prompt([2.5, 5.0], 8.0)
    assert "[2.5, 5.0]" in p, "硬切边界须进 prompt"
    assert "8秒" in p or "8.0秒" in p or "8 秒" in p, "视频时长须进 prompt"
    assert "只输出一个JSON对象" in p, "强制 JSON 输出"


def test_build_prompt_business_rules():
    """反推五条底线:动作写全、product_role 判准、静音字幕不进台词、屏字逐字抄。"""
    p = build_prompt([], 10.0)
    assert "action 要把主体+动作都写全" in p
    assert "product_role" in p
    assert "台词只收录真实人声" in p
    assert "onscreen_text 逐句原样采集" in p
    assert "实体纪律" in p, "Qwen 腿应带实体纪律"


def test_build_prompt_same_schema_as_seed():
    """与 seed/kimi 共用同一 SCHEMA(合并同构)。"""
    from dy_fanpai.reverse.seed import SCHEMA

    assert "host_on_camera" in SCHEMA
    assert "product_role" in SCHEMA
    p = build_prompt([], 5.0)
    assert SCHEMA in p, "SCHEMA 必须完整嵌入 prompt"


def test_build_request_body_video_data_uri(tmp_path):
    """请求体:video_url 用 base64 data URI(本地视频无需公网 URL)。"""
    v = tmp_path / "clip.mp4"
    v.write_bytes(b"\x00\x01\x02\x03fake-mp4")
    body = build_request_body(str(v), "prompt-x", "qwen3.7-plus")
    assert body["model"] == "qwen3.7-plus"
    assert body["stream"] is False, "非流式直接收完整 JSON"
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "video_url"
    url = content[0]["video_url"]["url"]
    assert url.startswith("data:video/mp4;base64,"), "视频以 base64 data URI 传入"
    assert content[1] == {"type": "text", "text": "prompt-x"}


def test_qwen_call_request(monkeypatch, tmp_path):
    """Mock 请求:验证 URL/密钥/NO_PROXY/超时,返回解析。"""
    v = tmp_path / "clip.mp4"
    v.write_bytes(b"\x00fake")
    calls = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"choices": [{"message": {"content": '{"shots": []}'}}]}

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["proxies"] = proxies
        calls["timeout"] = timeout
        assert headers["Authorization"].startswith("Bearer test-key")
        assert proxies == {"http": None, "https": None}, "百炼国内端点直连"
        return FakeResp()

    monkeypatch.setattr(qwen.requests, "post", fake_post)
    cfg = Config(dashscope_api_key="test-key", qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    txt, secs = qwen_call(str(v), "p", cfg, timeout=30)
    assert calls["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert calls["timeout"] == (10, 30)
    assert '"shots": []' in txt
    assert secs >= 0


def test_qwen_call_requires_key():
    """无 key 时必须抛 ConfigError(不允许静默降级)。"""
    cfg = Config()  # dashscope_api_key 为空
    with pytest.raises(Exception, match="dashscope_api_key"):
        qwen_call("/tmp/x.mp4", "p", cfg)


def test_extract_json_fenced():
    """复用 seed.extract_json,兼容 markdown 围栏输出。"""
    from dy_fanpai.reverse.seed import extract_json

    d = extract_json('```json\n{"shots": [{"shot_id": 1}]}\n```')
    assert d["shots"][0]["shot_id"] == 1


def test_reverse_offline_no_api_call(monkeypatch, tmp_path):
    """reverse() 编排层离线路径:patch ffmpeg 函数与 qwen_call,验证编排与落盘。"""
    v = tmp_path / "src.mp4"
    v.write_bytes(b"\x00" * 100)
    out = tmp_path / "shotlist_qwen.json"

    # patch ffmpeg 依赖的三个确定性函数(返回合成数据),并造一个真实 clip 文件
    def fake_detect(video, thresh=0.15):
        return [0.5, 1.0]

    def fake_video_info(video):
        return {"duration": 3.0, "width": 720, "height": 1280}

    def fake_make_clip(video, scale, keep_audio, workdir):
        p = os.path.join(workdir, "_seed_upload.mp4")
        open(p, "wb").write(b"\x00" * 64)  # 真实落盘,让 getsize 通过
        return p

    def fake_call(clip, prompt, cfg, timeout=900):
        return '{"shots": [{"shot_id": 1, "start": 0.0, "end": 3.0, "dialogue": "hi"}]}', 0.1

    # qwen.py 用 from .seed import ... 直接绑定,须 patch qwen 模块自身的引用
    monkeypatch.setattr(qwen, "detect_cuts", fake_detect)
    monkeypatch.setattr(qwen, "video_info", fake_video_info)
    monkeypatch.setattr(qwen, "make_upload_clip", fake_make_clip)
    monkeypatch.setattr(qwen, "qwen_call", fake_call)
    cfg = Config(dashscope_api_key="k")
    data = reverse(str(v), out=str(out), cuts=None, cfg=cfg)
    assert data["shots"][0]["shot_id"] == 1
    assert data["video_info"]["duration"] == 3.0
    assert out.exists(), "应写出 shotlist_qwen.json"
