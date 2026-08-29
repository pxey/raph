from permission_graph import ActionStatus, PermissionGraph
from permission_graph.storage import InMemoryStorage


def test_nested_context_managers_record_chain():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1") as actor:
        with pg.tool("browser") as tool:
            with pg.resource("https://example.com") as resource:
                pg.action("http_get", status=ActionStatus.ALLOWED)

    events = pg.storage.all_events()
    assert len(events) == 3  # actor->tool, tool->resource, resource->action

    chain_pairs = [(e.source_id, e.target_id) for e in events]
    assert (actor.id, tool.id) in chain_pairs
    assert (tool.id, resource.id) in chain_pairs


def test_stack_resets_after_context_exits():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        pass
    assert pg.current_chain() == []


def test_sibling_scopes_do_not_leak_parent():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        with pg.tool("browser"):
            pass
        with pg.tool("filesystem") as fs_tool:
            pg.action("read_file")

    events = pg.storage.all_events()
    # filesystem tool's parent must be the actor, not the browser tool
    fs_parent_events = [e for e in events if e.target_id == fs_tool.id]
    assert len(fs_parent_events) == 1
    actor = next(n for n in pg.storage.all_nodes() if n.name == "agent-1")
    assert fs_parent_events[0].source_id == actor.id


def test_action_status_recorded():
    pg = PermissionGraph(storage=InMemoryStorage())
    with pg.actor("agent-1"):
        action = pg.action("delete_file", status="denied")
    assert action.status == ActionStatus.DENIED
