#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRSS Client - Unified Python SDK for WeRSS API.
Zero external dependencies, uses standard library only.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def get_skill_dir() -> Path:
    """Return the root path of the werss skill directory."""
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    """Return the path to the werss data directory, ensuring it exists."""
    data_dir = get_skill_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    base_url: Optional[str] = None,
    ak: Optional[str] = None,
    sk: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Load WeRSS configuration in priority order:
    1. Explicit parameters passed to this function
    2. Environment variables (WERSS_BASE_URL, WERSS_ACCESS_KEY, WERSS_SECRET_KEY)
    3. Custom config_path if provided
    4. werss/config.json (skill root directory)
    5. ~/.werss/config.json (user home directory)
    """
    env_base_url = os.environ.get("WERSS_BASE_URL")
    env_ak = os.environ.get("WERSS_ACCESS_KEY")
    env_sk = os.environ.get("WERSS_SECRET_KEY")

    resolved_base_url = base_url if base_url is not None else env_base_url
    resolved_ak = ak if ak is not None else env_ak
    resolved_sk = sk if sk is not None else env_sk

    candidate_files = []
    if config_path:
        candidate_files.append(Path(config_path))
    candidate_files.append(get_skill_dir() / "config.json")
    candidate_files.append(Path.home() / ".werss" / "config.json")

    file_cfg = {}
    for p in candidate_files:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    file_cfg = json.load(f)
                    break
            except Exception:
                continue

    if resolved_base_url is None:
        resolved_base_url = file_cfg.get("base_url") or "https://rss.mmdai.top"
    if resolved_ak is None:
        resolved_ak = file_cfg.get("access_key")
    if resolved_sk is None:
        resolved_sk = file_cfg.get("secret_key")

    resolved_base_url = resolved_base_url.rstrip("/")
    return resolved_base_url, resolved_ak, resolved_sk


class WeRssClient:
    """Client for interacting with the WeRSS API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None,
        timeout: int = 30,
    ):
        self.base_url, self.ak, self.sk = load_config(
            config_path=config_path, base_url=base_url, ak=ak, sk=sk
        )
        self.timeout = timeout

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], List[Any], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Send an authenticated request to WeRSS API using AK/SK."""
        if not self.ak or not self.sk:
            raise ValueError(
                "Missing Access Key or Secret Key. Please configure WERSS_ACCESS_KEY and WERSS_SECRET_KEY "
                "or provide config.json."
            )

        url = f"{self.base_url}{endpoint}"
        if params:
            encoded_params = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            url = f"{url}?{encoded_params}" if "?" not in url else f"{url}&{encoded_params}"

        req_headers = {
            "Authorization": f"AK-SK {self.ak}:{self.sk}",
            "User-Agent": "WeRSS-Client/1.0",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        req_data = None
        if data is not None:
            if isinstance(data, (dict, list)):
                req_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
                req_headers["Content-Type"] = "application/json; charset=utf-8"
            elif isinstance(data, str):
                req_data = data.encode("utf-8")
            elif isinstance(data, bytes):
                req_data = data

        req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)

        to = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=to) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
                if "application/json" in content_type or raw.startswith(b"{") or raw.startswith(b"["):
                    return json.loads(raw.decode("utf-8"))
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_msg)
                return {"code": e.code, "error": err_json.get("detail", err_msg)}
            except Exception:
                return {"code": e.code, "error": err_msg}
        except Exception as e:
            return {"code": -1, "error": str(e)}

    # -------------------------------------------------------------------------
    # Subscription Management
    # -------------------------------------------------------------------------

    def subscribe_by_article(self, url: str) -> Dict[str, Any]:
        """Subscribe to a WeChat Official Account by parsing an article URL."""
        return self.request(
            method="POST",
            endpoint="/api/v1/wx/mps/by_article",
            params={"url": url},
        )

    def subscribe_by_name(self, mp_name: str) -> Dict[str, Any]:
        """Subscribe directly by Official Account name."""
        return self.request(
            method="POST",
            endpoint="/api/v1/wx/mps",
            data={"mp_name": mp_name},
        )

    def list_mps(
        self, page: int = 1, size: int = 20, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """List subscribed Official Accounts with pagination and optional keyword search."""
        params = {"page": page, "size": size}
        if keyword:
            params["keyword"] = keyword
        return self.request(method="GET", endpoint="/api/v1/wx/mps", params=params)

    def list_all_mps(self, batch_size: int = 50) -> List[Dict[str, Any]]:
        """Fetch all subscribed Official Accounts by traversing all pages."""
        all_mps = []
        page = 1
        while True:
            res = self.list_mps(page=page, size=batch_size)
            if not isinstance(res, dict) or res.get("code") not in (None, 0, 200):
                break
            items = res.get("data") or res.get("items") or []
            if isinstance(res, list):
                items = res
            if not items:
                break
            all_mps.extend(items)
            total = res.get("total")
            if total is not None and len(all_mps) >= total:
                break
            if len(items) < batch_size:
                break
            page += 1
        return all_mps

    def search_mps(self, keyword: str) -> Dict[str, Any]:
        """Search WeChat Official Accounts online."""
        kw_encoded = urllib.parse.quote(keyword)
        return self.request(method="GET", endpoint=f"/api/v1/wx/mps/search/{kw_encoded}")

    def update_mp(self, mp_id: str, start_page: int = 0, end_page: int = 1) -> Dict[str, Any]:
        """Trigger an instant scrape and sync update for an Official Account."""
        return self.request(
            method="GET",
            endpoint=f"/api/v1/wx/mps/update/{mp_id}",
            params={"start_page": start_page, "end_page": end_page},
        )

    def delete_mp(self, mp_id: str) -> Dict[str, Any]:
        """Delete an Official Account subscription."""
        return self.request(method="DELETE", endpoint=f"/api/v1/wx/mps/{mp_id}")

    # -------------------------------------------------------------------------
    # Articles & Feeds
    # -------------------------------------------------------------------------

    def get_articles(
        self,
        mp_id: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Query articles from subscribed Official Accounts."""
        params = {"page": page, "limit": limit}
        if mp_id:
            params["mp_id"] = mp_id
        if keyword:
            params["keyword"] = keyword
        return self.request(method="GET", endpoint="/api/v1/wx/articles", params=params)

    def export_opml(self) -> str:
        """Export all subscriptions as standard OPML 2.0 XML."""
        return self.request(method="GET", endpoint="/api/v1/wx/export/mps/opml")

    def get_feed_urls(self, mp_id: Optional[str] = None) -> Dict[str, str]:
        """Generate RSS, Atom, and JSON feed URLs for a specific MP or the global feed."""
        if mp_id:
            return {
                "rss": f"{self.base_url}/feed/{mp_id}.xml",
                "atom": f"{self.base_url}/feed/{mp_id}.atom",
                "json": f"{self.base_url}/feed/{mp_id}.json",
            }
        return {
            "rss": f"{self.base_url}/feed/all.xml",
            "atom": f"{self.base_url}/feed/all.atom",
            "json": f"{self.base_url}/feed/all.json",
        }

    # -------------------------------------------------------------------------
    # Tags Management
    # -------------------------------------------------------------------------

    def get_tags(self) -> Dict[str, Any]:
        """List all subscription tags."""
        return self.request(method="GET", endpoint="/api/v1/wx/tags")

    def create_tag(self, name: str, intro: str = "") -> Dict[str, Any]:
        """Create a new tag."""
        return self.request(
            method="POST",
            endpoint="/api/v1/wx/tags",
            data={"name": name, "intro": intro},
        )

    def tag_add_mps(self, tag_id: str, mp_ids: List[str]) -> Dict[str, Any]:
        """Add Official Accounts to a tag."""
        return self.request(
            method="POST",
            endpoint=f"/api/v1/wx/tags/{tag_id}/mps",
            data={"mp_ids": mp_ids},
        )


def api_request(
    base_url: str,
    ak: Optional[str],
    sk: Optional[str],
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Union[Dict[str, Any], List[Any], str, bytes]] = None,
) -> Any:
    """One-shot authenticated API request (module-level convenience wrapper)."""
    client = WeRssClient(base_url=base_url, ak=ak, sk=sk)
    return client.request(method=method, endpoint=endpoint, params=params, data=data)
