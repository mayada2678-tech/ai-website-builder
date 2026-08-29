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

# Speichert Daten auch nach Änderungen und Streamlit-Neuladen.
for key, default_value in {
    "generated_html": "",
    "html_editor": "",
    "published_html": "",
    "image_name": "",
    "image_base64": "",
    "image_mime_type": "",
    "live_url": "",
    "deployment_id": "",
    "delete_confirmation": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_value


def create_preview_html(html: str) -> str:
    """Ersetzt die lokale Bilddatei für die Vorschau durch Base64-Bilddaten."""
    if (
        st.session_state.image_name
        and st.session_state.image_base64
        and st.session_state.image_mime_type
    ):
        image_data_url = (
            f"data:{st.session_state.image_mime_type};base64,"
            f"{st.session_state.image_base64}"
        )
        return html.replace(st.session_state.image_name, image_data_url)

    return html


def update_preview() -> None:
    """Übernimmt Editor-Änderungen nur in den Entwurf und die Vorschau."""
    edited_html = st.session_state.html_editor.strip()

    if edited_html:
        st.session_state.generated_html = edited_html


def discard_changes() -> None:
    """Setzt den Editor auf die letzte veröffentlichte oder erzeugte Version zurück."""
    if st.session_state.published_html:
        st.session_state.generated_html = st.session_state.published_html
        st.session_state.html_editor = st.session_state.published_html
    else:
        st.session_state.html_editor = st.session_state.generated_html


def generate_website(user_prompt: str, uploaded_file) -> None:
    """Erstellt einen neuen Entwurf. Die Seite wird dabei nicht veröffentlicht."""
    image_instruction = ""

    if uploaded_file is not None:
        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in {".png", ".jpg", ".jpeg"}:
            extension = ".png"

        st.session_state.image_name = f"upload-bild{extension}"
        image_bytes = uploaded_file.getvalue()
        st.session_state.image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        st.session_state.image_mime_type = uploaded_file.type or (
            "image/png" if extension == ".png" else "image/jpeg"
        )

        image_instruction = f"""
Der Nutzer hat ein Bild hochgeladen.
Binde dieses Bild professionell ein, beispielsweise im Hero- oder Über-mich-Bereich.
Nutze exakt diese Bilddatei:
<img src="{st.session_state.image_name}" alt="Profilbild">
"""
    else:
        st.session_state.image_name = ""
        st.session_state.image_base64 = ""
        st.session_state.image_mime_type = ""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
Du bist ein professioneller Frontend-Entwickler und Webdesigner.
Erstelle eine vollständige, moderne und responsive Einzelseiten-Webseite.

Regeln:
- Verwende vollständiges, valides HTML5.
- Binde Tailwind CSS ein: https://cdn.tailwindcss.com
- Erstelle Navigation, Hero, Über mich, Fähigkeiten, Projekte, Kontakt und Footer.
- Das Design soll hochwertig, modern und mobilfreundlich sein.
- Gib ausschließlich vollständigen HTML-Code zurück.
- Kein Markdown, keine Backticks und keine Erklärungen.
- Beginne direkt mit <!doctype html>.
{image_instruction}
""",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    html = response.choices[0].message.content or ""
    html = html.replace("```html", "").replace("```", "").strip()

    if not html:
        raise ValueError("OpenAI hat keinen HTML-Code zurückgegeben.")

    # Der neue Code ist zunächst nur ein Entwurf.
    st.session_state.generated_html = html
    st.session_state.html_editor = html


def publish_website() -> None:
    """Veröffentlicht den aktuell bearbeiteten Entwurf auf Vercel."""
    html = st.session_state.generated_html.strip()

    if not html:
        raise ValueError("Es gibt keinen HTML-Entwurf zum Veröffentlichen.")

    files = [
        {
            "file": "index.html",
            "data": html,
        }
    ]

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
        raise ValueError(f"Vercel-Antwort ist unvollständig: {deployment}")

    st.session_state.live_url = f"https://{deployment['url']}"
    st.session_state.deployment_id = deployment["id"]

    # Diese Version ist jetzt die letzte veröffentlichte Version.
    st.session_state.published_html = html
    st.session_state.html_editor = html


def delete_published_website() -> None:
    """Löscht das letzte Vercel-Deployment."""
    deployment_id = st.session_state.deployment_id

    if not deployment_id:
        raise ValueError("Es wurde keine veröffentlichte Website gefunden.")

    response = requests.delete(
        f"https://api.vercel.com/v13/deployments/{deployment_id}",
        headers={
            "Authorization": f"Bearer {VERCEL_TOKEN}",
        },
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
    "Erstelle, bearbeite und prüfe deine Website. "
    "Veröffentliche sie erst, wenn du mit der Vorschau zufrieden bist."
)
st.divider()

left_column, right_column = st.columns([1, 1], gap="large")

with left_column:
    st.subheader("1. Beschreibung")

    user_prompt = st.text_area(
        "Was soll auf deiner Website stehen?",
        placeholder=(
            "Beispiel: Moderne Portfolio-Webseite für eine angehende "
            "Data-Engineering- und KI-Spezialistin mit Projekten und Kontakt."
        ),
        height=190,
    )

    st.subheader("2. Optionales Bild")

    uploaded_file = st.file_uploader(
        "Profilbild oder Logo hochladen",
        type=["png", "jpg", "jpeg"],
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
            with st.status("Website-Entwurf wird erstellt ...", expanded=True) as status:
                try:
                    st.write("🧠 Generiere Texte, Design und HTML ...")
                    generate_website(user_prompt, uploaded_file)

                    status.update(
                        label="✅ Entwurf erstellt. Prüfe jetzt die Vorschau.",
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
    st.subheader("Status")

    if st.session_state.live_url:
        st.success("Deine Website ist aktuell veröffentlicht.")
        st.markdown(
            f"### 🔗 [Live-Website öffnen]({st.session_state.live_url})"
        )
        st.caption(
            "Du kannst unten weiter Änderungen machen. "
            "Die Live-Seite ändert sich erst nach „Änderungen veröffentlichen“."
        )
    else:
        st.info(
            "Noch nicht veröffentlicht. Erstelle zuerst einen Entwurf, "
            "prüfe die Vorschau und veröffentliche ihn danach."
        )

    st.subheader("Ablauf")
    st.write(
        "1. Beschreibung eingeben  \n"
        "2. Entwurf generieren  \n"
        "3. HTML bearbeiten und Vorschau prüfen  \n"
        "4. Änderungen veröffentlichen"
    )


if st.session_state.generated_html:
    st.divider()
    st.header("3. Entwurf bearbeiten und Vorschau prüfen")

    if st.session_state.live_url:
        st.info(
            "✏️ Du bearbeitest einen Entwurf. Deine veröffentlichte Website "
            "bleibt unverändert, bis du auf „Änderungen veröffentlichen“ klickst."
        )
    else:
        st.warning(
            "Dieser Entwurf ist noch nicht veröffentlicht. "
            "Prüfe ihn zuerst in der Vorschau."
        )

    edit_column, preview_column = st.columns([1, 1], gap="large")

    with edit_column:
        st.subheader("HTML bearbeiten")

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
            st.button(
                "↩️ Änderungen verwerfen",
                use_container_width=True,
                on_click=discard_changes,
            )

        if st.session_state.live_url:
            st.caption(
                "„Änderungen verwerfen“ setzt den Entwurf auf die zuletzt "
                "veröffentlichte Version zurück."
            )
        else:
            st.caption(
                "„Änderungen verwerfen“ setzt nicht gespeicherte Eingaben "
                "im Editor zurück."
            )

    with preview_column:
        st.subheader("Vorschau des Entwurfs")

        preview_html = create_preview_html(st.session_state.generated_html)

        st.components.v1.html(
            preview_html,
            height=650,
            scrolling=True,
        )

    st.divider()
    st.header("4. Veröffentlichung")

    publish_column, settings_column = st.columns([1, 1], gap="large")

    with publish_column:
        publish_button_text = (
            "🔄 Änderungen veröffentlichen"
            if st.session_state.live_url
            else "🚀 Website veröffentlichen"
        )

        publish_clicked = st.button(
            publish_button_text,
            type="primary",
            use_container_width=True,
        )

        if publish_clicked:
            with st.status("Website wird auf Vercel veröffentlicht ...", expanded=True) as status:
                try:
                    st.write("🌐 Lade den aktuellen Entwurf hoch ...")
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
                st.write("Hier kannst du die veröffentlichte Seite löschen.")
                st.warning(
                    "Das Löschen entfernt das zuletzt veröffentlichte "
                    "Vercel-Deployment dauerhaft."
                )

                st.checkbox(
                    "Ich möchte die veröffentlichte Website dauerhaft löschen.",
                    key="delete_confirmation",
                )

                delete_clicked = st.button(
                    "🗑️ Live-Website dauerhaft löschen",
                    type="secondary",
                    use_container_width=True,
                    disabled=not st.session_state.delete_confirmation,
                )

                if delete_clicked:
                    with st.status("Live-Website wird gelöscht ...", expanded=True) as status:
                        try:
                            delete_published_website()

                            status.update(
                                label="✅ Die Live-Website wurde gelöscht.",
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
            st.info("Einstellungen zum Löschen erscheinen nach der Veröffentlichung.")