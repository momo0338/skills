#!/usr/bin/env python3
"""用户级 ijob 技能适配器。

只负责运行时发现、版本校验和 JSON 错误归一化；业务查询完全委托 ijob
自己的公共契约，不解析旧 CLI 文本、不访问 SQLite。

纪律：显式 `--ijob-home` 或 `IJOB_HOME` 一旦给出就必须被尊重，候选目录
校验不通过要直接报错，禁止静默回退到其他绝对路径。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_CONTRACT = "ijob.skill"
SKILL_SCHEMA_VERSION = "1.0.0"
CAMPAIGN_SEMANTICS_SCHEMA_VERSION = 3
MIN_CONTRACT = (1, 0, 0)
MAX_CONTRACT_MAJOR = 1
OPERATIONS = (
    "discover",
    "health",
    "status",
    "backlog",
    "inbox",
    "next",
    "brief",
    "info",
    "cycle-status",
)
ENVELOPE_REQUIRED = (
    "schema_version",
    "contract",
    "operation",
    "generated_at",
    "data",
    "meta",
    "warnings",
)


class SkillError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.exit_code = exit_code


def _generated_at() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _config_home() -> str | None:
    config = Path.home() / ".config" / "ijob" / "config.json"
    if not config.is_file():
        return None
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    home = data.get("ijob_home") if isinstance(data, dict) else None
    return str(home) if home else None


def _conventional_homes() -> list[str]:
    values: list[str] = []
    command = shutil.which("ijob")
    if command:
        try:
            values.append(str(Path(command).resolve().parent.parent))
        except (OSError, RuntimeError):
            pass
    values.extend([
        str(Path.home() / "src" / "ijob"),
        str(Path.cwd() / "ijob"),
    ])
    return values


def candidate_homes(explicit: str | None = None) -> tuple[list[Path], dict[str, Any]]:
    """返回 (候选目录, 来源说明)。

    `sources` 让调用方能区分「显式指定失败」与「自动发现失败」，这是禁止
    静默回退的前提。
    """
    values: list[str] = []
    sources: dict[str, Any] = {}
    if explicit:
        values.append(explicit)
        sources["explicit"] = explicit
    env_home = os.environ.get("IJOB_HOME")
    if env_home:
        values.append(env_home)
        sources["environment"] = env_home
    config_home = _config_home()
    if config_home:
        values.append(config_home)
        sources["user_config"] = config_home
    conventional = _conventional_homes()
    if conventional:
        sources["conventional_count"] = len(conventional)
    values.extend(conventional)

    unique: list[Path] = []
    seen: set[str] = set()
    for value in values:
        try:
            path = Path(value).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique, sources


def validate_home(home: Path) -> Path:
    required = (
        home / "api" / "contract.py",
        home / "api" / "public_contract.json",
        home / "api" / "public_contract.schema.json",
    )
    missing = [item.name for item in required if not item.is_file()]
    if missing:
        raise SkillError(
            "ijob_home_invalid",
            "候选目录不是完整 ijob 公共契约运行时",
            details={"missing": missing},
        )
    return home


def discover_home(explicit: str | None = None) -> Path:
    candidates, sources = candidate_homes(explicit)
    if explicit:
        # 显式指定即视为硬约束：只有它自己可用，否则直接失败而非回退。
        for home in candidates[:1]:
            try:
                return validate_home(home)
            except SkillError as exc:
                raise SkillError(
                    "ijob_home_invalid",
                    f"显式指定的 ijob 目录不可用，已停止且不会回退到其他路径: {exc.message}",
                    details={"source": "explicit", "missing": exc.details.get("missing", [])},
                ) from exc
    env_home = os.environ.get("IJOB_HOME")
    if env_home:
        target = Path(env_home).expanduser().resolve()
        try:
            return validate_home(target)
        except SkillError as exc:
            raise SkillError(
                "ijob_home_invalid",
                f"IJOB_HOME 指向的目录不是完整 ijob 运行时，已停止且不会回退: {exc.message}",
                details={"source": "environment", "missing": exc.details.get("missing", [])},
            ) from exc
    for home in candidates:
        try:
            return validate_home(home)
        except SkillError:
            continue
    raise SkillError(
        "ijob_home_not_found",
        "未发现 ijob；请设置 IJOB_HOME 或 ~/.config/ijob/config.json",
        details={"checked_candidates": len(candidates), "sources": sources},
    )


def version_tuple(value: str) -> tuple[int, int, int]:
    try:
        parts = str(value).split(".")
        if len(parts) != 3:
            raise ValueError
        return tuple(int(item) for item in parts)  # type: ignore[return-value]
    except (TypeError, ValueError) as exc:
        raise SkillError(
            "contract_version_invalid",
            "ijob 公共契约版本格式无效",
            details={"actual": value},
        ) from exc


def validate_envelope(payload: Any) -> dict[str, Any]:
    """校验 ijob.public 成功/错误响应，以及本技能自己生成的 ijob.skill 错误外壳。"""
    if not isinstance(payload, dict):
        raise SkillError("invalid_response", "ijob 未返回 JSON 对象")

    contract = payload.get("contract")
    if contract == SKILL_CONTRACT:
        return _validate_skill_error(payload)
    if contract != "ijob.public":
        raise SkillError("contract_mismatch", "响应不是 ijob.public 契约")

    missing = [key for key in ENVELOPE_REQUIRED if key not in payload]
    if missing:
        raise SkillError(
            "invalid_response",
            "ijob 响应缺少契约字段",
            details={"missing": missing},
        )
    version = version_tuple(str(payload.get("schema_version")))
    if version[0] != MAX_CONTRACT_MAJOR or version < MIN_CONTRACT:
        raise SkillError(
            "contract_incompatible",
            "ijob 公共契约版本与技能不兼容",
            details={"skill": "1.x >= 1.0.0", "actual": payload.get("schema_version")},
        )
    meta = payload.get("meta")
    if (
        not isinstance(meta, dict)
        or meta.get("read_only") is not True
        or meta.get("source") != "ijob"
    ):
        raise SkillError("invalid_response", "ijob 响应未声明稳定只读边界")
    if meta.get("campaign_semantics_version") != CAMPAIGN_SEMANTICS_SCHEMA_VERSION:
        raise SkillError(
            "semantics_incompatible",
            "ijob 响应绑定的招聘业务语义版本与技能不兼容",
            details={
                "expected": CAMPAIGN_SEMANTICS_SCHEMA_VERSION,
                "actual": meta.get("campaign_semantics_version"),
            },
        )
    error = payload.get("error")
    if error is not None and not isinstance(error, dict):
        raise SkillError("invalid_response", "ijob 响应 error 字段不是对象")
    return payload


def _validate_skill_error(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in ("schema_version", "contract", "operation", "generated_at", "data", "meta", "error") if key not in payload]
    if missing:
        raise SkillError(
            "invalid_response",
            "ijob.skill 错误外壳缺少字段",
            details={"missing": missing},
        )
    if payload.get("schema_version") != SKILL_SCHEMA_VERSION:
        raise SkillError(
            "contract_incompatible",
            "ijob.skill 错误外壳版本不兼容",
            details={"expected": SKILL_SCHEMA_VERSION, "actual": payload.get("schema_version")},
        )
    meta = payload.get("meta")
    if (
        not isinstance(meta, dict)
        or meta.get("read_only") is not True
        or meta.get("source") != "ijob.skill"
        or meta.get("campaign_semantics_version") != CAMPAIGN_SEMANTICS_SCHEMA_VERSION
    ):
        raise SkillError("invalid_response", "ijob.skill 错误外壳未声明稳定只读边界")
    if not isinstance(payload.get("error"), dict) or not payload["error"].get("code"):
        raise SkillError("invalid_response", "ijob.skill 错误外壳缺少 error.code")
    return payload


def call_contract(home: Path, operation: str, contract_args: list[str]) -> dict[str, Any]:
    python = os.environ.get("IJOB_PYTHON") or sys.executable
    command = [python, str(home / "api" / "contract.py"), operation, *contract_args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SkillError("python_missing", "配置的 Python 运行时不存在") from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillError("contract_timeout", "ijob 公共契约执行超时", exit_code=5) from exc
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SkillError(
            "invalid_response",
            "ijob 公共契约未返回有效 JSON",
            details={"exit_code": result.returncode, "stderr_present": bool(result.stderr.strip())},
        ) from exc
    payload = validate_envelope(payload)
    if payload.get("error"):
        error = payload["error"]
        code = str(error.get("code") or "contract_error")
        message = str(error.get("message") or "ijob 公共契约返回错误")
        details = error.get("details") if isinstance(error.get("details"), dict) else {}
        raise SkillError(code, message, details=details, exit_code=result.returncode or 2)
    if result.returncode != 0:
        raise SkillError(
            "contract_process_failed",
            "ijob 公共契约进程返回非零退出码",
            details={"exit_code": result.returncode},
        )
    return payload


WRITE_CONTRACT = "ijob.write"
WRITE_SCHEMA_VERSION = "1.0.0"


def call_write_gate(
    home: Path,
    *,
    write_op: str | None,
    write_args: list[str],
    apply_: bool,
    timeout: int | None = None,
    allow_degraded_backup: bool = False,
    python_exe: str | None = None,
) -> dict[str, Any]:
    """调用 ijob 写网关。

    与只读路径完全隔离：
      * 只读响应外壳恒为 `ijob.public`（meta.read_only=true）；
      * 写响应外壳为 `ijob.write`（meta.read_only=false, meta.mutating=true）。
    网关内部强制「单次 apply + 自动备份 + SHA-256 校验」，技能层不重复实现。
    """
    if not write_op:
        raise SkillError("invalid_request",
                          "write 需要 --write-op（如 promote / probe / reconcile-articles）")
    argv = [
        python_exe or sys.executable,
        str(home / "api" / "writegate.py"),
        "run",
        write_op,
        *write_args,
    ]
    if apply_:
        argv.append("--apply")
    if timeout is not None:
        argv.extend(["--timeout", str(timeout)])

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=(timeout or 3600) + 120)
    except subprocess.TimeoutExpired as err:
        raise SkillError("operation_timeout",
                         "写操作超时，未确认写入状态；请用备份核对") from err

    raw = proc.stdout.strip()
    if not raw:
        raise SkillError("invalid_response",
                         f"写网关无输出（退出码 {proc.returncode}）: {proc.stderr[:300]}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as err:
        raise SkillError("invalid_response", f"写网关输出非 JSON: {raw[:200]}") from err

    if payload.get("contract") != WRITE_CONTRACT:
        raise SkillError("contract_mismatch",
                         f"写网关返回契约异常: {payload.get('contract')}")
    version = payload.get("schema_version")
    if not isinstance(version, str) or not version.startswith("1."):
        raise SkillError("contract_incompatible", f"写契约版本不兼容: {version}")
    meta = payload.get("meta") or {}
    if meta.get("source") != "ijob" or meta.get("mutating") is not True:
        raise SkillError("invalid_response", "写响应外壳未声明 mutating 边界")

    data = payload.get("data") or {}
    if not apply_ and data.get("backup") is not None and not allow_degraded_backup:
        raise SkillError("degraded_backup",
                         "dry-run 模式却产生了备份，违反门禁，已中止")
    return payload


def make_skill_error(operation: str, error: SkillError) -> dict[str, Any]:
    return {
        "contract": SKILL_CONTRACT,
        "schema_version": SKILL_SCHEMA_VERSION,
        "operation": operation,
        "generated_at": _generated_at(),
        "data": None,
        "meta": {
            "read_only": True,
            "source": "ijob.skill",
            "campaign_semantics_version": CAMPAIGN_SEMANTICS_SCHEMA_VERSION,
        },
        "warnings": [],
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.exit_code == 5,
            "details": error.details,
        },
    }


class _JsonArgumentParser(argparse.ArgumentParser):
    """参数错误同样输出 JSON，不向 stderr 吐 usage 文本。"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._raw_argv: list[str] = []

    def parse_known_args(self, args: Any = None, namespace: Any = None) -> tuple[Any, list[str]]:
        if args is None:
            self._raw_argv = list(sys.argv[1:])
        elif isinstance(args, (list, tuple)):
            self._raw_argv = [str(item) for item in args]
        else:
            self._raw_argv = []
        return super().parse_known_args(args, namespace)

    def _guess_operation(self) -> str:
        for token in self._raw_argv:
            if not token.startswith("-"):
                return token
        return "unknown"

    def error(self, message: str) -> Any:  # type: ignore[override]
        payload = make_skill_error(
            self._guess_operation(),
            SkillError("invalid_request", f"命令行参数无效: {message}"),
        )
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(prog="ijob.py", description="ijob 独立项目数据适配器（只读契约 + 受控写网关）")
    parser.add_argument("operation", choices=OPERATIONS + ("write",))
    parser.add_argument("--ijob-home", help="覆盖 ijob 安装目录；无效时直接报错，不回退")
    parser.add_argument("--python", help="覆盖解释器；不持久化")
    parser.add_argument("--campaign-id", type=int)
    parser.add_argument(
        "--query",
        help="info 的单个完整关键词（只收一个，不拆词）；纯数字也按关键词处理",
    )
    parser.add_argument("--recruit-type", choices=("校招", "社招"))
    parser.add_argument("--include-written", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int)
    parser.add_argument("--cycle-config", type=Path, help="仅供隔离环境诊断")
    parser.add_argument("--pretty", action="store_true")

    # ── 写网关专用（仅 operation == "write" 时生效）──
    parser.add_argument("--write-op", help="写操作名，如 promote / ignore / probe / daily / "
                                          "reconcile-articles / sync-cycle")
    parser.add_argument("--apply", action="store_true",
                        help="真正写库；不加则只 dry-run 预演（不备份也不写）")
    parser.add_argument("--write-arg", action="append", default=[],
                        help="传给写子命令的参数，可重复")
    parser.add_argument("--timeout", type=int, help="写操作超时秒数（默认 3600）")
    parser.add_argument("--allow-degraded-backup", action="store_true",
                        help="仅诊断用：备份校验不一致时是否仍继续（默认拒绝）")
    return parser


