# examples/trade_bot.py

import asyncio
import signal
import random
import numpy as np
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from collections import deque
from datetime import datetime

email, password = credentials()
client = Quotex(
    email=email,
    password=password,
    lang="pt",
)

# ===================================================================
#  STRATEGIES & INDICATORS – copied from TRADEIQDEV x AI BOT
# ===================================================================

# ---------- Global settings (user-configurable) ----------
EMA_PERIOD = 10
RSI_PERIOD = 14
CURRENT_STRATEGY = "EMA_RSI"          # default
MIN_SIGNAL_SCORE = 4
SUPPORT_RESISTANCE_STRATEGY = False   # enable/disable S/R strategy
SUPERTREND_STRATEGY = False           # enable/disable Supertrend strategy
AVAILABLE_STRATEGIES = [
    "EMA_RSI", "Trend", "Bollinger", "Support_Resistance",
    "Trend_Reverse", "Price_Action", "Supertrend", "FVG_Strategy",
    "TripleConfirmation"   # <-- ADDED FOR TRIPLE CONFIRMATION
]

# ---------- Constants for Triple Confirmation strategy ----------
TRIPLE_CONFIRMATION_EMA_FAST = 20
TRIPLE_CONFIRMATION_EMA_SLOW = 50
TRIPLE_CONFIRMATION_RSI_PERIOD = 7
TRIPLE_CONFIRMATION_STOCH_K = 14
TRIPLE_CONFIRMATION_STOCH_D = 3
# Slightly relaxed thresholds to get more signals
TRIPLE_CALL_RSI_MIN = 45
TRIPLE_PUT_RSI_MAX = 55
TRIPLE_STOCH_OVERBOUGHT = 65
TRIPLE_STOCH_OVERSOLD = 35

# ---------- Indicator functions ----------
def ema(values, period):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    ema_val = sum(values[-period:]) / period
    for i in range(-period + 1, 0):
        ema_val = values[i] * alpha + ema_val * (1 - alpha)
    return ema_val

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(len(prices)-period, len(prices)-1):
        change = prices[i+1] - prices[i]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    if not gains or not losses:
        return 50.0
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_bollinger(prices, period=20, std_dev=2):
    if len(prices) < period:
        return None, None, None
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    return ma, upper, lower

def calculate_support_resistance_levels(prices, lookback=20):
    if len(prices) < lookback:
        return None, None
    recent_prices = prices[-lookback:]
    resistance = max(recent_prices)
    support = min(recent_prices)
    return support, resistance

def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    if len(prices) < slow_period:
        return None, None, None
    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)
    if fast_ema is None or slow_ema is None:
        return None, None, None
    macd_line = fast_ema - slow_ema
    # Signal line (simplified)
    signal_line = ema([macd_line], signal_period)
    macd_histogram = macd_line - signal_line if signal_line else None
    return macd_line, signal_line, macd_histogram

def calculate_parabolic_sar(candles, acceleration=0.02, maximum=0.2):
    if len(candles) < 5:
        return []
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    sar_values = []
    uptrend = True
    sar = low[0]
    ep = high[0]
    af = acceleration
    for i in range(len(candles)):
        sar_values.append(sar)
        if uptrend:
            if low[i] < sar:
                uptrend = False
                sar = ep
                ep = low[i]
                af = acceleration
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + acceleration, maximum)
                sar = sar + af * (ep - sar)
                if i >= 2:
                    sar = min(sar, low[i-1], low[i-2])
        else:
            if high[i] > sar:
                uptrend = True
                sar = ep
                ep = high[i]
                af = acceleration
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + acceleration, maximum)
                sar = sar + af * (ep - sar)
                if i >= 2:
                    sar = max(sar, high[i-1], high[i-2])
    return sar_values

