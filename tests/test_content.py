"""HTML-Werkzeuge, Dokumentquellen, Vorlagen, KI-Erstellung und Export."""

import io
import zipfile
from datetime import datetime
from types import SimpleNamespace

import pytest
from conftest import SIMPLE_HTML, FakeUpload

import logic


class TestHtmlHelpers:
    def test_clean_html_removes_markdown_fences(self):
        assert logic.clean_html("```html\n<html></html>\n```") == "<html></html>"
        assert logic.clean_html("```HTML<html></html>```") == "<html></html>"

    def test_require_complete_html(self):
        assert logic.require_complete_html("```html\n" + SIMPLE_HTML + "```") == SIMPLE_HTML
        with pytest.raises(ValueError, match="kein HTML"):
            logic.require_complete_html("  ")
        with pytest.raises(ValueError, match="keine vollständige"):
            logic.require_complete_html("<div>Teil</div>")

    def test_ensure_customer_email_replaces_and_appends(self):
        html = '<html><body><a href="mailto:alt@beispiel.de">alt@beispiel.de</a></body></html>'
        result = logic.ensure_customer_email(html, " Info@Firma.de ")
        assert "alt@beispiel.de" not in result
        assert result.count("mailto:info@firma.de") == 1
        appended = logic.ensure_customer_email("<html><body></body></html>", "info@firma.de")
        assert '<a href="mailto:info@firma.de">info@firma.de</a></p></body>' in appended

    def test_replace_first_image_escapes_attributes(self):
        result = logic.replace_first_image_source(SIMPLE_HTML, "neu.png", 'Firma "Best" & Co')
        assert '<img src="neu.png" alt="Firma &quot;Best&quot; &amp; Co">' in result
        assert "alt.png" not in result
        placeholder = '<html><body><div class="image-placeholder">Bild</div></body></html>'
        assert '<img src="b.png"' in logic.replace_first_image_source(placeholder, "b.png", "x")
        assert logic.replace_first_image_source("<html><body></body></html>", "c.png", "x").endswith('<img src="c.png" alt="x"></body></html>')

    def test_replace_visible_text(self):
        assert "<h1>Hallo &amp; Tschüss</h1>" in logic.replace_visible_text(SIMPLE_HTML, "Willkommen", "Hallo & Tschüss")
        with pytest.raises(ValueError, match="bisherigen Text"):
            logic.replace_visible_text(SIMPLE_HTML, " ", "x")
        with pytest.raises(ValueError, match="nicht gefunden"):
            logic.replace_visible_text(SIMPLE_HTML, "Gibt es nicht", "x")

    @pytest.mark.parametrize(("color", "light"), [("#FFFFFF", True), ("#000000", False), ("#2563EB", False), ("#FDE68A", True), ("rot", False), ("#FFF", False)])
    def test_color_helpers(self, color, light):
        assert logic.is_light_color(color) is light
        assert logic.contrast_text_color(color) == ("#111827" if light else "#FFFFFF")


class TestProjectNames:
    @pytest.mark.parametrize(("name", "expected"), [("Firma GmbH & Co", "firma-gmbh-co"), ("Haardesign und Wohlfühlen", "haardesign-und-wohlfuehlen"), ("Café Straße", "cafe-strasse"), ("---", "ai-website-builder"), ("x" * 150, "x" * 100)])
    def test_safe_project_name(self, name, expected):
        assert logic.safe_project_name(name) == expected

    def test_deployment_name_is_unique_and_valid(self, session):
        session.client_company_name = "Café Müller"
        first, second = logic.create_deployment_project_name(), logic.create_deployment_project_name()
        assert first != second
        assert first.startswith("cafe-mueller-") and len(first) <= 97

    @pytest.mark.parametrize(("url", "expected"), [("https://meine-seite.vercel.app/x", "meine-seite"), ("firma.de", "firma"), ("", "ai-website-builder")])
    def test_project_name_from_url(self, url, expected):
        assert logic.get_project_name_from_url(url) == expected


