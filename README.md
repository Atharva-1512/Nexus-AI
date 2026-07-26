# NEXUS AI
### NIFTY Expert eXecution & Understanding System

> **Institutional-grade AI-powered trading intelligence platform for the Indian stock market.**
> Specialized in NIFTY 50 option trade probability estimation and decision support.

---

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=nextdotjs)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What NEXUS AI Does

NEXUS AI is an **AI Decision Support System**, not a trading bot. It combines:

- **Quantitative Finance** — Options pricing (Black-Scholes, Heston, SABR), Greeks, volatility models
- **Machine Learning** — LSTM, Transformers, XGBoost, LightGBM, ensemble models
- **Market Microstructure** — Order book, OI analysis, GEX, PCR, Max Pain
- **NLP Intelligence** — News sentiment, event detection, impact scoring
- **Macro Analysis** — Global markets, FII/DII flows, macro regime detection
- **Explainable AI** — Every prediction shows WHY with weighted factor breakdown

### Primary Output

```
┌─────────────────────────────────────────────────┐
│  NEXUS AI Signal                                 │
│                                                  │
│  ● BUY CALL          Confidence: 87%            │
│                                                  │
│  Entry:    24,215    Stop Loss:  23,980          │
│  Target 1: 24,490    Target 2:   24,750          │
│  Risk:Reward  2.1:1  Hold Time:  ~90 min         │
│                                                  │
│  Factor Breakdown:                               │
│  PCR ↑           18% ████████                   │
│  OI Build-up     21% █████████                  │
│  FII Buying      15% ██████                     │
│  Indicators      20% ████████                   │
│  News Positive   12% █████                      │
│  Greeks          14% ██████                     │
│                                                  │
│  ⚠ VIX elevated — confidence reduced by 8%      │
└─────────────────────────────────────────────────┘
```

> **PAPER TRADING MODE IS ALWAYS ON BY DEFAULT.**
> Live execution is disabled. The system is for analysis and decision support only.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, TradingView Charts, Recharts |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **AI/ML** | PyTorch, TensorFlow, XGBoost, LightGBM, CatBoost, HuggingFace Transformers |
| **Streaming** | Apache Kafka, Redis |
| **Database** | PostgreSQL 16 + TimescaleDB, MongoDB |
| **Deployment** | Docker, Docker Compose, Kubernetes-ready |

### Free Data Sources (No API Key Required)

| Data | Source |
|---|---|
| NIFTY Historical OHLCV | `yfinance` (Yahoo Finance) |
| NSE Option Chain (Live) | NSE India website (`nsepython`) |
| India VIX | Yahoo Finance / NSE direct |
| Global Indices | Yahoo Finance |
| Macro (Crude, Gold, DXY) | Yahoo Finance / Stooq |
| Bond Yields | Yahoo Finance / FRED |
| News | NewsAPI (free tier) + web scraping |
| FII/DII Data | NSE India website |
| Social Sentiment | Reddit (`praw` — free) |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker Desktop
- Git

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd nexus-ai
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env — all defaults work for local development
# Optional: add free API keys for NewsAPI, Reddit, FRED
```

### 3. Start Infrastructure (Docker)
```bash
# Start databases, Redis, Kafka
make up-infra
```

### 4. Start Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/api/docs

### 5. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard at: http://localhost:3000

### Using Docker Compose (Recommended)
```bash
make dev
```
This starts everything: databases, Redis, Kafka, backend, and frontend.

---

## Project Structure

```
nexus-ai/
├── frontend/                    # Next.js dashboard
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API endpoints
│   │   ├── core/                # Config, logging
│   │   ├── models/              # Pydantic schemas
│   │   └── services/            # Business logic
│   └── tests/                   # Test suite
├── modules/                     # 24 independent analytical modules
│   ├── market_data/             # Module 1: Data Engine (yfinance, NSE)
│   ├── microstructure/          # Module 2: Order book, bid/ask
│   ├── options_engine/          # Module 3: BS, Heston, SABR pricing
│   ├── greeks_engine/           # Module 4: All 12 Greeks
│   ├── chain_intelligence/      # Module 5: PCR, GEX, Max Pain, OI
│   ├── technical_analysis/      # Module 6: 25+ TA indicators
│   ├── price_action/            # Module 7: Structure, patterns
│   ├── volume_analysis/         # Module 8: Volume Profile, footprint
│   ├── volatility_engine/       # Module 9: HV, RV, IV, GARCH
│   ├── macro_engine/            # Module 10: Macro signals
│   ├── global_markets/          # Module 11: Global correlations
│   ├── news_intelligence/       # Module 12: NLP news classifier
│   ├── social_intelligence/     # Module 13: Reddit/social sentiment
│   ├── corporate_events/        # Module 14: Results, buybacks, splits
│   ├── calendar_intelligence/   # Module 15: Expiry, RBI, elections
│   ├── ml_engine/               # Module 16: All ML models
│   ├── feature_engineering/     # Module 17: 100+ features, feature store
│   ├── regime_detection/        # Module 18: Market regime (HMM)
│   ├── risk_management/         # Module 19: Kelly, drawdown, sizing
│   ├── backtesting/             # Module 20: Walk-forward, Monte Carlo
│   ├── explainable_ai/          # Module 21: SHAP, LIME, factor weights
│   ├── decision_engine/         # Module 22: Signal fusion, final output
│   ├── alert_engine/            # Module 24: Desktop + sound alerts
│   └── explainability_dashboard/ # Module 23: XAI dashboard data
├── data/                        # Data pipeline
├── streaming/                   # Kafka producers/consumers
├── ml/                          # Training pipelines & model registry
├── infrastructure/              # Docker, Kubernetes configs
├── docs/                        # Full documentation
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Modules (24 Total)

