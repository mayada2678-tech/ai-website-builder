import base64
import asyncio
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
import zipfile
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
import streamlit as st
from fastmcp import Client
from openai import OpenAI

from domain_provisioning import (
    ProvisioningError,
    check_domain_with_registrar,
    normalize_domain,
)
from mcp_server import mcp as website_mcp_server


st.set_page_config(
    page_title="AI Website Builder",
    page_icon=":material/auto_awesome:",
    layout="wide",
)

CLICKABLE_TEMPLATE_EDITOR = st.components.v2.component(
        "clickable_template_editor",
        html='<section id="template-editor"></section>',
        css="""
        #template-editor { font-family: Georgia, serif; }
        .template-shell { position: relative; overflow: visible; border: 1px solid var(--border); border-radius: var(--radius); background: var(--background); color: var(--text); }
        .template-header { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 18px 28px; border-bottom: 1px solid var(--border); font-family: ui-sans-serif, sans-serif; }
        .template-nav { display: flex; justify-content: flex-end; gap: 16px; flex-wrap: wrap; font-size: 12px; }
        .template-nav button { border: 0; padding: 0; background: transparent; color: inherit; cursor: pointer; font: inherit; }
        .template-nav button:hover, .template-nav button:focus-visible { color: var(--accent); }
        .template-hero { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(220px, .9fr); gap: 34px; padding: 48px 28px 42px; align-items: center; }
        .template-eyebrow { color: var(--accent); font: 700 11px ui-sans-serif, sans-serif; text-transform: uppercase; }
        .template-heading { margin: 12px 0 0; font-size: 34px; line-height: 1.1; }
        .template-description { max-width: 500px; margin: 18px 0 24px; color: var(--muted); font: 15px/1.65 ui-sans-serif, sans-serif; }
        .template-button { border: 0; display: inline-block; background: var(--accent); color: var(--accent-text); padding: 11px 16px; border-radius: var(--radius); cursor: pointer; font: 700 13px ui-sans-serif, sans-serif; }
        .template-image { width: 100%; min-height: 220px; max-height: 320px; object-fit: cover; border-radius: var(--radius); }
        .template-placeholder { min-height: 220px; border: 1px dashed var(--accent); border-radius: var(--radius); display: grid; place-items: center; padding: 18px; color: var(--accent); text-align: center; font: 700 12px ui-sans-serif, sans-serif; }
        .template-hint { margin: 0; padding: 12px 28px; background: var(--surface); color: var(--muted); font: 12px ui-sans-serif, sans-serif; }
        .template-page { padding: 58px 28px; }
        .template-page h1 { margin: 12px 0; font-size: 38px; line-height: 1.1; }
        .template-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 34px; }
        .template-card { min-height: 210px; padding: 22px; border-top: 3px solid var(--accent); background: var(--surface); font-family: ui-sans-serif, sans-serif; }
        .template-card p { color: var(--muted); }
        .template-footer { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 28px; padding: 34px 28px 20px; border-top: 1px solid var(--border); font-family: ui-sans-serif, sans-serif; }
        .template-footer h2 { margin: 0; font-size: 15px; } .template-footer p, .template-footer a { color: var(--muted); font-size: 13px; line-height: 1.6; text-decoration: none; }
        .template-footer a:hover { color: var(--accent); } .template-footer-legal { grid-column: 1 / -1; margin: 0; padding-top: 16px; border-top: 1px solid var(--border); }
        .template-chatbot { position: fixed; right: 18px; bottom: 18px; z-index: 2147483647; font-family: ui-sans-serif, sans-serif; }
        .template-chatbot-toggle { width: 56px; height: 56px; border: 0; border-radius: 50%; background: var(--accent); color: var(--accent-text); cursor: pointer; font: 700 13px ui-sans-serif, sans-serif; box-shadow: 0 10px 28px rgba(15, 23, 42, .24); }
        .template-chatbot-panel { display: none; width: min(300px, calc(100vw - 44px)); margin: 0 0 10px auto; padding: 18px; background: var(--background); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 16px 38px rgba(15, 23, 42, .22); }
        .template-chatbot-panel.is-open { display: block; }
        .template-chatbot-panel h2 { margin: 0; font-size: 16px; }
        .template-chatbot-panel p { margin: 8px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
        .template-chatbot-form { display: flex; gap: 6px; margin-top: 14px; }
        .template-chatbot-form input { min-width: 0; flex: 1; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--background); color: var(--text); }
        .template-chatbot-form button { border: 0; padding: 8px 10px; border-radius: 4px; background: var(--accent); color: var(--accent-text); cursor: pointer; }
        @media (max-width: 700px) { .template-header { align-items: flex-start; flex-direction: column; } .template-nav { justify-content: flex-start; } .template-hero, .template-cards, .template-footer { grid-template-columns: 1fr; } }
        """,
        js="""
        export default function(component) {
            const { data, parentElement, setTriggerValue } = component;
            const root = parentElement.querySelector('#template-editor');
            if (!root || !data) return;
            const copy = data.copy;
            root.lang = data.language;
            root.dir = data.direction;
            root.replaceChildren();
            const create = (tag, className, text) => {
                const element = document.createElement(tag);
                element.className = className;
                if (text !== undefined) element.textContent = text;
                return element;
            };
            const shell = create('section', 'template-shell');
            shell.style.setProperty('--background', data.backgroundColor);
            shell.style.setProperty('--accent', data.accentColor);
            shell.style.setProperty('--text', data.textColor);
            shell.style.setProperty('--muted', data.mutedTextColor);
            shell.style.setProperty('--border', data.borderColor);
            shell.style.setProperty('--surface', data.surfaceColor);
            shell.style.setProperty('--accent-text', data.accentTextColor);
            shell.style.setProperty('--radius', data.radius);
            const header = create('header', 'template-header');
            const company = create('strong', '', data.companyName);
            const nav = create('nav', 'template-nav');
            if (data.multiPage) {
                Object.entries(copy.nav).forEach(([page, label]) => {
                    const link = create('button', '', label);
                    link.type = 'button';
                    link.onclick = () => setTriggerValue('navigated', page);
                    nav.append(link);
                });
            }
            header.append(company, nav);
            if (data.page !== 'start') {
                const page = create('main', 'template-page');
                const pageContent = copy.pages[data.page];
                page.append(create('p', 'template-eyebrow', pageContent[0]));
                page.append(create('h1', '', pageContent[1]));
                page.append(create('p', 'template-description', data.description));
                const cards = create('section', 'template-cards');
                pageContent[2].forEach(([title, text], index) => {
                    const card = create('article', 'template-card');
                    const fallback = data.page === 'kontakt' && index === 0 ? data.businessEmail : data.description;
                    card.append(create('p', 'template-eyebrow', String(index + 1).padStart(2, '0')), create('h2', '', title), create('p', '', text || fallback));
                    cards.append(card);
                });
                page.append(cards);
                shell.append(header, page, create('p', 'template-hint', copy.pageHint));
                if (data.showCustomerChatbot) {
                    const chatbot = create('aside', 'template-chatbot');
                    const chatbotPanel = create('section', 'template-chatbot-panel');
                    const chatbotAnswer = create('p', '', data.chatbotKnowledge || copy.welcome);
                    const chatbotForm = create('form', 'template-chatbot-form');
                    const chatbotInput = create('input', '');
                    chatbotInput.placeholder = copy.question;
                    chatbotInput.setAttribute('aria-label', copy.question);
                    const chatbotSend = create('button', '', copy.send);
                    chatbotSend.type = 'submit';
                    chatbotForm.append(chatbotInput, chatbotSend);
                    chatbotForm.onsubmit = event => { event.preventDefault(); const question = chatbotInput.value.trim(); if (!question) return; chatbotAnswer.textContent = `${copy.thanks}: „${question}“. ${data.chatbotKnowledge || copy.reply}`; chatbotInput.value = ''; };
                    chatbotPanel.append(create('h2', '', data.chatbotName || `${data.companyName} ${copy.assistant}`), chatbotAnswer, chatbotForm);
                    const chatbotToggle = create('button', 'template-chatbot-toggle', '🤖');
                    chatbotToggle.type = 'button';
                    chatbotToggle.setAttribute('aria-label', copy.openChat);
                    chatbotToggle.title = copy.openChat;
                    chatbotToggle.style.fontSize = '28px';
                    chatbotToggle.style.background = data.chatbotColor || data.accentColor;
                    chatbotToggle.style.borderRadius = data.chatbotRadius || '50%';
                    chatbotToggle.onclick = () => chatbotPanel.classList.toggle('is-open');
                    chatbot.append(chatbotPanel, chatbotToggle);
                    shell.append(chatbot);
                }
                root.append(shell);
                return;
            }
            const hero = create('div', 'template-hero');
            const heroCopy = create('div', '');
            const fields = [['heading', 'h3', 'template-heading'], ['description', 'p', 'template-description'], ['buttonText', 'button', 'template-button']];
            fields.forEach(([key, tag, className]) => {
                const field = create(tag, className, data[key]);
                if (key === 'buttonText') field.type = 'button';
                if (key === 'buttonText') field.onclick = () => setTriggerValue('navigated', 'angebote');
                heroCopy.append(field);
            });
            const image = data.imageDataUrl ? create('img', 'template-image') : create('div', 'template-placeholder', copy.imagePlaceholder);
            if (data.imageDataUrl) { image.src = data.imageDataUrl; image.alt = data.companyName; }
            hero.append(heroCopy, image);
            const templateSections = create('section', 'template-cards');
            data.templateSections.forEach((section, index) => {
                const card = create('article', 'template-card');
                card.append(create('p', 'template-eyebrow', String(index + 1).padStart(2, '0')), create('h2', '', section.title), create('p', '', section.text));
                templateSections.append(card);
            });
            const footer = create('footer', 'template-footer');
            const brand = create('section', '');
            brand.append(create('h2', '', data.companyName), create('p', '', data.footerText));
            const contact = create('section', '');
            contact.append(create('h2', '', copy.contact), create('a', '', data.businessEmail));
            contact.lastChild.href = `mailto:${data.businessEmail}`;
            const legal = create('section', '');
            legal.append(create('h2', '', copy.legal), create('a', '', copy.imprint), create('p', '', copy.privacy));
            const legalNote = create('p', 'template-footer-legal', `© ${new Date().getFullYear()} ${data.companyName}. ${copy.rights}`);
            footer.append(brand, contact, legal, legalNote);
            shell.append(header, hero, templateSections, footer, create('p', 'template-hint', copy.designHint));
            if (data.showCustomerChatbot) {
                const chatbot = create('aside', 'template-chatbot');
                const chatbotPanel = create('section', 'template-chatbot-panel');
                const chatbotAnswer = create('p', '', data.chatbotKnowledge || copy.welcome);
                const chatbotForm = create('form', 'template-chatbot-form');
                const chatbotInput = create('input', '');
                chatbotInput.placeholder = copy.question;
                chatbotInput.setAttribute('aria-label', copy.question);
                const chatbotSend = create('button', '', copy.send);
                chatbotSend.type = 'submit';
                chatbotForm.append(chatbotInput, chatbotSend);
                chatbotForm.onsubmit = event => { event.preventDefault(); const question = chatbotInput.value.trim(); if (!question) return; chatbotAnswer.textContent = `${copy.thanks}: „${question}“. ${data.chatbotKnowledge || copy.reply}`; chatbotInput.value = ''; };
                chatbotPanel.append(create('h2', '', data.chatbotName || `${data.companyName} ${copy.assistant}`), chatbotAnswer, chatbotForm);
                const chatbotToggle = create('button', 'template-chatbot-toggle', '🤖');
                chatbotToggle.type = 'button';
                chatbotToggle.setAttribute('aria-label', copy.openChat);
                chatbotToggle.title = copy.openChat;
                chatbotToggle.style.fontSize = '28px';
                chatbotToggle.style.background = data.chatbotColor || data.accentColor;
                chatbotToggle.style.borderRadius = data.chatbotRadius || '50%';
                chatbotToggle.onclick = () => chatbotPanel.classList.toggle('is-open');
                chatbot.append(chatbotPanel, chatbotToggle);
                shell.append(chatbot);
            }
            root.append(shell);
        }
        """,
)

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
    .st-key-help_chat_launcher {
        position: fixed;
        right: 1.5rem;
        bottom: 1.5rem;
        z-index: 1000000;
    }
    .st-key-help_chat_launcher > button {
        min-width: 3.2rem;
        min-height: 3.2rem;
        border-radius: 50%;
        border-color: #22d3ee;
        box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.55);
        animation: chatbot-pulse 2.2s ease-out infinite;
    }
    [data-testid="stPopoverBody"] {
        width: min(22rem, calc(100vw - 2rem)) !important;
        max-width: calc(100vw - 2rem) !important;
        max-height: min(22rem, calc(100vh - 6rem)) !important;
    }
    @keyframes chatbot-pulse {
        0% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.5); }
        70% { box-shadow: 0 0 0 10px rgba(34, 211, 238, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); }
    }
    @media (prefers-reduced-motion: reduce) {
        .st-key-help_chat_launcher > button {
            animation: none;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

OPENAI_MODEL = "gpt-4o-mini"
FORMSPREE_ENDPOINT = "https://formspree.io/f/mnpqnyvk"
VERCEL_DEPLOYMENTS_URL = (
    "https://api.vercel.com/v13/deployments"
    "?skipAutoDetectionConfirmation=1"
)
DATABASE_PATH = Path(__file__).with_name("saas_platform.db")
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}"
)
TEMPLATES = {
    "Automobil und KFZ-Gewerbe": {
        "icon": ":material/directions_car:",
        "description": "Dynamisches Design fuer Autohaeuser, Werkstaetten und Zulieferer.",
        "sections": "Fahrzeugangebote oder Werkstattservices, Service-Termin, Finanzierung und Leasing, Kundenversprechen, Standort und Kontakt",
        "style_hint": (
            "Nutze scharfkantige Karten, metallische Grautoene, dunkle Akzente "
            "und sportliche rote oder blaue Buttons. Integriere Fahrzeugmodelle "
            "und Werkstatt-Services."
        ),
    },
    "GmbH und Corporate Unternehmen": {
        "icon": ":material/business:",
        "description": "Serioeses, vertrauenswuerdiges B2B-Layout fuer Unternehmen.",
        "sections": "Leistungsportfolio, Branchenkompetenz, Arbeitsweise, Kennzahlen oder Zertifizierungen, Ansprechpartner und Kontakt",
        "style_hint": (
            "Nutze grosszuegigen Freiraum, klare Linien sowie tiefblaue oder "
            "anthrazitfarbene Toene. Integriere Ueber uns, Leistungen, "
            "Zertifizierungen und ein Corporate-Kontaktformular."
        ),
    },
    "Cafe und Baeckerei": {
        "icon": ":material/bakery_dining:",
        "description": "Warmes, handwerkliches Design fuer Cafes und Baeckereien.",
        "sections": "Frühstücks- und Speisekarte, handwerkliche Spezialitäten, Tagesangebot, Öffnungszeiten, Standort und Vorbestellung",
        "style_hint": (
            "Nutze weiche Ecken und warme Toene. Integriere eine Speise- oder "
            "Fruehstueckskarte sowie Oeffnungszeiten."
        ),
    },
    "Restaurant und Gastronomie": {
        "icon": ":material/restaurant:",
        "description": "Elegantes, bildorientiertes Layout mit Fokus auf Reservierungen.",
        "sections": "Speisekarte mit Preisen, kulinarisches Konzept, besondere Menüs, Reservierung, Öffnungszeiten und Anfahrt",
        "style_hint": (
            "Nutze ein edles dunkles Design in Schwarz und Gold oder Dunkelgruen. "
            "Erstelle eine strukturierte Speisekarte mit Preisen und ein "
            "Tischreservierungsformular."
        ),
    },
    "Formale Agentur oder Kanzlei": {
        "icon": ":material/account_balance:",
        "description": "Minimalistisches, hochprofessionelles Design fuer Beratungen und Kanzleien.",
        "sections": "Beratungsfelder, Vorgehensweise, Expertise und Referenzen, Erstgespräch, Ansprechpartner und Kontakt",
        "style_hint": (
            "Nutze elegante serifenlose Typografie, geometrische Strukturen und "
            "monochrome Farben mit einem edlen Akzent. Der Fokus liegt auf "
            "Fallstudien und Erstgespraechen."
        ),
    },
    "Schule und Bildung": {
        "icon": ":material/school:",
        "description": "Uebersichtliche, einladende Vorlage fuer Schulen, Lernzentren und Bildungseinrichtungen.",
        "sections": "Bildungsangebote, Aktuelles und Termine, Lernkonzept, Lehrkräfte oder Team, Informationen für Eltern und Kontakt",
        "style_hint": (
            "Nutze eine freundliche, gut lesbare Gestaltung mit klaren Bereichen fuer "
            "Aktuelles, Unterrichtsangebot, Termine, Lehrkraefte und Kontakt. Wichtige "
            "Informationen fuer Eltern und Lernende muessen schnell auffindbar sein."
        ),
    },
    "Bibliothek": {
        "icon": ":material/local_library:",
        "description": "Ruhige, zugängliche Vorlage fuer Bibliotheken, Medienzentren und Lesecafes.",
        "sections": "Medienangebot, Neuerscheinungen, Veranstaltungen, Mitgliedschaft und Ausleihe, Öffnungszeiten und Kontakt",
        "style_hint": (
            "Nutze ein ruhiges, lesefreundliches Design mit einer klaren Mediensuche, "
            "Oeffnungszeiten, Veranstaltungen, Mitgliedschaft und Kontakt. Hebe neue "
            "Buecher und aktuelle Termine deutlich hervor."
        ),
    },
    "Supermarkt und Einzelhandel": {
        "icon": ":material/storefront:",
        "description": "Praktische, kundennahe Vorlage fuer Supermaerkte, Lebensmittelgeschaefte und Einzelhandel.",
        "sections": "Wochenangebote, Sortiment, Services, Nachhaltigkeit oder Qualität, Öffnungszeiten, Standort und Kontakt",
        "style_hint": (
            "Gestalte einen klaren, aktionsorientierten Auftritt mit Wochenangeboten, "
            "Sortiment, Standort, Oeffnungszeiten und Kontakt. Angebote muessen auf "
            "Mobilgeraeten besonders schnell erfassbar sein."
        ),
    },
}
DESIGN_USE_CASES = {
    "Individuell konfigurieren": {},
    "Landingpage für Angebot oder Kampagne": {
        "background": "#FFFFFF",
        "accent": "#0F766E",
        "border_style": "rounded",
        "page_structure": "Eine übersichtliche Seite",
        "sections": [
            "Hero und Willkommensbereich",
            "Leistungen oder Produkte",
            "Kundenstimmen oder Referenzen",
            "Kontakt und Erreichbarkeit",
        ],
        "description": "Klare Landingpage mit starkem Angebot, Nutzenargumenten, Vertrauen und einer eindeutigen Kontaktaktion.",
    },
    "Business-Website": {
        "background": "#F3F4F6",
        "accent": "#1D4ED8",
        "border_style": "rounded",
        "page_structure": "Mehrseitige Website",
        "sections": [
            "Hero und Willkommensbereich",
            "Über uns",
            "Leistungen oder Produkte",
            "Galerie oder Projekte",
            "Kontakt und Erreichbarkeit",
        ],
        "description": "Vertrauenswürdiger Unternehmensauftritt mit Leistungen, Unternehmensprofil, Projekten und Kontakt.",
    },
    "Kontakt- und Leadformular": {
        "background": "#EFF6FF",
        "accent": "#2563EB",
        "border_style": "rounded",
        "page_structure": "Eine übersichtliche Seite",
        "sections": [
            "Hero und Willkommensbereich",
            "Leistungen oder Produkte",
            "Kontakt und Erreichbarkeit",
        ],
        "description": "Fokussierte Formularseite zur Gewinnung qualifizierter Anfragen mit klaren Vorteilen und Kontaktmöglichkeit.",
    },
    "Daten-Dashboard und Reporting": {
        "background": "#111827",
        "accent": "#22C55E",
        "border_style": "sharp",
        "page_structure": "Mehrseitige Website",
        "sections": [
            "Hero und Willkommensbereich",
            "Leistungen oder Produkte",
            "Galerie oder Projekte",
            "Kontakt und Erreichbarkeit",
        ],
        "description": "Professionelles Informations- und Reporting-Portal mit Kennzahlen, klaren Datenbereichen und Kontakt.",
    },
}
BACKGROUND_PRESET_COLORS = {
    "Weiß": "#FFFFFF",
    "Schwarz": "#000000",
    "Dunkel": "#111827",
    "Hellgrau": "#F3F4F6",
}
SUPPORTED_LANGUAGES = {
    "Deutsch": {"code": "de", "dir": "ltr"},
    "English": {"code": "en", "dir": "ltr"},
    "Arabisch (العربية)": {"code": "ar", "dir": "rtl"},
    "Kurdisch (Kurdî / كوردی)": {"code": "ku", "dir": "rtl"},
    "Türkisch (Türkçe)": {"code": "tr", "dir": "ltr"},
    "Französisch (Français)": {"code": "fr", "dir": "ltr"},
    "Spanisch (Español)": {"code": "es", "dir": "ltr"},
    "Italienisch (Italiano)": {"code": "it", "dir": "ltr"},
    "Hindi (हिन्दी)": {"code": "hi", "dir": "ltr"},
}
APP_LANGUAGES = {
    "Deutsch": "de",
    "English": "en",
    "العربية": "ar",
    "کوردی": "ku",
    "Español": "es",
    "Italiano": "it",
    "हिन्दी": "hi",
}
APP_LANGUAGE_LABELS = {
    "Deutsch": "Deutsch 🇩🇪",
    "English": "English 🇬🇧",
    "Español": "Español 🇪🇸",
    "Italiano": "Italiano 🇮🇹",
    "हिन्दी": "Hindi 🇮🇳",
    "العربية": "العربية 🇦🇪",
    "کوردی": "Kurdî (Sorani) ☀️",
}
TRANSLATIONS = {
    "de": {
        "app_language": "App-Sprache",
        "auth_title": "AI Website Builder",
        "auth_subtitle": "Melden Sie sich an, um Ihre Website zu entwerfen und online zu veröffentlichen.",
        "login": "Anmelden",
        "register": "Konto erstellen",
        "email": "E-Mail-Adresse",
        "password": "Passwort",
        "confirm_password": "Passwort wiederholen",
        "invalid_login": "E-Mail-Adresse oder Passwort ist nicht korrekt.",
        "password_mismatch": "Die Passwörter stimmen nicht überein.",
        "account_created": "Ihr Konto wurde erstellt. Sie können sich jetzt anmelden.",
        "balance_empty": "Ihr KI-Guthaben ist aufgebraucht.",
        "premium_info": "Premium schaltet unbegrenzte Generierungen für 20,00 EUR pro Monat frei.",
        "activate_premium": "Premium im Testmodus aktivieren",
        "low_balance": "Ihr kostenloses Guthaben beträgt noch {balance:.2f} EUR.",
        "account": "Ihr Konto",
        "premium_active": "Premium-Konto aktiv",
        "balance": "KI-Guthaben: {balance:.2f} EUR",
        "logout": "Abmelden",
        "drafts": "Ihre Entwürfe",
        "draft_name": "Name des Entwurfs",
        "save_draft": "Entwurf speichern",
        "no_drafts": "Sie haben noch keine Entwürfe gespeichert.",
        "load": "Laden",
        "delete": "Löschen",
        "main_title": "KI Website Builder",
        "main_subtitle": "Website erstellen, bearbeiten, prüfen und veröffentlichen.",
        "new_website": "Neue Website",
        "load_published": "Veröffentlichte Website laden",
        "template": "Vorlage und Grunddesign",
        "target_language": "Ziel-Sprache der Website",
        "choose_industry": "Branche wählen",
        "background_color": "Hintergrund-Grundton",
        "accent_color": "Akzentfarbe für Highlights und Buttons",
        "corner_style": "Ecken-Design",
        "rounded": "Abgerundet",
        "sharp": "Scharfkantig",
        "company_description": "Unternehmensbeschreibung und besondere Wünsche",
        "generate_template": "Website mit dieser Vorlage generieren",
        "live_preview": "Live-Vorschau",
        "edit_website": "Website bearbeiten",
        "publish": "Veröffentlichung",
    },
    "en": {
        "app_language": "App language", "auth_title": "AI Website Builder", "auth_subtitle": "Log in to design your website and publish it online.", "login": "Log in", "register": "Create account", "email": "Email address", "password": "Password", "confirm_password": "Confirm password", "invalid_login": "Invalid email address or password.", "password_mismatch": "Passwords do not match.", "account_created": "Account created. You can now log in.", "balance_empty": "Your AI balance has been used up.", "premium_info": "Premium unlocks unlimited generations for EUR 20.00 per month.", "activate_premium": "Activate premium test mode", "low_balance": "Your free balance is {balance:.2f} EUR.", "account": "My account", "premium_active": "Premium account active", "balance": "AI balance: {balance:.2f} EUR", "logout": "Log out", "drafts": "My drafts", "draft_name": "Draft name", "save_draft": "Save draft", "no_drafts": "No saved drafts yet.", "load": "Load", "delete": "Delete", "main_title": "AI Website Builder", "main_subtitle": "Create, edit, review, and publish websites.", "new_website": "New website", "load_published": "Load published website", "template": "Template and base design", "target_language": "Website target language", "choose_industry": "Choose industry", "background_color": "Background color", "accent_color": "Accent color for highlights and buttons", "corner_style": "Corner style", "rounded": "Rounded", "sharp": "Sharp", "company_description": "Business description and special requests", "generate_template": "Generate website with this template", "live_preview": "Live preview", "edit_website": "Edit website", "publish": "Publishing",
    },
    "ar": {
        "app_language": "لغة التطبيق", "auth_title": "منشئ المواقع بالذكاء الاصطناعي", "auth_subtitle": "سجّل الدخول لتصميم موقعك ونشره عبر الإنترنت.", "login": "تسجيل الدخول", "register": "إنشاء حساب", "email": "البريد الإلكتروني", "password": "كلمة المرور", "confirm_password": "تأكيد كلمة المرور", "invalid_login": "البريد الإلكتروني أو كلمة المرور غير صحيحة.", "password_mismatch": "كلمتا المرور غير متطابقتين.", "account_created": "تم إنشاء الحساب. يمكنك تسجيل الدخول الآن.", "balance_empty": "تم استهلاك رصيد الذكاء الاصطناعي.", "premium_info": "تفتح العضوية المميزة إنشاءات غير محدودة مقابل 20.00 يورو شهرياً.", "activate_premium": "تفعيل وضع التجربة المميزة", "low_balance": "رصيدك المجاني المتبقي هو {balance:.2f} يورو.", "account": "حسابي", "premium_active": "الحساب المميز نشط", "balance": "رصيد الذكاء الاصطناعي: {balance:.2f} يورو", "logout": "تسجيل الخروج", "drafts": "مسوداتي", "draft_name": "اسم المسودة", "save_draft": "حفظ المسودة", "no_drafts": "لا توجد مسودات محفوظة بعد.", "load": "تحميل", "delete": "حذف", "main_title": "منشئ المواقع بالذكاء الاصطناعي", "main_subtitle": "أنشئ المواقع وعدّلها وراجعها وانشرها.", "new_website": "موقع جديد", "load_published": "تحميل موقع منشور", "template": "القالب والتصميم الأساسي", "target_language": "لغة الموقع المستهدفة", "choose_industry": "اختر المجال", "background_color": "لون الخلفية", "accent_color": "لون التمييز للأزرار", "corner_style": "نمط الزوايا", "rounded": "مستدير", "sharp": "حاد", "company_description": "وصف الشركة والطلبات الخاصة", "generate_template": "إنشاء موقع بهذا القالب", "live_preview": "معاينة مباشرة", "edit_website": "تعديل الموقع", "publish": "النشر",
    },
    "ku": {
        "app_language": "زمانی ئەپ", "auth_title": "دروستکەری وێبگەی زیرەکی دەستکرد", "auth_subtitle": "بچۆ ژوورەوە بۆ دیزاینکردن و بڵاوکردنەوەی وێبگەکەت لەسەر ئینتەرنێت.", "login": "چوونەژوورەوە", "register": "دروستکردنی هەژمار", "email": "ئیمەیڵ", "password": "وشەی نهێنی", "confirm_password": "دڵنیابوونەوەی وشەی نهێنی", "invalid_login": "ئیمەیڵ یان وشەی نهێنی دروست نییە.", "password_mismatch": "وشە نهێنییەکان یەکسان نین.", "account_created": "هەژمارەکە دروستکرا. ئێستا دەتوانیت بچیتە ژوورەوە.", "balance_empty": "باڵانسی زیرەکی دەستکردت بەسەرچووە.", "premium_info": "پریمیۆم بەرامبەر 20.00 یۆرۆ لە مانگێکدا دروستکردنی بێ سنوور دەکاتەوە.", "activate_premium": "چالاککردنی دۆخی تاقیکردنەوەی پریمیۆم", "low_balance": "باڵانسی بەخۆڕاییت {balance:.2f} یۆرۆیە.", "account": "هەژمارەکەم", "premium_active": "هەژماری پریمیۆم چالاکە", "balance": "باڵانسی زیرەکی دەستکرد: {balance:.2f} یۆرۆ", "logout": "چوونەدەرەوە", "drafts": "ڕەشنووسەکانم", "draft_name": "ناوی ڕەشنووس", "save_draft": "پاشەکەوتکردنی ڕەشنووس", "no_drafts": "هێشتا هیچ ڕەشنووسێکی پاشەکەوتکراو نییە.", "load": "بارکردن", "delete": "سڕینەوە", "main_title": "دروستکەری وێبگەی زیرەکی دەستکرد", "main_subtitle": "وێبگە دروست بکە، دەستکاری بکە، پشکنین بکە و بڵاوی بکەرەوە.", "new_website": "وێبگەی نوێ", "load_published": "بارکردنی وێبگەی بڵاوکراوە", "template": "قاڵب و دیزاینی بنەڕەتی", "target_language": "زمانی ئامانجی وێبگە", "choose_industry": "بوار هەڵبژێرە", "background_color": "ڕەنگی پاشبنەما", "accent_color": "ڕەنگی دوگمەکان", "corner_style": "شێوازی گوشەکان", "rounded": "گەرد", "sharp": "تیژ", "company_description": "وەسفی کۆمپانیا و داواکاری تایبەتەکان", "generate_template": "وێبگە بەو قاڵبە دروست بکە", "live_preview": "پیشاندانی ڕاستەوخۆ", "edit_website": "دەستکاریکردنی وێبگە", "publish": "بڵاوکردنەوە",
    },
    "es": {
        "app_language": "Idioma de la aplicación", "auth_title": "Creador de sitios web con IA", "auth_subtitle": "Inicia sesión para diseñar y publicar tu sitio web en línea.", "login": "Iniciar sesión", "register": "Crear cuenta", "email": "Correo electrónico", "password": "Contraseña", "confirm_password": "Confirmar contraseña", "invalid_login": "El correo electrónico o la contraseña no son correctos.", "password_mismatch": "Las contraseñas no coinciden.", "account_created": "Cuenta creada. Ahora puedes iniciar sesión.", "balance_empty": "Tu saldo de IA se ha agotado.", "premium_info": "Premium desbloquea generaciones ilimitadas por 20,00 EUR al mes.", "activate_premium": "Activar modo de prueba Premium", "low_balance": "Tu saldo gratuito es de {balance:.2f} EUR.", "account": "Mi cuenta", "premium_active": "Cuenta Premium activa", "balance": "Saldo de IA: {balance:.2f} EUR", "logout": "Cerrar sesión", "drafts": "Mis borradores", "draft_name": "Nombre del borrador", "save_draft": "Guardar borrador", "no_drafts": "Aún no hay borradores guardados.", "load": "Cargar", "delete": "Eliminar", "main_title": "Creador de sitios web con IA", "main_subtitle": "Crea, edita, revisa y publica sitios web.", "new_website": "Nuevo sitio web", "load_published": "Cargar sitio web publicado", "template": "Plantilla y diseño base", "target_language": "Idioma de destino del sitio web", "choose_industry": "Elegir sector", "background_color": "Color de fondo", "accent_color": "Color de acento", "corner_style": "Estilo de esquinas", "rounded": "Redondeado", "sharp": "Recto", "company_description": "Descripción de la empresa y solicitudes especiales", "generate_template": "Generar sitio web con esta plantilla", "live_preview": "Vista previa en directo", "edit_website": "Editar sitio web", "publish": "Publicar",
    },
    "it": {
        "app_language": "Lingua dell'app", "auth_title": "Creatore di siti web con IA", "auth_subtitle": "Accedi per progettare e pubblicare il tuo sito web online.", "login": "Accedi", "register": "Crea account", "email": "Indirizzo email", "password": "Password", "confirm_password": "Conferma password", "invalid_login": "Email o password non corrette.", "password_mismatch": "Le password non corrispondono.", "account_created": "Account creato. Ora puoi accedere.", "balance_empty": "Il tuo credito IA è esaurito.", "premium_info": "Premium sblocca generazioni illimitate per 20,00 EUR al mese.", "activate_premium": "Attiva modalità di prova Premium", "low_balance": "Il tuo credito gratuito è di {balance:.2f} EUR.", "account": "Il mio account", "premium_active": "Account Premium attivo", "balance": "Credito IA: {balance:.2f} EUR", "logout": "Esci", "drafts": "Le mie bozze", "draft_name": "Nome della bozza", "save_draft": "Salva bozza", "no_drafts": "Nessuna bozza salvata.", "load": "Carica", "delete": "Elimina", "main_title": "Creatore di siti web con IA", "main_subtitle": "Crea, modifica, controlla e pubblica siti web.", "new_website": "Nuovo sito web", "load_published": "Carica sito web pubblicato", "template": "Modello e design di base", "target_language": "Lingua di destinazione del sito", "choose_industry": "Scegli settore", "background_color": "Colore di sfondo", "accent_color": "Colore di accento", "corner_style": "Stile degli angoli", "rounded": "Arrotondato", "sharp": "Netto", "company_description": "Descrizione dell'azienda e richieste speciali", "generate_template": "Genera sito con questo modello", "live_preview": "Anteprima dal vivo", "edit_website": "Modifica sito web", "publish": "Pubblicazione",
    },
    "hi": {
        "app_language": "ऐप की भाषा", "auth_title": "एआई वेबसाइट बिल्डर", "auth_subtitle": "अपनी वेबसाइट डिज़ाइन करने और ऑनलाइन प्रकाशित करने के लिए लॉग इन करें।", "login": "लॉग इन", "register": "खाता बनाएं", "email": "ईमेल पता", "password": "पासवर्ड", "confirm_password": "पासवर्ड की पुष्टि करें", "invalid_login": "ईमेल पता या पासवर्ड सही नहीं है।", "password_mismatch": "पासवर्ड मेल नहीं खाते हैं।", "account_created": "खाता बन गया। अब आप लॉग इन कर सकते हैं।", "balance_empty": "आपका एआई बैलेंस समाप्त हो गया है।", "premium_info": "प्रीमियम प्रति माह 20.00 EUR में असीमित जनरेशन खोलता है।", "activate_premium": "प्रीमियम परीक्षण मोड सक्रिय करें", "low_balance": "आपका निःशुल्क बैलेंस {balance:.2f} EUR है।", "account": "मेरा खाता", "premium_active": "प्रीमियम खाता सक्रिय है", "balance": "एआई बैलेंस: {balance:.2f} EUR", "logout": "लॉग आउट", "drafts": "मेरे ड्राफ्ट", "draft_name": "ड्राफ्ट का नाम", "save_draft": "ड्राफ्ट सहेजें", "no_drafts": "अभी तक कोई ड्राफ्ट सहेजा नहीं गया है।", "load": "लोड करें", "delete": "हटाएं", "main_title": "एआई वेबसाइट बिल्डर", "main_subtitle": "वेबसाइट बनाएं, संपादित करें, जांचें और प्रकाशित करें।", "new_website": "नई वेबसाइट", "load_published": "प्रकाशित वेबसाइट लोड करें", "template": "टेम्पलेट और आधार डिज़ाइन", "target_language": "वेबसाइट की लक्ष्य भाषा", "choose_industry": "उद्योग चुनें", "background_color": "पृष्ठभूमि रंग", "accent_color": "एक्सेंट रंग", "corner_style": "कोने की शैली", "rounded": "गोल", "sharp": "नुकीला", "company_description": "कंपनी विवरण और विशेष अनुरोध", "generate_template": "इस टेम्पलेट से वेबसाइट बनाएं", "live_preview": "लाइव पूर्वावलोकन", "edit_website": "वेबसाइट संपादित करें", "publish": "प्रकाशित करें",
    },
}
LANGUAGE_SWITCHER_REQUIREMENTS = """
MEHRSPRACHIGKEIT UND RTL:
- Baue rechts in die Navigation ein elegantes dunkles <select id="language-switcher"> mit
    den Optionen DE, EN, AR und KU. Es muss im Dark-Mode gut lesbar sein und ohne Seiten-Reload arbeiten.
- Binde direkt vor </body> ein JavaScript ein. Definiere darin ein JSON-Objekt namens translations
    mit den Sprachcodes de, en, ar und ku. Jede Sprache enthaelt Texte fuer nav_home, nav_about,
    nav_services, nav_contact, hero_title, hero_text, about_title, about_text, services_title,
    services_text, contact_title und contact_text.
- Verwende diese biografischen Inhalte, fehlerfrei uebersetzt: Mayada ist AI Engineer, hat einen
    Bachelor an der Universitaet Aleppo, einen Master in Hannover und die AI-Engineer-Weiterbildung
    bei alfatraining abgeschlossen. Kontakt-E-Mail: mayada2678@gmail.com.
- Kennzeichne alle wechselbaren Navigation-, Hero-, Ueber-mich-, Services- und Kontakttexte mit
    passenden data-i18n-Attributen. Beim Aendern des Dropdowns ersetzt JavaScript deren textContent
    aus translations ohne Neuladen.
- Lege die vier Uebersetzungen vollstaendig im JavaScript ab:
    de: "Mayada - AI Engineer", "Bachelor an der Universitaet Aleppo, Master in Hannover und
    AI-Engineer-Weiterbildung bei alfatraining.", "Ueber mich", "Ich entwickle intelligente,
    nutzerfreundliche digitale Loesungen.", "Leistungen", "KI-Loesungen, Webentwicklung und
    technische Beratung.", "Kontakt", "Schreiben Sie an mayada2678@gmail.com.";
    en: "Mayada - AI Engineer", "Bachelor's degree from the University of Aleppo, Master's degree
    in Hanover, and AI Engineer training at alfatraining.", "About me", "I build intelligent,
    user-friendly digital solutions.", "Services", "AI solutions, web development, and technical
    consulting.", "Contact", "Email mayada2678@gmail.com.";
    ar: "مايادا - مهندسة ذكاء اصطناعي", "حاصلة على البكالوريوس من جامعة حلب والماجستير من هانوفر،
    وأكملت تدريب مهندسة الذكاء الاصطناعي في alfatraining.", "من أنا", "أطوّر حلولاً رقمية ذكية
    وسهلة الاستخدام.", "الخدمات", "حلول الذكاء الاصطناعي وتطوير الويب والاستشارات التقنية.",
    "تواصل", "راسليني على mayada2678@gmail.com.";
    ku: "مایادا - ئەندازیاری زیرەکی دەستکرد", "بڕوانامەی بەکالۆریۆس لە زانکۆی حەلەب و ماستەر لە
    هانوڤەر، و ڕاهێنانی ئەندازیاری زیرەکی دەستکرد لە alfatraining تەواو کردووە.", "دەربارەی من",
    "چارەسەری دیجیتاڵی زیرەک و بەکارهێنەر-دۆست پەرەپێدەدەم.", "خزمەتگوزارییەکان", "چارەسەرییەکانی
    زیرەکی دەستکرد، پەرەپێدانی وێب و ڕاوێژکاریی تەکنیکی.", "پەیوەندی", "بۆ پەیوەندی بنووسە بۆ
    mayada2678@gmail.com.".
- Die Funktion applyLanguage(code) muss document.documentElement.lang auf den Code und dir fuer
    ar und ku auf "rtl", sonst auf "ltr" setzen. Bei RTL muessen text-left/text-right-Klassen
    getauscht sowie Flex- und Navigationsrichtungen gespiegelt werden; bei de/en ist alles wieder
    auf LTR und linksbuendig zurueckzusetzen. Verwende classList und speichere den LTR-Ausgangszustand,
    damit wiederholtes Umschalten keine Klassen verliert.
"""


