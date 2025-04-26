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
st.set_page_config(page_title="Crypto Signals", layout="wide")

# Sidebar-Einstellungen
symbol = st.sidebar.selectbox(
    "Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0
)
limit = st.sidebar.slider(
    "Kerzenanzahl", min_value=50, max_value=500, value=200
)

# Unterstützte Timeframes
timeframes = ["5m", "15m", "1h", "4h", "1d"]

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    """
    Versucht mehrere Exchanges als Fallback und liefert OHLCV-Daten.
    """
    exchanges = [
        ccxt.binance({'enableRateLimit': True}),
        ccxt.kraken({'enableRateLimit': True}),
    ]
    for exchange in exchanges:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
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
    Berechnet Kauf/Short-Signal basierend auf Bollinger Bändern, RSI und Volumen.
    """
    if df.empty:
        return 'NEUTRAL', df
    # Bollinger Bänder (MA=14, Std=2)
    bb_df = ta.bbands(df['close'], length=14, std=2)
    df = df.join(bb_df)
    # RSI (14)
    df['RSI'] = ta.rsi(df['close'], length=14)
    # Volumen-MA (20)
    df['vol_ma'] = df['volume'].rolling(20).mean()
    last = df.iloc[-1]

    signals = []
    if last['close'] < last['BBL_14_2.0']:
        signals.append('BUY')
    if last['close'] > last['BBU_14_2.0']:
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


# Hauptansicht: vereinigte Charts für alle Timeframes
for tf in timeframes:
    st.subheader(f"Zeitfenster: {tf}")
    df_tf = fetch_ohlcv(symbol, tf, limit)
    signal_tf, df_tf = compute_signals(df_tf)
    st.metric(label="Signal", value=signal_tf)

    if not df_tf.empty:
        # Kombinierter Chart mit Primär-Achse Price+BB und Sekundär-Achse RSI
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # Preis und Bollinger Bänder
        fig.add_trace(
            go.Line(x=df_tf.index, y=df_tf['close'], name='Close'),
            secondary_y=False
        )
        fig.add_trace(
            go.Line(x=df_tf.index, y=df_tf['BBU_14_2.0'], name='BB Upper', line=dict(dash='dash')),
            secondary_y=False
        )
        fig.add_trace(
            go.Line(x=df_tf.index, y=df_tf['BBL_14_2.0'], name='BB Lower', line=dict(dash='dash')),
            secondary_y=False
        )
        # RSI auf sekundärer Achse
        fig.add_trace(
            go.Line(x=df_tf.index, y=df_tf['RSI'], name='RSI'),
            secondary_y=True
        )
        # Überkauft/überverkauft Linien
        fig.add_hline(y=70, line=dict(color='red', dash='dash'), annotation_text='Overbought', secondary_y=True)
        fig.add_hline(y=50, line=dict(color='grey', dash='dot'), annotation_text='Mid 50', secondary_y=True)
        fig.add_hline(y=30, line=dict(color='green', dash='dash'), annotation_text='Oversold', secondary_y=True)
        # Achsen-Beschriftung
        fig.update_yaxes(title_text='Preis', secondary_y=False)
        fig.update_yaxes(title_text='RSI', range=[0,100], secondary_y=True)
        fig.update_layout(title=f"{symbol} {tf}", legend=dict(orientation='h', x=0, y=-0.2))

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Keine Daten verfügbar für dieses Zeitfenster.")
```
