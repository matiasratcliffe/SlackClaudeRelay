"""A seeded sample graph so the CLI/demo works with zero setup.

Builds root → work/personal/ideas sections with a few people, projects, and notes, plus secondary
edges (mentors, works_on, inspired_by, reports_to) that cross subtrees — enough to make search,
traversal, and export produce meaningful output.
"""

from __future__ import annotations

from .graph import Authority, ContextGraph
from .model import NodeType


def build_sample(graph: ContextGraph | None = None) -> ContextGraph:
    g = graph or ContextGraph()
    g.ensure_root("Context")

    work = g.add_node("Work", type=NodeType.SECTION, parent_id="root", tags=["work"])
    personal = g.add_node("Personal", type=NodeType.SECTION, parent_id="root", tags=["personal"])
    ideas = g.add_node("Ideas", type=NodeType.SECTION, parent_id="root", tags=["ideas"])

    aurora = g.add_node("Project Aurora", type=NodeType.PROJECT, parent_id=work.id,
                        body="Team Aurora's main initiative.", tags=["work", "project"])
    jane = g.add_node("Jane Doe", type=NodeType.PERSON, parent_id=work.id,
                      body="Senior engineer, mentor.", tags=["work", "coworker"])
    me = g.add_node("Me", type=NodeType.PERSON, parent_id=personal.id,
                    body="The graph owner.", tags=["personal"])
    kg_idea = g.add_node("Context knowledge graph", type=NodeType.NOTE, parent_id=ideas.id,
                         body="Agent long-term memory as a traversable graph.",
                         tags=["ideas", "graph", "memory"])

    g.link(jane.id, me.id, verb_tags=["mentors"], authority=Authority.USER_STATED)
    g.link(me.id, aurora.id, verb_tags=["works_on"], authority=Authority.USER_STATED)
    g.link(jane.id, aurora.id, verb_tags=["works_on"])
    g.link(kg_idea.id, aurora.id, verb_tags=["inspired_by"], directed=True)
    g.link(me.id, jane.id, verb_tags=["reports_to"], authority=Authority.USER_STATED)
    return g
