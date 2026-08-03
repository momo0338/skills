"""generation/dreamina.py 离线确定性单测(命令构造 + 输出解析,不跑即梦 CLI)。

submit / wait_download 含 subprocess/网络,不在单测范围。
"""

import math

from dy_fanpai.generation import dreamina as D

# 与原项目一致的 hex id 正则匹配串(8 + 九个 4 + 末段 12 hex)
_UUID = "12345678-1234-1234-1234-1234-1234-1234-1234-1234-1234-123412341234"


def test_fitted_duration_unchanged_when_audio_shorter():
    assert D.fitted_duration(5, 4.0) == 5
    assert D.fitted_duration(5, 5.2) == 5  # 容差 0.25 内不算超长


def test_fitted_duration_raises_to_audio():
    assert D.fitted_duration(5, 6.0) == min(15, math.ceil(6.5))  # 7
    assert D.fitted_duration(5, 5.3) == 6  # 5.3 > 5.25 → ceil(5.8)=6


def test_fitted_duration_capped():
    assert D.fitted_duration(5, 20.0) == 15


def test_fit_duration_to_audio_mm(monkeypatch, tmp_path):
    monkeypatch.setattr(D, "wav_dur", lambda p: 6.0)
    (tmp_path / "S1.wav").write_bytes(b"RIFF")  # fit 仅当段 wav 存在才查时长
    seg = {"type": "mm", "seg": "S1", "duration": 5}
    D.fit_duration_to_audio(seg, str(tmp_path))
    assert seg["duration"] == 7


def test_fit_duration_to_audio_i2v_ignored(monkeypatch):
    monkeypatch.setattr(D, "wav_dur", lambda p: 9.0)
    seg = {"type": "i2v", "seg": "S2", "duration": 5}
    D.fit_duration_to_audio(seg, ".")
    assert seg["duration"] == 5  # i2v 不调时长


def test_build_submit_cmd_mm_no_audio(tmp_path):
    seg = {"type": "mm", "seg": "S1", "images": ["a.png", "b.png"],
           "prompt": "p", "duration": 5}
    args = D.build_submit_cmd(seg, None, "dreamina")
    assert args[0] == "dreamina" and args[1] == "multimodal2video"
    assert "--image" in args and args[args.index("--image") + 1] == "a.png"
    assert "--prompt" in args and args[args.index("--prompt") + 1] == "p"
    assert "--ratio" in args and args[args.index("--ratio") + 1] == "9:16"
    assert "--model_version" in args and "seedance2.0_vip" in args
    assert "--poll" in args and args[args.index("--poll") + 1] == "0"
    assert "--audio" not in args


def test_build_submit_cmd_mm_with_audio(tmp_path):
    wav = tmp_path / "S1.wav"
    wav.write_bytes(b"RIFF")
    seg = {"type": "mm", "seg": "S1", "images": ["a.png"], "prompt": "p", "duration": 5}
    args = D.build_submit_cmd(seg, str(tmp_path), "dreamina")
    assert "--audio" in args and args[args.index("--audio") + 1] == str(wav)


def test_build_submit_cmd_i2v():
    seg = {"type": "i2v", "seg": "S1", "anchor": "prod.png", "prompt": "p", "duration": 5}
    args = D.build_submit_cmd(seg, None, "dreamina")
    assert args[1] == "image2video"
    assert "--image" in args and args[args.index("--image") + 1] == "prod.png"
    assert "--audio" not in args


def test_parse_submit_out_ok():
    out = f'提交成功 id={_UUID} "credit_count": 120'
    sid, cc, _ = D.parse_submit_out(out)
    assert sid == _UUID
    assert cc == "120"


def test_parse_submit_out_none():
    sid, cc, _ = D.parse_submit_out("无任何 id 的输出")
    assert sid is None and cc == "?"


def test_is_fatal():
    assert D.is_fatal("error: out of allowed range") is True
    assert D.is_fatal("其他错误") is False


def test_parse_query_out_success():
    out = '"gen_status": "success", "video_url": "http://x.mp4"'
    assert D.parse_query_out(out) == ("success", "http://x.mp4")


def test_parse_query_out_fail():
    out = '"gen_status": "fail", "fail_reason": "参数非法"'
    assert D.parse_query_out(out) == ("fail", "参数非法")


def test_parse_query_out_pending():
    assert D.parse_query_out('"gen_status": "running"') == (None, None)
