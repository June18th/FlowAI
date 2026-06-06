from __future__ import annotations

from app.engine.node_executor.base import NodeExecutor


class NodeExecutorFactory:
    """Registry of node type -> executor."""

    def __init__(self):
        self._executors: dict[str, NodeExecutor] = {}

    def register(self, executor: NodeExecutor) -> None:
        node_type = executor.get_supported_node_type()
        self._executors[node_type] = executor

    def get_executor(self, node_type: str) -> NodeExecutor:
        if node_type not in self._executors:
            raise ValueError(f"No executor found for node type: {node_type}")
        return self._executors[node_type]

    def has_executor(self, node_type: str) -> bool:
        return node_type in self._executors


# Singleton factory — executors are registered at import time
node_executor_factory = NodeExecutorFactory()
