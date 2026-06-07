from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.dag_parser import DAGParser
from app.engine.models import WorkflowConfig, WorkflowNode
from app.engine.node_executor.factory import node_executor_factory
from app.engine.workflow_config_parser import parse_workflow_config
from app.models.execution import ExecutionRecord
from app.models.workflow import Workflow


class LangGraphWorkflowEngine:
    ENGINE_TYPE = "langgraph"

    def __init__(self, db_session_factory=None):
        self._db_factory = db_session_factory
        self._dag_parser = DAGParser()

    @staticmethod
    def _sanitize_output(data: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in data.items() if not k.startswith("__")}

    async def execute(
        self,
        workflow: Workflow,
        input_data: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        config = parse_workflow_config(workflow.flow_data)
        node_map = {n.id: n for n in config.nodes}

        graph = StateGraph(dict)

        # Add workflow nodes
        for wn in config.nodes:
            async def make_node_fn(n=wn, evt=event_callback):
                async def node_fn(state: dict) -> dict:
                    current_input = dict(state.get("current_input", {}))
                    current_input["__nodeOutputs__"] = dict(state.get("node_outputs", {}))
                    node_input_before = dict(current_input)
                    self._emit(evt, "NODE_START", nodeId=n.id, nodeName=n.display_name)

                    max_retries = n.data.get("maxRetries", 0)
                    retry_delay_ms = n.data.get("retryDelayMs", 2000)
                    attempt = 0
                    last_error: Exception | None = None

                    while True:
                        try:
                            start = time.time()
                            executor = node_executor_factory.get_executor(n.type)
                            output = await executor.execute(n, current_input, evt)
                            output = self._sanitize_output(output)
                            break
                        except Exception as e:
                            attempt += 1
                            last_error = e
                            if attempt <= max_retries:
                                delay = retry_delay_ms * (2 ** (attempt - 1)) / 1000.0
                                self._emit(evt, "NODE_RETRY", nodeId=n.id,
                                           nodeName=n.display_name,
                                           message=f"重试 {attempt}/{max_retries}，等待 {delay:.1f}s")
                                await asyncio.sleep(delay)
                                continue
                            state["status"] = "FAILED"
                            state["error_message"] = str(last_error)
                            self._emit(evt, "NODE_ERROR", nodeId=n.id,
                                       nodeName=n.display_name,
                                       message=str(last_error))
                            raise

                    duration = int((time.time() - start) * 1000)

                    state.setdefault("node_outputs", {})
                    state["node_outputs"][n.id] = {
                        "nodeId": n.id,
                        "input": self._sanitize_output(node_input_before),
                        "output": output,
                        "status": "SUCCESS",
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration": duration,
                    }
                    state["current_input"] = output
                    state["current_node_id"] = n.id

                    self._emit(evt, "NODE_SUCCESS", nodeId=n.id,
                               nodeName=n.display_name,
                               message=f"耗时 {duration}ms",
                               data={"input": self._sanitize_output(node_input_before),
                                     "output": output})

                    return state
                return node_fn

            node_fn = await make_node_fn(wn)
            graph.add_node(wn.id, node_fn)

        # Add edges
        for edge in config.edges:
            graph.add_edge(edge.source, edge.target)

        # Find entry/exit nodes
        entry_nodes = self._dag_parser.find_entry_nodes(config)
        exit_nodes = self._dag_parser.find_exit_nodes(config)

        for en in entry_nodes:
            graph.add_edge(START, en)
        for ex in exit_nodes:
            graph.add_edge(ex, END)

        compiled = graph.compile()

        # Initial state
        initial_state = {
            "input_data": input_data,
            "current_input": {"input": input_data},
            "node_outputs": {},
            "status": "RUNNING",
            "error_message": None,
            "start_time": time.time(),
            "current_node_id": None,
        }

        # Create execution record
        record = ExecutionRecord(
            flow_id=workflow.id,
            input_data={"input": input_data},
            status="RUNNING",
            node_results=[],
        )
        if db:
            db.add(record)
            await db.flush()
            await db.refresh(record)

        self._emit(event_callback, "WORKFLOW_START", data=record.id)

        result = {}
        try:
            import json as _json
            result = await compiled.ainvoke(initial_state) or {}

            def _safe_serialize(obj):
                try:
                    return _json.loads(_json.dumps(obj, default=str))
                except (ValueError, TypeError):
                    return str(obj)

            record.status = "SUCCESS"
            record.output_data = _safe_serialize(result.get("current_input", {}))
            record.duration = int((time.time() - result.get("start_time", time.time())) * 1000)

            # Build node results from state
            node_results = []
            for nid, ndata in result.get("node_outputs", {}).items():
                node_results.append({
                    "nodeId": nid,
                    "nodeName": node_map.get(nid, WorkflowNode(id=nid, type="")).display_name,
                    "status": ndata.get("status", "SUCCESS"),
                    "input": _safe_serialize(ndata.get("input")),
                    "output": _safe_serialize(ndata.get("output")),
                    "duration": ndata.get("duration", 0),
                })
            record.node_results = node_results

            if db:
                await db.flush()
                await db.commit()

            self._emit(event_callback, "WORKFLOW_COMPLETE",
                       status=record.status,
                       message=f"总耗时 {record.duration}ms",
                       data=record.output_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            record.status = "FAILED"
            record.error_message = str(e)
            record.duration = int((time.time() - result.get("start_time", time.time())) * 1000) if result else 0
            if db:
                await db.flush()
                await db.commit()
            self._emit(event_callback, "WORKFLOW_COMPLETE", status="FAILED",
                       message=f"总耗时 {record.duration}ms",
                       data={"error": str(e)})
            raise

        return {
            "executionId": record.id,
            "status": record.status,
            "inputData": record.input_data,
            "nodeResults": record.node_results,
            "outputData": record.output_data,
            "duration": record.duration,
            "errorMessage": record.error_message,
        }

    @staticmethod
    def _emit(callback: Callable | None, event_type: str, **kwargs) -> None:
        if callback:
            callback({"eventType": event_type, "timestamp": time.time(), **kwargs})


async def _wrap_async(fn):
    """Helper to ensure the node function can be used as async."""
    return lambda state: fn(state)
