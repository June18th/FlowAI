from __future__ import annotations

import re
from typing import Any

VAR_PATTERN = re.compile(r"\{\{(.*?)\}\}")


def process_template(
    prompt_template: str,
    input_params: list[dict[str, Any]] | None,
    runtime_input: dict[str, Any],
) -> str:
    """Replace {{variable}} placeholders with resolved values."""
    if not prompt_template:
        return ""

    # Build param value map
    param_values: dict[str, str] = {}

    if input_params:
        for param in input_params:
            name = param.get("name", "")
            param_type = param.get("type", "input")
            if param_type == "input":
                # Static value from config
                value = param.get("value", "")
                if isinstance(value, str):
                    param_values[name] = value
                else:
                    param_values[name] = str(value)
            elif param_type == "reference":
                # Dynamic value from runtime input
                ref = param.get("referenceNode", "")
                field = ref or param.get("field", name)
                value = _resolve_reference(field, runtime_input)
                if value is None and "." in field:
                    value = _resolve_reference(field.split(".")[-1], runtime_input)
                if value is not None:
                    param_values[name] = str(value)

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1).strip()
        if var_name in param_values:
            return param_values[var_name]
        # Fallback: try runtime input
        if var_name == "user_input" and "input" in runtime_input:
            return str(runtime_input["input"])
        if var_name in runtime_input:
            val = runtime_input[var_name]
            return str(val) if not isinstance(val, (dict, list)) else str(val)
        # Fallback: try nested lookup
        resolved = _resolve_reference(var_name, runtime_input)
        if resolved is not None:
            return str(resolved)
        return match.group(0)  # Keep original placeholder

    result = VAR_PATTERN.sub(replace_var, prompt_template)
    return result


def _resolve_reference(field: str, data: dict[str, Any]) -> Any:
    """Resolve dot-notation field reference from data dict."""
    if not field:
        return None

    parts = field.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current
