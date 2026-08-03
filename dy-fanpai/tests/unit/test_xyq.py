"""generation/xyq.py 离线确定性单测(参数构造,不跑 pippit-tool-cli)。

submit_* / wait_download 含 CLI subprocess,不在单测范围。
"""

from dy_fanpai.generation import xyq as X


def test_common_appends_audio_guard():
    a = X._common("促销卖点", 5, "720p", "9:16", True, "m1")
    joined = " ".join(a)
    assert "--prompt" in a
    assert "无人声,无背景音乐。" in joined
    assert "--model" in a and "m1" in a
    assert "--duration" in a and "5" in a


def test_common_no_guard():
    a = X._common("促销卖点", 5, "720p", "9:16", False, "m1")
    assert "无人声" not in a
    assert "--model" in a


def test_common_guard_skips_when_already_present():
    a = X._common("无人声旁白", 5, "720p", "9:16", True, "m1")
    # 已含"无人声"则不重复追加
    assert a.count("无人声,无背景音乐。") == 0


def test_build_i2v_args():
    args = X.build_i2v_args("img.png", "促销", 5, "720p", "9:16", "m1")
    assert args[0] == "generate-video"
    assert "--image" in args and args[args.index("--image") + 1] == "img.png"
    assert "无人声,无背景音乐。" in " ".join(args)


def test_build_mm_args_no_guard():
    args = X.build_mm_args(["a.png", "b.png"], "v.wav", "口播", 5, "720p", "9:16", "m1")
    assert args[0] == "generate-video"
    assert args[args.index("--image") + 1] == "a.png"
    assert "--audio" in args and args[args.index("--audio") + 1] == "v.wav"
    assert "无人声" not in args  # 口播段不加无人声限定


def test_build_t2v_args():
    args = X.build_t2v_args("纯产品", 5, "720p", "9:16", "m1")
    assert args[0] == "generate-video"
    assert "无人声,无背景音乐。" in " ".join(args)


def test_audio_guard_constant():
    assert X.AUDIO_GUARD == "无人声,无背景音乐。"
