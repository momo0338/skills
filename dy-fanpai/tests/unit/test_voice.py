"""audio/voice.py 离线确定性单测(不碰 CosyVoice/Seed-VC)。

只测纯函数:apply_pron_fix(参→身 + CAN 词黑名单) / parse_speakers /
resolve_target / seedvc_status / cosyvoice_status。
synth / convert 重型 subprocess 不在单测范围。
"""


import pytest

from dy_fanpai.audio import voice as V
from dy_fanpai.config import Config


def test_apply_pron_fix_haishen_default():
    """默认海参模式: 参→身(同音同调)。"""
    assert V.apply_pron_fix("海参很好吃") == "海身很好吃"


def test_apply_pron_fix_protects_can_words():
    """CAN 词(参加/参考...)被保护,不参与 参→身。"""
    assert V.apply_pron_fix("参加比赛") == "参加比赛"
    assert V.apply_pron_fix("参考一下") == "参考一下"


def test_apply_pron_fix_mixed():
    assert V.apply_pron_fix("海参参加") == "海身参加"


def test_apply_pron_fix_haishen_off():
    """haishen=False: 只用自定义词表,不做 参→身。"""
    assert V.apply_pron_fix("海参", haishen=False) == "海参"


def test_apply_pron_fix_extra_then_haishen():
    """先自定义词表,再 参→身,二者不冲突。"""
    assert V.apply_pron_fix("海参参加", extra={"海参": "HS"}) == "HS参加"


def test_can_words_byte_identical():
    """CAN_WORDS 是读音修正的硬约束,顺序无关但集合须固定。"""
    assert len(V.CAN_WORDS) == 17
    assert "参加" in V.CAN_WORDS and "参保" in V.CAN_WORDS


def test_parse_speakers_no_label():
    assert V.parse_speakers("你好世界") == [("B", "你好世界")]


def test_parse_speakers_with_labels():
    assert V.parse_speakers("A：你好 B：他好") == [("A", "你好"), ("B", "他好")]


def test_parse_speakers_chinese_labels():
    assert V.parse_speakers("甲：各位") == [("甲", "各位")]


def test_parse_speakers_leading_text_default():
    assert V.parse_speakers("前奏 A：开说") == [("B", "前奏"), ("A", "开说")]


def test_resolve_target_existing_path(tmp_path):
    wav = tmp_path / "ref.wav"
    wav.write_bytes(b"RIFF")
    assert V.resolve_target(str(wav)) == str(wav)


def test_resolve_target_builtin_match(tmp_path):
    (tmp_path / "内置女声1_古丽.wav").write_bytes(b"x")
    (tmp_path / "内置男声1_广智.wav").write_bytes(b"x")
    got = V.resolve_target("男声1", builtin_dir=str(tmp_path))
    assert got.endswith("内置男声1_广智.wav")


def test_resolve_target_missing_raises(tmp_path):
    with pytest.raises(ValueError):
        V.resolve_target("不存在的音色", builtin_dir=str(tmp_path))


def test_seedvc_status_missing():
    ok, msg = V.seedvc_status("/no/such/home")
    assert ok is False and "Seed-VC 未装" in msg


def test_seedvc_status_no_venv(tmp_path):
    ok, msg = V.seedvc_status(str(tmp_path))
    assert ok is False and ".venv" in msg


def test_seedvc_status_ok(tmp_path):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    ok, msg = V.seedvc_status(str(tmp_path))
    assert ok is True and "就位" in msg


def test_cosyvoice_status_missing(tmp_path):
    cfg = Config(cosyvoice_home=str(tmp_path))
    ok, msg = V.cosyvoice_status(cfg)
    assert ok is False


def test_cosyvoice_status_ok(tmp_path):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    script = tmp_path / "cosy_drama.py"
    script.write_text("")
    cfg = Config(cosyvoice_home=str(tmp_path), tts_drama_script=str(script))
    ok, msg = V.cosyvoice_status(cfg)
    assert ok is True
