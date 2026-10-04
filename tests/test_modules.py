"""MCP-Server, Domain-Provisionierung, Analytics-Auswertung und Stripe-Webhook."""

import hashlib
import hmac
import io
import json
import time
from types import SimpleNamespace

import pytest
import requests
from conftest import SIMPLE_HTML, FakeResponse

import analytics_automation
import domain_provisioning
import logic
import mcp_server


def network_error(*_args, **_kwargs):
    raise requests.ConnectionError("offline")


class TestMcpTools:
    def test_require_html_document(self):
        assert "<html" in mcp_server.require_html_document(SIMPLE_HTML)
        for invalid in ("", "   ", "<div>x</div>", None):
            with pytest.raises(ValueError):
                mcp_server.require_html_document(invalid)

    @pytest.mark.parametrize(("label", "expected"), [("Kundenbewertungen", "testimonials"), ("FAQ", "faq"), ("Häufige Fragen", "faq"), ("CTA", "call_to_action"), ("Kundenbewertng", "testimonials")])
    def test_normalize_section_type(self, label, expected):
        assert mcp_server.normalize_section_type(label) == expected

    def test_unknown_section_type(self):
        with pytest.raises(ValueError, match="nicht erkannt"):
            mcp_server.normalize_section_type("Wetterbericht")

    @pytest.mark.parametrize("language", ["de", "en", "ar", "xx"])
    def test_inject_section_once(self, language):
        first = mcp_server.inject_section_into_html(SIMPLE_HTML, "faq", language)
        assert "eingefügt" in first["message"] and 'id="haeufige-fragen"' in first["html"]
        second = mcp_server.inject_section_into_html(first["html"], "faq", language)
        assert "bereits vorhanden" in second["message"] and second["html"].count('id="haeufige-fragen"') == 1

    def test_translated_section_texts(self):
        html = mcp_server.inject_section_into_html(SIMPLE_HTML, "testimonials", "en")["html"]
        assert "What customers say about us" in html and "Was Kunden" not in html

    def test_seo_optimization_creates_missing_tags(self):
        result = mcp_server.optimize_seo_and_content("<html><body><p>x</p></body></html>", "Friseur", "Salon Anna", "de")
        html = result["html"]
        assert "<title>Salon Anna | Friseur</title>" in html
        assert 'name="description"' in html and "<h1>Friseur bei Salon Anna</h1>" in html

    def test_industry_profiles(self):
        assert mcp_server.get_industry_chatbot_profile("Restaurant")["name"] == "Genusszeit-Assistent"
        generic = mcp_server.get_industry_chatbot_profile("Unbekannt", "it")
        assert set(generic) == set(mcp_server.CHATBOT_PROFILE_FIELDS) and generic["name"].startswith("Assistente")
        assert mcp_server.get_industry_chatbot_profile("Unbekannt", "xx") == mcp_server.GENERIC_CHATBOT_PROFILES["en"]
        for profile in mcp_server.CHATBOT_INDUSTRY_PROFILES.values():
            assert set(profile) == set(mcp_server.CHATBOT_PROFILE_FIELDS)

    def test_translation_tool(self, monkeypatch):
        assert mcp_server.translate_content_fields({"a": "Hallo"}, "de") == {"a": "Hallo"}
        with pytest.raises(ValueError, match="Unsupported"):
            mcp_server.translate_content_fields({"a": "x"}, "xx")

        class FakeOpenAI:
            def __init__(self, api_key):
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **k: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=FakeOpenAI.reply))])))

        monkeypatch.setattr(mcp_server, "OpenAI", FakeOpenAI)
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        FakeOpenAI.reply = json.dumps({"a": " Hello "})
        assert mcp_server.translate_content_fields({"a": "Hallo"}, "en") == {"a": "Hello"}
        for reply, message in (("kein json", "invalid JSON"), (json.dumps({"b": "x"}), "structure"), (json.dumps({"a": 1}), "text")):
            FakeOpenAI.reply = reply
            with pytest.raises(ValueError, match=message):
                mcp_server.translate_content_fields({"a": "Hallo"}, "en")

    @pytest.mark.parametrize(
        ("status", "expected"),
        [(404, ("not_registered", True)), (200, ("registered", False)), (500, ("unknown", False))],
    )
    def test_domain_availability(self, monkeypatch, status, expected):
        mcp_server.domain_cache.clear()
        monkeypatch.setattr(mcp_server.requests, "get", lambda *a, **k: FakeResponse(status))
        result = mcp_server.check_domain_availability("https://Beispiel-Firma.de/pfad", "de")
        assert (result["status"], result["available"]) == expected
        assert result["domain"] == "beispiel-firma.de"

    def test_domain_availability_edge_cases(self, monkeypatch):
        mcp_server.domain_cache.clear()
        assert mcp_server.check_domain_availability("kein domain", "de")["status"] == "invalid"
        # Nicht unterstützte Sprache fällt auf Englisch zurück statt abzustürzen.
        assert mcp_server.check_domain_availability("ungültig", "xx")["message"].startswith("Enter a valid domain")
        monkeypatch.setattr(mcp_server.requests, "get", network_error)
        assert mcp_server.check_domain_availability("offline.de", "de")["status"] == "unknown"
        monkeypatch.setattr(mcp_server.requests, "get", lambda *a, **k: pytest.fail("Cache wurde nicht genutzt"))
        assert mcp_server.check_domain_availability("offline.de", "de")["status"] == "unknown"


