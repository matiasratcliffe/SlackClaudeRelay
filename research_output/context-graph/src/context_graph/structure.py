"""Deployable graph structures.

`opinionated` deploys the owner's macro-node taxonomy — empty of content but rich in *addresses*:
every section has a FIXED id and a hardcoded description, so every agent (and every skill that
describes this tool) finds the same sections at the same ids on any deployment. `free` deploys only
the root. Deployment is idempotent: existing nodes are left untouched.
"""

from __future__ import annotations

from .model import NodeType

# (id, parent_id, title, type, tags, description) — descriptions are the deployed node bodies.
OPINIONATED_STRUCTURE: list[tuple[str, str, str, NodeType, list[str], str]] = [
    ("preferences", "root", "User Preferences", NodeType.SECTION, ["preferences"],
     "Stable, cross-domain preferences about how the owner likes things done — tone, formats, "
     "defaults, dos and don'ts. Agents MUST consult this section before acting on the owner's "
     "behalf, and write durable preference learnings here (not in chat history)."),
    ("skills", "root", "Skills & Guidance", NodeType.SECTION, ["skills", "guidance"],
     "Behaviour and guidance nodes — HOW to do things — kept deliberately separate from pure "
     "context/knowledge (facts). Store procedures, playbooks, and skill references here; store "
     "what is true about the world in the facts sections instead."),
    ("work", "root", "Work", NodeType.SECTION, ["work"],
     "Everything owned by the owner's professional life. Projects, work facts, and the team live "
     "in the subsections; cross-cutting relationships use secondary edges or mounts."),
    ("work-facts", "work", "Work Facts", NodeType.SECTION, ["work", "facts"],
     "Durable facts about the owner's job: systems, processes, decisions, deadlines, domain "
     "knowledge. Sub-agents with limited chat context persist work learnings here."),
    ("work-team", "work", "Team", NodeType.SECTION, ["work", "team", "people"],
     "The owner's team as a navigation hub. People are OWNED by Social Context and MOUNTED here — "
     "mounting keeps one canonical person node while letting work-side traversal reach them."),
    ("work-projects", "work", "Projects", NodeType.SECTION, ["work", "projects"],
     "One node per project/initiative, each owning its sub-facts and linking to the people and "
     "systems involved."),
    ("personal", "root", "Personal", NodeType.SECTION, ["personal"],
     "Everything owned by the owner's private life: personal facts and personal organization."),
    ("personal-facts", "personal", "Personal Facts", NodeType.SECTION, ["personal", "facts"],
     "Durable facts about the owner's private life: health, home, finances, routines, history."),
    ("personal-org", "personal", "Personal Organization", NodeType.SECTION, ["personal", "org"],
     "Ongoing personal organization: recurring commitments, plans, lists, and life admin. "
     "(Ephemeral day-to-day scratch — like today's itinerary — belongs in an agent scratchpad, "
     "not here; promote only what should persist.)"),
    ("social", "root", "Social Context", NodeType.SECTION, ["social", "people"],
     "Canonical home of PEOPLE and relationships. Every person node is owned here exactly once; "
     "other sections (e.g. Team) reference people via mounts or secondary edges, never copies."),
    ("ideas", "root", "Ideas", NodeType.SECTION, ["ideas"],
     "Owner's ideas, brainstorms, and explorations — each idea a node, linked by secondary edges "
     "to whatever inspired it or wherever it may apply."),
]


def deploy_structure(graph, mode: str = "free") -> list[str]:
    """Deploy `mode` ('free' | 'opinionated') onto `graph`. Returns the ids created (idempotent)."""
    graph.ensure_root()
    if mode == "free":
        return []
    if mode != "opinionated":
        raise ValueError(f"unknown structure mode: {mode!r}")
    created: list[str] = []
    for node_id, parent, title, ntype, tags, description in OPINIONATED_STRUCTURE:
        if graph.store.get_node(node_id) is not None:
            continue
        graph.add_node(title, type=ntype, body=description, parent_id=parent, tags=tags,
                       node_id=node_id)   # fixed id → deterministically addressable section
        created.append(node_id)
    return created
