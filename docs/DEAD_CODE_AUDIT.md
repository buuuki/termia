# Dead-code cleanup audit

Original tracking issue: #367. The audit baseline is commit `b6212bc`, after the standard
GTK migrations. This record covers the approved cleanup batches; the wider
audit is not blanket approval to remove every suspected legacy implementation.

## Verification method

Search production code, tests, scripts and packaging metadata for identifier
references and string-based consumers. Follow GTK signal connections, factories,
Gio actions and menu models, deferred callbacks, dynamic attribute access,
resource loading and serialization. Before removal, actively search for a
counterexample that would prove the candidate is still used.

The conclusions below apply to in-repository consumers. Accidental reexports
are not a supported external plugin API. File locations refer to the baseline;
line numbers change as cleanup progresses.

## Follow-up #437: initial cleanup

The follow-up baseline is `a1085e9` on `0.6.1-dev`. Only the following two
removals are included in this first approved batch; other audit candidates
require separate proposals and approval.

| File | Removed element | Evidence and retained behavior |
| --- | --- | --- |
| `src/termia/notes_store.py` | `NotesFileStore.detect_storage_mode` | Only its definition remained; no caller, signal, action, or string/dynamic consumer was found in the repository. `load` retains its active format detection, and loading, saving, encryption, backups and migration behavior remain unchanged. |
| `src/termia/sidebar.py` | `self.sidebar_projection` assignment | The attribute was written once and never read, including through dynamic access. The local `projection`, its construction and the native GTK tree remain unchanged. Remove the stale attribute from `WINDOW_MIXIN_CONTRACTS.md`; retain the projection module and its data. |

These are internal elements, not a public plugin contract. Confidence is high
for the absence of in-repository consumers. There is no intended UI, data-format,
Core/add-on boundary or version metadata change. In particular, this batch does
not remove the flat-row calculations, resources, translation keys, snippet
controls or updater fields identified as other candidates.

Compare normalized ASTs against this baseline to verify only the approved
method and assignment were removed. Existing behavior tests cover Notes
storage, encryption and recovery, and sidebar search, expansion, selection and
menus; do not add tests merely asserting the absence of these internal names.
Run the full standard checks once stable. The focused check is:

```bash
python3 scripts/run_sandbox_tests.py tests.test_notes tests.test_sidebar_navigation tests.test_sidebar_projection tests.test_sidebar_menus
```

For the isolated manual check, run `./scripts/run_test_instance.sh --fresh`.
Create and save a note, close and reopen Notes, and verify its content remains.
Create synthetic connection groups, expand/collapse them, filter the sidebar,
and verify keyboard selection after clearing the search. No SSH connection,
container or VM execution is needed for this batch.

Automated validation for this follow-up passed: 185 focused tests and the full
793-test private sandbox suite, Python compilation, setup-script syntax,
translation synchronization (615 messages), and whitespace checks. Normalized
AST comparison confirms exactly the two approved removals and unchanged retained
code. Ruff remains at 54 findings and Bandit at 157, with no new findings or
blocking cases; existing reviewed findings remain visible. GTK/VTE deprecation
and GLib source-ID warnings were observed without test failures. The requester
confirmed the isolated manual checks for this batch before publication.

## Original audit #367

The batches below retain their original baseline, validation evidence and
requester decisions.

## Batch A: confirmed removals

