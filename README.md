# QSOL-ORACLE

**The evidentiary membrane around QSOL-NEXUS and the QSOL Three-Pillar architecture.**

> **Maximum Truth Mode: enabled.**  
> Maximum comfort, mystical certainty, and telling people what they wanted to hear were not included in the protocol.

QSOL-ORACLE is a public, vendor-neutral witness, attestation, routing, and temporal-contract layer for the QSOL ecosystem. It does **not** try to be an all-knowing AI. That job would be both impossible and, frankly, suspicious.

Its preferred answer when evidence runs out is:

> **Sorry, I don't have that information. Here is what I do have, what is missing, and what you could search next.**

The core rule is simple:

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS ACROSS THEM
```

ORACLE sits outside the Three Pillars and can wrap around NEXUS:

```text
 external sources / repositories / releases / publications
                         |
                         v
                +-----------------+
                |   QSOL-ORACLE   |
                |    WITNESSES    |
                |                 |
                | provenance      |
                | observations    |
                | conflicts       |
                | unknowns        |
                | timelocks       |
                | witness ledger  |
                |       |         |
                |       v         |
                | +-----------+   |
                | |QSOL-NEXUS |   |
                | |  REASONS  |   |
                | +-----------+   |
                |       |         |
                | claim-boundary  |
                | audit / receipt |
                +-------+---------+
                        |
                        v
                      USER
```

## Constitutional invariants

```text
OBSERVED != TRUE
RECORDED != ENDORSED
HASH_MATCH != AUTHENTICATED_AUTHORSHIP
EVENT != SEMANTIC_AUTHORITY
ARCHIVED != CANONICAL
UNKNOWN > PLAUSIBLE_GUESS
ORACLE_OBSERVATION != SOURCE_TRUTH
ORACLE_ATTESTATION != SEMANTIC_AUTHORITY
ORACLE_ROUTING != CANONICALIZATION
ORACLE_TRIGGER != PERMISSION
ORACLE_MAY_CONSTRAIN_NEXUS
ORACLE_MUST_NOT_PRETEND_TO_BE_NEXUS
NEXUS_MUST_NOT_PRESENT_REASONING_AS_ORACLE_EVIDENCE
```

The practical interpretation is equally simple: **ORACLE provides evidence; NEXUS provides understanding.**

## What ORACLE does

ORACLE is intended to provide deterministic, inspectable records for:

- repository state and commit observations;
- releases and publication events;
- cross-repository fingerprints and compatibility receipts;
- QSOL-SUBSTRATE public-state observations;
- QSOL-ARK recovery-capability observations;
- QSOL-INT compatibility/drift observations;
- QSOL-NEXUS witness input/output receipts without capturing hidden reasoning;
- DOI/publication observations;
- append-only hash-linked event history;
- explicit `known`, `conflict`, and `unknown` response states;
- actionable research continuation hints when evidence is insufficient; and
- long-horizon temporal contracts such as the QSOL-CONTEXT 2056 publication directive.

ORACLE is **not** another knowledge base, another Council member, a truth machine, an AI deity, a blockchain, or a substitute for primary evidence.

## The Maximum Truth response contract

When ORACLE can establish something:

```text
KNOWN
-> state the observation
-> identify the source
-> preserve provenance
-> distinguish observation from interpretation
```

When sources disagree:

```text
CONFLICT
-> preserve both sides
-> identify the unresolved disagreement
-> do not average disagreement into fake certainty
```

When evidence is insufficient:

```text
UNKNOWN
-> say that the information is unavailable
-> state what evidence is missing
-> return useful search topics or primary-source targets
-> do not convert the suggested search into evidence
```

The Oracle therefore has the unusual commercial disadvantage of sometimes answering **"I don't know."** This is considered a feature.

## NEXUS and the Courtroom Stenographer

QSOL-NEXUS already has a passive append-only **Courtroom Stenographer / Knowledge-Watchman** with zero control authority. ORACLE generalizes that pattern across the ecosystem.

NEXUS may consume ORACLE feeds and expose them through its Stenographer UI/persona, but the public evidentiary record belongs outside NEXUS. The intended boundary is:

```text
ORACLE witnesses.
NEXUS reasons.
NEXUS may ask ORACLE for evidence.
ORACLE may audit claim boundaries around NEXUS output.
Neither inherits the other's authority.
```

See `docs/NEXUS.md` and `ai/nexus-boundary.json`.

## Witness ledger

`ledger/events.jsonl` is the bootstrap append-only witness ledger. Each record contains a sequence number, source locator, observation state, previous-record hash, and its own deterministic SHA-256 identity.

Validate it with:

```bash
python3 tools/oracle.py validate
```

The ledger is evidence **about observations**. A valid hash chain does not magically make the contents scientifically true.

## QSOL-CONTEXT 2056 timelock

The founding temporal contract is `contracts/qsol-context-2056.json`.

It records an explicit directive that **QSOLKCB/QSOL-CONTEXT becomes eligible for public release on 18 August 2056**, subject to fail-closed publication gates.

Check the current state with:

```bash
python3 tools/oracle.py timelock
python3 tools/oracle.py timelock --at 2056-08-18T00:00:00+09:30
```

The crucial distinction is:

```text
ELIGIBLE_FOR_PUBLICATION != ALREADY_PUBLIC
TIME_REACHED != IGNORE_PRIVACY_OR_RIGHTS
```

The contract does not store a 30-year GitHub credential. That would not be an archival strategy; it would be a very slow security incident.

A future executor must satisfy the then-current platform, authorization, provenance, and publication-clearance gates before changing visibility. The executor is replaceable; the semantic directive is not tied to GitHub surviving unchanged until 2056.

See `docs/TIMELOCK.md`.

## Repository layout

```text
QSOL-ORACLE/
├── README.md
├── README4AI.md
├── AGENTS.md
├── ROADMAP.md
├── manifest.json
├── ai/
│   ├── constitution.json
│   └── nexus-boundary.json
├── contracts/
│   └── qsol-context-2056.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── NEXUS.md
│   └── TIMELOCK.md
├── ledger/
│   └── events.jsonl
├── schema/
│   └── oracle-event.schema.json
├── tools/
│   └── oracle.py
├── tests/
│   └── test_oracle.py
└── .github/workflows/validate.yml
```

## Status

**Bootstrap architecture implemented.** The repository now defines the witness role, Maximum Truth response contract, Three-Pillar authority firewall, NEXUS/Stenographer boundary, deterministic hash-linked ledger, and QSOL-TIMELOCK/1 contract for QSOL-CONTEXT.

Live GitHub/Zenodo/repository collectors, signed attestations, NEXUS runtime transport, public feed generation, and future publication executors are sequenced in `ROADMAP.md`.

---

**QSOL-ORACLE does not tell you what you want to hear. It tells you what the evidence permits it to say — which is terrible for prophecy, but rather useful for research.**
