# Project: Crypto Signals WebApp (Streamlit)

Project structure:
- app.py
- requirements.txt
- README.md
- .github/workflows/deploy.yml
- tests/test_signals.py

---
## README.md
```markdown
# Crypto Signals WebApp

Dieses Projekt implementiert eine Web-App mit Streamlit, die Kauf- und Short-Signale für Kryptowährungen auf Basis von Bollinger Bändern, Market Cypher B, RSI und Volumen berechnet.

## Features
- Signale für 5m, 15m, 60m, 240m und Daily
- Interaktive Charts mit Plotly
- Deployment via GitHub & Streamlit Community Cloud

## Quickstart
1. Repo klonen:
   ```bash
   git clone https://github.com/<dein-user>/crypto-signals-webapp.git
   cd crypto-signals-webapp
   ```
2. Virtuelle Umgebung (lokal, optional):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
4. Lokalen Server starten:
   ```bash
   streamlit run app.py
   ```

## Deployment
- Push auf `main` → Streamlit Community Cloud liest `requirements.txt` und deployed automatisch.
```
---
## requirements.txt
```text
streamlit
ccxt
pandas
numpy>=1.22.0
pandas_ta>=0.4.5
plotly
pytest
```
---
## app.py
```python
# Workaround: Sicherstellen, dass numpy das Attribut NaN exportiert,
# um Import-Fehler bei pandas_ta in manchen Versionen zu verhindern.
import numpy as np  # muss vor pandas_ta importiert werden
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
symbol = st.sidebar.selectbox("Symbol", ["BTC/USDT", "ETH/USDT", "ADA/USDT"], index=0)
timeframe = st.sidebar.radio("Timeframe", ["5m", "15m", "60m", "240m", "1d"], index=0)
limit = st.sidebar.slider("Kerzenanzahl", min_value=50, max_value=500, value=200)

@st.cache_data
def fetch_ohlcv(symbol: str, tf: str, lim: int) -> pd.DataFrame:
    exchange = ccxt.binance()
    data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def compute_signals(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    bb = df["close"].ta.bbands(length=20, std=2)
    df = df.join(bb)
    df["RSI"] = df["close"].ta.rsi(14)
    df["vol_ma"] = df["volume"].rolling(20).mean()
    last = df.iloc[-1]
    signals: list[str] = []
    if last["close"] < last["BBL_20_2.0"]:
        signals.append("BUY")
    if last["close"] > last["BBU_20_2.0"]:
        signals.append("SHORT")
    if last["RSI"] < 30:
        signals.append("BUY")
    if last["RSI"] > 70:
        signals.append("SHORT")
    if last["volume"] > last["vol_ma"]:
        signals.append("BUY")
    cnt = Counter(signals)
    if cnt.get("BUY", 0) >= 2:
        overall = "BUY"
    elif cnt.get("SHORT", 0) >= 2:
        overall = "SHORT"
    else:
        overall = "NEUTRAL"
    return overall, df

# Daten holen & Signale berechnen
df = fetch_ohlcv(symbol, timeframe, limit)
signal, df = compute_signals(df)

# Dashboard rendern
st.title(f"📊 Signals: {symbol} [{timeframe}]")
col1, col2 = st.columns((3, 1))
with col1:
    fig = go.Figure()
    fig.add_trace(go.Line(x=df.index, y=df["close"], name="Close"))
    fig.add_trace(go.Line(x=df.index, y=df["BBU_20_2.0"], name="BB Upper", line=dict(dash="dash")))
    fig.add_trace(go.Line(x=df.index, y=df["BBL_20_2.0"], name="BB Lower", line=dict(dash="dash")))
    st.plotly_chart(fig, use_container_width=True)
with col2:
    st.metric(label="Overall Signal", value=signal)
    st.markdown("---")
    st.write("**Details:**")
    st.write(f"RSI: {df.iloc[-1]['RSI']:.2f}")
    st.write(f"Volumen vs. MA: {df.iloc[-1]['volume']:.0f} vs. {df.iloc[-1]['vol_ma']:.0f}")
```
---
## .github/workflows/deploy.yml
```yaml
name: Deploy to Streamlit

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Deploy to Streamlit Cloud
        env:
          STREAMLIT_TOKEN: ${{ secrets.STREAMLIT_TOKEN }}
        run: |
          streamlit run app.py --server.port $${{ env.PORT }}
```
---
## tests/test_signals.py
```python
import pandas as pd
from app import compute_signals

def test_compute_signals_constant_data():
    # konstante Daten => NEUTRAL
    idx = pd.date_range(start='2025-01-01', periods=30, freq='T')
    df = pd.DataFrame({
        'timestamp': idx,
        'open': [100]*30,
        'high': [100]*30,
        'low': [100]*30,
        'close': [100]*30,
        'volume': [100]*30
    }).set_index('timestamp')
    signal, out_df = compute_signals(df)
    assert signal == 'NEUTRAL'
    assert 'RSI' in out_df.columns
```
