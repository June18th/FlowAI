from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.engine.models import WorkflowNode
from app.engine.node_executor.abstract_llm import AbstractLLMNodeExecutor, LLMNodeConfig
from app.engine.node_executor.factory import node_executor_factory


class ReActAgentNodeExecutor(AbstractLLMNodeExecutor):
    DEFAULT_MAX_STEPS = 5
    MAX_ALLOWED_STEPS = 20

    def get_supported_node_type(self) -> str:
        return "react_agent"

    def _parse_decision(self, text: str) -> dict[str, Any]:
        """Parse LLM response JSON for action decision."""
        # Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"action": "final_answer", "finalAnswer": text}

    def _build_agent_system_prompt(self, config: LLMNodeConfig, node: WorkflowNode) -> str:
        tools = node.data.get("tools", [])
        tool_descriptions = "\n".join(
            f"- {t.get('name', t)}: {t.get('description', '')}" for t in tools
        )

        base = self.build_system_prompt(config)

        prompt = f"""{base}

You are a ReAct (Reasoning + Acting) agent. Follow this format:

Available tools:
{tool_descriptions}

Respond ONLY with a JSON object:
- To use a tool: {{"action": "tool_call", "toolName": "<tool_name>", "toolInput": {{<params>}}}}
- To answer: {{"action": "final_answer", "finalAnswer": "<your answer>"}}

Current tools available: {', '.join(t.get('name', str(t)) for t in tools)}
"""
        return prompt

    async def execute(
        self,
        node: WorkflowNode,
        input_data: dict[str, Any],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        config = self.extract_config(node)
        self.validate_config(config)

        max_steps = min(
            node.data.get("maxSteps", self.DEFAULT_MAX_STEPS),
            self.MAX_ALLOWED_STEPS,
        )

        system_prompt = self._build_agent_system_prompt(config, node)
        tool_trace: list[dict[str, Any]] = []
        total_tokens = 0
        current_input = input_data.get("input", str(input_data))

        for step in range(1, max_steps + 1):
            if progress_callback:
                progress_callback({
                    "eventType": "NODE_PROGRESS",
                    "nodeId": node.id,
                    "nodeName": node.display_name,
                    "message": f"ReAct Step {step}/{max_steps}",
                })

            # Call LLM
            user_msg = f"Current input: {current_input}\nStep {step}/{max_steps}. What do you do?"
            llm_result = await self.call_llm(config, system_prompt, user_msg)
            content = llm_result["content"]
            total_tokens += llm_result["totalTokens"]

            decision = self._parse_decision(content)

            if decision.get("action") == "final_answer":
                return {
                    "output": decision.get("finalAnswer", content),
                    "finalAnswer": decision.get("finalAnswer", content),
                    "toolTrace": tool_trace,
                    "steps": step,
                    "tokens": total_tokens,
                }

            # Tool call
            tool_name = decision.get("toolName", "")
            tool_input = decision.get("toolInput", {})
            tool_trace.append({
                "step": step,
                "toolName": tool_name,
                "toolInput": tool_input,
                "status": "not_implemented",
                "observation": f"Tool '{tool_name}' execution not implemented in this version",
            })
            current_input = json.dumps(decision)

        return {
            "output": f"Reached max steps ({max_steps}) without final answer",
            "finalAnswer": None,
            "toolTrace": tool_trace,
            "steps": max_steps,
            "tokens": total_tokens,
        }


node_executor_factory.register(ReActAgentNodeExecutor())
