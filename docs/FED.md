# ORACLE ↔ FED live-local transport

`QSOL-ORACLE-FED/1` is the donor-side evidence export membrane consumed by QSOL-FED.

It exists to make ORACLE observations available to a separate process without turning ORACLE into a truth, governance, capability, or execution authority.

```text
ORACLE LEDGER
    |
    | validated read-only observation
    v
QSOL-ORACLE-FED/1
    |
    | canonical local stdio JSONL
    v
qsol-fed-oracle-observation/1
    |
    +-- state = known | conflict | unknown
    +-- attributed oracle-event:<sha256> references
    +-- suggested searches remain non-evidence
    +-- truth_claim = false
    +-- evidence_promotion = false
    +-- authority_effect = none
```

## Consumer pin

The v1 donor contract is pinned to QSOL-FED commit:

`407d0ed75c7d8a76bd49b3c30e74a0ae2c59f1e6`

and specifically to:

`schemas/oracle-observation-v1.schema.json`

ORACLE carries an exact copy at `schema/fed-oracle-observation.schema.json`. CI checks out that FED commit and byte-compares the two schema files. Drift therefore requires an explicit review instead of silent reinterpretation.

## Transport profile

The reference transport is **local stdio JSON Lines**, not a public network service.

```bash
python3 tools/fed_transport.py validate
python3 tools/fed_transport.py export --request fixtures/fed-known-request.jsonl
python3 tools/fed_transport.py serve
```

`serve` reads one canonical request per line from stdin and writes one canonical response per line to stdout.

Hard limits:

- 65,536 bytes per request/response line;
- maximum nesting depth 32;
- maximum UTF-8 string size 8,192 bytes;
- maximum array length 1,024;
- maximum object members 1,024;
- safe integers only;
- floats and non-finite numbers forbidden;
- duplicate and NFC-colliding object keys forbidden;
- request bytes must already be in the transport's deterministic canonical form.

Malformed or authority-bearing input fails closed. The process emits no partial authoritative result.

## Request boundary

`qsol-oracle-fed-request/1` accepts a structured evidence query plus optional research-continuation requirements.

The following request fields are hard false:

```text
synthetic_input               = false
evidence_promotion_requested  = false
authority_requested           = false
remote_execution_requested    = false
```

Hidden chain-of-thought fields remain forbidden by the existing ORACLE membrane scanner.

## Evidence states

The transport preserves ORACLE's three states:

```text
known
conflict
unknown
```

`known` requires at least one explicit evidence reference.

`conflict` requires at least two distinct `is_evidence=true` references. A single event labelled conflict is insufficient for the FED export and fails closed rather than fabricating a second observation.

`unknown` may contain zero evidence references. If the caller supplied explicit unsatisfied research requirements, ORACLE may include deterministic suggested searches. Those searches always remain:

```text
purpose = discovery-only
is_evidence = false
admissible_as_evidence_without_observation = false
```

## Identity and provenance

Exported ledger references use:

`oracle-event:<64 lowercase hex event hash>`

The response also includes a SHA-256 of the exact selected source-event list and a SHA-256 of the response envelope. This identifies what was exported without turning a hash into truth or authorship.

## Authority firewall

The transport cannot:

- mutate the ORACLE ledger;
- create semantic truth;
- promote evidence;
- create or reweight Council votes;
- create governance authority;
- install capabilities;
- mutate citizenship;
- rewrite history;
- trigger remote execution;
- accept synthetic/Holodeck input;
- request or persist hidden reasoning.

```text
OBSERVATION != TRUTH
TRANSPORT != AUTHORITY
HASH != ENDORSEMENT
SUGGESTED_SEARCH != EVIDENCE
SYNTHETIC_INPUT != ADMISSIBLE_INPUT
```

## Relationship to QSOL-FED Phase 5

QSOL-FED Phase 5 deliberately left `oracle_live_transport = false` until this donor-side contract existed and was gated.

After this PR is reviewed and merged, QSOL-FED may open a separate successor PR that pins the resulting ORACLE commit and proves cross-repository conformance before promoting `oracle_live_transport`.

`oracle_holodeck_synthetic_admission` remains a separate hard-false claim. This transport does not change that boundary.
