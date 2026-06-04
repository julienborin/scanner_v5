# -*- coding: utf-8 -*-
# ============================================================
# TRADING SCANNER v5.0 (ULTIMATE EDITION)
# Best of: Streamlit + pandas-ta + ccxt + LightGBM + Telegram
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import pytz
import requests
import json
import os
import warnings
warnings.filterwarnings('ignore')

# --- NOUVEAUX IMPORTS v5.0 ---
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

st.set_page_config(page_title="Trading Scanner v5.0", page_icon="🧠", layout="wide")

# ══════════════════════════════════════════════════════════
# PERSISTANCE CONFIGURATION
# ══════════════════════════════════════════════════════════

CONFIG_FILE = "scanner_config.json"

def charger_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def sauver_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# ══════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════

if "signaux_detectes" not in st.session_state:
    st.session_state.signaux_detectes = {}
if "historique_signaux" not in st.session_state:
    st.session_state.historique_signaux = []

AVATRADE_LINK = "https://www.avatrade.com/trading-account/login"

ACTIFS = {
    "🥇 Or (Gold)": "GC=F",
    "🥈 Argent (Silver)": "SI=F",
    "💶 EUR/CHF": "EURCHF=X",
    "💵 EUR/USD": "EURUSD=X",
    "₿ Bitcoin": "BTC-USD",
    "🍎 Apple": "AAPL",
    "💻 Microsoft": "MSFT",
    "🚗 Tesla": "TSLA",
    "⟠ Ethereum": "ETH-USD",
    "⬜ Platine": "PL=F",
    "🛢️ Pétrole": "CL=F",
    "📊 S&P 500": "^GSPC",
    "💎 Solana": "SOL-USD",
    "🔗 Chainlink": "LINK-USD",
    "🟡 BNB": "BNB-USD",
    "📈 Nasdaq": "^IXIC",
}

# Tickers ccxt pour données temps réel
CCXT_SYMBOLS = {
    "BTC-USD": "BTC/USDT",
    "ETH-USD": "ETH/USDT",
    "SOL-USD": "SOL/USDT",
    "LINK-USD": "LINK/USDT",
    "BNB-USD": "BNB/USDT",
}

POIDS = {
    "RSI": 2.0,
    "MACD": 2.0,
    "STOCH": 1.0,
    "FIBO": 1.5,
    "MA200": 1.5,
    "VOLUME": 1.5,
    "BOLLINGER": 1.5,
    "DIVERGENCE": 2.0,
    "OR_BTC": 1.5,
    "MACRO": 2.5,
    "SENTIMENT": 2.0,
    "NEWS_NLP": 2.0,
    "ONCHAIN": 2.5,
    "ICHIMOKU": 2.0,       # NOUVEAU v5.0
    "SUPPORTS_RES": 1.5,   # NOUVEAU v5.0
    "ML_PREDICTION": 3.0,  # NOUVEAU v5.0
    "VWAP": 1.0,           # NOUVEAU v5.0
    "ORDER_FLOW": 1.5,     # NOUVEAU v5.0
}

SEUIL_ADX = 25

ACTIF_CATEGORIE = {
    "🥇 Or (Gold)": "matieres_premieres",
    "🥈 Argent (Silver)": "matieres_premieres",
    "💶 EUR/CHF": "forex",
    "💵 EUR/USD": "forex",
    "₿ Bitcoin": "crypto",
    "🍎 Apple": "actions",
    "💻 Microsoft": "actions",
    "🚗 Tesla": "actions",
    "⟠ Ethereum": "crypto",
    "⬜ Platine": "matieres_premieres",
    "🛢️ Pétrole": "matieres_premieres",
    "📊 S&P 500": "actions",
    "💎 Solana": "crypto",
    "🔗 Chainlink": "crypto",
    "🟡 BNB": "crypto",
    "📈 Nasdaq": "actions",
}

MACRO_SENSITIVITY = {
    "crypto": 0.9,
    "matieres_premieres": 0.85,
    "forex": 0.7,
    "actions": 0.75,
}

HORAIRES_OPTIMAUX = {
    "forex": {
        "nom": "Forex",
        "achat_horaire": "8h-10h ou 14h-16h",
        "vente_horaire": "8h-10h ou 14h-16h",
        "eviter": "12h-13h et apres 20h",
        "heures_favorables_achat": [8, 9, 10, 14, 15, 16],
        "heures_favorables_vente": [8, 9, 10, 14, 15, 16],
        "heures_a_eviter": [12, 13, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5],
    },
    "crypto": {
        "nom": "Crypto",
        "achat_horaire": "6h-8h (creux matinal)",
        "vente_horaire": "15h-17h (pic US)",
        "eviter": "22h-2h",
        "heures_favorables_achat": [6, 7, 8],
        "heures_favorables_vente": [15, 16, 17],
        "heures_a_eviter": [22, 23, 0, 1, 2],
    },
    "actions": {
        "nom": "Actions US",
        "achat_horaire": "15h45-16h15 CET",
        "vente_horaire": "19h-21h CET",
        "eviter": "15h30-15h45 (ouverture volatile)",
        "heures_favorables_achat": [15, 16],
        "heures_favorables_vente": [19, 20, 21],
        "heures_a_eviter": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    },
    "matieres_premieres": {
        "nom": "Matieres premieres",
        "achat_horaire": "8h-10h ou 14h30",
        "vente_horaire": "16h-18h",
        "eviter": "Apres 21h",
        "heures_favorables_achat": [8, 9, 10, 14, 15],
        "heures_favorables_vente": [16, 17, 18],
        "heures_a_eviter": [21, 22, 23, 0, 1, 2, 3, 4, 5],
    },
}

NEWS_KEYWORDS = {
    "GC=F": ["gold price", "gold market", "precious metals", "XAUUSD"],
    "SI=F": ["silver price", "silver market", "XAGUSD"],
    "EURCHF=X": ["EUR CHF", "euro franc suisse", "SNB", "swiss franc"],
    "EURUSD=X": ["EUR USD", "euro dollar", "Fed rates", "ECB"],
    "BTC-USD": ["bitcoin", "BTC", "crypto market", "bitcoin ETF", "halving"],
    "ETH-USD": ["ethereum", "ETH", "DeFi", "ethereum ETF"],
    "SOL-USD": ["solana", "SOL token", "solana DeFi"],
    "AAPL": ["Apple stock", "Apple earnings", "AAPL", "iPhone"],
    "MSFT": ["Microsoft stock", "Microsoft AI", "MSFT", "Azure"],
    "TSLA": ["Tesla stock", "Elon Musk", "TSLA", "EV market"],
    "CL=F": ["oil price", "crude oil", "OPEC", "WTI", "brent"],
    "^GSPC": ["S&P 500", "stock market", "Wall Street", "Fed"],
    "PL=F": ["platinum price", "platinum market"],
    "LINK-USD": ["chainlink", "LINK", "oracle blockchain"],
    "BNB-USD": ["BNB", "binance coin", "binance"],
    "^IXIC": ["nasdaq", "tech stocks", "nasdaq composite"],
}

BULLISH_KEYWORDS = [
    "rally", "surge", "breakout", "bullish", "all-time high",
    "inflows", "accumulation", "upgrade", "beat expectations",
    "rate cut", "stimulus", "adoption", "approval", "record high",
    "institutional buying", "strong demand", "outperform",
]

BEARISH_KEYWORDS = [
    "crash", "plunge", "selloff", "bearish", "dump", "liquidation",
    "outflows", "hack", "ban", "regulation", "hawkish", "rate hike",
    "recession", "default", "downgrade", "warning", "fear",
    "bankruptcy", "investigation", "lawsuit",
]


# ══════════════════════════════════════════════════════════
# TELEGRAM ALERTS (NOUVEAU v5.0)
# ══════════════════════════════════════════════════════════

def envoyer_telegram(message, bot_token, chat_id):
    """Envoie une alerte Telegram instantanée"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False


def formater_alerte_telegram(resultat):
    """Formate un signal pour Telegram"""
    r = resultat
    emoji = "🟢" if r['action'] == "ACHAT" else "🔴"
    direction = "LONG" if r['action'] == "ACHAT" else "SHORT"
    score = r['score_achat'] if r['action'] == "ACHAT" else r['score_vente']

    msg = f"""
{emoji} <b>SIGNAL {direction}</b> — {r['nom']}

💰 Prix: {round(r['prix'], 2)}
📊 Score: {round(score, 1)}/{round(r['score_max'], 0)}
📈 ADX: {round(r['adx'], 1)}
"""
    if r.get('sl_tp'):
        msg += f"""
🛑 SL: {round(r['sl_tp']['stop_loss'], 2)} (-{round(r['sl_tp']['risque_pct'], 2)}%)
🎯 TP: {round(r['sl_tp']['take_profit'], 2)} (+{round(r['sl_tp']['reward_pct'], 2)}%)
📐 R:R = 1:{round(r['sl_tp']['ratio_rr'], 1)}
"""
    if r.get('ml_prediction'):
        msg += f"\n🤖 ML: {round(r['ml_prediction']['proba'] * 100, 0)}% confiance"

    msg += f"\n⏰ {datetime.now(pytz.timezone('Europe/Zurich')).strftime('%H:%M:%S')}"
    return msg


# ══════════════════════════════════════════════════════════
# CCXT — DONNÉES TEMPS RÉEL (NOUVEAU v5.0)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner="⚡ Données temps réel...")
def get_realtime_data_ccxt(symbol, timeframe='1d', limit=365):
    """Récupère les données via ccxt (Binance) — plus rapide et fiable que Yahoo pour crypto"""
    if not HAS_CCXT:
        return None
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except:
        return None


@st.cache_data(ttl=30, show_spinner="📊 Order book...")
def get_order_book_imbalance(symbol):
    """Analyse le carnet d'ordres pour détecter la pression achat/vente"""
    if not HAS_CCXT:
        return None
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ob = exchange.fetch_order_book(symbol, limit=50)
        bids_volume = sum([b[1] for b in ob['bids'][:20]])
        asks_volume = sum([a[1] for a in ob['asks'][:20]])
        total = bids_volume + asks_volume
        if total == 0:
            return None
        imbalance = (bids_volume - asks_volume) / total  # -1 à +1
        bid_wall = max(ob['bids'][:20], key=lambda x: x[1]) if ob['bids'] else None
        ask_wall = max(ob['asks'][:20], key=lambda x: x[1]) if ob['asks'] else None
        return {
            'imbalance': imbalance,
            'bids_volume': bids_volume,
            'asks_volume': asks_volume,
            'bid_wall': bid_wall,
            'ask_wall': ask_wall,
            'spread_pct': ((ob['asks'][0][0] - ob['bids'][0][0]) / ob['bids'][0][0]) * 100 if ob['bids'] and ob['asks'] else 0
        }
    except:
        return None


# ══════════════════════════════════════════════════════════
# INDICATEURS TECHNIQUES v5.0 (pandas-ta + custom)
# ══════════════════════════════════════════════════════════

def calc_rsi(series, period=14):
    """RSI — fallback si pandas-ta pas dispo"""
    if HAS_PANDAS_TA:
        result = ta.rsi(series, length=period)
        return result if result is not None else _calc_rsi_manual(series, period)
    return _calc_rsi_manual(series, period)

