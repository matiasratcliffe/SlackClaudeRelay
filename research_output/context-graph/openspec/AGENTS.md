# AGENTS.md — how to use OpenSpec in this repo

This repo practices **spec-driven development** with an OpenSpec + Kiro hybrid. Read this before
changing specs or code.

## Layout
- `openspec/project.md` — project context (stack, conventions).
- `openspec/specs/<capability>/spec.md` — **current-state truth**: what each capability does *today*.
  Requirements use `#### Scenario:` blocks with WHEN/THEN.
- `openspec/changes/<change-id>/` — an in-flight **change = a story**:
  - `proposal.md` — why, what changes, impact.
  - `requirements.md` — **Kiro-style** per-story requirements in **EARS** notation + acceptance
    criteria.
  - `design.md` — technical design/decisions for the story.
  - `tasks.md` — ordered implementation checklist.
  - `specs/<capability>/spec.md` — the **delta** (`## ADDED / MODIFIED / REMOVED Requirements`).
- `openspec/changes/archive/` — completed changes (deltas already folded into `specs/`).

## Workflow (per story)
1. **Propose:** create `changes/<id>/` with proposal + Kiro requirements + design + tasks + delta.
2. **Grill:** self-interrogate requirements and design for genuine ambiguities (autonomous mode —
   no human gate); tighten. Do not manufacture nitpicks.
3. **Implement:** work `tasks.md` top-to-bottom; keep code clean.
4. **Archive:** fold the delta into `openspec/specs/`, move the change to `archive/`.

## Why hybrid
OpenSpec `specs/` give durable, deduplicated **capability truth**; Kiro per-story specs give
**intent + acceptance** for each unit of work. Keeping both means current-state and
per-story-history are each first-class.
