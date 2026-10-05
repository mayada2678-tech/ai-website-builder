"""Chat-Funktionen: Hilfe-Chatbot der App sowie Design, Wissen, Widget und
API-Route des Kunden-Chatbots auf den erstellten Websites.
"""

import asyncio
import json
import re
from html import escape

import requests
import streamlit as st
from fastmcp import Client

from mcp_server import mcp as website_mcp_server

from logic import (
    build_analytics_api_route,
    build_testing_variant_api_route,
    contrast_text_color,
    HF_API_KEY,
    INDUSTRY_CONTENT_PRESETS,
    inject_site_analytics,
    OTHER_INDUSTRY_OPTION,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
    VERCEL_TOKEN,
)


CHATBOT_SHAPE_RADIUS = {
    "Rund (Kreis)": "50%",
    "Eckig mit Rundung": "14px",
    "Quadratisch": "0",
}


CHATBOT_FIGURE_ICONS = {
    "Freundlicher Roboter": "🤖",
    "Salon-Stylistin": "✂",
    "Werkstatt-Profi": "🔧",
    "Haus und Dach": "🏠",
    "Praxis-Begleitung": "✚",
    "Restaurant-Service": "🍽",
    "Gastronomie-Service": "☕",
    "Shop-Beratung": "🛍",
    "Kanzlei-Beratung": "⚖",
    "Kreativ-Studio": "📷",
    "Reinigungs-Service": "✨",
}


# Design des Kunden-Chatbots je Geschäftsart: Akzentfarbe, Button-Form, Figur,
# Schrift, Eckenradius des Fensters sowie Hintergrund- und Textfarben.
CHATBOT_DESIGN_THEMES = {
    "werkstatt": {"color": "#C2410C", "shape": "Eckig mit Rundung", "figure": "Werkstatt-Profi", "font": 'Arial,"Helvetica Neue",sans-serif', "radius": "6px", "panel": "#FFFFFF", "surface": "#F5F5F4", "text": "#1C1917", "border": "#D6D3D1"},
    "dach": {"color": "#991B1B", "shape": "Eckig mit Rundung", "figure": "Haus und Dach", "font": 'Arial,"Helvetica Neue",sans-serif', "radius": "4px", "panel": "#FFFFFF", "surface": "#F7F3F0", "text": "#292524", "border": "#E7DED8"},
    "salon": {"color": "#9D174D", "shape": "Rund (Kreis)", "figure": "Salon-Stylistin", "font": 'Georgia,"Times New Roman",serif', "radius": "18px", "panel": "#FFFBFD", "surface": "#FDF2F8", "text": "#3B0A24", "border": "#F5D0E3"},
    "praxis": {"color": "#0F766E", "shape": "Rund (Kreis)", "figure": "Praxis-Begleitung", "font": 'ui-sans-serif,-apple-system,"Segoe UI",sans-serif', "radius": "14px", "panel": "#FFFFFF", "surface": "#F0FDFA", "text": "#134E4A", "border": "#CCEDE8"},
    "restaurant": {"color": "#881337", "shape": "Eckig mit Rundung", "figure": "Restaurant-Service", "font": 'Georgia,"Times New Roman",serif', "radius": "10px", "panel": "#FFFDF8", "surface": "#FBF3EA", "text": "#3F1D0B", "border": "#EBDCCB"},
    "cafe": {"color": "#78350F", "shape": "Rund (Kreis)", "figure": "Gastronomie-Service", "font": 'Georgia,"Times New Roman",serif', "radius": "16px", "panel": "#FFFDF9", "surface": "#FBF5EC", "text": "#3B2412", "border": "#EADBC8"},
    "shop": {"color": "#4338CA", "shape": "Eckig mit Rundung", "figure": "Shop-Beratung", "font": 'ui-sans-serif,-apple-system,"Segoe UI",sans-serif', "radius": "12px", "panel": "#FFFFFF", "surface": "#F5F3FF", "text": "#1E1B4B", "border": "#DDD6FE"},
    "kanzlei": {"color": "#1E3A5F", "shape": "Quadratisch", "figure": "Kanzlei-Beratung", "font": 'Georgia,"Times New Roman",serif', "radius": "2px", "panel": "#FFFFFF", "surface": "#F1F5F9", "text": "#0F172A", "border": "#CBD5E1"},
    "kreativ": {"color": "#6D28D9", "shape": "Rund (Kreis)", "figure": "Kreativ-Studio", "font": 'ui-sans-serif,-apple-system,"Segoe UI",sans-serif', "radius": "20px", "panel": "#FFFFFF", "surface": "#FAF5FF", "text": "#2E1065", "border": "#E9D5FF"},
    "reinigung": {"color": "#0369A1", "shape": "Rund (Kreis)", "figure": "Reinigungs-Service", "font": 'ui-sans-serif,-apple-system,"Segoe UI",sans-serif', "radius": "14px", "panel": "#FFFFFF", "surface": "#F0F9FF", "text": "#0C4A6E", "border": "#CDE7F6"},
    "standard": {"color": "#2563EB", "shape": "Rund (Kreis)", "figure": "Freundlicher Roboter", "font": 'ui-sans-serif,-apple-system,"Segoe UI",sans-serif', "radius": "8px", "panel": "#FFFFFF", "surface": "#F8FAFC", "text": "#0F172A", "border": "#DBE3EC"},
}


