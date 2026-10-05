"""Oberflächentests mit Streamlit AppTest: die echte App wird Ende-zu-Ende ausgeführt.

Datenbank, Netzwerk und Secrets sind wie in allen Tests isoliert (siehe conftest.py).
"""

import pytest
import streamlit as st
from conftest import PROJECT_ROOT, REAL_SECRETS, REAL_SESSION_STATE
from streamlit.testing.v1 import AppTest

import logic

LANGUAGES = {code: name for name, code in logic.APP_LANGUAGES.items()}


@pytest.fixture
def session(monkeypatch):
    """Überschreibt den Test-Sitzungsstatus: AppTest nutzt den echten von Streamlit."""
    monkeypatch.setattr(st, "session_state", REAL_SESSION_STATE)
    monkeypatch.setattr(st, "secrets", REAL_SECRETS)


def make_app(user_id=None, language="de"):
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=120)
    app.secrets["openai_api_key"] = "test-openai-key"
    app.secrets["vercel_token"] = "test-vercel-token"
    app.session_state["app_language"] = language
    app.session_state["app_language_name"] = LANGUAGES[language]
    if user_id is not None:
        app.session_state["user_id"] = user_id
        app.session_state["user_email"] = "kunde@example.com"
    return app.run()


def assert_no_errors(app):
    assert not app.exception, [exception.value for exception in app.exception]
    assert not app.error, [error.value for error in app.error]


def has_widget(widgets, key):
    return any(widget.key == key for widget in widgets)


def find_button(app, label_part):
    return next(button for button in app.button if label_part in str(button.label))


class TestAuthentication:
    def test_login_page(self):
        app = make_app()
        assert_no_errors(app)
        assert has_widget(app.text_input, "login_email")
        assert has_widget(app.text_input, "registration_email")

    def test_register_then_login(self):
        app = make_app()
        app.text_input(key="registration_email").input("neu@example.com")
        app.text_input(key="registration_password").input("sicheres-passwort")
        app.text_input(key="registration_password_confirmation").input("sicheres-passwort")
        app.button[1].click().run()
        assert_no_errors(app)
        assert app.success[0].value == logic.TRANSLATIONS["de"]["account_created"]

        app.text_input(key="login_email").input("neu@example.com")
        app.text_input(key="login_password").input("sicheres-passwort")
        app.button[0].click().run()
        assert_no_errors(app)
        assert app.session_state["user_email"] == "neu@example.com"
        assert has_widget(app.text_input, "client_company_name")

    def test_wrong_login_and_password_mismatch(self, user_id):
        app = make_app()
        app.text_input(key="login_email").input("kunde@example.com")
        app.text_input(key="login_password").input("falsch")
        app.button[0].click().run()
        assert app.error[0].value == logic.TRANSLATIONS["de"]["invalid_login"]

        app = make_app()
        app.text_input(key="registration_email").input("x@example.com")
        app.text_input(key="registration_password").input("sicheres-passwort")
        app.text_input(key="registration_password_confirmation").input("anders-passwort")
        app.button[1].click().run()
        assert app.error[0].value == logic.TRANSLATIONS["de"]["password_mismatch"]

    def test_missing_secrets_stop_the_app(self, monkeypatch):
        monkeypatch.setattr(logic, "OPENAI_API_KEY", None)
        app = make_app()
        assert "API-Schlüssel fehlen" in app.error[0].value
        assert not has_widget(app.text_input, "login_email")


