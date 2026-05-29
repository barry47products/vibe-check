"""Regenerate JSON Schemas under schemas/ from helpers/types.py.

One file per concrete shape (not the union) — the OCS Extract node
targets a specific shape post-routing. Re-run after any change to
helpers/types.py and commit the resulting schemas/*.json alongside.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from helpers.types import (
    DeepWorkEntry,
    LearningEntry,
    MeetingEntry,
    OffsiteEntry,
    OpsEntry,
)

SHAPE_FILES: dict[type[BaseModel], str] = {
    DeepWorkEntry: "entry.deep-work.json",
    MeetingEntry: "entry.meeting.json",
    OffsiteEntry: "entry.offsite.json",
    OpsEntry: "entry.ops.json",
    LearningEntry: "entry.learning.json",
}


def generate(schemas_dir: Path) -> dict[str, str]:
    """Write one JSON Schema per shape. Returns {filename: schema_json_text}."""
    schemas_dir.mkdir(exist_ok=True)
    written: dict[str, str] = {}
    for model_cls, filename in SHAPE_FILES.items():
        schema = model_cls.model_json_schema()
        text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        (schemas_dir / filename).write_text(text)
        written[filename] = text
    return written


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "schemas"
    files = generate(out_dir)
    for name in sorted(files):
        print(f"wrote {out_dir / name}")
