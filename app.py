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

try:
    OPENAI_API_KEY = st.secrets["openai_api_key"]
    VERCEL_TOKEN = st.secrets["vercel_token"]
except KeyError:
    st.error(
        "API-Schlüssel fehlen. Prüfe `.streamlit/secrets.toml`. "
        "Dort müssen `openai_api_key` und `vercel_token` stehen."
    )
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# Daten bleiben bei Streamlit-Neuladen innerhalb derselben Sitzung erhalten.
for key, default_value in {
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "saved_design_html": "",
    "saved_design_name": "",
    "assets": {},
    "live_url": "",
    "deployment_id": "",
    "managed_live_url": "",
    "project_name": "ai-website-builder",
    "delete_confirmation": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Wichtig: Der Editor-Wert wird aktualisiert, bevor das Textfeld erstellt wird.
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


def queue_html_update(html: str) -> None:
    """Plant eine sichere HTML-Aktualisierung für den nächsten Durchlauf."""
    cleaned_html = clean_html(html)

    if not cleaned_html:
        raise ValueError("Die KI hat keinen HTML-Code zurückgegeben.")

    if "<html" not in cleaned_html.lower() and "<!doctype" not in cleaned_html.lower():
        raise ValueError("Die Antwort enthält keinen vollständigen HTML-Code.")

    st.session_state.pending_html = cleaned_html


def save_uploaded_image(uploaded_file, section_name: str) -> str:
    """Speichert ein Bild als Asset und gibt den Dateinamen zurück."""
    if uploaded_file is None:
        raise ValueError("Bitte wähle zuerst ein Bild aus.")

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg"}:
        extension = ".png"

    safe_section_name = re.sub(
        r"[^a-z0-9]+",
        "-",
        section_name.lower(),
    ).strip("-")

    file_name = f"{safe_section_name}-bild{extension}"
    image_bytes = uploaded_file.getvalue()

    mime_type = uploaded_file.type
    if not mime_type:
        mime_type = "image/png" if extension == ".png" else "image/jpeg"

    st.session_state.assets[file_name] = {
        "base64": base64.b64encode(image_bytes).decode("utf-8"),
        "mime_type": mime_type,
    }

    return file_name


def create_preview_html(html: str) -> str:
    """Ersetzt gespeicherte Bilddateien in der lokalen Vorschau durch Base64."""
    preview_html = html

    for file_name, asset in st.session_state.assets.items():
        data_url = f"data:{asset['mime_type']};base64,{asset['base64']}"
        preview_html = preview_html.replace(file_name, data_url)

    return preview_html


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert von OpenAI vollständigen HTML-Code an."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
        temperature=0.4,
    )

    return response.choices[0].message.content or ""


def generate_website(user_prompt: str, uploaded_file) -> None:
    """Erstellt einen neuen Entwurf, veröffentlicht ihn aber nicht."""
    image_instruction = ""

    if uploaded_file is not None:
        image_name = save_uploaded_image(uploaded_file, "profil")

        image_instruction = f"""
Es gibt ein hochgeladenes Profilbild. Binde es im Hero- oder Über-mich-Bereich ein:

<img src="{image_name}" alt="Profilbild">
"""

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein professioneller Frontend-Entwickler und Webdesigner.

Erstelle eine vollständige, moderne, hochwertige und responsive Single-Page-Website.

Regeln:
- Verwende valides HTML5.
- Binde Tailwind CSS mit https://cdn.tailwindcss.com ein.
- Verwende Navigation, Hero-Bereich, Über mich, Fähigkeiten, Projekte,
  Kontaktbereich und Footer.
- Nutze ein professionelles, übersichtliches Design.
- Gib ausschließlich vollständigen HTML-Code zurück.
- Verwende kein Markdown, keine Backticks und keine Erklärungen.
- Beginne direkt mit <!doctype html>.
{image_instruction}
""",
        user_instruction=user_prompt,
    )

    queue_html_update(html)


def modify_current_website(change_request: str) -> None:
    """Ändert nur die gewünschten Teile des aktuellen HTML-Entwurfs."""
    current_html = st.session_state.generated_html.strip()

    if not current_html:
        raise ValueError("Erstelle oder lade zuerst eine Website.")

    html = ask_ai_for_html(
        system_instruction="""
