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

## Follow-up #449: obsolete translation keys

Baseline: `5f6fb6b`. Remove 23 keys without current production consumers:

- Updater: `update_copy_log`, `update_debian_dependencies`, `update_manual`,
  `update_manual_steps`, `update_copy_commands`.
- Preferences: `prompt`, `preferences`, `configuration`, `debug_mode_enabled`,
  `debug_mode_disabled`, `restart_language`, `language_settings_saved`,
  `prompt_settings_saved`.
- Transfers: `send_files_to_server_failed_detail`,
  `send_files_to_server_fingerprint`.
- Notes: `notes_minimize_window`, `notes_maximize_window`,
  `notes_restore_window`, `notes_choose_server`, `notes_manage_categories`,
  `notes_server_group`, `notes_empty_all`.
- Snippets: `snippet_duplicate`.

Search tracked sources, tests and scripts for direct and indirect consumers,
including key variables, menu tables, exception messages and constructed keys.
Retain the active `theme_*`, `split_*` and `prompt_datetime_*` families: their
keys are constructed dynamically. Other suspected keys remain outside scope.
Ignored laboratory source snapshots are historical consumers, not the current
checkout; leave them untouched. The only remaining literal consumer of these
23 keys was the updater's negative manual-button assertion. Preserve that
English-language assertion with the original label instead of translating a
removed key, which would silently fall back to the key itself.

Remove only the corresponding POT/PO blocks and regenerate both MO files.
Catalog cardinality changes from 615 to 592 unique messages; verify every
surviving English, Spanish and Catalan value against the baseline. No controls,
stored formats, Core/add-on contracts or version metadata change. Include this
maintenance in the planned `0.6.1-beta`.

Focused validation uses the private sandbox runner with `tests.test_update_view`,
`tests.test_general_preferences`, `tests.test_terminal_preferences`,
`tests.test_notes` and `tests.test_snippet_dialogs`. Run catalog synchronization,
standard checks, the full suite and static comparison before publication.
For manual validation, run `./scripts/run_test_instance.sh --fresh`; inspect
updates, general and terminal preferences, Notes and snippets in EN/ES/CA.
Theme, split-direction and prompt date/time labels must remain translated,
without raw key names or empty labels. No real SSH or update installation is
needed. These checks cannot prove absence of every possible dynamic consumer.

Automated validation passed: 195 focused tests and all 798 private-suite tests,
with no skips; compilation, shell syntax and synchronization of 592 messages.
All surviving source messages and ES/CA compiled translations match the baseline.
Ruff passes on touched Python files; globally it retains 52 existing findings.
Bandit retains 157 findings (143 low, 14 medium), with no new/blocking findings
and all 17 reviewed entries unchanged. Coverage includes all 74 production
modules: 76.03% lines/63.59% branches; i18n has 90.00%/62.50%. Reports remain
ignored under `htmlcov/449-translations/` and logs stay local. The private runner
cleans up its display and bus. Visual validation was not confirmed; the
requester explicitly instructed publication and merge after the automated
checks. Do not record a manual pass.

## Follow-up #447: unread dependency comparison state

Baseline: `9b9377d`. Remove `DependencyPlan.added`, its calculation and the
planner's previous-requirements input. No production consumer reads the field;
adapt the existing model fixtures without changing active plan fields.
Both adapters retain parsing of previous-release metadata: invalid metadata
must still block preparation before invoking the planner. Target requirements,
checkout identity, alternatives/version checks, cancellation, runtime probes,
confirmation and installation safeguards remain unchanged. This is internal
maintenance for the planned `0.6.1-beta`, with no UI or stored-data change.

Focused validation:

```bash
python3 scripts/run_sandbox_tests.py tests.test_update_dependencies tests.test_updates tests.test_update_view tests.test_static_analysis
```

