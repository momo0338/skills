#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for werss.client module.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure skill root is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from werss.client import WeRssClient, load_config, get_skill_dir, get_data_dir


def test_get_skill_dir_and_data_dir():
    skill_dir = get_skill_dir()
    assert skill_dir.is_dir()
    assert (skill_dir / "SKILL.md").exists()

    data_dir = get_data_dir()
    assert data_dir.is_dir()
    assert data_dir.parent == skill_dir


def test_load_config_defaults(monkeypatch):
    monkeypatch.delenv("WERSS_BASE_URL", raising=False)
    monkeypatch.delenv("WERSS_ACCESS_KEY", raising=False)
    monkeypatch.delenv("WERSS_SECRET_KEY", raising=False)

    base_url, ak, sk = load_config(config_path="/nonexistent/path/config.json")
    # Should fallback to skill config.json if present, or defaults
    assert base_url.startswith("http")


def test_load_config_env_override(monkeypatch):
    monkeypatch.setenv("WERSS_BASE_URL", "https://custom.rss.example.com")
    monkeypatch.setenv("WERSS_ACCESS_KEY", "env_ak_123")
    monkeypatch.setenv("WERSS_SECRET_KEY", "env_sk_456")

    base_url, ak, sk = load_config()
    assert base_url == "https://custom.rss.example.com"
    assert ak == "env_ak_123"
    assert sk == "env_sk_456"


def test_client_init_and_feed_urls():
    client = WeRssClient(base_url="https://test.rss", ak="ak", sk="sk")
    assert client.base_url == "https://test.rss"
    assert client.ak == "ak"
    assert client.sk == "sk"

    feeds = client.get_feed_urls("MP_WXS_123")
    assert feeds["rss"] == "https://test.rss/feed/MP_WXS_123.xml"
    assert feeds["atom"] == "https://test.rss/feed/MP_WXS_123.atom"
    assert feeds["json"] == "https://test.rss/feed/MP_WXS_123.json"

    global_feeds = client.get_feed_urls()
    assert global_feeds["rss"] == "https://test.rss/feed/all.xml"


def test_client_request_missing_credentials():
    client = WeRssClient(base_url="https://test.rss", ak="", sk="")
    with pytest.raises(ValueError, match="Missing Access Key or Secret Key"):
        client.request("GET", "/api/v1/test")