class TestWorkspace:
    @pytest.mark.parametrize("language", sorted(LANGUAGES))
    def test_workspace_renders_in_every_language(self, user_id, language):
        app = make_app(user_id, language)
        assert_no_errors(app)
        assert len(app.tabs) >= 4
        assert has_widget(app.text_input, "client_company_name")

    def test_expired_trial_shows_payment_hint(self, user_id, database):
        import sqlite3

        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE users SET created_at = '2000-01-01T00:00:00+00:00'")
        app = make_app(user_id)
        assert not app.exception
        assert any("Testphase ist abgelaufen" in warning.value for warning in app.warning)

    def test_industry_preset_fills_form_and_chatbot(self, user_id):
        app = make_app(user_id)
        select = next(box for box in app.selectbox if box.key and box.key.startswith("industry_content_preset_"))
        select.set_value("Physiotherapie-Praxis").run()
        app.button(key="apply_industry_content_preset").click().run()
        assert_no_errors(app)
        assert app.session_state["client_company_name"] == "Praxis für Physiotherapie und Bewegung"
        assert app.session_state["customer_chatbot_figure"] == "Praxis-Begleitung"
        assert app.text_input(key="client_company_name").value == "Praxis für Physiotherapie und Bewegung"

    def test_adopt_template_and_edit_draft(self, user_id):
        app = make_app(user_id)
        select = next(box for box in app.selectbox if box.key and box.key.startswith("industry_content_preset_"))
        select.set_value("Kfz-Meisterwerkstatt").run()
        app.button(key="apply_industry_content_preset").click().run()
        app.text_input(key="client_business_email").input("info@werkstatt.de").run()
        find_button(app, "Kundendaten").click().run()
        assert_no_errors(app)
        html = app.session_state["generated_html"]
        assert "Kfz-Meisterbetrieb Schmidt" in html and html.count('id="customer-chatbot"') == 1
        assert "🔧" in html
        # Der Editorbereich für die erstellte Website wird ohne Fehler aufgebaut.
        assert has_widget(app.text_area, "html_editor")

    def test_customer_service_request(self, user_id):
        app = make_app(user_id)
        app.text_input(key="support_subject").input("Vorschau lädt nicht")
        app.text_area(key="support_description").input("Die Vorschau bleibt nach dem Klick leer.")
        next(button for button in app.button if "senden" in str(button.label).lower()).click().run()
        assert_no_errors(app)
        assert logic.get_support_requests(user_id)[0][3] == "Vorschau lädt nicht"

    def test_customer_service_validation(self, user_id):
        app = make_app(user_id)
        app.text_input(key="support_subject").input("ab")
        next(button for button in app.button if "senden" in str(button.label).lower()).click().run()
        assert app.error and logic.get_support_requests(user_id) == []

    def test_save_and_list_draft_in_sidebar(self, user_id):
        logic.save_website(user_id, "Alte Version", "<!doctype html><html><body>alt</body></html>", "", "site-1")
        app = make_app(user_id)
        assert_no_errors(app)
        draft = next(expander for expander in app.sidebar.expander if expander.label == "Alte Version")
        draft.button[0].click().run()
        assert_no_errors(app)
        assert "alt" in app.session_state["generated_html"]
        assert app.session_state["generated_html"].count('id="customer-chatbot"') <= 1

        draft = next(expander for expander in app.sidebar.expander if expander.label == "Alte Version")
        draft.button[1].click().run()
        assert_no_errors(app)
        assert logic.get_websites(user_id) == []


def create_draft(app):
    select = next(box for box in app.selectbox if box.key and box.key.startswith("industry_content_preset_"))
    select.set_value("Restaurant").run()
    app.button(key="apply_industry_content_preset").click().run()
    app.text_input(key="client_business_email").input("info@genuss.de").run()
    find_button(app, "Kundendaten").click().run()
    assert_no_errors(app)
    return app


