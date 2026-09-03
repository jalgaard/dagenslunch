import requests
from bs4 import BeautifulSoup
import pdfplumber
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =====================
# KONFIGURATON
# =====================

OUTPUT_FILE = "index.html"

RESTAURANTS = [
    {
        "name": "FEI Restaurang & Lounge",
        "url": "https://www.fei.se/meny-fei-restaurant-lounge",
        "logo": "https://res.cloudinary.com/emg-prod/image/upload/c_limit,h_100,w_200/v1/institutes/institute10621/logos/logo",
        "type": "html"
    },
    {
        "name": "Restaurang Cirkeln",
        "url": "https://cirkelnstockholm.se/restauranger/restaurang-cirkeln/",
        "logo": "https://cirkelnstockholm.se/wp-content/uploads/2021/09/c_restaurang-S-150x150.png",
        "type": "html"
    },
    {
        "name": "Restaurang Rydbergs",
        "url": "https://www.restaurangrydbergs.se/#lunch",
        "logo": "https://www.restaurangrydbergs.se/wp-content/uploads/2025/03/Rydbergs-orange-transperant.png",
        "type": "pdf"
    }
]

WEEKDAYS = {
    0: "MÅNDAG",
    1: "TISDAG",
    2: "ONSDAG",
    3: "TORSDAG",
    4: "FREDAG"
}

STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")
now = datetime.now(STOCKHOLM_TZ)
today_index = now.weekday()
TODAY = WEEKDAYS.get(today_index, None)
TIMESTAMP_STR = now.strftime("%Y-%m-%d %H:%M")

# Gemensam HTTP-session med retries. Minskar risken att ett tillfälligt
# nätverksfel hos en restaurang publicerar en tom/felaktig sida.
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DagensLunchBot/1.0)"
})
retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
SESSION.mount("https://", HTTPAdapter(max_retries=retry))
SESSION.mount("http://", HTTPAdapter(max_retries=retry))

# =====================
# HJÄLPFUNKTIONER
# =====================

def clean_lines(text):
    # Klipp bort allt från och med "Pris:" (oavsett stor/liten bokstav)
    # Detta städar bort sidfoten på Rydbergs meny
    split_match = re.search(r"(Pris:|Pris\s*\d)", text, re.IGNORECASE)
    if split_match:
        text = text[:split_match.start()]
        
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "<br>".join(lines)

# =====================
# HÄMTA MENYER (HTML)
# =====================

def fetch_html_menu(url):
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator="\n")
    except Exception as e:
        print(f"⚠️  Fel vid hämtning av {url}: {e}")
        return ""

# =====================
# HÄMTA MENYER (PDF)
# =====================

def fetch_rydbergs_pdf_text():
    try:
        page = SESSION.get("https://www.restaurangrydbergs.se/", timeout=20)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")

        pdf_link = None
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                pdf_link = a["href"]
                break

        if not pdf_link:
            print("⚠️  Hittade ingen PDF-länk på Rydbergs hemsida.")
            return ""

        if pdf_link.startswith("/"):
            pdf_link = "https://www.restaurangrydbergs.se" + pdf_link

        print(f"   Hittade PDF: {pdf_link}")
        pdf_data = SESSION.get(pdf_link, timeout=20)
        pdf_data.raise_for_status()
        
        # Spara temporärt för analys
        pdf_path = Path("rydbergs.pdf")
        pdf_path.write_bytes(pdf_data.content)

        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text
    except Exception as e:
        print(f"⚠️  Fel vid PDF-hantering: {e}")
        return ""

# =====================
# PARSING LOGIK
# =====================

def extract_today_menu(raw_text):
    if not TODAY:
        return "Ingen lunch idag (Helg)."

    # Regex som letar efter DAGENS NAMN fram till nästa dag eller slut på text
    pattern = rf"{TODAY}(.*?)(MÅNDAG|TISDAG|ONSDAG|TORSDAG|FREDAG|$)"
    match = re.search(pattern, raw_text, re.S | re.I)

    if not match:
        return "Ingen meny hittades för idag."

    return clean_lines(match.group(1))

# =====================
# HUVUDPROGRAM
# =====================

html_blocks = []
errors = []

