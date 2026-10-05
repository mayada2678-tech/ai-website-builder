"""Streamlit-Oberfläche: Seitenstil, Anmeldung, Formulare, Editoren,
Vorschau, Kundenservice, Datenschutz und Veröffentlichung.
"""

import json
import re
import uuid
from functools import partial

import streamlit as st
from domain_provisioning import (
    ProvisioningError,
    check_domain_with_registrar,
    normalize_domain,
)

from logic import (
    APP_LANGUAGE_LABELS,
    APP_LANGUAGES,
    apply_app_language,
    apply_background_preset,
    apply_industry_content_preset,
    apply_saved_website,
    authenticate_user,
    AUTHENTICATION_COPY,
    BACKGROUND_PRESET_COLORS,
    build_offer_page_section,
    build_website_zip,
    confirm_stripe_checkout,
    create_analytics_optimized_version,
    create_deployment_project_name,
    build_draft_preview_pages,
    build_template_preview_pages,
    create_preview_html,
    create_professional_standard_draft,
    create_stripe_checkout_session,
    delete_previous_vercel_deployment,
    delete_published_website,
    delete_saved_website,
    DOMAIN_PRICE_EUR,
    generate_website,
    get_creation_form_copy,
    get_project_name_from_url,
    get_support_requests,
    get_template_preview_copy,
    check_external_domain,
    connect_external_domain,
    get_owned_domains,
    get_user_status,
    get_websites,
    INDUSTRY_CONTENT_PRESETS,
    INWX_PASSWORD,
    INWX_USERNAME,
    load_published_website,
    load_uploaded_html_template,
    load_website,
    modify_current_website,
    optimize_editor_text,
    optimize_text_with_transformer,
    OTHER_INDUSTRY_OPTION,
    PRIVACY_CONTACT_EMAIL,
    PRIVACY_CONTROLLER_ADDRESS,
    PRIVACY_CONTROLLER_NAME,
    publish_copy,
    publish_to_owned_domain,
    publish_website,
    queue_html_update,
    register_user,
    replace_first_image_source,
    replace_visible_text,
    require_complete_html,
    safe_project_name,
    set_primary_button_target,
    sync_domain_orders,
    save_support_request,
    save_uploaded_image,
    save_website,
    STRIPE_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_SUCCESS_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
    SUPPORT_ADMIN_EMAIL,
    SUPPORTED_LANGUAGES,
    t,
    TARGET_LANGUAGE_BY_APP_CODE,
    TEMPLATES,
    update_draft_with_mcp_tool,
    wait_for_domain_provisioning,
    workspace_copy,
)

from chat import (
    CHATBOT_FIGURE_ICONS,
)


def show_after_rerun(message: str) -> None:
    """Merkt eine Erfolgsmeldung vor, damit sie nach st.rerun() sichtbar bleibt."""
    st.session_state.flash_message = message


def render_flash_message() -> None:
    """Zeigt eine vor dem letzten Neustart vorgemerkte Erfolgsmeldung an."""
    message = str(st.session_state.pop("flash_message", "") or "")
    if message:
        st.toast(message, icon=":material/check_circle:")


# Streamlit verlangt die Registrierung in jedem Skriptlauf. Die Definition wird
# daher hier nur vorbereitet und erst beim Rendern registriert.
LIVE_SITE_PREVIEW = partial(
    st.components.v2.component,
    "live_site_preview",
    html='<section class="site-preview" aria-label="Live-Vorschau"></section>',
    css="""
    .site-preview { --chrome: #0b1220; --chrome-line: rgba(148, 163, 184, .18); --chrome-text: #e2e8f0; --chrome-muted: #94a3b8; --accent: #22d3ee;
        overflow: hidden; border: 1px solid var(--chrome-line); border-radius: 12px; background: var(--chrome);
        box-shadow: 0 24px 60px rgba(0, 0, 0, .35); font: 13px/1.4 ui-sans-serif, -apple-system, "Segoe UI", sans-serif; color: var(--chrome-text); }
    .site-preview__bar { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 14px; padding: 10px 14px; border-bottom: 1px solid var(--chrome-line); }
    .site-preview__dots { display: flex; gap: 6px; } .site-preview__dots span { width: 11px; height: 11px; border-radius: 50%; background: #334155; }
    .site-preview__dots span:nth-child(1) { background: #f87171; } .site-preview__dots span:nth-child(2) { background: #fbbf24; } .site-preview__dots span:nth-child(3) { background: #34d399; }
    .site-preview__address { display: flex; align-items: center; gap: 8px; min-width: 0; padding: 7px 12px; border-radius: 8px; background: rgba(148, 163, 184, .1); color: var(--chrome-muted); }
    .site-preview__address strong { color: var(--chrome-text); font-weight: 600; }
    .site-preview__address span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .site-preview__lock { flex: none; width: 12px; height: 12px; color: #34d399; }
    .site-preview__actions { display: flex; align-items: center; gap: 10px; }
    .site-preview__devices { display: flex; padding: 3px; border-radius: 8px; background: rgba(148, 163, 184, .1); }
    .site-preview button { border: 0; background: transparent; color: var(--chrome-muted); font: inherit; cursor: pointer; }
    .site-preview__devices button { display: grid; place-items: center; width: 34px; height: 28px; border-radius: 6px; }
    .site-preview__devices button svg { width: 16px; height: 16px; }
    .site-preview__devices button[aria-pressed="true"] { background: var(--chrome-text); color: var(--chrome); }
    .site-preview__open { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border: 1px solid var(--chrome-line) !important; border-radius: 8px; color: var(--chrome-text) !important; }
    .site-preview__open svg { width: 14px; height: 14px; }
    .site-preview button:hover { color: var(--chrome-text); }
    .site-preview button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .site-preview__tabs { display: flex; gap: 4px; overflow-x: auto; padding: 0 12px; border-bottom: 1px solid var(--chrome-line); scrollbar-width: thin; }
    .site-preview__tabs:empty { display: none; }
    .site-preview__tabs button { flex: none; padding: 10px 12px; border-bottom: 2px solid transparent !important; white-space: nowrap; }
    .site-preview__tabs button[aria-selected="true"] { color: var(--chrome-text); border-bottom-color: var(--accent) !important; font-weight: 600; }
    .site-preview__stage { position: relative; display: flex; justify-content: center; overflow: hidden; padding: 18px; background:
        radial-gradient(circle at 1px 1px, rgba(148, 163, 184, .14) 1px, transparent 0) 0 0 / 18px 18px, #0f172a; }
    .site-preview__device { flex: none; overflow: hidden; border-radius: 8px; background: #fff; box-shadow: 0 12px 34px rgba(0, 0, 0, .45); transform-origin: top center; }
    .site-preview__device.is-phone { border: 10px solid #020617; border-radius: 28px; }
    .site-preview__device.is-tablet { border: 12px solid #020617; border-radius: 20px; }
    .site-preview iframe { display: block; width: 100%; height: 100%; border: 0; background: #fff; }
    .site-preview__status { display: flex; justify-content: space-between; gap: 12px; padding: 8px 14px; border-top: 1px solid var(--chrome-line); color: var(--chrome-muted); font-size: 12px; }
    .site-preview__notice { color: #fbbf24; }
    @media (max-width: 640px) { .site-preview__bar { grid-template-columns: minmax(0, 1fr) auto; } .site-preview__dots, .site-preview__open span { display: none; } }
    """,
    js="""
    const ICONS = {
        desktop: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
        tablet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M11 18h2"/></svg>',
        mobile: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg>',
        open: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
        lock: '<svg class="site-preview__lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
    };
    const DEVICES = { desktop: 1280, tablet: 820, mobile: 390 };

    // Wird in jede Vorschauseite eingefügt: interne Links wechseln die Seite,
    // externe öffnen in neuem Tab, Formulare mit Ziel-Adresse werden nicht gesendet.
    function previewPageHelper(token, pageList) {
        const pages = new Set(pageList);
        const post = (message) => parent.postMessage(Object.assign({ token }, message), '*');
        const pageOf = (href) => {
            const clean = href.replace(/^\\.?\\//, '').split(/[?#]/)[0];
            if (!clean) return 'index.html';
            if (pages.has(clean)) return clean;
            if (pages.has(clean + '.html')) return clean + '.html';
            return null;
        };
        document.addEventListener('click', (event) => {
            const link = event.target.closest && event.target.closest('a[href]');
            if (!link) return;
            const href = link.getAttribute('href') || '';
            if (href.startsWith('#')) {
                event.preventDefault();
                const id = decodeURIComponent(href.slice(1));
                const target = id && document.getElementById(id);
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                else scrollTo({ top: 0, behavior: 'smooth' });
                return;
            }
            if (/^(mailto:|tel:|https?:|\\/\\/)/i.test(href)) {
                event.preventDefault();
                post({ type: 'external', href: link.href });
                return;
            }
            const page = pageOf(href);
            if (page) {
                event.preventDefault();
                post({ type: 'navigate', page });
            }
        }, true);
        document.addEventListener('submit', (event) => {
            const action = (event.target.getAttribute('action') || '').trim();
            if (action) {
                event.preventDefault();
                post({ type: 'form' });
            }
        }, true);
    }

    // Quelltext der Funktion wird unverändert eingefügt (keine Escape-Verluste).
    const helperScript = (token, pages) =>
        '<script>(' + previewPageHelper.toString() + ')(' + JSON.stringify(token) + ',' + JSON.stringify(pages) + ');<' + '/script>';

    const withHelper = (html, token, pages) => {
        const script = helperScript(token, pages);
        return /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (head) => head + script) : script + html;
    };

    export default function(component) {
        const { data, parentElement } = component;
        const root = parentElement.querySelector('.site-preview');
        if (!root || !data) return;
        const pageNames = Object.keys(data.pages || {});
        const state = root.__state || (root.__state = { device: 'desktop', page: 'index.html', token: Math.random().toString(36).slice(2) });
        if (!pageNames.includes(state.page)) state.page = pageNames[0] || 'index.html';
        const labels = data.labels;

        root.replaceChildren();
        root.dir = 'ltr';
        const element = (tag, className, html) => { const node = document.createElement(tag); if (className) node.className = className; if (html !== undefined) node.innerHTML = html; return node; };

        const bar = element('div', 'site-preview__bar');
        bar.append(element('div', 'site-preview__dots', '<span></span><span></span><span></span>'));
        const address = element('div', 'site-preview__address', ICONS.lock);
        const addressText = element('span');
        address.append(addressText);
        bar.append(address);
        const actions = element('div', 'site-preview__actions');
        const devices = element('div', 'site-preview__devices');
        devices.setAttribute('role', 'group');
        devices.setAttribute('aria-label', labels.devices);
        Object.keys(DEVICES).forEach((device) => {
            const button = element('button', '', ICONS[device]);
            button.type = 'button';
            button.title = labels[device];
            button.setAttribute('aria-label', labels[device]);
            button.setAttribute('aria-pressed', String(state.device === device));
            button.onclick = () => { state.device = device; render(); devices.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === button))); };
            devices.append(button);
        });
        const openButton = element('button', 'site-preview__open', `${ICONS.open}<span>${labels.open}</span>`);
        openButton.type = 'button';
        openButton.onclick = () => {
            const html = data.pages[state.page] || '';
            const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
            window.open(url, '_blank', 'noopener');
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        };
        actions.append(devices, openButton);
        bar.append(actions);

        const tabs = element('div', 'site-preview__tabs');
        tabs.setAttribute('role', 'tablist');
        if (pageNames.length > 1) {
            pageNames.forEach((page) => {
                const tab = element('button');
                tab.type = 'button';
                tab.textContent = (data.pageLabels || {})[page] || page;
                tab.setAttribute('role', 'tab');
                tab.onclick = () => { state.page = page; loadPage(); };
                tab.dataset.page = page;
                tabs.append(tab);
            });
        }

        const stage = element('div', 'site-preview__stage');
        const device = element('div', 'site-preview__device');
        const frame = document.createElement('iframe');
        frame.title = labels.frameTitle;
        // Abgeschottet: kein Zugriff auf den Builder, keine echten Formularziele.
        frame.setAttribute('sandbox', 'allow-scripts allow-forms allow-popups allow-modals');
        device.append(frame);
        stage.append(device);
        const status = element('div', 'site-preview__status');
        const statusText = element('span', '', labels.hint);
        const notice = element('span', 'site-preview__notice');
        status.append(statusText, notice);
        root.append(bar, tabs, stage, status);

        const height = Number(data.height) || 720;
        function render() {
            const width = DEVICES[state.device];
            const available = Math.max(280, stage.clientWidth - 36);
            const scale = Math.min(1, available / width);
            device.className = 'site-preview__device' + (state.device === 'mobile' ? ' is-phone' : state.device === 'tablet' ? ' is-tablet' : '');
            const frameHeight = state.device === 'desktop' ? height / scale : Math.min(height / scale, state.device === 'mobile' ? 780 : 1100);
            device.style.width = `${width}px`;
            device.style.height = `${frameHeight}px`;
            device.style.transform = `scale(${scale})`;
            stage.style.height = `${frameHeight * scale + 36}px`;
            notice.textContent = scale < 1 ? `${Math.round(scale * 100)} %` : '';
        }
        function loadPage() {
            const html = data.pages[state.page] || `<p style="font-family:sans-serif;padding:24px">${labels.empty}</p>`;
            frame.srcdoc = withHelper(html, state.token, pageNames);
            addressText.innerHTML = `<strong>${data.host}</strong>/${state.page === 'index.html' ? '' : state.page}`;
            tabs.querySelectorAll('button').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.page === state.page)));
            notice.textContent = '';
            render();
        }

        if (root.__onMessage) window.removeEventListener('message', root.__onMessage);
        root.__onMessage = (event) => {
            if (event.source !== frame.contentWindow || !event.data || event.data.token !== state.token) return;
            if (event.data.type === 'navigate' && data.pages[event.data.page]) { state.page = event.data.page; loadPage(); }
            if (event.data.type === 'external' && typeof event.data.href === 'string') window.open(event.data.href, '_blank', 'noopener');
            if (event.data.type === 'form') { notice.textContent = labels.formBlocked; }
        };
        window.addEventListener('message', root.__onMessage);
        if (root.__resize) root.__resize.disconnect();
        root.__resize = new ResizeObserver(() => render());
        root.__resize.observe(stage);
        loadPage();
    }
    """,
)


def apply_global_styles() -> None:
    """Setzt das globale Erscheinungsbild der Builder-Oberfläche."""
    st.markdown(
        """
    <style>
    .stApp {
        background: radial-gradient(circle at 88% 4%, rgba(34, 211, 238, 0.12), transparent 23%), #111827;
    }
    [data-testid="stHeader"] {
        background: transparent;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(103, 232, 249, 0.16);
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.7rem;
    }
    .stButton > button {
        min-height: 2.65rem;
        font-weight: 600;
        border-radius: 0.4rem;
        transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
    }
    .stButton > button:not(:disabled):hover {
        border-color: #67e8f9;
        transform: translateY(-1px);
    }
    .stButton > button:focus-visible,
    [data-testid="stTextInput"] input:focus-visible,
    [data-testid="stTextArea"] textarea:focus-visible {
        outline: 2px solid #22d3ee;
        outline-offset: 2px;
    }
    .st-key-delete_published_site_from_domain_center > button:not(:disabled) {
        background: #facc15;
        border-color: #facc15;
        color: #1f2937;
    }
    .st-key-delete_published_site_from_domain_center > button:not(:disabled):hover {
        background: #eab308;
        border-color: #eab308;
        color: #111827;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        min-height: 2.65rem;
    }
    [data-testid="stTextArea"] textarea {
        line-height: 1.5;
    }
    [data-testid="stTabs"] [role="tab"] {
        font-weight: 600;
        min-height: 2.65rem;
        padding-inline: 1rem;
    }
    [data-testid="stTabs"] [role="tablist"] {
        gap: 0.3rem;
        border-bottom-color: rgba(103, 232, 249, 0.16);
    }
    [data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }
    [data-testid="stExpander"] {
        border-color: rgba(103, 232, 249, 0.18);
    }
    .st-key-authentication_shell {
        width: min(68rem, calc(100vw - 2rem));
        min-height: 35rem;
        margin: 3rem auto 2rem;
        padding: 1.25rem;
        border: 1px solid rgba(103, 232, 249, 0.22);
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(17, 34, 52, 0.92));
        box-shadow: 0 1.5rem 4rem rgba(0, 0, 0, 0.22);
    }
    .st-key-authentication_shell [data-testid="stHorizontalBlock"] {
        min-height: 31rem;
        align-items: stretch;
    }
    .st-key-authentication_shell [data-testid="stColumn"]:first-child {
        padding: 1.35rem 2rem 1.35rem 0.75rem;
        border-right: 1px solid rgba(103, 232, 249, 0.16);
    }
    .st-key-authentication_shell [data-testid="stColumn"]:last-child {
        padding: 1.35rem 0.75rem 1.35rem 2rem;
    }
    .st-key-authentication_shell [data-testid="stTextInput"] input {
        min-height: 2.85rem;
    }
    .st-key-authentication_shell [data-testid="InputInstructions"] {
        display: none;
    }
    .st-key-authentication_shell [data-testid="stFormSubmitButton"] button {
        min-height: 3rem;
    }
    .st-key-authentication_shell [data-testid="stTabs"] {
        margin-top: 0.4rem;
    }
    .st-key-authentication_shell [data-testid="stForm"] {
        padding-top: 0.55rem;
    }
    @media (max-width: 640px) {
        .st-key-authentication_shell {
            width: calc(100vw - 1rem);
            min-height: auto;
            margin-top: 1.25rem;
            padding: 0.5rem;
        }
        .st-key-authentication_shell [data-testid="stHorizontalBlock"] {
            min-height: auto;
        }
        .st-key-authentication_shell [data-testid="stColumn"]:first-child,
        .st-key-authentication_shell [data-testid="stColumn"]:last-child {
            padding: 1rem 0.5rem;
            border-right: 0;
        }
    }
    [data-testid="stPopoverBody"] {
        width: min(22rem, calc(100vw - 2rem)) !important;
        max-width: calc(100vw - 2rem) !important;
        max-height: min(22rem, calc(100vh - 6rem)) !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_payment_ui(user_id: int, user_email: str) -> None:
    """Zeigt die verfügbaren Stripe-Zahlungswege für das Premium-Abonnement."""
    st.subheader("Premium-Abonnement")
    st.caption(
        "Mit Premium veröffentlichen Sie Websites mit Wunsch-URL und eigener Domain. "
        f"Das Abonnement wird für {user_email} abgeschlossen."
    )
    if STRIPE_SECRET_KEY and STRIPE_PRICE_ID and STRIPE_SUCCESS_URL:
        if st.button(
            "Stripe Checkout öffnen",
            icon=":material/open_in_new:",
            key="open_stripe_checkout",
            width="stretch",
        ):
            try:
                st.session_state.stripe_checkout_url = create_stripe_checkout_session(
                    user_id, user_email
                )
            except ValueError as error:
                st.error(str(error))
        checkout_url = str(st.session_state.get("stripe_checkout_url", ""))
        if checkout_url:
            st.link_button(
                "Sicheren Checkout fortsetzen",
                checkout_url,
                icon=":material/lock:",
                width="stretch",
            )
    else:
        st.error(
            "Der kontogebundene Stripe Checkout ist noch nicht eingerichtet. "
            "Hinterlegen Sie stripe_secret_key, stripe_price_id und stripe_success_url."
        )


def render_language_switcher() -> None:
    """Rendert die App-Sprachauswahl und die Rechts-nach-links-Darstellung."""
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.selectbox(
            t("app_language"),
            list(APP_LANGUAGES),
            format_func=lambda name: APP_LANGUAGE_LABELS[name],
            key="app_language_name",
            on_change=apply_app_language,
            width=230,
        )

    if st.session_state.app_language in {"ar", "ku"}:
        st.markdown(
            """
        <style>
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"],
        [data-testid="stTextArea"],
        [data-testid="stMarkdownContainer"] {
            direction: rtl;
            text-align: right;
        }
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
            direction: rtl;
            text-align: right;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )


def show_authentication() -> None:
    """Rendert Anmeldung und Registrierung, bevor der Builder erreichbar ist."""
    authentication_copy = AUTHENTICATION_COPY.get(
        str(st.session_state.app_language), AUTHENTICATION_COPY["en"]
    )
    with st.container(border=True, key="authentication_shell"):
        intro_column, form_column = st.columns((1.05, 0.95), gap="large")

        with intro_column:
            st.badge(
                authentication_copy["workflow"],
                icon=":material/auto_awesome:",
                color="blue",
            )
            st.title(t("auth_title"), anchor=False)
            st.write(t("auth_subtitle"))
            st.space("small")
            st.markdown(f":material/check_circle: {authentication_copy['plan']}")
            st.markdown(f":material/visibility: {authentication_copy['review']}")
            st.markdown(f":material/rocket_launch: {authentication_copy['publish']}")
            st.space("small")
            st.caption(authentication_copy["privacy"])

        with form_column:
            st.subheader(authentication_copy["workspace"], anchor=False)
            st.caption(authentication_copy["workspace_hint"])
            login_tab, register_tab = st.tabs([t("login"), t("register")])

            with login_tab:
                with st.form("login_form"):
                    email = st.text_input(t("email"), key="login_email")
                    password = st.text_input(
                        t("password"),
                        type="password",
                        key="login_password",
                    )
                    submitted = st.form_submit_button(
                        t("login"),
                        type="primary",
                        width="stretch",
                    )

                if submitted:
                    user = authenticate_user(email, password)
                    if user is None:
                        st.error(t("invalid_login"))
                    else:
                        st.session_state.user_id, st.session_state.user_email = user
                        st.rerun()

            with register_tab:
                with st.form("registration_form"):
                    email = st.text_input(t("email"), key="registration_email")
                    password = st.text_input(
                        t("password"),
                        type="password",
                        key="registration_password",
                    )
                    password_confirmation = st.text_input(
                        t("confirm_password"),
                        type="password",
                        key="registration_password_confirmation",
                    )
                    submitted = st.form_submit_button(
                        t("register"),
                        type="primary",
                        width="stretch",
                    )

                if submitted:
                    if password != password_confirmation:
                        st.error(t("password_mismatch"))
                    else:
                        try:
                            register_user(email, password)
                            st.success(t("account_created"))
                        except ValueError as error:
                            st.error(str(error))


def render_authentication_gate() -> dict:
    """Erzwingt die Anmeldung und zeigt Test- bzw. Premiumstatus an."""
    if st.session_state.user_id is None:
        show_authentication()
        st.stop()

    current_user_id = int(st.session_state.user_id)

    user_info = get_user_status(current_user_id)

    return_to_publish = st.query_params.get("publish") == "1"

    if confirm_stripe_checkout(current_user_id):
        st.session_state.publish_after_checkout = return_to_publish and not st.session_state.get(
            "paid_domain_checkout_session_id"
        )
        show_after_rerun("Zahlung bestätigt. Die Veröffentlichung ist jetzt freigeschaltet.")
        st.rerun()

    if not user_info["subscribed"] and not user_info["trial_active"]:
        st.warning(
            "Ihre kostenlose 24-Stunden-Testphase ist abgelaufen. Mit Premium können Sie "
        "weiter Websites erstellen und veröffentlichen."
        )
        render_payment_ui(current_user_id, st.session_state.user_email)
    elif not user_info["subscribed"]:
        st.info(
            workspace_copy()["trial_active"].format(
                hours=user_info["trial_remaining_hours"]
            )
        )
    return user_info


