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
        "API-Schlüssel fehlen. Prüfe `.streamlit/secrets.toml`. "
        "Benötigt werden `openai_api_key` und `vercel_token`."
    )
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

DEFAULT_STATE = {
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "saved_design_html": "",
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

# Aktualisiert den HTML-Editor sicher beim nächsten Streamlit-Durchlauf.
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
    """Prüft, ob ein vollständiges HTML-Dokument vorhanden ist."""
    html = clean_html(html)
    html_lower = html.lower()

    if not html:
        raise ValueError("Es wurde kein HTML-Code erstellt.")

    if "<!doctype html" not in html_lower and "<html" not in html_lower:
        raise ValueError("Die Antwort enthält keine vollständige HTML-Website.")

    return html


def queue_html_update(html: str) -> None:
    """Plant ein sicheres Update des HTML-Editors."""
    st.session_state.pending_html = require_complete_html(html)


def is_valid_email(email: str) -> bool:
    """Prüft grob, ob eine E-Mail-Adresse gültig aussieht."""
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def make_safe_file_name(section_name: str, extension: str) -> str:
    """Erstellt einen sicheren Namen für Bilddateien."""
    safe_name = re.sub(r"[^a-z0-9]+", "-", section_name.lower()).strip("-")
    return f"{safe_name or 'bild'}-bild{extension}"


def save_uploaded_image(uploaded_file, section_name: str) -> str:
    """Speichert ein Bild als Asset für Vorschau und Vercel-Deployment."""
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

    st.session_state.assets[file_name] = {
        "base64": base64.b64encode(uploaded_file.getvalue()).decode("utf-8"),
        "mime_type": uploaded_file.type or mime_types[extension],
    }

    return file_name


def create_preview_html(html: str) -> str:
    """Zeigt gespeicherte Bilder in der Streamlit-Vorschau an."""
    preview_html = html

    for file_name, asset in st.session_state.assets.items():
        data_url = f"data:{asset['mime_type']};base64,{asset['base64']}"
        preview_html = preview_html.replace(file_name, data_url)

    return preview_html


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert vollständigen HTML-Code von OpenAI an."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.35,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
    )

    return response.choices[0].message.content or ""


def build_contact_form_instruction() -> str:
    """Erstellt Anforderungen für das Kontaktformular."""
    admin_email = st.session_state.admin_email.strip()

    if not admin_email:
        return """
Erstelle einen Kontaktbereich mit Name, E-Mail, Betreff, Nachricht und Button.
Alle Eingabefelder benötigen passende name-Attribute.
"""

    return f"""
Erstelle einen professionellen Kontaktbereich mit einem funktionierenden Formular.

Das Formular muss genau diese Attribute besitzen:
<form action="https://formsubmit.co/{admin_email}" method="POST">

Das Formular muss diese versteckten Felder enthalten:
<input type="hidden" name="_subject" value="Neue Kundenanfrage über die Website">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="false">

Diese Pflichtfelder müssen enthalten sein:
<input name="name" required>
<input type="email" name="email" required>
<input name="subject" required>
<textarea name="message" required></textarea>

Füge einen sichtbaren Absenden-Button hinzu.
"""


def generate_website(description: str, initial_image) -> None:
    """Erstellt einen neuen Website-Entwurf."""
    image_instruction = ""

    if initial_image is not None:
        image_name = save_uploaded_image(initial_image, "profil")
        image_instruction = f"""
Ein Bild wurde hochgeladen. Nutze es professionell im Hero- oder Über-mich-Bereich:
<img src="{image_name}" alt="Profilbild">
"""

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein professioneller Webdesigner und Frontend-Entwickler.

Erstelle eine moderne, hochwertige, responsive Single-Page-Website.

Regeln:
- Nutze valides HTML5 und beginne mit <!doctype html>.
- Binde Tailwind CSS mit https://cdn.tailwindcss.com ein.
- Erstelle Navigation, Hero, Über mich, Leistungen/Fähigkeiten, Projekte,
  Kontaktbereich und Footer.