def calculate_supertrend(candles, period=10, multiplier=3):
    if len(candles) < period:
        return [], []
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    close = [c['close'] for c in candles]
    # ATR
    tr = []
    for i in range(1, len(high)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr.append(max(hl, hc, lc))
    atr = [sum(tr[:period]) / period]
    for i in range(period, len(tr)):
        atr.append((atr[-1] * (period - 1) + tr[i]) / period)
    supertrend = []
    trend = []
    for i in range(len(candles)):
        if i < period:
            supertrend.append(None)
            trend.append(None)
            continue
        hl2 = (high[i] + low[i]) / 2
        upper_band = hl2 + multiplier * atr[i-period]
        lower_band = hl2 - multiplier * atr[i-period]
        if i == period:
            supertrend.append(upper_band)
            trend.append(1)
        else:
            if close[i] > supertrend[-1]:
                current_trend = 1
                supertrend.append(max(lower_band, supertrend[-1]) if trend[-1] == 1 else lower_band)
            else:
                current_trend = -1
                supertrend.append(min(upper_band, supertrend[-1]) if trend[-1] == -1 else upper_band)
            trend.append(current_trend)
    return supertrend, trend

def detect_price_action_patterns(candles):
    if len(candles) < 5:
        return []
    patterns = []
    for i in range(2, len(candles) - 2):
        # Bullish Engulfing
        if (candles[i-1]['close'] < candles[i-1]['open'] and
            candles[i]['close'] > candles[i]['open'] and
            candles[i]['open'] < candles[i-1]['close'] and
            candles[i]['close'] > candles[i-1]['open']):
            patterns.append({'type': 'BULLISH_ENGULFING', 'candle_index': i,
                             'strength': (candles[i]['close'] - candles[i-1]['open']) / candles[i-1]['open']})
        # Bearish Engulfing
        elif (candles[i-1]['close'] > candles[i-1]['open'] and
              candles[i]['close'] < candles[i]['open'] and
              candles[i]['open'] > candles[i-1]['close'] and
              candles[i]['close'] < candles[i-1]['open']):
            patterns.append({'type': 'BEARISH_ENGULFING', 'candle_index': i,
                             'strength': (candles[i-1]['open'] - candles[i]['close']) / candles[i-1]['open']})
        # Hammer
        elif (candles[i]['close'] > candles[i]['open'] and
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['close'] - candles[i]['open']) and
              (candles[i]['close'] - candles[i]['low']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):
            patterns.append({'type': 'HAMMER', 'candle_index': i,
                             'strength': (candles[i]['close'] - candles[i]['low']) / (candles[i]['high'] - candles[i]['low'])})
        # Shooting Star
        elif (candles[i]['close'] < candles[i]['open'] and
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['open'] - candles[i]['close']) and
              (candles[i]['high'] - candles[i]['open']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):
            patterns.append({'type': 'SHOOTING_STAR', 'candle_index': i,
                             'strength': (candles[i]['high'] - candles[i]['open']) / (candles[i]['high'] - candles[i]['low'])})
    return patterns

def detect_fvg_gaps(candles, threshold=0.001):
    if len(candles) < 3:
        return []
    fvg_gaps = []
    for i in range(1, len(candles) - 1):
        prev_candle = candles[i-1]
        curr_candle = candles[i]
        next_candle = candles[i+1]
        # Bullish FVG
        if (curr_candle['high'] > prev_candle['low'] and
            next_candle['low'] > curr_candle['low'] and
            abs(curr_candle['high'] - prev_candle['low']) / prev_candle['low'] > threshold):
            fvg_gaps.append({'type': 'BULLISH_FVG',
                             'start_price': prev_candle['low'],
                             'end_price': curr_candle['high'],
                             'candle_index': i,
                             'strength': (curr_candle['high'] - prev_candle['low']) / prev_candle['low']})
        # Bearish FVG
        if (curr_candle['low'] < prev_candle['high'] and
            next_candle['high'] < curr_candle['high'] and
            abs(prev_candle['high'] - curr_candle['low']) / prev_candle['high'] > threshold):
            fvg_gaps.append({'type': 'BEARISH_FVG',
                             'start_price': prev_candle['high'],
                             'end_price': curr_candle['low'],
                             'candle_index': i,
                             'strength': (prev_candle['high'] - curr_candle['low']) / prev_candle['high']})
    return fvg_gaps

def calculate_snr_levels(prices, num_levels=5):
    if len(prices) < 20:
        return []
    local_highs = []
    local_lows = []
    for i in range(2, len(prices) - 2):
        if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
            prices[i] > prices[i+1] and prices[i] > prices[i+2]):
            local_highs.append(prices[i])
        if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
            prices[i] < prices[i+1] and prices[i] < prices[i+2]):
            local_lows.append(prices[i])
    all_levels = local_highs + local_lows
    all_levels.sort()
    clusters = []
    current_cluster = []
    cluster_threshold = (max(prices) - min(prices)) * 0.01
    for level in all_levels:
        if not current_cluster:
            current_cluster.append(level)
        elif abs(level - np.mean(current_cluster)) < cluster_threshold:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    if current_cluster:
        clusters.append(current_cluster)
    snr_levels = []
    for cluster in clusters:
        if len(cluster) >= 2:
            avg_level = np.mean(cluster)
            strength = len(cluster)
            snr_levels.append({
                'level': avg_level,
                'strength': strength,
                'type': 'RESISTANCE' if avg_level > np.mean(prices) else 'SUPPORT'
            })
    snr_levels.sort(key=lambda x: x['strength'], reverse=True)
    return snr_levels[:num_levels]

# ---------- Stochastic indicator for Triple Confirmation ----------
def calculate_stochastic(closes, highs, lows, k_period=14, d_period=3):
    """Calculate Stochastic %K and %D."""
    if len(closes) < k_period + d_period:
        return {'k': [], 'd': []}
    k_values = []
    for i in range(k_period-1, len(closes)):
        high_max = max(highs[i-k_period+1:i+1])
        low_min = min(lows[i-k_period+1:i+1])
        if high_max == low_min:
            k = 50.0
        else:
            k = 100 * (closes[i] - low_min) / (high_max - low_min)
        k_values.append(k)
    # D is SMA of K
    d_values = []
    for i in range(d_period-1, len(k_values)):
        d = sum(k_values[i-d_period+1:i+1]) / d_period
        d_values.append(d)
    return {'k': k_values, 'd': d_values}