INDUSTRY_CHATBOT_THEME_MAP = {
    "Kfz-Meisterwerkstatt": "werkstatt",
    "Friseursalon": "salon",
    "Dachdeckerfachbetrieb": "dach",
    "Physiotherapie-Praxis": "praxis",
    "Restaurant": "restaurant",
    "Café und Bäckerei": "cafe",
    "Onlineshop": "shop",
}


# Stichwörter für frei eingegebene Branchen; die Reihenfolge entscheidet bei
# mehreren Treffern (z. B. „Barbershop“ ist ein Salon, kein Shop).
CHATBOT_THEME_KEYWORDS = (
    ("salon", ("friseur", "frisör", "barber", "kosmetik", "beauty", "nagel", "nail", "wellness", "massage", "make-up", "makeup", "tattoo", "hair", "spa ")),
    ("praxis", ("arzt", "ärzt", "zahn", "praxis", "therap", "physio", "pflege", "klinik", "heilprakt", "apothe", "hebamme", "doctor", "dental", "clinic", "tierarzt")),
    ("reinigung", ("reinigung", "putz", "clean", "hausmeister", "gebäudeservice", "umzug", "wäsche")),
    ("kanzlei", ("anwalt", "kanzlei", "steuer", "notar", "versicherung", "finanz", "berater", "beratung", "immobil", "makler", "lawyer", "accountant")),
    ("kreativ", ("foto", "photo", "design", "agentur", "musik", "kunst", "atelier", "video", "event", "hochzeit", "studio")),
    ("werkstatt", ("kfz", "auto", "werkstatt", "reifen", "motorrad", "elektri", "sanitär", "heizung", "installat", "schlosser", "tischler", "schreiner", "mechani", "garage")),
    ("dach", ("dach", "bau", "maler", "fliesen", "garten", "landschaft", "zimmer", "maurer", "handwerk", "roof")),
    ("cafe", ("café", "cafe", "kaffee", "coffee", "bäcker", "baecker", "bakery", "konditor", "eiscafé", "eisdiele")),
    ("restaurant", ("restaurant", "imbiss", "pizz", "trattoria", "gastro", "bistro", "catering", "grill", "kneipe", "döner", "sushi", "food")),
    ("shop", ("shop", "laden", "boutique", "handel", "store", "mode", "kiosk", "verkauf")),
)


