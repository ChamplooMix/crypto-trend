import numpy as np
np.NaN = np.nan  # pandas_ta workaround

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from collections import Counter

# Seite konfigurieren
st.set_page_config(page_title="Crypto Signals (RSI + Bollinger)", layout="wide")

# Sidebar-Einstellungen
symbol = st.sidebar.selectbox("Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0)
limit = st.sidebar.slider("Kerzenanzahl", min_value=50, max_value=500, value=200)

timeframes = ["5m", "15m", "1h", "4h", "1d"]

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    exchanges = [
        ccxt.binance({'enableRateLimit': True}),
        ccxt.kraken({'enableRateLimit': True}),
    ]
    for exchange in exchanges:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception:
            continue
    st.error("Alle Exchanges nicht verfügbar. Bitte später erneut versuchen.")
    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def compute_signals(df: pd.DataFrame) -> str:
    if df.empty:
        return 'NEUTRAL'
    # RSI und Volumen-MA
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['vol_ma'] = df['volume'].rolling(20).mean()
    # Bollinger Bänder auf RSI
    bb_rsi = ta.bbands(df['RSI'], length=14, std=2)
    df = df.join(bb_rsi)
    last = df.iloc[-1]
    signals = []
    if last['RSI'] < 30 or last['RSI'] < last['BBL_14_2.0']:
        signals.append('BUY')
    if last['RSI'] > 70 or last['RSI'] > last['BBU_14_2.0']:
        signals.append('SHORT')
    if last['volume'] > last['vol_ma']:
        signals.append('BUY')
    cnt = Counter(signals)
    if cnt.get('BUY', 0) >= 2:
        return 'BUY'
    if cnt.get('SHORT', 0) >= 2:
        return 'SHORT'
    return 'NEUTRAL'

# Main: Chart für jedes Timeframe
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    signal_tf = compute_signals(df_tf)
    st.metric(label="Signal (RSI-BB)", value=signal_tf)
    if df_tf.empty:
        st.write("Keine Daten verfügbar.")
        continue
    # Plot: RSI und Bollinger-Bänder
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['RSI'], name='RSI'))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBU_14_2.0'], name='BB Upper', line=dict(dash='dash')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBM_14_2.0'], name='BB Middle', line=dict(color='yellow')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBL_14_2.0'], name='BB Lower', line=dict(dash='dash')))
    # Zonenlinien
    fig.add_hline(y=70, line=dict(color='red', dash='dash'), annotation_text='Overbought 70')
    fig.add_hline(y=50, line=dict(color='grey', dash='dot'), annotation_text='Mid 50')
    fig.add_hline(y=30, line=dict(color='green', dash='dash'), annotation_text='Oversold 30')
    fig.update_layout(
        yaxis=dict(range=[0,100]),
        title_text=f"{symbol} - RSI14 + BB(14,2) {tf}",
        legend=dict(orientation='h', x=0, y=1.1)
    )
    st.plotly_chart(fig, use_container_width=True)
