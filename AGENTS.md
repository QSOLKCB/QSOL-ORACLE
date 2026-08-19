# AGENTS.md — QSOL-ORACLE

## Prime directive

Preserve evidence boundaries before producing convenient answers.

## Before changing ORACLE

1. Read `README4AI.md`.
2. Read `manifest.json`.
3. Read `ai/constitution.json`.
4. Read the specific schema/contract being changed.
5. Run `python3 tools/oracle.py validate` and the test suite after modifications.

## Authority rules

- Never make ORACLE a semantic authority over QSOL-SUBSTRATE.
- Never make ORACLE a recovery authority over QSOL-ARK.
- Never make ORACLE a composition authority over QSOL-INT.
- Never make ORACLE a reasoning/governance authority over QSOL-NEXUS.
- Never turn a witnessed event into a factual endorsement merely because it is recorded.
- Never turn a successful workflow, valid signature, matching hash, fresh timestamp, DOI, archive presence, clearance receipt, or dry run into semantic truth.
- Never turn a suggested search or primary-source target into evidence.

## Unknown and research-continuation rules

When evidence is insufficient, prefer the structured `unknown` envelope from `tools/research.py`.

```text
UNKNOWN > PLAUSIBLE_GUESS
SUGGESTED_SEARCH != EVIDENCE
```

Missing-evidence classification is structural: callers declare explicit evidence requirements. Do not infer a convenient requirement set from rhetoric in order to manufacture an answer.

Primary-source targets and suggested searches are discovery aids only. They become evidence only after a source is actually observed through an admissible evidence path.

Conflict bundles preserve incompatible observations. Do not average, vote, rank by rhetorical confidence, or invent a consensus value.

## Ledger rules

`ledger/events.jsonl` is a **single-writer, append-only canonical ledger**. File order is canonical order, and `sequence` must equal zero-based file position.

Existing event bytes must not be silently rewritten to make history look cleaner. Corrections and supersessions are new events that reference prior records.

Allowed provenance classes are:

- `primary_observation` — direct observation of the cited source or artifact;
- `derived_statement` — interpretation or transformation derived from earlier witnessed events;
- `correction` — a new record correcting an earlier event without deleting history;
- `supersession` — a new record replacing an earlier record's applicability without deleting history;
- `metadata` — ledger/protocol metadata rather than an observed external claim.

`derived_statement`, `correction`, and `supersession` require non-empty `derived_from` arrays of earlier canonical hashes.

A correction must use `event_type=evidence.correction`; a supersession must use `event_type=evidence.supersession`. Both require `target_event_hash`, and the target must appear in `derived_from`.

## Signatures

Detached signatures are authentication evidence only.

```text
SIGNATURE_VALID != CLAIM_TRUE
```

The reference implementation validates envelope and byte binding. External cryptographic verification must not be silently replaced with a home-grown trust claim.

## Collector rules

Collectors normalize source payloads into observation receipts. They do not append to the ledger automatically.

```text
COLLECTED != CANONICAL
FRESH != TRUE
STALE != FALSE
```

Prefer native parent artifacts for QSOL-SUBSTRATE, QSOL-ARK, and QSOL-INT. Do not redefine the parent's authority model inside ORACLE.

Offline fixture mode must remain network-free and deterministic.

## QSOL-TIMELOCK publication rules

The founding `contracts/qsol-context-2056.json` bytes are already witnessed. Do not mutate that historic contract in place. New safety and executor contracts surround it.

```text
TIME_REACHED != SAFE_TO_PUBLISH
CLEARANCE != EXECUTION_AUTHORITY
DRY_RUN != EXECUTED
```

The local classification scanner is fail-closed:

- missing classification means `unclassified`;
- hash drift in a classified file means `unclassified`;
- `permanent-deny`, `redact-before-publication`, sensitive findings, unsafe symlinks, or orphan classification entries block clearance;
- scanner reports must not emit suspected secret values.

A publication-clearance receipt never grants execution authority. The GitHub executor defaults to dry-run. Real execution requires a cleared eligible receipt, explicit current authority confirmation, a runtime credential, platform preflight, and postcondition verification.

Never persist a credential for future execution. Never reconstruct a decades-old token from ARK or any other archive.

Executors are replaceable. If GitHub is no longer suitable, implement the versioned future-platform interface instead of weakening the timelock contract.

## ARK recovery and archival preservation

`recovery/ark-timelock-executor.json` is the machine recovery recipe intended for preservation with QSOL-ARK. Recovery restores contracts and procedure, never historic credentials.

`release/2056-archive-plan.json` requires multiple independent public preservation locations after clearance. Archive presence remains preservation evidence, not semantic authority.

## Deterministic release identity

Regenerate and validate after changing any `manifest.release_fingerprint_paths` input:

```bash
python3 tools/oracle.py checkpoint > /tmp/checkpoint.json
python3 tools/oracle.py fingerprint > /tmp/fingerprint.json
python3 tools/oracle.py validate
python3 -W default -m unittest discover -s tests -v
```

Committed checkpoint and fingerprint files must match the exact repository bytes they describe.

## NEXUS boundary

Audit only visible inputs, outputs, citations, receipts, and explicit evidence. Do not request, persist, reconstruct, or claim access to hidden chain-of-thought.