class TestImagesAndPreview:
    def test_save_uploaded_image(self, session):
        name = logic.save_uploaded_image(FakeUpload("logo.JPG", b"bild"), "Über uns!")
        assert name == "ber-uns-bild.jpg"
        assert session.assets[name]["mime_type"] == "image/jpeg"
        assert logic.save_uploaded_image(FakeUpload("x.gif", b"g", "image/gif"), "") == "bild-bild.png"
        with pytest.raises(ValueError, match="Bild"):
            logic.save_uploaded_image(None, "Hero")

    def test_preview_embeds_assets_and_hides_chatbot(self, session):
        session.assets = {"logo.png": {"base64": "QUJD", "mime_type": "image/png"}}
        html = logic.queue_html_update.__module__ and SIMPLE_HTML.replace("alt.png", "logo.png")
        logic.queue_html_update(html)
        preview = logic.create_preview_html(session.generated_html)
        assert "data:image/png;base64,QUJD" in preview
        assert "customer-chatbot" not in preview
        assert "customer-chatbot" in logic.create_preview_html(session.generated_html, include_customer_chatbot=True)


class TestDocuments:
    def test_text_document(self):
        text = logic.extract_uploaded_document_text(FakeUpload("info.txt", "Zeile   eins\n\n\n\nZeile\tzwei".encode()))
        assert text == "Zeile eins\n\nZeile zwei"

    @pytest.mark.parametrize(
        ("upload", "message"),
        [
            (FakeUpload("a.txt", b"\xff\xfe\xfa"), "UTF-8"),
            (FakeUpload("a.txt", b"   \n "), "keinen auslesbaren"),
            (FakeUpload("a.pdf", b"kein pdf"), "PDF"),
            (FakeUpload("a.txt", b"x" * (10 * 1024 * 1024 + 1)), "10 MB"),
        ],
    )
    def test_invalid_documents(self, upload, message):
        with pytest.raises(ValueError, match=message):
            logic.extract_uploaded_document_text(upload)

    def test_chunks_respect_size_and_keep_all_words(self):
        words = [f"wort{index}" for index in range(2000)]
        text = "\n".join(" ".join(words[i:i + 37]) for i in range(0, 2000, 37)) + "\n" + "x" * 3000
        chunks = logic.chunk_document_text(text, chunk_size=500, overlap=80)
        assert all(0 < len(chunk) <= 500 for chunk in chunks)
        joined = " ".join(chunks)
        assert all(word in joined for word in words)
        assert logic.chunk_document_text("") == []

    def test_retrieval_ranks_by_similarity(self, fake_openai):
        def embeddings(model, input):
            vectors = [[1.0, 0.0] if "Kfz" in text or text.startswith("Firma") else [0.0, 1.0] for text in input]
            return SimpleNamespace(data=[SimpleNamespace(embedding=vector) for vector in vectors])

        fake_openai.client.embeddings.create = embeddings
        files = [FakeUpload("auto.txt", b"Kfz Reparatur und Reifen"), FakeUpload("kochen.txt", b"Rezepte fuer Kuchen")]
        context, sources = logic.retrieve_document_context(files, "Firma Kfz", limit=1)
        assert context.startswith("QUELLE 1 (auto.txt)") and sources == ["auto.txt"]
        assert logic.retrieve_document_context([], "x") == ("", [])

    def test_retrieval_errors(self, fake_openai):
        def failing(**_kwargs):
            raise RuntimeError("API down")

        fake_openai.client.embeddings.create = failing
        with pytest.raises(ValueError, match="nicht ausgewertet"):
            logic.retrieve_document_context([FakeUpload("a.txt", b"Text")], "x")
        too_many = [FakeUpload(f"{i}.txt", ("Absatz " * 300).encode()) for i in range(130)]
        with pytest.raises(ValueError, match="zu umfangreich"):
            logic.retrieve_document_context(too_many, "x")


class TestTexts:
    def test_translation_helpers_fall_back(self, session):
        session.app_language = "de"
        assert logic.t("login") == "Anmelden"
        assert logic.t("unbekannter_schluessel") == "unbekannter_schluessel"
        session.app_language = "xx"
        assert logic.t("login") == "Anmelden"
        assert logic.workspace_copy() is logic.WORKSPACE_COPY["en"]
        assert logic.publish_copy() is logic.PUBLISH_COPY["en"]

    @pytest.mark.parametrize("language", ["de", "en", "ar", "ku", "es", "it", "hi"])
    def test_template_and_form_copy_complete_for_every_language(self, session, language):
        session.app_language = language
        copy = logic.get_template_preview_copy(language)
        assert set(copy["pages"]) == {"leistungen", "angebote", "projekte", "ueber_uns", "kontakt"}
        assert all(len(cards) == 3 for _, _, cards in copy["pages"].values())
        form = logic.get_creation_form_copy()
        assert len(form["labels"]) == 16 and len(form["sections"]) == 6 and len(form["placements"]) == 4


