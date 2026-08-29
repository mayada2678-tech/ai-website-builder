import base64
from pathlib import Path

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

for key, default_value in {
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "saved_design_html": "",
    "saved_design_name": "",
    "image_name": "",
    "image_base64": "",
    "image_mime_type": "",
    "live_url": "",
    "deployment_id": "",
    "delete_confirmation": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Wichtig: Der HTML-Editor darf nur vor seiner Erstellung verändert werden.
if st.session_state.pending_html:
    st.session_state.generated_html = st.session_state.pending_html
    st.session_state.html_editor = st.session_state.pending_html
    st.session_state.pending_html = ""


def create_preview_html(html: str) -> str:
    """Ersetzt hochgeladene lokale Bilder nur in der Vorschau durch Base64."""
    if (
        st.session_state.image_name
        and st.session_state.image_base64
        and st.session_state.image_mime_type
    ):
        data_url = (
            f"data:{st.session_state.image_mime_type};base64,"
            f"{st.session_state.image_base64}"
        )
        return html.replace(st.session_state.image_name, data_url)

    return html


def clean_html(html: str) -> str:
    """Entfernt mögliche Markdown-Codeblöcke aus der KI-Antwort."""
    return (
        html.replace("```html", "")
        .replace("```HTML", "")
        .replace("```", "")
        .strip()
    )


def queue_html_update(html: str) -> None:
    """Plant eine HTML-Aktualisierung für den nächsten Streamlit-Durchlauf."""
    cleaned_html = clean_html(html)

    if not cleaned_html:
        raise ValueError("Die KI hat keinen HTML-Code zurückgegeben.")

    st.session_state.pending_html = cleaned_html


def update_preview() -> None:
    """Übernimmt den manuell bearbeiteten Code in die Vorschau."""
    edited_html = st.session_state.html_editor.strip()

    if edited_html:
        st.session_state.generated_html = edited_html


def discard_changes() -> None:
    """Setzt den Entwurf auf die letzte veröffentlichte Version zurück."""
    if st.session_state.published_html:
        st.session_state.pending_html = st.session_state.published_html
    else:
        st.session_state.pending_html = st.session_state.generated_html


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert vollständigen HTML-Code von OpenAI an."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": system_instruction,
            },
            {
                "role": "user",
                "content": user_instruction,
            },
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content or ""


def generate_website(user_prompt: str, uploaded_file) -> None:
    """Erstellt einen neuen, noch nicht veröffentlichten Entwurf."""
    image_instruction = ""

    if uploaded_file is not None:
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg"}:
            extension = ".png"

        image_bytes = uploaded_file.getvalue()
        st.session_state.image_name = f"upload-bild{extension}"
        st.session_state.image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        st.session_state.image_mime_type = uploaded_file.type or (
            "image/png" if extension == ".png" else "image/jpeg"
        )

        image_instruction = f"""
Ein Bild wurde hochgeladen. Binde es professionell in den Hero- oder
Über-mich-Bereich ein. Verwende exakt:

<img src="{st.session_state.image_name}" alt="Profilbild">
"""
    else:
        st.session_state.image_name = ""
        st.session_state.image_base64 = ""
        st.session_state.image_mime_type = ""

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein professioneller Frontend-Entwickler und Webdesigner.

Erstelle eine vollständige, moderne, responsive und hochwertige
Einzelseiten-Webseite.

Regeln:
- Nutze valides HTML5.
- Binde Tailwind CSS über https://cdn.tailwindcss.com ein.
- Erstelle Navigation, Hero, Über mich, Fähigkeiten, Projekte, Kontakt und Footer.
- Gib ausschließlich vollständigen HTML-Code zurück.
- Kein Markdown, keine Backticks und keine Erklärungen.
- Beginne direkt mit <!doctype html>.
{image_instruction}
""",
        user_instruction=user_prompt,
    )

    queue_html_update(html)


def modify_current_website(change_request: str) -> None:
    """Ändert nur den vom Benutzer gewünschten Bereich der aktuellen Website."""
    current_html = st.session_state.generated_html

    if not current_html.strip():
        raise ValueError("Erstelle zuerst einen Website-Entwurf.")

    html = ask_ai_for_html(
        system_instruction="""
Du bist ein sorgfältiger Frontend-Entwickler.

Du erhältst vollständigen HTML-Code einer bestehenden Website und eine konkrete
Änderungsanweisung. Ändere nur die gewünschten Bereiche. Erhalte alle anderen
Inhalte, Texte, Abschnitte und das allgemeine Design soweit wie möglich.

Regeln:
- Antworte ausschließlich mit vollständigem HTML5.
- Kein Markdown, keine Backticks und keine Erklärungen.
- Beginne direkt mit <!doctype html>.
- Tailwind CSS muss weiterhin eingebunden bleiben.
""",
        user_instruction=f"""
AKTUELLER HTML-CODE:
{current_html}

