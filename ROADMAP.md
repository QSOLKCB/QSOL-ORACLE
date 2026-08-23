# QSOL-ORACLE Roadmap

## Phase 0 — Witness constitution

- [x] Define ORACLE as the external witness/attestation layer.
- [x] Preserve the Three-Pillar authority split: SUBSTRATE knows, ARK survives, INT composes.
- [x] Define NEXUS as the reasoning layer rather than another ORACLE authority.
- [x] Define Maximum Truth response states: `known`, `conflict`, `unknown`.
- [x] Require actionable unknowns without pretending search suggestions are evidence.
- [x] Add machine-readable constitution and NEXUS boundary contracts.

## Phase 1 — Deterministic witness ledger

- [x] Add append-only JSONL event format.
- [x] Add previous-hash chaining.
- [x] Add deterministic event SHA-256 identity.
- [x] Add schema and standard-library validator.
- [x] Record the ORACLE genesis event.
- [x] Record the QSOL-CONTEXT 2056 directive as a witnessed event.
- [x] Add explicit correction/supersession event types.
- [x] Add detached signatures without making signatures equal truth.
- [x] Add deterministic ledger checkpoints and release fingerprints.

## Phase 2 — Feed collectors

- [x] GitHub repository state collector.
- [x] GitHub commit/release/tag collector.
- [x] GitHub Actions/validation receipt collector.
- [x] Zenodo DOI/publication collector.
- [x] QSOL-SUBSTRATE snapshot/fingerprint collector.
- [x] QSOL-ARK recovery-capability collector.
- [x] QSOL-INT compatibility/drift collector.
- [x] Explicit freshness and stale-source semantics.
- [x] Offline fixture mode for deterministic CI.

## Phase 3 — QSOL-NEXUS membrane

- [x] Define versioned ORACLE↔NEXUS transport envelopes.
- [x] Add NEXUS evidence query operations.
- [x] Add Stenographer-compatible ORACLE event view.
- [x] Add visible-claim audit receipts around NEXUS responses.
- [x] Preserve hidden-chain-of-thought prohibition.
- [x] Ensure ORACLE cannot vote, govern, mutate WorldStore, or gain Council authority.
- [x] Add adversarial tests for evidence-to-reasoning authority leakage.

## Phase 3B — QSOL-FED live-local evidence transport

**Status: implemented on the Phase 3B branch; merge requires the dedicated transport gate to remain green.**

- [x] Define `QSOL-ORACLE-FED/1` as a separate evidence-export membrane.
- [x] Pin the reviewed QSOL-FED consumer commit and `qsol-fed-oracle-observation/1` schema.
- [x] Add canonical, bounded local stdio JSONL request/response transport.
- [x] Export attributed `oracle-event:<sha256>` evidence references.
- [x] Preserve `known` / `conflict` / `unknown` exactly.
- [x] Require at least one explicit evidence reference for `known`.
- [x] Require at least two distinct evidence references for `conflict`.
- [x] Preserve suggested searches as discovery-only non-evidence.
- [x] Keep synthetic/Holodeck input rejected.
- [x] Keep evidence promotion, authority, governance, capability and remote-execution requests rejected.
- [x] Keep the canonical ORACLE ledger read-only.
- [x] Add deterministic one-shot and streaming conformance tests.
- [x] Add byte-for-byte schema conformance against the pinned QSOL-FED commit.

### Phase 3B gate

For identical canonical requests and validated ledger bytes, the reference transport must produce byte-identical responses.

Every response must preserve:

```text
truth_claim        = false
evidence_promotion = false
authority_effect   = none
ledger_mutated     = false
transport_authority = none
```

`oracle_holodeck_synthetic_admission` remains out of scope and must stay false until a separate reviewed contract exists.

---

## Phase 4 — Research continuation

- [x] Structured `unknown` response envelope.
- [x] Missing-evidence classifier.
- [x] Primary-source-target generator.
- [x] Suggested-search generator with explicit non-evidence labelling.
- [x] Conflict bundles preserving incompatible observations.
- [x] Tests ensuring ORACLE prefers `unknown` to plausible invention.

## Phase 5 — QSOL-TIMELOCK/1

- [x] Record the QSOL-CONTEXT 2056 publication contract.
- [x] Implement deterministic `locked`/`eligible` evaluation.
- [x] Separate deadline maturity from execution authority.
- [x] Forbid 30-year stored credentials.
- [x] Define publication-clearance receipt schema.
- [x] Add local private-repository classification scanner.
- [x] Add permanent-deny and unclassified-material gates.
- [x] Add replaceable GitHub publication executor with dry-run default.
- [x] Add future-platform executor interface.
- [x] Add ARK-preserved executor recovery instructions.
- [x] Add multi-location public archival release plan for 2056.

## Phase 6 — Public feeds and receipts

- [ ] Generate deterministic per-subject feeds.
- [ ] Generate latest-state indexes without deleting history.
- [ ] Publish feed fingerprints.
- [ ] Add subscriber polling examples.
- [ ] Add portable single-file ORACLE snapshot.
- [ ] Add provenance-closed export for tool-less consumers.

## Phase 7 — Hostile truthfulness battery

- [ ] Unsupported-confidence attack cases.
- [ ] Consensus-is-truth attack cases.
- [ ] Hash-is-authorship attack cases.
- [ ] Archive-is-canonical attack cases.
- [ ] Search-suggestion-is-evidence attack cases.
- [ ] Stale-source freshness attack cases.
- [ ] NEXUS reasoning laundering attack cases.
- [ ] Timelock bypass attack cases.
- [ ] FED transport authority-escalation cases.
- [ ] FED transport synthetic-input laundering cases.
- [ ] FED transport canonicalization and resource-limit cases.

Success criterion:

```text
The Oracle remains maximally useful while retaining the deeply unpopular ability to say "I don't know."
```
