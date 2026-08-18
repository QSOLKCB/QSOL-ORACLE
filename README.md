# QSOL-ORACLE

**The evidentiary membrane around QSOL-NEXUS and the QSOL Three-Pillar architecture.**

> **Maximum Truth Mode: enabled.**

QSOL-ORACLE is a public, vendor-neutral witness, attestation, routing, and temporal-contract layer for the QSOL ecosystem. It records what a source was observed to say or contain without promoting that observation into semantic truth.

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS ACROSS THEM
```

The practical rule remains: **ORACLE provides evidence; NEXUS provides understanding.**

## Constitutional invariants

```text
OBSERVED != TRUE
RECORDED != ENDORSED
HASH_MATCH != AUTHENTICATED_AUTHORSHIP
SIGNATURE_VALID != CLAIM_TRUE
CHECKPOINT_MATCH != SOURCE_TRUE
FRESH != TRUE
STALE != FALSE
COLLECTED != CANONICAL
UNKNOWN > PLAUSIBLE_GUESS
```

## Phase 1: deterministic witness ledger

The append-only ledger now supports explicit correction and supersession relationships:

```text
evidence.correction
  -> provenance_kind=correction
  -> target_event_hash=<earlier event>
  -> target is also in derived_from

evidence.supersession
  -> provenance_kind=supersession
  -> target_event_hash=<earlier event>
  -> target is also in derived_from
```

History is never rewritten to make the ledger prettier.

### Detached signatures

`QSOL-ORACLE-SIGNATURE/1` binds externally produced signature bytes to exact object bytes. The reference implementation validates the envelope and binding while leaving cryptographic key verification external.

A valid signature is authentication evidence, not a universal truth wand. 🪄

### Checkpoints and release fingerprints

```bash
python3 tools/oracle.py checkpoint
python3 tools/oracle.py fingerprint
```

`ledger/checkpoint.json` deterministically binds the current ledger. `release/fingerprint.json` binds the manifest-declared canonical release identity set plus the ledger checkpoint.

## Phase 2: feed collectors

Implemented collectors:

- GitHub repository state;
- GitHub commit;
- GitHub release;
- GitHub tag;
- GitHub Actions validation receipt;
- Zenodo DOI/publication record;
- QSOL-SUBSTRATE canonical fingerprint;
- QSOL-ARK recovery capability; and
- QSOL-INT compatibility/drift report.

Collectors emit `QSOL-ORACLE-FEED/1` receipts. Receipts are observations and **are not automatically admitted to the canonical ledger**.

### Freshness

Every receipt has explicit freshness semantics: `fresh`, `stale`, `undated`, or `future-dated`.

```text
FRESH != TRUE
STALE != FALSE
```

Freshness measures currency. It does not magically validate the source's claim.

### Offline deterministic CI

```bash
python3 tools/oracle.py collect github.repository --fixture fixtures/collectors.json
python3 tools/oracle.py collect github.actions --fixture fixtures/collectors.json
python3 tools/oracle.py collect qsol.substrate --fixture fixtures/collectors.json
python3 tools/oracle.py collect qsol.ark --fixture fixtures/collectors.json
python3 tools/oracle.py collect qsol.int --fixture fixtures/collectors.json
```

The fixture bundle covers all nine collector kinds without network access.

Live public GitHub and Zenodo API collection is also supported through the Python standard library. See `docs/FEEDS.md`.

## Validate

```bash
python3 tools/oracle.py validate
python3 -W default -m unittest discover -s tests -v
```

## QSOL-CONTEXT 2056 timelock

The founding temporal contract remains `contracts/qsol-context-2056.json`.

```text
ELIGIBLE_FOR_PUBLICATION != ALREADY_PUBLIC
TIME_REACHED != IGNORE_PRIVACY_OR_RIGHTS
```

The contract stores no thirty-year credential. Future execution requires then-current authorization and every fail-closed publication gate.

## Repository layout

```text
QSOL-ORACLE/
├── ai/
├── contracts/
├── docs/
│   └── FEEDS.md
├── fixtures/
│   └── collectors.json
├── ledger/
│   ├── events.jsonl
│   └── checkpoint.json
├── release/
│   └── fingerprint.json
├── schema/
│   ├── oracle-event.schema.json
│   ├── detached-signature.schema.json
│   ├── feed-receipt.schema.json
│   ├── ledger-checkpoint.schema.json
│   └── release-fingerprint.schema.json
├── tools/
│   ├── oracle.py
│   └── collectors.py
└── tests/
    └── test_oracle.py
```

## Status

**Roadmap Phases 0, 1, and 2 are implemented.** Phase 3 remains the ORACLE↔NEXUS transport membrane and visible-claim audit layer.

---

**QSOL-ORACLE does not tell you what you want to hear. It tells you what the evidence permits it to say.**
