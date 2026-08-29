from permission_graph.models import Actor, Event, NodeKind, Resource
from permission_graph.storage import InMemoryStorage, SQLiteStorage


def test_actor_creation_has_stable_id_and_kind():
    a = Actor.create("agent-1", role="assistant")
    assert a.kind == NodeKind.ACTOR
    assert a.name == "agent-1"
    assert a.attributes["role"] == "assistant"
    assert a.id.startswith("actor_")


def test_inmemory_storage_roundtrip():
    storage = InMemoryStorage()
    a = Actor.create("agent-1")
    r = Resource.create("db://prod")
    storage.save_node(a)
    storage.save_node(r)
    event = Event(source_id=a.id, source_kind=a.kind, target_id=r.id, target_kind=r.kind)
    storage.save_event(event)

    assert storage.get_node(a.id) == a
    assert len(storage.all_nodes()) == 2
    assert len(storage.all_events()) == 1
    assert len(storage.events_for(a.id)) == 1


def test_sqlite_storage_roundtrip(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    a = Actor.create("agent-1", team="platform")
    r = Resource.create("s3://bucket/key")
    storage.save_node(a)
    storage.save_node(r)
    event = Event(source_id=a.id, source_kind=a.kind, target_id=r.id, target_kind=r.kind, label="reads")
    storage.save_event(event)
    storage.close()

    # reopen and confirm persistence
    reopened = SQLiteStorage(db_path)
    fetched_actor = reopened.get_node(a.id)
    assert fetched_actor is not None
    assert fetched_actor.name == "agent-1"
    assert fetched_actor.attributes["team"] == "platform"

    events = reopened.all_events()
    assert len(events) == 1
    assert events[0].label == "reads"
    reopened.close()
