"""planner 对原始算法 golden 的结构化 parity 测试。

golden = 用**当前** plan_segments.py 跑 sample_shotlist+sample_assets 的权威输出
(见 tests/fixtures/original/A__planning.golden.json)。WP2 的目标是逐字节复刻该算法,
故最强的 parity 断言是「plan(shotlist, assets) == golden」。

注意:committed 的 references/sample_segments.json 是**旧版** plan_segments 产物(口播段
只取 hero 图,当前版取全部匹配表单),因此 parity 基准只用本目录下的 golden,不用 references。

golden 结构要点(来自实测,写测试时必须据此而非臆测):
- mm 段(口播出镜):含 images(>=1)、anchor_labels(>=1) 键,且 prompt 含固定 TAIL;
- i2v 段(纯产品/人物):**不含** images / anchor_labels 键;prompt 不含 TAIL;
- 每个段的 shots 是镜引用列表(字符串/整数混合,如 ['1a'] / ['1b', 2]),
  不是 shot dict,故不对其做时间连续性断言;images 数可多于 anchor_labels 数。
"""

import json
import os

import pytest

from dy_fanpai.planning import planner

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "original")
SHOTLIST = os.path.normpath(os.path.join(FIX, "A__planning_shotlist.json"))
ASSETS = os.path.normpath(os.path.join(FIX, "A__planning_assets.json"))
GOLDEN = os.path.normpath(os.path.join(FIX, "A__planning.golden.json"))


@pytest.fixture
def shotlist():
    return json.load(open(SHOTLIST, encoding="utf-8"))


@pytest.fixture
def assets():
    return json.load(open(ASSETS, encoding="utf-8"))


@pytest.fixture
def golden():
    return json.load(open(GOLDEN, encoding="utf-8"))


@pytest.fixture
def planned(shotlist, assets):
    return planner.plan(shotlist, assets, out_path=None)


def test_exact_json_parity(planned, golden):
    """最强断言:planner 输出与 golden 逐字节相等。"""
    assert planned == golden


def test_type_routing(planned):
    """mm=口播出镜(必有图锚键且非空);i2v=纯产品/人物(无图锚键)。"""
    for s in planned:
        if s["type"] == "mm":
            assert s["images"], f"{s['seg']} 口播段必须有图像锚"
            assert s["anchor_labels"], f"{s['seg']} 口播段必须有锚点标签"
        else:
            assert s["type"] == "i2v"
            assert "images" not in s, f"{s['seg']} i2v 段不应带 images 键"
            assert "anchor_labels" not in s, f"{s['seg']} i2v 段不应带 anchor_labels 键"


def test_anchor_labels_subset_of_images(planned):
    """锚标数 <= 图数(mm 段);i2v 段无此键。"""
    for s in planned:
        if s["type"] == "mm":
            assert len(s["anchor_labels"]) <= len(s["images"]), (
                f"{s['seg']} 锚标数 {len(s['anchor_labels'])} > 图数 {len(s['images'])}"
            )


def test_duration_within_cap(planned):
    """单段时长不超过 MAX_DUR(12s)硬约束。"""
    for s in planned:
        assert s["duration"] <= planner.MAX_DUR, (
            f"{s['seg']} 时长 {s['duration']} 超 MAX_DUR={planner.MAX_DUR}"
        )


def test_segment_basic_structure(planned):
    """每段:非空 shots 引用列表、start<end、duration 为正、opening_3s 为布尔。

    注:duration 是段目标生成时长(如 10s),不要求等于 end-start(实际镜跨度),
    二者由规划器独立赋值,故只校验各自合理。
    """
    for s in planned:
        assert isinstance(s["shots"], list) and s["shots"], f"{s['seg']} 空/非列表 shots"
        assert s["end"] > s["start"], f"{s['seg']} end<=start"
        assert s["duration"] > 0, f"{s['seg']} duration 非正"
        assert isinstance(s["opening_3s"], bool)


def test_mm_prompt_carries_dialogue_marker(planned):
    """口播段 prompt 必须含 台词{...} 占位(供本地化/口型同步)。"""
    for s in planned:
        if s["type"] == "mm":
            assert "台词{" in s["prompt"], f"{s['seg']} 口播 prompt 缺 台词{{}}"


def test_dialogue_present_for_mm(planned):
    """口播段必须有 dialogue 文本。"""
    for s in planned:
        if s["type"] == "mm":
            assert s["dialogue"], f"{s['seg']} 口播段缺 dialogue"


def test_mm_prompt_fixed_tail(planned):
    """口播(mm)段 prompt 必须带冻结期固定的 TAIL(无字幕/无水印/无BGM)。"""
    for s in planned:
        if s["type"] == "mm":
            assert planner.TAIL in s["prompt"], f"{s['seg']} mm prompt 缺 TAIL 固定尾"


def test_completeness_check_runs_on_shot_dicts(shotlist):
    """completeness_check 接收 shot dicts(带 action),可调用且不抛异常。"""
    shots = shotlist["shots"][:3]
    warns = planner.completeness_check("示例 prompt", shots)
    assert isinstance(warns, list)