Validation passed: 71 focused updater tests, all 798 private-suite tests with
no skips, Python compilation, shell syntax, 615 synchronized translations and
whitespace checks. Ruff reports 52 existing findings and Bandit 157 (143 low,
14 medium), with no new or blocking findings; touched Python files pass Ruff.
All 17 reviewed entries remain unchanged. Global coverage includes all 74
production modules: 76.03% lines and 63.59% branches. Dependency planning has
91.41% line/86.00% branch coverage; adapters have 77.78%/67.86%. Uncovered
integration, native and privileged paths still require separate validation.
Reports are ignored under `htmlcov/447-dependency-state/`; logs remain local.
The private display and bus are cleaned up by the runner.

Manual inspection uses `./scripts/run_test_instance.sh --fresh`: open About,
check for updates, and verify the existing status and controls render correctly.
Do not install an update on the development host. This UI check cannot validate
adapter metadata rejection; the synthetic adapter tests exercise those paths.
The requester confirmed that the isolated updater window check passed.
Remaining translation, session-state and GTK migration candidates are separate.

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

## Follow-up #439: obsolete flat sidebar rows

Baseline: `2767cc8` on `0.6.1-dev`, after the first #437 cleanup. The native
connections tree reads the projection's eight index/section fields, not its
`rows` field. The only direct readers of the flat result were assertions in
`tests/test_sidebar_projection.py`.

This batch removes `SidebarProjection.rows`, `server_connection_text`, the
nested `is_expanded`, `server_row` and `collect_group_rows` helpers, and the
flat-row assembly. The builder's `expanded_groups` and
`collapse_groups_on_startup` parameters served only that assembly, so remove
them from the signature and its production/test callers as well. The unused
`group_matches_query` import in the projection module is removed; the native
tree retains its own active use of group-name matching.

Retain `SidebarRow`, all eight surviving projection fields, their filtering and
ordering, and the native GTK tree. Expansion preferences remain owned by
`SidebarMixin.get_group_expanded`, `group_expanded_state` and the native model's
existing callbacks. No controls, persistence format, Core/add-on boundary or
version metadata change is intended.

The projection tests now check the actual indexes and filtered section data.
Native model tests cover the former flat-list visibility expectations through
startup collapse, retained child expansion, default workspace/local/recent/
favorite visibility, directory-based profile search, clearing search, ordered
identities and activation. Existing native hierarchy/search/selection tests
remain. These tests replace obsolete representation assertions rather than
merely checking that a name was removed.

An in-memory comparison of the final implementation against the baseline on
36 synthetic combinations of query and expansion settings preserved all eight
active projection fields. A normalized AST comparison confirms only the
approved removals and caller adaptation. Run focused tests with:

```bash
python3 scripts/run_sandbox_tests.py tests.test_sidebar_projection tests.test_sidebar_navigation tests.test_sidebar_menus tests.test_server_group_move
```

Run the complete standard checks once stable, with production line/branch
coverage because tests change. Keep coverage reports local/ignored. For the
manual check, use `./scripts/run_test_instance.sh --fresh` and synthetic saved
connection records without connecting to them. Verify nested group collapse,
startup collapse, search expansion/restoration, section ordering and keyboard
selection. No live Docker/VM or remote-host trial is part of this batch.

Automated validation passed: 52 focused tests and the full 795-test private
sandbox suite, with no skipped tests; Python compilation, setup-script syntax,
translation synchronization (615 messages), and whitespace checks also passed.
Ruff remains at 54 findings and Bandit at 157, with no new findings or blocking
cases; 17 existing Bandit findings retain their reviewed status. No analyzer
rules or review entries changed. GTK/VTE deprecation and GLib source-ID
warnings were observed without test failures.

Coverage includes all 74 production Python modules, including the unexecuted
`__main__.py`: global line coverage is 76.04% and branch coverage is 63.61%.
`sidebar_projection.py` has 100% line and branch coverage; `sidebar.py` has
70.63% line and 58.26% branch coverage. Per-module results and missing paths
remain in the ignored `htmlcov/439-sidebar-flat-rows/` HTML/JSON reports.
Missing sidebar paths include scroll restoration and several context-action
wrappers. Coverage combines the child test process; it does not establish
complete native GTK/VTE, process-lifecycle, remote-host or enabled/disabled
add-on coverage. The requester confirmed the isolated manual check before
publication.

Other audit candidates remain outside this cleanup and require separate scope
approval.