| File | Removed element | Evidence and retained behavior |
| --- | --- | --- |
| `src/termia/notes_dialogs.py` | `build_notes_context_menu` | Only its definition remained. Current context-menu builders use `Gtk.PopoverMenu` and `Gio.Menu`; no signal, action, factory or dynamic-name consumer was found. |
| `src/termia/notes_dialogs.py` | `notes_list_scroller` assignment | The attribute was written once and never read, including through dynamic access. The local scroller and its placement in the window remain. |
| `src/termia/notes_presenter.py` | `NotesPresenter.categories` | No caller of this flat category-count method remained. Notes uses `tree`; calls to `presenter.categories()` resolve to the separate `SnippetPresenter`. |
| `src/termia/stores.py` | `update_prompt_settings` | Only its definition remained. The combined Terminal/Prompt preferences save through `update_terminal_settings`, including prompt values. |
| `src/termia/terminal_sessions.py` | `on_request_disconnect_session` | No registration or caller remained. Root and split disconnect buttons and terminal menu dispatch use `on_request_disconnect_pane`. Active `disconnect_session`, pane cleanup and tab lifecycle callbacks remain. |
| `src/termia/terminal_processes.py` | `signal` import | No reads or in-repository consumers of the imported binding. Process ownership and termination behavior are unchanged. |
| `src/termia/notes_io.py` | `datetime` import | No reads or dynamic consumers. Notes serialization and timestamps retain their active implementations. |
| `src/termia/app.py` | `FileTransferController` import | No use of this binding in the composition root. The active controller construction remains in `terminal_sessions.py`. |
| `src/termia/preferences.py` | `KeybindingCaptureRow` import | The module composes mixins only. Active callers import the control directly from `keybinding_preferences.py`. |
| `tests/test_server_group_move.py` | `Group`, `Server` imports | Neither imported binding was read. The tests create their entities through the store. |
| `tests/test_sidebar_navigation.py` | `Gio` import | No use of the imported binding. Navigation coverage is unchanged. |
| `src/termia/styles.py` | `.termia-menu-separator`, `.termia-tab-overflow-item` | Neither class is assigned by production code, including dynamic construction. Current menu separators and overflow rows are GTK-owned. |

Confidence is high for these removals after the counterexample search. The
unregistered disconnect handler needs particular care because nearby active
session and pane methods manage process cleanup. No data format, migration,
action contract or Core/add-on boundary changes are intended.

## Batch B: obsolete menu helpers

After batch A, a second reference search found only the definitions and their
three direct tests for the following helpers. No signal, action, factory or
dynamic-name consumers were found. This batch was approved separately.

| File | Removed element | Retained production path and coverage |
| --- | --- | --- |
| `src/termia/notes_dialogs.py` | `style_notes_menu`, `append_notes_context_menu_item` | The three native context-menu builders retain their styling, action groups and lifetime guards. `NoteTabContextMenuTests`, `CategoryContextMenuTests` and `NoteListContextMenuTests` retain native-menu dispatch, permission and popup-lifetime coverage. |
| `src/termia/tabs.py` | `on_tab_overflow_item_clicked` | `rebuild_tab_overflow_popover` registers the active `tab-overflow.select` action. `NativeOverflowMenuTests` covers selection, ordering, long titles and stale targets. |

Remove only the corresponding tests
`test_note_context_menu_rows_use_gtk_selection_states`,
`test_notes_context_surfaces_reuse_main_menu_style`, and
`test_overflow_item_activates_selected_session_after_closing_popover`.
They directly exercised abandoned implementations rather than current menu
paths. The shared `FakePopover` test helper still has other consumers and stays.

This completes the legacy chain from `build_notes_context_menu` removed in
batch A to `style_notes_menu`. The independently test-only custom row helper
and old overflow callback are also retired. Confidence is high and runtime
risk is low; native controls, signal connections and actions remain unchanged.

## Batch C: legacy Notes list renderer

The requester accepted batch B manual checks and approved retiring the old
`Gtk.ListBox` path separately. `ensure_window` always builds the native tree;
only tests and the fallback in `refresh_list` reached the old renderer.

Removed chain in `src/termia/notes_dialogs.py`:

```text
refresh_list fallback
  -> _refresh_list_rows
     -> append_note_draft_row
     -> append_note_row -> on_note_context_pressed -> iter_note_rows
     -> append_note_tree_header
     -> append_note_category_header
```

`refresh_list` now refreshes the native model only. Deselection retains its
pre-initialization guard and otherwise uses `Gtk.SingleSelection`. The
`.termia-note-category.drop-target` rule in `styles.py` was assigned only by
the removed builders, so it was retired with them. Native drag controllers and
their GTK feedback are unchanged.

Shared selection, activation, scope, category and private-drag handlers remain.
Their stale list-box type annotations now describe native nodes and widgets.
The native renderer, model factory and deferred right-click handler retain
their implementation; no Core/add-on or storage contract is changed.

