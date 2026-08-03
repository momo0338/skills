"""reverse/ — P1 反推阶段（WP2 实现）。

- seed  : Ark Seed 2.1 Pro 单反推（腿 1）
- kimi  : Kimi K3 单反推（腿 2，双反推用）
- qwen  : 通义千问 Qwen 单反推（腿 3，百炼原生视频输入；experimental 未实机验收）
- merge : 双反推合并证据准备（机械部分，终审由人工裁决）

确定性函数（detect_cuts / video_info / make_upload_clip / build_prompt /
extract_json / merge.build_merged 及其纯 helper）与网络调用解耦，可离线单测。
"""

from . import kimi, qwen, seed
from .kimi import reverse as kimi_reverse
from .merge import (
    build_merged,
    gender_sig,
    merge,
    silence_spans,
    speech_overlap,
    ts_in_text,
)
from .qwen import reverse as qwen_reverse
from .seed import (
    SCHEMA,
    ark_reverse,
    build_prompt,
    detect_cuts,
    extract_json,
    make_upload_clip,
    reverse,
    video_info,
)

__all__ = [
    "seed",
    "kimi",
    "qwen",
    "merge",
    "reverse",
    "kimi_reverse",
    "qwen_reverse",
    "SCHEMA",
    "detect_cuts",
    "video_info",
    "make_upload_clip",
    "build_prompt",
    "ark_reverse",
    "extract_json",
    "build_merged",
    "silence_spans",
    "speech_overlap",
    "ts_in_text",
    "gender_sig",
]
