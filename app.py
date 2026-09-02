import base64
import hashlib
import hmac
import io
import re
import secrets
import sqlite3
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import requests
import streamlit as st
from openai import OpenAI


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
        .template-shell { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); background: var(--background); color: var(--text); }
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
        [contenteditable="true"] { cursor: text; outline: 1px dashed transparent; outline-offset: 4px; }
        [contenteditable="true"]:hover, [contenteditable="true"]:focus { outline-color: var(--accent); }
        .template-hint { margin: 0; padding: 12px 28px; background: var(--surface); color: var(--muted); font: 12px ui-sans-serif, sans-serif; }
        .template-page { padding: 58px 28px; }
        .template-page h1 { margin: 12px 0; font-size: 38px; line-height: 1.1; }
        .template-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 34px; }
        .template-card { min-height: 210px; padding: 22px; border-top: 3px solid var(--accent); background: var(--surface); font-family: ui-sans-serif, sans-serif; }
        .template-card p { color: var(--muted); }
        .template-footer { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 28px; padding: 34px 28px 20px; border-top: 1px solid var(--border); font-family: ui-sans-serif, sans-serif; }
        .template-footer h2 { margin: 0; font-size: 15px; } .template-footer p, .template-footer a { color: var(--muted); font-size: 13px; line-height: 1.6; text-decoration: none; }
        .template-footer a:hover { color: var(--accent); } .template-footer-legal { grid-column: 1 / -1; margin: 0; padding-top: 16px; border-top: 1px solid var(--border); }
        .template-chatbot { position: fixed; right: 22px; bottom: 22px; z-index: 10; font-family: ui-sans-serif, sans-serif; }
        .template-chatbot-toggle { width: 48px; height: 48px; border: 0; border-radius: 50%; background: var(--accent); color: var(--accent-text); cursor: pointer; font: 700 20px ui-sans-serif, sans-serif; box-shadow: 0 10px 28px rgba(15, 23, 42, .24); }
        .template-chatbot-panel { display: none; width: min(300px, calc(100vw - 44px)); margin: 0 0 10px auto; padding: 18px; background: var(--background); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 16px 38px rgba(15, 23, 42, .22); }
        .template-chatbot-panel.is-open { display: block; }
        .template-chatbot-panel h2 { margin: 0; font-size: 16px; }
        .template-chatbot-panel p { margin: 8px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
        @media (max-width: 700px) { .template-header { align-items: flex-start; flex-direction: column; } .template-nav { justify-content: flex-start; } .template-hero, .template-cards, .template-footer { grid-template-columns: 1fr; } }
        """,
        js="""
        export default function(component) {
            const { data, parentElement, setTriggerValue } = component;
            const root = parentElement.querySelector('#template-editor');
            if (!root || !data) return;
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
                [['start', 'Start'], ['leistungen', 'Leistungen'], ['angebote', 'Angebote'], ['projekte', 'Projekte'], ['ueber_uns', 'Über uns'], ['kontakt', 'Kontakt']].forEach(([page, label]) => {
                    const link = create('button', '', label);
                    link.type = 'button';
                    link.onclick = () => setTriggerValue('navigated', page);
                    nav.append(link);
                });
            }
            header.append(company, nav);
            if (data.page !== 'start') {
                const page = create('main', 'template-page');
                const pageContent = {
                    leistungen: ['Leistungen', 'Leistungen für Ihren Erfolg.', [['01', 'Individuelle Beratung', 'Wir analysieren Ihren Bedarf und entwickeln eine passende Lösung.'], ['02', 'Verlässliche Umsetzung', 'Klare Abläufe, hohe Qualität und ein verbindlicher Ansprechpartner.'], ['03', 'Nachhaltiger Service', 'Auch nach dem Projekt bleiben wir persönlich für Sie erreichbar.']]],
                    angebote: ['Angebote', 'Passende Angebote, klar erklärt.', [['01', 'Individuelles Angebot', data.description], ['02', 'Transparente Konditionen', 'Leistungsumfang und nächster Schritt sind klar beschrieben.'], ['03', 'Persönliche Anfrage', 'Wir beraten Sie persönlich zu Ihrem Vorhaben.']]],
                    projekte: ['Projekte', 'Einblicke in unsere Arbeit.', [['01', 'Ausgewählte Projekte', 'Einblick in Lösungen, die wir gemeinsam mit unseren Kunden umgesetzt haben.'], ['02', 'Unser Vorgehen', 'Von der ersten Idee bis zur verlässlichen Umsetzung begleiten wir jedes Vorhaben.'], ['03', 'Ihr nächstes Projekt', data.description]]],
                    ueber_uns: ['Über uns', 'Ein Unternehmen, das persönlich erreichbar bleibt.', [['01', 'Unsere Arbeitsweise', 'Wir verbinden Kompetenz mit klarer Kommunikation.'], ['02', 'Unser Anspruch', 'Qualität und Verlässlichkeit bestimmen jede Zusammenarbeit.'], ['03', 'Ihr Vorteil', data.description]]],
                    kontakt: ['Kontakt', 'Sprechen Sie mit uns.', [['01', 'Direkter Kontakt', data.businessEmail], ['02', 'Persönliche Beratung', 'Wir melden uns zeitnah bei Ihnen.'], ['03', 'Nächster Schritt', 'Senden Sie uns Ihre Anfrage und erzählen Sie uns von Ihrem Vorhaben.']]],
                }[data.page];
                page.append(create('p', 'template-eyebrow', pageContent[0]));
                page.append(create('h1', '', pageContent[1]));
                page.append(create('p', 'template-description', data.description));
                const cards = create('section', 'template-cards');
                pageContent[2].forEach(([number, title, text]) => {
                    const card = create('article', 'template-card');
                    card.append(create('p', 'template-eyebrow', number), create('h2', '', title), create('p', '', text));
                    cards.append(card);
                });
                page.append(cards);
                shell.append(header, page, create('p', 'template-hint', 'Dies ist eine eigenständige Unterseite im selben Unternehmensdesign.'));
                root.append(shell);
                return;
            }
            const hero = create('div', 'template-hero');
            const copy = create('div', '');
            copy.append(create('p', 'template-eyebrow', 'Professionelle Markenwebsite'));
            const fields = [['heading', 'h3', 'template-heading'], ['description', 'p', 'template-description'], ['buttonText', 'button', 'template-button']];
            const changed = {};
            fields.forEach(([key, tag, className]) => {
                const field = create(tag, className, data[key]);
                field.contentEditable = 'true';
                field.setAttribute('role', 'textbox');
                field.setAttribute('aria-label', key === 'heading' ? 'Überschrift bearbeiten' : key === 'description' ? 'Beschreibung bearbeiten' : 'Button-Text bearbeiten');
                if (key === 'buttonText') field.type = 'button';
                field.onblur = () => {
                    const value = field.textContent.trim();
                    if (value !== data[key]) { changed[key] = value; setTriggerValue('saved', changed); }
                };
                if (key === 'buttonText') field.onclick = () => setTriggerValue('navigated', 'angebote');
                copy.append(field);
            });
            const image = data.imageDataUrl ? create('img', 'template-image') : create('div', 'template-placeholder', 'BILDPLATZ: Hero oder Willkommensbereich');
            if (data.imageDataUrl) { image.src = data.imageDataUrl; image.alt = data.companyName; }
            hero.append(copy, image);
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
            contact.append(create('h2', '', 'Kontakt'), create('a', '', data.businessEmail));
            contact.lastChild.href = `mailto:${data.businessEmail}`;
            const legal = create('section', '');
            legal.append(create('h2', '', 'Rechtliches'), create('a', '', 'Impressum'), create('p', '', 'Datenschutz'));
            const legalNote = create('p', 'template-footer-legal', `© ${new Date().getFullYear()} ${data.companyName}. Alle Rechte vorbehalten.`);
            footer.append(brand, contact, legal, legalNote);
            shell.append(header, hero, templateSections, footer, create('p', 'template-hint', 'Änderungen werden sofort in dieser Entwurfsvorschau angezeigt.'));
            const chatbot = create('aside', 'template-chatbot');
            const chatbotPanel = create('section', 'template-chatbot-panel');
            chatbotPanel.append(create('h2', '', `${data.companyName} Assistent`), create('p', '', data.chatbotKnowledge || `Willkommen. Wie können wir Ihnen bei ${data.companyName} helfen?`));
            const chatbotToggle = create('button', 'template-chatbot-toggle', '?');
            chatbotToggle.type = 'button';
            chatbotToggle.setAttribute('aria-label', 'Chatbot öffnen');
            chatbotToggle.onclick = () => chatbotPanel.classList.toggle('is-open');
            chatbot.append(chatbotPanel, chatbotToggle);
            shell.append(chatbot);
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
                is_subscribed INTEGER DEFAULT 0
            )
            """
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

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        raise ValueError("Bitte gib eine gueltige E-Mail-Adresse ein.")
    if len(password) < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen haben.")

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (normalized_email, hash_password(password)),
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


def get_user_status(user_id: int) -> dict[str, float | bool]:
    """Liest Guthaben und Premium-Status des angemeldeten Nutzers."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        user = connection.execute(
            "SELECT token_balance, is_subscribed FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if user is None:
        return {"balance": 0.0, "subscribed": False}
    return {"balance": float(user[0]), "subscribed": bool(user[1])}