def initialize_database() -> None:
    """Erstellt die lokale Datenbank fuer Nutzer und gespeicherte Websites."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                token_balance REAL DEFAULT 5.00,
                is_subscribed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        if "created_at" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
            connection.execute(
                "UPDATE users SET created_at = ? WHERE created_at IS NULL",
                (datetime.now(timezone.utc).isoformat(),),
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_name TEXT NOT NULL,
                html_content TEXT NOT NULL,
                domain TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_type TEXT NOT NULL,
                app_area TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                reproduction_steps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )


def hash_password(password: str) -> str:
    """Erzeugt einen salt-basierten Passwort-Hash ohne Klartextspeicherung."""
    salt = secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def password_matches(password: str, stored_value: str) -> bool:
    """Prueft ein Passwort gegen den gespeicherten scrypt-Hash."""
    try:
        salt_hex, hash_hex = stored_value.split(":", maxsplit=1)
        expected_hash = bytes.fromhex(hash_hex)
        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=2**14,
            r=8,
            p=1,
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_hash, expected_hash)


def register_user(email: str, password: str) -> None:
    """Legt ein lokales Nutzerkonto an."""
    normalized_email = email.strip().lower()

    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Bitte gib eine gueltige E-Mail-Adresse ein.")
    if len(password) < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen haben.")

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (normalized_email, hash_password(password), datetime.now(timezone.utc).isoformat()),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("Zu dieser E-Mail-Adresse existiert bereits ein Konto.") from error


def authenticate_user(email: str, password: str) -> tuple[int, str] | None:
    """Gibt die Nutzer-ID bei gueltiger Anmeldung zurueck."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        user = connection.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    if user and password_matches(password, user[2]):
        return user[0], user[1]
    return None


def save_website(user_id: int, site_name: str, html: str, domain: str) -> None:
    """Speichert einen Entwurf in der Historie des angemeldeten Nutzers."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO websites (user_id, site_name, html_content, domain)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, site_name.strip() or "Meine Website", html, domain),
        )


def get_websites(user_id: int) -> list[tuple[int, str, str]]:
    """Laedt die gespeicherten Websites eines Nutzers, zuletzt gespeicherte zuerst."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        return connection.execute(
            """
            SELECT id, site_name, COALESCE(domain, '')
            FROM websites
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()


def load_website(user_id: int, website_id: int) -> tuple[str, str, str] | None:
    """Laedt eine Website nur, wenn sie dem angemeldeten Nutzer gehoert."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        return connection.execute(
            """
            SELECT site_name, html_content, COALESCE(domain, '')
            FROM websites
            WHERE id = ? AND user_id = ?
            """,
            (website_id, user_id),
        ).fetchone()


