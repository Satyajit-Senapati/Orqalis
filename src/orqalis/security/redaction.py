"""Defense in depth for diagnostic text, never a substitute for safe typed payloads."""

import re

_PATTERNS = (
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"(?i)\b(?:bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}"),
    re.compile(r"""(?i)\b(?:password|token|secret|api[_-]?key)["']?\s*[:=]\s*["']?[^\s"',;]+"""),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
)


def redact(text: str) -> str:
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
