from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.engine.models import WorkflowNode


class NodeExecutor(ABC):
    """Interface for node executors."""

    @abstractmethod
    def get_supported_node_type(self) -> str:
        """Return the node type this executor handles."""
        ...

    async def execute(
        self,
        node: WorkflowNode,
        input_data: dict[str, Any],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Execute the node and return output."""
        raise NotImplementedError
