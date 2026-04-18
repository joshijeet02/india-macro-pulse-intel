import json
import re
import requests
from pathlib import Path
from datetime import date
from typing import Optional

MOSPI_PRESS_RELEASE_BASE = "https://mospi.gov.in"
MOSPI_IIP_LIST_URL = (
    "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/"
    "5XjCDPHnBClZ/content/index-industrial-production"
)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_iip.json"

_MONTH_MAP = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def fetch_latest_iip(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest IIP release from MOSPI.

    Returns dict with use-based classification YoY values.
    Returns None on any failure so callers can fall back to the DB.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_iip()
    except Exception as e:
        print(f"[mospi_iip] scrape failed: {e}")
        return None


def _scrape_mospi_iip() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (research bot; joshijeet02@gmail.com)"}
    resp = requests.get(MOSPI_IIP_LIST_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    pdf_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf") and "iip" in a["href"].lower()
    ]
    if not pdf_links:
        raise ValueError("No IIP PDF links found on MOSPI press release page")

    url = pdf_links[0]
    if not url.startswith("http"):
        url = MOSPI_PRESS_RELEASE_BASE + url

    return _parse_iip_pdf(url, headers)


def _parse_iip_pdf(pdf_url: str, headers: dict) -> dict:
    import pdfplumber
    import io

    resp = requests.get(pdf_url, headers=headers, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:4])

    month_match = re.search(
        r"(January|February|March|April|May|June|July|August|September"
        r"|October|November|December)[,\s]+(\d{4})",
        text,
    )
    if not month_match:
        raise ValueError(f"Cannot extract reference month from: {pdf_url}")

    reference_month = f"{month_match.group(2)}-{_MONTH_MAP[month_match.group(1)]}"

    def extract(pattern: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                return None
        return None

    return {
        "reference_month":          reference_month,
        "release_date":             date.today().isoformat(),
        "headline_yoy":             extract(r"General Index.*?(-?\d+\.\d+)"),
        "manufacturing_yoy":        extract(r"Manufacturing.*?(-?\d+\.\d+)"),
        "mining_yoy":               extract(r"Mining.*?(-?\d+\.\d+)"),
        "electricity_yoy":          extract(r"Electricity.*?(-?\d+\.\d+)"),
        "capital_goods_yoy":        extract(r"Capital Goods.*?(-?\d+\.\d+)"),
        "consumer_durables_yoy":    extract(r"Consumer Durables.*?(-?\d+\.\d+)"),
        "consumer_nondurables_yoy": extract(r"Consumer Non.durables.*?(-?\d+\.\d+)"),
        "infra_construction_yoy":   extract(r"Infrastructure.*?(-?\d+\.\d+)"),
        "primary_goods_yoy":        extract(r"Primary Goods.*?(-?\d+\.\d+)"),
        "intermediate_goods_yoy":   extract(r"Intermediate Goods.*?(-?\d+\.\d+)"),
        "source":                   pdf_url,
    }
