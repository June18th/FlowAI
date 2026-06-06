from __future__ import annotations

from app.engine.models import WorkflowConfig


class DAGParser:
    """Topological sort using Kahn's algorithm with DFS cycle detection."""

    def parse(self, config: WorkflowConfig) -> list[str]:
        """Return topologically sorted node IDs."""
        node_ids = {n.id for n in config.nodes}

        # Build adjacency and in-degree
        adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in config.edges:
            if edge.source in adj and edge.target in adj:
                adj[edge.source].append(edge.target)
                in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Cycle detection via DFS
        self._detect_cycles(adj, list(node_ids))

        # Kahn's algorithm
        queue = [nid for nid in node_ids if in_degree[nid] == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(node_ids):
            # Find remaining nodes for better error message
            remaining = node_ids - set(result)
            raise RuntimeError(f"工作流存在循环依赖，未处理的节点: {remaining}")

        return result

    def _detect_cycles(self, adj: dict[str, list[str]], node_ids: list[str]) -> None:
        """DFS-based cycle detection."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for nid in node_ids:
            if nid not in visited:
                if dfs(nid):
                    raise RuntimeError("工作流存在循环依赖")

    @staticmethod
    def build_dependency_graph(config: WorkflowConfig) -> dict[str, list[str]]:
        """Build source -> [targets] adjacency map."""
        adj: dict[str, list[str]] = {}
        for node in config.nodes:
            adj[node.id] = []
        for edge in config.edges:
            if edge.source in adj and edge.target in adj:
                adj[edge.source].append(edge.target)
        return adj

    @staticmethod
    def build_reverse_dependency_graph(config: WorkflowConfig) -> dict[str, list[str]]:
        """Build target -> [sources] adjacency map."""
        rev: dict[str, list[str]] = {}
        for node in config.nodes:
            rev[node.id] = []
        for edge in config.edges:
            if edge.source in rev and edge.target in rev:
                rev[edge.target].append(edge.source)
        return rev

    @staticmethod
    def find_entry_nodes(config: WorkflowConfig) -> list[str]:
        """Find nodes with no incoming edges."""
        targets = {e.target for e in config.edges}
        return [n.id for n in config.nodes if n.id not in targets]

    @staticmethod
    def find_exit_nodes(config: WorkflowConfig) -> list[str]:
        """Find nodes with no outgoing edges."""
        sources = {e.source for e in config.edges}
        return [n.id for n in config.nodes if n.id not in sources]