class TestMcpThroughLogic:
    def test_update_draft(self):
        html = logic.update_draft_with_mcp_tool("inject_section_into_html", {"html": SIMPLE_HTML, "section_type": "cta", "language": "de"})
        assert 'id="kontaktaufruf"' in html
        with pytest.raises(ValueError, match="MCP-Inhaltsbearbeitung"):
            logic.update_draft_with_mcp_tool("inject_section_into_html", {"html": "kaputt", "section_type": "faq"})

    def test_domain_check(self, monkeypatch, session):
        mcp_server.domain_cache.clear()
        monkeypatch.setattr(mcp_server.requests, "get", lambda *a, **k: FakeResponse(404))
        assert logic.check_custom_domain_with_mcp("frei.de")["available"] is True

    def test_translation(self):
        assert logic.translate_content_fields_with_mcp({"a": "Hallo"}, "de") == {"a": "Hallo"}
        with pytest.raises(ValueError, match="MCP-Übersetzung"):
            logic.translate_content_fields_with_mcp({"a": "Hallo"}, "xx")

    def test_chatbot_profile(self, session):
        import chat

        assert chat.get_industry_chatbot_profile_with_mcp("Friseursalon")["name"] == "Salon-Assistent"


class TestDomainProvisioning:
    @pytest.mark.parametrize(("raw", "expected"), [("HTTPS://www.Firma.de/pfad", "firma.de"), ("firma.de.", "firma.de"), ("//shop.firma.co.uk", "shop.firma.co.uk")])
    def test_normalize(self, raw, expected):
        assert domain_provisioning.normalize_domain(raw) == expected

    @pytest.mark.parametrize("raw", ["", "kein domain", "-x.de", "a" * 64 + ".de"])
    def test_invalid(self, raw):
        with pytest.raises(domain_provisioning.ProvisioningError):
            domain_provisioning.normalize_domain(raw)

    @pytest.fixture
    def inwx(self, monkeypatch):
        monkeypatch.setenv("INWX_USERNAME", "user")
        monkeypatch.setenv("INWX_PASSWORD", "pass")
        monkeypatch.setenv("INWX_ENVIRONMENT", "ote")
        calls = []
        replies = {"domain.check": {"status": "free", "price": 9.9, "currency": "EUR"}}

        def post(self, url, json, timeout):
            calls.append(json["method"])
            return FakeResponse(200, {"code": 1000, "resData": replies.get(json["method"], {})})

        monkeypatch.setattr(requests.Session, "post", post)
        return SimpleNamespace(calls=calls, replies=replies)

    def test_configuration_errors(self, monkeypatch):
        monkeypatch.setenv("INWX_ENVIRONMENT", "test")
        with pytest.raises(domain_provisioning.ProvisioningError, match="ote"):
            domain_provisioning.InwxClient()
        monkeypatch.setenv("INWX_ENVIRONMENT", "ote")
        monkeypatch.delenv("INWX_USERNAME", raising=False)
        with pytest.raises(domain_provisioning.ProvisioningError, match="credentials"):
            domain_provisioning.InwxClient()

    def test_check(self, inwx):
        result = domain_provisioning.check_domain_with_registrar("www.firma.de")
        assert result == {"domain": "firma.de", "available": True, "status": "free", "price": 9.9, "currency": "EUR", "environment": "ote"}
        assert inwx.calls == ["account.login", "domain.check"]

    def test_api_and_network_errors(self, inwx, monkeypatch):
        monkeypatch.setattr(requests.Session, "post", lambda self, url, json, timeout: FakeResponse(200, {"code": 2400, "msg": "Fehler"}))
        with pytest.raises(domain_provisioning.ProvisioningError, match="2400"):
            domain_provisioning.InwxClient()
        monkeypatch.setattr(requests.Session, "post", lambda self, *a, **k: network_error())
        with pytest.raises(domain_provisioning.ProvisioningError, match="unavailable"):
            domain_provisioning.InwxClient()

    def test_live_purchase_guard(self, inwx, monkeypatch):
        monkeypatch.setenv("INWX_ENVIRONMENT", "live")
        with pytest.raises(domain_provisioning.ProvisioningError, match="disabled"):
            domain_provisioning.InwxClient().register("firma.de")

    def test_full_provisioning(self, inwx, monkeypatch):
        for handle in ("REGISTRANT", "ADMIN", "TECH", "BILLING"):
            monkeypatch.setenv(f"INWX_{handle}_HANDLE", "h1")
        monkeypatch.setenv("VERCEL_TOKEN", "t")
        monkeypatch.setattr(domain_provisioning.requests, "post", lambda *a, **k: FakeResponse(200, {"name": "firma.de"}))
        result = domain_provisioning.provision_paid_domain("firma.de", "prj_1")
        assert result["domain"] == "firma.de" and result["vercel"] == {"name": "firma.de"}
        assert inwx.calls == ["account.login", "domain.check", "domain.create", "nameserver.createRecord", "nameserver.createRecord"]

    def test_unavailable_domain_is_not_bought(self, inwx):
        inwx.replies["domain.check"] = {"status": "taken"}
        with pytest.raises(domain_provisioning.ProvisioningError, match="no longer available"):
            domain_provisioning.provision_paid_domain("firma.de", "prj_1")
        assert "domain.create" not in inwx.calls

    def test_vercel_assignment(self, monkeypatch):
        # Streamlit legt Secrets auch als Umgebungsvariablen an (unter Windows ohne Groß-/Kleinschreibung).
        for name in ("VERCEL_TOKEN", "vercel_token"):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(domain_provisioning.ProvisioningError, match="missing"):
            domain_provisioning.add_domain_to_vercel("firma.de", "prj")
        monkeypatch.setenv("VERCEL_TOKEN", "t")
        monkeypatch.setattr(domain_provisioning.requests, "post", lambda *a, **k: FakeResponse(409, {}))
        assert domain_provisioning.add_domain_to_vercel("firma.de", "prj") == {"name": "firma.de", "already_assigned": True}
        monkeypatch.setattr(domain_provisioning.requests, "post", network_error)
        with pytest.raises(domain_provisioning.ProvisioningError, match="unavailable"):
            domain_provisioning.add_domain_to_vercel("firma.de", "prj")


