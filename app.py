import base64
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
import streamlit as st
from openai import OpenAI


st.set_page_config(
    page_title="AI Website Builder",
    page_icon="🚀",
    layout="wide",
)

OPENAI_MODEL = "gpt-4o-mini"
VERCEL_DEPLOYMENTS_URL = (
    "https://api.vercel.com/v13/deployments"
    "?skipAutoDetectionConfirmation=1"
)

try:
    OPENAI_API_KEY = st.secrets["openai_api_key"]
    VERCEL_TOKEN = st.secrets["vercel_token"]
except KeyError:
    st.error(
        "API-Schlüssel fehlen. Prüfe die Datei `.streamlit/secrets.toml`."
    )
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)


DEFAULT_STATE = {
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "saved_design_html": "",
    "saved_design_name": "",
    "assets": {},
    "live_url": "",
    "deployment_id": "",
    "project_name": "ai-website-builder",
    "admin_email": "",
    "delete_confirmation": False,
}

for state_key, default_value in DEFAULT_STATE.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value

# Dieser Block muss VOR dem HTML-Editor stehen.
if st.session_state.pending_html:
    st.session_state.generated_html = st.session_state.pending_html
    st.session_state.html_editor = st.session_state.pending_html
    st.session_state.pending_html = ""


def clean_html(html: str) -> str:
    """Entfernt Markdown-Codeblöcke aus KI-Antworten."""
    return (
        html.replace("```html", "")
        .replace("```HTML", "")
        .replace("```", "")
        .strip()
    )


def require_complete_html(html: str) -> str:
    """Prüft, ob eine vollständige HTML-Seite vorhanden ist."""
    cleaned_html = clean_html(html)
    lowered_html = cleaned_html.lower()

    if not cleaned_html:
        raise ValueError("Es wurde kein HTML-Code erstellt.")

    if "<!doctype html" not in lowered_html and "<html" not in lowered_html:
        raise ValueError("Die Antwort enthält keine vollständige HTML-Website.")

    return cleaned_html


def queue_html_update(html: str) -> None:
    """Plant eine Editor-Aktualisierung für den nächsten Streamlit-Durchlauf."""
    st.session_state.pending_html = require_complete_html(html)


def make_safe_file_name(section_name: str, extension: str) -> str:
    """Erstellt einen sicheren Dateinamen für hochgeladene Bilder."""
    safe_name = re.sub(r"[^a-z0-9]+", "-", section_name.lower()).strip("-")
    return f"{safe_name or 'bild'}-bild{extension}"


def save_uploaded_image(uploaded_file, section_name: str) -> str:
    """Speichert ein Bild in der Sitzung und gibt den Dateinamen zurück."""
    if uploaded_file is None:
        raise ValueError("Bitte wähle zuerst ein Bild aus.")

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        extension = ".png"

    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    file_name = make_safe_file_name(section_name, extension)
    mime_type = uploaded_file.type or mime_types[extension]

    st.session_state.assets[file_name] = {
        "base64": base64.b64encode(uploaded_file.getvalue()).decode("utf-8"),
        "mime_type": mime_type,
    }

    return file_name


def create_preview_html(html: str) -> str:
    """Ersetzt lokale Bilddateien in der Vorschau durch Base64-Bilder."""
    preview_html = html

    for file_name, asset in st.session_state.assets.items():
        data_url = (
            f"data:{asset['mime_type']};base64,{asset['base64']}"
        )
        preview_html = preview_html.replace(file_name, data_url)

    return preview_html


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Erstellt oder bearbeitet HTML mit OpenAI."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.35,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
    )

    return response.choices[0].message.content or ""


