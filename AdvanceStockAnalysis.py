import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import yfinance as yf
import warnings
import json
from nselib import capital_market
from nselib import derivatives
import pandas_market_calendars as mcal
import urllib.parse

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from openai import OpenAI as OpenAIClient
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False

try:
    from supabase import create_client, Client as SupabaseClient
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

warnings.filterwarnings('ignore')

# --- API Keys — loaded from .streamlit/secrets.toml (local) or Streamlit Cloud Secrets ---
def _secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return default

FINNHUB_API_KEY = _secret("FINNHUB_API_KEY")
GEMINI_API_KEY  = _secret("GEMINI_API_KEY")
GROQ_API_KEY    = _secret("GROQ_API_KEY")
XAI_API_KEY     = _secret("XAI_API_KEY")
SUPABASE_URL    = _secret("SUPABASE_URL")
SUPABASE_KEY    = _secret("SUPABASE_KEY")
XAI_MODEL = "grok-3"
model_name = "gemini-2.0-flash"

# Nifty 50 stocks for heatmap and screener
NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK",
    "INFY", "SBIN", "HINDUNILVR", "ITC", "LT",
    "KOTAKBANK", "BAJFINANCE", "HCLTECH", "MARUTI", "AXISBANK",
    "ASIANPAINT", "TITAN", "ULTRACEMCO", "WIPRO", "NESTLEIND",
    "POWERGRID", "NTPC", "SUNPHARMA", "TATACONSUM", "ONGC",
    "JSWSTEEL", "TATASTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA",
    "BAJAJFINSV", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "CIPLA",
    "M&M", "BRITANNIA", "SBILIFE", "TECHM", "BPCL",
    "APOLLOHOSP", "LTIM", "BAJAJ-AUTO", "UPL", "TATASTEEL"
]

NIFTY50_SECTORS = {
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy",
    "NTPC": "Energy", "POWERGRID": "Utilities", "COALINDIA": "Materials",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
    "TECHM": "IT", "LTIM": "IT",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance", "HDFCLIFE": "Finance",
    "SBILIFE": "Finance",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "MARUTI": "Auto", "HEROMOTOCO": "Auto",
    "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto", "M&M": "Auto",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "DIVISLAB": "Pharma",
    "CIPLA": "Pharma", "APOLLOHOSP": "Pharma",
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "ASIANPAINT": "Paints", "TITAN": "Consumer", "ULTRACEMCO": "Cement",
    "GRASIM": "Cement", "LT": "Infra", "ADANIPORTS": "Infra",
    "ADANIENT": "Conglomerate", "BHARTIARTL": "Telecom", "UPL": "Agri"
}

# --- Safe Imports with Fallback ---
try:
    from nselib import capital_market, derivatives
    NSELIB_AVAILABLE = True
