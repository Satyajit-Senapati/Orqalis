import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import JsonValue

from orqalis.domain.provider import ProviderErrorCode
from orqalis.providers.errors import ProviderError
from orqalis.providers.validation import safe_value
from orqalis.security.redaction import is_credential_field, safe_diagnostic


@pytest.mark.parametrize(
    "name",
    [
        "api_key",
        "ORQALIS_OPENAI_API_KEY",
        "DATABASE_PASSWORD",
        "access_token",
        "refresh_token",
        "client_secret",
        "apiKey",
        "accessToken",
        "refreshToken",
        "databasePassword",
        "privateKey",
        "authorization",
        "cookie",
    ],
)
def test_credential_names_reject_opaque_structured_provider_values(name: str) -> None:
    secret = uuid4().hex
    assert is_credential_field(name)
    payload: dict[str, JsonValue] = {"result": [{name: secret}]}
    with pytest.raises(ProviderError) as caught:
        safe_value(payload)
    assert caught.value.error_code == ProviderErrorCode.INVALID_OUTPUT
    assert secret not in str(caught.value)
    assert secret not in safe_diagnostic(json.dumps(payload))
    assert secret not in safe_diagnostic(f'{name}="{secret}"')


@pytest.mark.parametrize(
    "template",
    [
        'DATABASE_PASSWORD="a secret with spaces {secret}"',
        "access_token={secret}",
        "Authorization: Basic {secret}",
        "Request headers: Authorization: Basic {secret}",
        "Cookie: session={secret}; identity=private",
        "postgresql://operator:{secret}@localhost/database",
        '{{"summary": "access_token={secret}"}}',
    ],
)
def test_diagnostics_remove_complete_nested_or_header_credential(template: str) -> None:
    secret = uuid4().hex
    result = safe_diagnostic(template.format(secret=secret))
    assert secret not in result
    assert "a secret with spaces" not in result
    assert safe_diagnostic(result) == result


def test_usage_metadata_and_ordinary_source_remain_public() -> None:
    payload: dict[str, JsonValue] = {
        "input_tokens": 42,
        "output_tokens": 9,
        "cached_input_tokens": 4,
        "max_output_tokens": 100,
        "token_count": 51,
        "summary": "Use basic tests and token_count for usage and password_reset for navigation.",
    }
    safe_value(payload)
    text = json.dumps(payload)
    assert safe_diagnostic(text) == text
    assert all(not is_credential_field(key) for key in payload)


def test_escaped_json_credentials_and_long_assignment_text_are_bounded() -> None:
    secret = uuid4().hex
    nested = json.dumps({"summary": json.dumps({"access_token": secret})})
    assert secret not in safe_diagnostic(nested)
    ordinary = "value=" * 2_000 + "public"
    assert safe_diagnostic(ordinary) == ordinary


def test_guardian_rejects_environment_named_opaque_credentials(git_repo: Path) -> None:
    from orqalis.delivery.guardian import ChangeGuardian
    from orqalis.domain.delivery import DeliveryPolicy
    from orqalis.domain.execution import ExecutionPolicy, RunWorkspace
    from orqalis.git.service import LocalGitService

    git = LocalGitService()
    binding = RunWorkspace(
        run_id=uuid4(),
        path=git_repo,
        branch="main",
        base_commit=git.status(git_repo).head,
        policy=ExecutionPolicy(write_paths=("main.py",)),
    )
    secret = uuid4().hex
    (git_repo / "main.py").write_text(f'ORQALIS_OPENAI_API_KEY = "{secret}"\n')
    report = ChangeGuardian(git).inspect(binding, DeliveryPolicy(), uuid4(), "implementation")
    assert not report.passed
    assert "secret" in {finding.category for finding in report.findings}
    assert secret not in report.model_dump_json()
