"""Event collector: the primary developer-facing API.

Usage::

    from permission_graph import PermissionGraph

    pg = PermissionGraph()

    with pg.actor("agent-1"):
        with pg.tool("browser"):
            with pg.resource("https://example.com") as res:
                pg.action("http_get", status="allowed")

Every nested context manager pushes a node onto an async-safe stack. When a
new node is opened, an :class:`~permission_graph.models.Event` is recorded
linking the current top of the stack (the parent) to the new node. This is
how the Actor -> Process -> Tool -> API -> Resource -> Action chain is
captured without the caller having to wire ids together manually.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator

from .models import (
    Action,
    ActionStatus,
    Actor,
    API,
    Event,
    Node,
    NodeKind,
    Process,
    Resource,
    Tool,
)
from .storage import SQLiteStorage, StorageBackend

_stack: contextvars.ContextVar[tuple[Node, ...]] = contextvars.ContextVar("permission_graph_stack", default=())


class PermissionGraph:
    """Entry point for recording and querying the runtime permission graph."""

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self.storage: StorageBackend = storage if storage is not None else SQLiteStorage()

    # -- internal -----------------------------------------------------

    def _current_parent(self) -> Node | None:
        stack = _stack.get()
        return stack[-1] if stack else None

    def _record(self, node: Node, label: str = "invokes", **metadata: Any) -> None:
        self.storage.save_node(node)
        parent = self._current_parent()
        if parent is not None:
            event = Event(
                source_id=parent.id,
                source_kind=parent.kind,
                target_id=node.id,
                target_kind=node.kind,
                label=label,
                metadata=metadata,
            )
            self.storage.save_event(event)

    @contextlib.contextmanager
    def _push(self, node: Node, label: str = "invokes", **metadata: Any) -> Iterator[Node]:
        self._record(node, label=label, **metadata)
        token = _stack.set(_stack.get() + (node,))
        try:
            yield node
        finally:
            _stack.reset(token)

    # -- public context managers --------------------------------------

    def actor(self, name: str, **attributes: Any) -> contextlib._GeneratorContextManager[Actor]:
        return self._push(Actor.create(name, **attributes))  # type: ignore[return-value]

    def process(self, name: str, **attributes: Any) -> contextlib._GeneratorContextManager[Process]:
        return self._push(Process.create(name, **attributes))  # type: ignore[return-value]

    def tool(self, name: str, **attributes: Any) -> contextlib._GeneratorContextManager[Tool]:
        return self._push(Tool.create(name, **attributes))  # type: ignore[return-value]

    def api(self, name: str, **attributes: Any) -> contextlib._GeneratorContextManager[API]:
        return self._push(API.create(name, **attributes))  # type: ignore[return-value]

    def resource(self, name: str, **attributes: Any) -> contextlib._GeneratorContextManager[Resource]:
        return self._push(Resource.create(name, **attributes))  # type: ignore[return-value]

    def action(
        self,
        name: str,
        status: ActionStatus | str = ActionStatus.UNKNOWN,
        **attributes: Any,
    ) -> Action:
        """Record a leaf Action node. Unlike the others this is not a context
        manager: an action is a terminal event, not a scope you nest inside.
        """
        if isinstance(status, str):
            status = ActionStatus(status)
        node = Action.create(name, status=status, **attributes)
        self._record(node)
        return node

    # -- convenience ----------------------------------------------------

    def current_chain(self) -> list[Node]:
        """Return the currently open chain of nodes (innermost last)."""
        return list(_stack.get())

    def reset(self) -> None:
        """Clear the current async-local stack. Mainly useful in tests."""
        _stack.set(())

    def close(self) -> None:
        self.storage.close()