# ---------- Main strategy analysis ----------
def analyze_market(candle_data):
    global CURRENT_STRATEGY, EMA_PERIOD, RSI_PERIOD, MIN_SIGNAL_SCORE
    global SUPPORT_RESISTANCE_STRATEGY, SUPERTREND_STRATEGY

    if not candle_data or len(candle_data) < max(EMA_PERIOD, RSI_PERIOD):
        return None, 0.0

    closes = [c['close'] for c in candle_data]

    if CURRENT_STRATEGY == "EMA_RSI":
        rsi = calculate_rsi(closes, RSI_PERIOD)
        ema_val = ema(closes, EMA_PERIOD)
        current_price = closes[-1]
        sig_dir = None
        score = 0
        if current_price > ema_val and 50 < rsi < 70:
            sig_dir = "call"
            score = 5
        elif current_price < ema_val and 30 < rsi < 50:
            sig_dir = "put"
            score = 5
        elif rsi > 80:
            sig_dir = "put"
            score = 4
        elif rsi < 20:
            sig_dir = "call"
            score = 4
        if score < MIN_SIGNAL_SCORE:
            return None, 0.0
        if len(closes) >= 3:
            recent_trend = sum(1 for i in range(-3, 0) if closes[i] > closes[i-1])
            if sig_dir == "call" and recent_trend < 2:
                score -= 1
            elif sig_dir == "put" and recent_trend > 1:
                score -= 1
        if score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        return None, 0.0

    elif CURRENT_STRATEGY == "Trend":
        if len(closes) < 10:
            return None, 0.0
        trend_score = sum(1 if closes[i] > closes[i-1] else -1 for i in range(-5, 0))
        if trend_score >= 3:
            return "call", 4
        elif trend_score <= -3:
            return "put", 4
        return None, 0.0

    elif CURRENT_STRATEGY == "Bollinger":
        if len(closes) < 20:
            return None, 0.0
        ma, upper, lower = calculate_bollinger(closes)
        if ma is None:
            return None, 0.0
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        if current_price < lower and prev_price >= lower:
            return "call", 5
        elif current_price > upper and prev_price <= upper:
            return "put", 5
        return None, 0.0

    elif CURRENT_STRATEGY == "Support_Resistance" and SUPPORT_RESISTANCE_STRATEGY:
        if len(closes) < 20:
            return None, 0.0
        support, resistance = calculate_support_resistance_levels(closes)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        if support and resistance:
            if current_price > resistance and prev_price <= resistance:
                return "call", 5
            elif current_price < support and prev_price >= support:
                return "put", 5
            elif abs(current_price - resistance) / resistance < 0.001 and current_price < prev_price:
                return "put", 4
            elif abs(current_price - support) / support < 0.001 and current_price > prev_price:
                return "call", 4
        return None, 0.0

    elif CURRENT_STRATEGY == "Trend_Reverse":
        if len(closes) < 30:
            return None, 0.0
        ma20 = ema(closes, 20) if len(closes) >= 20 else None
        ma50 = ema(closes, 50) if len(closes) >= 50 else None
        current_price = closes[-1]
        rsi = calculate_rsi(closes, 14)
        support, resistance = calculate_support_resistance_levels(closes, lookback=20)
        sig_dir = None
        score = 0
        if ma20 and ma50:
            if current_price > ma20 and ma20 > ma50:
                if rsi > 70 and resistance and abs(current_price - resistance) / resistance < 0.005:
                    sig_dir = "put"
                    score = 5
                else:
                    sig_dir = "call"
                    score = 4
            elif current_price < ma20 and ma20 < ma50:
                if rsi < 30 and support and abs(current_price - support) / support < 0.005:
                    sig_dir = "call"
                    score = 5
                else:
                    sig_dir = "put"
                    score = 4
            else:
                if resistance and support:
                    range_mid = (resistance + support) / 2
                    if current_price > range_mid and rsi < 60:
                        sig_dir = "call"
                        score = 3
                    elif current_price < range_mid and rsi > 40:
                        sig_dir = "put"
                        score = 3
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        return None, 0.0

    elif CURRENT_STRATEGY == "Price_Action":
        if len(candle_data) < 5:
            return None, 0.0
        patterns = detect_price_action_patterns(candle_data)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        sig_dir = None
        score = 0
        recent_patterns = [p for p in patterns if p['candle_index'] >= len(candle_data) - 3]
        for pattern in recent_patterns:
            if pattern['type'] in ['BULLISH_ENGULFING', 'HAMMER']:
                sig_dir = "call"
                score = 5
                break
            elif pattern['type'] in ['BEARISH_ENGULFING', 'SHOOTING_STAR']:
                sig_dir = "put"
                score = 5
                break
        if not sig_dir and len(closes) >= 3:
            if closes[-1] > closes[-2] > closes[-3]:
                sig_dir = "call"
                score = 4
            elif closes[-1] < closes[-2] < closes[-3]:
                sig_dir = "put"
                score = 4
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        return None, 0.0

    elif CURRENT_STRATEGY == "Supertrend" and SUPERTREND_STRATEGY:
        if len(candle_data) < 20:
            return None, 0.0
        supertrend_values, trend_values = calculate_supertrend(candle_data, period=10, multiplier=3)
        if supertrend_values and trend_values and supertrend_values[-1] is not None:
            current_price = closes[-1]
            current_supertrend = supertrend_values[-1]
            current_trend = trend_values[-1]
            sig_dir = None
            score = 0
            if current_trend == 1 and current_price > current_supertrend:
                sig_dir = "call"
                score = 5
            elif current_trend == -1 and current_price < current_supertrend:
                sig_dir = "put"
                score = 5
            elif current_trend == 1 and current_price > current_supertrend * 1.001:
                sig_dir = "call"
                score = 4
            elif current_trend == -1 and current_price < current_supertrend * 0.999:
                sig_dir = "put"
                score = 4
            if sig_dir and score >= MIN_SIGNAL_SCORE:
                return sig_dir, score
        return None, 0.0

    elif CURRENT_STRATEGY == "FVG_Strategy":
        if len(candle_data) < 10:
            return None, 0.0
        fvg_gaps = detect_fvg_gaps(candle_data)
        current_price = closes[-1]
        sig_dir = None
        score = 0
        recent_fvg = [g for g in fvg_gaps if g['candle_index'] >= len(candle_data) - 5]
        for fvg in recent_fvg:
            if fvg['type'] == 'BULLISH_FVG' and current_price > fvg['end_price']:
                sig_dir = "call"
                score = 5
                break
            elif fvg['type'] == 'BEARISH_FVG' and current_price < fvg['end_price']:
                sig_dir = "put"
                score = 5
                break
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        return None, 0.0

    # ==================== TRIPLE CONFIRMATION STRATEGY ====================
    elif CURRENT_STRATEGY == "TripleConfirmation":
        # Need enough candles for slow EMA and stochastic
        min_candles = max(TRIPLE_CONFIRMATION_EMA_SLOW,
                          TRIPLE_CONFIRMATION_STOCH_K + TRIPLE_CONFIRMATION_STOCH_D) + 5
        if len(candle_data) < min_candles:
            return None, 0.0

        closes = [c['close'] for c in candle_data]
        highs = [c['high'] for c in candle_data]
        lows = [c['low'] for c in candle_data]

        # 1. EMA trend
        ema20 = ema(closes, TRIPLE_CONFIRMATION_EMA_FAST)
        ema50 = ema(closes, TRIPLE_CONFIRMATION_EMA_SLOW)
        if ema20 is None or ema50 is None:
            return None, 0.0
        price = closes[-1]
        uptrend = price > ema20 > ema50
        downtrend = price < ema20 < ema50

        # 2. RSI momentum (relaxed thresholds)
        rsi = calculate_rsi(closes, TRIPLE_CONFIRMATION_RSI_PERIOD)
        if rsi is None:
            return None, 0.0
        last_rsi = rsi

        # 3. Stochastic entry
        stoch = calculate_stochastic(closes, highs, lows,
                                     TRIPLE_CONFIRMATION_STOCH_K,
                                     TRIPLE_CONFIRMATION_STOCH_D)
        if len(stoch['k']) < 2 or len(stoch['d']) < 2:
            return None, 0.0
        k_now, k_prev = stoch['k'][-1], stoch['k'][-2]
        d_now, d_prev = stoch['d'][-1], stoch['d'][-2]

        # CALL: uptrend + RSI > threshold + bullish K/D cross below oversold
        if uptrend and last_rsi > TRIPLE_CALL_RSI_MIN:
            if k_prev < d_prev and k_now > d_now and d_now < TRIPLE_STOCH_OVERSOLD:
                return "call", 5

        # PUT: downtrend + RSI < threshold + bearish K/D cross above overbought
        if downtrend and last_rsi < TRIPLE_PUT_RSI_MAX:
            if k_prev > d_prev and k_now < d_now and d_now > TRIPLE_STOCH_OVERBOUGHT:
                return "put", 5

        return None, 0.0

    return None, 0.0


