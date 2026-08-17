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

External repositories, releases, publications, APIs, and deterministic QSOL artifacts are observed by ORACLE. ORACLE records source identity, time, payload identity, freshness, and evidence state. It must not turn observation into endorsement.

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

## Why ORACLE is deliberately boring

An oracle that always provides an answer eventually manufactures one. QSOL-ORACLE instead has three first-class result states: `known`, `conflict`, and `unknown`.

`unknown` is not a dead end. It should name missing evidence and useful research targets while preserving the rule that a search suggestion is not evidence.

## Witness ledger

The JSONL ledger is append-only and hash-linked. Corrections are future events, not silent edits of history.

Hash integrity establishes that a record chain has not changed under the reference algorithm. It does not establish authorship, correctness, scientific truth, or canonical status.

## Non-goals

ORACLE is not:

- a blockchain or cryptocurrency;
- an omniscient model;
- another NEXUS Council seat;
- a substitute for primary sources;
- a semantic override for SUBSTRATE;
- a recovery override for ARK; or
- a compatibility override for INT.
