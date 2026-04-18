import json
import re
import requests
from pathlib import Path
from datetime import date
from typing import Optional

MOSPI_PRESS_RELEASE_BASE = "https://mospi.gov.in"
MOSPI_CPI_LIST_URL = (
    "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/"
    "5XjCDPHnBClZ/content/consumer-price-indices-cpi"
)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_cpi.json"

_MONTH_MAP = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def fetch_latest_cpi(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest CPI release from MOSPI.

    Returns dict with: reference_month, release_date, headline_yoy, food_yoy, fuel_yoy, source.
    Returns None on any failure so callers can fall back to the DB.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_cpi()
    except Exception as e:
        print(f"[mospi_cpi] scrape failed: {e}")
        return None


def _scrape_mospi_cpi() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (research bot; joshijeet02@gmail.com)"}
    resp = requests.get(MOSPI_CPI_LIST_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    pdf_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf") and "cpi" in a["href"].lower()
    ]
    if not pdf_links:
        raise ValueError("No CPI PDF links found on MOSPI press release page")

    url = pdf_links[0]
    if not url.startswith("http"):
        url = MOSPI_PRESS_RELEASE_BASE + url

    return _parse_cpi_pdf(url, headers)


def _parse_cpi_pdf(pdf_url: str, headers: dict) -> dict:
    import pdfplumber
    import io

    resp = requests.get(pdf_url, headers=headers, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])

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
        "reference_month": reference_month,
        "release_date": date.today().isoformat(),
        "headline_yoy": extract(r"General Index.*?(-?\d+\.\d+)"),
        "food_yoy":     extract(r"Food and Beverages.*?(-?\d+\.\d+)"),
        "fuel_yoy":     extract(r"Fuel and Light.*?(-?\d+\.\d+)"),
        "source":       pdf_url,
    }
