"""Service Account API route adapters.

Provides stub endpoints for the Tokens web page so it loads correctly
in dev/demo mode without requiring a production identity service.
"""

from __future__ import annotations

from ..schemas.envelopes import success_response


def list_service_accounts(service, *, request_id: str = "req_unknown", **query_params: str) -> dict:
    return success_response({"service_accounts": [], "total": 0}, request_id=request_id)


def create_service_account(service, *, request_id: str = "req_unknown", **payload) -> dict:
    return success_response({"id": "stub-sa", "name": payload.get("name", ""), "owner_id": "dev", "tenant_scope": "default", "roles": [], "status": "active"}, request_id=request_id)


def get_service_account(service, sa_id: str, *, request_id: str = "req_unknown") -> dict:
    return success_response({"id": sa_id, "name": "stub", "owner_id": "dev", "tenant_scope": "default", "roles": [], "status": "active"}, request_id=request_id)


def create_token_for_sa(service, sa_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    return success_response({"id": "stub-token", "service_account_id": sa_id, "prefix": "stk_", "scopes": [], "expires_at": ""}, request_id=request_id)


__all__ = ["create_service_account", "create_token_for_sa", "get_service_account", "list_service_accounts"]
