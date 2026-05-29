"""Append validated entries to per-day markdown files with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from helpers.types import EntryEnvelope


def write_log(entry: EntryEnvelope, *, logs_dir: Path) -> Path:
    """Append `entry` to `<logs_dir>/YYYY-MM-DD.md` and return the path.

    Idempotent on the entry's `id`: if an entry with the same id is already
    present in the file, the file is returned unchanged.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"{entry.date.isoformat()}.md"
    existing = path.read_text() if path.exists() else ""

    if _file_contains_id(existing, entry.id):
        return path

    block = _format_block(entry)
    new_text = block if not existing else existing.rstrip() + "\n\n" + block
    path.write_text(new_text)
    return path


def _format_block(entry: EntryEnvelope) -> str:
    data = entry.model_dump(mode="json", exclude_none=False)
    # `model_dump(mode='json')` produces JSON-safe scalars (dates as ISO strings),
    # which yaml.safe_dump renders cleanly.
    fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    title = data["title"]
    narrative = data["narrative"]
    return f"---\n{fm}\n---\n\n## {title}\n\n{narrative}\n"


_ID_PATTERN = re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE)


def _file_contains_id(text: str, target_id: str) -> bool:
    return any(m.group(1) == target_id for m in _ID_PATTERN.finditer(text))
