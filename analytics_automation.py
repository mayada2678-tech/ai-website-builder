from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class AnalyticsSummary:
    sessions: int
    conversions: int
    conversion_rate: float
    mobile_sessions: int
    mobile_short_sessions: int
    average_duration_seconds: float
    average_scroll_depth: float
    top_clicked_elements: tuple[tuple[str, int], ...]

    def as_prompt(self) -> str:
        clicks = ", ".join(f"{name}: {count}" for name, count in self.top_clicked_elements)
        mobile_bounce_rate = (
            self.mobile_short_sessions / self.mobile_sessions
            if self.mobile_sessions
            else 0
        )
        return (
            f"Sitzungen: {self.sessions}\n"
            f"Conversions: {self.conversions} ({self.conversion_rate:.2%})\n"
            f"Durchschnittliche Dauer: {self.average_duration_seconds:.1f} Sekunden\n"
            f"Durchschnittliche Scrolltiefe: {self.average_scroll_depth:.1f}%\n"
            f"Mobile Absprungrate unter 4 Sekunden: {mobile_bounce_rate:.2%}\n"
            f"Häufigste Klickziele: {clicks or 'keine'}"
        )


class SupabaseAnalyticsClient:
    def __init__(self, url: str, service_role_key: str) -> None:
        self.base_url = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = requests.request(
            method,
            f"{self.base_url}/{path}",
            headers=self.headers,
            timeout=30,
            **kwargs,
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Supabase HTTP {response.status_code}: {response.text[:500]}"
            )
        return response

    def analytics(self, site_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "site_analytics",
            params={
                "site_id": f"eq.{site_id}",
                "select": "session_id,version,event_type,device_type,element_clicked,is_conversion,duration_seconds,scroll_depth,created_at",
                "order": "created_at.desc",
                "limit": "10000",
            },
        )
        return list(response.json())

    def create_version(
        self,
        site_id: str,
        html_code: str,
        status: str = "testing",
        conversion_rate: float = 0.0,
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            "site_versions",
            headers={**self.headers, "Prefer": "return=representation"},
            json={
                "site_id": site_id,
                "html_code": html_code,
                "status": status,
                "conversion_rate": conversion_rate,
            },
        )
        rows = response.json()
        return rows[0] if rows else {}

    def archive_live_versions(self, site_id: str) -> None:
        self._request(
            "PATCH",
            "site_versions",
            params={"site_id": f"eq.{site_id}", "status": "eq.live"},
            headers={**self.headers, "Prefer": "return=minimal"},
            json={"status": "archived"},
        )


def summarize_analytics(events: list[dict[str, Any]]) -> AnalyticsSummary:
    sessions: dict[str, list[dict[str, Any]]] = {}
    click_counts: dict[str, int] = {}
    for event in events:
        session_id = str(event.get("session_id", ""))
        sessions.setdefault(session_id, []).append(event)
        clicked = str(event.get("element_clicked") or "").strip()
        if clicked:
            click_counts[clicked] = click_counts.get(clicked, 0) + 1

    session_rows = []
    for rows in sessions.values():
        session_row = dict(
            max(rows, key=lambda row: int(row.get("duration_seconds") or 0))
        )
        session_row["is_conversion"] = any(
            bool(row.get("is_conversion")) for row in rows
        )
        session_rows.append(session_row)
    session_count = len(session_rows)
    conversions = sum(bool(row.get("is_conversion")) for row in session_rows)
    mobile_rows = [row for row in session_rows if row.get("device_type") == "mobile"]
    durations = [int(row.get("duration_seconds") or 0) for row in session_rows]
    scroll_depths = [int(row.get("scroll_depth") or 0) for row in session_rows]
    top_clicks = tuple(sorted(click_counts.items(), key=lambda item: item[1], reverse=True)[:8])
    return AnalyticsSummary(
        sessions=session_count,
        conversions=conversions,
        conversion_rate=conversions / session_count if session_count else 0.0,
        mobile_sessions=len(mobile_rows),
        mobile_short_sessions=sum(int(row.get("duration_seconds") or 0) < 4 for row in mobile_rows),
        average_duration_seconds=sum(durations) / session_count if session_count else 0.0,
        average_scroll_depth=sum(scroll_depths) / session_count if session_count else 0.0,
        top_clicked_elements=top_clicks,
    )