def is_valid_email(email: str) -> bool:
    """Einfache Prüfung einer E-Mail-Adresse."""
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def build_contact_form_instruction() -> str:
    """Erstellt die Vorgaben für das Kontaktformular."""
    admin_email = st.session_state.admin_email.strip()

    if not admin_email:
        return """
Erstelle einen Kontaktbereich mit Name, E-Mail, Betreff und Nachricht.
Die Felder brauchen passende name-Attribute und einen Absenden-Button.
"""

    return f"""
Erstelle einen professionellen Kontaktbereich mit einem funktionierenden Formular.

Das Formular muss genau so beginnen:
<form action="https://formsubmit.co/{admin_email}" method="POST">

Das Formular muss diese versteckten Felder enthalten:
<input type="hidden" name="_subject" value="Neue Kundenanfrage über die Website">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="false">

Diese Pflichtfelder müssen vorhanden sein:
- <input name="name" required>
- <input type="email" name="email" required>
- <input name="subject" required>
- <textarea name="message" required></textarea>

Füge einen sichtbaren Absenden-Button hinzu.
"""


def generate_website(description: str, initial_image) -> None:
    """Erstellt einen neuen Website-Entwurf."""
    image_instruction = ""

    if initial_image is not None:
        image_name = save_uploaded_image(initial_image, "profil")
        image_instruction = f"""
Ein Bild wurde hochgeladen. Binde es professionell im Hero- oder Über-mich-Bereich ein:
<img src="{image_name}" alt="Profilbild">
"""

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein professioneller Webdesigner und Frontend-Entwickler.

Erstelle eine hochwertige, moderne und responsive Single-Page-Website.

Regeln:
- Nutze valides HTML5.
- Beginne direkt mit <!doctype html>.
- Binde Tailwind CSS über https://cdn.tailwindcss.com ein.
- Erstelle Navigation, Hero, Über mich, Leistungen oder Fähigkeiten,
  Projekte, Kontaktbereich und Footer.
- Die Seite muss auf Desktop und Mobilgeräten professionell aussehen.
- Antworte ausschließlich mit vollständigem HTML.
- Kein Markdown, keine Backticks, keine Erklärung.

{image_instruction}

{build_contact_form_instruction()}
""",
        user_instruction=description,
    )

    queue_html_update(html)


def modify_current_website(change_request: str) -> None:
    """Ändert gezielt nur den gewünschten Website-Bereich."""
    current_html = st.session_state.generated_html.strip()

    if not current_html:
        raise ValueError("Erstelle oder lade zuerst eine Website.")

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein sorgfältiger Frontend-Entwickler.

Du erhältst eine bestehende vollständige HTML-Website. Bearbeite nur die
angeforderte Änderung. Alle anderen Inhalte, Bilder, Links, Bereiche,
Farben und Styles müssen so weit wie möglich erhalten bleiben.

Regeln:
- Gib ausschließlich vollständiges HTML5 zurück.
- Beginne direkt mit <!doctype html>.
- Kein Markdown, keine Backticks und keine Erklärung.
- Tailwind CSS muss erhalten bleiben.
- Entferne keine bestehenden Bereiche, außer dies wird ausdrücklich verlangt.
- Wenn ein Kontaktformular vorhanden ist, behalte action, method,
  versteckte Felder und name-Attribute unverändert.

{build_contact_form_instruction()}
""",
        user_instruction=f"""
AKTUELLER HTML-CODE:
{current_html}

GEWÜNSCHTE ÄNDERUNG:
{change_request}
""",
    )

    queue_html_update(html)


def get_project_name_from_url(live_url: str) -> str:
    """Leitet einen gültigen Projektnamen aus einem Live-Link ab."""
    hostname = urlparse(live_url).hostname or ""
    name = hostname.split(".")[0].lower()
    name = re.sub(r"[^a-z0-9-]", "-", name).strip("-")

    return name or "ai-website-builder"


def is_vercel_login_page(response: requests.Response) -> bool:
    """Erkennt Vercel-Login- und Deployment-Schutzseiten."""
    page_url = response.url.lower()
    page_html = response.text.lower()

    login_markers = [
        "vercel.com/login",
        "<title>log in to vercel</title>",
        "continue with github",
        "continue with google",
        "continue with chatgpt",
        "deployment protection",
        "vercel authentication",
    ]

    return any(marker in page_url or marker in page_html for marker in login_markers)