def delete_saved_website(user_id: int, website_id: int) -> None:
    """Loescht eine Website nur aus der eigenen Historie."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "DELETE FROM websites WHERE id = ? AND user_id = ?",
            (website_id, user_id),
        )


def save_support_request(
    user_id: int,
    request_type: str,
    app_area: str,
    subject: str,
    description: str,
    reproduction_steps: str,
) -> None:
    """Speichert eine Kundenanfrage samt nachvollziehbarer Fehlerbeschreibung."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO support_requests (
                user_id, request_type, app_area, subject, description,
                reproduction_steps, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request_type,
                app_area,
                subject.strip(),
                description.strip(),
                reproduction_steps.strip(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_support_requests(user_id: int | None = None) -> list[tuple]:
    """Lädt eigene Anfragen oder für den App-Inhaber die gesamte Support-Inbox."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        if user_id is None:
            return connection.execute(
                """
                SELECT support_requests.id, users.email, support_requests.request_type,
                       support_requests.app_area, support_requests.subject,
                       support_requests.description, support_requests.reproduction_steps,
                       support_requests.created_at
                FROM support_requests
                JOIN users ON users.id = support_requests.user_id
                ORDER BY support_requests.id DESC
                """
            ).fetchall()
        return connection.execute(
            """
            SELECT id, request_type, app_area, subject, description,
                   reproduction_steps, created_at
            FROM support_requests
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()


TRIAL_DURATION = timedelta(hours=24)


def get_user_status(user_id: int) -> dict[str, float | bool | int]:
    """Liest Premium- und 24-Stunden-Teststatus des angemeldeten Nutzers."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        user = connection.execute(
            "SELECT token_balance, is_subscribed, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if user is None:
        return {"balance": 0.0, "subscribed": False, "trial_active": False, "trial_remaining_hours": 0}
    try:
        created_at = datetime.fromisoformat(user[2]).astimezone(timezone.utc)
    except (TypeError, ValueError):
        created_at = datetime.now(timezone.utc) - TRIAL_DURATION
    remaining = max(timedelta(), created_at + TRIAL_DURATION - datetime.now(timezone.utc))
    return {
        "balance": float(user[0]),
        "subscribed": bool(user[1]),
        "trial_active": remaining > timedelta(),
        "trial_remaining_hours": max(0, int(remaining.total_seconds() // 3600) + (1 if remaining else 0)),
    }


def deduct_tokens(user_id: int, amount: float = 0.05) -> bool:
    """Erlaubt Generierungen waehrend der 24-Stunden-Testphase oder mit Premium."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        user = connection.execute(
            "SELECT is_subscribed, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if user is None:
            return False
        if user[0]:
            return True
        try:
            created_at = datetime.fromisoformat(user[1]).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return False
        return datetime.now(timezone.utc) < created_at + TRIAL_DURATION


def refund_tokens(user_id: int, amount: float = 0.05) -> None:
    """Kompatibilitaetsfunktion: Die kostenlose Testphase verbraucht kein Guthaben."""
    return None


def activate_premium_demo(user_id: int) -> None:
    """Aktiviert Premium fuer lokale Tests, bis eine Zahlungsintegration vorhanden ist."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE users SET is_subscribed = 1 WHERE id = ?",
            (user_id,),
        )


def create_stripe_checkout_session(
    user_id: int,
    user_email: str,
    domain: str = "",
    vercel_project_id: str = "",
) -> str:
    """Erstellt eine Stripe-Checkout-Sitzung für die Veröffentlichungsfreigabe."""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID or not STRIPE_SUCCESS_URL:
        raise ValueError("Stripe ist noch nicht eingerichtet.")

    separator = "&" if "?" in STRIPE_SUCCESS_URL else "?"
    success_url = (
        f"{STRIPE_SUCCESS_URL}{separator}checkout_session_id={{CHECKOUT_SESSION_ID}}"
        "&publish=1"
    )
    checkout_data = {
        "mode": "subscription",
        "customer_email": user_email,
        "client_reference_id": str(user_id),
        "line_items[0][price]": STRIPE_PRICE_ID,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": STRIPE_SUCCESS_URL,
    }
    if domain and vercel_project_id:
        checkout_data.update(
            {
                "metadata[domain]": domain,
                "metadata[vercel_project_id]": vercel_project_id,
                "metadata[provisioning_status]": "pending",
                "subscription_data[metadata][domain]": domain,
                "subscription_data[metadata][vercel_project_id]": vercel_project_id,
            }
        )
    response = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        auth=(STRIPE_SECRET_KEY, ""),
        data=checkout_data,
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError("Stripe konnte die Zahlung nicht vorbereiten.")
    checkout_url = response.json().get("url")
    if not checkout_url:
        raise ValueError("Stripe hat keine Zahlungsadresse geliefert.")
    return checkout_url


def confirm_stripe_checkout(user_id: int) -> bool:
    """Schaltet Veröffentlichung nur nach bestätigter Stripe-Zahlung frei."""
    session_id = st.query_params.get("checkout_session_id")
    if not session_id or not STRIPE_SECRET_KEY:
        return False
    response = requests.get(
        f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
        auth=(STRIPE_SECRET_KEY, ""),
        timeout=30,
    )
    if response.status_code != 200:
        return False
    checkout = response.json()
    if (
        checkout.get("payment_status") != "paid"
        or checkout.get("client_reference_id") != str(user_id)
    ):
        return False
    activate_premium_demo(user_id)
    st.query_params.clear()
    return True


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


initialize_database()

try:
    OPENAI_API_KEY = st.secrets["openai_api_key"]
    VERCEL_TOKEN = st.secrets["vercel_token"]
except KeyError:
    st.error(
        "API-Schlüssel fehlen. Hinterlege `openai_api_key` und "
        "`vercel_token` in `.streamlit/secrets.toml`."
    )
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)
os.environ["OPENAI_API_KEY"] = str(OPENAI_API_KEY)
STRIPE_PAYMENT_LINK = "https://buy.stripe.com/3cIfZh5qseusaOpdYP5Rm02"
STRIPE_SECRET_KEY = str(st.secrets.get("stripe_secret_key", "")).strip()
STRIPE_PRICE_ID = str(st.secrets.get("stripe_price_id", "")).strip()
STRIPE_SUCCESS_URL = str(st.secrets.get("stripe_success_url", "")).strip().rstrip("?")
INWX_USERNAME = str(st.secrets.get("inwx_username", "")).strip()
INWX_PASSWORD = str(st.secrets.get("inwx_password", "")).strip()
INWX_ENVIRONMENT = str(st.secrets.get("inwx_environment", "ote")).strip().lower()
for environment_key, environment_value in {
    "INWX_USERNAME": INWX_USERNAME,
    "INWX_PASSWORD": INWX_PASSWORD,
    "INWX_ENVIRONMENT": INWX_ENVIRONMENT,
}.items():
    if environment_value:
        os.environ[environment_key] = environment_value
HF_API_KEY = str(st.secrets.get("HF_API_KEY", "")).strip()
HF_TEXT_MODEL_URL = (
    "https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-7B-Instruct"
)
SUPPORT_ADMIN_EMAIL = str(st.secrets.get("support_admin_email", "")).strip().lower()
PRIVACY_CONTACT_EMAIL = str(st.secrets.get("privacy_contact_email", "")).strip()
PRIVACY_CONTROLLER_NAME = str(
    st.secrets.get("privacy_controller_name", "App-Betreiber")
).strip()
PRIVACY_CONTROLLER_ADDRESS = str(
    st.secrets.get("privacy_controller_address", "")
).strip()

DEFAULT_STATE = {
    "user_id": None,
    "user_email": "",
    "target_language": "Deutsch",
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "assets": {},
    "site_pages": {},
    "template_preview_page": "start",
    "live_url": "",
    "deployment_url": "",
    "deployment_id": "",
    "vercel_project_id": "",
    "project_name": "ai-website-builder",
    "stripe_checkout_url": "",
    "publish_after_checkout": False,
    "delete_confirmation": False,
    "show_botpress_chatbot": True,
    "client_chatbot_hours": "",
    "client_chatbot_contact": "",
    "client_chatbot_services": "",
    "client_chatbot_emergency": "",
    "customer_chatbot_color": "#2563EB",
    "customer_chatbot_shape": "Rund (Kreis)",
    "customer_chatbot_figure": "Freundlicher Roboter",
    "customer_chatbot_name": "Kundenservice-Assistent",
    "customer_chatbot_position": "Unten rechts",
    "customer_chatbot_fixed": True,
    "chat_messages": [
        {
            "role": "assistant",
            "content": (
                "Herzlich willkommen. Ich unterstütze Sie bei der Erstellung, "
                "Vorschau und Veröffentlichung Ihrer Website."
            ),
        }
    ],
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.session_state.setdefault("app_language", "de")
APP_LANGUAGE_NAMES_BY_CODE = {
    language_code: language_name
    for language_name, language_code in APP_LANGUAGES.items()
}
TARGET_LANGUAGE_BY_APP_CODE = {
    "de": "Deutsch",
    "en": "English",
    "ar": "Arabisch (العربية)",
    "ku": "Kurdisch (Kurdî / كوردی)",
    "es": "Spanisch (Español)",
    "it": "Italienisch (Italiano)",
    "hi": "Hindi (हिन्दी)",
}
st.session_state.setdefault(
    "app_language_name",
    APP_LANGUAGE_NAMES_BY_CODE[st.session_state.app_language],
)


def t(key: str, **values: object) -> str:
    """Gibt den sichtbaren App-Text in der ausgewaehlten Sprache zurueck."""
    language = str(st.session_state.app_language)
    text = TRANSLATIONS.get(language, TRANSLATIONS["de"]).get(key, key)
    return text.format(**values)


AUTHENTICATION_COPY = {
    "de": {
        "workflow": "KI-gestützter Website-Workflow",
        "plan": "**Planen** Sie Struktur, Inhalte und Markenauftritt.",
        "review": "**Prüfen** Sie Ihr Ergebnis in einer Live-Vorschau.",
        "publish": "**Veröffentlichen** Sie fertige Entwürfe direkt auf Vercel.",
        "workspace": "Ihr Arbeitsbereich",
        "workspace_hint": "Melden Sie sich an oder erstellen Sie ein neues Konto.",
        "privacy": "Ihre Entwürfe, Einstellungen und Bearbeitungen bleiben Ihrem Konto zugeordnet.",
    },
    "en": {
        "workflow": "AI-powered website workflow",
        "plan": "**Plan** your structure, content, and brand presence.",
        "review": "**Review** your result in a live preview.",
        "publish": "**Publish** finished drafts directly to Vercel.",
        "workspace": "Your workspace",
        "workspace_hint": "Log in or create a new account.",
        "privacy": "Your drafts, settings, and edits remain associated with your account.",
    },
    "ar": {
        "workflow": "مسار عمل لإنشاء المواقع بالذكاء الاصطناعي",
        "plan": "**خطّط** لبنية موقعك ومحتواه وهوية علامتك التجارية.",
        "review": "**راجع** النتيجة من خلال المعاينة المباشرة.",
        "publish": "**انشر** المسودات المكتملة مباشرة على Vercel.",
        "workspace": "مساحة عملك",
        "workspace_hint": "سجّل الدخول أو أنشئ حساباً جديداً.",
        "privacy": "تبقى مسوداتك وإعداداتك وتعديلاتك مرتبطة بحسابك.",
    },
    "ku": {
        "workflow": "ڕێڕەوی دروستکردنی وێبگە بە زیرەکی دەستکرد",
        "plan": "**پلان دابنێ** بۆ پێکهاتە، ناوەڕۆک و ناسنامەی براندەکەت.",
        "review": "**ئەنجامەکە پشکنە** لە پێشبینینی ڕاستەوخۆدا.",
        "publish": "**ڕەشنووسە تەواوەکان بڵاو بکەرەوە** ڕاستەوخۆ لە Vercel.",
        "workspace": "شوێنی کارەکەت",
        "workspace_hint": "بچۆ ژوورەوە یان هەژمارێکی نوێ دروست بکە.",
        "privacy": "ڕەشنووس و ڕێکخستن و دەستکارییەکانت بە هەژمارەکەتەوە بەستراو دەمێننەوە.",
    },
}

WORKSPACE_COPY = {
    "de": {"trial_active": "Kostenlose Testphase aktiv: noch etwa {hours} Stunden.", "trial_sidebar": "Kostenlose Testphase: noch etwa {hours} Stunden", "trial_expired": "Kostenlose Testphase abgelaufen", "premium_hint": "Premium kann im Bereich Veröffentlichung sicher abgeschlossen werden.", "service": "Kundenservice", "privacy": "Datenschutz", "project_title": "1. Website-Projekt festlegen", "project_hint": "Wählen Sie Branche, Startmodus und Seitenstruktur. Alle Inhalte bleiben anschließend bearbeitbar.", "start": "Wie möchten Sie starten?", "professional": "Professionelle Vorlage", "free": "Freier Entwurf", "existing": "Bestehenden Entwurf anpassen", "structure": "Seitenstruktur", "single": "Eine übersichtliche Seite", "multi": "Mehrseitige Website", "client_title": "2. Kundendaten und Kunden-Chatbot", "client_hint": "Diese Angaben werden direkt in Vorschau, Kontaktbereich und Chatbot übernommen.", "draft_saved": "Ihr Entwurf wurde gespeichert."},
    "en": {"trial_active": "Free trial active: about {hours} hours remaining.", "trial_sidebar": "Free trial: about {hours} hours remaining", "trial_expired": "Free trial expired", "premium_hint": "Premium can be purchased securely in Publishing.", "service": "Customer service", "privacy": "Privacy", "project_title": "1. Define website project", "project_hint": "Choose the industry, starting mode, and page structure. All content remains editable.", "start": "How would you like to start?", "professional": "Professional template", "free": "Blank draft", "existing": "Edit existing draft", "structure": "Page structure", "single": "Single-page website", "multi": "Multi-page website", "client_title": "2. Customer details and customer chatbot", "client_hint": "These details are used directly in the preview, contact section, and chatbot.", "draft_saved": "Your draft has been saved."},
    "ar": {"trial_active": "الفترة التجريبية المجانية نشطة: متبقٍ نحو {hours} ساعة.", "trial_sidebar": "الفترة التجريبية المجانية: متبقٍ نحو {hours} ساعة", "trial_expired": "انتهت الفترة التجريبية المجانية", "premium_hint": "يمكن الاشتراك في Premium بأمان من قسم النشر.", "service": "خدمة العملاء", "privacy": "الخصوصية", "project_title": "1. تحديد مشروع الموقع", "project_hint": "اختر المجال وطريقة البدء وبنية الصفحات. ويمكن تعديل جميع المحتويات لاحقاً.", "start": "كيف تريد أن تبدأ؟", "professional": "قالب احترافي", "free": "مسودة حرة", "existing": "تعديل مسودة موجودة", "structure": "بنية الصفحات", "single": "صفحة واحدة واضحة", "multi": "موقع متعدد الصفحات", "client_title": "2. بيانات العميل وروبوت المحادثة", "client_hint": "تُستخدم هذه البيانات مباشرة في المعاينة وقسم الاتصال وروبوت المحادثة.", "draft_saved": "تم حفظ المسودة."},
    "ku": {"trial_active": "ماوەی تاقیکردنەوەی بەخۆڕایی چالاکە: نزیکەی {hours} کاتژمێر ماوە.", "trial_sidebar": "تاقیکردنەوەی بەخۆڕایی: نزیکەی {hours} کاتژمێر ماوە", "trial_expired": "ماوەی تاقیکردنەوەی بەخۆڕایی کۆتایی هات", "premium_hint": "دەتوانیت Premium بە پارێزراوی لە بەشی بڵاوکردنەوە بکڕیت.", "service": "خزمەتگوزاری کڕیار", "privacy": "پاراستنی نهێنی", "project_title": "1. دیاریکردنی پڕۆژەی وێبگە", "project_hint": "بوار، شێوازی دەستپێکردن و پێکهاتەی پەڕەکان هەڵبژێرە. هەموو ناوەڕۆکێک دواتر دەستکاری دەکرێت.", "start": "چۆن دەتەوێت دەست پێ بکەیت؟", "professional": "قاڵبی پیشەیی", "free": "ڕەشنووسی ئازاد", "existing": "دەستکاریکردنی ڕەشنووسی هەبوو", "structure": "پێکهاتەی پەڕەکان", "single": "یەک پەڕەی ڕوون", "multi": "وێبگەی چەند پەڕەیی", "client_title": "2. زانیاری کڕیار و چاتبۆت", "client_hint": "ئەم زانیارییانە ڕاستەوخۆ لە پێشبینین و بەشی پەیوەندی و چاتبۆت بەکاردێن.", "draft_saved": "ڕەشنووسەکە پاشەکەوت کرا."},
}


def workspace_copy() -> dict[str, str]:
    """Liefert Texte des Arbeitsbereichs in der gewählten Sprache."""
    return WORKSPACE_COPY.get(str(st.session_state.app_language), WORKSPACE_COPY["en"])


PUBLISH_COPY = {
    "de": {"title": "Veröffentlichung und Liveschaltung", "need_site": "Erstellen oder laden Sie zuerst eine Website, bevor Sie sie veröffentlichen.", "load_title": "Öffentliche Website laden", "load_hint": "Die Original-Website wird geladen, ohne HTML oder Design vor der Bearbeitung zu ändern.", "live_link": "Öffentlicher Live-Link", "load_button": "Original-Website laden", "link_required": "Bitte geben Sie einen Live-Link ein.", "loading": "Website wird geladen ...", "loaded": "Original-Website wurde unverändert geladen.", "failed": "Laden fehlgeschlagen"},
    "en": {"title": "Publishing and going live", "need_site": "Create or load a website before publishing it.", "load_title": "Load public website", "load_hint": "The original website is loaded without changing its HTML or design before editing.", "live_link": "Public live link", "load_button": "Load original website", "link_required": "Please enter a live link.", "loading": "Loading website ...", "loaded": "The original website was loaded unchanged.", "failed": "Loading failed"},
    "ar": {"title": "النشر وإطلاق الموقع", "need_site": "أنشئ موقعاً أو حمّله أولاً قبل نشره.", "load_title": "تحميل موقع عام", "load_hint": "يتم تحميل الموقع الأصلي من دون تغيير HTML أو التصميم قبل التعديل.", "live_link": "الرابط العام للموقع", "load_button": "تحميل الموقع الأصلي", "link_required": "يرجى إدخال رابط عام للموقع.", "loading": "جارٍ تحميل الموقع...", "loaded": "تم تحميل الموقع الأصلي من دون تغيير.", "failed": "فشل التحميل"},
    "ku": {"title": "بڵاوکردنەوە و خستنە سەر هێڵ", "need_site": "پێش بڵاوکردنەوە سەرەتا وێبگەیەک دروست بکە یان باری بکە.", "load_title": "بارکردنی وێبگەی گشتی", "load_hint": "وێبگە ڕەسەنەکە بەبێ گۆڕینی HTML یان دیزاین پێش دەستکاریکردن بار دەکرێت.", "live_link": "بەستەری گشتی وێبگە", "load_button": "بارکردنی وێبگە ڕەسەنەکە", "link_required": "تکایە بەستەری گشتی وێبگە بنووسە.", "loading": "وێبگەکە بار دەکرێت...", "loaded": "وێبگە ڕەسەنەکە بەبێ گۆڕانکاری بار کرا.", "failed": "بارکردن سەرکەوتوو نەبوو"},
}


def publish_copy() -> dict[str, str]:
    """Liefert Import- und Veröffentlichungstexte in der App-Sprache."""
    return PUBLISH_COPY.get(str(st.session_state.app_language), PUBLISH_COPY["en"])

HELP_CHAT_TEXTS = {
    "de": {
        "title": "Hilfe-Chat", "input": "Schreiben Sie Ihre Frage",
        "greeting": "Herzlich willkommen. Ich unterstütze Sie bei der Erstellung, Vorschau und Veröffentlichung Ihrer Website.",
        "publish": "Wählen Sie nach dem Erstellen Ihrer Website den Bereich „Veröffentlichung und Liveschaltung“. Dort können Sie einen Vercel-Projektnamen festlegen und die Website veröffentlichen.",
        "preview": "In der Live-Vorschau können Sie Ihre Website prüfen und den HTML-Code direkt anpassen.",
        "image": "Sie können beim Erstellen ein Logo oder Bild hochladen. Weitere Bilder lassen sich später im Bereich „Bilder“ austauschen.",
        "default": "Beschreiben Sie Ihr Unternehmen, wählen Sie Branche und Design und erstellen Sie anschließend Ihren Website-Entwurf. Wobei darf ich Ihnen helfen?",
    },
    "en": {
        "title": "Help chat", "input": "Write your question",
        "greeting": "Welcome. I can help you create, preview, and publish your website.",
        "publish": "After creating your website, open Publishing and go live. There you can choose a Vercel project name and publish the website.",
        "preview": "Use the live preview to review your website and adjust its HTML directly.",
        "image": "You can upload a logo or image while creating the website. Replace additional images later in the Images section.",
        "default": "Describe your business, choose an industry and design, then create your website draft. How can I help?",
    },
    "es": {
        "title": "Chat de ayuda", "input": "Escribe tu pregunta",
        "greeting": "Bienvenido. Te ayudo a crear, revisar y publicar tu sitio web.",
        "publish": "Después de crear tu sitio, abre la sección de publicación. Allí puedes elegir un nombre de proyecto de Vercel y publicar el sitio.",
        "preview": "Usa la vista previa en vivo para revisar tu sitio y ajustar el HTML directamente.",
        "image": "Puedes subir un logo o imagen al crear el sitio. Cambia más imágenes después en la sección Imágenes.",
        "default": "Describe tu empresa, elige un sector y diseño y crea tu borrador. ¿Cómo puedo ayudarte?",
    },
    "it": {
        "title": "Chat di assistenza", "input": "Scrivi la tua domanda",
        "greeting": "Benvenuto. Ti aiuto a creare, visualizzare e pubblicare il tuo sito web.",
        "publish": "Dopo aver creato il sito, apri la sezione Pubblicazione. Qui puoi scegliere il nome di un progetto Vercel e pubblicare il sito.",
        "preview": "Usa l'anteprima dal vivo per controllare il sito e modificare direttamente l'HTML.",
        "image": "Puoi caricare un logo o un'immagine durante la creazione. Sostituisci altre immagini nella sezione Immagini.",
        "default": "Descrivi la tua azienda, scegli settore e design e crea la bozza del sito. Come posso aiutarti?",
    },
    "ar": {
        "title": "دردشة المساعدة", "input": "اكتب سؤالك",
        "greeting": "مرحباً. أساعدك في إنشاء موقعك ومعاينته ونشره.",
        "publish": "بعد إنشاء موقعك، افتح قسم النشر. هناك يمكنك اختيار اسم مشروع Vercel ونشر الموقع.",
        "preview": "استخدم المعاينة المباشرة لمراجعة موقعك وتعديل HTML مباشرة.",
        "image": "يمكنك رفع شعار أو صورة أثناء إنشاء الموقع، وتغيير الصور الأخرى لاحقاً في قسم الصور.",
        "default": "صف شركتك واختر المجال والتصميم ثم أنشئ مسودة موقعك. كيف يمكنني مساعدتك؟",
    },
    "ku": {
        "title": "چاتی یارمەتی", "input": "پرسیارەکەت بنووسە",
        "greeting": "بەخێربێیت. یارمەتیت دەدەم وێبگەکەت دروست بکەیت، پشکنینی بکەیت و بڵاوی بکەیتەوە.",
        "publish": "دوای دروستکردنی وێبگەکەت، بەشی بڵاوکردنەوە بکەرەوە. لەوێ دەتوانیت ناوی پڕۆژەی Vercel هەڵبژێریت و بڵاوی بکەیتەوە.",
        "preview": "پیشاندانی ڕاستەوخۆ بەکاربهێنە بۆ پشکنینی وێبگەکەت و دەستکاریکردنی HTML.",
        "image": "دەتوانیت لە کاتی دروستکردندا لۆگۆ یان وێنە باربکەیت و وێنەکانی تر لە بەشی وێنەکان بگۆڕیت.",
        "default": "کۆمپانیاکەت باس بکە، بوار و دیزاین هەڵبژێرە و ڕەشنووسی وێبگەکەت دروست بکە. چۆن یارمەتیت بدەم؟",
    },
    "hi": {
        "title": "सहायता चैट", "input": "अपना प्रश्न लिखें",
        "greeting": "स्वागत है। मैं आपकी वेबसाइट बनाने, देखने और प्रकाशित करने में सहायता कर सकता हूं।",
        "publish": "वेबसाइट बनाने के बाद प्रकाशन अनुभाग खोलें। वहां आप Vercel प्रोजेक्ट नाम चुनकर वेबसाइट प्रकाशित कर सकते हैं।",
        "preview": "अपनी वेबसाइट जांचने और HTML बदलने के लिए लाइव प्रीव्यू का उपयोग करें।",
        "image": "वेबसाइट बनाते समय आप लोगो या चित्र अपलोड कर सकते हैं। अतिरिक्त चित्र बाद में Images अनुभाग में बदलें।",
        "default": "अपने व्यवसाय का वर्णन करें, उद्योग और डिज़ाइन चुनें, फिर वेबसाइट ड्राफ्ट बनाएं। मैं कैसे मदद कर सकता हूं?",
    },
}


def get_help_chat_texts() -> dict[str, str]:
    """Liefert Texte für den Hilfe-Chat in der global gewählten Sprache."""
    return HELP_CHAT_TEXTS.get(str(st.session_state.app_language), HELP_CHAT_TEXTS["de"])


HELP_CHAT_ACTIONS = {
    "de": {"plan": "Website planen", "next": "Nächsten Schritt prüfen", "improve": "Prompt verbessern", "preview": "Vorschau prüfen", "publish": "Veröffentlichen", "clear": "Verlauf leeren", "empty": "Noch kein Entwurf geladen", "ready": "Entwurf ist zur Bearbeitung bereit"},
    "en": {"plan": "Plan website", "next": "Check next step", "improve": "Improve prompt", "preview": "Review preview", "publish": "Publish", "clear": "Clear history", "empty": "No draft loaded yet", "ready": "Draft is ready to edit"},
    "es": {"plan": "Planificar sitio", "next": "Ver siguiente paso", "improve": "Mejorar indicación", "preview": "Revisar vista previa", "publish": "Publicar", "clear": "Borrar historial", "empty": "Aún no hay borrador cargado", "ready": "El borrador está listo para editar"},
    "it": {"plan": "Pianifica sito", "next": "Controlla il prossimo passo", "improve": "Migliora richiesta", "preview": "Controlla anteprima", "publish": "Pubblica", "clear": "Cancella cronologia", "empty": "Nessuna bozza caricata", "ready": "La bozza è pronta per la modifica"},
    "ar": {"plan": "خطط للموقع", "next": "تحقق من الخطوة التالية", "improve": "حسّن الطلب", "preview": "راجع المعاينة", "publish": "انشر", "clear": "مسح السجل", "empty": "لا توجد مسودة محمّلة بعد", "ready": "المسودة جاهزة للتعديل"},
    "ku": {"plan": "وێبگە پلان بکە", "next": "هەنگاوی داهاتوو پشکنە", "improve": "داواکارییەکە باشتر بکە", "preview": "پیشاندان پشکنە", "publish": "بڵاوی بکەوە", "clear": "مێژوو بسڕەوە", "empty": "هێشتا هیچ ڕەشنووسێک بار نەکراوە", "ready": "ڕەشنووسەکە ئامادەی دەستکاریکردنە"},
    "hi": {"plan": "वेबसाइट की योजना", "next": "अगला चरण जांचें", "improve": "प्रॉम्प्ट सुधारें", "preview": "प्रीव्यू जांचें", "publish": "प्रकाशित करें", "clear": "इतिहास साफ़ करें", "empty": "अभी कोई ड्राफ्ट लोड नहीं है", "ready": "ड्राफ्ट संपादन के लिए तैयार है"},
}


def get_help_chat_actions() -> dict[str, str]:
    """Liefert sprachabhängige Schnellaktionen für den Hilfe-Chat."""
    return HELP_CHAT_ACTIONS.get(
        str(st.session_state.app_language), HELP_CHAT_ACTIONS["de"]
    )


def get_customer_guidance() -> str:
    """Ermittelt den nächsten sinnvollen Schritt aus den vorhandenen Kundendaten."""
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    business_email = str(st.session_state.get("client_business_email", "")).strip()
    has_draft = bool(st.session_state.get("generated_html"))
    language = str(st.session_state.app_language)

    if language == "de":
        if not company_name:
            return "Nächster Schritt: Geben Sie den offiziellen Unternehmensnamen des Kunden ein. Danach kann die Vorlage auf die Marke ausgerichtet werden."
        if not business_email:
            return f"Für {company_name}: Hinterlegen Sie als Nächstes die geschäftliche Kontakt-E-Mail. Sie wird im Kontaktbereich und Footer verwendet."
        if not has_draft:
            return f"Die Kundendaten für {company_name} sind bereit. Wählen Sie Vorlage, Abschnitte und Design und erstellen Sie anschließend den ersten Entwurf."
        return f"Der Entwurf für {company_name} ist bereit. Prüfen Sie Vorschau, Inhalte und Bilder, bevor Sie die Website veröffentlichen."

    if language == "en":
        if not company_name:
            return "Next step: Add the customer's official company name so the template can be aligned with the brand."
        if not business_email:
            return f"For {company_name}: add the business contact email next. It will be used in the contact section and footer."
        if not has_draft:
            return f"Customer data for {company_name} is ready. Choose a template, sections, and design, then create the first draft."
        return f"The draft for {company_name} is ready. Review preview, content, and images before publishing."

    return get_help_chat_texts()["default"]


def get_help_chat_greeting() -> str:
    """Begrüßt den Kunden mit dem zum Entwurf passenden nächsten Schritt."""
    language = str(st.session_state.app_language)
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    if language == "en":
        name = f" for {company_name}" if company_name else ""
        return (
            f"Hello{name}. I am your website assistant. Ask me about planning, content, "
            "design, templates, previews, errors, or publishing. I can also improve your prompt. "
            f"{get_customer_guidance()}"
        )
    if language == "ar":
        name = f"، {company_name}" if company_name else ""
        return (
            f"مرحباً{name}. أنا مساعد إنشاء موقعك. اسألني عن التخطيط أو المحتوى أو التصميم "
            "أو القوالب أو المعاينة أو الأخطاء أو النشر. ويمكنني أيضاً تحسين وصف موقعك. "
            f"{get_customer_guidance()}"
        )
    if language == "ku":
        name = f"، {company_name}" if company_name else ""
        return (
            f"سڵاو{name}. من یاریدەدەری دروستکردنی وێبگەکەت دەبم. دەتوانیت پرسیار لەسەر "
            "پلان، ناوەڕۆک، دیزاین، قاڵب، پێشبینین، هەڵە یان بڵاوکردنەوە بکەیت. "
            f"{get_customer_guidance()}"
        )
    name = f", {company_name}" if company_name else ""
    return (
        f"Hallo{name}. Ich bin Ihr Website-Assistent. Fragen Sie mich zu Planung, Inhalten, "
        "Design, Vorlagen, Vorschau, Fehlern oder Veröffentlichung. Ich verbessere auch Ihren Prompt. "
        f"{get_customer_guidance()}"
    )


def correct_customer_text(text: str) -> str:
    """Korrigiert häufige Schreibfehler ohne Inhalte an einen Dienst zu übertragen."""
    corrections = {
        "webseite": "Website",
        "webseiten": "Websites",
        "profesionell": "professionell",
        "profesionelle": "professionelle",
        "profesioneller": "professioneller",
        "proffessionell": "professionell",
        "proffessionelle": "professionelle",
        "proffessioneller": "professioneller",
        "erstellund": "Erstellung",
        "erstellenung": "Erstellung",
        "vorlageen": "Vorlagen",
        "kunden": "Kunden",
        "mögllichkeit": "Möglichkeit",
        "möchde": "möchte",
        "können sie": "Können Sie",
    }
    corrected = text.strip()
    for incorrect, replacement in corrections.items():
        corrected = re.sub(
            rf"\b{re.escape(incorrect)}\b",
            replacement,
            corrected,
            flags=re.IGNORECASE,
        )
    if corrected and corrected[0].islower():
        corrected = corrected[0].upper() + corrected[1:]
    if corrected and corrected[-1] not in ".!?":
        corrected += "."
    return corrected


def get_project_coach_response(prompt: str) -> str:
    """Gibt lokale, datensparsame Hilfe zu Planung, Entwurf und Textqualität."""
    question = prompt.strip()
    normalized_question = question.lower()
    language = str(st.session_state.app_language)
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    current_description = str(
        st.session_state.get("template_custom_description", "")
    ).strip()

    correction_match = re.search(
        r"(?:korrigier(?:e|en)?|schreibfehler|rechtschreibung|correct|spelling)\s*[:\-]\s*(.+)",
        question,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if correction_match:
        corrected_text = correct_customer_text(correction_match.group(1))
        if language == "en":
            return f"Corrected version:\n\n{corrected_text}"
        return f"Korrigierte Fassung:\n\n{corrected_text}"

    if prompt == "__improve_customer_prompt__":
        source = current_description or company_name or "das Unternehmen"
        if language == "en":
            return (
                "Professional prompt:\n\n"
                f"Create a high-quality, trustworthy website for {source}. "
                "Clarify the target audience, explain the main services with concrete benefits, "
                "use a consistent brand style, include proof of trust, and end each key section "
                "with a clear contact or enquiry call to action. Keep the structure accessible, "
                "mobile-first, and easy to scan."
            )
        return (
            "Professioneller Prompt:\n\n"
            f"Erstelle eine hochwertige, vertrauenswürdige Website für {source}. "
            "Definiere die Zielgruppe, erkläre die wichtigsten Leistungen mit konkretem Nutzen, "
            "verwende einen einheitlichen Markenstil, zeige Vertrauenselemente und beende jeden "
            "wichtigen Bereich mit einer klaren Kontakt- oder Anfrageaufforderung. Die Struktur "
            "soll barrierearm, mobil optimiert und schnell erfassbar sein."
        )

    if any(word in normalized_question for word in (
        "plan", "planning", "planung", "struktur", "zielgruppe", "entwurf", "draft", "layout",
        "design", "sektion", "section", "seiten", "page", "konzept",
    )):
        if language == "en":
            return (
                "Start with a concise plan: define the main goal and target audience, choose the "
                "most suitable template, then use this order: hero with a clear offer, benefits or "
                "services, trust signals, portfolio or testimonials, and contact. Keep one primary "
                "call to action throughout the draft."
            )
        return (
            "Beginnen Sie mit einem klaren Plan: Hauptziel und Zielgruppe festlegen, passende "
            "Vorlage wählen und dann diese Reihenfolge verwenden: Einstieg mit klarem Angebot, "
            "Leistungen oder Vorteile, Vertrauenselemente, Referenzen oder Bewertungen und Kontakt. "
            "Verwenden Sie im gesamten Entwurf eine eindeutige Hauptaktion."
        )

    response_topics = (
        (
            ("vorlage", "template", "muster"),
            "Wählen Sie zuerst die Vorlage, die Branche und Zielgruppe am besten abbildet. Prüfen Sie sie in der Vorschau und passen Sie danach Farben, Abschnitte und Inhalte an. Eigene HTML-Vorlagen oder öffentliche Websites können Sie im Modus „Bestehende Vorlage bearbeiten“ laden.",
            "Choose the template that best matches the business and audience first. Review it in the preview, then adjust colors, sections, and content. You can load your own HTML template or a public website in Edit existing template.",
        ),
        (
            ("farbe", "farb", "background", "hintergrund", "weiß", "weiss", "color"),
            "Wählen Sie eine Hintergrundvorlage und eine Akzentfarbe, die zur Marke passt. Bei Weiß und hellen Farben verwendet die Vorschau automatisch dunklen Text für gute Lesbarkeit. Prüfen Sie anschließend Kontraste und Buttons in der Vorschau.",
            "Choose a background preset and an accent color that match the brand. With white and light colors, the preview uses dark text automatically for readability. Then review contrast and buttons in the preview.",
        ),
        (
            ("inhalt", "texte", "überschrift", "ueberschrift", "menü", "menu", "footer", "content"),
            "Bearbeiten Sie Überschriften, Leistungen und Kontaktangaben im Bereich „Inhalte“. Formulieren Sie aus Sicht der Zielgruppe: klarer Nutzen, konkrete Leistung und eine eindeutige nächste Aktion wie „Angebot anfragen“ oder „Termin buchen“.",
            "Edit headings, services, and contact details in Contents. Write from the audience's perspective: a clear benefit, a concrete service, and one clear next action such as Request a quote or Book an appointment.",
        ),
        (
            ("mehrseit", "mehr seite", "unterseite", "navigation", "multi-page", "multiple pages"),
            "Wählen Sie bei der Seitenstruktur eine mehrseitige Website. Die Navigation wird im fertigen Einzel-HTML als interne Seitenansicht umgesetzt. Prüfen Sie danach in der Vorschau, ob alle Menüeinträge zu den gewünschten Bereichen führen.",
            "Choose a multi-page structure under page structure. Navigation is implemented as internal views in the final single HTML file. Then verify in the preview that each menu item leads to the intended area.",
        ),
        (
            ("kontakt", "formular", "email", "e-mail", "anfrage", "form"),
            "Tragen Sie die geschäftliche Kontakt-E-Mail ein, bevor Sie den Entwurf erstellen. Sie wird im Kontaktbereich und Footer verwendet. Für echte Formularsendungen brauchen Sie zusätzlich einen konfigurierten Formularanbieter; ohne diesen zeigt die Website die Kontakt-E-Mail deutlich an.",
            "Add the business contact email before creating the draft. It is used in the contact section and footer. For real form submissions, configure a form provider; without one, the website clearly displays the contact email.",
        ),
        (
            ("fehler", "funktioniert nicht", "fehlgeschlagen", "problem", "error", "broken", "failed"),
            "Beschreiben Sie bitte, bei welchem Schritt der Fehler erscheint und kopieren Sie die genaue Fehlermeldung hier hinein. Prüfen Sie vorher: Pflichtfelder sind ausgefüllt, die E-Mail ist gültig, der HTML-Entwurf ist vollständig und bei der Veröffentlichung ist das Premium-Konto aktiv.",
            "Tell me which step shows the error and paste the exact error message here. First check that required fields are filled, the email is valid, the HTML draft is complete, and the Premium account is active for publishing.",
        ),
    )
    for keywords, german_response, english_response in response_topics:
        if any(keyword in normalized_question for keyword in keywords):
            return english_response if language == "en" else german_response

    if any(word in normalized_question for word in (
        "prompt", "besser", "verbess", "profession", "text", "schreib", "fehler",
        "korrig", "rechtschreib", "grammar", "spelling", "correct", "improve",
    )):
        if language == "en":
            return (
                "For a stronger professional prompt, name the business, audience, offer, desired "
                "tone, required sections, and the action visitors should take. I can improve the "
                "current website description with the “Improve prompt” action. For text corrections, "
                "send the exact sentence or paragraph here and I will provide a clean version."
            )
        return (
            "Für einen stärkeren professionellen Prompt nennen Sie Unternehmen, Zielgruppe, Angebot, "
            "gewünschten Ton, benötigte Abschnitte und die gewünschte Aktion der Besucher. Mit "
            "„Prompt verbessern“ formuliere ich die aktuelle Website-Beschreibung professioneller. "
            "Für Schreibkorrekturen senden Sie den genauen Satz oder Absatz hier; ich liefere eine "
            "saubere Fassung."
        )

    return ""


def reset_help_chat_for_language() -> None:
    """Beginnt den Hilfe-Chat mit einer passenden Begrüßung in der neuen Sprache."""
    st.session_state.chat_messages = [
        {"role": "assistant", "content": get_help_chat_greeting()}
    ]
    st.session_state.chat_language = st.session_state.app_language


def add_help_chat_response(prompt: str, display_prompt: str | None = None) -> None:
    """Speichert eine Nutzerfrage und die passende Hilfeantwort im Verlauf."""
    st.session_state.chat_messages.append(
        {"role": "user", "content": display_prompt or prompt}
    )
    st.session_state.chat_messages.append(
        {"role": "assistant", "content": get_help_response(prompt)}
    )


def translate_content_fields_with_mcp(
    fields: dict[str, str], language: str
) -> dict[str, str]:
    """Translates a complete set of editable content fields through the local MCP server."""
    if language == "de":
        return dict(fields)

    async def run_tool() -> dict[str, str]:
        async with Client(website_mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "translate_content_fields",
                {"fields": fields, "language": language},
            )
            content = result.structured_content
            if not isinstance(content, dict) or set(content) != set(fields):
                raise ValueError("Der MCP-Server hat nicht alle Inhaltsfelder übersetzt.")
            return {
                key: str(content[key]).strip()
                for key in fields
            }

    try:
        return asyncio.run(run_tool())
    except Exception as error:
        raise ValueError(f"Die vollständige MCP-Übersetzung ist fehlgeschlagen: {error}") from error


def apply_app_language() -> None:
    """Übernimmt die Sprachwahl des Kunden für den nächsten App-Durchlauf."""
    st.session_state.app_language = APP_LANGUAGES[st.session_state.app_language_name]
    st.session_state.target_language = TARGET_LANGUAGE_BY_APP_CODE[
        st.session_state.app_language
    ]
    language = str(st.session_state.app_language)
    source_preset = st.session_state.get("industry_source_preset")
    if not isinstance(source_preset, dict):
        selected_industry = str(
            st.session_state.get("industry_content_preset", "")
        )
        available_presets = globals().get("INDUSTRY_CONTENT_PRESETS", {})
        source_preset = available_presets.get(selected_industry)
        other_industry = globals().get("OTHER_INDUSTRY_OPTION")
        custom_industry = str(
            st.session_state.get("custom_industry_name", "")
        ).strip()
        generic_preset_builder = globals().get("build_generic_industry_preset")
        if (
            source_preset is None
            and selected_industry == other_industry
            and custom_industry
            and callable(generic_preset_builder)
        ):
            source_preset = generic_preset_builder(custom_industry)
        if isinstance(source_preset, dict):
            source_preset = dict(source_preset)
            st.session_state.industry_source_preset = source_preset
    if isinstance(source_preset, dict):
        try:
            translated_preset = translate_content_fields_with_mcp(
                {key: str(value) for key, value in source_preset.items()}, language
            )
        except ValueError as error:
            st.session_state.language_translation_error = str(error)
        else:
            st.session_state.update(translated_preset)
            st.session_state.industry_preset_language = language
            st.session_state.language_translation_error = ""
    reset_help_chat_for_language()


def apply_design_use_case() -> None:
    """Übernimmt eine Designhilfe als bearbeitbare Startkonfiguration."""
    use_case = DESIGN_USE_CASES[st.session_state.design_use_case]
    if not use_case:
        return

    st.session_state.template_background_color = use_case["background"]
    st.session_state.template_accent_color = use_case["accent"]
    st.session_state.template_border_style = use_case["border_style"]
    st.session_state.page_structure = use_case["page_structure"]
    st.session_state.selected_website_sections = use_case["sections"]
    st.session_state.template_custom_description = use_case["description"]
    st.session_state.template_background_preset = next(
        name
        for name, color in BACKGROUND_PRESET_COLORS.items()
        if color == use_case["background"]
    )


def apply_background_preset() -> None:
    """Übernimmt eine Hintergrundvorlage vor dem Rendern des Color-Pickers."""
    preset_name = st.session_state.template_background_preset
    st.session_state.template_background_color = BACKGROUND_PRESET_COLORS[preset_name]


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

# Übernimmt KI- oder HTML-Änderungen vor dem Erstellen der Widgets.
if st.session_state.pending_html:
    st.session_state.generated_html = st.session_state.pending_html
    st.session_state.html_editor = st.session_state.pending_html
    st.session_state.pending_html = ""


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


def get_help_response(prompt: str) -> str:
    """Gibt eine kurze Hilfeantwort für die wichtigsten Builder-Abläufe zurück."""
    question = prompt.lower()
    texts = get_help_chat_texts()
    language = str(st.session_state.app_language)

    if prompt == "__next_customer_step__":
        return get_customer_guidance()
    if language in {"de", "en"}:
        coach_response = get_project_coach_response(prompt)
        if coach_response:
            return coach_response
    if language == "de" and any(word in question for word in ("url", "link", "adresse", "live-link", "live link")):
        live_url = str(st.session_state.get("live_url", "")).strip()
        if live_url:
            return f"Ihre veröffentlichte Website erreichen Sie hier: {live_url}"
        return "Ihre Live-URL erscheint nach der erfolgreichen Vercel-Veröffentlichung im Bereich „Aktuelle Veröffentlichung“. Dort können Sie die veröffentlichte Seite direkt laden."
    if language == "de" and any(word in question for word in ("aktiv", "aktivier", "freischalt", "abo", "abonnement", "bezahlt", "zahlung")):
        if st.session_state.get("live_url"):
            return "Ihr Konto ist für die Veröffentlichung aktiv; Ihre Live-URL wird im Bereich „Aktuelle Veröffentlichung“ angezeigt."
        return "Während der ersten 24 Stunden ist die Veröffentlichung kostenlos aktiviert. Danach aktivieren Sie Premium über den Bereich „Veröffentlichung und Liveschaltung“. Nach bestätigter Zahlung wird die Website automatisch veröffentlicht."
    if any(word in question for word in ("veröffent", "veroeffent", "publish", "publicar", "pubblic", "vercel", "domain", "نشر", "بڵاو", "प्रकाश")):
        return texts["publish"]
    if any(word in question for word in ("vorschau", "test", "prüf", "pruef", "preview", "vista", "anteprima", "معاين", "پیشاندان", "प्रीव्यू")):
        return texts["preview"]
    if any(word in question for word in ("bild", "logo", "foto", "image", "imagen", "immagine", "صورة", "وێنە", "चित्र")):
        return texts["image"]
    return texts["default"]


def render_help_chatbot() -> None:
    """Rendert einen schwebenden Hilfe-Chat mit scrollbarer Nachrichtenhistorie."""
    if not st.session_state.show_botpress_chatbot:
        return

    if st.session_state.get("chat_language") != st.session_state.app_language:
        reset_help_chat_for_language()

    texts = get_help_chat_texts()
    actions = get_help_chat_actions()

    with st.popover(
        "",
        icon=":material/forum:",
        help=texts["title"],
        key="help_chat_launcher",
        type="primary",
    ):
        header_column, clear_column = st.columns((4, 1), vertical_alignment="center")
        with header_column:
            st.subheader(texts["title"], anchor=False)
            st.caption(actions["ready"] if st.session_state.generated_html else actions["empty"])
            st.caption(get_customer_guidance())
        with clear_column:
            if st.button(
                "",
                icon=":material/delete_sweep:",
                help=actions["clear"],
                key="clear_help_chat",
            ):
                reset_help_chat_for_language()
                st.rerun()

        primary_columns = st.columns(2)
        for column, action_name, action_prompt in (
            (primary_columns[0], "next", "__next_customer_step__"),
            (primary_columns[1], "improve", "__improve_customer_prompt__"),
        ):
            with column:
                if st.button(
                    actions[action_name],
                    key=f"help_chat_action_{action_name}",
                    width="stretch",
                ):
                    add_help_chat_response(action_prompt, actions[action_name])
                    st.rerun()

        action_columns = st.columns(3)
        action_prompts = {
            "plan": "I need help planning my website.",
            "preview": "How do I review the website preview?",
            "publish": "How do I publish my website on Vercel?",
        }
        for column, action_name in zip(action_columns, action_prompts):
            with column:
                if st.button(
                    actions[action_name],
                    key=f"help_chat_action_{action_name}",
                    width="stretch",
                ):
                    add_help_chat_response(
                        action_prompts[action_name],
                        actions[action_name],
                    )
                    st.rerun()

        with st.container(height=280, border=True, key="help_chat_history"):
            for message in st.session_state.chat_messages:
                with st.chat_message(
                    message["role"], avatar=":material/support_agent:"
                ):
                    st.write(message["content"])

        prompt = st.chat_input(texts["input"], key="help_chat_input")
        if prompt:
            add_help_chat_response(prompt)
            st.rerun()


if st.session_state.user_id is None:
    show_authentication()
    st.stop()

current_user_id = int(st.session_state.user_id)
user_info = get_user_status(current_user_id)
return_to_publish = st.query_params.get("publish") == "1"
if not user_info["subscribed"] and confirm_stripe_checkout(current_user_id):
    st.session_state.publish_after_checkout = return_to_publish
    st.success("Zahlung bestätigt. Die Veröffentlichung ist jetzt freigeschaltet.")
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


def clean_html(html: str) -> str:
    """Entfernt Markdown-Codeblöcke aus einer KI-Antwort."""
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
        raise ValueError("Es wurde kein HTML-Code gefunden.")

    if not re.search(r"<html\b", html_lower):
        raise ValueError("Der Inhalt enthält keine vollständige HTML-Website.")

    return html


def ensure_customer_email(html: str, business_email: str) -> str:
    """Stellt sicher, dass der Entwurf die konfigurierte Kontaktadresse verwendet."""
    business_email = business_email.strip().lower()
    email_pattern = r"(?i)(mailto:)?[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"

    html = re.sub(
        email_pattern,
        lambda match: f"mailto:{business_email}" if match.group(1) else business_email,
        html,
    )
    if f"mailto:{business_email}" not in html.lower():
        contact_link = (
            f'<p><a href="mailto:{business_email}">{business_email}</a></p>'
        )
        html = re.sub(r"(?i)</body\s*>", f"{contact_link}</body>", html, count=1)

    return html


def ensure_multi_page_navigation(html: str) -> str:
        """Hält Hash-Navigation innerhalb eines mehrseitigen HTML-Entwurfs."""
        hash_link_pattern = r'(?i)(<a\b[^>]*href=["\']#[^"\']+["\'][^>]*)\s+target=["\'](?:_parent|_top)["\']'
        html = re.sub(hash_link_pattern, r"\1", html)
        router_script = """
<script>
(() => {
    const pages = [...document.querySelectorAll('[data-page]')];
    if (!pages.length) return;
    const showActivePage = () => {
        const requestedPage = decodeURIComponent(location.hash.slice(1) || 'start');
        const activePage = pages.some((page) => page.dataset.page === requestedPage)
            ? requestedPage
            : 'start';
        if (location.hash.slice(1) !== activePage) history.replaceState(null, '', `#${activePage}`);
        pages.forEach((page) => { page.hidden = page.dataset.page !== activePage; });
    };
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.removeAttribute('target');
        link.addEventListener('click', (event) => {
            event.preventDefault();
            location.hash = link.getAttribute('href');
        });
    });
    addEventListener('hashchange', showActivePage);
    showActivePage();
})();
</script>
"""
        return re.sub(r"(?i)</body\s*>", f"{router_script}</body>", html, count=1)


def inject_configured_customer_chatbot(html: str) -> str:
    """Setzt genau einen zentral konfigurierten Chatbot in den Kundenentwurf ein."""
    existing_widget_pattern = (
        r'(?is)<aside\b[^>]*\bclass=["\'][^"\']*\bcustomer-chatbot\b'
        r'[^"\']*["\'][^>]*>.*?</aside>\s*<script>.*?</script>'
    )
    html_without_existing_widget = re.sub(existing_widget_pattern, "", html)
    shape_to_radius = {
        "Rund (Kreis)": "50%",
        "Eckig mit Rundung": "8px",
        "Quadratisch": "0",
    }
    widget = build_customer_chatbot_widget(
        str(st.session_state.get("customer_chatbot_name", "")),
        str(st.session_state.get("customer_chatbot_color", "#2563EB")),
        get_configured_chatbot_knowledge(),
    ).replace('border-radius:50%;width:56px', (
        f'border-radius:{shape_to_radius.get(str(st.session_state.get("customer_chatbot_shape", "Rund (Kreis)")), "50%")};width:56px'
    ))
    return re.sub(
        r"(?i)</body\s*>",
        lambda _match: f"{widget}</body>",
        html_without_existing_widget,
        count=1,
    )


def queue_html_update(html: str, reset_site_pages: bool = False) -> None:
    """Stores an updated page while preserving the adopted template page set."""
    index_html = inject_configured_customer_chatbot(require_complete_html(html))
    site_pages = {} if reset_site_pages else dict(st.session_state.site_pages)
    site_pages["index.html"] = index_html
    st.session_state.site_pages = site_pages
    st.session_state.pending_html = index_html
    st.session_state.generated_html = index_html
    st.session_state.html_editor = index_html


def build_chat_api_route(chatbot_knowledge: str) -> str:
        """Erstellt eine Vercel-Route, die den Hugging-Face-Schlüssel serverseitig hält."""
        language = str(st.session_state.app_language)
        api_copy = {
            "de": {"name": "Deutsch", "fallback": "Gerne helfe ich weiter. Fragen Sie mich zu unserem Angebot oder erzählen Sie mir, wobei ich Sie unterstützen darf.", "hello": "Hallo! Schön, dass Sie da sind. Wie kann ich Ihnen helfen?", "thanks": "Sehr gern. Haben Sie noch eine Frage?", "bye": "Auf Wiedersehen und einen schönen Tag!", "invalid": "Bitte senden Sie eine gültige Frage."},
            "en": {"name": "English", "fallback": "I am happy to help. Ask me about our services or tell me what you need.", "hello": "Hello! It is nice to meet you. How can I help?", "thanks": "You are welcome. Is there anything else I can help with?", "bye": "Goodbye and have a wonderful day!", "invalid": "Please send a valid question."},
            "ar": {"name": "Arabic", "fallback": "يسعدني مساعدتك. اسألني عن خدماتنا أو أخبرني بما تحتاج إليه.", "hello": "مرحباً! يسعدني وجودك هنا. كيف يمكنني مساعدتك؟", "thanks": "على الرحب والسعة. هل لديك سؤال آخر؟", "bye": "إلى اللقاء، ونتمنى لك يوماً سعيداً!", "invalid": "يرجى إرسال سؤال صحيح."},
            "ku": {"name": "Sorani Kurdish", "fallback": "بە خۆشحاڵییەوە یارمەتیت دەدەم. دەربارەی خزمەتگوزارییەکانمان بپرسە یان پێم بڵێ چیت پێویستە.", "hello": "سڵاو! خۆشحاڵم کە لێرەیت. چۆن دەتوانم یارمەتیت بدەم؟", "thanks": "بەخێربێیت. پرسیارێکی ترت هەیە؟", "bye": "خواحافیز و ڕۆژێکی خۆشت هەبێت!", "invalid": "تکایە پرسیارێکی دروست بنێرە."},
            "es": {"name": "Spanish", "fallback": "Estaré encantado de ayudarte. Pregúntame por nuestros servicios o dime qué necesitas.", "hello": "¡Hola! Me alegra verte. ¿Cómo puedo ayudarte?", "thanks": "De nada. ¿Puedo ayudarte con algo más?", "bye": "¡Hasta pronto y que tengas un buen día!", "invalid": "Envía una pregunta válida."},
            "it": {"name": "Italian", "fallback": "Sarò felice di aiutarti. Chiedimi dei nostri servizi o dimmi di cosa hai bisogno.", "hello": "Ciao! È un piacere averti qui. Come posso aiutarti?", "thanks": "Prego. Posso aiutarti con qualcos'altro?", "bye": "Arrivederci e buona giornata!", "invalid": "Invia una domanda valida."},
            "hi": {"name": "Hindi", "fallback": "मुझे आपकी सहायता करके खुशी होगी। हमारी सेवाओं के बारे में पूछें या बताएं कि आपको क्या चाहिए।", "hello": "नमस्ते! आपका स्वागत है। मैं आपकी कैसे सहायता कर सकता हूं?", "thanks": "आपका स्वागत है। क्या मैं किसी और चीज में सहायता कर सकता हूं?", "bye": "फिर मिलेंगे, आपका दिन शुभ हो!", "invalid": "कृपया एक मान्य प्रश्न भेजें।"},
        }.get(language)
        if api_copy is None:
            api_copy = {"name": "English", "fallback": "Please contact us using the contact details on this website.", "invalid": "Please send a valid question."}
        knowledge = chatbot_knowledge.strip() or (
                "Keine zusätzlichen Firmendaten vorhanden. Verweise bei unbekannten Fragen "
                "auf die Kontaktmöglichkeiten der Website."
        )
        knowledge_json = json.dumps(knowledge, ensure_ascii=False)
        copy_json = json.dumps(api_copy, ensure_ascii=False)
        return f'''const CHATBOT_KNOWLEDGE = {knowledge_json};
    const CHAT_LANGUAGE = "{language}";
    const CHAT_COPY = {copy_json};
    const MODEL_URL = "https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-7B-Instruct";
    const FALLBACK_ANSWER = CHAT_COPY.fallback;

function findDetail(...labels) {{
    for (const label of labels) {{
        const match = CHATBOT_KNOWLEDGE.match(new RegExp(label + ":\\s*([^\\n]+)", "i"));
        if (match) return match[1].trim();
    }}
    return "";
}}

function targetedAnswer(question) {{
    if (CHAT_LANGUAGE !== "de") return "";
    const normalized = question.toLowerCase();
    const contact = findDetail("Kontaktwege");
    const hours = findDetail("Öffnungszeiten");
    const services = findDetail("Preise und Leistungen", "Typische Leistungen dieser Branche");
    const emergency = findDetail("Notfall und Bereitschaft");
    const company = findDetail("Unternehmen");
    const description = findDetail("Unternehmensbeschreibung");
    const hasVerifiedPrices = CHATBOT_KNOWLEDGE.includes("Preise und Leistungen:");
    if (/(kontakt|telefon|e-mail|mail|erreich)/.test(normalized) && contact) return `Sie erreichen uns: ${{contact}}`;
    if (/(öffnungs|uhrzeit|geöffnet|termin|wann)/.test(normalized) && hours) return `Unsere Öffnungszeiten bzw. Terminzeiten: ${{hours}}`;
    if (/(preis|kosten)/.test(normalized) && !hasVerifiedPrices) return "Konkrete Preise liegen uns nicht vor. Bitte fragen Sie direkt über die Kontaktmöglichkeiten der Website an.";
    if (/(preis|kosten)/.test(normalized) && services) return `Zu Preisen und Leistungen: ${{services}}`;
    if (/(leistung|service|angebot|behandlung)/.test(normalized) && services) return `Wir bieten unter anderem: ${{services}}`;
    if (/(notfall|dringend|bereit|panne)/.test(normalized) && emergency) return emergency;
    if (/(über euch|über sie|unternehmen|firma|wer seid|wer sind sie)/.test(normalized) && description) return company ? `${{company}}: ${{description}}` : description;
    if (/(hallo|guten tag|hilfe|was machen sie|wer sind sie)/.test(normalized) && services) return `Gerne helfe ich weiter. Wir bieten unter anderem ${{services}}.`;
    return "";
}}

function offlineAnswer(question) {{
    const normalized = question.toLocaleLowerCase();
    if (/(^|\\s)(hallo|hi|hey|hello|hola|ciao|مرحبا|أهلا|سڵاو|नमस्ते)(\\s|$|!)/u.test(normalized)) return CHAT_COPY.hello;
    if (/(danke|thank|gracias|grazie|شكرا|سوپاس|धन्यवाद)/u.test(normalized)) return CHAT_COPY.thanks;
    if (/(tschüss|auf wiedersehen|goodbye|bye|adiós|arrivederci|مع السلامة|خواحافیز|अलविदा)/u.test(normalized)) return CHAT_COPY.bye;
    return CHAT_COPY.fallback;
}}

export default async function handler(request, response) {{
    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", "Content-Type");
    if (request.method === "OPTIONS") {{
        return response.status(204).end();
    }}
    if (request.method !== "POST") {{
        response.setHeader("Allow", "POST");
        return response.status(405).json({{ error: "Method not allowed" }});
    }}

    const question = typeof request.body?.question === "string" ? request.body.question.trim() : "";
    if (!question || question.length > 800) {{
        return response.status(400).json({{ error: CHAT_COPY.invalid }});
    }}

    const directAnswer = targetedAnswer(question);
    if (directAnswer) {{
        return response.status(200).json({{ answer: directAnswer }});
    }}

    const apiKey = process.env.HF_API_KEY;
    if (!apiKey) {{
        return response.status(200).json({{ answer: offlineAnswer(question) }});
    }}

    const prompt = `<|im_start|>system\nYou are a warm, intelligent customer-service assistant. Respond only in ${{CHAT_COPY.name}} and keep answers concise. Hold natural conversations, including greetings, thanks, farewells, and light small talk. For factual questions about the company, use only the verified details below and never invent prices, opening hours, availability, policies, or contact details. If a requested company fact is unavailable, say so naturally and offer the website contact options. Verified company details:\n${{CHATBOT_KNOWLEDGE}}<|im_end|>\n<|im_start|>user\n${{question}}<|im_end|>\n<|im_start|>assistant\n`;
    try {{
        const hfResponse = await fetch(MODEL_URL, {{
            method: "POST",
            headers: {{ Authorization: `Bearer ${{apiKey}}`, "Content-Type": "application/json" }},
            body: JSON.stringify({{ inputs: prompt, parameters: {{ max_new_tokens: 120, temperature: 0.2, return_full_text: false }} }}),
        }});
        const data = await hfResponse.json();
        if (!hfResponse.ok) {{
            return response.status(200).json({{ answer: offlineAnswer(question) }});
        }}
        const generated = Array.isArray(data) ? data[0]?.generated_text : data.generated_text;
        const answer = typeof generated === "string" ? generated.split("<|im_start|>assistant").pop().replace("<|im_end|>", "").trim() : "";
        return response.status(200).json({{ answer: answer || offlineAnswer(question) }});
    }} catch (error) {{
        return response.status(200).json({{ answer: offlineAnswer(question) }});
    }}
}}
'''


def add_vercel_chat_api(site_pages: dict[str, str]) -> dict[str, str]:
        """Fügt jeder Kundenwebsite die geschützte Chat-Route hinzu."""
        site_pages["api/chat.js"] = build_chat_api_route(
                get_configured_chatbot_knowledge()
        )
        site_pages["vercel.json"] = '{"cleanUrls": true}'
        return site_pages


def build_website_zip() -> bytes:
    """Packt den aktuellen Vercel-Entwurf mit Seiten, CSS und Bildern in eine ZIP-Datei."""
    index_html = require_complete_html(st.session_state.generated_html)
    site_pages = dict(st.session_state.site_pages) or {"index.html": index_html}
    site_pages["index.html"] = index_html
    site_pages = add_vercel_chat_api(site_pages)
    archive = io.BytesIO()

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, page_content in site_pages.items():
            content = (
                require_complete_html(page_content)
                if file_name.endswith(".html")
                else page_content
            )
            zip_file.writestr(file_name, content)
        for file_name, asset in st.session_state.assets.items():
            zip_file.writestr(file_name, base64.b64decode(asset["base64"]))

    return archive.getvalue()


def safe_project_name(name: str) -> str:
    """Erstellt einen gültigen Vercel-Projektnamen."""
    safe_name = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return safe_name[:100] or "ai-website-builder"


def create_deployment_project_name() -> str:
    """Erstellt für jede Veröffentlichung einen neuen Vercel-Projektnamen."""
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    template_name = str(st.session_state.get("template_name", "website"))
    name_prefix = safe_project_name(company_name or template_name)
    return f"{name_prefix[:88]}-{secrets.token_hex(4)}"


def get_project_name_from_url(live_url: str) -> str:
    """Erstellt einen Projektnamen-Vorschlag aus einer URL."""
    normalized_url = live_url.strip()
    if not normalized_url.startswith(("https://", "http://")):
        normalized_url = f"https://{normalized_url}"
    hostname = urlparse(normalized_url).hostname or ""
    return safe_project_name(hostname.split(".")[0])


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

    safe_section = re.sub(
        r"[^a-z0-9]+",
        "-",
        section_name.lower(),
    ).strip("-")

    file_name = f"{safe_section or 'bild'}-bild{extension}"

    st.session_state.assets[file_name] = {
        "base64": base64.b64encode(uploaded_file.getvalue()).decode("utf-8"),
        "mime_type": uploaded_file.type or mime_types[extension],
    }

    return file_name


def create_preview_html(html: str, include_customer_chatbot: bool = False) -> str:
    """Erstellt die Builder-Vorschau aus derselben Kunden-HTML wie der Export."""
    preview_html = html
    if not include_customer_chatbot:
        preview_html = re.sub(
            r'<aside class="customer-chatbot".*?</aside>\s*<script>.*?</script>',
            "",
            preview_html,
            flags=re.DOTALL,
        )

    for file_name, asset in st.session_state.assets.items():
        data_url = f"data:{asset['mime_type']};base64,{asset['base64']}"
        preview_html = preview_html.replace(file_name, data_url)

    return preview_html


def replace_first_image_source(html: str, image_name: str, alt_text: str) -> str:
    """Ersetzt das erste Bild im Entwurf lokal durch ein hochgeladenes Asset."""
    image_tag = f'<img src="{image_name}" alt="{alt_text}">'
    if re.search(r"(?i)<img\b[^>]*>", html):
        return re.sub(r"(?i)<img\b[^>]*>", image_tag, html, count=1)
    if re.search(r'(?i)<div\b[^>]*class=["\'][^"\']*image-placeholder[^"\']*["\'][^>]*>.*?</div>', html, re.DOTALL):
        return re.sub(
            r'(?i)<div\b[^>]*class=["\'][^"\']*image-placeholder[^"\']*["\'][^>]*>.*?</div>',
            image_tag,
            html,
            count=1,
            flags=re.DOTALL,
        )
    return re.sub(r"(?i)</body\s*>", f"{image_tag}</body>", html, count=1)


def replace_visible_text(html: str, old_text: str, new_text: str) -> str:
    """Ersetzt eine bewusst ausgewählte Textstelle ohne HTML-Markup zu verändern."""
    old_text = old_text.strip()
    new_text = new_text.strip()
    if not old_text:
        raise ValueError("Bitte geben Sie den bisherigen Text ein.")
    if old_text not in html:
        raise ValueError("Die angegebene Textstelle wurde im aktuellen Entwurf nicht gefunden.")
    return html.replace(old_text, escape(new_text), 1)


def build_offer_page_section(offer_name: str, offer_price: str, offer_details: str) -> str:
    """Erstellt eine lokale Angebots-Unterseite mit professioneller Kartenstruktur."""
    language = str(st.session_state.app_language)
    copy = get_template_preview_copy(language)
    page_title, page_heading, cards = copy["pages"]["angebote"]
    price_defaults = {
        "de": "Preis auf Anfrage", "en": "Price on request",
        "ar": "السعر عند الطلب", "ku": "نرخ بە داواکاری",
        "es": "Precio a consultar", "it": "Prezzo su richiesta",
        "hi": "मूल्य अनुरोध पर",
    }
    title = escape(offer_name.strip() or page_heading)
    price = escape(offer_price.strip() or price_defaults.get(language, price_defaults["en"]))
    details = escape(offer_details.strip() or cards[0][1])
    return f"""
