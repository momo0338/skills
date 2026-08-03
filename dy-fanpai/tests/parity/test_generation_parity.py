"""generation 对当前算法 golden 的 parity 测试（WP4，验收门 4 统一 golden）。

PARITY.md 待办 1/2：为 WP4（提交命令 / 轮询输出解析）建「当前算法 golden」。
覆盖即梦(Dreamina)、Ark、小云雀(XYQ)、下载代理四类确定性输出：
- 与 golden 逐字段一致（防参数漂移）；
- 业务铁律断言：mm 走 multimodal2video、i2v 走 image2video、人物口播带音频、
  i2v 不带音频、AUDIO_GUARD 只对非口播段追加、Ark NO_PROXY、时长按 wav 上调等。
"""

import json
import os

from dy_fanpai.generation import ark, dreamina, xyq
from dy_fanpai.media import download

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SEGS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "scenarios", "A", "segments.golden.json"))


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def _segs():
    return _load(SEGS)


def test_dreamina_cmds_parity():
    """即梦提交命令与 golden 逐字段一致。"""
    golden = _load(os.path.join(FIX, "wp4_dreamina.golden.json"))
    segs = _segs()
    mm = next(s for s in segs if s["type"] == "mm")
    i2v = next(s for s in segs if s["type"] == "i2v")
    assert dreamina.build_submit_cmd(mm, "audio", "/usr/bin/dreamina") == golden["mm_submit_cmd"]
    assert dreamina.build_submit_cmd(i2v, "audio", "/usr/bin/dreamina") == golden["i2v_submit_cmd"]


def test_dreamina_route_rules(tmp_path):
    """路由铁律：mm→multimodal2video 带图；存在段配音时带 --audio；i2v→image2video 单图不带音频。"""
    segs = _segs()
    mm = next(s for s in segs if s["type"] == "mm")
    i2v = next(s for s in segs if s["type"] == "i2v")
    # 无配音目录 → 不带 --audio（golden 固化路径）
    mm_cmd = dreamina.build_submit_cmd(mm, None, "/bin/d")
    i2v_cmd = dreamina.build_submit_cmd(i2v, "audio", "/bin/d")
    assert mm_cmd[1] == "multimodal2video", "口播段走 multimodal2video"
    assert "--audio" not in mm_cmd, "无配音文件时不应带 --audio"
    assert i2v_cmd[1] == "image2video", "纯产品段走 image2video"
    assert "--audio" not in i2v_cmd, "i2v 段不带音频"
    assert "--image" in i2v_cmd, "i2v 段必须带锚图"
    # 真实 wav 存在 → 口播段带 --audio
    wav = tmp_path / f"{mm['seg']}.wav"
    wav.write_bytes(b"RIFF")
    mm_cmd2 = dreamina.build_submit_cmd(mm, str(tmp_path), "/bin/d")
    assert "--audio" in mm_cmd2, "存在段配音时口播段必须带 --audio"
    assert str(wav) in mm_cmd2, "--audio 指向段 wav"


def test_dreamina_fixed_params():
    """即梦固定参数：模型 seedance2.0_vip、9:16、720p、--poll 0。"""
    segs = _segs()
    cmd = dreamina.build_submit_cmd(next(s for s in segs if s["type"] == "mm"), None, "/bin/d")
    joined = " ".join(cmd)
    assert "seedance2.0_vip" in joined, "模型版本"
    assert "9:16" in joined, "比例"
    assert "720p" in joined, "分辨率"
    assert "--poll 0" in joined, "提交后不阻塞"


def test_dreamina_parse_parity():
    """即梦输出解析与 golden 一致。"""
    golden = _load(os.path.join(FIX, "wp4_dreamina.golden.json"))
    assert list(dreamina.parse_submit_out('{"task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "credit_count": 3}')) == golden["parse_submit_ok"]
    assert list(dreamina.parse_submit_out("error: no task")) == golden["parse_submit_fail"]
    assert list(dreamina.parse_query_out('{"gen_status": "success", "video_url": "https://cdn.example.com/v.mp4"}')) == golden["parse_query_success"]
    assert list(dreamina.parse_query_out('{"gen_status": "fail", "fail_reason": "内容违规"}')) == golden["parse_query_fail"]
    assert list(dreamina.parse_query_out('{"gen_status": "running"}')) == golden["parse_query_pending"]


def test_dreamina_duration_fit():
    """配音超长自动上调生成时长（上限 15s）；不超长不动。"""
    assert dreamina.fitted_duration(10.0, 9.5) == 10.0, "配音不超长不调整"
    assert dreamina.fitted_duration(10.0, 12.3) == 13, "超长向上取整+0.5"
    assert dreamina.fitted_duration(10.0, 20.0) == 15, "封顶 15s"
    assert dreamina.fitted_duration(10.0, 10.1) == 10, "容差 0.25 内不调整"