Du bist ein sorgfältiger Frontend-Entwickler.

Du erhältst den vollständigen HTML-Code einer bestehenden Website.
Ändere ausschließlich den gewünschten Bereich. Erhalte alle anderen Texte,
Abschnitte, Bilder und Styles so weit wie möglich.

Regeln:
- Antworte ausschließlich mit vollständigem HTML5.
- Beginne direkt mit <!doctype html>.
- Kein Markdown, keine Backticks und keine Erklärung.
- Tailwind CSS muss weiterhin eingebunden bleiben.
- Entferne keine vorhandenen Bilder oder Abschnitte, außer dies wird verlangt.
""",
        user_instruction=f"""
AKTUELLER HTML-CODE:
{current_html}

GEWÜNSCHTE ÄNDERUNG:
{change_request}
""",
    )

    queue_html_update(html)


def update_preview() -> None:
    """Übernimmt manuelle HTML-Änderungen in die Vorschau."""
    edited_html = st.session_state.html_editor.strip()

    if not edited_html:
        st.warning("Der HTML-Code darf nicht leer sein.")
        return

    st.session_state.generated_html = edited_html


def discard_changes() -> None:
    """Setzt den Entwurf auf die letzte veröffentlichte Version zurück."""
    if st.session_state.published_html:
        st.session_state.pending_html = st.session_state.published_html
    else:
        st.session_state.pending_html = st.session_state.generated_html


def get_project_name_from_url(live_url: str) -> str:
    """Ermittelt einen brauchbaren Vercel-Projektnamen aus dem Live-Link."""
    hostname = urlparse(live_url).hostname or ""
    first_part = hostname.split(".")[0].lower()

    project_name = re.sub(r"[^a-z0-9-]", "-", first_part).strip("-")
    return project_name or "ai-website-builder"


def load_published_website(live_url: str) -> None:
    """Lädt eine veröffentlichte Website über ihren Link in den Editor."""
    live_url = live_url.strip()

    if not live_url.startswith(("https://", "http://")):
        live_url = f"https://{live_url}"

    response = requests.get(
        live_url,
        headers={"User-Agent": "AI-Website-Builder/1.0"},
        timeout=30,
    )

    if response.status_code != 200:
        raise ValueError(
            f"Die Website konnte nicht geladen werden. HTTP {response.status_code}."
        )

    html = response.text.strip()

    if "<html" not in html.lower() and "<!doctype" not in html.lower():
        raise ValueError("Der angegebene Link enthält keine vollständige HTML-Website.")

    st.session_state.managed_live_url = live_url
    st.session_state.live_url = live_url
    st.session_state.project_name = get_project_name_from_url(live_url)
    st.session_state.published_html = html
    st.session_state.pending_html = html


def publish_website() -> None:
    """Veröffentlicht den aktuell sichtbaren Entwurf auf Vercel."""
    html = st.session_state.generated_html.strip()

    if not html:
        raise ValueError("Es gibt keinen Entwurf zum Veröffentlichen.")

    files = [
        {
            "file": "index.html",
            "data": html,
        }
    ]

    # Alle Bilder werden gemeinsam mit index.html veröffentlicht.
    for file_name, asset in st.session_state.assets.items():
        files.append(
            {
                "file": file_name,
                "data": asset["base64"],
                "encoding": "base64",
            }
        )

    response = requests.post(
        "https://api.vercel.com/v13/deployments",
        headers={
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "name": st.session_state.project_name,
            "target": "production",
            "files": files,
        },
        timeout=90,
    )

    if response.status_code not in (200, 201):
        raise ValueError(f"HTTP {response.status_code}: {response.text}")

    deployment = response.json()

    if not deployment.get("url") or not deployment.get("id"):
        raise ValueError(f"Vercel-Antwort unvollständig: {deployment}")

    st.session_state.live_url = f"https://{deployment['url']}"
    st.session_state.managed_live_url = st.session_state.live_url
    st.session_state.deployment_id = deployment["id"]
    st.session_state.published_html = html


def delete_published_website() -> None:
    """Löscht das letzte Deployment der App."""
    deployment_id = st.session_state.deployment_id

    if not deployment_id:
        raise ValueError(
            "Kein Deployment in dieser Sitzung gefunden. "
            "Nur Seiten, die in dieser App veröffentlicht wurden, können hier gelöscht werden."
        )

    response = requests.delete(
        f"https://api.vercel.com/v13/deployments/{deployment_id}",
        headers={"Authorization": f"Bearer {VERCEL_TOKEN}"},
        timeout=60,
    )

    if response.status_code not in (200, 202, 204):
        raise ValueError(f"HTTP {response.status_code}: {response.text}")

    st.session_state.live_url = ""
    st.session_state.managed_live_url = ""
    st.session_state.deployment_id = ""
    st.session_state.published_html = ""
    st.session_state.delete_confirmation = False


st.title("🚀 KI Website Builder")
st.write(
    "Erstelle, bearbeite, speichere und veröffentliche Websites. "
    "Alle Änderungen werden zuerst in einer Vorschau angezeigt."
)
st.divider()

create_tab, manage_tab = st.tabs(
    [
        "✨ Neue Website erstellen",
        "⚙️ Veröffentlichte Seiten verwalten",
    ]
)

with create_tab:
    left_column, right_column = st.columns([1.4, 1], gap="large")

    with left_column:
        st.subheader("Neue Website erstellen")

        user_prompt = st.text_area(
            "Beschreibe die gewünschte Website",
            placeholder=(
                "Beispiel: Moderne Portfolio-Webseite für eine Data-Engineering- "
                "und KI-Spezialistin. Mit Kompetenzen, Projekten und Kontakt."
            ),
            height=180,
        )

        initial_image = st.file_uploader(
            "Profilbild oder Logo für den ersten Entwurf (optional)",
            type=["png", "jpg", "jpeg"],
            key="initial_image",
        )

        if st.button(
            "✨ Neuen Entwurf generieren",
            type="primary",
            use_container_width=True,
        ):
            if not user_prompt.strip():
                st.warning("Bitte gib zuerst eine Beschreibung ein.")
            else:
                with st.status("Entwurf wird erstellt ...", expanded=True) as status:
                    try:
                        st.write("🧠 Erstelle Texte, Struktur und Design ...")
                        generate_website(user_prompt, initial_image)
                        status.update(
                            label="✅ Entwurf erstellt. Vorschau wird geladen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Generierung fehlgeschlagen",
                            state="error",
                            expanded=True,
                        )
                        st.error(f"**OpenAI-Fehler:** {error}")

    with right_column:
        st.subheader("Ablauf")
        st.info(
            "1. Website beschreiben\n\n"
            "2. Entwurf erstellen\n\n"
            "3. Text, Bilder oder Design einzeln ändern\n\n"
            "4. Vorschau prüfen\n\n"
            "5. Erst dann veröffentlichen"
        )

with manage_tab:
    st.subheader("Veröffentlichte Seiten verwalten")
    st.write(
        "Gib den Live-Link einer bereits veröffentlichten Website ein. "
        "Danach kannst du sie bearbeiten, um Abschnitte erweitern und erneut veröffentlichen."
    )

    manage_column, info_column = st.columns([1.4, 1], gap="large")

    with manage_column:
        manage_url = st.text_input(
            "Live-Link der Website",
            placeholder="https://deine-website.vercel.app",
            key="manage_url_input",
        )

        if st.button(
            "⚙️ Veröffentlichte Seite laden und verwalten",
            type="primary",
            use_container_width=True,
        ):
            if not manage_url.strip():
                st.warning("Bitte gib zuerst einen Live-Link ein.")
            else:
                with st.status("Live-Website wird geladen ...", expanded=True) as status:
                    try:
                        st.write("🌐 HTML-Code der Website wird geladen ...")
                        load_published_website(manage_url)
                        status.update(
                            label="✅ Website geladen. Du kannst sie jetzt bearbeiten.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Website konnte nicht geladen werden",
                            state="error",
                            expanded=True,
                        )
                        st.error(f"**Fehler:** {error}")

    with info_column:
        st.info(
            "Nach dem Laden kannst du:\n\n"
            "- Texte und Abschnitte ändern\n"
            "- neue Seitenbereiche ergänzen\n"
            "- Bilder je Abschnitt austauschen\n"
            "- Farben und Layout anpassen\n"
            "- Änderungen prüfen und veröffentlichen"
        )

if st.session_state.live_url:
    st.success("Eine Website ist aktuell geladen oder veröffentlicht.")
    st.markdown(f"### 🔗 [Live-Website öffnen]({st.session_state.live_url})")

if st.session_state.generated_html:
    st.divider()
    st.header("Website bearbeiten")

    st.info(
        "Die Live-Seite bleibt unverändert, bis du unten auf "
        "**„Änderungen veröffentlichen“** klickst."
    )

    tool_tabs = st.tabs(
        [
            "📝 Text & Abschnitte",
            "🎨 Layout & Farben",
            "🖼️ Bilder verwalten",
            "💾 Design speichern",
        ]
    )

    with tool_tabs[0]:
        st.subheader("Text oder Abschnitt bearbeiten")

        text_section = st.selectbox(
            "Bereich auswählen",
            [
                "Navigation",
                "Hero-Bereich",
                "Über mich",
                "Fähigkeiten",
                "Projekte",
                "Kontakt",
                "Footer",
                "Neuen Abschnitt hinzufügen",
            ],
            key="text_section",
        )

        text_change = st.text_area(
            "Gewünschte Änderung",
            placeholder=(
                "Beispiel: Ergänze im Abschnitt Projekte ein neues Projekt "
                "mit Titel, Beschreibung, Technologien und einem Button."
            ),
            height=130,
            key="text_change",
        )

        if st.button("📝 Nur diesen Bereich aktualisieren", use_container_width=True):
            if not text_change.strip():
                st.warning("Bitte beschreibe zuerst die gewünschte Änderung.")
            else:
                with st.status("Bereich wird aktualisiert ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Abschnitt „{text_section}“: "
                            f"{text_change}"
                        )
                        status.update(
                            label="✅ Änderung wird in der Vorschau angezeigt.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Änderung fehlgeschlagen",
                            state="error",
                        )
                        st.error(f"**OpenAI-Fehler:** {error}")

    with tool_tabs[1]:
        st.subheader("Layout und Farben anpassen")

        color_style = st.selectbox(
            "Farbstil",
            [
                "Modernes Blau und Violett",
                "Minimalistisch Schwarz und Weiß",
                "Elegant Beige und Gold",
                "Natürlich Grün und Creme",
                "Kreativ Pink und Violett",
                "Dunkles Premium-Design",
                "Eigene Farben beschreiben",
            ],
            key="color_style",
        )

        layout_style = st.selectbox(
            "Layout-Stil",
            [
                "Bestehendes Layout beibehalten",
                "Minimalistisch mit viel Weißraum",
                "Modern mit Karten",
                "Kreativ und farbenfroh",
                "Seriöses Business-Design",
                "Editorial/Magazin-Stil",
            ],
            key="layout_style",
        )

        custom_design = st.text_input(
            "Zusätzlicher Designwunsch",
            placeholder="Zum Beispiel: größere Buttons, runde Karten, weniger Animationen",
            key="custom_design",
        )

        if st.button("🎨 Nur Layout und Farben aktualisieren", use_container_width=True):
            with st.status("Design wird angepasst ...", expanded=True) as status:
                try:
                    modify_current_website(
                        f"""