GEWÜNSCHTE ÄNDERUNG:
{change_request}
""",
    )

    queue_html_update(html)


def update_image_for_section(uploaded_file, section_name: str) -> None:
    """Ersetzt oder ergänzt ein Bild in einem einzigen gewählten Abschnitt."""
    if uploaded_file is None:
        raise ValueError("Bitte wähle zuerst ein Bild aus.")

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg"}:
        extension = ".png"

    image_bytes = uploaded_file.getvalue()
    st.session_state.image_name = f"{section_name.lower()}-bild{extension}"
    st.session_state.image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    st.session_state.image_mime_type = uploaded_file.type or (
        "image/png" if extension == ".png" else "image/jpeg"
    )

    modify_current_website(
        f"""
Ändere ausschließlich den Bildbereich im Abschnitt „{section_name}“.

Binde das neu hochgeladene Bild exakt so ein:
<img src="{st.session_state.image_name}" alt="{section_name} Bild">

Passe Größe, Bildausschnitt, abgerundete Ecken und responsive Darstellung
professionell an. Alle anderen Abschnitte sollen unverändert bleiben.
"""
    )


def publish_website() -> None:
    """Veröffentlicht den aktuellen Vorschau-Entwurf auf Vercel."""
    html = st.session_state.generated_html.strip()

    if not html:
        raise ValueError("Es gibt keinen Entwurf zum Veröffentlichen.")

    files = [{"file": "index.html", "data": html}]

    if st.session_state.image_name and st.session_state.image_base64:
        files.append(
            {
                "file": st.session_state.image_name,
                "data": st.session_state.image_base64,
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
            "name": "ai-website-builder",
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
    st.session_state.deployment_id = deployment["id"]
    st.session_state.published_html = html


def delete_published_website() -> None:
    """Löscht das zuletzt erstellte Vercel-Deployment."""
    if not st.session_state.deployment_id:
        raise ValueError("Es wurde keine Live-Website gefunden.")

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
st.write(
    "Erstelle einen Entwurf, bearbeite einzelne Bereiche und prüfe jede "
    "Änderung in der Vorschau vor der Veröffentlichung."
)
st.divider()

start_column, status_column = st.columns([1.4, 1], gap="large")

with start_column:
    st.subheader("1. Neue Website erstellen")

    user_prompt = st.text_area(
        "Beschreibe die gewünschte Website",
        placeholder=(
            "Beispiel: Moderne Portfolio-Webseite für eine Data-Engineering- "
            "und KI-Spezialistin. Mit Projekten, Kompetenzen und Kontakt."
        ),
        height=180,
    )

    initial_image = st.file_uploader(
        "Profilbild oder Logo für den ersten Entwurf (optional)",
        type=["png", "jpg", "jpeg"],
        key="initial_image",
    )

    generate_clicked = st.button(
        "✨ Neuen Entwurf generieren",
        type="primary",
        use_container_width=True,
    )

    if generate_clicked:
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

with status_column:
    st.subheader("Status")

    if st.session_state.live_url:
        st.success("Die Website ist veröffentlicht.")
        st.markdown(f"### 🔗 [Live-Website öffnen]({st.session_state.live_url})")
        st.caption(
            "Änderungen bleiben zunächst nur im Entwurf. "
            "Die Live-Seite ändert sich erst nach erneutem Veröffentlichen."
        )
    else:
        st.info("Noch nicht veröffentlicht.")

    if st.session_state.saved_design_html:
        st.success(f"Gespeichertes Design: {st.session_state.saved_design_name}")


if st.session_state.generated_html:
    st.divider()
    st.header("2. Website-Bereiche bearbeiten")

    st.info(
        "Jede Aktion ändert nur den gewünschten Bereich. "
        "Prüfe anschließend rechts die Vorschau."
    )

    tool_tabs = st.tabs(
        [
            "📝 Text & Abschnitte",
            "🎨 Layout & Farben",
            "🖼️ Bild aktualisieren",
            "💾 Design speichern",
        ]
    )

    with tool_tabs[0]:
        st.subheader("Text oder Abschnitt ändern")

        text_section = st.selectbox(
            "Welchen Bereich möchtest du ändern?",
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
            "Was soll geändert oder hinzugefügt werden?",
            placeholder=(
                "Beispiel: Ändere nur den Über-mich-Text. "
                "Füge meinen Namen, meinen Studiengang und drei Sätze "
                "zu meinen Zielen im Bereich KI ein."
            ),
            height=130,
            key="text_change",
        )

        if st.button("📝 Nur diesen Text/Abschnitt aktualisieren", use_container_width=True):
            if not text_change.strip():
                st.warning("Bitte beschreibe die gewünschte Änderung.")
            else:
                with st.status("Textbereich wird aktualisiert ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Abschnitt „{text_section}“: "
                            f"{text_change}"
                        )
                        status.update(
                            label="✅ Änderung wurde in die Vorschau übernommen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Änderung fehlgeschlagen", state="error")
                        st.error(f"**OpenAI-Fehler:** {error}")

    with tool_tabs[1]:
        st.subheader("Layout und Farben ändern")

        color_style = st.selectbox(
            "Farbstil",
            [
                "Keine Änderung",
                "Modernes Blau und Violett",
                "Minimalistisch Schwarz und Weiß",
                "Elegant Beige und Gold",
                "Natürlich Grün und Creme",
                "Kreativ Pink und Violett",
                "Eigene Farben beschreiben",
            ],
        )

        layout_style = st.selectbox(
            "Layout-Stil",
            [
                "Bestehendes Layout beibehalten",
                "Minimalistisch und viel Weißraum",
                "Modern mit Karten",
                "Dunkles Premium-Design",
                "Kreativ und farbenfroh",
                "Seriöses Business-Design",
            ],
        )

        custom_design_change = st.text_input(
            "Zusätzlicher Designwunsch (optional)",
            placeholder="Zum Beispiel: Runde Buttons, größere Schrift, weniger Animationen",
        )

        if st.button("🎨 Nur Layout und Farben aktualisieren", use_container_width=True):
            if color_style == "Keine Änderung" and layout_style == "Bestehendes Layout beibehalten":
                st.warning("Bitte wähle mindestens eine Layout- oder Farbänderung.")
            else:
                with st.status("Design wird angepasst ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"""
