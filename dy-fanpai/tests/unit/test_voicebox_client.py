"""audio/voicebox_client.py 确定性单测（mock /profiles 响应，不碰真实服务）。

回归 2026-08-05 修复：find_profile_id 在 voicebox_profile_id 未配置时，
按 voicebox_profile_name 查找已有 profile，避免每段重复 create_profile。
"""

from dy_fanpai.audio import voicebox_client as VB
from dy_fanpai.config import Config


def _cfg(profile_id: str = "", profile_name: str = "dyfanpai-voice") -> Config:
    return Config(voicebox_profile_id=profile_id, voicebox_profile_name=profile_name)


def test_find_by_id_when_configured(monkeypatch):
    monkeypatch.setattr(
        VB, "_get_json",
        lambda cfg, path, timeout=15: [
            {"id": "abc-123", "name": "dyfanpai-voice"},
            {"id": "xyz-999", "name": "other"},
        ],
    )
    assert VB.find_profile_id(_cfg(profile_id="abc-123")) == "abc-123"


def test_find_by_name_when_id_missing(monkeypatch):
    """profile_id 未配置 → 按 profile_name 找到已有 profile（不再重复创建）。"""
    monkeypatch.setattr(
        VB, "_get_json",
        lambda cfg, path, timeout=15: [
            {"id": "abc-123", "name": "dyfanpai-voice"},
            {"id": "xyz-999", "name": "other"},
        ],
    )
    assert VB.find_profile_id(_cfg(profile_id="")) == "abc-123"


def test_find_by_default_name(monkeypatch):
    """profile_name 也未配置时回退默认名 dyfanpai-voice。"""
    monkeypatch.setattr(
        VB, "_get_json",
        lambda cfg, path, timeout=15: [{"id": "abc-123", "name": "dyfanpai-voice"}],
    )
    assert VB.find_profile_id(_cfg(profile_id="", profile_name="")) == "abc-123"


def test_not_found_returns_none(monkeypatch):
    monkeypatch.setattr(VB, "_get_json", lambda cfg, path, timeout=15: [])
    assert VB.find_profile_id(_cfg()) is None


def test_profile_id_precedes_name(monkeypatch):
    """配置了 id 时只按 id 匹配（不误匹配同名其他 profile）。"""
    monkeypatch.setattr(
        VB, "_get_json",
        lambda cfg, path, timeout=15: [
            {"id": "abc-123", "name": "dyfanpai-voice"},
            {"id": "xyz-999", "name": "dyfanpai-voice"},
        ],
    )
    assert VB.find_profile_id(_cfg(profile_id="xyz-999")) == "xyz-999"