`tests/test_notes.py` now checks hierarchy depth, search expansion/restoration,
draft placement, private category drag formats, named-category context controls,
empty-list editor preservation and no automatic selection against native models
or bound rows. The context-menu fixture now uses `Gtk.ListView`, the production
factory and deferred right-click entry point, retaining permission, stale-target,
save, rebuild, anchoring and popup-lifetime coverage. A simulated rebuild restores
selection just as the native refresh does. Test windows own the factory lifecycle;
format checks read the GObject `formats` property to avoid boxed-format lifetime
errors encountered when inspecting the getter during fixture cleanup.

## Batch D: redundant dialog argument and test-only helpers

The requester accepted batch C manual checks and approved this batch separately.

| File(s) | Removed element | Evidence and retained coverage |
| --- | --- | --- |
| `dialog_actions.py`, `main_menu.py` and their callers | `last` keyword-only argument | The shared helper never read the argument. Remove it from both signatures and all 22 keyword arguments across 12 caller files, including the wrapper forwarding and a security test fixture. Button creation order, default responses and shared spacing/insets remain unchanged. |
| `src/termia/notes.py` | `note_matches_query` | Only two assertions in a domain test used it. Search runs through `NotesPresenter.items`; its existing test now verifies content matching, whitespace/case normalization and no matches. Domain validation and timestamp assertions remain. |
| `src/termia/known_hosts.py` | `parse_scanned_host_key` | Only tests used this first-result wrapper. Production scanning already calls `parse_scanned_host_keys`. Existing tests now check list cardinality, fingerprint calculation, non-default-port host formatting and invalid input directly through the plural parser. |

All dialog callers were checked together, including SCP, SFTP, Statistics,
Notes, history, updates, optional tools and preferences. No new Core/add-on
dependency or capability was introduced; injected callbacks retain their actual
button-construction behavior. No host connection or installation is part of
validation. Shared helpers, parsers, persistence and migration logic remain.

An AST comparison against the pre-batch working tree confirms that affected
production modules differ only by the approved argument/signature removals and
the two unused helper deletions. AST searches find no remaining `last` keyword
arguments or keyword-only parameters in production or tests. The unrelated
uses of the word "last" remain.

## Batch E: write-only timer identifiers

The requester accepted batch D manual checks and approved this cleanup subject
to confirming that the timer IDs have no consumers. A repeated reference and
AST search found exactly two declarations in `ui_state.py` and four attribute
writes in `terminal_sessions.py`, with no reads, keyword arguments, string-based
accesses or workspace/session serialization consumers. Production constructors
use keywords; the two positional test constructors stop before optional fields.

Remove `TerminalPane.timeout_id` and `TerminalSession.timeout_id`. Replace the
four assignments with the same `GLib.timeout_add_seconds` expressions, keeping
their original position, interval, callback and arguments. The two local/SSH
session timers and the two local/SSH split timers still run. Their callbacks
continue returning `GLib.SOURCE_REMOVE` for disconnected or removed panes, and
`GLib.SOURCE_CONTINUE` while active; process cleanup and other source IDs remain.

Normalized AST comparison against the pre-batch working tree must show only
these two field deletions and four assignment-to-expression changes. Statistics
continues reading its existing timing/process fields and retaining its own
independent flush timer. `SessionObserver` is retained as the documented
Core/Statistics contract. No stored format or version metadata changes.

## Retained by requester decision

Keep `src/termia/assets/termia-about-256.png`. The requester explicitly excluded
this resource from cleanup after discussing its apparent lack of runtime use.

## Deferred candidates

- **Dynamic or architectural candidates:** translation keys,
  callback parameters, session/pane state duplication and `SessionObserver`
  require separate evidence and scope approval.

Preserve supported storage migrations, GTK virtual methods, Paramiko policies,
updater redirect callbacks, schema fields, runtime resources and disabled-add-on
behavior. Their lack of direct call sites is not evidence of obsolescence.

## Validation

