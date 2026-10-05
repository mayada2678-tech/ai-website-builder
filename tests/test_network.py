"""Stripe, Vercel, Hugging Face und Website-Import mit simulierten HTTP-Antworten."""

import base64

import pytest
import requests
import streamlit as st
from conftest import SIMPLE_HTML, FakeResponse, FakeUpload

import logic


def network_error(*_args, **_kwargs):
    raise requests.ConnectionError("keine Verbindung")


@pytest.fixture
def stripe_configured(monkeypatch):
    monkeypatch.setattr(logic, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(logic, "STRIPE_PRICE_ID", "price_1")
    monkeypatch.setattr(logic, "STRIPE_SUCCESS_URL", "https://app.example/")


class TestStripeCheckout:
    def test_requires_configuration(self):
        with pytest.raises(ValueError, match="nicht eingerichtet"):
            logic.create_stripe_checkout_session(1, "kunde@example.com")

    def test_creates_session_with_domain_metadata(self, monkeypatch, stripe_configured):
        sent = {}

        def post(url, auth, data, timeout):
            sent.update(url=url, auth=auth, data=data)
            return FakeResponse(200, {"url": "https://checkout.stripe.com/abc"})

        monkeypatch.setattr(logic.requests, "post", post)
        url = logic.create_stripe_checkout_session(7, "kunde@example.com", "firma.de", "prj_1")
        assert url == "https://checkout.stripe.com/abc"
        assert sent["auth"] == ("sk_test", "")
        assert sent["data"]["client_reference_id"] == "7"
        assert sent["data"]["metadata[domain]"] == "firma.de"
        assert sent["data"]["success_url"].startswith("https://app.example/?checkout_session_id={CHECKOUT_SESSION_ID}&publish=1")

    @pytest.mark.parametrize("response", [FakeResponse(402, {}), FakeResponse(200, {})])
    def test_rejects_failed_or_incomplete_response(self, monkeypatch, stripe_configured, response):
        monkeypatch.setattr(logic.requests, "post", lambda *a, **k: response)
        with pytest.raises(ValueError, match="Stripe"):
            logic.create_stripe_checkout_session(1, "kunde@example.com")

    def test_network_error_becomes_user_message(self, monkeypatch, stripe_configured):
        monkeypatch.setattr(logic.requests, "post", network_error)
        with pytest.raises(ValueError, match="nicht erreichbar"):
            logic.create_stripe_checkout_session(1, "kunde@example.com")


class TestStripeConfirmation:
    def test_without_session_id_nothing_happens(self, stripe_configured):
        assert logic.confirm_stripe_checkout(1) is False

    def test_paid_checkout_activates_premium(self, monkeypatch, stripe_configured, user_id, session):
        st.query_params.update(checkout_session_id="cs_1")
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"payment_status": "paid", "client_reference_id": str(user_id), "metadata": {"domain": "firma.de"}}))
        assert logic.confirm_stripe_checkout(user_id) is True
        assert logic.get_user_status(user_id)["subscribed"]
        assert session.paid_domain_checkout_session_id == "cs_1"
        assert st.query_params == {}

    @pytest.mark.parametrize("payload", [{"payment_status": "unpaid", "client_reference_id": "1"}, {"payment_status": "paid", "client_reference_id": "999"}])
    def test_unpaid_or_foreign_checkout_is_rejected(self, monkeypatch, stripe_configured, user_id, payload):
        st.query_params.update(checkout_session_id="cs_1")
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, payload))
        assert logic.confirm_stripe_checkout(user_id) is False
        assert not logic.get_user_status(user_id)["subscribed"]

    def test_network_error_does_not_crash(self, monkeypatch, stripe_configured, user_id):
        st.query_params.update(checkout_session_id="cs_1")
        monkeypatch.setattr(logic.requests, "get", network_error)
        assert logic.confirm_stripe_checkout(user_id) is False


