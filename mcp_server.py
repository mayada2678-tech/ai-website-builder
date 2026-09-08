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
    }
    if normalized in aliases:
        return aliases[normalized]
    close_match = get_close_matches(normalized, aliases, n=1, cutoff=0.72)
    if close_match:
        return aliases[close_match[0]]
    raise ValueError(
        "Der gewünschte Bereich wurde nicht erkannt. Verwenden Sie zum Beispiel "
        "Kundenbewertungen, Kundenstimmen oder Testimonials."
    )


@mcp.tool()
def inject_section_into_html(html: str, section_type: str = "testimonials") -> dict[str, str]:
    """Adds a customer-review section before the closing main area of a customer page."""
    document = require_html_document(html)
    normalize_section_type(section_type)
    soup = BeautifulSoup(document, "html.parser")
    if soup.find(id="kundenbewertungen") is not None:
        return {"html": document, "message": "Der Bereich Kundenbewertungen ist bereits vorhanden."}

    section = '''<section id="kundenbewertungen" class="customer-testimonials" aria-labelledby="kundenbewertungen-title">
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
    section_soup = BeautifulSoup(section, "html.parser")
    target = soup.main or soup.body
    if target is None:
        raise ValueError("Die HTML-Datei enthält keinen bearbeitbaren Body-Bereich.")
    for element in list(section_soup.contents):
        target.append(element)
    return {"html": str(soup), "message": "Kundenbewertungen wurden in den Entwurf eingefügt."}


@mcp.tool()
def optimize_seo_and_content(html: str, industry: str, company_name: str) -> dict[str, str]:
    """Improves the title, meta description, and first heading of a customer HTML page."""
    document = require_html_document(html)
    soup = BeautifulSoup(document, "html.parser")
    clean_industry = industry.strip() or "Dienstleistungen"
    clean_company = company_name.strip() or "Unser Unternehmen"
    title = f"{clean_company} | {clean_industry}"
    description = f"{clean_company}: professionelle Leistungen rund um {clean_industry}. Persönliche Beratung und direkte Kontaktaufnahme."
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
    seo_heading = f"{clean_industry} bei {clean_company}"
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
        }
    elif response.status_code == 200:
        result = {
            "domain": normalized_domain,
            "available": False,
            "status": "registered",
            "message": f"{normalized_domain} ist bereits registriert.",
        }
    else:
        result = {
            "domain": normalized_domain,
            "available": False,
            "status": "unknown",
            "message": "Der Registrierungsstatus konnte nicht zuverlässig ermittelt werden.",
        }
    domain_cache[normalized_domain] = (time.monotonic(), result)
    return result


if __name__ == "__main__":
    mcp.run()