class TestEditing:
    def test_success_message_survives_rerun(self, user_id):
        app = create_draft(make_app(user_id))
        assert any("Kundendaten übernommen" in toast.value for toast in app.toast)

    def test_direct_text_replacement(self, user_id):
        app = create_draft(make_app(user_id))
        app.text_input(key="direct_previous_text").input("Restaurant Genusszeit")
        app.text_area(key="direct_edited_text").input("Trattoria Sole")
        app.button(key="apply_direct_text").click().run()
        assert_no_errors(app)
        assert "Trattoria Sole" in app.session_state["generated_html"]
        assert any("Textstelle" in toast.value for toast in app.toast)

    def test_unknown_text_shows_error(self, user_id):
        app = create_draft(make_app(user_id))
        app.text_input(key="direct_previous_text").input("Gibt es nicht")
        app.button(key="apply_direct_text").click().run()
        assert not app.exception and "nicht gefunden" in app.error[0].value

    def test_offer_page_and_button_target(self, user_id):
        app = create_draft(make_app(user_id))
        app.text_input(key="offer_page_name").input("Mittagsmenü")
        app.button(key="create_offer_page").click().run()
        assert 'id="angebote"' in app.session_state["generated_html"]
        app.button(key="create_offer_page").click().run()
        assert any("bereits vorhanden" in warning.value for warning in app.warning)

        app.radio(key="direct_button_target_type").set_value("Angebots-Unterseite öffnen")
        app.button(key="apply_direct_button_target").click().run()
        assert_no_errors(app)
        assert '<a class="button" href="#angebote">' in app.session_state["generated_html"]

    def test_mcp_tools(self, user_id):
        app = create_draft(make_app(user_id))
        app.button(key="mcp_insert_section").click().run()
        assert_no_errors(app)
        assert 'id="kundenbewertungen"' in app.session_state["generated_html"]
        app.button(key="mcp_optimize_seo").click().run()
        assert_no_errors(app)
        assert 'name="description"' in app.session_state["generated_html"]
        assert app.session_state["generated_html"].count('id="customer-chatbot"') == 1

    def test_html_editor(self, user_id):
        app = create_draft(make_app(user_id))
        app.text_area(key="html_editor").input("kein html")
        app.button(key="apply_html_editor_preview").click().run()
        assert not app.exception and app.warning
        app.text_area(key="html_editor").input("<!doctype html><html><body>Neu</body></html>")
        app.button(key="apply_html_editor_preview").click().run()
        assert app.session_state["generated_html"] == "<!doctype html><html><body>Neu</body></html>"

    def test_ai_edit_with_fake_model(self, user_id, fake_openai):
        app = create_draft(make_app(user_id))
        fake_openai.replies["chat"] = "<!doctype html><html><body><h1>KI-Version</h1></body></html>"
        app.text_area(key="content_editor_request").input("Kürzer formulieren")
        app.button(key="apply_content_editor_request").click().run()
        assert_no_errors(app)
        assert "KI-Version" in app.session_state["generated_html"]
        assert app.session_state["generated_html"].count('id="customer-chatbot"') == 1

    def test_ai_failure_is_reported(self, user_id, fake_openai):
        app = create_draft(make_app(user_id))
        fake_openai.replies["error"] = RuntimeError("Timeout")
        app.text_area(key="design_editor_request").input("Dunkler")
        app.button(key="apply_design_editor_request").click().run()
        assert not app.exception and any("nicht erreichbar" in error.value for error in app.error)


class TestPublishing:
    def test_zip_download_is_prepared(self, user_id):
        app = create_draft(make_app(user_id))
        app.button(key="generate_chatbot_website_zip").click().run()
        assert_no_errors(app)
        assert app.session_state["finished_website_zip"][:2] == b"PK"

    def test_publish_failure_shows_message(self, user_id, monkeypatch):
        import requests

        def offline(*_a, **_k):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(logic.requests, "post", offline)
        app = create_draft(make_app(user_id))
        app.button(key="publish_from_domain_center").click().run()
        assert not app.exception
        assert any("nicht zu Vercel hochgeladen" in error.value for error in app.error)

    def test_load_published_website_in_manage_tab(self, user_id, monkeypatch):
        from conftest import SIMPLE_HTML, FakeResponse

        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, text=SIMPLE_HTML, url="https://firma.de/"))
        app = make_app(user_id)
        app.text_input(key="manage_live_url").input("firma.de")
        find_button(app, logic.PUBLISH_COPY["de"]["load_button"]).click().run()
        assert_no_errors(app)
        assert app.session_state["live_url"] == "https://firma.de/"
        assert "Willkommen" in app.session_state["generated_html"]

    def test_transformer_without_key_shows_error(self, user_id, monkeypatch):
        monkeypatch.setattr(logic, "HF_API_KEY", "")
        app = make_app(user_id)
        app.button(key="transformer_test_submit").click().run()
        assert not app.exception and any("HF_API_KEY" in error.value for error in app.error)


def configure(monkeypatch, **values):
    """Setzt Konfigurationswerte in logic und gui (gui importiert sie direkt)."""
    import gui

    for name, value in values.items():
        monkeypatch.setattr(logic, name, value)
        if hasattr(gui, name):
            monkeypatch.setattr(gui, name, value)


