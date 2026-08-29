"""Core domain model for the Runtime Permission Graph.

The graph is built from a chain of typed nodes:

    Actor -> Process -> Tool -> API -> Resource -> Action

Every node is immutable once created and carries an ``id`` that is stable
for the lifetime of the process. Nodes are linked together by ``Event``
records emitted by the collector as code executes inside context managers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NodeKind(str, Enum):
    ACTOR = "actor"
    PROCESS = "process"
    TOOL = "tool"
    API = "api"
    RESOURCE = "resource"
    ACTION = "action"


class Node(BaseModel):
    """A single node in the permission graph."""

    id: str
    kind: NodeKind
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    model_config = {"frozen": True}


class Actor(Node):
    kind: NodeKind = NodeKind.ACTOR

    @classmethod
    def create(cls, name: str, **attributes: Any) -> "Actor":
        return cls(id=_new_id("actor"), name=name, attributes=attributes)


class Process(Node):
    kind: NodeKind = NodeKind.PROCESS

    @classmethod
    def create(cls, name: str, **attributes: Any) -> "Process":
        return cls(id=_new_id("proc"), name=name, attributes=attributes)


class Tool(Node):
    kind: NodeKind = NodeKind.TOOL

    @classmethod
    def create(cls, name: str, **attributes: Any) -> "Tool":
        return cls(id=_new_id("tool"), name=name, attributes=attributes)


class API(Node):
    kind: NodeKind = NodeKind.API

    @classmethod
    def create(cls, name: str, **attributes: Any) -> "API":
        return cls(id=_new_id("api"), name=name, attributes=attributes)


class Resource(Node):
    kind: NodeKind = NodeKind.RESOURCE

    @classmethod
    def create(cls, name: str, **attributes: Any) -> "Resource":
        return cls(id=_new_id("res"), name=name, attributes=attributes)


class ActionStatus(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class Action(Node):
    kind: NodeKind = NodeKind.ACTION
    status: ActionStatus = ActionStatus.UNKNOWN

    @classmethod
    def create(cls, name: str, status: ActionStatus = ActionStatus.UNKNOWN, **attributes: Any) -> "Action":
        return cls(id=_new_id("act"), name=name, status=status, attributes=attributes)


class Event(BaseModel):
    """An observed runtime edge between two nodes in the chain.

    Events are the raw, append-only unit of truth. The graph is derived
    from the accumulated set of events, never mutated directly.
    """

    id: str = Field(default_factory=lambda: _new_id("evt"))
    timestamp: datetime = Field(default_factory=_utcnow)
    source_id: str
    source_kind: NodeKind
    target_id: str
    target_kind: NodeKind
    label: str = "invokes"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class AccessPath(BaseModel):
    """A resolved, explainable chain from an Actor down to an Action/Resource."""

    nodes: list[Node]
    events: list[Event]

    def as_chain(self) -> str:
        return " -> ".join(f"{n.kind.value}:{n.name}" for n in self.nodes)


class DriftKind(str, Enum):
    NEW_EDGE = "new_edge"
    NEW_PERMISSION_USED = "new_permission_used"
    UNUSED_PERMISSION = "unused_permission"
    OUT_OF_SCOPE = "out_of_scope"


class DriftRecord(BaseModel):
    """A detected change in the permission graph relative to a baseline/policy."""

    kind: DriftKind
    description: str
    path: AccessPath
    detected_at: datetime = Field(default_factory=_utcnow)