def render_analytics_optimization_ui(user_email: str) -> None:
    """Rendert den manuellen Startpunkt für den datengestützten Optimierungsjob."""
    if not SUPPORT_ADMIN_EMAIL or user_email.strip().lower() != SUPPORT_ADMIN_EMAIL:
        return
    st.divider()
    st.subheader("KI-Optimierung und A/B-Test", anchor=False)
    st.caption(
        "Analysiert ausschließlich aggregierte Sitzungsdaten. Ab 500 Sitzungen erstellt die KI "
        "eine Testversion; die Live-Website wird dabei nicht automatisch überschrieben."
    )
    st.code(str(st.session_state.analytics_site_id), language=None)
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        st.warning(
            "Supabase ist noch nicht konfiguriert. Führen Sie supabase_schema.sql aus und "
            "hinterlegen Sie supabase_url sowie supabase_service_role_key in den Secrets."
        )
        return
    if st.button(
        "Analytics auswerten und Testversion erstellen",
        icon=":material/auto_awesome:",
        key="run_analytics_optimization",
        disabled=not st.session_state.generated_html,
        width="stretch",
    ):
        with st.status("Analytics werden ausgewertet ...", expanded=True) as status:
            try:
                summary, version = create_analytics_optimized_version()
                status.update(label="Testversion wurde erstellt.", state="complete")
                show_after_rerun(
                    f"{summary.sessions} Sitzungen ausgewertet. Version "
                    f"{version.get('version_id', '')} ist als testing gespeichert und in der Vorschau geladen."
                )
                st.rerun()
            except Exception as error:
                status.update(label="Optimierung konnte nicht ausgeführt werden.", state="error")
                st.error(str(error))


def render_client_contact_ui() -> None:
    """Erfasst die Kontaktdaten, die in jede neue Kundenwebsite einfliessen."""
    language = str(st.session_state.app_language)
    copy_by_language = {
        "de": ["Geschäfts- und Kontaktdaten des Kunden", "E-Mail-Adresse für Kundenanfragen", "z. B. info@unternehmen.de", "Offizieller Unternehmensname", "z. B. Autohaus Müller GmbH", "Slogan oder Hauptüberschrift (optional)", "z. B. Ihr Partner für Qualität und Vertrauen", "Telefonnummer (optional)", "z. B. +49 30 123456", "Web3Forms Access Key (optional)", "Mit diesem Schlüssel erhält die generierte Website ein Web3Forms-Kontaktformular.", "Kunden-Chatbot konfigurieren", "Allgemeiner Kundenservice", "Der Chatbot erhält automatisch Basiswissen über die Branche: {industry}. Er wird beim Erstellen in die Kundenwebsite eingefügt. Für KI-Antworten nach der Veröffentlichung muss im Vercel-Projekt einmalig HF_API_KEY gesetzt sein.", "Hinterlegen Sie die Firmendaten, die der Chatbot Ihren Website-Besuchern nennen darf.", "Öffnungszeiten", "z. B. Mo-Fr: 08:00-17:00 Uhr", "Telefon und weitere Kontaktwege", "z. B. +49 30 123456 oder info@unternehmen.de", "Preise und wichtige Leistungen", "z. B. Erstberatung kostenlos, Wartung ab 89 Euro", "Notfall und Bereitschaft", "z. B. Notdienst unter +49 171 123456", "Chat-Designfarbe", "Form des Chat-Icons", "Chatbot-Figur", "Name des Chatbots", "Position des Chatbots", "Beim Scrollen sichtbar halten", "Aktiv: Der Chatbot bleibt am Bildschirmrand. Deaktiviert: Er steht am Ende der Seite.", "Chatbot bereit: Die Firmendaten werden automatisch in Vorschau, ZIP und veröffentlichte Website übernommen.", "Empfehlung: Ergänzen Sie Öffnungszeiten, Leistungen, Preise oder den Notdienst. Ohne eigene Angaben verwendet der Chatbot das Branchenwissen und eine sichere Kontaktantwort."],
        "en": ["Customer business and contact details", "Email address for customer enquiries", "e.g. info@company.com", "Official company name", "e.g. Example Company Ltd", "Slogan or main heading (optional)", "e.g. Your partner for quality and trust", "Phone number (optional)", "e.g. +44 20 1234 5678", "Web3Forms access key (optional)", "This key enables a Web3Forms contact form on the generated website.", "Configure customer chatbot", "General customer service", "The chatbot automatically receives basic knowledge about the industry: {industry}. It is added to the customer website during creation. Set HF_API_KEY once in the Vercel project for AI answers after publishing.", "Enter the company details the chatbot may share with website visitors.", "Opening hours", "e.g. Mon-Fri: 8:00-17:00", "Phone and other contact methods", "e.g. +44 20 1234 5678 or info@company.com", "Prices and key services", "e.g. Free initial consultation, maintenance from EUR 89", "Emergency and on-call service", "e.g. Emergency number +44 7000 123456", "Chat design color", "Chat icon shape", "Chatbot character", "Chatbot name", "Chatbot position", "Keep visible while scrolling", "On: the chatbot remains at the screen edge. Off: it appears at the end of the page.", "Chatbot ready: Company details are automatically included in the preview, ZIP, and published website.", "Recommendation: Add opening hours, services, prices, or emergency information. Without your own details, the chatbot uses industry knowledge and a safe contact response."],
        "ar": ["بيانات الشركة والاتصال الخاصة بالعميل", "البريد الإلكتروني لاستفسارات العملاء", "مثال: info@company.com", "الاسم الرسمي للشركة", "مثال: شركة النور", "الشعار أو العنوان الرئيسي (اختياري)", "مثال: شريكك للجودة والثقة", "رقم الهاتف (اختياري)", "مثال: +49 30 123456", "مفتاح Web3Forms (اختياري)", "يتيح هذا المفتاح إضافة نموذج اتصال Web3Forms إلى الموقع الناتج.", "إعداد روبوت محادثة العملاء", "خدمة عملاء عامة", "يحصل روبوت المحادثة تلقائياً على معلومات أساسية عن المجال: {industry}. ويُضاف إلى موقع العميل عند إنشائه. للحصول على إجابات الذكاء الاصطناعي بعد النشر، يجب ضبط HF_API_KEY مرة واحدة في مشروع Vercel.", "أدخل بيانات الشركة التي يُسمح لروبوت المحادثة بعرضها لزوار الموقع.", "ساعات العمل", "مثال: الاثنين-الجمعة: 08:00-17:00", "الهاتف ووسائل الاتصال الأخرى", "مثال: +49 30 123456 أو info@company.com", "الأسعار والخدمات المهمة", "مثال: الاستشارة الأولى مجانية، الصيانة من 89 يورو", "الطوارئ وخدمة الاستعداد", "مثال: رقم الطوارئ +49 171 123456", "لون تصميم المحادثة", "شكل أيقونة المحادثة", "شخصية روبوت المحادثة", "اسم روبوت المحادثة", "موضع روبوت المحادثة", "إبقاؤه ظاهراً أثناء التمرير", "عند التفعيل يبقى روبوت المحادثة عند حافة الشاشة، وعند التعطيل يظهر في نهاية الصفحة.", "روبوت المحادثة جاهز: ستُضاف بيانات الشركة تلقائياً إلى المعاينة وملف ZIP والموقع المنشور.", "نصيحة: أضف ساعات العمل والخدمات والأسعار أو معلومات الطوارئ. من دون بياناتك يستخدم الروبوت معلومات المجال وإجابة اتصال آمنة."],
        "ku": ["زانیاری بازرگانی و پەیوەندیی کڕیار", "ئیمەیڵ بۆ پرسیارەکانی کڕیار", "بۆ نموونە: info@company.com", "ناوی فەرمی کۆمپانیا", "بۆ نموونە: کۆمپانیای ڕووناکی", "دروشـم یان سەردێڕی سەرەکی (ئارەزوومەندانە)", "بۆ نموونە: هاوبەشی تۆ بۆ کوالێتی و متمانە", "ژمارەی تەلەفۆن (ئارەزوومەندانە)", "بۆ نموونە: +49 30 123456", "کلیلی Web3Forms (ئارەزوومەندانە)", "ئەم کلیلە فۆڕمی پەیوەندی Web3Forms بۆ وێبگەی دروستکراو چالاک دەکات.", "ڕێکخستنی چاتبۆتی کڕیار", "خزمەتگوزاری گشتی کڕیار", "چاتبۆتەکە خۆکارانە زانیاری بنەڕەتی دەربارەی بوارەکە وەردەگرێت: {industry}. لە کاتی دروستکردندا زیاد دەکرێت. بۆ وەڵامی زیرەکی دەستکرد دوای بڵاوکردنەوە، HF_API_KEY جارێک لە پڕۆژەی Vercel دابنێ.", "ئەو زانیارییەی کۆمپانیا بنووسە کە چاتبۆت دەتوانێت بە سەردانکەرانی وێبگە بڵێت.", "کاتەکانی کردنەوە", "بۆ نموونە: دووشەممە-هەینی: 08:00-17:00", "تەلەفۆن و ڕێگاکانی تری پەیوەندی", "بۆ نموونە: +49 30 123456 یان info@company.com", "نرخ و خزمەتگوزارییە گرنگەکان", "بۆ نموونە: ڕاوێژکاری یەکەم بەخۆڕاییە", "فریاکەوتن و ئامادەباشی", "بۆ نموونە: ژمارەی فریاکەوتن +49 171 123456", "ڕەنگی دیزاینی چات", "شێوەی ئایکۆنی چات", "کەسایەتی چاتبۆت", "ناوی چاتبۆت", "شوێنی چاتبۆت", "لە کاتی سکرۆڵکردن دیار بێت", "کاتێک چالاکە چاتبۆت لە کەناری شاشە دەمێنێتەوە؛ کاتێک ناچالاکە لە کۆتایی پەڕە دەردەکەوێت.", "چاتبۆت ئامادەیە: زانیاری کۆمپانیا خۆکارانە دەخرێتە پێشبینین و ZIP و وێبگەی بڵاوکراوە.", "پێشنیار: کاتەکانی کردنەوە، خزمەتگوزاری، نرخ یان زانیاری فریاکەوتن زیاد بکە."],
    }
    labels = copy_by_language.get(language, copy_by_language["en"])
    st.subheader(labels[0])
    contact_column, company_column = st.columns(2)
    with contact_column:
        st.text_input(
            labels[1],
            placeholder=labels[2],
            key="client_business_email",
        )
    with company_column:
        st.text_input(
            labels[3],
            placeholder=labels[4],
            key="client_company_name",
        )
    st.text_input(
        labels[5],
        placeholder=labels[6],
        key="client_company_slogan",
    )
    address_labels = {
        "de": ("Anschrift des Kunden-Unternehmens", "z. B. Musterstraße 1, 10115 Berlin"),
        "en": ("Customer company address", "e.g. 1 Example Street, London"),
        "ar": ("عنوان شركة العميل", "مثال: الشارع والرقم والمدينة"),
        "ku": ("ناونیشانی کۆمپانیای کڕیار", "بۆ نموونە: شەقام، ژمارە و شار"),
    }.get(language, ("Customer company address", "Street, number, postal code and city"))
    st.text_input(
        address_labels[0],
        placeholder=address_labels[1],
        key="client_company_address",
    )
    contact_details_column, form_column = st.columns(2)
    with contact_details_column:
        st.text_input(
            labels[7],
            placeholder=labels[8],
            key="client_business_phone",
        )
    with form_column:
        st.text_input(
            labels[9],
            type="password",
            help=labels[10],
            key="client_web3forms_access_key",
        )
    industry = str(st.session_state.get("industry_content_preset", ""))
    industry_knowledge = industry if industry in INDUSTRY_CONTENT_PRESETS else labels[12]
    st.subheader(labels[11], anchor=False)
    st.info(
        labels[13].format(industry=industry_knowledge)
    )
    st.write(labels[14])
    hours_column, contact_column = st.columns(2)
    with hours_column:
        st.text_input(
            labels[15],
            placeholder=labels[16],
            key="client_chatbot_hours",
        )
        st.text_input(
            labels[17],
            placeholder=labels[18],
            key="client_chatbot_contact",
        )
    with contact_column:
        st.text_area(
            labels[19],
            placeholder=labels[20],
            key="client_chatbot_services",
            height=100,
        )
        st.text_input(
            labels[21],
            placeholder=labels[22],
            key="client_chatbot_emergency",
        )
    option_copy = {
        "ar": {"Rund (Kreis)": "دائري", "Eckig mit Rundung": "بحواف مستديرة", "Quadratisch": "مربع", "Freundlicher Roboter": "روبوت ودود", "Salon-Stylistin": "خبيرة تصفيف", "Werkstatt-Profi": "خبير ورشة", "Praxis-Begleitung": "مساعد العيادة", "Gastronomie-Service": "مساعد المطعم", "Shop-Beratung": "مساعد المتجر", "Haus und Dach": "خبير الأسقف", "Restaurant-Service": "خدمة المطعم", "Kanzlei-Beratung": "مستشار قانوني", "Kreativ-Studio": "استوديو إبداعي", "Reinigungs-Service": "خدمة التنظيف", "Unten rechts": "أسفل اليمين", "Unten links": "أسفل اليسار"},
        "ku": {"Rund (Kreis)": "بازنەیی", "Eckig mit Rundung": "گۆشەی خڕ", "Quadratisch": "چوارگۆشە", "Freundlicher Roboter": "ڕۆبۆتی دۆستانە", "Salon-Stylistin": "پسپۆڕی جوانکاری", "Werkstatt-Profi": "پسپۆڕی وەرشە", "Praxis-Begleitung": "یاریدەدەری کلینیک", "Gastronomie-Service": "یاریدەدەری چێشتخانە", "Shop-Beratung": "ڕاوێژکاری فرۆشگا", "Haus und Dach": "پسپۆڕی سەربان", "Restaurant-Service": "خزمەتگوزاری چێشتخانە", "Kanzlei-Beratung": "ڕاوێژکاری یاسایی", "Kreativ-Studio": "ستۆدیۆی داهێنەرانە", "Reinigungs-Service": "خزمەتگوزاری پاککردنەوە", "Unten rechts": "خوارەوە لای ڕاست", "Unten links": "خوارەوە لای چەپ"},
    }.get(language, {})
    display_option = lambda option: option_copy.get(option, option)
    color_column, shape_column, figure_column, name_column = st.columns(4)
    with color_column:
        st.color_picker(
            labels[23],
            "#2563EB",
            key="customer_chatbot_color",
        )
    with shape_column:
        st.selectbox(
            labels[24],
            ["Rund (Kreis)", "Eckig mit Rundung", "Quadratisch"],
            format_func=display_option,
            key="customer_chatbot_shape",
        )
    with figure_column:
        st.selectbox(
            labels[25],
            list(CHATBOT_FIGURE_ICONS),
            format_func=display_option,
            key="customer_chatbot_figure",
        )
    with name_column:
        st.text_input(
            labels[26],
            key="customer_chatbot_name",
        )
    position_column, behavior_column = st.columns(2)
    with position_column:
        st.segmented_control(
            labels[27],
            ["Unten rechts", "Unten links"],
            default="Unten rechts",
            format_func=display_option,
            key="customer_chatbot_position",
        )
    with behavior_column:
        st.checkbox(
            labels[28],
            value=True,
            key="customer_chatbot_fixed",
            help=labels[29],
        )
    has_business_knowledge = any(
        str(st.session_state.get(key, "")).strip()
        for key in (
            "client_chatbot_hours",
            "client_chatbot_contact",
            "client_chatbot_services",
            "client_chatbot_emergency",
        )
    )
    if has_business_knowledge:
        st.success(labels[30])
    else:
        st.caption(labels[31])


def render_language_selector() -> tuple[dict[str, str], str]:
    """Leitet Website-Sprache und Leserichtung aus der globalen Sprachwahl ab."""
    language = str(st.session_state.app_language)
    if (
        st.session_state.get("industry_preset_applied")
        and st.session_state.get("industry_preset_language") != language
    ):
        apply_app_language()
    target_language = TARGET_LANGUAGE_BY_APP_CODE[st.session_state.app_language]
    st.session_state.target_language = target_language
    translation_error = str(
        st.session_state.get("language_translation_error", "")
    ).strip()
    if translation_error:
        st.error(translation_error)
    return SUPPORTED_LANGUAGES[target_language], target_language


PREVIEW_COPY = {
    "de": {"devices": "Gerät", "desktop": "Desktop", "tablet": "Tablet", "mobile": "Smartphone", "open": "In neuem Tab", "frameTitle": "Live-Vorschau der Website", "hint": "Echte Website mit Chatbot. Links und Unterseiten sind klickbar.", "formBlocked": "Formulare werden in der Vorschau nicht gesendet.", "empty": "Noch kein Entwurf vorhanden."},
    "en": {"devices": "Device", "desktop": "Desktop", "tablet": "Tablet", "mobile": "Smartphone", "open": "Open in new tab", "frameTitle": "Live website preview", "hint": "The real website with chatbot. Links and pages are clickable.", "formBlocked": "Forms are not sent in the preview.", "empty": "No draft yet."},
    "ar": {"devices": "الجهاز", "desktop": "سطح المكتب", "tablet": "جهاز لوحي", "mobile": "هاتف ذكي", "open": "فتح في علامة تبويب جديدة", "frameTitle": "المعاينة المباشرة للموقع", "hint": "الموقع الحقيقي مع روبوت المحادثة. الروابط والصفحات قابلة للنقر.", "formBlocked": "لا يتم إرسال النماذج في المعاينة.", "empty": "لا توجد مسودة بعد."},
    "ku": {"devices": "ئامێر", "desktop": "کۆمپیوتەر", "tablet": "تابلێت", "mobile": "مۆبایل", "open": "لە تابێکی نوێ بیکەرەوە", "frameTitle": "پێشبینینی ڕاستەوخۆی وێبگە", "hint": "وێبگەی ڕاستەقینە لەگەڵ چاتبۆت. بەستەر و پەڕەکان کلیک دەکرێن.", "formBlocked": "فۆڕمەکان لە پێشبینیندا نانێردرێن.", "empty": "هێشتا ڕەشنووس نییە."},
    "es": {"devices": "Dispositivo", "desktop": "Escritorio", "tablet": "Tableta", "mobile": "Móvil", "open": "Abrir en pestaña nueva", "frameTitle": "Vista previa del sitio", "hint": "El sitio real con chatbot. Enlaces y páginas son clicables.", "formBlocked": "Los formularios no se envían en la vista previa.", "empty": "Todavía no hay borrador."},
    "it": {"devices": "Dispositivo", "desktop": "Desktop", "tablet": "Tablet", "mobile": "Smartphone", "open": "Apri in nuova scheda", "frameTitle": "Anteprima del sito", "hint": "Il sito reale con chatbot. Link e pagine sono cliccabili.", "formBlocked": "I moduli non vengono inviati nell'anteprima.", "empty": "Nessuna bozza disponibile."},
    "hi": {"devices": "डिवाइस", "desktop": "डेस्कटॉप", "tablet": "टैबलेट", "mobile": "स्मार्टफ़ोन", "open": "नए टैब में खोलें", "frameTitle": "वेबसाइट का लाइव पूर्वावलोकन", "hint": "चैटबॉट सहित वास्तविक वेबसाइट। लिंक और पृष्ठ क्लिक करने योग्य हैं।", "formBlocked": "पूर्वावलोकन में फ़ॉर्म नहीं भेजे जाते।", "empty": "अभी कोई प्रारूप नहीं है।"},
}

PREVIEW_PAGE_KEYS = {
    "index.html": "start",
    "leistungen.html": "leistungen",
    "angebote.html": "angebote",
    "projekte.html": "projekte",
    "ueber-uns.html": "ueber_uns",
    "kontakt.html": "kontakt",
}


def render_live_site_preview(pages: dict[str, str], key: str, height: int = 720) -> None:
    """Zeigt die echte Website in einem Browser-Rahmen mit Geräte- und Seitenumschaltung."""
    language = str(st.session_state.app_language)
    navigation = get_template_preview_copy(language)["nav"]
    project = safe_project_name(
        str(st.session_state.get("client_company_name", "")).strip()
        or str(st.session_state.get("project_name", ""))
    )
    LIVE_SITE_PREVIEW()(
        key=key,
        data={
            "pages": pages,
            "pageLabels": {name: navigation.get(page_key, name) for name, page_key in PREVIEW_PAGE_KEYS.items()},
            "labels": PREVIEW_COPY.get(language, PREVIEW_COPY["en"]),
            "host": f"{project}.vercel.app",
            "height": height,
        },
    )


@st.dialog("Live-Vorschau des Entwurfs", width="large")
def show_full_draft_preview() -> None:
    """Öffnet die vollständige, testbare Kundenvorschau vor der Veröffentlichung."""
    render_live_site_preview(build_draft_preview_pages(), key="full_draft_preview", height=640)