except ImportError:
    NSELIB_AVAILABLE = False
    st.warning("NSELib not available. Using alternative data sources.")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Indian Stock Insight Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Styling ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .prediction-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .buy-signal {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .sell-signal {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    .hold-signal {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    .error-box {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }
    .transaction-log {
        max-height: 300px;
        overflow-y: auto;
        padding: 10px;
        background-color: #f9f9f9;
        border-radius: 5px;
        border: 1px solid #eee;
    }
    .gemini-box {
        background: #e0f7fa;
        color: #006064;
        border: 1px solid #b2ebf2;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .groq-box {
        background: #f3e5f5;
        color: #4a148c;
        border: 1px solid #ce93d8;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .grok-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #a5b4fc;
        border: 1px solid #6366f1;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
        box-shadow: 0 0 12px rgba(99,102,241,0.25);
    }
    .whatsapp-btn {
        background: #25D366;
        color: white;
        border: none;
        padding: 0.6rem 1.5rem;
        border-radius: 8px;
        font-size: 1rem;
        font-weight: bold;
        cursor: pointer;
        text-decoration: none;
        display: inline-block;
        margin-top: 0.5rem;
    }
    .whatsapp-btn:hover { background: #128C7E; color: white; }
    .screener-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 0.8rem;
        border-left: 4px solid #667eea;
        margin-bottom: 0.5rem;
    }
    .final-decision-box {
        background: #e8f5e9;
        color: #2e7d32;
        border: 1px solid #c8e6c9;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.5em;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .portfolio-gain { color: #16a34a; font-weight: 700; }
    .portfolio-loss { color: #dc2626; font-weight: 700; }
    .portfolio-summary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 1.5rem; border-radius: 12px;
        text-align: center; margin-bottom: 1.5rem;
    }
    .holding-card {
        background: #ceeddc; border-radius: 10px; padding: 1rem;
        border-left: 5px solid #667eea; margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if 'transaction_log' not in st.session_state:
    st.session_state.transaction_log = []
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []   # local fallback when Supabase not configured

# --- Sidebar Configuration ---
st.sidebar.title("📡 Dashboard Controls")
st.sidebar.markdown("---")

# --- Dark Mode Toggle ---
dark = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode_toggle")
st.session_state.dark_mode = dark

if dark:
    st.markdown("""
    <style>
        .stApp, .main, section.main { background-color: #0f172a !important; color: #e2e8f0 !important; }
        .stApp * { color: #e2e8f0; }
        .stSidebar, [data-testid="stSidebar"] { background-color: #1e293b !important; }
        .stSidebar * { color: #e2e8f0 !important; }
        .stTextInput > div > div > input,
        .stSelectbox > div > div,
        .stNumberInput > div > div > input { background-color: #1e293b !important; color: #e2e8f0 !important; border-color: #334155 !important; }
        .stDataFrame, [data-testid="stDataFrame"] { background-color: #1e293b !important; }
        .stMetric { background-color: #1e293b !important; border-radius: 8px; padding: 0.5rem; }
        .metric-container { background: #1e293b !important; border-left-color: #818cf8 !important; }
        .main-header { background: linear-gradient(90deg, #1e1b4b 0%, #312e81 100%) !important; }
        .prediction-box.buy-signal { background: #052e16 !important; color: #86efac !important; border-color: #166534 !important; }
        .prediction-box.sell-signal { background: #450a0a !important; color: #fca5a5 !important; border-color: #991b1b !important; }
        .prediction-box.hold-signal { background: #1c1917 !important; color: #fcd34d !important; border-color: #92400e !important; }
        .final-decision-box { background: #052e16 !important; color: #86efac !important; border-color: #166534 !important; }
        .gemini-box { background: #0c4a6e !important; color: #7dd3fc !important; border-color: #0369a1 !important; }
        .groq-box { background: #2e1065 !important; color: #d8b4fe !important; border-color: #7c3aed !important; }
        .error-box { background: #450a0a !important; color: #fca5a5 !important; }
        .screener-card { background: #1e293b !important; border-left-color: #818cf8 !important; }
        div[data-testid="stExpander"] { background-color: #1e293b !important; border-color: #334155 !important; }
        .stTabs [data-baseweb="tab-list"] { background-color: #1e293b !important; }
        .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; }
        .stTabs [aria-selected="true"] { color: #818cf8 !important; border-bottom-color: #818cf8 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Main Header ---
st.markdown("""
<div class="main-header">
    <h1>📡 Indian Stock Market Insight Dashboard</h1>
    <p>Real-time Analysis | Smart Predictions | Comprehensive Insights</p>
</div>
""", unsafe_allow_html=True)

# --- Error Handling Decorator ---
def safe_execute(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            st.error(f"Network or API request failed: {e}")
            return None, f"Network or API request failed: {e}"
        except KeyError as e:
            st.error(f"Data processing error: Missing key in response - {e}")
            return None, f"Data processing error: Missing key in response - {e}"
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return None, f"An unexpected error occurred: {e}"
    return wrapper

# --- Stock Symbol Validation with multiple sources ---
def validate_stock_symbol(symbol):
    """Validate if the stock symbol exists and is tradeable on Yahoo Finance or Finnhub."""
    
    # Try Yahoo Finance first (most reliable for Indian stocks)
    ticker_variants = [f"{symbol}.NS", f"{symbol}.BO", symbol]
    for ticker in ticker_variants:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return True, ticker
        except Exception:
            continue
    
    # Fallback to Finnhub API
    if FINNHUB_API_KEY:
        url = f"https://finnhub.io/api/v1/search?q={symbol}&token={FINNHUB_API_KEY}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if 'result' in data and any(item['symbol'].upper() == f"NSE:{symbol.upper()}" or item['symbol'].upper() == f"BSE:{symbol.upper()}" for item in data['result']):
                return True, f"NSE:{symbol}"
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            pass
            
    return False, f"Stock symbol '{symbol}' not found. Please check the symbol and try again."

# --- Improved Data Fetching Functions ---
@st.cache_data(ttl=300) # Cache for 5 minutes
@safe_execute
def get_realtime_stock_data(symbol):
    """Fetch real-time stock data using multiple sources"""

    is_valid, ticker_or_error = validate_stock_symbol(symbol)
    if not is_valid:
        return None, ticker_or_error
    
    # Try Yahoo Finance
    try:
        if ".NS" in ticker_or_error or ".BO" in ticker_or_error or "." not in ticker_or_error:
            stock = yf.Ticker(ticker_or_error)
            info = stock.info
            hist = stock.history(period="1y")
            
            if not hist.empty and info:
                latest_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else latest_price
                volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0
                day_high = hist['High'].iloc[-1]
                day_low = hist['Low'].iloc[-1]
                
                return {
                    'symbol': symbol,
                    'price': latest_price,
                    'prev_close': prev_close,
                    'volume': volume,
                    'day_high': day_high,
                    'day_low': day_low,
                    'historical': hist,
                    'info': info,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data_source': 'Yahoo Finance'
                }, None
    except Exception as e:
        st.warning(f"Yahoo Finance data fetch failed. Trying Finnhub. Details: {e}")

    # Fallback to Finnhub
    try:
        finnhub_symbol = f"NSE:{symbol}"
        url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and 'c' in data and data['c'] != 0:
            current_price = data['c']
            prev_close = data.get('pc', current_price)
            
            # Generate synthetic historical data for analysis since Finnhub's quote endpoint is limited
            dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
            np.random.seed(hash(symbol) % 1000)
            prices = [current_price]
            for _ in range(99):
                change = np.random.normal(0, 0.01)
                prev_price_calc = prices[-1] / (1 + change)
                prices.append(max(0.01, prev_price_calc))
            prices.reverse()
            
            hist = pd.DataFrame({
                'Close': prices,
                'Open': [p * np.random.uniform(0.99, 1.01) for p in prices],
                'High': [p * np.random.uniform(1.00, 1.02) for p in prices],
                'Low': [p * np.random.uniform(0.98, 1.00) for p in prices],
                'Volume': np.random.randint(1000000, 10000000, 100)
            }, index=dates)

            # Ensure the last day's data matches the real-time quote
            hist.loc[hist.index[-1], 'Close'] = current_price
            hist.loc[hist.index[-1], 'High'] = max(current_price, hist.loc[hist.index[-1], 'High'])
            hist.loc[hist.index[-1], 'Low'] = min(current_price, hist.loc[hist.index[-1], 'Low'])

            return {
                'symbol': symbol,
                'price': current_price,
                'prev_close': prev_close,
                'volume': "N/A",
                'day_high': hist['High'].iloc[-1],
                'day_low': hist['Low'].iloc[-1],
                'historical': hist,
                'info': {},
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': 'Finnhub (Simulated Historical)'
            }, None
    except Exception as e:
        st.warning(f"Finnhub data fetch failed. Details: {e}")
        
    return None, "Unable to fetch live or historical data from all sources. Please try again later."


# --- Advanced Technical Analysis with Real Mathematics ---
def calculate_advanced_technical_indicators(data):
    """Calculate comprehensive technical indicators using proven mathematical formulas"""
    if data is None or len(data) < 50:
        st.warning("Not enough data to calculate all technical indicators. Need at least 50 data points.")
        return pd.DataFrame()
    
    df = data.copy()
    
    # Basic Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    if len(df) >= 200:
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # Exponential Moving Averages
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    # Stochastic Oscillator
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['%K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    df['%D'] = df['%K'].rolling(window=3).mean()
    
    # Volume indicators
    if 'Volume' in df.columns and not df['Volume'].isnull().all():
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    else:
        df['Volume_SMA'] = np.nan

    return df.dropna()

# --- Rule-based Trading Signal Generator ---
def generate_rule_based_trading_signal(data):
    """Generate trading signals using a weighted rule-based system."""
    
    if data.empty or len(data) < 50:
        return "HOLD", "Insufficient data for rule-based analysis.", 0.5

    latest = data.iloc[-1]
    
    buy_score = 0
    sell_score = 0
    reasons = []

    # 1. Moving Averages Crossover (25 points)
    # Golden Cross (20-day SMA crosses above 50-day SMA)
    if latest.get('SMA_20') > latest.get('SMA_50') and data.iloc[-2].get('SMA_20') <= data.iloc[-2].get('SMA_50'):
        buy_score += 25
        reasons.append("Golden Cross (SMA 20/50)")
    # Death Cross (20-day SMA crosses below 50-day SMA)
    if latest.get('SMA_20') < latest.get('SMA_50') and data.iloc[-2].get('SMA_20') >= data.iloc[-2].get('SMA_50'):
        sell_score += 25
        reasons.append("Death Cross (SMA 20/50)")

    # 2. RSI (20 points)
    rsi = latest.get('RSI', 50)
    if rsi < 30 and latest['Close'] > latest.get('Low', latest['Close']):
        buy_score += 20
        reasons.append(f"RSI oversold ({rsi:.2f})")
    elif rsi > 70 and latest['Close'] < latest.get('High', latest['Close']):
        sell_score += 20
        reasons.append(f"RSI overbought ({rsi:.2f})")

    # 3. MACD Crossover (20 points)
    if latest.get('MACD', 0) > latest.get('MACD_Signal', 0) and data.iloc[-2].get('MACD') <= data.iloc[-2].get('MACD_Signal'):
        buy_score += 20
        reasons.append("MACD bullish crossover")
    if latest.get('MACD', 0) < latest.get('MACD_Signal', 0) and data.iloc[-2].get('MACD') >= data.iloc[-2].get('MACD_Signal'):
        sell_score += 20
        reasons.append("MACD bearish crossover")
    
    # 4. Price vs Moving Averages (10 points)
    if latest['Close'] > latest.get('SMA_20', latest['Close']) and latest['Close'] > latest.get('SMA_50', latest['Close']):
        buy_score += 10
        reasons.append("Price above key MAs")
    elif latest['Close'] < latest.get('SMA_20', latest['Close']) and latest['Close'] < latest.get('SMA_50', latest['Close']):
        sell_score += 10
        reasons.append("Price below key MAs")

    # 5. Bollinger Bands (10 points)
    if latest['Close'] < latest.get('BB_Lower', latest['Close']):
        buy_score += 10
        reasons.append("Price below Bollinger Lower Band")
    elif latest['Close'] > latest.get('BB_Upper', latest['Close']):
        sell_score += 10
        reasons.append("Price above Bollinger Upper Band")

    # 6. Stochastic Oscillator (5 points)
    k_percent = latest.get('%K', 50)
    d_percent = latest.get('%D', 50)
    if k_percent < 20 and d_percent < 20 and latest['Close'] > latest['Low']:
        buy_score += 5
        reasons.append("Stochastic oversold")
    elif k_percent > 80 and d_percent > 80 and latest['Close'] < latest['High']:
        sell_score += 5
        reasons.append("Stochastic overbought")

    # Calculate final signal and confidence
    total_score = buy_score + sell_score
    if total_score == 0:
        return "HOLD", "No clear signals detected.", 0.5
    
    if buy_score > sell_score:
        signal = "BUY"
        confidence = min(buy_score / total_score, 1.0)
        reason = f"Bullish signals detected: {', '.join(reasons[:3])}"
    elif sell_score > buy_score:
        signal = "SELL"
        confidence = min(sell_score / total_score, 1.0)
        reason = f"Bearish signals detected: {', '.join(reasons[:3])}"
    else: # Equal scores
        signal = "HOLD"
        confidence = 0.5
        reason = "Mixed signals or weak consensus. Wait for a clearer trend."

    return signal, reason, confidence

# --- Gemini AI Recommendation Function ---
@st.cache_data(ttl=300) # Cache Gemini responses for 5 minutes
def get_gemini_recommendation(symbol, current_price, analyzed_data):
    """
    Gets a stock recommendation from the Gemini AI model based on current price and technical indicators.
    Returns a tuple: (signal, reason, confidence) or (None, error_message, None)
    """
    if analyzed_data.empty:
        return "HOLD", "Insufficient data for Gemini analysis.", 0.5

    latest = analyzed_data.iloc[-1]

    # Prepare detailed input for Gemini
    prompt_text = f"""
    Analyze the stock {symbol} with the following latest data and provide a trading recommendation (BUY, SELL, or HOLD).
    Current Price: ₹{current_price:.2f}

    Technical Indicators:
    - Last Close Price: ₹{latest.get('Close', 'N/A'):.2f}
    - SMA 20: ₹{latest.get('SMA_20', 'N/A'):.2f}
    - SMA 50: ₹{latest.get('SMA_50', 'N/A'):.2f}
    - RSI: {latest.get('RSI', 'N/A'):.2f}
    - MACD: {latest.get('MACD', 'N/A'):.4f}
    - MACD Signal: {latest.get('MACD_Signal', 'N/A'):.4f}
    - Bollinger Bands (Upper): ₹{latest.get('BB_Upper', 'N/A'):.2f}
    - Bollinger Bands (Middle): ₹{latest.get('BB_Middle', 'N/A'):.2f}
    - Bollinger Bands (Lower): ₹{latest.get('BB_Lower', 'N/A'):.2f}
    - Stochastic %K: {latest.get('%K', 'N/A'):.2f}
    - Stochastic %D: {latest.get('%D', 'N/A'):.2f}

    Consider these factors:
    - RSI below 30 suggests oversold, above 70 suggests overbought.
    - MACD crossover above signal line is bullish, below is bearish.
    - Price above moving averages (SMA 20, 50) is bullish, below is bearish.
    - Price near Bollinger Lower Band is bullish, near Upper Band is bearish.
    - Stochastic %K and %D below 20 suggest oversold, above 80 suggest overbought.

    Provide your recommendation as a JSON object with the following keys:
    "signal": "BUY" | "SELL" | "HOLD"
    "reason": "A brief explanation for the recommendation."
    "confidence": 0.0 to 1.0 (float, indicating confidence in the recommendation)
    """

    chat_history = []
    # FIX: Changed .push to .append for Python list
    chat_history.append({ "role": "user", "parts": [{ "text": prompt_text }] });
    
    payload = {
        "contents": chat_history,
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "signal": {"type": "STRING", "enum": ["BUY", "SELL", "HOLD"]},
                    "reason": {"type": "STRING"},
                    "confidence": {"type": "NUMBER", "format": "float"}
                },
                "required": ["signal", "reason", "confidence"]
            }
        }
    }
    
    # Using the provided API call structure
    
    apiKey = GEMINI_API_KEY
    # url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={apiKey}"
    # url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={apiKey}"
    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={apiKey}"



    try:
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload, timeout=20)

        if response.status_code == 429:
            return "HOLD", "Gemini AI: API rate limit reached. Please wait a moment and try again.", 0.5
        if response.status_code == 404:
            return "HOLD", "Gemini AI: The selected model is unavailable. Please check your API key and model name.", 0.5

        response.raise_for_status()
        
        result = response.json()
        
        if result.get('candidates') and len(result['candidates']) > 0 and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts') and len(result['candidates'][0]['content']['parts']) > 0:
            json_text = result['candidates'][0]['content']['parts'][0]['text']
            gemini_output = json.loads(json_text)
            
            signal = gemini_output.get('signal', 'HOLD').upper()
            reason = gemini_output.get('reason', 'No specific reason provided by AI.')
            confidence = float(gemini_output.get('confidence', 0.5))
            
            return signal, reason, confidence
        else:
            return "HOLD", "Gemini AI: No valid response from the model.", 0.5
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        if status == 429:
            return "HOLD", "Gemini AI: API rate limit reached. Please wait a moment and try again.", 0.5
        if status == 403:
            return "HOLD", "Gemini AI: Access denied. Please check your API key permissions.", 0.5
        return "HOLD", f"Gemini AI: HTTP error {status}. Please try again later.", 0.5
    except requests.exceptions.RequestException as e:
        return "HOLD", "Gemini AI: Network error. Please check your internet connection.", 0.5
    except json.JSONDecodeError:
        return "HOLD", "Gemini AI: Could not parse JSON response.", 0.5
    except Exception as e:
        return "HOLD", f"Gemini AI: An unexpected error occurred: {e}", 0.5


# --- Grok AI (xAI) Recommendation Function — Top Priority ---
@st.cache_data(ttl=300)
def get_grok_recommendation(symbol, current_price, analyzed_data):
    """Primary AI: xAI Grok — fast reasoning model for Indian stock analysis."""
    if not OPENAI_SDK_AVAILABLE:
        return None, "openai SDK not installed. Run: pip install openai", None
    if not XAI_API_KEY:
        return None, "xAI API key not set.", None
    if analyzed_data.empty:
        return "HOLD", "Insufficient data for Grok analysis.", 0.5

    latest = analyzed_data.iloc[-1]
    prompt = f"""You are an expert quantitative analyst specialising in Indian stock markets (NSE/BSE).
Analyse {symbol} using the technical data below and give a precise trading recommendation.

Current Price: ₹{current_price:.2f}
Technical Indicators:
- RSI (14): {latest.get('RSI', 'N/A'):.2f}
- MACD: {latest.get('MACD', 'N/A'):.4f} | MACD Signal: {latest.get('MACD_Signal', 'N/A'):.4f}
- SMA 20: ₹{latest.get('SMA_20', 'N/A'):.2f} | SMA 50: ₹{latest.get('SMA_50', 'N/A'):.2f}
- Bollinger Upper: ₹{latest.get('BB_Upper', 'N/A'):.2f} | Lower: ₹{latest.get('BB_Lower', 'N/A'):.2f}
- Stochastic %K: {latest.get('%K', 'N/A'):.2f} | %D: {latest.get('%D', 'N/A'):.2f}

Rules:
- RSI < 30 = oversold (bullish), RSI > 70 = overbought (bearish)
- MACD above signal line = bullish momentum
- Price above SMA 20 & SMA 50 = bullish trend
- Price below BB Lower = potential reversal up

Reply ONLY with a JSON object — no extra text:
{{"signal": "BUY" | "SELL" | "HOLD", "reason": "<one concise sentence>", "confidence": <0.0-1.0>}}"""

    try:
        client = OpenAIClient(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model=XAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise Indian stock market analyst. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        output = json.loads(content)
        signal = output.get("signal", "HOLD").upper()
        reason = output.get("reason", "No reason provided.")
        confidence = float(output.get("confidence", 0.5))
        return signal, reason, confidence
    except json.JSONDecodeError:
        return "HOLD", "Grok AI: Could not parse response as JSON.", 0.5
    except Exception as e:
        err = str(e)
        if "429" in err or "rate" in err.lower():
            return None, "Grok AI: Rate limit reached. Falling back to next AI.", None
        if "credits" in err.lower() or "licenses" in err.lower():
            return None, "Grok AI: No credits on xAI account. Add credits at console.x.ai — falling back.", None
        if "401" in err:
            return None, "Grok AI: Invalid API key — falling back.", None
        if "403" in err:
            return None, "Grok AI: Access denied (no credits/license) — falling back.", None
        return None, f"Grok AI unavailable — falling back. ({err[:80]})", None


# --- Groq AI Recommendation Function (Secondary AI) ---
@st.cache_data(ttl=300)
def get_groq_recommendation(symbol, current_price, analyzed_data):
    """Primary AI: Groq llama3-70b — 14,400 free requests/day."""
    if not GROQ_AVAILABLE:
        return None, "Groq library not installed. Run: pip install groq", None
    if not GROQ_API_KEY:
        return None, "Groq API key not set. Get a free key at groq.com", None
    if analyzed_data.empty:
        return "HOLD", "Insufficient data for Groq analysis.", 0.5

    latest = analyzed_data.iloc[-1]
    prompt = f"""You are a professional stock analyst for Indian markets (NSE/BSE).
Analyze {symbol} and give a trading recommendation.

Current Price: ₹{current_price:.2f}
Technical Indicators:
- RSI: {latest.get('RSI', 'N/A'):.2f}
- MACD: {latest.get('MACD', 'N/A'):.4f} | Signal: {latest.get('MACD_Signal', 'N/A'):.4f}
- SMA 20: ₹{latest.get('SMA_20', 'N/A'):.2f} | SMA 50: ₹{latest.get('SMA_50', 'N/A'):.2f}
- Bollinger Upper: ₹{latest.get('BB_Upper', 'N/A'):.2f} | Lower: ₹{latest.get('BB_Lower', 'N/A'):.2f}
- Stochastic %K: {latest.get('%K', 'N/A'):.2f} | %D: {latest.get('%D', 'N/A'):.2f}

Return ONLY a JSON object with keys: signal (BUY/SELL/HOLD), reason (1 sentence), confidence (0.0-1.0)
Example: {{"signal": "BUY", "reason": "RSI oversold with MACD bullish crossover.", "confidence": 0.72}}"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200,
        )
        content = response.choices[0].message.content
        output = json.loads(content)
        signal = output.get("signal", "HOLD").upper()
        reason = output.get("reason", "No reason provided.")
        confidence = float(output.get("confidence", 0.5))
        return signal, reason, confidence
    except Exception as e:
        return None, f"Groq AI error: {e}", None


# --- Nifty 50 Heatmap ---
@st.cache_data(ttl=600)
def fetch_nifty50_heatmap_data():
    """Fetch 1-day % change for all Nifty 50 stocks."""
    results = []
    for sym in NIFTY50_SYMBOLS:
        try:
            ticker = yf.Ticker(f"{sym}.NS")
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                chg = ((curr - prev) / prev) * 100
                results.append({
                    "Symbol": sym,
                    "Price": round(curr, 2),
                    "Change%": round(chg, 2),
                    "Sector": NIFTY50_SECTORS.get(sym, "Other")
                })
        except Exception:
            continue
    return pd.DataFrame(results)


def show_nifty50_heatmap():
    st.subheader("🗺️ Nifty 50 Sector Heatmap")
    st.caption("Color shows 1-day % change. Green = up, Red = down. Data refreshes every 10 minutes.")
    with st.spinner("Loading Nifty 50 data..."):
        df = fetch_nifty50_heatmap_data()

    if df.empty:
        st.warning("Could not load Nifty 50 data. Please try again.")
        return

    col1, col2, col3 = st.columns(3)
    gainers = df[df["Change%"] > 0].shape[0]
    losers = df[df["Change%"] < 0].shape[0]
    col1.metric("Gainers", gainers, delta=None)
    col2.metric("Losers", losers, delta=None)
    col3.metric("Avg Change", f"{df['Change%'].mean():.2f}%")

    fig = px.treemap(
        df,
        path=["Sector", "Symbol"],
        values=df["Change%"].abs() + 0.5,
        color="Change%",
        color_continuous_scale=["#c0392b", "#e74c3c", "#f8f9fa", "#2ecc71", "#27ae60"],
        color_continuous_midpoint=0,
        custom_data=["Symbol", "Price", "Change%"],
        title="Nifty 50 — Sector-wise Performance Heatmap"
    )
    fig.update_traces(
        texttemplate="<b>%{customdata[0]}</b><br>%{customdata[2]:.2f}%",
        textfont_size=13
    )
    fig.update_layout(height=550, margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Full Data Table"):
        df_sorted = df.sort_values("Change%", ascending=False)
        st.dataframe(
            df_sorted.style.background_gradient(subset=["Change%"], cmap="RdYlGn", vmin=-3, vmax=3),
            use_container_width=True
        )


# --- Stock Screener ---
@st.cache_data(ttl=600)
def fetch_screener_data():
    """Fetch key metrics for all Nifty 50 stocks for screening."""
    results = []
    for sym in NIFTY50_SYMBOLS:
        try:
            ticker = yf.Ticker(f"{sym}.NS")
            hist = ticker.history(period="3mo")
            if len(hist) < 50:
                continue
            close = hist["Close"]
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]
            curr = close.iloc[-1]
            prev = close.iloc[-2]
            chg1d = ((curr - prev) / prev) * 100
            chg1m = ((curr - close.iloc[-21]) / close.iloc[-21]) * 100 if len(close) > 21 else 0
            results.append({
                "Symbol": sym,
                "Sector": NIFTY50_SECTORS.get(sym, "Other"),
                "Price (₹)": round(curr, 2),
                "1D %": round(chg1d, 2),
                "1M %": round(chg1m, 2),
                "RSI": round(rsi, 1),
                "Above SMA20": curr > sma20,
                "Above SMA50": curr > sma50,
            })
        except Exception:
            continue
    return pd.DataFrame(results)


def show_stock_screener():
    st.subheader("🔍 Stock Screener — Nifty 50")

    col1, col2, col3, col4 = st.columns(4)
    sector_filter = col1.multiselect(
        "Sector", options=sorted(set(NIFTY50_SECTORS.values())), default=[]
    )
    rsi_min, rsi_max = col2.slider("RSI Range", 0, 100, (20, 80))
    change_min = col3.number_input("Min 1D Change %", value=-10.0, step=0.5)
    change_max = col4.number_input("Max 1D Change %", value=10.0, step=0.5)

    above_sma20 = st.checkbox("Only stocks above SMA 20")
    above_sma50 = st.checkbox("Only stocks above SMA 50")

    with st.spinner("Screening Nifty 50 stocks..."):
        df = fetch_screener_data()

    if df.empty:
        st.warning("Could not fetch screener data.")
        return

    filtered = df.copy()
    if sector_filter:
        filtered = filtered[filtered["Sector"].isin(sector_filter)]
    filtered = filtered[
        (filtered["RSI"] >= rsi_min) & (filtered["RSI"] <= rsi_max) &
        (filtered["1D %"] >= change_min) & (filtered["1D %"] <= change_max)
    ]
    if above_sma20:
        filtered = filtered[filtered["Above SMA20"] == True]
    if above_sma50:
        filtered = filtered[filtered["Above SMA50"] == True]

    st.markdown(f"**{len(filtered)} stocks match your criteria** (out of {len(df)} screened)")

    if not filtered.empty:
        display_df = filtered.drop(columns=["Above SMA20", "Above SMA50"]).reset_index(drop=True)
        st.dataframe(
            display_df.style
                .background_gradient(subset=["1D %", "1M %"], cmap="RdYlGn", vmin=-5, vmax=5)
                .background_gradient(subset=["RSI"], cmap="RdYlGn", vmin=30, vmax=70),
            use_container_width=True
        )
    else:
        st.info("No stocks match the selected filters.")


# --- WhatsApp Daily Digest ---
def generate_whatsapp_digest(symbol, price, change_pct, signal, reason, rsi, sma20, sma50):
    """Generate a WhatsApp-ready plain text market digest."""
    direction = "📈" if change_pct >= 0 else "📉"
    signal_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(signal, "⚪")
    trend = "above" if price > sma20 else "below"
    date_str = datetime.now().strftime("%d %b %Y")

    text = f"""🇮🇳 *IndianStockAI Daily Digest* — {date_str}

*Stock:* {symbol}
*Price:* ₹{price:.2f}  {direction} {change_pct:+.2f}%

{signal_emoji} *AI Signal: {signal}*
_{reason}_

📊 *Key Indicators:*
• RSI: {rsi:.1f} {"(Oversold)" if rsi < 30 else "(Overbought)" if rsi > 70 else "(Neutral)"}
• Price is {trend} SMA 20 (₹{sma20:.2f})
• SMA 50: ₹{sma50:.2f}

⚠️ _For educational purposes only. Not financial advice._
🔗 indianstockai.streamlit.app"""
    return text


def show_whatsapp_digest(stock_data, analyzed_data, ai_signal, ai_reason):
    st.subheader("📲 Share on WhatsApp")
    if analyzed_data.empty:
        st.info("Analyse a stock first to generate a digest.")
        return

    latest = analyzed_data.iloc[-1]
    price = stock_data["price"]
    prev = stock_data["prev_close"]
    chg = ((price - prev) / prev) * 100 if prev else 0
    rsi = latest.get("RSI", 50)
    sma20 = latest.get("SMA_20", price)
    sma50 = latest.get("SMA_50", price)

    digest = generate_whatsapp_digest(
        stock_data["symbol"], price, chg, ai_signal, ai_reason, rsi, sma20, sma50
    )

    st.code(digest, language=None)
    encoded = urllib.parse.quote(digest)
    wa_url = f"https://wa.me/?text={encoded}"
    st.markdown(
        f'<a href="{wa_url}" target="_blank" class="whatsapp-btn">📤 Share on WhatsApp</a>',
        unsafe_allow_html=True
    )


# --- News Sentiment via GDELT ---
@st.cache_data(ttl=900)  # Cache 15 min
def fetch_gdelt_news(query, max_articles=8):
    """Fetch recent news articles from GDELT for a given query."""
    try:
        encoded = urllib.parse.quote(f"{query} stock NSE India")
        url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={encoded}&mode=artlist&maxrecords={max_articles}"
            f"&format=json&timespan=3d&sort=DateDesc"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception:
        return []


def score_sentiment(title: str, desc: str) -> tuple[str, float]:
    """Simple keyword-based sentiment score on headline + description."""
    text = (title + " " + desc).lower()
    positive = ["surge", "rally", "gain", "profit", "beat", "growth", "rise",
                "record", "strong", "upgrade", "bullish", "buy", "outperform",
                "dividend", "breakout", "jumps", "soars"]
    negative = ["fall", "drop", "loss", "decline", "crash", "weak", "sell",
                "downgrade", "bearish", "miss", "concern", "risk", "cut",
                "below", "slump", "tumble", "plunge", "fraud", "probe"]
    pos = sum(1 for w in positive if w in text)
    neg = sum(1 for w in negative if w in text)
    total = pos + neg
    if total == 0:
        return "Neutral", 0.5
    score = pos / total
    if score >= 0.6:
        return "Positive", round(score, 2)
    elif score <= 0.4:
        return "Negative", round(1 - score, 2)
    return "Neutral", 0.5


def show_news_sentiment(symbol):
    st.subheader(f"📰 News Sentiment — {symbol}")
    st.caption("Source: GDELT Project (free, real-time global news). Last 3 days.")

    with st.spinner(f"Fetching latest news for {symbol}..."):
        articles = fetch_gdelt_news(symbol)

    if not articles:
        st.info("No recent news found via GDELT. Try a broader symbol name (e.g., 'Reliance' instead of 'RELIANCE').")
        return

    sentiments = []
    for art in articles:
        title = art.get("title", "No title")
        url_art = art.get("url", "#")
        src = art.get("domain", "Unknown source")
        date = art.get("seendate", "")[:8]
        if date:
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        desc = art.get("socialimage", "") + " " + title
        label, score = score_sentiment(title, desc)
        sentiments.append({"label": label, "score": score})

        colour = {"Positive": "#16a34a", "Negative": "#dc2626", "Neutral": "#d97706"}.get(label, "#64748b")
        emoji = {"Positive": "🟢", "Negative": "🔴", "Neutral": "🟡"}.get(label, "⚪")
        st.markdown(
            f"<div style='padding:0.7rem;border-radius:8px;border-left:4px solid {colour};"
            f"background:{"#f0fdf4" if label=="Positive" else "#fef2f2" if label=="Negative" else "#fffbeb"};margin-bottom:0.5rem'>"
            f"<b>{emoji} {label}</b> &nbsp;·&nbsp; <small>{src} · {date}</small><br>"
            f"<a href='{url_art}' target='_blank' style='color:#1d4ed8;font-size:0.92rem'>{title}</a>"
            f"</div>",
            unsafe_allow_html=True
        )

    # Aggregate sentiment bar
    st.markdown("#### Overall Sentiment Summary")
    pos_c = sum(1 for s in sentiments if s["label"] == "Positive")
    neg_c = sum(1 for s in sentiments if s["label"] == "Negative")
    neu_c = sum(1 for s in sentiments if s["label"] == "Neutral")
    total = len(sentiments) or 1
    avg_score = sum(s["score"] for s in sentiments) / total

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🟢 Positive", pos_c)
    col2.metric("🔴 Negative", neg_c)
    col3.metric("🟡 Neutral", neu_c)
    overall = "Bullish 📈" if avg_score > 0.55 else "Bearish 📉" if avg_score < 0.45 else "Mixed ↔️"
    col4.metric("Overall", overall)

    fig = px.bar(
        x=["Positive", "Neutral", "Negative"],
        y=[pos_c, neu_c, neg_c],
        color=["Positive", "Neutral", "Negative"],
        color_discrete_map={"Positive": "#16a34a", "Neutral": "#d97706", "Negative": "#dc2626"},
        labels={"x": "Sentiment", "y": "Articles"},
        title=f"News Sentiment Distribution — {symbol} (last 3 days)"
    )
    fig.update_layout(showlegend=False, height=300, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


# --- Enhanced Charting Functions ---
def create_comprehensive_chart(data, symbol):
    """Create a comprehensive technical analysis chart"""
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="No chart data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.2, 0.15, 0.15],
        subplot_titles=('Price & Moving Averages', 'Bollinger Bands', 'RSI', 'MACD')
    )
    
    # Main price chart with candlesticks
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="Price",
        increasing_line_color='green',
        decreasing_line_color='red'
    ), row=1, col=1)
    
    if 'SMA_20' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], mode='lines', name='SMA 20', line=dict(color='orange', width=2)), row=1, col=1)
    if 'SMA_50' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_50'], mode='lines', name='SMA 50', line=dict(color='blue', width=2)), row=1, col=1)
    if 'SMA_200' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_200'], mode='lines', name='SMA 200', line=dict(color='red', width=2)), row=1, col=1)
    
    # Bollinger Bands
    if all(col in data.columns for col in ['BB_Upper', 'BB_Middle', 'BB_Lower']):
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='gray', width=1), showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Middle'], mode='lines', name='BB Middle', line=dict(color='darkgray', width=1), showlegend=True), row=2, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], mode='lines', name='BB Lower', line=dict(color='gray', width=1), fill='tonexty', fillcolor='rgba(128,128,128,0.1)', showlegend=False), row=2, col=1)
    
    # RSI
    if 'RSI' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], mode='lines', name='RSI', line=dict(color='purple', width=2)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
    
    # MACD
    if 'MACD' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['MACD'], mode='lines', name='MACD', line=dict(color='blue', width=2)), row=4, col=1)
        if 'MACD_Signal' in data.columns:
            fig.add_trace(go.Scatter(x=data.index, y=data['MACD_Signal'], mode='lines', name='Signal', line=dict(color='red', width=2)), row=4, col=1)
    
    fig.update_layout(title=f'{symbol} - Comprehensive Technical Analysis', xaxis_rangeslider_visible=False, height=800, showlegend=True, template='plotly_white')
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Bollinger", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)
    fig.update_yaxes(title_text="MACD", row=4, col=1)
    
    return fig


