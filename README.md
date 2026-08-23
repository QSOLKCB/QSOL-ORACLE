# QSOL-ORACLE

**The evidentiary membrane around QSOL-NEXUS and the QSOL Three-Pillar architecture.**

> **Maximum Truth Mode: enabled.**

QSOL-ORACLE is a public, vendor-neutral witness, attestation, research-continuation, routing, and temporal-contract layer for the QSOL ecosystem. It records what evidence permits without promoting observation, search, signatures, freshness, clearance, or archival presence into semantic truth.

```text
QSOL-SUBSTRATE  KNOWS
QSOL-ARK        SURVIVES
QSOL-INT        COMPOSES
QSOL-ORACLE     WITNESSES
QSOL-NEXUS      REASONS ACROSS THEM
```

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
SUGGESTED_SEARCH != EVIDENCE
UNKNOWN > PLAUSIBLE_GUESS
CLEARANCE != EXECUTION_AUTHORITY
DRY_RUN != EXECUTED
ARCHIVED_COPY != SEMANTIC_AUTHORITY
TRANSPORT != AUTHORITY
```

## Research continuation

Phase 4 turns `unknown` into a useful machine state rather than a conversational shrug.

```bash
python3 tools/oracle.py research-unknown \
  --subject QSOLKCB/QSOL-CONTEXT \
  --question "Is the repository public now?" \
  --requirement current:current_state:"current visibility has not been directly observed"
```

The structured response contains:

- classified missing evidence;
- primary-source targets;
- suggested discovery searches explicitly labelled **non-evidence**;
- `answer: null` while evidence is missing; and
- deterministic envelope identity.

A plausible completion supplied by a caller is deliberately ignored when required evidence is absent.

Conflict bundles preserve incompatible observations without averaging them into synthetic certainty.

See `docs/RESEARCH.md`.

## Deterministic witness and feeds

The append-only ledger supports correction and supersession events without rewriting prior bytes. Detached signatures remain authentication evidence only. Deterministic checkpoints and release fingerprints bind exact repository artifacts.

Feed collectors cover GitHub repository/commit/release/tag/Actions observations, Zenodo records, QSOL-SUBSTRATE fingerprints, QSOL-ARK recovery capability, and QSOL-INT compatibility/drift receipts. Collector receipts are observations and are **not automatically canonical ledger events**.

See `docs/FEEDS.md`.

## QSOL-FED live-local evidence transport

Phase 3B adds `QSOL-ORACLE-FED/1`, a deterministic local process transport for exporting attributed ORACLE observations to QSOL-FED.

It is deliberately **not** a public network service. The reference implementation uses canonical JSON Lines over stdin/stdout:

```bash
python3 tools/fed_transport.py validate
python3 tools/fed_transport.py export --request fixtures/fed-known-request.jsonl
python3 tools/fed_transport.py serve
```

The donor contract pins QSOL-FED commit `407d0ed75c7d8a76bd49b3c30e74a0ae2c59f1e6` and its `qsol-fed-oracle-observation/1` schema. CI checks out that exact commit and byte-compares the schema before exercising the transport.

Exports preserve:

```text
state              = known | conflict | unknown
truth_claim        = false
evidence_promotion = false
authority_effect   = none
ledger_mutated     = false
transport_authority = none
```

Suggested searches remain discovery-only non-evidence. Synthetic/Holodeck input remains rejected and is still governed by a separate future contract.

See `docs/FED.md`.

## QSOL-CONTEXT 2056 publication safety

The original witnessed contract remains `contracts/qsol-context-2056.json`. Its bytes are not rewritten by the later publication machinery.

The publication path is deliberately layered:

```text
founding timelock
    |
    v
locked / eligible evaluation
    |
    v
local classification scan
    |
    v
publication-clearance receipt
    |
    |  still no execution authority
    v
replaceable platform executor
    |
    |  dry-run by default
    v
current authorization + runtime credential
    |
    v
platform action + postcondition verification
    |
    v
multi-location archival release
```

### Local classification scanner

```bash
python3 tools/oracle.py scan-publication \
  --repo /path/to/private/QSOL-CONTEXT \
  --classification /path/to/classification.json \
  --subject QSOLKCB/QSOL-CONTEXT \
  --source-commit <exact-commit>
```

The scanner fails closed. Unclassified files, permanent-deny material, pending redaction, sensitive-token/key signatures, unsafe symlinks, orphan classification records, or classified-file hash drift block publication clearance.

### Publication clearance

```bash
python3 tools/oracle.py publication-clearance \
  --scan scan.json \
  --at 2056-08-18T00:00:00+09:30 \
  --provenance-passed
```

A cleared receipt means the declared safety gates passed for that exact scan and time. It **does not grant execution authority**.

### Replaceable executor

```bash
# Default: no side effects
python3 tools/oracle.py publish --clearance clearance.json

# Future real execution additionally requires current authorization and a runtime token.
python3 tools/oracle.py publish \
  --clearance clearance.json \
  --execute \
  --confirm-current-authority
```

No long-lived credential is stored. GitHub is the current adapter, not an eternal dependency. `contracts/publication-executor-interface.json` defines the future-platform interface.

The recovery procedure is captured in `recovery/ark-timelock-executor.json`, and the 2056 plan requires at least three independent archival location classes. See `docs/PUBLICATION.md` and `docs/TIMELOCK.md`.

## Validate

```bash
python3 -m compileall -q tools tests
python3 tools/oracle.py validate
python3 tools/fed_transport.py validate
python3 -W default -m unittest discover -s tests -v
```

## Status

Roadmap Phases **0, 1, 2, 3, 3B, 4, and 5** are implemented on this branch. Phase 3 is the ORACLE↔NEXUS transport/audit membrane; Phase 3B is the ORACLE↔FED live-local evidence transport. Public feed/export work and the hostile truthfulness battery remain future work.

---

**QSOL-ORACLE does not tell you what you want to hear. It tells you what the evidence permits it to say.**