class TestDomainProvisioningStatus:
    @pytest.mark.parametrize("status", ["complete", "failed"])
    def test_final_status(self, monkeypatch, status):
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"metadata": {"provisioning_status": status, "provisioned_domain": "firma.de"}}))
        assert logic.wait_for_domain_provisioning("cs_1") == {"status": status, "domain": "firma.de"}

    def test_times_out_as_pending(self, monkeypatch):
        clock = iter([0, 0, 100])
        monkeypatch.setattr(logic.time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(logic.time, "sleep", lambda _s: None)
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"metadata": {}}))
        assert logic.wait_for_domain_provisioning("cs_1", timeout_seconds=1) == {"status": "pending", "domain": ""}

    @pytest.mark.parametrize("get", [network_error, lambda *a, **k: FakeResponse(500, {})])
    def test_errors_become_user_message(self, monkeypatch, get):
        monkeypatch.setattr(logic.requests, "get", get)
        with pytest.raises(ValueError, match="Veröffentlichungsstatus"):
            logic.wait_for_domain_provisioning("cs_1")


class TestPublishedWebsiteImport:
    def test_loads_website_unchanged(self, monkeypatch, session):
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, text=SIMPLE_HTML, url="https://firma.de/"))
        logic.load_published_website("firma.de")
        assert session.pending_html == SIMPLE_HTML
        assert session.live_url == "https://firma.de/" and session.deployment_id == ""

    @pytest.mark.parametrize(
        ("response", "message"),
        [
            (FakeResponse(200, text="<title>Log in to Vercel</title>", url="https://vercel.com/login"), "geschützt"),
            (FakeResponse(404, text="nicht da"), "HTTP 404"),
            (FakeResponse(200, text="nur Text"), "keine vollständige HTML"),
        ],
    )
    def test_rejects_protected_missing_or_invalid_pages(self, monkeypatch, response, message):
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: response)
        with pytest.raises(ValueError, match=message):
            logic.load_published_website("https://firma.de")

    def test_network_error(self, monkeypatch):
        monkeypatch.setattr(logic.requests, "get", network_error)
        with pytest.raises(ValueError, match="nicht erreicht"):
            logic.load_published_website("firma.de")

    def test_uploaded_template(self, session):
        logic.load_uploaded_html_template(FakeUpload("Meine Seite!.html", SIMPLE_HTML.encode()))
        assert session.pending_html == SIMPLE_HTML
        assert session.project_name == "meine-seite"
        with pytest.raises(ValueError, match="UTF-8"):
            logic.load_uploaded_html_template(FakeUpload("x.html", b"\xff\xfe"))
        with pytest.raises(ValueError, match="HTML-Datei"):
            logic.load_uploaded_html_template(None)


