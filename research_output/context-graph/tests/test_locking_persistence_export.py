import pytest

from context_graph import ContextGraph, MemoryStore, build_sample, export_vault
from context_graph.locking import LockConflict


def test_lock_conflict_and_reentrant():
    g = ContextGraph()
    g.ensure_root()
    n = g.add_node("n")
    g.locks.acquire_write("a1", n.id)
    g.locks.acquire_write("a1", n.id)                 # re-entrant: no error
    with pytest.raises(LockConflict):
        g.locks.acquire_write("a2", n.id)
    g.locks.release_all("a1")
    g.locks.acquire_write("a2", n.id)                 # freed → now succeeds


def test_disjoint_subtrees_do_not_contend():
    g = ContextGraph()
    g.ensure_root()
    w = g.add_node("W")
    p = g.add_node("P")
    wc = g.add_node("wc", parent_id=w.id)
    pc = g.add_node("pc", parent_id=p.id)
    g.locks.acquire_write("a1", wc.id)
    g.locks.acquire_write("a2", pc.id)                # share only root (IX+IX) → ok


def test_cas_stale_write_fails():
    g = ContextGraph()
    g.ensure_root()
    n = g.add_node("n")
    assert g.store.cas_update("node", n.id, n.version, {"body": "x"}) is True
    assert g.store.cas_update("node", n.id, n.version, {"body": "y"}) is False  # version bumped


def test_persistence_roundtrip(tmp_path):
    g = build_sample()
    path = tmp_path / "db.json"
    g.store.save(path)
    s2 = MemoryStore.load(path)
    assert len(list(s2.all_nodes())) == len(list(g.store.all_nodes()))
    assert len(s2.current_edges()) == len(g.store.current_edges())
    root = s2.get_node("root")
    assert root and root.type.value == "root"


def test_export_mirrors_tree_and_wikilinks(tmp_path):
    g = build_sample()
    out = export_vault(g, tmp_path / "vault")
    files = list(out.rglob("*.md"))
    assert files
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    assert "(mentors)" in text                        # verb-annotated wikilink
    assert (out / "context" / "work").exists()        # folder mirrors the tree