def deduct_tokens(user_id: int, amount: float = 0.05) -> bool:
    """Bucht Guthaben atomar ab und sperrt Free-Nutzer ohne ausreichendes Guthaben."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT token_balance, is_subscribed FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if user is None:
            return False
        if user[1]:
            return True
        if float(user[0]) < amount:
            return False

        connection.execute(
            "UPDATE users SET token_balance = token_balance - ? WHERE id = ?",
            (amount, user_id),
        )
        return True


def refund_tokens(user_id: int, amount: float = 0.05) -> None:
    """Erstattet Guthaben, wenn die KI-Anfrage nicht ausgeführt werden konnte."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE users SET token_balance = token_balance + ? "
            "WHERE id = ? AND is_subscribed = 0",
            (amount, user_id),
        )


def activate_premium_demo(user_id: int) -> None:
    """Aktiviert Premium fuer lokale Tests, bis eine Zahlungsintegration vorhanden ist."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE users SET is_subscribed = 1 WHERE id = ?",
            (user_id,),
        )


def create_stripe_checkout_session(user_id: int, user_email: str) -> str:
    """Erstellt eine Stripe-Checkout-Sitzung für die Veröffentlichungsfreigabe."""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID or not STRIPE_SUCCESS_URL:
        raise ValueError("Stripe ist noch nicht eingerichtet.")

    response = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        auth=(STRIPE_SECRET_KEY, ""),
        data={
            "mode": "subscription",
            "customer_email": user_email,
            "client_reference_id": str(user_id),
            "line_items[0][price]": STRIPE_PRICE_ID,
            "line_items[0][quantity]": "1",
            "success_url": f"{STRIPE_SUCCESS_URL}?checkout_session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": STRIPE_SUCCESS_URL,
        },
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
    """Zeigt die Zahlung für die Veröffentlichung, ohne Freischaltung vor Zahlung."""
    st.subheader("Veröffentlichung freischalten")
    st.caption("Nach bestätigter Zahlung kann die Website mit Wunsch-URL und eigener Domain veröffentlicht werden.")
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID or not STRIPE_SUCCESS_URL:
        st.warning("Zahlung ist noch nicht eingerichtet. Hinterlegen Sie stripe_secret_key, stripe_price_id und stripe_success_url in den Streamlit-Secrets.")
        return
    if st.button("Zahlung vorbereiten", icon=":material/payment:", key="create_stripe_checkout", width="stretch"):
        try:
            st.session_state.stripe_checkout_url = create_stripe_checkout_session(user_id, user_email)
        except ValueError as error:
            st.error(str(error))
    checkout_url = str(st.session_state.get("stripe_checkout_url", ""))
    if checkout_url:
        st.link_button("Sicher bezahlen", checkout_url, icon=":material/open_in_new:", type="primary", width="stretch")


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
STRIPE_SECRET_KEY = str(st.secrets.get("stripe_secret_key", "")).strip()
STRIPE_PRICE_ID = str(st.secrets.get("stripe_price_id", "")).strip()
STRIPE_SUCCESS_URL = str(st.secrets.get("stripe_success_url", "")).strip().rstrip("?")
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
    "project_name": "ai-website-builder",
    "delete_confirmation": False,
    "show_botpress_chatbot": True,
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


def apply_app_language() -> None:
    """Übernimmt die Sprachwahl des Kunden für den nächsten App-Durchlauf."""
    st.session_state.app_language = APP_LANGUAGES[st.session_state.app_language_name]
    st.session_state.target_language = TARGET_LANGUAGE_BY_APP_CODE[
        st.session_state.app_language
    ]
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
    with st.container(border=True, key="authentication_shell"):
        intro_column, form_column = st.columns((1.05, 0.95), gap="large")

        with intro_column:
            st.badge("KI-gestützter Website-Workflow", icon=":material/auto_awesome:", color="blue")
            st.title(t("auth_title"), anchor=False)
            st.write(t("auth_subtitle"))
            st.space("small")
            st.markdown(":material/check_circle: **Planen** Sie Struktur, Inhalte und Markenauftritt.")
            st.markdown(":material/visibility: **Prüfen** Sie Ihr Ergebnis in einer Live-Vorschau.")
            st.markdown(":material/rocket_launch: **Veröffentlichen** Sie fertige Entwürfe direkt auf Vercel.")
            st.space("small")
            st.caption("Ihre Entwürfe, Einstellungen und Bearbeitungen bleiben Ihrem Konto zugeordnet.")

        with form_column:
            st.subheader("Ihr Arbeitsbereich", anchor=False)
            st.caption("Melden Sie sich an oder erstellen Sie ein neues Konto.")
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

    if prompt == "__next_customer_step__":
        return get_customer_guidance()
    coach_response = get_project_coach_response(prompt)
    if coach_response:
        return coach_response
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
if not user_info["subscribed"] and confirm_stripe_checkout(current_user_id):
    st.success("Zahlung bestätigt. Die Veröffentlichung ist jetzt freigeschaltet.")
    st.rerun()
render_help_chatbot()

if not user_info["subscribed"] and user_info["balance"] <= 0:
    st.error(t("balance_empty"))
    st.info(t("premium_info"))
    render_payment_ui(current_user_id, st.session_state.user_email)

if not user_info["subscribed"] and user_info["balance"] < 1.00:
    st.warning(t("low_balance", balance=user_info["balance"]))


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


def queue_html_update(html: str) -> None:
    """Plant ein sicheres HTML-Update für den nächsten Durchlauf."""
    index_html = require_complete_html(html)
    st.session_state.site_pages = {"index.html": index_html}
    st.session_state.pending_html = index_html


def build_website_zip() -> bytes:
    """Packt den aktuellen Vercel-Entwurf mit Seiten, CSS und Bildern in eine ZIP-Datei."""
    index_html = require_complete_html(st.session_state.generated_html)
    site_pages = dict(st.session_state.site_pages) or {"index.html": index_html}
    site_pages["index.html"] = index_html
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


def create_preview_html(html: str) -> str:
    """Ersetzt lokale Bildnamen in der Vorschau durch eingebettete Data-URLs."""
    preview_html = html

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
    title = escape(offer_name.strip() or "Unsere Angebote")
    price = escape(offer_price.strip() or "Preis auf Anfrage")
    details = escape(offer_details.strip() or "Individuell konfigurierbare Leistungen mit transparenter Beratung.")
    return f"""
