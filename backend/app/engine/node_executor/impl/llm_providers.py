from __future__ import annotations

from app.engine.node_executor.abstract_llm import AbstractLLMNodeExecutor
from app.engine.node_executor.factory import node_executor_factory
from app.engine.node_executor.impl.react_agent import ReActAgentNodeExecutor


class OpenAINodeExecutor(AbstractLLMNodeExecutor):
    def get_supported_node_type(self) -> str:
        return "openai"


class DeepSeekNodeExecutor(AbstractLLMNodeExecutor):
    def get_supported_node_type(self) -> str:
        return "deepseek"


class QwenNodeExecutor(AbstractLLMNodeExecutor):
    def get_supported_node_type(self) -> str:
        return "qwen"


class StepNodeExecutor(AbstractLLMNodeExecutor):
    def get_supported_node_type(self) -> str:
        return "step"


class ZhiPuNodeExecutor(AbstractLLMNodeExecutor):
    def get_supported_node_type(self) -> str:
        return "zhipu"




class LlmNodeExecutor(AbstractLLMNodeExecutor):
    """Generic LLM node — delegates to ReAct if configured."""

    def get_supported_node_type(self) -> str:
        return "llm"

    async def execute(self, node, input_data, progress_callback=None):
        # Check for ReAct mode
        agent_strategy = node.data.get("agentStrategy", "")
        tools = node.data.get("tools", [])
        if agent_strategy == "react" or tools:
            react = ReActAgentNodeExecutor()
            return await react.execute(node, input_data, progress_callback)
        return await super().execute(node, input_data, progress_callback)


# Register all
for cls in [OpenAINodeExecutor, DeepSeekNodeExecutor, QwenNodeExecutor, StepNodeExecutor, ZhiPuNodeExecutor, LlmNodeExecutor]:
    node_executor_factory.register(cls())
