"""JSON export helpers for the permission graph."""

from __future__ import annotations

import json
from typing import Any

from .graph import PermissionGraphEngine
from .models import AccessPath, DriftRecord
from .storage import StorageBackend


def graph_to_dict(storage: StorageBackend) -> dict[str, Any]:
    nodes = [n.model_dump(mode="json") for n in storage.all_nodes()]
    events = [e.model_dump(mode="json") for e in storage.all_events()]
    return {"nodes": nodes, "events": events}


def export_json(storage: StorageBackend, indent: int = 2) -> str:
    return json.dumps(graph_to_dict(storage), indent=indent, ensure_ascii=False)


def path_to_dict(path: AccessPath) -> dict[str, Any]:
    return {
        "chain": path.as_chain(),
        "nodes": [n.model_dump(mode="json") for n in path.nodes],
        "events": [e.model_dump(mode="json") for e in path.events],
    }


def drift_to_dict(drift: DriftRecord) -> dict[str, Any]:
    return {
        "kind": drift.kind.value,
        "description": drift.description,
        "detected_at": drift.detected_at.isoformat(),
        "path": path_to_dict(drift.path),
    }


def export_dot(storage: StorageBackend) -> str:
    """Minimal Graphviz DOT export — no hard dependency on graphviz itself,
    just text generation so the user can pipe it into `dot` if they want.
    """
    lines = ["digraph permission_graph {", '  rankdir="LR";']
    nodes = {n.id: n for n in storage.all_nodes()}
    for node in nodes.values():
        label = f"{node.kind.value}\\n{node.name}".replace('"', "'")
        lines.append(f'  "{node.id}" [label="{label}"];')
    for e in storage.all_events():
        lines.append(f'  "{e.source_id}" -> "{e.target_id}" [label="{e.label}"];')
    lines.append("}")
    return "\n".join(lines)
