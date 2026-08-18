# QSOL-ORACLE — AI Bootstrap

Read `manifest.json` first. Structured contracts are authoritative when they conflict with prose.

## Identity

```text
protocol: QSOL-ORACLE/1
role: witness / attestation / routing / temporal-contract layer
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

Load `ai/constitution.json` and `ai/nexus-boundary.json`.

At minimum preserve:

```text
OBSERVED != TRUE
RECORDED != ENDORSED
SIGNATURE_VALID != CLAIM_TRUE
CHECKPOINT_MATCH != SOURCE_TRUE
FRESH != TRUE
STALE != FALSE
COLLECTED != CANONICAL
UNKNOWN > PLAUSIBLE_GUESS
```

Do not infer truth from a successful observation. Do not infer authorship from a hash. Do not infer canonical status from archival presence. Do not treat NEXUS reasoning as ORACLE evidence.

## Response states

Use exactly these conceptual states when answering from ORACLE evidence:

- `known`: sufficient cited evidence establishes the requested observation;
- `conflict`: relevant evidence materially disagrees;
- `unknown`: available evidence cannot establish the answer.

For `unknown`, preserve uncertainty and return bounded `suggested_searches` or primary-source targets. Suggested searches are research hints, not evidence.

## Ledger

`ledger/events.jsonl` is a **single-writer append-only** hash-linked ledger. File order is canonical order and `sequence` equals the zero-based file position.

`event_hash` is SHA-256 of canonical JSON for the record with `event_hash` omitted, using UTF-8, sorted keys, and compact separators.

Every event declares one `provenance_kind`:

```text
primary_observation
derived_statement
correction
supersession
metadata
```

`derived_statement`, `correction`, and `supersession` require `derived_from` references to earlier canonical event hashes.

Corrections use `event_type=evidence.correction`. Supersessions use `event_type=evidence.supersession`. Both require `target_event_hash`, and that target must also appear in `derived_from`. Earlier history remains intact.

A valid chain establishes deterministic ledger integrity only. It does not establish semantic truth, authorship, endorsement, or scientific validity.

## Detached signatures

`schema/detached-signature.schema.json` defines `QSOL-ORACLE-SIGNATURE/1`.

The reference tool binds externally produced signature bytes to an exact object SHA-256. Cryptographic key verification is deliberately external. The envelope always carries:

```text
authority = authentication-evidence-only
truth_claim = false
```

Example:

```bash
python3 tools/oracle.py signature-envelope \
  --object release/fingerprint.json \
  --signature release/fingerprint.sig \
  --kind release-fingerprint \
  --id local-release \
  --algorithm ed25519 \
  --key-id did:key:example
```

## Checkpoints and release identity

```bash
python3 tools/oracle.py checkpoint
python3 tools/oracle.py fingerprint
```

`ledger/checkpoint.json` binds exact ledger bytes, event count, ledger head, and event-hash sequence.

`release/fingerprint.json` binds the manifest-declared release identity set plus the current ledger checkpoint. These are integrity artifacts, not source-truth artifacts.

## Feed collectors

Collectors emit deterministic `QSOL-ORACLE-FEED/1` observation receipts. They do **not** append to the ledger automatically.

Implemented kinds:

```text
github.repository
github.commit
github.release
github.tag
github.actions
zenodo.record
qsol.substrate
qsol.ark
qsol.int
```

See `docs/FEEDS.md`.

Offline CI:

```bash
python3 tools/oracle.py collect github.repository --fixture fixtures/collectors.json
python3 tools/oracle.py collect qsol.int --fixture fixtures/collectors.json
```

Freshness states are `fresh`, `stale`, `undated`, and `future-dated`. Freshness describes currency, not truth.

## Temporal contract

`contracts/qsol-context-2056.json` records the QSOL-CONTEXT publication directive.

`eligible != executed`.

Do not bypass publication clearance, permanent-deny, unclassified-material, authorization, or platform checks merely because the time condition has matured.

## NEXUS

ORACLE may provide evidence feeds and receipts to NEXUS and may check whether NEXUS output exceeds cited evidence. ORACLE must never expose or request hidden chain-of-thought. Audit visible claims and explicit evidence only.