Ändere ausschließlich Styling, Layout und Farben.

Farbstil: {color_style}
Layout-Stil: {layout_style}
Zusätzlicher Wunsch: {custom_design_change or "Keiner"}

Die Texte, Bilder, Navigation und Inhaltsstruktur sollen erhalten bleiben.
"""
                        )
                        status.update(
                            label="✅ Design-Änderung in Vorschau übernommen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Design-Änderung fehlgeschlagen", state="error")
                        st.error(f"**OpenAI-Fehler:** {error}")

    with tool_tabs[2]:
        st.subheader("Bild in einem Abschnitt ändern")

        image_section = st.selectbox(
            "In welchem Abschnitt soll das Bild angezeigt werden?",
            [
                "Hero-Bereich",
                "Über mich",
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
                with st.status("Bild wird in den Abschnitt eingefügt ...", expanded=True) as status:
                    try:
                        update_image_for_section(section_image, image_section)
                        status.update(
                            label="✅ Bild-Änderung in Vorschau übernommen.",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(label="❌ Bild-Änderung fehlgeschlagen", state="error")
                        st.error(f"**Fehler:** {error}")

    with tool_tabs[3]:
        st.subheader("Design sichern")

        design_name = st.text_input(
            "Name des gespeicherten Designs",
            value="Mein Website-Design",
        )

        if st.button("💾 Design in dieser Sitzung speichern", use_container_width=True):
            st.session_state.saved_design_html = st.session_state.generated_html
            st.session_state.saved_design_name = design_name.strip() or "Mein Website-Design"
            st.success("Design wurde gespeichert.")

        st.download_button(
            "⬇️ Design als HTML-Datei herunterladen",
            data=st.session_state.generated_html,
            file_name="mein-website-design.html",
            mime="text/html",
            use_container_width=True,
        )

        if st.session_state.saved_design_html:
            if st.button("↩️ Gespeichertes Design wiederherstellen", use_container_width=True):
                st.session_state.pending_html = st.session_state.saved_design_html
                st.success("Gespeichertes Design wird wiederhergestellt.")
                st.rerun()

    st.divider()
    st.header("3. HTML bearbeiten und Vorschau")

    edit_column, preview_column = st.columns([1, 1], gap="large")

    with edit_column:
        st.subheader("Erweiterte HTML-Bearbeitung")

        st.text_area(
            "HTML-Quellcode",
            height=650,
            key="html_editor",
        )

        preview_button, discard_button = st.columns(2)

        with preview_button:
            st.button(
                "👁️ Vorschau aktualisieren",
                on_click=update_preview,
                use_container_width=True,
            )

        with discard_button:
            if st.button("↩️ Änderungen verwerfen", use_container_width=True):
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
    st.header("4. Veröffentlichung")

    publish_column, settings_column = st.columns([1, 1], gap="large")

    with publish_column:
        button_text = (
            "🔄 Änderungen veröffentlichen"
            if st.session_state.live_url
            else "🚀 Website veröffentlichen"
        )

        if st.button(button_text, type="primary", use_container_width=True):
            with st.status("Website wird veröffentlicht ...", expanded=True) as status:
                try:
                    st.write("🌐 Lade den geprüften Entwurf zu Vercel hoch ...")
                    publish_website()
                    status.update(
                        label="🎉 Website wurde veröffentlicht.",
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
                st.markdown(f"[Live-Website öffnen]({st.session_state.live_url})")
                st.warning(
                    "Das Löschen entfernt das zuletzt veröffentlichte "
                    "Vercel-Deployment dauerhaft."
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
            st.info("Die Einstellungen erscheinen nach der Veröffentlichung.")