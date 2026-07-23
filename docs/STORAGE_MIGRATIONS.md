# Storage schema migrations

Termia stores connections, settings, statistics, and connection history in
separate local files. Each format now carries schema version `1` where the
format is an object or event payload.

## Compatibility policy

- Unversioned files are treated as schema `0` and are migrated to schema `1`
  when loaded and subsequently saved.
- The oldest supported format is the unversioned legacy format shipped before
  schema versioning was introduced.
- Schema migrations must preserve user data and remain in the code while that
  legacy format is supported.
- Removing a migration requires a documented support-policy change and a
  major release or explicit user-data migration plan.
- Files with a schema newer than the application understand are rejected and
  backed up through the existing recovery path; Termia must not silently
  discard fields from a future format.

## Current schemas

- `connections.json`: object schema `1`; embedded legacy settings and
  statistics are extracted into their dedicated files.
- `settings.json`: object schema `1`; legacy terminal palette and color values
  are normalized by a named migration.
- `statistics.json`: object schema `1`.
- `history.jsonl`: each event uses schema `1`; unversioned events remain
  readable and receive the current version when rewritten.