- Das Ergebnis muss professionell auf Mobilgeräten und Desktop aussehen.
- Antworte nur mit vollständigem HTML.
- Kein Markdown, keine Backticks, keine Erklärung.

{image_instruction}

{build_contact_form_instruction()}
""",
        user_instruction=description,
    )

    queue_html_update(html)


def modify_current_website(change_request: str) -> None:
    """Ändert gezielt nur einen gewünschten Bereich."""
    current_html = st.session_state.generated_html.strip()

    if not current_html:
        raise ValueError("Erstelle oder lade zuerst eine Website.")

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein sorgfältiger Frontend-Entwickler.

Bearbeite nur die angeforderte Änderung in einer bestehenden HTML-Website.
Behalte alle anderen Texte, Bereiche, Bilder, Links und Styles unverändert,
soweit dies möglich ist.

Regeln:
- Antworte nur mit vollständigem HTML5.
- Beginne direkt mit <!doctype html>.
- Kein Markdown, keine Backticks und keine Erklärung.
- Tailwind CSS bleibt erhalten.
- Entferne keine Bereiche, außer dies wird ausdrücklich verlangt.
- Wenn ein Kontaktformular existiert, behalte action, method, hidden fields
  und name-Attribute unverändert.

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
    """Erstellt einen gültigen Vercel-Projektnamen aus einem Link."""
    hostname = urlparse(live_url).hostname or ""
    project_name = hostname.split(".")[0].lower()
    project_name = re.sub(r"[^a-z0-9-]", "-", project_name).strip("-")
    return project_name or "ai-website-builder"


def is_vercel_login_page(response: requests.Response) -> bool:
    """Erkennt Vercel-Anmeldung und Vercel-Deployment-Schutzseiten."""
    page_url = response.url.lower()
    page_html = response.text.lower()

    markers = [
        "vercel.com/login",
        "<title>log in to vercel</title>",
        "continue with github",
        "continue with google",
        "continue with chatgpt",
        "deployment protection",
        "vercel authentication",
    ]

    return any(marker in page_url or marker in page_html for marker in markers)


def load_published_website(live_url: str) -> None:
    """
    Lädt eine öffentliche Live-Website unverändert.

    Es erfolgt kein KI-Aufruf und keine Veränderung am Original-HTML.
    """
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
            "Diese Seite verlangt eine Vercel-Anmeldung oder ist geschützt. "
            "Verwende einen öffentlichen Live-Link."
        )

    if response.status_code != 200:
        raise ValueError(
            f"Die Website konnte nicht geladen werden. HTTP {response.status_code}."
        )

    # Original-HTML exakt übernehmen.
    html = require_complete_html(response.text)

    # Alte lokale Bilder dürfen die neu geladene Seite nicht verändern.
    st.session_state.assets = {}

    # response.url ist der tatsächliche Link nach Weiterleitungen.
    st.session_state.live_url = response.url
    st.session_state.project_name = get_project_name_from_url(response.url)
    st.session_state.published_html = html
    st.session_state.pending_html = html

    # Eine extern geladene Seite darf nicht versehentlich gelöscht werden.
    st.session_state.deployment_id = ""


def publish_website() -> None:
    """Veröffentlicht den aktuellen HTML-Entwurf und Bilder auf Vercel."""
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
                "framework": "other",
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

    if not deployment.get("url") or not deployment.get("id"):
        raise ValueError("Vercel hat keine vollständige Deployment-Antwort geliefert.")

    st.session_state.live_url = f"https://{deployment['url']}"
    st.session_state.deployment_id = deployment["id"]
    st.session_state.published_html = html


def delete_published_website() -> None:
    """Löscht nur das letzte Deployment dieser Sitzung."""
    if not st.session_state.deployment_id:
        raise ValueError("Kein Deployment aus dieser Sitzung zum Löschen vorhanden.")

    response = requests.delete(
        f"https://api.vercel.com/v13/deployments/{st.session_state.deployment_id}",
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
st.caption("Websites erstellen, bearbeiten, prüfen und veröffentlichen.")

create_tab, manage_tab = st.tabs(
    ["✨ Neue Website", "⚙️ Veröffentlichte Seiten verwalten"]
)

with create_tab:
    form_column, info_column = st.columns([1.4, 1], gap="large")

    with form_column:
        st.subheader("Neuen Entwurf erstellen")

        description = st.text_area(
            "Beschreibung der Website",
            placeholder="Beispiel: Moderne Website für ein Kosmetikstudio in Berlin mit Leistungen, Preisen, Team und Kontaktformular.",
            height=160,
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
        )

        if st.button("✨ Website-Entwurf generieren", type="primary", use_container_width=True):
            if not description.strip():
                st.warning("Bitte beschreibe zuerst die gewünschte Website.")
            elif admin_email.strip() and not is_valid_email(admin_email.strip()):
                st.warning("Bitte gib eine gültige E-Mail-Adresse ein.")
            else:
                with st.status("Website wird erstellt ...", expanded=True) as status:
                    try:
                        st.session_state.admin_email = admin_email.strip()
                        generate_website(description, initial_image)
                        status.update("✅ Entwurf wurde erstellt.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update("❌ Erstellung fehlgeschlagen", state="error")
                        st.error(str(error))

    with info_column:
        st.subheader("Ablauf")
        st.info(
            "1. Website beschreiben\n\n"
            "2. Admin-E-Mail eintragen\n\n"
            "3. Entwurf erstellen\n\n"
            "4. Vorschau und Inhalte bearbeiten\n\n"
            "5. Veröffentlichen"
        )

with manage_tab:
    st.subheader("Öffentliche Website laden")
    st.caption(
        "Der Original-Code wird unverändert geladen. "
        "Vercel-Login- und Schutzseiten werden blockiert."
    )

    manage_url = st.text_input(
        "Öffentlicher Live-Link",
        placeholder="https://deine-website.vercel.app",
        key="manage_url",
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
                    load_published_website(manage_url)
                    status.update(
                        "✅ Die Original-Website wurde unverändert geladen.",
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update("❌ Laden fehlgeschlagen", state="error")
                    st.error(str(error))

if st.session_state.live_url:
    st.success("Eine Website ist geladen oder veröffentlicht.")
    st.link_button(
        "🔗 Veröffentlichte Seite unverändert öffnen",
        st.session_state.live_url,
        use_container_width=True,
    )

if st.session_state.generated_html:
    st.divider()
    st.header("Website bearbeiten")
    st.info(
        "Änderungen erscheinen zuerst in der Vorschau. "
        "Die Live-Website ändert sich erst nach dem Veröffentlichen."
    )

    content_tab, design_tab, image_tab, code_tab = st.tabs(
        ["📝 Inhalte", "🎨 Design", "🖼️ Bilder", "💻 HTML & Vorschau"]
    )

    with content_tab:
        section = st.selectbox(
            "Bereich auswählen",
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
        )

        request = st.text_area(
            "Gewünschte Änderung",
            placeholder="Beispiel: Füge im Projektbereich ein neues Projekt mit Titel, Beschreibung und Button hinzu.",
            height=130,
        )

        if st.button("📝 Bereich aktualisieren", use_container_width=True):
            if not request.strip():
                st.warning("Bitte beschreibe die gewünschte Änderung.")
            else:
                with st.status("Bereich wird bearbeitet ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Bereich „{section}“: {request}"
                        )
                        status.update("✅ Vorschau wurde aktualisiert.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update("❌ Änderung fehlgeschlagen", state="error")
                        st.error(str(error))

    with design_tab:
        colors = st.selectbox(
            "Farbstil",
            [
                "Modernes Blau und Violett",
                "Minimalistisch Schwarz und Weiß",
                "Elegant Beige und Gold",
                "Natürlich Grün und Creme",
                "Kreativ Pink und Violett",
                "Dunkles Premium-Design",
            ],
        )

        layout = st.selectbox(
            "Layout-Stil",
            [
                "Bestehendes Layout beibehalten",
                "Minimalistisch mit viel Weißraum",
                "Modern mit Karten",
                "Seriöses Business-Design",
                "Kreativ und farbenfroh",
            ],
        )

        design_request = st.text_input(
            "Zusätzlicher Wunsch",
            placeholder="Zum Beispiel: größere Buttons und runde Karten",
        )

        if st.button("🎨 Design aktualisieren", use_container_width=True):
            with st.status("Design wird angepasst ...", expanded=True) as status:
                try:
                    modify_current_website(
                        f"""
