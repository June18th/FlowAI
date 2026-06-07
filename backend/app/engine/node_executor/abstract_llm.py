from __future__ import annotations

import json
import time
from abc import ABC
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.engine.llm.chat_client_factory import _normalize_provider, create_chat_client
from app.engine.llm.prompt_template import process_template
from app.engine.models import WorkflowNode
from app.engine.node_executor.base import NodeExecutor


class LLMNodeConfig:
    """Resolved LLM configuration for a node."""

    def __init__(
        self,
        provider: str = "",
        api_url: str = "",
        api_key: str = "",
        model: str = "",
        temperature: float = 0.7,
        prompt_template: str = "",
        input_params: list[dict[str, Any]] | None = None,
        output_params: list[dict[str, Any]] | None = None,
        streaming: bool = False,
        skill_name: str | None = None,
        config_id: int | None = None,
        memory_enabled: bool = False,
        knowledge_base_id: int | None = None,
        max_tokens: int | None = None,
    ):
        self.provider = provider
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.prompt_template = prompt_template
        self.input_params = input_params or []
        self.output_params = output_params or []
        self.streaming = streaming
        self.skill_name = skill_name
        self.config_id = config_id
        self.memory_enabled = memory_enabled
        self.knowledge_base_id = knowledge_base_id
        self.max_tokens = max_tokens


class AbstractLLMNodeExecutor(NodeExecutor, ABC):
    """Base class for all LLM provider node executors."""

    MAX_FUNCTION_ITERATIONS = 5

    def __init__(self, db_session_factory=None, skill_registry=None, knowledge_service=None):
        self._db_session_factory = db_session_factory
        self._skill_registry = skill_registry
        self._knowledge_service = knowledge_service

    def extract_config(self, node: WorkflowNode) -> LLMNodeConfig:
        """Extract LLM configuration from node data, checking global config first."""
        data = node.data

        config_id = data.get("configId")
        provider = data.get("provider", "") or node.type
        api_url = data.get("apiUrl", "")
        api_key = data.get("apiKey", "")
        model = data.get("model", "")
        temperature = float(data.get("temperature", 0.7))
        prompt_template = data.get("prompt", data.get("promptTemplate", ""))
        input_params = data.get("inputParams", [])
        output_params = data.get("outputParams", [])
        streaming = data.get("streaming", False)
        skill_name = data.get("skillName")
        memory_enabled = data.get("memoryEnabled", False)
        knowledge_base_id = data.get("knowledgeBaseId")
        max_tokens = data.get("maxTokens")

        # Resolve global config if configId is set
        if config_id:
            try:
                import asyncio
                from app.database import async_session
                from sqlalchemy import select
                from app.models.llm_config import LLMGlobalConfig
                async def _get():
                    async with async_session() as db:
                        r = await db.execute(select(LLMGlobalConfig).where(LLMGlobalConfig.id == config_id))
                        return r.scalar_one_or_none()
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import nest_asyncio; nest_asyncio.apply()
                gc = asyncio.get_event_loop().run_until_complete(_get()) if asyncio.get_event_loop().is_running() else asyncio.run(_get())
                if gc:
                    if not provider or provider == node.type:
                        provider = _normalize_provider(gc.provider or "")
                    if not api_url:
                        api_url = gc.api_url or ""
                    if not api_key:
                        api_key = gc.api_key or ""
                    if not model:
                        model = gc.model or ""
            except Exception:
                pass

        provider = _normalize_provider(provider)

        return LLMNodeConfig(
            provider=provider,
            api_url=api_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            prompt_template=prompt_template,
            input_params=input_params,
            output_params=output_params,
            streaming=streaming,
            skill_name=skill_name,
            config_id=config_id,
            memory_enabled=memory_enabled,
            knowledge_base_id=knowledge_base_id,
            max_tokens=max_tokens,
        )

    def validate_config(self, config: LLMNodeConfig) -> None:
        if not config.provider:
            raise ValueError("LLM provider is required")
        if not config.api_url and not config.config_id:
            raise ValueError("LLM API URL or configId is required")
        if not config.api_key and not config.config_id:
            raise ValueError("LLM API Key or configId is required")
        if not config.model and not config.config_id:
            raise ValueError("LLM model or configId is required")

    def build_system_prompt(self, config: LLMNodeConfig) -> str:
        """Build system prompt including skill content and references."""
        parts = []

        if config.skill_name and self._skill_registry:
            skill = self._skill_registry.get_skill(config.skill_name)
            if skill:
                refs = self._skill_registry.load_all_references(config.skill_name)
                full = skill.content
                for ref_name, ref_content in refs.items():
                    full += f"\n\n---\n## Reference: {ref_name}\n{ref_content}"
                parts.append(full)

        return "\n\n".join(parts)

    def build_context_prompt(self, config: LLMNodeConfig, current_input: dict[str, Any]) -> str:
        """Build context from memory and knowledge base."""
        parts = []

        if config.memory_enabled:
            parts.append("(Memory recall context would be injected here)")

        if config.knowledge_base_id and self._knowledge_service:
            parts.append("(Knowledge base RAG context would be injected here)")

        return "\n\n".join(parts)

    async def call_llm(
        self,
        config: LLMNodeConfig,
        system_prompt: str,
        user_message: str,
    ) -> dict[str, Any]:
        """Call the LLM and return result with token stats."""
        client = create_chat_client(
            provider=config.provider,
            api_url=config.api_url,
            api_key=config.api_key,
            model=config.model,
            temperature=config.temperature,
        )

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))

        start = time.time()
        response = client.invoke(messages)
        elapsed_ms = int((time.time() - start) * 1000)

        content = response.content if hasattr(response, "content") else str(response)

        # Extract token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

        return {
            "content": content,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
            "duration": elapsed_ms,
        }

    def build_output(self, llm_result: dict[str, Any], config: LLMNodeConfig) -> dict[str, Any]:
        """Build output dict from LLM result and output params config."""
        output: dict[str, Any] = {
            "output": llm_result["content"],
            "tokens": llm_result["totalTokens"],
            "inputTokens": llm_result["inputTokens"],
            "outputTokens": llm_result["outputTokens"],
            "duration": llm_result["duration"],
        }
        return output

    async def execute(
        self,
        node: WorkflowNode,
        input_data: dict[str, Any],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        config = self.extract_config(node)
        self.validate_config(config)

        # Build system prompt with skills
        system_prompt = self.build_system_prompt(config)

        # Process prompt template
        user_message = process_template(config.prompt_template, config.input_params, input_data)

        # Build context
        context = self.build_context_prompt(config, input_data)
        if context:
            user_message = f"{context}\n\n---\n\n{user_message}"

        # Call LLM
        llm_result = await self.call_llm(config, system_prompt, user_message)

        return self.build_output(llm_result, config)
