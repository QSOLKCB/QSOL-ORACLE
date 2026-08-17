# QSOL-TIMELOCK/1

## Founding directive

`contracts/qsol-context-2056.json` records the maintainer directive that `QSOLKCB/QSOL-CONTEXT` becomes eligible for transition from private to public on **18 August 2056**.

The contract exists publicly now so the future release intent can be independently witnessed without exposing private QSOL-CONTEXT contents.

## State machine

```text
before not_before
    LOCKED
       |
       | time condition matures
       v
    ELIGIBLE
       |
       | all publication and authorization gates pass
       v
    EXECUTED

Any failed mandatory gate -> BLOCKED
```

The reference tool currently evaluates `locked` and `eligible`. Publication-clearance and platform executors are intentionally separate phases.

## Why eligibility is not execution

Thirty years is long enough for repository contents, law, platform APIs, credentials, account ownership, third-party rights, and security assumptions to change.

Therefore:

```text
TIME_REACHED != SAFE_TO_PUBLISH
ELIGIBLE != EXECUTED
```

A future executor must establish every contract precondition before changing visibility.

## Credential rule

No credential is intended to be stored for thirty years.

The 2056 executor obtains then-current authorization at execution time. GitHub is the preferred current platform implementation, not an eternal protocol dependency.

## Publication-clearance receipt

A future phase must define a deterministic receipt proving, at minimum:

- the exact QSOL-CONTEXT commit proposed for release;
- classification coverage for the complete repository;
- zero unclassified material;
- zero material marked permanent deny;
- required redaction/secret scans passed;
- applicable source/provenance requirements passed; and
- the executor has current authorization for the target platform.

The public ORACLE repository should record the receipt hash and resulting visibility event without copying private pre-release material into ORACLE.

## Supersession

The founding contract records the 2056 intent. Before execution, a newer explicitly authenticated maintainer directive may supersede it. Supersession must be recorded as a new witness event; history is not rewritten.

## Recovery

The temporal directive should eventually be duplicated into QSOL-ARK recovery material so a future system can reconstruct the intent even if GitHub or the current ORACLE runtime no longer exists.