class TestSessionHelpers:
    def test_initialize_does_not_overwrite_and_copies_defaults(self, session):
        session.project_name = "eigenes-projekt"
        logic.initialize_session_state()
        assert session.project_name == "eigenes-projekt"
        session.assets["x"] = 1
        assert logic.DEFAULT_STATE["assets"] == {}
        assert session.app_language_name == "Deutsch" or session.app_language_name in logic.APP_LANGUAGES

    def test_pending_html_is_applied_once(self, session):
        session.pending_html = SIMPLE_HTML
        logic.apply_pending_html_update()
        assert session.generated_html == session.html_editor == SIMPLE_HTML and session.pending_html == ""

    def test_background_preset(self, session):
        name = next(iter(logic.BACKGROUND_PRESET_COLORS))
        session.template_background_preset = name
        logic.apply_background_preset()
        assert session.template_background_color == logic.BACKGROUND_PRESET_COLORS[name]

    def test_queue_html_update_injects_single_chatbot(self, session):
        session.site_pages = {"kontakt.html": SIMPLE_HTML}
        logic.queue_html_update(SIMPLE_HTML)
        assert set(session.site_pages) == {"kontakt.html", "index.html"}
        logic.queue_html_update(session.generated_html, reset_site_pages=True)
        assert set(session.site_pages) == {"index.html"}
        assert session.generated_html.count('id="customer-chatbot"') == 1


class TestTemplates:
    def build(self, **overrides):
        values = dict(
            template_name="Restaurant und Gastronomie", background_color="#FFFFFF", accent_color="#2563EB",
            border_style="sharp", company_name="Müller & Söhne <GmbH>", business_email="info@mueller.de",
            slogan="", phone="+49 1", description="Beste <Küche>", image_file=None,
        )
        values.update(overrides)
        return logic.build_customized_template_html(**values)

    def test_escapes_customer_input_and_uses_defaults(self):
        html = self.build()
        assert "Müller &amp; Söhne &lt;GmbH&gt;" in html and "<GmbH>" not in html
        assert "Beste &lt;Küche&gt;" in html
        assert logic.get_template_preview_copy("de")["defaults"][0] in html
        assert f"© {datetime.now().year}" in html
        assert "--radius: 0" in html and "+49 1" in html
        assert "customer-chatbot" not in html

    def test_multi_and_single_page_navigation(self):
        assert 'href="kontakt.html"' in self.build(multi_page=True)
        single = self.build(multi_page=False)
        assert 'href="#kontakt"' in single and "kontakt.html" not in single

    def test_custom_sections_and_image(self, session):
        html = self.build(template_sections="Reparatur | Schnell\nNur Titel\nDrei | x\nVier | y", image_file=FakeUpload("hero.png", b"p"))
        assert "<h3>Reparatur</h3><p>Schnell</p>" in html
        assert "<h3>Nur Titel</h3><p>Beste &lt;Küche&gt;</p>" in html
        assert "Vier" not in html
        assert 'src="vorlagen-hero-bild.png"' in html and "vorlagen-hero-bild.png" in session.assets

    def test_rtl_languages(self, session):
        session.app_language = "ar"
        assert 'dir="rtl"' in self.build() and 'lang="ar"' in self.build()

    def test_subpages_have_chatbot_and_shared_styles(self, session):
        pages = logic.build_customized_template_pages("Firma & Co", "info@firma.de", "#FFFFFF", "#2563EB", "")
        assert set(pages) == {"leistungen.html", "angebote.html", "projekte.html", "ueber-uns.html", "kontakt.html", "styles.css"}
        for name, page in pages.items():
            if name.endswith(".html"):
                assert page.count('id="customer-chatbot"') == 1 and "data-customer-chatbot-resilience" in page
                assert "Firma &amp; Co" in page and "Firma &amp;amp; Co" not in page
        assert pages["styles.css"] == logic.build_customized_template_styles()

    def test_offer_section_escapes_and_defaults(self, session):
        html = logic.build_offer_page_section("<b>Paket</b>", "", "")
        assert "&lt;b&gt;Paket&lt;/b&gt;" in html and "Preis auf Anfrage" in html


