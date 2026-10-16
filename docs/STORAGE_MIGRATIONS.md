# Storage schema migrations

Termia stores connections, notes, settings, statistics, and connection history
in separate local files. Each format carries an explicit schema version where
the format is an object or event payload.

## Compatibility policy

- Unversioned files are treated as schema `0` and are migrated to the current
  schema when loaded and subsequently saved.
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

- `connections.json`: object schema `3`; embedded legacy settings and
  statistics are extracted into their dedicated files, schema `2` adds
  locally stored command snippets and persistent snippet categories, and
  schema `3` adds an optional per-server startup command. Existing server
  profiles receive an empty command when migrated; empty categories remain
  stored explicitly.
- `settings.json`: object schema `1`; legacy terminal palette and color values
  are normalized by a named migration.
- `notes.json`: object schema `3`; stores notes and persistent note categories
  separately from connections. Categories carry an optional `server_id` and
  schema 3 adds an optional `parent` category name within that same scope.
  Names remain unique per scope; missing parents and cycles are rejected.
  Schema 2 categories migrate as root-level groups. Before the first save of
  an older schema, Termia backs up the original bytes as `notes.json.backup-*`,
  preserving its encryption or obfuscation. Read-only loading does not rewrite
  or back up files. Older Termia versions cannot read schema 3; restore that
  backup before downgrading, after separately exporting any newer notes.
  When a removed server's categories become personal, those incoming groups
  are flattened to avoid invalid hierarchies when names collide with personal groups.
  Schema 1 shared category names migrate to each scope that uses them; unused
  legacy categories remain personal. The notes file follows the connection storage
  protection mode; importing a notes export replaces the file only after
  validation and, when existing notes are present, a backup.
- `statistics.json`: object schema `1`.
- `connections-history.jsonl`: each event uses schema `1`; unversioned events remain
  readable and receive the current version when rewritten.
