"""media/ffmpeg.py 离线确定性单测(命令构造 + 时长契约 + 解码体检逻辑,不跑真实 ffmpeg)。

dur / assemble 含 ffmpeg IO,用合成小视频做 T3 集成测试,不在本文件。
"""



from dy_fanpai.media import ffmpeg as F


def test_segment_duration_prefers_explicit_duration():
    segment = {"seg": "S1", "duration": 4, "start": 0, "end": 3}
    assert F.segment_duration(segment, 2.0) == 4.0


def test_segment_duration_uses_timeline_span():
    assert F.segment_duration({"seg": "S1", "start": 1.5, "end": 4.0}, 2.0) == 2.5


def test_segment_duration_falls_back_to_video_duration():
    assert F.segment_duration({"seg": "S1"}, 2.0) == 2.0


def test_normalize_args():
    args = F.normalize_args("clip.mp4", "nv.mp4")
    joined = " ".join(args)
    assert "scale=720:1280" in joined
    assert "setsar=1" in joined
    assert "libx264" in joined
    assert "crf" in joined and "20" in joined
    assert "yuv420p" in joined
    assert "-t" not in args  # 不传段长时保持原时长


def test_normalize_args_with_seg_dur():
    args = F.normalize_args("clip.mp4", "nv.mp4", seg_dur=4)
    assert "-t" in args and args[args.index("-t") + 1] == "4.00"


def test_pad_audio_args():
    args = F.pad_audio_args("a.wav", 5.0, "na.wav")
    joined = " ".join(args)
    assert "-af" in args and "apad" in joined
    assert "-t" in args and args[args.index("-t") + 1] == "5.0"
    assert "-ar" in args and args[args.index("-ar") + 1] == "44100"
    assert "-ac" in args and args[args.index("-ac") + 1] == "2"


def test_silence_args():
    args = F.silence_args(5.0, "na.wav")
    assert "anullsrc" in " ".join(args)
    assert "-t" in args and args[args.index("-t") + 1] == "5.0"


def test_concat_args_copy():
    args = F.concat_args("v.txt", "out.mp4", vcopy=True)
    assert "-f" in args and "concat" in args
    assert "-c" in args and "copy" in args


def test_concat_args_reencode():
    args = F.concat_args("v.txt", "out.mp4", vcopy=False)
    assert "libx264" in args


def test_mux_args():
    args = F.mux_args("vo.mp4", "vo.wav", "final.mp4")
    assert "-map" in args and "0:v" in args and "1:a" in args
    assert "aac" in args


def test_decode_ok_passes_clean(monkeypatch):
    class R:
        stderr = ""
    monkeypatch.setattr(F, "_run", lambda *a, **k: R())
    assert F.decode_ok("x.mp4") is True


def test_decode_ok_fails_on_bad_nal(monkeypatch):
    class R:
        stderr = "[h264 @ 0x0] Invalid NAL unit 0\n"
    monkeypatch.setattr(F, "_run", lambda *a, **k: R())
    assert F.decode_ok("x.mp4") is False


def test_decode_ok_fails_on_invalid_data(monkeypatch):
    class R:
        stderr = "Invalid data found when processing input\n"
    monkeypatch.setattr(F, "_run", lambda *a, **k: R())
    assert F.decode_ok("x.mp4") is False
