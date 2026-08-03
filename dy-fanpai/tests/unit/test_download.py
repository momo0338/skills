"""media/download.py 离线确定性单测(代理选择逻辑,不跑真实下载)。"""

from dy_fanpai.media import download as D


def test_proxy_for_attempt_explicit_proxy():
    assert D.proxy_for_attempt("http://p", 0) == {"http": "http://p", "https": "http://p"}
    assert D.proxy_for_attempt("http://p", 3) == {"http": "http://p", "https": "http://p"}


def test_proxy_for_attempt_direct_first_two():
    assert D.proxy_for_attempt(None, 0) == {}
    assert D.proxy_for_attempt(None, 1) == {}


def test_proxy_for_attempt_fallback_env_after_two():
    assert D.proxy_for_attempt(None, 2) is None
    assert D.proxy_for_attempt(None, 3) is None


def test_min_bytes_constant():
    assert D.MIN_BYTES == 10240