def load_published_website(live_url: str) -> None:
    """Lädt ausschließlich eine öffentliche HTML-Seite als Entwurf."""
    live_url = live_url.strip()

    if not live_url.startswith(("https://", "http://")):
        live_url = f"https://{live_url}"

    response = requests.get(
        live_url,
        headers={"User-Agent": "AI-Website-Builder/1.0"},
        timeout=30,
        allow_redirects=True,
    )

    if is_vercel_login_page(response):
        raise ValueError(
            "Diese Seite ist durch Vercel geschützt oder verlangt eine Anmeldung. "
            "Sie wurde nicht geladen. Verwende einen öffentlichen Live-Link."
        )

    if response.status_code != 200:
        raise ValueError(
            f"Die Website konnte nicht geladen werden. HTTP {response.status_code}."
        )

    html = require_complete_html(response.text)

    st.session_state.live_url = live_url
    st.session_state.project_name = get_project_name_from_url(live_url)
    st.session_state.published_html = html
    st.session_state.pending_html = html


def publish_website() -> None:
    """Veröffentlicht HTML und Bilddateien als statische Vercel-Website."""
    html = require_complete_html(st.session_state.generated_html)

    files = [{"file": "index.html", "data": html}]

    for file_name, asset in st.session_state.assets.items():
        files.append(
            {
                "file": file_name,
                "data": asset["base64"],
                "encoding": "base64",
            }
        )

    response = requests.post(
        VERCEL_DEPLOYMENTS_URL,
        headers={
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "name": st.session_state.project_name,
            "target": "production",
            "files": files,
            "projectSettings": {
                "framework": None,
                "buildCommand": None,
                "devCommand": None,
                "installCommand": None,
                "outputDirectory": None,
                "rootDirectory": None,
            },
        },
        timeout=90,
    )

    if response.status_code not in (200, 201):
        raise ValueError(f"HTTP {response.status_code}: {response.text}")

    deployment = response.json()
    deployment_url = deployment.get("url")
    deployment_id = deployment.get("id")

    if not deployment_url or not deployment_id:
        raise ValueError("Vercel hat keine vollständige Deployment-Antwort geliefert.")

    st.session_state.live_url = f"https://{deployment_url}"
    st.session_state.deployment_id = deployment_id
    st.session_state.published_html = html


def delete_published_website() -> None:
    """Löscht ausschließlich das zuletzt in dieser Sitzung erstellte Deployment."""
    deployment_id = st.session_state.deployment_id

    if not deployment_id:
        raise ValueError(
            "Kein Deployment aus dieser Sitzung gefunden. "
            "Die Seite kann hier nicht gelöscht werden."
        )

    response = requests.delete(
        f"https://api.vercel.com/v13/deployments/{deployment_id}",
        headers={"Authorization": f"Bearer {VERCEL_TOKEN}"},
        timeout=60,
    )

    if response.status_code not in (200, 202, 204):
        raise ValueError(f"HTTP {response.status_code}: {response.text}")

    st.session_state.live_url = ""
    st.session_state.deployment_id = ""
    st.session_state.published_html = ""
    st.session_state.delete_confirmation = False


st.title("🚀 KI Website Builder")
st.caption(
    "Websites erstellen, einzelne Bereiche bearbeiten, Vorschau prüfen und veröffentlichen."
)

create_tab, manage_tab = st.tabs(
    ["✨ Neue Website", "⚙️ Veröffentlichte Seiten verwalten"]
)

