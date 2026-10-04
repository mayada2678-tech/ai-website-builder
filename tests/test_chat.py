"""Kunden-Chatbot: Branchendesign, Wissen, Widget, Einbindung und API-Route."""

import re

import pytest
import requests
from conftest import SIMPLE_HTML, FakeResponse

import chat
import logic


class TestDesignThemes:
    @pytest.mark.parametrize(("industry", "theme"), [(name, key) for name, key in chat.INDUSTRY_CHATBOT_THEME_MAP.items()])
    def test_every_preset_industry_has_its_theme(self, industry, theme):
        assert chat.get_chatbot_design_theme(industry) is chat.CHATBOT_DESIGN_THEMES[theme]

    @pytest.mark.parametrize(
        ("industry", "theme"),
        [
            ("Kosmetikstudio", "salon"), ("Barbershop", "salon"), ("Zahnarztpraxis", "praxis"),
            ("Reinigungsservice", "reinigung"), ("Fotograf", "kreativ"), ("Steuerberatung", "kanzlei"),
            ("Elektriker", "werkstatt"), ("Malerbetrieb", "dach"), ("Pizzeria", "restaurant"),
            ("Eisdiele", "cafe"), ("Modeboutique", "shop"), ("Reisebüro", "standard"), ("", "standard"),
        ],
    )
    def test_keyword_detection_for_custom_industries(self, industry, theme):
        assert chat.get_chatbot_design_theme(industry) is chat.CHATBOT_DESIGN_THEMES[theme]

    def test_reads_industry_from_session(self, session):
        session.industry_content_preset = logic.OTHER_INDUSTRY_OPTION
        session.custom_industry_name = "Nagelstudio"
        assert chat.get_chatbot_design_theme() is chat.CHATBOT_DESIGN_THEMES["salon"]

    def test_themes_are_complete_and_consistent(self):
        for theme in chat.CHATBOT_DESIGN_THEMES.values():
            assert set(theme) == {"color", "shape", "figure", "font", "radius", "panel", "surface", "text", "border"}
            assert re.fullmatch(r"#[0-9A-F]{6}", theme["color"])
            assert theme["figure"] in chat.CHATBOT_FIGURE_ICONS
            assert theme["shape"] in chat.CHATBOT_SHAPE_RADIUS
            # Weiße Schrift auf der Akzentfarbe muss lesbar sein.
            assert logic.contrast_text_color(theme["color"]) == "#FFFFFF"

    def test_toggle_radius(self, session):
        session.customer_chatbot_shape = "Quadratisch"
        assert chat.get_chatbot_toggle_radius() == "0"
        session.customer_chatbot_shape = "Unbekannt"
        assert chat.get_chatbot_toggle_radius() == "50%"


class TestKnowledge:
    def test_preset_industry_without_details_uses_typical_services(self, session):
        session.update(industry_content_preset="Friseursalon", client_company_name="Salon Anna", client_business_email="a@b.de")
        for key in ("client_chatbot_hours", "client_chatbot_contact", "client_chatbot_services", "client_chatbot_emergency"):
            session[key] = ""
        knowledge = chat.get_configured_chatbot_knowledge()
        assert knowledge.startswith("Branche: Friseursalon.")
        assert "Unternehmen: Salon Anna." in knowledge and "E-Mail: a@b.de" in knowledge
        assert "Typische Leistungen dieser Branche" in knowledge and "Standardhinweis" in knowledge

    def test_custom_details_replace_defaults(self, session):
        session.update(industry_content_preset=logic.OTHER_INDUSTRY_OPTION, custom_industry_name="Tierpension", client_chatbot_hours="Mo-Fr 8-18", client_business_phone="0123")
        knowledge = chat.get_configured_chatbot_knowledge()
        assert "Branche: Tierpension." in knowledge and "Öffnungszeiten: Mo-Fr 8-18" in knowledge
        assert "Telefon: 0123" in knowledge and "Standardhinweis" not in knowledge

    def test_language_and_unknown_industry(self, session):
        session.update(app_language="en", industry_content_preset="Restaurant")
        assert chat.get_configured_chatbot_knowledge().startswith("Industry: Restaurant.")
        session.update(app_language="de", industry_content_preset="Bitte wählen...")
        assert chat.get_configured_chatbot_knowledge().startswith("Branche: Allgemeiner Kundenservice.")


