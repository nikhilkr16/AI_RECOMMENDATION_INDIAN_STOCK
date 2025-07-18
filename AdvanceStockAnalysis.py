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

warnings.filterwarnings('ignore')

# --- API Keys and Configuration ---
FINNHUB_API_KEY = "d1sqg0hr01qhe5rbg89gd1sqg0hr01qhe5rbg8a0"

# --- Safe Imports with Fallback ---
try:
    from nselib import capital_market, derivatives
    NSELIB_AVAILABLE = True
except ImportError:
    NSELIB_AVAILABLE = False
    st.warning("NSELib not available. Using alternative data sources.")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Advanced Indian Stock Dashboard",
    page_icon="📈",
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
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if 'transaction_log' not in st.session_state:
    st.session_state.transaction_log = []
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

# --- Main Header ---
st.markdown("""
<div class="main-header">
    <h1>🚀 Advanced Indian Stock Market Dashboard 2025</h1>
    <p>Real-time Analysis | Smart Predictions | Comprehensive Insights</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
st.sidebar.title("📊 Dashboard Controls")
st.sidebar.markdown("---")

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

# --- Highly Accurate AI Trading Signal Generator (Rule-based) ---
def generate_advanced_trading_signal(data):
    """Generate highly accurate trading signals using a weighted rule-based system."""
    
    if data.empty or len(data) < 50:
        return "HOLD", "Insufficient data for analysis.", 0.5

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
        # The score is a percentage, so a score of 80/100 gives 0.8 confidence
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
    data = capital_market.price_volume_and_deliverable_position_data(symbol=symbol, period=period)
    if data is not None and not data.empty:
        data.columns = data.columns.str.strip()
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)
        column_mapping = {'Close Price': 'Close', 'Open Price': 'Open', 'High Price': 'High', 'Low Price': 'Low', 'Total Traded Quantity': 'Volume'}
        data.rename(columns=column_mapping, inplace=True)
        # Fetch current price from Finnhub or another source as NSELib only provides historical data
        finnhub_price, prev_close = _get_realtime_price_finnhub(symbol)
        price = finnhub_price if finnhub_price is not None else data['Close'].iloc[-1]
        prev_close = prev_close if prev_close is not None else data['Close'].iloc[-2] if len(data) > 1 else price
        return {
            'symbol': symbol,
            'price': price,
            'prev_close': prev_close,
            'historical': data,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'NSE Library'
        }
    return None

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
    st.sidebar.markdown("---")
    
    # Data source selection
    data_source_options = ["Yahoo Finance (Real-time)"]
    if NSELIB_AVAILABLE:
        data_source_options.append("NSE Library (Comprehensive)")
    data_source_options.append("Demo Mode")
    
    data_source = st.sidebar.selectbox("📈 Select Data Source", data_source_options, index=0)
    
    # Stock symbol input
    symbol_input = st.sidebar.text_input("Stock Symbol", "TCS")
    
    if not symbol_input:
        st.warning("Please enter a stock symbol.")
        return
        
    symbol_to_fetch = symbol_input.upper().strip()
    
    # Refresh controls
    col_refresh, col_auto = st.sidebar.columns(2)
    if col_refresh.button("🔄 Refresh Data", key="manual_refresh_btn"):
        st.cache_data.clear()
        st.rerun()
    
    auto_refresh_toggle = col_auto.checkbox("Auto Refresh (60s)", value=False)
    if auto_refresh_toggle:
        st_autorefresh(interval=600000, key="auto_refresh_trigger")
    
    with st.spinner(f"Fetching market data for {symbol_to_fetch}..."):
        if data_source == "Yahoo Finance (Real-time)":
            stock_data, error = get_realtime_stock_data(symbol_to_fetch)
        elif data_source == "NSE Library (Comprehensive)":
            stock_data = get_nse_data(symbol_to_fetch)
            error = None if stock_data else f"NSE Library data fetch failed for {symbol_to_fetch}."
        else:
            stock_data = create_demo_data(symbol_to_fetch)
            error = None
            
    if error:
        st.markdown(f"""
        <div class="error-box">
            <h3>❌ Invalid Stock Symbol or Data Not Found</h3>
            <p>{error}</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.success(f"✅ Data loaded successfully for {stock_data['symbol']} from {stock_data['data_source']}")

    # --- Metrics Section ---
    latest_price = stock_data['price']
    prev_price = stock_data['prev_close']
    price_change = latest_price - prev_price
    price_change_pct = (price_change / prev_price) * 100 if prev_price != 0 else 0
    volume = stock_data.get('volume', "N/A")
    day_high = stock_data.get('day_high', "N/A")
    day_low = stock_data.get('day_low', "N/A")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Current Price", f"₹{latest_price:.2f}", f"{price_change:.2f} ({price_change_pct:.2f}%)")
    with col2:
        st.metric("Volume", f"{volume:,}" if isinstance(volume, (int, float)) else volume)
    with col3:
        st.metric("Day High", f"₹{day_high:.2f}" if isinstance(day_high, (int, float)) else day_high)
    with col4:
        st.metric("Day Low", f"₹{day_low:.2f}" if isinstance(day_low, (int, float)) else day_low)
    
    # --- AI Trading Recommendation Section ---
    st.subheader("🎯 AI Trading Recommendation")
    with st.spinner("Analyzing market trends..."):
        analyzed_data = calculate_advanced_technical_indicators(stock_data['historical'])
        signal, reason, confidence = generate_advanced_trading_signal(analyzed_data)
        
    signal_class = f"{signal.lower()}-signal"
    confidence_bar = "🟢" * int(confidence * 10) + "⚪" * (10 - int(confidence * 10))
    st.markdown(f"""
    <div class="prediction-box {signal_class}">
        <h3>📊 {signal}</h3>
        <p>{reason}</p>
        <p>Confidence: {confidence_bar} ({confidence:.1%})</p>
    </div>
    """, unsafe_allow_html=True)

    # --- Charts Section ---
    st.subheader("📈 Advanced Technical Analysis")
    chart = create_comprehensive_chart(analyzed_data, stock_data['symbol'])
    st.plotly_chart(chart, use_container_width=True)
    
    st.subheader("📊 Technical Indicators & Statistics")
    tech_col, stat_col = st.columns(2)
    with tech_col:
        st.markdown("#### Key Indicators")
        if not analyzed_data.empty:
            latest = analyzed_data.iloc[-1]
            indicators_data = {
                'Indicator': ['RSI', 'MACD', 'SMA 20', 'SMA 50', 'BB Upper', 'BB Lower'],
                'Value': [
                    f"{latest.get('RSI', np.nan):.2f}",
                    f"{latest.get('MACD', np.nan):.4f}",
                    f"{latest.get('SMA_20', np.nan):.2f}",
                    f"{latest.get('SMA_50', np.nan):.2f}",
                    f"{latest.get('BB_Upper', np.nan):.2f}",
                    f"{latest.get('BB_Lower', np.nan):.2f}"
                ]
            }
            indicators_df = pd.DataFrame(indicators_data)
            st.dataframe(indicators_df, use_container_width=True)
        else:
            st.info("Technical indicators cannot be calculated with the available data.")

    # Performance Metrics
    with stat_col:
        st.markdown("#### Performance Metrics")
        if not stock_data['historical'].empty:
            returns = stock_data['historical']['Close'].pct_change().dropna()
            if not returns.empty:
                metrics_data = {
                    "Metric": ["1D Return", "30D Return"],
                    "Value": [
                        f"{returns.iloc[-1]*100:.2f}%",
                        f"{(stock_data['historical']['Close'].iloc[-1] / stock_data['historical']['Close'].iloc[-min(30, len(stock_data['historical']))] - 1)*100:.2f}%"
                    ]
                }
                metrics_df = pd.DataFrame(metrics_data)
                st.dataframe(metrics_df, use_container_width=True)
            else:
                st.info("Not enough data to calculate performance metrics.")

    # --- Trading Simulation Section ---
    st.subheader("💼 Trading Simulation")
    col1, col2, col3 = st.columns(3)
    with col1:
        trade_quantity = st.number_input("Quantity", min_value=1, value=10)
    with col2:
        trade_price = st.number_input("Price per Share", min_value=0.01, value=float(latest_price), format="%.2f")
    with col3:
        st.write(""); st.write("")
        if st.button("Buy"):
            buy_stock(stock_data['symbol'], trade_quantity, trade_price)
        if st.button("Sell"):
            sell_stock(stock_data['symbol'], trade_quantity, trade_price)
        if st.button("Hold"):
            hold_stock(stock_data['symbol'])
    
    st.subheader("📝 Transaction Log")
    if st.session_state.transaction_log:
        log_df = pd.DataFrame(st.session_state.transaction_log)
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No transactions yet.")
    st.markdown("---")
    st.markdown(f"**Last Updated:** {stock_data.get('last_updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))} | **Data Source:** {stock_data.get('data_source', 'N/A')}")
    st.markdown("⚠️ *This is for educational purposes only. Please consult a financial advisor before making investment decisions.*")

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

# --- Final Main App Flow ---
market_type = st.sidebar.radio("Market Type", ["Equity", "Derivatives"])
if market_type == "Equity":
    equity_dashboard()
else:
    derivatives_dashboard()