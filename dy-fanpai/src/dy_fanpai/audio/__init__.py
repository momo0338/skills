"""dy_fanpai.audio — P3 音频：原音切段 + 2 秒闸 + timing + TTS/换声（WP3 实现）。"""

from . import service, tts_backend, voice, voicebox_client, voxcpm_client

__all__ = ["service", "voice", "tts_backend", "voicebox_client", "voxcpm_client"]