def test_ark_bodies_parity():
    """Ark 请求体与 golden 逐字段一致。"""
    golden = _load(os.path.join(FIX, "wp4_ark.golden.json"))
    assert ark.build_i2v_body("QUJD", "image/png", "产品特写", 5, "720p", "9:16", "model-x") == golden["i2v_body"]
    assert ark.build_mm_body([("image/png", "QUJD"), ("image/jpeg", "RUZH")], ("audio/wav", "QVVE"),
                             "口播", 10, "720p", "9:16", "model-x") == golden["mm_body"]
    assert ark.build_t2v_body("文字生成", 5, "720p", "9:16", "model-x") == golden["t2v_body"]


def test_ark_body_business_rules():
    """Ark 铁律：文本参数带 --resolution/--duration/--ratio；多图带 role=reference_image。"""
    body = ark.build_mm_body([("image/png", "QUJD"), ("image/jpeg", "RUZH")], None,
                             "口播", 10, "720p", "9:16", "model-x")
    text = body["content"][-1]["text"]
    assert "--resolution 720p" in text and "--duration 10" in text and "--ratio 9:16" in text
    for c in body["content"][:-1]:
        assert c.get("role") == "reference_image", "多图必须带 reference_image role"
    # 带音频时音频 role=reference_audio
    body2 = ark.build_mm_body([("image/png", "QUJD")], ("audio/wav", "QVVE"), "口播", 10, "720p", "9:16", "m")
    roles = [c.get("role") for c in body2["content"]]
    assert "reference_audio" in roles, "音频必须带 reference_audio role"


def test_ark_mime_parity():
    """MIME 推断与 golden 一致。"""
    golden = _load(os.path.join(FIX, "wp4_ark.golden.json"))
    assert ark._mime_for_image("a.png") == golden["mime_png"]
    assert ark._mime_for_image("a.webp") == golden["mime_webp"]
    assert ark._mime_for_image("a.jpg") == golden["mime_jpg"]
    assert ark._mime_for_audio("a.wav") == golden["mime_wav"]
    assert ark._mime_for_audio("a.mp3") == golden["mime_mp3"]


def test_xyq_args_parity():
    """XYQ 命令参数与 golden 逐字段一致。"""
    golden = _load(os.path.join(FIX, "wp4_xyq.golden.json"))
    assert xyq.build_i2v_args("img.png", "产品展示", 5, "720p", "9:16", "Seedance_2.0_mini_lite") == golden["i2v_args"]
    assert xyq.build_mm_args(["a.png", "b.png"], "v.wav", "口播词", 10, "720p", "9:16", "Seedance_2.0_mini_lite") == golden["mm_args"]
    assert xyq.build_t2v_args("纯文本", 5, "720p", "9:16", "Seedance_2.0_mini_lite") == golden["t2v_args"]


def test_xyq_audio_guard():
    """AUDIO_GUARD 铁律：非口播段自动追加『无人声』；已含无人声不重复；口播段(mock 语义)不加。"""
    assert xyq._common("画面展示产品", 5, "720p", "9:16", True, "")[1].endswith("无人声,无背景音乐。"), "非口播段追加 AUDIO_GUARD"
    assert "无人声" in xyq._common("无人声,画面展示", 5, "720p", "9:16", True, "")[1]
    assert not xyq._common("口播说话", 5, "720p", "9:16", False, "")[1].endswith("无人声,无背景音乐。"), "口播段不加无人声限定"


def test_xyq_field_parity():
    """XYQ 字段提取（JSON 行 / key=value / 嵌套 data.run）与 golden 一致。"""
    golden = _load(os.path.join(FIX, "wp4_xyq.golden.json"))
    assert xyq._field('{"thread_id": "t-1", "run_id": "r-2", "web_thread_link": "https://x/y"}', "thread_id") == golden["field_json_line"]
    assert xyq._field("thread_id=t-1\nrun_id=r-2", "run_id") == golden["field_kv"]
    assert xyq._field('{"data": {"run": {"output_path": "https://cdn/x.mp4"}}}', "output_path") == golden["field_json_nested"]


def test_download_proxy_parity():
    """代理选择策略：显式代理始终走；前 2 次直连；第 3 次起回退环境代理。"""
    golden = _load(os.path.join(FIX, "wp4_download.golden.json"))
    assert download.proxy_for_attempt(None, 0) == golden["direct_attempt0"]
    assert download.proxy_for_attempt(None, 1) == golden["direct_attempt1"]
    assert download.proxy_for_attempt(None, 2) == golden["env_fallback_attempt2"]
    assert download.proxy_for_attempt("http://p:8080", 0) == {"http": "http://p:8080", "https": "http://p:8080"}
    assert golden["proxy_given"] is True, "显式代理应始终使用"
