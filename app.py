"""Einstiegspunkt des AI Website Builders.

Die Anwendung ist aufgeteilt in:
- logic.py: Konfiguration, Datenbank, Website-Erstellung und Veröffentlichung
- chat.py:  Hilfe-Chatbot und Kunden-Chatbot der erstellten Websites
- gui.py:   Streamlit-Oberfläche

Hier wird nur die Reihenfolge festgelegt, in der alles aufgerufen wird.
"""

import streamlit as st

st.set_page_config(
    page_title="AI Website Builder",
    page_icon=":material/auto_awesome:",
    layout="wide",
)

from gui import (  # noqa: E402  (set_page_config muss zuerst laufen)
    apply_global_styles,
    render_authentication_gate,
    render_domain_and_deployment_ui,
    render_generated_website_editor,
    render_language_switcher,
    render_main_tabs,
    render_sidebar,
)
from logic import (  # noqa: E402
    OPENAI_API_KEY,
    VERCEL_TOKEN,
    apply_pending_html_update,
    initialize_database,
    initialize_session_state,
)

apply_global_styles()
initialize_database()

if not OPENAI_API_KEY or not VERCEL_TOKEN:
    st.error(
        "API-Schlüssel fehlen. Hinterlege `openai_api_key` und "
        "`vercel_token` in `.streamlit/secrets.toml`."
    )
    st.stop()

initialize_session_state()
render_language_switcher()
apply_pending_html_update()

user_info = render_authentication_gate()
render_sidebar(user_info)
render_main_tabs()
render_generated_website_editor()

st.divider()
render_domain_and_deployment_ui()