class TestVercelHelpers:
    def test_public_url(self):
        assert logic.get_public_url({"url": "seite.vercel.app"}) == "https://seite.vercel.app"
        with pytest.raises(ValueError):
            logic.get_public_url({})

    def test_wait_for_deployment(self, monkeypatch):
        states = iter([FakeResponse(200, {"readyState": "BUILDING"}), FakeResponse(200, {"readyState": "READY", "url": "x"})])
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: next(states))
        monkeypatch.setattr(logic.time, "sleep", lambda _s: None)
        assert logic.wait_for_vercel_deployment("dpl_1")["readyState"] == "READY"

    @pytest.mark.parametrize(
        ("get", "message"),
        [
            (lambda *a, **k: FakeResponse(200, {"readyState": "ERROR"}), "nicht veröffentlicht werden"),
            (lambda *a, **k: FakeResponse(403, {}), "HTTP 403"),
            (network_error, "nicht geprüft"),
        ],
    )
    def test_wait_for_deployment_errors(self, monkeypatch, get, message):
        monkeypatch.setattr(logic.requests, "get", get)
        with pytest.raises(ValueError, match=message):
            logic.wait_for_vercel_deployment("dpl_1")

    def test_delete_published_website(self, monkeypatch, session):
        with pytest.raises(ValueError, match="Kein Deployment"):
            logic.delete_published_website()
        session.update(deployment_id="dpl_1", live_url="https://x", published_html="<html>")
        monkeypatch.setattr(logic.requests, "delete", lambda *a, **k: FakeResponse(204))
        logic.delete_published_website()
        assert session.deployment_id == "" and session.live_url == "" and session.published_html == ""

    def test_delete_previous_deployment_by_url(self, monkeypatch):
        looked_up = []
        monkeypatch.setattr(logic.requests, "get", lambda url, **k: looked_up.append(url) or FakeResponse(200, {"id": "dpl_9"}))
        deleted = []
        monkeypatch.setattr(logic.requests, "delete", lambda url, **k: deleted.append(url) or FakeResponse(200))
        logic.delete_previous_vercel_deployment("https://alt.vercel.app/pfad")
        assert looked_up[0].endswith("/alt.vercel.app") and deleted[0].endswith("/dpl_9")
        with pytest.raises(ValueError, match="Adresse der alten Website"):
            logic.delete_previous_vercel_deployment(" ")

    def test_project_setup_and_upload(self, monkeypatch):
        monkeypatch.setattr(logic.requests, "patch", lambda *a, **k: FakeResponse(200, {}))
        assert logic.configure_public_vercel_project("prj") == ""
        monkeypatch.setattr(logic.requests, "patch", lambda *a, **k: FakeResponse(403, {}))
        assert "HTTP 403" in logic.configure_public_vercel_project("prj")
        monkeypatch.setattr(logic.requests, "patch", network_error)
        assert "nicht automatisch" in logic.configure_public_vercel_project("prj")


        monkeypatch.setattr(logic.requests, "post", lambda *a, **k: FakeResponse(200, {}))
        assert logic.upload_vercel_file("index.html", b"abc") == {"file": "index.html", "sha": "a9993e364706816aba3e25717850c26c9cd0d89d"}
        monkeypatch.setattr(logic.requests, "post", lambda *a, **k: FakeResponse(400, text="kaputt"))
        with pytest.raises(ValueError, match="HTTP 400"):
            logic.upload_vercel_file("index.html", b"abc")


class TestPublishWebsite:
    @pytest.fixture
    def vercel(self, monkeypatch):
        calls = {"files": [], "deployments": []}

        def post(url, headers=None, json=None, data=None, timeout=None):
            if url.endswith("/v2/files"):
                calls["files"].append(data)
                return FakeResponse(200, {})
            if "deployments" in url:
                calls["deployments"].append(json)
                return FakeResponse(200, {"id": "dpl_1", "url": "kunde.vercel.app", "projectId": "prj_1"})
            if url.endswith("/env"):
                return FakeResponse(201, {})
            raise AssertionError(url)

        def get(url, **_kwargs):
            if url.endswith("/env"):
                return FakeResponse(200, {"envs": []})
            return FakeResponse(200, {"readyState": "READY", "url": "kunde.vercel.app"})

        monkeypatch.setattr(logic.requests, "post", post)
        monkeypatch.setattr(logic.requests, "get", get)
        monkeypatch.setattr(logic.requests, "patch", lambda *a, **k: FakeResponse(200, {}))
        monkeypatch.setattr(logic, "HF_API_KEY", "")
        monkeypatch.setattr("chat.HF_API_KEY", "")
        return calls

    def test_publishes_all_pages_assets_and_api_routes(self, vercel, session):
        session.generated_html = SIMPLE_HTML
        session.site_pages = {"index.html": SIMPLE_HTML, "kontakt.html": SIMPLE_HTML, "styles.css": "body{}"}
        session.assets = {"logo.png": {"base64": base64.b64encode(b"PNG").decode(), "mime_type": "image/png"}}
        session.project_name = "Firma GmbH"
        logic.publish_website()

        deployed_files = {entry["file"] for entry in vercel["deployments"][0]["files"]}
        assert deployed_files == {"index.html", "kontakt.html", "styles.css", "logo.png", "api/chat.js", "api/analytics.js", "api/variant.js", "vercel.json"}
        assert vercel["deployments"][0]["name"] == "firma-gmbh"
        assert session.live_url == "https://kunde.vercel.app"
        assert session.deployment_id == "dpl_1"
        assert session.published_html.count('id="customer-chatbot"') == 1
        assert "HF_API_KEY fehlt" in session.chatbot_environment_warning

    def test_supabase_outage_is_only_a_warning(self, vercel, session, monkeypatch):
        session.generated_html = SIMPLE_HTML
        monkeypatch.setattr(logic, "SUPABASE_URL", "https://nicht-vorhanden.supabase.co")
        monkeypatch.setattr(logic, "SUPABASE_SERVICE_ROLE_KEY", "geheim")
        monkeypatch.setattr("analytics_automation.requests.request", network_error)
        logic.publish_website()
        assert session.deployment_id == "dpl_1"
        assert "Supabase ist nicht erreichbar" in session.chatbot_environment_warning

    def test_vercel_rejection_raises_user_message(self, monkeypatch, session):
        session.generated_html = SIMPLE_HTML
        monkeypatch.setattr(logic.requests, "post", lambda url, **k: FakeResponse(200, {}) if url.endswith("/v2/files") else FakeResponse(403, {"error": "forbidden"}))
        with pytest.raises(ValueError, match="Hosting-Fehler HTTP 403"):
            logic.publish_website()

    def test_requires_html(self, session):
        session.generated_html = ""
        with pytest.raises(ValueError, match="kein HTML"):
            logic.publish_website()


