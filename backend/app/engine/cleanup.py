"""Execution cleanup & rollback — release temp resources after workflow run."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class CleanupManager:
    """Collect cleanup callbacks during execution, run them on completion."""

    def __init__(self):
        self._hooks: list[Callable[[], Any]] = []
        self._rollback_hooks: list[Callable[[], Any]] = []

    def on_cleanup(self, fn: Callable[[], Any]) -> None:
        """Register a cleanup hook (always runs)."""
        self._hooks.append(fn)

    def on_rollback(self, fn: Callable[[], Any]) -> None:
        """Register a rollback hook (runs on failure only)."""
        self._rollback_hooks.append(fn)

    async def cleanup(self, failed: bool = False) -> None:
        """Run all hooks. Rollback hooks run only on failure, in reverse order."""
        if failed:
            for fn in reversed(self._rollback_hooks):
                try:
                    await fn() if _is_coro(fn) else fn()
                except Exception:
                    pass  # cleanup must not throw

        for fn in reversed(self._hooks):
            try:
                await fn() if _is_coro(fn) else fn()
            except Exception:
                pass

    def snapshot_released(self) -> int:
        """Return count of hooks registered."""
        return len(self._hooks) + len(self._rollback_hooks)


def _is_coro(fn: Callable) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)


# ── Node-level temp resource tracking ──

class TempResource:
    """Track a temporary resource produced by a node."""

    def __init__(self, node_id: str, resource_type: str, location: str):
        self.node_id = node_id
        self.resource_type = resource_type  # "minio_object", "local_file", "redis_key"
        self.location = location


class TempRegistry:
    """Collect temp resources during execution for batch cleanup."""

    def __init__(self):
        self._resources: list[TempResource] = []

    def track(self, node_id: str, resource_type: str, location: str) -> None:
        self._resources.append(TempResource(node_id, resource_type, location))

    def list_by_node(self, node_id: str) -> list[TempResource]:
        return [r for r in self._resources if r.node_id == node_id]

    def list_all(self) -> list[TempResource]:
        return list(self._resources)

    def clear(self) -> None:
        self._resources.clear()

    @property
    def count(self) -> int:
        return len(self._resources)