def _calc_rsi_manual(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_stochastique(data, period=14):
    if HAS_PANDAS_TA:
        stoch = ta.stoch(data['High'], data['Low'], data['Close'], k=period)
        if stoch is not None and not stoch.empty:
            cols = stoch.columns.tolist()
            return stoch[cols[0]], stoch[cols[1]]
    low = data['Low'].rolling(period).min()
    high = data['High'].rolling(period).max()
    k = ((data['Close'] - low) / (high - low)) * 100
    d = k.rolling(3).mean()
    return k, d

def calc_macd(close):
    if HAS_PANDAS_TA:
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            cols = macd_df.columns.tolist()
            return macd_df[cols[0]], macd_df[cols[2]]  # MACD, Signal
    ema_12 = close.ewm(span=12).mean()
    ema_26 = close.ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    return macd, signal

def calc_fibonacci(data, period=50):
    high = data['High'].rolling(period).max()
    low = data['Low'].rolling(period).min()
    fib_618 = high - 0.618 * (high - low)
    fib_382 = high - 0.382 * (high - low)
    fib_236 = high - 0.236 * (high - low)
    fib_786 = high - 0.786 * (high - low)
    return fib_618, fib_382, fib_236, fib_786

def calc_ma200(close):
    return close.rolling(200).mean()

def calc_adx(data, period=14):
    if HAS_PANDAS_TA:
        adx_df = ta.adx(data['High'], data['Low'], data['Close'], length=period)
        if adx_df is not None and not adx_df.empty:
            return adx_df.iloc[:, 0]  # ADX column
    # Fallback manual
    high = data['High']
    low = data['Low']
    close = data['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0).where(plus_dm > 0, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0).where(minus_dm > 0, 0)
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    return adx

def calc_atr(data, period=14):
    if HAS_PANDAS_TA:
        result = ta.atr(data['High'], data['Low'], data['Close'], length=period)
        if result is not None:
            return result
    high = data['High']
    low = data['Low']
    close = data['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calc_bollinger(close, period=20, std_mult=2):
    if HAS_PANDAS_TA:
        bb = ta.bbands(close, length=period, std=std_mult)
        if bb is not None and not bb.empty:
            cols = bb.columns.tolist()
            upper = bb[cols[2]]  # BBU
            lower = bb[cols[0]]  # BBL
            mid = bb[cols[1]]    # BBM
            bandwidth = ((upper - lower) / mid) * 100
            return upper, lower, mid, bandwidth
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + (std_mult * std)
    lower = sma - (std_mult * std)
    bandwidth = ((upper - lower) / sma) * 100
    return upper, lower, sma, bandwidth


# ══════════════════════════════════════════════════════════
# NOUVEAUX INDICATEURS v5.0
# ══════════════════════════════════════════════════════════

def calc_ichimoku(data):
    """Ichimoku Cloud — indicateur japonais puissant"""
    if HAS_PANDAS_TA:
        ichi = ta.ichimoku(data['High'], data['Low'], data['Close'])
        if ichi is not None and len(ichi) == 2:
            return ichi[0]  # DataFrame with all Ichimoku lines
    # Manual calculation
    high = data['High']
    low = data['Low']
    close = data['Close']

    # Tenkan-sen (Conversion Line) — 9 periods
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    # Kijun-sen (Base Line) — 26 periods
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    # Senkou Span A (Leading Span A)
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    # Senkou Span B (Leading Span B)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    # Chikou Span (Lagging Span)
    chikou = close.shift(-26)

    return pd.DataFrame({
        'tenkan': tenkan,
        'kijun': kijun,
        'senkou_a': senkou_a,
        'senkou_b': senkou_b,
        'chikou': chikou
    }, index=data.index)


def calc_vwap(data):
    """VWAP — Volume Weighted Average Price"""
    if HAS_PANDAS_TA:
        result = ta.vwap(data['High'], data['Low'], data['Close'], data['Volume'])
        if result is not None:
            return result
    # Manual VWAP (daily reset approximation)
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    vwap = (typical_price * data['Volume']).cumsum() / data['Volume'].cumsum()
    return vwap


def detecter_supports_resistances(data, window=20, nb_levels=5):
    """Détecte les supports et résistances clés"""
    close = data['Close'].values
    high = data['High'].values
    low = data['Low'].values

    supports = []
    resistances = []

    for i in range(window, len(close) - window):
        # Support : point bas local
        if low[i] == min(low[i-window:i+window+1]):
            supports.append(low[i])
        # Résistance : point haut local
        if high[i] == max(high[i-window:i+window+1]):
            resistances.append(high[i])

    # Regrouper les niveaux proches (clustering)
    supports = _cluster_levels(supports, tolerance=0.02)
    resistances = _cluster_levels(resistances, tolerance=0.02)

    # Garder les plus pertinents (proches du prix actuel)
    prix_actuel = close[-1]
    supports = sorted(supports, key=lambda x: abs(x - prix_actuel))[:nb_levels]
    resistances = sorted(resistances, key=lambda x: abs(x - prix_actuel))[:nb_levels]

    return sorted(supports), sorted(resistances)


def _cluster_levels(levels, tolerance=0.02):
    """Regroupe les niveaux proches"""
    if not levels:
        return []
    levels = sorted(levels)
    clustered = [levels[0]]
    for level in levels[1:]:
        if (level - clustered[-1]) / clustered[-1] > tolerance:
            clustered.append(level)
        else:
            clustered[-1] = (clustered[-1] + level) / 2  # Moyenne
    return clustered


def detecter_divergences(data, lookback=14):
    """Détection améliorée des divergences RSI et MACD"""
    divergences = {'rsi': None, 'macd': None, 'force': 0}
    if len(data) < lookback + 5:
        return divergences

    close = data['Close'].values
    rsi = data['RSI'].values
    macd = data['MACD'].values

    # Chercher les 2 derniers creux et sommets
    try:
        recent = close[-lookback:]
        recent_rsi = rsi[-lookback:]
        recent_macd = macd[-lookback:]

        # Divergence haussière (prix fait lower low, RSI fait higher low)
        prix_lows = []
        rsi_lows = []
        for i in range(2, lookback - 2):
            if recent[i] <= min(recent[i-2:i]) and recent[i] <= min(recent[i+1:i+3]):
                prix_lows.append((i, recent[i], recent_rsi[i], recent_macd[i]))

        if len(prix_lows) >= 2:
            last = prix_lows[-1]
            prev = prix_lows[-2]
            # Prix lower low + RSI higher low = divergence haussière
            if last[1] < prev[1] and last[2] > prev[2]:
                divergences['rsi'] = "HAUSSIERE"
                divergences['force'] = abs(last[2] - prev[2])
            if last[1] < prev[1] and last[3] > prev[3]:
                divergences['macd'] = "HAUSSIERE"
                divergences['force'] = max(divergences['force'], abs(last[3] - prev[3]))

        # Divergence baissière (prix fait higher high, RSI fait lower high)
        prix_highs = []
        for i in range(2, lookback - 2):
            if recent[i] >= max(recent[i-2:i]) and recent[i] >= max(recent[i+1:i+3]):
                prix_highs.append((i, recent[i], recent_rsi[i], recent_macd[i]))

        if len(prix_highs) >= 2:
            last = prix_highs[-1]
            prev = prix_highs[-2]
            if last[1] > prev[1] and last[2] < prev[2]:
                divergences['rsi'] = "BAISSIERE"
                divergences['force'] = abs(last[2] - prev[2])
            if last[1] > prev[1] and last[3] < prev[3]:
                divergences['macd'] = "BAISSIERE"
                divergences['force'] = max(divergences['force'], abs(last[3] - prev[3]))
    except:
        pass

    return divergences


# ══════════════════════════════════════════════════════════
# MACHINE LEARNING v5.0 (LightGBM + Feature Engineering)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner="🤖 Entraînement ML...")
def entrainer_modele_ml(ticker, data):
    """Entraîne un modèle ML pour prédire le mouvement à 5 jours"""
    try:
        if len(data) < 120:
            return None

        df = data.copy()

        # --- FEATURE ENGINEERING ---
        # Retours
        df['return_1d'] = df['Close'].pct_change(1)
        df['return_3d'] = df['Close'].pct_change(3)
        df['return_5d'] = df['Close'].pct_change(5)
        df['return_10d'] = df['Close'].pct_change(10)

        # Volatilité
        df['volatility_10'] = df['return_1d'].rolling(10).std()
        df['volatility_20'] = df['return_1d'].rolling(20).std()

        # Momentum
        df['momentum_10'] = df['Close'] / df['Close'].shift(10) - 1
        df['momentum_20'] = df['Close'] / df['Close'].shift(20) - 1

        # Prix relatif aux MA
        df['price_vs_ma20'] = df['Close'] / df['Close'].rolling(20).mean() - 1
        df['price_vs_ma50'] = df['Close'] / df['Close'].rolling(50).mean() - 1

        # Volume relatif
        df['vol_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()

        # RSI momentum
        df['rsi_change'] = df['RSI'].diff(3)

        # MACD momentum
        df['macd_hist'] = df['MACD'] - df['MACD_Signal']
        df['macd_hist_change'] = df['macd_hist'].diff(3)

        # Bollinger position
        bb_range = df['BB_Upper'] - df['BB_Lower']
        df['bb_position'] = (df['Close'] - df['BB_Lower']) / bb_range

        # ATR relatif
        df['atr_pct'] = df['ATR'] / df['Close'] * 100

        # --- TARGET ---
        # 1 si le prix monte de >1% dans les 5 prochains jours
        df['target'] = (df['Close'].shift(-5) / df['Close'] - 1 > 0.01).astype(int)

        # Features
        features = [
            'RSI', 'Stoch_K', 'ADX', 'return_1d', 'return_3d', 'return_5d',
            'return_10d', 'volatility_10', 'volatility_20', 'momentum_10',
            'momentum_20', 'price_vs_ma20', 'price_vs_ma50', 'vol_ratio',
            'rsi_change', 'macd_hist', 'macd_hist_change', 'bb_position', 'atr_pct'
        ]

        # Nettoyer
        df_clean = df[features + ['target']].dropna()
        if len(df_clean) < 60:
            return None

        X = df_clean[features]
        y = df_clean['target']

        # Train/test split temporel (80/20)
        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]

        # Scaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Modèle
        if HAS_LGBM:
            model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                min_child_samples=10, verbose=-1
            )
        else:
            model = GradientBoostingClassifier(
                n_estimators=150, max_depth=5, learning_rate=0.05,
                subsample=0.8
            )

        model.fit(X_train_scaled, y_train)

        # Évaluation
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)

        # Prédiction actuelle
        X_current = scaler.transform(X.iloc[[-1]])
        proba = model.predict_proba(X_current)[0]

        # Feature importance
        if HAS_LGBM:
            importance = dict(zip(features, model.feature_importances_))
        else:
            importance = dict(zip(features, model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            'proba_hausse': proba[1],
            'proba_baisse': proba[0],
            'accuracy': accuracy,
            'direction': "ACHAT" if proba[1] > 0.55 else "VENTE" if proba[0] > 0.55 else "NEUTRE",
            'confiance': max(proba),
            'top_features': top_features,
            'nb_samples': len(X_train),
        }
    except Exception as e:
        return None


# ══════════════════════════════════════════════════════════
# MOTEUR MACRO v5.0 (identique v4.1 + améliorations)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner="🌍 Chargement macro...")
def fetch_macro_data():
    data = {}
    details = []

    def fetch_single(ticker, period="60d"):
        d = yf.download(ticker, period=period, interval="1d", progress=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        return d

    # Parallel fetching pour accélérer
    tickers_macro = {
        'dxy': "DX-Y.NYB",
        'oil': "CL=F",
        'tnx': "^TNX",
        'vix': "^VIX",
        'spy': "SPY",
        'ibit': "IBIT",
    }

    fetched = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_single, t): name for name, t in tickers_macro.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                fetched[name] = future.result()
            except:
                fetched[name] = pd.DataFrame()

    # 1. DOLLAR INDEX
    try:
        dxy = fetched.get('dxy', pd.DataFrame())
        if len(dxy) >= 20:
            ma20 = float(dxy['Close'].rolling(20).mean().iloc[-1])
            prix = float(dxy['Close'].iloc[-1])
            var_5j = float((dxy['Close'].iloc[-1] - dxy['Close'].iloc[-5]) / dxy['Close'].iloc[-5] * 100)
            score = 0
            if prix < ma20: score += 3
            if var_5j < -0.5: score += 2
            elif var_5j > 0.5: score -= 2
            if prix > ma20: score -= 3
            data['dxy'] = {'prix': prix, 'ma20': ma20, 'var_5j': var_5j, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} Dollar: {round(prix, 1)} (5j: {round(var_5j, 1)}%)")
    except:
        data['dxy'] = {'score': 0}

    # 2. PÉTROLE
    try:
        oil = fetched.get('oil', pd.DataFrame())
        if len(oil) >= 20:
            prix = float(oil['Close'].iloc[-1])
            ma20 = float(oil['Close'].rolling(20).mean().iloc[-1])
            var_5j = float((oil['Close'].iloc[-1] - oil['Close'].iloc[-5]) / oil['Close'].iloc[-5] * 100)
            score = 0
            if prix > ma20: score += 2
            if var_5j > 2: score += 2
            elif var_5j < -2: score -= 2
            if prix > 90: score += 2
            elif prix < 65: score -= 2
            data['oil'] = {'prix': prix, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} Pétrole ${round(prix, 1)}")
    except:
        data['oil'] = {'score': 0}

    # 3. TAUX 10 ANS
    try:
        tnx = fetched.get('tnx', pd.DataFrame())
        if len(tnx) >= 20:
            prix = float(tnx['Close'].iloc[-1])
            ma20 = float(tnx['Close'].rolling(20).mean().iloc[-1])
            score = 0
            if prix < ma20: score += 3
            elif prix > ma20: score -= 3
            if prix > 4.5: score -= 2
            elif prix < 3.5: score += 2
            data['yields'] = {'prix': prix, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} Taux 10Y: {round(prix, 2)}%")
    except:
        data['yields'] = {'score': 0}

    # 4. VIX
    try:
        vix = fetched.get('vix', pd.DataFrame())
        if len(vix) >= 5:
            prix = float(vix['Close'].iloc[-1])
            score = 0
            if prix > 30: score -= 5
            elif prix > 25: score -= 3
            elif prix < 15: score += 3
            elif prix < 18: score += 1
            data['vix'] = {'prix': prix, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} VIX: {round(prix, 1)}")
    except:
        data['vix'] = {'score': 0}

    # 5. FEAR & GREED
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if r.status_code == 200:
            fg_value = int(r.json()["data"][0]["value"])
            fg_label = r.json()["data"][0]["value_classification"]
            score = (fg_value - 50) / 5
            data['fear_greed'] = {'value': fg_value, 'label': fg_label, 'score': max(-10, min(10, score))}
            details.append(f"😱 Fear & Greed: {fg_value}/100 ({fg_label})")
        else:
            data['fear_greed'] = {'value': 50, 'score': 0}
    except:
        data['fear_greed'] = {'value': 50, 'score': 0}

    # 6. FUNDING RATE
    try:
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        r = requests.get(url, params={"symbol": "BTCUSDT", "limit": 10}, timeout=5)
        if r.status_code == 200:
            rates = [float(x["fundingRate"]) for x in r.json()]
            current_rate = rates[-1]
            score = 0
            if current_rate > 0.0005: score -= 3
            elif current_rate < -0.0001: score += 3
            elif current_rate < 0: score += 1
            data['funding'] = {'current': current_rate * 100, 'score': max(-10, min(10, score))}
            details.append(f"📊 Funding BTC: {round(current_rate * 100, 4)}%")
    except:
        data['funding'] = {'current': 0, 'score': 0}

    # 7. ETF BTC
    try:
        ibit = fetched.get('ibit', pd.DataFrame())
        if len(ibit) >= 5:
            price_change = float((ibit['Close'].iloc[-1] - ibit['Close'].iloc[-5]) / ibit['Close'].iloc[-5] * 100)
            score = 0
            if price_change > 2: score += 4
            elif price_change > 0: score += 1
            elif price_change < -2: score -= 3
            elif price_change < 0: score -= 1
            data['etf_btc'] = {'price_change': price_change, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} ETF BTC: {round(price_change, 1)}% (5j)")
    except:
        data['etf_btc'] = {'score': 0}

    # 8. S&P 500
    try:
        spy = fetched.get('spy', pd.DataFrame())
        if len(spy) >= 20:
            prix = float(spy['Close'].iloc[-1])
            ma20 = float(spy['Close'].rolling(20).mean().iloc[-1])
            var_5j = float((spy['Close'].iloc[-1] - spy['Close'].iloc[-5]) / spy['Close'].iloc[-5] * 100)
            score = 0
            if prix > ma20: score += 3
            elif prix < ma20: score -= 3
            if var_5j > 2: score += 2
            elif var_5j < -2: score -= 2
            data['spy'] = {'prix': prix, 'var_5j': var_5j, 'score': max(-10, min(10, score))}
            emoji = "✅" if score > 0 else "❌"
            details.append(f"{emoji} S&P 500: {round(var_5j, 1)}% (5j)")
    except:
        data['spy'] = {'score': 0}

    # 9. OPEN INTEREST BTC (NOUVEAU v5.0)
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/openInterest", params={"symbol": "BTCUSDT"}, timeout=5)
        if r.status_code == 200:
            oi = float(r.json()["openInterest"])
            data['open_interest'] = {'value': oi}
            details.append(f"📈 OI BTC: {round(oi, 0)} BTC")
    except:
        pass

    return data, details


def calculate_macro_score(macro_data, ticker, categorie):
    sensitivity = MACRO_SENSITIVITY.get(categorie, 0.7)
    if categorie == "crypto":
        weights = {'dxy': 0.15, 'yields': 0.10, 'vix': 0.10, 'fear_greed': 0.25, 'funding': 0.20, 'etf_btc': 0.15, 'spy': 0.05}
    elif categorie == "matieres_premieres":
        weights = {'dxy': 0.30, 'yields': 0.25, 'oil': 0.10, 'vix': 0.10, 'spy': 0.15, 'fear_greed': 0.10}
    elif categorie == "forex":
        weights = {'dxy': 0.35, 'yields': 0.25, 'vix': 0.15, 'spy': 0.15, 'oil': 0.10}
    elif categorie == "actions":
        weights = {'spy': 0.25, 'vix': 0.25, 'yields': 0.20, 'dxy': 0.15, 'fear_greed': 0.15}
    else:
        weights = {'dxy': 0.20, 'yields': 0.20, 'vix': 0.20, 'spy': 0.20, 'fear_greed': 0.20}

    total_score = 0
    total_weight = 0
    breakdown = {}
    for factor, weight in weights.items():
        if factor in macro_data and 'score' in macro_data[factor]:
            factor_score = macro_data[factor]['score']
            total_score += factor_score * weight
            total_weight += weight
            breakdown[factor] = {'score': factor_score, 'weight': weight}
    if total_weight > 0:
        composite = (total_score / total_weight) * sensitivity
    else:
        composite = 0
    return max(-10, min(10, composite)), breakdown


# ══════════════════════════════════════════════════════════
# DIVERGENCE OR/BITCOIN
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner="🔗 Divergence Or/Bitcoin...")
def get_divergence_or_btc():
    try:
        or_data = yf.download("GC=F", period="30d", interval="1d", progress=False)
        btc_data = yf.download("BTC-USD", period="30d", interval="1d", progress=False)
        if isinstance(or_data.columns, pd.MultiIndex):
            or_data.columns = or_data.columns.get_level_values(0)
        if isinstance(btc_data.columns, pd.MultiIndex):
            btc_data.columns = btc_data.columns.get_level_values(0)
        if len(or_data) < 7 or len(btc_data) < 7:
            return None
        var_or = float(((or_data['Close'].iloc[-1] - or_data['Close'].iloc[-7]) / or_data['Close'].iloc[-7]) * 100)
        var_btc = float(((btc_data['Close'].iloc[-1] - btc_data['Close'].iloc[-7]) / btc_data['Close'].iloc[-7]) * 100)
        ecart = var_or - var_btc
        return {'var_or': var_or, 'var_btc': var_btc, 'ecart': ecart}
    except:
        return None

def indicateur_divergence_or_btc(ticker):
    data = get_divergence_or_btc()
    if data is None:
        return 0, "Données indisponibles"
    var_or = data['var_or']
    var_btc = data['var_btc']
    ecart = data['ecart']
    if ticker == "GC=F":
        if ecart < -5:
            return 1, f"BTC +{round(var_btc, 1)}% vs Or -> Or devrait rattraper"
        elif ecart > 5:
            return -1, f"Or +{round(var_or, 1)}% vs BTC -> Or en excès"
        else:
            return 0, f"Écart neutre ({round(ecart, 1)}%)"
    elif ticker in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        if ecart > 5:
            return 1, f"Or +{round(var_or, 1)}% vs BTC -> Crypto devrait rattraper"
        elif ecart < -5:
            return -1, f"BTC +{round(var_btc, 1)}% vs Or -> Crypto en excès"
        else:
            return 0, f"Écart neutre ({round(ecart, 1)}%)"
    else:
        if var_or > 3 and var_btc > 3:
            return 1, "Or et BTC montent -> Fuite vers refuges"
        elif var_or < -3 and var_btc < -3:
            return -1, "Or et BTC baissent -> Confiance marché"
        else:
            return 0, "Pas de signal clair"


# ══════════════════════════════════════════════════════════
# NLP NEWS SENTIMENT (amélioré v5.0)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner="📰 Analyse des news...")
def get_news_sentiment(ticker):
    try:
        keywords = NEWS_KEYWORDS.get(ticker, [ticker])
        query = "+".join(keywords[:3]).replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        if not feed.entries:
            return {'score': 0, 'nb_articles': 0, 'details': "Pas d'articles", 'headlines': []}

        vader = SentimentIntensityAnalyzer()
        scores = []
        headlines = []

        for entry in feed.entries[:15]:  # Plus d'articles
            title = entry.get('title', '')
            compound = vader.polarity_scores(title)['compound']
            title_lower = title.lower()
            bull_count = sum(1 for kw in BULLISH_KEYWORDS if kw.lower() in title_lower)
            bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw.lower() in title_lower)
            keyword_bonus = (bull_count - bear_count) * 0.25
            final = max(-1, min(1, compound + keyword_bonus))
            scores.append(final)
            headlines.append({'title': title, 'score': final})

        if not scores:
            return {'score': 0, 'nb_articles': 0, 'details': "Analyse échouée", 'headlines': []}

        # Pondération : articles récents comptent plus
        weights = np.linspace(1.5, 0.5, len(scores))
        weighted_avg = np.average(scores, weights=weights)
        final_score = max(-10, min(10, weighted_avg * 10))

        bull_articles = sum(1 for s in scores if s > 0.1)
        bear_articles = sum(1 for s in scores if s < -0.1)
        neutral_articles = len(scores) - bull_articles - bear_articles
        details = f"{bull_articles} positifs / {neutral_articles} neutres / {bear_articles} négatifs"

        return {
            'score': final_score,
            'nb_articles': len(scores),
            'details': details,
            'headlines': sorted(headlines, key=lambda x: abs(x['score']), reverse=True)[:5]
        }
    except:
        return {'score': 0, 'nb_articles': 0, 'details': "Erreur", 'headlines': []}