# ===================================================================
#  ORIGINAL TRADE BOT CODE (modified to fetch more candles)
# ===================================================================

# -------------------- Asset list for shuffle --------------------
SHUFFLE_ASSETS = [
    "AUDCAD_otc",
    "EURUSD_otc",
    "GBPUSD_otc",
    "USDJPY_otc",
    "AUDUSD_otc",
    "EURGBP_otc",
    "EURJPY_otc",
    "GBPJPY_otc",
    "AUDCAD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
]

# -------------------- Multi-Market Scanner (unchanged) --------------------
class MultiMarketScanner:
    """Scans multiple markets simultaneously for signals"""
    def __init__(self):
        self.markets = {
            "AUDCAD_otc": [5, 10, 30, 60],
            "EURUSD_otc": [5, 10, 30, 60],
            "GBPUSD_otc": [5, 10, 30, 60],
            "USDJPY_otc": [5, 10, 30, 60],
            "AUDUSD_otc": [5, 10, 30, 60],
            "EURGBP_otc": [5, 10, 30, 60],
            "AUDCAD": [5, 10, 30, 60],
            "EURUSD": [5, 10, 30, 60],
        }
        self.price_cache = {}
        self.active_trades = []

    async def get_quick_prices(self, asset, count=30):
        try:
            # Request enough candles (count + buffer)
            candles = await client.get_candles(asset, None, 60, count + 20, use_cache=True)
            if candles:
                prices = []
                for c in candles[-count:]:
                    if isinstance(c, dict):
                        prices.append(float(c.get("close", 0)))
                    else:
                        prices.append(float(c))
                return [p for p in prices if p > 0]
        except:
            pass
        return []

    def quick_signal_check(self, prices):
        if len(prices) < 15:
            return None, 0
        current = prices[-1]
        momentum = sum(prices[i] - prices[i-1] for i in range(-5, 0))
        changes = [prices[i] - prices[i-1] for i in range(-10, 0)]
        gains = sum(c for c in changes if c > 0)
        losses = sum(abs(c) for c in changes if c < 0)
        if losses == 0:
            rsi = 100
        else:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
        if momentum > 0.0001 and rsi < 65 and rsi > 30:
            return "call", min(abs(momentum) * 5000, 90)
        elif momentum < -0.0001 and rsi > 35 and rsi < 70:
            return "put", min(abs(momentum) * 5000, 90)
        return None, 0

    async def scan_all(self):
        signals = []
        tasks = []
        for asset in self.markets:
            tasks.append(self.get_quick_prices(asset))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for asset, prices in zip(self.markets.keys(), results):
            if isinstance(prices, list) and len(prices) > 15:
                direction, strength = self.quick_signal_check(prices)
                if direction and strength >= 60:
                    for tf in self.markets[asset]:
                        signals.append({
                            "asset": asset,
                            "timeframe": tf,
                            "direction": direction,
                            "strength": strength,
                            "price": prices[-1]
                        })
                        break
        signals.sort(key=lambda x: x["strength"], reverse=True)
        return signals

# -------------------- Strategy & parameter prompts --------------------
def select_trading_strategy():
    global CURRENT_STRATEGY
    print("\n" + "="*60)
    print("📊 AVAILABLE STRATEGIES")
    print("="*60)
    for i, name in enumerate(AVAILABLE_STRATEGIES, 1):
        print(f"{i}. {name}")
    print("="*60)
    while True:
        choice = input("\n👉 Select strategy number (0 for default EMA_RSI): ").strip()
        if choice == '0':
            CURRENT_STRATEGY = "EMA_RSI"
            print(f"✅ Using default: {CURRENT_STRATEGY}")
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_STRATEGIES):
                CURRENT_STRATEGY = AVAILABLE_STRATEGIES[idx]
                print(f"✅ Strategy set to: {CURRENT_STRATEGY}")
                return
            else:
                print("❌ Invalid number.")
        except ValueError:
            print("❌ Enter a number.")

