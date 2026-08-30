import base64
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
import streamlit as st
from openai import OpenAI


st.set_page_config(page_title="AI Website Builder", page_icon="🚀", layout="wide")

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
        "API-Schlüssel fehlen. In `.streamlit/secrets.toml` werden "
        "`openai_api_key` und `vercel_token` benötigt."
    )
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

DEFAULT_STATE = {
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "assets": {},
    "live_url": "",
    "deployment_id": "",
    "project_name": "ai-website-builder",
    "delete_confirmation": False,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.pending_html:
    st.session_state.generated_html = st.session_state.pending_html
    st.session_state.html_editor = st.session_state.pending_html
    st.session_state.pending_html = ""


def clean_html(html: str) -> str:
    """Entfernt Markdown-Codeblöcke aus einer KI-Antwort."""
    return (
        html.replace("```html", "")
        .replace("```HTML", "")
        .replace("```", "")
        .strip()
    )


def require_complete_html(html: str) -> str:
    """Prüft, ob HTML vorhanden ist."""
    html = clean_html(html)
    lowered = html.lower()

    if not html:
        raise ValueError("Es wurde kein HTML-Code gefunden.")

    if "<html" not in lowered and "<!doctype" not in lowered:
        raise ValueError("Die Antwort enthält keine vollständige HTML-Website.")

    return html


def queue_html_update(html: str) -> None:
    """Aktualisiert den Editor sicher beim nächsten Streamlit-Durchlauf."""
    st.session_state.pending_html = require_complete_html(html)


def safe_project_name(name: str) -> str:
    """Erstellt einen gültigen Vercel-Projektnamen."""
    name = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return (name[:100] or "ai-website-builder")


def get_project_name_from_url(live_url: str) -> str:
    """Ermittelt einen Projektnamen aus einer URL."""
    hostname = urlparse(live_url).hostname or ""
    return safe_project_name(hostname.split(".")[0])


def save_uploaded_image(uploaded_file, section_name: str) -> str:
    """Speichert ein Bild als Asset für Vorschau und Deployment."""
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

    name = re.sub(r"[^a-z0-9]+", "-", section_name.lower()).strip("-")
    file_name = f"{name or 'bild'}-bild{extension}"

    st.session_state.assets[file_name] = {
        "base64": base64.b64encode(uploaded_file.getvalue()).decode("utf-8"),
        "mime_type": uploaded_file.type or mime_types[extension],
    }

    return file_name


def create_preview_html(html: str) -> str:
    """Ersetzt lokale hochgeladene Bilder in der Vorschau durch Data-URLs."""
    for file_name, asset in st.session_state.assets.items():
        data_url = f"data:{asset['mime_type']};base64,{asset['base64']}"
        html = html.replace(file_name, data_url)

    return html


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


def generate_website(description: str, image_file) -> None:
    """Erstellt eine neue Website."""
    image_instruction = ""

    if image_file:
        image_name = save_uploaded_image(image_file, "profil")
        image_instruction = f"""
Verwende dieses Bild professionell im Hero- oder Über-mich-Bereich:
<img src="{image_name}" alt="Profilbild">
"""

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist professioneller Webdesigner und Frontend-Entwickler.
Erstelle eine moderne, hochwertige und responsive Single-Page-Website.

Regeln:
- Vollständiges valides HTML5, beginnend mit <!doctype html>.
- Binde Tailwind CSS über https://cdn.tailwindcss.com ein.
- Erstelle Navigation, Hero, Über mich, Leistungen, Projekte, Kontakt und Footer.
- Verwende ein modernes, zugängliches und mobilfreundliches Design.
- Das Kontaktformular hat Name, E-Mail, Betreff, Nachricht und Absenden-Button.
- Antworte ausschließlich mit HTML. Kein Markdown und keine Erklärung.

{image_instruction}
""",
        user_instruction=description,
    )

    queue_html_update(html)


def modify_current_website(change_request: str) -> None:
    """Ändert nur angeforderte Bereiche einer bestehenden Website."""
    current_html = st.session_state.generated_html.strip()

    if not current_html:
        raise ValueError("Erstelle oder lade zuerst eine Website.")

    html = ask_ai_for_html(
        system_instruction="""
Du bist ein sorgfältiger Frontend-Entwickler.
Bearbeite nur die angeforderte Änderung in der vorhandenen Website.

Regeln:
- Gib ausschließlich vollständiges HTML5 zurück, beginnend mit <!doctype html>.
- Kein Markdown und keine Erklärungen.
- Bestehende Bereiche, Texte, Bilder, Links und Styles bleiben erhalten,
  sofern ihre Änderung nicht ausdrücklich angefordert wird.
- Tailwind CSS muss erhalten bleiben.
- Vorhandene Formular-Endpunkte und Formularattribute bleiben erhalten.
""",
        user_instruction=f"""
AKTUELLER HTML-CODE:
{current_html}

ÄNDERUNGSWUNSCH:
{change_request}
""",
    )

    queue_html_update(html)


def is_vercel_login_page(response: requests.Response) -> bool:
    """Erkennt Vercel-Anmelde- und Schutzseiten."""
    content = response.text.lower()
    url = response.url.lower()

    markers = [
        "vercel.com/login",
        "<title>log in to vercel</title>",
        "continue with github",
        "continue with google",
        "deployment protection",
        "vercel authentication",
    ]

    return any(marker in url or marker in content for marker in markers)


def load_published_website(live_url: str) -> None:
    """Lädt eine öffentliche Website unverändert."""
    live_url = live_url.strip()

    if not live_url.startswith(("https://", "http://")):
        live_url = f"https://{live_url}"

    try:
        response = requests.get(
            live_url,
            headers={"User-Agent": "AI-Website-Builder/1.0"},
            timeout=30,
            allow_redirects=True,
        )
    except requests.RequestException as error:
        raise ValueError(f"Die Website konnte nicht erreicht werden: {error}") from error

    if is_vercel_login_page(response):
        raise ValueError(
            "Die Website ist durch Vercel geschützt oder verlangt eine Anmeldung."
        )

    if response.status_code != 200:
        raise ValueError(f"Die Website konnte nicht geladen werden. HTTP {response.status_code}.")

    # Original unverändert übernehmen: kein KI-Aufruf, keine HTML-Bearbeitung.
    html = require_complete_html(response.text)

    st.session_state.assets = {}
    st.session_state.live_url = response.url
    st.session_state.project_name = get_project_name_from_url(response.url)
    st.session_state.published_html = html
    st.session_state.pending_html = html
    st.session_state.deployment_id = ""


def publish_website() -> None:
    """Veröffentlicht die aktuelle Website bei Vercel."""
    html = require_complete_html(st.session_state.generated_html)
    project_name = safe_project_name(st.session_state.project_name)

    files = [{"file": "index.html", "data": html}]

    for file_name, asset in st.session_state.assets.items():
        files.append(
            {
                "file": file_name,
                "data": asset["base64"],
                "encoding": "base64",
            }
        )

    payload = {
        "name": project_name,
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
    }

    try:
        response = requests.post(
            VERCEL_DEPLOYMENTS_URL,
            headers={
                "Authorization": f"Bearer {VERCEL_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
    except requests.RequestException as error:
        raise ValueError(f"Vercel konnte nicht erreicht werden: {error}") from error

    if response.status_code not in (200, 201):
        try:
            details = response.json()
        except ValueError:
            details = response.text

        raise ValueError(f"Vercel HTTP {response.status_code}: {details}")

    deployment = response.json()
    deployment_url = deployment.get("url")
    deployment_id = deployment.get("id")

    if not deployment_url or not deployment_id:
        raise ValueError(f"Unvollständige Vercel-Antwort: {deployment}")

    st.session_state.project_name = project_name
    st.session_state.live_url = f"https://{deployment_url}"
    st.session_state.deployment_id = deployment_id
    st.session_state.published_html = html


def delete_published_website() -> None:
    """Löscht nur das letzte Deployment dieser Sitzung."""
    deployment_id = st.session_state.deployment_id

    if not deployment_id:
        raise ValueError("Kein Deployment dieser Sitzung zum Löschen gefunden.")

    response = requests.delete(
        f"https://api.vercel.com/v13/deployments/{deployment_id}",
        headers={"Authorization": f"Bearer {VERCEL_TOKEN}"},
        timeout=60,
    )

    if response.status_code not in (200, 202, 204):
        raise ValueError(f"Vercel HTTP {response.status_code}: {response.text}")

    st.session_state.live_url = ""
    st.session_state.deployment_id = ""
    st.session_state.published_html = ""
    st.session_state.delete_confirmation = False


st.title("🚀 KI Website Builder")
st.caption("Website erstellen, bearbeiten, prüfen und veröffentlichen.")

new_tab, manage_tab = st.tabs(["✨ Neue Website", "⚙️ Website laden"])

with new_tab:
    description = st.text_area(
        "Beschreibung der Website",
        placeholder="Beispiel: Moderne Website für ein Kosmetikstudio mit Preisen, Team, Galerie und Kontaktformular.",
        height=170,
    )

    initial_image = st.file_uploader(
        "Logo oder Bild (optional)",
        type=["png", "jpg", "jpeg", "webp"],
    )

    if st.button("✨ Website-Entwurf generieren", type="primary", use_container_width=True):
        if not description.strip():
            st.warning("Bitte beschreibe die gewünschte Website.")
        else:
            with st.status("Website wird erstellt ...", expanded=True) as status:
                try:
                    generate_website(description, initial_image)
                    status.update(label="✅ Entwurf wurde erstellt.", state="complete")
                    st.rerun()
                except Exception as error:
                    status.update(label="❌ Erstellung fehlgeschlagen", state="error")
                    st.error(str(error))

with manage_tab:
    st.caption("Die Original-Website wird unverändert geladen. Geschützte Vercel-Seiten werden blockiert.")

    live_url_input = st.text_input(
        "Öffentlicher Live-Link",
        placeholder="https://deine-website.vercel.app",
    )

    if st.button("⚙️ Website laden", type="primary", use_container_width=True):
        if not live_url_input.strip():
            st.warning("Bitte gib einen Live-Link ein.")
        else:
            with st.status("Website wird geladen ...", expanded=True) as status:
                try:
                    load_published_website(live_url_input)
                    status.update(
                        label="✅ Original-Website wurde unverändert geladen.",
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update(label="❌ Laden fehlgeschlagen", state="error")
                    st.error(str(error))

if st.session_state.live_url:
    st.link_button(
        "🔗 Veröffentlichte Seite unverändert öffnen",
        st.session_state.live_url,
        use_container_width=True,
    )

if st.session_state.generated_html:
    st.divider()
    st.header("Website bearbeiten")

    content_tab, design_tab, image_tab, preview_tab = st.tabs(
        ["📝 Inhalte", "🎨 Design", "🖼️ Bilder", "💻 HTML & Vorschau"]
    )

    with content_tab:
        section = st.selectbox(
            "Bereich auswählen",
            ["Navigation", "Hero", "Über mich", "Leistungen", "Projekte", "Kontakt", "Footer"],
        )
        change_request = st.text_area("Gewünschte Änderung", height=130)

        if st.button("📝 Bereich aktualisieren", use_container_width=True):
            if not change_request.strip():
                st.warning("Bitte beschreibe die gewünschte Änderung.")
            else:
                with st.status("Bereich wird bearbeitet ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Bereich '{section}': {change_request}"
                        )
                        status.update(label="✅ Vorschau wurde aktualisiert.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Änderung fehlgeschlagen", state="error")
                        st.error(str(error))

    with design_tab:
        design_request = st.text_area(
            "Design-Änderung",
            placeholder="Beispiel: Verwende ein dunkles Premium-Design mit goldenen Akzenten und runden Karten.",
            height=130,
        )

        if st.button("🎨 Design aktualisieren", use_container_width=True):
            if not design_request.strip():
                st.warning("Bitte beschreibe die Design-Änderung.")
            else:
                with st.status("Design wird angepasst ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            "Ändere nur Layout, Farben, Abstände und Styling. "
                            "Texte, Bilder und Struktur müssen bleiben. "
                            f"Wunsch: {design_request}"
                        )
                        status.update(label="✅ Design wurde aktualisiert.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Design-Änderung fehlgeschlagen", state="error")
                        st.error(str(error))

    with image_tab:
        image_section = st.selectbox(
            "Abschnitt für das Bild",
            ["Hero", "Über mich", "Leistungen", "Projekte", "Kontakt"],
        )
        image_file = st.file_uploader(
            "Neues Bild",
            type=["png", "jpg", "jpeg", "webp"],
            key="section_image",
        )

        if st.button("🖼️ Bild aktualisieren", use_container_width=True):
            if image_file is None:
                st.warning("Bitte wähle ein Bild aus.")
            else:
                with st.status("Bild wird aktualisiert ...", expanded=True) as status:
                    try:
                        image_name = save_uploaded_image(image_file, image_section)
                        modify_current_website(
                            f"Ändere ausschließlich das Bild im Bereich '{image_section}'. "
                            f'Verwende: <img src="{image_name}" alt="{image_section} Bild">'
                        )
                        status.update(label="✅ Bild wurde aktualisiert.", state="complete")
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Bild-Änderung fehlgeschlagen", state="error")
                        st.error(str(error))

    with preview_tab:
        editor_column, preview_column = st.columns(2, gap="large")

        with editor_column:
            st.text_area("HTML-Quellcode", height=620, key="html_editor")

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
        if st.button("🚀 Website veröffentlichen", type="primary", use_container_width=True):
            with st.status("Website wird auf Vercel veröffentlicht ...", expanded=True) as status:
                try:
                    publish_website()
                    status.update(
                        label="🎉 Website wurde erfolgreich veröffentlicht.",
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Veröffentlichung fehlgeschlagen",
                        state="error",
                        expanded=True,
                    )
                    st.error("Die Veröffentlichung bei Vercel ist fehlgeschlagen.")
                    st.code(str(error), language="text")

    with delete_column:
        if st.session_state.deployment_id:
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
            st.info("Nur Deployments aus der aktuellen Sitzung können gelöscht werden.")