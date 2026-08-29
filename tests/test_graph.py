from permission_graph import PermissionGraph
from permission_graph.graph import PermissionGraphEngine
from permission_graph.storage import InMemoryStorage


def _build_sample_graph() -> PermissionGraph:
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        with pg.tool("browser"):
            with pg.api("http"):
                with pg.resource("https://example.com"):
                    pg.action("http_get", status="allowed")
    return pg


def test_explain_returns_full_chain():
    pg = _build_sample_graph()
    engine = PermissionGraphEngine(pg.storage)
    action_node = next(n for n in pg.storage.all_nodes() if n.name == "http_get")

    path = engine.explain(action_node.id)
    assert path is not None
    names = [n.name for n in path.nodes]
    assert names == ["agent-1", "browser", "http", "https://example.com", "http_get"]


def test_who_can_access_finds_actor_paths():
    pg = _build_sample_graph()
    engine = PermissionGraphEngine(pg.storage)

    paths = engine.who_can_access("https://example.com")
    assert len(paths) == 1
    assert paths[0].nodes[0].name == "agent-1"
    assert paths[0].nodes[-1].name == "https://example.com"


def test_actions_by_actor():
    pg = _build_sample_graph()
    engine = PermissionGraphEngine(pg.storage)
    actor = next(n for n in pg.storage.all_nodes() if n.name == "agent-1")

    actions = engine.actions_by(actor.id)
    assert len(actions) == 1
    assert actions[0].name == "http_get"


def test_who_can_access_unknown_resource_returns_empty():
    pg = _build_sample_graph()
    engine = PermissionGraphEngine(pg.storage)
    assert engine.who_can_access("nonexistent") == []
