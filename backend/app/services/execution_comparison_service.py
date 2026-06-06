from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import ExecutionRecord, ExecutionSnapshot


class ExecutionComparisonService:
    async def compare_executions(
        self, db: AsyncSession, execution_id_1: int, execution_id_2: int
    ) -> dict | None:
        stmt1 = select(ExecutionRecord).where(
            ExecutionRecord.id == execution_id_1,
            ExecutionRecord.deleted == 0,
        )
        stmt2 = select(ExecutionRecord).where(
            ExecutionRecord.id == execution_id_2,
            ExecutionRecord.deleted == 0,
        )
        r1_result = await db.execute(stmt1)
        r2_result = await db.execute(stmt2)
        e1 = r1_result.scalar_one_or_none()
        e2 = r2_result.scalar_one_or_none()
        if not e1 or not e2:
            return None

        snap1_stmt = select(ExecutionSnapshot).where(
            ExecutionSnapshot.execution_id == execution_id_1
        ).order_by(ExecutionSnapshot.execution_order)
        snap2_stmt = select(ExecutionSnapshot).where(
            ExecutionSnapshot.execution_id == execution_id_2
        ).order_by(ExecutionSnapshot.execution_order)
        s1_result = await db.execute(snap1_stmt)
        s2_result = await db.execute(snap2_stmt)
        snapshots1 = {s.node_id: s for s in s1_result.scalars().all()}
        snapshots2 = {s.node_id: s for s in s2_result.scalars().all()}

        # Input diff
        input1 = e1.input_data or {}
        input2 = e2.input_data or {}
        input_diff = self._compute_diff(input1, input2)

        # Output diff
        output1 = e1.output_data or {}
        output2 = e2.output_data or {}
        output_diff = self._compute_diff(output1, output2)

        # Node comparisons
        all_node_ids = set(snapshots1.keys()) | set(snapshots2.keys())
        common_nodes = set(snapshots1.keys()) & set(snapshots2.keys())
        node_comparisons = []
        for nid in sorted(common_nodes):
            s1 = snapshots1[nid]
            s2 = snapshots2[nid]
            out1 = s1.output_data or {}
            out2 = s2.output_data or {}
            node_comparisons.append({
                "nodeId": nid,
                "nodeName": s1.node_name or s2.node_name,
                "nodeType": s1.node_type or s2.node_type,
                "status1": s1.status,
                "status2": s2.status,
                "duration1": s1.duration,
                "duration2": s2.duration,
                "durationDelta": (s2.duration or 0) - (s1.duration or 0),
                "outputDiff": self._compute_diff(out1, out2),
                "error1": s1.error_message,
                "error2": s2.error_message,
            })

        nodes_only_in_first = sorted(set(snapshots1.keys()) - common_nodes)
        nodes_only_in_second = sorted(set(snapshots2.keys()) - common_nodes)

        return {
            "execution1": {
                "executionId": e1.id,
                "flowId": e1.flow_id,
                "status": e1.status,
                "duration": e1.duration,
                "executedAt": e1.executed_at.isoformat() if e1.executed_at else None,
            },
            "execution2": {
                "executionId": e2.id,
                "flowId": e2.flow_id,
                "status": e2.status,
                "duration": e2.duration,
                "executedAt": e2.executed_at.isoformat() if e2.executed_at else None,
            },
            "statusComparison": "SAME" if e1.status == e2.status else "CHANGED",
            "durationDiff": {
                "execution1": e1.duration or 0,
                "execution2": e2.duration or 0,
                "delta": (e2.duration or 0) - (e1.duration or 0),
            },
            "inputDiff": input_diff,
            "outputDiff": output_diff,
            "nodeComparisons": node_comparisons,
            "nodesOnlyInFirst": nodes_only_in_first,
            "nodesOnlyInSecond": nodes_only_in_second,
            "commonNodeCount": len(common_nodes),
        }

    @staticmethod
    def _compute_diff(d1: dict, d2: dict) -> dict:
        keys1 = set(d1.keys())
        keys2 = set(d2.keys())
        added = sorted(keys2 - keys1)
        removed = sorted(keys1 - keys2)
        changed = []
        for k in sorted(keys1 & keys2):
            if d1[k] != d2[k]:
                changed.append({
                    "key": k,
                    "value1": str(d1[k])[:200],
                    "value2": str(d2[k])[:200],
                })
        return {
            "addedKeys": added,
            "removedKeys": removed,
            "changedValues": changed,
        }


execution_comparison_service = ExecutionComparisonService()