class TestMoreFlows:
    def test_free_draft_with_ai(self, user_id, fake_openai):
        fake_openai.replies["chat"] = "<!doctype html><html><head></head><body><h1>Freier Entwurf</h1></body></html>"
        app = make_app(user_id)
        app.segmented_control(key="creation_mode").set_value("Freier Entwurf").run()
        app.text_input(key="client_company_name").input("Studio Nord").run()
        app.text_input(key="client_business_email").input("hallo@studio-nord.de").run()
        app.text_area(key="creation_description").input("Fotostudio in Hamburg").run()
        app.button(key="create_website").click().run()
        assert_no_errors(app)
        html = app.session_state["generated_html"]
        assert "Freier Entwurf" in html and "mailto:hallo@studio-nord.de" in html
        assert "Fotostudio in Hamburg" in fake_openai.calls[0]["messages"][1]["content"]

    def test_existing_template_from_url(self, user_id, monkeypatch):
        from conftest import SIMPLE_HTML, FakeResponse

        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, text=SIMPLE_HTML, url="https://vorlage.de/"))
        app = make_app(user_id)
        app.segmented_control(key="creation_mode").set_value("Bestehenden Entwurf anpassen").run()
        app.button(key="load_existing_template_url").click().run()
        assert any("öffentliche Website-Adresse" in warning.value for warning in app.warning)
        app.text_input(key="existing_template_url").input("vorlage.de")
        app.button(key="load_existing_template_url").click().run()
        assert_no_errors(app)
        assert app.session_state["project_name"] == "vorlage"
        assert "Willkommen" in app.session_state["generated_html"]

    def test_live_editor_requires_instructions(self, user_id, fake_openai):
        app = create_draft(make_app(user_id))
        app.button(key="update_live_editor_section").click().run()
        assert any("beschreiben" in warning.value for warning in app.warning)
        assert fake_openai.calls == []
        app.text_area(key="editor_instructions").input("Hintergrund heller")
        app.button(key="update_live_editor_section").click().run()
        assert_no_errors(app)
        assert "Hintergrund heller" in fake_openai.calls[0]["messages"][1]["content"]

    def test_expired_trial_payment_flow(self, user_id, database, monkeypatch):
        import sqlite3

        from conftest import FakeResponse

        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE users SET created_at = '2000-01-01T00:00:00+00:00'")
        configure(monkeypatch, STRIPE_SECRET_KEY="sk", STRIPE_PRICE_ID="price", STRIPE_SUCCESS_URL="https://app.example/")
        monkeypatch.setattr(logic.requests, "post", lambda *a, **k: FakeResponse(200, {"url": "https://checkout.stripe.com/x"}))
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": []}))
        app = make_app(user_id)
        app.button(key="open_stripe_checkout").click().run()
        assert not app.exception
        assert app.session_state["stripe_checkout_url"] == "https://checkout.stripe.com/x"

    def test_admin_analytics_section(self, user_id, monkeypatch):
        configure(monkeypatch, SUPPORT_ADMIN_EMAIL="kunde@example.com", SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="")
        app = make_app(user_id)
        assert_no_errors(app)
        assert any("Supabase ist noch nicht konfiguriert" in warning.value for warning in app.warning)

    def test_admin_sees_support_inbox(self, user_id, monkeypatch):
        configure(monkeypatch, SUPPORT_ADMIN_EMAIL="kunde@example.com")
        logic.save_support_request(user_id, "Fehler", "Vorschau", "Betreff Admin", "Beschreibung lang genug", "")
        app = make_app(user_id)
        assert_no_errors(app)

    def test_custom_domain_check_and_checkout(self, user_id, monkeypatch):
        """Der Entwurf wird vor der Zahlung veröffentlicht; die Bestellung nennt genau dieses Projekt."""
        import gui
        from conftest import FakeResponse

        configure(monkeypatch, INWX_USERNAME="user", INWX_PASSWORD="pass", STRIPE_SECRET_KEY="sk", STRIPE_PRICE_ID="price", STRIPE_SUCCESS_URL="https://app.example/", HF_API_KEY="")
        monkeypatch.setattr(gui, "check_domain_with_registrar", lambda domain: {"domain": "firma.de", "available": True, "status": "free"})
        steps = []

        def post(url, headers=None, json=None, data=None, timeout=None, auth=None):
            if url.endswith("/v2/files"):
                return FakeResponse(200, {})
            if "deployments" in url:
                steps.append(("deploy", json["name"]))
                return FakeResponse(200, {"id": "dpl_1", "url": "firma.vercel.app", "projectId": "prj_1"})
            if url.endswith("/env"):
                return FakeResponse(201, {})
            if "stripe.com" in url:
                steps.append(("checkout", dict(data)))
                return FakeResponse(200, {"url": "https://checkout.stripe.com/domain"})
            raise AssertionError(url)

        def get(url, **_kwargs):
            if url.endswith("/env"):
                return FakeResponse(200, {"envs": []})
            return FakeResponse(200, {"readyState": "READY", "url": "firma.vercel.app"})

        monkeypatch.setattr(logic.requests, "post", post)
        monkeypatch.setattr(logic.requests, "get", get)
        monkeypatch.setattr(logic.requests, "patch", lambda *a, **k: FakeResponse(200, {}))
        monkeypatch.setattr("chat.requests.get", get)
        monkeypatch.setattr("chat.requests.post", post)
        app = create_draft(make_app(user_id))
        app.radio(key="domain_type").set_value("Eigene Domain verbinden").run()
        app.text_input(key="custom_domain").input("www.firma.de").run()
        app.button(key="check_custom_domain_with_mcp").click().run()
        assert_no_errors(app)
        app.button(key="buy_and_publish_custom_domain").click().run()
        assert_no_errors(app)

        assert [step for step, _ in steps] == ["deploy", "checkout"]
        project_name = steps[0][1]
        checkout = steps[1][1]
        assert checkout["metadata[vercel_project_id]"] == "prj_1"
        assert checkout["metadata[project_name]"] == project_name
        saved = logic.load_website(user_id, int(checkout["metadata[website_id]"]))
        assert saved is not None and "Genusszeit" in saved[1]
        assert app.session_state["deployment_id"] == "dpl_1"
        assert app.session_state["stripe_checkout_url"] == "https://checkout.stripe.com/domain"
        # Kein zweiter Kauf derselben Domain: nach dem Neuladen ist der Button weg,
        # die vorbereitete Zahlung bleibt, und es wird nichts erneut veröffentlicht.
        app.run()
        assert not has_widget(app.button, "buy_and_publish_custom_domain")
        assert any("bitte schließen sie jetzt die zahlung ab" in message.value.lower() for message in app.success)
        assert [step for step, _ in steps] == ["deploy", "checkout"]

    def test_unavailable_registrar_shows_error(self, user_id, monkeypatch):
        import gui

        import domain_provisioning

        configure(monkeypatch, INWX_USERNAME="user", INWX_PASSWORD="pass")

        def unavailable(domain):
            raise domain_provisioning.ProvisioningError("INWX domain.check is unavailable")

        monkeypatch.setattr(gui, "check_domain_with_registrar", unavailable)
        app = create_draft(make_app(user_id))
        app.radio(key="domain_type").set_value("Eigene Domain verbinden").run()
        app.text_input(key="custom_domain").input("firma.de").run()
        app.button(key="check_custom_domain_with_mcp").click().run()
        assert not app.exception and any("unavailable" in error.value for error in app.error)


