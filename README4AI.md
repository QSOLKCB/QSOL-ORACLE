# QSOL-ORACLE — AI Bootstrap

Read `manifest.json` first. Structured contracts are authoritative when they conflict with prose.

## Identity

```text
protocol: QSOL-ORACLE/1
role: witness / attestation / research-continuation / routing / temporal-contract layer
semantic_authority: none by default
reasoning_authority: none
control_authority_over_nexus: none
ledger_model: single-writer-append-only
```

## Required interpretation

```text
SUBSTRATE = KNOWS
ARK       = SURVIVES
INT       = COMPOSES
ORACLE    = WITNESSES
NEXUS     = REASONS
```

ORACLE is outside the Three Pillars. It may surround NEXUS as an evidentiary membrane, but it must not become a hidden knowledge authority or Council member.

## Hard invariants

Load `ai/constitution.json` and preserve at minimum:

```text
OBSERVED != TRUE
RECORDED != ENDORSED
SIGNATURE_VALID != CLAIM_TRUE
CHECKPOINT_MATCH != SOURCE_TRUE
FRESH != TRUE
STALE != FALSE
COLLECTED != CANONICAL
SUGGESTED_SEARCH != EVIDENCE
UNKNOWN > PLAUSIBLE_GUESS
CLEARANCE != EXECUTION_AUTHORITY
DRY_RUN != EXECUTED
ARCHIVED_COPY != SEMANTIC_AUTHORITY
```

## Response states and research continuation

Use exactly these conceptual states when answering from ORACLE evidence:

- `known`: sufficient cited evidence establishes the requested observation;
- `conflict`: relevant evidence materially disagrees;
- `unknown`: available evidence cannot establish the answer.

Phase 4 implementation is `tools/research.py`.

### Structured unknown

`build_unknown_response` consumes **explicit structured evidence requirements**. The classifier does not invent a likely requirement set from prose. If any required evidence is absent, the envelope uses:

```text
protocol = QSOL-ORACLE-RESEARCH/1
state = unknown
answer = null
plausible_completion_used = false
plausible_completion_allowed = false
truth_claim = false
```

Missing-evidence classes map to bounded primary-source targets. Suggested searches are generated from those targets but remain `discovery-only`, `is_evidence=false`, and inadmissible as evidence until a source is actually observed.

### Conflict bundle

`QSOL-ORACLE-CONFLICT/1` requires two or more materially incompatible values. Preserve each source-linked observation and set:

```text
resolution = unresolved
consensus_value = null
averaging_forbidden = true
truth_claim = false
```

Do not convert disagreement into a majority vote or guessed compromise.

## Ledger and signatures

`ledger/events.jsonl` is a single-writer append-only hash-linked ledger. Corrections and supersessions are new events referencing earlier canonical hashes. Earlier bytes remain intact.

Detached signatures bind externally produced signature bytes to exact object identity. Cryptographic key verification remains external, and a valid signature is not semantic truth.

## Feed collectors

Collectors emit deterministic `QSOL-ORACLE-FEED/1` observation receipts. They do **not** append to the ledger automatically. Freshness describes currency, not truth.

See `docs/FEEDS.md`.

## QSOL-TIMELOCK publication pipeline

The founding `contracts/qsol-context-2056.json` is already hash-witnessed. Do not silently rewrite it to add later implementation detail.

Phase 5 adds separate machine contracts and tools around that founding intent:

```text
contracts/publication-safety-policy.json
contracts/publication-executor-interface.json
schema/publication-classification.schema.json
schema/publication-clearance.schema.json
schema/publication-executor.schema.json
tools/timelock.py
tools/publication_executor.py
recovery/ark-timelock-executor.json
release/2056-archive-plan.json
```

### Classification scanner

`tools/timelock.py` scans a **local** candidate repository. It does not upload private bytes.

The scanner is fail-closed:

```text
missing classification -> unclassified -> block
classification SHA mismatch -> unclassified -> block
permanent-deny -> block
redact-before-publication -> block
sensitive finding -> block
unsafe symlink -> block
orphan classification entry -> block
```

Sensitive findings report detector IDs and paths only. Suspected secret values must not be copied into public reports.

### Publication clearance

A `QSOL-PUBLICATION-CLEARANCE/1` receipt binds the exact scan, source commit, evaluation time, timelock state, and safety gates.

Even when `clearance_state=cleared`:

```text
execution_authority_included = false
execution_authorized = false
```

Deadline maturity and publication clearance therefore remain separate from execution authority.

### Publication executor

`tools/publication_executor.py` implements a replaceable adapter interface. GitHub is the current concrete adapter.

Every execution plan defaults to:

```text
dry_run = true
credential_source = runtime-only
credential_persisted = false
current_platform_authority_required = true
oracle_execution_authority = false
```

Real execution requires an eligible cleared receipt, explicit current authority confirmation, a runtime credential, platform preflight, and postcondition verification. Never reconstruct or persist a decades-old credential.

If the platform changes by 2056, replace the adapter under `QSOL-PUBLICATION-EXECUTOR-INTERFACE/1`. Do not weaken the founding timelock or safety gates.

### Recovery and archival release

`recovery/ark-timelock-executor.json` is the recovery recipe intended for preservation with QSOL-ARK. It reconstructs procedure and contracts, never historic credentials.

`release/2056-archive-plan.json` requires at least three independent public preservation location classes after publication clearance. Archive presence is preservation evidence, not semantic authority.

## Temporal rule

```text
eligible != executed
TIME_REACHED != SAFE_TO_PUBLISH
CLEARANCE != EXECUTION_AUTHORITY
```

Do not bypass publication clearance, permanent-deny, unclassified-material, authorization, provenance, or platform checks merely because the time condition has matured.

## NEXUS

ORACLE may provide evidence feeds and receipts to NEXUS and may check whether visible NEXUS output exceeds cited evidence. ORACLE must never expose or request hidden chain-of-thought.
