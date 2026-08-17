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

`ledger/events.jsonl` is append-only. Existing event bytes must not be silently rewritten to make history look cleaner. Corrections are new events that reference prior records.

Every appended record must link to the prior `event_hash` and pass deterministic validation.

## NEXUS boundary

Audit only visible inputs, outputs, citations, receipts, and explicit evidence. Do not request, persist, reconstruct, or claim access to hidden chain-of-thought.

The Courtroom Stenographer may present ORACLE records, but NEXUS presentation does not become canonical ORACLE evidence unless separately witnessed.

## Timelock rules

Never store a credential intended to survive until 2056. Executors are replaceable. The temporal contract is platform-neutral and fail-closed.

A matured clock creates `eligible`, not `executed`.
