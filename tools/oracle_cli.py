"""Command-line surface for the QSOL-ORACLE reference implementation."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _print(value) -> int:
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def build_parser(api) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="QSOL-ORACLE reference tooling")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate contracts and witness ledger")
    cp = sub.add_parser("checkpoint", help="emit deterministic ledger checkpoint")
    cp.add_argument("--ledger")
    sub.add_parser("fingerprint", help="emit deterministic release fingerprint")
    sig = sub.add_parser("signature-envelope", help="bind detached signature bytes to an object")
    for name in ("object", "signature", "kind", "id", "algorithm", "key-id"):
        sig.add_argument("--" + name, required=True)
    sig.add_argument("--created-at")
    col = sub.add_parser("collect", help="collect a source observation into a deterministic receipt")
    col.add_argument("kind", choices=sorted(api.collectors.COLLECTOR_KINDS))
    col.add_argument("--repo"); col.add_argument("--selector"); col.add_argument("--subject")
    col.add_argument("--source"); col.add_argument("--source-time"); col.add_argument("--input")
    col.add_argument("--fixture"); col.add_argument("--fixture-case"); col.add_argument("--at")
    col.add_argument("--max-age", type=int)
    tl = sub.add_parser("timelock", help="evaluate the QSOL-CONTEXT timelock")
    tl.add_argument("--at")
    un = sub.add_parser("unknown", help="emit an actionable unknown response")
    un.add_argument("--missing", action="append", default=[]); un.add_argument("--search", action="append", default=[])
    return p


def _collect(api, args):
    c = api.collectors
    if args.fixture:
        case_id = args.fixture_case or args.kind
        case, receipt = c.load_fixture_case(Path(args.fixture), case_id)
        if case.get("collector") != args.kind:
            raise ValueError(
                f"fixture case collector mismatch: requested {args.kind!r}, case declares {case.get('collector')!r}"
            )
        if args.at or args.max_age is not None:
            receipt = c.collect_from_payload(
                kind=case["collector"], subject=case["subject"], source_locator=case["source_locator"],
                payload=case["payload"], evaluated_at=args.at or case["evaluated_at"],
                max_age_seconds=args.max_age if args.max_age is not None else case["max_age_seconds"],
                acquisition_mode="fixture", source_time=case.get("source_time"),
                fixture_sha256=c.sha256_bytes(Path(args.fixture).read_bytes()))
    else:
        at = args.at or datetime.now(timezone.utc).isoformat()
        max_age = args.max_age if args.max_age is not None else 86400
        if args.input:
            source_path = Path(args.input)
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("collector input must be a JSON object")
            receipt = c.collect_from_payload(
                kind=args.kind, subject=args.subject or args.repo or args.kind,
                source_locator=args.source or str(source_path), payload=payload,
                evaluated_at=at, max_age_seconds=max_age, acquisition_mode="local-file",
                source_time=args.source_time)
        else:
            if args.kind.startswith("github."):
                if not args.repo:
                    raise ValueError("live GitHub collectors require --repo OWNER/NAME")
                locator, subject = c.github_url(args.kind, args.repo, args.selector), args.subject or args.repo
            elif args.kind == "zenodo.record":
                locator, subject = c.zenodo_url(args.selector or ""), args.subject or f"zenodo:{args.selector}"
            else:
                raise ValueError("QSOL-specific collectors require --input or --fixture")
            receipt = c.collect_from_payload(
                kind=args.kind, subject=subject, source_locator=locator, payload=c.fetch_json(locator),
                evaluated_at=at, max_age_seconds=max_age, acquisition_mode="live", source_time=args.source_time)
    c.validate_receipt(receipt)
    return receipt


def main(api) -> int:
    args = build_parser(api).parse_args()
    if args.command == "validate":
        return _print(api.validate_repository())
    if args.command == "checkpoint":
        return _print(api.build_ledger_checkpoint(Path(args.ledger) if args.ledger else api.LEDGER))
    if args.command == "fingerprint":
        return _print(api.build_release_fingerprint(api.ROOT, api.load_json(api.MANIFEST)))
    if args.command == "signature-envelope":
        obj = Path(args.object); sig = Path(args.signature)
        envelope = api.detached_signature_envelope(
            object_kind=args.kind, object_id=args.id, object_sha256=api.sha256_bytes(obj.read_bytes()),
            algorithm=args.algorithm, key_id=args.key_id, signature_bytes=sig.read_bytes(),
            created_at=args.created_at or datetime.now(timezone.utc).isoformat())
        api.validate_detached_signature_envelope(envelope, obj.read_bytes())
        return _print(envelope)
    if args.command == "collect":
        return _print(_collect(api, args))
    if args.command == "timelock":
        contract = api.load_json(api.TIMELOCK)
        at = api.parse_time(args.at) if args.at else datetime.now(timezone.utc)
        return _print({
            "protocol": contract["protocol"], "contract_id": contract["contract_id"],
            "subject": contract["subject"], "evaluated_at": at.isoformat(), "not_before": contract["not_before"],
            "state": api.timelock_state(contract, at), "execution_authorized": False,
            "note": "Deadline maturity creates eligibility only; publication still requires every fail-closed precondition and a current authorized executor."})
    return _print(api.unknown_response(args.missing, args.search))
