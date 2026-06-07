from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.config import settings
from app.database import async_session as _async_session_factory
from app.engine.checkpoint import apply_checkpoint, build_checkpoint, load_checkpoint
from app.engine.circuit_breaker import get_breaker
from app.engine.dag_parser import DAGParser
from app.engine.models import WorkflowConfig, WorkflowEdge, WorkflowNode
from app.engine.recovery_worker import get_worker_id
from app.engine.workflow_config_parser import parse_workflow_config
from app.metrics import (
    record_execution_end,
    record_execution_start,
    record_node_failure,
    record_node_retry,
    record_node_success,
    record_resume,
)
from app.models.execution import ExecutionRecord, ExecutionSnapshot, ExecutionVariable
from app.models.workflow import Workflow
from app.telemetry import get_tracer

# ── Redis cancel flag helpers ──

_cancel_redis: aioredis.Redis | None = None


def _get_cancel_redis() -> aioredis.Redis:
    global _cancel_redis
    if _cancel_redis is None:
        _cancel_redis = aioredis.Redis(connection_pool=aioredis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
            max_connections=5,
            protocol=2,
        ))
    return _cancel_redis


async def _set_cancel_flag(execution_id: int) -> None:
    r = _get_cancel_redis()
    await r.set(f"execution:cancel:{execution_id}", "1", ex=3600)


async def _check_cancel_flag(execution_id: int) -> bool:
    r = _get_cancel_redis()
    val = await r.get(f"execution:cancel:{execution_id}")
    return val == "1"


async def _clear_cancel_flag(execution_id: int) -> None:
    r = _get_cancel_redis()
    await r.delete(f"execution:cancel:{execution_id}")


