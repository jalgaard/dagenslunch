import requests
from bs4 import BeautifulSoup
import pdfplumber
from datetime import datetime
import re
from pathlib import Path

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

now = datetime.now()
today_index = now.weekday()
TODAY = WEEKDAYS.get(today_index, None)
TIMESTAMP_STR = now.strftime("%Y-%m-%d %H:%M")

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
        r = requests.get(url, timeout=15)
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
        page = requests.get("https://www.restaurangrydbergs.se/", timeout=15)
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
        pdf_data = requests.get(pdf_link, timeout=15)
        
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

print(f"🚀 Startar uppdatering för: {TODAY}...")

for r in RESTAURANTS:
    print(f"→ Bearbetar {r['name']}...")
    if r["type"] == "html":
        raw = fetch_html_menu(r["url"])
    else:
        raw = fetch_rydbergs_pdf_text()

    lunch = extract_today_menu(raw)

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

Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
print("✅ index.html är uppdaterad! Öppna filen för att se resultatet.")
