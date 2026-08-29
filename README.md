# Runtime Permission Graph

A local-first, open-source Python library that builds a **runtime
authorization graph** — the *actual* access relationships between actors,
processes, tools, APIs, resources, and actions — by observing what your
application or AI agent does while it runs, not just what it was
declared to be allowed to do.

```
Actor -> Process -> Tool -> API -> Resource -> Action
```

## Why

Declared permissions (IAM policies, RBAC roles, tool allow-lists) tell you
what *should* be possible. They don't tell you:

- Who actually accessed what, and how?
- Which granted permissions were never used?
- Did an agent do something outside its expected scope?
- What is the full causal chain that led to a given action?

Runtime Permission Graph answers these by recording every access as an
`Event` connecting two typed nodes, then letting you query the resulting
graph.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.12+. The only hard runtime dependency is `pydantic`.

## Quick start

```python
from permission_graph import PermissionGraph

pg = PermissionGraph()  # defaults to a local SQLite file

with pg.actor("research-agent"):
    with pg.tool("browser"):
        with pg.resource("https://example.com"):
            pg.action("http_get", status="allowed")
```

That's it — the chain `actor -> tool -> resource -> action` is now
recorded as a set of events in `permission_graph.db`.

### Ask "who can access X?"

```python
from permission_graph.graph import PermissionGraphEngine

engine = PermissionGraphEngine(pg.storage)
for path in engine.who_can_access("https://example.com"):
    print(path.as_chain())
# research-agent -> tool:browser -> resource:https://example.com
```

### Ask "why did this happen?"

```python
action = next(n for n in pg.storage.all_nodes() if n.name == "http_get")
path = engine.explain(action.id)
print(path.as_chain())
```

### Detect scope violations and unused permissions

```python
from permission_graph.policy import Policy, PolicyEngine

policy = Policy(actor_name="research-agent", allowed_names={"browser", "http_get"})
drifts = PolicyEngine(engine).evaluate(policy)

for drift in drifts:
    print(drift.kind, "-", drift.description)
```

### CLI

```bash
permgraph show --db permission_graph.db
permgraph explain <node_id> --db permission_graph.db
permgraph who-can-access https://example.com --db permission_graph.db
permgraph export --db permission_graph.db --format json > graph.json
permgraph export --db permission_graph.db --format dot | dot -Tpng -o graph.png
```

## Design principles

- **Library first, not SaaS.** No server, no dashboard, no telemetry.
  Everything runs locally in your process.
- **Event log is the source of truth.** The graph is derived from an
  append-only event log, never mutated directly — this makes replay,
  audit, and export trivial.
- **Async-safe.** The current chain is tracked with `contextvars`, so
  nested async tasks each see their own correct parent chain.
- **Pluggable storage.** `SQLiteStorage` is the zero-config default;
  implement the `StorageBackend` protocol to plug in anything else.
- **No dashboard in the MVP.** JSON and Graphviz DOT export are provided
  so you can visualize with existing tools.

## Project layout

```
src/permission_graph/
  models.py     domain model: Actor, Process, Tool, API, Resource, Action, Event
  collector.py  PermissionGraph — the context-manager API you use in your code
  storage.py    StorageBackend protocol + SQLiteStorage + InMemoryStorage
  graph.py      read-side queries: access paths, explain(), reachability
  policy.py     Policy + PolicyEngine — scope violations, unused permissions
  export.py     JSON / Graphviz DOT export
  cli.py        `permgraph` command-line tool
tests/          pytest suite
examples/       runnable example scripts
```

## Status

Alpha / MVP. The core model, collector, graph queries, policy engine, and
SQLite storage are implemented and tested. Not yet implemented: a
dashboard (intentionally out of scope for the MVP), distributed/remote
storage backends, and OpenTelemetry interop.

## License

MIT