class TestProfessionalDraft:
    def test_validation(self, session):
        with pytest.raises(ValueError, match="Firmennamen"):
            logic.create_professional_standard_draft()

    @pytest.mark.parametrize("structure", ["Eine Seite", "Mehrseitige Website"])
    def test_creates_draft(self, session, structure):
        session.update(client_company_name="Firma", client_business_email="info@firma.de", page_structure=structure, template_accent_color="kaputt")
        logic.create_professional_standard_draft()
        assert session.generated_html.count('id="customer-chatbot"') == 1
        assert "--accent: #2563EB" in session.generated_html
        expected = {"index.html", "styles.css"} | ({"leistungen.html", "angebote.html", "projekte.html", "ueber-uns.html", "kontakt.html"} if structure == "Mehrseitige Website" else set())
        assert set(session.site_pages) == expected


class TestAiFunctions:
    def test_ai_requires_access(self, session, fake_openai):
        session.user_id = 999
        with pytest.raises(ValueError, match="Testphase"):
            logic.ask_ai_for_html("system", "user")
        assert fake_openai.calls == []

    def test_ai_error_becomes_user_message(self, user_id, session, fake_openai):
        session.user_id = user_id
        fake_openai.replies["error"] = RuntimeError("Timeout")
        with pytest.raises(ValueError, match="nicht erreichbar"):
            logic.ask_ai_for_html("system", "user")

    def test_generate_validates_before_any_paid_call(self, user_id, session, fake_openai):
        session.user_id = user_id
        session.client_company_name = "Firma"
        session.client_business_email = "keine-mail"
        fake_openai.client.embeddings.create = lambda **k: pytest.fail("Embeddings vor Validierung aufgerufen")
        with pytest.raises(ValueError, match="gültige"):
            logic.generate_website("Beschreibung", None, [FakeUpload("a.txt", b"Text")])
        assert fake_openai.calls == []

    @pytest.mark.parametrize("multi_page", [False, True])
    def test_generate_website(self, user_id, session, fake_openai, multi_page):
        session.update(user_id=user_id, client_company_name="Firma", client_business_email="info@firma.de", client_web3forms_access_key="key-123")
        fake_openai.replies["chat"] = "```html\n<!doctype html><html><head></head><body><a href='mailto:x@y.de'>x@y.de</a></body></html>\n```"
        logic.generate_website("Wir reparieren Autos", FakeUpload("logo.png", b"p"), None, "Logo", multi_page)
        prompt = fake_openai.calls[0]["messages"][0]["content"]
        assert "info@firma.de" in prompt and 'value="key-123"' in prompt and 'src="logo-bild.png"' in prompt
        html = session.generated_html
        assert "x@y.de" not in html and "mailto:info@firma.de" in html
        assert html.count('id="customer-chatbot"') == 1
        if multi_page:
            assert 'href="styles.css"' in html
            assert "leistungen.html" not in session.site_pages
            assert 'href="index.html"' in session.site_pages["kontakt.html"]
            assert 'href="leistungen.html"' not in session.site_pages["kontakt.html"]
        else:
            assert set(session.site_pages) == {"index.html"}

    def test_modify_and_optimize_text(self, user_id, session, fake_openai):
        session.user_id = user_id
        with pytest.raises(ValueError, match="zuerst"):
            logic.modify_current_website("blau")
        session.generated_html = SIMPLE_HTML
        logic.modify_current_website("Mach den Titel blau")
        assert "Mach den Titel blau" in fake_openai.calls[0]["messages"][1]["content"]
        assert session.generated_html.startswith("<!doctype html><html><head></head><body><h1>KI</h1>")
        fake_openai.replies["chat"] = "```Besserer Text```"
        assert logic.optimize_editor_text("text") == "Besserer Text"
        with pytest.raises(ValueError, match="Text"):
            logic.optimize_editor_text("  ")


