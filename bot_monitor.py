import json
import os
import re
import html
import feedparser
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
STATE_FILE = "last_seen_posts.json"

# ================= LISTA COMPLETA DE CUENTAS =================
SOURCES = [
    # --- Truth Social directo ---
    {"category": "TRUTH SOCIAL", "author": "Donald Trump", "url": "https://trumpstruth.org/feed"},

    # --- Liderazgo Casa Blanca y círculo cercano ---
    {"category": "VICEPRESIDENCIA", "author": "JD Vance (@JDVance)", "url": "https://nitter.privacydev.net/JDVance/rss"},
    {"category": "TRUMP OFICIAL", "author": "@realDonaldTrump", "url": "https://nitter.privacydev.net/realDonaldTrump/rss"},
    {"category": "TRUMP FEED", "author": "@TrumpDailyPosts", "url": "https://nitter.privacydev.net/TrumpDailyPosts/rss"},
    {"category": "TRUMP FEED", "author": "@TruthTrumpPosts", "url": "https://nitter.privacydev.net/TruthTrumpPosts/rss"},
    {"category": "EQUIPO TRUMP", "author": "@RapidResponse47", "url": "https://nitter.privacydev.net/RapidResponse47/rss"},
    {"category": "EQUIPO TRUMP", "author": "@TeamTrump", "url": "https://nitter.privacydev.net/TeamTrump/rss"},
    {"category": "REDES TRUMP", "author": "@DanScavino", "url": "https://nitter.privacydev.net/DanScavino/rss"},
    {"category": "CASA BLANCA", "author": "Stephen Miller (@StephenM)", "url": "https://nitter.privacydev.net/StephenM/rss"},
    {"category": "SENADO / GOBIERNO", "author": "Marco Rubio (@marcorubio)", "url": "https://nitter.privacydev.net/marcorubio/rss"},

    # --- Diplomacia y Relaciones Exteriores ---
    {"category": "DIPLOMACIA EE.UU.", "author": "State Dept (@StateDept)", "url": "https://nitter.privacydev.net/StateDept/rss"},

    # --- Operativos, Frontera, Seguridad y Justicia ---
    {"category": "ZAR DE LA FRONTERA", "author": "Tom Homan (@RealTomHoman)", "url": "https://nitter.privacydev.net/RealTomHoman/rss"},
    {"category": "AGENCIA SEGURIDAD", "author": "DEA HQ (@DEAHQ)", "url": "https://nitter.privacydev.net/DEAHQ/rss"},
    {"category": "JUSTICIA EE.UU.", "author": "DOJ (@TheJusticeDept)", "url": "https://nitter.privacydev.net/TheJusticeDept/rss"},
    {"category": "SEGURIDAD NACIONAL", "author": "DHS (@DHSgov)", "url": "https://nitter.privacydev.net/DHSgov/rss"},
    {"category": "SEGURIDAD NACIONAL", "author": "CBP (@CBP)", "url": "https://nitter.privacydev.net/CBP/rss"},
    {"category": "GOBIERNO TEXAS", "author": "Gov. Greg Abbott (@GregAbbott_TX)", "url": "https://nitter.privacydev.net/GregAbbott_TX/rss"},
    {"category": "FRONTERA REPORTEROS", "author": "Ali Bradley (@AliBradleyTV)", "url": "https://nitter.privacydev.net/AliBradleyTV/rss"},
    {"category": "FRONTERA REPORTEROS", "author": "Bill Melugin (@BillMelugin_)", "url": "https://nitter.privacydev.net/BillMelugin_/rss"},
    {"category": "FRONTERA REPORTEROS", "author": "Griff Jenkins (@GriffJenkins)", "url": "https://nitter.privacydev.net/GriffJenkins/rss"},

    # --- Comercio, Aranceles y T-MEC ---
    {"category": "COMERCIO EE.UU.", "author": "USTR (@USTradeRep)", "url": "https://nitter.privacydev.net/USTradeRep/rss"},
    {"category": "COMERCIO EE.UU.", "author": "Dept of Commerce (@CommerceGov)", "url": "https://nitter.privacydev.net/CommerceGov/rss"},
    {"category": "PRENSA COMERCIAL", "author": "Doug Palmer (@DougPalmer)", "url": "https://nitter.privacydev.net/DougPalmer/rss"},
    {"category": "PRENSA COMERCIAL", "author": "Gavin Bade (@GavinBade)", "url": "https://nitter.privacydev.net/GavinBade/rss"},

    # --- Ruptura política, clips y filtraciones ---
    {"category": "CLIPS TRUMP", "author": "Acyn (@Acyn)", "url": "https://nitter.privacydev.net/Acyn/rss"},
    {"category": "FILTRACIONES NYT", "author": "Maggie Haberman (@maggieNYT)", "url": "https://nitter.privacydev.net/maggieNYT/rss"},
    {"category": "CONGRESO EE.UU.", "author": "Punchbowl News (@PunchbowlNews)", "url": "https://nitter.privacydev.net/PunchbowlNews/rss"},
    {"category": "CONGRESO EE.UU.", "author": "Jake Sherman (@JakeSherman)", "url": "https://nitter.privacydev.net/JakeSherman/rss"}
]

# ================= FILTROS TEMÁTICOS =================
KEYWORDS_REGEX = re.compile(
    r"\b("
    r"m[eé]xic\w*|"
    r"sheinbaum|"
    r"c[aá]rtel\w*|"
    r"fentan\w*|"
    r"extradit\w*|extradici[oó]n\w*|"
    r"indictment|cargos\s*criminales|"
    r"drug\s*traffick\w*|narcotr[aá]fico|"
    r"tariff\w*|arancel\w*|"
    r"usmca|t-?mec|nafta|"
    r"trade\s*war|comercio\s*exterior|"
    r"border|frontera|"
    r"migra\w*|immigra\w*|"
    r"cbp|border\s*patrol|"
    r"port\s*of\s*entry|garita\w*|puente\s*internacional|"
    r"caravan\w*|deport\w*"
    r")\b",
    re.IGNORECASE
)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(category, author, text, link):
    message = (
        f"🚨 <b>[GreciaMini - {category}]</b>\n"
        f"👤 <b>Fuente:</b> {author}\n\n"
        f"{html.escape(text)}\n\n"
        f"🔗 <a href='{link}'>Ver publicación</a>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

def clean_html(raw_html):
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())

def main():
    state = load_state()
    is_initial_run = (len(state) == 0)

    for source in SOURCES:
        category = source["category"]
        name = source["author"]
        url = source["url"]
        last_id = state.get(name)

        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        except Exception:
            continue

        if not feed.entries:
            continue

        if is_initial_run or last_id is None:
            state[name] = feed.entries[0].get("id", feed.entries[0].link)
            continue

        new_entries = []
        for entry in feed.entries:
            entry_id = entry.get("id", entry.link)
            if entry_id == last_id:
                break
            new_entries.append(entry)

        for entry in reversed(new_entries):
            raw_title = entry.get("title", "")
            raw_summary = entry.get("summary", "")
            full_text = clean_html(f"{raw_title} {raw_summary}")

            if KEYWORDS_REGEX.search(full_text):
                preview = full_text[:400] + ("..." if len(full_text) > 400 else "")
                send_telegram(category, name, preview, entry.link)

        if new_entries:
            state[name] = new_entries[0].get("id", new_entries[0].link)

    save_state(state)

if __name__ == "__main__":
    main()
