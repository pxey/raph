"""Command-line interface for inspecting an existing permission graph DB.

    permgraph show --db permission_graph.db
    permgraph explain <node_id> --db permission_graph.db
    permgraph who-can-access <name> --db permission_graph.db
    permgraph export --db permission_graph.db --format json > graph.json
"""

from __future__ import annotations

import argparse
import sys

from .export import export_dot, export_json, path_to_dict
from .graph import PermissionGraphEngine
from .storage import SQLiteStorage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="permgraph", description="Inspect a Runtime Permission Graph database.")
    parser.add_argument("--db", default="permission_graph.db", help="Path to the SQLite database (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="List all nodes and events.")

    p_explain = sub.add_parser("explain", help="Explain the access path leading to a node.")
    p_explain.add_argument("node_id")

    p_who = sub.add_parser("who-can-access", help="List access paths reaching a resource/action by name.")
    p_who.add_argument("name")

    p_export = sub.add_parser("export", help="Export the graph.")
    p_export.add_argument("--format", choices=["json", "dot"], default="json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    storage = SQLiteStorage(args.db)
    engine = PermissionGraphEngine(storage)

    try:
        if args.command == "show":
            for node in storage.all_nodes():
                print(f"[{node.kind.value}] {node.id}  {node.name}")
            print("--- events ---")
            for event in storage.all_events():
                print(f"{event.source_id} --{event.label}--> {event.target_id}")

        elif args.command == "explain":
            path = engine.explain(args.node_id)
            if path is None:
                print(f"Node not found: {args.node_id}", file=sys.stderr)
                return 1
            print(path.as_chain())

        elif args.command == "who-can-access":
            paths = engine.who_can_access(args.name)
            if not paths:
                print(f"No access paths found for '{args.name}'.")
            for path in paths:
                print(path.as_chain())

        elif args.command == "export":
            if args.format == "json":
                print(export_json(storage))
            else:
                print(export_dot(storage))

        return 0
    finally:
        storage.close()


if __name__ == "__main__":
    raise SystemExit(main())