class TestAnalyticsOptimization:
    def test_requires_configuration(self, monkeypatch):
        monkeypatch.setattr(logic, "SUPABASE_URL", "")
        with pytest.raises(ValueError, match="supabase_url"):
            logic.create_analytics_optimized_version()

    def test_requires_enough_sessions(self, monkeypatch):
        fake = SimpleNamespace(analytics=lambda site_id: [{"session_id": "a"}])
        monkeypatch.setattr(logic, "get_supabase_analytics_client", lambda: fake)
        with pytest.raises(ValueError, match="500 Sitzungen"):
            logic.create_analytics_optimized_version()

    def test_creates_testing_version(self, monkeypatch, session, fake_openai):
        events = [{"session_id": str(i), "is_conversion": i % 10 == 0, "duration_seconds": 20} for i in range(500)]
        stored = {}
        fake = SimpleNamespace(analytics=lambda site_id: events, create_version=lambda site_id, html, status, conversion_rate: stored.update(status=status, rate=conversion_rate) or {"id": 1})
        monkeypatch.setattr(logic, "get_supabase_analytics_client", lambda: fake)
        session.generated_html = SIMPLE_HTML
        summary, version = logic.create_analytics_optimized_version()
        assert summary.sessions == 500 and version == {"id": 1}
        assert stored == {"status": "testing", "rate": 0.1}
        assert session.generated_html.count('id="customer-chatbot"') == 1


class TestExport:
    def test_zip_contains_pages_routes_and_assets(self, session):
        logic.queue_html_update(SIMPLE_HTML)
        session.site_pages["styles.css"] = "body{}"
        session.assets = {"logo.png": {"base64": "UE5H", "mime_type": "image/png"}}
        archive = zipfile.ZipFile(io.BytesIO(logic.build_website_zip()))
        assert set(archive.namelist()) == {"index.html", "styles.css", "api/chat.js", "api/analytics.js", "api/variant.js", "vercel.json", "logo.png"}
        assert archive.read("logo.png") == b"PNG"
        assert b"data-site-analytics" in archive.read("index.html")

    def test_analytics_injection_is_idempotent(self, js, scripts):
        once = logic.inject_site_analytics(SIMPLE_HTML, "site")
        twice = logic.inject_site_analytics(once, "site")
        assert once == twice and twice.count("data-site-analytics>") == 1
        for script in scripts(once):
            js(script)

    def test_api_routes_are_valid_javascript(self, js, monkeypatch):
        monkeypatch.setattr(logic, "ANALYTICS_RETENTION_DAYS", 30)
        route = logic.build_analytics_api_route()
        assert "const RETENTION_DAYS = 30;" in route
        js(route)
        js(logic.build_testing_variant_api_route())


class TestPrimaryButtonTarget:
    def test_prefers_button_over_navigation_link(self):
        html = '<nav><a href="#leistungen">Leistungen</a></nav><a class="button" href="angebote.html">Angebot</a>'
        updated, replaced = logic.set_primary_button_target(html, "https://shop.example/?a=1&b=2")
        assert replaced
        assert '<a href="#leistungen">' in updated
        assert '<a class="button" href="https://shop.example/?a=1&amp;b=2">' in updated

    def test_falls_back_to_first_anchor_link(self):
        updated, replaced = logic.set_primary_button_target('<a href="#kontakt">Los</a>', "#angebote")
        assert replaced and updated == '<a href="#angebote">Los</a>'

    def test_reports_missing_button(self):
        assert logic.set_primary_button_target('<a href="https://x.de">x</a>', "#angebote") == ('<a href="https://x.de">x</a>', False)

    def test_works_on_generated_template(self):
        html = TestTemplates().build(multi_page=False)
        updated, replaced = logic.set_primary_button_target(html, "#angebote")
        assert replaced and '<a class="button" href="#angebote">' in updated
        assert '<a href="#leistungen">' in updated