| # | Module | Status | Phase |
|---|---|---|---|
| 1 | Market Data Engine | ✅ Base Implemented | Phase 1-2 |
| 2 | Market Microstructure | 🔄 Stub | Phase 2 |
| 3 | Options Engine (BS, Heston, SABR) | ✅ BS Implemented | Phase 3 |
| 4 | Greeks Engine (12 Greeks) | ✅ Implemented | Phase 3 |
| 5 | Option Chain Intelligence | 🔄 Stub | Phase 4 |
| 6 | Technical Analysis (25+ indicators) | 🔄 Stub | Phase 5 |
| 7 | Price Action Engine | 🔄 Stub | Phase 5 |
| 8 | Volume Analysis | 🔄 Stub | Phase 5 |
| 9 | Volatility Engine | 🔄 Stub | Phase 6 |
| 10 | Macro Engine | 🔄 Stub | Phase 6 |
| 11 | Global Markets | 🔄 Stub | Phase 6 |
| 12 | News Intelligence (NLP) | 🔄 Stub | Phase 7 |
| 13 | Social Media Intelligence | 🔄 Stub | Phase 7 |
| 14 | Corporate Events | 🔄 Stub | Phase 7 |
| 15 | Calendar Intelligence | 🔄 Stub | Phase 7 |
| 16 | Machine Learning Engine | 🔄 Stub | Phase 8 |
| 17 | Feature Engineering | 🔄 Stub | Phase 8 |
| 18 | Market Regime Detection | 🔄 Stub | Phase 9 |
| 19 | Risk Management | 🔄 Stub | Phase 9 |
| 20 | Backtesting | 🔄 Stub | Phase 9 |
| 21 | Explainable AI (SHAP) | 🔄 Stub | Phase 10 |
| 22 | Decision Engine | 🔄 Stub | Phase 10 |
| 23 | Explainability Dashboard | 🔄 Stub | Phase 10 |
| 24 | Alert Engine (Desktop + Sound) | 🔄 Stub | Phase 10 |

---

## Running Tests

```bash
# All tests
make test

# With coverage report
make test-cov

# Black-Scholes pricer tests only
make test-bs

# API endpoint tests only
make test-api
```

---

## API Documentation

Once the backend is running:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## Alert System

NEXUS AI includes a real-time alert engine with:
- Desktop push notifications (Windows/Mac/Linux via `plyer`)
- Sound alerts (configurable: beep, chime, custom WAV)
- Browser web push notifications (via service worker)
- Alert types: Trade Signal, Setup Forming, Stop Loss Hit, Macro Event, News Alert, Expiry Warning
- Do-Not-Disturb window (configurable quiet hours)

---

## Design Principles

| Principle | How |
|---|---|
| No Look-ahead Bias | Strict timestamp gating — all features use only past data |
| No Survivorship Bias | Full historical data including delisted instruments |
| Provider Independence | All data sources behind abstract `DataProvider` interface |
| Module Independence | Each module is self-contained with own tests |
| Confidence Gating | Signals only output when confidence >= threshold |
| Explainability First | Every prediction includes SHAP-based factor breakdown |
| Paper Trading Default | Live execution disabled; paper trading always on |

---

## Makefile Commands

```bash
make help           # Show all available commands
make dev            # Start full stack (Docker)
make up-infra       # Start only infrastructure
make test           # Run test suite
make test-cov       # Tests with coverage report
make lint           # Lint Python code
make format         # Auto-format code
make db-shell       # Open PostgreSQL shell
make redis-cli      # Open Redis CLI
make logs           # Tail all service logs
make health         # Check backend health
```

---

## License

MIT License — See [LICENSE](LICENSE)

---

*Built with precision for institutional-grade trading intelligence.*
*NEXUS AI is for analysis and decision support only. Not financial advice.*