# ══════════════════════════════════════════════════════════
# ON-CHAIN (amélioré v5.0)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=900, show_spinner="⛓️ Analyse on-chain...")
def get_onchain_score(ticker):
    if ticker not in ['BTC-USD', 'ETH-USD', 'SOL-USD']:
        return {'score': 0, 'details': []}
    score = 0
    details = []

    if ticker == 'BTC-USD':
        # Fees
        try:
            r = requests.get("https://mempool.space/api/v1/fees/recommended", timeout=5)
            if r.status_code == 200:
                fees = r.json()
                fastest = fees.get('fastestFee', 0)
                if fastest > 100:
                    score -= 2
                    details.append(f"🔴 Fees élevés ({fastest} sat/vB)")
                elif fastest < 10:
                    score += 1
                    details.append(f"🟢 Fees bas ({fastest} sat/vB)")
                else:
                    details.append(f"⚪ Fees normaux ({fastest} sat/vB)")
        except:
            pass

        # Mempool
        try:
            r = requests.get("https://mempool.space/api/mempool", timeout=5)
            if r.status_code == 200:
                mempool = r.json()
                count = mempool.get('count', 0)
                if count > 100000:
                    score -= 1
                    details.append(f"🔴 Mempool congestionné ({count} TX)")
                elif count < 10000:
                    score += 1
                    details.append(f"🟢 Mempool calme ({count} TX)")
                else:
                    details.append(f"⚪ Mempool normal ({count} TX)")
        except:
            pass

        # Hashrate
        try:
            r = requests.get("https://api.blockchain.info/charts/hash-rate?timespan=30days&format=json", timeout=10)
            if r.status_code == 200:
                values = [point['y'] for point in r.json().get('values', [])]
                if len(values) >= 14:
                    recent = np.mean(values[-7:])
                    earlier = np.mean(values[:7])
                    change = (recent - earlier) / earlier * 100
                    if change > 5:
                        score += 2
                        details.append(f"🟢 Hashrate +{round(change, 1)}%")
                    elif change < -5:
                        score -= 2
                        details.append(f"🔴 Hashrate {round(change, 1)}%")
                    else:
                        details.append(f"⚪ Hashrate stable ({round(change, 1)}%)")
        except:
            pass

    # DeFi TVL
    try:
        r = requests.get("https://api.llama.fi/v2/historicalChainTvl", timeout=10)
        if r.status_code == 200:
            tvl_data = r.json()
            if len(tvl_data) >= 7:
                recent = tvl_data[-1].get('tvl', 0)
                week_ago = tvl_data[-7].get('tvl', 0)
                change = (recent - week_ago) / week_ago * 100 if week_ago > 0 else 0
                tvl_b = recent / 1e9
                if change > 5:
                    score += 2
                    details.append(f"🟢 DeFi TVL +{round(change, 1)}% (${round(tvl_b, 0)}B)")
                elif change < -5:
                    score -= 2
                    details.append(f"🔴 DeFi TVL {round(change, 1)}% (${round(tvl_b, 0)}B)")
                else:
                    details.append(f"⚪ DeFi TVL stable (${round(tvl_b, 0)}B)")
    except:
        pass

    # Long/Short Ratio (NOUVEAU v5.0)
    if ticker == 'BTC-USD':
        try:
            r = requests.get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                           params={"symbol": "BTCUSDT", "period": "1h", "limit": 1}, timeout=5)
            if r.status_code == 200:
                ratio_data = r.json()
                if ratio_data:
                    ls_ratio = float(ratio_data[0]['longShortRatio'])
                    if ls_ratio > 2.0:
                        score -= 2
                        details.append(f"🔴 L/S Ratio: {round(ls_ratio, 2)} (trop de longs)")
                    elif ls_ratio < 0.8:
                        score += 2
                        details.append(f"🟢 L/S Ratio: {round(ls_ratio, 2)} (shorts dominants)")
                    else:
                        details.append(f"⚪ L/S Ratio: {round(ls_ratio, 2)}")
        except:
            pass

    return {'score': max(-10, min(10, score)), 'details': details}