class TestLivePreview:
    def test_pages_are_self_contained_and_ordered(self, session):
        assets = {"logo-bild.png": {"base64": "UE5H", "mime_type": "image/png"}}
        index = '<html><head><link rel="stylesheet" href="styles.css"></head><body><img src="logo-bild.png" alt="logo-bild.png"></body></html>'
        pages = logic.build_live_preview_pages(index, {"kontakt.html": index, "zusatz.html": index, "leistungen.html": index, "styles.css": "body{color:red}"}, assets)
        assert list(pages) == ["index.html", "leistungen.html", "kontakt.html", "zusatz.html"]
        for html in pages.values():
            assert "<style>body{color:red}</style>" in html and 'href="styles.css"' not in html
            assert 'src="data:image/png;base64,UE5H"' in html
            assert 'alt="logo-bild.png"' not in html or html.count("data:image/png") == 2

    def test_inline_assets_only_replaces_references(self):
        html = '<p>Datei logo.png</p><img src="logo.png"><div style="background:url(logo.png)">'
        result = logic.inline_assets(html, {"logo.png": {"base64": "QQ==", "mime_type": "image/png"}})
        assert "<p>Datei logo.png</p>" in result
        assert result.count("data:image/png;base64,QQ==") == 2

    def test_template_preview_has_no_side_effects(self, session):
        session.update(industry_content_preset="Restaurant", page_structure="Mehrseitige Website", initial_image=FakeUpload("hero.png", b"bild", "image/png"))
        logic.apply_industry_content_preset()
        pages = logic.build_template_preview_pages()
        assert set(pages) == {"index.html", "leistungen.html", "angebote.html", "projekte.html", "ueber-uns.html", "kontakt.html"}
        assert 'src="data:image/png;base64,YmlsZA=="' in pages["index.html"]
        assert pages["index.html"].count('id="customer-chatbot"') == 1
        assert session.assets == {} and session.generated_html == "" and session.site_pages == {}

    def test_template_preview_uses_placeholders_without_customer_data(self, session):
        pages = logic.build_template_preview_pages()
        assert "Ihre Kontakt-E-Mail" in pages["index.html"]
        assert 'class="hero-visual"' in pages["index.html"]

    def test_draft_preview_matches_published_content(self, session):
        logic.queue_html_update(SIMPLE_HTML.replace("alt.png", "logo.png"))
        session.assets = {"logo.png": {"base64": "QQ==", "mime_type": "image/png"}}
        session.site_pages["styles.css"] = "h1{color:blue}"
        pages = logic.build_draft_preview_pages()
        assert list(pages) == ["index.html"]
        assert pages["index.html"].count('id="customer-chatbot"') == 1
        assert "data:image/png;base64,QQ==" in pages["index.html"]

    def test_template_quality_details(self):
        html = TestTemplates().build(company_name="Kfz Meister Schmidt", accent_color="#881337")
        assert '<span>KM</span>' in html and "BILDBEREICH" not in html
        assert "--accent-text: #FFFFFF" in html
        css = logic.build_customized_template_styles()
        assert "customer-chatbot" not in css and "var(--accent-text" in css

    def test_preview_component_script_is_valid(self, js):
        import gui

        js(gui.LIVE_SITE_PREVIEW.keywords["js"].replace("export default function(", "function renderPreview(", 1))
        for labels in gui.PREVIEW_COPY.values():
            assert set(labels) == set(gui.PREVIEW_COPY["de"])


class TestPreviewNavigationScript:
    """Regression: das in Vorschauseiten eingefügte Skript muss gültig bleiben (Backslashes!)."""

    def test_injected_helper_is_valid_and_keeps_regex_escapes(self):
        from py_mini_racer import MiniRacer

        import gui

        engine = MiniRacer()
        engine.eval(gui.LIVE_SITE_PREVIEW.keywords["js"].replace("export default function(", "function renderPreview(", 1))
        source = engine.eval("previewPageHelper.toString()")
        assert r"/^\.?\//" in source
        engine.eval(f"new Function({__import__('json').dumps('(' + source + ')')})")
        script = engine.eval("helperScript('t', ['index.html', 'kontakt.html'])")
        assert script.startswith("<script>(function previewPageHelper") and script.endswith("</script>")

    def test_subpages_share_template_styles(self, session):
        pages = logic.build_customized_template_pages("Firma", "a@b.de", "#FFFFFF", "#881337", "", "Restaurant und Gastronomie")
        assert "header{background:#17120d" in pages["kontakt.html"]