class TestTransformerOptimization:
    def test_requires_key(self, monkeypatch):
        monkeypatch.setattr(logic, "HF_API_KEY", "")
        with pytest.raises(ValueError, match="HF_API_KEY"):
            logic.optimize_text_with_transformer("Text")

    @pytest.mark.parametrize("payload", [[{"generated_text": " Besser. "}], {"generated_text": "Besser."}])
    def test_success(self, monkeypatch, payload):
        monkeypatch.setattr(logic, "HF_API_KEY", "hf")
        monkeypatch.setattr(logic.requests, "post", lambda *a, **k: FakeResponse(200, payload))
        assert logic.optimize_text_with_transformer("Text").startswith("Besser")

    @pytest.mark.parametrize(
        ("post", "message"),
        [
            (lambda *a, **k: FakeResponse(503, {}), "gestartet"),
            (lambda *a, **k: FakeResponse(500, text="<html>Fehler</html>"), "Unbekannter Fehler"),
            (lambda *a, **k: FakeResponse(400, {"error": "zu lang"}), "zu lang"),
            (lambda *a, **k: FakeResponse(200, [{"generated_text": "  "}]), "keinen optimierten"),
            (network_error, "nicht erreichbar"),
        ],
    )
    def test_errors(self, monkeypatch, post, message):
        monkeypatch.setattr(logic, "HF_API_KEY", "hf")
        monkeypatch.setattr(logic.requests, "post", post)
        with pytest.raises(ValueError, match=message):
            logic.optimize_text_with_transformer("Text")


def test_stripe_error_reason_is_shown(monkeypatch, stripe_configured):
    monkeypatch.setattr(logic.requests, "post", lambda *a, **k: FakeResponse(400, {"error": {"message": "No such price: 'price_x'"}}))
    with pytest.raises(ValueError, match="No such price"):
        logic.create_stripe_checkout_session(1, "kunde@example.com")


