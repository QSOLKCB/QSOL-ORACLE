# QSOL-ORACLE ↔ QSOL-NEXUS

## Principle

```text
ORACLE provides evidence.
NEXUS provides understanding.
```

QSOL-ORACLE is designed to wrap around QSOL-NEXUS as an evidentiary membrane without becoming a Council member, reasoning engine, or governance authority.

## Inbound to NEXUS

Future ORACLE feeds may provide NEXUS with:

- repository/release observations;
- public publication receipts;
- source locators and payload hashes;
- freshness/staleness state;
- compatibility observations from QSOL-INT;
- public epistemic observations from QSOL-SUBSTRATE;
- recovery observations from QSOL-ARK;
- conflict bundles;
- explicit unknown states; and
- suggested research continuations.

NEXUS may reason over these records. That reasoning remains NEXUS reasoning.

## Outbound from NEXUS

ORACLE may witness public or explicitly admitted NEXUS actions and visible outputs. A future claim-boundary auditor may compare visible claims with cited evidence and emit bounded receipts.

ORACLE must not request, capture, reconstruct, or claim access to hidden chain-of-thought.

## Courtroom Stenographer

NEXUS already defines its Courtroom Stenographer / Knowledge-Watchman as passive, append-only, and zero-control-authority. ORACLE externalizes the same evidentiary idea across repositories and systems.

The intended long-term split is:

```text
QSOL-ORACLE
└── public/vendor-neutral witness ledger and feeds

QSOL-NEXUS
└── Courtroom Stenographer
    └── presentation/query surface over admitted ORACLE evidence
```

The Stenographer may render, filter, or narrate ORACLE records for humans. Rendering is not a new observation and must not silently increase authority.

## Failure behavior

Witness/recorder failure is fail-passive for NEXUS execution: it records a completeness gap when possible rather than rewriting, blocking, or fabricating the underlying result.

Security-sensitive workflows may independently require a receipt as a precondition, but that policy belongs to the caller; ORACLE itself does not gain governance authority by being unavailable.

## Future transport sketch

A future versioned envelope may resemble:

```json
{
  "protocol": "QSOL-ORACLE-NEXUS/1",
  "direction": "oracle-to-nexus",
  "kind": "witness_event",
  "event_hash": "<sha256>",
  "source": "QSOL-ORACLE",
  "authority": "observation-only"
}
```

The transport may evolve. The authority boundary must not.