class TestCheckoutReturnInApp:
    def test_premium_customer_gets_second_domain_order_confirmed(self, user_id, monkeypatch):
        from conftest import SIMPLE_HTML, FakeResponse

        logic.activate_premium(user_id)
        website_id = logic.save_website(user_id, "zweite.de", SIMPLE_HTML, "zweite.de", "site")
        configure(monkeypatch, STRIPE_SECRET_KEY="sk_test")
        metadata = {"domain": "zweite.de", "vercel_project_id": "prj_2", "project_name": "zweite-x1", "website_id": str(website_id), "provisioning_status": "complete", "provisioned_domain": "zweite.de"}
        monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"payment_status": "paid", "client_reference_id": str(user_id), "metadata": metadata}))
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=120)
        app.secrets["openai_api_key"] = "x"
        app.secrets["vercel_token"] = "y"
        app.query_params["checkout_session_id"] = "cs_2"
        app.session_state["user_id"] = user_id
        app.session_state["user_email"] = "kunde@example.com"
        app.run()
        assert not app.exception
        assert app.session_state["project_name"] == "zweite-x1"
        assert "Willkommen" in app.session_state["generated_html"]
        assert app.session_state["live_url"] == "https://zweite.de"


class TestDomainOffer:
    def open_domain_section(self, user_id, monkeypatch):
        import gui

        configure(monkeypatch, INWX_USERNAME="user", INWX_PASSWORD="pass")
        monkeypatch.setattr(gui, "check_domain_with_registrar", lambda domain: {"domain": "firma.de", "available": True, "status": "free"})
        app = create_draft(make_app(user_id))
        app.radio(key="domain_type").set_value("Eigene Domain verbinden").run()
        app.text_input(key="custom_domain").input("firma.de").run()
        app.button(key="check_custom_domain_with_mcp").click().run()
        return app

    def test_premium_customer_sees_one_time_domain_price(self, user_id, monkeypatch):
        logic.activate_premium(user_id)
        app = self.open_domain_section(user_id, monkeypatch)
        label = app.button(key="buy_and_publish_custom_domain").label
        assert "firma.de" in label and "15,00 €" in label and "Premium-Abo" not in label
        assert any("Kein weiteres Abo" in caption.value for caption in app.caption)

    def test_new_customer_sees_subscription_offer(self, user_id, monkeypatch):
        app = self.open_domain_section(user_id, monkeypatch)
        assert "Premium-Abo (Domain inklusive)" in app.button(key="buy_and_publish_custom_domain").label