class TestCheckoutReturn:
    """Nach der Zahlung öffnet Stripe die App in einer neuen Sitzung."""

    def test_checkout_records_project_and_draft(self, monkeypatch, stripe_configured):
        sent = {}
        monkeypatch.setattr(logic.requests, "post", lambda url, auth, data, timeout: sent.update(data) or FakeResponse(200, {"url": "https://checkout"}))
        logic.create_stripe_checkout_session(1, "a@b.de", "firma.de", "prj_1", project_name="firma-ab12", website_id=7)
        assert sent["metadata[project_name]"] == "firma-ab12" and sent["metadata[website_id]"] == "7"
        assert sent["metadata[vercel_project_id]"] == "prj_1"

    def test_draft_and_project_are_restored(self, monkeypatch, stripe_configured, user_id, session):
        website_id = logic.save_website(user_id, "firma.de", SIMPLE_HTML, "firma.de", "22222222-2222-4222-8222-222222222222")
        assert isinstance(website_id, int)
        session.update(generated_html="", project_name="ai-website-builder", vercel_project_id="")
        st.query_params.update(checkout_session_id="cs_1")
        metadata = {"domain": "firma.de", "vercel_project_id": "prj_1", "project_name": "firma-ab12", "website_id": str(website_id)}
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"payment_status": "paid", "client_reference_id": str(user_id), "metadata": metadata}))
        assert logic.confirm_stripe_checkout(user_id)
        assert session.generated_html == SIMPLE_HTML and session.pending_html == SIMPLE_HTML
        assert session.project_name == "firma-ab12" and session.vercel_project_id == "prj_1"
        assert session.analytics_site_id == "22222222-2222-4222-8222-222222222222"
        assert session.paid_domain_checkout_session_id == "cs_1"

    def test_foreign_draft_is_never_loaded(self, monkeypatch, stripe_configured, user_id, session):
        logic.register_user("fremd@example.com", "sicheres-passwort")
        stranger = logic.authenticate_user("fremd@example.com", "sicheres-passwort")[0]
        foreign_id = logic.save_website(stranger, "x", "<html>fremd</html>", "", "site")
        logic.restore_checkout_draft(user_id, {"website_id": str(foreign_id)})
        assert session.generated_html == ""
        logic.restore_checkout_draft(user_id, {"website_id": "kein-wert"})
        assert session.generated_html == ""


class TestDomainPurchaseForPremium:
    def capture(self, monkeypatch):
        sent = {}
        monkeypatch.setattr(logic.requests, "post", lambda url, auth, data, timeout: sent.update(data) or FakeResponse(200, {"url": "https://checkout"}))
        return sent

    def test_premium_pays_domain_once_without_subscription(self, monkeypatch, stripe_configured):
        monkeypatch.setattr(logic, "DOMAIN_PRICE_EUR", 12.5)
        sent = self.capture(monkeypatch)
        logic.create_stripe_checkout_session(1, "a@b.de", "firma.de", "prj_1", one_time_domain=True)
        assert sent["mode"] == "payment"
        assert sent["line_items[0][price_data][unit_amount]"] == "1250"
        assert sent["line_items[0][price_data][product_data][name]"] == "Domain firma.de (1 Jahr)"
        assert "line_items[0][price]" not in sent and not any(key.startswith("subscription_data") for key in sent)
        assert sent["metadata[domain]"] == "firma.de" and sent["metadata[purchase]"] == "domain"

    def test_new_customer_gets_subscription_with_domain(self, monkeypatch, stripe_configured):
        sent = self.capture(monkeypatch)
        logic.create_stripe_checkout_session(1, "a@b.de", "firma.de", "prj_1")
        assert sent["mode"] == "subscription" and sent["line_items[0][price]"] == "price_1"
        assert sent["subscription_data[metadata][domain]"] == "firma.de"

    def test_one_time_purchase_needs_domain_and_project(self, stripe_configured):
        with pytest.raises(ValueError, match="Domain oder Website-Projekt"):
            logic.create_stripe_checkout_session(1, "a@b.de", one_time_domain=True)


