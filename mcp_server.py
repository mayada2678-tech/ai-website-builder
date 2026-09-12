"""MCP tools for AI Website Builder integrations."""

from __future__ import annotations

from difflib import get_close_matches
import re
import time

import requests
from bs4 import BeautifulSoup, Tag
from fastmcp import FastMCP


mcp = FastMCP("AI-Webify-Server")
RDAP_URL = "https://rdap.org/domain/{domain_name}"
DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
DOMAIN_CACHE_TTL_SECONDS = 300
domain_cache: dict[str, tuple[float, dict[str, str | bool]]] = {}
DOMAIN_COST_GUIDANCE = (
    "Typische Registrierungsgebühr: .de etwa 5-20 EUR/Jahr, .com etwa "
    "10-25 EUR/Jahr. Aktions-, Verlängerungs- und Zusatzpreise unterscheiden sich je Anbieter."
)
CHATBOT_INDUSTRY_PROFILES = {
    "Kfz-Meisterwerkstatt": {
        "name": "Werkstatt-Assistent",
        "hours": "Mo-Fr: 08:00-18:00 Uhr",
        "contact": "Telefonisch oder per E-Mail während der Öffnungszeiten",
        "services": "Meisterhafte Kfz-Reparaturen, präziser Reifenwechsel und umfassender Autoservice",
        "emergency": "Für Pannen außerhalb der Öffnungszeiten wenden Sie sich bitte an einen Pannendienst.",
    },
    "Friseursalon": {
        "name": "Salon-Assistent",
        "hours": "Di-Fr: 09:00-18:00 Uhr, Sa: 09:00-14:00 Uhr",
        "contact": "Termine telefonisch oder per E-Mail vereinbaren",
        "services": "Moderne Haarschnitte, brillante Colorationen und individuelles Styling",
        "emergency": "Für kurzfristige Termine kontaktieren Sie den Salon direkt.",
    },
    "Dachdeckerfachbetrieb": {
        "name": "Dachservice-Assistent",
        "hours": "Mo-Fr: 07:00-17:00 Uhr",
        "contact": "Telefonisch oder per E-Mail",
        "services": "Dachsanierung, Neueindeckung, Abdichtung und Reparatur",
        "emergency": "Bei akuten Sturmschäden kontaktieren Sie uns telefonisch.",
    },
    "Physiotherapie-Praxis": {
        "name": "Praxis-Assistent",
        "hours": "Mo-Fr: 08:00-18:00 Uhr",
        "contact": "Termine telefonisch oder per E-Mail",
        "services": "Krankengymnastik, manuelle Therapie, Lymphdrainage und Trainingsberatung",
        "emergency": "Bei akuten Beschwerden wenden Sie sich bitte an den ärztlichen Notdienst.",
    },
    "Restaurant": {
        "name": "Genusszeit-Assistent",
        "hours": "Di-So: 12:00-22:00 Uhr",
        "contact": "Reservierungen telefonisch oder per E-Mail",
        "services": "Saisonale Küche, Tischreservierung, Gruppen und Feiern",
        "emergency": "Für kurzfristige Reservierungen rufen Sie uns bitte direkt an.",
    },
    "Café und Bäckerei": {
        "name": "Café-Assistent",
        "hours": "Mo-Sa: 07:00-18:00 Uhr, So: 08:00-16:00 Uhr",
        "contact": "Vorbestellungen telefonisch oder per E-Mail",
        "services": "Kaffeespezialitäten, Frühstück, frische Backwaren und hausgemachte Kuchen",
        "emergency": "Für tagesaktuelle Bestellungen kontaktieren Sie uns direkt.",
    },
    "Onlineshop": {
        "name": "Shop-Assistent",
        "hours": "Mo-Fr: 09:00-17:00 Uhr",
        "contact": "Kundenservice per E-Mail",
        "services": "Produktauswahl, sicherer Onlinekauf, Versand und Kundenservice",
        "emergency": "Bei dringenden Bestellfragen schreiben Sie uns bitte mit Bestellnummer.",
    },
}


