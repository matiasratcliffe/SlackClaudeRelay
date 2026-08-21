# Change: add-traversal-assembly

## Why
Agents need bounded, cheap retrieval from seeds without an LLM deciding stopping hop-by-hop.

## What changes
Add a mechanical layer (spreading activation + Personalized PageRank) that yields a bounded
candidate subgraph, plus budgeted ranking/assembly into a rendered context blob with an explainable
path.

## Impact
- New capability: `traversal-assembly`.
- New code: `traversal.py`, `assembly.py`.
