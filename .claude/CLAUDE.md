# India Economic Intelligence — Project Context

## What This Project Is

Five AI-powered economic intelligence systems built by Jeet Joshi (economist + builder) to demonstrate
genuine value to India's top private-sector economists. Each system is:
- Built in a 2-day sprint
- Deployed publicly at a URL (no login, no friction)
- Designed around a specific daily bottleneck in a Chief Economist's workflow
- Uses only public Indian government data sources (RBI, MOSPI, SEBI, DPIIT, PPAC)

These systems are NOT portfolio projects. They are working tools sent to real economists
as part of a deliberate outreach strategy for mentorship and career access.

## Build Status

| System | Status | Key Finding | Live URL |
|--------|--------|-------------|----------|
| System 2: India Macro Pulse | ✅ COMPLETE — deploy pending | Mar 2025 CPI 3.34% = SIGNIFICANT BELOW CONSENSUS (z=-2.0, -0.36pp) | TBD (Streamlit Cloud) |
| System 1: RBI Communication Intelligence | 🔲 Next | — | — |
| System 3: India Nowcast Engine | 🔲 Pending | — | — |
| System 4: India External Sector Intelligence | 🔲 Pending | — | — |
| System 5: India Credit Cycle Intelligence | 🔲 Pending | — | — |

System 2 specs: 38 tests passing. DB seeded with 12mo CPI + 11mo IIP, full component decomposition.
Release calendar live (IIP Feb-2026 in ~11 days, CPI Apr-2026 in ~24 days).
Flash briefs via Claude API (gated behind ANTHROPIC_API_KEY in Streamlit Cloud secrets).
Deploy: push to GitHub (public) → Streamlit Cloud → add ANTHROPIC_API_KEY secret.

## The Five Systems (Build Order)

### System 1: RBI Communication Intelligence (BUILD FIRST)
**What:** RAG pipeline on all public RBI documents — MPC minutes (2016–present), policy statements,
governor speeches, Monetary Policy Reports. Two modes: query-based exploration + auto-briefing
on every new MPC release (what changed across 5 dimensions: growth assessment, inflation assessment,
risk balance, liquidity stance, forward guidance language).
**Data:** rbi.org.in — all PDFs publicly available
**Target economists:** Universal — every economist tracks MPC
**Economic logic embedded:** Knows the difference between rate stance and liquidity stance,
tracks uncertainty language, maps vote patterns

### System 2: India Macro Pulse — Data Release Intelligence
**What:** Monitors all major India public data releases in real time. Computes surprise vs consensus
(from RBI SPF and newspaper surveys). Decomposes intelligently (CPI: core ex-food-fuel / food / fuel;
IIP: capital goods / consumer durables / infrastructure). Generates structured flash briefs.
**Data:** RBI DBIE, MOSPI press releases, SEBI FPI data, DPIIT, PPAC
**Target economists:** Universal — Soumya Kanti Ghosh (SBI Ecowrap), CRISIL desk, all bank economists
**Economic logic embedded:** Component decomposition reflects what RBI/market actually watches,
not just headline numbers

### System 3: India Nowcast Engine — High-Frequency Activity Tracker
**What:** Aggregates HF indicators (GST collections, e-way bills, electricity generation, railway freight,
fuel consumption, bank credit, UPI volume, PMI, port cargo) into a composite activity index.
Generates GDP nowcast range for current quarter. Shows which indicators are accelerating vs decelerating.
**Data:** MoF (GST), GSTN (e-way), CEA (power), Railways, PPAC, NPCI (UPI), DPIIT (ports)
**Target economists:** All sell-side economists — Sajjid Chinoy, Neelkanth Mishra, Samiran Chakraborty
**Economic logic embedded:** Weights derived from historical correlation with GDP, not arbitrary

### System 4: India External Sector Intelligence
**What:** Unified BoP/external position monitor. FPI flows (SEBI weekly), trade data (DGCI&S monthly),
forex reserves (RBI weekly), REER/NEER (RBI), crude import bill (PPAC). Computes external vulnerability
score, rupee pressure analysis, BoP sustainability, peer comparison (India vs Indonesia/Brazil/S.Africa/Turkey).
**Data:** RBI DBIE, SEBI data portal, PPAC, DGCI&S
**Target economists:** Foreign bank Chief Economists — Pranjul Bhandari (HSBC), Sajjid Chinoy (JP Morgan),
Samiran Chakraborty (Citi), Sonal Varma (Nomura)
**Economic logic embedded:** Guidotti-Greenspan reserve adequacy, import cover ratio, BoP accounting

### System 5: India Credit Cycle Intelligence
**What:** Ingests RBI sectoral credit deployment tables + SEBI corporate bond data.
Generates: credit momentum map (30+ sectors), credit-activity alignment analysis,
early warning layer (credit faster than activity = Minsky signal), NBFC vs bank split.
**Data:** RBI DBIE sectoral credit tables (quarterly), SEBI bond issuance, IIP sector data
**Target economists:** Dharmakirti Joshi (CRISIL), Aditi Nayar (ICRA), Rajani Sinha (CareEdge),
Soumya Kanti Ghosh (SBI), Neelkanth Mishra (Axis Bank)
**Economic logic embedded:** Hyman Minsky early warning logic, CRAMEL framework awareness

## Key Economists Being Targeted

