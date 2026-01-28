import requests
from bs4 import BeautifulSoup
import pdfplumber
from datetime import datetime
import re
from pathlib import Path

# =====================
# KONFIG
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
        "logo": "Rydbergs-orange-transperant.png",
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

today_index = datetime.now().weekday()
TODAY = WEEKDAYS.get(today_index, None)

# =====================
# HJÄLPFUNKTIONER
# =====================

def clean_lines(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "<br>".join(lines)

# =====================
# FEI + CIRKELN
# =====================

def fetch_html_menu(url):
    r = requests.get(url, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.get_text(separator="\n")

# =====================
# RYDBERGS (PDF)
# =====================

def fetch_rydbergs_pdf_text():
    page = requests.get("https://www.restaurangrydbergs.se/")
    soup = BeautifulSoup(page.text, "html.parser")

    pdf_link = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            pdf_link = a["href"]
            break

    if not pdf_link:
        return ""

    if pdf_link.startswith("/"):
        pdf_link = "https://www.restaurangrydbergs.se" + pdf_link

    pdf_data = requests.get(pdf_link)
    pdf_path = Path("rydbergs.pdf")
    pdf_path.write_bytes(pdf_data.content)

    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"

    return text

# =====================
# PARSING
# =====================

def extract_today_menu(raw_text):
    if not TODAY:
        return "Ingen lunch idag."

    pattern = rf"{TODAY}(.*?)(MÅNDAG|TISDAG|ONSDAG|TORSDAG|FREDAG|$)"
    match = re.search(pattern, raw_text, re.S | re.I)

    if not match:
        return "Ingen meny hittades."

    return clean_lines(match.group(1))

# =====================
# BYGG HTML
# =====================

html_blocks = []

for r in RESTAURANTS:
    if r["type"] == "html":
        raw = fetch_html_menu(r["url"])
    else:
        raw = fetch_rydbergs_pdf_text()

    lunch = extract_today_menu(raw)

    block = f"""
    <div class="restaurant">
        <div class="header">
            <img src="{r['logo']}" alt="{r['name']}">
            <h2>{r['name']}</h2>
        </div>
        <p>{lunch}</p>
    </div>
    """

    html_blocks.append(block)

# =====================
# SLUTLIG HTML
# =====================

html = f"""
<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<title>Dagens lunch</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f7f7f7;
    padding: 20px;
}}
h1 {{
    text-align: center;
}}
.day {{
    text-align: center;
    font-weight: bold;
    margin-bottom: 30px;
}}
.restaurant {{
    background: white;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 8px;
}}
.header {{
    display: flex;
    align-items: center;
    gap: 15px;
}}
.header img {{
    width: 50px;
    height: auto;
}}
</style>
</head>
<body>

<h1>Dagens lunch by PMO IT</h1>
<div class="day">{TODAY if TODAY else "Ingen lunch idag"}</div>

{''.join(html_blocks)}

</body>
</html>
"""

Path(OUTPUT_FILE).write_text(html, encoding="utf-8")

print("index.html skapad ✅")
