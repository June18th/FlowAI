from __future__ import annotations

from langchain_openai import ChatOpenAI


def _normalize_base_url(provider: str, api_url: str) -> str:
    """Normalize base URL for provider compatibility."""
    url = api_url.rstrip("/")

    # Strip common suffixes
    for suffix in ["/v1/chat/completions", "/v1"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break

    return url


def _normalize_provider(provider: str) -> str:
    mapping = {
        "open ai": "openai", "deep seek": "deepseek",
        "通义千问": "qwen", "阶跃星辰": "step", "智谱": "zhipu",        "火山方舟": "volcengine_agent_plan", "ark": "volcengine_agent_plan",
        "agent_plan": "volcengine_agent_plan",
    }
    return mapping.get(provider.lower().strip(), provider.lower().strip())


def _normalize_model(provider: str, model: str) -> str:
    """Normalize model name per provider."""
    if provider == "apifree" and "skyclaw" in model.lower():
        return "skywork-ai/skyclaw-v1"
    return model


def create_chat_client(
    provider: str,
    api_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.7,
    **kwargs,
) -> ChatOpenAI:
    """Create a LangChain ChatOpenAI client for any OpenAI-compatible provider."""
    provider = _normalize_provider(provider)
    model = _normalize_model(provider, model)

    if provider == "volcengine_agent_plan":
        # Volcengine Agent Plan uses custom completion path
        base_url = _normalize_base_url(provider, api_url)
        base_url = base_url + "/api/plan/v3"
    else:
        base_url = _normalize_base_url(provider, api_url)

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        **kwargs,
    )
