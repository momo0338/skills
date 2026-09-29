#!/usr/bin/env python3
"""Audit a Markdown geographic-point inventory.

The script parses the overview table and exact section headings; it does not know
any expected point count. Use --expect-total/--expect-outdoor/--expect-indoor
only when an external task specification requires those values.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_title_numbers(text: str) -> tuple[int, int, int]:
    m = re.search(
        r"(?:这\s*)?(\d+)\s*个.*?室外\s*(\d+)\s*个.*?室内\s*(\d+)\s*个",
        text,
    )
    if not m:
        raise ValueError("title/count format not found: N points, N outdoor, N indoor")
    return tuple(map(int, m.groups()))


def parse_rows(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in block.splitlines():
        if re.match(r"^\|\s*\d+\s*\|", line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def section(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    tail = text.split(start, 1)[1]
    return tail.split(end, 1)[0] if end in tail else tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("--expect-total", type=int)
    ap.add_argument("--expect-outdoor", type=int)
    ap.add_argument("--expect-indoor", type=int)
    args = ap.parse_args()

    text = Path(args.markdown).read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    fm = re.search(r"^title:\s*(.+)$", text, re.M)
    h1 = re.search(r"^#\s+(.+)$", text, re.M)
    if not fm or not h1:
        errors.append("missing frontmatter title or H1")
        print_errors(errors, warnings)
        return 1
    if fm.group(1).strip() != h1.group(1).strip():
        errors.append("frontmatter title != H1")

    title = h1.group(1).strip()
    if len(title) > 64:
        errors.append(f"H1 is {len(title)} characters (>64)")

    overview = section(
        text,
        "## 五、全景对照表",
        "## 六、",
    )
    rows = parse_rows(overview)
    if not rows:
        errors.append("overview table not found or empty")
        print_errors(errors, warnings)
        return 1
    if len(rows) < 3:
        errors.append("overview table has too few rows")
        return 1

    number_col = 0
    name_col = 1
    class_col = 2
    nums = [int(r[number_col]) for r in rows]
    if nums != list(range(1, len(rows) + 1)):
        errors.append("overview numbering is not continuous from 1")
    names = [r[name_col].replace("**", "") for r in rows]
    if len(names) != len(set(names)):
        errors.append("overview contains duplicate point names")
    classes = [r[class_col].strip() for r in rows]
    unexpected = sorted(set(classes) - {"室外", "室内"})
    if unexpected:
        errors.append(f"unexpected primary classes: {unexpected}")
    counts = {c: classes.count(c) for c in set(classes)}

    outdoor = section(text, "## 二、室外", "## 三、")
    indoor = section(text, "## 三、室内", "## 四、")
    outdoor_rows = parse_rows(outdoor)
    indoor_rows = parse_rows(indoor)
    if len(outdoor_rows) != counts.get("室外", 0):
        errors.append(
            f"outdoor section rows {len(outdoor_rows)} != overview outdoor {counts.get('室外', 0)}"
        )
    if len(indoor_rows) != counts.get("室内", 0):
        errors.append(
            f"indoor section rows {len(indoor_rows)} != overview indoor {counts.get('室内', 0)}"
        )
    section_names = [r[1].replace("**", "") for r in outdoor_rows + indoor_rows]
    if len(section_names) != len(set(section_names)):
        errors.append("section tables contain duplicate names")
    if set(section_names) != set(names):
        errors.append(
            "section names and overview names differ: "
            f"section-only={sorted(set(section_names)-set(names))}, "
            f"overview-only={sorted(set(names)-set(section_names))}"
        )

    try:
        t_total, t_out, t_in = parse_title_numbers(title)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if t_total != len(rows):
            errors.append(f"H1 total {t_total} != overview {len(rows)}")
        if t_out != counts.get("室外", 0):
            errors.append(f"H1 outdoor {t_out} != overview {counts.get('室外', 0)}")
        if t_in != counts.get("室内", 0):
            errors.append(f"H1 indoor {t_in} != overview {counts.get('室内', 0)}")

    if args.expect_total is not None and len(rows) != args.expect_total:
        errors.append(f"expected total {args.expect_total}, got {len(rows)}")
    if args.expect_outdoor is not None and counts.get("室外", 0) != args.expect_outdoor:
        errors.append(
            f"expected outdoor {args.expect_outdoor}, got {counts.get('室外', 0)}"
        )
    if args.expect_indoor is not None and counts.get("室内", 0) != args.expect_indoor:
        errors.append(f"expected indoor {args.expect_indoor}, got {counts.get('室内', 0)}")

    seo = re.search(
        r"(?:无emoji)?长尾SEO摘要[^\n]*\n>\s*(.+)",
        text,
    )
    if not seo:
        warnings.append("SEO summary not found")
    elif len(seo.group(1).strip()) > 120:
        errors.append(f"SEO summary is {len(seo.group(1).strip())} characters (>120)")

    if text.count("<!-- benchmark:start -->") != 1 or text.count(
        "<!-- benchmark:end -->"
    ) != 1:
        warnings.append("benchmark block is missing or not paired exactly once")

    print(
        json_summary(
            total=len(rows),
            outdoor=counts.get("室外", 0),
            indoor=counts.get("室内", 0),
            title=title,
        )
    )
    print_errors(errors, warnings)
    return 1 if errors else 0


def json_summary(*, total: int, outdoor: int, indoor: int, title: str) -> str:
    return (
        f"RESULT total={total} outdoor={outdoor} indoor={indoor} "
        f"title_chars={len(title)}"
    )


def print_errors(errors: list[str], warnings: list[str]) -> None:
    for item in errors:
        print(f"ERROR: {item}")
    for item in warnings:
        print(f"WARN: {item}")
    print("PASS" if not errors else "FAIL")


if __name__ == "__main__":
    sys.exit(main())
