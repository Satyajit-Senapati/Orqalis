"""Shared identifier-aware lexical terms for local, provider-free retrieval."""

import re

_WORDS = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def lexical_terms(value: str) -> tuple[str, ...]:
    """Keep complete identifiers and add snake_case/CamelCase constituent words."""
    full = _WORDS.findall(value.casefold())
    # Ordinary prose has identical full/constituent tokens. Avoid building a
    # second large list when no identifier boundary needs expansion.
    if "_" not in value and _CAMEL.search(value) is None:
        return tuple(dict.fromkeys(term for term in full if len(term) >= 2))
    parts = _WORDS.findall(_CAMEL.sub(" ", value).replace("_", " ").casefold())
    return tuple(dict.fromkeys(term for term in (*full, *parts) if len(term) >= 2))