## Follow-up #441: unread snippet category-button state

Baseline: `efc12fb` on `0.6.1-dev`, after #439 / PR #440. Remove only
`ManagerState.new_category_confirm` and `new_category_cancel`, plus their two
arguments at the single positional constructor in `build_manager()`.

A reference and AST search across 178 tracked Python files found no attribute
readers or exact string-based consumers of either field. An in-memory rehearsal
preserved the argument mapping of all 45 remaining fields. `ManagerState` is
internal UI state, not a stored configuration model or a public add-on API.

The buttons themselves remain active: `build_manager()` creates and appends
them to `new_category_box` and connects their `clicked` signals using local
variables. Keep this hierarchy, creation, signal wiring and callback behavior.
The scroller fields have test consumers and remain. No third removable state
field is established by this review.

Adapt the existing category-persistence regression to emit the actual save and
cancel button signals, including after garbage collection. Check that saving
creates the selected empty category, cancelling another name leaves categories
unchanged, both actions clear/hide the inline entry and restore the controls,
and cancelling the snippet retains the saved category in the manager.

Focused validation:

```bash
python3 scripts/run_sandbox_tests.py tests.test_snippet_dialogs tests.test_snippet_shortcuts tests.test_snippets
```

Compare the final production AST against the baseline, run the complete standard
checks and tracked-source static comparison, and measure production line/branch
coverage with local ignored reports. No analyzer rules or review entries change.

Automated validation passed: 46 focused tests and the full 795-test private
sandbox suite, with no skipped tests; Python compilation, setup-script syntax,
translation synchronization (615 messages) and whitespace checks also passed.
Ruff on the modified Python files and Bandit on the production module report no
findings. The tracked-source comparison against `efc12fb` reports no new findings
or blocking cases; all 157 existing Bandit findings, including 17 reviewed
findings, remain. The final production AST differs only by the two approved
field deletions and matching constructor arguments; button creation, parenting,
signals and callbacks remain unchanged.

Coverage includes all 74 production Python modules, including the unexecuted
`__main__.py`: global line coverage is 76.04% and branch coverage is 63.61%.
`snippet_dialogs.py` has 94.27% line and 75.97% branch coverage; the category
cancel callback is now exercised. Empty-name and category-store error paths,
several manager action/delete callbacks and the picker close callback remain
unexecuted. Per-module results and missing paths remain in the ignored
`htmlcov/441-snippet-button-state/` HTML/JSON reports. Child-process coverage
does not establish complete native GTK/VTE, lifecycle or remote-host coverage.
Existing GTK/VTE deprecation and GLib source-ID warnings occurred without test
failures.

For manual validation, run `./scripts/run_test_instance.sh --fresh`. Open the
snippet editor and save a synthetic category; cancel the unsaved snippet and
verify the empty category remains. Reopen the editor, cancel a different
category name and verify it was not saved. Check that the category controls
remain usable and the window can be closed and reopened. No snippet command,
remote host, Docker/VM workload or personal profile is needed. This maintenance
belongs to planned `0.6.1-beta`; no version metadata changes are included.
The requester confirmed the isolated manual checks before publication. Other
audit candidates remain outside this batch.

## Follow-up #443: unused manual dependency commands

Baseline: `66fcf93` on `0.6.1-dev`. Remove `DependencyPlan.manual_commands`,
its command-text assembly and the otherwise unused `shlex` import. Only tests
read this field; the current view displays dependency status and installation
output, while assisted installation uses the existing package tuple and fixed
APT helper. Adapt all positional fixtures and replace obsolete text assertions
with checks of required/missing requirements and packages.

Keep `added`, previous-version metadata reads and validation, parsing, runtime
probes, cancellation, plan-expiry checks and installation safeguards unchanged.
Removing the previous metadata chain would change failure behavior and requires
separate review. Correct the stale manual-command instructions in the regression
checklist to match the current UI; no controls or translations change.

