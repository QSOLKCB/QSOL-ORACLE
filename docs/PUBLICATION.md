# Publication clearance and execution

This document describes the reference publication pipeline surrounding `QSOL-TIMELOCK/1`.

The founding 2056 directive is already witnessed. The later machinery does not rewrite that history. It adds explicit safety, clearance, executor, recovery, and archival contracts.

## Boundary

```text
DEADLINE_MATURED != SAFE_TO_PUBLISH
CLEARANCE != EXECUTION_AUTHORITY
DRY_RUN != EXECUTED
```

The pipeline is intentionally split into four responsibilities:

1. **classification** determines how each candidate file may be handled;
2. **clearance** evaluates publication safety and temporal gates;
3. **execution** performs a current platform action only with current authorization; and
4. **archival release** creates redundant public preservation copies after execution.

## Classification

A classification manifest uses `QSOL-PUBLICATION-CLASSIFICATION/1` and binds to one exact source commit.

Allowed file classifications are:

- `public`;
- `redact-before-publication`; and
- `permanent-deny`.

The scanner is fail-closed. Anything absent from the manifest is `unclassified`. If a declared per-file SHA-256 no longer matches, the file is treated as unclassified rather than silently inheriting an old decision.

## Local private-repository scan

`tools/timelock.py` operates on a local path. The candidate repository does not need to be sent to ORACLE or any external service.

The scanner records file paths, byte sizes, content hashes, classification state, and detector IDs. It does not include suspected secret values in its report.

Publication is blocked by any of:

- unclassified material;
- permanent-deny material;
- material still requiring redaction;
- sensitive token/key signatures;
- symlinks;
- classification records for missing files; or
- classification hash drift.

This scanner is a deterministic safety gate, not a claim that no undiscovered secret or legal issue exists. Independent review remains appropriate for a real 2056 publication event.

## Clearance receipt

A `QSOL-PUBLICATION-CLEARANCE/1` receipt combines:

- the exact source commit;
- the classification scan identity;
- the timelock state at a declared evaluation time;
- zero-unclassified/permanent-deny/redaction/sensitive/symlink/orphan gates; and
- an explicit external provenance-requirements result.

All gates must pass for `clearance_state=cleared`.

The receipt still contains:

```text
execution_authority_included = false
execution_authorized = false
```

This prevents a safety calculation from mutating into administrative permission.

## GitHub executor

`tools/publication_executor.py` implements the current GitHub adapter and the versioned platform-neutral executor interface.

A plan contains the target repository, exact cleared source commit, clearance receipt identity, target visibility, request description, and postcondition. Plans always default to `dry_run=true`.

Dry-run mode performs no platform write.

Real execution additionally requires:

- `--execute`;
- `--confirm-current-authority`;
- a runtime `GITHUB_TOKEN` or explicitly supplied runtime token;
- successful repository-identity preflight; and
- successful public-visibility postcondition verification.

Credentials are never copied into the plan or result and are not persisted by the reference implementation.

The operator's current-authority confirmation is a required operational assertion, but it is explicitly **not proof** by itself. Platform authorization is ultimately enforced by the current platform request.

## Future platforms

`contracts/publication-executor-interface.json` preserves the semantics a replacement adapter must implement:

- dry-run default;
- no stored credentials;
- current authority required;
- fail closed;
- verify postcondition; and
- keep the adapter replaceable.

If GitHub is unavailable, obsolete, or inappropriate in 2056, implement a conforming successor adapter instead of weakening the founding directive or safety gates.

## Recovery through QSOL-ARK

`recovery/ark-timelock-executor.json` describes how a future system reconstructs the publication procedure from preserved contracts and tools.

The recovery recipe expressly forbids restoring an historic token. It instructs a future operator to re-resolve the current platform, obtain a fresh candidate checkout, rerun classification and clearance, obtain current authorization, dry-run the adapter, and only then execute.

## Multi-location archival release

`release/2056-archive-plan.json` requires at least three independent location classes:

- public source host;
- DOI-bearing archive; and
- independent source/content archive.

An optional content-addressed public mirror adds another independent retrieval path.

The plan publishes checksums and binds copies to the same source commit or explicitly equivalent archive payload.

```text
ARCHIVED_COPY != SEMANTIC_AUTHORITY
```

Redundancy improves survival. It does not turn repository contents into universal truth.