class TestOwnedDomains:
    def stripe_sessions(self, monkeypatch, sessions):
        monkeypatch.setattr(logic, "STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": sessions}))

    def session(self, session_id, user, domain, paid=True, provisioning="", error="", created=1, project="firma-ab12"):
        return {"id": session_id, "client_reference_id": str(user), "payment_status": "paid" if paid else "unpaid", "created": created,
                "metadata": {"domain": domain, "project_name": project, "vercel_project_id": "prj_1", "provisioning_status": provisioning, "provisioning_error": error}}

    def test_sync_keeps_only_own_paid_domain_orders(self, monkeypatch, user_id):
        self.stripe_sessions(monkeypatch, [
            self.session("cs_1", user_id, "Firma.de", provisioning="complete"),
            self.session("cs_2", user_id, "offen.de", paid=False),
            self.session("cs_3", 999, "fremd.de", provisioning="complete"),
            {"id": "cs_4", "client_reference_id": str(user_id), "payment_status": "paid", "metadata": {}},
        ])
        logic.sync_domain_orders(user_id)
        assert [item["domain"] for item in logic.get_owned_domains(user_id)] == ["firma.de"]

    def test_best_order_per_domain_and_status_updates(self, monkeypatch, user_id):
        self.stripe_sessions(monkeypatch, [
            self.session("cs_new", user_id, "firma.de", provisioning="failed", error="Billing failure", created=3),
            self.session("cs_old", user_id, "firma.de", provisioning="complete", created=2, project="caf--alt-1"),
            self.session("cs_wait", user_id, "zweite.de", created=1),
        ])
        logic.sync_domain_orders(user_id)
        owned = {item["domain"]: item for item in logic.get_owned_domains(user_id)}
        assert owned["firma.de"]["status"] == "complete" and owned["firma.de"]["project_name"] == "caf--alt-1"
        assert owned["zweite.de"]["status"] == "paid"
        self.stripe_sessions(monkeypatch, [self.session("cs_wait", user_id, "zweite.de", provisioning="complete", created=1)])
        logic.sync_domain_orders(user_id)
        assert {item["domain"]: item["status"] for item in logic.get_owned_domains(user_id)}["zweite.de"] == "complete"

    def test_failed_order_shows_reason(self, monkeypatch, user_id):
        self.stripe_sessions(monkeypatch, [self.session("cs_1", user_id, "firma.de", provisioning="failed", error="INWX domain.create failed (2104): Billing failure")])
        logic.sync_domain_orders(user_id)
        assert logic.get_owned_domains(user_id)[0]["detail"].endswith("Billing failure")

    def test_stripe_outage_keeps_known_domains(self, monkeypatch, user_id):
        self.stripe_sessions(monkeypatch, [self.session("cs_1", user_id, "firma.de", provisioning="complete")])
        logic.sync_domain_orders(user_id)
        monkeypatch.setattr(logic.requests, "get", network_error)
        logic.sync_domain_orders(user_id)
        assert logic.get_owned_domains(user_id)[0]["domain"] == "firma.de"

    def test_publish_to_owned_domain_uses_its_project(self, monkeypatch, user_id, session):
        self.stripe_sessions(monkeypatch, [self.session("cs_1", user_id, "firma.de", provisioning="complete", project="caf--morgenrot-a600b35a")])
        logic.sync_domain_orders(user_id)
        published = []
        monkeypatch.setattr(logic, "publish_website", lambda public_url="": published.append((logic.st.session_state.project_name, public_url)))
        logic.publish_to_owned_domain(user_id, "firma.de")
        assert published == [("caf--morgenrot-a600b35a", "https://www.firma.de")]

    def test_publish_requires_completed_setup(self, monkeypatch, user_id):
        self.stripe_sessions(monkeypatch, [self.session("cs_1", user_id, "firma.de", provisioning="failed")])
        logic.sync_domain_orders(user_id)
        with pytest.raises(ValueError, match="noch nicht eingerichtet"):
            logic.publish_to_owned_domain(user_id, "firma.de")
        with pytest.raises(ValueError, match="noch nicht eingerichtet"):
            logic.publish_to_owned_domain(user_id, "unbekannt.de")


def test_existing_vercel_project_names_stay_unchanged():
    assert logic.safe_project_name("caf--morgenrot-a600b35a") == "caf--morgenrot-a600b35a"
    assert logic.safe_project_name("Café Morgenrot") == "cafe-morgenrot"


