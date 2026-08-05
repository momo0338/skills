"""H3 三能力模板(t2v/r2v)与扁平格式提交测试(generation/comfyui.py)。

覆盖:扁平模板格式识别、aspect_ratio 映射、r2v 单图裁剪、
submit_h3_t2v / submit_h3_r2v 全链路 Mock、service 后端注册。
网络调用用 monkeypatch Mock,不真实连接 ComfyUI(T4 纪律)。
"""

import json

from dy_fanpai.config import Config
from dy_fanpai.generation import comfyui
from dy_fanpai.generation.comfyui import (
    PH_ASPECT,
    PH_DURATION,
    PH_IMAGE,
    PH_IMAGE2,
    PH_PROMPT,
    PH_SEED,
    aspect_ratio_for,
    prune_r2v_single,
    submit_h3_r2v,
    submit_h3_t2v,
)


def _flat_t2v_tmpl(tmp_path):
    """最小 H3 t2v 扁平模板(与 resources 模板同构)。"""
    p = tmp_path / "h3_t2v.json"
    p.write_text(json.dumps({
        "92": {"class_type": "SaveVideo", "inputs": {"video": ["105:91", 0]}},
        "115": {"class_type": "ResolutionSelector",
                "inputs": {"aspect_ratio": PH_ASPECT, "megapixels": 0.4, "multiple": 32}},
        "105:104": {"class_type": "MiniMaxH3ImageToVideo",
                    "inputs": {"prompt": PH_PROMPT, "width": ["115", 0], "height": ["115", 1],
                               "length": ["105:107", 1]}},
        "105:107": {"class_type": "ComfyMathExpression",
                    "inputs": {
                        "expression":
                            "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
                        "values.a": ["105:111", 0]}},
        "105:111": {"class_type": "PrimitiveFloat", "inputs": {"value": PH_DURATION}},
        "105:15": {"class_type": "RandomNoise", "inputs": {"noise_seed": PH_SEED}},
    }), encoding="utf-8")
    return p


def _flat_r2v_tmpl(tmp_path):
    """最小 H3 r2v 扁平模板(双参考图)。"""
    p = tmp_path / "h3_r2v.json"
    p.write_text(json.dumps({
        "136": {"class_type": "MiniMaxH3ReferenceToVideo",
                "inputs": {"prompt": PH_PROMPT, "ref_image_size": "match",
                           "ref_images.ref_image_0": ["137", 0],
                           "ref_images.ref_image_1": ["139", 0]}},
        "137": {"class_type": "LoadImage", "inputs": {"image": PH_IMAGE}},
        "139": {"class_type": "LoadImage", "inputs": {"image": PH_IMAGE2}},
        "115": {"class_type": "ResolutionSelector", "inputs": {"aspect_ratio": PH_ASPECT}},
        "132": {"class_type": "PrimitiveFloat", "inputs": {"value": PH_DURATION}},
        "129": {"class_type": "RandomNoise", "inputs": {"noise_seed": PH_SEED}},
    }), encoding="utf-8")
    return p


def test_aspect_ratio_for():
    assert aspect_ratio_for(720, 1280) == "9:16 (Portrait Widescreen)"
    assert aspect_ratio_for(768, 1344) == "9:16 (Portrait Widescreen)"
    assert aspect_ratio_for(1280, 720) == "16:9 (Widescreen)"
    assert aspect_ratio_for(1024, 1024) == "1:1 (Square)"
    assert aspect_ratio_for(768, 512) == "3:2 (Photo)"


def test_prune_r2v_single_removes_second_ref():
    """单参考图:移除第二个 LoadImage 与 ref_image_1 引用,不动原模板。"""
    wf = {
        "136": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "ref_images.ref_image_0": ["137", 0],
            "ref_images.ref_image_1": ["139", 0]}},
        "137": {"class_type": "LoadImage", "inputs": {"image": "a.png"}},
        "139": {"class_type": "LoadImage", "inputs": {"image": PH_IMAGE2}},
    }
    out = prune_r2v_single(wf)
    assert "139" not in out
    assert "ref_images.ref_image_1" not in out["136"]["inputs"]
    assert out["136"]["inputs"]["ref_images.ref_image_0"] == ["137", 0]
    assert "139" in wf, "原模板不被修改"


def test_prune_r2v_single_two_images_keeps_both():
    wf = {
        "137": {"class_type": "LoadImage", "inputs": {"image": "a.png"}},
        "139": {"class_type": "LoadImage", "inputs": {"image": "b.png"}},
    }
    out = prune_r2v_single(wf)
    assert "139" in out


