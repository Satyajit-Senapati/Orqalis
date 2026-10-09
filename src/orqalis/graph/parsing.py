"""Source-independent syntax facts; backend extraction never resolves runtime dispatch."""

from pydantic import Field

from orqalis.domain.base import Contract

MAX_VISITS = 50_000
MAX_DEPTH = 64
MAX_SYMBOLS = 2_000
MAX_CALLS = 5_000
MAX_IMPORTS = 1_000
MAX_NAME = 300
MAX_QUALIFIED_NAME = 512
MAX_BINDINGS = 5_000


class CallSpec(Contract):
    name: str
    line: int = Field(ge=1)


class ImportSpec(Contract):
    module: str
    names: tuple[str, ...] = ()
    level: int = Field(default=0, ge=0)
    owner: str | None = None
    line: int = Field(ge=1)
    aliases: tuple[tuple[str, str], ...] = ()


class SymbolSpec(Contract):
    kind: str
    name: str
    qualified_name: str
    parent_qualified_name: str | None = None
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    byte_start: int | None = Field(default=None, ge=0)
    byte_end: int | None = Field(default=None, ge=0)
    bases: tuple[str, ...] = ()
    implements: tuple[str, ...] = ()
    calls: tuple[CallSpec, ...] = ()
    bound_names: tuple[str, ...] = ()


class ParsedSource(Contract):
    parser_version: str
    parser_kind: str
    content_hash: str
    line_count: int = Field(ge=1)
    syntax_error: bool = False
    extraction_truncated: bool = False
    diagnostics: tuple[str, ...] = ()
    symbols: tuple[SymbolSpec, ...] = ()
    imports: tuple[ImportSpec, ...] = ()
    module_calls: tuple[CallSpec, ...] = ()
