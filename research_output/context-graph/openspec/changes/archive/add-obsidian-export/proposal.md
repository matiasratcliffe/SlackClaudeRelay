# Change: add-obsidian-export

## Why
Humans need to eyeball what agents have built; Obsidian renders folders + wikilinks natively.

## What changes
Add a vault exporter: one markdown file per node under its tree folder path, YAML frontmatter, and
secondary edges as verb-annotated wikilinks.

## Impact
- New capability: `obsidian-export`.
- New code: `export_obsidian.py`.
