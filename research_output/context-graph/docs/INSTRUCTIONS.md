# Operating Instructions (agent contract)

This document records the **operating constraints** the owner set for building this project.
It is the meta-contract for the autonomous agent doing the work — not part of the product.
The product plan lives in [PLANNING.md](PLANNING.md); the wishlist in [BACKLOG.md](BACKLOG.md).

## Budget / stopping condition

- **No dollar cap.** Work continues until a **hard token/usage limit** is reached — either the
  **Fable model's usage limit** or the **session token budget** — or until the scoped work is
  reasonably complete (core build + one bounded improvement round; do not spin inventing features).
- Token usage is tracked in [COST-LEDGER.md](COST-LEDGER.md) as a running note.

## Stop-and-report protocol

On hitting a token/usage limit (or finishing the scoped work), use the **`slack-notification`** skill
(`slack-notify "<message>"`) to DM the owner with:
1. **Which** limit stopped the work (Fable usage limit vs session token limit) — or that the scope
   completed under the limits — and **how much** was used (the numbers).
2. A short paragraph: **how far the work got**, and **what % of the total intended scope** was
   completed (honest estimate).
Then halt and await the owner's decision on continuing.

## Token efficiency

**Token efficiency is the top priority.** Prefer dense, high-signal output; avoid redundant
re-reading, verbose narration, and repeated context loads. Delegate bulk reads to cheaper
sub-agents where it keeps the main context lean.

## Process rules

- **SDD (spec-driven development).** Follow the `implement-backlog-item` skill's discipline:
  review → clarify/grill → plan → critique/grill → implement → verify, per story. In this project
  the grills are **self-answered autonomously** (no human gate), raising only genuine ambiguities —
  no manufactured nitpicks.
- **Spec tooling = OpenSpec + Kiro hybrid.** OpenSpec holds the *current-state* capability specs
  (living truth) under `openspec/specs/`; each change proposal under `openspec/changes/` also carries
  **Kiro-style per-story specs** (EARS `requirements.md`, `design.md`, `tasks.md`). Best of both:
  durable capability truth **and** per-story intent.
- **No external trackers.** No Azure DevOps, no Jira, no PRs. All backlog/stories/specs are
  **internal files** in this repo.
- **The only outside tools** are internet searches (for research) and **git** (inside this repo).
- **Version control.** This project lives inside the existing `slack-agent` git repo. **Commit
  directly to `main`** (no PRs, no feature branches required). Conventional-commit messages, no AI
  attribution.
- **Clean code.** Apply the `clean-code` standard: minimal moving parts, slim contract-only
  docstrings, one-line justifications for non-obvious decisions, no verbosity slop.

## Scope guardrails

- **In scope:** the context long-term-memory **knowledge-graph tool** (see BACKLOG/PLANNING).
- **Iteration:** after the first build, iterate to propose → grill → improve features *within the
  KG-tool scope only*. "Cool stuff that makes sense" — do **not** go wild or scope-creep.
- **Out of scope (describe only, never implement):** the future **"pi" super-agent** that would
  consume this graph (progressive skill disclosure, scratchpad short-term memory, the "ring-a-bell"
  interrupt system, model-skill-interpretation benchmark). PLANNING.md describes intent at a high
  level; no code for it now or in the improvement loop.
- **Do not run or test anything** for this phase — write and grill backlog, specs, docs, and code
  only. (Runnability is a design goal of the code, but execution/verification is deferred.)