def render_template_and_design_ui() -> str:
    """Rendert die Branchenvorlagen für einen geführten Website-Entwurf."""
    language = str(st.session_state.app_language)
    template_ui_labels = {
        "de": ["Button-Text in der Vorlage", "z. B. Termin vereinbaren", "Überschrift der Vorlage", "z. B. Ihr Partner für Qualität und Vertrauen", "Beschreibung in der Vorlage", "Beschreiben Sie Angebot, Zielgruppe und Ihre besonderen Stärken.", "Vorlagenabschnitte", "Ein Abschnitt pro Zeile. Optional: Überschrift | Beschreibung.", "Footer-Text", "z. B. Muster GmbH | Impressum | Datenschutz", "Hintergrund-Vorlage"],
        "en": ["Template button text", "e.g. Book an appointment", "Template heading", "e.g. Your partner for quality and trust", "Template description", "Describe your offer, audience, and key strengths.", "Template sections", "One section per line. Optional: Heading | Description.", "Footer text", "e.g. Example Ltd | Imprint | Privacy", "Background preset"],
        "ar": ["نص زر القالب", "مثال: احجز موعداً", "عنوان القالب", "مثال: شريكك للجودة والثقة", "وصف القالب", "صف عرضك وجمهورك المستهدف ونقاط قوتك.", "أقسام القالب", "قسم واحد في كل سطر. اختياري: العنوان | الوصف.", "نص التذييل", "مثال: الشركة | بيانات الموقع | الخصوصية", "نمط الخلفية"],
        "ku": ["دەقی دوگمەی قاڵب", "بۆ نموونە: کاتێک دیاری بکە", "سەردێڕی قاڵب", "بۆ نموونە: هاوبەشی تۆ بۆ کوالێتی و متمانە", "وەسفی قاڵب", "پێشنیار، ئامانج و خاڵە بەهێزەکانت باس بکە.", "بەشەکانی قاڵب", "لە هەر دێڕێکدا بەشێک. ئارەزوومەندانە: سەردێڕ | وەسف.", "دەقی پێپەڕە", "بۆ نموونە: کۆمپانیا | زانیاری یاسایی | نهێنی", "قاڵبی پاشبنەما"],
    }
    labels = template_ui_labels.get(language, template_ui_labels["en"])
    localized_templates = {
        "en": {
            "Automobil und KFZ-Gewerbe": ("Automotive and vehicle services", "Dynamic design for dealerships, workshops, and suppliers."),
            "GmbH und Corporate Unternehmen": ("Corporate business", "Professional and trustworthy B2B design for companies."),
            "Cafe und Baeckerei": ("Cafe and bakery", "Warm, handcrafted design for cafes and bakeries."),
            "Restaurant und Gastronomie": ("Restaurant and hospitality", "Elegant, image-led design focused on reservations."),
            "Formale Agentur oder Kanzlei": ("Agency or professional office", "Refined design for agencies, consultancies, and professional offices."),
            "Schule und Bildung": ("School and education", "Clear and welcoming design for educational organizations."),
            "Bibliothek": ("Library", "Organized information design for media, events, and opening hours."),
            "Supermarkt und Einzelhandel": ("Retail and supermarket", "Practical sales-focused design for products and local services."),
        },
        "ar": {
            "Automobil und KFZ-Gewerbe": ("السيارات وخدمات المركبات", "تصميم ديناميكي لمعارض السيارات والورش والموردين."),
            "GmbH und Corporate Unternehmen": ("الشركات والمؤسسات", "تصميم مهني موثوق للشركات وخدمات الأعمال."),
            "Cafe und Baeckerei": ("مقهى ومخبز", "تصميم دافئ وحرفي للمقاهي والمخابز."),
            "Restaurant und Gastronomie": ("المطاعم والضيافة", "تصميم أنيق يركز على الصور والحجوزات."),
            "Formale Agentur oder Kanzlei": ("وكالة أو مكتب مهني", "تصميم راقٍ للوكالات والاستشارات والمكاتب المهنية."),
            "Schule und Bildung": ("المدارس والتعليم", "تصميم واضح ومرحب للمؤسسات التعليمية."),
            "Bibliothek": ("مكتبة", "تصميم منظم للكتب والفعاليات وساعات العمل."),
            "Supermarkt und Einzelhandel": ("التجزئة والسوبرماركت", "تصميم عملي يركز على المنتجات والخدمات المحلية."),
        },
        "ku": {
            "Automobil und KFZ-Gewerbe": ("ئۆتۆمبێل و خزمەتگوزاری ئۆتۆمبێل", "دیزاینێکی جووڵاو بۆ پێشانگا و وەرشە و دابینکەرانی ئۆتۆمبێل."),
            "GmbH und Corporate Unternehmen": ("کۆمپانیا و دامەزراوە", "دیزاینێکی پیشەیی و متمانەپێکراو بۆ کۆمپانیاکان."),
            "Cafe und Baeckerei": ("کافێ و نانەواخانە", "دیزاینێکی گەرم و دەستکرد بۆ کافێ و نانەواخانە."),
            "Restaurant und Gastronomie": ("چێشتخانە و میوانداری", "دیزاینێکی جوان بە گرنگیدان بە وێنە و حجزکردن."),
            "Formale Agentur oder Kanzlei": ("ئاژانس یان نووسینگەی پیشەیی", "دیزاینێکی ڕێک بۆ ئاژانس و ڕاوێژکاری و نووسینگە پیشەییەکان."),
            "Schule und Bildung": ("قوتابخانە و پەروەردە", "دیزاینێکی ڕوون و بەخێرهێنەر بۆ دامەزراوە پەروەردەییەکان."),
            "Bibliothek": ("کتێبخانە", "دیزاینێکی ڕێکخراو بۆ کتێب و چالاکی و کاتەکانی کردنەوە."),
            "Supermarkt und Einzelhandel": ("فرۆشتنی تاک و سوپەرمارکێت", "دیزاینێکی کرداری بۆ بەرهەم و خزمەتگوزاری ناوخۆییەکان."),
        },
    }.get(language, {})
    section_defaults = {
        "de": "Unsere Leistungen | Passende Lösungen für Ihr Anliegen.\nPersönliche Beratung | Wir nehmen uns Zeit für Ihre Fragen.\nKontakt | Sprechen Sie direkt mit unserem Team.",
        "en": "Our services | Solutions tailored to your needs.\nPersonal consultation | We take time to answer your questions.\nContact | Speak directly with our team.",
        "ar": "خدماتنا | حلول مناسبة لاحتياجاتك.\nاستشارة شخصية | نخصص الوقت للإجابة عن أسئلتك.\nاتصل بنا | تحدث مباشرة مع فريقنا.",
        "ku": "خزمەتگوزارییەکانمان | چارەسەری گونجاو بۆ پێداویستییەکانت.\nڕاوێژکاری تایبەت | کات بۆ پرسیارەکانت تەرخان دەکەین.\nپەیوەندی | ڕاستەوخۆ لەگەڵ تیمەکەمان قسە بکە.",
    }
    background_labels = {
        "en": {"Weiß": "White", "Schwarz": "Black", "Dunkel": "Dark", "Hellgrau": "Light gray"},
        "ar": {"Weiß": "أبيض", "Schwarz": "أسود", "Dunkel": "داكن", "Hellgrau": "رمادي فاتح"},
        "ku": {"Weiß": "سپی", "Schwarz": "ڕەش", "Dunkel": "تاریک", "Hellgrau": "خۆڵەمێشی کاڵ"},
    }.get(language, {})
    st.subheader(f"3. {t('template')}")
    selected_language, language_name = render_language_selector()
    st.caption(f"{t('target_language')}: {language_name}")

    template_column, design_column = st.columns(2)
    with template_column:
        display_template = lambda name: localized_templates.get(name, (name, ""))[0]
        selected_template_name = st.selectbox(
            t("choose_industry"),
            list(TEMPLATES),
            format_func=lambda name: f"{TEMPLATES[name]['icon']} {display_template(name)}",
            key="template_name",
        )
        current_template = TEMPLATES[selected_template_name]
        template_display_name, template_description = localized_templates.get(
            selected_template_name,
            (selected_template_name, current_template["description"]),
        )
        st.info(template_description)

    with design_column:
        background_presets = st.segmented_control(
            labels[10],
            list(BACKGROUND_PRESET_COLORS),
            default="Weiß",
            format_func=lambda option: background_labels.get(option, option),
            key="template_background_preset",
            on_change=apply_background_preset,
        )
        preset_background_color = BACKGROUND_PRESET_COLORS[background_presets]
        st.color_picker(
            f"{t('background_color')} ({background_labels.get(background_presets, background_presets)})",
            preset_background_color,
            key=f"template_preset_background_{background_presets}",
            disabled=True,
            help=t("background_color"),
        )
        background_color = preset_background_color
        accent_color = st.color_picker(
            t("accent_color"),
            "#38BDF8",
            key="template_accent_color",
        )
        border_style = st.segmented_control(
            t("corner_style"),
            ["rounded", "sharp"],
            default="rounded",
            format_func=lambda option: t(option),
            key="template_border_style",
        )

    st.text_input(
        labels[0],
        placeholder=labels[1],
        key="template_button_text",
        help=t("live_preview"),
    )
    content_columns = st.columns(2)
    with content_columns[0]:
        st.text_input(
            labels[2],
            placeholder=labels[3],
            key="template_hero_heading",
        )
    with content_columns[1]:
        st.text_area(
            labels[4],
            placeholder=labels[5],
            key="template_custom_description",
            height=100,
        )

    st.text_area(
        labels[6],
        value=str(st.session_state.get("template_sections_text", section_defaults.get(language, current_template["sections"]))),
        help=labels[7],
        key="template_sections_text",
        height=150,
    )
    st.text_input(
        labels[8],
        value=str(st.session_state.get("template_footer_text", "")),
        placeholder=labels[9],
        key="template_footer_text",
    )

    st.markdown(f"**{t('live_preview')}**")
    render_live_site_preview(build_template_preview_pages(), key="template_live_preview")

    radius_class = "rounded-none" if border_style == "sharp" else "rounded-2xl"
    description = str(st.session_state.get("template_custom_description", "")).strip()
    dir_attribute = (
        f'dir="{selected_language["dir"]}" '
        f'lang="{selected_language["code"]}"'
    )
    return f"""
Erstelle eine professionelle Website fuer die Branche: {selected_template_name}.
Kundenbeschreibung: {description or 'Ein professioneller Auftritt fuer diese Branche.'}

DESIGN-VORGABEN:
- Generiere die gesamte Website vollstaendig in der Sprache: {language_name}.
- Das Haupt-HTML-Tag MUSS exakt so strukturiert sein: <html {dir_attribute}>.
- Richte bei dir="rtl" Navigation, Texte, Formulare und Flex-Layouts gespiegelt aus.
- Verwende bei dir="rtl" fuer Text die Tailwind-Klasse text-right.
- Hintergrundfarbe: {background_color}
- Akzentfarbe fuer Buttons und Highlights: {accent_color}
- Stil-Richtung: {current_template['style_hint']}
- EMPFOHLENE BRANCHENABSCHNITTE: {current_template['sections']}.
- Die vom Kunden ausgewählten Abschnitte im Nutzerauftrag sind verbindlich. Entwickle
    sie als vollständig ausgearbeitete Bereiche mit passenden Überschriften, konkreten
    Inhalten und sichtbaren Handlungsaufrufen.
- Verwende fuer Boxen, Bilder und Buttons die Tailwind-Klasse {radius_class}.
- Erstelle eine hochwertige, eigenstaendige Markenwebsite. Vermeide Standard-Layouts,
    Lorem Ipsum, erfundene Bewertungen, Stockbild-Links, Platzhalter und sichtbare
    technische Hinweise.
- Beginne mit einer klaren, responsiven Kopfzeile mit Logo-Text, Navigation und einem
    primären Handlungsaufruf. Ergänze einen aussagekräftigen Hero-Bereich mit konkreter
    Nutzenbotschaft, zwei Handlungsaufrufen und einer passenden visuellen Komposition.
- Baue danach mindestens drei klar unterscheidbare Inhaltsbereiche aus: Kernleistungen,
    einen vertrauensbildenden Bereich mit Arbeitsweise oder Kennzahlen sowie einen
    branchenspezifischen Bereich mit konkretem Nutzen für Besucher.
- Nutze eine eindeutige visuelle Hierarchie mit großzügigen Abständen, kontrastreicher
    Typografie, zugänglichen Fokuszuständen und gut lesbaren Textgrößen. Die Website muss
    auf Mobilgeräten, Tablets und großen Bildschirmen ohne Überlappungen funktionieren.
- Verwende nur hochwertige CSS-Details: dezente Übergänge, konsistente Schatten und
    gezielte Akzentflächen. Verzichte auf überladene Animationen, Farbverläufe als Ersatz
    für Inhalte und unruhige Dekoration.
- Ergänze eine finale Kontaktsektion mit der Kunden-E-Mail-Adresse, Öffnungszeiten oder
    sinnvoller Erreichbarkeit sowie einen vollständigen Footer mit Impressum und Datenschutz.
- Erzeuge vollständiges, semantisches und valides HTML. Alle Navigationseinträge und
    Handlungsaufrufe müssen auf vorhandene Seitenbereiche oder sinnvolle Ziel-Links zeigen.
- ABNAHMEKRITERIEN: Liefere mindestens diese Abschnitte mit passenden IDs: `#hero`,
    `#services`, `#about`, `#highlights`, `#contact` und `#footer`. Erstelle mindestens
    drei konkrete Leistungen und drei branchenspezifische Vorteile. Jeder Abschnitt braucht
    eine eigene Überschrift, aussagekräftige Texte und eine professionelle Gestaltung.
- Prüfe vor der Antwort, dass die Kunden-E-Mail-Adresse im Kontaktbereich und Footer als
    sichtbarer `mailto:`-Link vorkommt. Antworte erst danach mit dem vollständigen
    HTML-Dokument.
"""


def render_section_configuration() -> str:
    """Erfasst den gewünschten Umfang und die Kerninhalte eines Entwurfs."""
    form_copy = get_creation_form_copy()
    labels = form_copy["labels"]
    section_labels = form_copy["sections"]
    st.subheader(labels[0])
    selected_sections = st.multiselect(
        labels[1],
        [
            "Hero und Willkommensbereich",
            "Über uns",
            "Leistungen oder Produkte",
            "Galerie oder Projekte",
            "Kundenstimmen oder Referenzen",
            "Kontakt und Erreichbarkeit",
        ],
        default=[
            "Hero und Willkommensbereich",
            "Über uns",
            "Leistungen oder Produkte",
            "Kontakt und Erreichbarkeit",
        ],
        key="selected_website_sections",
        format_func=lambda section: section_labels.get(section, section),
    )
    if not selected_sections:
        st.warning(labels[2])

    details: list[str] = []
    if "Hero und Willkommensbereich" in selected_sections:
        with st.expander(section_labels["Hero und Willkommensbereich"], expanded=True):
            title = st.text_input(labels[3], key="section_hero_title")
            subtitle = st.text_area(labels[4], key="section_hero_subtitle")
            details.append(f"Hero: Titel '{title}', Untertitel '{subtitle}'.")
    if "Über uns" in selected_sections:
        with st.expander(section_labels["Über uns"]):
            about = st.text_area(labels[5], key="section_about_text")
            details.append(f"Über uns: {about}")
    if "Leistungen oder Produkte" in selected_sections:
        with st.expander(section_labels["Leistungen oder Produkte"]):
            services = st.text_area(
                labels[6],
                key="section_services",
            )
            details.append(f"Leistungen oder Produkte: {services}")
    if "Galerie oder Projekte" in selected_sections:
        with st.expander(section_labels["Galerie oder Projekte"]):
            projects = st.text_area(labels[7], key="section_projects")
            details.append(f"Galerie oder Projekte: {projects}")
    if "Kundenstimmen oder Referenzen" in selected_sections:
        with st.expander(section_labels["Kundenstimmen oder Referenzen"]):
            references = st.text_area(labels[8], key="section_references")
            details.append(f"Kundenstimmen oder Referenzen: {references}")

    return (
        "AUSGEWÄHLTE PFLICHTABSCHNITTE:\n- "
        + "\n- ".join(selected_sections)
        + "\n\nKUNDENINHALTE FÜR DIE ABSCHNITTE:\n"
        + "\n".join(details)
    )


def render_editor() -> None:
    """Rendert den kombinierten Design- und Abschnittseditor."""
    language = str(st.session_state.app_language)
    copy_by_language = {
        "de": ["Live-Design und Abschnittseditor", "Hintergrundfarbe", "Akzentfarbe für Buttons", "Bereich bearbeiten", "Änderungswunsch für '{section}'", "Zum Beispiel: Ändern Sie die Hintergrundfarbe dieses Bereichs oder fügen Sie ein Bild hinzu.", "Abschnitt aktualisieren", "Bitte beschreiben Sie die gewünschte Änderung.", "Abschnitt wird aktualisiert ...", "Abschnitt wurde aktualisiert.", "Aktualisierung fehlgeschlagen"],
        "en": ["Live design and section editor", "Background color", "Button accent color", "Edit section", "Requested change for '{section}'", "For example: Change this section's background color or add an image.", "Update section", "Please describe the requested change.", "Updating section ...", "Section updated.", "Update failed"],
        "ar": ["التصميم المباشر ومحرر الأقسام", "لون الخلفية", "لون تمييز الأزرار", "تعديل القسم", "التغيير المطلوب لقسم «{section}»", "مثال: غيّر لون خلفية هذا القسم أو أضف صورة.", "تحديث القسم", "يرجى وصف التغيير المطلوب.", "جارٍ تحديث القسم...", "تم تحديث القسم.", "فشل التحديث"],
        "ku": ["دیزاینی ڕاستەوخۆ و دەستکاریکەری بەشەکان", "ڕەنگی پاشبنەما", "ڕەنگی دوگمەکان", "دەستکاریکردنی بەش", "گۆڕانکاریی داواکراو بۆ «{section}»", "بۆ نموونە: ڕەنگی پاشبنەمای ئەم بەشە بگۆڕە یان وێنەیەک زیاد بکە.", "نوێکردنەوەی بەش", "تکایە گۆڕانکاریی داواکراو ڕوون بکەرەوە.", "بەشەکە نوێ دەکرێتەوە...", "بەشەکە نوێ کرایەوە.", "نوێکردنەوە سەرکەوتوو نەبوو"],
        "es": ["Diseño en vivo y editor de secciones", "Color de fondo", "Color de acento de los botones", "Editar sección", "Cambio solicitado para «{section}»", "Por ejemplo: Cambia el color de fondo de esta sección o añade una imagen.", "Actualizar sección", "Describe el cambio solicitado.", "Actualizando la sección...", "Sección actualizada.", "Error al actualizar"],
        "it": ["Design dal vivo ed editor delle sezioni", "Colore di sfondo", "Colore principale dei pulsanti", "Modifica sezione", "Modifica richiesta per «{section}»", "Ad esempio: cambia il colore di sfondo di questa sezione o aggiungi un'immagine.", "Aggiorna sezione", "Descrivi la modifica richiesta.", "Aggiornamento della sezione...", "Sezione aggiornata.", "Aggiornamento non riuscito"],
        "hi": ["लाइव डिज़ाइन और अनुभाग संपादक", "पृष्ठभूमि रंग", "बटन एक्सेंट रंग", "अनुभाग संपादित करें", "‘{section}’ के लिए अनुरोधित बदलाव", "उदाहरण: इस अनुभाग का पृष्ठभूमि रंग बदलें या चित्र जोड़ें।", "अनुभाग अपडेट करें", "कृपया अनुरोधित बदलाव का वर्णन करें।", "अनुभाग अपडेट हो रहा है...", "अनुभाग अपडेट हो गया।", "अपडेट विफल रहा"],
    }
    section_copy = {
        "de": ["Hero", "Über mich", "Fähigkeiten und Services", "Projekte", "Kontakt und Footer"],
        "en": ["Hero", "About", "Skills and services", "Projects", "Contact and footer"],
        "ar": ["الواجهة الرئيسية", "من نحن", "المهارات والخدمات", "المشاريع", "الاتصال والتذييل"],
        "ku": ["بەشی سەرەکی", "دەربارە", "توانا و خزمەتگوزارییەکان", "پڕۆژەکان", "پەیوەندی و پێپەڕە"],
        "es": ["Portada", "Sobre nosotros", "Habilidades y servicios", "Proyectos", "Contacto y pie de página"],
        "it": ["Sezione principale", "Chi siamo", "Competenze e servizi", "Progetti", "Contatti e piè di pagina"],
        "hi": ["मुख्य अनुभाग", "हमारे बारे में", "कौशल और सेवाएं", "परियोजनाएं", "संपर्क और पादलेख"],
    }
    labels = copy_by_language.get(language, copy_by_language["en"])
    section_labels = dict(zip(section_copy["de"], section_copy.get(language, section_copy["en"])))
    st.subheader(labels[0])

    color_columns = st.columns(2)
    with color_columns[0]:
        background_color = st.color_picker(
            labels[1],
            "#111827",
            key="editor_background_color",
        )
    with color_columns[1]:
        accent_color = st.color_picker(
            labels[2],
            "#38BDF8",
            key="editor_accent_color",
        )

    section = st.selectbox(
        labels[3],
        [
            "Hero",
            "Über mich",
            "Fähigkeiten und Services",
            "Projekte",
            "Kontakt und Footer",
        ],
        format_func=lambda option: section_labels.get(option, option),
        key="editor_section",
    )
    instructions = st.text_area(
        labels[4].format(section=section_labels.get(section, section)),
        placeholder=labels[5],
        key="editor_instructions",
        height=130,
    )

    if st.button(
        labels[6],
        icon=":material/refresh:",
        type="primary",
        key="update_live_editor_section",
        width="stretch",
    ):
        if not instructions or not instructions.strip():
            st.warning(labels[7])
            return

        with st.status(labels[8], expanded=True) as status:
            try:
                modify_current_website(
                    f"Aendere ausschliesslich den Bereich '{section}' basierend auf: "
                    f"{instructions.strip()}. Beachte das globale Farbschema: "
                    f"Hintergrund {background_color}, Akzent {accent_color}."
                )
                status.update(label=labels[9], state="complete")
                show_after_rerun(labels[9])
                st.rerun()
            except Exception as error:
                status.update(label=labels[10], state="error")
                st.error(str(error))


