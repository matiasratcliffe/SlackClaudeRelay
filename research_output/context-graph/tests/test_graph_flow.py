from context_graph import ContextGraph, NodeType
from context_graph.embeddings import HashingEmbedder
from context_graph.graph import Authority


def _graph():
    g = ContextGraph()
    g.ensure_root()
    work = g.add_node("Work", type=NodeType.SECTION, parent_id="root", tags=["work"])
    jane = g.add_node("Jane the mentor", type=NodeType.PERSON, parent_id=work.id)
    me = g.add_node("Me", parent_id="root")
    aurora = g.add_node("Project Aurora", type=NodeType.PROJECT, parent_id=work.id)
    g.link(jane.id, me.id, verb_tags=["mentors"], authority=Authority.USER_STATED)
    g.link(me.id, aurora.id, verb_tags=["works_on"])
    return g, {"work": work, "jane": jane, "me": me, "aurora": aurora}


def test_embed_deterministic():
    e = HashingEmbedder()
    assert e.embed("hello world") == e.embed("hello world")
    assert len(e.embed("x")) == e.dim


def test_search_finds_relevant():
    g, n = _graph()
    hits = g.search("mentor")
    assert hits and hits[0][0].id == n["jane"].id


def test_auto_embed_on_add():
    g, n = _graph()
    assert g.store.get_node(n["me"].id).embedding is not None


def test_traverse_budget_and_path():
    g, _ = _graph()
    res = g.traverse("aurora", budget_nodes=3)
    assert 0 < len(res.node_ids) <= 3
    assert res.markdown.startswith("# Assembled context")
    assert all(nid in res.path for nid in res.node_ids)


def test_dedup_reinforces_edge():
    g, n = _graph()
    first = g.store.edges_from(n["jane"].id)[0]
    again = g.link(n["jane"].id, n["me"].id, verb_tags=["mentors"], weight=1.0)
    assert again.id == first.id and again.weight > first.weight


def test_supersede_preserves_history():
    g, n = _graph()
    e = g.link(n["me"].id, n["jane"].id, verb_tags=["reports_to"])
    new = g.supersede(e.id, verb_tags=["reports_to"])
    assert g.store.get_edge(e.id).valid_to is not None
    assert new.is_current and new.id != e.id


def test_functional_contradiction_flagged():
    g, n = _graph()
    g.link(n["me"].id, n["jane"].id, verb_tags=["reports_to"])
    g.link(n["me"].id, n["aurora"].id, verb_tags=["reports_to"])
    flags = g.contradictions()
    assert any(verb == "reports_to" for _, verb, _ in flags)


def test_hub_summary_recompute():
    g, n = _graph()
    # give Jane degree >= 3: mentors->me (out) + reports_to & owned_by (in)
    g.link(n["me"].id, n["jane"].id, verb_tags=["reports_to"])
    g.link(n["aurora"].id, n["jane"].id, verb_tags=["owned_by"])
    updated = g.recompute_hub_summaries(threshold=3)
    assert updated
    assert g.store.get_node(updated[0]).summary
