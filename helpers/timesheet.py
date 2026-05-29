"""Aggregate monthly logs into a CSV + markdown summary for the invoice."""

from __future__ import annotations

import calendar
import csv
import io
import re
from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Timesheet(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    csv: bytes
    summary_md: str
    total_hours: float
    by_project: dict[str, float]


def build_timesheet(logs_dir: Path, *, year: int, month: int) -> Timesheet:
    """Walk `logs_dir`, sum hours for the given month, return CSV + summary."""
    if not logs_dir.exists():
        return _empty(year, month)

    entries = _read_month(logs_dir, year=year, month=month)

    by_project: dict[str, float] = defaultdict(float)
    for e in entries:
        by_project[e["project"]] += float(e["duration_hours"])

    total = round(sum(by_project.values()), 4)
    return Timesheet(
        csv=_to_csv(entries),
        summary_md=_to_summary_md(entries, year=year, month=month, total=total),
        total_hours=total,
        by_project=dict(by_project),
    )


def _read_month(logs_dir: Path, *, year: int, month: int) -> list[dict]:
    last_day = calendar.monthrange(year, month)[1]
    start = date_cls(year, month, 1)
    end = date_cls(year, month, last_day)

    entries: list[dict] = []
    for md_file in sorted(logs_dir.glob("*.md")):
        try:
            file_date = date_cls.fromisoformat(md_file.stem)
        except ValueError:
            continue
        if not (start <= file_date <= end):
            continue
        entries.extend(_parse_frontmatter_blocks(md_file.read_text()))
    return entries


_BLOCK = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL | re.MULTILINE)


def _parse_frontmatter_blocks(text: str) -> list[dict]:
    out: list[dict] = []
    for m in _BLOCK.finditer(text):
        parsed = yaml.safe_load(m.group(1))
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _to_csv(entries: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["date", "client", "project", "shape", "duration_hours", "title"]
    )
    writer.writeheader()
    for e in entries:
        writer.writerow(
            {
                "date": e.get("date", ""),
                "client": e.get("client", ""),
                "project": e.get("project", ""),
                "shape": e.get("shape", ""),
                "duration_hours": e.get("duration_hours", 0),
                "title": e.get("title", ""),
            }
        )
    return buf.getvalue().encode()


def _to_summary_md(entries: list[dict], *, year: int, month: int, total: float) -> str:
    by_project: dict[str, float] = defaultdict(float)
    for e in entries:
        by_project[e["project"]] += float(e["duration_hours"])

    lines = [f"# Vibe Check timesheet — {year}-{month:02d}", "", f"**Total: {total}h**", ""]
    for project in sorted(by_project):
        lines.append(f"- {project}: {by_project[project]}h")
    return "\n".join(lines) + "\n"


def _empty(year: int, month: int) -> Timesheet:
    return Timesheet(
        csv=_to_csv([]),
        summary_md=_to_summary_md([], year=year, month=month, total=0.0),
        total_hours=0.0,
        by_project={},
    )
