"""Example: recording the access graph of a small AI agent.

Run:
    python examples/agent_example.py
"""

from __future__ import annotations

from permission_graph import PermissionGraph
from permission_graph.export import export_json
from permission_graph.graph import PermissionGraphEngine
from permission_graph.policy import Policy, PolicyEngine
from permission_graph.storage import InMemoryStorage


def simulate_agent_run(pg: PermissionGraph) -> None:
    with pg.actor("research-agent", team="growth"):
        with pg.tool("browser"):
            with pg.resource("https://example.com/pricing"):
                pg.action("http_get", status="allowed")

        with pg.tool("filesystem"):
            with pg.resource("/tmp/notes.txt"):
                pg.action("write_file", status="allowed")

            # Something outside the declared scope: the agent also
            # touches a secrets file it was never granted access to.
            with pg.resource("/etc/secrets.env"):
                pg.action("read_file", status="denied")


def main() -> None:
    pg = PermissionGraph(storage=InMemoryStorage())
    simulate_agent_run(pg)

    engine = PermissionGraphEngine(pg.storage)

    print("== Access paths to /etc/secrets.env ==")
    for path in engine.who_can_access("/etc/secrets.env"):
        print(path.as_chain())

    print("\n== Policy evaluation ==")
    policy = Policy(
        actor_name="research-agent",
        allowed_names={"browser", "http_get", "filesystem", "write_file", "/tmp/notes.txt", "https://example.com/pricing"},
    )
    policy_engine = PolicyEngine(engine)
    for drift in policy_engine.evaluate(policy):
        print(f"[{drift.kind.value}] {drift.description}")

    print("\n== JSON export (truncated) ==")
    print(export_json(pg.storage)[:400], "...")


if __name__ == "__main__":
    main()
