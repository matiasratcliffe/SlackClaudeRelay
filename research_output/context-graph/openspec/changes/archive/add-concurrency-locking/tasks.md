# Tasks — add-concurrency-locking

- [x] Lock modes + compatibility matrix.
- [x] `acquire_write` (root→leaf IX + X), re-entrancy, `LockConflict`.
- [x] Shared read locks; `release`/`release_all`; lease `sweep`.
- [x] CAS `retry` helper for secondary-edge updates.
- [x] Fold requirements into `specs/concurrency-locking/spec.md`.
