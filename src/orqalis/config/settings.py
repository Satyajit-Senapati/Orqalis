from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORQALIS_", extra="ignore", hide_input_in_errors=True
    )

    project_root: Path | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str | None = None
    operator_token: SecretStr | None = None
    skill_roots: tuple[Path, ...] = ()
    log_level: str = "INFO"
    telemetry_console: bool = False
    max_repair_iterations: int = Field(default=5, ge=0, le=100)
    host: str = "127.0.0.1"
    port: int = Field(default=7842, ge=1, le=65535)

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid logging level")
        return value
