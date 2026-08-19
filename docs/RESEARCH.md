# Research continuation

QSOL-ORACLE treats insufficient evidence as a first-class research state.

The design goal is not to make `unknown` sound clever. It is to make the next evidentiary step deterministic and inspectable while preserving:

```text
UNKNOWN > PLAUSIBLE_GUESS
SUGGESTED_SEARCH != EVIDENCE
```

## Structured evidence requirements

`tools/research.py` intentionally does not run an NLP classifier over a question and guess what evidence the user probably needs. The caller declares explicit structured requirements:

```json
{
  "id": "current-state",
  "kind": "current_state",
  "satisfied": false,
  "detail": "the current repository visibility has not been directly observed"
}
```

Supported requirement classes cover primary sources, current state, identity, provenance, conflict resolution, execution receipts, and scope.

Unsatisfied requirements are classified into stable missing-evidence classes such as `primary-source-absent`, `current-state-unverified`, and `execution-unverified`.

## Primary-source targets

Every missing-evidence class maps to a bounded primary-source target. A target describes what should be observed next. It is not itself evidence.

Examples include:

- first-party primary records;
- live authoritative state;
- canonical identity records;
- provenance records;
- conflict-resolution primary records; and
- execution receipts.

Each target carries:

```text
is_evidence = false
status = target-only
```

## Suggested searches

Search suggestions are generated from the primary-source targets. They are labelled:

```text
purpose = discovery-only
is_evidence = false
admissible_as_evidence_without_observation = false
```

A search phrase is therefore an instruction for finding evidence, not a substitute for finding it.

## Structured unknown envelope

`QSOL-ORACLE-RESEARCH/1` contains the question, missing evidence, source targets, searches, and a deterministic SHA-256 identity.

While required evidence is missing:

```text
state = unknown
answer = null
plausible_completion_used = false
plausible_completion_allowed = false
truth_claim = false
```

A caller may deliberately supply a plausible answer when testing the boundary. The reference builder ignores it.

## Conflict bundles

`QSOL-ORACLE-CONFLICT/1` preserves source-linked incompatible observations.

A valid conflict bundle requires at least two distinct value hashes and retains each observation separately. It explicitly records:

```text
state = conflict
resolution = unresolved
consensus_value = null
averaging_forbidden = true
truth_claim = false
```

Conflict is resolved only by new evidence, correction, supersession, or an explicit higher-level reasoning process outside ORACLE's witness authority.

## Examples

Structured unknown:

```bash
python3 tools/oracle.py research-unknown \
  --subject QSOLKCB/QSOL-CONTEXT \
  --question "Is this repository public?" \
  --requirement current:current_state:"current visibility has not been observed"
```

Conflict input file:

```json
{
  "subject": "QSOLKCB/example",
  "dimension": "visibility",
  "observations": [
    {
      "receipt_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "source_locator": "source-a",
      "value": "private"
    },
    {
      "receipt_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
      "source_locator": "source-b",
      "value": "public"
    }
  ]
}
```

Then:

```bash
python3 tools/oracle.py conflict-bundle --input conflict.json
```
