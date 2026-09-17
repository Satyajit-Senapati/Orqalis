"""Opaque local-server scope identities used to prevent cross-project UI reuse."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def project_scope_id(root: Path | None) -> str | None:
    """Return a non-reversible identity for this process's resolved project root."""

    if root is None:
        return None
    normalized = os.path.normcase(str(root.expanduser().resolve(strict=False)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = ["project_scope_id"]