with create_tab:
    form_column, info_column = st.columns([1.4, 1], gap="large")

    with form_column:
        st.subheader("Neuen Entwurf erstellen")

        description = st.text_area(
            "Beschreibung der Website",
            placeholder=(
                "Beispiel: Moderne Website für ein Kosmetikstudio in Berlin. "
                "Mit Leistungen, Preisen, Galerie, Team und Kontaktformular."
            ),
            height=180,
            key="website_description",
        )

        initial_image = st.file_uploader(
            "Logo oder Profilbild (optional)",
            type=["png", "jpg", "jpeg", "webp"],
            key="initial_image",
        )

        admin_email = st.text_input(
            "E-Mail für Kundenanfragen",
            value=st.session_state.admin_email,
            placeholder="kontakt@unternehmen.de",
            help="Nachrichten des Kontaktformulars werden an diese Adresse gesendet.",
            key="admin_email_input",
        )

        if st.button(
            "✨ Website-Entwurf generieren",
            type="primary",
            use_container_width=True,
        ):
            if not description.strip():
                st.warning("Bitte beschreibe zuerst die gewünschte Website.")
            elif admin_email.strip() and not is_valid_email(admin_email.strip()):
                st.warning("Bitte gib eine gültige E-Mail-Adresse ein.")
            else:
                with st.status("Website wird erstellt ...", expanded=True) as status:
                    try:
                        st.session_state.admin_email = admin_email.strip()
                        st.write("🧠 Design, Texte und Struktur werden erstellt ...")
                        generate_website(description, initial_image)

                        status.update(
                            label="✅ Entwurf wurde erstellt.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Erstellung fehlgeschlagen",
                            state="error",
                            expanded=True,
                        )
                        st.error(f"**Fehler:** {error}")

    with info_column:
        st.subheader("Ablauf")
        st.info(
            "1. Website beschreiben\n\n"
            "2. E-Mail für Kundenanfragen eintragen\n\n"
            "3. Entwurf generieren\n\n"
            "4. Text, Bilder oder Design gezielt ändern\n\n"
            "5. Vorschau prüfen\n\n"
            "6. Veröffentlichen"
        )

with manage_tab:
    st.subheader("Bereits veröffentlichte Website laden")

    st.warning(
        "Nur öffentliche Webseiten können geladen werden. "
        "Vercel-Login- oder Schutzseiten werden automatisch blockiert."
    )

    manage_url = st.text_input(
        "Öffentlicher Live-Link",
        placeholder="https://deine-website.vercel.app",
        key="manage_url_input",
    )

    if st.button(
        "⚙️ Veröffentlichte Seite laden und bearbeiten",
        type="primary",
        use_container_width=True,
    ):
        if not manage_url.strip():
            st.warning("Bitte gib einen Live-Link ein.")
        else:
            with st.status("Website wird geladen ...", expanded=True) as status:
                try:
                    st.write("🌐 Öffentliche HTML-Seite wird geprüft ...")
                    load_published_website(manage_url)

                    status.update(
                        label="✅ Website wurde geladen und kann bearbeitet werden.",
                        state="complete",
                        expanded=False,
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Laden fehlgeschlagen",
                        state="error",
                        expanded=True,
                    )
                    st.error(f"**Fehler:** {error}")

if st.session_state.live_url:
    st.success("Eine Website ist geladen oder veröffentlicht.")
    st.markdown(f"### 🔗 [Live-Website öffnen]({st.session_state.live_url})")

