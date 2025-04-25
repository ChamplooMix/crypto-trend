# Workaround für pandas_ta Import-Error: numpy muss NaN exportieren
import numpy as np
np.NaN = np.nan

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from collections import Counter

# Seite konfigurieren
st.set_page_config(
    page_title="Crypto Signals",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
symbol = st.sidebar.selectbox(
    "Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0
)
timeframe = st.sidebar.radio(
    "Timeframe", ["5m", "15m", "60m", "240m", "1d"], index=0
)
limit = st.sidebar.slider(
    "Kerzenanzahl", min_value=50, max_value=500, value=200
)

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
    except ccxt.NetworkError as e:
        st.error(f"Netzwerk-Fehler beim Abrufen der Daten: {e}")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    except ccxt.BaseError as e:
        st.error(f"Exchange-Fehler: {e}")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
        data,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df

def compute_signals(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if df.empty:
        return "NEUTRAL", df
    bb = df["close"].ta.bbands(length=20, std=2)
    df = df.join(bb)
    df["RSI"] = df["close"].ta.rsi(14)
    df["vol_ma"] = df["volume"].rolling(20).mean()
    last = df.iloc[-1]
    signals: list[str] = []
    if last.get("close", float("nan")) < last.get("BBL_20_2.0", float("nan")):
        signals.append("BUY")
    if last.get("close", float("nan")) > last.get("BBU_20_2.0", float("nan")):
        signals.append("SHORT")
    if last.get("RSI", 50) < 30:
        signals.append("BUY")
    if last.get("RSI", 50) > 70:
        signals.append("SHORT")
    if last.get("volume", 0) > last.get("vol_ma", 0):
        signals.append("BUY")
    cnt = Counter(signals)
    if cnt.get("BUY", 0) >= 2:
        return "BUY", df
    if cnt.get("SHORT", 0) >= 2:
        return "SHORT", df
    return "NEUTRAL", df

# Daten holen & Signale berechnen
df = fetch_ohlcv(symbol, timeframe, limit)
signal, df = compute_signals(df)

# Ausgabe
st.title(f"📊 Signals: {symbol} [{timeframe}]")
if df.empty:
    st.warning("Keine Marktdaten verfügbar. Bitte später erneut versuchen.")
else:
    col1, col2 = st.columns((3, 1))
    with col1:
        fig = go.Figure()
        fig.add_trace(go.Line(x=df.index, y=df["close"], name="Close"))
        fig.add_trace(go.Line(
            x=df.index,
            y=df["BBU_20_2.0"],
            name="BB Upper",
            line=dict(dash="dash")
        ))
        fig.add_trace(go.Line(
            x=df.index,
            y=df["BBL_20_2.0"],
            name="BB Lower",
            line=dict(dash="dash")
        ))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.metric(label="Overall Signal", value=signal)
        st.markdown('---')
        st.write('**Details:**')
        st.write(f'RSI: {df.iloc[-1].get("RSI", 0):.2f}')
        st.write(f'Volumen vs. MA: {df.iloc[-1].get("volume", 0):.0f} vs. {df.iloc[-1].get("vol_ma", 0):.0f}')