def render_direct_content_editor() -> None:
    """Rendert direkte, kontrollierte Bearbeitungen für typische Website-Bausteine."""
    st.subheader("Direkt bearbeiten")
    st.caption(
        "Laden Sie ein Bild per Klick oder Drag-and-drop hoch, bearbeiten Sie Texte und "
        "konfigurieren Sie den primären Button. Änderungen werden sofort in die Vorschau übernommen."
    )

    with st.expander("Visueller Editor: Header, Inhalte und Bild", expanded=False):
        header_column, footer_column = st.columns(2)
        with header_column:
            visual_company_name = st.text_input(
                "Firmenname im Header",
                value=str(st.session_state.get("client_company_name", "")),
                key="visual_editor_company_name",
            )
        with footer_column:
            visual_footer_text = st.text_input(
                "Footer-Text",
                value=str(st.session_state.get("template_footer_text", "")),
                key="visual_editor_footer_text",
            )
        visual_heading = st.text_input(
            "Hauptüberschrift",
            value=str(st.session_state.get("template_hero_heading", "")),
            key="visual_editor_heading",
        )
        visual_description = st.text_area(
            "Hauptinhalt",
            value=str(st.session_state.get("template_custom_description", "")),
            key="visual_editor_description",
            height=120,
        )
        visual_image = st.file_uploader(
            "Hauptbild ersetzen",
            type=["png", "jpg", "jpeg", "webp"],
            key="visual_editor_image",
        )
        if st.button(
            "Änderungen in Vorschau übernehmen",
            icon=":material/save:",
            type="primary",
            key="apply_visual_editor_changes",
            width="stretch",
        ):
            change_request = (
                "Aktualisiere ausschließlich diese sichtbaren Website-Inhalte. "
                f"Firmenname im Header und Footer: {visual_company_name.strip()}. "
                f"Hauptüberschrift: {visual_heading.strip()}. "
                f"Hauptinhalt: {visual_description.strip()}. "
                f"Footer-Text: {visual_footer_text.strip()}."
            )
            if visual_image is not None:
                image_name = save_uploaded_image(visual_image, "visueller-editor")
                change_request += f' Verwende als Hauptbild: <img src="{image_name}" alt="Hauptbild">.'
            with st.status("Änderungen werden übernommen ...", expanded=True) as status:
                try:
                    modify_current_website(change_request)
                    status.update(label="Vorschau wurde aktualisiert.", state="complete")
                    show_after_rerun("Vorschau wurde aktualisiert.")
                    st.rerun()
                except Exception as error:
                    status.update(label="Aktualisierung fehlgeschlagen", state="error")
                    st.error(str(error))

    layout_side = st.radio(
        "Bild und Text anordnen",
        ["Bild links, Text rechts", "Text links, Bild rechts"],
        horizontal=True,
        key="direct_editor_layout_side",
    )
    first_column, second_column = st.columns(2)
    image_column, text_column = (
        (first_column, second_column)
        if layout_side.startswith("Bild")
        else (second_column, first_column)
    )

    with image_column:
        st.markdown("**Bildplatzhalter ersetzen**")
        replacement_image = st.file_uploader(
            "Bild klicken oder hier ablegen",
            type=["png", "jpg", "jpeg", "webp"],
            key="direct_placeholder_image",
            help="Das hochgeladene Bild ersetzt sofort das erste Bild im aktuellen Entwurf.",
        )
        if st.button(
            "Bild live ersetzen",
            icon=":material/image:",
            disabled=replacement_image is None,
            key="replace_direct_placeholder_image",
            width="stretch",
        ):
            image_name = save_uploaded_image(replacement_image, "direkter-bildplatzhalter")
            st.session_state.generated_html = replace_first_image_source(
                st.session_state.generated_html, image_name, "Website-Bild"
            )
            st.session_state.html_editor = st.session_state.generated_html
            show_after_rerun("Das Bild wurde in der Vorschau ersetzt.")
            st.rerun()

    with text_column:
        st.markdown("**Textstelle bearbeiten**")
        previous_text = st.text_input(
            "Bisheriger Text in der Website",
            placeholder="z. B. Ihr Angebot entdecken",
            key="direct_previous_text",
        )
        edited_text = st.text_area(
            "Neuer Text (leer lassen zum Löschen)",
            placeholder="Schreiben Sie hier den neuen Text oder lassen Sie das Feld leer.",
            key="direct_edited_text",
            height=100,
        )
        optimize_column, apply_column = st.columns(2)
        with optimize_column:
            if st.button(
                "Text durch KI optimieren",
                icon=":material/auto_awesome:",
                disabled=not edited_text.strip(),
                key="optimize_direct_text",
                width="stretch",
            ):
                with st.status("Text wird professionell optimiert ...", expanded=True) as status:
                    try:
                        st.session_state.direct_optimized_text = optimize_editor_text(edited_text)
                        status.update(label="Optimierter Text ist bereit.", state="complete")
                    except ValueError as error:
                        status.update(label="Optimierung fehlgeschlagen", state="error")
                        st.error(str(error))
        with apply_column:
            if st.button(
                "Text übernehmen",
                icon=":material/save:",
                disabled=not previous_text.strip(),
                key="apply_direct_text",
                width="stretch",
            ):
                try:
                    st.session_state.generated_html = replace_visible_text(
                        st.session_state.generated_html, previous_text, edited_text
                    )
                    st.session_state.html_editor = st.session_state.generated_html
                    show_after_rerun("Die Textstelle wurde aktualisiert.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        optimized_text = str(st.session_state.get("direct_optimized_text", "")).strip()
        if optimized_text:
            st.code(optimized_text, language=None)

    st.divider()
    with st.popover("Button konfigurieren", icon=":material/smart_button:", width="stretch"):
        button_target = st.radio(
            "Beim Klick auf den primären Button",
            ["Externe Website öffnen", "Angebots-Unterseite öffnen"],
            key="direct_button_target_type",
        )
        external_url = ""
        if button_target == "Externe Website öffnen":
            external_url = st.text_input(
                "Externer Link", placeholder="https://www.beispiel.de", key="direct_button_url"
            )
        if st.button("Button-Ziel übernehmen", type="primary", key="apply_direct_button_target", width="stretch"):
            target_url = external_url.strip() if external_url.strip() else "#angebote"
            if button_target == "Externe Website öffnen" and not re.fullmatch(r"https?://[^\s]+", target_url):
                st.error("Bitte geben Sie eine gültige externe Adresse mit https:// ein.")
            else:
                updated_html, replaced = set_primary_button_target(
                    st.session_state.generated_html, target_url
                )
                if not replaced:
                    st.error("Im Entwurf wurde kein konfigurierbarer Button-Link gefunden.")
                else:
                    st.session_state.generated_html = updated_html
                    st.session_state.html_editor = updated_html
                    show_after_rerun("Das Button-Ziel wurde aktualisiert.")
                    st.rerun()

    st.subheader("Angebots-Unterseite", anchor=False)
    st.caption("Ergänzt eine professionelle Angebotssektion mit Karten, Preis und Anfrage-Button.")
    offer_columns = st.columns(3)
    with offer_columns[0]:
        offer_name = st.text_input("Angebot oder Service", key="offer_page_name", placeholder="Inspektion und Service")
    with offer_columns[1]:
        offer_price = st.text_input("Preis oder Hinweis", key="offer_page_price", placeholder="ab 99 EUR")
    with offer_columns[2]:
        offer_details = st.text_input("Kurzer Nutzen", key="offer_page_details", placeholder="Transparent, schnell und zuverlässig")
    if st.button(
        "Angebots-Unterseite erstellen",
        icon=":material/add_circle:",
        key="create_offer_page",
        width="stretch",
    ):
        if 'id="angebote"' in st.session_state.generated_html:
            st.warning("Eine Angebots-Unterseite ist bereits vorhanden.")
        else:
            offer_section = build_offer_page_section(offer_name, offer_price, offer_details)
            st.session_state.generated_html = re.sub(
                r"(?i)</body\s*>", f"{offer_section}</body>", st.session_state.generated_html, count=1
            )
            st.session_state.html_editor = st.session_state.generated_html
            show_after_rerun("Die Angebots-Unterseite wurde zur Website ergänzt.")
            st.rerun()


def render_mcp_content_tools_ui() -> None:
    """Rendert MCP-Aktionen für die Struktur und SEO des aktuellen Entwurfs."""
    language = str(st.session_state.app_language)
    copy = {
        "de": ["MCP-Inhaltswerkzeuge", "Erweitern oder optimieren Sie den aktuellen Entwurf. Die Änderung wird erst mit Veröffentlichung live.", "Erstellen oder laden Sie zuerst einen Website-Entwurf.", "Bereich ergänzen", "Kundenbewertungen", "Häufige Fragen", "Kontaktaufruf", "Bereich per MCP einfügen", "{section} wurde in den Entwurf eingefügt.", "SEO für Google optimieren", "SEO-Daten wurden im Entwurf aktualisiert."],
        "en": ["MCP content tools", "Extend or optimize the current draft. Changes only go live when published.", "Create or load a website draft first.", "Add section", "Customer reviews", "Frequently asked questions", "Contact call to action", "Insert section with MCP", "{section} was added to the draft.", "Optimize SEO for Google", "SEO data was updated in the draft."],
        "ar": ["أدوات محتوى MCP", "وسّع المسودة الحالية أو حسّنها. لا تظهر التغييرات للعامة إلا بعد النشر.", "أنشئ مسودة موقع أو حمّلها أولاً.", "إضافة قسم", "آراء العملاء", "الأسئلة الشائعة", "دعوة للتواصل", "إضافة القسم باستخدام MCP", "تمت إضافة قسم «{section}» إلى المسودة.", "تحسين SEO لمحرك Google", "تم تحديث بيانات SEO في المسودة."],
        "ku": ["ئامرازەکانی ناوەڕۆکی MCP", "ڕەشنووسەکە فراوان یان باشتر بکە. گۆڕانکارییەکان تەنها دوای بڵاوکردنەوە دەردەکەون.", "سەرەتا ڕەشنووسی وێبگەیەک دروست بکە یان باری بکە.", "زیادکردنی بەش", "هەڵسەنگاندنی کڕیاران", "پرسیارە باوەکان", "بانگهێشتی پەیوەندی", "زیادکردنی بەش بە MCP", "بەشی «{section}» زیاد کرا بۆ ڕەشنووسەکە.", "باشترکردنی SEO بۆ Google", "زانیاری SEO لە ڕەشنووسەکە نوێ کرایەوە."],
    }.get(language)
    if copy is None:
        copy = ["MCP content tools", "Extend or optimize the current draft. Changes only go live when published.", "Create or load a website draft first.", "Add section", "Customer reviews", "Frequently asked questions", "Contact call to action", "Insert section with MCP", "{section} was added to the draft.", "Optimize SEO for Google", "SEO data was updated in the draft."]
    st.subheader(copy[0], anchor=False)
    st.caption(copy[1])
    if not st.session_state.generated_html:
        st.info(copy[2])
        return

    section_column, seo_column = st.columns(2)
    with section_column:
        section_options = {
            copy[4]: "testimonials",
            copy[5]: "faq",
            copy[6]: "call_to_action",
        }
        selected_section_label = st.selectbox(
            copy[3],
            list(section_options),
            key="mcp_section_type",
        )
        if st.button(
            copy[7],
            icon=":material/add_circle:",
            key="mcp_insert_section",
            width="stretch",
        ):
            try:
                updated_html = update_draft_with_mcp_tool(
                    "inject_section_into_html",
                    {
                        "html": st.session_state.generated_html,
                        "section_type": section_options[selected_section_label],
                        "language": language,
                    },
                )
                queue_html_update(updated_html)
                show_after_rerun(copy[8].format(section=selected_section_label))
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    with seo_column:
        if st.button(
            copy[9],
            icon=":material/travel_explore:",
            key="mcp_optimize_seo",
            width="stretch",
        ):
            try:
                updated_html = update_draft_with_mcp_tool(
                    "optimize_seo_and_content",
                    {
                        "html": st.session_state.generated_html,
                        "industry": str(st.session_state.get("industry_content_preset", "")),
                        "company_name": str(st.session_state.get("client_company_name", "")),
                        "language": language,
                    },
                )
                queue_html_update(updated_html)
                show_after_rerun(copy[10])
                st.rerun()
            except ValueError as error:
                st.error(str(error))


OWNED_DOMAIN_COPY = {
    "de": ["Ihre Domains", "Aktiv", "Wird eingerichtet ...", "Einrichtung fehlgeschlagen", "Gewählten Entwurf auf {domain} veröffentlichen", "Der gewählte Entwurf ist jetzt online unter {domain}.", "Domain öffnen", "Status aktualisieren", "Laden oder erstellen Sie zuerst den Entwurf, der unter dieser Domain erscheinen soll.", "Bitte wenden Sie sich an den Support. Ihre Zahlung bleibt erhalten."],
    "en": ["Your domains", "Active", "Being set up ...", "Setup failed", "Publish selected draft to {domain}", "The selected draft is now live at {domain}.", "Open domain", "Refresh status", "Load or create the draft that should appear on this domain first.", "Please contact support. Your payment is safe."],
    "ar": ["نطاقاتك", "نشط", "جارٍ الإعداد...", "فشل الإعداد", "نشر المسودة المختارة على {domain}", "المسودة المختارة متاحة الآن على {domain}.", "فتح النطاق", "تحديث الحالة", "حمّل أو أنشئ أولاً المسودة التي يجب أن تظهر على هذا النطاق.", "يرجى التواصل مع الدعم. دفعتك محفوظة."],
    "ku": ["دۆمەینەکانت", "چالاک", "ئامادە دەکرێت...", "ئامادەکردن سەرکەوتوو نەبوو", "بڵاوکردنەوەی ڕەشنووسی هەڵبژێردراو لەسەر {domain}", "ڕەشنووسی هەڵبژێردراو ئێستا لەسەر {domain} بەردەستە.", "کردنەوەی دۆمەین", "نوێکردنەوەی دۆخ", "سەرەتا ئەو ڕەشنووسە بار بکە یان دروست بکە کە دەبێت لەسەر ئەم دۆمەینە دەربکەوێت.", "تکایە پەیوەندی بە پشتگیرییەوە بکە. پارەدانەکەت پارێزراوە."],
    "es": ["Sus dominios", "Activo", "Configurándose...", "La configuración falló", "Publicar el borrador seleccionado en {domain}", "El borrador seleccionado ya está en línea en {domain}.", "Abrir dominio", "Actualizar estado", "Cargue o cree primero el borrador que debe aparecer en este dominio.", "Contacte con soporte. Su pago está seguro."],
    "it": ["I tuoi domini", "Attivo", "Configurazione in corso...", "Configurazione non riuscita", "Pubblica la bozza selezionata su {domain}", "La bozza selezionata è ora online su {domain}.", "Apri dominio", "Aggiorna stato", "Carica o crea prima la bozza da mostrare su questo dominio.", "Contatta l'assistenza. Il pagamento è al sicuro."],
    "hi": ["आपके डोमेन", "सक्रिय", "सेटअप हो रहा है...", "सेटअप विफल", "चुना गया प्रारूप {domain} पर प्रकाशित करें", "चुना गया प्रारूप अब {domain} पर लाइव है।", "डोमेन खोलें", "स्थिति अपडेट करें", "पहले वह प्रारूप लोड करें या बनाएं जो इस डोमेन पर दिखना चाहिए।", "कृपया सहायता से संपर्क करें। आपका भुगतान सुरक्षित है।"],
}


EXTERNAL_DOMAIN_HELP = {
    "de": ("So geht's: eigene Domain verbinden", """**1. In der App**
- Gewünschten Entwurf erstellen oder links unter „Ihre Entwürfe“ auf **Laden** klicken. Genau dieser Entwurf wird veröffentlicht.
- Unten Ihre Domain eingeben (z. B. `mein-betrieb.de`) und auf **Domain verbinden & Website veröffentlichen** klicken.

**2. Bei Ihrem Domain-Anbieter** (z. B. IONOS, Strato, GoDaddy)
- Anmelden und die **DNS-Einstellungen** der Domain öffnen („DNS verwalten“, „DNS-Einträge“).
- Die angezeigten Einträge eintragen bzw. vorhandene ersetzen:

| Typ | Name / Host | Wert / Ziel |
|---|---|---|
| A | `@` (bei manchen Anbietern leer lassen) | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- Zeigt die App zusätzlich einen **TXT**-Eintrag an, diesen ebenfalls eintragen. Danach speichern.

**3. Zurück in der App**
- Unter „Ihre Domains“ auf **Verbindung prüfen** klicken. Meist ist die Domain nach wenigen Minuten aktiv, selten nach bis zu 48 Stunden. Das SSL-Zertifikat (https) wird automatisch eingerichtet.
- Später einen anderen Entwurf veröffentlichen: Entwurf laden und unter „Ihre Domains“ auf **Gewählten Entwurf … veröffentlichen** klicken. Die DNS-Einträge bleiben unverändert."""),
    "en": ("How it works: connect your own domain", """**1. In the app**
- Create the draft you want or click **Load** under "Your drafts" on the left. Exactly this draft is published.
- Enter your domain below (e.g. `my-business.com`) and click **Connect domain & publish website**.

**2. At your domain provider** (e.g. GoDaddy, Namecheap, IONOS)
- Sign in and open the domain's **DNS settings** ("Manage DNS", "DNS records").
- Add the records shown or replace existing ones:

| Type | Name / Host | Value / Target |
|---|---|---|
| A | `@` (some providers: leave empty) | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- If the app also shows a **TXT** record, add it as well. Then save.

**3. Back in the app**
- Click **Check connection** under "Your domains". The domain is usually active within minutes, rarely after up to 48 hours. The SSL certificate (https) is set up automatically.
- To publish another draft later: load it and click **Publish selected draft to …** under "Your domains". The DNS records stay the same."""),
    "ar": ("طريقة ربط نطاقك الخاص", """**1. في التطبيق**
- أنشئ المسودة المطلوبة أو اضغط **تحميل** ضمن «مسوداتك» على اليسار. سيتم نشر هذه المسودة تحديداً.
- أدخل نطاقك أدناه (مثل `my-business.com`) واضغط **ربط النطاق ونشر الموقع**.

**2. لدى مزود النطاق**
- سجّل الدخول وافتح **إعدادات DNS** للنطاق.
- أضف السجلات المعروضة أو استبدل الموجودة:

| النوع | الاسم / المضيف | القيمة / الهدف |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- إذا عرض التطبيق سجلاً من نوع **TXT** فأضفه أيضاً، ثم احفظ.

**3. العودة إلى التطبيق**
- اضغط **التحقق من الربط** ضمن «نطاقاتك». يصبح النطاق نشطاً عادة خلال دقائق، ونادراً بعد 48 ساعة. يتم إعداد شهادة SSL تلقائياً."""),
    "ku": ("ڕێنمایی: بەستنەوەی دۆمەینی خۆت", """**1. لە ئەپەکەدا**
- ڕەشنووسی دڵخواز دروست بکە یان لە «ڕەشنووسەکانت» کلیک لە **بارکردن** بکە.
- دۆمەینەکەت بنووسە (بۆ نموونە `my-business.com`) و کلیک لە **بەستنەوەی دۆمەین و بڵاوکردنەوەی وێبگە** بکە.

**2. لای دابینکەری دۆمەین**
- **ڕێکخستنەکانی DNS** بکەرەوە و ئەم تۆمارانە زیاد بکە:

| جۆر | ناو / هۆست | بەها / ئامانج |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- ئەگەر تۆمارێکی **TXT** پیشان درا، ئەویش زیاد بکە.

**3. گەڕانەوە بۆ ئەپ**
- لە «دۆمەینەکانت» کلیک لە **پشکنینی بەستنەوە** بکە. زۆرجار لە چەند خولەکێکدا چالاک دەبێت."""),
    "es": ("Cómo conectar su propio dominio", """**1. En la aplicación**
- Cree el borrador deseado o pulse **Cargar** en «Sus borradores» a la izquierda. Se publica exactamente ese borrador.
- Introduzca su dominio abajo (p. ej. `mi-empresa.com`) y pulse **Conectar dominio y publicar sitio**.

**2. En su proveedor de dominio**
- Abra la **configuración DNS** del dominio y añada o sustituya estos registros:

| Tipo | Nombre / Host | Valor / Destino |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- Si la aplicación muestra además un registro **TXT**, añádalo también.

**3. De vuelta en la aplicación**
- Pulse **Comprobar conexión** en «Sus dominios». Suele estar activo en minutos, raramente hasta 48 horas. El certificado SSL se crea automáticamente."""),
    "it": ("Come collegare il tuo dominio", """**1. Nell'app**
- Crea la bozza desiderata o clicca **Carica** in «Le tue bozze» a sinistra. Viene pubblicata esattamente questa bozza.
- Inserisci il dominio qui sotto (ad es. `mia-azienda.com`) e clicca **Collega dominio e pubblica sito**.

**2. Presso il provider del dominio**
- Apri le **impostazioni DNS** del dominio e aggiungi o sostituisci questi record:

| Tipo | Nome / Host | Valore / Destinazione |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- Se l'app mostra anche un record **TXT**, aggiungilo.

**3. Di nuovo nell'app**
- Clicca **Verifica collegamento** in «I tuoi domini». Di solito è attivo in pochi minuti, raramente fino a 48 ore. Il certificato SSL viene creato automaticamente."""),
    "hi": ("अपना डोमेन कैसे जोड़ें", """**1. ऐप में**
- इच्छित प्रारूप बनाएं या बाईं ओर «आपके प्रारूप» में **लोड** पर क्लिक करें।
- नीचे अपना डोमेन दर्ज करें (जैसे `my-business.com`) और **डोमेन जोड़ें और वेबसाइट प्रकाशित करें** पर क्लिक करें।

**2. अपने डोमेन प्रदाता के पास**
- डोमेन की **DNS सेटिंग** खोलें और ये रिकॉर्ड जोड़ें या बदलें:

| प्रकार | नाम / होस्ट | मान / लक्ष्य |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

- यदि ऐप एक **TXT** रिकॉर्ड भी दिखाए, तो उसे भी जोड़ें।

**3. वापस ऐप में**
- «आपके डोमेन» में **कनेक्शन जांचें** पर क्लिक करें। आमतौर पर कुछ मिनटों में सक्रिय हो जाता है। SSL प्रमाणपत्र अपने आप बनता है।"""),
}


EXTERNAL_DOMAIN_COPY = {
    "de": {"option": "Bereits gekaufte Domain verbinden", "intro": "Sie haben Ihre Domain schon bei einem anderen Anbieter (z. B. IONOS, Strato, GoDaddy) gekauft? Geben Sie sie ein. Wir veröffentlichen Ihren Entwurf und zeigen Ihnen die DNS-Einträge, die Sie bei Ihrem Anbieter eintragen.", "label": "Ihre Domain", "placeholder": "z. B. mein-betrieb.de", "button": "Domain verbinden & Website veröffentlichen", "working": "Website wird veröffentlicht und Domain verbunden ...", "connected": "{domain} ist verbunden. Ihre Website ist online.", "pending": "Website ist veröffentlicht. Tragen Sie jetzt die DNS-Einträge bei Ihrem Domain-Anbieter ein.", "badge": "DNS-Einträge eintragen", "records": "Tragen Sie diese Einträge in der DNS-Verwaltung Ihres Domain-Anbieters ein:", "type": "Typ", "name": "Name / Host", "value": "Wert / Ziel", "check": "Verbindung prüfen", "not_yet": "Noch nicht verbunden. DNS-Änderungen werden meist in wenigen Minuten aktiv, selten erst nach bis zu 48 Stunden.", "need_draft": "Erstellen oder laden Sie zuerst den Entwurf, der unter der Domain erscheinen soll."},
    "en": {"option": "Connect a domain you already own", "intro": "Already bought your domain elsewhere (e.g. GoDaddy, Namecheap, IONOS)? Enter it. We publish your draft and show you the DNS records to add at your provider.", "label": "Your domain", "placeholder": "e.g. my-business.com", "button": "Connect domain & publish website", "working": "Publishing website and connecting domain ...", "connected": "{domain} is connected. Your website is online.", "pending": "Your website is published. Now add the DNS records at your domain provider.", "badge": "Add DNS records", "records": "Add these records in your domain provider's DNS settings:", "type": "Type", "name": "Name / Host", "value": "Value / Target", "check": "Check connection", "not_yet": "Not connected yet. DNS changes usually take a few minutes, rarely up to 48 hours.", "need_draft": "First create or load the draft that should appear on the domain."},
    "ar": {"option": "ربط نطاق مملوك لك بالفعل", "intro": "هل اشتريت نطاقك من مزود آخر؟ أدخله هنا. سننشر مسودتك ونعرض لك سجلات DNS التي تضيفها لدى مزودك.", "label": "نطاقك", "placeholder": "مثال: my-business.com", "button": "ربط النطاق ونشر الموقع", "working": "جارٍ نشر الموقع وربط النطاق...", "connected": "تم ربط {domain}. موقعك متاح الآن.", "pending": "تم نشر موقعك. أضف الآن سجلات DNS لدى مزود النطاق.", "badge": "أضف سجلات DNS", "records": "أضف هذه السجلات في إعدادات DNS لدى مزود النطاق:", "type": "النوع", "name": "الاسم / المضيف", "value": "القيمة / الهدف", "check": "التحقق من الربط", "not_yet": "لم يتم الربط بعد. تصبح تغييرات DNS فعالة عادة خلال دقائق، ونادراً بعد 48 ساعة.", "need_draft": "أنشئ أو حمّل أولاً المسودة التي يجب أن تظهر على النطاق."},
    "ku": {"option": "بەستنەوەی دۆمەینێک کە پێشتر کڕیوتە", "intro": "دۆمەینەکەت لە دابینکەرێکی تر کڕیوە؟ لێرە بینووسە. ڕەشنووسەکەت بڵاو دەکەینەوە و تۆمارەکانی DNS پیشان دەدەین.", "label": "دۆمەینەکەت", "placeholder": "بۆ نموونە: my-business.com", "button": "بەستنەوەی دۆمەین و بڵاوکردنەوەی وێبگە", "working": "وێبگە بڵاو دەکرێتەوە و دۆمەین دەبەسترێتەوە...", "connected": "{domain} بەسترایەوە. وێبگەکەت لەسەر هێڵە.", "pending": "وێبگەکەت بڵاوکرایەوە. ئێستا تۆمارەکانی DNS لای دابینکەری دۆمەین زیاد بکە.", "badge": "تۆمارەکانی DNS زیاد بکە", "records": "ئەم تۆمارانە لە ڕێکخستنەکانی DNS ی دابینکەرەکەت زیاد بکە:", "type": "جۆر", "name": "ناو / هۆست", "value": "بەها / ئامانج", "check": "پشکنینی بەستنەوە", "not_yet": "هێشتا نەبەستراوەتەوە. گۆڕانکارییەکانی DNS زۆرجار لە چەند خولەکێکدا کار دەکەن.", "need_draft": "سەرەتا ئەو ڕەشنووسە دروست بکە یان بار بکە کە دەبێت لەسەر دۆمەینەکە دەربکەوێت."},
    "es": {"option": "Conectar un dominio que ya tiene", "intro": "¿Ya compró su dominio en otro proveedor? Introdúzcalo. Publicamos su borrador y le mostramos los registros DNS que debe añadir.", "label": "Su dominio", "placeholder": "p. ej. mi-empresa.com", "button": "Conectar dominio y publicar sitio", "working": "Publicando el sitio y conectando el dominio...", "connected": "{domain} está conectado. Su sitio está en línea.", "pending": "Su sitio está publicado. Añada ahora los registros DNS en su proveedor.", "badge": "Añadir registros DNS", "records": "Añada estos registros en la configuración DNS de su proveedor:", "type": "Tipo", "name": "Nombre / Host", "value": "Valor / Destino", "check": "Comprobar conexión", "not_yet": "Aún no conectado. Los cambios DNS suelen tardar minutos, raramente hasta 48 horas.", "need_draft": "Cree o cargue primero el borrador que debe aparecer en el dominio."},
    "it": {"option": "Collega un dominio che possiedi già", "intro": "Hai già acquistato il dominio presso un altro provider? Inseriscilo. Pubblichiamo la bozza e ti mostriamo i record DNS da aggiungere.", "label": "Il tuo dominio", "placeholder": "ad es. mia-azienda.com", "button": "Collega dominio e pubblica sito", "working": "Pubblicazione del sito e collegamento del dominio...", "connected": "{domain} è collegato. Il sito è online.", "pending": "Il sito è pubblicato. Ora aggiungi i record DNS presso il tuo provider.", "badge": "Aggiungi record DNS", "records": "Aggiungi questi record nelle impostazioni DNS del provider:", "type": "Tipo", "name": "Nome / Host", "value": "Valore / Destinazione", "check": "Verifica collegamento", "not_yet": "Non ancora collegato. Le modifiche DNS richiedono di solito pochi minuti, raramente fino a 48 ore.", "need_draft": "Crea o carica prima la bozza da mostrare sul dominio."},
    "hi": {"option": "पहले से खरीदा डोमेन जोड़ें", "intro": "क्या आपने डोमेन किसी अन्य प्रदाता से खरीदा है? उसे दर्ज करें। हम आपका प्रारूप प्रकाशित करेंगे और DNS रिकॉर्ड दिखाएंगे।", "label": "आपका डोमेन", "placeholder": "उदा. my-business.com", "button": "डोमेन जोड़ें और वेबसाइट प्रकाशित करें", "working": "वेबसाइट प्रकाशित हो रही है और डोमेन जुड़ रहा है...", "connected": "{domain} जुड़ गया है। आपकी वेबसाइट ऑनलाइन है।", "pending": "वेबसाइट प्रकाशित हो गई है। अब अपने प्रदाता के पास DNS रिकॉर्ड जोड़ें।", "badge": "DNS रिकॉर्ड जोड़ें", "records": "अपने डोमेन प्रदाता की DNS सेटिंग में ये रिकॉर्ड जोड़ें:", "type": "प्रकार", "name": "नाम / होस्ट", "value": "मान / लक्ष्य", "check": "कनेक्शन जांचें", "not_yet": "अभी जुड़ा नहीं है। DNS बदलाव आमतौर पर कुछ मिनटों में, कभी-कभी 48 घंटे तक में सक्रिय होते हैं।", "need_draft": "पहले वह प्रारूप बनाएं या लोड करें जो डोमेन पर दिखना चाहिए।"},
}


def render_dns_records(records_json: str, copy: dict[str, str]) -> None:
    """Zeigt die DNS-Einträge, die der Kunde bei seinem Domain-Anbieter eintragen muss."""
    try:
        records = json.loads(records_json or "[]")
    except ValueError:
        records = []
    if not records:
        return
    st.caption(copy["records"])
    for record in records:
        type_column, name_column, value_column = st.columns((1, 2, 4))
        type_column.markdown(f"**{copy['type']}**  \n`{record.get('type', '')}`")
        name_column.markdown(f"**{copy['name']}**")
        name_column.code(str(record.get("name", "")), language=None)
        value_column.markdown(f"**{copy['value']}**")
        value_column.code(str(record.get("value", "")), language=None)


def render_owned_domains(language: str) -> None:
    """Zeigt gekaufte Domains und veröffentlicht den gewählten Entwurf per Klick darauf."""
    copy = OWNED_DOMAIN_COPY.get(language, OWNED_DOMAIN_COPY["en"])
    user_id = int(st.session_state.user_id)
    refresh = st.session_state.pop("refresh_domain_orders", False)
    if refresh or not st.session_state.get("domain_orders_synced"):
        sync_domain_orders(user_id)
        st.session_state.domain_orders_synced = True
    owned_domains = get_owned_domains(user_id)
    if not owned_domains:
        return
    st.subheader(copy[0], anchor=False)
    for order in owned_domains:
        domain = order["domain"]
        with st.container(border=True):
            name_column, status_column = st.columns((3, 2), vertical_alignment="center")
            name_column.markdown(f"**{domain}**")
            if order["status"] == "complete":
                status_column.markdown(f":green-badge[:material/check_circle: {copy[1]}]")
            elif order["status"] == "paid":
                status_column.markdown(f":orange-badge[:material/progress_activity: {copy[2]}]")
            elif order["status"] == "dns":
                external_copy = EXTERNAL_DOMAIN_COPY.get(language, EXTERNAL_DOMAIN_COPY["en"])
                status_column.markdown(f":orange-badge[:material/dns: {external_copy['badge']}]")
                render_dns_records(order["detail"], external_copy)
                if st.button(external_copy["check"], icon=":material/sync:", key=f"check_dns_{domain}"):
                    try:
                        if check_external_domain(user_id, domain):
                            show_after_rerun(external_copy["connected"].format(domain=domain))
                            st.rerun()
                        st.info(external_copy["not_yet"])
                    except ValueError as error:
                        st.error(str(error))
                continue
            else:
                status_column.markdown(f":red-badge[:material/error: {copy[3]}]")
                st.caption(f"{copy[9]} {order['detail']}".strip())
                continue
            if order["status"] != "complete":
                continue
            if not st.session_state.generated_html:
                st.caption(copy[8])
            publish_column, open_column = st.columns(2)
            if publish_column.button(
                copy[4].format(domain=domain),
                icon=":material/rocket_launch:",
                type="primary",
                disabled=not st.session_state.generated_html,
                key=f"publish_to_domain_{domain}",
                width="stretch",
            ):
                with st.spinner(copy[4].format(domain=domain)):
                    try:
                        publish_to_owned_domain(user_id, domain)
                        show_after_rerun(copy[5].format(domain=domain))
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
            open_column.link_button(copy[6], f"https://{domain}", icon=":material/open_in_new:", width="stretch")
    if st.button(copy[7], icon=":material/refresh:", key="refresh_domain_orders_button"):
        st.session_state.refresh_domain_orders = True
        st.rerun()
    st.divider()


def render_domain_and_deployment_ui() -> None:
    """Rendert die Premium-geschützte Konfiguration für die Vercel-Veröffentlichung."""
    labels = publish_copy()
    language = str(st.session_state.app_language)
    domain_copy_by_language = {
        "de": ["Live-Vorschau des Entwurfs öffnen", "Wunschadresse festlegen", "Wählen Sie die Adresse für Ihre Website, bevor Sie das Abonnement abschließen.", "Adresse wählen", "Vercel-Projektadresse", "Eigene Domain verbinden", "Name für die Vercel-Projektadresse", "z. B. autohaus-mueller", "Vercel vergibt die endgültige .vercel.app-Adresse beim Deployment.", "Geplante Adresse: {address}", "Sie können Ihre Website jetzt live schalten."],
        "en": ["Open live draft preview", "Choose your preferred address", "Choose the address for your website before completing the subscription.", "Choose address", "Vercel project address", "Connect your own domain", "Name for the Vercel project address", "e.g. example-company", "Vercel assigns the final .vercel.app address during deployment.", "Planned address: {address}", "You can publish your website now."],
        "ar": ["فتح المعاينة المباشرة للمسودة", "تحديد العنوان المطلوب", "اختر عنوان موقعك قبل إكمال الاشتراك.", "اختيار العنوان", "عنوان مشروع Vercel", "ربط نطاقك الخاص", "اسم عنوان مشروع Vercel", "مثال: example-company", "يحدد Vercel عنوان .vercel.app النهائي عند النشر.", "العنوان المخطط: {address}", "يمكنك نشر موقعك الآن."],
        "ku": ["کردنەوەی پێشبینینی ڕاستەوخۆی ڕەشنووس", "دیاریکردنی ناونیشانی دڵخواز", "پێش تەواوکردنی بەشداریکردن ناونیشانی وێبگەکەت هەڵبژێرە.", "هەڵبژاردنی ناونیشان", "ناونیشانی پڕۆژەی Vercel", "بەستنەوەی دۆمەینی خۆت", "ناوی ناونیشانی پڕۆژەی Vercel", "بۆ نموونە: example-company", "Vercel لە کاتی بڵاوکردنەوە ناونیشانی کۆتایی .vercel.app دیاری دەکات.", "ناونیشانی پلانکراو: {address}", "ئێستا دەتوانیت وێبگەکەت بڵاوبکەیتەوە."],
        "es": ["Abrir vista previa del borrador", "Definir la dirección deseada", "Elija la dirección de su sitio antes de completar la suscripción.", "Elegir dirección", "Dirección del proyecto Vercel", "Conectar dominio propio", "Nombre de la dirección del proyecto Vercel", "p. ej. empresa-ejemplo", "Vercel asigna la dirección .vercel.app definitiva durante la publicación.", "Dirección prevista: {address}", "Ya puede publicar su sitio web."],
        "it": ["Apri l'anteprima della bozza", "Imposta l'indirizzo desiderato", "Scegliete l'indirizzo del sito prima di completare l'abbonamento.", "Scegli indirizzo", "Indirizzo del progetto Vercel", "Collega il tuo dominio", "Nome dell'indirizzo del progetto Vercel", "ad es. azienda-esempio", "Vercel assegna l'indirizzo .vercel.app definitivo durante la pubblicazione.", "Indirizzo previsto: {address}", "Ora potete pubblicare il sito."],
        "hi": ["प्रारूप का लाइव पूर्वावलोकन खोलें", "पसंदीदा पता निर्धारित करें", "सदस्यता पूरी करने से पहले अपनी वेबसाइट का पता चुनें।", "पता चुनें", "Vercel परियोजना पता", "अपना डोमेन जोड़ें", "Vercel परियोजना पते का नाम", "उदा. example-company", "प्रकाशन के समय Vercel अंतिम .vercel.app पता निर्धारित करता है।", "नियोजित पता: {address}", "अब आप अपनी वेबसाइट प्रकाशित कर सकते हैं।"],
    }
    domain_labels = domain_copy_by_language.get(language, domain_copy_by_language["en"])
    external_copy = EXTERNAL_DOMAIN_COPY.get(language, EXTERNAL_DOMAIN_COPY["en"])
    domain_options = ["Vercel-Projektadresse", "Eigene Domain verbinden", "Bereits gekaufte Domain verbinden"]
    domain_option_labels = dict(zip(domain_options, [*domain_labels[4:6], external_copy["option"]]))
    action_copy_by_language = {
        "de": ["Veröffentlichung mit Chatbot", "Das Paket enthält den aktuellen Website-Entwurf einschließlich des konfigurierten Chatbots.", "Vercel-ZIP-Paket mit Chatbot generieren", "Website-Paket wird erstellt ...", "Das Website-Paket ist bereit zum Download.", "Website mit Chatbot herunterladen (ZIP)", "Jetzt auf Vercel veröffentlichen", "Vercel veröffentlicht die Website ...", "Die Website wurde veröffentlicht.", "Ihre Kundenwebsite ist bereit: {url}", "Kundenwebsite jetzt öffnen", "Veröffentlichung fehlgeschlagen", "Aktuelle Veröffentlichung", "Ihre Website ist live: {url}", "Noch keine Website veröffentlicht. Nach der Veröffentlichung können Sie sie hier laden oder löschen.", "Veröffentlichte Seite laden", "Löschen bestätigen", "Veröffentlichte Website löschen", "Entfernt nur das aktuelle Vercel-Deployment. Der gespeicherte Entwurf und das lokale Website-Paket bleiben erhalten.", "Veröffentlichung wird entfernt ...", "Die veröffentlichte Website wurde entfernt.", "Löschen fehlgeschlagen"],
        "en": ["Publish with chatbot", "The package contains the current website draft including the configured chatbot.", "Generate Vercel ZIP package with chatbot", "Creating website package ...", "The website package is ready to download.", "Download website with chatbot (ZIP)", "Publish to Vercel now", "Vercel is publishing the website ...", "The website has been published.", "Your customer website is ready: {url}", "Open customer website now", "Publishing failed", "Current publication", "Your website is live: {url}", "No website has been published yet. After publishing, you can open or delete it here.", "Open published page", "Confirm deletion", "Delete published website", "Only the current Vercel deployment is removed. The saved draft and local website package remain available.", "Removing publication ...", "The published website was removed.", "Deletion failed"],
        "ar": ["النشر مع روبوت المحادثة", "تتضمن الحزمة مسودة الموقع الحالية مع روبوت المحادثة الذي تم إعداده.", "إنشاء حزمة Vercel ZIP مع روبوت المحادثة", "جارٍ إنشاء حزمة الموقع...", "حزمة الموقع جاهزة للتنزيل.", "تنزيل الموقع مع روبوت المحادثة (ZIP)", "النشر الآن على Vercel", "يقوم Vercel بنشر الموقع...", "تم نشر الموقع.", "موقع عميلك جاهز: {url}", "فتح موقع العميل الآن", "فشل النشر", "النشر الحالي", "موقعك متاح الآن: {url}", "لم يتم نشر أي موقع بعد. بعد النشر يمكنك فتحه أو حذفه هنا.", "فتح الصفحة المنشورة", "تأكيد الحذف", "حذف الموقع المنشور", "يؤدي هذا إلى إزالة نشر Vercel الحالي فقط. تبقى المسودة المحفوظة وحزمة الموقع المحلية محفوظتين.", "جارٍ إزالة النشر...", "تمت إزالة الموقع المنشور.", "فشل الحذف"],
        "ku": ["بڵاوکردنەوە لەگەڵ چاتبۆت", "پاکێجەکە ڕەشنووسی ئێستای وێبگە لەگەڵ چاتبۆتی ڕێکخراو لەخۆدەگرێت.", "دروستکردنی پاکێجی Vercel ZIP لەگەڵ چاتبۆت", "پاکێجی وێبگە دروست دەکرێت...", "پاکێجی وێبگە ئامادەی داگرتنە.", "داگرتنی وێبگە لەگەڵ چاتبۆت (ZIP)", "ئێستا لە Vercel بڵاوبکەرەوە", "Vercel وێبگەکە بڵاودەکاتەوە...", "وێبگەکە بڵاوکرایەوە.", "وێبگەی کڕیارەکەت ئامادەیە: {url}", "ئێستا وێبگەی کڕیار بکەرەوە", "بڵاوکردنەوە سەرکەوتوو نەبوو", "بڵاوکراوەی ئێستا", "وێبگەکەت لەسەر هێڵە: {url}", "هێشتا هیچ وێبگەیەک بڵاونەکراوەتەوە. دوای بڵاوکردنەوە دەتوانیت لێرە بیکەیتەوە یان بیسڕیتەوە.", "کردنەوەی پەڕەی بڵاوکراوە", "پشتڕاستکردنەوەی سڕینەوە", "سڕینەوەی وێبگەی بڵاوکراوە", "تەنها بڵاوکراوەی ئێستای Vercel لادەبات. ڕەشنووسی پاشەکەوتکراو و پاکێجی ناوخۆیی دەمێننەوە.", "بڵاوکراوەکە لادەبرێت...", "وێبگە بڵاوکراوەکە لابرا.", "سڕینەوە سەرکەوتوو نەبوو"],
        "es": ["Publicación con chatbot", "El paquete contiene el borrador actual y el chatbot configurado.", "Generar paquete ZIP de Vercel con chatbot", "Creando el paquete del sitio...", "El paquete está listo para descargar.", "Descargar sitio con chatbot (ZIP)", "Publicar ahora en Vercel", "Vercel está publicando el sitio...", "El sitio ha sido publicado.", "El sitio de su cliente está listo: {url}", "Abrir ahora el sitio del cliente", "Error de publicación", "Publicación actual", "Su sitio está en línea: {url}", "Todavía no se ha publicado ningún sitio. Después de publicarlo podrá abrirlo o eliminarlo aquí.", "Abrir página publicada", "Confirmar eliminación", "Eliminar sitio publicado", "Solo se elimina el despliegue actual de Vercel. El borrador y el paquete local se conservan.", "Eliminando publicación...", "El sitio publicado fue eliminado.", "Error al eliminar"],
        "it": ["Pubblicazione con chatbot", "Il pacchetto contiene la bozza attuale e il chatbot configurato.", "Genera pacchetto ZIP Vercel con chatbot", "Creazione del pacchetto del sito...", "Il pacchetto è pronto per il download.", "Scarica sito con chatbot (ZIP)", "Pubblica ora su Vercel", "Vercel sta pubblicando il sito...", "Il sito è stato pubblicato.", "Il sito del cliente è pronto: {url}", "Apri ora il sito del cliente", "Pubblicazione non riuscita", "Pubblicazione attuale", "Il sito è online: {url}", "Nessun sito è stato ancora pubblicato. Dopo la pubblicazione potrete aprirlo o eliminarlo qui.", "Apri pagina pubblicata", "Conferma eliminazione", "Elimina sito pubblicato", "Viene rimosso solo il deployment Vercel attuale. La bozza e il pacchetto locale restano disponibili.", "Rimozione della pubblicazione...", "Il sito pubblicato è stato rimosso.", "Eliminazione non riuscita"],
        "hi": ["चैटबॉट के साथ प्रकाशन", "पैकेज में कॉन्फ़िगर किए गए चैटबॉट सहित वर्तमान वेबसाइट प्रारूप शामिल है।", "चैटबॉट सहित Vercel ZIP पैकेज बनाएं", "वेबसाइट पैकेज बनाया जा रहा है...", "वेबसाइट पैकेज डाउनलोड के लिए तैयार है।", "चैटबॉट सहित वेबसाइट डाउनलोड करें (ZIP)", "अब Vercel पर प्रकाशित करें", "Vercel वेबसाइट प्रकाशित कर रहा है...", "वेबसाइट प्रकाशित हो गई है।", "आपके ग्राहक की वेबसाइट तैयार है: {url}", "ग्राहक वेबसाइट अभी खोलें", "प्रकाशन विफल", "वर्तमान प्रकाशन", "आपकी वेबसाइट लाइव है: {url}", "अभी कोई वेबसाइट प्रकाशित नहीं हुई है। प्रकाशन के बाद आप इसे यहां खोल या हटा सकते हैं।", "प्रकाशित पृष्ठ खोलें", "हटाने की पुष्टि करें", "प्रकाशित वेबसाइट हटाएं", "केवल वर्तमान Vercel प्रकाशन हटाया जाएगा। सहेजा गया प्रारूप और स्थानीय पैकेज उपलब्ध रहेंगे।", "प्रकाशन हटाया जा रहा है...", "प्रकाशित वेबसाइट हटा दी गई।", "हटाना विफल"],
    }
    action_labels = action_copy_by_language.get(language, action_copy_by_language["en"])
    old_publication_copy = {
        "de": ["Alte Veröffentlichung löschen", "Vercel-URL oder Deployment-ID der alten Website", "z. B. meine-seite-abc123.vercel.app", "Ich möchte diese alte Veröffentlichung endgültig löschen.", "Alte veröffentlichte Seite löschen", "Alte Veröffentlichung wird entfernt ...", "Die alte veröffentlichte Website wurde entfernt.", "Löschen fehlgeschlagen"],
        "en": ["Delete an old publication", "Vercel URL or deployment ID of the old website", "e.g. my-site-abc123.vercel.app", "I want to permanently delete this old publication.", "Delete old published page", "Removing old publication ...", "The old published website was removed.", "Deletion failed"],
        "ar": ["حذف نشر قديم", "رابط Vercel أو معرّف نشر الموقع القديم", "مثال: my-site-abc123.vercel.app", "أريد حذف هذا النشر القديم نهائياً.", "حذف الصفحة القديمة المنشورة", "جارٍ إزالة النشر القديم...", "تمت إزالة الموقع القديم المنشور.", "فشل الحذف"],
        "ku": ["سڕینەوەی بڵاوکراوەی کۆن", "بەستەری Vercel یان ناسنامەی بڵاوکردنەوەی وێبگە کۆنەکە", "بۆ نموونە: my-site-abc123.vercel.app", "دەمەوێت ئەم بڵاوکراوە کۆنە بە یەکجاری بسڕمەوە.", "سڕینەوەی پەڕە کۆنە بڵاوکراوەکە", "بڵاوکراوە کۆنەکە لادەبرێت...", "وێبگە کۆنە بڵاوکراوەکە لابرا.", "سڕینەوە سەرکەوتوو نەبوو"],
        "es": ["Eliminar una publicación anterior", "URL de Vercel o ID de despliegue del sitio anterior", "p. ej. mi-sitio-abc123.vercel.app", "Quiero eliminar definitivamente esta publicación anterior.", "Eliminar página publicada anterior", "Eliminando publicación anterior...", "El sitio publicado anterior fue eliminado.", "Error al eliminar"],
        "it": ["Elimina una vecchia pubblicazione", "URL Vercel o ID deployment del vecchio sito", "ad es. mio-sito-abc123.vercel.app", "Voglio eliminare definitivamente questa vecchia pubblicazione.", "Elimina la vecchia pagina pubblicata", "Rimozione della vecchia pubblicazione...", "Il vecchio sito pubblicato è stato rimosso.", "Eliminazione non riuscita"],
        "hi": ["पुराना प्रकाशन हटाएं", "पुरानी वेबसाइट का Vercel URL या प्रकाशन ID", "उदा. my-site-abc123.vercel.app", "मैं इस पुराने प्रकाशन को स्थायी रूप से हटाना चाहता हूं।", "पुराना प्रकाशित पृष्ठ हटाएं", "पुराना प्रकाशन हटाया जा रहा है...", "पुरानी प्रकाशित वेबसाइट हटा दी गई।", "हटाना विफल"],
    }
    old_publication_copy = old_publication_copy.get(language, old_publication_copy["en"])
    next_step_copy = {
        "de": "Nächster Schritt: {step}",
        "en": "Next step: {step}",
        "ar": "الخطوة التالية: {step}",
        "ku": "هەنگاوی داهاتوو: {step}",
        "es": "Siguiente paso: {step}",
        "it": "Passo successivo: {step}",
        "hi": "अगला कदम: {step}",
    }
    next_step_label = next_step_copy.get(language, next_step_copy["en"])
    automated_domain_copy = {
        "de": ["Domain wird geprüft ...", "Jetzt kaufen & veröffentlichen", "Website und sicherer Checkout werden vorbereitet ...", "Sichere Zahlung öffnen", "Der automatische Domainkauf ist momentan nicht verfügbar.", "{domain} ist verfügbar.", "{domain} ist nicht verfügbar.", "Wunschdomain prüfen", "Nach erfolgreicher Zahlung wird Ihre Domain automatisch registriert, verbunden und mit SSL veröffentlicht."],
        "en": ["Checking domain ...", "Buy & publish now", "Preparing your website and secure checkout ...", "Open secure payment", "Automated domain purchasing is currently unavailable.", "{domain} is available.", "{domain} is unavailable.", "Check preferred domain", "After successful payment, your domain is registered, connected, and published with SSL automatically."],
        "ar": ["جارٍ التحقق من النطاق...", "الشراء والنشر الآن", "جارٍ إعداد موقعك والدفع الآمن...", "فتح الدفع الآمن", "شراء النطاق تلقائياً غير متاح حالياً.", "النطاق {domain} متاح.", "النطاق {domain} غير متاح.", "التحقق من النطاق المطلوب", "بعد نجاح الدفع، يتم تسجيل نطاقك وربطه ونشره مع SSL تلقائياً."],
        "ku": ["دۆمەینەکە دەپشکنرێت...", "ئێستا بیکڕە و بڵاوی بکەرەوە", "وێبگە و پارەدانی پارێزراو ئامادە دەکرێت...", "کردنەوەی پارەدانی پارێزراو", "کڕینی خۆکاری دۆمەین لە ئێستادا بەردەست نییە.", "{domain} بەردەستە.", "{domain} بەردەست نییە.", "پشکنینی دۆمەینی دڵخواز", "دوای پارەدانی سەرکەوتوو، دۆمەینەکەت خۆکارانە تۆمار و پەیوەست و بە SSL بڵاودەکرێتەوە."],
        "es": ["Comprobando dominio...", "Comprar y publicar ahora", "Preparando su sitio y el pago seguro...", "Abrir pago seguro", "La compra automática de dominios no está disponible actualmente.", "{domain} está disponible.", "{domain} no está disponible.", "Comprobar dominio deseado", "Tras el pago, su dominio se registra, conecta y publica con SSL automáticamente."],
        "it": ["Verifica del dominio...", "Acquista e pubblica ora", "Preparazione del sito e del pagamento sicuro...", "Apri pagamento sicuro", "L'acquisto automatico del dominio non è al momento disponibile.", "{domain} è disponibile.", "{domain} non è disponibile.", "Verifica dominio desiderato", "Dopo il pagamento, il dominio viene registrato, collegato e pubblicato con SSL automaticamente."],
        "hi": ["डोमेन जांचा जा रहा है...", "अभी खरीदें और प्रकाशित करें", "वेबसाइट और सुरक्षित भुगतान तैयार हो रहा है...", "सुरक्षित भुगतान खोलें", "स्वचालित डोमेन खरीद अभी उपलब्ध नहीं है।", "{domain} उपलब्ध है।", "{domain} उपलब्ध नहीं है।", "पसंदीदा डोमेन जांचें", "सफल भुगतान के बाद आपका डोमेन स्वतः पंजीकृत, कनेक्ट और SSL सहित प्रकाशित होगा।"],
    }
    automated_domain_copy = automated_domain_copy.get(language, automated_domain_copy["en"])
    domain_offer_copy = {
        "de": ("{domain} kaufen & veröffentlichen ({price})", "Sie haben Premium: Sie zahlen nur die Domain, einmalig {price} für 1 Jahr. Kein weiteres Abo.", "Mit dem Premium-Abo (Domain inklusive) veröffentlichen", "Website ist veröffentlicht. Bitte schließen Sie jetzt die Zahlung ab."),
        "en": ("Buy {domain} & publish ({price})", "You have Premium: you only pay for the domain, once, {price} for 1 year. No additional subscription.", "Publish with the Premium subscription (domain included)", "Your website is published. Please complete the payment now."),
        "ar": ("شراء {domain} والنشر ({price})", "لديك Premium: تدفع ثمن النطاق فقط، مرة واحدة {price} لمدة سنة. بدون اشتراك إضافي.", "النشر مع اشتراك Premium (النطاق مشمول)", "تم نشر موقعك. يرجى إكمال الدفع الآن."),
        "ku": ("کڕینی {domain} و بڵاوکردنەوە ({price})", "تۆ Premiumت هەیە: تەنها پارەی دۆمەین دەدەیت، یەکجار {price} بۆ ساڵێک. بێ بەشداریکردنی زیادە.", "بڵاوکردنەوە لەگەڵ بەشداریکردنی Premium (دۆمەین لەخۆدەگرێت)", "وێبگەکەت بڵاوکرایەوە. تکایە ئێستا پارەدانەکە تەواو بکە."),
        "es": ("Comprar {domain} y publicar ({price})", "Tiene Premium: solo paga el dominio, una vez {price} por 1 año. Sin suscripción adicional.", "Publicar con la suscripción Premium (dominio incluido)", "Su sitio está publicado. Complete ahora el pago."),
        "it": ("Acquista {domain} e pubblica ({price})", "Hai Premium: paghi solo il dominio, una volta {price} per 1 anno. Nessun abbonamento aggiuntivo.", "Pubblica con l'abbonamento Premium (dominio incluso)", "Il sito è pubblicato. Completa ora il pagamento."),
        "hi": ("{domain} खरीदें और प्रकाशित करें ({price})", "आपके पास Premium है: केवल डोमेन का भुगतान, एक बार {price}, 1 वर्ष के लिए। कोई अतिरिक्त सदस्यता नहीं।", "Premium सदस्यता के साथ प्रकाशित करें (डोमेन शामिल)", "आपकी वेबसाइट प्रकाशित हो गई है। कृपया अब भुगतान पूरा करें।"),
    }
    domain_offer_copy = domain_offer_copy.get(language, domain_offer_copy["en"])
    is_premium = bool(get_user_status(int(st.session_state.user_id))["subscribed"])
    domain_price_label = f"{DOMAIN_PRICE_EUR:.2f} €".replace(".", ",") if language == "de" else f"€{DOMAIN_PRICE_EUR:.2f}"
    provisioning_copy = {
        "de": ["Zahlung bestätigt. Ihre Website wird eingerichtet ...", "Ihre Website ist fertig.", "Live-Website öffnen", "Die Einrichtung dauert noch an. Diese Seite kann gleich erneut geprüft werden.", "Die automatische Einrichtung konnte nicht abgeschlossen werden. Der Support wurde informiert."],
        "en": ["Payment confirmed. Your website is being set up ...", "Your website is ready.", "Open live website", "Setup is still in progress. You can check this page again shortly.", "Automatic setup could not be completed. Support has been notified."],
        "ar": ["تم تأكيد الدفع. جارٍ إعداد موقعك...", "موقعك جاهز.", "فتح الموقع المباشر", "لا يزال الإعداد جارياً. يمكنك التحقق من هذه الصفحة مرة أخرى بعد قليل.", "تعذر إكمال الإعداد التلقائي. تم إبلاغ الدعم."],
        "ku": ["پارەدان پشتڕاست کرایەوە. وێبگەکەت ئامادە دەکرێت...", "وێبگەکەت ئامادەیە.", "کردنەوەی وێبگەی ڕاستەوخۆ", "ئامادەکردن هێشتا بەردەوامە. دەتوانیت بەم زووانە دووبارە بپشکنیت.", "ئامادەکردنی خۆکار تەواو نەکرا. پشتگیری ئاگادار کرایەوە."],
        "es": ["Pago confirmado. Estamos configurando su sitio...", "Su sitio está listo.", "Abrir sitio web", "La configuración continúa. Puede volver a comprobar esta página en breve.", "No se pudo completar la configuración automática. Se ha informado al soporte."],
        "it": ["Pagamento confermato. Configurazione del sito in corso...", "Il sito è pronto.", "Apri il sito", "La configurazione è ancora in corso. Puoi ricontrollare tra poco.", "Non è stato possibile completare la configurazione automatica. L'assistenza è stata informata."],
        "hi": ["भुगतान की पुष्टि हो गई। आपकी वेबसाइट तैयार की जा रही है...", "आपकी वेबसाइट तैयार है।", "लाइव वेबसाइट खोलें", "सेटअप अभी जारी है। थोड़ी देर बाद इस पृष्ठ पर फिर जांचें।", "स्वचालित सेटअप पूरा नहीं हो सका। सहायता टीम को सूचित कर दिया गया है।"],
    }
    provisioning_copy = provisioning_copy.get(language, provisioning_copy["en"])
    domain_input_copy = {
        "de": ["Ihre Wunschdomain", "z. B. noor.com", "Geben Sie nur Ihren gewünschten Domainnamen ein.", "Gewünschte Domain: {domain}"],
        "en": ["Your preferred domain", "e.g. noor.com", "Enter only your preferred domain name.", "Preferred domain: {domain}"],
        "ar": ["النطاق المطلوب", "مثال: noor.com", "أدخل اسم النطاق الذي تريده فقط.", "النطاق المطلوب: {domain}"],
        "ku": ["دۆمەینی دڵخوازت", "بۆ نموونە: noor.com", "تەنها ناوی دۆمەینی دڵخوازت بنووسە.", "دۆمەینی دڵخواز: {domain}"],
        "es": ["Su dominio deseado", "p. ej. noor.com", "Introduzca únicamente el nombre de dominio deseado.", "Dominio deseado: {domain}"],
        "it": ["Il dominio desiderato", "ad es. noor.com", "Inserite solo il nome del dominio desiderato.", "Dominio desiderato: {domain}"],
        "hi": ["आपका पसंदीदा डोमेन", "उदा. noor.com", "केवल अपना पसंदीदा डोमेन नाम दर्ज करें।", "पसंदीदा डोमेन: {domain}"],
    }
    domain_input_copy = domain_input_copy.get(language, domain_input_copy["en"])
    st.header(labels["title"])

    paid_domain_session_id = str(
        st.session_state.get("paid_domain_checkout_session_id", "")
    ).strip()
    if paid_domain_session_id:
        with st.status(provisioning_copy[0], expanded=True) as status:
            try:
                provisioning = wait_for_domain_provisioning(paid_domain_session_id)
            except ValueError as error:
                status.update(label=str(error), state="error")
            else:
                if provisioning["status"] == "complete" and provisioning["domain"]:
                    live_url = f"https://{provisioning['domain']}"
                    st.session_state.live_url = live_url
                    st.session_state.paid_domain_checkout_session_id = ""
                    status.update(label=provisioning_copy[1], state="complete")
                    st.link_button(
                        provisioning_copy[2],
                        live_url,
                        icon=":material/open_in_new:",
                        type="primary",
                        width="stretch",
                    )
                elif provisioning["status"] == "failed":
                    st.session_state.paid_domain_checkout_session_id = ""
                    status.update(label=provisioning_copy[4], state="error")
                else:
                    status.update(label=provisioning_copy[3], state="running")

    render_owned_domains(language)

    if not st.session_state.generated_html:
        st.info(labels["need_site"])
        return

    chatbot_environment_warning = str(
        st.session_state.get("chatbot_environment_warning", "")
    ).strip()
    if chatbot_environment_warning:
        st.warning(chatbot_environment_warning)

    if st.session_state.get("creation_mode") == "Professionelle Vorlage":
        if st.button(
            domain_labels[0],
            icon=":material/visibility:",
            key="open_full_draft_preview",
            width="stretch",
        ):
            show_full_draft_preview()

    st.subheader(domain_labels[1])
    st.caption(domain_labels[2])
    domain_type = st.radio(
        domain_labels[3],
        domain_options,
        format_func=lambda option: domain_option_labels[option],
        key="domain_type",
    )
    requested_name = ""
    if domain_type == "Vercel-Projektadresse":
        requested_name = st.text_input(
            domain_labels[6],
            value=st.session_state.project_name,
            placeholder=domain_labels[7],
            key="deployment_project_name",
            help=domain_labels[8],
        )
        if requested_name:
            st.caption(
                domain_labels[9].format(
                    address=f"{safe_project_name(requested_name)}.vercel.app"
                )
            )
    elif domain_type == "Bereits gekaufte Domain verbinden":
        st.info(external_copy["intro"])
        help_title, help_text = EXTERNAL_DOMAIN_HELP.get(language, EXTERNAL_DOMAIN_HELP["en"])
        with st.expander(help_title, icon=":material/help:"):
            st.markdown(help_text)
        external_domain = st.text_input(
            external_copy["label"],
            placeholder=external_copy["placeholder"],
            key="external_domain",
        )
        if st.button(
            external_copy["button"],
            icon=":material/link:",
            type="primary",
            disabled=not external_domain.strip(),
            key="connect_external_domain",
            width="stretch",
        ):
            with st.status(external_copy["working"], expanded=True) as status:
                try:
                    dns_status = connect_external_domain(int(st.session_state.user_id), external_domain)
                    message = (
                        external_copy["connected"].format(domain=normalize_domain(external_domain))
                        if dns_status["connected"]
                        else external_copy["pending"]
                    )
                    status.update(label=message, state="complete")
                    show_after_rerun(message)
                    st.session_state.refresh_domain_orders = True
                    st.rerun()
                except ValueError as error:
                    status.update(label=action_labels[11], state="error")
                    st.error(str(error))
    else:
        st.info(automated_domain_copy[8])
        custom_domain = st.text_input(
            domain_input_copy[0],
            placeholder=domain_input_copy[1],
            key="custom_domain",
            help=domain_input_copy[2],
        )
        if custom_domain:
            try:
                displayed_domain = normalize_domain(custom_domain)
            except ProvisioningError:
                displayed_domain = custom_domain.strip()
            st.caption(domain_input_copy[3].format(domain=displayed_domain))
        if st.button(
            automated_domain_copy[7],
            icon=":material/domain_verification:",
            disabled=not custom_domain.strip() or not (INWX_USERNAME and INWX_PASSWORD),
            key="check_custom_domain_with_mcp",
            width="stretch",
        ):
            with st.spinner(automated_domain_copy[0]):
                try:
                    domain_check = check_domain_with_registrar(custom_domain)
                    domain_check["source"] = "authoritative"
                    domain_check["message"] = automated_domain_copy[
                        5 if domain_check.get("available") else 6
                    ].format(domain=domain_check["domain"])
                    st.session_state.domain_check_result = domain_check
                    if domain_check.get("available"):
                        st.success(str(domain_check["message"]))
                    elif domain_check.get("status") == "registered":
                        st.warning(str(domain_check["message"]))
                    else:
                        st.error(str(domain_check["message"]))
                except (ValueError, ProvisioningError) as error:
                    st.error(str(error))
        domain_check = st.session_state.get("domain_check_result")
        if isinstance(domain_check, dict) and domain_check.get("domain"):
            checked_domain = str(domain_check.get("domain", ""))
            if checked_domain == custom_domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/"):
                if domain_check.get("next_step"):
                    st.info(next_step_label.format(step=domain_check["next_step"]))
                if domain_check.get("cost_guidance"):
                    st.caption(str(domain_check["cost_guidance"]))
        registrar_ready = bool(INWX_USERNAME and INWX_PASSWORD)
        try:
            normalized_custom_domain = normalize_domain(custom_domain)
        except ProvisioningError:
            normalized_custom_domain = ""
        domain_available = bool(
            isinstance(domain_check, dict)
            and domain_check.get("source") == "authoritative"
            and domain_check.get("available")
            and str(domain_check.get("domain", "")) == normalized_custom_domain
        )
        if not registrar_ready:
            st.warning(automated_domain_copy[4])
        checked_domain_name = normalized_custom_domain or custom_domain.strip()
        if is_premium:
            st.caption(domain_offer_copy[1].format(price=domain_price_label))
            buy_label = domain_offer_copy[0].format(domain=checked_domain_name or "Domain", price=domain_price_label)
        else:
            buy_label = domain_offer_copy[2]
        checkout_prepared = bool(
            st.session_state.get("stripe_checkout_url")
            and st.session_state.get("prepared_checkout_domain") == normalized_custom_domain
        )
        if checkout_prepared:
            st.success(domain_offer_copy[3])
        elif st.button(
            buy_label,
            icon=":material/shopping_cart_checkout:",
            type="primary",
            disabled=not domain_available,
            key="buy_and_publish_custom_domain",
            width="stretch",
        ):
            with st.status(automated_domain_copy[2], expanded=True) as status:
                try:
                    # Erst den gewählten Entwurf veröffentlichen: Nach der Zahlung verbindet
                    # der Webhook die Domain mit genau diesem Projekt, die Website ist sofort da.
                    st.session_state.project_name = create_deployment_project_name()
                    st.session_state.vercel_project_id = ""
                    publish_website()
                    project_id = str(st.session_state.vercel_project_id)
                    if not project_id:
                        raise ValueError("Vercel hat keine Projekt-ID für die Website geliefert.")
                    # Stripe öffnet die App danach in einer neuen Sitzung: Entwurf sichern.
                    website_id = save_website(
                        int(st.session_state.user_id),
                        str(domain_check["domain"]),
                        create_preview_html(st.session_state.generated_html),
                        str(domain_check["domain"]),
                        str(st.session_state.analytics_site_id),
                        site_pages={**dict(st.session_state.site_pages), "index.html": st.session_state.generated_html},
                        assets=dict(st.session_state.assets),
                    )
                    st.session_state.stripe_checkout_url = create_stripe_checkout_session(
                        int(st.session_state.user_id),
                        st.session_state.user_email,
                        str(domain_check["domain"]),
                        project_id,
                        project_name=st.session_state.project_name,
                        website_id=website_id,
                        one_time_domain=is_premium,
                    )
                    st.session_state.prepared_checkout_domain = str(domain_check["domain"])
                    status.update(label=domain_offer_copy[3], state="complete")
                except (ValueError, ProvisioningError) as error:
                    status.update(label=action_labels[11], state="error")
                    st.error(str(error))
        custom_checkout_url = str(st.session_state.get("stripe_checkout_url", ""))
        if domain_available and custom_checkout_url and (
            st.session_state.get("prepared_checkout_domain") == normalized_custom_domain
        ):
            st.link_button(
                automated_domain_copy[3],
                custom_checkout_url,
                icon=":material/lock:",
                type="primary",
                width="stretch",
            )

    if st.session_state.get("publish_after_checkout"):
        st.session_state.publish_after_checkout = False
        if domain_type == "Vercel-Projektadresse":
            st.session_state.project_name = safe_project_name(requested_name or "")
        with st.status(action_labels[7], expanded=True) as status:
            try:
                publish_website()
                status.update(label=action_labels[8], state="complete")
                st.success(action_labels[9].format(url=st.session_state.live_url))
                st.link_button(
                    action_labels[10],
                    st.session_state.live_url,
                    icon=":material/open_in_new:",
                    type="primary",
                    key="open_customer_site_after_checkout",
                    width="stretch",
                )
            except ValueError as error:
                status.update(label=action_labels[11], state="error")
                st.error(str(error))

    st.info(
        "Website-Erstellung, Vorschau und Veröffentlichung auf einer Vercel-Adresse "
        "sind direkt ohne Stripe-Zahlung möglich."
    )
    st.divider()
    st.subheader(action_labels[0], anchor=False)
    st.caption(action_labels[1])
    if st.button(
        action_labels[2],
        icon=":material/folder_zip:",
        key="generate_chatbot_website_zip",
        width="stretch",
    ):
        with st.spinner(action_labels[3]):
            st.session_state.finished_website_zip = build_website_zip()
        st.success(action_labels[4])
    if st.session_state.get("finished_website_zip"):
        st.download_button(
            action_labels[5],
            data=st.session_state.finished_website_zip,
            file_name="kunden-website-mit-chatbot.zip",
            mime="application/zip",
            icon=":material/download:",
            key="download_website_zip",
            width="stretch",
        )
    if domain_type == "Vercel-Projektadresse":
        if st.button(
            action_labels[6],
            icon=":material/rocket_launch:",
            type="primary",
            key="publish_from_domain_center",
            width="stretch",
        ):
            st.session_state.project_name = safe_project_name(requested_name or "")
            with st.status(action_labels[7], expanded=True) as status:
                try:
                    publish_website()
                    status.update(label=action_labels[8], state="complete")
                    st.success(action_labels[9].format(url=st.session_state.live_url))
                    st.link_button(
                        action_labels[10],
                        st.session_state.live_url,
                        icon=":material/open_in_new:",
                        type="primary",
                        key="open_customer_site_after_publish",
                        width="stretch",
                    )
                except ValueError as error:
                    status.update(
                        label=f"{action_labels[11]}: {error}",
                        state="error",
                        expanded=True,
                    )
                    st.error(str(error))

    st.divider()
    st.subheader(action_labels[12], anchor=False)
    if st.session_state.deployment_id:
        st.success(action_labels[13].format(url=st.session_state.live_url))
    else:
        st.info(action_labels[14])
    action_column, delete_column = st.columns(2)
    with action_column:
        if st.session_state.deployment_id:
            st.link_button(
                action_labels[15],
                st.session_state.live_url,
                icon=":material/open_in_new:",
                key="open_published_site_from_domain_center",
                width="stretch",
            )
        else:
            st.button(
                action_labels[15],
                icon=":material/open_in_new:",
                disabled=True,
                key="open_published_site_disabled",
                width="stretch",
            )
    with delete_column:
        delete_confirmed = st.checkbox(
            action_labels[16],
            key="delete_published_site_confirmation",
            disabled=not st.session_state.deployment_id,
        )
        delete_requested = st.button(
            action_labels[17],
            icon=":material/delete:",
            type="secondary",
            disabled=not st.session_state.deployment_id or not delete_confirmed,
            key="delete_published_site_from_domain_center",
            width="stretch",
        )
    st.caption(action_labels[18])
    if delete_requested:
        with st.status(action_labels[19], expanded=True) as status:
            try:
                delete_published_website()
                status.update(label=action_labels[20], state="complete")
                show_after_rerun(action_labels[20])
                st.rerun()
            except ValueError as error:
                status.update(label=action_labels[21], state="error")
                st.error(str(error))

    st.divider()
    st.subheader(old_publication_copy[0], anchor=False)
    old_deployment_reference = st.text_input(
        old_publication_copy[1],
        placeholder=old_publication_copy[2],
        key="old_deployment_reference",
    )
    old_deployment_confirmed = st.checkbox(
        old_publication_copy[3],
        key="old_deployment_delete_confirmation",
    )
    if st.button(
        old_publication_copy[4],
        icon=":material/delete_forever:",
        type="secondary",
        disabled=not old_deployment_reference.strip() or not old_deployment_confirmed,
        key="delete_old_published_site",
        width="stretch",
    ):
        with st.status(old_publication_copy[5], expanded=True) as status:
            try:
                delete_previous_vercel_deployment(old_deployment_reference)
                status.update(label=old_publication_copy[6], state="complete")
                show_after_rerun(old_publication_copy[6])
                st.rerun()
            except ValueError as error:
                status.update(label=old_publication_copy[7], state="error")
                st.error(str(error))


def render_customer_service_ui(user_id: int, user_email: str) -> None:
    """Ermöglicht Kunden Feedback und nachvollziehbare Supportanfragen."""
    language = str(st.session_state.app_language)
    copy = {
        "de": ["Kundenservice", "Melden Sie einen Fehler, eine Frage oder Feedback. Beschreiben Sie den betroffenen Bereich und die Schritte möglichst genau, damit wir schnell helfen können.", "Anliegen", "Betroffener App-Bereich", "Kurzer Betreff", "z. B. Vorschau lädt nach Bild-Upload nicht", "Was ist passiert oder welches Feedback möchten Sie geben?", "Beschreiben Sie das gewünschte Ergebnis und was stattdessen passiert ist.", "Schritte bis zum Problem (optional)", "1. Vorlage wählen\n2. Bild hochladen\n3. Vorschau öffnen", "Anfrage an Kundenservice senden", "Bitte geben Sie einen kurzen Betreff mit mindestens 4 Zeichen ein.", "Bitte beschreiben Sie Ihr Anliegen mit mindestens 15 Zeichen.", "Ihre Anfrage wurde gespeichert. Der Kundenservice kann sie jetzt prüfen.", "Meine Anfragen", "Sie haben noch keine Anfrage gesendet.", "Bereich", "Gesendet", "Kundenservice-Inbox", "Noch keine Kundenanfragen vorhanden.", "Kunde"],
        "en": ["Customer service", "Report an error, ask a question, or share feedback. Describe the affected area and steps precisely so we can help quickly.", "Request type", "Affected app area", "Short subject", "e.g. Preview does not load after image upload", "What happened or what feedback would you like to share?", "Describe the expected result and what happened instead.", "Steps leading to the issue (optional)", "1. Choose template\n2. Upload image\n3. Open preview", "Send request to customer service", "Enter a subject with at least 4 characters.", "Describe your request using at least 15 characters.", "Your request was saved and can now be reviewed.", "My requests", "You have not sent any requests yet.", "Area", "Sent", "Customer service inbox", "No customer requests yet.", "Customer"],
        "ar": ["خدمة العملاء", "أبلغ عن خطأ أو اطرح سؤالاً أو أرسل ملاحظاتك. صف القسم المتأثر والخطوات بدقة حتى نتمكن من مساعدتك سريعاً.", "نوع الطلب", "القسم المتأثر في التطبيق", "موضوع مختصر", "مثال: المعاينة لا تعمل بعد رفع الصورة", "ماذا حدث أو ما الملاحظات التي تريد إرسالها؟", "صف النتيجة المتوقعة وما حدث بدلاً منها.", "خطوات الوصول إلى المشكلة (اختياري)", "1. اختر القالب\n2. ارفع الصورة\n3. افتح المعاينة", "إرسال الطلب إلى خدمة العملاء", "يرجى كتابة موضوع من 4 أحرف على الأقل.", "يرجى وصف طلبك باستخدام 15 حرفاً على الأقل.", "تم حفظ طلبك ويمكن لخدمة العملاء مراجعته الآن.", "طلباتي", "لم ترسل أي طلب بعد.", "القسم", "تاريخ الإرسال", "صندوق طلبات خدمة العملاء", "لا توجد طلبات عملاء بعد.", "العميل"],
        "ku": ["خزمەتگوزاری کڕیار", "هەڵەیەک ڕاپۆرت بکە، پرسیارێک بکە یان بۆچوون بنێرە. بەش و هەنگاوە پەیوەندیدارەکان بە وردی باس بکە بۆ ئەوەی زوو یارمەتیت بدەین.", "جۆری داواکاری", "بەشی پەیوەندیداری ئەپ", "بابەتی کورت", "بۆ نموونە: پێشبینین دوای بارکردنی وێنە کار ناکات", "چی ڕوویدا یان چ بۆچوونێکت هەیە؟", "ئەنجامی چاوەڕوانکراو و ئەوەی لە جیاتی ڕوویدا باس بکە.", "هەنگاوەکانی گەیشتن بە کێشەکە (ئارەزوومەندانە)", "1. قاڵب هەڵبژێرە\n2. وێنە بار بکە\n3. پێشبینین بکەرەوە", "ناردنی داواکاری بۆ خزمەتگوزاری کڕیار", "تکایە بابەتێک بە لانیکەم 4 پیت بنووسە.", "تکایە داواکارییەکەت بە لانیکەم 15 پیت باس بکە.", "داواکارییەکەت پاشەکەوت کرا و ئێستا دەتوانرێت پشکنین بکرێت.", "داواکارییەکانم", "هێشتا هیچ داواکارییەکت نەناردووە.", "بەش", "نێردراوە", "سندووقی خزمەتگوزاری کڕیار", "هێشتا هیچ داواکارییەکی کڕیار نییە.", "کڕیار"],
    }.get(language)
    if copy is None:
        copy = ["Customer service", "Report an error, ask a question, or share feedback.", "Request type", "Affected app area", "Short subject", "e.g. Preview does not load", "What happened?", "Describe the expected result and what happened instead.", "Steps (optional)", "1. Choose template\n2. Upload image\n3. Open preview", "Send request", "Enter a subject with at least 4 characters.", "Describe your request using at least 15 characters.", "Your request was saved.", "My requests", "You have not sent any requests yet.", "Area", "Sent", "Customer service inbox", "No customer requests yet.", "Customer"]
    request_types = ["Fehler melden", "Frage zur Nutzung", "Idee oder Feedback"]
    app_areas = ["Website planen", "Vorlage und Design", "Bilder und Inhalte", "Vorschau und Editor", "Veröffentlichung", "Anmeldung oder Konto", "Andere Funktion"]
    option_labels = {
        "ar": dict(zip(request_types + app_areas, ["الإبلاغ عن خطأ", "سؤال حول الاستخدام", "فكرة أو ملاحظة", "تخطيط الموقع", "القالب والتصميم", "الصور والمحتوى", "المعاينة والمحرر", "النشر", "تسجيل الدخول أو الحساب", "وظيفة أخرى"])),
        "ku": dict(zip(request_types + app_areas, ["ڕاپۆرتکردنی هەڵە", "پرسیار دەربارەی بەکارهێنان", "بیرۆکە یان بۆچوون", "پلانکردنی وێبگە", "قاڵب و دیزاین", "وێنە و ناوەڕۆک", "پێشبینین و دەستکاریکەر", "بڵاوکردنەوە", "چوونەژوورەوە یان هەژمار", "تایبەتمەندیی تر"])),
    }.get(language, {})
    display_option = lambda option: option_labels.get(option, option)
    st.header(copy[0])
    st.caption(copy[1])

    with st.form("customer_service_form", clear_on_submit=True):
        request_type, app_area = st.columns(2)
        with request_type:
            support_type = st.selectbox(
                copy[2],
                request_types,
                format_func=display_option,
                key="support_request_type",
            )
        with app_area:
            affected_area = st.selectbox(
                copy[3],
                app_areas,
                format_func=display_option,
                key="support_app_area",
            )
        subject = st.text_input(
            copy[4],
            placeholder=copy[5],
            key="support_subject",
        )
        description = st.text_area(
            copy[6],
            placeholder=copy[7],
            key="support_description",
            height=150,
        )
        reproduction_steps = st.text_area(
            copy[8],
            placeholder=copy[9],
            key="support_reproduction_steps",
            height=110,
        )
        submitted = st.form_submit_button(
            copy[10],
            icon=":material/send:",
            type="primary",
            width="stretch",
        )

    if submitted:
        if len(subject.strip()) < 4:
            st.error(copy[11])
        elif len(description.strip()) < 15:
            st.error(copy[12])
        else:
            save_support_request(
                user_id, support_type, affected_area, subject, description, reproduction_steps
            )
            st.success(copy[13])

    own_requests = get_support_requests(user_id)
    st.subheader(copy[14], anchor=False)
    if not own_requests:
        st.caption(copy[15])
    for request_id, support_type, affected_area, subject, description, steps, created_at in own_requests:
        with st.expander(f"#{request_id} · {support_type} · {subject}"):
            st.caption(f"{copy[16]}: {display_option(affected_area)} · {copy[17]}: {created_at[:16].replace('T', ' ')} UTC")
            st.write(description)
            if steps:
                st.code(steps, language=None)

    if user_email.strip().lower() != SUPPORT_ADMIN_EMAIL or not SUPPORT_ADMIN_EMAIL:
        return

    st.divider()
    st.subheader(copy[18], anchor=False)
    support_requests = get_support_requests()
    if not support_requests:
        st.caption(copy[19])
    for request_id, requester_email, support_type, affected_area, subject, description, steps, created_at in support_requests:
        with st.expander(f"#{request_id} · {support_type} · {subject}"):
            st.caption(
                f"{copy[20]}: {requester_email} · {copy[16]}: {display_option(affected_area)} · "
                f"{copy[17]}: {created_at[:16].replace('T', ' ')} UTC"
            )
            st.write(description)
            if steps:
                st.code(steps, language=None)


def render_industry_content_preset_ui() -> None:
    """Rendert die formularbasierte Branchenauswahl für Website-Inhalte."""
    language = str(st.session_state.app_language)
    copy_by_language = {
        "de": {"caption": "Wählen Sie eine Branche und übernehmen Sie vorbereitete Inhalte in den Entwurf.", "question": "Was ist Ihr Betrieb?", "choose": "Bitte wählen...", "other": "Andere Branche oder Kleingewerbe", "custom": "Branche oder Art des Kleingewerbes", "placeholder": "z. B. Kosmetikstudio, Reinigungsservice oder Fotograf", "apply": "Vorlage automatisch mit Brancheninhalten befüllen", "required": "Bitte geben Sie zuerst eine Branche oder Art des Kleingewerbes ein.", "success": "Die Inhalte für „{industry}“ wurden vorbereitet."},
        "en": {"caption": "Choose an industry and add prepared content to the draft.", "question": "What type of business is it?", "choose": "Please choose...", "other": "Other industry or small business", "custom": "Industry or type of small business", "placeholder": "e.g. beauty salon, cleaning service, or photographer", "apply": "Automatically fill template with industry content", "required": "Please enter an industry or type of small business first.", "success": "Content for “{industry}” has been prepared."},
        "ar": {"caption": "اختر مجال العمل وأضف المحتوى المُعد مسبقاً إلى المسودة.", "question": "ما نوع نشاطك التجاري؟", "choose": "يرجى الاختيار...", "other": "مجال آخر أو مشروع صغير", "custom": "المجال أو نوع المشروع الصغير", "placeholder": "مثال: صالون تجميل أو شركة تنظيف أو مصور", "apply": "ملء القالب تلقائياً بمحتوى المجال", "required": "يرجى إدخال المجال أو نوع المشروع الصغير أولاً.", "success": "تم إعداد المحتوى للمجال «{industry}»."},
        "ku": {"caption": "بوارێک هەڵبژێرە و ناوەڕۆکی ئامادەکراو زیاد بکە بۆ ڕەشنووسەکە.", "question": "جۆری کاروبارەکەت چییە؟", "choose": "تکایە هەڵبژێرە...", "other": "بواری تر یان کاروباری بچووک", "custom": "بوار یان جۆری کاروباری بچووک", "placeholder": "بۆ نموونە: سالۆنی جوانکاری، خزمەتگوزاری پاککردنەوە یان وێنەگر", "apply": "قاڵبەکە خۆکارانە بە ناوەڕۆکی بوارەکە پڕ بکەرەوە", "required": "تکایە سەرەتا بوار یان جۆری کاروباری بچووک بنووسە.", "success": "ناوەڕۆکی «{industry}» ئامادە کرا."},
    }
    labels = copy_by_language.get(language, copy_by_language["en"])
    industry_names = {
        "ar": {"Bitte wählen...": labels["choose"], "Kfz-Meisterwerkstatt": "ورشة سيارات متخصصة", "Friseursalon": "صالون حلاقة وتجميل", "Dachdeckerfachbetrieb": "شركة متخصصة في الأسقف", "Physiotherapie-Praxis": "عيادة علاج طبيعي", "Restaurant": "مطعم", "Café und Bäckerei": "مقهى ومخبز", "Onlineshop": "متجر إلكتروني", OTHER_INDUSTRY_OPTION: labels["other"]},
        "ku": {"Bitte wählen...": labels["choose"], "Kfz-Meisterwerkstatt": "وەرشەی پسپۆڕی ئۆتۆمبێل", "Friseursalon": "سالۆنی قژبڕین و جوانکاری", "Dachdeckerfachbetrieb": "کۆمپانیای پسپۆڕی سەربان", "Physiotherapie-Praxis": "کلینیکی فیزیۆتێراپی", "Restaurant": "چێشتخانە", "Café und Bäckerei": "کافێ و نانەواخانە", "Onlineshop": "فرۆشگای ئۆنلاین", OTHER_INDUSTRY_OPTION: labels["other"]},
    }.get(language, {"Bitte wählen...": labels["choose"], OTHER_INDUSTRY_OPTION: labels["other"]})
    display_industry = lambda option: industry_names.get(option, option)
    industry_options = ["Bitte wählen..."] + list(INDUSTRY_CONTENT_PRESETS) + [OTHER_INDUSTRY_OPTION]
    selected_industry = str(st.session_state.get("industry_content_preset", "Bitte wählen..."))
    selected_index = industry_options.index(selected_industry) if selected_industry in industry_options else 0
    st.caption(labels["caption"])
    industry = st.selectbox(
        labels["question"],
        industry_options,
        index=selected_index,
        format_func=display_industry,
        key=f"industry_content_preset_{language}",
    )
    st.session_state.industry_content_preset = industry
    custom_industry = ""
    if industry == OTHER_INDUSTRY_OPTION:
        custom_industry = st.text_input(
            labels["custom"],
            placeholder=labels["placeholder"],
            key="custom_industry_name",
        ).strip()
    if industry != "Bitte wählen..." and st.button(
        labels["apply"],
        icon=":material/auto_awesome:",
        type="primary",
        key="apply_industry_content_preset",
    ):
        if industry == OTHER_INDUSTRY_OPTION and not custom_industry:
            st.warning(labels["required"])
        else:
            apply_industry_content_preset()
            st.rerun()
    applied_industry = custom_industry or industry
    if industry != "Bitte wählen..." and st.session_state.get("industry_preset_applied") == applied_industry:
        st.success(labels["success"].format(industry=display_industry(applied_industry)))


def render_transformer_test_ui() -> None:
    """Rendert den manuellen Test für die Transformer-Textoptimierung."""
    st.divider()
    st.subheader("Live-Test: Transformer-Netzwerk", anchor=False)
    st.write("Verwandeln Sie kurze Stichpunkte in einen professionellen Website-Text.")
    test_input = st.text_area(
        "Eingabe, zum Beispiel für die Angebotsseite",
        value=(
            "Bremsen-Service für PKW. Wechseln Beläge und Scheiben. "
            "Dauer ca. 1 Stunde. Qualitätsteile."
        ),
        height=100,
        key="transformer_test_input",
    )
    if st.button(
        "Transformer-Anfrage starten",
        icon=":material/auto_awesome:",
        type="primary",
        key="transformer_test_submit",
    ):
        if not test_input.strip():
            st.warning("Bitte geben Sie zunächst Stichpunkte ein.")
            return
        with st.spinner("Text wird optimiert ..."):
            try:
                st.session_state.transformer_test_result = optimize_text_with_transformer(test_input)
            except ValueError as error:
                st.error(str(error))

    result = str(st.session_state.get("transformer_test_result", "")).strip()
    if result:
        st.markdown("#### Optimierter Website-Text")
        st.info(result)


def render_privacy_policy_ui() -> None:
    """Zeigt eine verständliche Übersicht der in der App genutzten Datenverarbeitung."""
    st.header("Datenschutzbestimmungen")
    st.caption("Stand: 2. September 2026")

    st.subheader("1. Verantwortliche Stelle", anchor=False)
    st.write(PRIVACY_CONTROLLER_NAME or "App-Betreiber")
    if PRIVACY_CONTROLLER_ADDRESS:
        st.write(PRIVACY_CONTROLLER_ADDRESS)
    if PRIVACY_CONTACT_EMAIL:
        st.write(f"Datenschutz-Kontakt: {PRIVACY_CONTACT_EMAIL}")

    st.subheader("2. Datenkategorien", anchor=False)
    st.write(
        "Wir verarbeiten Ihre Konto-E-Mail-Adresse, ein sicher gehashtes Passwort, den Guthaben- "
        "und Premiumstatus sowie gespeicherte Website-Entwürfe. Bei einer Supportanfrage speichern "
        "wir Anliegen, Beschreibung und optionale Reproduktionsschritte. Bitte übermitteln Sie in "
        "Freitextfeldern keine besonderen Kategorien personenbezogener Daten oder Zugangsdaten."
    )

    st.subheader("3. Zwecke und Rechtsgrundlagen", anchor=False)
    st.write(
        "Die Verarbeitung erfolgt zur Bereitstellung Ihres Nutzerkontos, zum Speichern und "
        "Bearbeiten Ihrer Entwürfe sowie zur Bearbeitung von Supportanfragen. Rechtsgrundlage ist "
        "in der Regel Art. 6 Abs. 1 lit. b DSGVO zur Vertragserfüllung. Die optionale KI-Erstellung "
        "und Veröffentlichung erfolgen nur, wenn Sie die jeweilige Funktion aktiv starten."
    )

    st.subheader("4. Empfänger und externe Dienste", anchor=False)
    st.write(
        "Wenn Sie eine Website erstellen oder Inhalte per KI bearbeiten, werden die eingegebenen "
        "Anforderungen an OpenAI übermittelt. Starten Sie eine Veröffentlichung, werden die von "
        "Ihnen gewählten Website-Dateien und Bilder an Vercel übertragen. Der lokale Hilfe-Chat "
        "übermittelt seine Standardantworten und Schreibkorrekturen nicht an OpenAI. Informationen "
        "zu möglichen Drittlandübermittlungen entnehmen Sie bitte den Datenschutzinformationen der "
        "jeweiligen Anbieter."
    )

    st.subheader("5. Speicherdauer", anchor=False)
    st.write(
        "Kontodaten und Entwürfe werden gespeichert, solange Ihr Konto besteht oder bis Sie die "
        "jeweiligen Entwürfe löschen. Supportanfragen werden nur so lange aufbewahrt, wie sie zur "
        "Bearbeitung und nachvollziehbaren Dokumentation erforderlich sind. Gesetzliche "
        "Aufbewahrungspflichten bleiben unberührt."
    )

    st.subheader("6. Sicherheit", anchor=False)
    st.write(
        "Die Anwendung schützt Passwörter durch einen salt-basierten Hash und speichert Daten in "
        "einer lokalen Anwendungsdatenbank. Bitte sichern Sie Ihr Konto mit einem starken, nur hier "
        "verwendeten Passwort und teilen Sie keine Zugangsdaten über den Kundenservice."
    )

    st.subheader("7. Ihre Rechte", anchor=False)
    st.write(
        "Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung "
        "und Datenübertragbarkeit nach Maßgabe der DSGVO. Soweit eine Verarbeitung auf einer "
        "Einwilligung beruht, können Sie diese mit Wirkung für die Zukunft widerrufen. Sie können "
        "sich außerdem bei einer Datenschutzaufsichtsbehörde beschweren."
    )

    st.subheader("8. Kontakt und Änderungen", anchor=False)
    if PRIVACY_CONTACT_EMAIL:
        st.write(f"Für Datenschutzanfragen schreiben Sie an: {PRIVACY_CONTACT_EMAIL}")
    else:
        st.write(
            "Nutzen Sie für Datenschutzanfragen den Bereich Kundenservice in dieser App. Der "
            "App-Betreiber sollte zusätzlich eine Datenschutz-Kontaktadresse in "
            "`privacy_contact_email` in den Streamlit-Secrets hinterlegen."
        )
    st.info(
        "Diese Informationen beschreiben die technische Datenverarbeitung dieser App. Lassen Sie "
        "die Erklärung vor einem öffentlichen oder gewerblichen Einsatz rechtlich prüfen und "
        "aktualisieren Sie sie bei Änderungen an eingesetzten Diensten oder Datenflüssen."
    )


def render_sidebar(user_info: dict) -> None:
    """Rendert Konto, Guthaben und gespeicherte Entwürfe in der Seitenleiste."""
    with st.sidebar:
        workspace_labels = workspace_copy()
        with st.container(border=True):
            st.subheader(t("account"))
            st.caption(st.session_state.user_email)

            if user_info["subscribed"]:
                st.badge(t("premium_active"), icon=":material/workspace_premium:", color="green")
            else:
                st.caption(
                    workspace_labels["trial_sidebar"].format(
                        hours=user_info["trial_remaining_hours"]
                    )
                    if user_info["trial_active"]
                    else workspace_labels["trial_expired"]
                )
                st.caption(workspace_labels["premium_hint"])

            if st.button(t("logout"), icon=":material/logout:", width="stretch"):
                st.session_state.clear()
                st.rerun()

        st.subheader(t("drafts"))

        history_site_name = st.text_input(
            t("draft_name"),
            value=st.session_state.project_name,
            key="history_site_name",
        )
        if st.button(
            t("save_draft"),
            icon=":material/save:",
            disabled=not st.session_state.generated_html,
            width="stretch",
        ):
            save_website(
                st.session_state.user_id,
                str(history_site_name or ""),
                create_preview_html(st.session_state.generated_html),
                st.session_state.live_url,
                str(st.session_state.analytics_site_id),
                site_pages={**dict(st.session_state.site_pages), "index.html": st.session_state.generated_html},
                assets=dict(st.session_state.assets),
            )
            show_after_rerun(workspace_labels["draft_saved"])
            st.rerun()

        saved_websites = get_websites(st.session_state.user_id)
        if not saved_websites:
            st.caption(t("no_drafts"))

        for website_id, site_name, domain in saved_websites:
            with st.expander(site_name):
                if domain:
                    st.caption(domain)
                if st.button(
                    t("load"),
                    key=f"load_website_{website_id}",
                    icon=":material/folder_open:",
                    width="stretch",
                ):
                    saved_website = load_website(st.session_state.user_id, website_id)
                    if saved_website is not None:
                        loaded_name, _loaded_html, loaded_domain, analytics_site_id = saved_website
                        apply_saved_website(st.session_state.user_id, website_id)
                        st.session_state.live_url = loaded_domain
                        st.session_state.deployment_url = loaded_domain
                        st.session_state.deployment_id = ""
                        st.session_state.project_name = safe_project_name(loaded_name)
                        st.session_state.analytics_site_id = (
                            analytics_site_id or str(uuid.uuid4())
                        )
                        st.rerun()
                if st.button(
                    t("delete"),
                    key=f"delete_website_{website_id}",
                    icon=":material/delete:",
                    width="stretch",
                ):
                    delete_saved_website(st.session_state.user_id, website_id)
                    st.rerun()


def render_main_tabs() -> None:
    """Rendert Titel und die Hauptbereiche Erstellen, Verwalten, Service und Datenschutz."""
    workspace_labels = workspace_copy()
    st.title(t("main_title"), anchor=False)

    st.caption(t("main_subtitle"))

    new_tab, manage_tab, service_tab, privacy_tab = st.tabs(
        [t("new_website"), t("load_published"), workspace_labels["service"], workspace_labels["privacy"]]
    )

    with new_tab:
        st.subheader(workspace_labels["project_title"])
        st.caption(workspace_labels["project_hint"])
        creation_mode_labels = {
            "Professionelle Vorlage": workspace_labels["professional"],
            "Freier Entwurf": workspace_labels["free"],
            "Bestehenden Entwurf anpassen": workspace_labels["existing"],
        }
        creation_mode = st.segmented_control(
            workspace_labels["start"],
            ["Professionelle Vorlage", "Freier Entwurf", "Bestehenden Entwurf anpassen"],
            default="Professionelle Vorlage",
            format_func=lambda option: creation_mode_labels[option],
            key="creation_mode",
        )
        page_structure_labels = {
            "Eine übersichtliche Seite": workspace_labels["single"],
            "Mehrseitige Website": workspace_labels["multi"],
        }
        page_structure = st.segmented_control(
            workspace_labels["structure"],
            ["Eine übersichtliche Seite", "Mehrseitige Website"],
            default="Eine übersichtliche Seite",
            format_func=lambda option: page_structure_labels[option],
            key="page_structure",
        )
        render_industry_content_preset_ui()
        st.divider()

        if creation_mode != "Bestehenden Entwurf anpassen":
            st.subheader(workspace_labels["client_title"])
            st.caption(workspace_labels["client_hint"])
            render_client_contact_ui()
            st.divider()

        template_prompt = ""
        if creation_mode == "Professionelle Vorlage":
            template_prompt = render_template_and_design_ui()
        elif creation_mode == "Bestehenden Entwurf anpassen":
            st.info(
                "Importieren Sie eine eigene HTML-Vorlage oder eine öffentlich erreichbare Website. "
            "Danach stehen Vorschau und alle Bearbeitungswerkzeuge zur Verfügung.",
                icon=":material/edit_document:",
            )
            upload_column, website_column = st.columns(2, gap="large")
            with upload_column:
                st.subheader("Eigene Vorlage hochladen", anchor=False)
                uploaded_template = st.file_uploader(
                    "HTML-Vorlage",
                    type=["html", "htm"],
                    key="existing_template_upload",
                    help="Laden Sie eine vollständige HTML-Datei hoch, die Sie für Ihren Kunden anpassen möchten.",
                )
                if st.button(
                    "Vorlage zur Bearbeitung öffnen",
                    icon=":material/upload_file:",
                    key="load_uploaded_template",
                    width="stretch",
                ):
                    try:
                        load_uploaded_html_template(uploaded_template)
                        show_after_rerun("Die Vorlage wurde geladen und kann jetzt bearbeitet werden.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

            with website_column:
                st.subheader("Vorlage aus dem Internet laden", anchor=False)
                template_url = st.text_input(
                    "Öffentliche Website-Adresse",
                    placeholder="https://www.beispiel.de",
                    key="existing_template_url",
                    help="Die Seite muss öffentlich erreichbar sein und darf keinen Login erfordern.",
                )
                if st.button(
                    "Website zur Bearbeitung laden",
                    icon=":material/language:",
                    key="load_existing_template_url",
                    width="stretch",
                ):
                    if not template_url.strip():
                        st.warning("Bitte geben Sie eine öffentliche Website-Adresse ein.")
                    else:
                        with st.status("Website wird als Vorlage geladen ...", expanded=True) as status:
                            try:
                                load_published_website(template_url)
                                st.session_state.project_name = get_project_name_from_url(template_url)
                                status.update(label="Website wurde geladen und kann bearbeitet werden.", state="complete")
                                show_after_rerun("Website wurde geladen und kann bearbeitet werden.")
                                st.rerun()
                            except ValueError as error:
                                status.update(label="Vorlage konnte nicht geladen werden.", state="error")
                                st.error(str(error))

        section_prompt = ""
        if creation_mode != "Bestehenden Entwurf anpassen":
            section_prompt = render_section_configuration()

        if creation_mode != "Bestehenden Entwurf anpassen":
            creation_copy = get_creation_form_copy()
            creation_labels = creation_copy["labels"]
            placement_labels = creation_copy["placements"]
            if creation_mode == "Professionelle Vorlage":
                description = str(st.session_state.get("template_custom_description", ""))
            else:
                description = st.text_area(
                    creation_labels[9],
                    placeholder=creation_labels[10],
                    key="creation_description",
                    height=150,
                )
            source_documents = []
            if creation_mode != "Professionelle Vorlage":
                document_copy = {
                    "de": ("Unternehmensdokumente für die KI (optional)", "PDF-, TXT- oder Markdown-Dateien werden zerlegt und per Vektorsuche als belegte Inhaltsquelle verwendet."),
                    "en": ("Business documents for AI (optional)", "PDF, TXT, or Markdown files are chunked and used as verified content sources through vector search."),
                    "ar": ("مستندات الشركة للذكاء الاصطناعي (اختياري)", "تُقسّم ملفات PDF أو TXT أو Markdown وتُستخدم كمصادر موثوقة عبر البحث المتجهي."),
                    "ku": ("بەڵگەنامەکانی کۆمپانیا بۆ زیرەکی دەستکرد (ئارەزوومەندانە)", "فایلەکانی PDF و TXT یان Markdown پارچە دەکرێن و بە گەڕانی ڤێکتەر وەک سەرچاوە بەکاردێن."),
                    "es": ("Documentos de empresa para la IA (opcional)", "Los archivos PDF, TXT o Markdown se dividen y se usan como fuentes verificadas mediante búsqueda vectorial."),
                    "it": ("Documenti aziendali per l'IA (facoltativi)", "I file PDF, TXT o Markdown vengono suddivisi e usati come fonti verificate tramite ricerca vettoriale."),
                    "hi": ("एआई के लिए व्यावसायिक दस्तावेज़ (वैकल्पिक)", "PDF, TXT या Markdown फ़ाइलों को भागों में बांटकर वेक्टर खोज से प्रमाणित स्रोत के रूप में उपयोग किया जाता है।"),
                }.get(str(st.session_state.app_language), ("Business documents for AI (optional)", "Documents are used as verified content sources."))
                source_documents = st.file_uploader(
                    document_copy[0],
                    type=["pdf", "txt", "md"],
                    accept_multiple_files=True,
                    help=document_copy[1],
                    key="website_source_documents",
                )
                st.caption(document_copy[1])
                if source_documents:
                    st.success(
                        f"{len(source_documents)} Dokument(e) bereit: "
                        + ", ".join(document.name for document in source_documents)
                    )
                used_sources = st.session_state.get("document_source_names", [])
                if used_sources:
                    st.info("Für den letzten Entwurf verwendete Quellen: " + ", ".join(used_sources))
            st.subheader(creation_labels[11])
            initial_image = st.file_uploader(
                creation_labels[12],
                type=["png", "jpg", "jpeg", "webp"],
                key="initial_image",
            )
            image_placement = st.selectbox(
                creation_labels[13],
                [
                    "Logo",
                    "Hero- und Willkommensbereich",
                    "Über-uns-Bereich",
                    "Projektbereich",
                ],
                format_func=lambda placement: placement_labels.get(placement, placement),
                disabled=initial_image is None,
                key="image_placement",
            )
            submit_label = (
                creation_labels[14]
                if creation_mode == "Professionelle Vorlage"
                else creation_labels[15]
            )
            if st.button(
                submit_label,
                icon=":material/edit_document:",
                type="primary",
                key="create_website",
                width="stretch",
            ):
                if creation_mode == "Professionelle Vorlage":
                    try:
                        create_professional_standard_draft()
                        show_after_rerun("Die Vorlage wurde mit Ihren Kundendaten übernommen und kann jetzt direkt bearbeitet werden.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
                else:
                    page_prompt = (
                        "Erstelle die statische Startseite `index.html` für eine Vercel-Website. Verwende ausschließlich echte Dateilinks in der Navigation: `index.html` für Leistungen/Start, `angebote.html`, `projekte.html`, `ueber-uns.html` und `kontakt.html`. Verwende keine Hash-Navigation, keine `data-page`-Ansichten und kein JavaScript-Routing. Die verlinkten Unterseiten werden beim Deployment als eigenständige HTML-Dateien bereitgestellt."
                        if page_structure == "Mehrseitige Website"
                        else "Erstelle eine klar gegliederte, einseitige Website mit Navigation zu den jeweiligen Inhaltsbereichen."
                    )
                    prompt = (
                        f"{template_prompt}\n{section_prompt}\n\n"
                    f"WEITERE KUNDENANFORDERUNGEN:\n{description.strip()}\n\n"
                    f"SEITENSTRUKTUR:\n{page_prompt}"
                    )
                    with st.status("Website wird erstellt ...", expanded=True) as status:
                        try:
                            generate_website(
                                prompt,
                                initial_image,
                                source_documents,
                                image_placement,
                                multi_page=page_structure == "Mehrseitige Website",
                            )
                            status.update(label="Website wurde erstellt.", state="complete")
                            show_after_rerun("Website wurde erstellt.")
                            st.rerun()
                        except Exception as error:
                            error_message = str(error) or "Unbekannter Fehler bei der Erstellung."
                            status.update(
                                label=f"Erstellung fehlgeschlagen: {error_message}",
                                state="error",
                            )
                            st.error(error_message)

    with manage_tab:
        import_labels = publish_copy()
        st.subheader(import_labels["load_title"])
        st.caption(import_labels["load_hint"])

        live_url_input = st.text_input(
            import_labels["live_link"],
            placeholder="https://ihre-website.vercel.app",
            key="manage_live_url",
        )

        if st.button(
            import_labels["load_button"],
            icon=":material/settings:",
            type="primary",
            width="stretch",
        ):
            if not live_url_input.strip():
                st.warning(import_labels["link_required"])
            else:
                with st.status(import_labels["loading"], expanded=True) as status:
                    try:
                        load_published_website(live_url_input)
                        status.update(label=import_labels["loaded"], state="complete")
                        show_after_rerun(import_labels["loaded"])
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label=import_labels["failed"],
                            state="error",
                        )
                        st.error(str(error))

    with service_tab:
        render_mcp_content_tools_ui()
        render_analytics_optimization_ui(st.session_state.user_email)
        st.divider()
        render_customer_service_ui(int(st.session_state.user_id), st.session_state.user_email)
        render_transformer_test_ui()

    with privacy_tab:
        render_privacy_policy_ui()

    if st.session_state.live_url:
        st.success("Eine veröffentlichte oder geladene Website ist verfügbar.")

        st.link_button(
            "🔗 Geänderte Website öffnen",
            st.session_state.live_url,
            width="stretch",
        )

        st.caption(f"Live-Link: {st.session_state.live_url}")


def render_generated_website_editor() -> None:
    """Rendert Vorschau, Bearbeitung und Download der erstellten Website."""
    if st.session_state.generated_html:
        st.divider()
        if st.session_state.get("creation_mode") != "Professionelle Vorlage":
            with st.container(border=True):
                st.subheader("Optional: aktuellen Entwurf ersetzen", anchor=False)
                st.caption(
                    "Erstellt aus Ihren Unternehmensdaten eine vollständige, responsive Website mit "
                "klarer Navigation, Leistungen, Vertrauenselementen, Kontaktführung und Chatbot."
                )
                if st.button(
                    "Aktuellen Entwurf durch Standard-Entwurf ersetzen",
                    icon=":material/auto_awesome:",
                    type="secondary",
                    key="create_professional_standard_draft",
                    width="stretch",
                ):
                    with st.status(
                        "Professioneller Standard-Entwurf wird erstellt ...", expanded=True
                    ) as status:
                        try:
                            create_professional_standard_draft()
                            status.update(label="Professioneller Standard-Entwurf wurde erstellt.", state="complete")
                            show_after_rerun("Professioneller Standard-Entwurf wurde erstellt.")
                            st.rerun()
                        except ValueError as error:
                            status.update(label="Entwurf konnte nicht erstellt werden.", state="error")
                            st.error(str(error))
            st.divider()
        st.header(t("live_preview"))
        render_live_site_preview(build_draft_preview_pages(), key="draft_live_preview")
        st.header(t("edit_website"))

        editor_language = str(st.session_state.app_language)
        editor_copy = {
            "de": {"tabs": ["Live-Design", "Direkt bearbeiten", "Inhalte", "Design", "Bilder", "HTML-Code"], "select": "Bereich auswählen", "sections": ["Navigation", "Hero-Bereich", "Über mich", "Leistungen", "Projekte", "Kontakt", "Footer", "Neuen Bereich hinzufügen"], "change": "Gewünschte Änderung", "placeholder": "Beispiel: Ersetzen Sie das Kontaktformular und behalten Sie das aktuelle Design.", "update": "Bereich aktualisieren", "required": "Bitte beschreiben Sie die gewünschte Änderung.", "working": "Bereich wird bearbeitet ...", "done": "Vorschau wurde aktualisiert.", "failed": "Änderung fehlgeschlagen"},
            "en": {"tabs": ["Live design", "Direct editing", "Content", "Design", "Images", "HTML code"], "select": "Select section", "sections": ["Navigation", "Hero section", "About", "Services", "Projects", "Contact", "Footer", "Add new section"], "change": "Requested change", "placeholder": "Example: Replace the contact form and preserve the current design.", "update": "Update section", "required": "Please describe the requested change.", "working": "Editing section ...", "done": "Preview updated.", "failed": "Change failed"},
            "ar": {"tabs": ["التصميم المباشر", "التحرير المباشر", "المحتوى", "التصميم", "الصور", "كود HTML"], "select": "اختر القسم", "sections": ["التنقل", "الواجهة الرئيسية", "من نحن", "الخدمات", "المشاريع", "الاتصال", "التذييل", "إضافة قسم جديد"], "change": "التغيير المطلوب", "placeholder": "مثال: استبدل نموذج الاتصال مع الحفاظ على التصميم الحالي.", "update": "تحديث القسم", "required": "يرجى وصف التغيير المطلوب.", "working": "جارٍ تعديل القسم...", "done": "تم تحديث المعاينة.", "failed": "فشل التغيير"},
            "ku": {"tabs": ["دیزاینی ڕاستەوخۆ", "دەستکاریی ڕاستەوخۆ", "ناوەڕۆک", "دیزاین", "وێنەکان", "کۆدی HTML"], "select": "بەش هەڵبژێرە", "sections": ["ڕێنیشاندەر", "بەشی سەرەکی", "دەربارە", "خزمەتگوزارییەکان", "پڕۆژەکان", "پەیوەندی", "پێپەڕە", "زیادکردنی بەشی نوێ"], "change": "گۆڕانکاریی داواکراو", "placeholder": "بۆ نموونە: فۆڕمی پەیوەندی بگۆڕە و دیزاینی ئێستا بهێڵەرەوە.", "update": "نوێکردنەوەی بەش", "required": "تکایە گۆڕانکاریی داواکراو ڕوون بکەرەوە.", "working": "بەشەکە دەستکاری دەکرێت...", "done": "پێشبینین نوێ کرایەوە.", "failed": "گۆڕانکاری سەرکەوتوو نەبوو"},
            "es": {"tabs": ["Diseño en vivo", "Edición directa", "Contenido", "Diseño", "Imágenes", "Código HTML"], "select": "Seleccionar sección", "sections": ["Navegación", "Portada", "Sobre nosotros", "Servicios", "Proyectos", "Contacto", "Pie de página", "Añadir nueva sección"], "change": "Cambio solicitado", "placeholder": "Ejemplo: Sustituye el formulario de contacto y conserva el diseño actual.", "update": "Actualizar sección", "required": "Describe el cambio solicitado.", "working": "Editando la sección...", "done": "Vista previa actualizada.", "failed": "Error al aplicar el cambio"},
            "it": {"tabs": ["Design dal vivo", "Modifica diretta", "Contenuti", "Design", "Immagini", "Codice HTML"], "select": "Seleziona sezione", "sections": ["Navigazione", "Sezione principale", "Chi siamo", "Servizi", "Progetti", "Contatti", "Piè di pagina", "Aggiungi nuova sezione"], "change": "Modifica richiesta", "placeholder": "Esempio: sostituisci il modulo di contatto e conserva il design attuale.", "update": "Aggiorna sezione", "required": "Descrivi la modifica richiesta.", "working": "Modifica della sezione...", "done": "Anteprima aggiornata.", "failed": "Modifica non riuscita"},
            "hi": {"tabs": ["लाइव डिज़ाइन", "सीधा संपादन", "सामग्री", "डिज़ाइन", "चित्र", "HTML कोड"], "select": "अनुभाग चुनें", "sections": ["नेविगेशन", "मुख्य अनुभाग", "हमारे बारे में", "सेवाएं", "परियोजनाएं", "संपर्क", "पादलेख", "नया अनुभाग जोड़ें"], "change": "अनुरोधित बदलाव", "placeholder": "उदाहरण: संपर्क फ़ॉर्म बदलें और वर्तमान डिज़ाइन बनाए रखें।", "update": "अनुभाग अपडेट करें", "required": "कृपया अनुरोधित बदलाव का वर्णन करें।", "working": "अनुभाग संपादित हो रहा है...", "done": "पूर्वावलोकन अपडेट हो गया।", "failed": "बदलाव विफल रहा"},
        }.get(editor_language)
        if editor_copy is None:
            editor_copy = {"tabs": ["Live design", "Direct editing", "Content", "Design", "Images", "HTML code"], "select": "Select section", "sections": ["Navigation", "Hero section", "About", "Services", "Projects", "Contact", "Footer", "Add new section"], "change": "Requested change", "placeholder": "Describe the requested change.", "update": "Update section", "required": "Please describe the requested change.", "working": "Editing section ...", "done": "Preview updated.", "failed": "Change failed"}
        internal_sections = ["Navigation", "Hero-Bereich", "Über mich", "Leistungen", "Projekte", "Kontakt", "Footer", "Neuen Bereich hinzufügen"]
        localized_sections = dict(zip(internal_sections, editor_copy["sections"]))
        live_editor_tab, direct_edit_tab, content_tab, design_tab, image_tab, html_tab = st.tabs(
            editor_copy["tabs"]
        )

        with live_editor_tab:
            render_editor()

        with direct_edit_tab:
            render_direct_content_editor()

        with content_tab:
            section = st.selectbox(
                editor_copy["select"],
                internal_sections,
                format_func=lambda option: localized_sections.get(option, option),
                key="content_editor_section",
            )

            change_request = st.text_area(
                editor_copy["change"],
                placeholder=editor_copy["placeholder"],
                key="content_editor_request",
                height=130,
            )

            if st.button(
                editor_copy["update"],
                key="apply_content_editor_request",
                width="stretch",
            ):
                if not change_request.strip():
                    st.warning(editor_copy["required"])
                else:
                    with st.status(editor_copy["working"], expanded=True) as status:
                        try:
                            modify_current_website(
                                f"Ändere ausschließlich den Bereich „{section}“: "
                            f"{change_request}"
                            )
                            status.update(label=editor_copy["done"], state="complete")
                            show_after_rerun(editor_copy["done"])
                            st.rerun()
                        except Exception as error:
                            status.update(
                                label=editor_copy["failed"],
                                state="error",
                            )
                            st.error(str(error))

        with design_tab:
            st.subheader("Markenauftritt")
            company_name = str(st.session_state.get("client_company_name", "")).strip()
            company_slogan = str(st.session_state.get("client_company_slogan", "")).strip()
            contact_email = str(st.session_state.get("client_business_email", "")).strip()
            contact_phone = str(st.session_state.get("client_business_phone", "")).strip()
            st.caption(
                "Firmenname, Slogan, Kontaktdaten und Chatbot-Wissen bearbeiten Sie oben "
            "im Bereich Kundendaten."
            )
            brand_color = st.color_picker(
                "Markenfarbe",
                "#38BDF8",
                key="premium_brand_color",
            )
            accent_color = st.color_picker(
                "Akzentfarbe für Highlights und Icons",
                "#14B8A6",
                key="premium_accent_color",
            )
            company_description = st.text_area(
                "Kurzbeschreibung für Über uns",
                key="premium_company_description",
                height=100,
            )
            social_columns = st.columns(2)
            with social_columns[0]:
                instagram_link = st.text_input(
                    "Instagram-Link",
                    placeholder="https://instagram.com/ihrunternehmen",
                    key="premium_instagram_link",
                )
            with social_columns[1]:
                linkedin_link = st.text_input(
                    "LinkedIn-Link",
                    placeholder="https://linkedin.com/company/ihrunternehmen",
                    key="premium_linkedin_link",
                )

            if st.button(
                "Markenauftritt übernehmen",
                icon=":material/save:",
                key="apply_premium_basics",
                width="stretch",
            ):
                if not company_name.strip() or not re.fullmatch(
                    r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email.strip()
                ):
                    st.warning("Geben Sie einen Firmennamen und eine gültige Kontakt-E-Mail-Adresse ein.")
                else:
                    with st.status("Markenauftritt wird aktualisiert ...", expanded=True) as status:
                        try:
                            modify_current_website(
                                f"""
Aktualisiere den Markenauftritt: Firmenname „{company_name.strip()}“,
Slogan „{company_slogan.strip()}“, Kontakt-E-Mail „{contact_email.strip()}“,
Telefonnummer „{contact_phone.strip()}“, Markenfarbe „{brand_color}" und
Akzentfarbe „{accent_color}". Aktualisiere den Über-uns-Bereich mit dieser
Kurzbeschreibung: „{company_description.strip()}“.
Nutze im Footer nur diese Social-Media-Links: Instagram „{instagram_link.strip()}"
und LinkedIn „{linkedin_link.strip()}". Entferne einen Social-Link, wenn dafür
keine gültige URL angegeben wurde. Erfinde keine zusätzlichen Öffnungszeiten, Preise oder
Angebote. Alle sonstigen Inhalte und Bilder bleiben erhalten.
"""
                            )
                            status.update(label="Markenauftritt wurde übernommen.", state="complete")
                            show_after_rerun("Markenauftritt wurde übernommen.")
                            st.rerun()
                        except Exception as error:
                            status.update(label="Aktualisierung fehlgeschlagen", state="error")
                            st.error(str(error))

            st.divider()
            design_request = st.text_area(
                "Design-Änderung",
                placeholder=(
                    "Beispiel: Dunkles Premium-Design mit goldenen Akzenten, "
                "runden Karten und größeren Buttons."
                ),
                key="design_editor_request",
                height=130,
            )

            if st.button(
                "🎨 Design aktualisieren",
                key="apply_design_editor_request",
                width="stretch",
            ):
                if not design_request.strip():
                    st.warning("Bitte beschreibe die gewünschte Design-Änderung.")
                else:
                    with st.status("Design wird angepasst ...", expanded=True) as status:
                        try:
                            modify_current_website(
                                "Ändere ausschließlich Farben, Layout, Abstände und "
                            "Styling. Texte, Bilder und Struktur bleiben erhalten. "
                            f"Wunsch: {design_request}"
                            )
                            status.update(label="✅ Design wurde aktualisiert.", state="complete")
                            show_after_rerun("✅ Design wurde aktualisiert.")
                            st.rerun()
                        except Exception as error:
                            status.update(
                                label="❌ Design-Änderung fehlgeschlagen",
                                state="error",
                            )
                            st.error(str(error))

        with image_tab:
            image_section = st.selectbox(
                "Abschnitt für das Bild",
                ["Logo", "Hero-Bereich", "Über mich", "Leistungen", "Projekte", "Kontakt"],
                key="image_editor_section",
            )

            image_file = st.file_uploader(
                "Neues Bild hochladen",
                type=["png", "jpg", "jpeg", "webp"],
                key="section_image",
            )

            if st.button(
                "🖼️ Bild aktualisieren",
                key="apply_image_editor_request",
                width="stretch",
            ):
                if image_file is None:
                    st.warning("Bitte wähle zuerst ein Bild aus.")
                else:
                    with st.status("Bild wird aktualisiert ...", expanded=True) as status:
                        try:
                            image_name = save_uploaded_image(image_file, image_section)

                            modify_current_website(
                                f"""
Ändere ausschließlich das Bild im Bereich „{image_section}“.

Verwende exakt dieses Bild:
<img src="{image_name}" alt="{image_section} Bild">

Alle anderen Inhalte müssen unverändert bleiben.
"""
                            )

                            status.update(label="✅ Bild wurde aktualisiert.", state="complete")
                            show_after_rerun("✅ Bild wurde aktualisiert.")
                            st.rerun()
                        except Exception as error:
                            status.update(
                                label="❌ Bild-Änderung fehlgeschlagen",
                                state="error",
                            )
                            st.error(str(error))

        with html_tab:
            st.text_area(
                "HTML-Quellcode",
                height=620,
                key="html_editor",
            )

            if st.button(
                "👁️ Vorschau aus HTML aktualisieren",
                key="apply_html_editor_preview",
                width="stretch",
            ):
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
                width="stretch",
            )