Validate the remaining five plan fields and production AST against the baseline,
then run updater tests, the full regression checks, Ruff and Bandit. Preserve
coverage of missing/ready dependencies, alternatives, cancellation, expired
plans, helper authorization and unchanged source after installation failures.
No real package installation, Docker/VM workload or personal profile is needed.
This is planned `0.6.1-beta` maintenance without a version metadata change.

Focused command:

```bash
python3 scripts/run_sandbox_tests.py tests.test_update_dependencies tests.test_updates tests.test_update_view
```

Local validation passed: 69 focused tests and the final 796-test private sandbox
suite, with no skips; compilation, setup-script syntax, translation sync (615
messages) and whitespace checks passed. Ruff on modified Python and Bandit on
the production module report no findings. The production AST differs only by
the approved field, import, text-assembly and constructor-argument removals.
The requester approved renewing the dependency module's reviewed context.
The registry changes only that context digest; the review rationale is recorded
in `STATIC_ANALYSIS_REVIEWS.md`. All 17 finding entries and checker rules remain.
The renewed global comparison passed: Ruff 54 existing findings and Bandit 157
existing findings (143 low, 14 medium), with no new findings, 17 reviewed and
zero blocking cases. All 16 static-analysis regression tests passed after the
registry update. No production code changed after the successful full suite.

Coverage includes all 74 production Python modules: 76.03% lines and 63.59%
branches globally; `update_dependencies.py` has 91.54% line and 86.00% branch
coverage. Per-module reports and missing paths remain in ignored
`htmlcov/443-manual-commands/`. Error branches and the unexecuted `__main__.py`
remain gaps; this does not verify native or privileged installations. Existing
GTK/VTE deprecation and GLib source-ID warnings occurred without test failures.

The requester expanded #443 to include the noisy test-console diagnostic.
The launcher filters only the GTK DEBUG symbolic-mask message on stdout using
line-buffered output; stderr and all other diagnostics remain unchanged.
Process substitution preserves the application's exec/PID and exit status.
`tests.test_test_instance` checks suppression, other debug domains/messages,
warning/error levels, stderr and both successful and failed application exits
with a synthetic executable. A native GLib probe confirms the diagnostic is
written to stdout in the supported prefix format. The launcher syntax check,
new test, Ruff and renewed global comparison pass. Localized launcher
documentation is updated. Final full-suite logs remain local; test fixtures
clean their synthetic profiles.

For isolated manual review use `./scripts/run_test_instance.sh --fresh` and open
About and the updater. Check that the existing controls remain usable and no
manual-installation action appears. A fresh source-development checkout may
block installation; opening this window does not validate missing-dependency
or privileged installation paths. The synthetic automated cases cover those
controller/view paths without installing packages. The requester confirmed the
isolated manual review, including the console filter, before publication.

## Follow-up #445: unread test bindings

Remove the unused `second` binding in the Notes failed-tab-switch test and
the unused `root` binding in the progressive split-geometry test. Preserve
both tab creations in order and the `FakeRoot(first_pane)` call, whose
constructor sets `first_pane.parent`. Assertions and production code remain
unchanged. This is maintenance for planned `0.6.1-beta`, with no version bump.

Validate with `python3 scripts/run_sandbox_tests.py tests.test_notes tests.test_split_panes`,
Ruff and the standard full regression checks. An application instance cannot
validate removal of local test names; the affected tests verify their retained
setup and behavior. Other audit candidates require separate review.

Validation passed: 153 affected tests and all 796 private sandbox tests, without
skips; compilation, shell syntax, translation synchronization (615 messages)
and whitespace checks passed. AST comparison confirms only the approved binding
changes, preserving all setup calls and assertions. Ruff decreases from 54 to
52 findings, with no new findings; the two existing RUF059 warnings in another
Notes test remain outside this batch. Bandit stays at 157 findings (143 low,
14 medium), with 17 reviewed and zero new or blocking cases. Production code
is unchanged. Coverage includes all 74 production modules at 76.03% lines and
63.59% branches; per-module results and gaps remain in ignored
`htmlcov/445-test-bindings/`. The unexecuted `__main__.py` and native/lifecycle
limitations remain; coverage does not establish complete runtime verification.
Existing GTK/VTE and GLib source-ID warnings appeared without test failures.

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
