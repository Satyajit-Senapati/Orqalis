"""Shared locations for deterministic dashboard browser fixtures."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
POINTER_ROOT = WORKSPACE_ROOT / ".tools"


def fixture_root() -> Path:
    """Return an external fixture root so nested Git repos stay out of the workspace."""

    configured = os.environ.get("ORQALIS_QA_FIXTURE_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        workspace_key = hashlib.sha256(str(WORKSPACE_ROOT).encode()).hexdigest()[:12]
        root = (
            Path(tempfile.gettempdir()) / "orqalis-dashboard-fixtures" / workspace_key
        ).resolve()
    workspace = WORKSPACE_ROOT.resolve()
    if root == workspace or root.is_relative_to(workspace):
        raise RuntimeError("ORQALIS_QA_FIXTURE_ROOT must be outside the Orqalis workspace")
    root.mkdir(parents=True, exist_ok=True)
    return root


def pointer_path(name: str) -> Path:
    """Keep small run-ID handoff records in the ignored workspace tools directory."""

    POINTER_ROOT.mkdir(parents=True, exist_ok=True)
    return POINTER_ROOT / name