def get_customer_chatbot_copy() -> dict[str, str]:
    """Liefert konsistente Kundensupport-Texte in der gewählten Website-Sprache."""
    copy_by_language = {
        "de": {"service": "Kundenservice", "open": "Chatbot öffnen", "close": "Chat schließen", "status": "Schnelle und verlässliche Auskunft", "welcome": "Hallo! Wie können wir Ihnen helfen?", "question": "Frage eingeben...", "send": "Senden", "loading": "Antwort wird erstellt ...", "thanks": "Sehr gern. Haben Sie noch eine Frage?", "bye": "Auf Wiedersehen und einen schönen Tag!", "fallback": "Dazu liegen mir keine gesicherten Angaben vor. Bitte nutzen Sie die Kontaktmöglichkeiten auf dieser Website.", "contact": "Sie erreichen uns hier: {value}", "hours": "Unsere Öffnungs- oder Terminzeiten: {value}", "services": "Informationen zu unseren Leistungen: {value}", "booking": "Für Ihre Termin- oder Buchungsanfrage erreichen Sie uns hier: {value}"},
        "en": {"service": "Customer service", "open": "Open chatbot", "close": "Close chat", "status": "Fast and reliable information", "welcome": "Hello! How can we help you?", "question": "Enter your question...", "send": "Send", "loading": "Creating an answer ...", "thanks": "You are welcome. Can I help with anything else?", "bye": "Goodbye and have a wonderful day!", "fallback": "I do not have verified information about that. Please use the contact details on this website.", "contact": "You can reach us here: {value}", "hours": "Our opening or appointment hours are: {value}", "services": "Information about our services: {value}", "booking": "For an appointment or booking request, contact us here: {value}"},
        "ar": {"service": "خدمة العملاء", "open": "فتح المحادثة", "close": "إغلاق المحادثة", "status": "معلومات سريعة وموثوقة", "welcome": "مرحباً! كيف يمكننا مساعدتك؟", "question": "اكتب سؤالك...", "send": "إرسال", "loading": "جارٍ إعداد الإجابة...", "thanks": "على الرحب والسعة. هل لديك سؤال آخر؟", "bye": "إلى اللقاء، ونتمنى لك يوماً سعيداً!", "fallback": "لا تتوفر لدي معلومات موثقة حول ذلك. يرجى استخدام بيانات الاتصال الموجودة في هذا الموقع.", "contact": "يمكنك التواصل معنا هنا: {value}", "hours": "ساعات العمل أو المواعيد لدينا: {value}", "services": "معلومات عن خدماتنا: {value}", "booking": "لطلب موعد أو حجز، تواصل معنا هنا: {value}"},
        "ku": {"service": "خزمەتگوزاری کڕیار", "open": "کردنەوەی چات", "close": "داخستنی چات", "status": "زانیاریی خێرا و متمانەپێکراو", "welcome": "سڵاو! چۆن دەتوانین یارمەتیت بدەین؟", "question": "پرسیارەکەت بنووسە...", "send": "ناردن", "loading": "وەڵام ئامادە دەکرێت...", "thanks": "بەخێربێیت. پرسیارێکی ترت هەیە؟", "bye": "خواحافیز و ڕۆژێکی خۆشت هەبێت!", "fallback": "زانیاریی پشتڕاستکراوەم دەربارەی ئەوە نییە. تکایە ڕێگاکانی پەیوەندی لەم وێبگەیە بەکاربهێنە.", "contact": "لێرە دەتوانیت پەیوەندیمان پێوە بکەیت: {value}", "hours": "کاتەکانی کردنەوە یان وادەکانمان: {value}", "services": "زانیاری دەربارەی خزمەتگوزارییەکانمان: {value}", "booking": "بۆ داواکاری وادە یان حجز لێرە پەیوەندیمان پێوە بکە: {value}"},
        "es": {"service": "Atención al cliente", "open": "Abrir chat", "close": "Cerrar chat", "status": "Información rápida y fiable", "welcome": "¡Hola! ¿Cómo podemos ayudarte?", "question": "Escribe tu pregunta...", "send": "Enviar", "loading": "Preparando la respuesta...", "thanks": "De nada. ¿Puedo ayudarte con algo más?", "bye": "¡Hasta pronto y que tengas un buen día!", "fallback": "No dispongo de información verificada sobre eso. Utiliza los datos de contacto de este sitio web.", "contact": "Puedes contactarnos aquí: {value}", "hours": "Nuestro horario de apertura o citas es: {value}", "services": "Información sobre nuestros servicios: {value}", "booking": "Para solicitar una cita o reserva, contáctanos aquí: {value}"},
        "it": {"service": "Servizio clienti", "open": "Apri chat", "close": "Chiudi chat", "status": "Informazioni rapide e affidabili", "welcome": "Ciao! Come possiamo aiutarti?", "question": "Scrivi la tua domanda...", "send": "Invia", "loading": "Preparazione della risposta...", "thanks": "Prego. Posso aiutarti con qualcos'altro?", "bye": "Arrivederci e buona giornata!", "fallback": "Non dispongo di informazioni verificate al riguardo. Utilizza i recapiti presenti su questo sito.", "contact": "Puoi contattarci qui: {value}", "hours": "I nostri orari di apertura o appuntamento sono: {value}", "services": "Informazioni sui nostri servizi: {value}", "booking": "Per richiedere un appuntamento o una prenotazione, contattaci qui: {value}"},
        "hi": {"service": "ग्राहक सेवा", "open": "चैट खोलें", "close": "चैट बंद करें", "status": "तेज़ और विश्वसनीय जानकारी", "welcome": "नमस्ते! हम आपकी कैसे सहायता कर सकते हैं?", "question": "अपना प्रश्न लिखें...", "send": "भेजें", "loading": "उत्तर तैयार हो रहा है...", "thanks": "आपका स्वागत है। क्या मैं किसी और चीज में सहायता कर सकता हूं?", "bye": "फिर मिलेंगे, आपका दिन शुभ हो!", "fallback": "मेरे पास इसकी सत्यापित जानकारी नहीं है। कृपया इस वेबसाइट पर दिए गए संपर्क विवरण का उपयोग करें।", "contact": "आप हमसे यहां संपर्क कर सकते हैं: {value}", "hours": "हमारे खुलने या अपॉइंटमेंट का समय: {value}", "services": "हमारी सेवाओं की जानकारी: {value}", "booking": "अपॉइंटमेंट या बुकिंग के लिए यहां संपर्क करें: {value}"},
    }
    return copy_by_language.get(
        str(st.session_state.get("app_language", "en")), copy_by_language["en"]
    )