# ══════════════════════════════════════════════════════════
# TÉLÉCHARGEMENT (hybride Yahoo + ccxt)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner="📥 Chargement...")
def telecharger_donnees(ticker):
    """Télécharge les données — ccxt pour crypto, Yahoo pour le reste"""
    # Essayer ccxt d'abord pour crypto (plus fiable)
    if HAS_CCXT and ticker in CCXT_SYMBOLS:
        data = get_realtime_data_ccxt(CCXT_SYMBOLS[ticker], '1d', 365)
        if data is not None and not data.empty:
            return data

    # Fallback Yahoo Finance
    data = yf.download(ticker, period="1y", interval="1d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


# ══════════════════════════════════════════════════════════
# CALCULER TOUS LES INDICATEURS
# ══════════════════════════════════════════════════════════

def calculer_tout(data):
    """Calcule tous les indicateurs techniques"""
    data['RSI'] = calc_rsi(data['Close'])
    data['Stoch_K'], data['Stoch_D'] = calc_stochastique(data)
    data['MACD'], data['MACD_Signal'] = calc_macd(data['Close'])
    data['Fib_618'], data['Fib_382'], data['Fib_236'], data['Fib_786'] = calc_fibonacci(data)
    data['MA_200'] = calc_ma200(data['Close'])
    data['MA_50'] = data['Close'].rolling(50).mean()
    data['EMA_21'] = data['Close'].ewm(span=21).mean()
    data['ADX'] = calc_adx(data)
    data['ATR'] = calc_atr(data)
    data['BB_Upper'], data['BB_Lower'], data['BB_Mid'], data['BB_Width'] = calc_bollinger(data['Close'])
    data['Vol_Moy_20'] = data['Volume'].rolling(20).mean()
    data['VWAP'] = calc_vwap(data)

    # Ichimoku
    ichimoku = calc_ichimoku(data)
    if ichimoku is not None:
        data['Ichi_Tenkan'] = ichimoku['tenkan']
        data['Ichi_Kijun'] = ichimoku['kijun']
        data['Ichi_SpanA'] = ichimoku['senkou_a']
        data['Ichi_SpanB'] = ichimoku['senkou_b']

    return data


# ══════════════════════════════════════════════════════════
# STOP-LOSS / TAKE-PROFIT (amélioré v5.0)
# ══════════════════════════════════════════════════════════

def calculer_sl_tp(prix, atr, action, supports=None, resistances=None, ratio_risque=1.5, ratio_reward=2.5):
    """SL/TP intelligent — utilise les supports/résistances si disponibles"""
    if action == "ACHAT":
        # SL sous le support le plus proche ou ATR
        if supports:
            support_proche = max([s for s in supports if s < prix], default=None)
            sl_support = support_proche * 0.998 if support_proche else None
            sl_atr = prix - (ratio_risque * atr)
            stop_loss = max(sl_support, sl_atr) if sl_support else sl_atr
        else:
            stop_loss = prix - (ratio_risque * atr)

        # TP à la résistance la plus proche ou ATR
        if resistances:
            resistance_proche = min([r for r in resistances if r > prix], default=None)
            tp_resistance = resistance_proche * 0.998 if resistance_proche else None
            tp_atr = prix + (ratio_reward * atr)
            take_profit = min(tp_resistance, tp_atr) if tp_resistance else tp_atr
        else:
            take_profit = prix + (ratio_reward * atr)

        risque_pct = ((prix - stop_loss) / prix) * 100
        reward_pct = ((take_profit - prix) / prix) * 100

    elif action == "VENTE":
        if resistances:
            resistance_proche = min([r for r in resistances if r > prix], default=None)
            sl_resistance = resistance_proche * 1.002 if resistance_proche else None
            sl_atr = prix + (ratio_risque * atr)
            stop_loss = min(sl_resistance, sl_atr) if sl_resistance else sl_atr
        else:
            stop_loss = prix + (ratio_risque * atr)

        if supports:
            support_proche = max([s for s in supports if s < prix], default=None)
            tp_support = support_proche * 1.002 if support_proche else None
            tp_atr = prix - (ratio_reward * atr)
            take_profit = max(tp_support, tp_atr) if tp_support else tp_atr
        else:
            take_profit = prix - (ratio_reward * atr)

        risque_pct = ((stop_loss - prix) / prix) * 100
        reward_pct = ((prix - take_profit) / prix) * 100
    else:
        return None

    ratio_rr = reward_pct / risque_pct if risque_pct > 0 else 0

    return {
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'atr': atr,
        'risque_pct': risque_pct,
        'reward_pct': reward_pct,
        'ratio_rr': ratio_rr,
    }

def calculer_taille_position(capital, risque_pct_capital, prix, stop_loss):
    risque_par_unite = abs(prix - stop_loss)
    if risque_par_unite == 0:
        return 0, 0
    montant_risque = capital * (risque_pct_capital / 100)
    nb_unites = montant_risque / risque_par_unite
    taille_position = nb_unites * prix
    return nb_unites, taille_position


# ══════════════════════════════════════════════════════════
# MULTI-TIMEFRAME (amélioré v5.0)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner="📥 Multi-timeframe...")
def telecharger_donnees_4h(ticker):
    # ccxt pour crypto
    if HAS_CCXT and ticker in CCXT_SYMBOLS:
        data = get_realtime_data_ccxt(CCXT_SYMBOLS[ticker], '4h', 200)
        if data is not None and not data.empty:
            return data
    # Fallback Yahoo
    data = yf.download(ticker, period="60d", interval="1h", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if data.empty:
        return data
    data_4h = data.resample('4h').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min',
        'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return data_4h

@st.cache_data(ttl=300, show_spinner="📥 Weekly...")
def telecharger_donnees_weekly(ticker):
    data = yf.download(ticker, period="2y", interval="1wk", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

def analyser_mtf(ticker):
    """Analyse Multi-Timeframe : 4h + Weekly"""
    result = {'4h': None, 'weekly': None, 'consensus': "NEUTRE"}

    # 4H
    try:
        data_4h = telecharger_donnees_4h(ticker)
        if not data_4h.empty and len(data_4h) >= 30:
            data_4h['RSI'] = calc_rsi(data_4h['Close'])
            data_4h['MACD'], data_4h['MACD_Signal'] = calc_macd(data_4h['Close'])
            derniere = data_4h.iloc[-1]
            rsi_4h = float(derniere['RSI']) if not np.isnan(float(derniere['RSI'])) else 50
            macd_4h = float(derniere['MACD'])
            signal_4h = float(derniere['MACD_Signal'])

            score_a = 0
            score_v = 0
            if rsi_4h < 35: score_a += 1
            elif rsi_4h > 65: score_v += 1
            if macd_4h > signal_4h: score_a += 1
            else: score_v += 1

            if score_a >= 2: tendance_4h = "ACHAT"
            elif score_v >= 2: tendance_4h = "VENTE"
            else: tendance_4h = "NEUTRE"

            result['4h'] = {'tendance': tendance_4h, 'rsi': rsi_4h}
    except:
        pass

    # WEEKLY
    try:
        data_w = telecharger_donnees_weekly(ticker)
        if not data_w.empty and len(data_w) >= 20:
            data_w['RSI'] = calc_rsi(data_w['Close'])
            data_w['MA_20'] = data_w['Close'].rolling(20).mean()
            derniere = data_w.iloc[-1]
            rsi_w = float(derniere['RSI']) if not np.isnan(float(derniere['RSI'])) else 50
            prix_w = float(derniere['Close'])
            ma20_w = float(derniere['MA_20']) if not np.isnan(float(derniere['MA_20'])) else prix_w

            if rsi_w < 40 and prix_w > ma20_w: tendance_w = "ACHAT"
            elif rsi_w > 60 and prix_w < ma20_w: tendance_w = "VENTE"
            elif prix_w > ma20_w: tendance_w = "ACHAT"
            elif prix_w < ma20_w: tendance_w = "VENTE"
            else: tendance_w = "NEUTRE"

            result['weekly'] = {'tendance': tendance_w, 'rsi': rsi_w}
    except:
        pass

    # CONSENSUS
    tendances = []
    if result['4h']: tendances.append(result['4h']['tendance'])
    if result['weekly']: tendances.append(result['weekly']['tendance'])

    if tendances.count("ACHAT") >= 2: result['consensus'] = "ACHAT"
    elif tendances.count("VENTE") >= 2: result['consensus'] = "VENTE"
    elif "ACHAT" in tendances and "VENTE" not in tendances: result['consensus'] = "ACHAT"
    elif "VENTE" in tendances and "ACHAT" not in tendances: result['consensus'] = "VENTE"

    return result


# ══════════════════════════════════════════════════════════
# TIMING
# ══════════════════════════════════════════════════════════

def evaluer_timing(nom_actif, ticker):
    tz_suisse = pytz.timezone("Europe/Zurich")
    now = datetime.now(tz_suisse)
    heure = now.hour
    jour = now.weekday()
    categorie = ACTIF_CATEGORIE.get(nom_actif, "forex")
    info = HORAIRES_OPTIMAUX[categorie]
    heure_bonne_achat = heure in info.get("heures_favorables_achat", [])
    heure_bonne_vente = heure in info.get("heures_favorables_vente", [])
    heure_a_eviter = heure in info.get("heures_a_eviter", [])
    jours_fr = {0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'}
    return {
        'heure': heure,
        'jour': jours_fr[jour],
        'heure_bonne_achat': heure_bonne_achat,
        'heure_bonne_vente': heure_bonne_vente,
        'heure_a_eviter': heure_a_eviter,
        'achat_ideal': info['achat_horaire'],
        'vente_ideal': info['vente_horaire'],
        'categorie': info['nom'],
    }


# ══════════════════════════════════════════════════════════
# ÉVALUATION v5.0 COMPLÈTE
# ══════════════════════════════════════════════════════════

def get_val(v):
    if hasattr(v, 'iloc'):
        return float(v.iloc[0])
    return float(v)

def evaluer_v50(data, ticker, nom_actif, macro_data):
    """Évaluation complète v5.0 avec tous les nouveaux indicateurs"""
    if len(data) < 2:
        return 0, 0, [], 0, 0, True, None, None, None

    derniere = data.iloc[-1]
    avant = data.iloc[-2]
    prix = get_val(derniere['Close'])
    adx_val = get_val(derniere['ADX'])
    atr_val = get_val(derniere['ATR']) if not np.isnan(get_val(derniere['ATR'])) else 0

    if np.isnan(adx_val) or adx_val < SEUIL_ADX:
        details = [("ADX", "PLAT", f"ADX = {round(adx_val, 1)} < {SEUIL_ADX} -> Marché plat")]
        return 0, 0, details, prix, adx_val, True, None, None, None

    score_achat = 0
    score_vente = 0
    details = []

    # ═══ RSI ═══
    rsi_now = get_val(derniere['RSI'])
    rsi_avant = get_val(avant['RSI'])
    if rsi_now < 30 and rsi_avant < 30:
        score_achat += POIDS["RSI"]
        details.append(("RSI", "ACHAT", f"Survendu confirmé ({round(rsi_now, 1)}) -> +{POIDS['RSI']} pts"))
    elif rsi_now > 70 and rsi_avant > 70:
        score_vente += POIDS["RSI"]
        details.append(("RSI", "VENTE", f"Suracheté confirmé ({round(rsi_now, 1)}) -> +{POIDS['RSI']} pts"))
    else:
        details.append(("RSI", "NEUTRE", f"RSI = {round(rsi_now, 1)}"))

    # ═══ STOCH ═══
    stoch_now = get_val(derniere['Stoch_K'])
    stoch_avant = get_val(avant['Stoch_K'])
    if stoch_now < 20 and stoch_avant < 20:
        score_achat += POIDS["STOCH"]
        details.append(("STOCH", "ACHAT", f"Survendu confirmé -> +{POIDS['STOCH']} pts"))
    elif stoch_now > 80 and stoch_avant > 80:
        score_vente += POIDS["STOCH"]
        details.append(("STOCH", "VENTE", f"Suracheté confirmé -> +{POIDS['STOCH']} pts"))
    else:
        details.append(("STOCH", "NEUTRE", f"Stoch = {round(stoch_now, 1)}"))

    # ═══ MACD ═══
    macd_now = get_val(derniere['MACD'])
    signal_now = get_val(derniere['MACD_Signal'])
    macd_av = get_val(avant['MACD'])
    signal_av = get_val(avant['MACD_Signal'])
    if macd_now > signal_now and macd_av > signal_av:
        score_achat += POIDS["MACD"]
        details.append(("MACD", "ACHAT", f"Au-dessus signal (confirmé) -> +{POIDS['MACD']} pts"))
    elif macd_now < signal_now and macd_av < signal_av:
        score_vente += POIDS["MACD"]
        details.append(("MACD", "VENTE", f"En dessous signal (confirmé) -> +{POIDS['MACD']} pts"))
    else:
        details.append(("MACD", "NEUTRE", "Croisement récent"))

    # ═══ FIBO ═══
    fib_618 = get_val(derniere['Fib_618'])
    fib_382 = get_val(derniere['Fib_382'])
    if prix <= fib_618:
        score_achat += POIDS["FIBO"]
        details.append(("FIBO", "ACHAT", f"Sous 61.8% -> +{POIDS['FIBO']} pts"))
    elif prix >= fib_382:
        score_vente += POIDS["FIBO"]
        details.append(("FIBO", "VENTE", f"Au-dessus 38.2% -> +{POIDS['FIBO']} pts"))
    else:
        details.append(("FIBO", "NEUTRE", "Entre les niveaux"))

    # ═══ MA200 ═══
    ma200 = get_val(derniere['MA_200'])
    if not np.isnan(ma200):
        if prix <= ma200 * 1.02:
            score_achat += POIDS["MA200"]
            details.append(("MA200", "ACHAT", f"Sous MA200 -> +{POIDS['MA200']} pts"))
        elif prix >= ma200 * 1.10:
            score_vente += POIDS["MA200"]
            details.append(("MA200", "VENTE", f"+10% au-dessus -> +{POIDS['MA200']} pts"))
        else:
            details.append(("MA200", "NEUTRE", "Zone normale"))
    else:
        details.append(("MA200", "NEUTRE", "Pas assez de données"))

    # ═══ VOLUME ═══
    vol_now = get_val(derniere['Volume'])
    vol_moy = get_val(derniere['Vol_Moy_20'])
    if not np.isnan(vol_moy) and vol_moy > 0:
        ratio_vol = vol_now / vol_moy
        if ratio_vol >= 1.5:
            if score_achat > score_vente:
                score_achat += POIDS["VOLUME"]
                details.append(("VOLUME", "ACHAT", f"Fort ({round(ratio_vol, 1)}x) confirme -> +{POIDS['VOLUME']} pts"))
            elif score_vente > score_achat:
                score_vente += POIDS["VOLUME"]
                details.append(("VOLUME", "VENTE", f"Fort ({round(ratio_vol, 1)}x) confirme -> +{POIDS['VOLUME']} pts"))
            else:
                details.append(("VOLUME", "NEUTRE", "Fort mais pas de direction"))
        else:
            details.append(("VOLUME", "NEUTRE", f"Normal ({round(ratio_vol, 1)}x)"))
    else:
        details.append(("VOLUME", "NEUTRE", "Pas de données"))

    # ═══ BOLLINGER ═══
    bb_upper = get_val(derniere['BB_Upper'])
    bb_lower = get_val(derniere['BB_Lower'])
    if not np.isnan(bb_upper) and not np.isnan(bb_lower):
        if prix <= bb_lower:
            score_achat += POIDS["BOLLINGER"]
            details.append(("BOLLINGER", "ACHAT", f"Bande basse -> +{POIDS['BOLLINGER']} pts"))
        elif prix >= bb_upper:
            score_vente += POIDS["BOLLINGER"]
            details.append(("BOLLINGER", "VENTE", f"Bande haute -> +{POIDS['BOLLINGER']} pts"))
        else:
            details.append(("BOLLINGER", "NEUTRE", "Entre les bandes"))

    # ═══ DIVERGENCES (amélioré) ═══
    divergences = detecter_divergences(data)
    if divergences['rsi'] == "HAUSSIERE" or divergences['macd'] == "HAUSSIERE":
        score_achat += POIDS["DIVERGENCE"]
        details.append(("DIVERGENCE", "ACHAT", f"Divergence haussière -> +{POIDS['DIVERGENCE']} pts"))
    elif divergences['rsi'] == "BAISSIERE" or divergences['macd'] == "BAISSIERE":
        score_vente += POIDS["DIVERGENCE"]
        details.append(("DIVERGENCE", "VENTE", f"Divergence baissière -> +{POIDS['DIVERGENCE']} pts"))
    else:
        details.append(("DIVERGENCE", "NEUTRE", "Pas de divergence"))

    # ═══ OR/BTC ═══
    signal_or_btc, msg_or_btc = indicateur_divergence_or_btc(ticker)
    if signal_or_btc == 1:
        score_achat += POIDS["OR_BTC"]
        details.append(("OR/BTC", "ACHAT", f"{msg_or_btc} -> +{POIDS['OR_BTC']} pts"))
    elif signal_or_btc == -1:
        score_vente += POIDS["OR_BTC"]
        details.append(("OR/BTC", "VENTE", f"{msg_or_btc} -> +{POIDS['OR_BTC']} pts"))
    else:
        details.append(("OR/BTC", "NEUTRE", msg_or_btc))

    # ═══ MACRO ═══
    categorie = ACTIF_CATEGORIE.get(nom_actif, "forex")
    if macro_data:
        macro_score, _ = calculate_macro_score(macro_data, ticker, categorie)
        if macro_score >= 3:
            score_achat += POIDS["MACRO"]
            details.append(("MACRO", "ACHAT", f"Score +{round(macro_score, 1)}/10 -> +{POIDS['MACRO']} pts"))
        elif macro_score <= -3:
            score_vente += POIDS["MACRO"]
            details.append(("MACRO", "VENTE", f"Score {round(macro_score, 1)}/10 -> +{POIDS['MACRO']} pts"))
        elif macro_score >= 1:
            score_achat += POIDS["MACRO"] * 0.4
            details.append(("MACRO", "ACHAT", f"Léger + ({round(macro_score, 1)}) -> +{round(POIDS['MACRO'] * 0.4, 1)} pts"))
        elif macro_score <= -1:
            score_vente += POIDS["MACRO"] * 0.4
            details.append(("MACRO", "VENTE", f"Léger - ({round(macro_score, 1)}) -> +{round(POIDS['MACRO'] * 0.4, 1)} pts"))
        else:
            details.append(("MACRO", "NEUTRE", f"Score {round(macro_score, 1)}/10"))

    # ═══ SENTIMENT ═══
    if macro_data and 'fear_greed' in macro_data:
        fg_value = macro_data['fear_greed'].get('value', 50)
        if fg_value < 25:
            score_achat += POIDS["SENTIMENT"]
            details.append(("SENTIMENT", "ACHAT", f"Extreme Fear ({fg_value}) -> +{POIDS['SENTIMENT']} pts"))
        elif fg_value < 35:
            score_achat += POIDS["SENTIMENT"] * 0.5
            details.append(("SENTIMENT", "ACHAT", f"Fear ({fg_value}) -> +{round(POIDS['SENTIMENT'] * 0.5, 1)} pts"))
        elif fg_value > 75:
            score_vente += POIDS["SENTIMENT"]
            details.append(("SENTIMENT", "VENTE", f"Extreme Greed ({fg_value}) -> +{POIDS['SENTIMENT']} pts"))
        elif fg_value > 65:
            score_vente += POIDS["SENTIMENT"] * 0.5
            details.append(("SENTIMENT", "VENTE", f"Greed ({fg_value}) -> +{round(POIDS['SENTIMENT'] * 0.5, 1)} pts"))
        else:
            details.append(("SENTIMENT", "NEUTRE", f"F&G = {fg_value}"))

    # ═══ NEWS NLP ═══
    news = get_news_sentiment(ticker)
    if news and news['nb_articles'] > 0:
        if news['score'] >= 4:
            score_achat += POIDS["NEWS_NLP"]
            details.append(("NEWS", "ACHAT", f"Positif ({round(news['score'], 1)}/10) -> +{POIDS['NEWS_NLP']} pts"))
        elif news['score'] <= -4:
            score_vente += POIDS["NEWS_NLP"]
            details.append(("NEWS", "VENTE", f"Négatif ({round(news['score'], 1)}/10) -> +{POIDS['NEWS_NLP']} pts"))
        elif news['score'] >= 2:
            score_achat += POIDS["NEWS_NLP"] * 0.4
            details.append(("NEWS", "ACHAT", f"Léger + ({round(news['score'], 1)}) -> +{round(POIDS['NEWS_NLP'] * 0.4, 1)} pts"))
        elif news['score'] <= -2:
            score_vente += POIDS["NEWS_NLP"] * 0.4
            details.append(("NEWS", "VENTE", f"Léger - ({round(news['score'], 1)}) -> +{round(POIDS['NEWS_NLP'] * 0.4, 1)} pts"))
        else:
            details.append(("NEWS", "NEUTRE", f"Score {round(news['score'], 1)}"))

    # ═══ ON-CHAIN ═══
    onchain = get_onchain_score(ticker)
    if onchain and onchain['score'] != 0:
        if onchain['score'] >= 3:
            score_achat += POIDS["ONCHAIN"]
            details.append(("ON-CHAIN", "ACHAT", f"Score +{onchain['score']}/10 -> +{POIDS['ONCHAIN']} pts"))
        elif onchain['score'] <= -3:
            score_vente += POIDS["ONCHAIN"]
            details.append(("ON-CHAIN", "VENTE", f"Score {onchain['score']}/10 -> +{POIDS['ONCHAIN']} pts"))
        elif onchain['score'] >= 1:
            score_achat += POIDS["ONCHAIN"] * 0.4
            details.append(("ON-CHAIN", "ACHAT", f"Léger + -> +{round(POIDS['ONCHAIN'] * 0.4, 1)} pts"))
        elif onchain['score'] <= -1:
            score_vente += POIDS["ONCHAIN"] * 0.4
            details.append(("ON-CHAIN", "VENTE", f"Léger - -> +{round(POIDS['ONCHAIN'] * 0.4, 1)} pts"))
    else:
        details.append(("ON-CHAIN", "NEUTRE", "N/A"))

    # ═══ ICHIMOKU (NOUVEAU v5.0) ═══
    if 'Ichi_Tenkan' in data.columns:
        try:
            tenkan = get_val(derniere['Ichi_Tenkan'])
            kijun = get_val(derniere['Ichi_Kijun'])
            span_a = get_val(derniere['Ichi_SpanA']) if not np.isnan(get_val(derniere['Ichi_SpanA'])) else 0
            span_b = get_val(derniere['Ichi_SpanB']) if not np.isnan(get_val(derniere['Ichi_SpanB'])) else 0

            if not np.isnan(tenkan) and not np.isnan(kijun):
                # Prix au-dessus du nuage + Tenkan > Kijun = bullish
                nuage_haut = max(span_a, span_b) if span_a and span_b else 0
                nuage_bas = min(span_a, span_b) if span_a and span_b else 0

                if prix > nuage_haut and tenkan > kijun:
                    score_achat += POIDS["ICHIMOKU"]
                    details.append(("ICHIMOKU", "ACHAT", f"Au-dessus nuage + TK cross -> +{POIDS['ICHIMOKU']} pts"))
                elif prix < nuage_bas and tenkan < kijun:
                    score_vente += POIDS["ICHIMOKU"]
                    details.append(("ICHIMOKU", "VENTE", f"Sous nuage + TK cross -> +{POIDS['ICHIMOKU']} pts"))
                elif prix > nuage_haut:
                    score_achat += POIDS["ICHIMOKU"] * 0.5
                    details.append(("ICHIMOKU", "ACHAT", f"Au-dessus nuage -> +{round(POIDS['ICHIMOKU'] * 0.5, 1)} pts"))
                elif prix < nuage_bas:
                    score_vente += POIDS["ICHIMOKU"] * 0.5
                    details.append(("ICHIMOKU", "VENTE", f"Sous le nuage -> +{round(POIDS['ICHIMOKU'] * 0.5, 1)} pts"))
                else:
                    details.append(("ICHIMOKU", "NEUTRE", "Dans le nuage"))
        except:
            details.append(("ICHIMOKU", "NEUTRE", "Erreur calcul"))
    else:
        details.append(("ICHIMOKU", "NEUTRE", "Non disponible"))

    # ═══ SUPPORTS/RÉSISTANCES (NOUVEAU v5.0) ═══
    supports, resistances = detecter_supports_resistances(data)
    if supports and resistances:
        support_proche = max([s for s in supports if s < prix], default=None)
        resistance_proche = min([r for r in resistances if r > prix], default=None)

        if support_proche and (prix - support_proche) / prix < 0.02:
            score_achat += POIDS["SUPPORTS_RES"]
            details.append(("S/R", "ACHAT", f"Proche support {round(support_proche, 2)} -> +{POIDS['SUPPORTS_RES']} pts"))
        elif resistance_proche and (resistance_proche - prix) / prix < 0.02:
            score_vente += POIDS["SUPPORTS_RES"]
            details.append(("S/R", "VENTE", f"Proche résistance {round(resistance_proche, 2)} -> +{POIDS['SUPPORTS_RES']} pts"))
        else:
            details.append(("S/R", "NEUTRE", f"S: {round(support_proche, 2) if support_proche else 'N/A'} | R: {round(resistance_proche, 2) if resistance_proche else 'N/A'}"))
    else:
        supports, resistances = [], []
        details.append(("S/R", "NEUTRE", "Non détectés"))

    # ═══ VWAP (NOUVEAU v5.0) ═══
    if 'VWAP' in data.columns:
        vwap = get_val(derniere['VWAP'])
        if not np.isnan(vwap):
            if prix < vwap * 0.99:
                score_achat += POIDS["VWAP"]
                details.append(("VWAP", "ACHAT", f"Prix sous VWAP -> +{POIDS['VWAP']} pts"))
            elif prix > vwap * 1.01:
                score_vente += POIDS["VWAP"]
                details.append(("VWAP", "VENTE", f"Prix au-dessus VWAP -> +{POIDS['VWAP']} pts"))
            else:
                details.append(("VWAP", "NEUTRE", "Proche du VWAP"))

    # ═══ ORDER FLOW / CARNET D'ORDRES (NOUVEAU v5.0) ═══
    if ticker in CCXT_SYMBOLS:
        ob_data = get_order_book_imbalance(CCXT_SYMBOLS[ticker])
        if ob_data:
            imbalance = ob_data['imbalance']
            if imbalance > 0.3:
                score_achat += POIDS["ORDER_FLOW"]
                details.append(("ORDER FLOW", "ACHAT", f"Pression achat +{round(imbalance*100, 0)}% -> +{POIDS['ORDER_FLOW']} pts"))
            elif imbalance < -0.3:
                score_vente += POIDS["ORDER_FLOW"]
                details.append(("ORDER FLOW", "VENTE", f"Pression vente {round(imbalance*100, 0)}% -> +{POIDS['ORDER_FLOW']} pts"))
            else:
                details.append(("ORDER FLOW", "NEUTRE", f"Équilibré ({round(imbalance*100, 0)}%)"))
        else:
            details.append(("ORDER FLOW", "NEUTRE", "Non disponible"))
    else:
        details.append(("ORDER FLOW", "NEUTRE", "N/A (pas crypto)"))

    # ═══ ML PREDICTION (NOUVEAU v5.0) ═══
    ml_result = entrainer_modele_ml(ticker, data)
    if ml_result and ml_result['accuracy'] > 0.52:
        if ml_result['direction'] == "ACHAT" and ml_result['confiance'] > 0.55:
            score_achat += POIDS["ML_PREDICTION"]
            details.append(("🤖 ML", "ACHAT", f"Proba hausse {round(ml_result['proba_hausse']*100, 0)}% (acc: {round(ml_result['accuracy']*100, 0)}%) -> +{POIDS['ML_PREDICTION']} pts"))
        elif ml_result['direction'] == "VENTE" and ml_result['confiance'] > 0.55:
            score_vente += POIDS["ML_PREDICTION"]
            details.append(("🤖 ML", "VENTE", f"Proba baisse {round(ml_result['proba_baisse']*100, 0)}% (acc: {round(ml_result['accuracy']*100, 0)}%) -> +{POIDS['ML_PREDICTION']} pts"))
        else:
            details.append(("🤖 ML", "NEUTRE", f"Confiance insuffisante ({round(ml_result['confiance']*100, 0)}%)"))
    else:
        details.append(("🤖 ML", "NEUTRE", "Pas assez de données ou accuracy faible"))

    # ═══ ADX INFO ═══
    details.append(("ADX", "OK", f"ADX = {round(adx_val, 1)} -> Tendance confirmée"))

    # ═══ MTF ═══
    mtf = analyser_mtf(ticker)
    if mtf:
        if mtf.get('4h'):
            details.append(("MTF 4H", mtf['4h']['tendance'], f"RSI 4h: {round(mtf['4h']['rsi'], 0)}"))
        if mtf.get('weekly'):
            details.append(("MTF WEEKLY", mtf['weekly']['tendance'], f"RSI W: {round(mtf['weekly']['rsi'], 0)}"))
        details.append(("MTF CONSENSUS", mtf['consensus'], "Alignement multi-TF"))

    # ═══ SL/TP ═══
    sl_tp = None
    if score_achat > score_vente:
        sl_tp = calculer_sl_tp(prix, atr_val, "ACHAT", supports, resistances)
    elif score_vente > score_achat:
        sl_tp = calculer_sl_tp(prix, atr_val, "VENTE", supports, resistances)

    return score_achat, score_vente, details, prix, adx_val, False, sl_tp, mtf, ml_result


# ══════════════════════════════════════════════════════════
# GRAPHIQUE (amélioré v5.0 — Ichimoku + S/R)
# ══════════════════════════════════════════════════════════

def creer_graphique(data, nom, supports=None, resistances=None):
    df = data.tail(60)
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.4, 0.2, 0.2, 0.2],
                        subplot_titles=["Prix + Indicateurs", "RSI", "MACD", "Volume"])

    # Prix
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Prix',
                             line=dict(color='#667eea', width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA_200'], name='MA 200',
                             line=dict(color='#ffd700', dash='dash', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], name='BB Upper',
                             line=dict(color='rgba(255,100,100,0.5)', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], name='BB Lower',
                             line=dict(color='rgba(100,255,100,0.5)', width=1),
                             fill='tonexty', fillcolor='rgba(100,100,255,0.05)'), row=1, col=1)

    # Ichimoku Cloud
    if 'Ichi_SpanA' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['Ichi_SpanA'], name='Span A',
                                 line=dict(color='rgba(0,255,100,0.3)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Ichi_SpanB'], name='Span B',
                                 line=dict(color='rgba(255,100,0,0.3)', width=1),
                                 fill='tonexty', fillcolor='rgba(100,200,100,0.1)'), row=1, col=1)

    # Supports/Résistances
    if supports:
        for s in supports[:3]:
            fig.add_hline(y=s, line_dash="dot", line_color="rgba(0,210,255,0.6)",
                         annotation_text=f"S: {round(s, 2)}", row=1, col=1)
    if resistances:
        for r in resistances[:3]:
            fig.add_hline(y=r, line_dash="dot", line_color="rgba(245,87,108,0.6)",
                         annotation_text=f"R: {round(r, 2)}", row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI',
                             line=dict(color='#a855f7', width=2)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(245,87,108,0.5)", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,210,255,0.5)", row=2, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD',
                             line=dict(color='#667eea', width=2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name='Signal',
                             line=dict(color='#f5576c', width=1.5)), row=3, col=1)
    hist = df['MACD'] - df['MACD_Signal']
    colors_hist = ['rgba(0,210,255,0.6)' if float(h) >= 0 else 'rgba(245,87,108,0.6)' for h in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, name='Hist', marker_color=colors_hist), row=3, col=1)

    # Volume
    vol_colors = ['rgba(0,210,255,0.6)' if float(df['Close'].iloc[i]) >= float(df['Open'].iloc[i])
                  else 'rgba(245,87,108,0.6)' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume',
                         marker_color=vol_colors), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_Moy_20'], name='Vol Moy 20',
                             line=dict(color='#ffd700', width=1.5, dash='dash')), row=4, col=1)

    fig.update_layout(
        height=800, showlegend=True, template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), margin=dict(l=50, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)')
    return fig


