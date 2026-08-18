# Architecture

QSOL-ORACLE is an evidentiary layer, not a semantic authority.

## Role split

```text
QSOL-SUBSTRATE  KNOWS       public epistemic/provenance authority
QSOL-ARK        SURVIVES    recovery and reconstruction authority
QSOL-INT        COMPOSES    cross-system compatibility authority
QSOL-ORACLE     WITNESSES   observations, receipts, chronology, timelocks
QSOL-NEXUS      REASONS     interactive reasoning and governance
```

The Three Pillars remain SUBSTRATE, ARK, and INT. ORACLE sits outside them and may wrap around NEXUS as an evidentiary membrane.

## Inbound path

External repositories, releases, publications, APIs, and deterministic QSOL artifacts are observed by ORACLE. ORACLE records source identity, payload identity, freshness, and evidence state. It must not turn observation into endorsement.

Collectors emit `QSOL-ORACLE-FEED/1` receipts. Those receipts are deterministic observation artifacts and are **not** automatically ledger events. Admission to the canonical witness ledger remains an explicit single-writer action.

## Native-source principle

ORACLE observes each subsystem's own authority-bearing artifacts instead of redefining them:

- QSOL-SUBSTRATE canonical payload fingerprints remain SUBSTRATE artifacts;
- QSOL-ARK recovery manifests/contracts remain ARK artifacts;
- QSOL-INT compatibility reports remain INT artifacts.

ORACLE records their identity, freshness, and observed state. It does not inherit their authority.

## Freshness

Freshness is first-class metadata with four states: `fresh`, `stale`, `undated`, and `future-dated`.

```text
FRESH != TRUE
STALE != FALSE
```

A stale observation may still accurately describe an older state. A fresh observation may still report a false claim made by the source. Freshness answers "how current is this observation?", not "is the source correct?".

## NEXUS path

NEXUS may query ORACLE for evidence. NEXUS may then reason, synthesize, compare, debate, or answer. The reasoning result belongs to NEXUS and must not be laundered back into ORACLE as if it were source evidence.

ORACLE may inspect visible NEXUS claims and citations to produce a bounded audit receipt such as:

```text
supported
claim_exceeds_evidence
inference_presented_as_fact
conflict_suppressed
unknown_suppressed
```

This is a claim-boundary audit, not access to hidden model reasoning.

## Witness ledger

The JSONL ledger is append-only and hash-linked. Corrections and supersessions are future events, not silent edits of history.

`evidence.correction` records must point to the corrected event through `target_event_hash` and `derived_from`. `evidence.supersession` uses the same explicit relation rule for a newer record that replaces an older record's applicability without deleting it.

Hash integrity establishes that a record chain has not changed under the reference algorithm. It does not establish authorship, correctness, scientific truth, or canonical status.

## Detached signatures

`QSOL-ORACLE-SIGNATURE/1` binds externally produced signature bytes to the exact SHA-256 identity of an object. The reference implementation validates envelope structure and byte binding; cryptographic key verification remains external so the repository does not silently invent a trust store.

```text
SIGNATURE_VALID != CLAIM_TRUE
```

A signature can support authentication. It cannot promote the signed statement into semantic truth.

## Checkpoints and releases

`QSOL-ORACLE-CHECKPOINT/1` fingerprints exact ledger bytes, event count, ledger head, and the canonical sequence of event hashes.

`QSOL-ORACLE-RELEASE/1` fingerprints the manifest-declared release identity set plus the current ledger checkpoint. Both are deterministic and timestamp-free.

```text
CHECKPOINT_MATCH != SOURCE_TRUE
```

They prove integrity under the declared algorithms, not truth of external claims.

## Why ORACLE is deliberately boring

An oracle that always provides an answer eventually manufactures one. QSOL-ORACLE instead has three first-class result states: `known`, `conflict`, and `unknown`.

`unknown` is not a dead end. It should name missing evidence and useful research targets while preserving the rule that a search suggestion is not evidence.

## Non-goals

ORACLE is not:

- a blockchain or cryptocurrency;
- an omniscient model;
- another NEXUS Council seat;
- a substitute for primary sources;
- a semantic override for SUBSTRATE;
- a recovery override for ARK; or
- a compatibility override for INT.