# --- Trading Functions ---
def buy_stock(symbol, quantity, price):
    st.session_state.transaction_log.append({
        'action': 'BUY',
        'symbol': symbol,
        'quantity': quantity,
        'price': price,
        'total': quantity * price,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    st.success(f"✅ Bought {quantity} shares of {symbol} at ₹{price:.2f} each (Total: ₹{quantity * price:.2f})")

def sell_stock(symbol, quantity, price):
    st.session_state.transaction_log.append({
        'action': 'SELL',
        'symbol': symbol,
        'quantity': quantity,
        'price': price,
        'total': quantity * price,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    st.success(f"✅ Sold {quantity} shares of {symbol} at ₹{price:.2f} each (Total: ₹{quantity * price:.2f})")

def hold_stock(symbol):
    st.session_state.transaction_log.append({
        'action': 'HOLD',
        'symbol': symbol,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    st.info(f"📊 Holding position in {symbol}")

def get_nse_data(symbol, period="3M"):
    if not NSELIB_AVAILABLE: return None
    
    # Fetch data using nselib
    try:
        data = capital_market.price_volume_and_deliverable_position_data(symbol=symbol, period=period)
    except Exception as e:
        st.error(f"Error fetching data from NSELib for {symbol}: {e}")
        return None

    if data is None or data.empty:
        st.warning(f"No data available from NSELib for {symbol} for the period {period}.")
        return None
    
    data.columns = data.columns.str.strip()
    
    # Define column mapping
    column_mapping = {
        'Close Price': 'Close',
        'Open Price': 'Open',
        'High Price': 'High',
        'Low Price': 'Low',
        'Total Traded Quantity': 'Volume'
    }
    
    # Rename columns. Use errors='ignore' to avoid KeyError if a column doesn't exist
    data.rename(columns=column_mapping, inplace=True)

    # Ensure essential columns exist after renaming
    required_cols = ['Close', 'Open', 'High', 'Low', 'Volume']
    if not all(col in data.columns for col in required_cols):
        missing_cols = [col for col in required_cols if col not in data.columns]
        st.error(f"NSE Library data for {symbol} is missing required columns: {', '.join(missing_cols)}. Cannot proceed with analysis.")
        return None

    if 'Date' in data.columns:
        data['Date'] = pd.to_datetime(data['Date'])
        data.set_index('Date', inplace=True)
    else:
        st.error(f"NSE Library data for {symbol} is missing 'Date' column. Cannot set index.")
        return None

    # Ensure there's enough data after processing for calculations
    if data.empty or len(data) < 2: # Need at least 2 data points for prev_close calculation
        st.warning(f"NSE Library data for {symbol} is insufficient for full analysis after processing.")
        return None

    # Fetch current price from Finnhub or another source as NSELib only provides historical data
    finnhub_price, prev_close_finnhub = _get_realtime_price_finnhub(symbol)
    
    # Prioritize Finnhub price if available, otherwise use the last close from NSELib data
    price = finnhub_price if finnhub_price is not None else data['Close'].iloc[-1]
    
    # Prioritize Finnhub prev_close if available, otherwise use the second to last close from NSELib data
    prev_close = prev_close_finnhub if prev_close_finnhub is not None else (data['Close'].iloc[-2] if len(data) > 1 else price)

    return {
        'symbol': symbol,
        'price': price,
        'prev_close': prev_close,
        'historical': data,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': 'NSE Library'
    }

def _get_realtime_price_finnhub(symbol):
    """Helper function to get a single price point from Finnhub."""
    if not FINNHUB_API_KEY:
        return None, None
    try:
        finnhub_symbol = f"NSE:{symbol}"
        url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data and 'c' in data and data['c'] != 0:
            return data['c'], data.get('pc', data['c'])
    except Exception:
        return None, None
    return None, None

def create_demo_data(symbol):
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    np.random.seed(hash(symbol) % 1000)
    base_price = 100 + (hash(symbol) % 1000)
    returns = np.random.normal(0.001, 0.02, 100)
    prices = [base_price]
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    historical_data = pd.DataFrame({
        'Date': dates,
        'Open': [p * np.random.uniform(0.98, 1.02) for p in prices],
        'High': [p * np.random.uniform(1.00, 1.05) for p in prices],
        'Low': [p * np.random.uniform(0.95, 1.00) for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, 100)
    })
    historical_data.set_index('Date', inplace=True)
    return {
        'symbol': symbol,
        'price': prices[-1],
        'prev_close': prices[-2] if len(prices) > 1 else prices[-1],
        'historical': historical_data,
        'day_high': historical_data['High'].iloc[-1],
        'day_low': historical_data['Low'].iloc[-1],
        'volume': historical_data['Volume'].iloc[-1],
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': 'Demo Data'
    }

# --- Main Dashboard Logic (Equity) ---
def equity_dashboard():
    st.sidebar.markdown("")

    # --- Quick Pick popular stocks ---
    st.sidebar.markdown("**🔥 Popular Stocks**")
    popular = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "BAJFINANCE", "WIPRO", "ICICIBANK"]
    cols = st.sidebar.columns(2)
    for i, s in enumerate(popular):
        if cols[i % 2].button(s, key=f"quick_{s}", use_container_width=True):
            st.session_state["quick_symbol"] = s

    st.sidebar.markdown("---")
    default_sym = st.session_state.get("quick_symbol", "TCS")
    symbol_input = st.sidebar.text_input("🔎 Or type any NSE symbol", default_sym)
    if not symbol_input:
        st.warning("Please enter a stock symbol.")
        return
    symbol_to_fetch = symbol_input.upper().strip()

    col_refresh, col_auto = st.sidebar.columns(2)
    if col_refresh.button("🔄 Refresh", key="manual_refresh_btn"):
        st.cache_data.clear()
        st.rerun()
    if col_auto.checkbox("Auto (5m)", value=False):
        st_autorefresh(interval=300000, key="auto_refresh_trigger")

    # --- Fetch Data ---
    with st.spinner(f"Loading {symbol_to_fetch}..."):
        stock_data, error = get_realtime_stock_data(symbol_to_fetch)

    if error or not stock_data:
        st.error(f"❌ Could not find **{symbol_to_fetch}**. Check the symbol and try again.\n\nExamples: TCS, RELIANCE, INFY, SBIN, HDFCBANK")
        return

    # --- Compute base values ---
    latest_price = stock_data['price']
    prev_price   = stock_data['prev_close']
    price_change = latest_price - prev_price
    price_pct    = (price_change / prev_price * 100) if prev_price else 0
    volume       = stock_data.get('volume', 0)
    day_high     = stock_data.get('day_high', latest_price)
    day_low      = stock_data.get('day_low', latest_price)
    up_today     = price_change >= 0

    # --- HERO Price Card ---
    arrow = "▲" if up_today else "▼"
    price_color = "#16a34a" if up_today else "#dc2626"
    st.markdown(f"""
    <div style="background:{'#f0fdf4' if up_today else '#fef2f2'};border:2px solid {price_color};
                border-radius:14px;padding:1.5rem 2rem;margin-bottom:1rem;display:flex;
                align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem">
        <div>
            <div style="font-size:2rem;font-weight:900;color:#0f172a">{symbol_to_fetch}</div>
            <div style="color:#64748b;font-size:0.9rem">NSE · {stock_data.get('data_source','Yahoo Finance')} · {stock_data.get('last_updated','')[:16]}</div>
        </div>
        <div style="text-align:right">
            <div style="font-size:2.8rem;font-weight:900;color:{price_color}">₹{latest_price:,.2f}</div>
            <div style="font-size:1.1rem;color:{price_color};font-weight:700">{arrow} ₹{abs(price_change):.2f} ({price_pct:+.2f}%) today</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 4 simple stat pills ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's High", f"₹{day_high:,.2f}" if isinstance(day_high, float) else "N/A")
    c2.metric("Today's Low",  f"₹{day_low:,.2f}"  if isinstance(day_low,  float) else "N/A")
    c3.metric("Volume",       f"{int(volume):,}"   if isinstance(volume,   (int,float)) and volume else "N/A")
    hist = stock_data['historical']
    ret1m = (hist['Close'].iloc[-1] / hist['Close'].iloc[-min(21,len(hist))] - 1) * 100 if len(hist) > 5 else 0
    c4.metric("1-Month Return", f"{ret1m:+.1f}%", delta_color="normal")

    st.markdown("---")

    # --- Run analysis silently ---
    with st.spinner("🧠 Analysing..."):
        analyzed_data = calculate_advanced_technical_indicators(stock_data['historical'])
        model_signal, model_reason, model_confidence = generate_rule_based_trading_signal(analyzed_data)

    # --- Run ALL models and collect individual results ---
    all_model_results = {}

    # Rule-based (already computed)
    all_model_results["⚙️ Rule-Based Model"] = {
        "signal": model_signal, "reason": model_reason,
        "confidence": model_confidence, "status": "ok",
        "desc": "Analyses RSI, MACD, Bollinger Bands, Moving Averages using fixed mathematical rules."
    }

    # Grok (xAI)
    if OPENAI_SDK_AVAILABLE and XAI_API_KEY:
        gk_signal, gk_reason, gk_conf = get_grok_recommendation(
            stock_data['symbol'], stock_data['price'], analyzed_data)
        if gk_signal is not None:
            all_model_results["✨ Grok AI (xAI)"] = {
                "signal": gk_signal, "reason": gk_reason,
                "confidence": gk_conf, "status": "ok",
                "desc": "xAI reasoning model — analyses indicators like a professional quant analyst."
            }
        else:
            all_model_results["✨ Grok AI (xAI)"] = {
                "signal": "N/A", "reason": gk_reason,
                "confidence": 0, "status": "error",
                "desc": "xAI Grok — unavailable (no credits or API error)."
            }

    # Groq (llama3)
    if GROQ_AVAILABLE and GROQ_API_KEY:
        gr_signal, gr_reason, gr_conf = get_groq_recommendation(
            stock_data['symbol'], stock_data['price'], analyzed_data)
        if gr_signal is not None:
            all_model_results["🟣 Groq (llama3-70b)"] = {
                "signal": gr_signal, "reason": gr_reason,
                "confidence": gr_conf, "status": "ok",
                "desc": "Meta's llama3-70b via Groq — 14,400 free API calls/day."
            }
        else:
            all_model_results["🟣 Groq (llama3-70b)"] = {
                "signal": "N/A", "reason": gr_reason,
                "confidence": 0, "status": "error",
                "desc": "Groq llama3 — unavailable."
            }

    # Gemini
    gem_signal, gem_reason, gem_conf = get_gemini_recommendation(
        stock_data['symbol'], stock_data['price'], analyzed_data)
    status = "ok" if "rate limit" not in gem_reason.lower() and "error" not in gem_reason.lower() else "warn"
    all_model_results["🔵 Gemini AI (Google)"] = {
        "signal": gem_signal, "reason": gem_reason,
        "confidence": gem_conf, "status": status,
        "desc": "Google Gemini 2.0 Flash — free fallback AI model."
    }

    # --- Pick best AI for the final decision (first working non-rule model) ---
    ai_signal, ai_reason, ai_confidence, ai_source = model_signal, model_reason, model_confidence, "⚙️ Rule-Based Model"
    priority = ["✨ Grok AI (xAI)", "🟣 Groq (llama3-70b)", "🔵 Gemini AI (Google)"]
    for name in priority:
        if name in all_model_results and all_model_results[name]["status"] == "ok":
            r = all_model_results[name]
            ai_signal, ai_reason, ai_confidence, ai_source = r["signal"], r["reason"], r["confidence"], name
            break

    # --- Final decision ---
    if model_signal == ai_signal:
        final_signal     = model_signal
        final_confidence = (model_confidence + ai_confidence) / 2
        agree_text       = "Both AI and technical analysis agree"
    elif model_confidence >= ai_confidence:
        final_signal, final_confidence = model_signal, model_confidence
        agree_text = "Technical analysis is stronger"
    else:
        final_signal, final_confidence = ai_signal, ai_confidence
        agree_text = f"{ai_source} is more confident"

    # Plain-English action text
    action_map = {
        "BUY":  ("🟢", "Looks like a good time to BUY", "#f0fdf4", "#16a34a",
                  "The stock shows signs of strength — price momentum and indicators point upward."),
        "SELL": ("🔴", "Consider SELLING or reducing position", "#fef2f2", "#dc2626",
                  "The stock shows weakness — indicators suggest the price may fall further."),
        "HOLD": ("🟡", "HOLD — wait and watch", "#fffbeb", "#d97706",
                  "No clear signal right now. If you own it, hold. If not, wait for a better entry."),
    }
    sig_icon, sig_text, sig_bg, sig_col, sig_desc = action_map.get(
        final_signal, ("⚪", "HOLD", "#f8f9fa", "#64748b", ""))

    conf_pct = int(final_confidence * 100)
    conf_label = "High" if conf_pct >= 70 else "Medium" if conf_pct >= 50 else "Low"
    conf_color = "#16a34a" if conf_pct >= 70 else "#d97706" if conf_pct >= 50 else "#dc2626"

    # --- BIG AI Decision Card ---
    st.markdown(f"""
    <div style="background:{sig_bg};border:3px solid {sig_col};border-radius:16px;
                padding:2rem;text-align:center;margin:0.5rem 0 1.5rem">
        <div style="font-size:3rem;margin-bottom:0.3rem">{sig_icon}</div>
        <div style="font-size:2rem;font-weight:900;color:{sig_col}">{sig_text}</div>
        <div style="font-size:1rem;color:#475569;margin:0.6rem 0 1rem">{sig_desc}</div>
        <div style="background:white;border-radius:10px;padding:0.8rem;display:inline-block;min-width:260px">
            <span style="font-size:0.85rem;color:#64748b">AI Confidence: </span>
            <span style="font-size:1.1rem;font-weight:800;color:{conf_color}">{conf_pct}% ({conf_label})</span>
            &nbsp;·&nbsp;
            <span style="font-size:0.85rem;color:#64748b">{agree_text}</span>
        </div>
        <div style="margin-top:0.8rem;font-size:0.85rem;color:#64748b">
            💬 {ai_reason} &nbsp;|&nbsp; Powered by {ai_source}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- All Models Detail Expander ---
    signal_colors = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#d97706", "N/A": "#94a3b8"}
    signal_bg     = {"BUY": "#f0fdf4", "SELL": "#fef2f2", "HOLD": "#fffbeb", "N/A": "#f1f5f9"}
    signal_icons  = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "N/A": "⚫"}

    with st.expander("🔍 See what each model thinks — full breakdown", expanded=False):
        for model_name, res in all_model_results.items():
            sig   = res["signal"]
            conf  = res["confidence"]
            col   = signal_colors.get(sig, "#64748b")
            bg    = signal_bg.get(sig, "#f8f9fa")
            icon  = signal_icons.get(sig, "⚪")
            conf_bar = ("█" * int(conf * 10) + "░" * (10 - int(conf * 10))) if conf else "░" * 10
            status_badge = ""
            if res["status"] == "error":
                status_badge = "<span style='background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:10px;font-size:0.75rem'>Unavailable</span>"
            elif res["status"] == "warn":
                status_badge = "<span style='background:#fffbeb;color:#d97706;padding:2px 8px;border-radius:10px;font-size:0.75rem'>Rate Limited</span>"
            else:
                status_badge = "<span style='background:#f0fdf4;color:#16a34a;padding:2px 8px;border-radius:10px;font-size:0.75rem'>✓ Active</span>"

            st.markdown(f"""
            <div style="background:{bg};border-left:5px solid {col};border-radius:10px;
                        padding:1rem 1.2rem;margin-bottom:0.8rem">
                <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
                    <div>
                        <span style="font-weight:800;font-size:1rem;color:#0f172a">{model_name}</span>
                        &nbsp;&nbsp;{status_badge}
                    </div>
                    <div style="font-size:1.5rem;font-weight:900;color:{col}">{icon} {sig}</div>
                </div>
                <div style="font-size:0.82rem;color:#64748b;margin:0.3rem 0">{res['desc']}</div>
                <div style="margin-top:0.5rem">
                    <span style="font-family:monospace;color:{col};font-size:0.95rem">{conf_bar}</span>
                    <span style="color:#64748b;font-size:0.85rem;margin-left:0.5rem">Confidence: <b>{int(conf*100)}%</b></span>
                </div>
                <div style="font-size:0.88rem;color:#475569;margin-top:0.4rem;font-style:italic">"{res['reason']}"</div>
            </div>
            """, unsafe_allow_html=True)

        # Summary comparison table
        st.markdown("**Quick Comparison**")
        rows = []
        for name, r in all_model_results.items():
            rows.append({"Model": name, "Signal": r["signal"], "Confidence": f"{int(r['confidence']*100)}%", "Status": r["status"].title()})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- Plain English Health Indicators ---
    st.markdown("#### 📊 Stock Health Check")
    if not analyzed_data.empty:
        latest = analyzed_data.iloc[-1]
        rsi   = latest.get('RSI', 50)
        macd  = latest.get('MACD', 0)
        macd_s = latest.get('MACD_Signal', 0)
        sma20 = latest.get('SMA_20', latest_price)
        sma50 = latest.get('SMA_50', latest_price)
        bb_u  = latest.get('BB_Upper', latest_price)
        bb_l  = latest.get('BB_Lower', latest_price)

        def health_row(label, status, detail, good=True):
            icon = "✅" if good else "⚠️"
            color = "#16a34a" if good else "#d97706"
            return f"""<div style="display:flex;align-items:center;gap:0.8rem;padding:0.6rem 1rem;
                        background:#f8f9fa;border-radius:8px;margin-bottom:0.5rem">
                <span style="font-size:1.3rem">{icon}</span>
                <div>
                    <span style="font-weight:700;color:#0f172a">{label}</span>
                    <span style="color:{color};font-weight:600;margin-left:0.5rem">{status}</span>
                    <div style="font-size:0.82rem;color:#64748b">{detail}</div>
                </div></div>"""

        # Trend
        if latest_price > sma20 and latest_price > sma50:
            h1 = health_row("Trend", "📈 Uptrend", f"Price ₹{latest_price:,.0f} is above both short & long-term averages", True)
        elif latest_price < sma20 and latest_price < sma50:
            h1 = health_row("Trend", "📉 Downtrend", f"Price ₹{latest_price:,.0f} is below both short & long-term averages", False)
        else:
            h1 = health_row("Trend", "↔️ Mixed", "Price is between the short and long-term averages — sideways market", True)

        # Momentum (RSI)
        if rsi < 30:
            h2 = health_row("Momentum (RSI)", f"🔵 Oversold ({rsi:.0f})", "Stock may have fallen too much — potential bounce opportunity", True)
        elif rsi > 70:
            h2 = health_row("Momentum (RSI)", f"🔴 Overbought ({rsi:.0f})", "Stock may have risen too fast — could correct downward", False)
        else:
            h2 = health_row("Momentum (RSI)", f"🟢 Healthy ({rsi:.0f})", "RSI in normal range (30–70) — no extreme conditions", True)

        # MACD
        if macd > macd_s:
            h3 = health_row("Momentum (MACD)", "📈 Bullish", "Buying pressure is increasing — a good sign", True)
        else:
            h3 = health_row("Momentum (MACD)", "📉 Bearish", "Selling pressure is increasing — be cautious", False)

        # Bollinger Bands
        if latest_price < bb_l:
            h4 = health_row("Price Level", "🔵 Near Support", f"Price near lower band ₹{bb_l:,.0f} — could bounce up from here", True)
        elif latest_price > bb_u:
            h4 = health_row("Price Level", "🔴 Near Resistance", f"Price near upper band ₹{bb_u:,.0f} — stretched, may pull back", False)
        else:
            h4 = health_row("Price Level", "🟢 Normal Range", f"Price within normal range (₹{bb_l:,.0f} – ₹{bb_u:,.0f})", True)

        st.markdown(h1 + h2 + h3 + h4, unsafe_allow_html=True)

    # --- Simple Price Chart ---
    st.markdown("#### 📈 Price Chart (Last 6 Months)")
    if not analyzed_data.empty:
        chart_data = analyzed_data.tail(130)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=chart_data.index, open=chart_data['Open'], high=chart_data['High'],
            low=chart_data['Low'], close=chart_data['Close'],
            name="Price", increasing_line_color='#16a34a', decreasing_line_color='#dc2626',
            showlegend=False
        ))
        if 'SMA_20' in chart_data.columns:
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA_20'],
                name='20-day Avg', line=dict(color='#f59e0b', width=2)))
        if 'SMA_50' in chart_data.columns:
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA_50'],
                name='50-day Avg', line=dict(color='#6366f1', width=2)))
        fig.update_layout(
            height=400, template='plotly_white',
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.05),
            margin=dict(t=20, b=20, l=10, r=10),
            yaxis_title="Price (₹)"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🟡 20-day Average  ·  🟣 50-day Average  ·  Green candle = price went up that day  ·  Red = went down")

    # --- Advanced Details (hidden by default) ---
    with st.expander("🔬 See detailed technical indicators (for advanced users)"):
        if not analyzed_data.empty:
            adv_chart = create_comprehensive_chart(analyzed_data, stock_data['symbol'])
            st.plotly_chart(adv_chart, use_container_width=True)
            latest = analyzed_data.iloc[-1]
            det_df = pd.DataFrame({
                "Indicator": ["RSI (14)", "MACD", "MACD Signal", "SMA 20", "SMA 50", "BB Upper", "BB Lower", "Stoch %K", "Stoch %D"],
                "Value": [
                    f"{latest.get('RSI',0):.1f}",
                    f"{latest.get('MACD',0):.4f}",
                    f"{latest.get('MACD_Signal',0):.4f}",
                    f"₹{latest.get('SMA_20',0):.2f}",
                    f"₹{latest.get('SMA_50',0):.2f}",
                    f"₹{latest.get('BB_Upper',0):.2f}",
                    f"₹{latest.get('BB_Lower',0):.2f}",
                    f"{latest.get('%K',0):.1f}",
                    f"{latest.get('%D',0):.1f}",
                ],
                "What it means": [
                    "Below 30 = oversold, Above 70 = overbought",
                    "Positive = bullish momentum",
                    "MACD above this = buy signal",
                    "Short-term average price",
                    "Long-term average price",
                    "Resistance level — hard to go above",
                    "Support level — hard to go below",
                    "Below 20 = oversold, Above 80 = overbought",
                    "3-day average of %K"
                ]
            })
            st.dataframe(det_df, use_container_width=True, hide_index=True)

    # --- Quick Trade Simulator ---
    st.markdown("---")
    st.markdown("#### 💰 Quick Investment Calculator")
    inv_col1, inv_col2 = st.columns(2)
    invest_amt = inv_col1.number_input("How much do you want to invest? (₹)", min_value=100, value=10000, step=500)
    shares = int(invest_amt // latest_price)
    actual_cost = shares * latest_price
    inv_col2.markdown(f"""
    <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:1rem;margin-top:0.3rem">
        <div style="font-size:0.85rem;color:#0369a1">At ₹{latest_price:,.2f} per share</div>
        <div style="font-size:1.4rem;font-weight:800;color:#0f172a">You get {shares} shares</div>
        <div style="font-size:0.85rem;color:#64748b">Actual cost: ₹{actual_cost:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    # Trade simulation buttons
    st.markdown("#### 📝 Paper Trade (Practice only)")
    t1, t2, t3, t4 = st.columns([2, 1, 1, 1])
    trade_qty = t1.number_input("Shares", min_value=1, value=max(1, shares), key="trade_qty_input")
    t2.write("")
    t3.write("")
    if t2.button("🟢 Buy",  use_container_width=True): buy_stock(stock_data['symbol'], trade_qty, latest_price)
    if t3.button("🔴 Sell", use_container_width=True): sell_stock(stock_data['symbol'], trade_qty, latest_price)
    if t4.button("🟡 Hold", use_container_width=True): hold_stock(stock_data['symbol'])

    if st.session_state.transaction_log:
        with st.expander(f"📋 Transaction log ({len(st.session_state.transaction_log)} trades)"):
            st.dataframe(pd.DataFrame(st.session_state.transaction_log), use_container_width=True, hide_index=True)

    # --- WhatsApp Share ---
    st.markdown("---")
    show_whatsapp_digest(stock_data, analyzed_data, final_signal, ai_reason)

    st.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:0.8rem;margin-top:1rem'>⚠️ For educational purposes only — not financial advice · Last updated {stock_data.get('last_updated','')[:16]}</div>", unsafe_allow_html=True)

# --- Derivatives Dashboard Logic ---
def derivatives_dashboard():
    st.sidebar.subheader("Derivatives Data Options")
    instrument = st.sidebar.selectbox("Instrument Type", options=("NSE Equity Market", "NSE Derivative Market"))
    data = None
    data_info = ""
    
    if not NSELIB_AVAILABLE:
        st.warning("NSE Library is not installed. This section is not functional.")
        return

    try:
        if instrument == "NSE Equity Market":
            data_info = st.sidebar.selectbox("Data to extract", options=("price_volume_and_deliverable_position_data", "bhav_copy_equities", "nifty50_equity_list", "india_vix_data", "market_watch_all_indices"))
            if data_info == "bhav_copy_equities":
                date_input = st.sidebar.date_input("Date", datetime.now())
                date_str = date_input.strftime("%d-%m-%Y")
                data = capital_market.bhav_copy_equities(date_str)
            elif data_info in ["nifty50_equity_list", "india_vix_data", "market_watch_all_indices"]:
                data = getattr(capital_market, data_info)()
            else:
                symbol = st.sidebar.text_input("Enter Stock Symbol (e.g., SBIN)", "SBIN")
                period = st.sidebar.selectbox("Select Period", ["1M", "3M", "6M", "1Y"])
                data = getattr(capital_market, data_info)(symbol=symbol, period=period)
        elif instrument == "NSE Derivative Market":
            data_info = st.sidebar.selectbox("Data to extract", options=("fno_bhav_copy", "nse_live_option_chain", "future_price_volume_data"))
            if data_info == "fno_bhav_copy":
                date_input = st.sidebar.date_input("Date", datetime.now())
                date_str = date_input.strftime("%d-%m-%Y")
                data = derivatives.fno_bhav_copy(date_str)
            elif data_info == "nse_live_option_chain":
                ticker = st.sidebar.text_input("Ticker", "BANKNIFTY")
                data = derivatives.nse_live_option_chain(ticker)
            elif data_info == "future_price_volume_data":
                ticker = st.sidebar.text_input("Ticker", "SBIN")
                type_ = st.sidebar.selectbox("Instrument Type", ["FUTSTK", "FUTIDX"])
                period_ = st.sidebar.selectbox("Period", ["1M", "3M", "6M", "1Y"])
                data = derivatives.future_price_volume_data(ticker, type_, period=period_)

    except requests.exceptions.RequestException as e:
        st.error(f"Network Error: Failed to connect to the data source. Details: {e}")
        data = None
    except Exception as e:
        st.error(f"An unexpected error occurred while fetching derivatives data: {e}")
        data = None
    
    if data is not None and not data.empty:
        st.subheader(f"Derivatives Data: {data_info.replace('_', ' ').title()}")
        st.dataframe(data, use_container_width=True)
    else:
        st.warning("No data available for the selected options.")

# --- Portfolio Tracker ---
def _get_supabase() -> "SupabaseClient | None":
    if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception:
            return None
    return None


def _portfolio_load():
    """Load holdings: Supabase if configured, else session state."""
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("portfolio").select("*").order("created_at", desc=True).execute()
            return res.data or []
        except Exception:
            pass
    return st.session_state.portfolio


def _portfolio_add(holding: dict):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("portfolio").insert(holding).execute()
            return
        except Exception:
            pass
    st.session_state.portfolio.insert(0, {**holding, "id": len(st.session_state.portfolio) + 1})


def _portfolio_delete(holding_id):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("portfolio").delete().eq("id", holding_id).execute()
            return
        except Exception:
            pass
    st.session_state.portfolio = [h for h in st.session_state.portfolio if h.get("id") != holding_id]


@st.cache_data(ttl=300)
def _fetch_current_price(symbol: str) -> float | None:
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    try:
        ticker = yf.Ticker(f"{symbol}.BO")
        hist = ticker.history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None


def show_portfolio_tracker():
    st.subheader("💼 Portfolio Tracker")

    sb = _get_supabase()
    if not sb:
        st.info(
            "**Running in local session mode** — holdings reset on page refresh.  \n"
            "To persist data permanently, set `SUPABASE_URL` and `SUPABASE_KEY` in the code "
            "using your free [supabase.com](https://supabase.com) project, then run this SQL once:\n"
            "```sql\n"
            "CREATE TABLE portfolio (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  symbol TEXT NOT NULL,\n"
            "  quantity NUMERIC NOT NULL,\n"
            "  buy_price NUMERIC NOT NULL,\n"
            "  buy_date DATE NOT NULL,\n"
            "  notes TEXT,\n"
            "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
            ");\n"
            "```"
        )

    # --- Add Holding Form ---
    with st.expander("➕ Add New Holding", expanded=False):
        with st.form("add_holding_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            sym = c1.text_input("Symbol (NSE)", placeholder="e.g. TCS").upper().strip()
            qty = c2.number_input("Quantity", min_value=0.01, value=10.0, step=1.0)
            bp  = c3.number_input("Buy Price (₹)", min_value=0.01, value=100.0, step=0.5)
            bd  = c4.date_input("Buy Date", value=datetime.today())
            notes = st.text_input("Notes (optional)", placeholder="e.g. Long-term hold")
            submitted = st.form_submit_button("Add to Portfolio")

        if submitted:
            if not sym:
                st.error("Please enter a stock symbol.")
            else:
                _portfolio_add({
                    "symbol": sym, "quantity": float(qty),
                    "buy_price": float(bp), "buy_date": str(bd),
                    "notes": notes
                })
                st.success(f"✅ Added {qty} × {sym} @ ₹{bp:.2f}")
                st.rerun()

    # --- Load & Display Holdings ---
    holdings = _portfolio_load()
    if not holdings:
        st.info("No holdings yet. Add your first stock above.")
        return

    rows = []
    for h in holdings:
        sym = h.get("symbol", "")
        qty = float(h.get("quantity", 0))
        bp  = float(h.get("buy_price", 0))
        cp  = _fetch_current_price(sym)
        invested = qty * bp
        if cp:
            current_val = qty * cp
            pl = current_val - invested
            pl_pct = (pl / invested) * 100 if invested else 0
        else:
            current_val = pl = pl_pct = None
        rows.append({
            "id": h.get("id"),
            "Symbol": sym,
            "Qty": qty,
            "Buy ₹": bp,
            "Current ₹": cp or "N/A",
            "Invested ₹": round(invested, 2),
            "Value ₹": round(current_val, 2) if current_val else "N/A",
            "P&L ₹": round(pl, 2) if pl is not None else "N/A",
            "P&L %": round(pl_pct, 2) if pl_pct is not None else "N/A",
            "Buy Date": h.get("buy_date", ""),
            "Notes": h.get("notes", ""),
        })

    # --- Summary Cards ---
    total_invested = sum(r["Invested ₹"] for r in rows)
    total_value = sum(r["Value ₹"] for r in rows if isinstance(r["Value ₹"], float))
    total_pl = total_value - total_invested if total_value else 0
    total_pl_pct = (total_pl / total_invested * 100) if total_invested else 0
    pl_color = "#22c55e" if total_pl >= 0 else "#ef4444"
    pl_arrow = "▲" if total_pl >= 0 else "▼"

    st.markdown(f"""
    <div class="portfolio-summary">
        <h3 style="margin:0 0 0.8rem">Portfolio Overview</h3>
        <div style="display:flex;justify-content:center;gap:3rem;flex-wrap:wrap">
            <div><div style="font-size:1.6rem;font-weight:800">₹{total_invested:,.0f}</div><div style="opacity:0.8;font-size:0.85rem">Total Invested</div></div>
            <div><div style="font-size:1.6rem;font-weight:800">₹{total_value:,.0f}</div><div style="opacity:0.8;font-size:0.85rem">Current Value</div></div>
            <div><div style="font-size:1.6rem;font-weight:800;color:{pl_color}">{pl_arrow} ₹{abs(total_pl):,.0f}</div><div style="opacity:0.8;font-size:0.85rem">Overall P&amp;L ({total_pl_pct:+.2f}%)</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Charts ---
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        alloc_df = pd.DataFrame({"Symbol": [r["Symbol"] for r in rows], "Invested": [r["Invested ₹"] for r in rows]})
        fig_pie = px.pie(alloc_df, values="Invested", names="Symbol", title="Portfolio Allocation",
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        fig_pie.update_layout(height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        pl_rows = [r for r in rows if isinstance(r["P&L %"], float)]
        if pl_rows:
            bar_df = pd.DataFrame({"Symbol": [r["Symbol"] for r in pl_rows], "P&L %": [r["P&L %"] for r in pl_rows]})
            bar_df["Color"] = bar_df["P&L %"].apply(lambda x: "#16a34a" if x >= 0 else "#dc2626")
            fig_bar = px.bar(bar_df, x="Symbol", y="P&L %", title="P&L % per Holding",
                             color="Color", color_discrete_map="identity",
                             text=bar_df["P&L %"].apply(lambda x: f"{x:+.2f}%"))
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(showlegend=False, height=320, margin=dict(t=40, b=10))
            st.plotly_chart(fig_bar, use_container_width=True)

    # --- Holdings Table ---
    st.markdown("#### Holdings")
    for r in rows:
        pl_val = r["P&L ₹"]
        pl_pct_val = r["P&L %"]
        pl_str = f'<span class="{"portfolio-gain" if isinstance(pl_val,float) and pl_val>=0 else "portfolio-loss"}">{"▲" if isinstance(pl_val,float) and pl_val>=0 else "▼"} ₹{abs(pl_val):,.2f} ({pl_pct_val:+.2f}%)</span>' if isinstance(pl_val, float) else "N/A"
        cp_str = f"₹{r['Current ₹']:,.2f}" if isinstance(r["Current ₹"], float) else "N/A"
        st.markdown(f"""
        <div class="holding-card">
            <b style="font-size:1.1rem">{r["Symbol"]}</b> &nbsp;·&nbsp; {r["Qty"]:.0f} shares &nbsp;·&nbsp; Bought @ ₹{r["Buy ₹"]:,.2f} on {r["Buy Date"]}
            <br>Current: {cp_str} &nbsp;|&nbsp; Invested: ₹{r["Invested ₹"]:,.2f} &nbsp;|&nbsp; P&amp;L: {pl_str}
            {"<br><small style='color:#64748b'>📝 " + r["Notes"] + "</small>" if r["Notes"] else ""}
        </div>
        """, unsafe_allow_html=True)
        if st.button(f"🗑️ Remove {r['Symbol']}", key=f"del_{r['id']}_{r['Symbol']}"):
            _portfolio_delete(r["id"])
            st.rerun()

    # --- Export ---
    st.markdown("---")
    display_cols = ["Symbol", "Qty", "Buy ₹", "Current ₹", "Invested ₹", "Value ₹", "P&L ₹", "P&L %", "Buy Date", "Notes"]
    export_df = pd.DataFrame(rows)[display_cols]
    csv = export_df.to_csv(index=False)
    st.download_button("📥 Export Portfolio to CSV", data=csv, file_name="portfolio.csv", mime="text/csv")


# --- F&O Options Chain & PCR ---
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
}

@st.cache_data(ttl=180)
def fetch_option_chain(symbol: str = "NIFTY"):
    """Fetch live option chain from NSE India (free, no API key)."""
    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        if symbol not in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"):
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        resp = session.get(url, headers=NSE_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None


def parse_option_chain(data: dict, atm_range: int = 10):
    """Parse NSE option chain JSON into a clean DataFrame."""
    try:
        records = data["records"]["data"]
        expiry_dates = data["records"]["expiryDates"]
        spot_price = data["records"]["underlyingValue"]
        nearest_expiry = expiry_dates[0] if expiry_dates else None

        rows = []
        for rec in records:
            if rec.get("expiryDate") != nearest_expiry:
                continue
            strike = rec.get("strikePrice", 0)
            ce = rec.get("CE", {})
            pe = rec.get("PE", {})
            rows.append({
                "Strike": strike,
                "CE OI": ce.get("openInterest", 0),
                "CE Chng OI": ce.get("changeinOpenInterest", 0),
                "CE LTP": ce.get("lastPrice", 0),
                "CE IV": ce.get("impliedVolatility", 0),
                "PE LTP": pe.get("lastPrice", 0),
                "PE OI": pe.get("openInterest", 0),
                "PE Chng OI": pe.get("changeinOpenInterest", 0),
                "PE IV": pe.get("impliedVolatility", 0),
            })

        df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)

        # Filter ±ATM strikes
        atm = min(df["Strike"], key=lambda x: abs(x - spot_price))
        strikes = sorted(df["Strike"].unique())
        atm_idx = strikes.index(atm)
        lo = max(0, atm_idx - atm_range)
        hi = min(len(strikes) - 1, atm_idx + atm_range)
        selected = strikes[lo:hi + 1]
        df = df[df["Strike"].isin(selected)].reset_index(drop=True)

        total_ce_oi = df["CE OI"].sum()
        total_pe_oi = df["PE OI"].sum()
        pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi else 0

        return df, spot_price, nearest_expiry, pcr, atm
    except Exception as e:
        return None, None, None, None, None


def show_fno_dashboard():
    st.subheader("📉 F&O Options Chain & Put-Call Ratio")
    st.caption("Live data from NSE India — no API key needed. Refreshes every 3 minutes.")

    col1, col2 = st.columns([2, 1])
    symbol = col1.selectbox(
        "Select Index / Stock",
        ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
         "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BAJFINANCE"],
        index=0
    )
    atm_range = col2.slider("Strikes around ATM", 5, 20, 10)

    with st.spinner(f"Fetching live option chain for {symbol} from NSE..."):
        data = fetch_option_chain(symbol)

    if not data:
        st.error("Could not fetch option chain from NSE. NSE blocks automated requests intermittently — please try again in a moment.")
        return

    df, spot, expiry, pcr, atm = parse_option_chain(data, atm_range)

    if df is None or df.empty:
        st.warning("Option chain data parsed but empty. Try a different symbol.")
        return

    # --- Key Metrics Row ---
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Spot Price", f"₹{spot:,.2f}")
    m2.metric("ATM Strike", f"₹{atm:,.0f}")
    m3.metric("Expiry", expiry)
    pcr_delta = "Bullish" if pcr > 1.2 else ("Bearish" if pcr < 0.8 else "Neutral")
    m4.metric("PCR", f"{pcr:.3f}", delta=pcr_delta)
    total_oi = df["CE OI"].sum() + df["PE OI"].sum()
    m5.metric("Total OI", f"{total_oi/1e5:.1f}L")

    # PCR Interpretation
    if pcr > 1.2:
        st.success(f"**PCR {pcr:.3f} → Bullish** — More puts being written than calls. Market participants expect the index to hold or go up.")
    elif pcr < 0.8:
        st.error(f"**PCR {pcr:.3f} → Bearish** — More calls being written. Market participants expect a fall or cap.")
    else:
        st.info(f"**PCR {pcr:.3f} → Neutral** — Balanced put-call activity. No strong directional bias.")

    # --- OI Bar Chart ---
    st.markdown("#### Open Interest — Calls vs Puts by Strike")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["CE OI"] / 1000,
        name="Call OI (K)", marker_color="#ef4444", opacity=0.85
    ))
    fig.add_trace(go.Bar(
        x=df["Strike"], y=df["PE OI"] / 1000,
        name="Put OI (K)", marker_color="#22c55e", opacity=0.85
    ))
    fig.add_vline(x=atm, line_dash="dash", line_color="#6366f1",
                  annotation_text=f"ATM ₹{atm:,.0f}", annotation_position="top")
    fig.update_layout(
        barmode="group", height=420, template="plotly_white",
        xaxis_title="Strike Price", yaxis_title="Open Interest (thousands)",
        legend=dict(orientation="h", y=1.02)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- OI Change Chart ---
    st.markdown("#### Change in OI — Buildup Detection")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df["Strike"], y=df["CE Chng OI"] / 1000,
        name="CE OI Change", marker_color="#f87171", opacity=0.85
    ))
    fig2.add_trace(go.Bar(
        x=df["Strike"], y=df["PE Chng OI"] / 1000,
        name="PE OI Change", marker_color="#4ade80", opacity=0.85
    ))
    fig2.add_vline(x=atm, line_dash="dash", line_color="#6366f1")
    fig2.update_layout(
        barmode="group", height=350, template="plotly_white",
        xaxis_title="Strike Price", yaxis_title="Change in OI (thousands)",
        legend=dict(orientation="h", y=1.02)
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Max Pain ---
    df["Pain"] = df["Strike"].apply(
        lambda s: (df["CE OI"] * (df["Strike"] - s).clip(lower=0)).sum()
                + (df["PE OI"] * (s - df["Strike"]).clip(lower=0)).sum()
    )
    max_pain_strike = df.loc[df["Pain"].idxmin(), "Strike"]
    st.info(f"**Max Pain Strike: ₹{max_pain_strike:,.0f}** — Options writers profit most if {symbol} expires near this level.")

    # --- Full Table ---
    with st.expander("📋 Full Option Chain Table"):
        display = df.drop(columns=["Pain"]).set_index("Strike")
        st.dataframe(
            display.style
                .background_gradient(subset=["CE OI", "PE OI"], cmap="RdYlGn")
                .format("{:,.0f}", subset=["CE OI", "PE Chng OI", "CE Chng OI", "PE OI"])
                .format("{:.2f}", subset=["CE LTP", "PE LTP", "CE IV", "PE IV"]),
            use_container_width=True
        )


# --- Final Main App Flow ---
market_type = st.sidebar.radio("Market Type", ["Equity", "Derivatives"])

if market_type == "Equity":
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Stock Analysis",
        "🗺️ Nifty 50 Heatmap",
        "🔍 Stock Screener",
        "📰 News Sentiment",
        "💼 Portfolio",
        "📉 F&O / Options"
    ])
    with tab1:
        equity_dashboard()
    with tab2:
        show_nifty50_heatmap()
    with tab3:
        show_stock_screener()
    with tab4:
        news_symbol = st.text_input("Enter company name or symbol for news", "Reliance", key="news_sym")
        if news_symbol:
            show_news_sentiment(news_symbol.strip())
    with tab5:
        show_portfolio_tracker()
    with tab6:
        show_fno_dashboard()
else:
    derivatives_dashboard()
















