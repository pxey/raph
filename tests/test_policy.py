from permission_graph import PermissionGraph
from permission_graph.graph import PermissionGraphEngine
from permission_graph.models import DriftKind
from permission_graph.policy import Policy, PolicyEngine
from permission_graph.storage import InMemoryStorage


def test_out_of_scope_access_is_detected():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        with pg.tool("browser"):
            pg.action("http_get")
        with pg.tool("shell"):
            pg.action("run_command")

    engine = PermissionGraphEngine(pg.storage)
    policy_engine = PolicyEngine(engine)
    policy = Policy(actor_name="agent-1", allowed_names={"browser", "http_get"})

    drifts = policy_engine.evaluate(policy)
    out_of_scope = [d for d in drifts if d.kind == DriftKind.OUT_OF_SCOPE]
    assert any(d.path.nodes[-1].name == "shell" for d in out_of_scope)
    assert any(d.path.nodes[-1].name == "run_command" for d in out_of_scope)


def test_unused_permission_is_detected():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        with pg.tool("browser"):
            pg.action("http_get")

    engine = PermissionGraphEngine(pg.storage)
    policy_engine = PolicyEngine(engine)
    policy = Policy(actor_name="agent-1", allowed_names={"browser", "http_get", "shell"})

    drifts = policy_engine.evaluate(policy)
    unused = [d for d in drifts if d.kind == DriftKind.UNUSED_PERMISSION]
    assert len(unused) == 1
    assert "shell" in unused[0].description


def test_fully_compliant_actor_has_no_drift():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        with pg.tool("browser"):
            pg.action("http_get")

    engine = PermissionGraphEngine(pg.storage)
    policy_engine = PolicyEngine(engine)
    policy = Policy(actor_name="agent-1", allowed_names={"browser", "http_get"})

    assert policy_engine.evaluate(policy) == []
