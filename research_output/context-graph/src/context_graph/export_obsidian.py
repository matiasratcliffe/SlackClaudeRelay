"""Export the graph to an Obsidian-compatible vault.

Folder path mirrors the primary ownership tree (folders = storage location, per Obsidian
convention); secondary edges render as verb-annotated `[[wikilinks]]` so Obsidian's backlink and
graph views surface the real semantic structure. One-way export; the raw embedding is omitted.
"""

from __future__ import annotations

import re
from pathlib import Path

from .model import ROOT_ID

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG.sub("-", (text or "").lower()).strip("-") or "node"


def _frontmatter(node) -> str:
    fields = {
        "id": node.id, "type": node.type.value, "tags": node.tags, "owner": node.owner_agent_id,
        "authority": node.authority, "version": node.version,
        "created_at": node.created_at, "updated_at": node.updated_at,
    }
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(map(str, v))}]")
        elif v is not None:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def export_vault(graph, out_dir: str | Path) -> Path:
    """Write one markdown file per node under its tree folder path. Returns the vault dir."""
    out = Path(out_dir)
    store = graph.store

    def rel_dir(node_id: str) -> Path:
        parts = [store.get_node(a).title for a in store.ancestors(node_id) if store.get_node(a)]
        parts = [p for p in parts if p and store.get_node(node_id).parent_id]  # skip for root
        return out.joinpath(*[_slug(p) for p in parts]) if parts else out

    for node in store.all_nodes():
        folder = out if node.id == ROOT_ID else rel_dir(node.id)
        folder.mkdir(parents=True, exist_ok=True)
        body = [_frontmatter(node), "", f"# {node.title}", "", node.body or ""]
        out_edges = store.edges_from(node.id)
        if out_edges:
            body += ["", "## Links"]
            for e in out_edges:
                tgt = store.get_node(e.target_id)
                verb = "|".join(e.verb_tags) or "rel"
                body.append(f"- [[{_slug(tgt.title) if tgt else e.target_id}]] ({verb})")
        mounts = store.mounts_of(node.id)
        if mounts:
            body += ["", "## Mounted here"]
            for m in mounts:
                mn = store.get_node(m.node_id)
                body.append(f"- [[{_slug(mn.title) if mn else m.node_id}]]"
                            f"{f' ({m.label})' if m.label else ''}")
        (folder / f"{_slug(node.title)}-{node.id}.md").write_text("\n".join(body), encoding="utf-8")
    return out
