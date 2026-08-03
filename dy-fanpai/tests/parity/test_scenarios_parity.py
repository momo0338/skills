"""六类场景 segments golden 的 parity 测试（验收门 3 + 门 4）。

PARITY.md 待办 3：把六类场景的 `segments.golden.json` 纳入 parity 基线。
每类场景有合成输入（shotlist.json + assets.json）与冻结的 golden 输出，
测试断言：
- planner 输出与 golden 逐字段一致（确定性复现）；
- 场景特征断言（路由正确性）：A=混合 mm/i2v；产品迁移=含换品段；
  B=无 hero 图但口播正常；群戏=多人口播；旁白/纯产品=全 i2v；
- 通用不变量：每段 prompt 非空、时长在 [4,15]、warns 为列表。
"""

import json
import os

import pytest

from dy_fanpai.planning import planner

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "scenarios"))

# 场景 → 期望的段型分布（不约束顺序,只约束存在性）
SCENARIOS = {
    "A": {"must_have": {"mm", "i2v"}, "must_not": set()},
    "product_migration": {"must_have": {"mm"}, "must_not": set()},
    "B": {"must_have": {"mm"}, "must_not": set()},
    "group": {"must_have": {"mm"}, "must_not": set()},
    "narration": {"must_have": {"i2v"}, "must_not": {"mm"}},
    "pure_product": {"must_have": {"i2v"}, "must_not": {"mm"}},
}


def _load(p):
    return json.load(open(p, encoding="utf-8"))


@pytest.fixture(params=sorted(SCENARIOS))
def scenario(request):
    name = request.param
    segs = planner.plan(
        os.path.join(BASE, name, "shotlist.json"),
        os.path.join(BASE, name, "assets.json"),
        out_path=None,
    )
    golden = _load(os.path.join(BASE, name, "segments.golden.json"))
    return name, segs, golden


def test_segments_match_golden(scenario):
    """planner 输出与六类场景 golden 逐字段一致（确定性复现）。"""
    name, segs, golden = scenario
    assert segs == golden, f"{name} segments 与 golden 不一致"


def test_route_distribution(scenario):
    """场景路由特征：必须包含/不得包含的段型。"""
    name, segs, _ = scenario
    kinds = {s["type"] for s in segs}
    spec = SCENARIOS[name]
    assert spec["must_have"] <= kinds, f"{name} 缺段型,期望 {spec['must_have']} ⊆ {kinds}"
    assert not (spec["must_not"] & kinds), f"{name} 出现不应有的段型 {kinds & spec['must_not']}"


def test_segment_invariants(scenario):
    """通用不变量：prompt/dialogue 非空、时长 [4,15]、warns 列表、start<end。"""
    name, segs, _ = scenario
    for s in segs:
        assert s["prompt"].strip(), f"{name}/{s['seg']} prompt 为空"
        assert 4 <= s["duration"] <= 15, f"{name}/{s['seg']} 时长 {s['duration']} 超出 [4,15]"
        assert isinstance(s["warns"], list), f"{name}/{s['seg']} warns 非列表"
        assert s["end"] > s["start"], f"{name}/{s['seg']} end<=start"
        assert isinstance(s["opening_3s"], bool)
        assert s["shots"], f"{name}/{s['seg']} shots 为空"


def test_scenario_inputs_are_synthetic():
    """六类场景输入是合成数据（无大文件、无真实素材依赖），可离线复现。"""
    for name in SCENARIOS:
        for f in ("shotlist.json", "assets.json", "segments.golden.json"):
            p = os.path.join(BASE, name, f)
            assert os.path.exists(p), f"{name} 缺 {f}"
            assert os.path.getsize(p) < 1_000_000, f"{name}/{f} 疑似大文件混入"