<section id="angebote" data-page="angebote" class="bg-slate-950 px-6 py-16 text-white">
  <div class="mx-auto max-w-6xl">
    <p class="text-sm font-semibold uppercase tracking-wide text-cyan-300">Angebote</p>
    <h1 class="mt-3 text-4xl font-bold">{title}</h1>
    <p class="mt-4 max-w-2xl text-slate-300">{details}</p>
    <div class="mt-10 grid gap-6 md:grid-cols-3">
      <article class="rounded-lg border border-slate-700 bg-slate-900 p-6">
        <p class="text-sm text-cyan-300">Angebot 01</p><h2 class="mt-2 text-xl font-semibold">{title}</h2>
        <p class="mt-4 text-slate-300">{details}</p><p class="mt-6 text-2xl font-bold">{price}</p>
        <a class="mt-6 inline-block rounded bg-cyan-400 px-4 py-2 font-semibold text-slate-950" href="#kontakt">Jetzt anfragen</a>
      </article>
      <article class="rounded-lg border border-slate-700 bg-slate-900 p-6"><p class="text-sm text-cyan-300">Details</p><h2 class="mt-2 text-xl font-semibold">Transparent beraten</h2><p class="mt-4 text-slate-300">Leistung, Umfang und nächster Schritt klar erklärt.</p></article>
      <article class="rounded-lg border border-slate-700 bg-slate-900 p-6"><p class="text-sm text-cyan-300">Kontakt</p><h2 class="mt-2 text-xl font-semibold">Persönliche Anfrage</h2><p class="mt-4 text-slate-300">Wir beraten Sie passend zu Ihrem Bedarf.</p></article>
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
) -> str:
    """Übernimmt die ausgewählte Vorlage lokal und füllt sie mit Kundendaten."""
    company_name = escape(company_name.strip())
    business_email = escape(business_email.strip())
    slogan = escape(slogan.strip() or "Qualität, die für Sie arbeitet.")
    description = escape(description.strip() or "Wir verbinden fachliche Kompetenz mit persönlicher Beratung.")
    button_text = escape(button_text.strip() or "Ihr Angebot entdecken")
    footer_text = escape(
        footer_text.strip()
        or f"{company_name} | {business_email} | Impressum | Datenschutz"
    )
    chatbot_knowledge = escape(
        chatbot_knowledge.strip()
        or f"Willkommen bei {company_name}. Wie können wir Ihnen helfen?"
    )
    phone = escape(phone.strip())
    radius = "0" if border_style == "sharp" else "10px"
    text_color = contrast_text_color(background_color)
    muted_color = "#334155" if is_light_color(background_color) else "#cbd5e1"
    image_html = '<div class="image-placeholder">Bild oder Logo hochladen</div>'
    if image_file is not None:
        image_name = save_uploaded_image(image_file, "vorlagen-hero")
        image_html = f'<img class="hero-image" src="{image_name}" alt="{company_name}">'
    phone_html = f'<p>Telefon: {phone}</p>' if phone else ""
    navigation = (
        '<a href="leistungen.html">Leistungen</a><a href="angebote.html">Angebote</a>'
        '<a href="projekte.html">Projekte</a><a href="ueber-uns.html">Über uns</a>'
        '<a href="kontakt.html">Kontakt</a>'
        if multi_page
        else '<a href="#leistungen">Leistungen</a><a href="#ueber-uns">Über uns</a><a href="#kontakt">Kontakt</a>'
    )
    button_target = "angebote.html" if multi_page else "#leistungen"
    footer_html = f'''<footer class="site-footer"><section><strong>{company_name}</strong><p>{footer_text}</p></section><section><strong>Kontakt</strong><p><a href="mailto:{business_email}">{business_email}</a></p></section><section><strong>Rechtliches</strong><p><a href="#impressum">Impressum</a> · <a href="#datenschutz">Datenschutz</a></p></section><p class="footer-legal">© 2026 {company_name}. Alle Rechte vorbehalten.</p></footer>'''
    return f"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{company_name}</title>