def build_customer_chatbot_resilience_script(chatbot_knowledge: str) -> str:
    """Haelt den Kundenchat auch bei einer nicht erreichbaren API bedienbar."""
    knowledge_json = json.dumps(chatbot_knowledge.strip(), ensure_ascii=False).replace(
        "</", "<\\/"
    )
    copy_json = json.dumps(get_customer_chatbot_copy(), ensure_ascii=False).replace(
        "</", "<\\/"
    )
    return rf'''<style data-customer-chatbot-resilience-style>
#customer-chatbot{{font-family:var(--cb-font,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif)!important}}
#customer-chat-panel{{display:flex;flex-direction:column;width:min(390px,calc(100vw - 32px))!important;max-height:min(620px,calc(100vh - 110px));padding:0!important;overflow:hidden;background:var(--cb-panel,#fff)!important;border:1px solid var(--cb-border,#dbe3ec)!important;border-radius:var(--cb-radius,8px)!important;box-shadow:0 24px 64px rgba(15,23,42,.24)!important}}
#customer-chat-panel[hidden]{{display:none!important}}
.customer-chat-topbar{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 18px;border-bottom:0;background:var(--cb-accent,#2563eb);color:var(--cb-on-accent,#fff)}}
.customer-chat-identity{{display:flex;align-items:center;gap:10px;min-width:0}}.customer-chat-avatar{{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:var(--cb-panel,#fff);color:var(--cb-accent,#1d4ed8);font-size:20px;font-weight:800}}.customer-chat-identity strong{{font-size:15px;color:inherit}}.customer-chat-status{{display:block;margin-top:2px;color:inherit;opacity:.85;font-size:12px}}
.customer-chat-close{{display:grid;place-items:center;width:34px;height:34px;border:0;border-radius:50%;background:rgba(255,255,255,.18);color:inherit;font-size:22px;line-height:1;cursor:pointer}}.customer-chat-close:hover{{background:rgba(255,255,255,.3)}}
#customer-chat-answer{{display:flex;flex:1;flex-direction:column;gap:10px;min-height:180px;max-height:390px;margin:0!important;padding:18px!important;overflow-y:auto;background:var(--cb-surface,#f8fafc)!important;color:var(--cb-text,#172033)!important}}
.customer-chat-message{{max-width:86%;padding:10px 12px;border-radius:var(--cb-radius,8px);font-size:14px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}}.customer-chat-message--assistant{{align-self:flex-start;background:var(--cb-panel,#fff);border:1px solid var(--cb-border,#e2e8f0);color:var(--cb-text,#334155)}}.customer-chat-message--user{{align-self:flex-end;background:var(--cb-accent,#2563eb);color:var(--cb-on-accent,#fff)}}.customer-chat-message--pending{{opacity:.7}}
#customer-chat-form{{display:grid!important;grid-template-columns:minmax(0,1fr) auto;gap:8px!important;padding:14px!important;border-top:1px solid var(--cb-border,#e2e8f0);background:var(--cb-panel,#fff)}}#customer-chat-input{{border:1px solid var(--cb-border,#cbd5e1);border-radius:6px;background:#fff;color:#111827;padding:11px 12px!important;font:inherit}}#customer-chat-send{{min-width:84px;border-radius:6px!important;font-weight:700}}#customer-chat-input:focus-visible,#customer-chat-send:focus-visible,.customer-chat-close:focus-visible{{outline:3px solid var(--cb-accent,#93c5fd);outline-offset:2px}}.customer-chat-close:focus-visible{{outline-color:currentColor}}
@media(max-width:480px){{#customer-chat-panel{{position:fixed!important;left:12px!important;right:12px!important;bottom:88px!important;width:auto!important;max-height:calc(100vh - 112px)}}#customer-chat-form{{grid-template-columns:1fr}}#customer-chat-send{{width:100%;min-height:42px}}}}
</style><script data-customer-chatbot-resilience>(()=>{{
const root=document.getElementById("customer-chatbot");
if(!root)return;
const copy={copy_json};
const toggle=root.querySelector("#customer-chat-toggle"),panel=root.querySelector("#customer-chat-panel"),form=root.querySelector("#customer-chat-form"),input=root.querySelector("#customer-chat-input"),answer=root.querySelector("#customer-chat-answer"),send=root.querySelector("#customer-chat-send");
if(!toggle||!panel||!form||!input||!answer||!send)return;
const originalHeading=panel.querySelector("strong");
const topbar=document.createElement("div");topbar.className="customer-chat-topbar";
const identity=document.createElement("div");identity.className="customer-chat-identity";
const avatar=document.createElement("span");avatar.className="customer-chat-avatar";avatar.setAttribute("aria-hidden","true");avatar.textContent=root.dataset.figure||"AI";
const identityText=document.createElement("div");const heading=document.createElement("strong");heading.textContent=originalHeading?.textContent||copy.service;const status=document.createElement("span");status.className="customer-chat-status";status.textContent=copy.status;identityText.append(heading,status);identity.append(avatar,identityText);
const close=document.createElement("button");close.type="button";close.className="customer-chat-close";close.setAttribute("aria-label",copy.close);close.textContent="×";topbar.append(identity,close);if(originalHeading)originalHeading.remove();panel.prepend(topbar);
const welcome=answer.textContent.trim();answer.textContent="";answer.setAttribute("role","log");answer.setAttribute("aria-live","polite");answer.setAttribute("aria-relevant","additions text");
const addMessage=(role,text,pending=false)=>{{const message=document.createElement("div");message.className=`customer-chat-message customer-chat-message--${{role}}${{pending?" customer-chat-message--pending":""}}`;message.textContent=text;answer.append(message);answer.scrollTop=answer.scrollHeight;return message;}};addMessage("assistant",welcome);
const setOpen=open=>{{panel.hidden=!open;toggle.setAttribute("aria-expanded",String(open));if(open)input.focus();}};
toggle.onclick=()=>setOpen(panel.hidden);
close.onclick=()=>{{setOpen(false);toggle.focus();}};
root.onkeydown=event=>{{if(event.key==="Escape"&&!panel.hidden){{setOpen(false);toggle.focus();}}}};
const knowledge={knowledge_json};
const history=[];
const detail=(...labels)=>{{for(const label of labels){{const escaped=label.replace(/[.*+?^${{}}()|[\]\\]/g,"\\$&");const match=knowledge.match(new RegExp(escaped+":\\s*([^\\n]+)","i"));if(match)return match[1].trim();}}return "";}};
const localAnswer=question=>{{const normalized=question.toLocaleLowerCase();const contact=detail("Kontaktwege","Contact methods","وسائل الاتصال","ڕێگاکانی پەیوەندی","Métodos de contacto","Metodi di contatto","संपर्क के तरीके");const hours=detail("Öffnungszeiten","Opening hours","ساعات العمل","کاتەکانی کردنەوە","Horario","Orari di apertura","कार्य समय");const services=detail("Preise und Leistungen","Typische Leistungen dieser Branche","Prices and services","Typical services in this industry","الأسعار والخدمات","الخدمات المعتادة في هذا المجال","نرخ و خزمەتگوزارییەکان","خزمەتگوزارییە باوەکانی ئەم بوارە","Precios y servicios","Servicios habituales del sector","Prezzi e servizi","Servizi tipici del settore","मूल्य और सेवाएं","इस उद्योग की सामान्य सेवाएं");const emergency=detail("Notfall und Bereitschaft","Emergency and on-call service","الطوارئ وخدمة الاستعداد","فریاکەوتن و ئامادەباشی","Emergencias y guardias","Emergenze e reperibilità","आपातकालीन और ऑन-कॉल सेवा");const fill=(template,value)=>template.replace("{{value}}",value);if(/(termin|reserv|book|appointment|cita|prenot|موعد|حجز|وادە|बुक)/u.test(normalized)&&contact)return fill(copy.booking,contact);if(/(kontakt|contact|telefon|phone|e-mail|mail|اتصال|هاتف|پەیوەندی|تەلەفۆن|contacto|contatto|संपर्क|फ़ोन)/u.test(normalized)&&contact)return fill(copy.contact,contact);if(/(öffnungs|uhrzeit|open|hours|horario|orari|ساعات|کاتەکان|समय)/u.test(normalized)&&hours)return fill(copy.hours,hours);if(/(preis|kost|service|leistung|angebot|price|cost|services|precio|servicio|prezzo|servizi|الأسعار|الخدمات|نرخ|خزمەتگوزاری|मूल्य|सेवा)/u.test(normalized)&&services)return fill(copy.services,services);if(/(notfall|dringend|emergency|urgent|emergencia|emergenza|طوارئ|فریاکەوتن|आपात)/u.test(normalized)&&emergency)return emergency;if(/(^|\\s)(hallo|hi|hey|hello|hola|ciao|مرحبا|أهلا|سڵاو|नमस्ते)(\\s|$|!)/u.test(normalized))return copy.welcome;if(/(danke|thank|gracias|grazie|شكرا|سوپاس|धन्यवाद)/u.test(normalized))return copy.thanks;if(/(tschüss|goodbye|bye|adiós|arrivederci|مع السلامة|خواحافیز|अलविदा)/u.test(normalized))return copy.bye;return contact?`${{copy.fallback}} ${{fill(copy.contact,contact)}}`:copy.fallback;}};
form.onsubmit=async event=>{{event.preventDefault();const question=input.value.trim();if(!question||send.disabled)return;addMessage("user",question);input.value="";send.disabled=true;input.disabled=true;form.setAttribute("aria-busy","true");const pending=addMessage("assistant",copy.loading,true);const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),8000);let reply="";try{{const result=await fetch("/api/chat",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{question,history:history.slice(-6)}}),signal:controller.signal}});const data=await result.json().catch(()=>({{}}));reply=result.ok&&typeof data.answer==="string"&&data.answer.trim()?data.answer:localAnswer(question);}}catch(error){{reply=localAnswer(question);}}finally{{clearTimeout(timeout);send.disabled=false;input.disabled=false;form.removeAttribute("aria-busy");}}pending.classList.remove("customer-chat-message--pending");pending.textContent=reply;answer.scrollTop=answer.scrollHeight;history.push({{role:"user",content:question}},{{role:"assistant",content:reply}});if(history.length>6)history.splice(0,history.length-6);input.focus();}};
}})();</script>'''