Ändere ausschließlich Layout, Farben, Abstände und Styling.

Farbstil: {colors}
Layout: {layout}
Zusatzwunsch: {design_request or "Keiner"}

Texte, Bilder, Kontaktformular und Seitenstruktur müssen erhalten bleiben.
"""
                    )
                    status.update("✅ Design wurde aktualisiert.", state="complete")
                    st.rerun()
                except Exception as error:
                    status.update("❌ Design-Änderung fehlgeschlagen", state="error")
                    st.error(str(error))

    with image_tab:
        image_section = st.selectbox(
            "Abschnitt für das Bild",
            ["Hero-Bereich", "Über mich", "Leistungen", "Projekte", "Kontakt"],
        )

        image_file = st.file_uploader(
            "Neues Bild hochladen",
            type=["png", "jpg", "jpeg", "webp"],
            key="section_image",
        )

        if st.button("🖼️ Bild aktualisieren", use_container_width=True):
            if image_file is None:
                st.warning("Bitte wähle zuerst ein Bild aus.")
            else:
                with st.status("Bild wird aktualisiert ...", expanded=True) as status:
                    try:
                        image_name = save_uploaded_image(image_file, image_section)

                        modify_current_website(
                            f"""
Ändere ausschließlich das Bild im Bereich „{image_section}“.