Use the existing Notes, styling, preferences, sidebar, tab and terminal lifecycle
coverage; no tests asserting the absence of implementation details are needed.
Run the sandbox suite and the standard syntax, shell and translation checks
from [Regression Checks](REGRESSION_CHECKS.md#automated-checks).

Batch A automated validation passed:

- `python3 scripts/run_sandbox_tests.py`: 636 tests passed in the private
  display/session-bus environment. GTK/VTE deprecation warnings and GLib
  source-ID warnings were emitted without test failures.
- `python3 -m py_compile run_termia.py scripts/compile_translations.py scripts/run_sandbox_tests.py src/termia/*.py tests/*.py`.
- `bash -n scripts/termia-setup.sh`.
- `scripts/compile_translations.py --check`: 569 messages synchronized.
- `git diff --check` and a comparison of method definitions against the
  baseline: only the four approved methods were removed.

Batch A manual checks were accepted by the requester before starting batch B.
Batch B automated validation passed:

- `python3 scripts/run_sandbox_tests.py tests.test_notes tests.test_tabs`:
  177 tests passed, including native menu dispatch and notebook integration.
- `python3 -m py_compile src/termia/notes_dialogs.py src/termia/tabs.py tests/test_notes.py tests/test_tabs.py`.
- Reference searches found no remaining consumers of the three removed helpers
  in production code, tests or scripts. An AST comparison against the baseline,
  accounting for batch A, confirmed that retained methods are unchanged.
- `git diff --check` passed. The complete suite result above belongs to batch A;
  only the affected modules were rerun for batch B.

Batch B manual checks were accepted by the requester before starting batch C.
Batch C automated validation passed:

- `python3 scripts/run_sandbox_tests.py tests.test_notes`: 142 tests passed.
- `python3 scripts/run_sandbox_tests.py`: 633 tests passed on the stable
  implementation, including native GTK, terminal lifecycle and optional tools.
  The count differs from batch A only by the three obsolete tests removed in
  batch B; batch C adapts existing behavior checks rather than deleting them.
- `python3 -m py_compile src/termia/notes_dialogs.py src/termia/styles.py tests/test_notes.py`.
- `git diff --check` passed. An AST comparison confirms that the 349 method
  lines of the legacy renderer were removed while retained native renderer,
  factory, deferred context-menu and shared-handler bodies are unchanged.
- Shell and translation files were unchanged by batches B/C; their successful
  batch A checks remain applicable.

Batch C manual checks were accepted by the requester before starting batch D.
Batch D automated validation passed:

- `python3 scripts/run_sandbox_tests.py`: 633 tests passed, with the updated
  Notes search and host-key assertions and existing dialog, SCP/SFTP,
  Statistics, preference and update coverage. GTK/VTE deprecation and GLib
  source-ID warnings remain observations, not test failures.
- Syntax checks passed for every Python file touched in this batch.
- Normalized AST hashes against the pre-batch working tree confirm that
  production changes are limited to the approved removals. Search and AST
  checks find no remaining helper consumers or `last` keyword arguments.
- `git diff --check` passed; shell and translation files remain unchanged.

Batch D manual checks were accepted by the requester before starting batch E.
Batch E automated validation passed:

- `python3 scripts/run_sandbox_tests.py`: 633 tests passed, including terminal
  lifecycle, split panes, workspace/session restoration and optional tools.
- `python3 -m py_compile src/termia/ui_state.py src/termia/terminal_sessions.py`.
- Normalized AST hashes match exactly the expected two field deletions and
  four assignment-to-expression changes; timer calls and callbacks are intact.
- `git diff --check` passed. No `timeout_id` consumers remain in production,
  tests or scripts. No previous versioned text documentation mentioned that
  attribute; its current documentation is this cleanup record.

Batch E manual checks were accepted by the requester after the complete suite
passed. All five approved batches have completed automated and requester-led
manual validation. The following command reproduces the isolated launch:

```bash
scripts/run_test_instance.sh --fresh
```

Open a local terminal and a local split, showing their status bars if hidden.
Wait a few seconds and check that both elapsed-time labels advance. Close a
split and the tab, and check that Termia remains responsive. If testing saved
workspaces, reopen a local-only workspace and check its timers. Synthetic tests
exercise the SSH paths without connecting to inventory hosts.

No version metadata change is needed for this maintenance batch; it belongs
to the active `0.6.0-beta.4` development line.
