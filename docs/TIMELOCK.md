# QSOL-TIMELOCK/1

## Founding directive

`contracts/qsol-context-2056.json` records the maintainer directive that `QSOLKCB/QSOL-CONTEXT` becomes eligible for transition from private to public on **18 August 2056**.

The founding contract is already witnessed by the append-only ORACLE ledger. Later implementation work therefore surrounds that contract instead of rewriting its bytes.

## State and authority split

```text
before not_before
    LOCKED
       |
       | time condition matures
       v
    ELIGIBLE
       |
       | local safety/provenance gates pass
       v
    CLEARED
       |
       | current platform authority + runtime credential
       | + explicit execution + postcondition verification
       v
    EXECUTED

Any failed mandatory gate -> BLOCKED
```

These are deliberately different concepts:

```text
TIME_REACHED != SAFE_TO_PUBLISH
ELIGIBLE != CLEARED
CLEARANCE != EXECUTION_AUTHORITY
DRY_RUN != EXECUTED
```

## Classification manifest and local scanner

`schema/publication-classification.schema.json` defines the exact candidate commit and classification of files as:

- `public`;
- `redact-before-publication`; or
- `permanent-deny`.

Omission is not permission. A local file without a classification becomes `unclassified` and blocks clearance. If an optional per-file classification hash no longer matches the candidate bytes, the file also becomes unclassified.

Run the scanner locally against a complete candidate checkout:

```bash
python3 tools/oracle.py scan-publication \
  --repo /private/path/QSOL-CONTEXT \
  --classification /private/path/publication-classification.json \
  --subject QSOLKCB/QSOL-CONTEXT \
  --source-commit <exact-commit>
```

The scanner excludes `.git` implementation storage but treats symlinks as unsafe. It reports sensitive detector IDs and paths without copying suspected secret values into the public report.

Clearance requires zero:

- unclassified material;
- permanent-deny material;
- material still requiring redaction;
- sensitive findings;
- unsafe symlinks; and
- orphan classification entries.

## Publication-clearance receipt

`QSOL-PUBLICATION-CLEARANCE/1` binds:

- the founding timelock contract;
- the exact source commit;
- the local classification scan identity;
- the evaluation time and resulting locked/eligible state;
- classification and safety gates; and
- the separate provenance gate.

A cleared receipt always says:

```text
execution_authority_included = false
execution_authorized = false
```

It demonstrates clearance under the declared reference algorithm. It does not become a credential, administrative permission, or semantic truth claim.

## Replaceable execution

`contracts/publication-executor-interface.json` defines the platform-neutral adapter contract. The current concrete adapter is GitHub in `tools/publication_executor.py`.

The executor is **dry-run by default**. Real execution additionally requires:

1. a cleared and eligible receipt;
2. explicit current platform-authority confirmation by the operator;
3. a runtime credential obtained at execution time;
4. a platform preflight that resolves the expected repository identity;
5. the requested visibility transition; and
6. a platform postcondition reporting public visibility.

No credential is written to ORACLE artifacts. No decades-old token is a recovery target.

If GitHub or its API is unsuitable in 2056, implement a new adapter conforming to the versioned executor interface. The adapter is replaceable; the safety boundaries are not.

## ARK recovery

`recovery/ark-timelock-executor.json` captures the machine recovery procedure intended for preservation with QSOL-ARK. It records which ORACLE contracts, schemas, tools, and archive plan are required to reconstruct the publication procedure.

Recovery explicitly forbids restoring historic credentials. A future operator obtains then-current authorization and reruns classification and clearance against the exact candidate commit.

## Multi-location archival release

`release/2056-archive-plan.json` requires at least three independent location classes after publication:

1. a public source host;
2. a DOI-bearing archival repository; and
3. an independent source/content archive.

A platform-neutral content-addressed mirror is an optional fourth class.

All providers are replaceable. Public copies must bind to the same exact source commit or explicitly equivalent archive payload, and checksums should be independently published.

```text
ARCHIVED_COPY != SEMANTIC_AUTHORITY
```

Archival redundancy preserves material. It does not make every claim inside the archive true.

## Supersession

Before execution, a newer explicitly authenticated maintainer directive may supersede the founding intent. Supersession must be recorded as a new witness event. History is not rewritten.
