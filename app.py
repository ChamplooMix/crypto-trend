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


def compute_signals(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """
    Berechnet Signal und erweitert DF um RSI, Bollinger-Bänder auf RSI und Volumen-MA.
    """
    if df.empty:
        return 'NEUTRAL', df
    # RSI (14)
    df['RSI'] = ta.rsi(df['close'], length=14)
    # Volumen-MA (20)
    df['vol_ma'] = df['volume'].rolling(20).mean()
    # Bollinger Bänder auf RSI (MA=14, std=2)
    bb = ta.bbands(df['RSI'], length=14, std=2)
    bb.columns = ['BBL_14_2.0', 'BBM_14_2.0', 'BBU_14_2.0']
    df = df.join(bb)
    # Letzte Werte
    last = df.iloc[-1]
    signals = []
    # Kaufsignal: RSI unter 30 oder unter unteres Band
    if last['RSI'] < 30 or last['RSI'] < last['BBL_14_2.0']:
        signals.append('BUY')
    # Shortsignal: RSI über 70 oder über oberes Band
    if last['RSI'] > 70 or last['RSI'] > last['BBU_14_2.0']:
        signals.append('SHORT')
    # Volumenbestätigung
    if last['volume'] > last['vol_ma']:
        signals.append('BUY')
    cnt = Counter(signals)
    if cnt.get('BUY', 0) >= 2:
        return 'BUY', df
    if cnt.get('SHORT', 0) >= 2:
        return 'SHORT', df
    return 'NEUTRAL', df

# Hauptanzeige: Chart pro Timeframe
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    sig, df_tf = compute_signals(df_tf)
    st.metric(label="Signal", value=sig)
    if df_tf.empty:
        st.write("Keine Daten verfügbar für dieses Zeitfenster.")
        continue
    # Plot: RSI und Bollinger Bands auf RSI
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['RSI'], name='RSI', line=dict(color='cyan')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBU_14_2.0'], name='BB Upper', line=dict(color='red', dash='dash')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBM_14_2.0'], name='BB Middle', line=dict(color='yellow')))
    fig.add_trace(go.Scatter(x=df_tf.index, y=df_tf['BBL_14_2.0'], name='BB Lower', line=dict(color='green', dash='dash')))
    # Zonenlinien
    fig.add_hline(y=70, line=dict(color='red', dash='dash'), annotation_text='Overbought 70')
    fig.add_hline(y=50, line=dict(color='grey', dash='dot'), annotation_text='Mid 50')
    fig.add_hline(y=30, line=dict(color='green', dash='dash'), annotation_text='Oversold 30')
    fig.update_layout(
        title=f"{symbol} RSI14 + BB(14,2) [{tf}]",
        yaxis=dict(range=[0,100]),
        legend=dict(orientation='h', x=0, y=1.1)
    )
    st.plotly_chart(fig, use_container_width=True)