# ══════════════════════════════════════════════════════════
# SCAN PRINCIPAL v5.0 (parallélisé)
# ══════════════════════════════════════════════════════════

def analyser_actif(nom, ticker, seuil_score, macro_data):
    """Analyse un seul actif — pour parallélisation"""
    try:
        data = telecharger_donnees(ticker)
        if data.empty:
            return None
        data = calculer_tout(data)
        rsi_check = get_val(data.iloc[-1]['RSI'])
        if np.isnan(rsi_check):
            return None

        score_achat, score_vente, details, prix, adx_val, marche_plat, sl_tp, mtf, ml_result = evaluer_v50(
            data, ticker, nom, macro_data
        )

        if marche_plat:
            action = "PLAT"
        elif score_achat >= seuil_score and score_achat > score_vente:
            action = "ACHAT"
        elif score_vente >= seuil_score:
            action = "VENTE"
        else:
            action = "ATTENDRE"

        timing = evaluer_timing(nom, ticker)
        atr_val = get_val(data.iloc[-1]['ATR']) if not np.isnan(get_val(data.iloc[-1]['ATR'])) else 0

        supports, resistances = detecter_supports_resistances(data)
        if action in ["ACHAT", "VENTE"]:
            sl_tp = calculer_sl_tp(prix, atr_val, action, supports, resistances)

        score_max = sum(POIDS.values())

        return {
            'nom': nom, 'ticker': ticker, 'prix': prix,
            'action': action,
            'score_achat': score_achat, 'score_vente': score_vente,
            'score_max': score_max, 'adx': adx_val,
            'details': details, 'data': data,
            'timing': timing, 'sl_tp': sl_tp, 'mtf': mtf,
            'atr': atr_val, 'ml_prediction': ml_result,
            'supports': supports, 'resistances': resistances,
        }
    except:
        return None


def lancer_scan(actifs_choisis, seuil_score, macro_data):
    """Scan parallélisé — 3x plus rapide"""
    resultats = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(analyser_actif, nom, ACTIFS[nom], seuil_score, macro_data): nom
            for nom in actifs_choisis
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                resultats.append(result)

    # Trier : signaux d'abord, puis par score
    resultats.sort(key=lambda x: (
        0 if x['action'] in ["ACHAT", "VENTE"] else 1,
        -max(x['score_achat'], x['score_vente'])
    ))
    return resultats


# ══════════════════════════════════════════════════════════
# EMAIL
# ══════════════════════════════════════════════════════════

