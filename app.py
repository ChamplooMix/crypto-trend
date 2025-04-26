import numpy as np
np.NaN = np.nan  # pandas_ta workaround

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from collections import Counter

# Seite konfigurieren
st.set_page_config(page_title="Crypto Signals (RSI + BB)", layout="wide")

# Sidebar-Einstellungen
symbol = st.sidebar.selectbox("Symbol", ["BTC/USDT", "ETH/USDT", "SUI/USDT", "SOL/USDT", "XRP/USDT", "AVAX/USDT"], index=0)
limit = st.sidebar.slider("Kerzenanzahl", min_value=50, max_value=500, value=200)

timeframes = ["5m", "15m", "1h", "4h", "1d"]

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    """
    Versucht mehrfach OHLCV-Daten von verschiedenen Exchanges abzurufen.
    """
    exchanges = [
        ccxt.binance({'enableRateLimit': True}),
        ccxt.kraken({'enableRateLimit': True}),
    ]
    for exch in exchanges:
        try:
            data = exch.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
            df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception:
            continue
    st.error("Alle Exchanges nicht verfügbar. Bitte später erneut versuchen.")
    return pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])


def compute_signal(df: pd.DataFrame) -> str:
    """
    Berechnet das Signal aus RSI-BB und Volumen.
    """
    if df.empty:
        return 'NEUTRAL'
    # RSI (14)
    rsi = ta.rsi(df['close'], length=14)
    # Volumen-MA (20)
    vol_ma = df['volume'].rolling(20).mean()
    # Bollinger Bänder auf RSI (MA=14, std=2)
    bb = ta.bbands(rsi, length=14, std=2)
    # Letzte Werte
    last_rsi = rsi.iloc[-1]
    lower = bb.iloc[-1, 0]
    upper = bb.iloc[-1, 2]
    last_vol = df['volume'].iloc[-1]
    last_vol_ma = vol_ma.iloc[-1]

    signals = []
    if last_rsi < 30 or last_rsi < lower:
        signals.append('BUY')
    if last_rsi > 70 or last_rsi > upper:
        signals.append('SHORT')
    if last_vol > last_vol_ma:
        signals.append('BUY')
    cnt = Counter(signals)
    if cnt.get('BUY', 0) >= 2:
        return 'BUY'
    if cnt.get('SHORT', 0) >= 2:
        return 'SHORT'
    return 'NEUTRAL'

# Hauptanzeige: Chart pro Timeframe
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    sig = compute_signal(df_tf)
    st.metric(label="Signal", value=sig)
    if df_tf.empty:
        st.write("Keine Daten verfügbar für dieses Zeitfenster.")
        continue

    # RSI und Bollinger Bänder für Chart
    rsi = ta.rsi(df_tf['close'], length=14)
    bb = ta.bbands(rsi, length=14, std=2)
    lower = bb.iloc[:, 0]
    middle = bb.iloc[:, 1]
    upper = bb.iloc[:, 2]

    fig = go.Figure()
    # Graue Flächenfüllung zwischen Lower und Upper
    fig.add_trace(go.Scatter(
        x=list(upper.index) + list(lower.index[::-1]),
        y=list(upper) + list(lower[::-1]),
        fill='toself',
        fillcolor='lightgrey',
        line=dict(color='lightgrey'),
        hoverinfo='skip',
        showlegend=False
    ))
    # RSI-Linie
    fig.add_trace(go.Scatter(x=rsi.index, y=rsi, name='RSI', line=dict(color='blue')))
    # Bollinger-Bänder als solide Linien
    fig.add_trace(go.Scatter(x=upper.index, y=upper, name='BB Upper', line=dict(color='red')))
    fig.add_trace(go.Scatter(x=middle.index, y=middle, name='BB Middle', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=lower.index, y=lower, name='BB Lower', line=dict(color='green')))

    # Zonenlinien
    fig.add_hline(y=70, line=dict(color='red', dash='solid'), annotation_text='Overbought 70')
    fig.add_hline(y=50, line=dict(color='grey', dash='solid'), annotation_text='Mid 50')
    fig.add_hline(y=30, line=dict(color='green', dash='solid'), annotation_text='Oversold 30')

    fig.update_layout(
        title=f"{symbol} RSI14 + BB(14,2) [{tf}]",
        yaxis=dict(range=[0,100]),
        legend=dict(orientation='h', x=0, y=1.1)
    )

    st.plotly_chart(fig, use_container_width=True)