def test_t2v_flat_template_submit(monkeypatch, tmp_path):
    """扁平模板直接提交:注入 prompt/duration/aspect/seed,不经过 graph 转换。"""
    tmpl = _flat_t2v_tmpl(tmp_path)
    seen = {}

    class FakeResp:
        status_code = 200
        text = '{"prompt_id": "pid-t2v"}'

        def json(self):
            return {"name": "x.png"}

    def fake_post(url, **kw):
        if "/upload/" in url:
            return FakeResp()
        seen["body"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://c:8188", comfyui_workflow_h3_t2v=str(tmpl))
    pid = submit_h3_t2v("海浪", cfg, duration=6, width=768, height=1344, seed=123)
    assert pid == "pid-t2v"
    prompt = seen["body"]["prompt"]
    assert prompt["105:104"]["inputs"]["prompt"] == "海浪"
    assert prompt["105:111"]["inputs"]["value"] == "6"
    assert prompt["115"]["inputs"]["aspect_ratio"] == "9:16 (Portrait Widescreen)"
    assert prompt["105:15"]["inputs"]["noise_seed"] == "123"
    # 扁平模板:节点 id 保持原样(未转 graph)
    assert "92" in prompt and prompt["92"]["class_type"] == "SaveVideo"


def test_t2v_default_seed_random(monkeypatch, tmp_path):
    """未传 seed 时注入随机种子(0..2^31)。"""
    tmpl = _flat_t2v_tmpl(tmp_path)
    seen = {}

    class FakeResp:
        status_code = 200
        text = '{"prompt_id": "p"}'

        def json(self):
            return {}

    def fake_post(url, **kw):
        seen["body"] = kw["json"] if "/prompt" in url else None
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://c:8188", comfyui_workflow_h3_t2v=str(tmpl))
    submit_h3_t2v("x", cfg, duration=5)
    seed = int(seen["body"]["prompt"]["105:15"]["inputs"]["noise_seed"])
    assert 0 <= seed < 2**31


def test_r2v_flat_template_submit_two_refs(monkeypatch, tmp_path):
    """r2v 双参考图:两张图都上传,ref_image_0/1 均保留。"""
    tmpl = _flat_r2v_tmpl(tmp_path)
    a = tmp_path / "a.png"
    a.write_bytes(b"\x89PNG")
    b = tmp_path / "b.png"
    b.write_bytes(b"\x89PNG")
    seen = {}

    class FakeResp:
        status_code = 200
        text = '{"prompt_id": "pid-r2v"}'

        def __init__(self, payload=None):
            self._p = payload or '{"prompt_id": "pid-r2v"}'
            self.text = self._p

        def json(self):
            return json.loads(self._p)

    def fake_post(url, **kw):
        if "/upload/" in url:
            return FakeResp(json.dumps({"name": "up.png"}))
        seen["body"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://c:8188", comfyui_workflow_h3_r2v=str(tmpl))
    pid = submit_h3_r2v([str(a), str(b)], "参考生成", cfg, duration=7)
    assert pid == "pid-r2v"
    prompt = seen["body"]["prompt"]
    assert prompt["136"]["inputs"]["ref_images.ref_image_0"] == ["137", 0]
    assert prompt["136"]["inputs"]["ref_images.ref_image_1"] == ["139", 0]
    assert "139" in prompt


def test_r2v_flat_template_submit_single_ref(monkeypatch, tmp_path):
    """r2v 单参考图:自动移除第二个 LoadImage 与 ref_image_1 引用。"""
    tmpl = _flat_r2v_tmpl(tmp_path)
    a = tmp_path / "a.png"
    a.write_bytes(b"\x89PNG")
    seen = {}

    class FakeResp:
        status_code = 200
        text = '{"prompt_id": "pid-r2v"}'

        def __init__(self, payload=None):
            self._p = payload or '{"prompt_id": "pid-r2v"}'
            self.text = self._p

        def json(self):
            return json.loads(self._p)

    def fake_post(url, **kw):
        if "/upload/" in url:
            return FakeResp(json.dumps({"name": "up.png"}))
        seen["body"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(comfyui.requests, "post", fake_post)
    cfg = Config(comfyui_base_url="http://c:8188", comfyui_workflow_h3_r2v=str(tmpl))
    pid = submit_h3_r2v([str(a)], "参考生成", cfg, duration=7)
    assert pid == "pid-r2v"
    prompt = seen["body"]["prompt"]
    assert "139" not in prompt, "单图时第二个 LoadImage 应被移除"
    assert "ref_images.ref_image_1" not in prompt["136"]["inputs"]


def test_service_registers_h3_t2v_r2v():
    from dy_fanpai.generation import service as S

    backends = S._default_backends()
    assert "comfyui_h3_t2v" in backends
    assert "comfyui_h3_r2v" in backends
    # r2v 提交用 [anchor] 单参考图
    import inspect

    fn = backends["comfyui_h3_r2v"]["submit"]
    src = inspect.getsource(fn)
    assert "submit_h3_r2v" in src