Ändere ausschließlich Styling, Layout und Farben.

Farbstil: {color_style}
Layout-Stil: {layout_style}
Zusätzlicher Wunsch: {custom_design or "Keiner"}

Die bestehenden Texte, Abschnitte und Bilder müssen erhalten bleiben.
"""
                    )
                    status.update(
                        label="✅ Design-Änderung wird in der Vorschau angezeigt.",
                        state="complete",
                        expanded=False,
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Design-Änderung fehlgeschlagen",
                        state="error",
                    )
                    st.error(f"**OpenAI-Fehler:** {error}")

    with tool_tabs[2]:
        st.subheader("Bild für einen Abschnitt aktualisieren")

        image_section = st.selectbox(
            "Abschnitt auswählen",
            [
                "Hero-Bereich",
                "Über mich",
                "Fähigkeiten",
                "Projekte",
                "Kontakt",
            ],
            key="image_section",
        )

        section_image = st.file_uploader(
            "Neues Bild auswählen",
            type=["png", "jpg", "jpeg"],
            key="section_image",
        )

        if st.button("🖼️ Nur dieses Bild aktualisieren", use_container_width=True):
            if section_image is None:
                st.warning("Bitte wähle zuerst ein Bild aus.")
            else:
                with st.status("Bild wird eingefügt ...", expanded=True) as status:
                    try:
                        image_name = save_uploaded_image(section_image, image_section)

                        modify_current_website(
                            f"""