def envoyer_email(sujet, message, email_addr, email_pass):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = sujet
        msg['From'] = email_addr
        msg['To'] = email_addr
        msg.attach(MIMEText(message, 'plain', 'utf-8'))
        with smtplib.SMTP_SSL("smtpauths.bluewin.ch", 465) as server:
            server.login(email_addr, email_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        return str(e)


# ══════════════════════════════════════════════════════════
# BACKTESTING v5.0 (vectorisé — plus rapide)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner="📊 Backtesting...")
def backtester_strategie(ticker, seuil_score):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if data.empty or len(data) < 100:
            return None
        data = calculer_tout(data)

        trades = []
        position = None
        prix_entree = 0

        for i in range(50, len(data) - 1):
            derniere = data.iloc[i]
            avant = data.iloc[i - 1]
            prix = float(derniere['Close'])
            adx_val = float(derniere['ADX']) if not np.isnan(float(derniere['ADX'])) else 0
            atr_val = float(derniere['ATR']) if not np.isnan(float(derniere['ATR'])) else 0

            if adx_val < SEUIL_ADX:
                if position == "LONG":
                    trades.append({'type': 'LONG', 'pnl': ((prix - prix_entree) / prix_entree) * 100, 'bars': i})
                    position = None
                elif position == "SHORT":
                    trades.append({'type': 'SHORT', 'pnl': ((prix_entree - prix) / prix_entree) * 100, 'bars': i})
                    position = None
                continue

            score_a = 0
            score_v = 0

            # RSI
            rsi_now = float(derniere['RSI']) if not np.isnan(float(derniere['RSI'])) else 50
            rsi_avant = float(avant['RSI']) if not np.isnan(float(avant['RSI'])) else 50
            if rsi_now < 30 and rsi_avant < 30: score_a += POIDS["RSI"]
            elif rsi_now > 70 and rsi_avant > 70: score_v += POIDS["RSI"]

            # MACD
            macd_now = float(derniere['MACD']) if not np.isnan(float(derniere['MACD'])) else 0
            signal_now = float(derniere['MACD_Signal']) if not np.isnan(float(derniere['MACD_Signal'])) else 0
            macd_av = float(avant['MACD']) if not np.isnan(float(avant['MACD'])) else 0
            signal_av = float(avant['MACD_Signal']) if not np.isnan(float(avant['MACD_Signal'])) else 0
            if macd_now > signal_now and macd_av > signal_av: score_a += POIDS["MACD"]
            elif macd_now < signal_now and macd_av < signal_av: score_v += POIDS["MACD"]

            # Stoch
            stoch_now = float(derniere['Stoch_K']) if not np.isnan(float(derniere['Stoch_K'])) else 50
            stoch_avant = float(avant['Stoch_K']) if not np.isnan(float(avant['Stoch_K'])) else 50
            if stoch_now < 20 and stoch_avant < 20: score_a += POIDS["STOCH"]
            elif stoch_now > 80 and stoch_avant > 80: score_v += POIDS["STOCH"]

            # Fibo
            fib_618 = float(derniere['Fib_618']) if not np.isnan(float(derniere['Fib_618'])) else prix
            fib_382 = float(derniere['Fib_382']) if not np.isnan(float(derniere['Fib_382'])) else prix
            if prix <= fib_618: score_a += POIDS["FIBO"]
            elif prix >= fib_382: score_v += POIDS["FIBO"]

            # MA200
            ma200 = float(derniere['MA_200']) if not np.isnan(float(derniere['MA_200'])) else prix
            if prix <= ma200 * 1.02: score_a += POIDS["MA200"]
            elif prix >= ma200 * 1.10: score_v += POIDS["MA200"]

            # Bollinger
            bb_lower = float(derniere['BB_Lower']) if not np.isnan(float(derniere['BB_Lower'])) else prix
            bb_upper = float(derniere['BB_Upper']) if not np.isnan(float(derniere['BB_Upper'])) else prix
            if prix <= bb_lower: score_a += POIDS["BOLLINGER"]
            elif prix >= bb_upper: score_v += POIDS["BOLLINGER"]

            # Ichimoku
            if 'Ichi_Tenkan' in data.columns:
                tenkan = float(derniere['Ichi_Tenkan']) if not np.isnan(float(derniere.get('Ichi_Tenkan', np.nan))) else prix
                kijun = float(derniere['Ichi_Kijun']) if not np.isnan(float(derniere.get('Ichi_Kijun', np.nan))) else prix
                span_a = float(derniere.get('Ichi_SpanA', np.nan))
                span_b = float(derniere.get('Ichi_SpanB', np.nan))
                if not np.isnan(span_a) and not np.isnan(span_b):
                    nuage_haut = max(span_a, span_b)
                    nuage_bas = min(span_a, span_b)
                    if prix > nuage_haut and tenkan > kijun: score_a += POIDS["ICHIMOKU"]
                    elif prix < nuage_bas and tenkan < kijun: score_v += POIDS["ICHIMOKU"]

            # Position management
            if position is None:
                if score_a >= seuil_score and score_a > score_v:
                    position = "LONG"
                    prix_entree = prix
                elif score_v >= seuil_score:
                    position = "SHORT"
                    prix_entree = prix
            elif position == "LONG":
                sl = prix_entree - (1.5 * atr_val) if atr_val > 0 else prix_entree * 0.97
                tp = prix_entree + (2.5 * atr_val) if atr_val > 0 else prix_entree * 1.05
                if prix <= sl:
                    trades.append({'type': 'LONG', 'pnl': ((sl - prix_entree) / prix_entree) * 100, 'bars': i})
                    position = None
                elif prix >= tp:
                    trades.append({'type': 'LONG', 'pnl': ((tp - prix_entree) / prix_entree) * 100, 'bars': i})
                    position = None
                elif score_v >= seuil_score:
                    trades.append({'type': 'LONG', 'pnl': ((prix - prix_entree) / prix_entree) * 100, 'bars': i})
                    position = None
            elif position == "SHORT":
                sl = prix_entree + (1.5 * atr_val) if atr_val > 0 else prix_entree * 1.03
                tp = prix_entree - (2.5 * atr_val) if atr_val > 0 else prix_entree * 0.95
                if prix >= sl:
                    trades.append({'type': 'SHORT', 'pnl': ((prix_entree - sl) / prix_entree) * 100, 'bars': i})
                    position = None
                elif prix <= tp:
                    trades.append({'type': 'SHORT', 'pnl': ((prix_entree - tp) / prix_entree) * 100, 'bars': i})
                    position = None
                elif score_a >= seuil_score:
                    trades.append({'type': 'SHORT', 'pnl': ((prix_entree - prix) / prix_entree) * 100, 'bars': i})
                    position = None

        # Clôturer position ouverte
        if position and len(data) > 0:
            prix_final = float(data.iloc[-1]['Close'])
            if position == "LONG":
                trades.append({'type': 'LONG', 'pnl': ((prix_final - prix_entree) / prix_entree) * 100, 'bars': len(data)})
            else:
                trades.append({'type': 'SHORT', 'pnl': ((prix_entree - prix_final) / prix_entree) * 100, 'bars': len(data)})

        if not trades:
            return None

        df_trades = pd.DataFrame(trades)
        nb_trades = len(df_trades)
        nb_gagnants = len(df_trades[df_trades['pnl'] > 0])
        nb_perdants = len(df_trades[df_trades['pnl'] <= 0])
        win_rate = (nb_gagnants / nb_trades) * 100
        pnl_total = df_trades['pnl'].sum()
        pnl_moyen = df_trades['pnl'].mean()
        meilleur_trade = df_trades['pnl'].max()
        pire_trade = df_trades['pnl'].min()
        gains = df_trades[df_trades['pnl'] > 0]['pnl'].sum()
        pertes = abs(df_trades[df_trades['pnl'] <= 0]['pnl'].sum())
        profit_factor = gains / pertes if pertes > 0 else float('inf')
        cumul = df_trades['pnl'].cumsum()
        max_drawdown = (cumul - cumul.cummax()).min()

        # Sharpe ratio approximation
        if df_trades['pnl'].std() > 0:
            sharpe = (pnl_moyen / df_trades['pnl'].std()) * np.sqrt(nb_trades)
        else:
            sharpe = 0

        return {
            'nb_trades': nb_trades,
            'nb_gagnants': nb_gagnants,
            'nb_perdants': nb_perdants,
            'win_rate': win_rate,
            'pnl_total': pnl_total,
            'pnl_moyen': pnl_moyen,
            'meilleur_trade': meilleur_trade,
            'pire_trade': pire_trade,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'trades': df_trades,
        }
    except:
        return None


# ══════════════════════════════════════════════════════════
# INTERFACE PRINCIPALE v5.0
# ══════════════════════════════════════════════════════════

st.title("🧠 Trading Scanner v5.0")
st.caption("ML + Ichimoku + Order Flow + Macro + NLP | Score max: " + str(sum(POIDS.values())) + " pts")

# Badges des modules actifs
modules = []
if HAS_PANDAS_TA: modules.append("✅ pandas-ta")
else: modules.append("⚠️ pandas-ta")
if HAS_CCXT: modules.append("✅ ccxt")
else: modules.append("⚠️ ccxt")
if HAS_LGBM: modules.append("✅ LightGBM")
else: modules.append("⚠️ GradientBoosting")
st.caption(" | ".join(modules))

config = charger_config()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")

    seuil_defaut = config.get("seuil_score", 8.0)
    seuil_score = st.slider("Seuil d'alerte", 4.0, 20.0, seuil_defaut, 0.5)
    if seuil_score != seuil_defaut:
        config["seuil_score"] = seuil_score
        sauver_config(config)
    st.caption(f"Score max: {sum(POIDS.values())} pts | {len(POIDS)} indicateurs")

    st.divider()

    st.header("💰 Capital & Risque")
    capital_defaut = config.get("capital", 1000)
    capital = st.number_input("Capital (CHF)", min_value=0, value=capital_defaut, step=100)
    if capital != capital_defaut:
        config["capital"] = capital
        sauver_config(config)
    risque_pct = st.slider("Risque par trade (%)", 0.5, 5.0, 2.0, 0.5)

    st.divider()

    st.header("📊 Actifs")
    actifs_defaut = config.get("actifs", ["🥇 Or (Gold)", "₿ Bitcoin", "💵 EUR/USD"])
    actifs_defaut = [a for a in actifs_defaut if a in ACTIFS]
    if not actifs_defaut:
        actifs_defaut = ["🥇 Or (Gold)", "₿ Bitcoin", "💵 EUR/USD"]
    actifs_choisis = st.multiselect("Sélection", list(ACTIFS.keys()), default=actifs_defaut)
    if actifs_choisis != actifs_defaut:
        config["actifs"] = actifs_choisis
        sauver_config(config)

    st.divider()

    # ALERTES
    st.header("🔔 Alertes")
    alert_mode = st.radio("Mode", ["Aucune", "Email Bluewin", "Telegram"])
    email_addr = ""
    email_pass = ""
    tg_token = ""
    tg_chat_id = ""
    if alert_mode == "Email Bluewin":
        email_addr = st.text_input("Adresse email", placeholder="nom@bluewin.ch")
        email_pass = st.text_input("Mot de passe", type="password")
    elif alert_mode == "Telegram":
        tg_token = st.text_input("Bot Token", type="password")
        tg_chat_id = st.text_input("Chat ID")

    st.divider()

    # MACRO
    st.header("🌍 Macro Live")
    macro_data, macro_details = fetch_macro_data()
    for detail in macro_details[:6]:
        st.caption(detail)
    scores_list = [v.get('score', 0) for v in macro_data.values() if isinstance(v, dict) and 'score' in v]
    if scores_list:
        avg = np.mean(scores_list)
        if avg >= 2: st.success(f"Score: +{round(avg, 1)}")
        elif avg <= -2: st.error(f"Score: {round(avg, 1)}")
        else: st.info(f"Score: {round(avg, 1)}")

    st.divider()

    # AIDE
    with st.expander("📖 AIDE", expanded=False):
        st.markdown("""
**Nouveautés v5.0 :**
- 🤖 **ML (Machine Learning)** : Prédit le mouvement à 5j via LightGBM
- ☁️ **Ichimoku** : Nuage japonais (tendance + supports)
- 📊 **Order Flow** : Analyse le carnet d'ordres (crypto)
- 🎯 **S/R dynamiques** : Supports/Résistances auto
- 📈 **VWAP** : Volume Weighted Average Price
- ⚡ **ccxt** : Données temps réel crypto
- 📱 **Telegram** : Alertes instantanées
- 🔄 **MTF Weekly** : Confirmation hebdomadaire
- 🧵 **Scan parallèle** : 3x plus rapide
        """)

# --- BOUTONS ---
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    btn_scan = st.button("🚀 Scanner", type="primary", use_container_width=True)
with col2:
    btn_backtest = st.button("📊 Backtest", use_container_width=True)
with col3:
    btn_alert_test = st.button("🔔 Test Alerte", use_container_width=True)
with col4:
    btn_refresh = st.button("🔄 Refresh", use_container_width=True)

if btn_refresh:
    st.cache_data.clear()
    st.success("✅ Cache vidé !")

# --- SCAN ---
if btn_scan:
    if not actifs_choisis:
        st.warning("Choisis au moins un actif.")
    else:
        with st.spinner("🧠 Analyse v5.0 en cours (parallélisée)..."):
            resultats = lancer_scan(actifs_choisis, seuil_score, macro_data)

        if not resultats:
            st.error("Pas de données.")
        else:
            # Résumé en haut
            st.subheader("📋 Résultats")
            cols = st.columns(min(len(resultats), 4))
            for i, r in enumerate(resultats):
                with cols[i % len(cols)]:
                    if r['action'] == "ACHAT":
                        st.metric(r['nom'], f"{round(r['prix'], 2)}",
                                  f"🟢 LONG ({round(r['score_achat'], 1)}/{round(r['score_max'], 0)})")
                    elif r['action'] == "VENTE":
                        st.metric(r['nom'], f"{round(r['prix'], 2)}",
                                  f"🔴 SHORT ({round(r['score_vente'], 1)}/{round(r['score_max'], 0)})",
                                  delta_color="inverse")
                    elif r['action'] == "PLAT":
                        st.metric(r['nom'], f"{round(r['prix'], 2)}",
                                  f"😴 Plat (ADX {round(r['adx'], 0)})", delta_color="off")
                    else:
                        sc = max(r['score_achat'], r['score_vente'])
                        st.metric(r['nom'], f"{round(r['prix'], 2)}",
                                  f"⏸️ ({round(sc, 1)}/{round(r['score_max'], 0)})", delta_color="off")

            # Envoyer alertes
            alertes = [r for r in resultats if r['action'] in ["ACHAT", "VENTE"]]
            if alertes:
                for a in alertes:
                    if alert_mode == "Telegram" and tg_token and tg_chat_id:
                        msg = formater_alerte_telegram(a)
                        envoyer_telegram(msg, tg_token, tg_chat_id)
                    elif alert_mode == "Email Bluewin" and email_addr and email_pass:
                        direction = "LONG" if a['action'] == "ACHAT" else "SHORT"
                        envoyer_email(
                            f"🚨 Signal {direction} — {a['nom']}",
                            f"Prix: {round(a['prix'], 2)}\nScore: {round(max(a['score_achat'], a['score_vente']), 1)}",
                            email_addr, email_pass
                        )

            st.divider()

            # Détails par actif
            for idx, r in enumerate(resultats):
                icone = "🟢" if r['action'] == "ACHAT" else "🔴" if r['action'] == "VENTE" else "😴" if r['action'] == "PLAT" else "🟡"
                label = "LONG" if r['action'] == "ACHAT" else "SHORT" if r['action'] == "VENTE" else r['action']

                with st.expander(f"{icone} {r['nom']} — {label}", expanded=(r['action'] in ["ACHAT", "VENTE"])):

                    if r['action'] == "ACHAT":
                        st.success(f"🟢 SIGNAL LONG — Score {round(r['score_achat'], 1)}/{round(r['score_max'], 0)} (seuil: {seuil_score})")
                    elif r['action'] == "VENTE":
                        st.error(f"🔴 SIGNAL SHORT — Score {round(r['score_vente'], 1)}/{round(r['score_max'], 0)} (seuil: {seuil_score})")
                    elif r['action'] == "PLAT":
                        st.warning(f"😴 PLAT — ADX = {round(r['adx'], 1)}")
                    else:
                        st.info(f"⏸️ Attendre — Score {round(max(r['score_achat'], r['score_vente']), 1)}/{round(r['score_max'], 0)}")

                    # ML Prediction
                    if r.get('ml_prediction'):
                        ml = r['ml_prediction']
                        col_ml1, col_ml2, col_ml3 = st.columns(3)
                        with col_ml1:
                            st.metric("🤖 Proba Hausse", f"{round(ml['proba_hausse']*100, 0)}%")
                        with col_ml2:
                            st.metric("📊 Accuracy", f"{round(ml['accuracy']*100, 0)}%")
                        with col_ml3:
                            st.metric("🎯 Direction ML", ml['direction'])
                        if ml.get('top_features'):
                            st.caption("Top features: " + ", ".join([f"{f[0]}" for f in ml['top_features'][:3]]))

                    # SL/TP
                    if r['sl_tp'] and r['action'] in ["ACHAT", "VENTE"]:
                        st.markdown("#### 🎯 Stop-Loss & Take-Profit")
                        col_sl, col_tp, col_rr = st.columns(3)
                        with col_sl:
                            st.metric("🛑 Stop-Loss", f"{round(r['sl_tp']['stop_loss'], 2)}",
                                      f"-{round(r['sl_tp']['risque_pct'], 2)}%", delta_color="inverse")
                        with col_tp:
                            st.metric("🎯 Take-Profit", f"{round(r['sl_tp']['take_profit'], 2)}",
                                      f"+{round(r['sl_tp']['reward_pct'], 2)}%")
                        with col_rr:
                            st.metric("📐 R:R", f"1:{round(r['sl_tp']['ratio_rr'], 1)}",
                                      f"ATR: {round(r['sl_tp']['atr'], 2)}")
                        if capital > 0:
                            nb, taille = calculer_taille_position(capital, risque_pct, r['prix'], r['sl_tp']['stop_loss'])
                            st.caption(f"💰 {round(capital, 0)} CHF ({risque_pct}% risque) -> {round(nb, 4)} unités ({round(taille, 2)} CHF)")

                    # Timing
                    t = r.get('timing')
                    if t and r['action'] in ["ACHAT", "VENTE"]:
                        if t['heure_a_eviter']:
                            st.warning(f"🕐 ⛔ MAUVAISE HEURE ({t['heure']}h)")
                        elif (r['action'] == "ACHAT" and t['heure_bonne_achat']) or (r['action'] == "VENTE" and t['heure_bonne_vente']):
                            st.success(f"🕐 ✅ Bonne heure ({t['heure']}h)")
                        else:
                            ideal = t['achat_ideal'] if r['action'] == "ACHAT" else t['vente_ideal']
                            st.info(f"🕐 Heure neutre ({t['heure']}h) | Idéal: {ideal}")

                    # MTF
                    mtf = r.get('mtf')
                    if mtf:
                        if mtf.get('consensus') == r['action']:
                            st.success(f"📊 Multi-TF CONFIRME {label}")
                        elif mtf.get('consensus') != "NEUTRE" and mtf.get('consensus') != r['action']:
                            st.warning(f"⚠️ Multi-TF = {mtf['consensus']} -> CONFLIT !")

                    # Graphique
                    fig = creer_graphique(r['data'], r['nom'], r.get('supports'), r.get('resistances'))
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{idx}")

                    # Détails indicateurs
                    st.markdown("**Détail indicateurs:**")
                    for ind, signal, explication in r['details']:
                        if signal == "ACHAT":
                            st.write(f"✅ **{ind}** — {explication}")
                        elif signal == "VENTE":
                            st.write(f"❌ **{ind}** — {explication}")
                        elif signal == "OK":
                            st.write(f"💪 **{ind}** — {explication}")
                        elif signal == "PLAT":
                            st.write(f"😴 **{ind}** — {explication}")
                        else:
                            st.write(f"⏸️ **{ind}** — {explication}")

            # Historique des signaux
            for a in alertes:
                st.session_state.historique_signaux.append({
                    'time': datetime.now(pytz.timezone('Europe/Zurich')).strftime("%H:%M"),
                    'nom': a['nom'],
                    'action': a['action'],
                    'score': round(max(a['score_achat'], a['score_vente']), 1),
                })


# --- BACKTEST ---
if btn_backtest:
    if not actifs_choisis:
        st.warning("Choisis au moins un actif.")
    else:
        st.divider()
        st.header("📊 Backtesting 1 an")
        st.caption(f"Seuil = {seuil_score} | SL = 1.5×ATR | TP = 2.5×ATR | Ichimoku inclus")

        for nom in actifs_choisis:
            ticker = ACTIFS[nom]
            with st.spinner(f"Backtesting {nom}..."):
                bt = backtester_strategie(ticker, seuil_score)

            if bt:
                with st.expander(f"📊 {nom}", expanded=True):
                    col_a, col_b, col_c, col_d, col_e = st.columns(5)
                    with col_a:
                        st.metric("💰 P&L Total", f"{round(bt['pnl_total'], 2)}%",
                                  f"{bt['nb_trades']} trades")
                    with col_b:
                        st.metric("🎯 Win Rate", f"{round(bt['win_rate'], 1)}%",
                                  f"{bt['nb_gagnants']}W / {bt['nb_perdants']}L")
                    with col_c:
                        st.metric("📈 Profit Factor", f"{round(bt['profit_factor'], 2)}")
                    with col_d:
                        st.metric("📉 Max Drawdown", f"{round(bt['max_drawdown'], 2)}%",
                                  delta_color="inverse")
                    with col_e:
                        st.metric("📐 Sharpe", f"{round(bt['sharpe'], 2)}")

                    if bt['win_rate'] >= 60 and bt['profit_factor'] >= 1.5:
                        st.success("✅ Stratégie PROFITABLE !")
                    elif bt['win_rate'] >= 50:
                        st.info("🟡 Correcte — peut être améliorée")
                    else:
                        st.error("❌ Non rentable — ajuste le seuil")

                    # Equity curve
                    cumul = bt['trades']['pnl'].cumsum()
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(y=cumul.values, mode='lines',
                                               line=dict(color='#667eea', width=2)))
                    fig_eq.update_layout(title="Equity Curve", height=200, template="plotly_dark",
                                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_eq, use_container_width=True, key=f"eq_{nom}")
            else:
                st.info(f"{nom} : pas assez de données")


