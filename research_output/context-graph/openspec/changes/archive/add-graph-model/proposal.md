# Change: add-graph-model

## Why
Everything else depends on a precise model: an ownership tree plus first-class secondary edges.

## What changes
Introduce `Node`, `SecondaryEdge`, id/typing, and tree-invariant validation (single-parent,
single-root, acyclic). Meaning lives on secondary edges; the tree is ownership/lock-scope only.

## Impact
- New capability: `graph-model`.
- New code: `src/context_graph/model.py`.
- Spec delta: introduces all requirements in `specs/graph-model/spec.md`.