Nutze genau dieses Bild:
<img src="{image_name}" alt="{image_section} Bild">

Alle anderen Bereiche müssen unverändert bleiben.
"""
                        )
                        status.update("✅ Bild wurde aktualisiert.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update("❌ Bild-Änderung fehlgeschlagen", state="error")
                        st.error(str(error))

    with code_tab:
        editor_column, preview_column = st.columns(2, gap="large")

        with editor_column:
            st.text_area(
                "HTML-Quellcode",
                height=620,
                key="html_editor",
            )

            if st.button("👁️ Vorschau aktualisieren", use_container_width=True):
                try:
                    st.session_state.generated_html = require_complete_html(
                        st.session_state.html_editor
                    )
                    st.rerun()
                except ValueError as error:
                    st.warning(str(error))

            st.download_button(
                "⬇️ HTML herunterladen",
                data=st.session_state.generated_html,
                file_name="website.html",
                mime="text/html",
                use_container_width=True,
            )

        with preview_column:
            st.subheader("Vorschau")
            st.components.v1.html(
                create_preview_html(st.session_state.generated_html),
                height=620,
                scrolling=True,
            )

    st.divider()
    st.header("Veröffentlichung")

    publish_column, delete_column = st.columns(2, gap="large")

    with publish_column:
        label = (
            "🔄 Änderungen veröffentlichen"
            if st.session_state.live_url
            else "🚀 Website veröffentlichen"
        )

        if st.button(label, type="primary", use_container_width=True):
            with st.status("Website wird auf Vercel veröffentlicht ...", expanded=True) as status:
                try:
                    publish_website()
                    status.update(
                        "🎉 Website wurde erfolgreich veröffentlicht.",
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update("❌ Veröffentlichung fehlgeschlagen", state="error")
                    st.error(f"Vercel-Fehler: {error}")

    with delete_column:
        if st.session_state.deployment_id:
            st.warning("Löscht nur das letzte Deployment dieser Sitzung.")

            st.checkbox(
                "Ich möchte das letzte Deployment löschen.",
                key="delete_confirmation",
            )

            if st.button(
                "🗑️ Letztes Deployment löschen",
                disabled=not st.session_state.delete_confirmation,
                use_container_width=True,
            ):
                try:
                    delete_published_website()
                    st.success("Deployment wurde gelöscht.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Löschen fehlgeschlagen: {error}")
        else:
            st.info(
                "Eine geladene externe Website kann nicht über diese App gelöscht werden."
            )