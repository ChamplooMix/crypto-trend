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
symbol = st.sidebar.selectbox("Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0)
limit = st.sidebar.slider("Kerzenanzahl", min_value=50, max_value=500, value=200)

timeframes = ["5m", "15m", "1h", "4h", "1d"]

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    """
    Versucht mehrfach, OHLCV von verschiedenen Exchanges zu laden.
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


def compute_signals(df: pd.DataFrame) -> str:
    """
    Gibt BUY, SHORT oder NEUTRAL basierend auf RSI-BB und Volumen.
    """
    if df.empty:
        return 'NEUTRAL'
    # RSI berechnen
    df['RSI'] = ta.rsi(df['close'], length=14)
    # Volumen-MA
    df['vol_ma'] = df['volume'].rolling(20).mean()
    # Bollinger Bänder auf RSI
    bb_rsi = ta.bbands(df['RSI'], length=14, std=2)
    df = df.join(bb_rsi)

    last = df.iloc[-1]
    signals = []
    # RSI unter unterer Band oder <30
    if last['RSI'] < 30 or last['RSI'] < last[bb_rsi.columns[0]]:
        signals.append('BUY')
    # RSI über oberer Band oder >70
    if last['RSI'] > 70 or last['RSI'] > last[bb_rsi.columns[2]]:
        signals.append('SHORT')
    # Volumenbestätigung
    if last['volume'] > last['vol_ma']:
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
    sig = compute_signals(df_tf)
    st.metric(label="Signal", value=sig)
    if df_tf.empty:
        st.write("Keine Daten verfügbar.")
        continue

    # Spalten für BB
    bb_cols = [c for c in df_tf.columns if c.startswith('BB') and '14_2.0' in c]
    bb_cols = sorted(bb_cols)  # [lower, middle, upper]
    lower, middle, upper = bb_cols

    # Plot erstellen
    fig = go.Figure()
    # RSI
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['RSI'], name='RSI', line=dict(color='cyan')))
    # BB-Linien
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf[upper], name='BB Upper', line=dict(color='red', dash='dash')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf[middle], name='BB Middle', line=dict(color='yellow')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf[lower], name='BB Lower', line=dict(color='green', dash='dash')))
    # Zonenlinien
    fig.add_hline(y=70, line=dict(color='red', dash='dash'), annotation_text='Overbought')
    fig.add_hline(y=50, line=dict(color='grey', dash='dot'), annotation_text='Mid 50')
    fig.add_hline(y=30, line=dict(color='green', dash='dash'), annotation_text='Oversold')

    fig.update_layout(
        title=f"{symbol} RSI14 + BB(14,2) [{tf}]",
        yaxis=dict(range=[0,100]),
        legend=dict(orientation='h', x=0, y=1.1)
    )

    st.plotly_chart(fig, use_container_width=True)
