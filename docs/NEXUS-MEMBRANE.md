# QSOL-ORACLE ↔ QSOL-NEXUS Membrane

Phase 3 implements a versioned evidentiary membrane without transferring authority between ORACLE and NEXUS.

## Protocol

`QSOL-ORACLE-NEXUS/1`

Supported operations are deliberately small:

- `evidence.query` — exact structured reads over a validated canonical ORACLE ledger;
- `event.view` — read-only ORACLE event projections for the NEXUS Courtroom Stenographer presentation surface; and
- `visible_claim.audit` — structural audits of visible NEXUS claims against explicit ORACLE event hashes.

Before any membrane operation, the reference CLI validates the complete ORACLE ledger hash/sequence/lineage chain. A parseable but invalid ledger is never served as evidence.

## Authority firewall

Every transport envelope requires these fields to remain false:

```text
hidden_reasoning_included
worldstore_mutation_authorized
council_vote_authority
governance_authority
output_mutation_authorized
```

Therefore:

```text
EVIDENCE_TRANSPORT != GOVERNANCE_AUTHORITY
AUDIT_RECEIPT != OUTPUT_CONTROL
VISIBLE_CLAIM_AUDIT != HIDDEN_REASONING_ACCESS
CITATION_PRESENT != CLAIM_SUPPORTED
```

The membrane contract validator checks the complete safety-critical contract shape, including query truth semantics, claim-audit control flags, Stenographer boundaries, direction/kind pairs, and source-observation metadata. Unexpected contract fields fail closed.

The implementation recursively rejects payload keys representing hidden chain-of-thought, private reasoning, reasoning traces, scratchpads, or equivalent private-reasoning fields. The CLI validates the complete audit input object before rebuilding a transport request, so prohibited private-reasoning fields cannot be laundered away by field selection.

## Evidence queries

Queries are exact and bounded. They may filter by subject, event hash, event type, provenance kind, or evidence state. They return `known`, `conflict`, or `unknown` based only on matching validated ORACLE records.

A matching event does not create semantic truth and a query never mutates the ORACLE ledger.

## Courtroom Stenographer

QSOL-NEXUS currently uses native schema `nexus-stenographer/1` with record scope `ai_actions_only` and zero authority. ORACLE evidence is therefore exposed as `QSOL-ORACLE-STENOGRAPHER-VIEW/1`, an external presentation-only object.

An ORACLE event view is explicitly **not** a native NEXUS Stenographer action record and is never appended to the native Stenographer ledger.

```text
STENOGRAPHER_VIEW != NATIVE_STENOGRAPHER_RECORD
```

Correction and supersession projections preserve `derived_from` and `target_event_hash`, so a presentation view does not sever the canonical relationship to the earlier event being corrected or replaced.

## Visible-claim audit

NEXUS may submit visible claims with explicit ORACLE event hashes. ORACLE may report:

- `citation_support`;
- `claim_exceeds_evidence`;
- `inference_presented_as_fact`;
- `conflict_suppressed`; and
- `unknown_suppressed`.

A primary observation citation establishes only that the cited ORACLE observation exists. The current membrane has no machine-verifiable relation between arbitrary visible claim text and event semantics, so a factual claim is **not** reported as supported merely because it cites a primary observation.

Receipts use `no-structural-objection` rather than `supported` when no structural finding is present. That state is deliberately narrower than semantic truth or factual support.

A missing citation is accumulated as a finding while every valid cited event is still inspected. Conflict and unknown suppression therefore remain visible even when another reference is invalid.

The receipt validator enforces the exact receipt/result field sets, per-claim findings, aggregate findings, status consistency, read-only authority flags, and deterministic receipt hash.

The audit does not inspect hidden model reasoning, modify NEXUS output, block NEXUS output, mutate WorldStore, vote, or govern.

## Reference CLI

```bash
python3 tools/nexus_membrane.py validate
python3 tools/nexus_membrane.py query --request-id demo --subject QSOLKCB/QSOL-CONTEXT
python3 tools/nexus_membrane.py view --request-id demo-view --event-hash <oracle-event-sha256>
python3 tools/nexus_membrane.py audit --request-id demo-audit --input visible-claims.json
```

The dedicated `validate-oracle-nexus-membrane` workflow compiles the membrane, exercises all three operations, and runs adversarial authority-leakage and review-hardening tests.
