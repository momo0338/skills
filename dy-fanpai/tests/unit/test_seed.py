"""reverse/seed.py 离线确定性单测(不碰 ffmpeg/网络)。

只测纯函数:build_prompt(段边界 → 提示词)、extract_json(抠 JSON)。
ark_reverse/reverse 等网络调用不在单测范围。
"""

import json

from dy_fanpai.reverse import seed as S


def test_build_prompt_segment_count():
    """段数 = 硬切数 + 1;提示词须含该段数与 SCHEMA。"""
    cuts = [3.5, 8.2]
    duration = 12.0
    p = S.build_prompt(cuts, duration)
    assert f"{len(cuts) + 1} 个镜头段" in p
    assert S.SCHEMA in p
    # 业务铁律:静音字幕残留只进 onscreen_text,严禁进 dialogue
    assert "严禁写进 dialogue" in p
    assert "onscreen_text" in p


def test_build_prompt_without_cuts():
    """无硬切 → 整段为 1 段。"""
    p = S.build_prompt([], 10.0)
    assert "1 个镜头段" in p


def test_extract_json_plain():
    txt = '{"overall": {"product": "x"}, "shots": []}'
    assert S.extract_json(txt) == {"overall": {"product": "x"}, "shots": []}


def test_extract_json_fenced():
    txt = '```json\n{"a": 1}\n```'
    assert S.extract_json(txt) == {"a": 1}


def test_extract_json_with_garbage():
    txt = '好的,这是结果:\n{"k": [1,2,3]} 完毕'
    assert S.extract_json(txt) == {"k": [1, 2, 3]}


def test_extract_json_nested():
    obj = {"overall": {"x": 1}, "shots": [{"shot_id": 1, "start": 0.0, "end": 2.0}]}
    raw = "噪声" + json.dumps(obj, ensure_ascii=False) + "尾噪声"
    assert S.extract_json(raw) == obj
