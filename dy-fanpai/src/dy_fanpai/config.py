"""dy_fanpai 配置层（WP1 冻结）。

读取优先级（EXECUTION_PLAN §0.8）：
    进程环境变量  →  ~/.config/dy-fanpai/<name>  →  默认值

所有密钥与路径集中在此，杜绝原项目「部分硬编码绕过 config」的反模式
（见 WP0_BASELINE §9 冲突点 1）。新增二进制路径（dreamina / tts-drama /
ark 生成模型）一律走 DY_FANPAI_ 前缀环境变量，默认指向已知位置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.path.expanduser("~/.config/dy-fanpai"))


def _read(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    if v and v.strip():
        return v.strip()
    p = CONFIG_DIR / name.lower()
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return default


def _secret(name: str) -> str:
    v = _read(name)
    if not v:
        raise ConfigError(f"未找到 {name}。请设置环境变量或写入 {CONFIG_DIR / name.lower()}")
    return v


class ConfigError(RuntimeError):
    """配置缺失或非法。"""


@dataclass(frozen=True)
class Config:
    # --- 反推 / 评委（Ark）---
    ark_api_key: str = field(default="", repr=False)
    ark_seed_model: str = "doubao-seed-2-1-pro-260628"
    ark_gen_model: str = "doubao-seedance-2-0-260128"  # 原硬编码，现收归配置

    # --- 反推腿2（Kimi K3）---
    kimi_api_key: str = field(default="", repr=False)
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_k3_model: str = "kimi-k3"

    # --- 反推腿3（通义千问 Qwen，百炼原生视频输入；experimental，未实机验收）---
    dashscope_api_key: str = field(default="", repr=False)
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.7-plus"

    # --- 小云雀 ---
    xyq_access_key: str = field(default="", repr=False)
    xyq_video_model: str = "Seedance_2.0_mini_lite"

    # --- MiniMax H3（视频生成,多模态参考含 reference_audio；口型能力待实测）---
    minimax_api_key: str = field(default="", repr=False)
    minimax_model: str = "MiniMax-H3"
    minimax_base_url: str = "https://api.minimaxi.com"

    # --- TTS / 换声 ---
    cosyvoice_home: str = field(default_factory=lambda: os.path.expanduser("~/CosyVoice"))
    seedvc_home: str = field(default_factory=lambda: os.path.expanduser("~/seed-vc"))
    tts_drama_script: str = field(
        default_factory=lambda: os.path.expanduser(
            "~/.claude/skills/tts-drama/scripts/cosy_drama.py"
        )
    )

    # --- 即梦 CLI ---
    dreamina_bin: str = field(default_factory=lambda: os.path.expanduser("~/.local/bin/dreamina"))

    # --- 剪映草稿 ---
    jy_drafts: str = ""
    jy_python: str = field(
        default_factory=lambda: os.path.expanduser("~/.venv-jianying/bin/python")
    )

    # --- 下载代理 ---
    download_proxy: str = ""

    # --- 派生 ---
    proxy_env: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    @classmethod
    def load(cls) -> Config:
        """加载配置。缺失密钥不抛错（留空），由 key_status() 报告，
        保证 doctor 不阻塞开工（EXECUTION_PLAN §0.2 / 清单 U6 之前可离线）。"""
        proxy = _read("DY_FANPAI_DOWNLOAD_PROXY", "")
        return cls(
            ark_api_key=_read("ARK_API_KEY") or "",
            ark_seed_model=_read("ARK_SEED_MODEL", "doubao-seed-2-1-pro-260628"),
            ark_gen_model=_read("DY_FANPAI_ARK_GEN_MODEL", "doubao-seedance-2-0-260128"),
            kimi_api_key=_read("KIMI_API_KEY") or _read("MOONSHOT_API_KEY") or "",
            kimi_base_url=_read("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
            kimi_k3_model=_read("KIMI_K3_MODEL", "kimi-k3"),
            dashscope_api_key=_read("DASHSCOPE_API_KEY") or "",
            qwen_base_url=_read(
                "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            qwen_model=_read("QWEN_MODEL", "qwen3.7-plus"),
            xyq_access_key=_read("XYQ_ACCESS_KEY") or "",
            xyq_video_model=_read("XYQ_VIDEO_MODEL", "Seedance_2.0_mini_lite"),
            minimax_api_key=_read("MINIMAX_API_KEY") or "",
            minimax_model=_read("MINIMAX_MODEL", "MiniMax-H3"),
            minimax_base_url=_read("MINIMAX_BASE_URL", "https://api.minimaxi.com"),
            cosyvoice_home=_read("COSYVOICE_HOME", os.path.expanduser("~/CosyVoice")),
            seedvc_home=_read("DY_FANPAI_SEEDVC_HOME", os.path.expanduser("~/seed-vc")),
            tts_drama_script=_read(
                "DY_FANPAI_TTS_DRAMA",
                os.path.expanduser("~/.claude/skills/tts-drama/scripts/cosy_drama.py"),
            ),
            dreamina_bin=_read(
                "DY_FANPAI_DREAMINA_BIN", os.path.expanduser("~/.local/bin/dreamina")
            ),
            jy_drafts=_read("DY_FANPAI_JY_DRAFTS", ""),
            jy_python=_read(
                "DY_FANPAI_JY_PYTHON", os.path.expanduser("~/.venv-jianying/bin/python")
            ),
            download_proxy=proxy,
            proxy_env={"http": proxy, "https": proxy} if proxy else {},
        )

    def require_key(self, name: str) -> str:
        """显式取密钥，缺失才抛（业务模块调用）。"""
        val = getattr(self, name, "")
        if not val:
            raise ConfigError(f"未找到 {name}。请设置环境变量或写入 {CONFIG_DIR / name.lower()}")
        return val

    # 仅取真实密钥状态用于 doctor，不抛异常
    def key_status(self) -> dict[str, tuple[bool, str]]:
        def ok(name: str, val: str, min_len: int = 20) -> tuple[bool, str]:
            if not val:
                return (False, f"缺失 {name}")
            src = "环境变量" if os.environ.get(name) else "配置文件"
            return (len(val) > min_len, f"就位({src},{len(val)}字节)")

        return {
            "ARK_API_KEY": ok("ARK_API_KEY", self.ark_api_key, 30),
            "KIMI_API_KEY": ok("KIMI_API_KEY", self.kimi_api_key, 30),
            "XYQ_ACCESS_KEY": ok("XYQ_ACCESS_KEY", self.xyq_access_key, 20),
            "DASHSCOPE_API_KEY": ok("DASHSCOPE_API_KEY", self.dashscope_api_key, 20),
            "MINIMAX_API_KEY": ok("MINIMAX_API_KEY", self.minimax_api_key, 20),
        }