print(f"🚀 Startar uppdatering för: {TODAY} ({TIMESTAMP_STR}, Europe/Stockholm)...")

for r in RESTAURANTS:
    print(f"→ Bearbetar {r['name']}...")
    if r["type"] == "html":
        raw = fetch_html_menu(r["url"])
    else:
        raw = fetch_rydbergs_pdf_text()

    if not raw.strip():
        errors.append(f"{r['name']}: kunde inte hämta källan")
        continue

    lunch = extract_today_menu(raw)
    if lunch == "Ingen meny hittades för idag.":
        errors.append(f"{r['name']}: dagens meny kunde inte hittas i källan")
        continue

    # Ny HTML-struktur som matchar designönskemålet
    block = f"""
    <div class="restaurant-item">
        <div class="header">
            <div class="logo-container">
                <img src="{r['logo']}" alt="Logo">
            </div>
            <h2>{r['name']}</h2>
        </div>
        <p class="menu-text">{lunch}</p>
    </div>
    """
    html_blocks.append(block)

# Publicera inte en halv eller tom sida. Då får nästa schemalagda körning
# försöka igen i stället för att ersätta en fungerande meny.
if errors:
    for error in errors:
        print(f"❌ {error}")
    raise SystemExit("Avbryter utan att skriva index.html eftersom en eller flera menyer saknas.")

# =====================
# SKAPA INDEX.HTML
# =====================

html = f"""
<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dagens lunch by PMO IT</title>
<style>
    :root {{
        --bg-color: #f4f5f7;
        --card-bg: #ffffff;
        --text-main: #172b4d;
        --text-muted: #5e6c84;
        --border-color: #ebecf0;
        --shadow: 0 4px 8px rgba(0,0,0,0.1);
        --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    body {{
        font-family: var(--font-stack);
        background: var(--bg-color);
        margin: 0;
        padding: 40px 20px;
        display: flex;
        justify-content: center;
        color: var(--text-main);
    }}

    .container {{
        background: var(--card-bg);
        width: 100%;
        max-width: 600px;
        border-radius: 12px;
        box-shadow: var(--shadow);
        padding: 40px;
        box-sizing: border-box;
    }}

    h1 {{
        font-size: 24px;
        margin: 0 0 8px 0;
        font-weight: 700;
        text-align: left;
    }}

    .day-header {{
        font-size: 14px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 30px;
    }}

    .restaurant-item {{
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 24px;
        margin-bottom: 24px;
    }}

    .restaurant-item:last-of-type {{
        border-bottom: none;
        padding-bottom: 0;
        margin-bottom: 0;
    }}

    .header {{
        display: flex;
        align-items: center;
        margin-bottom: 12px;
        gap: 12px;
    }}

    .logo-container {{
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
    }}

    .logo-container img {{
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }}

    .header h2 {{
        font-size: 16px;
        margin: 0;
        font-weight: 700;
    }}

    .menu-text {{
        font-size: 15px;
        line-height: 1.5;
        margin: 0;
        color: #333;
    }}

    .footer {{
        margin-top: 40px;
        border-top: 1px solid var(--border-color);
        padding-top: 15px;
        font-size: 11px;
        color: #999;
        text-align: left;
    }}

</style>
</head>
<body>

    <div class="container">
        <h1>Dagens lunch by PMO IT</h1>
        <div class="day-header">{TODAY if TODAY else "HELG"}</div>

        <div class="menu-list">
            {''.join(html_blocks)}
        </div>

        <div class="footer">
            Uppdaterad: {TIMESTAMP_STR}
        </div>
    </div>

</body>
</html>
"""

output_path = Path(OUTPUT_FILE)

# Om enda skillnaden är tidsstämpeln behöver vi inte skapa en ny commit.
def without_timestamp(value):
    return re.sub(r"Uppdaterad: \d{4}-\d{2}-\d{2} \d{2}:\d{2}", "Uppdaterad: <TIMESTAMP>", value)

if output_path.exists():
    old_html = output_path.read_text(encoding="utf-8")
    if without_timestamp(old_html) == without_timestamp(html):
        print("ℹ️ Menyinnehållet är oförändrat. Ingen fil behöver skrivas om.")
        raise SystemExit(0)

output_path.write_text(html, encoding="utf-8")
print("✅ index.html är uppdaterad!")
