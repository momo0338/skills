"""media/download.py — 稳健下载（WP3/WP4 共用）。

复刻原项目 gen_segments.robust_download 的下载与完整性校验逻辑，收归一处：
- 即梦 CDN 国内直连，默认不走代理（显式绕开系统 http_proxy 环境变量）；
- 设了 download_proxy 才走，且直连失败时回退环境代理；
- >10KB 视为有效；可选解码体检（坏流重下，07-25 大鹅4 S2 实翻车）。

确定性函数 proxy_for_attempt 与 orchestration robust_download 解耦，便于离线单测。
下载本身用 urllib，不碰付费 API。
"""

from __future__ import annotations

import os
import time
import urllib.request

from .ffmpeg import decode_ok

# 有效文件最小字节数（>10KB）
MIN_BYTES = 10240


def proxy_for_attempt(download_proxy: str | None, attempt: int) -> dict | None:
    """选择第 attempt 次(0-based)重试用的代理配置（确定性）。

    - 显式给了 download_proxy → 始终走它；
    - 没给且前 2 次(attempt<2) → 直连（空 dict，屏蔽环境代理）；
    - 没给且第 3 次起 → 回退跟随环境代理（返回 None，用默认 opener）。
    """
    if download_proxy:
        return {"http": download_proxy, "https": download_proxy}
    if attempt < 2:
        return {}  # 直连,屏蔽环境代理
    return None  # 回退:跟随环境代理再试


def robust_download(
    url: str,
    dst: str,
    proxy: str | None = None,
    retries: int = 4,
    min_bytes: int = MIN_BYTES,
    verify_decode: bool = False,
) -> int:
    """稳健下载：重试 + 完整性校验。返回下载字节数。

    直连失败回退环境代理；>min_bytes 视为有效；verify_decode=True 时额外做解码体检
    （坏流重下）。全部失败抛 RuntimeError（含最后一次原因）。
    """
    last: str | None = None
    for i in range(retries):
        proxy_cfg = proxy_for_attempt(proxy, i)
        handler = urllib.request.ProxyHandler(proxy_cfg) if proxy_cfg is not None else urllib.request.ProxyHandler()
        op = urllib.request.build_opener(handler)
        urllib.request.install_opener(op)
        try:
            urllib.request.urlretrieve(url, dst)
            if os.path.getsize(dst) > min_bytes:  # >10KB 视为有效
                if verify_decode and not decode_ok(dst):
                    last = "解码体检不过(字节流损坏)"
                else:
                    return os.path.getsize(dst)
            else:
                last = "文件过小"
        except Exception as e:  # noqa: BLE001 - 下载异常统一重试
            last = f"{type(e).__name__}"
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"下载失败(重试{retries}次): {last}")
