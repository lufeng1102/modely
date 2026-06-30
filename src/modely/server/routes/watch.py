"""Watch route adapters — expose watch target listing and drift checking as REST endpoints."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas.envelopes import error_response, success_response


WATCH_HISTORY_FILE = os.path.join(str(Path.home()), ".modely", "watch_history.json")


def list_watch_targets(config_path: str | None = None, *, config: str | None = None, request_id: str = "req_unknown", **kwargs) -> dict:
    """Return all configured watch targets with their current state.

    Query params:
      - config: optional path to watch config JSON (default ~/.modely/watch.json)

    Calls ``modely.syncing.watch.list_targets`` internally.
    """
    from modely.syncing.watch import list_targets as _list_targets

    # Accept both ``config`` (query param convention) and ``config_path``
    cfg = config or config_path

    try:
        rows = _list_targets(cfg or None)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    targets = []
    for row in rows:
        target = row["target"]
        state = row.get("state", {})
        targets.append({
            "key": row["key"],
            "source": target.get("source", ""),
            "repo_type": target.get("repo_type", ""),
            "repo_id": target.get("repo_id", ""),
            "revision": target.get("revision", ""),
            "download_mode": target.get("download", "snapshot"),
            "allow_patterns": target.get("allow_patterns", []) or [],
            "ignore_patterns": target.get("ignore_patterns", []) or [],
            "last_checked_at": state.get("last_checked_at"),
            "last_downloaded_at": state.get("last_downloaded_at"),
            "last_download_path": state.get("last_download_path"),
            "fingerprint": state.get("fingerprint"),
            "error": state.get("error"),
        })

    return success_response({"targets": targets, "total": len(targets)}, request_id=request_id)


def check_drift(config_path: str | None = None, *, config: str | None = None, request_id: str = "req_unknown", **kwargs) -> dict:
    """Check all configured watch targets for remote drift WITHOUT downloading.

    Returns the current fingerprint vs last-known fingerprint for each target.
    Calls ``modely.syncing.watch.check_drift`` internally.
    """
    from modely.syncing.watch import check_drift as _check_drift

    cfg = config or config_path
    try:
        results = _check_drift(cfg or None)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    items = []
    for result in results:
        target = result.get("target", {})
        items.append({
            "key": result["key"],
            "source": target.get("source", ""),
            "repo_type": target.get("repo_type", ""),
            "repo_id": target.get("repo_id", ""),
            "revision": target.get("revision", ""),
            "status": result["status"],
            "previous_fingerprint": result.get("previous"),
            "current_fingerprint": result.get("current"),
            "error": result.get("error"),
        })

    drifted = sum(1 for item in items if item["status"] == "drifted")
    errors = sum(1 for item in items if item["status"] == "error")
    return success_response({
        "results": items,
        "total": len(items),
        "drifted": drifted,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, request_id=request_id)


def get_watch_history(
    config_path: str | None = None,
    *,
    config: str | None = None,
    request_id: str = "req_unknown",
    **kwargs,
) -> dict:
    """Return change history for watch targets.

    Query params:
      - config: optional path to watch config JSON
      - target_key: optional filter to a specific target key (source:type:repo_id:revision)

    History is read from ``~/.modely/watch_history.json``.
    """
    history_path = WATCH_HISTORY_FILE
    if not os.path.exists(history_path):
        return success_response({"events": [], "total": 0}, request_id=request_id)

    try:
        with open(history_path, "r") as f:
            events = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return error_response("internal_error", f"Failed to read watch history: {exc}", request_id=request_id)

    target_filter = (kwargs.get("target_key") or "").strip()
    if target_filter:
        events = [e for e in events if e.get("key") == target_filter]

    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return success_response({"events": events, "total": len(events)}, request_id=request_id)


__all__ = ["check_drift", "get_watch_history", "list_watch_targets"]
