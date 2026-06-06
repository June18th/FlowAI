from __future__ import annotations

from app.engine.dag_engine import DAGWorkflowEngine
from app.engine.langgraph_engine import LangGraphWorkflowEngine
from app.models.workflow import Workflow


class EngineSelector:
    """Selects workflow engine based on workflow.engine_type."""

    def __init__(self, dag_engine: DAGWorkflowEngine, langgraph_engine: LangGraphWorkflowEngine):
        self._engines = {
            "dag": dag_engine,
            "langgraph": langgraph_engine,
        }

    def select(self, workflow: Workflow):
        engine_type = workflow.engine_type or "dag"
        engine = self._engines.get(engine_type)
        if engine is None:
            engine = self._engines["dag"]
        return engine


# Singleton instances
dag_engine = DAGWorkflowEngine()
langgraph_engine = LangGraphWorkflowEngine()
engine_selector = EngineSelector(dag_engine, langgraph_engine)
