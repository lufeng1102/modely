"""Unit tests for local audit logging."""

from modely.audit import list_audit_events, record_audit_event


def test_record_and_list_audit_events(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.audit.audit_path", lambda: tmp_path / "audit.jsonl")

    record_audit_event("download.plan", resource="hf:model:gpt2")
    record_audit_event("label.set", resource="hf:model:gpt2", metadata={"tags": ["prod"]})

    events = list_audit_events(action="label.set")

    assert len(events) == 1
    assert events[0]["action"] == "label.set"
    assert events[0]["resource"] == "hf:model:gpt2"
    assert events[0]["metadata"]["tags"] == ["prod"]
