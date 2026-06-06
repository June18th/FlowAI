from __future__ import annotations

import re
from typing import Any

from app.engine.models import WorkflowNode
from app.engine.node_executor.base import NodeExecutor
from app.engine.node_executor.factory import node_executor_factory


class OutputNodeExecutor(NodeExecutor):
    def get_supported_node_type(self) -> str:
        return "output"

    def _resolve_param(self, param: dict[str, Any], input_data: dict[str, Any], node_outputs: dict[str, Any] | None = None) -> str:
        param_type = param.get("type", "input")
        param_name = param.get("name", "")
        param_value = param.get("value", "")

        if param_type == "input":
            return str(param_value)
        elif param_type == "reference":
            # Resolve from __nodeOutputs__ (LangGraph) or flat input
            if node_outputs and "__nodeOutputs__" in param_value:
                ref = param_value.replace("__nodeOutputs__.", "")
                parts = ref.split(".")
                current = node_outputs
                for p in parts:
                    if isinstance(current, dict) and p in current:
                        current = current[p]
                    else:
                        return str(param_value)
                return str(current)
            # Try dot notation from input_data
            ref = param_value
            parts = ref.split(".")
            current: Any = input_data
            for p in parts:
                if isinstance(current, dict) and p in current:
                    current = current[p]
                else:
                    return str(param_value)
            return str(current)
        return ""

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        response_content = node.data.get("responseContent", "")
        input_params = node.data.get("inputParams", [])
        node_outputs = input_data.get("__nodeOutputs__")

        # Build param value map
        param_map: dict[str, str] = {}
        for param in input_params:
            name = param.get("name", "")
            value = self._resolve_param(param, input_data, node_outputs)
            param_map[name] = value

        # Replace {{param}} in template
        def replace_var(m: re.Match) -> str:
            var = m.group(1)
            if var in param_map:
                return param_map[var]
            return str(input_data.get(var, m.group(0)))

        result_text = re.sub(r"\{\{(.*?)\}\}", replace_var, response_content)

        return {
            "output": result_text,
            "inputParams": param_map,
        }


node_executor_factory.register(OutputNodeExecutor())
