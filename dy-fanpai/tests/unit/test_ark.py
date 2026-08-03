"""generation/ark.py 离线确定性单测(body 构造,不碰 Ark API)。

submit_* / wait_download 含网络,不在单测范围。
"""

from dy_fanpai.generation import ark as A


def test_build_i2v_body():
    body = A.build_i2v_body("YmI=", "image/png", "促销卖点", 5, "720p", "9:16", "modelX")
    assert body["model"] == "modelX"
    assert len(body["content"]) == 2
    img = body["content"][0]
    assert img["type"] == "image_url"
    assert img["image_url"]["url"] == "data:image/png;base64,YmI="
    txt = body["content"][1]
    assert txt["type"] == "text"
    assert "--resolution 720p --duration 5 --ratio 9:16" in txt["text"]


def test_build_mm_body_roles():
    body = A.build_mm_body([("image/png", "aa"), ("image/png", "bb")],
                            ("audio/wav", "cc"), "口播", 5, "720p", "9:16", "modelX")
    assert body["model"] == "modelX"
    imgs = [c for c in body["content"] if c["type"] == "image_url"]
    assert len(imgs) == 2
    assert all(c.get("role") == "reference_image" for c in imgs)
    aud = [c for c in body["content"] if c["type"] == "audio_url"]
    assert len(aud) == 1 and aud[0]["role"] == "reference_audio"
    assert any(c["type"] == "text" for c in body["content"])


def test_build_mm_body_no_audio():
    body = A.build_mm_body([("image/png", "aa")], None, "口播", 5)
    assert not any(c["type"] == "audio_url" for c in body["content"])


def test_build_t2v_body():
    body = A.build_t2v_body("纯产品", 5, "720p", "9:16", "modelX")
    assert body["model"] == "modelX"
    assert len(body["content"]) == 1
    assert body["content"][0]["type"] == "text"
    assert "--duration 5" in body["content"][0]["text"]
