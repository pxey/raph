"""Policy engine: declare the expected scope for an actor, then evaluate
the real runtime graph against it.

A policy is intentionally simple — a set of allowed node *names* reachable
from a given actor name (tools, apis, resources). This is enough to answer
the two questions the MVP cares about:

1. Did the actor do something outside its expected scope? (``OUT_OF_SCOPE``)
2. Did the actor never use a permission it was granted? (``UNUSED_PERMISSION``)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .graph import PermissionGraphEngine
from .models import AccessPath, DriftKind, DriftRecord, NodeKind


class Policy(BaseModel):
    """Declares what a named actor is expected to be able to reach."""

    actor_name: str
    allowed_names: set[str] = Field(default_factory=set)
    """Names of tools/apis/resources/actions this actor is allowed to reach."""

    def allows(self, name: str) -> bool:
        return name in self.allowed_names


class PolicyEngine:
    """Evaluates policies against the observed runtime graph."""

    def __init__(self, engine: PermissionGraphEngine) -> None:
        self.engine = engine

    def evaluate(self, policy: Policy) -> list[DriftRecord]:
        drifts: list[DriftRecord] = []
        snap = self.engine.snapshot()

        matching_actors = [n for n in snap.nodes.values() if n.kind == NodeKind.ACTOR and n.name == policy.actor_name]
        used_names: set[str] = set()

        for actor in matching_actors:
            reachable = self._reachable_named_nodes(actor.id, snap)
            for node, path in reachable:
                used_names.add(node.name)
                if not policy.allows(node.name):
                    drifts.append(
                        DriftRecord(
                            kind=DriftKind.OUT_OF_SCOPE,
                            description=(
                                f"Actor '{policy.actor_name}' reached "
                                f"'{node.name}' ({node.kind.value}), which is not in its allowed scope."
                            ),
                            path=path,
                        )
                    )

        for allowed in policy.allowed_names - used_names:
            drifts.append(
                DriftRecord(
                    kind=DriftKind.UNUSED_PERMISSION,
                    description=(
                        f"Actor '{policy.actor_name}' was granted access to "
                        f"'{allowed}' but never used it."
                    ),
                    path=AccessPath(nodes=[], events=[]),
                )
            )

        return drifts

    def _reachable_named_nodes(self, actor_id: str, snap) -> list[tuple]:  # type: ignore[no-untyped-def]
        results: list[tuple] = []
        seen: set[str] = set()

        def walk(node_id: str, node_chain: list, event_chain: list) -> None:  # type: ignore[type-arg]
            if node_id in seen:
                return
            seen.add(node_id)
            for e in snap.children.get(node_id, []):
                child = snap.nodes.get(e.target_id)
                if child is None:
                    continue
                new_node_chain = node_chain + [child]
                new_event_chain = event_chain + [e]
                results.append((child, AccessPath(nodes=new_node_chain, events=new_event_chain)))
                walk(child.id, new_node_chain, new_event_chain)

        root = snap.nodes.get(actor_id)
        if root is not None:
            walk(actor_id, [root], [])
        return results
