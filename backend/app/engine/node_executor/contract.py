"""Node contract — standardized input/output schema declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeInput:
    """Declared input fields for a node executor."""
    fields: dict[str, str] = field(default_factory=dict)
    # e.g. {"city": "str", "query": "str", "apiKey": "str"}

    @classmethod
    def from_schema(cls, schema: dict[str, Any] | None) -> "NodeInput":
        if not schema or "properties" not in schema:
            return cls(fields={})
        return cls(fields={
            k: v.get("type", "any")
            for k, v in schema.get("properties", {}).items()
        })


@dataclass
class NodeOutput:
    """Declared output fields for a node executor."""
    fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_schema(cls, schema: dict[str, Any] | None) -> "NodeOutput":
        if not schema or "properties" not in schema:
            return cls(fields={})
        return cls(fields={
            k: v.get("type", "any")
            for k, v in schema.get("properties", {}).items()
        })


@dataclass
class NodeContract:
    node_type: str
    display_name: str
    description: str = ""
    input: NodeInput = field(default_factory=NodeInput)
    output: NodeOutput = field(default_factory=NodeOutput)
    config: dict[str, str] = field(default_factory=dict)


# ── Registered contracts ──

REGISTRY: dict[str, NodeContract] = {}


def register_contract(contract: NodeContract) -> None:
    REGISTRY[contract.node_type] = contract


def get_contract(node_type: str) -> NodeContract | None:
    return REGISTRY.get(node_type)


# ── Built-in contracts ──

register_contract(NodeContract(
    node_type="input",
    display_name="输入",
    description="工作流起始节点，接收外部输入",
    input=NodeInput(fields={}),
    output=NodeOutput(fields={"input": "str"}),
))

register_contract(NodeContract(
    node_type="output",
    display_name="输出",
    description="工作流结束节点，输出最终结果",
    input=NodeInput(fields={"input": "str"}),
    output=NodeOutput(fields={"output": "str"}),
))

register_contract(NodeContract(
    node_type="llm",
    display_name="LLM",
    description="通用大模型节点，支持多厂商",
    input=NodeInput(fields={"input": "str"}),
    output=NodeOutput(fields={"output": "str", "tokens": "int"}),
    config={"provider": "str", "configId": "int", "prompt": "str", "temperature": "float"},
))

register_contract(NodeContract(
    node_type="condition",
    display_name="条件分支",
    description="根据条件路由到不同分支",
    input=NodeInput(fields={"input": "dict"}),
    output=NodeOutput(fields={"__selectedBranch__": "str"}),
    config={"conditions": "list"},
))

register_contract(NodeContract(
    node_type="tts",
    display_name="TTS 音频合成",
    description="文本转语音，支持 Qwen/Step 厂商",
    input=NodeInput(fields={"text": "str"}),
    output=NodeOutput(fields={"audioUrl": "str", "duration": "float"}),
    config={"provider": "str", "configId": "int", "voice": "str"},
))

register_contract(NodeContract(
    node_type="weather_query",
    display_name="天气查询",
    description="高德地图天气 API，返回实时和预报",
    input=NodeInput(fields={"city": "str"}),
    output=NodeOutput(fields={"city": "str", "live": "dict", "forecasts": "list", "forecastSummary": "str"}),
    config={"apiKey": "str"},
))

register_contract(NodeContract(
    node_type="web_search",
    display_name="联网搜索",
    description="基于 MCP 工具的网络搜索",
    input=NodeInput(fields={"query": "str"}),
    output=NodeOutput(fields={"query": "str", "results": "list", "citations": "list"}),
    config={"mcpToolIds": "list"},
))

register_contract(NodeContract(
    node_type="web_fetch",
    display_name="网页抓取",
    description="抓取指定 URL 的网页内容",
    input=NodeInput(fields={"urls": "list"}),
    output=NodeOutput(fields={"pages": "list", "content": "str"}),
    config={"urls": "list"},
))
