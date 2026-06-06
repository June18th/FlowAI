from __future__ import annotations

import json

from app.engine.models import WorkflowConfig, WorkflowEdge, WorkflowNode, WorkflowPosition


def parse_workflow_config(flow_data: str) -> WorkflowConfig:
    """Parse React Flow JSON into WorkflowConfig."""
    raw = json.loads(flow_data) if isinstance(flow_data, str) else flow_data

    nodes = []
    for n in raw.get("nodes", []):
        node_type = n.get("type", "")
        data = n.get("data", {})
        # Resolve actual type from data.type if outer type is generic
        if node_type == "workflow" or not node_type:
            node_type = data.get("type", node_type)

        position = None
        pos = n.get("position")
        if pos and "x" in pos and "y" in pos:
            position = WorkflowPosition(x=float(pos["x"]), y=float(pos["y"]))

        nodes.append(WorkflowNode(
            id=n["id"],
            type=node_type,
            position=position,
            data=data,
        ))

    edges = []
    for e in raw.get("edges", []):
        edges.append(WorkflowEdge(
            id=e["id"],
            source=e["source"],
            target=e["target"],
            sourceHandle=e.get("sourceHandle"),
            targetHandle=e.get("targetHandle"),
        ))

    return WorkflowConfig(nodes=nodes, edges=edges)
