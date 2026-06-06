from __future__ import annotations

import json
from typing import Any

from app.engine.models import WorkflowNode
from app.engine.node_executor.base import NodeExecutor
from app.engine.node_executor.factory import node_executor_factory


class ConditionNodeExecutor(NodeExecutor):
    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "gt": lambda a, b: float(a) > float(b) if _is_numeric(a, b) else a > b,
        "gte": lambda a, b: float(a) >= float(b) if _is_numeric(a, b) else a >= b,
        "lt": lambda a, b: float(a) < float(b) if _is_numeric(a, b) else a < b,
        "lte": lambda a, b: float(a) <= float(b) if _is_numeric(a, b) else a <= b,
        "contains": lambda a, b: str(b).lower() in str(a).lower(),
        "notContains": lambda a, b: str(b).lower() not in str(a).lower(),
        "startsWith": lambda a, b: str(a).lower().startswith(str(b).lower()),
        "endsWith": lambda a, b: str(a).lower().endswith(str(b).lower()),
        "isEmpty": lambda a, _: not a or str(a).strip() == "",
        "isNotEmpty": lambda a, _: bool(a) and str(a).strip() != "",
    }

    def get_supported_node_type(self) -> str:
        return "condition"

    def _resolve_field(self, field: str, input_data: dict[str, Any]) -> Any:
        """Resolve dot-notation field from input data."""
        # Try nested inside input_data
        parts = field.split(".")
        current: Any = input_data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    async def execute(self, node: WorkflowNode, input_data: dict, progress_callback=None) -> dict:
        conditions = node.data.get("conditions", [])

        # Try to parse input as JSON for nested field access
        parsed_input = input_data
        raw_input = input_data.get("input", "")
        if isinstance(raw_input, str):
            try:
                parsed = json.loads(raw_input)
                if isinstance(parsed, dict):
                    parsed_input = {**parsed, **input_data}
            except (json.JSONDecodeError, TypeError):
                pass

        for cond in conditions:
            cond_id = cond.get("id", "")
            field = cond.get("field", "")
            operator = cond.get("operator", "")
            value = cond.get("value", "")

            actual = self._resolve_field(field, parsed_input)
            op_func = self.OPERATORS.get(operator)

            if op_func and op_func(actual, value):
                return {
                    "__selectedBranch__": cond_id,
                    "__conditionNodeId__": node.id,
                }

        # Default branch
        return {
            "__selectedBranch__": "default",
            "__conditionNodeId__": node.id,
        }


def _is_numeric(a: Any, b: Any) -> bool:
    try:
        float(a)
        float(b)
        return True
    except (ValueError, TypeError):
        return False


node_executor_factory.register(ConditionNodeExecutor())
