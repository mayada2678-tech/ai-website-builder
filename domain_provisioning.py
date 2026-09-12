"""Registrar and Vercel operations for paid custom-domain provisioning."""

from __future__ import annotations

import os
import re
from typing import Any

import requests


DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
INWX_ENDPOINTS = {
    "ote": "https://api.ote.domrobot.com/jsonrpc/",
    "live": "https://api.domrobot.com/jsonrpc/",
}


class ProvisioningError(RuntimeError):
    """Raised when a paid domain cannot be provisioned safely."""


def normalize_domain(domain: str) -> str:
    normalized = domain.strip().lower().rstrip(".")
    normalized = re.sub(r"^[a-z][a-z0-9+.-]*://", "", normalized)
    normalized = normalized.removeprefix("://").removeprefix("//")
    if normalized.startswith(("https://", "http://")):
        normalized = normalized.split("://", maxsplit=1)[1].split("/", maxsplit=1)[0]
    normalized = normalized.split("/", maxsplit=1)[0]
    if normalized.startswith("www."):
        normalized = normalized[4:]
    if not DOMAIN_PATTERN.fullmatch(normalized):
        raise ProvisioningError("The requested domain is invalid.")
    return normalized


class InwxClient:
    """Minimal INWX JSON-RPC client with an isolated authenticated session."""

    def __init__(self) -> None:
        environment = os.environ.get("INWX_ENVIRONMENT", "ote").strip().lower()
        if environment not in INWX_ENDPOINTS:
            raise ProvisioningError("INWX_ENVIRONMENT must be 'ote' or 'live'.")
        self.environment = environment
        self.endpoint = INWX_ENDPOINTS[environment]
        self.username = os.environ.get("INWX_USERNAME", "").strip()
        self.password = os.environ.get("INWX_PASSWORD", "").strip()
        if not self.username or not self.password:
            raise ProvisioningError("INWX credentials are not configured.")
        self.session = requests.Session()
        self._request("account.login", {"user": self.username, "pass": self.password})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            self.endpoint,
            json={"method": method, "params": params},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        code = int(payload.get("code", 0))
        if code != 1000:
            message = str(payload.get("msg", "Unknown INWX error"))
            raise ProvisioningError(f"INWX {method} failed ({code}): {message}")
        result = payload.get("resData")
        return result if isinstance(result, dict) else {}

    def check(self, domain: str) -> dict[str, Any]:
        normalized = normalize_domain(domain)
        result = self._request("domain.check", {"domain": normalized})
        status = str(result.get("status", "")).lower()
        available = status in {"free", "available"} or result.get("available") is True
        return {
            "domain": normalized,
            "available": available,
            "status": status or ("available" if available else "unavailable"),
            "price": result.get("price"),
            "currency": result.get("currency"),
            "environment": self.environment,
        }

    def register(self, domain: str) -> dict[str, Any]:
        normalized = normalize_domain(domain)
        if self.environment == "live" and os.environ.get("INWX_LIVE_PURCHASE", "").lower() != "true":
            raise ProvisioningError("Live domain purchases are disabled by INWX_LIVE_PURCHASE.")
        handles = {
            key: os.environ.get(environment_key, "").strip()
            for key, environment_key in {
                "registrant": "INWX_REGISTRANT_HANDLE",
                "admin": "INWX_ADMIN_HANDLE",
                "tech": "INWX_TECH_HANDLE",
                "billing": "INWX_BILLING_HANDLE",
            }.items()
        }
        if not all(handles.values()):
            raise ProvisioningError("All INWX contact handles must be configured before registration.")
        return self._request(
            "domain.create",
            {"domain": normalized, "period": 1, **handles},
        )

    def create_record(self, domain: str, name: str, record_type: str, content: str) -> None:
        self._request(
            "nameserver.createRecord",
            {
                "domain": normalize_domain(domain),
                "name": name,
                "type": record_type,
                "content": content,
                "ttl": 3600,
            },
        )


def check_domain_with_registrar(domain: str) -> dict[str, Any]:
    return InwxClient().check(domain)


def add_domain_to_vercel(domain: str, project_id: str) -> dict[str, Any]:
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token or not project_id.strip():
        raise ProvisioningError("Vercel token or project ID is missing.")
    response = requests.post(
        f"https://api.vercel.com/v10/projects/{project_id.strip()}/domains",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": normalize_domain(domain)},
        timeout=45,
    )
    if response.status_code == 409:
        return {"name": normalize_domain(domain), "already_assigned": True}
    if response.status_code not in (200, 201):
        raise ProvisioningError(f"Vercel domain assignment failed: HTTP {response.status_code} {response.text}")
    return response.json()


def provision_paid_domain(domain: str, project_id: str) -> dict[str, Any]:
    """Registers one paid domain and points its apex/www records to Vercel."""
    normalized = normalize_domain(domain)
    registrar = InwxClient()
    availability = registrar.check(normalized)
    if not availability["available"]:
        raise ProvisioningError("The requested domain is no longer available.")
    registration = registrar.register(normalized)

    vercel_result = add_domain_to_vercel(normalized, project_id)
    apex_ip = os.environ.get("VERCEL_APEX_IP", "76.76.21.21").strip()
    cname_target = os.environ.get("VERCEL_CNAME_TARGET", "cname.vercel-dns.com").strip()
    registrar.create_record(normalized, "@", "A", apex_ip)
    registrar.create_record(normalized, "www", "CNAME", cname_target)
    return {
        "domain": normalized,
        "registration": registration,
        "vercel": vercel_result,
        "environment": registrar.environment,
    }
