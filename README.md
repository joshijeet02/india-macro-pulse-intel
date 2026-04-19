# India Macro Pulse — Data Release Intelligence

Streamlit-powered Indian macro intelligence platform. Ingests CPI and IIP data, computes surprise indices vs consensus, decomposes drivers (food/fuel/core), and generates AI-authored flash briefs using Anthropic Claude.

## Project Structure

- `systems/02-macro-pulse/`: Core application logic and Streamlit UI.
- `docs/`: Strategic plans and documentation.
- `shared/`: Utilities and common components.
- `requirements.txt`: Project-wide dependencies.

## Key Features

- **Automated Ingestion**: Scrapes MOSPI and RBI data releases.
- **Economic Decomposition**: Analyzes CPI into food, fuel, and core components.
- **Surprise Index**: Benchmarks releases against consensus forecasts.
- **AI Synthesis**: Generates expert-level flash briefs for rapid assimilation.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python 3.10+, SQLite
- **Intelligence**: Anthropic Claude API
- **Data Parsing**: pdfplumber, BeautifulSoup4

## Getting Started

1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Set up your `.env` file with `ANTHROPIC_API_KEY`.
4. Run the app: `streamlit run systems/02-macro-pulse/app.py`.