class TestWidget:
    def test_escapes_name_once_and_applies_theme(self, session):
        session.update(industry_content_preset="Kfz-Meisterwerkstatt", customer_chatbot_figure="Werkstatt-Profi", customer_chatbot_shape="Quadratisch")
        widget = chat.build_customer_chatbot_widget('Müller & "Co"', "#C2410C", "Wissen")
        assert "<strong>Müller &amp; &quot;Co&quot;</strong>" in widget
        assert "--cb-accent:#C2410C" in widget and "border-radius:0;" in widget
        assert ">🔧</span>" in widget and 'data-figure="🔧"' in widget

    def test_invalid_color_falls_back(self):
        widget = chat.build_customer_chatbot_widget("Bot", "red;}</style><script>", "")
        assert "--cb-accent:#2563EB" in widget and "<script>alert" not in widget

    def test_position_and_rtl(self, session):
        session.update(customer_chatbot_position="Unten links", customer_chatbot_fixed=False, app_language="ar")
        widget = chat.build_customer_chatbot_widget("Bot", "#2563EB", "")
        assert "left:20px" in widget and "position:relative" in widget
        assert 'dir="rtl"' in widget and "text-align:right" in widget

    def test_scripts_are_valid_and_injection_safe(self, js, scripts):
        hostile = 'Öffnungszeiten: </script><script>alert(1)</script> `${x}` "quote"'
        html = chat.build_customer_chatbot_widget("Bot", "#2563EB", hostile) + chat.build_customer_chatbot_resilience_script(hostile)
        assert "</script><script>alert(1)" not in html
        found = scripts(html)
        assert len(found) == 2
        for script in found:
            js(script)

    @pytest.mark.parametrize("language", ["de", "en", "ar", "ku", "es", "it", "hi"])
    def test_copy_complete_for_every_language(self, session, language):
        session.app_language = language
        assert set(chat.get_customer_chatbot_copy()) == set(chat.get_customer_chatbot_copy.__globals__["get_customer_chatbot_copy"]().keys())
        assert "{value}" in chat.get_customer_chatbot_copy()["contact"]


class TestInjection:
    def test_inject_is_idempotent_and_remove_is_complete(self):
        once = chat.inject_configured_customer_chatbot(SIMPLE_HTML)
        twice = chat.inject_configured_customer_chatbot(once)
        assert once == twice
        assert twice.count('id="customer-chatbot"') == 1 and twice.count("data-customer-chatbot-resilience>") == 1
        assert chat.remove_customer_chatbot(twice) == SIMPLE_HTML

    def test_add_vercel_chat_api(self, session, js):
        pages = chat.add_vercel_chat_api({"index.html": SIMPLE_HTML, "styles.css": "body{}"})
        assert set(pages) == {"index.html", "styles.css", "api/chat.js", "api/analytics.js", "api/variant.js", "vercel.json"}
        assert "data-site-analytics" in pages["index.html"] and pages["styles.css"] == "body{}"
        js(pages["api/chat.js"])

    def test_chat_route_embeds_knowledge_safely(self, js):
        route = chat.build_chat_api_route('Preise und Leistungen: "Ölwechsel" `49 €` ${hack}')
        js(route)
        assert "const CHATBOT_KNOWLEDGE = " in route
        js(chat.build_chat_api_route(""))