<link rel="stylesheet" href="styles.css">
<style>:root {{ --background: {background_color}; --accent: {accent_color}; --text: {text_color}; --muted: {muted_color}; --radius: {radius}; }}</style></head>
<body><header><strong>{company_name}</strong><nav>{navigation}</nav></header>
<main><section class="container hero" id="hero"><div><span class="eyebrow">{escape(template_name)}</span><h1>{slogan}</h1><p>{description}</p><a class="button" href="{button_target}">{button_text}</a></div>{image_html}</section>
<section class="band"><div class="container" id="leistungen"><span class="eyebrow">Leistungen und Vorteile</span><h2>Kompetent. Persönlich. Verlässlich.</h2><div class="cards"><article class="card"><strong>01</strong><h3>Klare Leistungen</h3><p>Passende Lösungen mit nachvollziehbarer Beratung.</p></article><article class="card"><strong>02</strong><h3>Vertrauen schaffen</h3><p>Qualität, Transparenz und ein verbindlicher Service.</p></article><article class="card"><strong>03</strong><h3>Kontakt erleichtern</h3><p>Schnell und direkt zu Ihrer persönlichen Anfrage.</p></article></div></div></section>
<section class="container" id="ueber-uns"><span class="eyebrow">Über uns</span><h2>Ein Auftritt, der zu Ihrem Unternehmen passt.</h2><p>{description}</p></section>
<section class="band"><div class="container contact" id="kontakt"><div><span class="eyebrow">Kontakt</span><h2>Wir freuen uns auf Ihre Anfrage.</h2><p><a href="mailto:{business_email}">{business_email}</a></p>{phone_html}</div><div class="card"><h3>Persönlich beraten lassen</h3><p>Schreiben Sie uns direkt. Wir melden uns zeitnah bei Ihnen.</p><a class="button" href="mailto:{business_email}">E-Mail schreiben</a></div></div></section></main>
{footer_html}<aside class="customer-chatbot"><button type="button" aria-expanded="false">?</button><section hidden><strong>{company_name} Assistent</strong><p>{chatbot_knowledge}</p></section></aside><script>const chatbot=document.querySelector('.customer-chatbot'),toggle=chatbot.querySelector('button'),panel=chatbot.querySelector('section');toggle.onclick=()=>{{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));}};</script></body></html>"""


def build_customized_template_styles() -> str:
    """Liefert das gemeinsame Design für alle statischen Vorlagen-Seiten."""
    return """* { box-sizing: border-box; } body { margin: 0; background: var(--background); color: var(--text); font: 16px/1.55 Arial, sans-serif; } header { padding: 20px max(5vw, 24px); border-bottom: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } header, nav { display: flex; gap: 18px; flex-wrap: wrap; justify-content: space-between; align-items: center; } nav a, .button, .site-footer a { color: inherit; text-decoration: none; } main, .container { max-width: 1120px; margin: auto; padding: 70px 24px; } .hero, .contact { display: grid; grid-template-columns: 1.1fr .9fr; gap: 40px; align-items: center; } .eyebrow { color: var(--accent); font-size: 13px; font-weight: 700; text-transform: uppercase; } h1 { font-family: Georgia, serif; font-size: clamp(2.4rem, 5vw, 4.4rem); line-height: 1.05; margin: 14px 0; } p { color: var(--muted); } .button { display: inline-block; margin-top: 18px; padding: 13px 19px; border-radius: var(--radius); background: var(--accent); color: #111827; font-weight: 700; } .hero-image, .image-placeholder { width: 100%; min-height: 310px; object-fit: cover; border-radius: var(--radius); border: 1px dashed var(--accent); display: grid; place-items: center; color: var(--accent); padding: 20px; } .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 45px; } .card { border-top: 3px solid var(--accent); background: color-mix(in srgb, var(--text) 6%, transparent); padding: 24px; margin-top: 32px; } .band { background: color-mix(in srgb, var(--text) 6%, transparent); } .site-footer { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 28px; padding: 34px max(5vw, 24px) 20px; border-top: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } .site-footer strong { display: block; } .site-footer p { margin: 8px 0 0; font-size: 13px; } .footer-legal { grid-column: 1 / -1; padding-top: 16px; border-top: 1px solid color-mix(in srgb, var(--text) 18%, transparent); } .customer-chatbot { position: fixed; right: 24px; bottom: 24px; z-index: 10; } .customer-chatbot button { width: 52px; height: 52px; border: 0; border-radius: 50%; background: var(--accent); color: #111827; cursor: pointer; font-weight: 700; font-size: 20px; } .customer-chatbot section { width: min(300px, calc(100vw - 48px)); margin-bottom: 10px; padding: 18px; border: 1px solid color-mix(in srgb, var(--text) 18%, transparent); border-radius: var(--radius); background: var(--background); box-shadow: 0 16px 38px rgba(15, 23, 42, .22); } @media (max-width: 700px) { header, .hero, .contact { display: block; } nav { margin-top: 12px; } .hero-image, .image-placeholder { margin-top: 26px; min-height: 220px; } .cards, .site-footer { grid-template-columns: 1fr; } }"""


def build_customized_template_pages(
    company_name: str, business_email: str, background_color: str,
    accent_color: str, description: str,
) -> dict[str, str]:
    """Erstellt echte statische Angebots- und Kontaktseiten der Kundenwebsite."""
    company_name = escape(company_name.strip())
    business_email = escape(business_email.strip())
    description = escape(description.strip() or "Individuelle Beratung und passende Lösungen.")
    text_color = contrast_text_color(background_color)
    muted_color = "#334155" if is_light_color(background_color) else "#cbd5e1"
    head = f"""<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{company_name}</title><link rel="stylesheet" href="styles.css"><style>:root{{--background:{background_color};--accent:{accent_color};--text:{text_color};--muted:{muted_color};--radius:10px;}}</style></head>"""
    navigation = f'<nav><a href="index.html">Start</a><a href="leistungen.html">Leistungen</a><a href="angebote.html">Angebote</a><a href="projekte.html">Projekte</a><a href="ueber-uns.html">Über uns</a><a href="kontakt.html">Kontakt</a></nav>'
    services = f"""<!doctype html><html lang="de">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>Leistungen für Ihren Erfolg.</h1><p>{description}</p><section class="card"><h2>Individuelle Beratung</h2><p>Wir analysieren Ihren Bedarf und entwickeln eine passende Lösung.</p></section><section class="card"><h2>Verlässliche Umsetzung</h2><p>Klare Abläufe, hohe Qualität und ein verbindlicher Ansprechpartner.</p></section><section class="card"><h2>Nachhaltiger Service</h2><p>Auch nach dem Projekt bleiben wir persönlich für Sie erreichbar.</p><a class="button" href="kontakt.html">Jetzt anfragen</a></section></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>"""
    projects = f"""<!doctype html><html lang="de">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>Projekte</h1><p>{description}</p><section class="card"><h2>Ausgewählte Projekte</h2><p>Einblick in Lösungen, die wir gemeinsam mit unseren Kunden umgesetzt haben.</p></section><section class="card"><h2>Unser Vorgehen</h2><p>Von der ersten Idee bis zur verlässlichen Umsetzung begleiten wir jedes Vorhaben.</p></section><section class="card"><h2>Ihr nächstes Projekt</h2><p>Wir freuen uns darauf, mehr über Ihr Vorhaben zu erfahren.</p><a class="button" href="kontakt.html">Projekt anfragen</a></section></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>"""
    about = f"""<!doctype html><html lang="de">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>Über uns</h1><p>{description}</p><section class="card"><h2>Unsere Arbeitsweise</h2><p>Wir verbinden fachliche Kompetenz mit klarer Kommunikation und persönlicher Beratung.</p></section><section class="card"><h2>Unser Anspruch</h2><p>Qualität, Verlässlichkeit und eine langfristige Zusammenarbeit stehen im Mittelpunkt.</p></section><section class="card"><h2>Persönlich erreichbar</h2><p>Wir nehmen uns Zeit für Ihr Anliegen und entwickeln passende Lösungen.</p><a class="button" href="kontakt.html">Kontakt aufnehmen</a></section></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>"""
    offers = f"""<!doctype html><html lang="de">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>Unsere Angebote</h1><p>{description}</p><section class="card"><h2>Individuelles Angebot</h2><p>{description}</p><a class="button" href="kontakt.html">Angebot anfragen</a></section></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>"""
    contact = f"""<!doctype html><html lang="de">{head}<body><header><strong>{company_name}</strong>{navigation}</header><main><h1>Kontakt</h1><p>Schreiben Sie uns. Wir melden uns zeitnah bei Ihnen.</p><section class="card"><h2>Kontakt aufnehmen</h2><p><a href="mailto:{business_email}">{business_email}</a></p><a class="button" href="mailto:{business_email}">E-Mail schreiben</a></section></main><footer>{company_name} · <a href="mailto:{business_email}">{business_email}</a></footer></body></html>"""
    return {"leistungen.html": services, "angebote.html": offers, "projekte.html": projects, "ueber-uns.html": about, "kontakt.html": contact, "styles.css": build_customized_template_styles()}


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert vollständigen HTML-Code von OpenAI an."""
    if not deduct_tokens(current_user_id):
        raise ValueError(
            "Ihr KI-Guthaben reicht für diese Anfrage nicht aus."
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
    chatbot_knowledge = str(st.session_state.get("client_chatbot_knowledge", "")).strip()
    web3forms_access_key = str(
        st.session_state.get("client_web3forms_access_key", "")
    ).strip()

    if business_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", business_email):
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
Du bist ein professioneller, internationaler Frontend-Entwickler und Webdesigner
fuer eine Webbuilder-SaaS-Plattform. Deine Aufgabe ist es, eine massgeschneiderte,
moderne Website exakt anhand der bereitgestellten Kundendaten zu erstellen.

REGELN FUER DIE GENERIERUNG:
- Nutze valides HTML5, beginne mit <!doctype html> und binde Tailwind CSS ueber
    https://cdn.tailwindcss.com ein.
- Orientiere dich strikt an der gewaehlten Branche, den Farben und den Kundendaten.
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
- Integriere unten rechts ein schwebendes, animiertes Chatbot-Widget, das ausschliesslich
    fuer {company_name} geschrieben ist und keine Daten anderer Personen enthaelt.
- Verwende ein JavaScript-Array mit hilfreichen, branchenspezifischen Antworten basierend
    auf Branche und Kundenbeschreibung.
- Berücksichtige dieses vom Kunden bereitgestellte Chatbot-Wissen in den Antworten:
    {chatbot_knowledge or 'Keine zusätzlichen Angaben; erfinde keine Öffnungszeiten, Preise oder Angebote.'}
- Bei Fragen nach Kontakt oder E-Mail verweist der Bot auf {business_email}; bei einer
    nichtdeutschen Website verwende die entsprechende Uebersetzung.
- Lies Bot-Antworten mit window.speechSynthesis in der passenden Sprache vor. Entferne
    vor dem Vorlesen Links, Emojis und HTML per JavaScript-Regex.

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
    st.subheader("Geschäfts- und Kontaktdaten des Kunden")
    contact_column, company_column = st.columns(2)
    with contact_column:
        st.text_input(
            "E-Mail-Adresse für Kundenanfragen",
            placeholder="z. B. info@unternehmen.de",
            key="client_business_email",
        )
    with company_column:
        st.text_input(
            "Offizieller Unternehmensname",
            placeholder="z. B. Autohaus Müller GmbH",
            key="client_company_name",
        )
    st.text_input(
        "Slogan oder Hauptüberschrift (optional)",
        placeholder="z. B. Ihr Partner für Qualität und Vertrauen",
        key="client_company_slogan",
    )
    contact_details_column, form_column = st.columns(2)
    with contact_details_column:
        st.text_input(
            "Telefonnummer (optional)",
            placeholder="z. B. +49 30 123456",
            key="client_business_phone",
        )
    with form_column:
        st.text_input(
            "Web3Forms Access Key (optional)",
            type="password",
            help="Mit diesem Schlüssel erhält die generierte Website ein Web3Forms-Kontaktformular.",
            key="client_web3forms_access_key",
        )
    st.text_area(
        "Chatbot-Wissen (optional)",
        placeholder="Zum Beispiel: Öffnungszeiten, Preise, Angebote, Terminvereinbarung oder häufige Fragen.",
        key="client_chatbot_knowledge",
        height=110,
    )


def render_language_selector() -> tuple[dict[str, str], str]:
    """Leitet Website-Sprache und Leserichtung aus der globalen Sprachwahl ab."""
    target_language = TARGET_LANGUAGE_BY_APP_CODE[st.session_state.app_language]
    st.session_state.target_language = target_language
    return SUPPORTED_LANGUAGES[target_language], target_language


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
) -> None:
    """Zeigt die Vorlage mit allen aktuell eingegebenen Kundendaten."""
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
    button_text = escape(str(st.session_state.get("template_button_text", "")).strip() or "Ihr Angebot entdecken")
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
        component_state = st.session_state.get("clickable_template_editor")
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
        component_state = st.session_state.get("clickable_template_editor")
        page = getattr(component_state, "navigated", None)
        if page in {"start", "leistungen", "angebote", "projekte", "ueber_uns", "kontakt"}:
            st.session_state.template_preview_page = page

    CLICKABLE_TEMPLATE_EDITOR(
        key="clickable_template_editor",
        data={
            "companyName": str(st.session_state.get("client_company_name", "")).strip() or template_name,
            "heading": str(st.session_state.get("template_hero_heading", "")).strip()
            or str(st.session_state.get("client_company_slogan", "")).strip()
            or "Eine Vorlage mit klarer Struktur und Raum für Ihre Inhalte.",
            "description": str(st.session_state.get("template_custom_description", "")).strip()
            or "Sie ersetzen Unternehmensdaten, Texte und Bilder direkt in dieser Vorlage. Die Gestaltung, Abstände und Inhaltsbereiche bleiben professionell geordnet.",
            "buttonText": str(st.session_state.get("template_button_text", "")).strip()
            or "Ihr Angebot entdecken",
            "templateSections": [
                {
                    "title": item.partition("|")[0].strip(),
                    "text": item.partition("|")[2].strip()
                    or str(st.session_state.get("template_custom_description", "")).strip()
                    or "Individuell auf Ihr Unternehmen abgestimmt.",
                }
                for item in str(st.session_state.get("template_sections_text", sections)).replace(",", "\n").splitlines()
                if item.strip()
            ],
            "footerText": str(st.session_state.get("template_footer_text", "")).strip()
            or f"{company_name} | {business_email} | Impressum | Datenschutz",
            "chatbotKnowledge": str(st.session_state.get("client_chatbot_knowledge", "")).strip(),
            "multiPage": st.session_state.get("page_structure") == "Mehrseitige Website",
            "businessEmail": str(st.session_state.get("client_business_email", "")).strip()
            or "Ihre Kontakt-E-Mail",
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


def render_template_and_design_ui() -> str:
    """Rendert die Branchenvorlagen fuer einen gefuehrten Website-Entwurf."""
    st.subheader(t("template"))
    selected_language, language_name = render_language_selector()
    st.caption(f"{t('target_language')}: {language_name}")

    template_column, design_column = st.columns(2)
    with template_column:
        selected_template_name = st.selectbox(
            t("choose_industry"),
            list(TEMPLATES),
            format_func=lambda name: f"{TEMPLATES[name]['icon']} {name}",
            key="template_name",
        )
        current_template = TEMPLATES[selected_template_name]
        st.info(current_template["description"])

    if st.session_state.get("template_preview_template") != selected_template_name:
        st.session_state.template_preview_template = selected_template_name
        st.session_state.template_preview_page = "start"

    with design_column:
        background_presets = st.segmented_control(
            "Hintergrund-Vorlage",
            list(BACKGROUND_PRESET_COLORS),
            default="Weiß",
            key="template_background_preset",
            on_change=apply_background_preset,
        )
        preset_background_color = BACKGROUND_PRESET_COLORS[background_presets]
        st.color_picker(
            f"{t('background_color')} ({background_presets})",
            preset_background_color,
            key=f"template_preset_background_{background_presets}",
            disabled=True,
            help="Die Hintergrundfarbe wird über die Auswahl der Hintergrund-Vorlage festgelegt.",
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
        "Button-Text in der Vorlage",
        placeholder="z. B. Termin vereinbaren",
        key="template_button_text",
        help="Die Beschriftung wird direkt in der Live-Vorlage und später auf der Website angezeigt.",
    )
    content_columns = st.columns(2)
    with content_columns[0]:
        st.text_input(
            "Überschrift der Vorlage",
            placeholder="z. B. Ihr Partner für Qualität und Vertrauen",
            key="template_hero_heading",
        )
    with content_columns[1]:
        st.text_area(
            "Beschreibung in der Vorlage",
            placeholder="Beschreiben Sie Angebot, Zielgruppe und Ihre besonderen Stärken.",
            key="template_custom_description",
            height=100,
        )

    st.text_area(
        "Vorlagenabschnitte",
        value=str(st.session_state.get("template_sections_text", current_template["sections"])),
        help="Ein Abschnitt pro Zeile. Neue Zeile hinzufügen erstellt einen Abschnitt; Zeile löschen entfernt ihn. Optional: Überschrift | Beschreibung.",
        key="template_sections_text",
        height=150,
    )
    st.text_input(
        "Footer-Text",
        value=str(st.session_state.get("template_footer_text", "")),
        placeholder="z. B. Muster GmbH | Impressum | Datenschutz",
        key="template_footer_text",
    )

    render_template_preview(
        selected_template_name,
        current_template["sections"],
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


def render_section_configuration() -> str:
    """Erfasst den gewünschten Umfang und die Kerninhalte eines Entwurfs."""
    st.subheader("Abschnitte und Inhalte")
    selected_sections = st.multiselect(
        "Welche Bereiche soll die Website enthalten?",
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
    )
    if not selected_sections:
        st.warning("Wählen Sie mindestens einen Abschnitt aus.")

    details: list[str] = []
    if "Hero und Willkommensbereich" in selected_sections:
        with st.expander("Hero und Willkommensbereich", expanded=True):
            title = st.text_input("Hauptüberschrift", key="section_hero_title")
            subtitle = st.text_area("Untertitel oder Slogan", key="section_hero_subtitle")
            details.append(f"Hero: Titel '{title}', Untertitel '{subtitle}'.")
    if "Über uns" in selected_sections:
        with st.expander("Über uns"):
            about = st.text_area("Text für Über uns", key="section_about_text")
            details.append(f"Über uns: {about}")
    if "Leistungen oder Produkte" in selected_sections:
        with st.expander("Leistungen oder Produkte"):
            services = st.text_area(
                "Leistungen oder Produkte, jeweils durch Komma trennen",
                key="section_services",
            )
            details.append(f"Leistungen oder Produkte: {services}")
    if "Galerie oder Projekte" in selected_sections:
        with st.expander("Galerie oder Projekte"):
            projects = st.text_area("Projekt- oder Galeriebeschreibung", key="section_projects")
            details.append(f"Galerie oder Projekte: {projects}")
    if "Kundenstimmen oder Referenzen" in selected_sections:
        with st.expander("Kundenstimmen oder Referenzen"):
            references = st.text_area("Referenzen oder Vertrauensargumente", key="section_references")
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
    if st.session_state.get("creation_mode") == "Professionelle Vorlage":
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

    
def publish_website() -> None:
    """Veröffentlicht den aktuellen HTML-Entwurf auf Vercel."""
    html = require_complete_html(st.session_state.generated_html)
    requested_project_name = str(st.session_state.project_name).strip()
    project_name = (
        safe_project_name(requested_project_name)
        if requested_project_name
        else create_deployment_project_name()
    )
    st.session_state.project_name = project_name

    site_pages = dict(st.session_state.site_pages) or {"index.html": html}
    site_pages["index.html"] = html
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

    # project_name hier NICHT verändern: Es gehört zum Streamlit-Textfeld.
    st.session_state.live_url = get_public_url(deployment)
    st.session_state.deployment_url = f"https://{deployment_url}"
    st.session_state.deployment_id = deployment_id
    st.session_state.published_html = html


def render_domain_and_deployment_ui() -> None:
    """Rendert die Premium-geschuetzte Konfiguration fuer die Vercel-Veröffentlichung."""
    st.header("Veröffentlichung und Liveschaltung")

    if not st.session_state.generated_html:
        st.info("Erstellen oder laden Sie zuerst eine Website, bevor Sie sie veröffentlichen.")
        return

    if not user_info["subscribed"]:
        st.warning(
            "Prüfen Sie Ihren Entwurf oben in der Live-Vorschau. Nach der Zahlung wird die Veröffentlichung mit Wunsch-URL oder eigener Domain freigeschaltet."
        )
        render_payment_ui(current_user_id, st.session_state.user_email)
        return

    st.caption(
        "Die Website wird auf Vercel veröffentlicht. Die finale Adresse wird nach "
        "der erfolgreichen Vercel-Antwort angezeigt."
    )
    st.download_button(
        "Website-Paket als ZIP herunterladen",
        data=build_website_zip(),
        file_name="kunden-website.zip",
        mime="application/zip",
        icon=":material/folder_zip:",
        key="download_website_zip",
        width="stretch",
    )
    domain_type = st.radio(
        "Adresse wählen",
        ["Vercel-Projektadresse", "Eigene Domain verbinden"],
        key="domain_type",
    )

    if domain_type == "Vercel-Projektadresse":
        requested_name = st.text_input(
            "Name für die Vercel-Projektadresse",
            value=st.session_state.project_name,
            placeholder="z. B. autohaus-mueller",
            key="deployment_project_name",
            help="Vercel vergibt die endgültige .vercel.app-Adresse beim Deployment.",
        )
        if requested_name:
            st.caption(
                f"Projektname: {safe_project_name(requested_name)}. "
                "Die genaue Live-URL wird von Vercel bestätigt."
            )

        if st.button(
            "Jetzt auf Vercel veröffentlichen",
            icon=":material/rocket_launch:",
            type="primary",
            key="publish_from_domain_center",
            width="stretch",
        ):
            st.session_state.project_name = safe_project_name(requested_name or "")
            with st.status("Vercel veröffentlicht die Website ...", expanded=True) as status:
                try:
                    publish_website()
                    status.update(label="Die Website wurde veröffentlicht.", state="complete")
                    st.rerun()
                except ValueError as error:
                    status.update(label="Veröffentlichung fehlgeschlagen", state="error")
                    st.error(str(error))
    else:
        custom_domain = st.text_input(
            "Bereits gekaufte eigene Domain",
            placeholder="z. B. www.mein-unternehmen.de",
            key="custom_domain",
        )
        if custom_domain:
            st.info(
                "Die Domain muss vor der Verknüpfung gekauft sein. Für die automatische "
                "Anbindung benötigen Sie eine verifizierte Domain, passende DNS-Einträge und eine "
                "serverseitige Vercel-Domain-API-Integration."
            )


def render_customer_service_ui(user_id: int, user_email: str) -> None:
    """Ermöglicht Kunden Feedback und nachvollziehbare Supportanfragen."""
    st.header("Kundenservice")
    st.caption(
        "Melden Sie einen Fehler, eine Frage oder Feedback. Beschreiben Sie den betroffenen "
        "Bereich und die Schritte möglichst genau, damit wir schnell helfen können."
    )

    with st.form("customer_service_form", clear_on_submit=True):
        request_type, app_area = st.columns(2)
        with request_type:
            support_type = st.selectbox(
                "Anliegen",
                ["Fehler melden", "Frage zur Nutzung", "Idee oder Feedback"],
                key="support_request_type",
            )
        with app_area:
            affected_area = st.selectbox(
                "Betroffener App-Bereich",
                [
                    "Website planen", "Vorlage und Design", "Bilder und Inhalte",
                    "Vorschau und Editor", "Veröffentlichung", "Anmeldung oder Konto",
                    "Andere Funktion",
                ],
                key="support_app_area",
            )
        subject = st.text_input(
            "Kurzer Betreff",
            placeholder="z. B. Vorschau lädt nach Bild-Upload nicht",
            key="support_subject",
        )
        description = st.text_area(
            "Was ist passiert oder welches Feedback möchten Sie geben?",
            placeholder="Beschreiben Sie das gewünschte Ergebnis und was stattdessen passiert ist.",
            key="support_description",
            height=150,
        )
        reproduction_steps = st.text_area(
            "Schritte bis zum Problem (optional)",
            placeholder="1. Vorlage wählen\n2. Bild hochladen\n3. Vorschau öffnen",
            key="support_reproduction_steps",
            height=110,
        )
        submitted = st.form_submit_button(
            "Anfrage an Kundenservice senden",
            icon=":material/send:",
            type="primary",
            width="stretch",
        )

    if submitted:
        if len(subject.strip()) < 4:
            st.error("Bitte geben Sie einen kurzen Betreff mit mindestens 4 Zeichen ein.")
        elif len(description.strip()) < 15:
            st.error("Bitte beschreiben Sie Ihr Anliegen mit mindestens 15 Zeichen.")
        else:
            save_support_request(
                user_id, support_type, affected_area, subject, description, reproduction_steps
            )
            st.success("Ihre Anfrage wurde gespeichert. Der Kundenservice kann sie jetzt prüfen.")

    own_requests = get_support_requests(user_id)
    st.subheader("Meine Anfragen", anchor=False)
    if not own_requests:
        st.caption("Sie haben noch keine Anfrage gesendet.")
    for request_id, support_type, affected_area, subject, description, steps, created_at in own_requests:
        with st.expander(f"#{request_id} · {support_type} · {subject}"):
            st.caption(f"Bereich: {affected_area} · Gesendet: {created_at[:16].replace('T', ' ')} UTC")
            st.write(description)
            if steps:
                st.code(steps, language=None)

    if user_email.strip().lower() != SUPPORT_ADMIN_EMAIL or not SUPPORT_ADMIN_EMAIL:
        return

    st.divider()
    st.subheader("Kundenservice-Inbox", anchor=False)
    support_requests = get_support_requests()
    if not support_requests:
        st.caption("Noch keine Kundenanfragen vorhanden.")
    for request_id, requester_email, support_type, affected_area, subject, description, steps, created_at in support_requests:
        with st.expander(f"#{request_id} · {support_type} · {subject}"):
            st.caption(
                f"Kunde: {requester_email} · Bereich: {affected_area} · "
                f"Gesendet: {created_at[:16].replace('T', ' ')} UTC"
            )
            st.write(description)
            if steps:
                st.code(steps, language=None)


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
    with st.container(border=True):
        st.subheader(t("account"))
        st.caption(st.session_state.user_email)

        if user_info["subscribed"]:
            st.badge(t("premium_active"), icon=":material/workspace_premium:", color="green")
        else:
            st.caption(t("balance", balance=user_info["balance"]))

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
        st.success("Ihr Entwurf wurde gespeichert.")
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
    [t("new_website"), t("load_published"), "Kundenservice", "Datenschutz"]
)



with new_tab:
    st.subheader("Website planen")
    st.selectbox(
        "Schnellstart für typische Use Cases",
        list(DESIGN_USE_CASES),
        help="Übernimmt eine passende Startkonfiguration. Alle Angaben können danach angepasst werden.",
        key="design_use_case",
        on_change=apply_design_use_case,
    )
    creation_mode = st.segmented_control(
        "Wie möchten Sie starten?",
        ["Professionelle Vorlage", "Freier Entwurf", "Bestehenden Entwurf anpassen"],
        default="Professionelle Vorlage",
        key="creation_mode",
    )
    page_structure = st.segmented_control(
        "Seitenstruktur",
        ["Eine übersichtliche Seite", "Mehrseitige Website"],
        default="Eine übersichtliche Seite",
        key="page_structure",
    )

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
        if creation_mode == "Professionelle Vorlage":
            description = str(st.session_state.get("template_custom_description", ""))
        else:
            description = st.text_area(
                "Unternehmensbeschreibung und besondere Wünsche",
                placeholder="Beschreiben Sie Angebot, Zielgruppe, Standort und die wichtigsten Inhalte Ihrer Website.",
                key="creation_description",
                height=150,
            )
        initial_image = st.file_uploader(
            "Logo oder Bild hochladen (optional)",
            type=["png", "jpg", "jpeg", "webp"],
            key="initial_image",
        )
        image_placement = st.selectbox(
            "Wo soll dieses Bild erscheinen?",
            [
                "Logo",
                "Hero- und Willkommensbereich",
                "Über-uns-Bereich",
                "Projektbereich",
            ],
            disabled=initial_image is None,
            key="image_placement",
        )

        st.divider()
        render_client_contact_ui()
        submit_label = (
            "Vorlage mit Kundendaten übernehmen"
            if creation_mode == "Professionelle Vorlage"
            else "Website erstellen"
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
                    if not company_name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", business_email):
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
                        str(st.session_state.get("client_chatbot_knowledge", "")),
                    )
                    queue_html_update(html)
                    if page_structure == "Mehrseitige Website":
                        st.session_state.site_pages.update(
                            build_customized_template_pages(
                                company_name,
                                business_email,
                                background_color,
                                str(st.session_state.template_accent_color),
                                description,
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
    st.subheader("Öffentliche Website laden")
    st.caption(
        "Die Original-Website wird geladen, ohne HTML oder Design vor der Bearbeitung zu ändern."
    )

    live_url_input = st.text_input(
        "Öffentlicher Live-Link",
        placeholder="https://ihre-website.vercel.app",
        key="manage_live_url",
    )

    if st.button(
        "⚙️ Original-Website laden",
        type="primary",
        width="stretch",
    ):
        if not live_url_input.strip():
            st.warning("Bitte geben Sie einen Live-Link ein.")
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
                    status.update(
                        label="❌ Laden fehlgeschlagen",
                        state="error",
                    )
                    st.error(str(error))

with service_tab:
    render_customer_service_ui(current_user_id, st.session_state.user_email)

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

st.divider()
render_saas_preview_and_testing_window()

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