<section id="angebote" data-page="angebote" class="bg-slate-950 px-6 py-16 text-white">
  <div class="mx-auto max-w-6xl">
    <p class="text-sm font-semibold uppercase tracking-wide text-cyan-300">{page_title}</p>
    <h1 class="mt-3 text-4xl font-bold">{title}</h1>
    <p class="mt-4 max-w-2xl text-slate-300">{details}</p>
    <div class="mt-10 grid gap-6 md:grid-cols-3">
      <article class="rounded-lg border border-slate-700 bg-slate-900 p-6">
                <p class="text-sm text-cyan-300">01</p><h2 class="mt-2 text-xl font-semibold">{title}</h2>
        <p class="mt-4 text-slate-300">{details}</p><p class="mt-6 text-2xl font-bold">{price}</p>
                <a class="mt-6 inline-block rounded bg-cyan-400 px-4 py-2 font-semibold text-slate-950" href="#kontakt">{copy["contact"]}</a>
      </article>
            <article class="rounded-lg border border-slate-700 bg-slate-900 p-6"><p class="text-sm text-cyan-300">02</p><h2 class="mt-2 text-xl font-semibold">{cards[1][0]}</h2><p class="mt-4 text-slate-300">{cards[1][1]}</p></article>
            <article class="rounded-lg border border-slate-700 bg-slate-900 p-6"><p class="text-sm text-cyan-300">03</p><h2 class="mt-2 text-xl font-semibold">{cards[2][0]}</h2><p class="mt-4 text-slate-300">{cards[2][1]}</p></article>
    </div>
  </div>
</section>
"""


def optimize_editor_text(text: str) -> str:
    """Optimiert einen ausgewählten Website-Text erst nach ausdrücklichem Nutzer-Klick."""
    if not text.strip():
        raise ValueError("Bitte geben Sie zuerst einen Text zur Optimierung ein.")
    response = ask_ai_for_html(
        "Du bist ein professioneller deutscher Webtexter. Antworte nur mit dem optimierten Text, ohne HTML, Markdown oder Erklärung.",
        "Optimiere diesen Text für eine professionelle Website. Korrigiere Rechtschreibung, "
        "formuliere klar und ansprechend und erfinde keine Fakten:\n\n" + text.strip(),
    )
    return clean_html(response)


def build_customized_template_html(
    template_name: str,
    background_color: str,
    accent_color: str,
    border_style: str,
    company_name: str,
    business_email: str,
    slogan: str,
    phone: str,
    description: str,
    image_file,
    button_text: str = "Ihr Angebot entdecken",
    footer_text: str = "",
    multi_page: bool = True,
    chatbot_knowledge: str = "",
    chatbot_name: str = "",
    chatbot_color: str = "#38BDF8",
    chatbot_radius: str = "50%",
    template_sections: str = "",
) -> str:
    """Übernimmt die ausgewählte Vorlage lokal und füllt sie mit Kundendaten."""
    language = str(st.session_state.app_language)
    page_copy = get_template_preview_copy(language)
    nav_copy = page_copy["nav"]
    services_copy = page_copy["pages"]["leistungen"]
    about_copy = page_copy["pages"]["ueber_uns"]
    contact_copy = page_copy["pages"]["kontakt"]
    direction = "rtl" if language in {"ar", "ku"} else "ltr"
    localized_template_names = {
        "en": {"Restaurant und Gastronomie": "Restaurant and hospitality"},
        "ar": {"Restaurant und Gastronomie": "المطاعم والضيافة"},
        "ku": {"Restaurant und Gastronomie": "چێشتخانە و میوانداری"},
        "es": {"Restaurant und Gastronomie": "Restauración y gastronomía"},
        "it": {"Restaurant und Gastronomie": "Ristorazione e gastronomia"},
        "hi": {"Restaurant und Gastronomie": "रेस्तरां और आतिथ्य"},
    }
    template_display_name = localized_template_names.get(language, {}).get(
        template_name, template_name if language == "de" else nav_copy["leistungen"]
    )
    company_name = escape(company_name.strip())
    business_email = escape(business_email.strip())
    slogan = escape(slogan.strip() or str(page_copy["defaults"][0]))
    description = escape(description.strip() or str(page_copy["defaults"][1]))
    button_text = escape(button_text.strip() or str(page_copy["defaults"][2]))
    footer_text = escape(
        footer_text.strip()
        or f'{company_name} | {business_email} | {page_copy["imprint"]} | {page_copy["privacy"]}'
    )
    chatbot_knowledge = escape(
        chatbot_knowledge.strip()
        or f"Willkommen bei {company_name}. Wie können wir Ihnen helfen?"
    )
    chatbot_name = escape(chatbot_name.strip() or f"{company_name} Assistent")
    chatbot_position = str(
        st.session_state.get("customer_chatbot_position", "Unten rechts")
    )
    chatbot_css_position = (
        "position:fixed;left:20px;right:auto;bottom:20px;"
        if chatbot_position == "Unten links"
        else "position:fixed;right:20px;left:auto;bottom:20px;"
    )
    if not st.session_state.get("customer_chatbot_fixed", True):
        chatbot_css_position = chatbot_css_position.replace(
            "position:fixed;", "position:relative;"
        )
    phone = escape(phone.strip())
    radius = "0" if border_style == "sharp" else "10px"
    text_color = contrast_text_color(background_color)
    muted_color = "#334155" if is_light_color(background_color) else "#cbd5e1"
    template_styles = {
        "Automobil und KFZ-Gewerbe": "header{border-bottom:4px solid var(--accent)}.hero{grid-template-columns:1fr 1fr}.card{border-radius:0}",
        "GmbH und Corporate Unternehmen": "header{border-bottom:1px solid var(--accent)}.hero{grid-template-columns:1.25fr .75fr}.card{border-top-width:1px}",
        "Cafe und Baeckerei": "header{background:color-mix(in srgb,var(--accent) 12%,var(--background))}.hero{grid-template-columns:.9fr 1.1fr}.card{border-radius:18px}",
        "Restaurant und Gastronomie": "header{background:#17120d;color:#f8e7bd}.hero{grid-template-columns:.85fr 1.15fr}.card{border-color:#d4a74a;border-radius:2px}",
        "Formale Agentur oder Kanzlei": "header{border-bottom:1px solid var(--text)}.hero{grid-template-columns:1.35fr .65fr}.card{border-left:3px solid var(--accent);border-top:0;border-radius:0}",
        "Schule und Bildung": "header{background:color-mix(in srgb,var(--accent) 10%,var(--background))}.cards{gap:24px}.card{border-radius:14px}",
        "Bibliothek": "header{border-bottom:1px solid var(--accent)}.hero{grid-template-columns:1.2fr .8fr}.card{border-radius:4px}",
        "Supermarkt und Einzelhandel": "header{background:var(--accent);color:#111827}.hero{grid-template-columns:1fr 1fr}.card{border-top-width:5px;border-radius:0}",
    }
    template_style = template_styles.get(template_name, "")
    image_html = f'<div class="image-placeholder">{page_copy["imagePlaceholder"]}</div>'
    if image_file is not None:
        image_name = save_uploaded_image(image_file, "vorlagen-hero")
        image_html = f'<img class="hero-image" src="{image_name}" alt="{company_name}">'
    phone_html = f'<p>{phone}</p>' if phone else ""
    navigation = (
        f'<a href="leistungen.html">{nav_copy["leistungen"]}</a><a href="angebote.html">{nav_copy["angebote"]}</a>'
        f'<a href="projekte.html">{nav_copy["projekte"]}</a><a href="ueber-uns.html">{nav_copy["ueber_uns"]}</a>'
        f'<a href="kontakt.html">{nav_copy["kontakt"]}</a>'
        if multi_page
        else f'<a href="#leistungen">{nav_copy["leistungen"]}</a><a href="#ueber-uns">{nav_copy["ueber_uns"]}</a><a href="#kontakt">{nav_copy["kontakt"]}</a>'
    )
    button_target = "angebote.html" if multi_page else "#leistungen"
    section_cards = []
    for index, section in enumerate(template_sections.splitlines()[:3], start=1):
        title, separator, text = section.partition("|")
        section_cards.append(
            f'<article class="card"><strong>{index:02d}</strong><h3>{escape(title.strip())}</h3><p>{escape(text.strip() if separator else description)}</p></article>'
        )
    if not section_cards:
        section_cards = [
            '<article class="card"><strong>01</strong><h3>Klare Leistungen</h3><p>Passende Lösungen mit nachvollziehbarer Beratung.</p></article>',
            '<article class="card"><strong>02</strong><h3>Vertrauen schaffen</h3><p>Qualität, Transparenz und ein verbindlicher Service.</p></article>',
            '<article class="card"><strong>03</strong><h3>Kontakt erleichtern</h3><p>Schnell und direkt zu Ihrer persönlichen Anfrage.</p></article>',
        ]
    section_cards_html = "".join(section_cards)
    footer_html = f'''<footer class="site-footer"><section><strong>{company_name}</strong><p>{footer_text}</p></section><section><strong>{page_copy["contact"]}</strong><p><a href="mailto:{business_email}">{business_email}</a></p></section><section><strong>{page_copy["legal"]}</strong><p><a href="#impressum">{page_copy["imprint"]}</a> · <a href="#datenschutz">{page_copy["privacy"]}</a></p></section><p class="footer-legal">© 2026 {company_name}. {page_copy["rights"]}</p></footer>'''
    chatbot_widget_html = f'''<style>.customer-chatbot{{{chatbot_css_position}z-index:10000;font-family:Arial,sans-serif}}.customer-chatbot-toggle{{border:0;color:#fff;padding:13px 18px;cursor:pointer;font-weight:700;box-shadow:0 4px 10px rgba(0,0,0,.2)}}.customer-chatbot-window{{position:absolute;right:0;bottom:64px;width:min(350px,calc(100vw - 40px));height:450px;background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:8px;box-shadow:0 5px 15px rgba(0,0,0,.3);overflow:hidden}}.customer-chatbot-window header{{display:flex;justify-content:space-between;align-items:center;padding:14px;color:#fff}}.customer-chatbot-window header button{{border:0;background:transparent;color:#fff;font-size:22px;cursor:pointer}}.customer-chatbot-messages{{height:calc(100% - 110px);overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:8px}}.customer-chatbot-message{{max-width:85%;margin:0;padding:8px 12px;background:#f3f4f6;border-radius:8px;color:#111827}}.customer-chatbot-message-user{{align-self:flex-end;background:{chatbot_color};color:#fff}}.customer-chatbot-form{{display:flex;gap:6px;padding:10px;border-top:1px solid #e5e7eb}}.customer-chatbot-form input{{min-width:0;flex:1;padding:8px;border:1px solid #d1d5db;border-radius:6px}}.customer-chatbot-form button{{border:0;border-radius:6px;padding:8px 12px;color:#fff;cursor:pointer}}@media(max-width:480px){{.customer-chatbot-window{{height:400px}}}}</style><aside class="customer-chatbot" data-knowledge="{chatbot_knowledge}">
<button class="customer-chatbot-toggle" type="button" aria-expanded="false" aria-label="{chatbot_name} öffnen" style="background:{chatbot_color};border-radius:{chatbot_radius}">Chat</button>
<section class="customer-chatbot-window" hidden>
<header style="background:{chatbot_color}"><strong>{chatbot_name}</strong><button type="button" aria-label="Chat schließen">×</button></header>
<div class="customer-chatbot-messages" aria-live="polite"><p class="customer-chatbot-message">Hallo! Wie kann ich Ihnen helfen?</p></div>
<form class="customer-chatbot-form"><input type="text" aria-label="Frage eingeben" placeholder="Frage eingeben..." required><button type="submit" style="background:{chatbot_color}">Senden</button></form>
</section></aside>
<script>const chatbot=document.querySelector('.customer-chatbot'),toggle=chatbot.querySelector('.customer-chatbot-toggle'),panel=chatbot.querySelector('.customer-chatbot-window'),closeButton=panel.querySelector('header button'),form=chatbot.querySelector('form'),input=form.querySelector('input'),messages=chatbot.querySelector('.customer-chatbot-messages'),knowledge=chatbot.dataset.knowledge;const setOpen=open=>{{panel.hidden=!open;toggle.setAttribute('aria-expanded',String(open));if(open)input.focus();}};toggle.onclick=()=>setOpen(panel.hidden);closeButton.onclick=()=>setOpen(false);form.onsubmit=event=>{{event.preventDefault();const question=input.value.trim();if(!question)return;const userMessage=document.createElement('p');userMessage.className='customer-chatbot-message customer-chatbot-message-user';userMessage.textContent=question;messages.append(userMessage);input.value='';const answer=document.createElement('p');answer.className='customer-chatbot-message';const questionLower=question.toLowerCase();answer.textContent=questionLower.includes('kontakt')||questionLower.includes('email')?`Sie erreichen uns unter {business_email}.`:knowledge||'Vielen Dank für Ihre Anfrage. Wir melden uns gerne persönlich bei Ihnen.';messages.append(answer);messages.scrollTop=messages.scrollHeight;}};</script>'''
    chatbot_widget_html = build_customer_chatbot_widget(
        chatbot_name, chatbot_color, chatbot_knowledge
    )
    return f"""<!doctype html>