if st.session_state.generated_html:
    st.divider()
    st.header("Website bearbeiten")

    st.info(
        "Änderungen erscheinen zuerst in der Vorschau. "
        "Die Live-Website wird erst beim Veröffentlichen aktualisiert."
    )

    text_tab, design_tab, image_tab, save_tab = st.tabs(
        [
            "📝 Text & Abschnitte",
            "🎨 Layout & Farben",
            "🖼️ Bilder",
            "💾 Design",
        ]
    )

    with text_tab:
        selected_section = st.selectbox(
            "Abschnitt auswählen",
            [
                "Navigation",
                "Hero-Bereich",
                "Über mich",
                "Leistungen oder Fähigkeiten",
                "Projekte",
                "Kontakt",
                "Footer",
                "Neuen Abschnitt hinzufügen",
            ],
            key="selected_section",
        )

        text_change = st.text_area(
            "Was soll geändert werden?",
            placeholder=(
                "Beispiel: Füge ein neues Projekt mit Titel, Beschreibung, "
                "Technologien und einem Button hinzu."
            ),
            height=130,
            key="text_change",
        )

        if st.button("📝 Nur diesen Bereich aktualisieren", use_container_width=True):
            if not text_change.strip():
                st.warning("Bitte beschreibe die gewünschte Änderung.")
            else:
                with st.status("Bereich wird bearbeitet ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Bereich "
                            f"„{selected_section}“: {text_change}"
                        )
                        status.update(
                            label="✅ Änderung wurde in die Vorschau übernommen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Änderung fehlgeschlagen",
                            state="error",
                        )
                        st.error(f"**Fehler:** {error}")

    with design_tab:
        color_style = st.selectbox(
            "Farbstil",
            [
                "Modernes Blau und Violett",
                "Minimalistisch Schwarz und Weiß",
                "Elegant Beige und Gold",
                "Natürlich Grün und Creme",
                "Kreativ Pink und Violett",
                "Dunkles Premium-Design",
            ],
            key="color_style",
        )

        layout_style = st.selectbox(
            "Layout-Stil",
            [
                "Bestehendes Layout beibehalten",
                "Minimalistisch mit viel Weißraum",
                "Modern mit Karten",
                "Seriöses Business-Design",
                "Kreativ und farbenfroh",
                "Editorial- oder Magazin-Stil",
            ],
            key="layout_style",
        )

        custom_design = st.text_input(
            "Zusätzlicher Designwunsch",
            placeholder="Zum Beispiel: größere Buttons, runde Karten, weniger Animationen",
            key="custom_design",
        )

        if st.button("🎨 Nur Design aktualisieren", use_container_width=True):
            with st.status("Design wird angepasst ...", expanded=True) as status:
                try:
                    modify_current_website(
                        f"""
Ändere ausschließlich Layout, Farben, Abstände und visuelles Styling.

Farbstil: {color_style}
Layout-Stil: {layout_style}
Zusatzwunsch: {custom_design or "Keiner"}

Texte, Bilder, Kontaktformular und Inhaltsstruktur müssen erhalten bleiben.
"""
                    )
                    status.update(
                        label="✅ Design wurde in die Vorschau übernommen.",
                        state="complete",
                        expanded=False,
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Design-Änderung fehlgeschlagen",
                        state="error",
                    )
                    st.error(f"**Fehler:** {error}")

    with image_tab:
        image_section = st.selectbox(
            "Abschnitt für das Bild",
            [
                "Hero-Bereich",
                "Über mich",
                "Leistungen",
                "Projekte",
                "Kontakt",
            ],
            key="image_section",
        )

        section_image = st.file_uploader(
            "Neues Bild hochladen",
            type=["png", "jpg", "jpeg", "webp"],
            key="section_image",
        )

        if st.button("🖼️ Nur dieses Bild aktualisieren", use_container_width=True):
            if section_image is None:
                st.warning("Bitte wähle zuerst ein Bild aus.")
            else:
                with st.status("Bild wird aktualisiert ...", expanded=True) as status:
                    try:
                        image_name = save_uploaded_image(
                            section_image,
                            image_section,
                        )

                        modify_current_website(
                            f"""
Ändere ausschließlich das Bild im Bereich „{image_section}“.

Nutze exakt diesen HTML-Code für das neue Bild:
<img src="{image_name}" alt="{image_section} Bild">

Das Bild soll responsiv, professionell zugeschnitten und optisch passend sein.
Alle anderen Bereiche müssen unverändert bleiben.
"""
                        )
                        status.update(
                            label="✅ Bild wurde in die Vorschau übernommen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Bild-Änderung fehlgeschlagen",
                            state="error",
                        )
                        st.error(f"**Fehler:** {error}")

    with save_tab:
        design_name = st.text_input(
            "Name des gespeicherten Designs",
            value="Mein Website-Design",
            key="design_name",
        )

        if st.button("💾 Design in dieser Sitzung speichern", use_container_width=True):
            st.session_state.saved_design_html = st.session_state.generated_html
            st.session_state.saved_design_name = (
                design_name.strip() or "Mein Website-Design"
            )
            st.success("Design wurde gespeichert.")

        st.download_button(
            "⬇️ HTML-Datei herunterladen",
            data=st.session_state.generated_html,
            file_name="mein-website-design.html",
            mime="text/html",
            use_container_width=True,
        )

        if st.session_state.saved_design_html:
            if st.button(
                "↩️ Gespeichertes Design wiederherstellen",
                use_container_width=True,
            ):
                st.session_state.pending_html = st.session_state.saved_design_html
                st.rerun()

    st.divider()
    st.header("Vorschau und HTML-Bearbeitung")

    editor_column, preview_column = st.columns([1, 1], gap="large")

    with editor_column:
        st.text_area(
            "HTML-Quellcode",
            height=650,
            key="html_editor",
        )

        update_column, discard_column = st.columns(2)

        with update_column:
            if st.button("👁️ Vorschau aktualisieren", use_container_width=True):
                try:
                    st.session_state.generated_html = require_complete_html(
                        st.session_state.html_editor
                    )
                    st.success("Vorschau wurde aktualisiert.")
                    st.rerun()
                except ValueError as error:
                    st.warning(str(error))

        with discard_column:
            if st.button("↩️ Änderungen verwerfen", use_container_width=True):
                if st.session_state.published_html:
                    st.session_state.pending_html = st.session_state.published_html
                    st.rerun()
                else:
                    st.warning("Es gibt noch keine veröffentlichte Version.")

    with preview_column:
        st.subheader("Vorschau")
        st.components.v1.html(
            create_preview_html(st.session_state.generated_html),
            height=650,
            scrolling=True,
        )

    st.divider()
    st.header("Veröffentlichung")

    publish_column, delete_column = st.columns([1, 1], gap="large")

    with publish_column:
        button_label = (
            "🔄 Änderungen veröffentlichen"
            if st.session_state.live_url
            else "🚀 Website veröffentlichen"
        )

        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
        ):
            with st.status("Website wird veröffentlicht ...", expanded=True) as status:
                try:
                    st.write("🌐 HTML und Bilder werden zu Vercel hochgeladen ...")
                    publish_website()
                    status.update(
                        label="🎉 Website wurde erfolgreich veröffentlicht.",
                        state="complete",
                        expanded=False,
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Veröffentlichung fehlgeschlagen",
                        state="error",
                        expanded=True,
                    )
                    st.error(f"**Vercel-Fehler:** {error}")

    with delete_column:
        if st.session_state.deployment_id:
            st.warning("Das Löschen entfernt das letzte Deployment dieser Sitzung.")

            st.checkbox(
                "Ich möchte die zuletzt veröffentlichte Website löschen.",
                key="delete_confirmation",
            )

            if st.button(
                "🗑️ Letztes Deployment löschen",
                disabled=not st.session_state.delete_confirmation,
                use_container_width=True,
            ):
                with st.status("Deployment wird gelöscht ...", expanded=True) as status:
                    try:
                        delete_published_website()
                        status.update(
                            label="✅ Deployment wurde gelöscht.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Löschen fehlgeschlagen",
                            state="error",
                            expanded=True,
                        )
                        st.error(f"**Vercel-Fehler:** {error}")
        else:
            st.info(
                "Die Löschfunktion ist verfügbar, nachdem eine Website "
                "in dieser Sitzung veröffentlicht wurde."
            )