# --- TEST ALERTE ---
if btn_alert_test:
    if alert_mode == "Telegram" and tg_token and tg_chat_id:
        success = envoyer_telegram("🧪 <b>Test Scanner v5.0</b>\n\nÇa marche ! 🚀", tg_token, tg_chat_id)
        if success:
            st.success("✅ Telegram envoyé !")
        else:
            st.error("❌ Erreur Telegram — vérifie le token et chat ID")
    elif alert_mode == "Email Bluewin" and email_addr and email_pass:
        result = envoyer_email("Test Scanner v5.0", "Ça marche !", email_addr, email_pass)
        if result is True:
            st.success("✅ Email envoyé !")
        else:
            st.error(f"❌ {result}")
    else:
        st.warning("Configure une méthode d'alerte d'abord.")


# ══════════════════════════════════════════════════════════
# SECTIONS BASSES (News, On-Chain, etc.)
# ══════════════════════════════════════════════════════════

st.divider()

# --- NLP NEWS ---
st.header("📰 Sentiment News (NLP)")
col_n1, col_n2, col_n3 = st.columns(3)
with col_n1:
    st.subheader("Bitcoin")
    news_btc = get_news_sentiment("BTC-USD")
    st.metric("Score", f"{round(news_btc['score'], 1)}/10")
    st.caption(news_btc['details'])
    if news_btc.get('headlines'):
        for h in news_btc['headlines'][:2]:
            emoji = "🟢" if h['score'] > 0.1 else "🔴" if h['score'] < -0.1 else "⚪"
            st.caption(f"{emoji} {h['title'][:60]}...")
with col_n2:
    st.subheader("Or")
    news_or = get_news_sentiment("GC=F")
    st.metric("Score", f"{round(news_or['score'], 1)}/10")
    st.caption(news_or['details'])
with col_n3:
    st.subheader("S&P 500")
    news_sp = get_news_sentiment("^GSPC")
    st.metric("Score", f"{round(news_sp['score'], 1)}/10")
    st.caption(news_sp['details'])

st.divider()

# --- ON-CHAIN ---
st.header("⛓️ On-Chain Bitcoin")
onchain = get_onchain_score("BTC-USD")
st.metric("Score On-Chain", f"{onchain['score']}/10")
for d in onchain['details']:
    st.write(d)

st.divider()

# --- DIVERGENCE OR/BTC ---
st.header("🔗 Divergence Or/Bitcoin (7j)")
div_data = get_divergence_or_btc()
if div_data:
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.metric("Or (7j)", f"{round(div_data['var_or'], 1)}%")
    with col_d2:
        st.metric("BTC (7j)", f"{round(div_data['var_btc'], 1)}%")
    with col_d3:
        st.metric("Écart", f"{round(div_data['ecart'], 1)}%")

# --- HISTORIQUE SIGNAUX ---
if st.session_state.historique_signaux:
    st.divider()
    st.header("📜 Historique des signaux (session)")
    for s in reversed(st.session_state.historique_signaux[-10:]):
        emoji = "🟢" if s['action'] == "ACHAT" else "🔴"
        st.caption(f"{s['time']} | {emoji} {s['nom']} — Score {s['score']}")


# ══════════════════════════════════════════════════════════
# SCAN AUTOMATIQUE
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.divider()
    st.header("⏰ Scan Auto")
    auto_scan = st.toggle("Activer scan auto", value=False)
    intervalle = st.selectbox("Fréquence", [
        "30 secondes", "1 minute", "5 minutes", "15 minutes", "30 minutes"
    ], index=2)
    intervalles_sec = {"30 secondes": 30, "1 minute": 60, "5 minutes": 300, "15 minutes": 900, "30 minutes": 1800}
    sec = intervalles_sec[intervalle]
    if auto_scan:
        st.success(f"🔄 Scan toutes les {intervalle}")

if auto_scan and actifs_choisis:
    st.subheader(f"🔄 Scan automatique — toutes les {intervalle}")
    placeholder = st.empty()
    compteur = st.empty()

    while True:
        now = datetime.now(pytz.timezone("Europe/Zurich")).strftime("%d.%m.%Y %H:%M:%S")
        with placeholder.container():
            st.caption(f"⏰ Dernier scan : {now}")
            resultats = lancer_scan(actifs_choisis, seuil_score, macro_data)
            if resultats:
                cols = st.columns(min(len(resultats), 4))
                for i, r in enumerate(resultats):
                    with cols[i % len(cols)]:
                        if r['action'] == "ACHAT":
                            st.metric(r['nom'], f"{round(r['prix'], 2)}", f"🟢 LONG ({round(r['score_achat'], 1)})")
                        elif r['action'] == "VENTE":
                            st.metric(r['nom'], f"{round(r['prix'], 2)}", f"🔴 SHORT ({round(r['score_vente'], 1)})", delta_color="inverse")
                        else:
                            sc = max(r['score_achat'], r['score_vente'])
                            st.metric(r['nom'], f"{round(r['prix'], 2)}", f"⏸️ ({round(sc, 1)})", delta_color="off")

                alertes = [r for r in resultats if r['action'] in ["ACHAT", "VENTE"]]
                if alertes:
                    st.warning(f"🚨 {len(alertes)} SIGNAL(S) !")
                    for a in alertes:
                        if alert_mode == "Telegram" and tg_token and tg_chat_id:
                            envoyer_telegram(formater_alerte_telegram(a), tg_token, tg_chat_id)

        for remaining in range(sec, 0, -1):
            mins, secs = divmod(remaining, 60)
            compteur.caption(f"⏳ Prochain scan dans {str(mins).zfill(2)}:{str(secs).zfill(2)}")
            time.sleep(1)
        st.rerun()

# ══════════════════════════════════════════════════════════
# 🎮 MODULE SIMULATION D'INVESTISSEMENT
# ══════════════════════════════════════════════════════════

SIMULATION_FILE = "simulation_data.json"
ALERTES_PRIX_FILE = "alertes_prix.json"

