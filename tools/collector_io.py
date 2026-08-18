"""Network and URL helpers for QSOL-ORACLE feed collectors."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def require_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} payload must be a JSON object")
    return payload


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "User-Agent": "QSOL-ORACLE/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise ValueError(f"collector fetch failed for {url}: {exc}") from exc
    return require_mapping(payload, url)


def github_url(kind: str, repo: str, selector: str | None = None) -> str:
    base = f"https://api.github.com/repos/{repo}"
    if kind == "github.repository":
        return base
    if kind == "github.commit":
        if not selector:
            raise ValueError("github.commit requires --selector <commit-or-ref>")
        return f"{base}/commits/{selector}"
    if kind == "github.release":
        return f"{base}/releases/tags/{selector}" if selector else f"{base}/releases/latest"
    if kind == "github.tag":
        if not selector:
            raise ValueError("github.tag requires --selector <tag>")
        return f"{base}/git/ref/tags/{selector}"
    if kind == "github.actions":
        if not selector:
            raise ValueError("github.actions requires --selector <run-id>")
        return f"{base}/actions/runs/{selector}"
    raise ValueError(f"{kind} is not a GitHub collector")


def zenodo_url(record_id: str) -> str:
    if not record_id:
        raise ValueError("zenodo.record requires --selector <record-id>")
    return f"https://zenodo.org/api/records/{record_id}"
