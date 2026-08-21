"""`context-graph` CLI.

Self-contained by default: the in-memory backend + offline embedder + a seeded sample graph, so
`search`/`traverse`/`export`/`demo` work with no service or credentials. The in-memory backend is
process-local (ephemeral across invocations); use `--backend neo4j` (env `NEO4J_URI/USER/PASSWORD`)
for persistence. `--empty` skips seeding.
"""

from __future__ import annotations

import argparse
import json
import os

from .export_obsidian import export_vault
from .graph import ContextGraph
from .model import NodeType
from .sample import build_sample


def _build_graph(args) -> ContextGraph:
    if getattr(args, "backend", "memory") == "neo4j":
        from .store.neo4j_store import Neo4jStore
        store = Neo4jStore(os.environ["NEO4J_URI"], os.environ["NEO4J_USER"],
                           os.environ["NEO4J_PASSWORD"])
        store.init()
        return ContextGraph(store, agent_id=args.agent)
    g = ContextGraph(agent_id=args.agent)
    if not getattr(args, "empty", False):
        build_sample(g)          # keep the memory CLI demoable
    else:
        g.ensure_root()
    return g


def _emit(obj, as_json: bool) -> None:
    print(json.dumps(obj, indent=2, default=str) if as_json else obj)


def cmd_init(args):
    g = _build_graph(args)
    _emit(f"initialized ({args.backend}); nodes={len(list(g.store.all_nodes()))}", args.json)


def cmd_add_node(args):
    g = _build_graph(args)
    n = g.add_node(args.title, type=NodeType(args.type), body=args.body or "",
                   parent_id=args.parent, tags=args.tag or [])
    _emit({"id": n.id, "title": n.title} if args.json else f"added {n.id} {n.title!r}", args.json)


def cmd_link(args):
    g = _build_graph(args)
    e = g.link(args.source, args.target, verb_tags=args.verb or [], directed=not args.undirected)
    _emit({"id": e.id} if args.json else f"linked {args.source}->{args.target} {e.id}", args.json)


def cmd_search(args):
    g = _build_graph(args)
    hits = g.search(args.query, query_tags=args.tag or [])
    if args.json:
        _emit([{"id": n.id, "title": n.title, "weight": w} for n, w in hits], True)
    else:
        for n, w in hits:
            print(f"{w:5.3f}  {n.type.value:8}  {n.title}  [{n.id}]")


def cmd_traverse(args):
    g = _build_graph(args)
    res = g.traverse(args.query, budget_nodes=args.budget, strategy=args.strategy,
                     query_tags=args.tag or [])
    if args.json:
        _emit({"nodes": res.node_ids, "edges": res.edges, "markdown": res.markdown}, True)
    else:
        print(res.markdown)


def cmd_export(args):
    g = _build_graph(args)
    path = export_vault(g, args.out)
    _emit(f"exported vault to {path}", args.json)


def cmd_lock_status(args):
    g = _build_graph(args)
    _emit(g.locks.snapshot() or "no locks held", args.json)


def cmd_demo(args):
    g = _build_graph(args)
    print("# demo: sample graph loaded\n")
    print("## search 'aurora mentor'")
    for n, w in g.search("aurora mentor"):
        print(f"  {w:5.3f}  {n.title}")
    print("\n## traverse 'who mentors me on aurora'\n")
    print(g.traverse("who mentors me on aurora", budget_nodes=6).markdown)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="context-graph", description=__doc__)
    p.add_argument("--backend", choices=["memory", "neo4j"], default="memory")
    p.add_argument("--agent", default="cli", help="agent id for lock ownership/provenance")
    p.add_argument("--empty", action="store_true", help="do not seed the sample graph (memory)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    a = sub.add_parser("add-node"); a.set_defaults(func=cmd_add_node)
    a.add_argument("title"); a.add_argument("--type", default="note",
                                            choices=[t.value for t in NodeType])
    a.add_argument("--body"); a.add_argument("--parent", default="root")
    a.add_argument("--tag", action="append")

    l = sub.add_parser("link"); l.set_defaults(func=cmd_link)
    l.add_argument("source"); l.add_argument("target")
    l.add_argument("--verb", action="append"); l.add_argument("--undirected", action="store_true")

    s = sub.add_parser("search"); s.set_defaults(func=cmd_search)
    s.add_argument("query"); s.add_argument("--tag", action="append")

    t = sub.add_parser("traverse"); t.set_defaults(func=cmd_traverse)
    t.add_argument("query"); t.add_argument("--budget", type=int, default=8)
    t.add_argument("--strategy", choices=["activation", "ppr"], default="activation")
    t.add_argument("--tag", action="append")

    e = sub.add_parser("export"); e.set_defaults(func=cmd_export)
    e.add_argument("--out", default="vault-export")

    sub.add_parser("lock-status").set_defaults(func=cmd_lock_status)
    sub.add_parser("demo").set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
