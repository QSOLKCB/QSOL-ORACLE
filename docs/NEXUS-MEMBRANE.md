# QSOL-ORACLE ↔ QSOL-NEXUS Membrane

Phase 3 implements a versioned evidentiary membrane without transferring authority between ORACLE and NEXUS.

## Protocol

`QSOL-ORACLE-NEXUS/1`

Supported operations are deliberately small:

- `evidence.query` — exact structured reads over canonical ORACLE events;
- `event.view` — read-only ORACLE event projections for the NEXUS Courtroom Stenographer presentation surface; and
- `visible_claim.audit` — structural audits of visible NEXUS claims against explicit ORACLE event hashes.

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
```

The implementation recursively rejects payload keys representing hidden chain-of-thought, private reasoning, reasoning traces, scratchpads, or equivalent private-reasoning fields.

## Evidence queries

Queries are exact and bounded. They may filter by subject, event hash, event type, provenance kind, or evidence state. They return `known`, `conflict`, or `unknown` based only on matching ORACLE records.

A matching event does not create semantic truth and a query never mutates the ORACLE ledger.

## Courtroom Stenographer

QSOL-NEXUS currently uses native schema `nexus-stenographer/1` with record scope `ai_actions_only` and zero authority. ORACLE evidence is therefore exposed as `QSOL-ORACLE-STENOGRAPHER-VIEW/1`, an external presentation-only object.

An ORACLE event view is explicitly **not** a native NEXUS Stenographer action record and is never appended to the native Stenographer ledger.

```text
STENOGRAPHER_VIEW != NATIVE_STENOGRAPHER_RECORD
```

## Visible-claim audit

NEXUS may submit visible claims with explicit ORACLE event hashes. ORACLE may report:

- `citation_support`;
- `claim_exceeds_evidence`;
- `inference_presented_as_fact`;
- `conflict_suppressed`; and
- `unknown_suppressed`.

The audit does not inspect hidden model reasoning, modify NEXUS output, block NEXUS output, mutate WorldStore, vote, or govern.

## Reference CLI

```bash
python3 tools/nexus_membrane.py validate
python3 tools/nexus_membrane.py query --request-id demo --subject QSOLKCB/QSOL-CONTEXT
python3 tools/nexus_membrane.py view --request-id demo-view --event-hash <oracle-event-sha256>
python3 tools/nexus_membrane.py audit --request-id demo-audit --input visible-claims.json
```

The dedicated `validate-oracle-nexus-membrane` workflow compiles the membrane, exercises all three operations, and runs adversarial authority-leakage tests.
