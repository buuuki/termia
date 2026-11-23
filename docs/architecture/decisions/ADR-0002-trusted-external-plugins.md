# ADR-0002: Trusted external plugins with separate distribution

- Status: Accepted
- Date: 2026-11-23
- Scope: #536, external plugin API 2 and the Diagnostics pilot
- Amends: [ADR-0001](ADR-0001-built-in-addons.md)

## Context

Diagnostics must be distributed separately from Termia and installed manually,
including by existing users. The built-in-only restriction in ADR-0001 does not
cover this requirement. Statistics and SFTP remain built-in optional add-ons.

## Decision

- Permit trusted external plugins alongside built-in add-ons. This supersedes
  ADR-0001's built-in-only restriction and its exclusion of external loading;
  its Core ownership, narrow contracts and data-preservation rules remain.
- Keep `app.py` as the composition root. It assembles the generic
  `PluginRuntime` and explicitly supplies host capabilities. Core modules must
  not import concrete external plugin implementations. The runtime loads them
  through their manifests; tests may load plugin sources directly.
- API 2 is experimental, not a stable third-party compatibility promise.
  Manifest and module API versions must match the host, and requested
  capabilities must exist. Reject incompatible plugins; never silently adapt
  an unknown API. The existing `context` alias remains available alongside
  `diagnostics_context` for API 2 compatibility.
- Discover manifests at startup in the user data directory's `termia/plugins`
  subdirectory, or `TERMIA_PLUGINS_DIR`. Each plugin has its own directory,
  manifest, import namespace, code, resources and translations.
- Install and update trusted plugin archives manually while Termia is closed.
  Do not download or install plugins automatically. The distribution plan is
  one separate repository for all plugins, with an archive and SHA-256 checksum
  for each plugin, built reproducibly without executing its code. The sources
  are prepared in the separate local `termia-plugins` tree; repository
  initialization, remote creation and publication require separate authorization.
- External enablement changes apply on Save; Cancel discards pending choices.
  Built-in Statistics/SFTP changes still require restart. This distinction
  supersedes ADR-0001's restart-only rule only for external plugins.
- Persist plugin choices separately under the profile's `plugins` directory.
  Disabling or removing a plugin must preserve its saved preference. Existing
  empty disabled markers retain their meaning. Do not migrate connection data.
- A plugin supplies `create(**capabilities)` and a controller with
  `show(language)` and `close()`. Closing, disabling and shutdown must release
  its workers, timers and windows. Loaded modules remain cached; changing
  plugin files requires restart. This is not hot reload.
- Diagnostics receives copied counts and process identities, window attachment
  and semantic styling callbacks. It must not receive the connection store,
  a main window or live terminal sessions. Plugin workers must not call GTK.
- Plugins own their translations; Diagnostics uses English fallback for missing
  optional catalogs or keys. Reuse native GTK controls and host visual roles.

## Trust and failure behavior

Plugins execute in Termia's process with its operating-system permissions.
Capability injection is an architectural contract, not an access-control or
security boundary. A malicious or defective plugin can access user data or
crash/block Termia. Install only trusted code; a checksum detects corruption
but does not authenticate its publisher. Sandboxing, a marketplace, dependency
installation and automatic plugin updates are outside this decision.

The runtime reports metadata, compatibility, import, activation and opening
errors. Caught plugin exceptions must not hide the other available tools.
Failure isolation is best effort, not protection against native crashes or
blocking code. Save applies changes sequentially, not as an atomic transaction
across all tools. Earlier successful changes can remain if a later one fails.
A failed close can require restart; the saved disabled choice is retained.
`TERMIA_DISABLE_PLUGINS=1` prevents external plugin code from loading.

## Consequences and validation

Termia must remain usable with no external plugins. Diagnostics is absent until
installed; existing users must install it manually after upgrading. Its legacy
built-in implementation is removed while the Core context contract remains.

Keep regression coverage for sampling, PID reuse, history and cancellation,
plugin compatibility and errors, host callbacks, translations, and enabled and
disabled behavior. Validate package contents and checksums independently of
runtime tests. See [regression checks](../../REGRESSION_CHECKS.md).

Approval of this architecture does not publish packages, create the separate
repository, freeze API 2, or approve a release version or stable maturity.
Release scope, distribution location and publication remain separate decisions.
