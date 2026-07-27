from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "download_with_metadata.py"
SPEC = importlib.util.spec_from_file_location("download_with_metadata", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def sample_detail() -> dict:
    return {
        "aweme_id": "7666337719992499300",
        "desc": "测试/标题",
        "create_time": 1784958347,
        "author": {
            "nickname": "作者",
            "sec_uid": "sec-1",
            "avatar_thumb": {"url_list": ["https://cdn/avatar.jpg?token=secret"]},
        },
        "statistics": {
            "play_count": 0,
            "digg_count": 12,
            "comment_count": 3,
        },
        "video": {
            "duration": 1000,
            "width": 1080,
            "height": 1920,
            "play_addr": {"url_list": ["https://cdn/playwm?id=1&token=secret"]},
            "origin_cover": {"url_list": ["https://cdn/cover.jpg"]},
        },
        "music": {
            "title": "原声",
            "play_url": {"url_list": ["https://cdn/music.m4a"]},
        },
        "text_extra": [{"hashtag_name": "测试"}, {"hashtag_name": "测试"}],
    }


class FakeClient:
    def __init__(self) -> None:
        self.resolved_urls: list[str] = []

    def resolve_share_url(self, url: str) -> str:
        self.resolved_urls.append(url)
        return "7635914294399817961"

    def download_file(self, url: str, output_path: str) -> str:
        path = Path(output_path)
        if "play" in url:
            path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"video")
        elif "music" in url:
            path.write_bytes(b"\x00\x00\x00\x18ftypM4A " + b"audio")
        else:
            path.write_bytes(b"\xff\xd8\xff\xe0" + b"image")
        return output_path

    def get_comments(self, aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
        return {
            "comments": [
                {
                    "cid": "c1",
                    "text": "评论",
                    "create_time": 1784958347,
                    "digg_count": 1,
                    "user": {"nickname": "用户", "sec_uid": "sec-user"},
                }
            ],
            "has_more": False,
            "cursor": 1,
        }


def options(**overrides) -> argparse.Namespace:
    values = {
        "archive": False,
        "cover": False,
        "avatar": False,
        "music": False,
        "include_raw": False,
        "comments": 0,
        "force": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class MetadataTests(unittest.TestCase):
    def test_resolve_bare_aweme_id_without_cache_or_network(self):
        calls = []
        value = MODULE.resolve_aweme_id(
            FakeClient(),
            lambda target: calls.append(target),
            "7635914294399817961",
        )
        self.assertEqual(value, "7635914294399817961")
        self.assertEqual(calls, [])

    def test_resolve_formal_video_url_without_redirect_request(self):
        client = FakeClient()
        value = MODULE.resolve_aweme_id(
            client,
            lambda target: self.fail("formal URL must not use the index cache"),
            "https://www.douyin.com/video/7635914294399817961?previous_page=app_code_link",
        )
        self.assertEqual(value, "7635914294399817961")
        self.assertEqual(client.resolved_urls, [])

    def test_resolve_iesdouyin_share_url_without_redirect_request(self):
        client = FakeClient()
        value = MODULE.resolve_aweme_id(
            client,
            lambda target: self.fail("share URL must not use the index cache"),
            "https://www.iesdouyin.com/share/video/7635914294399817961/",
        )
        self.assertEqual(value, "7635914294399817961")
        self.assertEqual(client.resolved_urls, [])

    def test_resolve_short_url_from_full_share_text(self):
        client = FakeClient()
        text = (
            "7.17 03/15 N@j.cA :0pm VyT:/ 开甲陀螺 "
            "https://v.douyin.com/lSvQylqiJwA/ 复制此链接，打开Dou音搜索"
        )
        value = MODULE.resolve_aweme_id(
            client,
            lambda target: self.fail("share text must not use the index cache"),
            text,
        )
        self.assertEqual(value, "7635914294399817961")
        self.assertEqual(client.resolved_urls, ["https://v.douyin.com/lSvQylqiJwA/"])

    def test_resolve_short_index_through_cache(self):
        client = FakeClient()
        value = MODULE.resolve_aweme_id(
            client,
            lambda target: "https://www.douyin.com/video/7635914294399817961"
            if target == "1"
            else "",
            "1",
        )
        self.assertEqual(value, "7635914294399817961")
        self.assertEqual(client.resolved_urls, [])

    def test_rejects_non_douyin_url(self):
        with self.assertRaisesRegex(MODULE.ArchiveError, "只接受"):
            MODULE.resolve_aweme_id(
                FakeClient(),
                lambda target: target,
                "https://example.com/video/7635914294399817961",
            )

    def test_normalize_preserves_unknown_play_count_as_null(self):
        value = MODULE.normalize_detail(sample_detail())
        self.assertEqual(value["identity"]["aweme_id"], "7666337719992499300")
        self.assertIsNone(value["statistics"]["play_count"])
        self.assertEqual(value["content"]["hashtags"], ["测试"])

    def test_raw_sanitizer_redacts_keys_and_signed_query_values(self):
        value = MODULE.sanitize_raw(
            {
                "cookie": "private",
                "signature": "作者简介",
                "url": "https://example.test/video?id=1&token=private&signature=s",
            }
        )
        self.assertEqual(value["cookie"], "<redacted>")
        self.assertEqual(value["signature"], "作者简介")
        self.assertEqual(value["url"], "https://example.test/video?id=1")

    def test_extract_assets_uses_unwatermarked_video_url(self):
        value = MODULE.extract_asset_urls(sample_detail())
        self.assertEqual(value["video"], ["https://cdn/play?id=1&token=secret"])
        self.assertEqual(value["cover"], ["https://cdn/cover.jpg"])

    def test_archive_writes_one_json_with_all_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            path, status = MODULE.archive_one(
                FakeClient(),
                sample_detail(),
                Path(directory),
                options(archive=True, include_raw=True, comments=1),
                "0.2.2",
            )
            self.assertEqual(status, "complete")
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["acquisition"]["status"], "complete")
            self.assertEqual(data["acquisition"]["detail_source"], "video_detail")
            self.assertEqual(data["comments"]["fetched"], 1)
            self.assertIsInstance(data["raw"], dict)
            roles = {item["role"] for item in data["local_assets"]}
            self.assertEqual(roles, {"video", "cover", "avatar", "music"})

    def test_archive_does_not_imply_raw_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path, status = MODULE.archive_one(
                FakeClient(),
                sample_detail(),
                Path(directory),
                options(archive=True),
                "0.2.2",
            )
            self.assertEqual(status, "complete")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("raw", data)
            self.assertNotIn("comments", data)
            self.assertNotIn("updated_at", data["acquisition"])
            self.assertNotIn("created_at_epoch", data["content"])
            self.assertNotIn("uid", data["author"])
            self.assertNotIn("ratio", data["platform_media"])

    def test_missing_optional_asset_is_partial_not_primary_failure(self):
        detail = sample_detail()
        detail["music"] = {}
        with tempfile.TemporaryDirectory() as directory:
            path, status = MODULE.archive_one(
                FakeClient(),
                detail,
                Path(directory),
                options(music=True),
                "0.2.2",
            )
            self.assertEqual(status, "partial")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["acquisition"]["components"]["video"], "complete")
            self.assertEqual(data["acquisition"]["components"]["music"], "failed")

    def test_resume_reuses_sidecar_when_title_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first_path, _ = MODULE.archive_one(
                FakeClient(),
                sample_detail(),
                output,
                options(),
                "0.2.2",
            )
            changed = sample_detail()
            changed["desc"] = "修改后的标题"
            second_path, status = MODULE.archive_one(
                FakeClient(),
                changed,
                output,
                options(),
                "0.2.2",
            )
            self.assertEqual(status, "complete")
            self.assertEqual(first_path, second_path)
            self.assertEqual(len(list(output.glob("*.metadata.json"))), 1)

            _, forced_status = MODULE.archive_one(
                FakeClient(),
                changed,
                output,
                options(force=True),
                "0.2.2",
            )
            self.assertEqual(forced_status, "complete")
            self.assertEqual(len(list(output.glob("*.metadata.json"))), 1)

    def test_partial_comments_make_overall_status_partial(self):
        class PartialCommentsClient(FakeClient):
            def get_comments(self, aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
                return {
                    "comments": [{"cid": "c1", "text": "一条", "user": {}}],
                    "has_more": True,
                    "cursor": cursor,
                }

        with tempfile.TemporaryDirectory() as directory:
            path, status = MODULE.archive_one(
                PartialCommentsClient(),
                sample_detail(),
                Path(directory),
                options(comments=10),
                "0.2.2",
            )
            self.assertEqual(status, "partial")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["comments"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