Ändere ausschließlich das Bild im Abschnitt „{image_section}“.

Verwende für das neue Bild exakt:
<img src="{image_name}" alt="{image_section} Bild">

Das Bild soll responsiv sein, einen professionellen Bildausschnitt haben
und zum bestehenden Layout passen. Alle anderen Bereiche bleiben unverändert.
"""
                        )

                        status.update(
                            label="✅ Bild-Änderung wird in der Vorschau angezeigt.",
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

    with tool_tabs[3]:
        st.subheader("Design speichern")

        design_name = st.text_input(
            "Name des Designs",
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
            "⬇️ HTML-Design herunterladen",
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
    st.header("Vorschau und erweiterte HTML-Bearbeitung")

    edit_column, preview_column = st.columns([1, 1], gap="large")

    with edit_column:
        st.subheader("HTML direkt bearbeiten")

        st.text_area(
            "HTML-Quellcode",
            height=650,
            key="html_editor",
        )

        preview_button, discard_button = st.columns(2)

        with preview_button:
            st.button(
                "👁️ Vorschau aktualisieren",
                use_container_width=True,
                on_click=update_preview,
            )

        with discard_button:
            if st.button(
                "↩️ Änderungen verwerfen",
                use_container_width=True,
            ):
                discard_changes()
                st.rerun()

    with preview_column:
        st.subheader("Vorschau des Entwurfs")

        st.components.v1.html(
            create_preview_html(st.session_state.generated_html),
            height=650,
            scrolling=True,
        )

    st.divider()
    st.header("Veröffentlichung und Einstellungen")

    publish_column, settings_column = st.columns([1, 1], gap="large")

    with publish_column:
        publish_text = (
            "🔄 Änderungen veröffentlichen"
            if st.session_state.live_url
            else "🚀 Website veröffentlichen"
        )

        if st.button(
            publish_text,
            type="primary",
            use_container_width=True,
        ):
            with st.status("Website wird auf Vercel veröffentlicht ...", expanded=True) as status:
                try:
                    st.write("🌐 Aktueller Entwurf wird hochgeladen ...")
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

    with settings_column:
        if st.session_state.live_url:
            with st.expander("⚙️ Einstellungen der Live-Website"):
                st.markdown(
                    f"[Live-Website öffnen]({st.session_state.live_url})"
                )
                st.warning(
                    "Das Löschen entfernt nur das letzte Deployment, "
                    "das in dieser Sitzung erstellt wurde."
                )

                st.checkbox(
                    "Ich möchte die Live-Website dauerhaft löschen.",
                    key="delete_confirmation",
                )

                if st.button(
                    "🗑️ Live-Website löschen",
                    type="secondary",
                    disabled=not st.session_state.delete_confirmation,
                    use_container_width=True,
                ):
                    with st.status("Live-Website wird gelöscht ...", expanded=True) as status:
                        try:
                            delete_published_website()
                            status.update(
                                label="✅ Live-Website wurde gelöscht.",
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
            st.info("Einstellungen erscheinen nach der Veröffentlichung.")