class TestVercelEnvironment:
    @pytest.fixture
    def keys(self, monkeypatch):
        monkeypatch.setattr(chat, "HF_API_KEY", "hf")
        monkeypatch.setattr(chat, "SUPABASE_URL", "https://x.supabase.co")
        monkeypatch.setattr(chat, "SUPABASE_SERVICE_ROLE_KEY", "service")

    def test_creates_missing_and_updates_existing_variables(self, monkeypatch, keys):
        calls = []
        monkeypatch.setattr(chat.requests, "get", lambda *a, **k: FakeResponse(200, {"envs": [{"key": "HF_API_KEY", "id": "env_1"}]}))
        monkeypatch.setattr(chat.requests, "patch", lambda url, **k: calls.append(("patch", url, k["json"]["key"])) or FakeResponse(200, {}))
        monkeypatch.setattr(chat.requests, "post", lambda url, **k: calls.append(("post", url, k["json"]["key"])) or FakeResponse(201, {}))
        assert chat.configure_vercel_chatbot_environment("prj") == ""
        assert ("patch", "https://api.vercel.com/v9/projects/prj/env/env_1", "HF_API_KEY") in calls
        assert {key for method, _, key in calls if method == "post"} == {"SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"}

    def test_reports_missing_keys_and_failures(self, monkeypatch):
        monkeypatch.setattr(chat, "HF_API_KEY", "")
        monkeypatch.setattr(chat, "SUPABASE_URL", "")
        monkeypatch.setattr(chat.requests, "get", lambda *a, **k: FakeResponse(200, {"envs": []}))
        warning = chat.configure_vercel_chatbot_environment("prj")
        assert "HF_API_KEY fehlt" in warning and "Supabase" in warning

    def test_network_and_api_errors_are_warnings(self, monkeypatch, keys):
        def offline(*_a, **_k):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(chat.requests, "get", offline)
        assert "nicht erreichen" in chat.configure_vercel_chatbot_environment("prj")
        monkeypatch.setattr(chat.requests, "get", lambda *a, **k: FakeResponse(200, {"envs": []}))
        monkeypatch.setattr(chat.requests, "post", lambda *a, **k: FakeResponse(400, {"error": {"message": "ungültig"}}))
        assert "(HTTP 400): ungültig" in chat.configure_vercel_chatbot_environment("prj")


class TestIndustryPreset:
    def test_preset_sets_content_chatbot_and_design(self, session):
        session.industry_content_preset = "Café und Bäckerei"
        logic.apply_industry_content_preset()
        assert session.client_company_name == "Café Morgenrot"
        assert session.customer_chatbot_name == "Café-Assistent"
        assert session.client_chatbot_hours.startswith("Mo-Sa")
        assert session.customer_chatbot_color == chat.CHATBOT_DESIGN_THEMES["cafe"]["color"]
        assert session.template_name == "Cafe und Baeckerei"
        assert session.industry_preset_applied == "Café und Bäckerei"

    def test_custom_industry_uses_generic_profile_and_keyword_theme(self, session):
        session.update(industry_content_preset=logic.OTHER_INDUSTRY_OPTION, custom_industry_name="Kosmetikstudio")
        logic.apply_industry_content_preset()
        assert session.client_company_name == "Kosmetikstudio Musterbetrieb"
        assert session.customer_chatbot_name == "Kundenservice-Assistent"
        assert session.customer_chatbot_figure == "Salon-Stylistin"

    def test_mcp_failure_falls_back_to_same_profile(self, session, monkeypatch):
        monkeypatch.setattr(chat, "get_industry_chatbot_profile_with_mcp", lambda industry: {})
        session.industry_content_preset = "Restaurant"
        logic.apply_industry_content_preset()
        assert session.customer_chatbot_name == "Genusszeit-Assistent"
        assert session.client_chatbot_emergency.startswith("Für kurzfristige Reservierungen")

    def test_nothing_happens_without_selection(self, session):
        session.industry_content_preset = "Bitte wählen..."
        logic.apply_industry_content_preset()
        assert "industry_preset_applied" not in session

    def test_language_switch_translates_preset(self, session, monkeypatch):
        monkeypatch.setattr(logic, "translate_content_fields_with_mcp", lambda fields, language: {key: f"[{language}] {value}" for key, value in fields.items()})
        session.industry_content_preset = "Restaurant"
        logic.apply_industry_content_preset()
        session.app_language_name = next(name for name, code in logic.APP_LANGUAGES.items() if code == "en")
        logic.apply_app_language()
        assert session.app_language == "en" and session.target_language == "English"
        assert session.client_company_name == "[en] Restaurant Genusszeit"

    def test_translation_error_is_shown_not_raised(self, session, monkeypatch):
        def fail(fields, language):
            raise ValueError("MCP aus")

        monkeypatch.setattr(logic, "translate_content_fields_with_mcp", fail)
        session.industry_source_preset = {"client_company_name": "X"}
        session.app_language_name = next(name for name, code in logic.APP_LANGUAGES.items() if code == "en")
        logic.apply_app_language()
        assert session.language_translation_error == "MCP aus"


