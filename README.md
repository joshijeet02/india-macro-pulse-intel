# India Macro Pulse — Data Release Intelligence

Streamlit-powered Indian macro intelligence platform. Ingests CPI and IIP data, computes surprise indices vs consensus, decomposes drivers (food / fuel / core), runs a real-time grocery price index against Amazon, and generates AI-authored flash briefs using Anthropic Claude.

Live: https://india-macro-pulse.streamlit.app/

## Project Structure

- `systems/02-macro-pulse/`: Core application logic and Streamlit UI.
- `.github/workflows/`: Autonomous data refresh and Amazon scrape jobs.
- `docs/`: PRDs and strategic plans.
- `requirements.txt`: Project-wide dependencies.

## Key Features

- **Autonomous ingestion**: A scheduled GitHub Action scrapes MOSPI on every release window (CPI ~12th, IIP ~28th–31st), updates `data/release_updates.json`, and pushes to `main` — Streamlit Cloud auto-redeploys with the new month live within minutes.
- **Real Amazon basket index**: A weekly GH Action scrapes a 20-item CPI-aligned grocery basket from Amazon India, applies outlier rejection vs trailing median, and persists to `data/amazon_prices.json`. Survives Streamlit Cloud's ephemeral filesystem.
- **CPI / IIP decomposition**: Headline broken into food, fuel, core (CPI) and use-based components — investment, consumption, infra (IIP). Rule-based assessments calibrated to RBI's monetary framework.
- **Surprise tracker**: Each release benchmarked vs consensus, z-scored against historical volatility.
- **Plain English mode**: A sidebar toggle reframes every assessment in non-jargon language for non-economists. Glossary tooltips on key terms.
- **Calendar export**: Download all upcoming MOSPI release dates as `.ics` for Google / Apple Calendar.
- **CSV exports**: Every chart's data is one click away from your spreadsheet.

## Data flow

```
MOSPI press release page ─┐
                          ├─► refresh-data.yml (cron) ─► data/release_updates.json
Amazon search results ────┤                                        │
                          └─► scrape-amazon.yml (cron) ─► data/amazon_prices.json
                                                                   │
                                          On Streamlit Cloud boot ─┘
                                                  │
                                                  ▼
                          SQLite hydrated → UI reads → user sees fresh data
```

The repo IS the database. No external infra needed.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python 3.10+, SQLite
- **Intelligence**: Anthropic Claude API (flash briefs)
- **Data Parsing**: pdfplumber + BeautifulSoup4 (MOSPI), Playwright (Amazon)
- **Automation**: GitHub Actions

## Getting Started

1. Clone and `cd systems/02-macro-pulse`.
2. `pip install -r requirements.txt`.
3. Optional: set `ANTHROPIC_API_KEY` in `.env` for AI flash briefs.
4. `streamlit run app.py`.

## Manually triggering the data refresh

```bash
# Smoke test with fixtures (no network)
python systems/02-macro-pulse/scripts/refresh_releases.py --use-fixture --dry-run

# Live scrape — appends new releases to data/release_updates.json
python systems/02-macro-pulse/scripts/refresh_releases.py
```

## Documentation

- [PRD: autonomous ingestion + enhancements](docs/PRD-2026-04-autonomous-ingestion-and-enhancements.md)
