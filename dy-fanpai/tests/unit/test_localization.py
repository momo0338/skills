"""planning/localization.py 离线单测。

apply_edits_dict 是 B 模式本地化的离线核心:把 edits 合并进 segments 的 dialogue,
口播(mm)段同时同步 prompt 里的 台词{...} 占位。★只改 dialogue,不动结构/路由/锚图。
"""

from dy_fanpai.planning import localization as L


def _segs():
    return [
        {
            "seg": "S1",
            "type": "mm",
            "dialogue": "旧口播词",
            "images": ["a.jpg"],
            "anchor_labels": ["锚1"],
            "prompt": "镜头描述...台词{旧口播词}结尾。",
            "shots": [{"in": 0.0, "out": 2.0}],
        },
        {
            "seg": "S2",
            "type": "i2v",
            "dialogue": "旧口播词2",
            "images": [],
            "anchor_labels": [],
            "prompt": "纯产品镜头,无台词占位。",
            "shots": [{"in": 2.0, "out": 4.0}],
        },
    ]


def test_syncs_mm_prompt_dialogue():
    segs = _segs()
    segs, changed, missing = L.apply_edits_dict(segs, {"S1": "新口播词"})
    assert segs[0]["dialogue"] == "新口播词"
    assert "台词{新口播词}" in segs[0]["prompt"]
    assert "台词{旧口播词}" not in segs[0]["prompt"]
    assert len(changed) == 1


def test_struct_untouched():
    segs = _segs()
    orig_s2_prompt = segs[1]["prompt"]
    segs, _, _ = L.apply_edits_dict(segs, {"S1": "新口播词", "S2": "新词2"})
    # S2 是 i2v,无台词{}占位,prompt 不变;dialogue 仍更新
    assert segs[1]["prompt"] == orig_s2_prompt
    assert segs[1]["dialogue"] == "新词2"
    # 结构字段保留
    assert segs[0]["images"] == ["a.jpg"]
    assert segs[0]["anchor_labels"] == ["锚1"]
    assert segs[0]["shots"] == [{"in": 0.0, "out": 2.0}]


def test_unedited_seg_unchanged():
    segs = _segs()
    segs, _, _ = L.apply_edits_dict(segs, {"S1": "新口播词"})
    assert segs[1]["dialogue"] == "旧口播词2"


def test_missing_seg_reported():
    segs = _segs()
    segs, changed, missing = L.apply_edits_dict(segs, {"S9": "不存在的段"})
    assert missing == ["S9"]
    assert changed == []


def test_wordcount_warn_on_big_delta():
    segs = _segs()
    segs, changed, _ = L.apply_edits_dict(segs, {"S1": "新口播词" * 20})
    assert changed
    assert "字数" in changed[0]
