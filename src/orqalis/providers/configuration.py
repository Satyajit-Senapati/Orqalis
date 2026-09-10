from orqalis.config.settings import Settings
from orqalis.providers.anthropic import AnthropicProvider
from orqalis.providers.openai import OpenAIProvider
from orqalis.providers.ports import AgentProvider


def configured_providers(settings: Settings) -> tuple[AgentProvider, ...]:
    providers: list[AgentProvider] = []
    if settings.openai_model and settings.openai_api_key:
        providers.append(OpenAIProvider(settings.openai_model, settings.openai_api_key))
    if settings.anthropic_model and settings.anthropic_api_key:
        providers.append(AnthropicProvider(settings.anthropic_model, settings.anthropic_api_key))
    return tuple(providers)
