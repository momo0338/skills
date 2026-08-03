"""reverse/merge.py 离线确定性单测(不碰 ffmpeg/网络)。

build_merged 是纯函数:输入 seed/alt 两份反推 JSON + 静音区间 sil + 视频时长 dur,
输出 (merged_draft, dossier_lines, frame_ts, n_warns)。本文件校验其机械合并逻辑与
「静音闸 / 性别信号」两条业务铁律。
"""

from dy_fanpai.reverse.merge import (
    _first_speech,
    build_merged,
    speech_overlap,
)


def _seed(shots):
    return {
        "overall": {
            "product": "测试品",
            "style": "种草",
            "why_viral": "爆点",
            "full_transcript": "台词一。台词二。",
        },
        "shots": shots,
    }


def _alt(shots):
    return {
        "overall": {
            "product": "测试品A",
            "style": "探店",
            "why_viral": "情绪",
            "full_transcript": "台词一。台词二。",
        },
        "shots": shots,
    }


def _shot(shot_id, lo, hi, **kw):
    base = {
        "shot_id": shot_id,
        "start": float(lo),
        "end": float(hi),
        "shot_size": "中景",
        "camera": "",
        "subject": "",
        "action": "",
        "scene": "",
        "lighting": "",
        "person": "",
        "host_on_camera": False,
        "product_in_frame": "",
        "product_role": "none",
        "onscreen_text": "",
        "dialogue": "",
        "key_colors": "",
    }
    base.update(kw)
    return base


def test_alt_fields_present():
    seed = _seed(
        [
            _shot(1, 0.0, 2.0, camera="", dialogue="台词一。", person="1女"),
            _shot(2, 2.0, 4.0, camera="推", dialogue="", person=""),
        ]
    )
    alt = _alt(
        [
            _shot(1, 0.0, 2.0, camera="推", dialogue="台词一。", person="1女"),
            _shot(2, 2.0, 4.0, camera="推", dialogue="", person=""),
        ]
    )
    merged, _, _, _ = build_merged(seed, alt, [(2.0, 4.0)], 4.0, "K3")
    for sh in merged["shots"]:
        assert "__alt_camera" in sh
        assert "__alt_action" in sh
        assert "__alt_transition_in" in sh
    assert "__alt_overall" in merged
    assert merged["__alt_overall"]["product"] == "测试品A"


def test_silence_gate_triggers():
    """整段落在静音区的口播 → 触发静音闸警告,台词应移 onscreen_text。"""
    seed = _seed([_shot(1, 1.0, 3.0, dialogue="疑似幻听台词", person="")])
    alt = _alt([_shot(1, 1.0, 3.0, dialogue="疑似幻听台词", person="")])
    sil = [(1.0, 3.0)]
    merged, md, frame_ts, n_warns = build_merged(seed, alt, sil, 3.0, "K3")
    assert n_warns >= 1
    assert any("静音闸" in line and "台词应移入" in line for line in md)


def test_no_false_silence_gate_when_speech_present():
    """区间内有真实人声(非静音)的口播不误报。"""
    seed = _seed([_shot(1, 0.0, 2.0, dialogue="真实口播", person="1女")])
    alt = _alt([_shot(1, 0.0, 2.0, dialogue="真实口播", person="1女")])
    sil = [(2.0, 4.0)]  # 静音在镜头之后
    _, _, _, n_warns = build_merged(seed, alt, sil, 4.0, "K3")
    assert n_warns == 0


def test_gender_signal_flag():
    """Seed 与 alt 性别不一致 → dossier 标 ⚑性别/人数分歧。

    gender_sig 按 '男'/'女' 字符计数,故需用真实性别差异(女 vs 男)触发,
    '1女' vs '2女' 都只含 1 个'女'字,不会判为分歧。
    """
    seed = _seed([_shot(1, 0.0, 2.0, person="1女", dialogue="")])
    alt = _alt([_shot(1, 0.0, 2.0, person="1男", dialogue="")])
    _, md, _, _ = build_merged(seed, alt, [(2.0, 4.0)], 4.0, "K3")
    assert any("性别/人数分歧" in line for line in md)


def test_first_speech():
    """首个人声=连续首部静音之后的时间点(间隔<=0.05 视为连续静音)。"""
    assert _first_speech([(0.0, 2.0), (2.5, 4.0)]) == 2.0
    assert _first_speech([(1.0, 3.0)]) == 0.0
    # (0,0.5) 与 (0.55,1.0) 间隔 0.05 视为连续 → 末段静音结束于 1.0
    assert _first_speech([(0.0, 0.5), (0.55, 1.0), (1.2, 2.0)]) == 1.0


def test_speech_overlap_known():
    sil = [(1.0, 2.0)]
    assert abs(speech_overlap(0.0, 3.0, sil) - 2.0) < 1e-6
    assert abs(speech_overlap(1.0, 2.0, sil) - 0.0) < 1e-6


def test_frame_ts_bounded_and_sorted():
    seed = _seed([_shot(1, 0.0, 2.0), _shot(2, 2.0, 4.0)])
    alt = _alt([_shot(1, 0.0, 2.0), _shot(2, 2.0, 4.0)])
    _, _, frame_ts, _ = build_merged(seed, alt, [(2.0, 4.0)], 4.0, "K3")
    assert frame_ts == sorted(frame_ts)
    assert all(0.0 <= t <= 4.0 for t in frame_ts)
