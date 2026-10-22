import json
import os
import re
import html
import sys
import time
import requests
import feedparser
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
X_AUTH_TOKEN = os.environ.get("X_AUTH_TOKEN", "").strip()
X_CT0 = os.environ.get("X_CT0", "").strip()

STATE_FILE = "last_seen_posts.json"

# ================= 1. TRUTH SOCIAL DIRECTO =================
TRUTH_SOURCES = [
    {"category": "TRUTH SOCIAL", "author": "Donald Trump", "url": "https://trumpstruth.org/feed"}
]

# ================= 2. CUENTAS DE X (ALGORITMO MAGA / GOBIERNO EE.UU.) =================
X_SOURCES = [
    # Liderazgo Casa Blanca y círculo cercano
    {"category": "VICEPRESIDENCIA", "author": "JD Vance", "handle": "JDVance"},
    {"category": "TRUMP OFICIAL", "author": "Donald J. Trump", "handle": "realDonaldTrump"},
    {"category": "TRUMP FEED", "author": "Trump Daily Posts", "handle": "TrumpDailyPosts"},
    {"category": "TRUMP FEED", "author": "Truth Trump Posts", "handle": "TruthTrumpPosts"},
    {"category": "EQUIPO TRUMP", "author": "Rapid Response 47", "handle": "RapidResponse47"},
    {"category": "EQUIPO TRUMP", "author": "Team Trump", "handle": "TeamTrump"},
    {"category": "REDES TRUMP", "author": "Dan Scavino", "handle": "DanScavino"},
    {"category": "CASA BLANCA", "author": "Stephen Miller", "handle": "StephenM"},
    {"category": "SENADO / GOBIERNO", "author": "Marco Rubio", "handle": "marcorubio"},

    # Diplomacia y Relaciones Exteriores
    {"category": "DIPLOMACIA EE.UU.", "author": "State Dept", "handle": "StateDept"},

    # Seguridad, Justicia y Frontera
    {"category": "ZAR DE LA FRONTERA", "author": "Tom Homan", "handle": "RealTomHoman"},
    {"category": "AGENCIA SEGURIDAD", "author": "DEA HQ", "handle": "DEAHQ"},
    {"category": "JUSTICIA EE.UU.", "author": "DOJ", "handle": "TheJusticeDept"},
    {"category": "SEGURIDAD NACIONAL", "author": "DHS", "handle": "DHSgov"},
    {"category": "SEGURIDAD NACIONAL", "author": "CBP", "handle": "CBP"},
    {"category": "INVESTIGACIONES SEGURIDAD", "author": "HSI HQ", "handle": "HSI_HQ"},
    {"category": "GOBIERNO TEXAS", "author": "Gov. Greg Abbott", "handle": "GregAbbott_TX"},
    {"category": "FRONTERA REPORTEROS", "author": "Ali Bradley", "handle": "AliBradleyTV"},
    {"category": "FRONTERA REPORTEROS", "author": "Bill Melugin", "handle": "BillMelugin_"},
    {"category": "FRONTERA REPORTEROS", "author": "Griff Jenkins", "handle": "GriffJenkins"},

    # Comercio, Aranceles y T-MEC
    {"category": "COMERCIO EE.UU.", "author": "USTR", "handle": "USTradeRep"},
    {"category": "COMERCIO EE.UU.", "author": "Dept of Commerce", "handle": "CommerceGov"},
    {"category": "PRENSA COMERCIAL", "author": "Doug Palmer", "handle": "DougPalmer"},
    {"category": "PRENSA COMERCIAL", "author": "Gavin Bade", "handle": "GavinBade"},

    # Ruptura política, clips y filtraciones
    {"category": "CLIPS TRUMP", "author": "Acyn", "handle": "Acyn"},
    {"category": "FILTRACIONES NYT", "author": "Maggie Haberman", "handle": "maggieNYT"},
    {"category": "CONGRESO EE.UU.", "author": "Punchbowl News", "handle": "PunchbowlNews"},
    {"category": "CONGRESO EE.UU.", "author": "Jake Sherman", "handle": "JakeSherman"}
]

# ================= FILTROS TEMÁTICOS DEPURADOS =================
KEYWORDS_REGEX = re.compile(
    r"\b("
    r"m[eé]xic\w*|mexican\w*|"
    r"claudia\s*sheinbaum|sheinbaum|"
    r"roberto\s*velasco|velasco\s*[aá]lvarez|@r_velascoa|"
    r"c[aá]rtel\w*|"
    r"fentan\w*|"
    r"extradit\w*|extradici[oó]n\w*|"
    r"drug\s*traffick\w*|narcotr[aá]fico|"
    r"tariff\w*|arancel\w*|"
    r"usmca|t-?mec|nafta|"
    r"trade\s*war|comercio\s*exterior"
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

def clean_html(raw_html):
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())