def configure_strategy_parameters():
    global EMA_PERIOD, RSI_PERIOD, MIN_SIGNAL_SCORE
    global SUPPORT_RESISTANCE_STRATEGY, SUPERTREND_STRATEGY
    print("\n" + "="*60)
    print("⚙️  STRATEGY PARAMETERS")
    print("="*60)
    try:
        ema = int(input(f"📊 EMA period (current {EMA_PERIOD}): ") or EMA_PERIOD)
        if ema > 0:
            EMA_PERIOD = ema
    except:
        pass
    try:
        rsi = int(input(f"📈 RSI period (current {RSI_PERIOD}): ") or RSI_PERIOD)
        if rsi > 0:
            RSI_PERIOD = rsi
    except:
        pass
    try:
        score = int(input(f"🎯 Minimum signal score (1-5, current {MIN_SIGNAL_SCORE}): ") or MIN_SIGNAL_SCORE)
        if 1 <= score <= 5:
            MIN_SIGNAL_SCORE = score
    except:
        pass
    # Flags for strategies that use them
    sr = input(f"🔄 Enable Support/Resistance strategy? (y/n, current {'ON' if SUPPORT_RESISTANCE_STRATEGY else 'OFF'}): ").strip().lower()
    if sr in ('y', 'yes'):
        SUPPORT_RESISTANCE_STRATEGY = True
    elif sr in ('n', 'no'):
        SUPPORT_RESISTANCE_STRATEGY = False
    st = input(f"📊 Enable Supertrend strategy? (y/n, current {'ON' if SUPERTREND_STRATEGY else 'OFF'}): ").strip().lower()
    if st in ('y', 'yes'):
        SUPERTREND_STRATEGY = True
    elif st in ('n', 'no'):
        SUPERTREND_STRATEGY = False
    print("✅ Parameters updated.")

# -------------------- Account & config --------------------
async def connect_with_retries(retries=3):
    for attempt in range(retries):
        print(f"🔗 Connecting... ({attempt+1}/{retries})")
        check_connect, message = await client.connect()
        if check_connect:
            print("✅ Connected!")
            return True
        print(f"❌ Failed: {message}")
        if attempt < retries - 1:
            await asyncio.sleep(2)
    return False

async def switch_account_and_check_balance(account_type):
    try:
        print(f"🔄 Switching to {account_type}...")
        await client.change_account(account_type)
        await asyncio.sleep(1)
        balance = await client.get_balance()
        if balance is None:
            return False, 0
        print(f"💰 {account_type} Balance: ${balance:.2f}")
        return True, balance
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, 0

def select_account():
    print("\n" + "="*50)
    print("🏦 ACCOUNT SELECTION")
    print("="*50)
    print("1. 💵 REAL Account")
    print("2. 🎮 PRACTICE (Demo) Account")
    print("="*50)
    while True:
        choice = input("\n👉 Choose (1 or 2): ").strip()
        if choice == "1":
            print("\n⚠️  REAL MONEY!")
            confirm = input("Confirm? (yes/no): ").strip().lower()
            if confirm == "yes":
                return "REAL"
            else:
                return "PRACTICE"
        elif choice == "2":
            return "PRACTICE"
        else:
            print("❌ 1 or 2 only!")

def select_trading_mode():
    print("\n" + "="*50)
    print("🎯 TRADING MODE SELECTION")
    print("="*50)
    print("1. 📊 SINGLE ASSET (One market, strategy signals)")
    print("2. 🌐 MULTI-MARKET (Scan 8+ markets, fast signals)")
    print("3. 🎲 SHUFFLE CURRENCIES (Random asset each trade, full analysis)")
    print("="*50)
    while True:
        choice = input("\n👉 Choose mode (1, 2, or 3): ").strip()
        if choice == "1":
            return "single"
        elif choice == "2":
            return "multi"
        elif choice == "3":
            return "shuffle"
        else:
            print("❌ 1, 2, or 3 only!")

async def get_user_config():
    print("\n" + "="*50)
    print("📋 TRADING CONFIGURATION")
    print("="*50)
    account_type = select_account()
    trading_mode = select_trading_mode()
    # If using single or shuffle, let user pick strategy and parameters
    if trading_mode in ["single", "shuffle"]:
        select_trading_strategy()
        configure_strategy_parameters()
    print("\n" + "="*50)
    print("⚙️  TRADING PARAMETERS")
    print("="*50)
    max_trades = int(input("🔄 Max trades (0=∞): "))
    base_amount = float(input("💰 Base amount: $"))
    stop_loss = float(input("🛑 Stop Loss (0=off): $"))
    stop_profit = float(input("🎯 Stop Profit (0=off): $"))
    if not await connect_with_retries(3):
        print("\n❌ Connection failed!")
        return None
    success, balance = await switch_account_and_check_balance(account_type)
    if not success or balance <= 0:
        print(f"\n❌ No balance!")
        return None
    if balance < base_amount:
        print(f"\n❌ Balance ${balance:.2f} < Base ${base_amount:.2f}")
        return None
    print("\n" + "="*50)
    print("✅ ALL SET!")
    print("="*50)
    mode_names = {"single": "Single Asset", "multi": "Multi-Market", "shuffle": "Shuffle Currencies"}
    print(f"Mode: {mode_names[trading_mode]}")
    print(f"Account: {account_type} | Balance: ${balance:.2f}")
    print(f"Trades: {'∞' if max_trades == 0 else max_trades} | Amount: ${base_amount}")
    if trading_mode in ["single", "shuffle"]:
        print(f"Strategy: {CURRENT_STRATEGY}")
        print(f"EMA: {EMA_PERIOD} | RSI: {RSI_PERIOD} | Min Score: {MIN_SIGNAL_SCORE}")
        print(f"S/R Strategy: {'ON' if SUPPORT_RESISTANCE_STRATEGY else 'OFF'}")
        print(f"Supertrend Strategy: {'ON' if SUPERTREND_STRATEGY else 'OFF'}")
    print("="*50 + "\n")
    return max_trades, base_amount, stop_loss, stop_profit, trading_mode

