from __future__ import annotations

from app.engine.models import WorkflowNode
from app.engine.node_executor.base import NodeExecutor
from app.engine.node_executor.factory import node_executor_factory


class InputNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "input"

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        return dict(input_data)


node_executor_factory.register(InputNodeExecutor())
