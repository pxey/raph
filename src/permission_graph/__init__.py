"""Runtime Permission Graph.

A local-first, open-source library that builds a runtime authorization
graph — Actor -> Process -> Tool -> API -> Resource -> Action — from
events emitted as your application or AI agent runs, so you can answer:

* Who can access what?
* What permissions were actually used?
* What permissions were granted but never used?
* Did an agent do something outside its expected scope?
* What is the full access path to a given resource?

Quick start::

    from permission_graph import PermissionGraph

    pg = PermissionGraph()

    with pg.actor("agent-1"):
        with pg.tool("browser"):
            with pg.resource("https://example.com"):
                pg.action("http_get", status="allowed")

    print(pg.storage.all_events())
"""

from .collector import PermissionGraph
from .graph import GraphSnapshot, PermissionGraphEngine
from .models import (
    Action,
    ActionStatus,
    Actor,
    AccessPath,
    API,
    DriftKind,
    DriftRecord,
    Event,
    Node,
    NodeKind,
    Process,
    Resource,
    Tool,
)
from .policy import Policy, PolicyEngine
from .storage import InMemoryStorage, SQLiteStorage, StorageBackend

__version__ = "0.1.0"

__all__ = [
    "PermissionGraph",
    "PermissionGraphEngine",
    "GraphSnapshot",
    "Actor",
    "Process",
    "Tool",
    "API",
    "Resource",
    "Action",
    "ActionStatus",
    "Node",
    "NodeKind",
    "Event",
    "AccessPath",
    "DriftKind",
    "DriftRecord",
    "Policy",
    "PolicyEngine",
    "StorageBackend",
    "SQLiteStorage",
    "InMemoryStorage",
    "__version__",
]
