from orqalis.domain.errors import OrqalisError
from orqalis.domain.provider import ProviderErrorCode


class ProviderError(OrqalisError):
    code = "provider_error"

    def __init__(self, error_code: ProviderErrorCode) -> None:
        self.error_code = error_code
        super().__init__(f"Provider invocation failed: {error_code.value}")
