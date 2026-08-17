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
- Never turn a suggested search into evidence.

## Unknown handling

If evidence is insufficient, prefer an explicit `unknown` result. Include missing evidence and useful search targets when possible.

Do not reward rhetorical confidence. Do not fabricate a complete answer to avoid saying `unknown`.

## Ledger rules

`ledger/events.jsonl` is a **single-writer, append-only canonical ledger**. File order is canonical order, and `sequence` must equal zero-based file position. Do not merge independently numbered fragments into this file and hope SHA-256 will negotiate custody.

Existing event bytes must not be silently rewritten to make history look cleaner. Corrections are new events that reference prior records.

Every appended record must link to the prior `event_hash`, declare a `provenance_kind`, and pass deterministic validation.

Allowed provenance classes are:

- `primary_observation` — direct observation of the cited source or artifact;
- `derived_statement` — interpretation or transformation derived from earlier witnessed events;
- `correction` — a new record correcting an earlier witnessed event without deleting history;
- `metadata` — ledger/protocol metadata rather than an observed external claim.

`derived_statement` and `correction` records must include a non-empty `derived_from` array of earlier canonical `event_hash` values. Search suggestions, NEXUS prose, summaries, and model inference must never be smuggled in as `primary_observation`.

## Adding a witnessed event

1. Identify the direct source locator.
2. Choose the correct `provenance_kind`.
3. If the event is derived or corrective, list the earlier event hashes in `derived_from`.
4. Set `sequence` to the next canonical ledger position.
5. Set `previous_hash` to the current ledger head.
6. Calculate `event_hash` over canonical JSON with `event_hash` omitted.
7. Append one JSON object as one JSONL line.
8. Run:

```bash
python3 tools/oracle.py validate
python3 -W default -m unittest discover -s tests -v
```

If validation rejects the event, fix the event. Do not weaken the validator because the Oracle is being "difficult." That is approximately its job.

## NEXUS boundary

Audit only visible inputs, outputs, citations, receipts, and explicit evidence. Do not request, persist, reconstruct, or claim access to hidden chain-of-thought.

The Courtroom Stenographer may present ORACLE records, but NEXUS presentation does not become canonical ORACLE evidence unless separately witnessed and correctly classified.

## Timelock rules

Never store a credential intended to survive until 2056. Executors are replaceable. The temporal contract is platform-neutral and fail-closed.

A matured clock creates `eligible`, not `executed`.
