import numpy as np
np.NaN = np.nan  # pandas_ta workaround

import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import Counter

# Seite konfigurieren
st.set_page_config(page_title="Crypto Signals (RSI + BB + Vol)", layout="wide")

# Sidebar-Einstellungen
symbol = st.sidebar.selectbox(
    "Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT", "SUI/USDT", "SOL/USDT", "ARPA/USDT"],
    index=0
)
limit = st.sidebar.slider(
    "Kerzenanzahl", min_value=50, max_value=500, value=200
)

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
    if df.empty:
        return 'NEUTRAL'
    rsi = ta.rsi(df['close'], length=14)
    vol_ma = df['volume'].rolling(20).mean()
    bb = ta.bbands(rsi, length=14, std=2)
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

# Hauptanzeige: Chart pro Timeframe mit Volumenbars
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    sig = compute_signal(df_tf)
    st.metric(label="Signal", value=sig)
    if df_tf.empty:
        st.write("Keine Daten verfügbar für dieses Zeitfenster.")
        continue

    # Berechnungen
    rsi = ta.rsi(df_tf['close'], length=14)
    bb = ta.bbands(rsi, length=14, std=2)
    lower = bb.iloc[:, 0]
    middle = bb.iloc[:, 1]
    upper = bb.iloc[:, 2]

    # Subplots: RSI+BB und Volumen
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.02
    )

    # RSI und BB im oberen Subplot
    fig.add_trace(
        go.Scatter(x=rsi.index, y=rsi, name='RSI', line=dict(color='#40E0D0')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=upper.index, y=upper, name='BB Upper', line=dict(color='red')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=middle.index, y=middle, name='BB Middle', line=dict(color='yellow', dash='dot')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=lower.index, y=lower, name='BB Lower', line=dict(color='green')),
        row=1, col=1
    )
    # Zonenlinien
    fig.add_hline(y=70, line=dict(color='red', dash='dot'), row=1, col=1)
    fig.add_hline(y=50, line=dict(color='grey', dash='dot'), row=1, col=1)
    fig.add_hline(y=30, line=dict(color='green', dash='dot'), row=1, col=1)

    # Volumen als Balken im unteren Subplot
    fig.add_trace(
        go.Bar(x=df_tf.index, y=df_tf['volume'], name='Volumen', marker_color='lightgrey'),
        row=2, col=1
    )

    # Layout-Anpassungen
    fig.update_yaxes(range=[0,100], row=1, col=1, title_text='RSI')
    fig.update_yaxes(title_text='Volumen', row=2, col=1)
    fig.update_layout(
        title_text=f"{symbol} RSI14 + BB(14,2) + Volumen [{tf}]",
        showlegend=False,
        margin=dict(r=50, t=40)
    )

    st.plotly_chart(fig, use_container_width=True)