# -------------------- Money Management --------------------
def get_next_amount(base_amount, is_win, loss_streak, prev_amount):
    if is_win:
        return base_amount, 0
    else:
        loss_streak += 1
        if loss_streak >= 5:
            return base_amount, 0
        elif loss_streak == 1:
            return base_amount * 2.0, loss_streak
        else:
            if loss_streak == 2:
                factor = 2.4
            elif loss_streak == 3:
                factor = 2.5
            else:
                factor = 2.6
            return prev_amount * factor, loss_streak

def check_stop_limits(initial, current, sl, sp):
    pnl = current - initial
    if sp > 0 and pnl >= sp:
        return True, f"🎯 STOP PROFIT! +${pnl:.2f}"
    if sl > 0 and pnl <= -sl:
        return True, f"🛑 STOP LOSS! -${abs(pnl):.2f}"
    return False, ""

# -------------------- Trading functions --------------------
async def calculate_profit(asset_name, amount, balance):
    payout = client.get_payout_by_asset(asset_name)
    profit = ((payout / 100) * amount)
    balance += amount + profit
    return balance, profit

async def check_result(buy_data, direction, asset_name=None):
    if asset_name is None:
        asset_name = buy_data.get('asset')
    if asset_name is None:
        return 'Loss'
    open_price = buy_data.get('openPrice')
    if open_price is None:
        try:
            win_status, profit = await client.check_win(buy_data["id"])
            return 'Win' if win_status == "win" else 'Loss' if win_status == "loss" else 'Doji'
        except:
            return 'Loss'
    while True:
        try:
            prices = await client.get_realtime_price(asset_name)
            if not prices:
                await asyncio.sleep(0.5)
                continue
            current_price = prices[-1]['price']
            if (direction == "call" and current_price > open_price) or (direction == "put" and current_price < open_price):
                return 'Win'
            elif (direction == "call" and current_price <= open_price) or (direction == "put" and current_price >= open_price):
                return 'Loss'
            else:
                return 'Doji'
        except:
            await asyncio.sleep(1)

async def cleanup():
    try:
        await client.close()
        await asyncio.sleep(0.5)
    except:
        pass