class TestExternalDomain:
    """Kunde hat die Domain selbst gekauft und verbindet sie mit seinem Entwurf."""

    @pytest.fixture
    def vercel(self, monkeypatch, session):
        state = {"misconfigured": True, "verified": True, "calls": [], "add_status": 200, "conflict_elsewhere": False}

        def request(method, url, headers=None, json=None, timeout=None):
            path = url.replace("https://api.vercel.com", "")
            state["calls"].append((method, path))
            if path.endswith("/config"):
                return FakeResponse(200, {"misconfigured": state["misconfigured"], "recommendedIPv4": [{"rank": 1, "value": ["76.76.21.21"]}], "recommendedCNAME": [{"rank": 1, "value": "cname.vercel-dns.com."}]})
            if method == "POST" and path.endswith("/domains"):
                state.setdefault("added", []).append(json)
                return FakeResponse(400 if state["conflict_elsewhere"] else state["add_status"], {"error": {"message": "Domain is already in use by another project"}} if state["conflict_elsewhere"] else {})
            if method == "GET" and "/domains/" in path:
                if state["conflict_elsewhere"]:
                    return FakeResponse(404, {})
                verification = [] if state["verified"] else [{"type": "TXT", "domain": "_vercel.firma.de", "value": "vc-domain-verify=abc"}]
                return FakeResponse(200, {"verified": state["verified"], "verification": verification})
            if method == "POST" and path.endswith("/verify"):
                return FakeResponse(200, {})
            raise AssertionError(path)

        monkeypatch.setattr(logic.requests, "request", request)
        published = []

        def publish(public_url=""):
            published.append(session.project_name)
            session.vercel_project_id = "prj_ext"
            session.live_url = public_url

        monkeypatch.setattr(logic, "publish_website", publish)
        session.generated_html = SIMPLE_HTML
        state["published"] = published
        return state

    def test_connect_publishes_draft_and_shows_dns_records(self, vercel, user_id, session):
        result = logic.connect_external_domain(user_id, "https://www.Firma.de/")
        assert len(vercel["published"]) == 1
        assert ("POST", "/v10/projects/prj_ext/domains") in vercel["calls"]
        assert result["connected"] is False
        assert result["records"] == [{"type": "A", "name": "@", "value": "76.76.21.21"}, {"type": "CNAME", "name": "www", "value": "cname.vercel-dns.com"}]
        owned = logic.get_owned_domains(user_id)[0]
        assert owned["domain"] == "firma.de" and owned["status"] == "dns" and owned["vercel_project_id"] == "prj_ext"
        # www.firma.de ist die Hauptadresse; firma.de leitet dauerhaft dorthin weiter.
        assert vercel["added"] == [{"name": "www.firma.de"}, {"name": "firma.de", "redirect": "www.firma.de", "redirectStatusCode": 308}]
        assert session.live_url == "https://www.firma.de"

    def test_check_marks_domain_active_once_dns_is_correct(self, vercel, user_id, session):
        logic.connect_external_domain(user_id, "firma.de")
        assert logic.check_external_domain(user_id, "firma.de") is False
        vercel["misconfigured"] = False
        assert logic.check_external_domain(user_id, "firma.de") is True
        assert logic.get_owned_domains(user_id)[0]["status"] == "complete"
        # Danach funktioniert der Veröffentlichen-Button für diese Domain.
        logic.publish_to_owned_domain(user_id, "firma.de")
        assert session.live_url == "https://www.firma.de"
        assert vercel["published"][-1] == vercel["published"][0]

    def test_already_correct_dns_is_immediately_active(self, vercel, user_id, session):
        vercel["misconfigured"] = False
        assert logic.connect_external_domain(user_id, "firma.de")["connected"] is True
        assert session.live_url == "https://www.firma.de"

    def test_ownership_challenge_is_shown(self, vercel, user_id):
        vercel["verified"] = False
        records = logic.connect_external_domain(user_id, "firma.de")["records"]
        assert {"type": "TXT", "name": "_vercel.firma.de", "value": "vc-domain-verify=abc"} in records

    def test_reconnecting_reuses_the_same_project(self, vercel, user_id):
        logic.connect_external_domain(user_id, "firma.de")
        logic.connect_external_domain(user_id, "firma.de")
        assert vercel["published"][0] == vercel["published"][1]

    @pytest.mark.parametrize(("domain", "message"), [("kein domain", "gültige Domain"), ("", "gültige Domain")])
    def test_invalid_domain(self, vercel, user_id, domain, message):
        with pytest.raises(ValueError, match=message):
            logic.connect_external_domain(user_id, domain)
        assert vercel["published"] == []

    def test_requires_draft(self, vercel, user_id, session):
        session.generated_html = ""
        with pytest.raises(ValueError, match="Entwurf"):
            logic.connect_external_domain(user_id, "firma.de")

    def test_domain_used_by_another_project(self, vercel, user_id):
        vercel["conflict_elsewhere"] = True
        with pytest.raises(ValueError, match="already in use"):
            logic.connect_external_domain(user_id, "firma.de")
