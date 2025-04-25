import numpy as np
np.NaN = np.nan  # pandas_ta workaround

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from collections import Counter

# Seite konfigurieren
st.set_page_config(
    page_title="Crypto Signals",
    layout="wide"
)

# User-Einstellungen in der Sidebar
symbol = st.sidebar.selectbox(
    "Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0
)
limit = st.sidebar.slider(
    "Kerzenanzahl", min_value=50, max_value=500, value=200
)

# Unterstützte Timeframes
timeframes = ["5m", "15m", "1h", "4h", "1d"]

# Funktion zum Abrufen von OHLCV mit Fallback
@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    exchanges = [
        ccxt.binance({'enableRateLimit': True}),
        ccxt.kraken({'enableRateLimit': True}),
    ]
    for exchange in exchanges:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
            df = pd.DataFrame(
                data,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception:
            continue
    st.error("Alle Exchanges nicht verfügbar. Bitte später erneut versuchen.")
    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# Signalberechnung

def compute_signals(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if df.empty:
        return 'NEUTRAL', df
    # Bollinger Bänder
    bb_df = ta.bbands(df['close'], length=20, std=2)
    df = df.join(bb_df)
    # RSI
    df['RSI'] = ta.rsi(df['close'], length=14)
    # Volumen-MA
    df['vol_ma'] = df['volume'].rolling(20).mean()
    last = df.iloc[-1]
    signals = []
    if last['close'] < last['BBL_20_2.0']:
        signals.append('BUY')
    if last['close'] > last['BBU_20_2.0']:
        signals.append('SHORT')
    if last['RSI'] < 30:
        signals.append('BUY')
    if last['RSI'] > 70:
        signals.append('SHORT')
    if last['volume'] > last['vol_ma']:
        signals.append('BUY')
    cnt = Counter(signals)
    if cnt.get('BUY', 0) >= 2:
        return 'BUY', df
    if cnt.get('SHORT', 0) >= 2:
        return 'SHORT', df
    return 'NEUTRAL', df

# Hauptansicht: Signale und Charts für alle Timeframes
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    signal_tf, df_tf = compute_signals(df_tf)
    st.metric(label="Signal", value=signal_tf)
    if not df_tf.empty:
        fig = go.Figure()
        fig.add_trace(go.Line(x=df_tf.index, y=df_tf['close'], name='Close'))
        fig.add_trace(go.Line(
            x=df_tf.index,
            y=df_tf.get('BBU_20_2.0', []),
            name='BB Upper',
            line=dict(dash='dash')
        ))
        fig.add_trace(go.Line(
            x=df_tf.index,
            y=df_tf.get('BBL_20_2.0', []),
            name='BB Lower',
            line=dict(dash='dash')
        ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Keine Daten verfügbar für dieses Zeitfenster.")