def charger_simulations():
    if os.path.exists(SIMULATION_FILE):
        try:
            with open(SIMULATION_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def sauver_simulations(sims):
    with open(SIMULATION_FILE, "w") as f:
        json.dump(sims, f, indent=2)

def charger_alertes_prix():
    if os.path.exists(ALERTES_PRIX_FILE):
        try:
            with open(ALERTES_PRIX_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def sauver_alertes_prix(alertes):
    with open(ALERTES_PRIX_FILE, "w") as f:
        json.dump(alertes, f, indent=2)

def get_prix_actuel(ticker):
    """Récupère le prix actuel d'un actif — multiple fallbacks"""
    # Méthode 1 : ccxt (crypto)
    try:
        if HAS_CCXT and ticker in CCXT_SYMBOLS:
            exchange = ccxt.binance({'enableRateLimit': True})
            t = exchange.fetch_ticker(CCXT_SYMBOLS[ticker])
            if t and t.get('last'):
                return float(t['last'])
    except:
        pass
    
    # Méthode 2 : yfinance Ticker
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.get('lastPrice') or info.get('regularMarketPrice')
        if price and price > 0:
            return float(price)
    except:
        pass
    
    # Méthode 3 : yfinance download
    try:
        data = yf.download(ticker, period="5d", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    # Méthode 4 : yfinance download 1mo (fallback ultime)
    try:
        data = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return None

st.divider()
st.header("🎮 Simulation d'investissement")
st.caption("Investis virtuellement et suis tes gains/pertes en temps réel")

simulations = charger_simulations()

with st.expander("➕ Nouvelle simulation", expanded=not simulations):
    col_sim1, col_sim2, col_sim3 = st.columns(3)
    with col_sim1:
        sim_actif = st.selectbox("Actif à simuler", list(ACTIFS.keys()), key="sim_actif_select")
    with col_sim2:
        sim_montant = st.number_input("Montant (CHF)", min_value=10, max_value=1000000, value=1000, step=100, key="sim_montant_input")
    with col_sim3:
        sim_direction = st.radio("Direction", ["📈 LONG (hausse)", "📉 SHORT (baisse)"], key="sim_direction_radio")

    if st.button("🚀 Investir (simulation)", type="primary", key="btn_sim_invest"):
        ticker = ACTIFS[sim_actif]
        prix_entree = get_prix_actuel(ticker)
        if prix_entree:
            tz_suisse = pytz.timezone("Europe/Zurich")
            now = datetime.now(tz_suisse)
            direction = "LONG" if "LONG" in sim_direction else "SHORT"
            nb_unites = sim_montant / prix_entree
            nouvelle_sim = {
                "id": hashlib.md5(f"{sim_actif}{now.isoformat()}".encode()).hexdigest()[:8],
                "actif": sim_actif, "ticker": ticker, "direction": direction,
                "montant_initial": sim_montant, "prix_entree": prix_entree,
                "nb_unites": nb_unites, "date_entree": now.strftime("%d.%m.%Y %H:%M:%S"),
                "timestamp": now.isoformat(), "statut": "OUVERT",
            }
            simulations.append(nouvelle_sim)
            sauver_simulations(simulations)
            st.success(f"✅ {sim_actif} {direction} @ {round(prix_entree, 4)} | {sim_montant} CHF")
            st.rerun()
        else:
            st.error("❌ Impossible de récupérer le prix.")

sims_ouvertes = [s for s in simulations if s['statut'] == "OUVERT"]
if sims_ouvertes:
    st.subheader(f"📊 Portefeuille ({len(sims_ouvertes)} position{'s' if len(sims_ouvertes) > 1 else ''})")
    total_investi = 0
    total_pnl = 0
    pnl_bars = []

    for sim in sims_ouvertes:
        prix_actuel = get_prix_actuel(sim['ticker'])
        if not prix_actuel:
            continue
        if sim['direction'] == "LONG":
            pnl_pct = ((prix_actuel - sim['prix_entree']) / sim['prix_entree']) * 100
        else:
            pnl_pct = ((sim['prix_entree'] - prix_actuel) / sim['prix_entree']) * 100
        pnl_chf = sim['montant_initial'] * (pnl_pct / 100)
        valeur = sim['montant_initial'] + pnl_chf
        total_investi += sim['montant_initial']
        total_pnl += pnl_chf
        pnl_bars.append({'actif': sim['actif'], 'pnl_pct': pnl_pct, 'pnl_chf': pnl_chf})

        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns([2, 1.5, 1.5, 1.5, 0.8])
        with col_s1:
            emoji_dir = "📈" if sim['direction'] == "LONG" else "📉"
            st.markdown(f"**{emoji_dir} {sim['actif']}** ({sim['direction']})")
            st.caption(f"Entrée: {sim['date_entree']}")
        with col_s2:
            st.metric("Prix", f"{round(prix_actuel, 4)}", f"E: {round(sim['prix_entree'], 4)}")
        with col_s3:
            st.metric("P&L", f"{round(pnl_chf, 2)} CHF", f"{'+' if pnl_pct >= 0 else ''}{round(pnl_pct, 2)}%",
                      delta_color="normal" if pnl_chf >= 0 else "inverse")
        with col_s4:
            st.metric("Valeur", f"{round(valeur, 2)} CHF", f"Investi: {sim['montant_initial']}")
        with col_s5:
            if st.button("❌", key=f"close_{sim['id']}"):
                sim['statut'] = "FERME"
                sim['prix_sortie'] = prix_actuel
                sim['date_sortie'] = datetime.now(pytz.timezone("Europe/Zurich")).strftime("%d.%m.%Y %H:%M:%S")
                sim['pnl_chf'] = pnl_chf
                sim['pnl_pct'] = pnl_pct
                sauver_simulations(simulations)
                st.rerun()

    # Résumé + Graphique performance
    st.divider()
    col_t1, col_t2, col_t3 = st.columns(3)
    pnl_total_pct = (total_pnl / total_investi * 100) if total_investi > 0 else 0
    col_t1.metric("💰 Total investi", f"{round(total_investi, 0)} CHF")
    col_t2.metric("📈 P&L Total", f"{round(total_pnl, 2)} CHF", f"{'+' if pnl_total_pct >= 0 else ''}{round(pnl_total_pct, 2)}%")
    col_t3.metric("📊 Positions", f"{len(sims_ouvertes)}")

    # Graphique barres P&L
    if pnl_bars:
        fig_sim = go.Figure()
        noms = [p['actif'] for p in pnl_bars]
        pnls = [p['pnl_pct'] for p in pnl_bars]
        colors = ['#00d2ff' if p >= 0 else '#f5576c' for p in pnls]
        fig_sim.add_trace(go.Bar(x=noms, y=pnls, marker_color=colors,
                                 text=[f"{p:+.1f}%" for p in pnls], textposition='outside'))
        fig_sim.update_layout(title="Performance par position", height=300, template="plotly_dark",
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig_sim, use_container_width=True)

# Historique fermées
sims_fermees = [s for s in simulations if s['statut'] == "FERME"]
if sims_fermees:
    with st.expander(f"📜 Historique ({len(sims_fermees)} clôturée{'s' if len(sims_fermees) > 1 else ''})"):
        for sim in reversed(sims_fermees[-20:]):
            emoji = "🟢" if sim.get('pnl_chf', 0) >= 0 else "🔴"
            st.caption(f"{emoji} {sim['actif']} ({sim['direction']}) | P&L: {round(sim.get('pnl_chf', 0), 2)} CHF ({round(sim.get('pnl_pct', 0), 2)}%) | {sim.get('date_sortie', '?')}")
        if len(sims_fermees) >= 2:
            pnls_hist = [s.get('pnl_pct', 0) for s in sims_fermees]
            gagnants = sum(1 for p in pnls_hist if p > 0)
            # Equity curve
            pnls_cum = np.cumsum([s.get('pnl_chf', 0) for s in sims_fermees])
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(y=pnls_cum, mode='lines+markers', line=dict(color='#667eea', width=2)))
            fig_eq.update_layout(title="💰 Equity Curve (simulations)", height=250, template="plotly_dark",
                                 paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_eq, use_container_width=True)
            st.caption(f"Win Rate: {round(gagnants/len(pnls_hist)*100, 0)}% | Moy: {round(np.mean(pnls_hist), 2)}% | Best: +{round(max(pnls_hist), 2)}% | Worst: {round(min(pnls_hist), 2)}%")

if simulations:
    if st.button("🗑️ Effacer toutes les simulations", key="reset_sims"):
        sauver_simulations([])
        st.rerun()


# ══════════════════════════════════════════════════════════
# 🚨 ALERTES PAR PRIX CIBLE
# ══════════════════════════════════════════════════════════

st.divider()
st.header("🚨 Alertes par prix cible")
st.caption("Reçois une notification quand un actif atteint ton prix")

alertes_prix = charger_alertes_prix()

with st.expander("➕ Nouvelle alerte prix", expanded=not alertes_prix):
    col_al1, col_al2, col_al3 = st.columns(3)
    with col_al1:
        al_actif = st.selectbox("Actif", list(ACTIFS.keys()), key="al_actif")
    with col_al2:
        prix_actuel_al = get_prix_actuel(ACTIFS[al_actif])
        st.caption(f"Prix actuel: {round(prix_actuel_al, 4) if prix_actuel_al else '?'}")
        al_prix = st.number_input("Prix cible", min_value=0.0, value=float(round(prix_actuel_al, 2)) if prix_actuel_al else 0.0, step=0.01, key="al_prix")
    with col_al3:
        al_condition = st.radio("Quand le prix passe...", ["au-dessus ⬆️", "en-dessous ⬇️"], key="al_cond")

    if st.button("➕ Créer l'alerte", type="primary", key="btn_al_create"):
        condition = "au-dessus" if "dessus" in al_condition else "en-dessous"
        nouvelle_al = {
            "id": hashlib.md5(f"{al_actif}{al_prix}{datetime.now().isoformat()}".encode()).hexdigest()[:8],
            "actif": al_actif, "ticker": ACTIFS[al_actif],
            "prix_cible": al_prix, "condition": condition,
            "date_creation": datetime.now(pytz.timezone("Europe/Zurich")).strftime("%d.%m.%Y %H:%M"),
            "declenchee": False,
        }
        alertes_prix.append(nouvelle_al)
        sauver_alertes_prix(alertes_prix)
        st.success(f"✅ Alerte: {al_actif} {condition} {al_prix}")
        st.rerun()

# Alertes actives
alertes_actives = [a for a in alertes_prix if not a.get('declenchee', False)]
if alertes_actives:
    st.subheader(f"🔔 Alertes actives ({len(alertes_actives)})")
    for al in alertes_actives:
        prix_now = get_prix_actuel(al['ticker'])
        if prix_now:
            distance = ((al['prix_cible'] - prix_now) / prix_now) * 100
            emoji = "⬆️" if al['condition'] == "au-dessus" else "⬇️"
            # Vérifier si déclenchée
            declenchee = False
            if al['condition'] == "au-dessus" and prix_now >= al['prix_cible']:
                declenchee = True
            elif al['condition'] == "en-dessous" and prix_now <= al['prix_cible']:
                declenchee = True
            if declenchee:
                al['declenchee'] = True
                al['date_declenchement'] = datetime.now(pytz.timezone("Europe/Zurich")).strftime("%d.%m.%Y %H:%M")
                sauver_alertes_prix(alertes_prix)
                st.success(f"🚨 DÉCLENCHÉE ! {al['actif']} = {round(prix_now, 4)} ({al['condition']} {al['prix_cible']})")
                if alert_mode == "Telegram" and tg_token and tg_chat_id:
                    envoyer_telegram(f"🚨 ALERTE PRIX\n{al['actif']} = {round(prix_now, 4)}\nCible: {al['condition']} {al['prix_cible']}", tg_token, tg_chat_id)
            else:
                col_a1, col_a2, col_a3, col_a4 = st.columns([2, 1.5, 1.5, 0.8])
                with col_a1:
                    st.markdown(f"**{emoji} {al['actif']}**")
                    st.caption(f"Créée: {al['date_creation']}")
                with col_a2:
                    st.metric("Cible", f"{al['prix_cible']}", al['condition'])
                with col_a3:
                    st.metric("Distance", f"{round(abs(distance), 2)}%", f"Actuel: {round(prix_now, 4)}")
                with col_a4:
                    if st.button("🗑️", key=f"del_al_{al['id']}"):
                        alertes_prix.remove(al)
                        sauver_alertes_prix(alertes_prix)
                        st.rerun()

# Alertes déclenchées
alertes_passees = [a for a in alertes_prix if a.get('declenchee', False)]
if alertes_passees:
    with st.expander(f"✅ Historique alertes ({len(alertes_passees)})"):
        for al in reversed(alertes_passees[-10:]):
            st.caption(f"✅ {al['actif']} {al['condition']} {al['prix_cible']} — {al.get('date_declenchement', '?')}")

if alertes_prix:
    if st.button("🗑️ Effacer toutes les alertes", key="reset_alertes"):
        sauver_alertes_prix([])
        st.rerun()


# ══════════════════════════════════════════════════════════
# 📖 AIDE & APPRENTISSAGE (popup)
# ══════════════════════════════════════════════════════════

st.divider()
with st.expander("📖 Aide & Apprentissage (cliquer pour ouvrir)", expanded=False):
    tab_glossaire, tab_indicateurs, tab_sources = st.tabs(["🔤 Glossaire", "📊 Indicateurs", "🎓 Apprendre"])

    with tab_glossaire:
        st.markdown("""
| Terme anglais | Français | Explication |
|---|---|---|
| **Bull / Bullish** | Haussier | Le marché monte 📈 |
| **Bear / Bearish** | Baissier | Le marché descend 📉 |
| **Long** | Achat | Pari sur la hausse |
| **Short** | Vente à découvert | Pari sur la baisse |
| **Stop-Loss (SL)** | Arrêt de perte | Limite ta perte auto |
| **Take-Profit (TP)** | Prise de bénéfice | Encaisse ton gain auto |
| **Risk:Reward (R:R)** | Risque/Récompense | 1:2 = risque 1 gagner 2 |
| **Spread** | Écart | Diff prix achat/vente |
| **Leverage** | Effet de levier | Multiplie gains ET pertes |
| **Drawdown** | Perte max | Chute depuis un sommet |
| **Win Rate** | Taux de réussite | % de trades gagnants |
| **Profit Factor** | Facteur de profit | Gains ÷ Pertes |
| **Breakout** | Cassure | Prix sort d'une zone |
| **Support** | Support | Plancher où ça rebondit |
| **Resistance** | Résistance | Plafond bloquant |
| **ATH** | Plus haut historique | All-Time High |
| **FOMO** | Peur de rater | Fear Of Missing Out |
| **FUD** | Peur/Doute | Fear Uncertainty Doubt |
| **DCA** | Achat régulier | Dollar Cost Averaging |
| **Whale** | Baleine | Gros investisseur |
| **Funding Rate** | Taux financement | Coût position ouverte |
| **Open Interest** | Intérêt ouvert | Contrats futures ouverts |
| **Liquidation** | Liquidation | Position fermée de force |
| **Slippage** | Glissement | Prix voulu ≠ exécuté |
| **Scalping** | Scalping | Trades très courts |
| **Swing Trading** | Swing | Trades quelques jours |
| **Backtesting** | Test historique | Tester sur le passé |
| **Sharpe Ratio** | Ratio de Sharpe | Performance/risque |
        """)

    with tab_indicateurs:
        st.markdown("""
#### 📈 RSI (Relative Strength Index) — 0 à 100
- **< 30** = Survendu → rebond probable
- **> 70** = Suracheté → correction probable
- Période : 14 jours

#### 📊 MACD (Moving Average Convergence Divergence)
- MACD > Signal = **Bullish** (tendance hausse)
- MACD < Signal = **Bearish** (tendance baisse)
- Histogramme = force du signal

#### 🎯 Stochastique
- **< 20** = Survendu | **> 80** = Suracheté

#### 📐 Fibonacci (Retracement)
- Niveaux : 23.6%, 38.2%, **61.8%**, 78.6%
- Le prix rebondit souvent sur ces niveaux

#### 📏 MA200 (Moyenne Mobile 200 jours)
- Prix au-dessus = tendance haussière long terme
- Prix en dessous = tendance baissière

#### ☁️ Ichimoku (Nuage japonais)
- Au-dessus du nuage = **Bullish**
- En dessous = **Bearish**
- Dans le nuage = **Indécis**
- Tenkan > Kijun = signal achat

#### 📊 Bandes de Bollinger
- Prix touche bande basse → survente possible
- Prix touche bande haute → surachat possible
- Bandes serrées → explosion de volatilité à venir

#### 💪 ADX (Force de tendance)
- **< 25** = Marché plat → PAS DE SIGNAL
- **> 25** = Tendance confirmée → signaux fiables
- **> 40** = Tendance très forte

#### 📈 VWAP (Prix moyen pondéré volume)
- Prix sous VWAP → "bon marché" pour institutionnels
- Prix au-dessus → "cher"

#### 🤖 Machine Learning
- Prédit hausse >1% à 5 jours
- Accuracy = fiabilité du modèle
- Confiance > 55% pour signal

#### 📊 Order Flow (Carnet d'ordres)
- Plus d'acheteurs → prix monte
- Plus de vendeurs → prix baisse
- Crypto uniquement (via Binance)

#### 🔀 Divergences
- Prix lower low + RSI higher low = **divergence haussière** (retournement)
- Prix higher high + RSI lower high = **divergence baissière**

#### 🌍 Score Macro
- Combine: Dollar, VIX, Taux, Pétrole, S&P, Fear & Greed, Funding
- Pondéré par catégorie d'actif

#### ⛓️ On-Chain (Bitcoin)
- Fees, Mempool, Hashrate, L/S Ratio, DeFi TVL
        """)

    with tab_sources:
        st.markdown("""
#### 🇫🇷 Ressources en français
- [Zonebourse](https://zonebourse.com) — Articles + formations
- [ABC Bourse](https://abcbourse.com) — Formation gratuite
- [Café de la Bourse](https://cafedelabourse.com) — Didactique

#### 🇬🇧 Ressources en anglais
- [Investopedia](https://investopedia.com) — Encyclopédie complète
- [BabyPips](https://babypips.com) — Cours Forex/Trading
- [TradingView](https://tradingview.com) — Graphiques + communauté
- [Coinglass](https://coinglass.com) — Données futures crypto

#### 📚 Livres recommandés
- *L'analyse technique des marchés financiers* — John Murphy
- *Trading in the Zone* — Mark Douglas (psychologie)
- *The Intelligent Investor* — Benjamin Graham

#### 🛠️ Outils gratuits
- **TradingView** — Graphiques + indicateurs
- **CoinMarketCap** — Données crypto
- **ForexFactory** — Calendrier économique
- **Mempool.space** — Bitcoin on-chain
- **DeFi Llama** — TVL DeFi

#### ⚠️ Règles d'or
1. 🎮 Commence en **simulation** (tu y es !)
2. 💰 Max **1-2%** risque par trade
3. 📐 Ratio R:R minimum **1:2**
4. 🧘 Jamais trader sous **émotion**
5. 📓 Tiens un **journal de trading**
6. 💪 Vérifie l'**ADX** avant d'entrer
7. 🔄 **Backteste** ta stratégie d'abord
8. ⏰ Respecte les **horaires optimaux**
9. 📊 Confirme sur **plusieurs timeframes**
10. 📱 Ne regarde pas toutes les 5 minutes
        """)

# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════

st.markdown("---")
st.caption(f"🧠 Trading Scanner v5.0 — Ultimate Edition | ⚠️ Pas un conseil financier")
st.caption(f"Score max: {sum(POIDS.values())} pts | {len(ACTIFS)} actifs | {len(POIDS)} indicateurs | ML + Ichimoku + Order Flow")
