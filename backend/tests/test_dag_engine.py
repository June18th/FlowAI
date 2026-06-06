from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.dag_engine import DAGWorkflowEngine
from app.engine.models import WorkflowConfig, WorkflowEdge, WorkflowNode


def _make_node(nid: str, ntype: str, name: str = "", data: dict | None = None):
    return WorkflowNode(
        id=nid,
        type=ntype,
        data={"name": name or nid, **(data or {})},
        position={"x": 0, "y": 0},
    )


def _make_edge(source: str, target: str, source_handle: str = ""):
    return WorkflowEdge(id=f"{source}-{target}", source=source, target=target, sourceHandle=source_handle)


class TestDAGEngineValidation:
    def setup_method(self):
        self.engine = DAGWorkflowEngine()

    def test_empty_workflow_passes_validation(self):
        """Input/Output only should pass."""
        config = WorkflowConfig(
            nodes=[
                _make_node("1", "input", "输入"),
                _make_node("2", "output", "输出"),
            ],
            edges=[_make_edge("1", "2")],
        )
        node_map = {n.id: n for n in config.nodes}
        errors = self.engine._validate(config, node_map)
        assert errors == []

    def test_condition_node_without_conditions_fails(self):
        """Condition node without conditions list should produce error."""
        config = WorkflowConfig(
            nodes=[
                _make_node("1", "input", "输入"),
                _make_node("2", "condition", "条件"),
                _make_node("3", "output", "输出"),
            ],
            edges=[_make_edge("1", "2"), _make_edge("2", "3")],
        )
        node_map = {n.id: n for n in config.nodes}
        errors = self.engine._validate(config, node_map)
        assert len(errors) == 1
        assert "条件分支节点未配置条件" in errors[0]

    def test_llm_node_without_config_fails(self):
        """LLM node without configId or apiKey should produce error."""
        config = WorkflowConfig(
            nodes=[
                _make_node("1", "input", "输入"),
                _make_node("2", "openai", "GPT"),
                _make_node("3", "output", "输出"),
            ],
            edges=[_make_edge("1", "2"), _make_edge("2", "3")],
        )
        node_map = {n.id: n for n in config.nodes}
        errors = self.engine._validate(config, node_map)
        assert len(errors) >= 1
        assert any("未配置 LLM 连接" in e for e in errors)


class TestInputResolution:
    def setup_method(self):
        self.engine = DAGWorkflowEngine()

    def test_entry_node_gets_initial_input(self):
        result = self.engine._resolve_node_input("node1", [], {}, "hello")
        assert result == {"input": "hello"}

    def test_downstream_node_gets_upstream_output(self):
        result = self.engine._resolve_node_input(
            "node2",
            [_make_edge("node1", "node2")],
            {"node1": {"result": "ok"}},
            "initial",
        )
        assert result == {"result": "ok"}


class TestEdgeIndex:
    def test_build_edge_index(self):
        edges = [_make_edge("a", "b"), _make_edge("b", "c")]
        idx = DAGWorkflowEngine._build_edge_index(edges)
        assert len(idx) == 3
        assert len(idx["a"]) == 1
        assert len(idx["b"]) == 2