| Economist | Institution | Primary Systems | Warmth |
|-----------|-------------|-----------------|--------|
| Sajjid Chinoy | JP Morgan (Chief India Economist) | 1, 2, 3, 4 | Cold |
| Dharmakirti Joshi | CRISIL (Chief Economist) | 1, 2, 5 | Cold |
| Samiran Chakraborty | Citi India (Chief Economist) | 1, 2, 3, 4 | Cold |
| Pranjul Bhandari | HSBC (Chief India Economist) | 1, 2, 4 | Cold |
| Neelkanth Mishra | Axis Bank (Chief Economist) | 1, 2, 3, 5 | Cold |
| Abheek Barua | HDFC Bank (Chief Economist) | 1, 2 | Cold |
| Aditi Nayar | ICRA (Chief Economist) | 1, 2, 5 | Cold |
| Soumya Kanti Ghosh | SBI (Group CEA) | 1, 2, 5 | Cold |
| Manish Sabharwal | TeamLease (VC) | 2, 3 | Accessible |
| Nitin Pai | Takshashila (Co-founder) | 1, 2 | Warm — published Jeet's work |

## About Jeet Joshi (Builder)

- Economist from Banswara, Rajasthan. Based in Ahmedabad.
- MSc Financial Economics, University of Sydney (2023–2025)
- BSc Economics, GIPE Pune (2020–2023), CGPA 8.77/10
- Newsletter: "Chai with an Economist" — 3,000+ readers, published by Takshashila/Pulliyabaazi
- Current role: Program Fellow, Alliance for Change (development sector research)
- Past: CBGA (budget & governance research), Dorian Scale (impact finance advisory), GIPE fieldwork Ladakh
- Builds real AI systems: VAAGDHARA (Hindi voice AI for tribal women), MNREGA dashboard, grant intelligence
- Email: joshijeet02@gmail.com | jeetjoshi.netlify.app

## Outreach Strategy

NOT job applications. The email framing is:
"I am an economist who builds. I built this specifically because I thought it would be
genuinely useful to your work. I'd love to learn where I got the economics wrong or
how you'd make it better — and if you're open to it, to learn from you more broadly."

First email targets Manish Sabharwal or Nitin Pai (warmest connections).
Foreign bank economists (Sajjid Chinoy, Pranjul Bhandari) come after 3+ systems are live.

## Technical Stack

- **Backend:** Python 3.10, FastAPI, requests, BeautifulSoup4, pdfplumber, pandas
- **Browser automation:** Playwright (Python) — for JS-rendered govt portals
- **RAG:** Anthropic API + custom retrieval (chromadb when available, else simple vector search)
- **UI:** Streamlit or React (TBD per system) — must be deployable with zero friction
- **Deployment:** Streamlit Cloud or Vercel (free tier, no auth required)
- **Scraping targets:** RBI DBIE, MOSPI, SEBI data portal, DPIIT, PPAC, GSTN, CEA, NPCI, Railways

## Development Rules (Non-Negotiable)

1. Economic logic first, tech second. Every architectural decision must be justified by
   what an economist actually needs, not what's technically elegant.
2. No friction for end users. Opens in browser in under 10 seconds. No signup. No install.
3. Data sources must be 100% public. No Bloomberg, no CMIE paid, no Reuters.
4. Each system must include at least one genuine economic insight that emerges from the data —
   not just a dashboard, but a finding.
5. 2-day sprint discipline: Day 1 = data pipeline + core logic. Day 2 = UI + deploy + document.

## Installed Skills (Available in This Project)

### From obra/superpowers (Development Methodology)
- brainstorming — refine system design before coding
- writing-plans — break each system into 2–5 minute tasks
- executing-plans — structured execution with verification
- subagent-driven-development — parallel agent dispatch for speed
- test-driven-development — RED-GREEN-REFACTOR for data pipelines
- systematic-debugging — root cause analysis when scrapers break
- verification-before-completion — evidence-based sign-off
- dispatching-parallel-agents — run multiple build tasks simultaneously

### From affaan-m/everything-claude-code (Build Skills)
- data-scraper-agent — automated data collection from public sources
- api-connector-builder — clean data connectors for each source
- backend-patterns — Python FastAPI patterns
- dashboard-builder — operational dashboards that answer real questions
- python-patterns — clean Python code standards
- python-testing — test coverage for data pipelines
- agentic-engineering — AI agent architecture
- research-ops — RAG pipeline patterns
- deep-research — multi-source document analysis
- market-research — synthesising economic intelligence
- autonomous-agent-harness — agentic data pipeline orchestration

### From nextlevelbuilder/ui-ux-pro-max (Design)
- ui-ux-pro-max — intelligent design system generator (fintech/data rules built in)
- design-system — complete design system for dashboards
- ui-styling — 67 UI styles, 161 colour palettes
- brand — consistent visual identity
- banner-design — landing page assets

### From thedotmack/claude-mem (Memory)
- mem-search — query past session observations
- make-plan — phased implementation planning
- do — execute phased plans with subagents
- smart-explore — explore codebase across sessions
- knowledge-agent — persistent knowledge retrieval
- timeline-report — what was built when

## Data Sources Reference

| Source | URL | Data | Update Frequency |
|--------|-----|------|-----------------|
| RBI DBIE | data.rbi.org.in | All macro, credit, monetary, external | Various |
| RBI Publications | rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | MPC minutes, policy statements | Bi-monthly |
| MOSPI | mospi.gov.in | GDP, CPI, IIP, NAS | Monthly/Quarterly |
| SEBI | sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes | FPI flows | Weekly |
| DPIIT | dpiit.gov.in | FDI, trade | Monthly |
| PPAC | ppac.gov.in | Crude oil, petroleum products | Monthly |
| GSTN | gst.gov.in/newsandupdates | GST collections | Monthly |
| CEA | cea.nic.in | Electricity generation | Daily/Monthly |
| NPCI | npci.org.in/what-we-do/upi/product-statistics | UPI transactions | Monthly |
| Railways | indianrailways.gov.in | Freight loading | Monthly |
