# Requirements (EARS) — add-traversal-assembly

## User story
As an agent, I need just-enough relevant context assembled from my query within a budget.

## Requirements
- R1. WHEN given weighted seeds, the system SHALL expand by spreading activation with per-hop decay,
  edge-weight scaling, an activation threshold, and a max-hop cap.
- R2. The system SHALL offer a Personalized-PageRank variant with similarity-weighted multi-seed
  restart.
- R3. WHILE propagating through a hub, the system SHALL normalize its contribution by out-degree.
- R4. WHEN assembling, the system SHALL rank candidates and include them up to a caller budget
  (nodes or characters).
- R5. WHEN assembly completes, the system SHALL return the subgraph, a rendered markdown blob, and
  the path (seeds/edges) that led to each node.
- R6. The mechanical layer SHALL make no LLM calls.

## Acceptance criteria
- Expansion is finite and respects threshold/hop cap.
- Over-budget queries drop lowest-ranked nodes; result records provenance path.
