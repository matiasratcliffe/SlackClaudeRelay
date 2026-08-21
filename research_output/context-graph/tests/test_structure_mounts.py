import pytest

from context_graph import ContextGraph, MemoryStore, NodeType, deploy_structure, export_vault
from context_graph.structure import OPINIONATED_STRUCTURE


def test_free_mode_root_only():
    g = ContextGraph()
    assert deploy_structure(g, "free") == []
    assert len(list(g.store.all_nodes())) == 1


def test_opinionated_deploys_fixed_ids_with_descriptions():
    g = ContextGraph()
    created = deploy_structure(g, "opinionated")
    assert set(created) == {sid for sid, *_ in OPINIONATED_STRUCTURE}
    for sid in ("preferences", "skills", "work-facts", "work-team", "personal-facts", "social"):
        n = g.store.get_node(sid)
        assert n is not None and n.type == NodeType.SECTION and n.body  # hardcoded description


def test_opinionated_idempotent():
    g = ContextGraph()
    deploy_structure(g, "opinionated")
    assert deploy_structure(g, "opinionated") == []      # second run creates nothing


def _team_graph():
    g = ContextGraph()
    deploy_structure(g, "opinionated")
    mate = g.add_node("Alex Teammate", type=NodeType.PERSON, parent_id="social",
                      body="Backend dev on my team.")
    return g, mate


def test_mount_keeps_ownership_and_traverses():
    g, mate = _team_graph()
    m = g.mount("work-team", mate.id)
    assert g.store.get_node(mate.id).parent_id == "social"          # ownership unchanged
    assert g.mount("work-team", mate.id).id == m.id                 # idempotent per (host, node)
    res = g.traverse("teammate backend team", budget_nodes=10)
    assert mate.id in res.node_ids                                   # reachable via work-side hop
    # lock scope still keys off the OWNERSHIP ancestors, not the mount host
    g.locks.acquire_write("a1", mate.id)
    assert ("a1", "X") in g.locks.holders(mate.id)
    assert any(a == "a1" for a, _ in g.locks.holders("social"))      # IX on owner subtree
    assert not any(a == "a1" for a, _ in g.locks.holders("work-team"))


def test_mount_guards():
    g, mate = _team_graph()
    with pytest.raises(ValueError):
        g.mount(mate.id, mate.id)                                    # self-mount
    with pytest.raises(ValueError):
        g.mount("social", mate.id)                                   # host is already the owner


def test_edge_enrichment_and_persistence(tmp_path):
    g, mate = _team_graph()
    me = g.add_node("Me", parent_id="personal-facts")
    e = g.link(me.id, mate.id, verb_tags=["collaborates_with"], rationale="pairing on Aurora")
    # root→personal→personal-facts→me (3) + root→social→mate (2), LCA=root → 5 hops
    assert e.similarity is not None and e.tree_distance == 5
    assert e.rationale == "pairing on Aurora"
    g.mount("work-team", mate.id)
    db = tmp_path / "db.json"
    g.store.save(db)
    s2 = MemoryStore.load(db)
    assert s2.mounts_of("work-team") and s2.get_edge(e.id).tree_distance == 5


def test_export_lists_mounts(tmp_path):
    g, mate = _team_graph()
    g.mount("work-team", mate.id, label="teammate")
    out = export_vault(g, tmp_path / "vault")
    team_files = [f for f in out.rglob("team-*.md")]
    assert team_files and "Mounted here" in team_files[0].read_text(encoding="utf-8")