class DAGWorkflowEngine:
    ENGINE_TYPE = "dag"

    def __init__(self, db_session_factory=None):
        self._db_factory = db_session_factory
        self._dag_parser = DAGParser()

    # ---------- Public API ----------

    async def execute(
        self,
        workflow: Workflow,
        input_data: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
        db: AsyncSession | None = None,
        resume_record: ExecutionRecord | None = None,
    ) -> dict[str, Any]:
        config = parse_workflow_config(workflow.flow_data)
        sorted_nodes = self._dag_parser.parse(config)
        node_map = {n.id: n for n in config.nodes}
        edge_index = self._build_edge_index(config.edges)

        errors = self._validate(config, node_map)
        if errors:
            msg = "执行前置校验失败: " + "; ".join(errors)
            self._emit(event_callback, "WORKFLOW_COMPLETE", status="FAILED", message=msg)
            raise RuntimeError(msg)

        # ── Metrics ──
        record_execution_start("dag")
        exec_start_time = time.time()

        # ── Resume or fresh execution ──
        if resume_record and resume_record.execution_state:
            record = resume_record
            (node_outputs, completed_ids, skipped_nodes,
             node_results, final_output, _) = load_checkpoint(record.execution_state)
            record.status = "RUNNING"
            record.worker_id = get_worker_id()
            if db:
                await db.flush()
            self._emit(event_callback, "WORKFLOW_RESUME",
                       data=record.id,
                       message=f"从节点 {record.last_completed_node_id} 之后恢复，"
                               f"已完成 {len(completed_ids)}/{len(sorted_nodes)} 个节点")
            record_resume("initiated")
        else:
            node_outputs: dict[str, dict[str, Any]] = {}
            completed_ids: set[str] = set()
            skipped_nodes: set[str] = set()
            node_results: list[dict] = []
            final_output: dict[str, Any] = {}

            record = ExecutionRecord(
                flow_id=workflow.id,
                input_data={"input": input_data},
                status="RUNNING",
                node_results=[],
                engine_type="dag",
                worker_id=get_worker_id(),
            )
            if db:
                db.add(record)
                await db.flush()
                await db.refresh(record)

            self._emit(event_callback, "WORKFLOW_START", data=record.id)

        # ── Start heartbeat ──
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(record.id, heartbeat_stop)
        )

        try:
            node_results, skipped_nodes, final_output = await self._execute_nodes(
                config, sorted_nodes, edge_index, input_data,
                record.id, workflow.id, event_callback, db,
                node_outputs, completed_ids, skipped_nodes,
                node_results, final_output, record,
            )

            record.status = "SUCCESS"
            record.output_data = (final_output if isinstance(final_output, dict)
                                  else {"output": str(final_output)})
            record.node_results = node_results
            record.duration = (int((time.time() - record.executed_at.timestamp()) * 1000)
                               if record.executed_at else 0)
            if db:
                await db.flush()
                await db.commit()

            self._emit(event_callback, "WORKFLOW_COMPLETE",
                       status="SUCCESS",
                       message=f"总耗时 {record.duration}ms",
                       data=record.output_data)
            record_execution_end("SUCCESS", "dag", time.time() - exec_start_time)
        except Exception as e:
            import traceback
            traceback.print_exc()
            record.status = "FAILED"
            record.error_message = str(e)
            record.duration = (int((time.time() - record.executed_at.timestamp()) * 1000)
                               if record.executed_at else 0)
            if db:
                await db.flush()
                await db.commit()

            self._emit(event_callback, "WORKFLOW_COMPLETE", status="FAILED",
                       message=f"总耗时 {record.duration}ms",
                       data={"error": str(e)})
            record_execution_end("FAILED", "dag", time.time() - exec_start_time)
            raise
        finally:
            heartbeat_stop.set()
            await heartbeat_task
            await _clear_cancel_flag(record.id)

        return {
            "executionId": record.id,
            "status": record.status,
            "inputData": record.input_data,
            "nodeResults": record.node_results,
            "outputData": record.output_data,
            "duration": record.duration,
            "errorMessage": record.error_message,
        }

    # ---------- Heartbeat ----------

    async def _heartbeat_loop(self, record_id: int, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                if await _check_cancel_flag(record_id):
                    return
                async with _async_session_factory() as session:
                    stmt = select(ExecutionRecord).where(ExecutionRecord.id == record_id)
                    result = await session.execute(stmt)
                    r = result.scalar_one_or_none()
                    if r and r.status == "RUNNING":
                        r.heartbeat_at = datetime.utcnow()
                        await session.commit()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass

    # ---------- Core execution loop ----------

    async def _execute_nodes(
        self,
        config: WorkflowConfig,
        sorted_nodes: list[str],
        edge_index: dict[str, list[WorkflowEdge]],
        input_data: str,
        execution_id: int,
        flow_id: int,
        event_callback: Callable | None,
        db: AsyncSession | None,
        node_outputs: dict[str, dict[str, Any]],
        completed_ids: set[str],
        skipped_nodes: set[str],
        node_results: list[dict],
        final_output: dict[str, Any],
        record: ExecutionRecord,
    ) -> tuple[list[dict], set[str], Any]:
        node_map = {n.id: n for n in config.nodes}

        for node_id in sorted_nodes:
            if node_id in skipped_nodes or node_id in completed_ids:
                continue

            # Cancel check — stop before next node
            if await _check_cancel_flag(execution_id):
                record.status = "CANCELLED"
                record.error_message = "执行已被用户取消"
                apply_checkpoint(record, node_outputs, completed_ids, skipped_nodes,
                                 node_results, final_output, sorted_nodes, node_id)
                if db:
                    await db.flush()
                self._emit(event_callback, "WORKFLOW_CANCELLED",
                           data=record.id, message="执行已被用户取消")
                return node_results, skipped_nodes, final_output

            node = node_map.get(node_id)
            if not node:
                continue

            node_input = self._resolve_node_input(node_id, config.edges, node_outputs, input_data)
            node_input["__nodeOutputs__"] = {
                nid: out for nid, out in node_outputs.items()
                if nid != node_id
            }

            snapshot = ExecutionSnapshot(
                execution_id=execution_id,
                flow_id=flow_id,
                node_id=node_id,
                node_type=node.type,
                node_name=node.display_name,
                status="RUNNING",
                input_data=node_input,
                started_at=datetime.utcnow(),
                execution_order=len(node_results) + len(completed_ids),
            )
            if db:
                db.add(snapshot)
                await db.flush()

            node_start = time.time()
            self._emit(event_callback, "NODE_START", nodeId=node_id, nodeName=node.display_name)

            max_retries = node.data.get("maxRetries", 0)
            retry_delay_ms = node.data.get("retryDelayMs", 2000)
            attempt = 0
            last_error: Exception | None = None

            # Circuit breaker check
            breaker = get_breaker(node.type)
            if not breaker.allow():
                msg = f"熔断器已开启，节点类型 '{node.type}' 暂时不可用"
                self._emit(event_callback, "NODE_ERROR", nodeId=node_id,
                           nodeName=node.display_name, message=msg)
                node_results.append({
                    "nodeId": node_id, "nodeName": node.display_name,
                    "status": "FAILED", "input": self._sanitize_output(node_input),
                    "error": f"CIRCUIT_OPEN: {msg}", "duration": 0, "retries": 0,
                })
                skipped_nodes.add(node_id)
                snapshot.status = "FAILED"
                snapshot.error_message = f"CIRCUIT_OPEN: {msg}"
                if db:
                    await db.flush()
                continue

            while True:
                try:
                    executor = node_executor_factory.get_executor(node.type)
                    output = await executor.execute(node, node_input, event_callback)
                    output = self._sanitize_output(output)
                    breaker.success()
                    break
                except Exception as e:
                    attempt += 1
                    last_error = e
                    if attempt <= max_retries:
                        delay = retry_delay_ms * (2 ** (attempt - 1)) / 1000.0
                        self._emit(event_callback, "NODE_RETRY", nodeId=node_id,
                                   nodeName=node.display_name,
                                   message=f"重试 {attempt}/{max_retries}，等待 {delay:.1f}s",
                                   data={"error": str(e), "attempt": attempt, "maxRetries": max_retries})
                        record_node_retry(node.type)
                        await asyncio.sleep(delay)
                        continue
                    duration = int((time.time() - node_start) * 1000)
                    node_results.append({
                        "nodeId": node_id,
                        "nodeName": node.display_name,
                        "status": "FAILED",
                        "input": self._sanitize_output(node_input),
                        "error": str(last_error),
                        "duration": duration,
                        "retries": attempt - 1,
                    })
                    snapshot.status = "FAILED"
                    snapshot.error_message = str(last_error)
                    snapshot.completed_at = datetime.utcnow()
                    snapshot.duration = duration
                    record_node_failure(node.type, duration / 1000.0)
                    breaker.failure()
                    self._emit(event_callback, "NODE_ERROR", nodeId=node_id,
                               nodeName=node.display_name, message=str(last_error))
                    # Save checkpoint even on failure so resume knows where we stopped
                    apply_checkpoint(record, node_outputs, completed_ids, skipped_nodes,
                                     node_results, final_output, sorted_nodes, node_id)
                    if db:
                        await db.flush()
                    raise

            duration = int((time.time() - node_start) * 1000)
            node_results.append({
                "nodeId": node_id,
                "nodeName": node.display_name,
                "status": "SUCCESS",
                "input": self._sanitize_output(node_input),
                "output": self._sanitize_output(output),
                "duration": duration,
                "retries": attempt,
            })
            node_outputs[node_id] = output
            completed_ids.add(node_id)

            snapshot.status = "SUCCESS"
            snapshot.output_data = self._sanitize_output(output)
            snapshot.completed_at = datetime.utcnow()
            snapshot.duration = duration
            record_node_success(node.type, duration / 1000.0)

            self._emit(event_callback, "NODE_SUCCESS", nodeId=node_id,
                       nodeName=node.display_name,
                       message=f"耗时 {duration}ms",
                       data={"input": self._sanitize_output(node_input),
                             "output": self._sanitize_output(output)})

            if node.type == "condition" and "__selectedBranch__" in output:
                selected = output["__selectedBranch__"]
                self._mark_skipped_branches(node_id, selected, config.edges, node_map, skipped_nodes)

            final_output = output

            # ── Save checkpoint after each successful node ──
            apply_checkpoint(record, node_outputs, completed_ids, skipped_nodes,
                             node_results, final_output, sorted_nodes, node_id)
            if db:
                await db.flush()

        return node_results, skipped_nodes, final_output

    # ---------- Condition branch routing ----------

    def _mark_skipped_branches(
        self,
        condition_node_id: str,
        selected_branch: str,
        edges: list[WorkflowEdge],
        node_map: dict[str, WorkflowNode],
        skipped: set[str],
    ) -> None:
        branches = [e for e in edges if e.source == condition_node_id]

        for branch_edge in branches:
            branch_id = branch_edge.sourceHandle or branch_edge.target
            is_selected = (
                branch_id == selected_branch
                or branch_edge.id == selected_branch
                or branch_edge.sourceHandle == selected_branch
            )
            if not is_selected:
                self._skip_downstream(branch_edge.target, edges, node_map, skipped)

    def _skip_downstream(
        self,
        node_id: str,
        edges: list[WorkflowEdge],
        node_map: dict[str, WorkflowNode],
        skipped: set[str],
    ) -> None:
        if node_id in skipped:
            return

        incoming = [e for e in edges if e.target == node_id]
        if not incoming:
            skipped.add(node_id)
        else:
            all_skipped = True
            for e in incoming:
                if e.source not in skipped:
                    all_skipped = False
                    break
            if all_skipped:
                skipped.add(node_id)
            else:
                return

        outgoing = [e for e in edges if e.source == node_id]
        for e in outgoing:
            self._skip_downstream(e.target, edges, node_map, skipped)

    # ---------- Input resolution ----------

    def _resolve_node_input(
        self,
        node_id: str,
        edges: list[WorkflowEdge],
        node_outputs: dict[str, dict[str, Any]],
        initial_input: str,
    ) -> dict[str, Any]:
        incoming = [e for e in edges if e.target == node_id]
        if not incoming:
            if isinstance(initial_input, str):
                return {"input": initial_input}
            return dict(initial_input) if isinstance(initial_input, dict) else {"input": str(initial_input)}

        merged: dict[str, Any] = {}
        for edge in incoming:
            src_output = node_outputs.get(edge.source, {})
            if edge.sourceHandle and edge.sourceHandle in src_output:
                merged[edge.sourceHandle] = src_output[edge.sourceHandle]
            else:
                merged.update(src_output)
        return merged

    # ---------- Helpers ----------

    @staticmethod
    def _build_edge_index(edges: list[WorkflowEdge]) -> dict[str, list[WorkflowEdge]]:
        idx: dict[str, list[WorkflowEdge]] = {}
        for e in edges:
            idx.setdefault(e.source, []).append(e)
            idx.setdefault(e.target, []).append(e)
        return idx

    @staticmethod
    def _emit(callback: Callable | None, event_type: str, **kwargs) -> None:
        if callback:
            callback({"eventType": event_type, "timestamp": time.time(), **kwargs})

    @staticmethod
    def _sanitize_output(data: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in data.items() if not k.startswith("__")}

    # ---------- Pre-execution validation ----------

    @staticmethod
    def _validate(config: WorkflowConfig, node_map: dict[str, WorkflowNode]) -> list[str]:
        errors: list[str] = []
        for node in config.nodes:
            node_type = node.type
            data = node.data
            node_name = node.display_name

            if node_type in ("input", "output"):
                continue

            if node_type == "condition":
                conditions = data.get("conditions", [])
                if not conditions:
                    errors.append(f"[{node_name}] 条件分支节点未配置条件")
                continue

            if node_type in ("openai", "deepseek", "qwen", "step", "zhipu",
                             "llm", "ai_ping", "apifree", "volcengine_agent_plan", "react_agent"):
                config_id = data.get("configId")
                api_key = data.get("apiKey", "")
                api_url = data.get("apiUrl", "")
                provider = data.get("provider", "")
                if not config_id and not (api_key and api_url):
                    errors.append(
                        f"[{node_name}] 未配置 LLM 连接: 请选择全局配置或填写 API Key/URL"
                    )
                if not provider and not config_id:
                    errors.append(f"[{node_name}] 未指定模型厂商 (provider)")

            if node_type == "tts":
                provider = data.get("provider", "")
                text = data.get("text", "")
                if not provider:
                    errors.append(f"[{node_name}] TTS 节点未指定厂商 (provider)")
                if not text:
                    errors.append(f"[{node_name}] TTS 节点未指定合成文本")

            if node_type == "weather_query":
                api_key = data.get("apiKey", "")
                if not api_key:
                    errors.append(f"[{node_name}] 天气查询节点未配置高德 API Key")

            if node_type == "web_search":
                mcp_tool_ids = data.get("mcpToolIds", [])
                if not mcp_tool_ids:
                    errors.append(f"[{node_name}] 联网搜索节点未配置 MCP 工具")

        return errors