def contract_arguments(args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    if args.campaign_id is not None:
        result.extend(["--campaign-id", str(args.campaign_id)])
    if args.query:
        result.extend(["--query", args.query])
    if args.recruit_type:
        result.extend(["--recruit-type", args.recruit_type])
    if args.include_written:
        result.append("--include-written")
    if args.limit is not None:
        result.extend(["--limit", str(args.limit)])
    if args.offset is not None:
        result.extend(["--offset", str(args.offset)])
    if args.cycle_config:
        result.extend(["--cycle-config", str(args.cycle_config)])
    if args.pretty:
        result.append("--pretty")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    operation = args.operation
    pretty = bool(args.pretty)
    try:
        if args.python:
            os.environ["IJOB_PYTHON"] = args.python
        if operation == "info" and args.campaign_id is None and not args.query:
            raise SkillError("invalid_request", "info 必须提供 --campaign-id 或 --query")
        if operation == "info" and args.campaign_id is not None and args.query:
            raise SkillError("invalid_request", "--campaign-id 与 --query 只能二选一")
        # ⛔ 写参数只允许出现在 `write` 上。只读 operation 携带 --apply/--write-op
        #    一律拒绝，否则 `status --apply` 会被静默忽略，人以为写了其实没写。
        if operation != "write":
            misused = [name for name, value in (
                ("--apply", args.apply),
                ("--write-op", args.write_op),
                ("--write-arg", args.write_arg),
                ("--allow-degraded-backup", args.allow_degraded_backup),
            ) if value]
            if misused:
                raise SkillError(
                    "invalid_request",
                    f"只读操作 {operation} 不接受写参数 {' '.join(misused)}；"
                    f"写操作请用 `write --write-op <名字>`",
                )
        home = discover_home(args.ijob_home)
        if operation == "write":
            payload = call_write_gate(
                home,
                write_op=args.write_op,
                write_args=list(args.write_arg),
                apply_=bool(args.apply),
                timeout=args.timeout,
                allow_degraded_backup=bool(args.allow_degraded_backup),
                python_exe=args.python or os.environ.get("IJOB_PYTHON"),
            )
        else:
            payload = call_contract(home, operation, contract_arguments(args))
    except SkillError as exc:
        print(json.dumps(make_skill_error(operation, exc), ensure_ascii=False, indent=2 if pretty else None))
        return exc.exit_code
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