# -------------------- Single Asset Mode (fixed: more candles) --------------------
async def single_asset_mode(config):
    max_trades, base_amount, stop_loss, stop_profit, trading_mode = config
    amount = base_amount
    asset = "AUDCAD"
    duration = 60
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    loss_streak = 0
    last_trade_amount = amount
    print(f"\n🚀 SINGLE ASSET MODE | Balance: ${balance:.2f}\n")
    asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
    if not asset_data[2]:
        print("❌ Asset closed!")
        return
    while True:
        if max_trades > 0 and trade_count >= max_trades:
            print(f"\n✅ MAX {max_trades} DONE!")
            break
        should_stop, reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
        if should_stop:
            print(f"\n{reason}")
            break
        if balance < amount:
            print(f"\n❌ Balance ${balance:.2f} < ${amount:.2f}")
            break
        print(f"{'='*80}")
        # FIX: Request many candles (200) to support all strategies
        candles = await client.get_candles(asset_name, None, 60, 200, use_cache=True)
        if not candles:
            print("   ❌ Failed to get candle data")
            await asyncio.sleep(3)
            continue
        # Convert to dict list with open, high, low, close
        candle_data = []
        for c in candles:
            if isinstance(c, dict):
                candle_data.append({
                    'open': float(c.get('open', 0)),
                    'high': float(c.get('high', 0)),
                    'low': float(c.get('low', 0)),
                    'close': float(c.get('close', 0))
                })
            else:
                # if list format, assume [open, high, low, close]
                if len(c) >= 4:
                    candle_data.append({
                        'open': float(c[0]),
                        'high': float(c[1]),
                        'low': float(c[2]),
                        'close': float(c[3])
                    })
        # Ensure enough candles for the chosen strategy
        min_needed = max(EMA_PERIOD, RSI_PERIOD, 20)  # safe minimum
        if len(candle_data) < min_needed:
            print(f"   ⚠️  Only {len(candle_data)} candles, need {min_needed}...")
            await asyncio.sleep(2)
            continue
        sig_dir, sig_score = analyze_market(candle_data)
        if sig_dir and sig_score >= MIN_SIGNAL_SCORE:
            direction = sig_dir
            print(f"   📊 Signal: {direction.upper()} ({sig_score:.0f}%) - {CURRENT_STRATEGY}")
        else:
            print(f"   ⏳ No signal ({sig_score:.0f}%)")
            await asyncio.sleep(3)
            continue
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | ${amount:.2f} | {direction.upper()} | Loss streak: {loss_streak}")
        if not await client.check_connect():
            await client.connect()
        balance_before = balance
        status, buy_info = await client.buy(amount, asset_name, direction, duration)
        if not status:
            print("   ❌ Buy Failed!")
            continue
        balance -= amount
        result = await check_result(buy_info, direction, asset_name)
        if result == "Win":
            balance, profit = await calculate_profit(asset_name, amount, balance)
            total_wins += 1
            total_profit += profit
            print(f"   ✅ WIN! +${profit:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
            amount, loss_streak = get_next_amount(base_amount, True, loss_streak, amount)
            last_trade_amount = amount
            print(f"   🔄 RESET TO BASE → ${amount:.2f}")
            continue
        if result == "Doji":
            print("   ⚪ DOJI")
            balance += amount
            continue
        total_losses += 1
        loss_amount = balance_before - balance
        total_loss_amount += loss_amount
        print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
        prev = amount
        amount, loss_streak = get_next_amount(base_amount, False, loss_streak, prev)
        last_trade_amount = amount
        if loss_streak == 0:
            print(f"   🔄 5 LOSS RESET → ${amount:.2f}")
        else:
            if loss_streak == 1:
                print(f"   📈 ×2.0 (first loss) → ${amount:.2f}")
            elif loss_streak == 2:
                print(f"   📈 ×2.4 (second loss) → ${amount:.2f}")
            elif loss_streak == 3:
                print(f"   📈 ×2.5 (third loss) → ${amount:.2f}")
            elif loss_streak == 4:
                print(f"   📈 ×2.6 (fourth loss) → ${amount:.2f}")
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount

# -------------------- Shuffle Mode (fixed: more candles) --------------------
async def shuffle_mode(config):
    max_trades, base_amount, stop_loss, stop_profit, trading_mode = config
    amount = base_amount
    duration = 60
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    loss_streak = 0
    last_trade_amount = amount
    print(f"\n🎲 SHUFFLE MODE | Balance: ${balance:.2f}")
    print(f"📋 Assets pool: {', '.join(SHUFFLE_ASSETS)}")
    print(f"🔀 Random asset each trade, full analysis\n")
    while True:
        if max_trades > 0 and trade_count >= max_trades:
            print(f"\n✅ MAX {max_trades} DONE!")
            break
        should_stop, reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
        if should_stop:
            print(f"\n{reason}")
            break
        if balance < amount:
            print(f"\n❌ Balance ${balance:.2f} < ${amount:.2f}")
            break
        asset = random.choice(SHUFFLE_ASSETS)
        print(f"\n{'='*80}")
        print(f"🎲 Shuffled Asset: {asset}")
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if not asset_data[2]:
            print(f"   ❌ {asset} is closed, skipping...")
            await asyncio.sleep(2)
            continue
        # FIX: Request many candles (200)
        candles = await client.get_candles(asset_name, None, 60, 200, use_cache=True)
        if not candles:
            print("   ❌ No candle data, skipping...")
            await asyncio.sleep(2)
            continue
        candle_data = []
        for c in candles:
            if isinstance(c, dict):
                candle_data.append({
                    'open': float(c.get('open', 0)),
                    'high': float(c.get('high', 0)),
                    'low': float(c.get('low', 0)),
                    'close': float(c.get('close', 0))
                })
            elif len(c) >= 4:
                candle_data.append({
                    'open': float(c[0]),
                    'high': float(c[1]),
                    'low': float(c[2]),
                    'close': float(c[3])
                })
        min_needed = max(EMA_PERIOD, RSI_PERIOD, 20)
        if len(candle_data) < min_needed:
            print(f"   ⚠️  Only {len(candle_data)} candles, need {min_needed}...")
            await asyncio.sleep(2)
            continue
        # Quick analysis display (using indicators)
        closes = [d['close'] for d in candle_data]
        rsi = calculate_rsi(closes, 14)
        ema9 = ema(closes, 9)
        trend = "BULLISH 📈" if closes[-1] > (ema9 if ema9 else closes[-1]) else "BEARISH 📉"
        print(f"   📊 Analysis: Price={closes[-1]:.5f} | RSI={rsi:.1f} | EMA9={ema9:.5f} | Trend={trend}")
        sig_dir, sig_score = analyze_market(candle_data)
        if sig_dir and sig_score >= MIN_SIGNAL_SCORE:
            direction = sig_dir
            print(f"   🎯 SIGNAL: {sig_dir.upper()} ({sig_score:.0f}%) - {CURRENT_STRATEGY}")
        else:
            print(f"   ⏳ No valid signal ({sig_score:.0f}% strength)")
            await asyncio.sleep(2)
            continue
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | ${amount:.2f} | {direction.upper()} | {asset} | Loss streak: {loss_streak}")
        if not await client.check_connect():
            await client.connect()
        balance_before = balance
        status, buy_info = await client.buy(amount, asset_name, direction, duration)
        if not status:
            print("   ❌ Buy Failed!")
            continue
        balance -= amount
        result = await check_result(buy_info, direction, asset_name)
        if result == "Win":
            balance, profit = await calculate_profit(asset_name, amount, balance)
            total_wins += 1
            total_profit += profit
            print(f"   ✅ WIN! +${profit:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
            amount, loss_streak = get_next_amount(base_amount, True, loss_streak, amount)
            last_trade_amount = amount
            print(f"   🔄 RESET TO BASE → ${amount:.2f}")
        elif result == "Doji":
            print("   ⚪ DOJI")
            balance += amount
        else:
            total_losses += 1
            loss_amount = balance_before - balance
            total_loss_amount += loss_amount
            print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
            prev = amount
            amount, loss_streak = get_next_amount(base_amount, False, loss_streak, prev)
            last_trade_amount = amount
            if loss_streak == 0:
                print(f"   🔄 5 LOSS RESET → ${amount:.2f}")
            else:
                if loss_streak == 1:
                    print(f"   📈 ×2.0 (first loss) → ${amount:.2f}")
                elif loss_streak == 2:
                    print(f"   📈 ×2.4 (second loss) → ${amount:.2f}")
                elif loss_streak == 3:
                    print(f"   📈 ×2.5 (third loss) → ${amount:.2f}")
                elif loss_streak == 4:
                    print(f"   📈 ×2.6 (fourth loss) → ${amount:.2f}")
        await asyncio.sleep(1)
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount

# -------------------- Multi-Market Mode (unchanged) --------------------
async def multi_market_mode(config):
    max_trades, base_amount, stop_loss, stop_profit, trading_mode = config
    scanner = MultiMarketScanner()
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    active_tasks = set()
    loss_streak = 0
    last_trade_amount = base_amount
    current_amount = base_amount
    print(f"\n🌐 MULTI-MARKET MODE | Balance: ${balance:.2f}")
    print(f"📊 Scanning {len(scanner.markets)} markets...\n")
    try:
        while True:
            if max_trades > 0 and trade_count >= max_trades:
                print(f"\n✅ MAX {max_trades} DONE!")
                break
            should_stop, reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
            if should_stop:
                print(f"\n{reason}")
                break
            signals = await scanner.scan_all()
            if signals:
                print(f"\n🔍 Found {len(signals)} signals:")
                for i, sig in enumerate(signals[:5], 1):
                    emoji = "🟢" if sig["direction"] == "call" else "🔴"
                    print(f"  {i}. {sig['asset']:<15} {sig['timeframe']}s {emoji} {sig['direction']:<4} {sig['strength']:.0f}%")
                for signal in signals[:3]:
                    active_count = len([t for t in active_tasks if not t.done()])
                    if active_count >= 5:
                        break
                    if balance < current_amount:
                        print("❌ Low balance!")
                        break
                    task = asyncio.create_task(
                        execute_multi_trade(signal, current_amount, scanner)
                    )
                    active_tasks.add(task)
                    trade_count += 1
            else:
                print("⏳ No signals...")
            done = {t for t in active_tasks if t.done()}
            for task in done:
                try:
                    result = await task
                    if result:
                        if result["win"]:
                            total_wins += 1
                            profit = result.get("profit", 0)
                            total_profit += profit
                            balance += profit
                            current_amount, loss_streak = get_next_amount(base_amount, True, loss_streak, current_amount)
                            last_trade_amount = current_amount
                            print(f"   ✅ WIN → Reset to base: ${current_amount:.2f}")
                        else:
                            total_losses += 1
                            loss = result.get("loss", current_amount)
                            total_loss_amount += loss
                            prev = current_amount
                            current_amount, loss_streak = get_next_amount(base_amount, False, loss_streak, prev)
                            last_trade_amount = current_amount
                            if loss_streak == 0:
                                print(f"   ❌ 5 LOSS RESET → ${current_amount:.2f}")
                            else:
                                factors = {1: 2.0, 2: 2.4, 3: 2.5, 4: 2.6}
                                factor = factors.get(loss_streak, 1.0)
                                print(f"   ❌ LOSS ×{factor} → ${current_amount:.2f}")
                except Exception as e:
                    print(f"   ⚠️ Trade error: {e}")
                active_tasks.remove(task)
            active = len([t for t in active_tasks if not t.done()])
            print(f"📊 Running: {active} | {total_wins}W/{total_losses}L | Bal: ${balance:.2f} | Next amount: ${current_amount:.2f}")
            await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
        for task in active_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*active_tasks, return_exceptions=True)
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount

async def execute_multi_trade(signal, amount, scanner):
    asset = signal["asset"]
    direction = signal["direction"]
    duration = signal["timeframe"]
    print(f"\n🔴 {asset} | {direction.upper()} | {duration}s | ${amount:.2f}")
    try:
        status, buy_info = await client.buy(amount, asset, direction, duration)
        if not status:
            return None
        await asyncio.sleep(duration + 2)
        if buy_info and "id" in buy_info:
            win_status, profit = await client.check_win(buy_info["id"])
            if win_status == "win":
                print(f"   ✅ WIN! +${profit:.2f}")
                return {"win": True, "profit": profit}
            else:
                print(f"   ❌ LOSS! -${amount:.2f}")
                return {"win": False, "loss": amount}
        return None
    except Exception as e:
        print(f"   ❌ Trade exception: {e}")
        return None

# -------------------- Main --------------------
async def trade_and_monitor():
    config = await get_user_config()
    if config is None:
        await cleanup()
        return
    _, _, _, _, trading_mode = config
    try:
        if trading_mode == "multi":
            initial, final, trades, wins, losses, profit, loss_amt = await multi_market_mode(config)
        elif trading_mode == "shuffle":
            initial, final, trades, wins, losses, profit, loss_amt = await shuffle_mode(config)
        else:
            initial, final, trades, wins, losses, profit, loss_amt = await single_asset_mode(config)
        final_pnl = final - initial
        print(f"\n{'='*60}")
        print(f"🏁 SESSION SUMMARY")
        print(f"{'='*60}")
        mode_names = {"single": "Single Asset", "multi": "Multi-Market", "shuffle": "Shuffle Currencies"}
        print(f"Mode: {mode_names[trading_mode]}")
        print(f"Trades: {trades} | ✅ {wins}W | ❌ {losses}L")
        if trades > 0:
            print(f"Win Rate: {wins/trades*100:.1f}%")
        print(f"💰 Initial: ${initial:.2f} → Final: ${final:.2f}")
        print(f"💚 Profit: +${profit:.2f} | 💔 Loss: -${loss_amt:.2f}")
        print(f"📊 Net: ${final_pnl:+.2f}")
        print(f"{'='*60}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await cleanup()
        print("👋 Done!\n")

async def main():
    try:
        await trade_and_monitor()
    finally:
        await cleanup()
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Closed")
