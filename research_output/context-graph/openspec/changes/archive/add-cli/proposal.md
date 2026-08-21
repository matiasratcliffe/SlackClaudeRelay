# Change: add-cli

## Why
A terminal surface makes the tool usable and demonstrable with zero setup.

## What changes
Add an argparse CLI (`init`, `add-node`, `link`, `search`, `traverse`, `export`, `lock-status`,
`demo`) plus a seeded sample graph, defaulting to the in-memory store + offline embeddings.

## Impact
- New capability: `cli`.
- New code: `cli.py`, `sample.py`.