class TestAnalytics:
    def test_summary(self):
        events = [
            {"session_id": "a", "duration_seconds": 3, "device_type": "mobile", "element_clicked": "Kontakt", "scroll_depth": 40},
            {"session_id": "a", "duration_seconds": 30, "device_type": "mobile", "is_conversion": True, "scroll_depth": 90},
            {"session_id": "b", "duration_seconds": 2, "device_type": "mobile", "element_clicked": "Kontakt", "scroll_depth": 10},
            {"session_id": "c", "duration_seconds": 10, "device_type": "desktop", "element_clicked": "Preise"},
        ]
        summary = analytics_automation.summarize_analytics(events)
        assert (summary.sessions, summary.conversions, summary.mobile_sessions, summary.mobile_short_sessions) == (3, 1, 2, 1)
        assert summary.conversion_rate == pytest.approx(1 / 3)
        assert summary.average_duration_seconds == pytest.approx(14)
        assert summary.top_clicked_elements[0] == ("Kontakt", 2)
        assert "Mobile Absprungrate unter 4 Sekunden: 50.00%" in summary.as_prompt()

    def test_empty_summary(self):
        summary = analytics_automation.summarize_analytics([])
        assert summary.sessions == 0 and summary.conversion_rate == 0.0
        assert "keine" in summary.as_prompt()

    def test_client_requests_and_errors(self, monkeypatch):
        sent = []
        monkeypatch.setattr(analytics_automation.requests, "request", lambda method, url, **k: sent.append((method, url, k)) or FakeResponse(200, [{"id": 5}]))
        client = analytics_automation.SupabaseAnalyticsClient("https://x.supabase.co/", "key")
        assert client.create_version("site", "<html>", "live") == {"id": 5}
        assert client.analytics("site") == [{"id": 5}]
        client.archive_live_versions("site")
        assert [entry[0] for entry in sent] == ["POST", "GET", "PATCH"]
        assert sent[0][1] == "https://x.supabase.co/rest/v1/site_versions"
        assert sent[0][2]["headers"]["Authorization"] == "Bearer key"

        monkeypatch.setattr(analytics_automation.requests, "request", lambda *a, **k: FakeResponse(401, text="denied"))
        with pytest.raises(ValueError, match="HTTP 401"):
            client.analytics("site")
        monkeypatch.setattr(analytics_automation.requests, "request", network_error)
        with pytest.raises(ValueError, match="nicht erreichbar"):
            client.analytics("site")


