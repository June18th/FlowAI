from __future__ import annotations

from datetime import datetime
from typing import Any


def build_checkpoint(
    node_outputs: dict[str, dict[str, Any]],
    completed_node_ids: set[str],
    skipped_nodes: set[str],
    node_results: list[dict[str, Any]],
    final_output: dict[str, Any],
    sorted_nodes: list[str],
    last_node_id: str | None = None,
) -> dict[str, Any]:
    return {
        "nodeOutputs": {k: v for k, v in node_outputs.items()},
        "completedNodeIds": list(completed_node_ids),
        "skippedNodes": list(skipped_nodes),
        "nodeResults": list(node_results),
        "finalOutput": final_output,
        "sortedNodes": list(sorted_nodes),
        "lastNodeId": last_node_id,
    }


def load_checkpoint(execution_state: dict[str, Any] | None) -> tuple[
    dict[str, dict[str, Any]],  # node_outputs
    set[str],                    # completed_node_ids
    set[str],                    # skipped_nodes
    list[dict[str, Any]],        # node_results
    dict[str, Any],              # final_output
    list[str],                   # sorted_nodes
]:
    if not execution_state:
        return {}, set(), set(), [], {}, []
    return (
        execution_state.get("nodeOutputs", {}),
        set(execution_state.get("completedNodeIds", [])),
        set(execution_state.get("skippedNodes", [])),
        execution_state.get("nodeResults", []),
        execution_state.get("finalOutput", {}),
        execution_state.get("sortedNodes", []),
    )


def apply_checkpoint(
    record,
    node_outputs: dict[str, dict[str, Any]],
    completed_node_ids: set[str],
    skipped_nodes: set[str],
    node_results: list[dict[str, Any]],
    final_output: dict[str, Any],
    sorted_nodes: list[str],
    last_node_id: str | None = None,
) -> None:
    record.execution_state = build_checkpoint(
        node_outputs, completed_node_ids, skipped_nodes,
        node_results, final_output, sorted_nodes, last_node_id,
    )
    record.last_completed_node_id = last_node_id
    record.heartbeat_at = datetime.utcnow()
