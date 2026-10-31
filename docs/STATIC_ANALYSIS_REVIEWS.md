# Reviewed static-analysis findings

The analyzers continue to report every finding. A reviewed finding may stop
blocking the comparison only when it matches an individually approved entry in
`.github/static-analysis-reviews.json`. This records a bounded review decision;
it is not a security certification or release approval.

## Scope

The initial registry covers the 17 low-severity Bandit findings reviewed for
#428 after executable paths, download redirects and trial-directory permissions
were hardened. Only B404, B603 and B606 are eligible. There are no rule-wide,
directory-wide, severity-wide or wildcard acceptances. Ruff findings, other
Bandit rules, and medium/high findings cannot use this registry.

Each entry identifies one occurrence through its repository path, rule,
severity/confidence and a digest of the analyzer message and source tokens.
The reason and issue reference document why the operation was reviewed.
Adding an occurrence, changing its metadata or moving it does not transfer an
existing acceptance. Duplicate identifiers or fingerprints are invalid.

## Reviewed context

The registry also binds the reviewed sources and related validation/build
inputs. Python context uses a location-independent AST digest: comments, blank
lines and equivalent formatting do not invalidate a review, while changed
guards, arguments, nesting or literal values do. Other context files use a byte
digest. The empty Python 3.12 `type_params` field is normalized for Python 3.10
compatibility. The pinned Bandit version must match.

A changed or missing context, malformed registry, stale entry, source symlink,
duplicate occurrence or missing evidence fails closed. Remove an obsolete entry
explicitly after fixing its finding. Keep an empty registry rather than deleting
a registry already present in the comparison base. Comparisons read the registry
from the requested revision; WORKTREE mode reads the current local file.
A review already present in the comparison base cannot be removed while its
finding remains: clearing entries must not turn reviewed cases into unchecked
baseline debt. Removing entries is allowed after the findings themselves disappear.

## Reports and approval

Rows remain visible with `status: reviewed` and their review ID. Summary `new`
still counts all findings introduced relative to the base; `reviewed` and
`blocking` explain which of them affect the exit code. Existing baseline debt
remains visible. Tool, report, syntax and history failures remain errors.

The registry records a human review decision; it does not authenticate a reviewer
or provide a digital signature. Changes to entries, context dependencies or the
checker require explicit review alongside the code. CI success alone never
authorizes merging, package installation or release publication. Do not accept
fresh scan results without explicit review, weaken analyzer rules, or rewrite safe operations
only to evade detection. Preserve the comparison base and legacy-history rules.

## Validation

```bash
python3 scripts/run_sandbox_tests.py tests.test_static_analysis
python3 scripts/check_static_analysis.py --base origin/0.6.1-dev
```

Tests cover exact acceptance, visible reporting, extra occurrences, new files,
changed guards and severity, stale/invalid registries, revision selection and
real scanner/Git comparisons without executing the analyzed sources. For #428,
expect 17 introduced low findings, 17 reviewed findings and zero blocking
findings; the findings themselves must still be present in the report.