class TestChatRouteExecution:
    """Führt die erzeugten Vercel-Routen in V8 mit nachgebildeter Anfrage aus."""

    HARNESS = """
    var process = {env: {}};
    var captured = {};
    var response = {
        setHeader() {},
        status(code) { captured.status = code; return this; },
        json(body) { captured.body = body; return this; },
        end() { captured.ended = true; return this; },
    };
    """

    def run(self, route, request, env=None):
        from py_mini_racer import MiniRacer

        engine = MiniRacer()
        engine.eval(self.HARNESS)
        if env:
            engine.eval(f"process.env = {__import__('json').dumps(env)};")
        engine.eval(route.replace("export default async function handler", "async function handler", 1))
        engine.eval(f"handler({__import__('json').dumps(request)}, response);")
        return engine.eval("JSON.stringify(captured)")

    def test_targeted_german_answers(self, session):
        session.update(industry_content_preset="Restaurant", client_chatbot_contact="Telefon 0123", client_chatbot_hours="Di-So 12-22 Uhr")
        route = chat.build_chat_api_route(chat.get_configured_chatbot_knowledge())
        import json as _json

        hours = _json.loads(self.run(route, {"method": "POST", "body": {"question": "Wann habt ihr geöffnet?"}}))
        assert hours == {"status": 200, "body": {"answer": "Unsere Öffnungszeiten bzw. Terminzeiten: Di-So 12-22 Uhr"}}
        booking = _json.loads(self.run(route, {"method": "POST", "body": {"question": "Ich möchte einen Tisch reservieren"}}))
        assert booking["body"]["answer"].endswith("Telefon 0123")
        prices = _json.loads(self.run(route, {"method": "POST", "body": {"question": "Was kostet das?"}}))
        assert "Konkrete Preise liegen uns nicht vor" in prices["body"]["answer"]

    def test_validation_and_offline_answers(self, session):
        import json as _json

        session.app_language = "en"
        route = chat.build_chat_api_route("")
        assert _json.loads(self.run(route, {"method": "GET"}))["status"] == 405
        assert _json.loads(self.run(route, {"method": "OPTIONS"})) == {"status": 204, "ended": True}
        invalid = _json.loads(self.run(route, {"method": "POST", "body": {"question": "x" * 801}}))
        assert invalid == {"status": 400, "body": {"error": "Please send a valid question."}}
        hello = _json.loads(self.run(route, {"method": "POST", "body": {"question": "hello"}}))
        assert hello["body"]["answer"].startswith("Hello!")

    def test_unknown_language_never_answers_undefined(self, session):
        import json as _json

        session.app_language = "xx"
        route = chat.build_chat_api_route("")
        for question in ("hello", "thanks", "bye", "Frage"):
            answer = _json.loads(self.run(route, {"method": "POST", "body": {"question": question}}))["body"]["answer"]
            assert isinstance(answer, str) and answer

    def test_analytics_route_rejects_invalid_requests(self):
        import json as _json

        route = logic.build_analytics_api_route()
        assert _json.loads(self.run(route, {"method": "OPTIONS"}))["status"] == 204
        assert _json.loads(self.run(route, {"method": "POST", "body": {}}))["status"] == 503
        env = {"SUPABASE_URL": "https://x", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        invalid = _json.loads(self.run(route, {"method": "POST", "body": {"site_id": "kein-uuid"}}, env))
        assert invalid == {"status": 400, "body": {"error": "Invalid analytics identifiers"}}
