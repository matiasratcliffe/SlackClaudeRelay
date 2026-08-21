# traversal-assembly Specification

## Purpose
From weighted entry seeds, produce a bounded candidate subgraph by mechanical propagation, then
assemble a budgeted, rendered context blob — without an LLM deciding stopping hop-by-hop.

## Requirements

### Requirement: Mechanical propagation
The system SHALL expand from seeds via spreading activation
(`activation(v) += activation(u)·decay^hop·edge_weight(u,v)`) with an activation threshold and a
hard max-hop cap, and SHALL offer a Personalized-PageRank variant with similarity-weighted
multi-seed restart.

#### Scenario: Bounded expansion
- **WHEN** propagation runs from seeds
- **THEN** it returns a finite candidate subgraph respecting the threshold and max-hop cap in one
  pass, with no LLM calls.

#### Scenario: Hub dampening
- **WHEN** activation flows through a high-degree hub
- **THEN** the hub's contribution to each neighbor is normalized by its out-degree.

### Requirement: Budgeted context assembly
The system SHALL rank the candidate subgraph and assemble a result within a caller-supplied budget
(node or character budget), returning both the selected subgraph and a rendered markdown blob, plus
the traversal path taken.

#### Scenario: Respect the budget
- **WHEN** a budget smaller than the candidate set is given
- **THEN** the highest-ranked nodes are included up to the budget and the rest are omitted.

#### Scenario: Explainable path
- **WHEN** assembly completes
- **THEN** the result records which seeds and edges led to each included node.