<html lang="{language}" dir="{direction}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{company_name}</title>
<link rel="stylesheet" href="styles.css">
<style>:root {{ --background: {background_color}; --accent: {accent_color}; --text: {text_color}; --muted: {muted_color}; --radius: {radius}; }} {template_style}</style></head>
<body><header><strong>{company_name}</strong><nav>{navigation}</nav></header>
<main><section class="container hero" id="hero"><div><span class="eyebrow">{escape(template_display_name)}</span><h1>{slogan}</h1><p>{description}</p><a class="button" href="{button_target}">{button_text}</a></div>{image_html}</section>
<section class="band"><div class="container" id="leistungen"><span class="eyebrow">{nav_copy["leistungen"]}</span><h2>{services_copy[1]}</h2><div class="cards">{section_cards_html}</div></div></section>
<section class="container" id="ueber-uns"><span class="eyebrow">{nav_copy["ueber_uns"]}</span><h2>{about_copy[1]}</h2><p>{description}</p></section>
<section class="band"><div class="container contact" id="kontakt"><div><span class="eyebrow">{nav_copy["kontakt"]}</span><h2>{contact_copy[1]}</h2><p><a href="mailto:{business_email}">{business_email}</a></p>{phone_html}</div><div class="card"><h3>{contact_copy[2][1][0]}</h3><p>{contact_copy[2][1][1]}</p><a class="button" href="mailto:{business_email}">{nav_copy["kontakt"]}</a></div></div></section></main>
    {footer_html}{chatbot_widget_html}</body></html>"""


def build_customized_template_styles() -> str:
    """Liefert das gemeinsame Design für alle statischen Vorlagen-Seiten."""
    return """* { box-sizing: border-box; } body { margin: 0; background: var(--background); color: var(--text); font: 16px/1.55 Arial, sans-serif; } header { padding: 20px max(5vw, 24px); border-bottom: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } header, nav { display: flex; gap: 18px; flex-wrap: wrap; justify-content: space-between; align-items: center; } nav a, .button, .site-footer a { color: inherit; text-decoration: none; } main, .container { max-width: 1120px; margin: auto; padding: 70px 24px; } .hero, .contact { display: grid; grid-template-columns: 1.1fr .9fr; gap: 40px; align-items: center; } .eyebrow { color: var(--accent); font-size: 13px; font-weight: 700; text-transform: uppercase; } h1 { font-family: Georgia, serif; font-size: clamp(2.4rem, 5vw, 4.4rem); line-height: 1.05; margin: 14px 0; } p { color: var(--muted); } .button { display: inline-block; margin-top: 18px; padding: 13px 19px; border-radius: var(--radius); background: var(--accent); color: #111827; font-weight: 700; } .hero-image, .image-placeholder { width: 100%; min-height: 310px; object-fit: cover; border-radius: var(--radius); border: 1px dashed var(--accent); display: grid; place-items: center; color: var(--accent); padding: 20px; } .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 45px; } .card { border-top: 3px solid var(--accent); background: color-mix(in srgb, var(--text) 6%, transparent); padding: 24px; margin-top: 32px; } .band { background: color-mix(in srgb, var(--text) 6%, transparent); } .site-footer { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 28px; padding: 34px max(5vw, 24px) 20px; border-top: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } .site-footer strong { display: block; } .site-footer p { margin: 8px 0 0; font-size: 13px; } .footer-legal { grid-column: 1 / -1; padding-top: 16px; border-top: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } .customer-chatbot { position: fixed; right: 24px; bottom: 24px; z-index: 10; } .customer-chatbot button { width: 52px; height: 52px; border: 0; border-radius: 50%; background: var(--accent); color: #111827; cursor: pointer; font-weight: 700; font-size: 20px; } .customer-chatbot section { width: min(300px, calc(100vw - 48px)); margin-bottom: 10px; padding: 18px; border: 1px solid color-mix(in srgb, var(--text) 18%, transparent); border-radius: var(--radius); background: var(--background); box-shadow: 0 16px 38px rgba(15, 23, 42, .22); } @media (max-width: 700px) { header, .hero, .contact { display: block; } nav { margin-top: 12px; } .hero-image, .image-placeholder { margin-top: 26px; min-height: 220px; } .cards, .site-footer { grid-template-columns: 1fr; } }"""


def _build_customer_chatbot_widget_legacy(
    chatbot_name: str, chatbot_color: str, chatbot_knowledge: str
) -> str:
    """Erstellt ein lokales Chat-Widget für die exportierte Kundenwebsite."""
    chatbot_name = escape(chatbot_name.strip() or "Kundenservice")
    chatbot_knowledge = chatbot_knowledge.strip() or (
        "Vielen Dank für Ihre Nachricht. Wir melden uns gerne persönlich bei Ihnen."
    )
    chatbot_knowledge_base64 = base64.b64encode(
        chatbot_knowledge.encode("utf-8")
    ).decode("ascii")
    chatbot_color = (
        chatbot_color
        if re.fullmatch(r"#[0-9a-fA-F]{6}", chatbot_color)
        else "#2563EB"
    )
    chatbot_figure = {
        "Freundlicher Roboter": "🤖",
        "Salon-Stylistin": "✂",
        "Werkstatt-Profi": "🔧",
        "Praxis-Begleitung": "✚",
        "Gastronomie-Service": "☕",
        "Shop-Beratung": "🛍",
    }.get(str(st.session_state.get("customer_chatbot_figure", "")), "🤖")
    is_left_aligned = st.session_state.get("customer_chatbot_position") == "Unten links"
    chatbot_side = "left:20px;right:auto;" if is_left_aligned else "right:20px;left:auto;"
    panel_side = "left:0;right:auto;" if is_left_aligned else "right:0;left:auto;"
    chatbot_behavior = "fixed" if st.session_state.get("customer_chatbot_fixed", True) else "relative"
    return f'''<style>#customer-chatbot{{font-family:Arial,sans-serif}}#customer-chatbot [hidden]{{display:none!important}}#customer-chat-panel{{box-sizing:border-box;position:absolute;{panel_side}bottom:76px;width:min(360px,calc(100vw - 32px));overflow:hidden;background:#fff;color:#172033;border:1px solid #dbe2ea;border-radius:8px;box-shadow:0 18px 48px rgba(15,23,42,.24)}}#customer-chat-header{{display:flex;align-items:center;gap:10px;padding:15px 16px;background:{chatbot_color};color:#fff}}#customer-chat-header strong{{display:block;font-size:15px}}#customer-chat-header span{{font-size:12px;opacity:.9}}#customer-chat-answer{{min-height:52px;margin:16px;padding:12px;background:#f3f6f9;border-radius:6px;color:#334155;font-size:14px;line-height:1.5}}#customer-chat-form{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:0 16px 16px}}#customer-chat-input{{min-width:0;border:1px solid #cbd5e1;border-radius:5px;padding:11px 12px;font:inherit}}#customer-chat-send{{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-width:104px;border:0;border-radius:5px;background:{chatbot_color};color:#fff;padding:10px 14px;font:700 14px Arial,sans-serif;cursor:pointer;white-space:nowrap;box-shadow:0 2px 5px rgba(15,23,42,.18);transition:filter .15s ease,transform .15s ease}}#customer-chat-send:hover{{filter:brightness(.92);transform:translateY(-1px)}}#customer-chat-send:disabled{{cursor:wait;opacity:.72;transform:none}}#customer-chat-send:focus-visible,#customer-chat-input:focus-visible,#customer-chat-toggle:focus-visible{{outline:3px solid #fbbf24;outline-offset:2px}}@media(max-width:420px){{#customer-chat-form{{grid-template-columns:1fr}}#customer-chat-send{{width:100%}}}}</style><aside id="customer-chatbot" class="customer-chatbot" style="position:{chatbot_behavior};{chatbot_side}bottom:20px;z-index:10000"><button id="customer-chat-toggle" type="button" aria-expanded="false" aria-label="{chatbot_name} öffnen" title="{chatbot_name} öffnen" style="display:grid;place-items:center;background:{chatbot_color};color:#fff;border:0;border-radius:50%;width:64px;height:64px;cursor:pointer;font-size:32px;line-height:1;box-shadow:0 6px 18px rgba(0,0,0,.24)"><span aria-hidden="true">{chatbot_figure}</span></button><section id="customer-chat-panel" hidden role="dialog" aria-label="Chat mit {chatbot_name}"><div id="customer-chat-header"><span aria-hidden="true" style="font-size:24px">{chatbot_figure}</span><div><strong>{chatbot_name}</strong><span>Online · Persönliche Auskunft</span></div></div><p id="customer-chat-answer">Guten Tag. Wobei dürfen wir Sie unterstützen?</p><form id="customer-chat-form"><input id="customer-chat-input" aria-label="Frage eingeben" placeholder="Ihre Frage eingeben" required><button id="customer-chat-send" type="submit"><span aria-hidden="true">➤</span><span>Senden</span></button></form></section></aside>
<script>(() => {{
    const toggle = document.getElementById('customer-chat-toggle');
    const panel = document.getElementById('customer-chat-panel');
    const form = document.getElementById('customer-chat-form');
    const input = document.getElementById('customer-chat-input');
    const answer = document.getElementById('customer-chat-answer');
    const sendButton = document.getElementById('customer-chat-send');
    const fallback = decodeURIComponent(escape(atob('{chatbot_knowledge_base64}')));
    const fallbackAnswer = (question) => {{
        const normalized = question.toLowerCase();
        const detail = (labels) => {{
            for (const label of labels) {{
                const match = fallback.match(new RegExp(label + ':\\s*([^\\n]+)', 'i'));
                if (match) return match[1].trim();
            }}
            return '';
        }};
        const contact = detail(['Kontaktwege']);
        const hours = detail(['Öffnungszeiten']);
        const services = detail(['Preise und Leistungen', 'Typische Leistungen dieser Branche']);
        const company = detail(['Unternehmen']);
        const description = detail(['Unternehmensbeschreibung']);
        if (/(kontakt|telefon|e-mail|mail|erreich)/.test(normalized) && contact) return `Sie erreichen uns: ${{contact}}`;
        if (/(öffnungs|uhrzeit|geöffnet|termin|wann)/.test(normalized) && hours) return `Unsere Öffnungszeiten bzw. Terminzeiten: ${{hours}}`;
        if (/(preis|kosten)/.test(normalized) && !fallback.includes('Preise und Leistungen:')) return 'Konkrete Preise liegen uns nicht vor. Bitte fragen Sie direkt über die Website an.';
        if (/(preis|kosten)/.test(normalized) && services) return `Zu Preisen und Leistungen: ${{services}}`;
        if (/(leistung|service|angebot|behandlung)/.test(normalized) && services) return `Wir bieten unter anderem: ${{services}}`;
        if (/(über euch|über sie|unternehmen|firma|wer seid|wer sind sie)/.test(normalized) && description) return company ? `${{company}}: ${{description}}` : description;
        return 'Bitte kontaktieren Sie uns direkt über die Kontaktmöglichkeiten der Website. Dort erhalten Sie eine verlässliche Auskunft.';
    }};
    if (!toggle || !panel || !form || !input || !answer || !sendButton) return;
    toggle.onclick = () => {{ panel.hidden = !panel.hidden; toggle.setAttribute('aria-expanded', String(!panel.hidden)); if (!panel.hidden) input.focus(); }};
    form.onsubmit = async (event) => {{
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;
        answer.textContent = 'Antwort wird erstellt ...';
        input.value = '';
        sendButton.disabled = true;
        sendButton.setAttribute('aria-busy', 'true');
        try {{
            const result = await fetch('/api/chat', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ question }}) }});
            const data = await result.json().catch(() => ({{}}));
            answer.textContent = result.ok && data.answer ? data.answer : fallbackAnswer(question);
        }} catch (error) {{
            answer.textContent = fallbackAnswer(question);
        }} finally {{
            sendButton.disabled = false;
            sendButton.removeAttribute('aria-busy');
        }}
    }};
}})();</script>'''
    return f'''<aside class="customer-chatbot" style="position:{chatbot_behavior};{chatbot_side}bottom:20px;z-index:10000"><button id="customer-chat-toggle" type="button" aria-expanded="false" aria-label="{chatbot_name} öffnen" style="background:{chatbot_color};color:#fff;border:0;border-radius:50%;width:56px;height:56px;cursor:pointer;font-weight:700;box-shadow:0 6px 18px rgba(0,0,0,.24)">Chat</button><section id="customer-chat-panel" hidden style="position:absolute;right:0;bottom:68px;width:min(330px,calc(100vw - 40px));padding:18px;background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.22)"><strong>{chatbot_name}</strong><p id="customer-chat-answer" style="margin:10px 0;color:#374151">Hallo! Wie können wir helfen?</p><form id="customer-chat-form" style="display:flex;gap:6px"><input id="customer-chat-input" aria-label="Frage eingeben" placeholder="Frage eingeben..." required style="min-width:0;flex:1;padding:8px"><button type="submit" style="border:0;background:{chatbot_color};color:#fff;padding:8px 12px;cursor:pointer">Senden</button></form></section></aside><script>(()=>{{const toggle=document.getElementById('customer-chat-toggle'),panel=document.getElementById('customer-chat-panel'),form=document.getElementById('customer-chat-form'),input=document.getElementById('customer-chat-input'),answer=document.getElementById('customer-chat-answer');toggle.onclick=()=>{{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();}};form.onsubmit=async event=>{{event.preventDefault();const question=input.value.trim();if(!question)return;answer.textContent='Antwort wird erstellt ...';try{{const result=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question}})}});const data=await result.json();answer.textContent=data.answer||data.error||'Bitte kontaktieren Sie uns direkt.';}}catch(error){{answer.textContent='Bitte kontaktieren Sie uns direkt.';}}input.value='';}};}})();</script>'''
    return f'''<aside class="customer-chatbot" data-knowledge="{chatbot_knowledge}" style="position:{chatbot_behavior};{chatbot_side}bottom:20px;z-index:10000"><button id="customer-chat-toggle" type="button" aria-expanded="false" aria-label="{chatbot_name} öffnen" style="background:{chatbot_color};color:#fff;border:0;border-radius:50%;width:56px;height:56px;cursor:pointer;font-weight:700;box-shadow:0 6px 18px rgba(0,0,0,.24)">Chat</button><section id="customer-chat-panel" hidden style="position:absolute;right:0;bottom:68px;width:min(330px,calc(100vw - 40px));padding:18px;background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.22)"><strong>{chatbot_name}</strong><p id="customer-chat-answer" style="margin:10px 0;color:#374151">Hallo! Wie können wir helfen?</p><form id="customer-chat-form" style="display:flex;gap:6px"><input id="customer-chat-input" aria-label="Frage eingeben" placeholder="Frage eingeben..." required style="min-width:0;flex:1;padding:8px"><button type="submit" style="border:0;background:{chatbot_color};color:#fff;padding:8px 12px;cursor:pointer">Senden</button></form></section></aside><script>(()=>{{const toggle=document.getElementById('customer-chat-toggle'),panel=document.getElementById('customer-chat-panel'),form=document.getElementById('customer-chat-form'),input=document.getElementById('customer-chat-input'),answer=document.getElementById('customer-chat-answer'),knowledge=document.querySelector('.customer-chatbot').dataset.knowledge;toggle.onclick=()=>{{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();}};form.onsubmit=async event=>{{event.preventDefault();const question=input.value.trim();if(!question)return;answer.textContent='Antwort wird erstellt ...';input.value='';try{{const result=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question}})}});const data=await result.json();answer.textContent=data.answer||data.error||knowledge;}}catch(error){{answer.textContent=knowledge||'Bitte nutzen Sie die Kontaktmöglichkeiten auf dieser Website.';}}}};}})();</script>'''


def build_customer_chatbot_widget(
    chatbot_name: str, chatbot_color: str, chatbot_knowledge: str
) -> str:
    """Erstellt den Kunden-Chatbot vollständig in der gewählten App-Sprache."""
    language = str(st.session_state.app_language)
    copy_by_language = {
        "de": {"service": "Kundenservice", "open": "Chatbot öffnen", "welcome": "Hallo! Wie können wir Ihnen helfen?", "question": "Frage eingeben...", "send": "Senden", "loading": "Antwort wird erstellt ...", "thanks": "Sehr gern. Haben Sie noch eine Frage?", "bye": "Auf Wiedersehen und einen schönen Tag!", "fallback": "Gerne helfe ich weiter. Fragen Sie mich zu unserem Angebot oder sagen Sie mir, was Sie benötigen."},
        "en": {"service": "Customer service", "open": "Open chatbot", "welcome": "Hello! How can we help you?", "question": "Enter your question...", "send": "Send", "loading": "Creating an answer ...", "thanks": "You are welcome. Can I help with anything else?", "bye": "Goodbye and have a wonderful day!", "fallback": "I am happy to help. Ask about our services or tell me what you need."},
        "ar": {"service": "خدمة العملاء", "open": "فتح المحادثة", "welcome": "مرحباً! كيف يمكننا مساعدتك؟", "question": "اكتب سؤالك...", "send": "إرسال", "loading": "جارٍ إعداد الإجابة...", "thanks": "على الرحب والسعة. هل لديك سؤال آخر؟", "bye": "إلى اللقاء، ونتمنى لك يوماً سعيداً!", "fallback": "يسعدني مساعدتك. اسألني عن خدماتنا أو أخبرني بما تحتاج إليه."},
        "ku": {"service": "خزمەتگوزاری کڕیار", "open": "کردنەوەی چات", "welcome": "سڵاو! چۆن دەتوانین یارمەتیت بدەین؟", "question": "پرسیارەکەت بنووسە...", "send": "ناردن", "loading": "وەڵام ئامادە دەکرێت...", "thanks": "بەخێربێیت. پرسیارێکی ترت هەیە؟", "bye": "خواحافیز و ڕۆژێکی خۆشت هەبێت!", "fallback": "بە خۆشحاڵییەوە یارمەتیت دەدەم. دەربارەی خزمەتگوزارییەکانمان بپرسە."},
        "es": {"service": "Atención al cliente", "open": "Abrir chat", "welcome": "¡Hola! ¿Cómo podemos ayudarte?", "question": "Escribe tu pregunta...", "send": "Enviar", "loading": "Preparando la respuesta...", "thanks": "De nada. ¿Puedo ayudarte con algo más?", "bye": "¡Hasta pronto y que tengas un buen día!", "fallback": "Estaré encantado de ayudarte. Pregúntame por nuestros servicios o dime qué necesitas."},
        "it": {"service": "Servizio clienti", "open": "Apri chat", "welcome": "Ciao! Come possiamo aiutarti?", "question": "Scrivi la tua domanda...", "send": "Invia", "loading": "Preparazione della risposta...", "thanks": "Prego. Posso aiutarti con qualcos'altro?", "bye": "Arrivederci e buona giornata!", "fallback": "Sarò felice di aiutarti. Chiedimi dei nostri servizi o dimmi di cosa hai bisogno."},
        "hi": {"service": "ग्राहक सेवा", "open": "चैट खोलें", "welcome": "नमस्ते! हम आपकी कैसे सहायता कर सकते हैं?", "question": "अपना प्रश्न लिखें...", "send": "भेजें", "loading": "उत्तर तैयार हो रहा है...", "thanks": "आपका स्वागत है। क्या मैं किसी और चीज में सहायता कर सकता हूं?", "bye": "फिर मिलेंगे, आपका दिन शुभ हो!", "fallback": "मुझे आपकी सहायता करके खुशी होगी। हमारी सेवाओं के बारे में पूछें या बताएं कि आपको क्या चाहिए।"},
    }
    copy = copy_by_language.get(language, copy_by_language["en"])
    direction = "rtl" if language in {"ar", "ku"} else "ltr"
    safe_name = escape(chatbot_name.strip() or copy["service"])
    safe_knowledge = escape(chatbot_knowledge.strip(), quote=True)
    safe_color = chatbot_color if re.fullmatch(r"#[0-9a-fA-F]{6}", chatbot_color) else "#2563EB"
    is_left = st.session_state.get("customer_chatbot_position") == "Unten links"
    side = "left:20px;right:auto;" if is_left else "right:20px;left:auto;"
    panel_side = "left:0;right:auto;" if is_left else "right:0;left:auto;"
    position = "fixed" if st.session_state.get("customer_chatbot_fixed", True) else "relative"
    copy_json = json.dumps(copy, ensure_ascii=False).replace("</", "<\\/")
    return f'''<aside id="customer-chatbot" lang="{language}" dir="{direction}" data-knowledge="{safe_knowledge}" style="position:{position};{side}bottom:20px;z-index:10000;font-family:Arial,sans-serif">
<button id="customer-chat-toggle" type="button" aria-expanded="false" aria-label="{escape(copy['open'])}" title="{escape(copy['open'])}" style="width:56px;height:56px;border:0;border-radius:50%;background:{safe_color};color:#fff;cursor:pointer;font-weight:700;box-shadow:0 6px 18px rgba(0,0,0,.24)">Chat</button>
<section id="customer-chat-panel" hidden style="position:absolute;{panel_side}bottom:68px;width:min(340px,calc(100vw - 40px));padding:18px;background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:8px;box-shadow:0 10px 28px rgba(0,0,0,.22);text-align:{'right' if direction == 'rtl' else 'left'}">
<strong>{safe_name}</strong><p id="customer-chat-answer" aria-live="polite" style="margin:10px 0;color:#374151">{escape(copy['welcome'])}</p>
<form id="customer-chat-form" style="display:flex;gap:6px"><input id="customer-chat-input" aria-label="{escape(copy['question'])}" placeholder="{escape(copy['question'])}" required style="min-width:0;flex:1;padding:8px;text-align:inherit"><button id="customer-chat-send" type="submit" style="border:0;background:{safe_color};color:#fff;padding:8px 12px;cursor:pointer">{escape(copy['send'])}</button></form></section></aside>
<script>(()=>{{const copy={copy_json};const root=document.getElementById('customer-chatbot');const toggle=document.getElementById('customer-chat-toggle');const panel=document.getElementById('customer-chat-panel');const form=document.getElementById('customer-chat-form');const input=document.getElementById('customer-chat-input');const answer=document.getElementById('customer-chat-answer');const send=document.getElementById('customer-chat-send');const offlineAnswer=question=>{{const normalized=question.toLocaleLowerCase();if(/(^|\\s)(hallo|hi|hey|hello|hola|ciao|مرحبا|أهلا|سڵاو|नमस्ते)(\\s|$|!)/u.test(normalized))return copy.welcome;if(/(danke|thank|gracias|grazie|شكرا|سوپاس|धन्यवाद)/u.test(normalized))return copy.thanks;if(/(tschüss|auf wiedersehen|goodbye|bye|adiós|arrivederci|مع السلامة|خواحافیز|अलविदा)/u.test(normalized))return copy.bye;return copy.fallback;}};toggle.onclick=()=>{{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();}};form.onsubmit=async event=>{{event.preventDefault();const question=input.value.trim();if(!question)return;answer.textContent=copy.loading;input.value='';send.disabled=true;try{{const result=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question,language:'{language}'}})}});const data=await result.json().catch(()=>({{}}));answer.textContent=result.ok&&data.answer?data.answer:offlineAnswer(question);}}catch(error){{answer.textContent=offlineAnswer(question);}}finally{{send.disabled=false;}}}};}})();</script>'''


def build_customized_template_pages(
    company_name: str, business_email: str, background_color: str,
    accent_color: str, description: str, chatbot_knowledge: str = "",
    chatbot_name: str = "", chatbot_color: str = "#2563EB",
) -> dict[str, str]:
    """Erstellt echte statische Angebots- und Kontaktseiten der Kundenwebsite."""
    language = str(st.session_state.app_language)
    copy = get_template_preview_copy(language)
    nav = copy["nav"]
    direction = "rtl" if language in {"ar", "ku"} else "ltr"
    company_name = escape(company_name.strip())
    business_email = escape(business_email.strip())
    description = escape(description.strip() or str(copy["defaults"][1]))
    text_color = contrast_text_color(background_color)
    muted_color = "#334155" if is_light_color(background_color) else "#cbd5e1"
    head = f"""<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{company_name}</title><link rel="stylesheet" href="styles.css"><style>:root{{--background:{background_color};--accent:{accent_color};--text:{text_color};--muted:{muted_color};--radius:10px;}}</style></head>"""
    navigation = f'<nav><a href="index.html">{nav["start"]}</a><a href="leistungen.html">{nav["leistungen"]}</a><a href="angebote.html">{nav["angebote"]}</a><a href="projekte.html">{nav["projekte"]}</a><a href="ueber-uns.html">{nav["ueber_uns"]}</a><a href="kontakt.html">{nav["kontakt"]}</a></nav>'

    def page_html(page_key: str) -> str:
        _title, heading, cards = copy["pages"][page_key]
        cards_html = "".join(
            f'<section class="card"><h2>{card_title}</h2><p>{card_text or description}</p></section>'
            for card_title, card_text in cards
        )
        return f'''<!doctype html><html lang="{language}" dir="{direction}">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>{heading}</h1><p>{description}</p>{cards_html}<a class="button" href="kontakt.html">{nav["kontakt"]}</a></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>'''

    services = page_html("leistungen")
    projects = page_html("projekte")
    about = page_html("ueber_uns")
    offers = page_html("angebote")
    contact = page_html("kontakt")
    chatbot_widget = build_customer_chatbot_widget(
        chatbot_name, chatbot_color, chatbot_knowledge
    )
    pages = {
        "leistungen.html": services,
        "angebote.html": offers,
        "projekte.html": projects,
        "ueber-uns.html": about,
        "kontakt.html": contact,
    }
    pages = {
        page_name: page_html.replace("</body>", f"{chatbot_widget}</body>")
        for page_name, page_html in pages.items()
    }
    pages["styles.css"] = build_customized_template_styles()
    return pages


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert vollständigen HTML-Code von OpenAI an."""
    if not deduct_tokens(current_user_id):
        raise ValueError(
            "Ihre kostenlose 24-Stunden-Testphase ist abgelaufen. Bitte schließen Sie "
            "Premium ab, um weitere Websites mit KI zu erstellen."
        )

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.35,
            timeout=90,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_instruction},
            ],
        )
    except Exception as error:
        refund_tokens(current_user_id)
        raise ValueError(
            "Die KI-Erstellung ist derzeit nicht erreichbar. Ihr Guthaben wurde "
            "nicht belastet. Bitte versuchen Sie es in wenigen Minuten erneut."
        ) from error

    return response.choices[0].message.content or ""


def generate_website(
    description: str,
    image_file,
    image_placement: str = "Hero- und Willkommensbereich",
    multi_page: bool = False,
) -> None:
    """Erstellt einen neuen Website-Entwurf."""
    image_instruction = ""
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    business_email = str(st.session_state.get("client_business_email", "")).strip()
    company_slogan = str(st.session_state.get("client_company_slogan", "")).strip()
    business_phone = str(st.session_state.get("client_business_phone", "")).strip()
    chatbot_knowledge = get_configured_chatbot_knowledge()
    web3forms_access_key = str(
        st.session_state.get("client_web3forms_access_key", "")
    ).strip()

    if business_email and not EMAIL_PATTERN.fullmatch(business_email):
        raise ValueError("Bitte gib eine gueltige geschäftliche E-Mail-Adresse ein.")
    if not business_email or not company_name:
        raise ValueError(
            "Bitte geben Sie Unternehmensname und geschäftliche E-Mail-Adresse ein."
        )

    if image_file is not None:
        image_name = save_uploaded_image(image_file, image_placement)
        image_instruction = f"""
    Bildplatzierung: {image_placement}.
    Nutze dieses Bild ausschließlich im Bereich „{image_placement}“ und verwende exakt:
    <img src="{image_name}" alt="{company_name}">
    Wenn „Logo“ gewählt wurde, nutze das Bild klein und klar im Kopfbereich sowie optional im Footer.
    Wenn „Hero- und Willkommensbereich“ gewählt wurde, nutze es groß im ersten sichtbaren Bereich.
    Wenn „Über-uns-Bereich“ gewählt wurde, nutze es nur bei der Unternehmensvorstellung.
    Wenn „Projektbereich“ gewählt wurde, nutze es ausschließlich als hervorgehobenes Projektbild.
"""

    if web3forms_access_key:
        contact_form_instruction = f"""- Erstelle einen sichtbaren, modernen Kontaktbereich mit diesem exakten Formularbeginn:
    <form action="https://api.web3forms.com/submit" method="POST" class="mt-8 space-y-4">
    <input type="hidden" name="access_key" value="{web3forms_access_key}">
    <input type="hidden" name="subject" value="Neue Anfrage für {company_name}">
    <input type="hidden" name="to_email" value="{business_email}">
- Das Formular braucht sichtbare Labels sowie die Pflichtfelder name, email und message.
- Baue vor dem Absenden per JavaScript ein verstecktes Feld name="redirect" ein und
    setze dessen value auf window.location.href."""
    else:
        contact_form_instruction = f"""- Erstelle einen sichtbaren Kontaktbereich mit der E-Mail-Adresse {business_email}.
- Verwende kein externes Formular und keinen Web3Forms Access Key."""

    saas_system_instruction = f"""
Du bist ein Weltklasse-Frontend-Entwickler und ein Experte fuer das Model Context
Protocol (MCP). Deine Aufgabe ist es, eine vollstaendige, hochgradig attraktive,
moderne und responsive Website exakt anhand der bereitgestellten Kundendaten zu
erstellen.

REGELN FUER DIE GENERIERUNG:
- Nutze valides HTML5, beginne mit <!doctype html> und binde Tailwind CSS ueber
    https://cdn.tailwindcss.com ein.
- Orientiere dich strikt an der gewaehlten Branche, den Farben und den Kundendaten.
- Beruecksichtige das MCP-Paradigma. Wenn die Nutzeranforderung externe Daten oder
    Aktionen erfordert, etwa Live-Preise, Domain-Pruefungen oder Datenbanken,
    bereite den JavaScript-Code mit standardisierten JSON-Daten fuer einen
    MCP-Server vor. Kommentiere jede solche Schnittstelle klar als
    // MCP-Schnittstelle: [Funktionsbeschreibung].
- Nutze fuer allgemeine Bilder hochwertige, passende Unsplash-Bild-URLs. Wenn ein
    hochgeladenes Bild angegeben ist, verwende ausschliesslich das im Bildauftrag
    vorgegebene <img>-Element mit dessen exaktem src-Pfad.
- Verwende niemals Beispielnamen, persoenliche Daten oder Platzhalter einer bestimmten
    Person. Alle Inhalte muessen sich ausschliesslich auf das Kundenunternehmen beziehen.
- Erstelle Navigation, Hero, Leistungen, Ueber uns, ein funktionsfaehiges
    Kontaktformular und einen mehrspaltigen Footer. Befolge die im Nutzerauftrag
    gewählte Seitenstruktur zwingend.
- Antworte ausschliesslich mit dem vollstaendigen HTML, ohne Markdown oder Erklaerung.

GESCHAEFTS- UND KONTAKTDATEN:
- Offizieller Unternehmensname: {company_name}
- Geschaeftliche Kontakt-E-Mail: {business_email}
- Slogan oder Hauptbotschaft: {company_slogan or 'Entwickle eine passende Hauptbotschaft.'}
- Telefonnummer: {business_phone or 'Nicht angegeben; erfinde keine Telefonnummer.'}
- Verwende den Unternehmensnamen in Navigation, Hero, Seitentitel und Footer.
- Zeige die Kontakt-E-Mail im Kontaktbereich und Footer an.
- Verwende den Slogan im Hero-Bereich. Zeige die Telefonnummer nur an, wenn sie angegeben wurde.

KONTAKTFORMULAR:
{contact_form_instruction}

CHATBOT MIT VOICE:
- Erstelle kein Chatbot-Markup und keinen Chatbot-Code. Der Kunden-Chatbot wird nach der
    HTML-Generierung zentral, mit sicheren Server-Aufrufen und den Kundendaten, eingefügt.

{image_instruction}
"""

    html = ask_ai_for_html(
        system_instruction=saas_system_instruction,
        user_instruction=description,
    )

    html = ensure_customer_email(html, business_email)
    if multi_page:
        html = re.sub(
            r"(?i)(</head\s*>)",
            r'<link rel="stylesheet" href="styles.css">\1',
            html,
            count=1,
        )
    queue_html_update(html)
    if multi_page:
        background_color = BACKGROUND_PRESET_COLORS.get(
            str(st.session_state.get("template_background_preset", "Weiß")),
            "#FFFFFF",
        )
        static_pages = build_customized_template_pages(
            company_name,
            business_email,
            background_color,
            str(st.session_state.get("template_accent_color", "#22D3EE")),
            description,
            get_configured_chatbot_knowledge(),
            str(st.session_state.get("customer_chatbot_name", "")),
            str(st.session_state.get("customer_chatbot_color", "#2563EB")),
        )
        static_pages.pop("leistungen.html")
        for page_name, page_content in static_pages.items():
            if page_name.endswith(".html"):
                static_pages[page_name] = page_content.replace(
                    'href="leistungen.html"', 'href="index.html"'
                )
        st.session_state.site_pages.update(static_pages)


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
        "ar": {"Rund (Kreis)": "دائري", "Eckig mit Rundung": "بحواف مستديرة", "Quadratisch": "مربع", "Freundlicher Roboter": "روبوت ودود", "Salon-Stylistin": "خبيرة تصفيف", "Werkstatt-Profi": "خبير ورشة", "Praxis-Begleitung": "مساعد العيادة", "Gastronomie-Service": "مساعد المطعم", "Shop-Beratung": "مساعد المتجر", "Unten rechts": "أسفل اليمين", "Unten links": "أسفل اليسار"},
        "ku": {"Rund (Kreis)": "بازنەیی", "Eckig mit Rundung": "گۆشەی خڕ", "Quadratisch": "چوارگۆشە", "Freundlicher Roboter": "ڕۆبۆتی دۆستانە", "Salon-Stylistin": "پسپۆڕی جوانکاری", "Werkstatt-Profi": "پسپۆڕی وەرشە", "Praxis-Begleitung": "یاریدەدەری کلینیک", "Gastronomie-Service": "یاریدەدەری چێشتخانە", "Shop-Beratung": "ڕاوێژکاری فرۆشگا", "Unten rechts": "خوارەوە لای ڕاست", "Unten links": "خوارەوە لای چەپ"},
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
            ["Freundlicher Roboter", "Salon-Stylistin", "Werkstatt-Profi", "Praxis-Begleitung", "Gastronomie-Service", "Shop-Beratung"],
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
    chatbot_knowledge = get_configured_chatbot_knowledge()
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


def get_template_preview_copy(language: str) -> dict[str, object]:
    """Liefert alle festen Texte der interaktiven Vorlage in der App-Sprache."""
    common = {
        "de": {"nav": ["Start", "Leistungen", "Angebote", "Projekte", "Über uns", "Kontakt"], "page": ["Leistungen für Ihren Erfolg.", "Passende Angebote, klar erklärt.", "Einblicke in unsere Arbeit.", "Ein Unternehmen, das persönlich erreichbar bleibt.", "Sprechen Sie mit uns."], "cards": ["Individuelle Beratung", "Verlässliche Umsetzung", "Nachhaltiger Service", "Individuelles Angebot", "Transparente Konditionen", "Persönliche Anfrage", "Ausgewählte Projekte", "Unser Vorgehen", "Ihr nächstes Projekt", "Unsere Arbeitsweise", "Unser Anspruch", "Ihr Vorteil", "Direkter Kontakt", "Persönliche Beratung", "Nächster Schritt"], "texts": ["Wir analysieren Ihren Bedarf und entwickeln eine passende Lösung.", "Klare Abläufe, hohe Qualität und ein verbindlicher Ansprechpartner.", "Auch nach dem Projekt bleiben wir persönlich für Sie erreichbar.", "Leistungsumfang und nächster Schritt sind klar beschrieben.", "Wir beraten Sie persönlich zu Ihrem Vorhaben.", "Einblick in Lösungen, die wir gemeinsam mit unseren Kunden umgesetzt haben.", "Von der ersten Idee bis zur verlässlichen Umsetzung begleiten wir jedes Vorhaben.", "Wir verbinden Kompetenz mit klarer Kommunikation.", "Qualität und Verlässlichkeit bestimmen jede Zusammenarbeit.", "Wir melden uns zeitnah bei Ihnen.", "Senden Sie uns Ihre Anfrage und erzählen Sie uns von Ihrem Vorhaben."], "ui": ["Dies ist eine eigenständige Unterseite im selben Unternehmensdesign.", "BILDBEREICH: Hero oder Willkommensbereich", "Rechtliches", "Impressum", "Datenschutz", "Alle Rechte vorbehalten.", "Design, Blöcke und Struktur bleiben erhalten. Inhalte werden über die Eingabefelder festgelegt.", "Willkommen. Wie können wir Ihnen helfen?", "Frage eingeben...", "Senden", "Danke für Ihre Frage", "Wir melden uns gerne bei Ihnen.", "Assistent", "Chatbot öffnen"], "defaults": ["Eine Vorlage mit klarer Struktur und Raum für Ihre Inhalte.", "Sie ersetzen Unternehmensdaten, Texte und Bilder direkt in dieser Vorlage.", "Ihr Angebot entdecken", "Ihre Kontakt-E-Mail", "Individuell auf Ihr Unternehmen abgestimmt."]},
        "en": {"nav": ["Home", "Services", "Offers", "Projects", "About us", "Contact"], "page": ["Services designed for your success.", "The right offers, clearly explained.", "A look at our work.", "A company that remains personally accessible.", "Talk to us."], "cards": ["Personal consultation", "Reliable delivery", "Lasting support", "Custom offer", "Transparent terms", "Personal request", "Selected projects", "Our approach", "Your next project", "How we work", "Our standards", "Your advantage", "Direct contact", "Personal advice", "Next step"], "texts": ["We analyze your needs and develop the right solution.", "Clear processes, high quality, and one dedicated contact.", "We remain personally available after the project.", "The scope and next step are clearly described.", "We will personally advise you about your project.", "Explore solutions we have delivered with our customers.", "We guide every project from the first idea to reliable delivery.", "We combine expertise with clear communication.", "Quality and reliability guide every collaboration.", "We will get back to you promptly.", "Send your request and tell us about your project."], "ui": ["This is a standalone page in the same company design.", "IMAGE AREA: Hero or welcome section", "Legal", "Imprint", "Privacy", "All rights reserved.", "The design, blocks, and structure remain intact. Content is controlled through the input fields.", "Welcome. How can we help you?", "Enter your question...", "Send", "Thank you for your question", "We will be happy to contact you.", "Assistant", "Open chatbot"], "defaults": ["A clear template with room for your content.", "Replace company details, text, and images directly in this template.", "Discover our offer", "Your contact email", "Tailored to your business."]},
        "ar": {"nav": ["الرئيسية", "الخدمات", "العروض", "المشاريع", "من نحن", "اتصل بنا"], "page": ["خدمات مصممة لنجاحك.", "عروض مناسبة وموضحة بوضوح.", "نظرة على أعمالنا.", "شركة تبقى قريبة ومتاحة لعملائها.", "تحدث معنا."], "cards": ["استشارة شخصية", "تنفيذ موثوق", "دعم مستمر", "عرض مخصص", "شروط شفافة", "طلب شخصي", "مشاريع مختارة", "أسلوب عملنا", "مشروعك القادم", "طريقة عملنا", "معاييرنا", "ميزتك", "تواصل مباشر", "استشارة شخصية", "الخطوة التالية"], "texts": ["نحلل احتياجاتك ونطور الحل المناسب.", "إجراءات واضحة وجودة عالية وجهة اتصال مخصصة.", "نبقى متاحين لك شخصياً بعد انتهاء المشروع.", "نوضح نطاق العمل والخطوة التالية بوضوح.", "نقدم لك استشارة شخصية حول مشروعك.", "اكتشف حلولاً نفذناها بالتعاون مع عملائنا.", "نرافق كل مشروع من الفكرة الأولى إلى التنفيذ الموثوق.", "نجمع بين الخبرة والتواصل الواضح.", "الجودة والموثوقية أساس كل تعاون.", "سنتواصل معك في أقرب وقت.", "أرسل طلبك وأخبرنا عن مشروعك."], "ui": ["هذه صفحة مستقلة ضمن تصميم الشركة نفسه.", "مساحة الصورة: الواجهة الرئيسية أو قسم الترحيب", "معلومات قانونية", "بيانات الموقع", "الخصوصية", "جميع الحقوق محفوظة.", "يبقى التصميم والأقسام والبنية كما هي، ويتم تحديد المحتوى عبر حقول الإدخال.", "مرحباً، كيف يمكننا مساعدتك؟", "اكتب سؤالك...", "إرسال", "شكراً لسؤالك", "يسعدنا التواصل معك.", "المساعد", "فتح المحادثة"], "defaults": ["قالب واضح يوفر مساحة لمحتواك.", "استبدل بيانات الشركة والنصوص والصور مباشرة في هذا القالب.", "اكتشف عرضنا", "بريدك الإلكتروني للتواصل", "مصمم خصيصاً لشركتك."]},
        "ku": {"nav": ["سەرەکی", "خزمەتگوزارییەکان", "پێشنیارەکان", "پڕۆژەکان", "دەربارەی ئێمە", "پەیوەندی"], "page": ["خزمەتگوزاری بۆ سەرکەوتنی تۆ.", "پێشنیاری گونجاو و ڕوون.", "سەیرێکی کارەکانمان بکە.", "کۆمپانیایەک کە هەمیشە لە بەردەستە.", "لەگەڵمان قسە بکە."], "cards": ["ڕاوێژکاری تایبەت", "جێبەجێکردنی متمانەپێکراو", "پشتیوانی بەردەوام", "پێشنیاری تایبەت", "مەرجی ڕوون", "داواکاری تایبەت", "پڕۆژە هەڵبژێردراوەکان", "شێوازی کارمان", "پڕۆژەی داهاتووت", "شێوازی کارمان", "ستانداردەکانمان", "سوودی تۆ", "پەیوەندی ڕاستەوخۆ", "ڕاوێژکاری تایبەت", "هەنگاوی داهاتوو"], "texts": ["پێداویستییەکانت شیکاری دەکەین و چارەسەری گونجاو دادەنێین.", "ڕێکاری ڕوون، کوالێتی بەرز و کەسێکی دیاریکراو بۆ پەیوەندی.", "دوای پڕۆژەکەش بەردەوام لە بەردەستت دەبین.", "سنووری کار و هەنگاوی داهاتوو بە ڕوونی باس دەکرێت.", "بۆ پڕۆژەکەت ڕاوێژکاری تایبەت پێشکەش دەکەین.", "چارەسەرە جێبەجێکراوەکانمان لەگەڵ کڕیاران ببینە.", "لە بیرۆکەی یەکەمەوە تا جێبەجێکردنی متمانەپێکراو لەگەڵتین.", "شارەزایی و پەیوەندی ڕوون پێکەوە دەبەستین.", "کوالێتی و متمانەپێکراوی بنەمای هەر هاوکارییەکن.", "بە زوویی وەڵامت دەدەینەوە.", "داواکارییەکەت بنێرە و باسی پڕۆژەکەت بۆمان بکە."], "ui": ["ئەمە پەڕەیەکی سەربەخۆیە بە هەمان دیزاینی کۆمپانیا.", "شوێنی وێنە: بەشی سەرەکی یان بەخێرهاتن", "یاسایی", "زانیاری خاوەن ماڵپەڕ", "پاراستنی نهێنی", "هەموو مافەکان پارێزراون.", "دیزاین و بەشەکان و پێکهاتەکە دەمێننەوە؛ ناوەڕۆک لە خانەکانی تێکردن دیاری دەکرێت.", "بەخێربێیت، چۆن دەتوانین یارمەتیت بدەین؟", "پرسیارەکەت بنووسە...", "ناردن", "سوپاس بۆ پرسیارەکەت", "بە خۆشحاڵییەوە پەیوەندیت پێوە دەکەین.", "یاریدەدەر", "کردنەوەی چات"], "defaults": ["قاڵبێکی ڕوون بە شوێن بۆ ناوەڕۆکەکەت.", "زانیاری کۆمپانیا و دەق و وێنەکان لەم قاڵبەدا بگۆڕە.", "پێشنیارەکەمان ببینە", "ئیمەیڵی پەیوەندیت", "بۆ کۆمپانیاکەت گونجێنراوە."]},
    }
    source = common.get(language, common["de"])
    nav_keys = ["start", "leistungen", "angebote", "projekte", "ueber_uns", "kontakt"]
    card_groups = [source["cards"][0:3], source["cards"][3:6], source["cards"][6:9], source["cards"][9:12], source["cards"][12:15]]
    text_groups = [[source["texts"][0], source["texts"][1], source["texts"][2]], ["", source["texts"][3], source["texts"][4]], [source["texts"][5], source["texts"][6], ""], [source["texts"][7], source["texts"][8], ""], ["", source["texts"][9], source["texts"][10]]]
    page_keys = nav_keys[1:]
    ui = source["ui"]
    return {"nav": dict(zip(nav_keys, source["nav"])), "pages": {key: [source["nav"][index + 1], source["page"][index], list(zip(card_groups[index], text_groups[index]))] for index, key in enumerate(page_keys)}, "pageHint": ui[0], "imagePlaceholder": ui[1], "contact": source["nav"][5], "legal": ui[2], "imprint": ui[3], "privacy": ui[4], "rights": ui[5], "designHint": ui[6], "welcome": ui[7], "question": ui[8], "send": ui[9], "thanks": ui[10], "reply": ui[11], "assistant": ui[12], "openChat": ui[13], "defaults": source["defaults"]}


def is_light_color(color: str) -> bool:
    """Ermittelt, ob eine Hex-Farbe eine dunkle Textfarbe benötigt."""
    color = color.lstrip("#")
    if len(color) != 6:
        return False

    red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    luminance = (red * 299 + green * 587 + blue * 114) / 1000
    return luminance >= 165


def contrast_text_color(background_color: str) -> str:
    """Liefert eine gut lesbare Textfarbe für eine farbige Fläche."""
    return "#111827" if is_light_color(background_color) else "#FFFFFF"


def render_template_preview(
        template_name: str,
    sections: str,
        background_color: str,
        accent_color: str,
        border_style: str,
    component_key: str = "clickable_template_editor",
) -> None:
    """Zeigt die Vorlage mit allen aktuell eingegebenen Kundendaten."""
    language = str(st.session_state.app_language)
    preview_copy = get_template_preview_copy(language)
    defaults = preview_copy["defaults"]
    radius = "0px" if border_style == "sharp" else "14px"
    light_background = is_light_color(background_color)
    text_color = "#111827" if light_background else "#f8fafc"
    muted_text_color = "#374151" if light_background else "#cbd5e1"
    surface_color = "rgba(17,24,39,.06)" if light_background else "rgba(255,255,255,.05)"
    border_color = "rgba(17,24,39,.18)" if light_background else "rgba(255,255,255,.16)"
    accent_text_color = contrast_text_color(accent_color)
    company_name = escape(str(st.session_state.get("client_company_name", "")).strip() or template_name)
    slogan = escape(
        str(st.session_state.get("template_hero_heading", "")).strip()
        or str(st.session_state.get("client_company_slogan", "")).strip()
        or "Eine Vorlage mit klarer Struktur und Raum für Ihre Inhalte."
    )
    description = escape(str(st.session_state.get("template_custom_description", "")).strip() or "Sie ersetzen Unternehmensdaten, Texte und Bilder direkt in dieser Vorlage. Die Gestaltung, Abstände und Inhaltsbereiche bleiben professionell geordnet.")
    business_email = escape(str(st.session_state.get("client_business_email", "")).strip() or "Ihre Kontakt-E-Mail")
    phone = escape(str(st.session_state.get("client_business_phone", "")).strip() or "Telefonnummer ergänzen")
    button_text = escape(
        str(st.session_state.get("template_button_text", "")).strip()
        or str(get_template_preview_copy(language)["defaults"][2])
    )
    image_file = st.session_state.get("initial_image")
    image_data_url = ""
    if image_file is not None:
        image_type = image_file.type or "image/png"
        image_data_url = (
            f"data:{image_type};base64,"
            f"{base64.b64encode(image_file.getvalue()).decode('ascii')}"
        )

    def save_clickable_template_changes() -> None:
        """Übernimmt eine im Klickeditor abgeschlossene Textänderung."""
        component_state = st.session_state.get(component_key)
        changes = getattr(component_state, "saved", None)
        if not isinstance(changes, dict):
            return
        fields = {
            "heading": "template_hero_heading",
            "description": "template_custom_description",
            "buttonText": "template_button_text",
        }
        for source, target in fields.items():
            if source in changes:
                st.session_state[target] = str(changes[source]).strip()

    def show_template_page() -> None:
        """Übernimmt den Navigationsklick aus der interaktiven Vorlagenvorschau."""
        component_state = st.session_state.get(component_key)
        page = getattr(component_state, "navigated", None)
        if page in {"start", "leistungen", "angebote", "projekte", "ueber_uns", "kontakt"}:
            st.session_state.template_preview_page = page

    CLICKABLE_TEMPLATE_EDITOR(
        key=component_key,
        data={
            "language": language,
            "direction": "rtl" if language in {"ar", "ku"} else "ltr",
            "copy": preview_copy,
            "companyName": str(st.session_state.get("client_company_name", "")).strip() or template_name,
            "heading": str(st.session_state.get("template_hero_heading", "")).strip()
            or str(st.session_state.get("client_company_slogan", "")).strip()
            or defaults[0],
            "description": str(st.session_state.get("template_custom_description", "")).strip()
            or defaults[1],
            "buttonText": str(st.session_state.get("template_button_text", "")).strip()
            or defaults[2],
            "templateSections": [
                {
                    "title": item.partition("|")[0].strip(),
                    "text": item.partition("|")[2].strip()
                    or str(st.session_state.get("template_custom_description", "")).strip()
                    or defaults[4],
                }
                for item in str(st.session_state.get("template_sections_text", sections)).replace(",", "\n").splitlines()
                if item.strip()
            ],
            "footerText": str(st.session_state.get("template_footer_text", "")).strip()
            or f"{company_name} | {business_email} | Impressum | Datenschutz",
            "chatbotKnowledge": get_configured_chatbot_knowledge(),
            "chatbotName": str(st.session_state.get("customer_chatbot_name", "")).strip(),
            "chatbotColor": str(st.session_state.get("customer_chatbot_color", "#2563EB")),
            "chatbotRadius": {"Rund (Kreis)": "50%", "Eckig mit Rundung": "8px", "Quadratisch": "0"}.get(str(st.session_state.get("customer_chatbot_shape", "Rund (Kreis)")), "50%"),
            "showCustomerChatbot": component_key == "full_draft_template_preview",
            "multiPage": st.session_state.get("page_structure") == "Mehrseitige Website",
            "businessEmail": str(st.session_state.get("client_business_email", "")).strip()
            or defaults[3],
            "page": str(st.session_state.get("template_preview_page", "start")),
            "imageDataUrl": image_data_url,
            "backgroundColor": background_color,
            "accentColor": accent_color,
            "textColor": text_color,
            "mutedTextColor": muted_text_color,
            "surfaceColor": surface_color,
            "borderColor": border_color,
            "accentTextColor": accent_text_color,
            "radius": radius,
        },
        on_saved_change=save_clickable_template_changes,
        on_navigated_change=show_template_page,
    )


@st.dialog("Live-Vorschau des Entwurfs", width="large")
def show_full_draft_preview() -> None:
    """Öffnet die vollständige, testbare Kundenvorschau vor der Veröffentlichung."""
    template_name = str(st.session_state.get("template_name", "Professionelle Vorlage"))
    template = TEMPLATES.get(template_name, {})
    background_name = str(st.session_state.get("template_background_preset", "Weiß"))
    render_template_preview(
        template_name,
        str(st.session_state.get("template_sections_text", template.get("sections", ""))),
        BACKGROUND_PRESET_COLORS.get(background_name, "#FFFFFF"),
        str(st.session_state.get("template_accent_color", "#38BDF8")),
        str(st.session_state.get("template_border_style", "rounded")),
        component_key="full_draft_template_preview",
    )
    st.caption("Prüfen Sie Inhalte, Navigation, Kontaktangaben und Chatbot. Änderungen werden als Entwurf übernommen.")


def render_template_and_design_ui() -> str:
    """Rendert die Branchenvorlagen fuer einen gefuehrten Website-Entwurf."""
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

    if st.session_state.get("template_preview_template") != selected_template_name:
        st.session_state.template_preview_template = selected_template_name
        st.session_state.template_preview_page = "start"

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

    render_template_preview(
        template_display_name,
        section_defaults.get(language, current_template["sections"]),
        background_color,
        accent_color,
        border_style,
    )

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


def get_creation_form_copy() -> dict[str, object]:
    """Returns localized labels for section selection and draft creation."""
    copy = {
        "de": ["4. Abschnitte und Inhalte", "Welche Bereiche soll die Website enthalten?", "Wählen Sie mindestens einen Abschnitt aus.", "Hauptüberschrift", "Untertitel oder Slogan", "Text für Über uns", "Leistungen oder Produkte, jeweils durch Komma trennen", "Projekt- oder Galeriebeschreibung", "Referenzen oder Vertrauensargumente", "Unternehmensbeschreibung und besondere Wünsche", "Beschreiben Sie Angebot, Zielgruppe, Standort und die wichtigsten Inhalte Ihrer Website.", "5. Bild und Entwurf erstellen", "Logo oder Bild hochladen (optional)", "Wo soll dieses Bild erscheinen?", "Vorlage mit Kundendaten übernehmen", "Website erstellen"],
        "en": ["4. Sections and content", "Which sections should the website include?", "Select at least one section.", "Main heading", "Subtitle or slogan", "About us text", "Services or products, separated by commas", "Project or gallery description", "References or trust indicators", "Company description and special requests", "Describe your offer, target audience, location, and the key content of your website.", "5. Create image and draft", "Upload logo or image (optional)", "Where should this image appear?", "Apply template with customer data", "Create website"],
        "ar": ["4. الأقسام والمحتوى", "ما الأقسام التي يجب أن يتضمنها الموقع؟", "اختر قسماً واحداً على الأقل.", "العنوان الرئيسي", "العنوان الفرعي أو الشعار", "نص من نحن", "الخدمات أو المنتجات، مفصولة بفواصل", "وصف المشاريع أو المعرض", "المراجع أو عناصر الثقة", "وصف الشركة والطلبات الخاصة", "صف عرضك والجمهور المستهدف والموقع وأهم محتويات موقعك.", "5. إنشاء الصورة والمسودة", "رفع شعار أو صورة (اختياري)", "أين يجب أن تظهر هذه الصورة؟", "اعتماد القالب مع بيانات العميل", "إنشاء الموقع"],
        "ku": ["4. بەشەکان و ناوەڕۆک", "وێبگەکە دەبێت کام بەشانە لەخۆبگرێت؟", "لانیکەم بەشێک هەڵبژێرە.", "سەردێڕی سەرەکی", "ژێرسەردێڕ یان دروشم", "دەقی دەربارەی ئێمە", "خزمەتگوزاری یان بەرهەمەکان، بە کۆما جیابکەرەوە", "وەسفی پڕۆژە یان گەلەری", "سەرچاوە یان هۆکاری متمانە", "وەسفی کۆمپانیا و داواکارییە تایبەتەکان", "پێشنیار، ئامانج، شوێن و گرنگترین ناوەڕۆکی وێبگەکەت باس بکە.", "5. دروستکردنی وێنە و ڕەشنووس", "بارکردنی لۆگۆ یان وێنە (ئارەزوومەندانە)", "ئەم وێنەیە لە کوێ دەربکەوێت؟", "بەکارهێنانی قاڵب بە زانیاریی کڕیار", "دروستکردنی وێبگە"],
        "es": ["4. Secciones y contenido", "¿Qué secciones debe incluir el sitio web?", "Seleccione al menos una sección.", "Título principal", "Subtítulo o eslogan", "Texto sobre nosotros", "Servicios o productos, separados por comas", "Descripción de proyectos o galería", "Referencias o argumentos de confianza", "Descripción de la empresa y requisitos especiales", "Describa su oferta, público objetivo, ubicación y contenidos principales.", "5. Crear imagen y borrador", "Subir logotipo o imagen (opcional)", "¿Dónde debe aparecer esta imagen?", "Aplicar plantilla con datos del cliente", "Crear sitio web"],
        "it": ["4. Sezioni e contenuti", "Quali sezioni deve includere il sito?", "Selezionate almeno una sezione.", "Titolo principale", "Sottotitolo o slogan", "Testo chi siamo", "Servizi o prodotti, separati da virgole", "Descrizione del progetto o della galleria", "Referenze o elementi di fiducia", "Descrizione dell'azienda e richieste speciali", "Descrivete l'offerta, il pubblico, la sede e i contenuti principali del sito.", "5. Crea immagine e bozza", "Carica logo o immagine (facoltativo)", "Dove deve apparire questa immagine?", "Applica il modello con i dati del cliente", "Crea sito web"],
        "hi": ["4. अनुभाग और सामग्री", "वेबसाइट में कौन से अनुभाग होने चाहिए?", "कम से कम एक अनुभाग चुनें।", "मुख्य शीर्षक", "उपशीर्षक या नारा", "हमारे बारे में पाठ", "सेवाएं या उत्पाद, अल्पविराम से अलग करें", "परियोजना या गैलरी का विवरण", "संदर्भ या विश्वास के आधार", "कंपनी का विवरण और विशेष अनुरोध", "अपने प्रस्ताव, लक्षित दर्शकों, स्थान और वेबसाइट की मुख्य सामग्री का वर्णन करें।", "5. चित्र और प्रारूप बनाएं", "लोगो या चित्र अपलोड करें (वैकल्पिक)", "यह चित्र कहां दिखाई देना चाहिए?", "ग्राहक डेटा के साथ टेम्पलेट लागू करें", "वेबसाइट बनाएं"],
    }
    labels = copy.get(str(st.session_state.app_language), copy["en"])
    section_names = {
        "de": ["Hero und Willkommensbereich", "Über uns", "Leistungen oder Produkte", "Galerie oder Projekte", "Kundenstimmen oder Referenzen", "Kontakt und Erreichbarkeit"],
        "en": ["Hero and welcome section", "About us", "Services or products", "Gallery or projects", "Testimonials or references", "Contact and availability"],
        "ar": ["الواجهة الرئيسية والترحيب", "من نحن", "الخدمات أو المنتجات", "المعرض أو المشاريع", "آراء العملاء أو المراجع", "الاتصال وإمكانية الوصول"],
        "ku": ["بەشی سەرەکی و بەخێرهاتن", "دەربارەی ئێمە", "خزمەتگوزاری یان بەرهەمەکان", "گەلەری یان پڕۆژەکان", "بۆچوونی کڕیاران یان سەرچاوەکان", "پەیوەندی و بەردەستبوون"],
        "es": ["Sección principal y bienvenida", "Sobre nosotros", "Servicios o productos", "Galería o proyectos", "Testimonios o referencias", "Contacto y disponibilidad"],
        "it": ["Sezione principale e benvenuto", "Chi siamo", "Servizi o prodotti", "Galleria o progetti", "Testimonianze o referenze", "Contatti e disponibilità"],
        "hi": ["मुख्य और स्वागत अनुभाग", "हमारे बारे में", "सेवाएं या उत्पाद", "गैलरी या परियोजनाएं", "ग्राहक राय या संदर्भ", "संपर्क और उपलब्धता"],
    }
    image_placements = {
        "de": ["Logo", "Hero- und Willkommensbereich", "Über-uns-Bereich", "Projektbereich"],
        "en": ["Logo", "Hero and welcome section", "About us section", "Project section"],
        "ar": ["الشعار", "الواجهة الرئيسية والترحيب", "قسم من نحن", "قسم المشاريع"],
        "ku": ["لۆگۆ", "بەشی سەرەکی و بەخێرهاتن", "بەشی دەربارەی ئێمە", "بەشی پڕۆژەکان"],
        "es": ["Logotipo", "Sección principal y bienvenida", "Sección sobre nosotros", "Sección de proyectos"],
        "it": ["Logo", "Sezione principale e benvenuto", "Sezione chi siamo", "Sezione progetti"],
        "hi": ["लोगो", "मुख्य और स्वागत अनुभाग", "हमारे बारे में अनुभाग", "परियोजना अनुभाग"],
    }
    return {
        "labels": labels,
        "sections": dict(zip(section_names["de"], section_names.get(str(st.session_state.app_language), section_names["en"]))),
        "placements": dict(zip(image_placements["de"], image_placements.get(str(st.session_state.app_language), image_placements["en"]))),
    }


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


def modify_current_website(change_request: str) -> None:
    """Ändert ausschließlich die angeforderten Bereiche der Website."""
    current_html = st.session_state.generated_html.strip()

    if not current_html:
        raise ValueError("Erstelle oder lade zuerst eine Website.")

    html = ask_ai_for_html(
        system_instruction=f"""
Du bist ein sorgfältiger Frontend-Entwickler.

Bearbeite ausschließlich die angeforderte Änderung in einer bestehenden Website.

Regeln:
- Antworte nur mit vollständigem HTML5, beginnend mit <!doctype html>.
- Kein Markdown, keine Backticks und keine Erklärung.
- Bestehende Texte, Bilder, Links, Bereiche und Styles bleiben erhalten,
  sofern ihre Änderung nicht ausdrücklich verlangt wird.
- Tailwind CSS muss erhalten bleiben.

Kontaktformular und Chatbot:
- Behalte einen vorhandenen Web3Forms-Endpunkt, Access Key und alle versteckten Felder
    vollstaendig unveraendert, sofern ihre Aenderung nicht ausdruecklich verlangt wird.
- Behalte die sichtbaren Pflichtfelder `name`, `email` und `message` mit ihren
    required-Attributen bei.
- Behalte den unternehmensspezifischen Chatbot mit Voice-Funktion und die konfigurierte
    Kontakt-E-Mail unveraendert bei.
- Behalte das Design des Kontaktbereichs bei.
""",
        user_instruction=f"""
AKTUELLER HTML-CODE:
{current_html}

GEWÜNSCHTE ÄNDERUNG:
{change_request}
""",
    )

    queue_html_update(html)


def render_editor() -> None:
    """Rendert den kombinierten Design- und Abschnittseditor."""
    st.subheader("Live-Design und Abschnittseditor")

    color_columns = st.columns(2)
    with color_columns[0]:
        background_color = st.color_picker(
            "Hintergrundfarbe",
            "#111827",
            key="editor_background_color",
        )
    with color_columns[1]:
        accent_color = st.color_picker(
            "Akzentfarbe fuer Buttons",
            "#38BDF8",
            key="editor_accent_color",
        )

    section = st.selectbox(
        "Bereich bearbeiten",
        [
            "Hero",
            "Ueber mich",
            "Faehigkeiten und Services",
            "Projekte",
            "Kontakt und Footer",
        ],
        key="editor_section",
    )
    instructions = st.text_area(
        f"Aenderungswunsch fuer '{section}'",
        placeholder=(
            "Zum Beispiel: Aendere die Hintergrundfarbe dieses Bereichs "
            "oder fuege ein Bild hinzu."
        ),
        key="editor_instructions",
        height=130,
    )

    if st.button(
        "Abschnitt aktualisieren",
        icon=":material/refresh:",
        type="primary",
        key="update_live_editor_section",
        width="stretch",
    ):
        if not instructions or not instructions.strip():
            st.warning("Bitte beschreibe die gewuenschte Aenderung.")
            return

        with st.status("Abschnitt wird aktualisiert ...", expanded=True) as status:
            try:
                modify_current_website(
                    f"Aendere ausschliesslich den Bereich '{section}' basierend auf: "
                    f"{instructions.strip()}. Beachte das globale Farbschema: "
                    f"Hintergrund {background_color}, Akzent {accent_color}."
                )
                status.update(label="Abschnitt wurde aktualisiert.", state="complete")
                st.rerun()
            except Exception as error:
                status.update(label="Aktualisierung fehlgeschlagen", state="error")
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
            st.success("Das Bild wurde in der Vorschau ersetzt.")
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
                    st.success("Die Textstelle wurde aktualisiert.")
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
                updated_html, replacements = re.subn(
                    r"(?i)(<a\b[^>]*href=[\"'])#[^\"']*([\"'][^>]*>)",
                    rf"\1{target_url}\2",
                    st.session_state.generated_html,
                    count=1,
                )
                if not replacements:
                    st.error("Im Entwurf wurde kein konfigurierbarer Button-Link gefunden.")
                else:
                    st.session_state.generated_html = updated_html
                    st.session_state.html_editor = updated_html
                    st.success("Das Button-Ziel wurde aktualisiert.")
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
            st.success("Die Angebots-Unterseite wurde zur Website ergänzt.")
            st.rerun()


def update_preview_from_test_editor() -> None:
    """Uebernimmt geprueften HTML-Code aus dem Testzentrum in die Vorschau."""
    st.session_state.generated_html = require_complete_html(
        str(st.session_state.preview_html_editor)
    )
    st.session_state.html_editor = st.session_state.generated_html


def discard_test_editor_changes() -> None:
    """Stellt den Testeditor auf den aktuell gespeicherten Entwurf zurueck."""
    st.session_state.preview_html_editor = st.session_state.generated_html


def render_saas_preview_and_testing_window() -> None:
    """Rendert die direkte Vorschau und optionale HTML-Feinbearbeitung."""
    if (
        st.session_state.get("creation_mode") == "Professionelle Vorlage"
        and not st.session_state.generated_html
    ):
        return

    st.header("Live-Vorschau")

    if not st.session_state.generated_html:
        st.info(
            "Erstellen oder laden Sie zuerst eine Website. Ihre Vorschau erscheint anschließend hier."
        )
        return

    preview_height = st.slider(
        "Vorschauhöhe",
        min_value=400,
        max_value=1200,
        value=650,
        step=50,
        key="live_preview_height",
    )
    st.components.v1.html(
        create_preview_html(st.session_state.generated_html),
        height=preview_height,
        scrolling=True,
    )

    with st.expander("HTML-Code und Details direkt anpassen", icon=":material/code:"):
        st.subheader("HTML-Code fein abstimmen")
        st.session_state.setdefault(
            "preview_html_editor", st.session_state.generated_html
        )
        st.text_area(
            "HTML und Design-Code",
            key="preview_html_editor",
            height=400,
        )
        apply_column, discard_column = st.columns(2)
        with apply_column:
            if st.button(
                "Aenderungen in Vorschau uebernehmen",
                icon=":material/refresh:",
                key="apply_preview_html",
                width="stretch",
            ):
                try:
                    update_preview_from_test_editor()
                    st.success("Die Änderungen wurden in die Vorschau übernommen.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        with discard_column:
            if st.button(
                "Manuelle Aenderungen verwerfen",
                icon=":material/delete:",
                key="discard_preview_html",
                width="stretch",
            ):
                discard_test_editor_changes()
                st.rerun()


def is_vercel_login_page(response: requests.Response) -> bool:
    """Erkennt Vercel-Login- und Deployment-Schutzseiten."""
    content = response.text.lower()
    url = response.url.lower()

    markers = [
        "vercel.com/login",
        "<title>log in to vercel</title>",
        "continue with github",
        "continue with google",
        "continue with chatgpt",
        "deployment protection",
        "vercel authentication",
    ]

    return any(marker in url or marker in content for marker in markers)


def load_published_website(live_url: str) -> None:
    """Lädt eine öffentliche Website unverändert, ohne KI-Bearbeitung."""
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
        raise ValueError(
            f"Die Website konnte nicht erreicht werden: {error}"
        ) from error

    if is_vercel_login_page(response):
        raise ValueError(
            "Die Website ist durch Vercel geschützt oder verlangt eine Anmeldung."
        )

    if response.status_code != 200:
        raise ValueError(
            f"Die Website konnte nicht geladen werden. HTTP {response.status_code}."
        )

    html = require_complete_html(response.text)

    st.session_state.assets = {}
    st.session_state.live_url = response.url
    st.session_state.deployment_url = response.url

    # Projektname nicht automatisch aus einer Deployment-URL ableiten.
    # Der richtige Projektname wird im Feld „Vercel-Projektname“ eingegeben.
    st.session_state.published_html = html
    st.session_state.pending_html = html

    # Geladene fremde Seiten dürfen über die App nicht gelöscht werden.
    st.session_state.deployment_id = ""


def load_uploaded_html_template(uploaded_file) -> None:
    """Übernimmt eine lokale HTML-Vorlage als bearbeitbaren Entwurf."""
    if uploaded_file is None:
        raise ValueError("Bitte wählen Sie eine HTML-Datei aus.")

    try:
        html = uploaded_file.getvalue().decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Die Vorlage muss als UTF-8 codierte HTML-Datei vorliegen.") from error

    st.session_state.assets = {}
    st.session_state.live_url = ""
    st.session_state.deployment_url = ""
    st.session_state.deployment_id = ""
    st.session_state.project_name = safe_project_name(Path(uploaded_file.name).stem)
    st.session_state.pending_html = require_complete_html(html)


def get_public_url(deployment: dict) -> str:
    """Ermittelt die öffentliche URL aus einer Vercel-Deployment-Antwort."""
    aliases = deployment.get("alias") or []
    deployment_url = deployment.get("url")

    if aliases:
        return f"https://{aliases[0]}"

    if deployment_url:
        return f"https://{deployment_url}"

    raise ValueError("Vercel hat keine öffentliche Deployment-URL geliefert.")


def check_custom_domain_with_mcp(domain_name: str) -> dict[str, str | bool]:
    """Calls the local MCP domain tool and returns its structured result."""
    async def run_check() -> dict[str, str | bool]:
        async with Client(website_mcp_server) as client:
            result = await client.call_tool(
                "check_domain_availability",
                {
                    "domain_name": domain_name,
                    "language": str(st.session_state.app_language),
                },
            )
            content = result.structured_content
            if not isinstance(content, dict):
                raise ValueError("Der MCP-Server hat kein gültiges Domain-Ergebnis geliefert.")
            return content

    try:
        return asyncio.run(run_check())
    except Exception as error:
        raise ValueError(f"Die MCP-Domainprüfung ist fehlgeschlagen: {error}") from error


def update_draft_with_mcp_tool(tool_name: str, arguments: dict[str, str]) -> str:
    """Runs a local MCP content tool and returns its updated customer HTML."""
    async def run_tool() -> dict[str, str]:
        async with Client(website_mcp_server) as client:
            result = await client.call_tool(tool_name, arguments)
            content = result.structured_content
            if not isinstance(content, dict) or not isinstance(content.get("html"), str):
                raise ValueError("Der MCP-Server hat keinen gültigen HTML-Entwurf geliefert.")
            return content

    try:
        result = asyncio.run(run_tool())
    except Exception as error:
        raise ValueError(f"Die MCP-Inhaltsbearbeitung ist fehlgeschlagen: {error}") from error
    return str(result["html"])


def get_industry_chatbot_profile_with_mcp(industry: str) -> dict[str, str]:
    """Loads editable chatbot defaults from the local MCP server."""
    async def run_tool() -> dict[str, str]:
        async with Client(website_mcp_server) as client:
            result = await client.call_tool(
                "get_industry_chatbot_profile",
                {"industry": industry, "language": str(st.session_state.app_language)},
            )
            content = result.structured_content
            if not isinstance(content, dict):
                raise ValueError("Der MCP-Server hat kein Chatbot-Profil geliefert.")
            return {
                key: str(value).strip()
                for key, value in content.items()
                if isinstance(value, str)
            }

    try:
        return asyncio.run(run_tool())
    except Exception:
        return {}


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
                st.success(copy[8].format(section=selected_section_label))
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
                st.success(copy[10])
                st.rerun()
            except ValueError as error:
                st.error(str(error))


def wait_for_vercel_deployment(deployment_id: str, timeout_seconds: int = 90) -> dict:
    """Wartet auf den abschließenden Vercel-Status vor der Weiterleitung."""
    deadline = time.monotonic() + timeout_seconds
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}

    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"https://api.vercel.com/v13/deployments/{deployment_id}",
                headers=headers,
                timeout=20,
            )
        except requests.RequestException as error:
            raise ValueError(f"Vercel-Status konnte nicht geprüft werden: {error}") from error

        if response.status_code != 200:
            raise ValueError(f"Vercel-Statusprüfung fehlgeschlagen: HTTP {response.status_code}.")

        deployment = response.json()
        state = str(deployment.get("readyState", "")).upper()
        if state == "READY":
            return deployment
        if state in {"ERROR", "CANCELED"}:
            raise ValueError("Vercel konnte die Website nicht veröffentlichen.")
        time.sleep(2)

    raise ValueError("Vercel benötigt länger als erwartet. Bitte öffnen Sie den Live-Link in wenigen Minuten.")

def delete_published_website() -> None:
    """Löscht nur das letzte Deployment aus der aktuellen Sitzung."""
    deployment_id = st.session_state.deployment_id

    if not deployment_id:
        raise ValueError("Kein Deployment aus dieser Sitzung zum Löschen vorhanden.")

    try:
        response = requests.delete(
            f"https://api.vercel.com/v13/deployments/{deployment_id}",
            headers={"Authorization": f"Bearer {VERCEL_TOKEN}"},
            timeout=60,
        )
    except requests.RequestException as error:
        raise ValueError(f"Vercel konnte nicht erreicht werden: {error}") from error

    if response.status_code not in (200, 202, 204):
        raise ValueError(f"Vercel HTTP {response.status_code}: {response.text}")

    st.session_state.live_url = ""
    st.session_state.deployment_url = ""
    st.session_state.deployment_id = ""
    st.session_state.published_html = ""


def delete_previous_vercel_deployment(deployment_reference: str) -> None:
    """Löscht ein älteres Deployment anhand seiner Vercel-URL oder Deployment-ID."""
    reference = deployment_reference.strip()
    if not reference:
        raise ValueError("Geben Sie die Vercel-URL oder Deployment-ID der alten Website ein.")

    parsed_url = urlparse(reference if "://" in reference else f"https://{reference}")
    deployment_lookup = parsed_url.netloc or reference
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        lookup_response = requests.get(
            f"https://api.vercel.com/v13/deployments/{quote(deployment_lookup, safe='')}",
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as error:
        raise ValueError(f"Vercel konnte nicht erreicht werden: {error}") from error

    if lookup_response.status_code != 200:
        raise ValueError("Die alte Vercel-Veröffentlichung wurde nicht gefunden oder gehört nicht zu diesem Konto.")

    deployment_id = str(lookup_response.json().get("id", "")).strip()
    if not deployment_id:
        raise ValueError("Vercel hat keine Deployment-ID für diese Veröffentlichung geliefert.")

    try:
        delete_response = requests.delete(
            f"https://api.vercel.com/v13/deployments/{deployment_id}",
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as error:
        raise ValueError(f"Vercel konnte nicht erreicht werden: {error}") from error

    if delete_response.status_code not in (200, 202, 204):
        raise ValueError(f"Vercel HTTP {delete_response.status_code}: {delete_response.text}")


def configure_vercel_chatbot_environment(project_id: str) -> str:
    """Hinterlegt den serverseitigen Chatbot-Schlüssel im Kundenprojekt."""
    if not HF_API_KEY:
        return "HF_API_KEY ist nicht in den Streamlit-Secrets hinterlegt. Der Kundenchatbot verwendet Branchenwissen als Rückfallantwort."

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "key": "HF_API_KEY",
        "value": HF_API_KEY,
        "type": "encrypted",
        "target": ["production", "preview", "development"],
    }
    try:
        environment_variables = requests.get(
            f"https://api.vercel.com/v9/projects/{project_id}/env",
            headers=headers,
            timeout=30,
        )
        environment_variables.raise_for_status()
        existing_variables = environment_variables.json().get("envs", [])
        existing_key = next(
            (
                str(item.get("id", ""))
                for item in existing_variables
                if item.get("key") == "HF_API_KEY"
            ),
            "",
        )
        if existing_key:
            response = requests.patch(
                f"https://api.vercel.com/v9/projects/{project_id}/env/{existing_key}",
                headers=headers,
                json=payload,
                timeout=30,
            )
        else:
            response = requests.post(
                f"https://api.vercel.com/v10/projects/{project_id}/env",
                headers=headers,
                json=payload,
                timeout=30,
            )
    except requests.RequestException as error:
        return f"Die automatische Chatbot-Konfiguration konnte Vercel nicht erreichen: {error}"

    if response.status_code in (200, 201):
        return ""
    try:
        details = response.json().get("error", {}).get("message", "")
    except ValueError:
        details = ""
    detail_suffix = f" Vercel meldet: {details}" if details else ""
    return (
        f"Die automatische Chatbot-Konfiguration ist fehlgeschlagen (HTTP {response.status_code})."
        f" Die Website wurde trotzdem veröffentlicht; der Chatbot verwendet Branchenwissen als Rückfallantwort.{detail_suffix}"
    )

    
def publish_website() -> None:
    """Veröffentlicht den aktuellen HTML-Entwurf auf Vercel."""
    html = inject_configured_customer_chatbot(
        require_complete_html(st.session_state.generated_html)
    )
    st.session_state.generated_html = html
    st.session_state.html_editor = html
    requested_project_name = str(st.session_state.project_name).strip()
    project_name = (
        safe_project_name(requested_project_name)
        if requested_project_name
        else create_deployment_project_name()
    )
    st.session_state.project_name = project_name

    site_pages = dict(st.session_state.site_pages) or {"index.html": html}
    site_pages["index.html"] = html
    site_pages = {
        file_name: (
            inject_configured_customer_chatbot(require_complete_html(page_content))
            if file_name.endswith(".html")
            else page_content
        )
        for file_name, page_content in site_pages.items()
    }
    st.session_state.site_pages = site_pages
    site_pages = add_vercel_chat_api(site_pages)
    files = [
        {
            "file": file_name,
            "data": (
                require_complete_html(page_content)
                if file_name.endswith(".html")
                else page_content
            ),
        }
        for file_name, page_content in site_pages.items()
    ]

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

    try:
        deployment = response.json()
    except ValueError as error:
        raise ValueError(
            "Vercel hat keine gültige JSON-Antwort zurückgegeben."
        ) from error

    deployment_id = deployment.get("id")
    deployment_url = deployment.get("url")

    if not deployment_id or not deployment_url:
        raise ValueError(f"Unvollständige Vercel-Antwort: {deployment}")

    project_id = str(deployment.get("projectId", "")).strip()
    st.session_state.vercel_project_id = project_id
    if project_id:
        environment_warning = configure_vercel_chatbot_environment(project_id)
        st.session_state.chatbot_environment_warning = environment_warning
        if not environment_warning and HF_API_KEY:
            try:
                redeploy_response = requests.post(
                    VERCEL_DEPLOYMENTS_URL,
                    headers={
                        "Authorization": f"Bearer {VERCEL_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=90,
                )
                redeploy_response.raise_for_status()
                redeployment = redeploy_response.json()
                deployment_id = str(redeployment.get("id", "")).strip()
                deployment_url = str(redeployment.get("url", "")).strip()
                if not deployment_id or not deployment_url:
                    raise ValueError("Vercel hat keine vollständigen Daten für das Chatbot-Deployment geliefert.")
            except (requests.RequestException, ValueError) as error:
                raise ValueError(
                    f"Der Chatbot-Schlüssel wurde gesetzt, aber das aktive Deployment konnte nicht erneuert werden: {error}"
                ) from error

    deployment = wait_for_vercel_deployment(deployment_id)

    # project_name hier NICHT verändern: Es gehört zum Streamlit-Textfeld.
    st.session_state.live_url = get_public_url(deployment)
    st.session_state.deployment_url = f"https://{deployment_url}"
    st.session_state.deployment_id = deployment_id
    st.session_state.published_html = html


def render_domain_and_deployment_ui() -> None:
    """Rendert die Premium-geschuetzte Konfiguration fuer die Vercel-Veröffentlichung."""
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
    domain_options = ["Vercel-Projektadresse", "Eigene Domain verbinden"]
    domain_option_labels = dict(zip(domain_options, domain_labels[4:6]))
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
    }.get(language)
    if old_publication_copy is None:
        old_publication_copy = []
    custom_domain_copy = {
        "de": ["Domain kaufen und verbinden: Anleitung", "1. Geben Sie unten Ihre gewünschte Domain ohne Pfad ein, zum Beispiel `mein-betrieb.de`.\n2. Prüfen Sie mit MCP, ob für die Domain bereits ein öffentlicher RDAP-Eintrag besteht.\n3. Kaufen Sie eine freie Domain direkt bei einem Domainanbieter Ihrer Wahl.\n4. Fügen Sie die Domain anschließend in Vercel hinzu und übernehmen Sie die dort angezeigten DNS-Einträge beim Domainanbieter.", "Preisorientierung: Eine .de-Domain kostet häufig etwa 5-20 EUR pro Jahr, eine .com-Domain etwa 10-25 EUR pro Jahr. Aktionspreise gelten oft nur im ersten Jahr; prüfen Sie deshalb immer den Verlängerungspreis und die Mehrwertsteuer.", "Die App kauft keine Domain automatisch und bucht dafür nichts ab. Der Domainanbieter berechnet die Domain separat. Ein App-Abonnement und mögliche Vercel-Kosten sind ebenfalls getrennte Verträge.", "Offizielle Vercel-Anleitung zur Domain-Verbindung", "Gewünschte oder bereits gekaufte Domain", "z. B. www.mein-unternehmen.de", "Die MCP-Prüfung ist ein Hinweis anhand öffentlicher Registrierungsdaten und keine Kaufgarantie.", "Geplante Domain: {domain}", "Eigene Domain per MCP prüfen", "MCP prüft die Domain ...", "Nächster Schritt: {step}"],
        "en": ["Buy and connect a domain: instructions", "1. Enter your preferred domain without a path, for example `my-business.com`.\n2. Use MCP to check whether a public RDAP record already exists.\n3. Buy an available domain from a provider of your choice.\n4. Add the domain to Vercel and copy the displayed DNS records to your domain provider.", "Price guide: a .de domain often costs about EUR 5-20 per year and a .com domain about EUR 10-25 per year. Promotional prices often apply only to the first year, so check renewal prices and taxes.", "The app does not buy or charge for a domain automatically. The domain provider bills it separately. The app subscription and possible Vercel costs are separate agreements.", "Official Vercel domain connection guide", "Preferred or already purchased domain", "e.g. www.my-company.com", "The MCP check uses public registration data as guidance and is not a purchase guarantee.", "Planned domain: {domain}", "Check own domain with MCP", "MCP is checking the domain ...", "Next step: {step}"],
        "ar": ["شراء نطاق وربطه: التعليمات", "1. أدخل النطاق المطلوب أدناه من دون مسار، مثل `my-business.com`.\n2. استخدم MCP للتحقق من وجود سجل RDAP عام للنطاق.\n3. اشترِ النطاق المتاح مباشرة من مزود تختاره.\n4. أضف النطاق إلى Vercel وانسخ سجلات DNS المعروضة إلى مزود النطاق.", "دليل الأسعار: يكلف نطاق .de عادةً نحو 5-20 يورو سنوياً، ونطاق .com نحو 10-25 يورو سنوياً. غالباً ما تسري الأسعار الترويجية في السنة الأولى فقط، لذا تحقق من سعر التجديد والضرائب.", "لا يشتري التطبيق أي نطاق تلقائياً ولا يخصم رسوماً مقابله. يحاسب مزود النطاق بشكل منفصل. كما أن اشتراك التطبيق وتكاليف Vercel المحتملة عقود منفصلة.", "دليل Vercel الرسمي لربط النطاق", "النطاق المطلوب أو الذي تم شراؤه", "مثال: www.my-company.com", "يعتمد فحص MCP على بيانات التسجيل العامة للإرشاد ولا يضمن إمكانية الشراء.", "النطاق المخطط: {domain}", "فحص النطاق الخاص باستخدام MCP", "يفحص MCP النطاق...", "الخطوة التالية: {step}"],
        "ku": ["کڕین و بەستنەوەی دۆمەین: ڕێنمایی", "1. دۆمەینی دڵخوازت بەبێ ڕێڕەو بنووسە، بۆ نموونە `my-business.com`.\n2. بە MCP بپشکنە کە تۆمارێکی گشتی RDAP هەیە یان نا.\n3. دۆمەینی بەردەست لە دابینکەرێکی هەڵبژێردراو بکڕە.\n4. دۆمەینەکە لە Vercel زیاد بکە و تۆمارەکانی DNS بگوازەرەوە بۆ دابینکەری دۆمەین.", "ڕێنمایی نرخ: دۆمەینی .de زۆرجار ساڵانە نزیکەی 5-20 یۆرۆ و .com نزیکەی 10-25 یۆرۆیە. نرخی داشکاندن زۆرجار تەنها بۆ ساڵی یەکەمە؛ نرخی نوێکردنەوە و باج بپشکنە.", "ئەپەکە خۆکارانە دۆمەین ناکڕێت و هیچ پارەیەک بۆی وەرناگرێت. دابینکەری دۆمەین جیاواز هەژمار دەکات. بەشداریکردنی ئەپ و خەرجییەکانی Vercel گرێبەستی جیاوازن.", "ڕێنمایی فەرمی Vercel بۆ بەستنەوەی دۆمەین", "دۆمەینی دڵخواز یان پێشتر کڕدراو", "بۆ نموونە: www.my-company.com", "پشکنینی MCP تەنها ڕێنماییە بە پشتبەستن بە زانیاری تۆماری گشتی و دڵنیایی کڕین نییە.", "دۆمەینی پلانکراو: {domain}", "پشکنینی دۆمەینی خۆت بە MCP", "MCP دۆمەینەکە دەپشکنێت...", "هەنگاوی داهاتوو: {step}"],
        "es": ["Comprar y conectar un dominio: instrucciones", "1. Introduzca el dominio deseado sin ruta, por ejemplo `mi-empresa.com`.\n2. Compruebe con MCP si ya existe un registro RDAP público.\n3. Compre un dominio disponible al proveedor que prefiera.\n4. Añada el dominio a Vercel y copie los registros DNS mostrados al proveedor.", "Guía de precios: un dominio .de suele costar entre 5 y 20 EUR al año y un .com entre 10 y 25 EUR. Las promociones suelen aplicarse solo el primer año; compruebe la renovación y los impuestos.", "La aplicación no compra ni cobra dominios automáticamente. El proveedor factura el dominio por separado. La suscripción de la aplicación y los posibles costes de Vercel son contratos independientes.", "Guía oficial de Vercel para conectar dominios", "Dominio deseado o ya adquirido", "p. ej. www.mi-empresa.com", "La comprobación MCP se basa en datos públicos y no garantiza la compra.", "Dominio previsto: {domain}", "Comprobar dominio propio con MCP", "MCP está comprobando el dominio...", "Siguiente paso: {step}"],
        "it": ["Acquistare e collegare un dominio: istruzioni", "1. Inserite il dominio desiderato senza percorso, ad esempio `mia-azienda.com`.\n2. Verificate con MCP se esiste già un record RDAP pubblico.\n3. Acquistate un dominio disponibile dal provider preferito.\n4. Aggiungete il dominio a Vercel e copiate i record DNS mostrati nel provider.", "Guida ai prezzi: un dominio .de costa spesso circa 5-20 EUR l'anno e un .com circa 10-25 EUR. Le promozioni valgono spesso solo il primo anno; controllate rinnovo e imposte.", "L'app non acquista né addebita automaticamente un dominio. Il provider lo fattura separatamente. L'abbonamento dell'app e gli eventuali costi Vercel sono contratti distinti.", "Guida ufficiale Vercel al collegamento del dominio", "Dominio desiderato o già acquistato", "ad es. www.mia-azienda.com", "Il controllo MCP usa dati pubblici a scopo indicativo e non garantisce l'acquisto.", "Dominio previsto: {domain}", "Controlla il dominio con MCP", "MCP sta controllando il dominio...", "Passo successivo: {step}"],
        "hi": ["डोमेन खरीदें और जोड़ें: निर्देश", "1. नीचे बिना पथ के अपना पसंदीदा डोमेन लिखें, जैसे `my-business.com`।\n2. MCP से जांचें कि सार्वजनिक RDAP रिकॉर्ड मौजूद है या नहीं।\n3. अपनी पसंद के प्रदाता से उपलब्ध डोमेन खरीदें।\n4. डोमेन को Vercel में जोड़ें और दिखाए गए DNS रिकॉर्ड प्रदाता में दर्ज करें।", "मूल्य मार्गदर्शिका: .de डोमेन प्रायः 5-20 EUR और .com डोमेन 10-25 EUR प्रति वर्ष होता है। प्रचार मूल्य अक्सर केवल पहले वर्ष के लिए होते हैं; नवीनीकरण मूल्य और कर जांचें।", "ऐप अपने आप डोमेन नहीं खरीदता और शुल्क नहीं लेता। डोमेन प्रदाता अलग बिल देता है। ऐप सदस्यता और संभावित Vercel लागत अलग अनुबंध हैं।", "डोमेन जोड़ने की आधिकारिक Vercel मार्गदर्शिका", "पसंदीदा या पहले से खरीदा हुआ डोमेन", "उदा. www.my-company.com", "MCP जांच सार्वजनिक पंजीकरण डेटा पर आधारित संकेत है और खरीद की गारंटी नहीं है।", "नियोजित डोमेन: {domain}", "MCP से अपना डोमेन जांचें", "MCP डोमेन की जांच कर रहा है...", "अगला कदम: {step}"],
    }.get(language)
    if custom_domain_copy is None:
        custom_domain_copy = []
    automated_domain_copy = {
        "de": ["Domain wird geprüft ...", "Jetzt kaufen & veröffentlichen", "Website und sicherer Checkout werden vorbereitet ...", "Sichere Zahlung öffnen", "Der automatische Domainkauf ist momentan nicht verfügbar.", "{domain} ist verfügbar.", "{domain} ist nicht verfügbar.", "Wunschdomain prüfen", "Nach erfolgreicher Zahlung wird Ihre Domain automatisch registriert, verbunden und mit SSL veröffentlicht."],
        "en": ["Checking domain ...", "Buy & publish now", "Preparing your website and secure checkout ...", "Open secure payment", "Automated domain purchasing is currently unavailable.", "{domain} is available.", "{domain} is unavailable.", "Check preferred domain", "After successful payment, your domain is registered, connected, and published with SSL automatically."],
        "ar": ["جارٍ التحقق من النطاق...", "الشراء والنشر الآن", "جارٍ إعداد موقعك والدفع الآمن...", "فتح الدفع الآمن", "شراء النطاق تلقائياً غير متاح حالياً.", "النطاق {domain} متاح.", "النطاق {domain} غير متاح.", "التحقق من النطاق المطلوب", "بعد نجاح الدفع، يتم تسجيل نطاقك وربطه ونشره مع SSL تلقائياً."],
        "ku": ["دۆمەینەکە دەپشکنرێت...", "ئێستا بیکڕە و بڵاوی بکەرەوە", "وێبگە و پارەدانی پارێزراو ئامادە دەکرێت...", "کردنەوەی پارەدانی پارێزراو", "کڕینی خۆکاری دۆمەین لە ئێستادا بەردەست نییە.", "{domain} بەردەستە.", "{domain} بەردەست نییە.", "پشکنینی دۆمەینی دڵخواز", "دوای پارەدانی سەرکەوتوو، دۆمەینەکەت خۆکارانە تۆمار و پەیوەست و بە SSL بڵاودەکرێتەوە."],
        "es": ["Comprobando dominio...", "Comprar y publicar ahora", "Preparando su sitio y el pago seguro...", "Abrir pago seguro", "La compra automática de dominios no está disponible actualmente.", "{domain} está disponible.", "{domain} no está disponible.", "Comprobar dominio deseado", "Tras el pago, su dominio se registra, conecta y publica con SSL automáticamente."],
        "it": ["Verifica del dominio...", "Acquista e pubblica ora", "Preparazione del sito e del pagamento sicuro...", "Apri pagamento sicuro", "L'acquisto automatico del dominio non è al momento disponibile.", "{domain} è disponibile.", "{domain} non è disponibile.", "Verifica dominio desiderato", "Dopo il pagamento, il dominio viene registrato, collegato e pubblicato con SSL automaticamente."],
        "hi": ["डोमेन जांचा जा रहा है...", "अभी खरीदें और प्रकाशित करें", "वेबसाइट और सुरक्षित भुगतान तैयार हो रहा है...", "सुरक्षित भुगतान खोलें", "स्वचालित डोमेन खरीद अभी उपलब्ध नहीं है।", "{domain} उपलब्ध है।", "{domain} उपलब्ध नहीं है।", "पसंदीदा डोमेन जांचें", "सफल भुगतान के बाद आपका डोमेन स्वतः पंजीकृत, कनेक्ट और SSL सहित प्रकाशित होगा।"],
    }.get(language, [])
    domain_input_copy = {
        "de": ["Ihre Wunschdomain", "z. B. noor.com", "Geben Sie nur Ihren gewünschten Domainnamen ein.", "Gewünschte Domain: {domain}"],
        "en": ["Your preferred domain", "e.g. noor.com", "Enter only your preferred domain name.", "Preferred domain: {domain}"],
        "ar": ["النطاق المطلوب", "مثال: noor.com", "أدخل اسم النطاق الذي تريده فقط.", "النطاق المطلوب: {domain}"],
        "ku": ["دۆمەینی دڵخوازت", "بۆ نموونە: noor.com", "تەنها ناوی دۆمەینی دڵخوازت بنووسە.", "دۆمەینی دڵخواز: {domain}"],
        "es": ["Su dominio deseado", "p. ej. noor.com", "Introduzca únicamente el nombre de dominio deseado.", "Dominio deseado: {domain}"],
        "it": ["Il dominio desiderato", "ad es. noor.com", "Inserite solo il nome del dominio desiderato.", "Dominio desiderato: {domain}"],
        "hi": ["आपका पसंदीदा डोमेन", "उदा. noor.com", "केवल अपना पसंदीदा डोमेन नाम दर्ज करें।", "पसंदीदा डोमेन: {domain}"],
    }.get(language, [])
    st.header(labels["title"])

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
                    if INWX_USERNAME and INWX_PASSWORD:
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
                except ValueError as error:
                    st.error(str(error))
                except ProvisioningError as error:
                    st.error(str(error))
        domain_check = st.session_state.get("domain_check_result")
        if isinstance(domain_check, dict) and domain_check.get("domain"):
            checked_domain = str(domain_check.get("domain", ""))
            if checked_domain == custom_domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/"):
                if domain_check.get("next_step"):
                    st.info(custom_domain_copy[11].format(step=domain_check["next_step"]))
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
        if st.button(
            automated_domain_copy[1],
            icon=":material/shopping_cart_checkout:",
            type="primary",
            disabled=not domain_available,
            key="buy_and_publish_custom_domain",
            width="stretch",
        ):
            with st.status(automated_domain_copy[2], expanded=True) as status:
                try:
                    st.session_state.project_name = create_deployment_project_name()
                    publish_website()
                    project_id = str(st.session_state.vercel_project_id).strip()
                    if not project_id:
                        raise ValueError("Vercel hat keine Projekt-ID geliefert.")
                    st.session_state.stripe_checkout_url = create_stripe_checkout_session(
                        current_user_id,
                        st.session_state.user_email,
                        str(domain_check["domain"]),
                        project_id,
                    )
                    status.update(label=automated_domain_copy[3], state="complete")
                except (ValueError, ProvisioningError) as error:
                    status.update(label=action_labels[11], state="error")
                    st.error(str(error))
        custom_checkout_url = str(st.session_state.get("stripe_checkout_url", ""))
        if domain_available and custom_checkout_url:
            st.link_button(
                automated_domain_copy[3],
                custom_checkout_url,
                icon=":material/lock:",
                type="primary",
                width="stretch",
            )

    if not user_info["subscribed"] and not user_info["trial_active"]:
        st.warning(
            "Ihre kostenlose 24-Stunden-Testphase ist abgelaufen. Mit Premium können Sie "
            "Ihre Website veröffentlichen."
        )
        render_payment_ui(current_user_id, st.session_state.user_email)
        return

    if (
        st.session_state.get("publish_after_checkout")
        and domain_type == "Vercel-Projektadresse"
    ):
        st.session_state.publish_after_checkout = False
        st.session_state.project_name = safe_project_name(requested_name or "")
        with st.status("Zahlung bestätigt. Vercel veröffentlicht Ihre Website ...", expanded=True) as status:
            try:
                publish_website()
                status.update(label="Ihre Website wurde veröffentlicht.", state="complete")
                st.success(f"Ihre Kundenwebsite ist bereit: {st.session_state.live_url}")
                st.link_button(
                    "Kundenwebsite jetzt öffnen",
                    st.session_state.live_url,
                    icon=":material/open_in_new:",
                    type="primary",
                    key="open_customer_site_after_checkout",
                    width="stretch",
                )
            except ValueError as error:
                status.update(label="Veröffentlichung fehlgeschlagen", state="error")
                st.error(str(error))

    if user_info["subscribed"]:
        st.caption(
            "Premium ist aktiv. Die Website wird auf Vercel veröffentlicht. Die finale "
            "Adresse wird nach der erfolgreichen Vercel-Antwort angezeigt."
        )
    else:
        st.info(
            f"{workspace_copy()['trial_active'].format(hours=user_info['trial_remaining_hours'])} "
            f"{domain_labels[10]}"
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
                    status.update(label=action_labels[11], state="error")
                    st.error(str(error))
    else:
        custom_domain = str(st.session_state.get("custom_domain", "")).strip()
        if custom_domain:
            st.info(
                "Die Domain muss vor der Verknüpfung gekauft sein. Für die automatische "
                "Anbindung benötigen Sie eine verifizierte Domain, passende DNS-Einträge und eine "
                "serverseitige Vercel-Domain-API-Integration."
            )

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
                status.update(
                    label=action_labels[20],
                    state="complete",
                )
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
                status.update(
                    label=old_publication_copy[6],
                    state="complete",
                )
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


def optimize_text_with_transformer(bullet_points: str) -> str:
    """Optimiert kurze Website-Texte mit einem Hugging-Face-Instruct-Modell."""
    if not HF_API_KEY:
        raise ValueError(
            "Der Hugging-Face-Schlüssel fehlt. Hinterlegen Sie HF_API_KEY in den Streamlit-Secrets."
        )

    prompt = (
        "Schreibe als professioneller Werbetexter diesen kurzen Text für eine "
        "Handwerker-Website attraktiv, seriös und fehlerfrei um. Verwende maximal "
        f"drei Sätze.\n\nText: {bullet_points.strip()}\n\nOptimierter Text:"
    )
    response = requests.post(
        HF_TEXT_MODEL_URL,
        headers={
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 150,
                "temperature": 0.4,
                "return_full_text": False,
            },
        },
        timeout=30,
    )
    if response.status_code == 503:
        raise ValueError(
            "Das KI-Modell wird gerade gestartet. Bitte versuchen Sie es in wenigen Sekunden erneut."
        )
    if response.status_code != 200:
        error_detail = response.json().get("error", "Unbekannter Fehler")
        raise ValueError(f"Hugging Face konnte den Text nicht verarbeiten: {error_detail}")

    result = response.json()
    if isinstance(result, list) and result:
        optimized_text = result[0].get("generated_text", "")
    elif isinstance(result, dict):
        optimized_text = result.get("generated_text", "")
    else:
        optimized_text = ""
    if not optimized_text.strip():
        raise ValueError("Hugging Face hat keinen optimierten Text zurückgegeben.")
    return optimized_text.strip()


def generate_website_recommendation(topic_or_industry: str) -> str:
    """Erstellt eine Branchenempfehlung für Titel, Leistungen und Angebot."""
    instruction = (
        "Du bist ein KI-Website-Generator für den AI Website Builder. Erstelle für "
        "das angegebene Thema eine professionelle, verkaufsstarke Struktur mit "
        "fertigen Texten für eine deutsche KMU-Website. Gib exakt dieses Format aus:\n"
        "EMPFOHLENER TITEL: [starker Slogan]\n"
        "LEISTUNGEN: [drei konkrete Empfehlungen]\n"
        "ANGEBOT: [Aktionsangebot für Neukunden]"
    )
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            max_tokens=300,
            timeout=30,
            messages=[
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": f"Generiere die Empfehlung für: {topic_or_industry.strip()}",
                },
            ],
        )
    except Exception as error:
        raise ValueError(f"Die Empfehlungs-Engine konnte nicht erreicht werden: {error}") from error

    recommendation = response.choices[0].message.content or ""
    if not recommendation.strip():
        raise ValueError("Die Empfehlungs-Engine hat keine Empfehlung zurückgegeben.")
    return recommendation.strip()


def render_website_recommendation_ui() -> None:
    """Rendert die automatische Empfehlung für eine Website-Branche."""
    st.caption("Geben Sie ein Schlagwort ein und erhalten Sie einen Titel, Leistungen und ein Angebot.")
    topic = st.text_input(
        "Thema oder Branche, zum Beispiel Kfz-Werkstatt, Friseur oder Dachdecker",
        key="website_recommendation_topic",
    )
    if st.button(
        "Automatische Empfehlung generieren",
        icon=":material/auto_awesome:",
        type="primary",
        key="website_recommendation_submit",
    ):
        if not topic.strip():
            st.warning("Bitte geben Sie zuerst ein Thema oder eine Branche ein.")
        else:
            with st.spinner(f"Empfehlung für {topic.strip()} wird erstellt ..."):
                try:
                    st.session_state.current_website_recommendation = (
                        generate_website_recommendation(topic)
                    )
                except ValueError as error:
                    st.error(str(error))

    recommendation = str(
        st.session_state.get("current_website_recommendation", "")
    ).strip()
    if recommendation:
        st.markdown("#### Automatisch generierte Website-Vorlage")
        st.info(recommendation)


INDUSTRY_CONTENT_PRESETS = {
    "Kfz-Meisterwerkstatt": {
        "client_company_name": "Kfz-Meisterbetrieb Schmidt",
        "client_company_slogan": "Ihre zuverlässige Autowerkstatt für alle Marken",
        "section_hero_title": "Meisterservice für Ihr Fahrzeug.",
        "section_hero_subtitle": "Persönlich, präzise und zuverlässig für alle Marken.",
        "template_hero_heading": "Ihre zuverlässige Autowerkstatt für alle Marken",
        "template_custom_description": "Vom Reifenwechsel über den Ölwechsel bis zur Motordiagnose: Wir halten Ihr Fahrzeug mit Meisterqualität sicher auf der Straße.",
        "template_footer_text": "© 2026 Kfz-Meisterbetrieb Schmidt | Impressum und Datenschutz",
        "template_sections_text": "Reparatur und Diagnose | Meisterhafte Reparaturen und präzise Fehleranalyse für alle Marken.\nReifen und Räder | Sicher unterwegs mit fachgerechtem Reifenwechsel und Einlagerung.\nInspektion und Service | Transparenter Autoservice mit Qualitätsersatzteilen.",
        "section_services": "Meisterhafte Kfz-Reparaturen, präziser Reifenwechsel, umfassender Autoservice",
        "section_about_text": "Seit über 15 Jahren reparieren wir Fahrzeuge aller Marken mit Leidenschaft und Meisterqualität.",
        "offer_page_name": "Ölwechsel-Komplettservice",
        "offer_page_price": "ab 49 EUR",
        "offer_page_details": "Inklusive kostenlosem Sicherheits- und Bremsencheck.",
    },
    "Friseursalon": {
        "client_company_name": "Haardesign und Wohlfühlen",
        "client_company_slogan": "Ihr perfekter Look in entspannter Atmosphäre",
        "section_hero_title": "Ihr Look. Unser Handwerk.",
        "section_hero_subtitle": "Individuelles Styling in entspannter Wohlfühlatmosphäre.",
        "template_hero_heading": "Ihr perfekter Look in entspannter Atmosphäre",
        "template_custom_description": "Ob Haarschnitt, Balayage oder klassisches Styling: Unser kreatives Team nimmt sich Zeit für Ihre Persönlichkeit und Ihr Haar.",
        "template_footer_text": "© 2026 Haardesign und Wohlfühlen | Impressum und Datenschutz",
        "template_sections_text": "Schnitt und Styling | Individuelle Looks für Damen, Herren und Kinder.\nFarbe und Balayage | Brillante Colorationen, präzise auf Ihren Typ abgestimmt.\nPflege und Beratung | Erstklassige Produkte und persönliche Empfehlungen für gesundes Haar.",
        "section_services": "Moderne Haarschnitte, brillante Colorationen, individuelles Styling für Damen, Herren und Kinder",
        "section_about_text": "Unser kreatives Team sorgt in Wohlfühlatmosphäre für Ihren perfekten Look und gesundes Haar.",
        "offer_page_name": "Premium-Balayage-Paket",
        "offer_page_price": "Beratung gratis",
        "offer_page_details": "Individuell abgestimmt inklusive hochwertiger Pflege.",
    },
    "Dachdeckerfachbetrieb": {
        "client_company_name": "Bedachungen Bednarz",
        "client_company_slogan": "Ihr Dach in besten Händen",
        "section_hero_title": "Schutz und Qualität für Ihr Dach.",
        "section_hero_subtitle": "Fachgerechte Lösungen für Neubau, Sanierung und Reparatur.",
        "template_hero_heading": "Ihr Dach in besten Händen",
        "template_custom_description": "Als Meisterbetrieb bieten wir zuverlässige Arbeiten für Steil- und Flachdächer, Fassaden und Bauklempnerei.",
        "template_footer_text": "© 2026 Bedachungen Bednarz | Impressum und Datenschutz",
        "template_sections_text": "Dachsanierung | Langlebige Lösungen für ein sicheres und energieeffizientes Dach.\nNeueindeckung | Hochwertige Materialien und sorgfältige Ausführung für Neubau und Umbau.\nReparatur und Abdichtung | Schnelle Hilfe bei Schäden, Feuchtigkeit und Undichtigkeiten.",
        "section_services": "Dachsanierung, Neueindeckung, Abdichtung und Reparatur, Dachfenster und Wärmedämmung",
        "section_about_text": "Wir verbinden solides Handwerk, langlebige Materialien und eine transparente Beratung für Ihr Zuhause.",
        "offer_page_name": "Kostenloser Dach-Check",
        "offer_page_price": "unverbindlich",
        "offer_page_details": "Wir prüfen den Zustand Ihres Dachs und beraten zu passenden Maßnahmen.",
    },
    "Physiotherapie-Praxis": {
        "client_company_name": "Praxis für Physiotherapie und Bewegung",
        "client_company_slogan": "Zurück zu Schmerzfreiheit und Mobilität",
        "section_hero_title": "Bewegung zurückgewinnen.",
        "section_hero_subtitle": "Persönliche Therapie für mehr Gesundheit und Lebensqualität.",
        "template_hero_heading": "Zurück zu Schmerzfreiheit und Mobilität",
        "template_custom_description": "Mit maßgeschneiderten Therapiekonzepten begleiten wir Sie nach Verletzungen, Operationen und bei chronischen Beschwerden.",
        "template_footer_text": "© 2026 Praxis für Physiotherapie und Bewegung | Impressum und Datenschutz",
        "template_sections_text": "Krankengymnastik | Individuelle Übungen für mehr Kraft, Beweglichkeit und Stabilität.\nManuelle Therapie | Gezielte Behandlung von Beschwerden und Bewegungseinschränkungen.\nLymphdrainage und Beratung | Persönliche Begleitung für Ihre nachhaltige Gesundheit.",
        "section_services": "Krankengymnastik, manuelle Therapie, Lymphdrainage und individuelle Trainingsberatung",
        "section_about_text": "Wir begleiten Sie mit fachlicher Kompetenz und einem ganzheitlichen Blick auf Ihre Gesundheit.",
        "offer_page_name": "Erstberatung",
        "offer_page_price": "persönlich und individuell",
        "offer_page_details": "Gemeinsam entwickeln wir den passenden Weg zu mehr Beweglichkeit.",
    },
    "Restaurant": {
        "client_company_name": "Restaurant Genusszeit",
        "client_company_slogan": "Frisch gekocht. Herzlich serviert.",
        "section_hero_title": "Genuss, der verbindet.",
        "section_hero_subtitle": "Saisonale Küche und echte Gastfreundschaft.",
        "template_hero_heading": "Frisch gekocht. Herzlich serviert.",
        "template_custom_description": "Wir servieren frisch zubereitete Gerichte, ausgewählte Getränke und eine entspannte Atmosphäre für Ihren Besuch.",
        "template_footer_text": "© 2026 Restaurant Genusszeit | Impressum und Datenschutz",
        "template_sections_text": "Speisekarte | Frische Gerichte und saisonale Spezialitäten.\nReservierung | Sichern Sie sich Ihren Tisch für einen genussvollen Abend.\nFeiern und Gruppen | Der passende Rahmen für besondere Anlässe.",
        "section_services": "Saisonale Küche, Tischreservierung, Gruppen und Feiern",
        "section_about_text": "Unser Team verbindet gute Zutaten, sorgfältige Zubereitung und persönliche Gastfreundschaft.",
        "offer_page_name": "Mittagsmenü",
        "offer_page_price": "ab 12,90 EUR",
        "offer_page_details": "Täglich frisch zubereitet, inklusive wechselnder Empfehlung des Hauses.",
    },
    "Café und Bäckerei": {
        "client_company_name": "Café Morgenrot",
        "client_company_slogan": "Kaffee, Kuchen und Zeit zum Genießen",
        "section_hero_title": "Ihr Lieblingsplatz im Alltag.",
        "section_hero_subtitle": "Hausgemachte Köstlichkeiten und guter Kaffee.",
        "template_hero_heading": "Kaffee, Kuchen und Zeit zum Genießen",
        "template_custom_description": "Bei uns erwarten Sie aromatischer Kaffee, frische Backwaren und hausgemachte Kuchen in entspannter Atmosphäre.",
        "template_footer_text": "© 2026 Café Morgenrot | Impressum und Datenschutz",
        "template_sections_text": "Kaffee und Getränke | Sorgfältig zubereitete Kaffeespezialitäten und erfrischende Getränke.\nFrühstück und Backwaren | Frisch gebacken für einen guten Start in den Tag.\nKuchen und Torten | Hausgemachte Klassiker und saisonale Kreationen.",
        "section_services": "Kaffeespezialitäten, Frühstück, frische Backwaren und hausgemachte Kuchen",
        "section_about_text": "Wir schaffen einen Ort für gute Gespräche, kleine Auszeiten und ehrlichen Genuss.",
        "offer_page_name": "Frühstück für zwei",
        "offer_page_price": "ab 24 EUR",
        "offer_page_details": "Ausgewählte Backwaren, Aufstriche und zwei Heißgetränke.",
    },
    "Onlineshop": {
        "client_company_name": "Studio Lieblingsstücke",
        "client_company_slogan": "Besondere Produkte einfach online entdecken",
        "section_hero_title": "Schönes für Ihren Alltag.",
        "section_hero_subtitle": "Ausgewählte Produkte, sicher bestellt und schnell geliefert.",
        "template_hero_heading": "Besondere Produkte einfach online entdecken",
        "template_custom_description": "Entdecken Sie sorgfältig ausgewählte Produkte mit klaren Informationen, sicheren Zahlungsarten und zuverlässigem Versand.",
        "template_footer_text": "© 2026 Studio Lieblingsstücke | Impressum und Datenschutz",
        "template_sections_text": "Unsere Produkte | Ausgewählte Artikel mit klaren Details und Bildern.\nVersand und Zahlung | Transparent, sicher und bequem bestellen.\nKundenservice | Persönliche Hilfe vor und nach Ihrem Einkauf.",
        "section_services": "Produktauswahl, sicherer Onlinekauf, Versand und Kundenservice",
        "section_about_text": "Wir wählen Produkte mit Anspruch aus und machen den Online-Einkauf angenehm und transparent.",
        "offer_page_name": "Willkommensrabatt",
        "offer_page_price": "10 Prozent",
        "offer_page_details": "Für Ihre erste Bestellung im Onlineshop.",
    },
}

OTHER_INDUSTRY_OPTION = "Andere Branche oder Kleingewerbe"

INDUSTRY_TEMPLATE_MAP = {
    "Kfz-Meisterwerkstatt": "Automobil und KFZ-Gewerbe",
    "Friseursalon": "Formale Agentur oder Kanzlei",
    "Dachdeckerfachbetrieb": "GmbH und Corporate Unternehmen",
    "Physiotherapie-Praxis": "Formale Agentur oder Kanzlei",
    "Restaurant": "Restaurant und Gastronomie",
    "Café und Bäckerei": "Cafe und Baeckerei",
    "Onlineshop": "Supermarkt und Einzelhandel",
}


def build_generic_industry_preset(industry: str) -> dict[str, str]:
    """Erstellt einen sofort nutzbaren Entwurf für nicht vorgegebene Branchen."""
    business_name = f"{industry} Musterbetrieb"
    return {
        "client_company_name": business_name,
        "client_company_slogan": "Persönlicher Service, passend für Ihr Anliegen",
        "section_hero_title": "Kompetenz, die für Sie da ist.",
        "section_hero_subtitle": "Individuelle Lösungen und persönliche Beratung.",
        "template_hero_heading": "Persönlicher Service, passend für Ihr Anliegen",
        "template_custom_description": f"{business_name} bietet zuverlässige Leistungen, klare Beratung und persönliche Betreuung.",
        "template_footer_text": f"© 2026 {business_name} | Impressum und Datenschutz",
        "template_sections_text": "Unsere Leistungen | Passende Lösungen für Ihr Anliegen.\nPersönliche Beratung | Wir nehmen uns Zeit für Ihre Fragen.\nKontakt | Sprechen Sie direkt mit unserem Team.",
        "section_services": "Individuelle Leistungen, persönliche Beratung und zuverlässiger Service",
        "section_about_text": "Wir stehen für Qualität, Verlässlichkeit und einen persönlichen Ansprechpartner.",
        "offer_page_name": "Unverbindliche Beratung",
        "offer_page_price": "kostenlos",
        "offer_page_details": "Wir besprechen Ihr Anliegen persönlich und transparent.",
    }


def get_configured_chatbot_knowledge() -> str:
    """Kombiniert Branchenwissen mit den strukturierten Firmendaten des Kunden."""
    language = str(st.session_state.app_language)
    knowledge_copy = {
        "de": ["Branche", "Unternehmen", "Unternehmensbeschreibung", "Öffnungszeiten", "Kontaktwege", "Preise und Leistungen", "Notfall und Bereitschaft", "Telefon", "Typische Leistungen dieser Branche", "Standardhinweis: Öffnungszeiten, Preise und konkrete Verfügbarkeiten liegen nicht vor. Verweise dafür auf die Kontaktmöglichkeiten der Website.", "Allgemeiner Kundenservice"],
        "en": ["Industry", "Company", "Company description", "Opening hours", "Contact methods", "Prices and services", "Emergency and on-call service", "Phone", "Typical services in this industry", "Note: Opening hours, prices, and specific availability are not provided. Refer visitors to the website contact details.", "General customer service"],
        "ar": ["المجال", "الشركة", "وصف الشركة", "ساعات العمل", "وسائل الاتصال", "الأسعار والخدمات", "الطوارئ وخدمة الاستعداد", "الهاتف", "الخدمات المعتادة في هذا المجال", "ملاحظة: لا تتوفر ساعات العمل أو الأسعار أو معلومات التوفر المحددة. يُرجى توجيه الزوار إلى بيانات الاتصال في الموقع.", "خدمة العملاء العامة"],
        "ku": ["بوار", "کۆمپانیا", "وەسفی کۆمپانیا", "کاتەکانی کردنەوە", "ڕێگاکانی پەیوەندی", "نرخ و خزمەتگوزارییەکان", "فریاکەوتن و ئامادەباشی", "تەلەفۆن", "خزمەتگوزارییە باوەکانی ئەم بوارە", "تێبینی: کاتەکانی کردنەوە، نرخ و بەردەستبوونی دیاریکراو نەدراون. سەردانکەران بۆ زانیاری پەیوەندیی وێبگەکە ڕێنمایی بکە.", "خزمەتگوزاری گشتی کڕیار"],
        "es": ["Sector", "Empresa", "Descripción de la empresa", "Horario", "Métodos de contacto", "Precios y servicios", "Emergencias y guardias", "Teléfono", "Servicios habituales del sector", "Nota: No se dispone de horarios, precios ni disponibilidad concreta. Remita a los visitantes a los datos de contacto del sitio web.", "Atención general al cliente"],
        "it": ["Settore", "Azienda", "Descrizione dell'azienda", "Orari di apertura", "Metodi di contatto", "Prezzi e servizi", "Emergenze e reperibilità", "Telefono", "Servizi tipici del settore", "Nota: Orari, prezzi e disponibilità specifiche non sono indicati. Indirizzate i visitatori ai recapiti del sito.", "Servizio clienti generale"],
        "hi": ["उद्योग", "कंपनी", "कंपनी का विवरण", "कार्य समय", "संपर्क के तरीके", "मूल्य और सेवाएं", "आपातकालीन और ऑन-कॉल सेवा", "फोन", "इस उद्योग की सामान्य सेवाएं", "नोट: कार्य समय, मूल्य और निश्चित उपलब्धता नहीं दी गई है। आगंतुकों को वेबसाइट के संपर्क विवरण पर भेजें।", "सामान्य ग्राहक सेवा"],
    }
    labels = knowledge_copy.get(language, knowledge_copy["en"])
    industry_names = {
        "en": {"Kfz-Meisterwerkstatt": "Automotive workshop", "Friseursalon": "Hair salon", "Dachdeckerfachbetrieb": "Roofing company", "Physiotherapie-Praxis": "Physiotherapy clinic", "Restaurant": "Restaurant", "Café und Bäckerei": "Cafe and bakery", "Onlineshop": "Online shop"},
        "ar": {"Kfz-Meisterwerkstatt": "ورشة سيارات متخصصة", "Friseursalon": "صالون حلاقة وتجميل", "Dachdeckerfachbetrieb": "شركة أسقف متخصصة", "Physiotherapie-Praxis": "عيادة علاج طبيعي", "Restaurant": "مطعم", "Café und Bäckerei": "مقهى ومخبز", "Onlineshop": "متجر إلكتروني"},
        "ku": {"Kfz-Meisterwerkstatt": "وەرشەی پسپۆڕی ئۆتۆمبێل", "Friseursalon": "سالۆنی قژبڕین", "Dachdeckerfachbetrieb": "کۆمپانیای سەربان", "Physiotherapie-Praxis": "کلینیکی فیزیۆتێراپی", "Restaurant": "چێشتخانە", "Café und Bäckerei": "کافێ و نانەواخانە", "Onlineshop": "فرۆشگای ئۆنلاین"},
        "es": {"Kfz-Meisterwerkstatt": "Taller de automóviles", "Friseursalon": "Peluquería", "Dachdeckerfachbetrieb": "Empresa de cubiertas", "Physiotherapie-Praxis": "Clínica de fisioterapia", "Restaurant": "Restaurante", "Café und Bäckerei": "Cafetería y panadería", "Onlineshop": "Tienda en línea"},
        "it": {"Kfz-Meisterwerkstatt": "Officina automobilistica", "Friseursalon": "Salone di parrucchieri", "Dachdeckerfachbetrieb": "Impresa di coperture", "Physiotherapie-Praxis": "Studio di fisioterapia", "Restaurant": "Ristorante", "Café und Bäckerei": "Caffetteria e panetteria", "Onlineshop": "Negozio online"},
        "hi": {"Kfz-Meisterwerkstatt": "वाहन कार्यशाला", "Friseursalon": "हेयर सैलून", "Dachdeckerfachbetrieb": "छत निर्माण कंपनी", "Physiotherapie-Praxis": "फिजियोथेरेपी क्लिनिक", "Restaurant": "रेस्तरां", "Café und Bäckerei": "कैफे और बेकरी", "Onlineshop": "ऑनलाइन दुकान"},
    }
    industry = str(st.session_state.get("industry_content_preset", ""))
    source_industry = industry
    custom_industry = str(st.session_state.get("custom_industry_name", "")).strip()
    if industry == OTHER_INDUSTRY_OPTION and custom_industry:
        industry = custom_industry
    elif industry not in INDUSTRY_CONTENT_PRESETS:
        industry = labels[10]
    else:
        industry = industry_names.get(language, {}).get(industry, industry)
    company_name = str(st.session_state.get("client_company_name", "")).strip()
    description = str(st.session_state.get("template_custom_description", "")).strip()
    business_email = str(st.session_state.get("client_business_email", "")).strip()
    business_phone = str(st.session_state.get("client_business_phone", "")).strip()
    fields = (
        (labels[3], "client_chatbot_hours"),
        (labels[4], "client_chatbot_contact"),
        (labels[5], "client_chatbot_services"),
        (labels[6], "client_chatbot_emergency"),
    )
    business_details = [
        f"{label}: {str(st.session_state.get(key, '')).strip()}"
        for label, key in fields
        if str(st.session_state.get(key, "")).strip()
    ]
    context = [f"{labels[0]}: {industry}."]
    if company_name:
        context.append(f"{labels[1]}: {company_name}.")
    if description:
        context.append(f"{labels[2]}: {description}")
    if business_email or business_phone:
        contact_details = " | ".join(
            detail
            for detail in (
                f"E-Mail: {business_email}" if business_email else "",
                f"{labels[7]}: {business_phone}" if business_phone else "",
            )
            if detail
        )
        context.append(f"{labels[4]}: {contact_details}")
    if business_details:
        context.extend(business_details)
    else:
        industry_preset = INDUSTRY_CONTENT_PRESETS.get(source_industry, {})
        default_services = str(industry_preset.get("section_services", "")).strip()
        if default_services:
            context.append(f"{labels[8]}: {default_services}.")
        context.append(labels[9])
    return "\n".join(context)


def apply_industry_content_preset() -> None:
    """Übernimmt die Inhalte der im Formular gewählten Branche."""
    industry = str(st.session_state.get("industry_content_preset", ""))
    custom_industry = str(st.session_state.get("custom_industry_name", "")).strip()
    preset = (
        build_generic_industry_preset(custom_industry)
        if industry == OTHER_INDUSTRY_OPTION and custom_industry
        else INDUSTRY_CONTENT_PRESETS.get(industry)
    )
    if preset:
        st.session_state.industry_source_preset = dict(preset)
        st.session_state.update(preset)
        apply_app_language()
        mcp_chatbot_profile = get_industry_chatbot_profile_with_mcp(industry)
        chatbot_defaults = {
            "Kfz-Meisterwerkstatt": ("Werkstatt-Assistent", "Mo-Fr: 08:00-18:00 Uhr", "Telefonisch oder per E-Mail während der Öffnungszeiten", "Für Pannen außerhalb der Öffnungszeiten wenden Sie sich bitte an einen Pannendienst."),
            "Friseursalon": ("Salon-Assistent", "Di-Fr: 09:00-18:00 Uhr, Sa: 09:00-14:00 Uhr", "Termine telefonisch oder per E-Mail vereinbaren", "Für kurzfristige Termine kontaktieren Sie den Salon direkt."),
            "Dachdeckerfachbetrieb": ("Dachservice-Assistent", "Mo-Fr: 07:00-17:00 Uhr", "Telefonisch oder per E-Mail", "Bei akuten Sturmschäden kontaktieren Sie uns telefonisch."),
            "Physiotherapie-Praxis": ("Praxis-Assistent", "Mo-Fr: 08:00-18:00 Uhr", "Termine telefonisch oder per E-Mail", "Bei akuten Beschwerden wenden Sie sich bitte an den ärztlichen Notdienst."),
            "Restaurant": ("Genusszeit-Assistent", "Di-So: 12:00-22:00 Uhr", "Reservierungen telefonisch oder per E-Mail", "Für kurzfristige Reservierungen rufen Sie uns bitte direkt an."),
            "Café und Bäckerei": ("Café-Assistent", "Mo-Sa: 07:00-18:00 Uhr, So: 08:00-16:00 Uhr", "Vorbestellungen telefonisch oder per E-Mail", "Für tagesaktuelle Bestellungen kontaktieren Sie uns direkt."),
            "Onlineshop": ("Shop-Assistent", "Mo-Fr: 09:00-17:00 Uhr", "Kundenservice per E-Mail", "Bei dringenden Bestellfragen schreiben Sie uns bitte mit Bestellnummer."),
        }
        chatbot_name, chatbot_hours, chatbot_contact, chatbot_emergency = chatbot_defaults.get(
            industry,
            ("Kundenservice-Assistent", "Öffnungszeiten nach Vereinbarung", "Kontakt per E-Mail", "Für dringende Anliegen kontaktieren Sie uns direkt."),
        )
        st.session_state.customer_chatbot_name = (
            mcp_chatbot_profile.get("name") or chatbot_name
        )
        st.session_state.client_chatbot_hours = (
            mcp_chatbot_profile.get("hours") or chatbot_hours
        )
        st.session_state.client_chatbot_contact = (
            mcp_chatbot_profile.get("contact") or chatbot_contact
        )
        st.session_state.client_chatbot_services = (
            mcp_chatbot_profile.get("services")
            or str(preset.get("section_services", ""))
        )
        st.session_state.client_chatbot_emergency = (
            mcp_chatbot_profile.get("emergency") or chatbot_emergency
        )
        st.session_state.customer_chatbot_color = "#2563EB"
        st.session_state.customer_chatbot_shape = "Rund (Kreis)"
        st.session_state.customer_chatbot_figure = {
            "Friseursalon": "Salon-Stylistin",
            "Kfz-Meisterwerkstatt": "Werkstatt-Profi",
            "Dachdeckerfachbetrieb": "Werkstatt-Profi",
            "Physiotherapie-Praxis": "Praxis-Begleitung",
            "Restaurant": "Gastronomie-Service",
            "Café und Bäckerei": "Gastronomie-Service",
            "Onlineshop": "Shop-Beratung",
        }.get(industry, "Freundlicher Roboter")
        st.session_state.customer_chatbot_position = "Unten rechts"
        st.session_state.customer_chatbot_fixed = True
        template_name = INDUSTRY_TEMPLATE_MAP.get(industry)
        if template_name:
            st.session_state.template_name = template_name
        st.session_state.template_preview_page = "start"
        st.session_state.template_preview_template = st.session_state.get(
            "template_name", ""
        )
        st.session_state.industry_preset_applied = custom_industry or industry


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
        )
        st.success(workspace_labels["draft_saved"])
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
                    loaded_name, loaded_html, loaded_domain = saved_website
                    st.session_state.assets = {}
                    st.session_state.pending_html = loaded_html
                    st.session_state.live_url = loaded_domain
                    st.session_state.deployment_url = loaded_domain
                    st.session_state.deployment_id = ""
                    st.session_state.project_name = safe_project_name(loaded_name)
                    st.rerun()
            if st.button(
                t("delete"),
                key=f"delete_website_{website_id}",
                icon=":material/delete:",
                width="stretch",
            ):
                delete_saved_website(st.session_state.user_id, website_id)
                st.rerun()


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
                    st.success("Die Vorlage wurde geladen und kann jetzt bearbeitet werden.")
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
                            status.update(
                                label="Website wurde geladen und kann bearbeitet werden.",
                                state="complete",
                            )
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
            icon=(":material/edit_document:" if creation_mode == "Professionelle Vorlage" else ":material/rocket_launch:"),
            type="primary",
            key="create_website",
            width="stretch",
        ):
            if creation_mode == "Professionelle Vorlage":
                try:
                    company_name = str(st.session_state.client_company_name).strip()
                    business_email = str(st.session_state.client_business_email).strip()
                    if not company_name or not EMAIL_PATTERN.fullmatch(business_email):
                        raise ValueError("Bitte geben Sie Unternehmensname und eine gültige geschäftliche E-Mail-Adresse ein.")
                    background_color = BACKGROUND_PRESET_COLORS[
                        st.session_state.template_background_preset
                    ]
                    html = build_customized_template_html(
                        str(st.session_state.template_name),
                        background_color,
                        str(st.session_state.template_accent_color),
                        str(st.session_state.template_border_style),
                        company_name,
                        business_email,
                        str(st.session_state.get("template_hero_heading", "")).strip()
                        or str(st.session_state.client_company_slogan),
                        str(st.session_state.client_business_phone),
                        description,
                        initial_image,
                        str(st.session_state.get("template_button_text", "")),
                        str(st.session_state.get("template_footer_text", "")),
                        page_structure == "Mehrseitige Website",
                        get_configured_chatbot_knowledge(),
                        str(st.session_state.get("customer_chatbot_name", "")),
                        str(st.session_state.get("customer_chatbot_color", "#2563EB")),
                        {"Rund (Kreis)": "50%", "Eckig mit Rundung": "8px", "Quadratisch": "0"}.get(str(st.session_state.get("customer_chatbot_shape", "Rund (Kreis)")), "50%"),
                        str(st.session_state.get("template_sections_text", "")),
                    )
                    queue_html_update(html, reset_site_pages=True)
                    st.session_state.site_pages["styles.css"] = (
                        build_customized_template_styles()
                    )
                    if page_structure == "Mehrseitige Website":
                        st.session_state.site_pages.update(
                            build_customized_template_pages(
                                company_name,
                                business_email,
                                background_color,
                                str(st.session_state.template_accent_color),
                                description,
                                get_configured_chatbot_knowledge(),
                                str(st.session_state.get("customer_chatbot_name", "")),
                                str(st.session_state.get("customer_chatbot_color", "#2563EB")),
                            )
                        )
                    st.success("Die Vorlage wurde mit Ihren Kundendaten übernommen und kann jetzt direkt bearbeitet werden.")
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
                            image_placement,
                            multi_page=page_structure == "Mehrseitige Website",
                        )
                        status.update(label="Website wurde erstellt.", state="complete")
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
                    status.update(
                        label=import_labels["loaded"],
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label=import_labels["failed"],
                        state="error",
                    )
                    st.error(str(error))

with service_tab:
    render_mcp_content_tools_ui()
    st.divider()
    render_customer_service_ui(current_user_id, st.session_state.user_email)
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

if (
    st.session_state.generated_html
    and st.session_state.get("creation_mode") != "Professionelle Vorlage"
):
    st.divider()
    st.header(t("edit_website"))

    live_editor_tab, direct_edit_tab, content_tab, design_tab, image_tab, html_tab = st.tabs(
        ["Live-Design", "Direkt bearbeiten", "📝 Inhalte", "🎨 Design", "🖼️ Bilder", "💻 HTML-Code"]
    )

    with live_editor_tab:
        render_editor()

    with direct_edit_tab:
        render_direct_content_editor()

    with content_tab:
        section = st.selectbox(
            "Bereich auswählen",
            [
                "Navigation",
                "Hero-Bereich",
                "Über mich",
                "Leistungen",
                "Projekte",
                "Kontakt",
                "Footer",
                "Neuen Bereich hinzufügen",
            ],
            key="content_editor_section",
        )

        change_request = st.text_area(
            "Gewünschte Änderung",
            placeholder=(
                "Beispiel: Ersetze das Kontaktformular durch das konfigurierte "
                "Formspree-Formular und behalte das aktuelle Design."
            ),
            key="content_editor_request",
            height=130,
        )

        if st.button(
            "📝 Bereich aktualisieren",
            key="apply_content_editor_request",
            width="stretch",
        ):
            if not change_request.strip():
                st.warning("Bitte beschreibe die gewünschte Änderung.")
            else:
                with st.status("Bereich wird bearbeitet ...", expanded=True) as status:
                    try:
                        modify_current_website(
                            f"Ändere ausschließlich den Bereich „{section}“: "
                            f"{change_request}"
                        )
                        status.update(
                            label="✅ Vorschau wurde aktualisiert.",
                            state="complete",
                        )
                        st.rerun()
                    except Exception as error:
                        status.update(
                            label="❌ Änderung fehlgeschlagen",
                            state="error",
                        )
                        st.error(str(error))

    with design_tab:
        st.subheader("Basisdaten und Markenauftritt")
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
        company_name = st.text_input(
            "Firmenname oder Logo-Text",
            value=str(st.session_state.get("client_company_name", "")),
            key="premium_company_name",
        )
        company_slogan = st.text_input(
            "Slogan oder Hauptüberschrift",
            value=str(st.session_state.get("client_company_slogan", "")),
            key="premium_company_slogan",
        )
        company_description = st.text_area(
            "Kurzbeschreibung für Über uns",
            key="premium_company_description",
            height=100,
        )
        contact_email = st.text_input(
            "Kontakt-E-Mail-Adresse",
            value=str(st.session_state.get("client_business_email", "")),
            key="premium_contact_email",
        )
        contact_phone = st.text_input(
            "Telefonnummer",
            value=str(st.session_state.get("client_business_phone", "")),
            key="premium_contact_phone",
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
        chatbot_knowledge = st.text_area(
            "Chatbot-Wissen",
            value=str(st.session_state.get("client_chatbot_knowledge", "")),
            placeholder="Öffnungszeiten, Preise, Angebote, Terminvereinbarung oder häufige Fragen.",
            key="premium_chatbot_knowledge",
            height=120,
        )

        if st.button(
            "Basisdaten übernehmen",
            icon=":material/save:",
            key="apply_premium_basics",
            width="stretch",
        ):
            if not company_name.strip() or not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email.strip()
            ):
                st.warning("Geben Sie einen Firmennamen und eine gültige Kontakt-E-Mail-Adresse ein.")
            else:
                st.session_state.client_company_name = company_name.strip()
                st.session_state.client_business_email = contact_email.strip()
                st.session_state.client_company_slogan = company_slogan.strip()
                st.session_state.client_business_phone = contact_phone.strip()
                st.session_state.client_chatbot_knowledge = chatbot_knowledge.strip()
                with st.status("Basisdaten werden übernommen ...", expanded=True) as status:
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
keine gültige URL angegeben wurde. Aktualisiere den Website-Chatbot mit diesem Wissen:
„{chatbot_knowledge.strip()}“. Erfinde keine zusätzlichen Öffnungszeiten, Preise oder
Angebote. Alle sonstigen Inhalte und Bilder bleiben erhalten.
"""
                        )
                        status.update(label="Basisdaten wurden übernommen.", state="complete")
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
                        status.update(
                            label="✅ Design wurde aktualisiert.",
                            state="complete",
                        )
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

                        status.update(
                            label="✅ Bild wurde aktualisiert.",
                            state="complete",
                        )
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

    st.divider()
    st.header(t("publish"))

    st.text_input(
        "Vercel-Projektname",
        key="project_name",
        help=(
            "Muss exakt dem Namen des Projekts im Vercel-Dashboard entsprechen. "
            "Dann wird dessen Production-Version aktualisiert."
        ),
    )

    publish_column, delete_column = st.columns(2, gap="large")

    with publish_column:
        if st.button(
            "🚀 Änderungen veröffentlichen",
            type="primary",
            key="publish_editor_changes",
            width="stretch",
        ):
            with st.status(
                "Website wird auf Vercel veröffentlicht ...",
                expanded=True,
            ) as status:
                try:
                    publish_website()
                    status.update(
                        label="🎉 Änderungen wurden veröffentlicht.",
                        state="complete",
                    )
                    st.rerun()
                except Exception as error:
                    status.update(
                        label="❌ Veröffentlichung fehlgeschlagen",
                        state="error",
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
                key="delete_latest_deployment",
                width="stretch",
            ):
                try:
                    delete_published_website()
                    st.success("Deployment wurde gelöscht.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Löschen fehlgeschlagen: {error}")
        else:
            st.info(
                "Extern geladene Websites können über diese App nicht gelöscht werden."
            )

st.divider()
render_domain_and_deployment_ui()