def send_telegram(category, author, text, link):
    safe_text = html.escape(text)
    message = (
        f"🚨 <b>[GreciaMini - {category}]</b>\n"
        f"👤 <b>Fuente:</b> {author}\n\n"
        f"{safe_text}\n\n"
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
        print(f"Error al enviar mensaje a Telegram: {e}", flush=True)

def scrape_tweets(page, handle):
    url = f"https://x.com/{handle}"
    page.goto(url, wait_until="domcontentloaded", timeout=12000)

    for _ in range(2):
        page.mouse.wheel(0, 800)
        time.sleep(0.8)

    tweet_elements = page.locator("article[data-testid='tweet']").all()[:5]
    if not tweet_elements:
        tweet_elements = page.locator("div[aria-label*='Timeline'] article, section article").all()[:5]

    tweets = []
    for art in tweet_elements:
        try:
            link_elem = art.locator("a[href*='/status/']").first
            href = link_elem.get_attribute("href") if link_elem.count() > 0 else None
            if not href or "/status/" not in href:
                continue

            match_id = re.search(r"/status/(\d+)", href)
            tweet_id = match_id.group(1) if match_id else href

            text_elem = art.locator("[data-testid='tweetText']").first
            text = text_elem.inner_text() if text_elem.count() > 0 else art.inner_text()

            tweets.append({
                "id": str(tweet_id),
                "text": text,
                "link": f"https://x.com{href}" if href.startswith("/") else href
            })
        except Exception:
            continue

    return tweets

def process_truth_social(state, is_initial_run):
    print("=== MONITOREANDO TRUTH SOCIAL ===", flush=True)
    for source in TRUTH_SOURCES:
        category = source["category"]
        name = source["author"]
        url = source["url"]
        last_id = state.get(name)

        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        except Exception as e:
            print(f"❌ Error al consultar Truth Social ({name}): {e}", flush=True)
            continue

        if not feed.entries:
            print(f"⚠️ Sin entradas en Truth Social ({name})", flush=True)
            continue

        print(f"✅ Truth Social ({name}): {len(feed.entries)} publicaciones obtenidas.", flush=True)

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
                print(f"🚨 Coincidencia en Truth Social: {full_text[:60]}", flush=True)
                preview = full_text[:400] + ("..." if len(full_text) > 400 else "")
                send_telegram(category, name, preview, entry.link)

        if new_entries:
            state[name] = new_entries[0].get("id", new_entries[0].link)

def process_x_sources(state, is_initial_run):
    print(f"\n=== MONITOREANDO X: {len(X_SOURCES)} FUENTES ===", flush=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-ES",
            viewport={"width": 1280, "height": 900}
        )

        context.add_cookies([
            {"name": "auth_token", "value": X_AUTH_TOKEN, "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": X_CT0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": X_AUTH_TOKEN, "domain": "x.com", "path": "/"},
            {"name": "ct0", "value": X_CT0, "domain": "x.com", "path": "/"}
        ])

        page = context.new_page()

        for source in X_SOURCES:
            category = source["category"]
            author = source["author"]
            handle = source["handle"]
            last_id = state.get(handle)

            try:
                tweets = scrape_tweets(page, handle)
            except Exception as e:
                print(f"❌ Error al consultar @{handle}: {e}", flush=True)
                continue

            print(f"✅ @{handle}: {len(tweets)} tuits obtenidos.", flush=True)

            if not tweets:
                continue

            if is_initial_run or last_id is None:
                state[handle] = tweets[0]["id"]
                continue

            new_tweets = []
            for t in tweets:
                if t["id"] == last_id:
                    break
                new_tweets.append(t)

            for t in reversed(new_tweets):
                full_text = clean_html(t["text"])
                if KEYWORDS_REGEX.search(full_text):
                    print(f"🚨 Coincidencia en @{handle}: {full_text[:60]}", flush=True)
                    preview = full_text[:400] + ("..." if len(full_text) > 400 else "")
                    send_telegram(category, f"{author} (@{handle})", preview, t["link"])

            if new_tweets:
                state[handle] = new_tweets[0]["id"]

        browser.close()

def main():
    state = load_state()
    is_initial_run = (len(state) == 0)

    # 1. Monitoreo de Truth Social
    process_truth_social(state, is_initial_run)

    # 2. Monitoreo de X con Playwright
    process_x_sources(state, is_initial_run)

    save_state(state)
    print("\n=== FIN DEL MONITOREO MAGA ===", flush=True)

if __name__ == "__main__":
    main()
