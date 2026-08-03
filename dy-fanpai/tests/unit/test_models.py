"""T1 单元与契约：枚举完整性、run.json 模型往返。"""

from dy_fanpai.models import (
    Gate,
    ProviderName,
    RunManifest,
    RunStatus,
    Stage,
)


def test_stage_has_seven_values():
    assert {s.value for s in Stage} == {
        "prepare",
        "reverse",
        "plan",
        "audio",
        "generate",
        "assemble",
        "deliver",
    }


def test_status_has_eleven_values():
    assert len(RunStatus) == 11
    assert RunStatus.QC_PASSED.value == "qc_passed"
    assert RunStatus.DELIVERED.value == "delivered"


def test_gate_has_four_values():
    assert {g.value for g in Gate} == {"rights", "plan", "cost", "qc"}


def test_provider_enum():
    assert ProviderName.DREAMINA.value == "dreamina"
    assert ProviderName.JIANYING.value == "jianying"


def test_run_manifest_roundtrip():
    run = RunManifest(project_id="demo", live=True, max_submits=3)
    dumped = run.model_dump_json()
    again = RunManifest.model_validate_json(dumped)
    assert again.project_id == "demo"
    assert again.max_submits == 3
    assert again.schema_version == 1