def remove_customer_chatbot(html: str) -> str:
    """Entfernt alle zuvor erzeugten Kundenchatbot-Artefakte aus einem HTML-Dokument."""
    patterns = (
        r'(?is)<style\b[^>]*\bdata-customer-chatbot-resilience-style\b[^>]*>.*?</style>',
        r'(?is)<script\b[^>]*\bdata-customer-chatbot-resilience\b[^>]*>.*?</script>',
        (
            r'(?is)<aside\b(?=[^>]*(?:\bid=["\']customer-chatbot["\']|'
            r'\bclass=["\'][^"\']*\bcustomer-chatbot\b[^"\']*["\']))[^>]*>'
            r'.*?</aside>\s*<script(?:\s[^>]*)?>.*?</script>'
        ),
    )
    for pattern in patterns:
        html = re.sub(pattern, "", html)
    return html


def inject_configured_customer_chatbot(html: str) -> str:
    """Setzt genau einen zentral konfigurierten Chatbot in den Kundenentwurf ein."""
    html_without_existing_widget = remove_customer_chatbot(html)
    knowledge = get_configured_chatbot_knowledge()
    widget = build_customer_chatbot_widget(
        str(st.session_state.get("customer_chatbot_name", "")),
        str(st.session_state.get("customer_chatbot_color", "#2563EB")),
        knowledge,
    ) + build_customer_chatbot_resilience_script(knowledge)
    return re.sub(
        r"(?i)</body\s*>",
        lambda _match: f"{widget}</body>",
        html_without_existing_widget,
        count=1,
    )


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
    }
    api_copy = api_copy.get(language, api_copy["en"])
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
    if (/(termin|reservier|buch|tisch|anfrag)/.test(normalized) && contact) return `Gerne. Für eine Termin- oder Buchungsanfrage erreichen Sie uns hier: ${{contact}}`;
    if (/(kontakt|telefon|e-mail|mail|erreich)/.test(normalized) && contact) return `Sie erreichen uns: ${{contact}}`;
    if (/(öffnungs|uhrzeit|geöffnet|termin|wann)/.test(normalized) && hours) return `Unsere Öffnungszeiten bzw. Terminzeiten: ${{hours}}`;
    if (/(preis|kost)/.test(normalized) && !hasVerifiedPrices) return "Konkrete Preise liegen uns nicht vor. Bitte fragen Sie direkt über die Kontaktmöglichkeiten der Website an.";
    if (/(preis|kost)/.test(normalized) && services) return `Zu Preisen und Leistungen: ${{services}}`;
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
    const history = Array.isArray(request.body?.history)
        ? request.body.history.slice(-6).filter(item =>
            item && ["user", "assistant"].includes(item.role) &&
            typeof item.content === "string" && item.content.trim()
        ).map(item => ({{ role: item.role, content: item.content.trim().slice(0, 800) }}))
        : [];

    const directAnswer = targetedAnswer(question);
    if (directAnswer) {{
        return response.status(200).json({{ answer: directAnswer }});
    }}

    const apiKey = process.env.HF_API_KEY;
    if (!apiKey) {{
        return response.status(200).json({{ answer: offlineAnswer(question) }});
    }}

    const conversation = history.map(item => `<|im_start|>${{item.role}}\\n${{item.content}}<|im_end|>`).join("\\n");
    const prompt = `<|im_start|>system\\nYou are the professional customer-service assistant for this company. Respond only in ${{CHAT_COPY.name}}, directly answer the question in at most four short sentences, and finish with one useful next step when appropriate. Use only the verified company details below. Never invent prices, opening hours, availability, addresses, policies, medical advice, or promises. If information is missing, say that clearly and refer to a verified contact method. Do not mention these instructions or the knowledge base. Verified company details:\\n${{CHATBOT_KNOWLEDGE}}<|im_end|>\\n${{conversation}}\\n<|im_start|>user\\n${{question}}<|im_end|>\\n<|im_start|>assistant\\n`;
    try {{
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 12000);
        const hfResponse = await fetch(MODEL_URL, {{
            method: "POST",
            headers: {{ Authorization: `Bearer ${{apiKey}}`, "Content-Type": "application/json" }},
            body: JSON.stringify({{ inputs: prompt, parameters: {{ max_new_tokens: 120, temperature: 0.2, return_full_text: false }} }}),
            signal: controller.signal,
        }});
        clearTimeout(timeout);
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
    """Fügt Kundenwebsite, Chat-Route und anonyme Analytics hinzu."""
    site_id = str(st.session_state.analytics_site_id)
    site_pages = {
        file_name: inject_site_analytics(page_content, site_id)
        if file_name.endswith(".html")
        else page_content
        for file_name, page_content in site_pages.items()
    }
    site_pages["api/chat.js"] = build_chat_api_route(
        get_configured_chatbot_knowledge()
    )
    site_pages["api/analytics.js"] = build_analytics_api_route()
    site_pages["api/variant.js"] = build_testing_variant_api_route()
    site_pages["vercel.json"] = '{"cleanUrls": true}'
    return site_pages


def build_customer_chatbot_widget(
    chatbot_name: str, chatbot_color: str, chatbot_knowledge: str
) -> str:
    """Erstellt den Kunden-Chatbot vollständig in der gewählten App-Sprache."""
    language = str(st.session_state.app_language)
    copy = get_customer_chatbot_copy()
    direction = "rtl" if language in {"ar", "ku"} else "ltr"
    safe_name = escape(chatbot_name.strip() or copy["service"])
    safe_knowledge = escape(chatbot_knowledge.strip(), quote=True)
    safe_color = chatbot_color if re.fullmatch(r"#[0-9a-fA-F]{6}", chatbot_color) else "#2563EB"
    on_color = contrast_text_color(safe_color)
    theme = get_chatbot_design_theme()
    figure = CHATBOT_FIGURE_ICONS.get(
        str(st.session_state.get("customer_chatbot_figure", "")),
        CHATBOT_FIGURE_ICONS[theme["figure"]],
    )
    toggle_radius = get_chatbot_toggle_radius(theme["shape"])
    theme_vars = (
        f"--cb-accent:{safe_color};--cb-on-accent:{on_color};--cb-font:{theme['font']};"
        f"--cb-radius:{theme['radius']};--cb-panel:{theme['panel']};--cb-surface:{theme['surface']};"
        f"--cb-text:{theme['text']};--cb-border:{theme['border']};"
    )
    is_left = st.session_state.get("customer_chatbot_position") == "Unten links"
    side = "left:20px;right:auto;" if is_left else "right:20px;left:auto;"
    panel_side = "left:0;right:auto;" if is_left else "right:0;left:auto;"
    position = "fixed" if st.session_state.get("customer_chatbot_fixed", True) else "relative"
    copy_json = json.dumps(copy, ensure_ascii=False).replace("</", "<\\/")
    return f'''<aside id="customer-chatbot" class="customer-chatbot" lang="{language}" dir="{direction}" data-knowledge="{safe_knowledge}" data-figure="{escape(figure)}" style="{escape(theme_vars)}position:{position};{side}bottom:20px;z-index:10000;font-family:var(--cb-font)">
<button id="customer-chat-toggle" type="button" aria-expanded="false" aria-label="{escape(copy['open'])}" title="{escape(copy['open'])}" style="display:grid;place-items:center;width:60px;height:60px;border:0;border-radius:{toggle_radius};background:var(--cb-accent);color:var(--cb-on-accent);cursor:pointer;font-size:28px;line-height:1;box-shadow:0 6px 18px rgba(0,0,0,.24)"><span aria-hidden="true">{escape(figure)}</span></button>
<section id="customer-chat-panel" hidden style="position:absolute;{panel_side}bottom:72px;width:min(340px,calc(100vw - 40px));padding:18px;background:var(--cb-panel);color:var(--cb-text);border:1px solid var(--cb-border);border-radius:var(--cb-radius);box-shadow:0 10px 28px rgba(0,0,0,.22);text-align:{'right' if direction == 'rtl' else 'left'}">
<strong>{safe_name}</strong><p id="customer-chat-answer" aria-live="polite" style="margin:10px 0;color:var(--cb-text)">{escape(copy['welcome'])}</p>
<form id="customer-chat-form" style="display:flex;gap:6px"><input id="customer-chat-input" aria-label="{escape(copy['question'])}" placeholder="{escape(copy['question'])}" required style="min-width:0;flex:1;padding:8px;text-align:inherit"><button id="customer-chat-send" type="submit" style="border:0;background:var(--cb-accent);color:var(--cb-on-accent);padding:8px 12px;cursor:pointer">{escape(copy['send'])}</button></form></section></aside>
<script>(()=>{{const copy={copy_json};const root=document.getElementById('customer-chatbot');const toggle=document.getElementById('customer-chat-toggle');const panel=document.getElementById('customer-chat-panel');const form=document.getElementById('customer-chat-form');const input=document.getElementById('customer-chat-input');const answer=document.getElementById('customer-chat-answer');const send=document.getElementById('customer-chat-send');const offlineAnswer=question=>{{const normalized=question.toLocaleLowerCase();if(/(^|\\s)(hallo|hi|hey|hello|hola|ciao|مرحبا|أهلا|سڵاو|नमस्ते)(\\s|$|!)/u.test(normalized))return copy.welcome;if(/(danke|thank|gracias|grazie|شكرا|سوپاس|धन्यवाद)/u.test(normalized))return copy.thanks;if(/(tschüss|auf wiedersehen|goodbye|bye|adiós|arrivederci|مع السلامة|خواحافیز|अलविदा)/u.test(normalized))return copy.bye;return copy.fallback;}};toggle.onclick=()=>{{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();}};form.onsubmit=async event=>{{event.preventDefault();const question=input.value.trim();if(!question)return;answer.textContent=copy.loading;input.value='';send.disabled=true;try{{const result=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question,language:'{language}'}})}});const data=await result.json().catch(()=>({{}}));answer.textContent=result.ok&&data.answer?data.answer:offlineAnswer(question);}}catch(error){{answer.textContent=offlineAnswer(question);}}finally{{send.disabled=false;}}}};}})();</script>'''


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


def configure_vercel_chatbot_environment(project_id: str) -> str:
    """Hinterlegt Chat- und Analytics-Secrets im Kundenprojekt."""
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }
    warnings = []
    environment_values = {
        "HF_API_KEY": HF_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
    }
    if not HF_API_KEY:
        warnings.append(
            "HF_API_KEY fehlt. Der Kundenchatbot verwendet lokale Rückfallantworten."
        )
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        warnings.append(
            "Supabase ist noch nicht vollständig konfiguriert; anonyme Analytics bleiben deaktiviert."
        )
    try:
        environment_variables = requests.get(
            f"https://api.vercel.com/v9/projects/{project_id}/env",
            headers=headers,
            timeout=30,
        )
        environment_variables.raise_for_status()
        existing_variables = environment_variables.json().get("envs", [])
    except requests.RequestException as error:
        return f"Die Server-Konfiguration ist nicht erreichbar: {error}"

    existing_by_name = {
        str(item.get("key", "")): str(item.get("id", ""))
        for item in existing_variables
    }
    for variable_name, variable_value in environment_values.items():
        if not variable_value:
            continue
        payload = {
            "key": variable_name,
            "value": variable_value,
            "type": "encrypted",
            "target": ["production", "preview", "development"],
        }
        existing_key = existing_by_name.get(variable_name, "")
        try:
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
            warnings.append(f"{variable_name} konnte nicht übertragen werden: {error}")
            continue
        if response.status_code not in (200, 201):
            try:
                details = response.json().get("error", {}).get("message", "")
            except ValueError:
                details = ""
            warnings.append(
                f"Der Hosting-Dienst konnte {variable_name} nicht speichern (HTTP {response.status_code})"
                + (f": {details}" if details else ".")
            )
    return "\n\n".join(warnings)


def get_chatbot_toggle_radius(default_shape: str = "Rund (Kreis)") -> str:
    """Liefert den Eckenradius des Chat-Buttons für die gewählte Form."""
    shape = str(st.session_state.get("customer_chatbot_shape", default_shape))
    return CHATBOT_SHAPE_RADIUS.get(shape, "50%")


def get_chatbot_design_theme(industry: str | None = None) -> dict[str, str]:
    """Ermittelt das passende Chatbot-Design für die Branche des Kunden."""
    if industry is None:
        industry = str(st.session_state.get("industry_content_preset", ""))
        if industry == OTHER_INDUSTRY_OPTION:
            industry = str(st.session_state.get("custom_industry_name", ""))
    theme_key = INDUSTRY_CHATBOT_THEME_MAP.get(industry)
    if not theme_key:
        normalized = f" {industry.strip().casefold()} "
        theme_key = next(
            (
                key
                for key, keywords in CHATBOT_THEME_KEYWORDS
                if any(keyword in normalized for keyword in keywords)
            ),
            "standard",
        )
    return CHATBOT_DESIGN_THEMES[theme_key]


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
