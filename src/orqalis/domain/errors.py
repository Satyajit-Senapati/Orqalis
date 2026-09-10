class OrqalisError(Exception):
    """An operational error safe for an interface to identify by code."""

    code = "orqalis_error"


class ConflictError(OrqalisError):
    code = "conflict"


class NotFoundError(OrqalisError):
    code = "not_found"


class PolicyDeniedError(OrqalisError):
    code = "policy_denied"


class InputError(OrqalisError):
    code = "invalid_input"


class EmbeddingUnavailableError(OrqalisError):
    code = "embedding_unavailable"
