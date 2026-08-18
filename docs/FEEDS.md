# Feed collectors

QSOL-ORACLE collectors transform source payloads into deterministic `QSOL-ORACLE-FEED/1` observation receipts.

A collector receipt is **not** a truth verdict, not a canonicalization action, and not automatically a ledger event.

## Implemented collectors

| Collector | Observes |
|---|---|
| `github.repository` | repository visibility/default branch/archive/fork/update state |
| `github.commit` | commit SHA, tree, commit time, GitHub verification metadata |
| `github.release` | release/tag/target/draft/prerelease/publication state |
| `github.tag` | tag ref and target identity |
| `github.actions` | workflow run status/conclusion/head SHA as a validation receipt |
| `zenodo.record` | DOI, concept DOI, metadata and file checksums |
| `qsol.substrate` | native QSOL-SUBSTRATE canonical payload fingerprint |
| `qsol.ark` | native QSOL-ARK recovery manifest/contract capability |
| `qsol.int` | native QSOL-INT compatibility report and live-parent drift state |

## Authority boundary

```text
collector receipt = observation
collector receipt != semantic truth
collector receipt != canonical source
collector receipt != ledger admission
```

GitHub Actions `conclusion: success` means the workflow reported success for the observed run. ORACLE does not relabel that as proof that every claim in the repository is true.

A Zenodo DOI is publication metadata. It does not grant semantic authority to the deposited content.

SUBSTRATE, ARK, and INT collectors intentionally preserve the parent system's native artifact rather than translating it into an ORACLE-owned knowledge model.

## Freshness semantics

Each receipt contains:

- `source_time` when the source exposes one;
- `evaluated_at`;
- `max_age_seconds`;
- `age_seconds`; and
- one of `fresh`, `stale`, `undated`, or `future-dated`.

The receipt also carries explicit machine booleans:

```json
{
  "stale_means_false": false,
  "fresh_means_true": false
}
```

This prevents a downstream consumer from upgrading recency into truth.

## Offline deterministic fixture mode

CI uses `fixtures/collectors.json`. No network is required.

```bash
python3 tools/oracle.py collect github.repository \
  --fixture fixtures/collectors.json

python3 tools/oracle.py collect qsol.int \
  --fixture fixtures/collectors.json
```

A fixture case fixes the payload, source locator, evaluation time, and freshness window. The resulting receipt hash is deterministic for the exact fixture bytes.

## Live mode

GitHub and Zenodo collectors can fetch public API payloads using the Python standard library:

```bash
python3 tools/oracle.py collect github.repository \
  --repo QSOLKCB/QSOL-ORACLE

python3 tools/oracle.py collect github.commit \
  --repo QSOLKCB/QSOL-ORACLE \
  --selector main

python3 tools/oracle.py collect github.release \
  --repo QSOLKCB/QSOL-ORACLE

python3 tools/oracle.py collect github.tag \
  --repo QSOLKCB/QSOL-ORACLE \
  --selector v1.0.0

python3 tools/oracle.py collect github.actions \
  --repo QSOLKCB/QSOL-ORACLE \
  --selector 123456789

python3 tools/oracle.py collect zenodo.record \
  --selector 21935097
```

Live output is deterministic for the exact source payload, evaluation timestamp, and freshness window. If `--at` is omitted, the current UTC time is used, so the freshness section is intentionally time-dependent.

## Native QSOL artifact mode

QSOL collectors accept local JSON artifacts, making cross-repository CI possible without granting ORACLE authority over those repositories:

```bash
python3 tools/oracle.py collect qsol.substrate \
  --input /path/to/substrate-fingerprint.json \
  --subject QSOLKCB/QSOL-SUBSTRATE

python3 tools/oracle.py collect qsol.ark \
  --input /path/to/ark-observation-bundle.json \
  --subject QSOLKCB/QSOL-ARK

python3 tools/oracle.py collect qsol.int \
  --input /path/to/compatibility-report.json \
  --subject QSOLKCB/QSOL-INT
```

For ARK, an observation bundle may contain `manifest` and `recovery_contract` objects. INT accepts its native compatibility report directly. SUBSTRATE accepts its native `qsol-substrate-fingerprint` object directly.