def test_no_second_deployment_after_domain_purchase(user_id, monkeypatch):
    from conftest import SIMPLE_HTML, FakeResponse

    website_id = logic.save_website(user_id, "firma.de", SIMPLE_HTML, "firma.de", "site")
    configure(monkeypatch, STRIPE_SECRET_KEY="sk_test")
    metadata = {"domain": "firma.de", "vercel_project_id": "prj_1", "project_name": "firma-x1", "website_id": str(website_id), "provisioning_status": "processing"}
    monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"payment_status": "paid", "client_reference_id": str(user_id), "metadata": metadata}))
    monkeypatch.setattr(logic.time, "sleep", lambda _s: None)
    monkeypatch.setattr(logic, "wait_for_domain_provisioning", lambda session_id: {"status": "pending", "domain": ""})
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=120)
    app.secrets["openai_api_key"] = "x"
    app.secrets["vercel_token"] = "y"
    app.query_params["checkout_session_id"] = "cs_1"
    app.query_params["publish"] = "1"
    app.session_state["user_id"] = user_id
    app.session_state["user_email"] = "kunde@example.com"
    app.run()
    # Ein Veröffentlichungsversuch würde am gesperrten Netzwerk scheitern und einen Fehler zeigen.
    assert not app.exception and not app.error
    assert app.session_state["publish_after_checkout"] is False
    assert app.session_state["project_name"] == "firma-x1"


def test_owned_domain_publish_button(user_id, monkeypatch):
    from conftest import FakeResponse

    configure(monkeypatch, STRIPE_SECRET_KEY="sk_test")
    sessions = [{"id": "cs_1", "client_reference_id": str(user_id), "payment_status": "paid", "created": 1,
                 "metadata": {"domain": "firma.de", "project_name": "firma-ab12", "vercel_project_id": "prj_1", "provisioning_status": "complete"}}]
    monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": sessions}))
    published = []
    monkeypatch.setattr(logic, "publish_website", lambda: published.append(logic.st.session_state.project_name))
    app = create_draft(make_app(user_id))
    assert_no_errors(app)
    button = app.button(key="publish_to_domain_firma.de")
    assert "firma.de" in button.label and not button.disabled
    button.click().run()
    assert_no_errors(app)
    assert published == ["firma-ab12"] and app.session_state["live_url"] == "https://firma.de"


def test_connect_external_domain_in_app(user_id, monkeypatch):
    from conftest import FakeResponse

    def request(method, url, **_kwargs):
        if url.endswith("/config"):
            return FakeResponse(200, {"misconfigured": True, "recommendedIPv4": [{"value": ["76.76.21.21"]}], "recommendedCNAME": [{"value": "cname.vercel-dns.com."}]})
        return FakeResponse(200, {"verified": True})

    monkeypatch.setattr(logic.requests, "request", request)
    monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": []}))
    monkeypatch.setattr(logic, "publish_website", lambda: logic.st.session_state.__setitem__("vercel_project_id", "prj_ext"))
    app = create_draft(make_app(user_id))
    app.radio(key="domain_type").set_value("Bereits gekaufte Domain verbinden").run()
    app.text_input(key="external_domain").input("firma.de").run()
    app.button(key="connect_external_domain").click().run()
    assert_no_errors(app)
    app.run()
    assert has_widget(app.button, "check_dns_firma.de")
    values = [code.value for code in app.code]
    assert "76.76.21.21" in values and "cname.vercel-dns.com" in values
