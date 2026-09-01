import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
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
    }
    [data-testid="stTabs"] [role="tab"] {
        font-weight: 600;
    }
    [data-testid="stExpander"] {
        border-color: rgba(103, 232, 249, 0.18);
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


def activate_premium_demo(user_id: int) -> None:
    """Aktiviert Premium fuer lokale Tests, bis eine Zahlungsintegration vorhanden ist."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "UPDATE users SET is_subscribed = 1 WHERE id = ?",
            (user_id,),
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

DEFAULT_STATE = {
    "user_id": None,
    "user_email": "",
    "target_language": "Deutsch",
    "generated_html": "",
    "html_editor": "",
    "pending_html": "",
    "published_html": "",
    "assets": {},
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


def t(key: str, **values: object) -> str:
    """Gibt den sichtbaren App-Text in der ausgewaehlten Sprache zurueck."""
    language = str(st.session_state.app_language)
    text = TRANSLATIONS.get(language, TRANSLATIONS["de"]).get(key, key)
    return text.format(**values)


st.selectbox(
    t("app_language"),
    list(APP_LANGUAGES),
    format_func=lambda name: APP_LANGUAGE_LABELS[name],
    key="app_language_name",
    on_change=lambda: st.session_state.update(
        app_language=APP_LANGUAGES[st.session_state.app_language_name]
    ),
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
    st.title(t("auth_title"))
    st.caption(t("auth_subtitle"))
    login_tab, register_tab = st.tabs([t("login"), t("register")])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input(t("email"), key="login_email")
            password = st.text_input(t("password"), type="password", key="login_password")
            submitted = st.form_submit_button(t("login"), type="primary")

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
            password = st.text_input(t("password"), type="password", key="registration_password")
            password_confirmation = st.text_input(
                t("confirm_password"),
                type="password",
                key="registration_password_confirmation",
            )
            submitted = st.form_submit_button(t("register"), type="primary")

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

    if any(word in question for word in ("veröffent", "veroeffent", "vercel", "domain")):
        return (
            "Wählen Sie nach dem Erstellen Ihrer Website den Bereich "
            "„Veröffentlichung und Liveschaltung“. Dort können Sie einen "
            "Vercel-Projektnamen festlegen und die Website veröffentlichen."
        )
    if any(word in question for word in ("vorschau", "test", "prüf", "pruef")):
        return (
            "Im Bereich „Interaktive Live-Vorschau und Testzentrum“ können Sie "
            "Ihre Website testen und den HTML-Code direkt anpassen."
        )
    if any(word in question for word in ("bild", "logo", "foto")):
        return (
            "Sie können beim Erstellen der Website ein Logo oder Bild hochladen. "
            "Weitere Bilder lassen sich später im Bereich „Bilder“ austauschen."
        )
    return (
        "Beschreiben Sie Ihr Unternehmen, wählen Sie Branche und Design und "
        "erstellen Sie anschließend Ihren Website-Entwurf. Wobei darf ich Ihnen helfen?"
    )


def render_help_chatbot() -> None:
    """Rendert einen schwebenden Hilfe-Chat mit scrollbarer Nachrichtenhistorie."""
    if not st.session_state.show_botpress_chatbot:
        return

    with st.popover(
        "",
        icon=":material/forum:",
        help="Hilfe-Chat öffnen",
        key="help_chat_launcher",
        type="primary",
    ):
        st.subheader("Hilfe-Chat", anchor=False)
        with st.container(height=220, border=True, key="help_chat_history"):
            for message in st.session_state.chat_messages:
                with st.chat_message(
                    message["role"], avatar=":material/support_agent:"
                ):
                    st.write(message["content"])

        prompt = st.chat_input("Schreiben Sie Ihre Frage", key="help_chat_input")
        if prompt:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": get_help_response(prompt)}
            )
            st.rerun()


if st.session_state.user_id is None:
    show_authentication()
    st.stop()

current_user_id = int(st.session_state.user_id)
user_info = get_user_status(current_user_id)
render_help_chatbot()

if not user_info["subscribed"] and user_info["balance"] <= 0:
    st.error(t("balance_empty"))
    st.info(t("premium_info"))
    if st.button(
        t("activate_premium"),
        type="primary",
        icon=":material/workspace_premium:",
    ):
        activate_premium_demo(current_user_id)
        st.rerun()
    st.stop()

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

    if "<html" not in html_lower and "<!doctype" not in html_lower:
        raise ValueError("Der Inhalt enthält keine vollständige HTML-Website.")

    return html


def ensure_customer_email(html: str, business_email: str) -> str:
    """Stellt sicher, dass der Entwurf die konfigurierte Kontaktadresse verwendet."""
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
    st.session_state.pending_html = require_complete_html(html)


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
    hostname = urlparse(live_url).hostname or ""
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


def ask_ai_for_html(system_instruction: str, user_instruction: str) -> str:
    """Fordert vollständigen HTML-Code von OpenAI an."""
    if not deduct_tokens(current_user_id):
        raise ValueError(
            "Ihr KI-Guthaben reicht für diese Anfrage nicht aus."
        )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.35,
        timeout=90,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
    )

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

{LANGUAGE_SWITCHER_REQUIREMENTS}

GESCHAEFTS- UND KONTAKTDATEN:
- Offizieller Unternehmensname: {company_name}
- Geschaeftliche Kontakt-E-Mail: {business_email}
- Verwende den Unternehmensnamen in Navigation, Hero, Seitentitel und Footer.
- Zeige die Kontakt-E-Mail im Kontaktbereich und Footer an.

KONTAKTFORMULAR:
{f'''- Erstelle einen sichtbaren, modernen Kontaktbereich mit diesem exakten Formularbeginn:
    <form action="https://api.web3forms.com/submit" method="POST" class="mt-8 space-y-4">
    <input type="hidden" name="access_key" value="{web3forms_access_key}">
    <input type="hidden" name="subject" value="Neue Anfrage für {company_name}">
    <input type="hidden" name="to_email" value="{business_email}">
- Das Formular braucht sichtbare Labels sowie die Pflichtfelder name, email und message.
- Baue vor dem Absenden per JavaScript ein verstecktes Feld name="redirect" ein und
    setze dessen value auf window.location.href.''' if web3forms_access_key else '''- Erstelle einen sichtbaren Kontaktbereich mit der E-Mail-Adresse {business_email}.
    setze dessen value auf window.location.href.''' if web3forms_access_key else f'''- Erstelle einen sichtbaren Kontaktbereich mit der E-Mail-Adresse {business_email}.
- Verwende kein externes Formular und keinen Web3Forms Access Key.'''}

CHATBOT MIT VOICE:
- Integriere unten rechts ein schwebendes, animiertes Chatbot-Widget, das ausschliesslich
    fuer {company_name} geschrieben ist und keine Daten anderer Personen enthaelt.
- Verwende ein JavaScript-Array mit hilfreichen, branchenspezifischen Antworten basierend
    auf Branche und Kundenbeschreibung.
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
        html = ensure_multi_page_navigation(html)
    queue_html_update(html)


def render_client_contact_ui() -> None:
    """Erfasst die Kontaktdaten, die in jede neue Kundenwebsite einfliessen."""
    st.subheader("Geschäfts- und Kontaktdaten des Kunden")
    contact_column, company_column, form_column = st.columns(3)
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
    with form_column:
        st.text_input(
            "Web3Forms Access Key",
            type="password",
            help="Optional. Mit diesem Schlüssel erhält die generierte Website ein Web3Forms-Kontaktformular.",
            key="client_web3forms_access_key",
        )


def render_language_selector() -> tuple[dict[str, str], str]:
    """Liest die globale Sprache und Leserichtung der zu erzeugenden Website."""
    target_language = st.selectbox(
        t("target_language"),
        list(SUPPORTED_LANGUAGES),
        key="target_language",
    )
    return SUPPORTED_LANGUAGES[target_language], target_language


def render_template_preview(
        template_name: str,
    sections: str,
        background_color: str,
        accent_color: str,
        border_style: str,
) -> None:
        """Zeigt eine visuelle Vorschau, bevor Kundendaten benötigt werden."""
        radius = "0px" if border_style == "sharp" else "18px"
        st.caption("Vorlagenvorschau")
        st.html(
                f"""
                <section style="background:{background_color}; border:1px solid {accent_color}; border-radius:{radius}; color:#f8fafc; overflow:hidden; font-family:Arial,sans-serif;">
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:16px 22px; border-bottom:1px solid rgba(255,255,255,.18);">
                        <strong style="font-size:18px;">{template_name}</strong>
                        <span style="font-size:13px; opacity:.78;">Start &nbsp; Leistungen &nbsp; Über uns &nbsp; Kontakt</span>
                    </div>
                    <div style="padding:38px 22px 30px; background:linear-gradient(135deg, {background_color}, {accent_color}55);">
                        <p style="margin:0 0 9px; color:{accent_color}; font-size:13px; font-weight:bold; text-transform:uppercase;">Ihre professionelle Website</p>
                        <h3 style="margin:0; font-size:28px; line-height:1.15;">Klare Inhalte. Starker erster Eindruck.</h3>
                        <p style="max-width:540px; margin:14px 0 20px; line-height:1.5; opacity:.85;">Diese Vorlage wird mit Ihrem Angebot, Ihrer Marke und Ihren Kundendaten personalisiert.</p>
                        <span style="display:inline-block; background:{accent_color}; color:#07111f; padding:10px 14px; border-radius:{radius}; font-weight:bold;">Kontakt aufnehmen</span>
                    </div>
                    <div style="padding:18px 22px 24px;">
                        <p style="margin:0 0 12px; color:{accent_color}; font-size:13px; font-weight:bold; text-transform:uppercase;">Enthaltene Bereiche</p>
                        <p style="margin:0; line-height:1.65; opacity:.9;">{sections}</p>
                    </div>
                </section>
                """
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

    with design_column:
        background_color = st.color_picker(
            t("background_color"),
            "#111827",
            key="template_background_color",
        )
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

    render_template_preview(
        selected_template_name,
        current_template["sections"],
        background_color,
        accent_color,
        border_style,
    )

    custom_description = st.text_area(
        t("company_description"),
        placeholder=(
            "Zum Beispiel: Autohaus Mueller in Hannover, spezialisiert auf "
            "E-Mobilitaet und Gebrauchtwagen mit fuenf Jahren Garantie."
        ),
        key="template_custom_description",
        height=130,
    )

    radius_class = "rounded-none" if border_style == "sharp" else "rounded-2xl"
    description = str(custom_description or "").strip()
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
    project_name = create_deployment_project_name()
    st.session_state.project_name = project_name

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
            "Die Veröffentlichung im Internet ist ausschließlich für Premium-Konten verfügbar."
        )
        return

    st.caption(
        "Die Website wird auf Vercel veröffentlicht. Die finale Adresse wird nach "
        "der erfolgreichen Vercel-Antwort angezeigt."
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

new_tab, manage_tab = st.tabs(
    [t("new_website"), t("load_published")]
)



with new_tab:
    st.subheader("Website planen")
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
        st.info("Laden Sie einen Entwurf oder erstellen Sie zuerst eine Website. Die Anpassung erfolgt anschließend im Abschnittseditor unter der Vorschau.")

    section_prompt = ""
    if creation_mode != "Bestehenden Entwurf anpassen":
        section_prompt = render_section_configuration()

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
    if st.button(
        "Website erstellen",
        icon=":material/rocket_launch:",
        type="primary",
        key="create_website",
        width="stretch",
        disabled=creation_mode == "Bestehenden Entwurf anpassen",
    ):
        page_prompt = (
            "Erstelle eine mehrseitige Informationsarchitektur innerhalb einer einzelnen, deploybaren HTML-Datei. Das HTML muss genau vier eigenständige Ansichten besitzen: `data-page=\"start\"`, `data-page=\"leistungen\"`, `data-page=\"ueber-uns\"` und `data-page=\"kontakt\"`. Die Navigation muss Links auf `#start`, `#leistungen`, `#ueber-uns` und `#kontakt` besitzen. Füge JavaScript für `hashchange` und beim initialen Laden hinzu: Es blendet nur die gewählte Ansicht ein und ergänzt bei unbekanntem Hash `#start`. Beim Klick auf Kontakt muss ausschließlich die vollständige Kontaktansicht mit E-Mail-Adresse, Erreichbarkeit und Kontaktformular erscheinen. Die Browsernavigation Zurück/Vorwärts muss die Ansichten korrekt wechseln."
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
                status.update(label="Erstellung fehlgeschlagen", state="error")
                st.error(str(error))

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
        use_container_width=True,
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

if st.session_state.live_url:
    st.success("Eine veröffentlichte oder geladene Website ist verfügbar.")

    st.link_button(
        "🔗 Geänderte Website öffnen",
        st.session_state.live_url,
        use_container_width=True,
    )

    st.caption(f"Live-Link: {st.session_state.live_url}")

st.divider()
render_saas_preview_and_testing_window()

if st.session_state.generated_html:
    st.divider()
    st.header(t("edit_website"))

    live_editor_tab, content_tab, design_tab, image_tab, html_tab = st.tabs(
        ["Live-Design", "📝 Inhalte", "🎨 Design", "🖼️ Bilder", "💻 HTML-Code"]
    )

    with live_editor_tab:
        render_editor()

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
        )

        change_request = st.text_area(
            "Gewünschte Änderung",
            placeholder=(
                "Beispiel: Ersetze das Kontaktformular durch das konfigurierte "
                "Formspree-Formular und behalte das aktuelle Design."
            ),
            height=130,
        )

        if st.button("📝 Bereich aktualisieren", use_container_width=True):
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
        design_request = st.text_area(
            "Design-Änderung",
            placeholder=(
                "Beispiel: Dunkles Premium-Design mit goldenen Akzenten, "
                "runden Karten und größeren Buttons."
            ),
            height=130,
        )

        if st.button("🎨 Design aktualisieren", use_container_width=True):
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
            use_container_width=True,
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
            use_container_width=True,
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
            use_container_width=True,
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
                "Extern geladene Websites können über diese App nicht gelöscht werden."
            )

st.divider()
render_domain_and_deployment_ui()