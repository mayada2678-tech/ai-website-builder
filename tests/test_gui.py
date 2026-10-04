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
