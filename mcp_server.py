"""MCP tools for AI Website Builder integrations."""

from __future__ import annotations

import re

import requests
from fastmcp import FastMCP


mcp = FastMCP("AI-Webify-Server")
RDAP_URL = "https://rdap.org/domain/{domain_name}"
DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)


@mcp.tool()
def check_domain_availability(domain_name: str) -> dict[str, str | bool]:
    """Checks whether a valid domain is currently registered via public RDAP data."""
    normalized_domain = domain_name.strip().lower().rstrip(".")
    if normalized_domain.startswith(("https://", "http://")):
        normalized_domain = normalized_domain.split("://", maxsplit=1)[1].split("/", maxsplit=1)[0]

    if not DOMAIN_PATTERN.fullmatch(normalized_domain):
        return {
            "domain": normalized_domain,
            "available": False,
            "status": "invalid",
            "message": "Bitte geben Sie eine gültige Domain wie beispiel.de ein.",
        }

    try:
        response = requests.get(RDAP_URL.format(domain_name=normalized_domain), timeout=10)
    except requests.RequestException:
        return {
            "domain": normalized_domain,
            "available": False,
            "status": "unknown",
            "message": "Die Domain-Prüfung ist momentan nicht erreichbar.",
        }

    if response.status_code == 404:
        return {
            "domain": normalized_domain,
            "available": True,
            "status": "not_registered",
            "message": f"Für {normalized_domain} wurde kein RDAP-Eintrag gefunden.",
        }
    if response.status_code == 200:
        return {
            "domain": normalized_domain,
            "available": False,
            "status": "registered",
            "message": f"{normalized_domain} ist bereits registriert.",
        }
    return {
        "domain": normalized_domain,
        "available": False,
        "status": "unknown",
        "message": "Der Registrierungsstatus konnte nicht zuverlässig ermittelt werden.",
    }


if __name__ == "__main__":
    mcp.run()