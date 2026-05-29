"""Fail CI if the committed schemas/ drift from helpers/types.py."""

from __future__ import annotations

from pathlib import Path

from scripts.generate_schemas import SHAPE_FILES, generate

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def test_committed_schemas_match_current_models(tmp_path: Path) -> None:
    fresh = generate(tmp_path)
    for filename in SHAPE_FILES.values():
        committed = (SCHEMAS_DIR / filename).read_text()
        assert committed == fresh[filename], (
            f"{filename} is stale — run `uv run python scripts/generate_schemas.py` "
            "and commit the result."
        )
