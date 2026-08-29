"""Pluggable storage layer.

``StorageBackend`` is the interface every backend must implement. The
default, dependency-free implementation is SQLite (``SQLiteStorage``).
Anything implementing the same protocol (Postgres, in-memory, etc.) can be
swapped in without touching the rest of the library.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .models import Action, Actor, API, Event, Node, NodeKind, Process, Resource, Tool

_NODE_CLASSES: dict[NodeKind, type[Node]] = {
    NodeKind.ACTOR: Actor,
    NodeKind.PROCESS: Process,
    NodeKind.TOOL: Tool,
    NodeKind.API: API,
    NodeKind.RESOURCE: Resource,
    NodeKind.ACTION: Action,
}


class StorageBackend(Protocol):
    """Protocol every storage backend must satisfy."""

    def save_node(self, node: Node) -> None: ...

    def save_event(self, event: Event) -> None: ...

    def get_node(self, node_id: str) -> Node | None: ...

    def all_nodes(self) -> list[Node]: ...

    def all_events(self) -> list[Event]: ...

    def events_for(self, node_id: str) -> list[Event]: ...

    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    attributes TEXT NOT NULL,
    extra TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    label TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_id);
CREATE INDEX IF NOT EXISTS idx_events_target ON events(target_id);
"""


class SQLiteStorage:
    """Default, local-first, zero-config storage backend."""

    def __init__(self, path: str | Path = "permission_graph.db") -> None:
        self._path = str(path)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_node(self, node: Node) -> None:
        data = node.model_dump(mode="json")
        extra = {k: v for k, v in data.items() if k not in {"id", "kind", "name", "attributes", "created_at"}}
        self._conn.execute(
            "INSERT OR REPLACE INTO nodes (id, kind, name, attributes, extra, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                node.id,
                node.kind.value,
                node.name,
                json.dumps(data.get("attributes", {})),
                json.dumps(extra),
                data["created_at"],
            ),
        )
        self._conn.commit()

    def save_event(self, event: Event) -> None:
        data = event.model_dump(mode="json")
        self._conn.execute(
            "INSERT OR REPLACE INTO events "
            "(id, timestamp, source_id, source_kind, target_id, target_kind, label, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                data["timestamp"],
                event.source_id,
                event.source_kind.value,
                event.target_id,
                event.target_kind.value,
                event.label,
                json.dumps(data.get("metadata", {})),
            ),
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        row = self._conn.execute(
            "SELECT id, kind, name, attributes, extra, created_at FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def all_nodes(self) -> list[Node]:
        rows = self._conn.execute(
            "SELECT id, kind, name, attributes, extra, created_at FROM nodes"
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def all_events(self) -> list[Event]:
        rows = self._conn.execute(
            "SELECT id, timestamp, source_id, source_kind, target_id, target_kind, label, metadata "
            "FROM events ORDER BY timestamp ASC"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def events_for(self, node_id: str) -> list[Event]:
        rows = self._conn.execute(
            "SELECT id, timestamp, source_id, source_kind, target_id, target_kind, label, metadata "
            "FROM events WHERE source_id = ? OR target_id = ? ORDER BY timestamp ASC",
            (node_id, node_id),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_node(row: tuple) -> Node:
        node_id, kind, name, attributes, extra, created_at = row
        cls = _NODE_CLASSES[NodeKind(kind)]
        payload = {
            "id": node_id,
            "kind": kind,
            "name": name,
            "attributes": json.loads(attributes),
            "created_at": created_at,
            **json.loads(extra),
        }
        return cls.model_validate(payload)

    @staticmethod
    def _row_to_event(row: tuple) -> Event:
        eid, ts, src, src_kind, tgt, tgt_kind, label, metadata = row
        return Event(
            id=eid,
            timestamp=datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
            if not ts.endswith("+00:00")
            else datetime.fromisoformat(ts),
            source_id=src,
            source_kind=NodeKind(src_kind),
            target_id=tgt,
            target_kind=NodeKind(tgt_kind),
            label=label,
            metadata=json.loads(metadata),
        )


class InMemoryStorage:
    """Simple in-memory backend, useful for tests and short-lived scripts."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._events: list[Event] = []

    def save_node(self, node: Node) -> None:
        self._nodes[node.id] = node

    def save_event(self, event: Event) -> None:
        self._events.append(event)

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def all_nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def all_events(self) -> list[Event]:
        return list(self._events)

    def events_for(self, node_id: str) -> list[Event]:
        return [e for e in self._events if e.source_id == node_id or e.target_id == node_id]

    def close(self) -> None:
        pass
