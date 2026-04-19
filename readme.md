# 📡 IndianStockAI — Free AI Stock Analysis Dashboard for NSE & BSE

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nikhilkr16-ai-recommendation-indian-stock.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-llama3--70b-orange)](https://groq.com)
[![xAI Grok](https://img.shields.io/badge/xAI-Grok-black)](https://x.ai)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase)](https://supabase.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Cost](https://img.shields.io/badge/Cost-₹0%20Free-brightgreen)](https://indianstockai.streamlit.app)

> **Production-grade AI stock analysis platform for Indian markets — built at zero cost.**  
> Real-time NSE/BSE data · Grok AI signals · Nifty 50 heatmap · Options chain · Portfolio tracker

**[🚀 Live Demo →](https://nikhilkr16-ai-recommendation-indian-stock.streamlit.app)** &nbsp;|&nbsp; **[🌐 SEO Landing Page →](https://nikhilkr16.github.io/AI_RECOMMENDATION_INDIAN_STOCK/)**

---

## ✨ Features

| Feature | Description | Unique? |
|---|---|---|
| 🤖 **AI Trading Signals** | Grok (xAI) → Groq llama3 → Gemini fallback chain | ✅ Yes |
| 🗺️ **Nifty 50 Heatmap** | Sector-grouped treemap with live % change | ✅ Yes |
| 📉 **F&O Options Chain** | Live OI, PCR, Max Pain from NSE (no API key) | ✅ Yes |
| 🔍 **Stock Screener** | Filter by RSI, sector, SMA, 1D/1M change | Rare |
| 📰 **News Sentiment** | GDELT real-time sentiment per ticker | ✅ Yes |
| 💼 **Portfolio Tracker** | Live P&L with Supabase cloud storage | ✅ Yes |
| 📲 **WhatsApp Digest** | One-click shareable stock summary | ✅ Yes |
| 🌙 **Dark Mode** | Full dark theme toggle | — |
| 📈 **Technical Analysis** | RSI, MACD, Bollinger Bands, Stochastic | — |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              User (Browser)                     │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Streamlit Frontend (Python)             │
│  6 Tabs: Analysis │ Heatmap │ Screener │        │
│          News │ Portfolio │ F&O                 │
└──┬─────────────┬──────────┬──────────┬──────────┘
   │             │          │          │
┌──▼──┐    ┌────▼────┐ ┌───▼───┐ ┌───▼──────┐
│ xAI │    │  Groq   │ │Gemini │ │ yFinance │
│Grok │    │llama3   │ │ Flash │ │  NSELib  │
│(AI) │    │  (AI)   │ │ (AI)  │ │  (Data)  │
└─────┘    └─────────┘ └───────┘ └──────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│           External APIs (Free)                  │
│  NSE India (F&O) │ GDELT (News) │ Finnhub       │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Supabase (PostgreSQL)                   │
│         Portfolio persistent storage            │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| Frontend | Streamlit Community Cloud | Free |
| Primary AI | xAI Grok (reasoning model) | Free tier |
| Secondary AI | Groq llama3-70b-8192 | 14,400 req/day free |
| Fallback AI | Google Gemini 2.0 Flash | 15 req/min free |
| Stock Data | yFinance (NSE `.NS` / BSE `.BO`) | Free |
| F&O Data | NSE India API (unofficial) | Free |
| News Data | GDELT Project | Free |
| Database | Supabase (PostgreSQL) | 500MB free |
| SEO Page | GitHub Pages | Free |
| Analytics | Google Analytics 4 | Free |

**Total monthly cost: ₹0**

---

## ⚡ Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/nikhil-bitm/indianstockai.git
cd indianstockai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your free API keys in AdvanceStockAnalysis.py
#    - GROQ_API_KEY  → groq.com (free, no credit card)
#    - XAI_API_KEY   → console.x.ai (Grok)
#    - SUPABASE_URL / SUPABASE_KEY → supabase.com (free)

# 4. Run
streamlit run AdvanceStockAnalysis.py
```

---

## 📦 Requirements

```
streamlit
yfinance
pandas
numpy
plotly
requests
beautifulsoup4
streamlit-autorefresh
nselib
pandas-market-calendars
groq
openai
supabase
```

Install all:
```bash
pip install -r requirements.txt
```

---

## 📊 How It Works

### AI Signal Pipeline
```
Stock Symbol Input
       ↓
Technical Indicators (RSI, MACD, BB, Stochastic)
       ↓
Rule-Based Model → BUY / SELL / HOLD
       ↓
Grok AI (xAI) → BUY / SELL / HOLD + reason + confidence
       ↓  (fallback if Grok unavailable)
Groq llama3-70b → BUY / SELL / HOLD
       ↓  (fallback if Groq unavailable)
Gemini 2.0 Flash → BUY / SELL / HOLD
       ↓
Final Decision = Weighted consensus (higher confidence wins)
```

### F&O Options Chain
- Fetches live data from NSE India (no API key)
- Calculates **Put-Call Ratio (PCR)**: PCR > 1.2 = Bullish, < 0.8 = Bearish
- **Max Pain** strike — where options writers profit most at expiry
- OI buildup detection via change-in-OI charts

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. It does not constitute financial advice. Always consult a SEBI-registered financial advisor before making investment decisions. Past performance is not indicative of future results.

---

## 👤 Author

**Nikhil — BIT Mesra**  
Built as a placement portfolio project · ₹0 budget · 100% open source

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://linkedin.com/in/nikhil-kumar-0686851b0)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?logo=github)](https://github.com/nikhilkr16)
