"""Snapshot I/O for the golden-response + OpenAPI harness.

Phase 0 of the normalization plan (``database-normalization.md`` §7.1) requires
committed snapshots that every later phase diffs against, so that "responses
identical except the enumerated drift set" is a check a machine can run.

Snapshots live in ``backend/tests/snapshots/`` and are **never written
implicitly**: a missing or drifted snapshot fails the test. Re-recording is a
deliberate act that produces a reviewable git diff — see
``tests/test_api_snapshots.py`` for the command.
"""

import difflib
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "snapshots"

UPDATE_ENV_VAR = "UPDATE_SNAPSHOTS"

_MAX_DIFF_LINES = 200

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

REGEN_HINT = (
    f"If this change is intentional, re-record it deliberately with "
    f"{UPDATE_ENV_VAR}=1:\n"
    "  docker compose exec -T -e UPDATE_SNAPSHOTS=1 backend \\\n"
    "      python -m pytest tests/test_api_snapshots.py\n"
    "  docker compose cp backend:/app/backend/tests/snapshots/. \\\n"
    "      backend/tests/snapshots/\n"
    "then review the resulting diff under backend/tests/snapshots/."
)


def updating_snapshots() -> bool:
    """True when the run was asked to re-record snapshots instead of assert."""
    return os.environ.get(UPDATE_ENV_VAR, "") not in ("", "0")


def _mask_uuids(text: str) -> str:
    """Replace each UUID with a stable ``<uuid:N>`` token.

    Primary keys come from ``default_factory=uuid.uuid4``, so raw UUIDs can
    never be committed. Numbering by order of first appearance keeps
    referential structure visible — an event's ``match_id`` still renders as
    the same token as that match's ``id`` — while making the text reproducible.
    This is only stable because every endpoint the harness hits has a
    deterministic ``ORDER BY`` and the fixtures avoid ties on the sort keys.
    """
    seen: dict[str, str] = {}

    def _replace(match: "re.Match[str]") -> str:
        return seen.setdefault(match.group(0), f"<uuid:{len(seen) + 1}>")

    return _UUID_RE.sub(_replace, text)


def canonicalize(payload: Any) -> str:
    """Render a JSON payload as the exact text stored in a snapshot file."""
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return _mask_uuids(text) + "\n"


def normalize_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip deployment-specific metadata from an OpenAPI document.

    ``info.title`` is ``settings.PROJECT_NAME``, a per-deployment env var, not
    part of the API contract this harness guards. Everything else — paths,
    operation ids, schemas and their ``required`` lists — is kept, because
    those are precisely the changes that a response-body diff cannot see.
    """
    normalized = dict(schema)
    info = dict(normalized.get("info", {}))
    if "title" in info:
        info["title"] = "<PROJECT_NAME>"
    normalized["info"] = info
    return normalized


def _render_diff(name: str, expected: str, actual: str) -> str:
    lines = list(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"{name} (committed)",
            tofile=f"{name} (actual)",
            lineterm="",
            n=2,
        )
    )
    if len(lines) > _MAX_DIFF_LINES:
        omitted = len(lines) - _MAX_DIFF_LINES
        lines = lines[:_MAX_DIFF_LINES] + [f"... ({omitted} more diff lines)"]
    return "\n".join(lines)


def assert_matches_snapshot(name: str, payload: Any) -> None:
    """Assert ``payload`` matches the committed snapshot ``name``.

    Fails — never silently records — when the snapshot is missing, so a
    forgotten snapshot cannot pass in CI.
    """
    path = SNAPSHOT_DIR / name
    actual = canonicalize(payload)

    if updating_snapshots():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        pytest.skip(f"{UPDATE_ENV_VAR} set: re-recorded {name} without asserting")

    if not path.exists():
        pytest.fail(f"Snapshot {path} is missing.\n\n{REGEN_HINT}")

    expected = path.read_text(encoding="utf-8")
    if expected != actual:
        pytest.fail(
            f"Response drifted from snapshot {name}:\n"
            f"{_render_diff(name, expected, actual)}\n\n{REGEN_HINT}"
        )
