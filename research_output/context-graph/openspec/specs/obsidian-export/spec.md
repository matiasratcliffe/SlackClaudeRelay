# obsidian-export Specification

## Purpose
Export the graph to an Obsidian-compatible vault so a human can browse what agents have built, using
Obsidian's native folders, wikilinks, and graph view.

## Requirements

### Requirement: One markdown file per node
The system SHALL export each node as a markdown file located by its primary-tree folder path, with
YAML frontmatter for properties (`id`, `type`, `tags`, `owner`, `version`, timestamps) and the
`body` as content; the raw embedding is omitted (referenced by id if needed).

#### Scenario: Folder mirrors the tree
- **WHEN** a node under `work/project-x` is exported
- **THEN** its file is written at `work/project-x/<node>.md`.

### Requirement: Secondary edges as wikilinks
The system SHALL render each secondary edge as a `[[Target]]` wikilink in the source node's body,
annotated with the verb tag (e.g. `[[Jane Doe]] (mentors)`), so Obsidian's backlink and graph views
surface the relationship.

#### Scenario: Edge becomes an annotated wikilink
- **WHEN** a node has a `mentors` edge to another node
- **THEN** its exported file contains `[[Target]] (mentors)`.
