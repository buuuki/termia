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

### Retron appearance profile

`CONFIG_DIR/themes/retron.json` is a separate schema-2 document containing
`current`, `presets` and `active_name`. Each appearance retains the schema-1
`theme`, `accent`, `common` and `components` structure. The collection stores up
to 32 named configurations and the active appearance in one atomic write, within
a 2 MiB file limit. Names are NFC-normalized, 1–64 characters, unique ignoring
case, and contain no control characters; they are data, never filenames.
`active_name` is null for an unnamed appearance or names a matching saved preset.
The file respects `TERMIA_CONFIG_DIR`. Appearance values remain validated colors,
bounded numbers, enumerated states/styles and up to three shadows per state.
CSS, selectors, URLs and resources are not accepted; no import/export UI exists.
Existing settings and their schema do not change.

Legacy schema-1 files retain their 64 KiB limit and load as the current unnamed
appearance without writing. Explicit Save, Save as, Rename or Delete writes
schema 2, preserving the current appearance and the remaining configurations.
Back up this file before downgrading to a single-profile checkout: that reader
rejects schema 2 and disables saving rather than overwriting it. Earlier versions
without a Retron editor ignore the file. Standard application themes remain usable.

Missing profiles inherit the existing `app.dark_glow_border_color` in memory.
Loading never writes. Save writes a private temporary file, flushes it and
atomically replaces the profile under the existing instance write guard.
Read-only/locked instances may preview but cannot save. Invalid, oversized,
unknown-field and future-version files remain untouched; saving is disabled
until the incompatible file is recovered outside the running instance.
External file changes also prevent overwriting. Retain a copy before recovery.
Unknown schema versions are protected from overwriting.

Save updates the active configuration; Save as adds a unique name and keeps the
editor open. Both persist the selected appearance and establish the cancellation
baseline. Rename and confirmed Delete persist collection changes immediately,
without saving pending appearance edits. Deleting the active name retains its
appearance as unnamed. Preview, selection and Apply are temporary until saved;
Cancel, Escape, close and shutdown revert to the opening or last-saved appearance.
Switching away from an edited draft requires Save, Discard or Cancel. Cancel does
not undo saved names or deletions. Restore defaults changes the draft to the
immutable original Retron preset, without resetting Terminal/Notes settings or other themes.
An explicit Retron content background overrides those settings only while active.

### Resource limits and recovery

Connection imports from the menu request the imported file's password when
needed. That password is used only to read the file; the target profile keeps
its current protection mode and master password. Cancelling or entering an
incorrect password leaves current data intact. The file is validated again
when the password is submitted, including its resource budgets; a rejected
import does not put an otherwise healthy current profile into read-only mode.

Connection and notes readers accept files up to 48 MiB, decoded UTF-8 JSON up
to 32 MiB, and PBKDF2 iteration counts from 100,000 to 2,000,000. Writers keep
the existing 390,000 iterations and reject output exceeding the size budgets
before replacing the destination. These limits do not change the schema.
They apply to plain, obfuscated and encrypted storage and their imports.
Compressed data must contain exactly one complete stream.

If an existing connection or notes file exceeds a limit, Termia preserves its
original bytes and does not rename it as corrupt. Editing remains disabled for
that application instance, including after another load or password attempt.
Imports exceeding a limit are rejected before replacing the current data.

To recover, close Termia, make an offline backup of both `connections.json`
and `notes.json` in the active profile, and restore a known compatible backup.
For legitimate large files, obtain assistance to reduce or convert a copy
offline within these limits; do not delete records or edit encrypted envelopes
in place. Restart Termia after recovery. Do not upload files containing
credentials or private notes. Isolated test instances use their own profile.

### Schema inventory

- `connections.json`: object schema `4`; embedded legacy settings and
  statistics are extracted into their dedicated files, schema `2` adds
  locally stored command snippets and persistent snippet categories, and
  schema `3` adds an optional per-server startup command. Existing server
  profiles receive an empty command when migrated; empty categories remain
  stored explicitly. Schema `4` adds an optional local-terminal profile password;
  older profiles receive an empty password. Passwords follow the connection
  storage protection mode and are included in connection exports and clones.
  Before first launch with schema 4 support, close Termia and make an offline
  backup of connections.json. Writable startup migrates and saves older schemas;
  read-only loading does not rewrite them. Previous Termia versions cannot read
  schema 4. Restore the pre-upgrade backup before downgrading, keeping a separate
  protected copy of newer data. Do not open a schema 4 file with an older client.
