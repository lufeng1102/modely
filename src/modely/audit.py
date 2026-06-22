"""Local audit log helpers for modely operations."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .common import cache

AUDIT_FILE = "audit.jsonl"


def audit_path() -> Path:
    """Return the local audit log path."""
    return Path(cache.CONFIG_DIR) / AUDIT_FILE


def record_audit_event(action: str, *, resource: Optional[str] = None, status: str = "ok", metadata: Optional[dict] = None) -> dict:
    """Append one local audit event and return it."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resource": resource,
        "status": status,
        "metadata": metadata or {},
    }
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def list_audit_events(*, limit: int = 50, action: Optional[str] = None, resource: Optional[str] = None) -> list[dict]:
    """Read local audit events newest first."""
    path = audit_path()
    if not path.exists():
        return []
    events = deque(maxlen=limit)
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if action and event.get("action") != action:
                continue
            if resource and event.get("resource") != resource:
                continue
            events.append(event)
    return list(reversed(events))


def print_audit_events(events: list[dict], *, as_json: bool = False) -> None:
    """Print audit events."""
    if as_json:
        print(json.dumps(events, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not events:
        print("No audit events found.")
        return
    for event in events:
        resource = event.get("resource") or "-"
        print(f"{event.get('ts', '-')}  {event.get('action', '-')}  {event.get('status', '-')}  {resource}")
