# Design — add-graph-model

- `Node` and `SecondaryEdge` as frozen-ish dataclasses; ids are short uuid4 hex.
- `NodeType` enum includes `root`, `person`, `project`, `fact`, `note`, `skill` (skill = the
  guidance/behaviour split; distinct from pure context).
- Validation lives in pure functions (`validate_new_node`, `would_create_cycle`) so both backends
  reuse them; cycle check walks `parent_id` ancestors.
- Embedding is `list[float] | None` (computed at ingest, not model construction).
- Edge validity: `valid_from`/`valid_to` (None = open); `version` starts at 1 for CAS.
- No storage concern here — model is backend-agnostic data + invariants only.
