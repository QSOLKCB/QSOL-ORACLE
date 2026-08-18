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

- [ ] Define versioned ORACLE↔NEXUS transport envelopes.
- [ ] Add NEXUS evidence query operations.
- [ ] Add Stenographer-compatible ORACLE event view.
- [ ] Add visible-claim audit receipts around NEXUS responses.
- [ ] Preserve hidden-chain-of-thought prohibition.
- [ ] Ensure ORACLE cannot vote, govern, mutate WorldStore, or gain Council authority.
- [ ] Add adversarial tests for evidence-to-reasoning authority leakage.

## Phase 4 — Research continuation

- [ ] Structured `unknown` response envelope.
- [ ] Missing-evidence classifier.
- [ ] Primary-source-target generator.
- [ ] Suggested-search generator with explicit non-evidence labelling.
- [ ] Conflict bundles preserving incompatible observations.
- [ ] Tests ensuring ORACLE prefers `unknown` to plausible invention.

## Phase 5 — QSOL-TIMELOCK/1

- [x] Record the QSOL-CONTEXT 2056 publication contract.
- [x] Implement deterministic `locked`/`eligible` evaluation.
- [x] Separate deadline maturity from execution authority.
- [x] Forbid 30-year stored credentials.
- [ ] Define publication-clearance receipt schema.
- [ ] Add local private-repository classification scanner.
- [ ] Add permanent-deny and unclassified-material gates.
- [ ] Add replaceable GitHub publication executor with dry-run default.
- [ ] Add future-platform executor interface.
- [ ] Add ARK-preserved executor recovery instructions.
- [ ] Add multi-location public archival release plan for 2056.

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

Success criterion:

```text
The Oracle remains maximally useful while retaining the deeply unpopular ability to say "I don't know."
```
