"""Graph engine: turns the flat event log into a queryable permission graph.

The graph is rebuilt on demand from storage rather than kept as a separate
mutable structure — the event log is the single source of truth, which
keeps the model simple and makes replay/audit trivial.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import AccessPath, Action, Event, Node, NodeKind
from .storage import StorageBackend


@dataclass
class GraphSnapshot:
    """An in-memory materialization of nodes + adjacency for one query."""

    nodes: dict[str, Node]
    events: list[Event]
    children: dict[str, list[Event]]
    parents: dict[str, list[Event]]


class PermissionGraphEngine:
    """Read-side queries over the permission graph: paths, explanations,
    unused-permission detection, and out-of-scope detection.
    """

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def snapshot(self) -> GraphSnapshot:
        nodes = {n.id: n for n in self.storage.all_nodes()}
        events = self.storage.all_events()
        children: dict[str, list[Event]] = defaultdict(list)
        parents: dict[str, list[Event]] = defaultdict(list)
        for e in events:
            children[e.source_id].append(e)
            parents[e.target_id].append(e)
        return GraphSnapshot(nodes=nodes, events=events, children=children, parents=parents)

    # -- queries ---------------------------------------------------------

    def who_can_access(self, resource_name: str) -> list[AccessPath]:
        """Return every distinct Actor-rooted path that reaches a resource
        (or action) whose name matches ``resource_name``.
        """
        snap = self.snapshot()
        targets = [
            n for n in snap.nodes.values()
            if n.kind in (NodeKind.RESOURCE, NodeKind.ACTION) and n.name == resource_name
        ]
        paths: list[AccessPath] = []
        for target in targets:
            paths.extend(self._paths_to(target, snap))
        return paths

    def explain(self, node_id: str) -> AccessPath | None:
        """Return the full access chain ending at ``node_id``, from the
        root Actor down to this node — answering "how did we get here?".
        """
        snap = self.snapshot()
        node = snap.nodes.get(node_id)
        if node is None:
            return None
        paths = self._paths_to(node, snap)
        return paths[0] if paths else AccessPath(nodes=[node], events=[])

    def _paths_to(self, target: Node, snap: GraphSnapshot) -> list[AccessPath]:
        results: list[AccessPath] = []

        def walk(node: Node, node_chain: list[Node], event_chain: list[Event]) -> None:
            incoming = snap.parents.get(node.id, [])
            if not incoming:
                results.append(AccessPath(nodes=list(reversed(node_chain)), events=list(reversed(event_chain))))
                return
            for e in incoming:
                parent = snap.nodes.get(e.source_id)
                if parent is None or parent in node_chain:
                    continue
                walk(parent, node_chain + [parent], event_chain + [e])

        walk(target, [target], [])
        return results or [AccessPath(nodes=[target], events=[])]

    def actors(self) -> list[Node]:
        return [n for n in self.storage.all_nodes() if n.kind == NodeKind.ACTOR]

    def actions_by(self, actor_id: str) -> list[Action]:
        """All Action nodes reachable downstream from a given actor id."""
        snap = self.snapshot()
        seen: set[str] = set()
        results: list[Action] = []

        def walk(node_id: str) -> None:
            if node_id in seen:
                return
            seen.add(node_id)
            for e in snap.children.get(node_id, []):
                child = snap.nodes.get(e.target_id)
                if child is None:
                    continue
                if isinstance(child, Action):
                    results.append(child)
                walk(child.id)

        walk(actor_id)
        return results

    def used_edge_kinds(self) -> set[tuple[NodeKind, NodeKind]]:
        """Distinct (source_kind, target_kind) pairs actually observed —
        the raw material for permission-drift and unused-permission checks.
        """
        return {(e.source_kind, e.target_kind) for e in self.storage.all_events()}