def require_html_document(html: str) -> str:
    """Validates that a tool receives a complete editable HTML document."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("Es wird eine vollständige HTML-Datei benötigt.")
    soup = BeautifulSoup(html, "html.parser")
    if soup.html is None:
        raise ValueError("Es wird eine vollständige HTML-Datei benötigt.")
    return str(soup)


def get_or_create_head(soup: BeautifulSoup) -> Tag:
    """Returns the head element, creating it before body when necessary."""
    if soup.head is not None:
        return soup.head
    head = soup.new_tag("head")
    if soup.body is not None:
        soup.body.insert_before(head)
    else:
        soup.html.insert(0, head)
    return head


def normalize_section_type(section_type: str) -> str:
    """Maps similar section labels to supported MCP section types."""
    normalized = re.sub(r"[^a-zäöüß]", "", section_type.strip().lower())
    aliases = {
        "testimonials": "testimonials",
        "testimonial": "testimonials",
        "bewertungen": "testimonials",
        "bewertung": "testimonials",
        "kundenbewertungen": "testimonials",
        "kundenbewertung": "testimonials",
        "kundenstimmen": "testimonials",
        "rezensionen": "testimonials",
        "faq": "faq",
        "fragen": "faq",
        "haeufigefragen": "faq",
        "häufigefragen": "faq",
        "calltoaction": "call_to_action",
        "cta": "call_to_action",
        "kontaktaufruf": "call_to_action",
        "anfrage": "call_to_action",
    }
    if normalized in aliases:
        return aliases[normalized]
    close_match = get_close_matches(normalized, aliases, n=1, cutoff=0.72)
    if close_match:
        return aliases[close_match[0]]
    raise ValueError(
        "Der gewünschte Bereich wurde nicht erkannt. Verwenden Sie Kundenbewertungen, "
        "häufige Fragen oder einen Kontaktaufruf."
    )


@mcp.tool()
def get_industry_chatbot_profile(industry: str, language: str = "de") -> dict[str, str]:
    """Returns safe, editable default knowledge for a customer chatbot industry."""
    profile = CHATBOT_INDUSTRY_PROFILES.get(industry.strip())
    if profile is not None and language == "de":
        return dict(profile)
    localized_profiles = {
        "de": ("Kundenservice-Assistent", "Öffnungszeiten nach Vereinbarung", "Kontakt per E-Mail", "Individuelle Leistungen und persönliche Beratung", "Für dringende Anliegen kontaktieren Sie uns direkt."),
        "en": ("Customer service assistant", "Opening hours by appointment", "Contact by email", "Tailored services and personal advice", "For urgent enquiries, please contact us directly."),
        "ar": ("مساعد خدمة العملاء", "ساعات العمل حسب الموعد", "التواصل عبر البريد الإلكتروني", "خدمات مخصصة واستشارة شخصية", "للاستفسارات العاجلة، يرجى التواصل معنا مباشرة."),
        "ku": ("یاریدەدەری خزمەتگوزاری کڕیار", "کاتەکانی کار بە پێی ڕێککەوتن", "پەیوەندی بە ئیمەیڵ", "خزمەتگوزاری گونجاو و ڕاوێژکاری تایبەت", "بۆ داواکارییە پەلەکان ڕاستەوخۆ پەیوەندیمان پێوە بکە."),
        "es": ("Asistente de atención al cliente", "Horario con cita previa", "Contacto por correo electrónico", "Servicios personalizados y asesoramiento personal", "Para consultas urgentes, contáctenos directamente."),
        "it": ("Assistente del servizio clienti", "Orari su appuntamento", "Contatto via e-mail", "Servizi personalizzati e consulenza personale", "Per richieste urgenti, contattaci direttamente."),
        "hi": ("ग्राहक सेवा सहायक", "कार्य समय अपॉइंटमेंट के अनुसार", "ईमेल द्वारा संपर्क", "अनुकूलित सेवाएं और व्यक्तिगत सलाह", "तत्काल पूछताछ के लिए सीधे हमसे संपर्क करें।"),
    }
    values = localized_profiles.get(language, localized_profiles["en"])
    return dict(zip(("name", "hours", "contact", "services", "emergency"), values))


@mcp.tool()
def inject_section_into_html(
    html: str, section_type: str = "testimonials", language: str = "de"
) -> dict[str, str]:
    """Adds a selected professional content section to a customer page."""
    document = require_html_document(html)
    normalized_type = normalize_section_type(section_type)
    soup = BeautifulSoup(document, "html.parser")
    localized_text = {
        "de": {
            "testimonials": ("Kundenstimmen", "Was Kunden über uns sagen", "Persönliche Beratung, verlässliche Umsetzung und ein Ergebnis, das überzeugt.", "Stammkundin", "Freundlich, professionell und jederzeit gut erreichbar. Wir kommen gerne wieder.", "Stammkunde", "Von der ersten Anfrage bis zum Abschluss hat alles unkompliziert funktioniert.", "Kundin"),
            "faq": ("Gut informiert", "Häufige Fragen", "Wie kann ich Kontakt aufnehmen?", "Nutzen Sie die Kontaktmöglichkeiten auf dieser Website. Wir melden uns zeitnah bei Ihnen.", "Wie läuft eine Anfrage ab?", "Beschreiben Sie kurz Ihr Anliegen. Gemeinsam klären wir den passenden nächsten Schritt.", "Erhalte ich eine persönliche Beratung?", "Ja. Wir nehmen uns Zeit für Ihre Fragen und beraten Sie individuell."),
            "call_to_action": ("Persönlich für Sie da", "Lassen Sie uns über Ihr Anliegen sprechen.", "Kontaktieren Sie uns direkt. Wir klären Ihre Fragen und besprechen den passenden nächsten Schritt.", "Kontakt aufnehmen"),
        },
        "en": {
            "testimonials": ("Customer feedback", "What customers say about us", "Personal advice, reliable delivery, and a convincing result.", "Regular customer", "Friendly, professional, and always easy to reach.", "Regular customer", "Everything worked smoothly from the first enquiry to completion.", "Customer"),
            "faq": ("Well informed", "Frequently asked questions", "How can I get in touch?", "Use the contact details on this website. We will respond promptly.", "How does an enquiry work?", "Briefly describe your request and we will agree on the right next step.", "Will I receive personal advice?", "Yes. We take time for your questions and advise you individually."),
            "call_to_action": ("Here for you", "Let us talk about your request.", "Contact us directly. We will answer your questions and discuss the right next step.", "Get in touch"),
        },
        "ar": {
            "testimonials": ("آراء العملاء", "ماذا يقول عملاؤنا عنا", "استشارة شخصية وتنفيذ موثوق ونتيجة مقنعة.", "عميلة دائمة", "خدمة ودودة واحترافية وسهولة في التواصل.", "عميل دائم", "سارت جميع الخطوات بسلاسة من الاستفسار الأول حتى الإنجاز.", "عميلة"),
            "faq": ("معلومات واضحة", "الأسئلة الشائعة", "كيف يمكنني التواصل؟", "استخدم بيانات الاتصال في هذا الموقع وسنرد عليك قريباً.", "كيف تتم معالجة الطلب؟", "صف طلبك باختصار وسنحدد معاً الخطوة التالية المناسبة.", "هل أحصل على استشارة شخصية؟", "نعم، نخصص الوقت لأسئلتك ونقدم لك استشارة فردية."),
            "call_to_action": ("نحن هنا من أجلك", "دعنا نتحدث عن طلبك.", "تواصل معنا مباشرة لنجيب عن أسئلتك ونناقش الخطوة التالية المناسبة.", "تواصل معنا"),
        },
        "ku": {
            "testimonials": ("بۆچوونی کڕیاران", "کڕیاران دەربارەمان چی دەڵێن", "ڕاوێژکاری تایبەت و جێبەجێکردنی متمانەپێکراو و ئەنجامێکی سەرکەوتوو.", "کڕیاری بەردەوام", "دۆستانە و پیشەیی و هەمیشە ئاسان بۆ پەیوەندی.", "کڕیاری بەردەوام", "لە یەکەم داواکارییەوە تا تەواوبوون هەموو شتێک بە ئاسانی بەڕێوەچوو.", "کڕیار"),
            "faq": ("زانیاری ڕوون", "پرسیارە باوەکان", "چۆن پەیوەندی بکەم؟", "زانیاری پەیوەندیی ناو ئەم وێبگەیە بەکاربهێنە و بە زوویی وەڵامت دەدەینەوە.", "داواکارییەک چۆن بەڕێوەدەچێت؟", "داواکارییەکەت بە کورتی باس بکە تا هەنگاوی گونجاو دیاری بکەین.", "ڕاوێژکاری تایبەت وەردەگرم؟", "بەڵێ، کات بۆ پرسیارەکانت تەرخان دەکەین."),
            "call_to_action": ("لە خزمەتتداین", "با دەربارەی داواکارییەکەت قسە بکەین.", "ڕاستەوخۆ پەیوەندیمان پێوە بکە تا پرسیارەکانت و هەنگاوی داهاتوو باس بکەین.", "پەیوەندی بکە"),
        },
    }
    sections = {
        "testimonials": (
            "kundenbewertungen",
            "Kundenbewertungen",
            '''<section id="kundenbewertungen" class="customer-testimonials" aria-labelledby="kundenbewertungen-title">
  <div class="customer-testimonials__inner">
    <p class="customer-testimonials__eyebrow">Kundenstimmen</p>
    <h2 id="kundenbewertungen-title">Was Kunden über uns sagen</h2>
    <div class="customer-testimonials__grid">
      <blockquote><p>"Persönliche Beratung, verlässliche Umsetzung und ein Ergebnis, das überzeugt."</p><footer>Stammkundin</footer></blockquote>
      <blockquote><p>"Freundlich, professionell und jederzeit gut erreichbar. Wir kommen gerne wieder."</p><footer>Stammkunde</footer></blockquote>
      <blockquote><p>"Von der ersten Anfrage bis zum Abschluss hat alles unkompliziert funktioniert."</p><footer>Kundin</footer></blockquote>
    </div>
  </div>
</section>
<style>
.customer-testimonials { padding: 72px 24px; background: #f1f5f9; color: #172033; }
.customer-testimonials__inner { max-width: 1120px; margin: 0 auto; }
.customer-testimonials__eyebrow { margin: 0; color: #2563eb; font-weight: 700; text-transform: uppercase; }
.customer-testimonials h2 { margin: 8px 0 28px; font-size: clamp(1.8rem, 4vw, 2.7rem); }
.customer-testimonials__grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.customer-testimonials blockquote { margin: 0; padding: 22px; background: #fff; border-left: 3px solid #2563eb; box-shadow: 0 6px 16px rgba(15, 23, 42, .08); }
.customer-testimonials blockquote p { margin: 0; line-height: 1.6; }.customer-testimonials footer { margin-top: 16px; font-weight: 700; }
@media (max-width: 700px) { .customer-testimonials__grid { grid-template-columns: 1fr; } }
</style>'''
    ),
    "faq": (
        "haeufige-fragen",
        "Häufige Fragen",
        '''<section id="haeufige-fragen" class="customer-faq" aria-labelledby="haeufige-fragen-title">
    <div class="customer-faq__inner">
        <p>Gut informiert</p><h2 id="haeufige-fragen-title">Häufige Fragen</h2>
        <details><summary>Wie kann ich Kontakt aufnehmen?</summary><p>Nutzen Sie die Kontaktmöglichkeiten auf dieser Website. Wir melden uns zeitnah bei Ihnen.</p></details>
        <details><summary>Wie läuft eine Anfrage ab?</summary><p>Beschreiben Sie kurz Ihr Anliegen. Gemeinsam klären wir den passenden nächsten Schritt.</p></details>
        <details><summary>Erhalte ich eine persönliche Beratung?</summary><p>Ja. Wir nehmen uns Zeit für Ihre Fragen und beraten Sie individuell.</p></details>
    </div>
</section>
<style>.customer-faq{padding:72px 24px;background:#f8fafc;color:#172033}.customer-faq__inner{max-width:860px;margin:0 auto}.customer-faq__inner>p{margin:0;color:#2563eb;font-weight:700;text-transform:uppercase}.customer-faq h2{margin:8px 0 24px;font-size:clamp(1.8rem,4vw,2.7rem)}.customer-faq details{padding:18px 0;border-top:1px solid #cbd5e1}.customer-faq summary{cursor:pointer;font-weight:700}.customer-faq details p{margin:12px 0 0;line-height:1.6}</style>'''
    ),
    "call_to_action": (
        "kontaktaufruf",
        "Kontaktaufruf",
        '''<section id="kontaktaufruf" class="customer-cta" aria-labelledby="kontaktaufruf-title">
    <div><p>Persönlich für Sie da</p><h2 id="kontaktaufruf-title">Lassen Sie uns über Ihr Anliegen sprechen.</h2><p>Kontaktieren Sie uns direkt. Wir klären Ihre Fragen und besprechen den passenden nächsten Schritt.</p><a href="#kontakt">Kontakt aufnehmen</a></div>
</section>
<style>.customer-cta{padding:72px 24px;background:#172033;color:#fff;text-align:center}.customer-cta div{max-width:720px;margin:0 auto}.customer-cta p{line-height:1.6}.customer-cta div>p:first-child{color:#93c5fd;font-weight:700;text-transform:uppercase}.customer-cta h2{margin:10px 0;font-size:clamp(2rem,5vw,3.2rem)}.customer-cta a{display:inline-block;margin-top:12px;padding:12px 18px;background:#fff;color:#172033;text-decoration:none;font-weight:700;border-radius:6px}</style>'''
    ),
    }
    if language != "de":
        translated_values = localized_text.get(language, localized_text["en"])[normalized_type]
        section_id, _, section = sections[normalized_type]
        section_soup = BeautifulSoup(section, "html.parser")
        visible_nodes = [
            node for node in section_soup.find_all(string=True)
            if node.strip() and node.parent is not None and node.parent.name != "style"
        ]
        for node, translated_value in zip(visible_nodes, translated_values):
            node.replace_with(translated_value)
        sections[normalized_type] = (section_id, translated_values[1], str(section_soup))
    section_id, section_label, section = sections[normalized_type]
    if soup.find(id=section_id) is not None:
        return {"html": document, "message": f"Der Bereich {section_label} ist bereits vorhanden."}

    section_soup = BeautifulSoup(section, "html.parser")
    target = soup.main or soup.body
    if target is None:
        raise ValueError("Die HTML-Datei enthält keinen bearbeitbaren Body-Bereich.")
    for element in list(section_soup.contents):
        target.append(element)
    return {"html": str(soup), "message": f"{section_label} wurde in den Entwurf eingefügt."}


@mcp.tool()
def optimize_seo_and_content(
    html: str, industry: str, company_name: str, language: str = "de"
) -> dict[str, str]:
    """Improves the title, meta description, and first heading of a customer HTML page."""
    document = require_html_document(html)
    soup = BeautifulSoup(document, "html.parser")
    defaults = {
        "de": ("Dienstleistungen", "Unser Unternehmen", "professionelle Leistungen rund um", "Persönliche Beratung und direkte Kontaktaufnahme.", "bei"),
        "en": ("Services", "Our company", "professional services for", "Personal advice and direct contact.", "at"),
        "ar": ("الخدمات", "شركتنا", "خدمات احترافية في مجال", "استشارة شخصية وتواصل مباشر.", "لدى"),
        "ku": ("خزمەتگوزارییەکان", "کۆمپانیاکەمان", "خزمەتگوزاریی پیشەیی بۆ", "ڕاوێژکاری تایبەت و پەیوەندی ڕاستەوخۆ.", "لە"),
        "es": ("Servicios", "Nuestra empresa", "servicios profesionales de", "Asesoramiento personal y contacto directo.", "en"),
        "it": ("Servizi", "La nostra azienda", "servizi professionali per", "Consulenza personale e contatto diretto.", "presso"),
        "hi": ("सेवाएं", "हमारी कंपनी", "के लिए पेशेवर सेवाएं", "व्यक्तिगत सलाह और सीधा संपर्क।", "में"),
    }
    service_default, company_default, service_phrase, contact_phrase, at_phrase = defaults.get(language, defaults["en"])
    clean_industry = industry.strip() or service_default
    clean_company = company_name.strip() or company_default
    title = f"{clean_company} | {clean_industry}"
    description = f"{clean_company}: {service_phrase} {clean_industry}. {contact_phrase}"
    head = get_or_create_head(soup)
    title_tag = head.find("title")
    if title_tag is None:
        title_tag = soup.new_tag("title")
        head.append(title_tag)
    title_tag.string = title
    meta_tag = head.find("meta", attrs={"name": "description"})
    if meta_tag is None:
        meta_tag = soup.new_tag("meta")
        meta_tag["name"] = "description"
        head.append(meta_tag)
    meta_tag["content"] = description
    seo_heading = f"{clean_industry} {at_phrase} {clean_company}"
    heading = soup.find("h1")
    if heading is None:
        heading = soup.new_tag("h1")
        (soup.body or soup.html).insert(0, heading)
    heading.string = seo_heading
    return {"html": str(soup), "message": "SEO-Titel, Meta-Beschreibung und Hauptüberschrift wurden optimiert."}


@mcp.tool()
def check_domain_availability(domain_name: str) -> dict[str, str | bool]:
    """Checks whether a valid domain is currently registered via public RDAP data."""
    normalized_domain = domain_name.strip().lower().rstrip(".")
    if normalized_domain.startswith(("https://", "http://")):
        normalized_domain = normalized_domain.split("://", maxsplit=1)[1].split("/", maxsplit=1)[0]

    if not DOMAIN_PATTERN.fullmatch(normalized_domain):
        return {
            "domain": normalized_domain,
            "available": False,
            "status": "invalid",
            "message": "Bitte geben Sie eine gültige Domain wie beispiel.de ein.",
        }

    cached_result = domain_cache.get(normalized_domain)
    if cached_result and time.monotonic() - cached_result[0] < DOMAIN_CACHE_TTL_SECONDS:
        return cached_result[1]

    try:
        response = requests.get(RDAP_URL.format(domain_name=normalized_domain), timeout=10)
    except requests.RequestException:
        result = {
            "domain": normalized_domain,
            "available": False,
            "status": "unknown",
            "message": "Die Domain-Prüfung ist momentan nicht erreichbar.",
        }
        domain_cache[normalized_domain] = (time.monotonic(), result)
        return result

    if response.status_code == 404:
        result = {
            "domain": normalized_domain,
            "available": True,
            "status": "not_registered",
            "message": f"Für {normalized_domain} wurde kein RDAP-Eintrag gefunden.",
            "next_step": (
                "Registrieren Sie die Domain jetzt bei einem Registrar und verbinden Sie "
                "sie danach über die von Vercel angezeigten DNS-Einträge."
            ),
            "cost_guidance": DOMAIN_COST_GUIDANCE,
        }
    elif response.status_code == 200:
        result = {
            "domain": normalized_domain,
            "available": False,
            "status": "registered",
            "message": f"{normalized_domain} ist bereits registriert.",
            "next_step": (
                "Falls die Domain Ihnen gehört, öffnen Sie die DNS-Verwaltung bei Ihrem "
                "Anbieter. Andernfalls prüfen Sie einen anderen Namen."
            ),
            "cost_guidance": DOMAIN_COST_GUIDANCE,
        }
    else:
        result = {
            "domain": normalized_domain,
            "available": False,
            "status": "unknown",
            "message": "Der Registrierungsstatus konnte nicht zuverlässig ermittelt werden.",
            "next_step": "Prüfen Sie die Domain zusätzlich direkt bei einem Registrar.",
            "cost_guidance": DOMAIN_COST_GUIDANCE,
        }
    domain_cache[normalized_domain] = (time.monotonic(), result)
    return result


if __name__ == "__main__":
    mcp.run()