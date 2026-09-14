"""Defense in depth for diagnostic text, never a substitute for safe typed payloads."""

import re

_CREDENTIAL_FIELD = re.compile(
    r"(?i)(?:^|[_-])(?:password|passwd|passphrase|token|secret|authorization|cookie|"
    r"api[_-]?key|private[_-]?key|secret[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"auth[_-]?token|id[_-]?token|client[_-]?secret)$"
)
_ASSIGNMENT = re.compile(r"""\b(?P<name>[A-Za-z_][A-Za-z0-9_-]*)(?:\\?["'])?\s*[:=]\s*""")
_VALUE = re.compile(
    r"""(?i)"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?:bearer|basic)\s+[a-z0-9._~+/=-]+|[^\s"',;]+"""
)


def is_credential_field(name: str) -> bool:
    """Recognize credential keys without treating usage counters as credentials."""
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return _CREDENTIAL_FIELD.search(normalized) is not None


_PATTERNS = (
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"(?i)\b(?:bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
)


def redact(text: str) -> str:
    text = re.sub(
        r"(?im)^\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*:[^\r\n]+",
        "[REDACTED]",
        text,
    )
    spans: list[tuple[int, int]] = []
    for match in _ASSIGNMENT.finditer(text):
        if not is_credential_field(match.group("name")):
            continue
        start = match.end()
        if text[start : start + 2] in {'\\"', "\\'"}:
            # A credential inside an escaped diagnostic string is not public output.
            # Omit the rest of its line rather than risk exposing an escaped fragment.
            newline = text.find("\n", start)
            end = newline if newline >= 0 else len(text)
        else:
            value = _VALUE.match(text, start)
            end = value.end() if value else start
        if spans and match.start() <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], end))
        else:
            spans.append((match.start(), end))
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.extend((text[cursor:start], "[REDACTED]"))
        cursor = end
    parts.append(text[cursor:])
    text = "".join(parts)
    for pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def safe_diagnostic(text: str) -> str:
    if re.search(r"(?i)-----BEGIN (?:[A-Z]+ )*PRIVATE KEY", text) or any(
        marker in text.lower()
        for marker in (
            "chain_of_thought",
            "<thinking>",
            "<analysis>",
            "-----begin private key",
            "-----begin rsa private key",
            "-----begin openssh private key",
        )
    ):
        return "[PRIVATE DIAGNOSTIC OMITTED]"
    return redact(text)