class TestStripeWebhook:
    SECRET = "whsec_test"

    @pytest.fixture
    def webhook(self, monkeypatch):
        import importlib

        import stripe

        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", self.SECRET)
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
        module = importlib.import_module("api.stripe_webhook")
        sessions = {"cs_1": {"id": "cs_1", "metadata": {"domain": "firma.de", "vercel_project_id": "prj_1"}}}
        modified = []
        # Echte Stripe-Objekte wie in der Live-Umgebung (ab stripe 15 keine dicts).
        monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda session_id: stripe.checkout.Session.construct_from(sessions[session_id], "sk_test"))
        monkeypatch.setattr(stripe.checkout.Session, "modify", lambda session_id, metadata: modified.append(metadata["provisioning_status"]))
        provisioned = []
        monkeypatch.setattr(module, "provision_paid_domain", lambda domain, project: provisioned.append(domain) or {"domain": domain, "environment": "ote"})
        return SimpleNamespace(module=module, sessions=sessions, modified=modified, provisioned=provisioned)

    def call(self, module, payload, signature=None):
        body = json.dumps(payload).encode()
        timestamp = int(time.time())
        if signature is None:
            digest = hmac.new(self.SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
            signature = f"t={timestamp},v1={digest}"
        handler = module.handler.__new__(module.handler)
        handler.headers = {"Content-Length": str(len(body)), "Stripe-Signature": signature}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        status = {}
        handler.send_response = lambda code: status.update(code=code)
        handler.send_header = lambda *a: None
        handler.end_headers = lambda: None
        handler.do_POST()
        return status["code"], json.loads(handler.wfile.getvalue())

    def event(self, event_type="checkout.session.completed", payment_status="paid"):
        return {"id": "evt_1", "object": "event", "type": event_type, "data": {"object": {"id": "cs_1", "object": "checkout.session", "payment_status": payment_status}}}

    def test_rejects_invalid_signature(self, webhook):
        assert self.call(webhook.module, self.event(), signature="t=1,v1=falsch")[0] == 400
        assert webhook.provisioned == []

    def test_provisions_paid_domain_once(self, webhook):
        assert self.call(webhook.module, self.event()) == (200, {"received": True, "domain": "firma.de"})
        assert webhook.modified == ["processing", "complete"] and webhook.provisioned == ["firma.de"]
        webhook.sessions["cs_1"]["metadata"]["provisioning_status"] = "complete"
        assert self.call(webhook.module, self.event())[1]["duplicate"] is True
        assert webhook.provisioned == ["firma.de"]

    def test_ignores_other_events_and_unpaid(self, webhook):
        assert self.call(webhook.module, self.event("invoice.paid"))[1]["ignored"] is True
        assert self.call(webhook.module, self.event(payment_status="unpaid"))[1]["waiting_for_payment"] is True
        assert webhook.provisioned == []

    def test_failure_is_recorded(self, webhook, monkeypatch):
        def fail(domain, project):
            raise domain_provisioning.ProvisioningError("vergeben")

        monkeypatch.setattr(webhook.module, "provision_paid_domain", fail)
        assert self.call(webhook.module, self.event())[0] == 500
        assert webhook.modified == ["processing", "failed"]

    def test_missing_configuration(self, webhook, monkeypatch):
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
        assert self.call(webhook.module, self.event())[0] == 503