- `settings.json`: object schema `1`; optional `app.connection_sidebar_width`
  and `app.notes_sidebar_width` remember sidebar widths in logical pixels,
  defaulting to 280. Nonnegative integers are retained without a fixed minimum;
  invalid values use the default. Loading does not write.
  Connections window constraints do not replace the preferred width;
  writable instances save an adjusted preference when hiding the sidebar or
  shutting down. Notes saves its current width when hiding the list, closing
  its window or shutting down; read-only or locked instances do not write it.
  Older clients ignore unsupported fields and discard them when saving.
  These additive settings require no schema bump.
  Legacy terminal palette and color values
  are normalized by a named migration.
  The local Retron research theme adds the `dark_glow` value to the existing
  `app.theme` string without a schema change. Choose System/Light/Dark before
  opening that profile in an older client, which does not recognize the new
  value and may replace it on save.
  Retron is the display name; the stored `dark_glow` identifier, CSS class and
  existing `dark_glow_border_color` preference retain their compatibility names.
  The rename requires no migration and preserves all per-theme colors.
  Optional `app.terminal_colors_by_theme` maps System/Light/Dark/Retron to
  foreground/background pairs. Older settings seed the three standard themes
  from their existing terminal colors; Retron initially uses Solarized text
  on the sidebar surface (`#839496` on `#182231`). Existing saved pairs,
  including a previous Solarized background, remain unchanged.
  Loading selects the current theme's pair in memory;
  the next normal writable save persists the map. Read-only loading never
  writes or backs up settings solely to initialize these pairs. Invalid entries
  fall back per theme without discarding other valid pairs. Font, size, ANSI
  palette and prompt remain shared settings. Explicit theme color profiles
  bypass the old Solarized-default/font heuristic, retaining chosen fonts.
  The legacy `terminal.foreground` and `terminal.background` fields retain the
  active pair for compatibility. No schema bump is required; older clients
  ignore the optional app field and discard it on saving. Back up settings
  before downgrading to preserve all per-theme customizations.
  Optional `app.copy_on_selection` defaults to `true` for new profiles and
  older settings without this field. An explicitly saved `false` remains
  disabled; invalid non-boolean values remain disabled. Loading the new
  default does not rewrite settings. It adds no schema migration and is separate from connection
  exports. Older clients can read settings but discard this field when saving;
  check the preference after downgrading and upgrading again.
  Optional `app.dark_glow_border_color` defaults to `#55BAC9`. It accepts an
  opaque six-digit hex color; missing or malformed values fall back to the
  default without discarding the remaining settings. The Retron editor seeds
  its independent profile from this legacy preference; General links to the
  editor instead of maintaining a second border-color control.
  Other themes ignore it; unrelated preference saves preserve it. It adds no
  schema change and is separate from terminal colors and semantic status roles.
  Older clients ignore this app field and discard it on saving, so retain a
  settings backup before downgrading if the custom color must be preserved.
  Optional `app.split_focus_shortcuts_version` defaults to `1` in new profiles.
  Old profiles without the marker migrate only legacy `Ctrl+Arrow` split-focus
  assignments to `Ctrl+Shift+Arrow`. Custom and disabled assignments survive;
  an occupied destination leaves an existing assignment unchanged, or disables
  a missing split-focus assignment rather than creating a conflict. The marker
  is saved with preferences so later deliberate `Ctrl+Arrow` choices survive
  restarts. Read-only loading never writes this migration. The object schema
  is unchanged; older versions may discard the marker on save, so retain a
  settings backup before downgrading and check shortcuts after upgrading again.
  Optional `app.keybindings` entries named `snippet:<id>` assign shortcuts to
  stable snippet IDs. This extends the existing action dictionary without
  changing object fields or the schema version. Old settings have no snippet
  assignments; this snippet extension does not change ordinary action defaults.
  These local settings
  are separate from connection exports. Older versions can still read the
  file but may discard snippet action keys when normalizing/saving settings;
  retain a settings backup before downgrading if these assignments are needed.
  Duplicate snippets receive new IDs and no assignment. Removing a snippet or
  its scope target prunes its assignment on the next connection save. Shortcut
  edits reject conflicts and stale concurrent changes before modifying data.
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
