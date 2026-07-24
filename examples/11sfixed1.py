import asyncio
import os
import sys
import time
import argparse
import contextlib
import traceback
import smtplib
import ssl
import json
import urllib.request
import urllib.error
import getpass
from email.message import EmailMessage
from datetime import datetime, timezone
from collections import defaultdict, deque

# --- Persistent crash log -----------------------------------------------
_LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_error.log")

def _log_to_file(message):
    try:
        with open(_LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            f.flush()
    except Exception:
        pass

def _fatal_startup_error(context, exc):
    err_text = traceback.format_exc()
    _log_to_file(f"FATAL STARTUP ERROR ({context}):\n{err_text}")
    print("\n" + "=" * 70)
    print(f"[!] Failed to start: {context}")
    print(err_text)
    print("=" * 70)
    print(f"[*] Full details were also saved to: {_LOG_FILE_PATH}")
    sys.stdout.flush()
    try:
        input("\nPress Enter to close this window...")
    except (KeyboardInterrupt, EOFError):
        pass
    sys.exit(1)
# --------------------------------------------------------------------------

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pyquotex.stable_api import Quotex
except Exception as _e:
    _fatal_startup_error("could not import pyquotex (check it's installed / in the same folder)", _e)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    from rich import box
    from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt
except ImportError as _e:
    _fatal_startup_error("'rich' library is required — run: pip install rich", _e)

console = Console()

def _credentials_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "quotex_credentials.json")

def _load_saved_credentials():
    path = _credentials_file_path()
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        email, password = data.get("email"), data.get("password")
        if email and password:
            return email, password
    except Exception:
        pass
    return None, None

def _save_credentials(email, password):
    path = _credentials_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"email": email, "password": password}, f)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return True
    except Exception:
        return False

def prompt_login_credentials():
    saved_email, saved_password = _load_saved_credentials()
    if saved_email and saved_password:
        console.print(Panel(
            f"Using saved credentials for [bold]{saved_email}[/] from "
            f"quotex_credentials.json (delete that file to be asked again).",
            title="LOCK: QUOTEX LOGIN", border_style="cyan"
        ))
        return saved_email, saved_password

    console.print(Panel(
        "No saved credentials found. After you enter them once, they will be "
        "saved in PLAIN TEXT to quotex_credentials.json next to this script, "
        "so you won't need to type them again. Delete that file any time to "
        "stop auto-login / be prompted again.",
        title="LOCK: QUOTEX LOGIN", border_style="cyan"
    ))
    email = Prompt.ask("Email")
    password = getpass.getpass("Password (hidden): ")
    if _save_credentials(email, password):
        console.print("[dim]Saved to quotex_credentials.json for next time.[/]")
    else:
        console.print("[yellow]Could not save credentials to disk — you'll be asked again next run.[/]")
    return email, password


@contextlib.contextmanager
def mute_stdout():
    import builtins
    original_print = builtins.print
    builtins.print = lambda *args, **kwargs: None
    try:
        yield
    finally:
        builtins.print = original_print

def format_price(price):
    if not isinstance(price, (int, float)):
        return str(price)
    if price == 0:
        return "0.00000"
    if price > 10000:
        return f"{price:,.1f}"
    if price > 100:
        return f"{price:,.2f}"
    if price > 1:
        return f"{price:.5f}"
    return f"{price:.6f}"

def format_asset_name(asset):
    name = asset.replace("_otc", "").replace("_OTC", "")
    if len(name) == 6 and name.isalpha():
        return f"{name[:3]}/{name[3:]}"
    return name

def resample_ticks_to_closes(tick_history, interval_seconds, now_ts=None):
    """Resamples a raw (timestamp, price) tick stream into a list of closed
    bucket closes for a given interval (e.g. 30s), oldest -> newest. The
    still-forming bucket is dropped. Used only by ProOTCEngine for
    sub-minute MTF confirmation."""
    if not tick_history:
        return []
    now_ts = now_ts if now_ts is not None else time.time()
    current_bucket = (int(now_ts) // interval_seconds) * interval_seconds
    buckets = {}
    order = []
    for ts, price in tick_history:
        b = (int(ts) // interval_seconds) * interval_seconds
        if b not in buckets:
            order.append(b)
        buckets[b] = price
    return [buckets[b] for b in sorted(order) if b < current_bucket]


class Indicators:
    """
    Stateless technical-indicator calculators. All *_aligned functions return
    a list the same length as the input, with None for indices that don't
    yet have enough history.
    """

    @staticmethod
    def ema_aligned(values, period):
        n = len(values)
        result = [None] * n
        if n < period:
            return result
        k = 2 / (period + 1)
        seed = sum(values[:period]) / period
        result[period - 1] = seed
        prev = seed
        for i in range(period, n):
            prev = values[i] * k + prev * (1 - k)
            result[i] = prev
        return result

    @staticmethod
    def rsi_aligned(values, period=14):
        n = len(values)
        result = [None] * n
        if n < period + 1:
            return result
        gains = [max(values[i] - values[i - 1], 0) for i in range(1, n)]
        losses = [max(values[i - 1] - values[i], 0) for i in range(1, n)]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        result[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rsi_val = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
            result[i + 1] = rsi_val
        return result

    @staticmethod
    def macd(closes, fast=12, slow=26, signal=9):
        ema_fast = Indicators.ema_aligned(closes, fast)
        ema_slow = Indicators.ema_aligned(closes, slow)
        macd_series = [f - s for f, s in zip(ema_fast, ema_slow) if f is not None and s is not None]
        if len(macd_series) < signal:
            return None, None, None
        signal_series = Indicators.ema_aligned(macd_series, signal)
        macd_val = macd_series[-1]
        signal_val = signal_series[-1]
        if signal_val is None:
            return macd_val, None, None
        return macd_val, signal_val, macd_val - signal_val

    @staticmethod
    def atr(highs, lows, closes, period=14):
        n = len(closes)
        if n < period + 1:
            return None, None
        trs = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        atr_val = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr_val = (atr_val * (period - 1) + tr) / period
        atr_pct = (atr_val / closes[-1] * 100) if closes[-1] else None
        return atr_val, atr_pct

    @staticmethod
    def adx(highs, lows, closes, period=14):
        n = len(closes)
        if n < period * 2:
            return None, None, None
        plus_dm, minus_dm, trs = [], [], []
        for i in range(1, n):
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]
            plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0)
            minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0)
            trs.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            ))

        def wilder_smooth(vals, period):
            sm = [sum(vals[:period])]
            for v in vals[period:]:
                sm.append(sm[-1] - (sm[-1] / period) + v)
            return sm

        tr_sm = wilder_smooth(trs, period)
        plus_sm = wilder_smooth(plus_dm, period)
        minus_sm = wilder_smooth(minus_dm, period)

        dx_series = []
        for tr_v, p_v, m_v in zip(tr_sm, plus_sm, minus_sm):
            if tr_v == 0:
                continue
            plus_di = 100 * p_v / tr_v
            minus_di = 100 * m_v / tr_v
            denom = plus_di + minus_di
            dx = 100 * abs(plus_di - minus_di) / denom if denom else 0
            dx_series.append((dx, plus_di, minus_di))

        if len(dx_series) < period:
            return None, None, None
        adx_val = sum(d[0] for d in dx_series[:period]) / period
        for d in dx_series[period:]:
            adx_val = (adx_val * (period - 1) + d[0]) / period
        _, plus_di, minus_di = dx_series[-1]
        return adx_val, plus_di, minus_di

    @staticmethod
    def bollinger(closes, period=20, num_std=2):
        if len(closes) < period:
            return None, None, None, None
        window = closes[-period:]
        mid = sum(window) / period
        variance = sum((c - mid) ** 2 for c in window) / period
        std = variance ** 0.5
        upper, lower = mid + num_std * std, mid - num_std * std
        percent_b = (closes[-1] - lower) / (upper - lower) if upper != lower else 0.5
        return upper, mid, lower, percent_b

    @staticmethod
    def stoch_rsi(closes, rsi_period=14, stoch_period=14):
        rsi_series = [r for r in Indicators.rsi_aligned(closes, rsi_period) if r is not None]
        if len(rsi_series) < stoch_period:
            return None
        window = rsi_series[-stoch_period:]
        lo, hi = min(window), max(window)
        if hi == lo:
            return 50.0
        return (rsi_series[-1] - lo) / (hi - lo) * 100

    @staticmethod
    def vwap(highs, lows, closes, volumes, window=20):
        n = len(closes)
        if n < 1:
            return None
        start = max(0, n - window)
        num, den = 0.0, 0.0
        for i in range(start, n):
            typical = (highs[i] + lows[i] + closes[i]) / 3
            vol = max(volumes[i], 1)
            num += typical * vol
            den += vol
        return num / den if den else None

    @staticmethod
    def _wma_aligned(values, period):
        n = len(values)
        result = [None] * n
        if n < period:
            return result
        weights = list(range(1, period + 1))
        weight_sum = sum(weights)
        for i in range(period - 1, n):
            window = values[i - period + 1:i + 1]
            result[i] = sum(w * v for w, v in zip(weights, window)) / weight_sum
        return result

    @staticmethod
    def hull_ma(closes, period=9):
        n = len(closes)
        half = max(1, period // 2)
        sqrt_p = max(1, round(period ** 0.5))
        wma_half = Indicators._wma_aligned(closes, half)
        wma_full = Indicators._wma_aligned(closes, period)
        raw = []
        for i in range(n):
            if wma_half[i] is not None and wma_full[i] is not None:
                raw.append(2 * wma_half[i] - wma_full[i])
        if len(raw) < sqrt_p:
            return None
        weights = list(range(1, sqrt_p + 1))
        weight_sum = sum(weights)
        window = raw[-sqrt_p:]
        return sum(w * v for w, v in zip(weights, window)) / weight_sum

    @staticmethod
    def supertrend(highs, lows, closes, period=10, multiplier=3.0):
        n = len(closes)
        if n < period + 1:
            return None, None
        atr_val, _ = Indicators.atr(highs, lows, closes, period)
        if atr_val is None:
            return None, None
        hl2 = (highs[-1] + lows[-1]) / 2
        upper_band = hl2 + multiplier * atr_val
        lower_band = hl2 - multiplier * atr_val
        direction = 1 if closes[-1] > upper_band else (-1 if closes[-1] < lower_band else 0)
        st_value = lower_band if direction >= 0 else upper_band
        return direction, st_value

    @staticmethod
    def keltner(closes, highs, lows, period=20, multiplier=2.0):
        if len(closes) < period:
            return None, None, None
        ema_vals = Indicators.ema_aligned(closes, period)
        basis = ema_vals[-1]
        atr_val, _ = Indicators.atr(highs, lows, closes, period)
        if basis is None or atr_val is None:
            return None, None, None
        upper = basis + multiplier * atr_val
        lower = basis - multiplier * atr_val
        return upper, basis, lower

    @staticmethod
    def donchian(highs, lows, period=20):
        if len(highs) < period:
            return None, None, None
        window_h = highs[-period:]
        window_l = lows[-period:]
        upper = max(window_h)
        lower = min(window_l)
        mid = (upper + lower) / 2
        return upper, mid, lower

    @staticmethod
    def stddev_pct(closes, period=20):
        if len(closes) < period:
            return None
        window = closes[-period:]
        mean = sum(window) / period
        var = sum((c - mean) ** 2 for c in window) / period
        std = var ** 0.5
        return (std / mean * 100) if mean else None

    @staticmethod
    def historical_volatility(closes, period=20):
        if len(closes) < period + 1:
            return None
        window = closes[-period - 1:]
        rets = [(window[i] - window[i - 1]) / window[i - 1] * 100 for i in range(1, len(window)) if window[i - 1]]
        if not rets:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        return var ** 0.5

    @staticmethod
    def cci(highs, lows, closes, period=20):
        if len(closes) < period:
            return None
        tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
        window = tp[-period:]
        sma = sum(window) / period
        mean_dev = sum(abs(t - sma) for t in window) / period
        if mean_dev == 0:
            return 0.0
        return (tp[-1] - sma) / (0.015 * mean_dev)

    @staticmethod
    def roc(closes, period=10):
        if len(closes) <= period:
            return None
        prev = closes[-1 - period]
        if prev == 0:
            return None
        return (closes[-1] - prev) / prev * 100

    @staticmethod
    def momentum(closes, period=10):
        if len(closes) <= period:
            return None
        return closes[-1] - closes[-1 - period]

    @staticmethod
    def williams_r(highs, lows, closes, period=14):
        if len(closes) < period:
            return None
        window_h = max(highs[-period:])
        window_l = min(lows[-period:])
        if window_h == window_l:
            return -50.0
        return (window_h - closes[-1]) / (window_h - window_l) * -100

    @staticmethod
    def mfi(highs, lows, closes, volumes, period=14):
        n = len(closes)
        if n < period + 1:
            return None
        tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
        pos_flow, neg_flow = 0.0, 0.0
        for i in range(max(1, n - period), n):
            raw_flow = tp[i] * max(volumes[i], 1)
            if tp[i] > tp[i - 1]:
                pos_flow += raw_flow
            elif tp[i] < tp[i - 1]:
                neg_flow += raw_flow
        if neg_flow == 0:
            return 100.0
        money_ratio = pos_flow / neg_flow
        return 100 - (100 / (1 + money_ratio))

    @staticmethod
    def linreg_slope(closes, period=14):
        if len(closes) < period:
            return None
        window = closes[-period:]
        n = len(window)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(window) / n
        denom = sum((x - mean_x) ** 2 for x in xs)
        if denom == 0:
            return None
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, window)) / denom
        return (slope / mean_y * 100) if mean_y else None

    @staticmethod
    def _adaptive_period(base_period, atr_pct, ref_atr_pct=0.05, min_period=5, max_period=50):
        if not atr_pct or atr_pct <= 0:
            return base_period
        ratio = ref_atr_pct / atr_pct
        period = round(base_period * ratio)
        return max(min_period, min(max_period, period))

    @staticmethod
    def adaptive_rsi(closes, atr_pct, base_period=14):
        period = Indicators._adaptive_period(base_period, atr_pct)
        series = Indicators.rsi_aligned(closes, period)
        return series[-1] if series else None

    @staticmethod
    def adaptive_macd(closes, atr_pct, base_fast=12, base_slow=26, base_signal=9):
        fast = Indicators._adaptive_period(base_fast, atr_pct, min_period=3, max_period=30)
        slow = Indicators._adaptive_period(base_slow, atr_pct, min_period=6, max_period=60)
        if slow <= fast:
            slow = fast + 3
        signal = Indicators._adaptive_period(base_signal, atr_pct, min_period=2, max_period=20)
        return Indicators.macd(closes, fast, slow, signal)


class CandlePatterns:
    """Detects classic Japanese candlestick patterns from the last few
    CLOSED candles."""

    @staticmethod
    def _body(c):
        return abs(c["close"] - c["open"])

    @staticmethod
    def _range(c):
        return max(c["high"] - c["low"], 1e-12)

    @staticmethod
    def detect(candles):
        found = []
        if len(candles) < 1:
            return found
        c0 = candles[-1]
        body0, range0 = CandlePatterns._body(c0), CandlePatterns._range(c0)
        upper_wick = c0["high"] - max(c0["open"], c0["close"])
        lower_wick = min(c0["open"], c0["close"]) - c0["low"]

        if body0 <= 0.1 * range0:
            found.append(("Doji", 0))

        if body0 <= 0.35 * range0 and lower_wick >= 2 * body0 and upper_wick <= 0.3 * body0 + 1e-12:
            found.append(("Hammer", +1))

        if body0 <= 0.35 * range0 and upper_wick >= 2 * body0 and lower_wick <= 0.3 * body0 + 1e-12:
            found.append(("Shooting Star", -1))

        if body0 <= 0.25 * range0:
            if lower_wick >= 0.6 * range0:
                found.append(("Pin Bar (bullish)", +1))
            elif upper_wick >= 0.6 * range0:
                found.append(("Pin Bar (bearish)", -1))

        if len(candles) >= 2:
            c1 = candles[-2]
            bull0, bear0 = c0["close"] > c0["open"], c0["close"] < c0["open"]
            bull1, bear1 = c1["close"] > c1["open"], c1["close"] < c1["open"]
            if bull0 and bear1 and c0["close"] >= c1["open"] and c0["open"] <= c1["close"]:
                found.append(("Bullish Engulfing", +1))
            if bear0 and bull1 and c0["open"] >= c1["close"] and c0["close"] <= c1["open"]:
                found.append(("Bearish Engulfing", -1))

        if body0 >= 0.92 * range0:
            if c0["close"] > c0["open"]:
                found.append(("Bullish Marubozu", +1))
            elif c0["close"] < c0["open"]:
                found.append(("Bearish Marubozu", -1))

        if len(candles) >= 2:
            c1 = candles[-2]
            if c0["high"] <= c1["high"] and c0["low"] >= c1["low"]:
                found.append(("Inside Bar", 0))
            if c0["high"] >= c1["high"] and c0["low"] <= c1["low"]:
                found.append(("Outside Bar", +1 if c0["close"] > c0["open"] else -1))

        if len(candles) >= 3:
            c1, c2 = candles[-2], candles[-3]
            body1 = CandlePatterns._body(c1)
            range1 = CandlePatterns._range(c1)
            small_middle = body1 <= 0.4 * range1
            if c2["close"] < c2["open"] and small_middle and c0["close"] > c0["open"] \
                    and c0["close"] > (c2["open"] + c2["close"]) / 2:
                found.append(("Morning Star", +1))
            if c2["close"] > c2["open"] and small_middle and c0["close"] < c0["open"] \
                    and c0["close"] < (c2["open"] + c2["close"]) / 2:
                found.append(("Evening Star", -1))

        if len(candles) >= 3:
            c1, c2 = candles[-2], candles[-3]
            all_bull = all(c["close"] > c["open"] for c in (c2, c1, c0))
            all_bear = all(c["close"] < c["open"] for c in (c2, c1, c0))
            rising_closes = c1["close"] > c2["close"] and c0["close"] > c1["close"]
            falling_closes = c1["close"] < c2["close"] and c0["close"] < c1["close"]
            if all_bull and rising_closes:
                found.append(("Three White Soldiers", +1))
            if all_bear and falling_closes:
                found.append(("Three Black Crows", -1))

        if len(candles) >= 2:
            c1 = candles[-2]
            body1 = CandlePatterns._body(c1)
            prior_bull = c1["close"] > c1["open"]
            prior_bear = c1["close"] < c1["open"]
            contained = (
                max(c0["open"], c0["close"]) <= max(c1["open"], c1["close"])
                and min(c0["open"], c0["close"]) >= min(c1["open"], c1["close"])
            )
            if contained and body1 >= 2 * body0:
                if prior_bear:
                    found.append(("Bullish Harami", +1))
                elif prior_bull:
                    found.append(("Bearish Harami", -1))

        if len(candles) >= 2:
            c1 = candles[-2]
            tolerance = 0.05 / 100
            high_match = abs(c0["high"] - c1["high"]) / max(c1["high"], 1e-9) <= tolerance
            low_match = abs(c0["low"] - c1["low"]) / max(c1["low"], 1e-9) <= tolerance
            prior_bull = c1["close"] > c1["open"]
            prior_bear = c1["close"] < c1["open"]
            cur_bull = c0["close"] > c0["open"]
            cur_bear = c0["close"] < c0["open"]
            if high_match and prior_bull and cur_bear:
                found.append(("Tweezer Top", -1))
            if low_match and prior_bear and cur_bull:
                found.append(("Tweezer Bottom", +1))

        return found


class TrendCandleEngine:
    """Trend Candles engine — power + fast EMA/swing trend + Fibonacci
    retracement/extension gates, recalibrated for a 4-candle window."""
    MIN_CANDLES = 4
    POWER_LOOKBACK = 4
    POWER_THRESHOLD = 60.0
    SWING_LOOKBACK = 1
    QUALITY_GOOD = 60
    QUALITY_EXCELLENT = 80
    TREND_EMA_FAST = 2
    TREND_EMA_SLOW = 3

    FIB_LOOKBACK_CANDLES = 20
    FIB_BUFFER_PCT = 0.05
    FIB_RETRACEMENT_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
    FIB_EXTENSION_LEVELS = [1.272, 1.618]

    STRICT_POWER_MARGIN = 10.0
    STRICT_FIB_MULTIPLIER = 2.0

    @staticmethod
    def _buy_sell_power(candles):
        buy_weight, sell_weight = 0.0, 0.0
        for c in candles:
            rng = c["high"] - c["low"]
            if rng <= 0:
                continue
            body = abs(c["close"] - c["open"])
            weight = (body / rng) * max(c.get("ticks", 1), 1)
            if c["close"] > c["open"]:
                buy_weight += weight
            elif c["close"] < c["open"]:
                sell_weight += weight
        total = buy_weight + sell_weight
        if total <= 0:
            return 50.0, 50.0
        buy_power = buy_weight / total * 100
        return buy_power, 100 - buy_power

    @staticmethod
    def _swings(candles, lookback):
        highs, lows = [], []
        n = len(candles)
        for i in range(lookback, n - lookback):
            window = candles[i - lookback:i + lookback + 1]
            hi, lo = candles[i]["high"], candles[i]["low"]
            if hi == max(c["high"] for c in window):
                highs.append((i, hi))
            if lo == min(c["low"] for c in window):
                lows.append((i, lo))
        return highs, lows

    @staticmethod
    def _trend(closes, highs_swings, lows_swings):
        fast_p, slow_p = TrendCandleEngine.TREND_EMA_FAST, TrendCandleEngine.TREND_EMA_SLOW
        ema_fast = Indicators.ema_aligned(closes, fast_p)[-1] if len(closes) >= fast_p else None
        ema_slow = Indicators.ema_aligned(closes, slow_p)[-1] if len(closes) >= slow_p else None
        ema_dir = None
        if ema_fast is not None and ema_slow is not None:
            ema_dir = 1 if ema_fast > ema_slow else (-1 if ema_fast < ema_slow else 0)

        structure_dir = None
        if len(highs_swings) >= 2 and len(lows_swings) >= 2:
            last_high, prev_high = highs_swings[-1][1], highs_swings[-2][1]
            last_low, prev_low = lows_swings[-1][1], lows_swings[-2][1]
            higher_high, higher_low = last_high > prev_high, last_low > prev_low
            lower_high, lower_low = last_high < prev_high, last_low < prev_low
            if higher_high and higher_low:
                structure_dir = 1
            elif lower_high and lower_low:
                structure_dir = -1
            else:
                structure_dir = 0

        if ema_dir is not None and structure_dir is not None:
            if ema_dir == structure_dir and ema_dir != 0:
                return ema_dir, "strong"
            if ema_dir != structure_dir:
                return 0, "conflict"
            return 0, "conflict"
        if ema_dir is not None:
            return ema_dir, "ema-only"
        if structure_dir is not None:
            return structure_dir, "structure-only"
        return 0, "none"

    @staticmethod
    def _fibonacci_levels(candles, lookback):
        window = candles[-lookback:] if len(candles) >= lookback else candles
        if len(window) < 2:
            return None, None, None, None

        high_idx = max(range(len(window)), key=lambda i: window[i]["high"])
        low_idx = min(range(len(window)), key=lambda i: window[i]["low"])
        swing_high = window[high_idx]["high"]
        swing_low = window[low_idx]["low"]
        if swing_high <= swing_low:
            return None, None, None, None

        up_leg = low_idx < high_idx
        rng = swing_high - swing_low

        levels = {}
        for pct in TrendCandleEngine.FIB_RETRACEMENT_LEVELS:
            pct_label = f"{pct * 100:.1f}%"
            if up_leg:
                levels[pct_label] = swing_high - rng * pct
            else:
                levels[pct_label] = swing_low + rng * pct

        for pct in TrendCandleEngine.FIB_EXTENSION_LEVELS:
            pct_label = f"{pct * 100:.1f}%"
            if up_leg:
                levels[pct_label] = swing_low + rng * pct
            else:
                levels[pct_label] = swing_high - rng * pct

        return levels, swing_high, swing_low, up_leg

    @staticmethod
    def compute(tracker, min_confidence=0, power_threshold=None, fib_buffer_pct=None, require_strong_trend=False,
                strict_confluence=False, strict_power_margin=None, strict_fib_multiplier=None):
        power_threshold = TrendCandleEngine.POWER_THRESHOLD if power_threshold is None else power_threshold
        fib_buffer_pct = TrendCandleEngine.FIB_BUFFER_PCT if fib_buffer_pct is None else fib_buffer_pct
        strict_power_margin = (
            TrendCandleEngine.STRICT_POWER_MARGIN if strict_power_margin is None else strict_power_margin
        )
        strict_fib_multiplier = (
            TrendCandleEngine.STRICT_FIB_MULTIPLIER if strict_fib_multiplier is None else strict_fib_multiplier
        )
        if strict_confluence:
            require_strong_trend = True

        closed_buckets = sorted(b for b in tracker.candles if tracker.candles[b]["is_closed"])
        if len(closed_buckets) < TrendCandleEngine.MIN_CANDLES:
            return {
                "direction": "WAIT", "label": "Collecting data", "confidence": 0, "quality": "WAIT",
                "reasons": [f"Need {TrendCandleEngine.MIN_CANDLES - len(closed_buckets)} more closed candles"],
                "seconds_to_entry": TrendCandleEngine._seconds_to_entry(tracker),
                "buy_power": None, "sell_power": None,
                "trend": 0, "trend_quality": "none",
                "fib_levels": None, "nearest_fib_level": None,
                "strict_confluence": strict_confluence,
            }

        candles = [tracker.candles[b] for b in closed_buckets]
        closes = [c["close"] for c in candles]

        reasons = []
        vetoes = []

        swing_highs, swing_lows = TrendCandleEngine._swings(candles, TrendCandleEngine.SWING_LOOKBACK)

        fib_levels, swing_high, swing_low, up_leg = TrendCandleEngine._fibonacci_levels(
            candles, TrendCandleEngine.FIB_LOOKBACK_CANDLES
        )

        power_window = candles[-TrendCandleEngine.POWER_LOOKBACK:]
        buy_power, sell_power = TrendCandleEngine._buy_sell_power(power_window)
        power_dir = 0
        if buy_power >= power_threshold:
            power_dir = 1
        elif sell_power >= power_threshold:
            power_dir = -1
        else:
            vetoes.append(
                f"Power not decisive (need >={power_threshold:.0f}%, "
                f"buy {buy_power:.1f}% / sell {sell_power:.1f}%)"
            )
        if power_dir != 0:
            reasons.append(f"Power {'BUY' if power_dir > 0 else 'SELL'} {max(buy_power, sell_power):.1f}%")
            if strict_confluence:
                margin = max(buy_power, sell_power) - power_threshold
                if margin < strict_power_margin:
                    vetoes.append(
                        f"Strict mode: power margin {margin:.1f}pp above threshold "
                        f"< required {strict_power_margin:.1f}pp"
                    )

        trend_dir, trend_quality = TrendCandleEngine._trend(closes, swing_highs, swing_lows)
        if trend_dir == 0:
            vetoes.append(f"No clear trend ({trend_quality})")
        elif power_dir != 0 and trend_dir != power_dir:
            vetoes.append("Power and trend DISAGREE")
        elif require_strong_trend and trend_quality != "strong":
            vetoes.append(f"Trend quality '{trend_quality}' is not 'strong' (required)")
        if trend_dir != 0:
            reasons.append(f"Trend {'UP' if trend_dir > 0 else 'DOWN'} ({trend_quality})")

        effective_fib_buffer = fib_buffer_pct * strict_fib_multiplier if strict_confluence else fib_buffer_pct
        nearest_fib_level = None
        last_close = closes[-1]
        if fib_levels is None:
            vetoes.append("Insufficient range to compute Fibonacci levels")
        else:
            for label, price in fib_levels.items():
                distance_pct = abs(price - last_close) / last_close * 100 if last_close else 0
                if distance_pct > effective_fib_buffer:
                    continue
                blocks_buy = power_dir > 0 and price >= last_close
                blocks_sell = power_dir < 0 and price <= last_close
                if blocks_buy or blocks_sell:
                    nearest_fib_level = (label, price)
                    vetoes.append(
                        f"Too close to Fib {label} level ({format_price(price)}, "
                        f"{distance_pct:.3f}% away, buffer {effective_fib_buffer:.3f}%)"
                    )
                    break
            if nearest_fib_level is None:
                reasons.append(
                    f"Clear of Fib levels (swing {format_price(swing_low)}-{format_price(swing_high)}, "
                    f"{'up-leg' if up_leg else 'down-leg'})"
                )

        strongest_power = max(buy_power, sell_power)
        confidence = round(min(max(strongest_power - 50, 0) / (power_threshold - 50) * 100, 100)) if power_threshold > 50 else 0
        if trend_quality == "strong":
            confidence = min(confidence + 10, 100)

        quality_floor = TrendCandleEngine.QUALITY_EXCELLENT if strict_confluence else TrendCandleEngine.QUALITY_GOOD
        if not vetoes and confidence < quality_floor:
            vetoes.append(
                f"Confidence {confidence} < {quality_floor} quality floor"
                + (" (strict mode)" if strict_confluence else "")
            )

        if vetoes:
            direction, confidence, quality = "WAIT", 0, "WAIT"
            reasons = vetoes + reasons
        else:
            direction = "BUY" if power_dir > 0 else "SELL"
            quality = "EXCELLENT" if confidence >= TrendCandleEngine.QUALITY_EXCELLENT else "GOOD"
            if strict_confluence:
                reasons.append("Strict confluence: power + trend + Fibonacci all strongly aligned")

        label = {"BUY": "CALL / UP", "SELL": "PUT / DOWN", "WAIT": "No clear edge"}[direction]

        return {
            "direction": direction,
            "label": label,
            "confidence": confidence,
            "quality": quality,
            "reasons": reasons,
            "seconds_to_entry": TrendCandleEngine._seconds_to_entry(tracker),
            "buy_power": round(buy_power, 1),
            "sell_power": round(sell_power, 1),
            "trend": trend_dir,
            "trend_quality": trend_quality,
            "fib_levels": fib_levels,
            "nearest_fib_level": nearest_fib_level,
            "fib_swing_high": swing_high,
            "fib_swing_low": swing_low,
            "fib_up_leg": up_leg,
            "strict_confluence": strict_confluence,
        }

    @staticmethod
    def _seconds_to_entry(tracker):
        if not tracker.candle_keys:
            return None
        bucket_end = tracker.candle_keys[-1] + 60
        return max(0, int(bucket_end - time.time()))


class SessionPatternEngine:
    """OTC-focused engine: candlestick patterns + session-time weight."""
    MIN_CANDLES = 5
    MIN_SESSION_WEIGHT = 0.4
    STREAK_CONTINUATION_MAX = 3
    STREAK_EXHAUSTION_MIN = 5
    QUALITY_GOOD = 60
    QUALITY_EXCELLENT = 80

    SESSION_WEIGHTS = {
        0: 0.5, 1: 0.4, 2: 0.35, 3: 0.35, 4: 0.4, 5: 0.5,
        6: 0.55, 7: 0.65, 8: 0.7, 9: 0.75, 10: 0.8, 11: 0.8,
        12: 0.85, 13: 0.9, 14: 0.9, 15: 0.85, 16: 0.8, 17: 0.75,
        18: 0.7, 19: 0.65, 20: 0.6, 21: 0.55, 22: 0.5, 23: 0.5,
    }

    @staticmethod
    def _streak(candles):
        if not candles:
            return 0, 0
        last = candles[-1]
        if last["close"] > last["open"]:
            direction = 1
        elif last["close"] < last["open"]:
            direction = -1
        else:
            return 0, 0

        length = 0
        for c in reversed(candles):
            d = 1 if c["close"] > c["open"] else (-1 if c["close"] < c["open"] else 0)
            if d != direction:
                break
            length += 1
            if length >= 5:
                break
        return direction, length

    @staticmethod
    def compute(tracker, min_confidence=0, min_session_weight=None, streak_continuation_max=None):
        min_session_weight = (
            SessionPatternEngine.MIN_SESSION_WEIGHT if min_session_weight is None else min_session_weight
        )
        streak_continuation_max = (
            SessionPatternEngine.STREAK_CONTINUATION_MAX if streak_continuation_max is None else streak_continuation_max
        )

        closed_buckets = sorted(b for b in tracker.candles if tracker.candles[b]["is_closed"])
        if len(closed_buckets) < SessionPatternEngine.MIN_CANDLES:
            return {
                "direction": "WAIT", "label": "Collecting data", "confidence": 0, "quality": "WAIT",
                "reasons": [f"Need {SessionPatternEngine.MIN_CANDLES - len(closed_buckets)} more closed candles"],
                "seconds_to_entry": SessionPatternEngine._seconds_to_entry(tracker),
                "pattern_bias": 0, "streak_dir": 0, "streak_len": 0,
                "session_weight": None, "hour_utc": None,
            }

        candles = [tracker.candles[b] for b in closed_buckets]
        reasons = []
        vetoes = []

        last_bucket = closed_buckets[-1]
        hour_utc = datetime.fromtimestamp(last_bucket, timezone.utc).hour
        session_weight = SessionPatternEngine.SESSION_WEIGHTS.get(hour_utc, 0.5)
        if session_weight < min_session_weight:
            vetoes.append(
                f"Hour {hour_utc:02d}:00 UTC session weight {session_weight:.2f} < "
                f"{min_session_weight:.2f} floor"
            )
        reasons.append(f"Session {hour_utc:02d}:00 UTC weight {session_weight:.2f}")

        patterns = CandlePatterns.detect(candles[-3:])
        pattern_bias = sum(b for _, b in patterns if b != 0)
        pattern_dir = 1 if pattern_bias > 0 else (-1 if pattern_bias < 0 else 0)
        if patterns:
            reasons.append("Patterns: " + ", ".join(p for p, _ in patterns))

        streak_dir, streak_len = SessionPatternEngine._streak(candles)
        streak_vote = 0
        if streak_len > 0:
            if streak_len <= streak_continuation_max:
                streak_vote = streak_dir
                reasons.append(f"Streak {streak_len} {'up' if streak_dir > 0 else 'down'} — continuation bias")
            elif streak_len >= SessionPatternEngine.STREAK_EXHAUSTION_MIN:
                streak_vote = -streak_dir
                reasons.append(f"Streak {streak_len} {'up' if streak_dir > 0 else 'down'} — exhaustion, reversal bias")
            else:
                reasons.append(f"Streak {streak_len} {'up' if streak_dir > 0 else 'down'} — neutral zone, no vote")

        combined = pattern_dir + streak_vote
        if combined > 0:
            direction_dir = 1
        elif combined < 0:
            direction_dir = -1
        else:
            direction_dir = 0

        if direction_dir == 0:
            vetoes.append("Pattern and streak give no clear combined direction")
        elif pattern_dir != 0 and streak_vote != 0 and pattern_dir != streak_vote:
            reasons.append("Note: pattern and streak partially disagree, net direction used")

        base_conf = min(abs(pattern_bias) * 25, 60)
        streak_conf = min(streak_len * 8, 25) if streak_vote != 0 else 0
        confidence = round((base_conf + streak_conf) * session_weight)
        confidence = min(confidence, 100)

        if not vetoes and confidence < SessionPatternEngine.QUALITY_GOOD:
            vetoes.append(f"Confidence {confidence} < {SessionPatternEngine.QUALITY_GOOD} quality floor")

        if vetoes:
            direction, confidence, quality = "WAIT", 0, "WAIT"
            reasons = vetoes + reasons
        else:
            direction = "BUY" if direction_dir > 0 else "SELL"
            quality = "EXCELLENT" if confidence >= SessionPatternEngine.QUALITY_EXCELLENT else "GOOD"

        label = {"BUY": "CALL / UP", "SELL": "PUT / DOWN", "WAIT": "No clear edge"}[direction]

        return {
            "direction": direction,
            "label": label,
            "confidence": confidence,
            "quality": quality,
            "reasons": reasons,
            "seconds_to_entry": SessionPatternEngine._seconds_to_entry(tracker),
            "pattern_bias": pattern_bias,
            "streak_dir": streak_dir,
            "streak_len": streak_len,
            "session_weight": round(session_weight, 2),
            "hour_utc": hour_utc,
        }

    @staticmethod
    def _seconds_to_entry(tracker):
        if not tracker.candle_keys:
            return None
        bucket_end = tracker.candle_keys[-1] + 60
        return max(0, int(bucket_end - time.time()))


class SmartMoneyConcepts:
    """Smart Money Concepts reader: swing structure, BOS/CHoCH, Order Block
    (retest-required), FVG + Inverse FVG (mitigation-required), liquidity
    sweep, stop hunt, institutional trap, equal highs/lows, premium/
    discount zone. Inducement/MSS folded into CHoCH per prior notes."""

    @staticmethod
    def _swings(candles, lookback=1):
        highs, lows = [], []
        n = len(candles)
        for i in range(lookback, n - lookback):
            window = candles[i - lookback:i + lookback + 1]
            hi, lo = candles[i]["high"], candles[i]["low"]
            if hi == max(c["high"] for c in window):
                highs.append((i, hi))
            if lo == min(c["low"] for c in window):
                lows.append((i, lo))
        return highs, lows

    @staticmethod
    def _structure_bias(candles, lookback):
        highs, lows = SmartMoneyConcepts._swings(candles, lookback)
        if len(highs) < 2 or len(lows) < 2:
            return 0, 0, "insufficient swings"
        last_close = candles[-1]["close"]
        last_high_idx, last_high = highs[-1]
        last_low_idx, last_low = lows[-1]
        prev_high = highs[-2][1]
        prev_low = lows[-2][1]

        structure_up = last_high > prev_high and last_low > prev_low
        structure_down = last_high < prev_high and last_low < prev_low

        bos, choch = 0, 0
        if last_close > last_high:
            if structure_up or (not structure_down):
                bos = 1
            else:
                choch = 1
        elif last_close < last_low:
            if structure_down or (not structure_up):
                bos = -1
            else:
                choch = -1
        return bos, choch, ("bullish structure" if structure_up else "bearish structure" if structure_down else "mixed structure")

    @staticmethod
    def _order_block(candles, bos_direction, lookback=30):
        if bos_direction == 0 or len(candles) < 5:
            return None
        window = candles[-lookback:] if len(candles) > lookback else candles
        for i in range(len(window) - 2, 0, -1):
            c = window[i]
            bullish_candle = c["close"] > c["open"]
            if bos_direction > 0 and not bullish_candle:
                return (c["low"], c["high"])
            if bos_direction < 0 and bullish_candle:
                return (c["low"], c["high"])
        return None

    @staticmethod
    def _order_block_retested(candles, ob_zone, bos_direction, lookback=30):
        if not ob_zone or bos_direction == 0 or len(candles) < 3:
            return False
        lo, hi = ob_zone
        window = candles[-lookback:] if len(candles) > lookback else candles
        offset = len(candles) - len(window)
        formed_idx = None
        for i in range(len(window) - 2, 0, -1):
            c = window[i]
            bullish_candle = c["close"] > c["open"]
            same_zone = abs(c["low"] - lo) < 1e-9 and abs(c["high"] - hi) < 1e-9
            if not same_zone:
                continue
            if (bos_direction > 0 and not bullish_candle) or (bos_direction < 0 and bullish_candle):
                formed_idx = offset + i
                break
        if formed_idx is None or formed_idx >= len(candles) - 1:
            return False
        after = candles[formed_idx + 1:-1]
        return any(lo <= c["low"] <= hi or lo <= c["high"] <= hi for c in after)

    @staticmethod
    def _fair_value_gap(candles, lookback=15):
        window = candles[-lookback:] if len(candles) > lookback else candles
        for i in range(len(window) - 1, 1, -1):
            c0, c1, c2 = window[i - 2], window[i - 1], window[i]
            if c0["high"] < c2["low"]:
                return ("bullish", c0["high"], c2["low"])
            if c0["low"] > c2["high"]:
                return ("bearish", c2["high"], c0["low"])
        return None

    @staticmethod
    def _fvg_mitigated(candles, fvg, lookback=15):
        if not fvg or len(candles) < 2:
            return False
        ftype, lo, hi = fvg
        window = candles[-lookback:] if len(candles) > lookback else candles
        offset = len(candles) - len(window)
        formed_idx = None
        for i in range(len(window) - 1, 1, -1):
            c0, c1, c2 = window[i - 2], window[i - 1], window[i]
            if ftype == "bullish" and abs(c0["high"] - lo) < 1e-9 and abs(c2["low"] - hi) < 1e-9:
                formed_idx = offset + i
                break
            if ftype == "bearish" and abs(c2["high"] - hi) < 1e-9 and abs(c0["low"] - lo) < 1e-9:
                formed_idx = offset + i
                break
        if formed_idx is None or formed_idx >= len(candles) - 1:
            return False
        after = candles[formed_idx + 1:-1]
        return any(lo <= c["low"] <= hi or lo <= c["high"] <= hi for c in after)

    @staticmethod
    def _liquidity_sweep(candles, highs, lows, lookback=15):
        if not candles:
            return 0
        c = candles[-1]
        recent_highs = [p for i, p in highs if i >= len(candles) - lookback]
        recent_lows = [p for i, p in lows if i >= len(candles) - lookback]
        if recent_lows:
            ref_low = min(recent_lows)
            if c["low"] < ref_low and c["close"] > ref_low:
                return 1
        if recent_highs:
            ref_high = max(recent_highs)
            if c["high"] > ref_high and c["close"] < ref_high:
                return -1
        return 0

    @staticmethod
    def _stop_hunt(candles, highs, lows, lookback=40, hold_min_candles=10):
        if not candles or len(candles) < hold_min_candles + 2:
            return 0
        c = candles[-1]
        n = len(candles)
        old_highs = [p for i, p in highs if n - lookback <= i <= n - hold_min_candles]
        old_lows = [p for i, p in lows if n - lookback <= i <= n - hold_min_candles]
        if old_lows:
            ref_low = min(old_lows)
            if c["low"] < ref_low and c["close"] > ref_low:
                return 1
        if old_highs:
            ref_high = max(old_highs)
            if c["high"] > ref_high and c["close"] < ref_high:
                return -1
        return 0

    @staticmethod
    def _institutional_trap(candles, liquidity_sweep_dir):
        if liquidity_sweep_dir == 0 or not candles:
            return 0
        c = candles[-1]
        rng = max(c["high"] - c["low"], 1e-12)
        body_pct = abs(c["close"] - c["open"]) / rng
        candle_dir = 1 if c["close"] > c["open"] else (-1 if c["close"] < c["open"] else 0)
        if candle_dir == liquidity_sweep_dir and body_pct >= 0.6:
            return liquidity_sweep_dir
        return 0

    @staticmethod
    def _equal_levels(points, tolerance_pct=0.03, count=2):
        if len(points) < count:
            return False
        prices = [p for _, p in points[-count:]]
        avg = sum(prices) / len(prices)
        if avg == 0:
            return False
        return all(abs(p - avg) / avg * 100 <= tolerance_pct for p in prices)

    @staticmethod
    def _breaker_and_mitigation(candles, order_block, bos_dir):
        if not order_block or bos_dir == 0 or len(candles) < 5:
            return None, 0
        lo, hi = order_block
        idx = None
        for i in range(len(candles) - 2, 0, -1):
            c = candles[i]
            bullish_candle = c["close"] > c["open"]
            same_zone = abs(c["low"] - lo) < 1e-9 and abs(c["high"] - hi) < 1e-9
            if not same_zone:
                continue
            if (bos_dir > 0 and not bullish_candle) or (bos_dir < 0 and bullish_candle):
                idx = i
                break
        if idx is None or idx >= len(candles) - 1:
            return None, 0

        after = candles[idx + 1:]
        last_close = candles[-1]["close"]
        broken = any((c["close"] < lo) if bos_dir > 0 else (c["close"] > hi) for c in after)
        touched = any(lo <= c["low"] <= hi or lo <= c["high"] <= hi for c in after[:-1]) if len(after) > 1 else False

        if broken:
            return ("breaker", -bos_dir) if lo <= last_close <= hi else ("breaker", 0)
        if touched:
            return ("mitigation", bos_dir) if lo <= last_close <= hi else ("mitigation", 0)
        return None, 0

    @staticmethod
    def compute(candles):
        out = {
            "bias": 0, "strength": 0.0,
            "internal_bos": 0, "internal_choch": 0,
            "external_bos": 0, "external_choch": 0,
            "order_block": None, "order_block_signal": 0, "order_block_retested": False,
            "fvg": None, "fvg_signal": 0, "fvg_mitigated": False,
            "inverse_fvg_signal": 0,
            "block_kind": None, "block_signal": 0,
            "liquidity_sweep": 0, "stop_hunt": 0, "institutional_trap": 0,
            "equal_highs": False, "equal_lows": False,
            "zone": "unknown",
            "notes": [],
        }
        if len(candles) < 20:
            out["notes"].append("SMC: insufficient candles")
            return out

        ext_highs, ext_lows = SmartMoneyConcepts._swings(candles, lookback=3)
        int_bos, int_choch, int_note = SmartMoneyConcepts._structure_bias(candles, lookback=1)
        ext_bos, ext_choch, ext_note = SmartMoneyConcepts._structure_bias(candles, lookback=3)
        out["internal_bos"], out["internal_choch"] = int_bos, int_choch
        out["external_bos"], out["external_choch"] = ext_bos, ext_choch
        out["notes"].append(f"internal: {int_note}, external: {ext_note}")

        bos_dir = ext_bos if ext_bos != 0 else int_bos
        ob = SmartMoneyConcepts._order_block(candles, bos_dir)
        out["order_block"] = ob
        last_close = candles[-1]["close"]
        if ob:
            lo, hi = ob
            retested = SmartMoneyConcepts._order_block_retested(candles, ob, bos_dir)
            out["order_block_retested"] = retested
            if retested and lo <= last_close <= hi:
                out["order_block_signal"] = 1 if bos_dir > 0 else -1

        fvg = SmartMoneyConcepts._fair_value_gap(candles)
        out["fvg"] = fvg
        if fvg:
            ftype, lo, hi = fvg
            mitigated = SmartMoneyConcepts._fvg_mitigated(candles, fvg)
            out["fvg_mitigated"] = mitigated
            if mitigated and lo <= last_close <= hi:
                out["fvg_signal"] = 1 if ftype == "bullish" else -1
            if ftype == "bullish" and last_close < lo:
                out["inverse_fvg_signal"] = -1
            elif ftype == "bearish" and last_close > hi:
                out["inverse_fvg_signal"] = 1

        block_kind, block_signal = SmartMoneyConcepts._breaker_and_mitigation(candles, ob, bos_dir)
        out["block_kind"] = block_kind
        out["block_signal"] = block_signal
        if block_kind and block_signal != 0:
            out["notes"].append(f"{block_kind.capitalize()} Block signal={'bullish' if block_signal > 0 else 'bearish'}")

        out["liquidity_sweep"] = SmartMoneyConcepts._liquidity_sweep(candles, ext_highs, ext_lows)
        out["stop_hunt"] = SmartMoneyConcepts._stop_hunt(candles, ext_highs, ext_lows)
        out["institutional_trap"] = SmartMoneyConcepts._institutional_trap(candles, out["liquidity_sweep"])
        out["equal_highs"] = SmartMoneyConcepts._equal_levels(ext_highs)
        out["equal_lows"] = SmartMoneyConcepts._equal_levels(ext_lows)

        if ext_highs and ext_lows:
            swing_high = max(p for _, p in ext_highs[-5:])
            swing_low = min(p for _, p in ext_lows[-5:])
            if swing_high > swing_low:
                position = (last_close - swing_low) / (swing_high - swing_low)
                if position >= 0.6:
                    out["zone"] = "premium"
                elif position <= 0.4:
                    out["zone"] = "discount"
                else:
                    out["zone"] = "equilibrium"

        bias_score = 0.0
        bias_score += 2.0 * ext_choch + 1.5 * ext_bos
        bias_score += 1.0 * int_choch + 0.7 * int_bos
        bias_score += 0.8 * out["order_block_signal"]
        bias_score += 0.8 * out["fvg_signal"]
        bias_score += 0.5 * out["inverse_fvg_signal"]
        bias_score += 0.6 * out["liquidity_sweep"]
        bias_score += 0.5 * out["stop_hunt"]
        bias_score += 0.5 * out["institutional_trap"]
        bias_score += 0.7 * block_signal
        max_component = 2.0 + 1.5 + 1.0 + 0.7 + 0.8 + 0.8 + 0.5 + 0.6 + 0.5 + 0.5 + 0.7
        out["bias"] = 1 if bias_score > 0.3 else (-1 if bias_score < -0.3 else 0)
        out["strength"] = round(min(abs(bias_score) / max_component, 1.0), 2)
        return out


class TradingSession:
    ASIA = (0, 9)
    LONDON = (7, 16)
    NEW_YORK = (12, 21)

    @staticmethod
    def _in_window(hour, window):
        start, end = window
        return start <= hour < end

    @staticmethod
    def label(hour_utc):
        in_asia = TradingSession._in_window(hour_utc, TradingSession.ASIA)
        in_london = TradingSession._in_window(hour_utc, TradingSession.LONDON)
        in_ny = TradingSession._in_window(hour_utc, TradingSession.NEW_YORK)
        if in_london and in_ny:
            return "London-NY Overlap"
        if in_london:
            return "London"
        if in_ny:
            return "New York"
        if in_asia:
            return "Asia"
        return "Off-Hours"


class SelfLearningStats:
    MIN_SAMPLES = 10
    MIN_MULT, MAX_MULT = 0.7, 1.3

    @staticmethod
    def _bucket_multiplier(records_subset):
        n = len(records_subset)
        if n < SelfLearningStats.MIN_SAMPLES:
            return 1.0
        wins = sum(1 for r in records_subset if r["result"] == "WIN")
        win_rate = wins / n
        mult = 1.0 + (win_rate - 0.5) * 2 * (SelfLearningStats.MAX_MULT - 1.0)
        return max(SelfLearningStats.MIN_MULT, min(SelfLearningStats.MAX_MULT, mult))

    @staticmethod
    def multiplier_for(journal, asset, hour_utc, weekday):
        recs = journal.records
        asset_recs = [r for r in recs if r["asset"] == asset]
        hour_recs = [r for r in recs if r["hour"] == hour_utc]
        weekday_recs = [r for r in recs if r.get("weekday") == weekday]
        session_label = TradingSession.label(hour_utc)
        session_recs = [r for r in recs if TradingSession.label(r["hour"]) == session_label]

        m_asset = SelfLearningStats._bucket_multiplier(asset_recs)
        m_hour = SelfLearningStats._bucket_multiplier(hour_recs)
        m_weekday = SelfLearningStats._bucket_multiplier(weekday_recs)
        m_session = SelfLearningStats._bucket_multiplier(session_recs)

        combined = (m_asset * m_hour * m_weekday * m_session) ** 0.25
        return max(SelfLearningStats.MIN_MULT, min(SelfLearningStats.MAX_MULT, combined))


class ProOTCEngine:
    """
    Professional OTC Trading Engine — quality-over-quantity, multi-layer
    confirmation. See prior notes for the full spec-section mapping.

    RESCALED FOR FEWER CANDLES (this turn): the original version needed
    up to 315 raw 1-minute candles before the 15-minute MTF timeframe
    alone could produce a direction, and ADX/fake-breakout hard gates
    needed 22-28 candles just to stop permanently vetoing. Every period
    below has been shortened proportionally (roughly halved or more):
      - ADX/ATR: 14 -> 7
      - MACD/Adaptive MACD: 12/26/9 -> 5/10/4
      - RSI/Adaptive RSI: 14 -> 7
      - StochRSI: 14/14 -> 7/7
      - CCI/Williams %R/MFI: 20/14/14 -> 10/7/7
      - Bollinger/Keltner/Donchian/StdDev/HistVol: 20 -> 10
      - SuperTrend/Hull MA: 10/9 -> 6/5
      - MTF quick-trend check (used for all 5 timeframes): EMA9/21 -> EMA3/6
      - EMA trend stack: 20/50/100/200 -> 5/10/20/40
      - Fake-breakout Donchian window: 22 -> 12 (matches shortened Donchian)
      - MIN_CANDLES: 60 -> 20 — chosen as the smallest number where ADX,
        ATR, and the fake-breakout check are all still genuinely
        computable, not just technically running while permanently
        vetoing. Going lower would make those hard gates meaningless.

    HONEST TRADE-OFF: shorter periods react faster to fewer candles but
    are meaningfully noisier — this is the same trade-off documented for
    every other engine rescale in this conversation, not free precision.
    A 7-period ADX or 5/10/4 MACD will fire and flip more often than the
    textbook 14/26/9 versions on genuinely random noise. Validate with
    --backtest-days before trusting it live.
    """
    MIN_CANDLES = 20

    # --- Gate defaults (relaxed; see STRICTNESS_PRESETS below) ---------
    ADX_THRESHOLD_DEFAULT = 18.0
    ATR_MIN_PCT_DEFAULT = 0.005
    ATR_MAX_PCT_DEFAULT = 3.00

    # Score is now normalised 0-100 (weights below sum to exactly 100),
    # so "min score" and "confidence %" are the same number.
    AI_SCORE_MAX = 100.0
    MIN_AI_SCORE_DEFAULT = 66.0
    WEIGHTS = {
        "trend": 26, "momentum": 18, "mtf": 16,
        "liquidity": 12, "order_block": 9, "fvg": 7,
        "pattern": 6, "volume": 6,
    }

    CANDLE_MIN_BODY_PCT = 0.10
    CANDLE_MAX_OPPOSITE_WICK_RATIO = 3.0

    STRICTNESS_DEFAULT = "BALANCED"
    STRICTNESS_PRESETS = {
        # min_score      : normalised score needed to fire
        # dominance      : share of directional weight the winning side needs
        # min_body       : minimum candle body as % of range
        # require_smc    : how many of (liquidity sweep / order block / FVG) must align
        # adx_gate       : veto when ADX below threshold
        # fake_bo_veto   : veto on failed-breakout against direction
        # mtf_conflict   : veto when the majority of timeframes point the other way
        "STRICT":     {"min_score": 58.0, "dominance": 0.68, "min_body": 0.15,
                       "require_smc": 1, "adx_gate": True,  "fake_bo_veto": True,  "mtf_conflict": True},
        "BALANCED":   {"min_score": 66.0, "dominance": 0.58, "min_body": 0.10,
                       "require_smc": 0, "adx_gate": True,  "fake_bo_veto": True,  "mtf_conflict": True},
        "AGGRESSIVE": {"min_score": 62.0, "dominance": 0.50, "min_body": 0.04,
                       "require_smc": 0, "adx_gate": False, "fake_bo_veto": False, "mtf_conflict": False},
    }

    # Rescaled periods (see class docstring)
    ADX_PERIOD = 7
    ATR_PERIOD = 7
    MTF_FAST, MTF_SLOW = 3, 6
    EMA_TIERS = (5, 10, 20, 40)
    SUPERTREND_PERIOD = 6
    HULL_PERIOD = 5
    RSI_PERIOD = 7
    MACD_FAST, MACD_SLOW, MACD_SIGNAL = 5, 10, 4
    STOCH_PERIOD = 7
    CCI_PERIOD = 10
    WILLIAMS_PERIOD = 7
    MFI_PERIOD = 7
    BB_KC_DC_PERIOD = 10
    FAKE_BREAKOUT_WINDOW = 12

    @staticmethod
    def _quick_trend_dir(closes, fast=None, slow=None):
        fast = ProOTCEngine.MTF_FAST if fast is None else fast
        slow = ProOTCEngine.MTF_SLOW if slow is None else slow
        if len(closes) < slow:
            return None
        f = Indicators.ema_aligned(closes, fast)[-1]
        s = Indicators.ema_aligned(closes, slow)[-1]
        if f is None or s is None:
            return None
        return 1 if f > s else (-1 if f < s else 0)

    @staticmethod
    def _resample_candle_closes(candles, interval_seconds):
        buckets = defaultdict(list)
        for c in candles:
            key = (c["timestamp"] // interval_seconds) * interval_seconds
            buckets[key].append(c)
        return [buckets[key][-1]["close"] for key in sorted(buckets.keys())]

    @staticmethod
    def _trend_engine(closes, highs, lows, volumes):
        notes = []
        votes = []

        tiers = [Indicators.ema_aligned(closes, p)[-1] if len(closes) >= p else None for p in ProOTCEngine.EMA_TIERS]
        stack = [v for v in tiers if v is not None]
        if len(stack) >= 2:
            pairs = len(stack) - 1
            up = sum(1 for i in range(pairs) if stack[i] > stack[i + 1])
            down = sum(1 for i in range(pairs) if stack[i] < stack[i + 1])
            ema_dir = 1 if up > down else (-1 if down > up else 0)
            ema_strength = max(up, down) / pairs if pairs else 0
            if ema_dir != 0:
                votes.append((ema_dir, 3 * ema_strength))
            notes.append(f"EMA stack {up}up/{down}down of {pairs} ({len(stack)}/{len(ProOTCEngine.EMA_TIERS)} EMAs available)")

        st_dir, st_val = Indicators.supertrend(highs, lows, closes, period=ProOTCEngine.SUPERTREND_PERIOD)
        if st_dir:
            votes.append((st_dir, 2))
            notes.append(f"SuperTrend {'bullish' if st_dir > 0 else 'bearish'}")

        hma = Indicators.hull_ma(closes, period=ProOTCEngine.HULL_PERIOD)
        if hma is not None:
            hma_dir = 1 if closes[-1] > hma else (-1 if closes[-1] < hma else 0)
            if hma_dir != 0:
                votes.append((hma_dir, 2))
                notes.append(f"Hull MA {'below' if hma_dir > 0 else 'above'} price")

        vwap_val = Indicators.vwap(highs, lows, closes, volumes)
        if vwap_val is not None:
            vwap_dir = 1 if closes[-1] > vwap_val else (-1 if closes[-1] < vwap_val else 0)
            if vwap_dir != 0:
                votes.append((vwap_dir, 2))
                notes.append(f"Price {'above' if vwap_dir > 0 else 'below'} VWAP")

        adx_val, plus_di, minus_di = Indicators.adx(highs, lows, closes, period=ProOTCEngine.ADX_PERIOD)
        if adx_val is not None and plus_di is not None:
            adx_dir = 1 if plus_di > minus_di else (-1 if minus_di > plus_di else 0)
            if adx_dir != 0:
                weight = 3 * min(adx_val / 40, 1.0)
                votes.append((adx_dir, weight))
                notes.append(f"ADX({ProOTCEngine.ADX_PERIOD}) {adx_val:.1f}, {'+DI' if adx_dir > 0 else '-DI'} dominant")

        slope = Indicators.linreg_slope(closes, period=7)
        if slope is not None:
            slope_dir = 1 if slope > 0 else (-1 if slope < 0 else 0)
            if slope_dir != 0:
                votes.append((slope_dir, 2))
                notes.append(f"Linear regression slope {'up' if slope_dir > 0 else 'down'} ({slope:+.3f}%/candle)")

        atr_strength_boost = 1.0
        if len(closes) > 15:
            atr_val, _ = Indicators.atr(highs, lows, closes, period=ProOTCEngine.ATR_PERIOD)
            prior_atr_val, _ = Indicators.atr(highs[:-3], lows[:-3], closes[:-3], period=ProOTCEngine.ATR_PERIOD)
            if atr_val is not None and prior_atr_val is not None:
                atr_rising = atr_val > prior_atr_val
                notes.append(f"ATR trend: {'expanding' if atr_rising else 'contracting'}")
                atr_strength_boost = 1.1 if atr_rising else 0.95

        if not votes:
            return 0, 0, notes + ["Trend: no indicators available yet"]

        total_weight = sum(w for _, w in votes)
        net = sum(d * w for d, w in votes)
        trend_dir = 1 if net > 0 else (-1 if net < 0 else 0)
        strength = abs(net) / total_weight if total_weight > 0 else 0
        trend_score_raw = min(100, round(strength * 100 * atr_strength_boost))
        return trend_dir, trend_score_raw, notes

    @staticmethod
    def _momentum_engine(closes, highs, lows, volumes, atr_pct):
        notes = []
        votes = []

        rsi = Indicators.rsi_aligned(closes, ProOTCEngine.RSI_PERIOD)[-1] if len(closes) >= ProOTCEngine.RSI_PERIOD + 1 else None
        if rsi is not None:
            if rsi < 30:
                votes.append((1, 2)); notes.append(f"RSI({ProOTCEngine.RSI_PERIOD}) {rsi:.0f} oversold")
            elif rsi > 70:
                votes.append((-1, 2)); notes.append(f"RSI({ProOTCEngine.RSI_PERIOD}) {rsi:.0f} overbought")

        a_rsi = Indicators.adaptive_rsi(closes, atr_pct, base_period=ProOTCEngine.RSI_PERIOD)
        if a_rsi is not None:
            if a_rsi < 30:
                votes.append((1, 2)); notes.append(f"Adaptive RSI {a_rsi:.0f} oversold")
            elif a_rsi > 70:
                votes.append((-1, 2)); notes.append(f"Adaptive RSI {a_rsi:.0f} overbought")

        macd_val, macd_sig, macd_hist = Indicators.macd(
            closes, fast=ProOTCEngine.MACD_FAST, slow=ProOTCEngine.MACD_SLOW, signal=ProOTCEngine.MACD_SIGNAL
        )
        if macd_hist is not None:
            d = 1 if macd_hist > 0 else (-1 if macd_hist < 0 else 0)
            if d != 0:
                votes.append((d, 2)); notes.append(f"MACD histogram {'positive' if d > 0 else 'negative'}")

        amacd_val, amacd_sig, amacd_hist = Indicators.adaptive_macd(
            closes, atr_pct, base_fast=ProOTCEngine.MACD_FAST, base_slow=ProOTCEngine.MACD_SLOW,
            base_signal=ProOTCEngine.MACD_SIGNAL
        )
        if amacd_hist is not None:
            d = 1 if amacd_hist > 0 else (-1 if amacd_hist < 0 else 0)
            if d != 0:
                votes.append((d, 2)); notes.append(f"Adaptive MACD histogram {'positive' if d > 0 else 'negative'}")

        stoch = Indicators.stoch_rsi(closes, rsi_period=ProOTCEngine.STOCH_PERIOD, stoch_period=ProOTCEngine.STOCH_PERIOD)
        if stoch is not None:
            if stoch < 20:
                votes.append((1, 1.5)); notes.append(f"StochRSI {stoch:.0f} oversold")
            elif stoch > 80:
                votes.append((-1, 1.5)); notes.append(f"StochRSI {stoch:.0f} overbought")

        cci_val = Indicators.cci(highs, lows, closes, period=ProOTCEngine.CCI_PERIOD)
        if cci_val is not None:
            if cci_val > 100:
                votes.append((1, 1.5)); notes.append(f"CCI {cci_val:.0f} bullish extreme")
            elif cci_val < -100:
                votes.append((-1, 1.5)); notes.append(f"CCI {cci_val:.0f} bearish extreme")

        roc_val = Indicators.roc(closes, period=6)
        if roc_val is not None:
            d = 1 if roc_val > 0 else (-1 if roc_val < 0 else 0)
            if d != 0:
                votes.append((d, 1)); notes.append(f"ROC {roc_val:+.2f}%")

        mom_val = Indicators.momentum(closes, period=6)
        if mom_val is not None:
            d = 1 if mom_val > 0 else (-1 if mom_val < 0 else 0)
            if d != 0:
                votes.append((d, 1))

        wr = Indicators.williams_r(highs, lows, closes, period=ProOTCEngine.WILLIAMS_PERIOD)
        if wr is not None:
            if wr > -20:
                votes.append((-1, 1.5)); notes.append(f"Williams %R {wr:.0f} overbought")
            elif wr < -80:
                votes.append((1, 1.5)); notes.append(f"Williams %R {wr:.0f} oversold")

        mfi_val = Indicators.mfi(highs, lows, closes, volumes, period=ProOTCEngine.MFI_PERIOD)
        if mfi_val is not None:
            if mfi_val < 20:
                votes.append((1, 1.5)); notes.append(f"MFI {mfi_val:.0f} oversold")
            elif mfi_val > 80:
                votes.append((-1, 1.5)); notes.append(f"MFI {mfi_val:.0f} overbought")

        if not votes:
            return 0, 0, notes + ["Momentum: no indicators available yet"]

        total_weight = sum(w for _, w in votes)
        net = sum(d * w for d, w in votes)
        momentum_dir = 1 if net > 0 else (-1 if net < 0 else 0)
        strength = abs(net) / total_weight if total_weight > 0 else 0
        momentum_score_raw = min(100, round(strength * 100))
        return momentum_dir, momentum_score_raw, notes

    @staticmethod
    def _volatility_engine(closes, highs, lows, adx_val, atr_pct, tentative_dir):
        notes = []
        p = ProOTCEngine.BB_KC_DC_PERIOD
        bb_upper, bb_mid, bb_lower, percent_b = Indicators.bollinger(closes, period=p)
        kc_upper, kc_mid, kc_lower = Indicators.keltner(closes, highs, lows, period=p)
        dc_upper, dc_mid, dc_lower = Indicators.donchian(highs, lows, period=p)
        stddev = Indicators.stddev_pct(closes, period=p)
        hv = Indicators.historical_volatility(closes, period=p)

        squeeze = False
        if bb_upper is not None and kc_upper is not None:
            squeeze = (bb_upper <= kc_upper) and (bb_lower >= kc_lower)

        fake_breakout_against = False
        w = ProOTCEngine.FAKE_BREAKOUT_WINDOW
        if len(closes) >= w:
            prior_upper = max(highs[-w:-2])
            prior_lower = min(lows[-w:-2])
            second_last_close = closes[-2]
            last_close = closes[-1]
            broke_up_then_failed = second_last_close > prior_upper and last_close <= prior_upper
            broke_down_then_failed = second_last_close < prior_lower and last_close >= prior_lower
            if tentative_dir > 0 and broke_up_then_failed:
                fake_breakout_against = True
                notes.append("Donchian: bullish breakout failed (fake breakout) — direction untrustworthy")
            if tentative_dir < 0 and broke_down_then_failed:
                fake_breakout_against = True
                notes.append("Donchian: bearish breakout failed (fake breakout) — direction untrustworthy")

        regime = "UNKNOWN"
        if adx_val is not None:
            if squeeze:
                regime = "COMPRESSION"
            elif adx_val >= 35:
                regime = "STRONG_TREND"
            elif adx_val >= 20:
                regime = "WEAK_TREND"
            elif atr_pct is not None and atr_pct > 0.15:
                regime = "HIGH_VOLATILITY"
            elif atr_pct is not None and atr_pct < 0.02:
                regime = "LOW_VOLATILITY"
            else:
                regime = "SIDEWAYS"
        notes.append(f"Regime: {regime}" + (" (squeeze/compression detected)" if squeeze else ""))
        if stddev is not None:
            hv_str = f", Historical Vol {hv:.3f}%" if hv is not None else ""
            notes.append(f"StdDev {stddev:.3f}%{hv_str}")

        return regime, notes, fake_breakout_against

    @staticmethod
    def compute(tracker, asset=None, adx_threshold=None, atr_min_pct=None, atr_max_pct=None,
                min_ai_score=None, self_learning_multiplier=1.0, strictness=None):
        """
        Weighted-confluence scoring.

        The previous version required ~12 independent conditions to be true
        on the SAME candle (liquidity sweep AND retested order block AND
        mitigated FVG AND unanimous 30s/1m/3m/5m/15m agreement AND ...).
        Measured on 400 simulated sessions those fired on 1.5% / 1.2% / 4.2%
        of candles respectively, so the joint probability was effectively
        zero — and the 95/110 score threshold was itself unreachable, because
        missing 'pattern' and 'volume' alone capped the score at 90.

        Now: a small number of real hard gates, and everything else is a
        weighted vote that adds or withholds points. Direction is decided by
        weight dominance, not by unanimity.
        """
        preset = ProOTCEngine.STRICTNESS_PRESETS.get(
            (strictness or ProOTCEngine.STRICTNESS_DEFAULT).upper(),
            ProOTCEngine.STRICTNESS_PRESETS["BALANCED"],
        )
        adx_threshold = ProOTCEngine.ADX_THRESHOLD_DEFAULT if adx_threshold is None else adx_threshold
        atr_min_pct = ProOTCEngine.ATR_MIN_PCT_DEFAULT if atr_min_pct is None else atr_min_pct
        atr_max_pct = ProOTCEngine.ATR_MAX_PCT_DEFAULT if atr_max_pct is None else atr_max_pct
        min_ai_score = preset["min_score"] if min_ai_score is None else min_ai_score

        empty_extra = {
            "ai_score": 0.0, "ai_score_max": ProOTCEngine.AI_SCORE_MAX, "min_ai_score": min_ai_score,
            "score_breakdown": {}, "regime": "UNKNOWN", "mtf_status": {}, "adx": None, "atr_pct": None,
            "self_learning_multiplier": round(self_learning_multiplier, 2),
            "strictness": (strictness or ProOTCEngine.STRICTNESS_DEFAULT).upper(),
            "dominance": 0.0, "missing": [],
        }

        closed_buckets = sorted(b for b in tracker.candles if tracker.candles[b]["is_closed"])
        if len(closed_buckets) < ProOTCEngine.MIN_CANDLES:
            base = {
                "direction": "WAIT", "label": "Collecting data", "confidence": 0, "quality": "WAIT",
                "reasons": [f"Need {ProOTCEngine.MIN_CANDLES - len(closed_buckets)} more closed candles"],
                "seconds_to_entry": ProOTCEngine._seconds_to_entry(tracker),
            }
            base.update(empty_extra)
            return base

        candles = [tracker.candles[b] for b in closed_buckets]
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [max(c.get("ticks", 1), 1) for c in candles]

        reasons = []
        vetoes = []
        missing = []

        # ---------------- candle quality (hard gate, relaxed) ----------
        last = candles[-1]
        rng = max(last["high"] - last["low"], 1e-12)
        body = abs(last["close"] - last["open"])
        body_pct = body / rng
        candle_bull = last["close"] > last["open"]
        upper_wick = last["high"] - max(last["open"], last["close"])
        lower_wick = min(last["open"], last["close"]) - last["low"]
        opposite_wick = lower_wick if candle_bull else upper_wick
        if body_pct < preset["min_body"]:
            vetoes.append(f"Weak candle: body {body_pct*100:.1f}% of range (min {preset['min_body']*100:.0f}%)")
        elif body > 0 and opposite_wick > ProOTCEngine.CANDLE_MAX_OPPOSITE_WICK_RATIO * body:
            vetoes.append("Weak candle: long opposite wick relative to body")
        else:
            reasons.append(f"Candle quality OK (body {body_pct*100:.0f}% of range)")

        # ---------------- multi-timeframe (now a weighted vote) --------
        now_ts = tracker.candle_keys[-1] + 60 if tracker.candle_keys else time.time()
        closes_30s = resample_ticks_to_closes(tracker.tick_history, 30, now_ts)
        d30 = ProOTCEngine._quick_trend_dir(closes_30s)
        d1 = ProOTCEngine._quick_trend_dir(closes)
        d3 = ProOTCEngine._quick_trend_dir(ProOTCEngine._resample_candle_closes(candles, 180))
        d5 = ProOTCEngine._quick_trend_dir(ProOTCEngine._resample_candle_closes(candles, 300))
        d15 = ProOTCEngine._quick_trend_dir(ProOTCEngine._resample_candle_closes(candles, 900))
        mtf_status = {}
        for label, d in (("30s", d30), ("1m", d1), ("3m", d3), ("5m", d5), ("15m", d15)):
            if d is not None:
                mtf_status[label] = d

        mtf_dir, mtf_quality = 0, 0.0
        if len(mtf_status) < 2:
            missing.append("MTF history")
        else:
            vals = list(mtf_status.values())
            ups = sum(1 for v in vals if v > 0)
            downs = sum(1 for v in vals if v < 0)
            if ups == downs:
                missing.append("MTF split")
            else:
                mtf_dir = 1 if ups > downs else -1
                mtf_quality = max(ups, downs) / len(vals)
                reasons.append(
                    f"MTF {ups}up/{downs}down of {len(vals)} → "
                    f"{'UP' if mtf_dir > 0 else 'DOWN'} ({mtf_quality*100:.0f}% agreement)"
                )

        # ---------------- smart money concepts (now bonuses) -----------
        smc = SmartMoneyConcepts.compute(candles)

        liquidity_dir = smc["liquidity_sweep"]
        liquidity_quality = 0.0
        liquidity_notes = []
        if liquidity_dir != 0:
            liquidity_quality = 0.7
            if (liquidity_dir > 0 and smc["equal_lows"]) or (liquidity_dir < 0 and smc["equal_highs"]):
                liquidity_quality += 0.1
                liquidity_notes.append("equal-level pool")
            if smc.get("stop_hunt") == liquidity_dir:
                liquidity_quality += 0.1
                liquidity_notes.append("stop-hunt")
            if smc.get("institutional_trap") == liquidity_dir:
                liquidity_quality += 0.1
                liquidity_notes.append("institutional trap")
            liquidity_quality = min(liquidity_quality, 1.0)
            extra = f" + {', '.join(liquidity_notes)}" if liquidity_notes else ""
            reasons.append(f"Liquidity sweep {'bullish' if liquidity_dir > 0 else 'bearish'}{extra}")
        else:
            missing.append("liquidity sweep")

        ob_dir = smc["order_block_signal"]
        if ob_dir != 0:
            reasons.append(f"Order Block confirmed after retest ({'bullish' if ob_dir > 0 else 'bearish'})")
        else:
            missing.append("order block")

        fvg_dir = smc["fvg_signal"] if smc["fvg_signal"] != 0 else smc["inverse_fvg_signal"]
        if fvg_dir != 0:
            reasons.append(f"FVG confirmed ({'bullish' if fvg_dir > 0 else 'bearish'})")
        else:
            missing.append("FVG")

        smc_hits = sum(1 for d in (liquidity_dir, ob_dir, fvg_dir) if d != 0)

        # ---------------- trend / momentum / volatility ----------------
        trend_dir, trend_score_raw, trend_notes = ProOTCEngine._trend_engine(closes, highs, lows, volumes)
        reasons.extend(trend_notes)

        adx_val, plus_di, minus_di = Indicators.adx(highs, lows, closes, period=ProOTCEngine.ADX_PERIOD)
        atr_val, atr_pct = Indicators.atr(highs, lows, closes, period=ProOTCEngine.ATR_PERIOD)

        if preset["adx_gate"]:
            if adx_val is None:
                vetoes.append("ADX: insufficient data")
            elif adx_val < adx_threshold:
                vetoes.append(f"ADX {adx_val:.1f} < {adx_threshold:.1f} threshold — trend not strong enough")

        if atr_pct is None:
            vetoes.append("ATR: insufficient data")
        elif atr_pct < atr_min_pct:
            vetoes.append(f"ATR {atr_pct:.3f}% below minimum {atr_min_pct:.3f}% — market flat/frozen")
        elif atr_pct > atr_max_pct:
            vetoes.append(f"ATR {atr_pct:.3f}% above maximum {atr_max_pct:.3f}% — market too wild")

        momentum_dir, momentum_score_raw, momentum_notes = ProOTCEngine._momentum_engine(
            closes, highs, lows, volumes, atr_pct
        )
        reasons.extend(momentum_notes)

        regime, vol_notes, fake_breakout_against = ProOTCEngine._volatility_engine(
            closes, highs, lows, adx_val, atr_pct, trend_dir
        )
        reasons.extend(vol_notes)

        # ---------------- patterns & volume ----------------------------
        patterns = CandlePatterns.detect(candles[-4:])
        pattern_bias = sum(b for _, b in patterns if b != 0)
        pattern_dir = 1 if pattern_bias > 0 else (-1 if pattern_bias < 0 else 0)
        pattern_quality = min(abs(pattern_bias) / 2.0, 1.0) if pattern_dir else 0.0
        if patterns:
            reasons.append("Patterns: " + ", ".join(p for p, _ in patterns))

        recent_vols = volumes[-20:] if len(volumes) >= 20 else volumes
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
        current_vol = volumes[-1] if volumes else 0
        vol_ratio = (current_vol / avg_vol) if avg_vol > 0 else None
        volume_dir, volume_quality = 0, 0.0
        if vol_ratio is not None and vol_ratio >= 1.05:
            volume_dir = 1 if candle_bull else -1
            volume_quality = min((vol_ratio - 1.0) / 0.5, 1.0)
            reasons.append(f"Volume {vol_ratio:.2f}x average confirming {'up' if volume_dir > 0 else 'down'} move")

        # ---------------- weighted directional vote --------------------
        W = ProOTCEngine.WEIGHTS
        components = [
            ("trend", trend_dir, W["trend"] * (trend_score_raw / 100.0)),
            ("momentum", momentum_dir, W["momentum"] * (momentum_score_raw / 100.0)),
            ("mtf", mtf_dir, W["mtf"] * mtf_quality),
            ("liquidity", liquidity_dir, W["liquidity"] * liquidity_quality),
            ("order_block", ob_dir, W["order_block"] * (1.0 if ob_dir else 0.0)),
            ("fvg", fvg_dir, W["fvg"] * (1.0 if fvg_dir else 0.0)),
            ("pattern", pattern_dir, W["pattern"] * pattern_quality),
            ("volume", volume_dir, W["volume"] * volume_quality),
        ]

        pos = sum(w for _, d, w in components if d > 0)
        neg = sum(w for _, d, w in components if d < 0)
        total_directional = pos + neg
        # Only components that actually produced a reading count toward the
        # denominator, so a missing order block lowers the ceiling instead of
        # silently making a good signal unreachable.
        available_weight = sum(W[name] for name, d, _ in components if d != 0)

        overall_dir = 0
        dominance = 0.0
        if total_directional > 0:
            overall_dir = 1 if pos > neg else (-1 if neg > pos else 0)
            dominance = max(pos, neg) / total_directional

        if overall_dir == 0:
            vetoes.append("No directional edge — bullish and bearish weight are balanced")
        elif dominance < preset["dominance"]:
            vetoes.append(
                f"Direction not dominant enough: {dominance*100:.0f}% of weight "
                f"(need >= {preset['dominance']*100:.0f}%) — up {pos:.1f} vs down {neg:.1f}"
            )
        else:
            reasons.insert(0, (
                f"Confluence {'UP' if overall_dir > 0 else 'DOWN'}: {dominance*100:.0f}% of directional weight "
                f"(up {pos:.1f} / down {neg:.1f})"
            ))

        if preset["mtf_conflict"] and mtf_dir != 0 and overall_dir != 0 and mtf_dir != overall_dir:
            vetoes.append("Multi-timeframe majority conflicts with the signal direction")

        if preset["fake_bo_veto"] and fake_breakout_against and overall_dir == trend_dir:
            vetoes.append("Fake breakout detected against the signal direction")

        if smc_hits < preset["require_smc"]:
            vetoes.append(
                f"Smart-money confirmation: {smc_hits} of {preset['require_smc']} required "
                f"(missing {', '.join(missing) or 'n/a'})"
            )

        # ---------------- score ----------------------------------------
        score_breakdown = {name: 0 for name, _, _ in components}
        ai_score = 0.0
        if overall_dir != 0:
            for name, d, w in components:
                score_breakdown[name] = round(w) if d == overall_dir else 0
            aligned = sum(w for _, d, w in components if d == overall_dir)
            opposed = sum(w for _, d, w in components if d != 0 and d != overall_dir)
            if available_weight > 0:
                ai_score = 100.0 * max(0.0, aligned - opposed) / available_weight
            ai_score *= self_learning_multiplier
            ai_score = max(0.0, min(ai_score, ProOTCEngine.AI_SCORE_MAX))
            if ai_score < min_ai_score:
                vetoes.append(f"Score {ai_score:.1f} < {min_ai_score:.1f} minimum required")

        confidence = round(min(ai_score / ProOTCEngine.AI_SCORE_MAX * 100, 100)) if overall_dir != 0 else 0

        if vetoes:
            direction, confidence, quality = "WAIT", 0, "WAIT"
            reasons = vetoes + reasons
        else:
            direction = "BUY" if overall_dir > 0 else "SELL"
            midpoint = min_ai_score + (ProOTCEngine.AI_SCORE_MAX - min_ai_score) / 2
            quality = "EXCELLENT" if ai_score >= midpoint else "GOOD"

        label = {"BUY": "CALL / UP", "SELL": "PUT / DOWN", "WAIT": "No clear edge"}[direction]

        return {
            "direction": direction, "label": label, "confidence": confidence, "quality": quality,
            "reasons": reasons, "seconds_to_entry": ProOTCEngine._seconds_to_entry(tracker),
            "ai_score": round(ai_score, 1), "ai_score_max": ProOTCEngine.AI_SCORE_MAX, "min_ai_score": min_ai_score,
            "score_breakdown": score_breakdown, "regime": regime, "mtf_status": mtf_status,
            "adx": round(adx_val, 1) if adx_val is not None else None,
            "atr_pct": round(atr_pct, 3) if atr_pct is not None else None,
            "self_learning_multiplier": round(self_learning_multiplier, 2),
            "strictness": (strictness or ProOTCEngine.STRICTNESS_DEFAULT).upper(),
            "dominance": round(dominance, 3),
            "missing": missing,
        }

    @staticmethod
    def _seconds_to_entry(tracker):
        if not tracker.candle_keys:
            return None
        bucket_end = tracker.candle_keys[-1] + 60
        return max(0, int(bucket_end - time.time()))


class TradeConfig:
    def __init__(self):
        self.execution_mode = "OFF"
        self.sizing_mode = "FIXED"
        self.base_amount = 1.0
        self.risk_percent = 1.0
        self.kelly_payout_pct = 85.0
        self.kelly_fraction_cap = 0.05
        self.min_confidence = 65
        self.money_mgmt_mode = "FLAT"
        self.stake_multiplier = 2.0
        self.max_stake_steps = 3
        self.daily_stop_loss = 20.0
        self.daily_take_profit = 20.0
        self.max_daily_trades = 60
        self.max_consecutive_losses = 4
        self.duration = 60
        # Frequency comes from breadth: several assets open at once, one
        # position per asset. This raises trade count WITHOUT lowering the
        # score threshold.
        self.max_concurrent_trades = 3

        self.engine = "TREND_CANDLES"

        self.power_threshold = 60.0
        self.fib_buffer_pct = 0.05
        self.require_strong_trend = False
        self.strict_confluence = False
        self.strict_power_margin = 10.0
        self.strict_fib_multiplier = 2.0

        self.min_session_weight = 0.4
        self.streak_continuation_max = 3

        self.pro_adx_threshold = 18.0
        self.pro_atr_min_pct = 0.005
        self.pro_atr_max_pct = 3.00
        # None => use the strictness preset's own threshold.
        self.pro_min_ai_score = None
        self.pro_strictness = "BALANCED"
        self.self_learning_enabled = True


def build_default_trade_config():
    config = TradeConfig()
    config.execution_mode = "PAPER"
    config.engine = "TREND_CANDLES"
    config.sizing_mode = "FIXED"
    config.base_amount = 1.0
    config.min_confidence = 65
    config.duration = 60
    config.power_threshold = 60.0
    config.fib_buffer_pct = 0.05
    config.require_strong_trend = False
    config.strict_confluence = True
    config.strict_power_margin = 10.0
    config.strict_fib_multiplier = 2.0
    config.money_mgmt_mode = "FLAT"
    config.daily_stop_loss = 20.0
    config.daily_take_profit = 20.0
    config.max_daily_trades = 20
    config.max_consecutive_losses = 4
    return config


class TradeJournal:
    def __init__(self):
        self.records = []

    def record(self, asset, direction, amount, duration, confidence, indicators, won, profit, opened_at, votes=None):
        self.records.append({
            "time": datetime.fromtimestamp(opened_at).strftime("%Y-%m-%d %H:%M:%S"),
            "hour": datetime.fromtimestamp(opened_at).hour,
            "weekday": datetime.fromtimestamp(opened_at).weekday(),
            "asset": asset,
            "direction": direction,
            "amount": amount,
            "duration": duration,
            "confidence": confidence,
            "votes": votes or {},
            "indicators": indicators,
            "result": "WIN" if won else "LOSS",
            "profit": profit,
        })

    def stats(self):
        recs = self.records
        n = len(recs)
        if n == 0:
            return {
                "trades": 0, "win_rate": 0, "total_pnl": 0.0, "wins": 0, "losses": 0,
                "best_pair": None, "worst_pair": None, "best_hour": None,
                "max_win_streak": 0, "max_loss_streak": 0, "profit_factor": None,
            }

        wins = sum(1 for r in recs if r["result"] == "WIN")
        losses = n - wins
        total_pnl = sum(r["profit"] for r in recs)
        gross_profit = sum(r["profit"] for r in recs if r["profit"] > 0)
        gross_loss = abs(sum(r["profit"] for r in recs if r["profit"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        per_pair = defaultdict(float)
        for r in recs:
            per_pair[r["asset"]] += r["profit"]
        best_pair = max(per_pair.items(), key=lambda kv: kv[1]) if per_pair else None
        worst_pair = min(per_pair.items(), key=lambda kv: kv[1]) if per_pair else None

        per_hour = defaultdict(float)
        for r in recs:
            per_hour[r["hour"]] += r["profit"]
        best_hour = max(per_hour.items(), key=lambda kv: kv[1]) if per_hour else None

        max_win_streak = max_loss_streak = cur_win = cur_loss = 0
        for r in recs:
            if r["result"] == "WIN":
                cur_win += 1
                cur_loss = 0
            else:
                cur_loss += 1
                cur_win = 0
            max_win_streak = max(max_win_streak, cur_win)
            max_loss_streak = max(max_loss_streak, cur_loss)

        return {
            "trades": n, "win_rate": round(wins / n * 100, 1), "total_pnl": round(total_pnl, 2),
            "wins": wins, "losses": losses,
            "best_pair": best_pair, "worst_pair": worst_pair, "best_hour": best_hour,
            "max_win_streak": max_win_streak, "max_loss_streak": max_loss_streak,
            "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        }


class TradeManager:
    def __init__(self, config: TradeConfig):
        self.config = config
        self.session_pnl = 0.0
        self.halted = False
        self.halt_reason = ""
        self.open_assets = set()
        self.steps = defaultdict(int)
        self.trade_count = 0
        self.consecutive_losses = 0
        self.journal = TradeJournal()
        self.pending_lock = None

    def is_active(self):
        return self.config.execution_mode != "OFF" and not self.halted

    def has_open_trade(self):
        return bool(self.open_assets)

    def open_slots(self):
        cap = max(1, int(getattr(self.config, "max_concurrent_trades", 1)))
        remaining_today = max(0, self.config.max_daily_trades - self.trade_count)
        return max(0, min(cap - len(self.open_assets), remaining_today))

    def is_asset_open(self, asset):
        return asset in self.open_assets

    def get_next_stake(self, asset, balance=None, signal_confidence=None):
        if self.config.sizing_mode == "KELLY" and balance:
            base = self._kelly_stake(balance)
        elif self.config.sizing_mode == "PERCENT_RISK" and balance:
            base = balance * (self.config.risk_percent / 100)
        else:
            base = self.config.base_amount

        if self.config.money_mgmt_mode == "FLAT":
            return round(base, 2)

        step = min(self.steps[asset], self.config.max_stake_steps)

        if self.config.money_mgmt_mode == "ADAPTIVE":
            conf = signal_confidence if signal_confidence is not None else 50
            eff_mult = self.config.stake_multiplier * (0.6 + (conf / 100) * 0.8)
            eff_mult = min(eff_mult, self.config.stake_multiplier * 2.0)
            return round(base * (eff_mult ** step), 2)

        return round(base * (self.config.stake_multiplier ** step), 2)

    def _kelly_stake(self, balance):
        stats = self.journal.stats()
        if stats["trades"] < 20:
            return self.config.base_amount
        win_rate = stats["win_rate"] / 100
        payout_ratio = self.config.kelly_payout_pct / 100
        if payout_ratio <= 0:
            return self.config.base_amount
        kelly_f = win_rate - (1 - win_rate) / payout_ratio
        kelly_f = max(0.0, min(kelly_f, self.config.kelly_fraction_cap))
        stake = balance * kelly_f
        return stake if stake > 0 else self.config.base_amount

    def mark_open(self, asset):
        self.open_assets.add(asset)

    def mark_closed(self, asset):
        self.open_assets.discard(asset)

    def record_result(self, asset, direction, amount, confidence, indicators, won, profit, opened_at, votes=None):
        self.open_assets.discard(asset)
        self.session_pnl += profit
        self.trade_count += 1
        self.journal.record(asset, direction, amount, self.config.duration, confidence,
                             indicators, won, profit, opened_at, votes=votes)

        mode = self.config.money_mgmt_mode
        if mode in ("MARTINGALE", "ADAPTIVE"):
            if won:
                self.steps[asset] = 0
                self.pending_lock = None
            elif self.steps[asset] < self.config.max_stake_steps:
                self.steps[asset] += 1
                self.pending_lock = {"asset": asset, "direction": direction}
            else:
                self.steps[asset] = 0
                self.pending_lock = None
        elif mode == "ANTI_MARTINGALE":
            if won and self.steps[asset] < self.config.max_stake_steps:
                self.steps[asset] += 1
                self.pending_lock = {"asset": asset, "direction": direction}
            else:
                self.steps[asset] = 0
                self.pending_lock = None
        else:
            self.steps[asset] = 0
            self.pending_lock = None

        self.consecutive_losses = 0 if won else self.consecutive_losses + 1

        if self.session_pnl <= -abs(self.config.daily_stop_loss):
            self.halted = True
            self.halt_reason = f"daily stop-loss reached ({self.session_pnl:+.2f})"
        elif self.session_pnl >= abs(self.config.daily_take_profit):
            self.halted = True
            self.halt_reason = f"daily take-profit reached ({self.session_pnl:+.2f})"
        elif self.consecutive_losses >= self.config.max_consecutive_losses:
            self.halted = True
            self.halt_reason = f"{self.consecutive_losses} consecutive losses (max {self.config.max_consecutive_losses})"
        elif self.trade_count >= self.config.max_daily_trades:
            self.halted = True
            self.halt_reason = f"max daily trades reached ({self.trade_count})"

def setup_trade_config(console, use_defaults=False):
    if use_defaults:
        config = build_default_trade_config()
        console.print(Panel(
            "Using default settings: PAPER mode, TREND_CANDLES engine, "
            "STRICT confluence gating ON, $1 fixed stake, 65% min confidence, "
            "60s trades, flat sizing, $20 stop-loss/take-profit, 20 trades/"
            "4 losses max.",
            title="USING DEFAULT SETTINGS", border_style="green"
        ))
        return config

    console.print(Panel(
        Text.from_markup(
            "Three signal engines are available:\n\n"
            "[bold]TREND CANDLES[/] — power + fast EMA/swing trend + "
            "Fibonacci levels, 4-candle window, optional STRICT mode.\n\n"
            "[bold]SESSION PATTERN[/] — candlestick patterns + streak, "
            "weighted by an hourly (UTC) session-strength table.\n\n"
            "[bold]PRO OTC[/] — Smart Money Concepts (retest/mitigation "
            "required, strengthened Liquidity Engine: sweep + stop-hunt + "
            "institutional trap), 5-timeframe unanimous MTF gate, trend/"
            "momentum/volatility engines, candle-quality rejection, pattern "
            "detection, weighted 110-point AI Score gated at >=95 by "
            "default. All periods rescaled short (ADX/ATR period 7, MACD "
            "5/10/4, etc.) so it needs only ~20 candles instead of 60+ — "
            "shorter windows react faster but are noisier.\n\n"
            "Only ONE trade is ever open at a time. None of this guarantees "
            "correctness or is a proven edge — test in PAPER/PRACTICE first."
        ),
        title="AUTO-TRADE SETUP", border_style="yellow"
    ))

    mode = Prompt.ask("Execution mode", choices=["off", "paper", "live"], default="off").upper()

    config = TradeConfig()
    config.execution_mode = mode
    if mode == "OFF":
        console.print("[dim]Auto-trading disabled — dashboard will only display signals.[/]")
        return config

    engine_choice = Prompt.ask(
        "Signal engine", choices=["trend_candles", "session_pattern", "pro_otc"], default="trend_candles"
    )
    config.engine = engine_choice.upper()

    sizing = Prompt.ask("Position sizing", choices=["fixed", "percent_risk", "kelly"], default="fixed")
    if sizing == "percent_risk":
        config.sizing_mode = "PERCENT_RISK"
        config.risk_percent = FloatPrompt.ask("Risk per trade as % of current balance", default=1.0)
        config.risk_percent = max(0.1, min(10.0, config.risk_percent))
    elif sizing == "kelly":
        config.sizing_mode = "KELLY"
        config.base_amount = FloatPrompt.ask("Base trade amount ($)", default=1.0)
        config.kelly_payout_pct = FloatPrompt.ask("Assumed payout % (for the Kelly formula)", default=85.0)
    else:
        config.sizing_mode = "FIXED"
        config.base_amount = FloatPrompt.ask("Base trade amount per entry ($)", default=1.0)

    config.min_confidence = IntPrompt.ask("Minimum signal confidence to auto-enter (0-100)", default=65)
    config.min_confidence = max(0, min(100, config.min_confidence))
    config.duration = IntPrompt.ask("Trade duration in seconds", default=60)

    if config.engine == "TREND_CANDLES":
        config.power_threshold = FloatPrompt.ask("Power threshold % (need >= this on one side)", default=60.0)
        config.fib_buffer_pct = FloatPrompt.ask("Fibonacci level buffer % (too close = veto)", default=0.05)
        config.require_strong_trend = Confirm.ask("Require STRONG trend only?", default=False)
        config.strict_confluence = Confirm.ask("Enable STRICT confluence mode?", default=True)
        if config.strict_confluence:
            config.strict_power_margin = FloatPrompt.ask("Strict power margin (pp above threshold)", default=10.0)
            config.strict_fib_multiplier = FloatPrompt.ask("Strict Fibonacci clearance multiplier", default=2.0)

    elif config.engine == "SESSION_PATTERN":
        config.min_session_weight = FloatPrompt.ask("Minimum session weight (0.0-1.0)", default=0.4)
        config.min_session_weight = max(0.0, min(1.0, config.min_session_weight))
        config.streak_continuation_max = IntPrompt.ask("Streak continuation max (candles)", default=3)

    else:
        console.print(
            "[dim]Strictness presets (measured on 600 simulated sessions):\n"
            "  strict     ~1% of candles produce a signal — needs a smart-money confirmation\n"
            "  balanced   ~5% of candles — recommended starting point\n"
            "  aggressive ~20% of candles — many more entries, no evidence of a better win rate[/]"
        )
        mode = Prompt.ask("PRO_OTC strictness", choices=["strict", "balanced", "aggressive"], default="balanced")
        config.pro_strictness = mode.upper()
        preset = ProOTCEngine.STRICTNESS_PRESETS[config.pro_strictness]
        config.pro_adx_threshold = FloatPrompt.ask("ADX threshold", default=18.0)
        config.pro_atr_min_pct = FloatPrompt.ask("ATR minimum %", default=0.005)
        config.pro_atr_max_pct = FloatPrompt.ask("ATR maximum %", default=3.00)
        if Confirm.ask(f"Override the preset's minimum score ({preset['min_score']:.0f}/100)?", default=False):
            config.pro_min_ai_score = FloatPrompt.ask("Minimum score (0-100)", default=preset["min_score"])
            config.pro_min_ai_score = max(0.0, min(100.0, config.pro_min_ai_score))
        else:
            config.pro_min_ai_score = None
        config.self_learning_enabled = Confirm.ask("Enable self-learning score adjustment?", default=True)

        # The auto-trade loop applies min_confidence as a SECOND gate on top of
        # the engine's own score threshold. If it sits higher, every signal the
        # engine releases gets silently dropped again.
        effective_min = config.pro_min_ai_score if config.pro_min_ai_score is not None else preset["min_score"]
        if config.min_confidence > effective_min:
            console.print(
                f"[yellow]Note:[/] minimum confidence {config.min_confidence}% is above the engine's "
                f"score threshold ({effective_min:.0f}); lowering it to {int(effective_min)}% so "
                f"qualifying signals are not dropped twice."
            )
            config.min_confidence = int(effective_min)

    mgmt = Prompt.ask("Money-management mode", choices=["flat", "martingale", "anti_martingale", "adaptive"], default="flat")
    config.money_mgmt_mode = mgmt.upper()
    if config.money_mgmt_mode in ("MARTINGALE", "ANTI_MARTINGALE", "ADAPTIVE"):
        label = "after a win" if config.money_mgmt_mode == "ANTI_MARTINGALE" else "after a loss (base)"
        config.stake_multiplier = FloatPrompt.ask(f"Stake multiplier {label}", default=2.0)
        requested_steps = IntPrompt.ask("Max consecutive escalation steps (hard safety ceiling: 5)", default=3)
        config.max_stake_steps = max(0, min(5, requested_steps))
        if requested_steps > 5:
            console.print("[yellow]Capped at 5 steps for account-safety reasons.[/]")

    config.daily_stop_loss = abs(FloatPrompt.ask("Daily stop-loss ($)", default=20.0))
    config.daily_take_profit = abs(FloatPrompt.ask("Daily take-profit ($)", default=20.0))
    config.max_daily_trades = IntPrompt.ask("Max trades per session", default=60)
    config.max_concurrent_trades = IntPrompt.ask(
        "Max positions open at the same time (different assets)", default=3
    )
    config.max_concurrent_trades = max(1, min(10, config.max_concurrent_trades))
    config.max_consecutive_losses = IntPrompt.ask("Max consecutive losses before halting", default=4)

    if mode == "LIVE":
        console.print(Panel(
            "You are about to let this bot place REAL trades automatically with no "
            "per-trade confirmation.",
            title="LIVE MODE WARNING", border_style="bold red"
        ))
        confirm_text = Prompt.ask("Type CONFIRM to proceed with LIVE auto-trading")
        if confirm_text.strip().upper() != "CONFIRM":
            console.print(Panel(
                "You did NOT type CONFIRM, so this session will run in PAPER mode instead.",
                title="LIVE NOT CONFIRMED — FALLING BACK TO PAPER", border_style="bold yellow"
            ))
            _log_to_file("LIVE mode was NOT confirmed at setup — falling back to PAPER mode.")
            input("Press Enter to acknowledge and continue in PAPER mode...")
            config.execution_mode = "PAPER"

    return config


class NotificationConfig:
    def __init__(self):
        self.telegram_enabled = False
        self.telegram_bot_token = None
        self.telegram_chat_id = None
        self.discord_enabled = False
        self.discord_webhook_url = None
        self.email_enabled = False
        self.smtp_host = None
        self.smtp_port = 465
        self.smtp_user = None
        self.smtp_password = None
        self.email_to = None
        self.min_confidence = 75


class NotificationManager:
    def __init__(self, config: NotificationConfig, log_fn=None):
        self.config = config
        self.log_fn = log_fn or (lambda msg: None)

    def _log(self, msg):
        self.log_fn(msg)

    async def notify_signal(self, asset, sig):
        cfg = self.config
        if sig["confidence"] < cfg.min_confidence:
            return
        text = (
            f"{format_asset_name(asset)} — {sig['direction']} ({sig['label']})\n"
            f"Confidence: {sig['confidence']}%\n"
            f"Reasons: {', '.join(sig['reasons'][:4])}"
        )
        tasks = []
        if cfg.telegram_enabled:
            tasks.append(asyncio.to_thread(self._send_telegram, text))
        if cfg.discord_enabled:
            tasks.append(asyncio.to_thread(self._send_discord, text))
        if cfg.email_enabled:
            tasks.append(asyncio.to_thread(self._send_email, asset, sig, text))
        for t in tasks:
            try:
                await t
            except Exception as e:
                self._log(f"[dim]Notification error: {e}[/]")

    def _send_telegram(self, text):
        cfg = self.config
        url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
        data = json.dumps({"chat_id": cfg.telegram_chat_id, "text": text}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.URLError as e:
            self._log(f"[dim]Telegram notification failed: {e}[/]")

    def _send_discord(self, text):
        cfg = self.config
        data = json.dumps({"content": text}).encode()
        req = urllib.request.Request(cfg.discord_webhook_url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.URLError as e:
            self._log(f"[dim]Discord notification failed: {e}[/]")

    def _send_email(self, asset, sig, text):
        cfg = self.config
        msg = EmailMessage()
        msg["Subject"] = f"Signal: {format_asset_name(asset)} {sig['direction']} ({sig['confidence']}%)"
        msg["From"] = cfg.smtp_user
        msg["To"] = cfg.email_to
        msg.set_content(text)
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context, timeout=10) as server:
                server.login(cfg.smtp_user, cfg.smtp_password)
                server.send_message(msg)
        except Exception as e:
            self._log(f"[dim]Email notification failed: {e}[/]")


def setup_notification_config(console):
    config = NotificationConfig()
    if not Confirm.ask("Set up alerts for new signals (Telegram/Discord/Email)?", default=False):
        return config

    config.min_confidence = IntPrompt.ask("Minimum confidence to send an alert (0-100)", default=75)

    if Confirm.ask("Enable Telegram alerts?", default=False):
        config.telegram_enabled = True
        config.telegram_bot_token = Prompt.ask("Telegram bot token")
        config.telegram_chat_id = Prompt.ask("Telegram chat ID")

    if Confirm.ask("Enable Discord alerts?", default=False):
        config.discord_enabled = True
        config.discord_webhook_url = Prompt.ask("Discord webhook URL")

    if Confirm.ask("Enable Email alerts?", default=False):
        config.email_enabled = True
        config.smtp_host = Prompt.ask("SMTP host (e.g. smtp.gmail.com)")
        config.smtp_port = IntPrompt.ask("SMTP port (SSL)", default=465)
        config.smtp_user = Prompt.ask("SMTP username / from-address")
        config.smtp_password = getpass.getpass("SMTP password (hidden): ")
        config.email_to = Prompt.ask("Send alerts to")

    return config


class CandleTracker:
    def __init__(self):
        self.candles = {}
        self.candle_keys = deque(maxlen=200)
        self.latest_depth_value = 0
        self.tick_history = deque(maxlen=4000)

    def pre_populate(self, history_candles):
        if not history_candles:
            return
        for candle in history_candles:
            ts = int(candle.get("time"))
            bucket = (ts // 60) * 60
            self.candles[bucket] = {
                "timestamp": bucket,
                "open": float(candle.get("open")),
                "high": float(candle.get("high")),
                "low": float(candle.get("low")),
                "close": float(candle.get("close")),
                "ticks": 0,
                "depth_values": [],
                "is_closed": True
            }
            if bucket not in self.candle_keys:
                self.candle_keys.append(bucket)

    def handle_tick(self, timestamp, price):
        self.tick_history.append((float(timestamp), float(price)))
        bucket = (int(timestamp) // 60) * 60

        if bucket not in self.candles:
            if self.candle_keys:
                prev_bucket = self.candle_keys[-1]
                if prev_bucket in self.candles:
                    self.candles[prev_bucket]["is_closed"] = True

            self.candles[bucket] = {
                "timestamp": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "ticks": 0,
                "depth_values": [self.latest_depth_value] if self.latest_depth_value > 0 else [],
                "is_closed": False
            }
            self.candle_keys.append(bucket)

        c = self.candles[bucket]
        c["ticks"] += 1
        c["close"] = price
        if price > c["high"]:
            c["high"] = price
        if price < c["low"]:
            c["low"] = price

    def handle_depth(self, order_count, server_timestamp=None):
        self.latest_depth_value = order_count
        ts = server_timestamp if server_timestamp else time.time()
        bucket = (int(ts) // 60) * 60

        if bucket in self.candles:
            self.candles[bucket]["depth_values"].append(order_count)
        elif self.candle_keys:
            latest_bucket = self.candle_keys[-1]
            self.candles[latest_bucket]["depth_values"].append(order_count)

class DashboardApp:
    def __init__(self, asset, account_type, max_rows=15, trade_manager=None, email=None, password=None,
                 notifier=None):
        self.asset = asset.upper()
        self.account_type = account_type
        self.max_rows = max_rows
        self.client = None
        self.tracker = None
        self.trackers = defaultdict(CandleTracker)
        self.payouts = {}
        self.categories = {}
        self.trade_manager = trade_manager or TradeManager(TradeConfig())
        self._auto_trade_task = None
        self.notifier = notifier
        self._last_notified_direction = {}
        self.email = email
        self.password = password

        self.logs = deque(maxlen=6)
        self.start_time = time.time()
        self.status = "Initializing..."
        self.balance_str = "0.00"
        self.active_assets = []
        self.last_tick_direction = {}

        self.price_read_offset = defaultdict(int)
        self.last_price = {}

        self.signals = {}
        self.asset_rank = {}

        self.autotrade_last_check = "not started yet"
        self.autotrade_last_check_time = None

    def add_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[dim]{ts}[/] {msg}")
        if "auto-trade" in msg.lower() or "Auto-trade" in msg:
            _log_to_file(f"[dashboard] {msg}")

    async def _refresh_balance(self):
        if not self.client or not self.client.api:
            return
        for method_name in ("get_balance", "get_profile", "update_balance", "refresh_balance"):
            method = getattr(self.client, method_name, None)
            if method is None:
                continue
            try:
                result = method()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.add_log(f"[dim]Balance refresh via {method_name}() failed: {e}[/]")
            break
        if self.client.api and self.client.api.account_balance:
            bal_key = "demoBalance" if self.account_type == "PRACTICE" else "liveBalance"
            new_balance = self.client.api.account_balance.get(bal_key)
            if new_balance is not None:
                self.balance_str = f"{new_balance:,.2f}"

    def poll_realtime_data(self):
        if not self.client or not self.client.api:
            return
        api = self.client.api

        for asset in self.active_assets:
            price_list = api.realtime_price.get(asset)
            if price_list:
                offset = self.price_read_offset[asset]
                new_items = price_list[offset:]
                for item in new_items:
                    ts = item.get("time")
                    price = item.get("price")
                    if ts is None or price is None:
                        continue
                    price = float(price)
                    prev = self.last_price.get(asset)
                    if prev is not None:
                        if price > prev:
                            self.last_tick_direction[asset] = 1
                        elif price < prev:
                            self.last_tick_direction[asset] = -1
                    self.last_price[asset] = price
                    self.trackers[asset].handle_tick(float(ts), price)
                self.price_read_offset[asset] = len(price_list)

                if self.price_read_offset[asset] >= len(price_list) and len(price_list) > 500:
                    price_list.clear()
                    self.price_read_offset[asset] = 0

            sentiment = api.realtime_sentiment.get(asset)
            if sentiment and "sentiment" in sentiment:
                buy_pct = sentiment["sentiment"].get("buy")
                if buy_pct is not None:
                    self.trackers[asset].handle_depth(int(buy_pct))

    def _compute_one_signal(self, asset):
        tm_cfg = self.trade_manager.config
        tracker = self.trackers[asset]

        if tm_cfg.engine == "SESSION_PATTERN":
            return asset, SessionPatternEngine.compute(
                tracker,
                min_session_weight=tm_cfg.min_session_weight,
                streak_continuation_max=tm_cfg.streak_continuation_max,
            )

        if tm_cfg.engine == "PRO_OTC":
            mult = 1.0
            if tm_cfg.self_learning_enabled and tracker.candle_keys:
                last_bucket = tracker.candle_keys[-1]
                hour_utc = datetime.fromtimestamp(last_bucket, timezone.utc).hour
                weekday = datetime.fromtimestamp(last_bucket, timezone.utc).weekday()
                mult = SelfLearningStats.multiplier_for(self.trade_manager.journal, asset, hour_utc, weekday)
            return asset, ProOTCEngine.compute(
                tracker, asset=asset,
                adx_threshold=tm_cfg.pro_adx_threshold,
                atr_min_pct=tm_cfg.pro_atr_min_pct,
                atr_max_pct=tm_cfg.pro_atr_max_pct,
                min_ai_score=tm_cfg.pro_min_ai_score,
                self_learning_multiplier=mult,
                strictness=getattr(tm_cfg, "pro_strictness", "BALANCED"),
            )

        return asset, TrendCandleEngine.compute(
            tracker,
            power_threshold=tm_cfg.power_threshold,
            fib_buffer_pct=tm_cfg.fib_buffer_pct,
            require_strong_trend=tm_cfg.require_strong_trend,
            strict_confluence=tm_cfg.strict_confluence,
            strict_power_margin=tm_cfg.strict_power_margin,
            strict_fib_multiplier=tm_cfg.strict_fib_multiplier,
        )

    async def update_signals(self):
        if not self.active_assets:
            return
        results = await asyncio.gather(
            *(asyncio.to_thread(self._compute_one_signal, asset) for asset in self.active_assets)
        )
        for asset, sig in results:
            self.signals[asset] = sig
            if self.notifier and sig["direction"] != "WAIT":
                if self._last_notified_direction.get(asset) != sig["direction"]:
                    self._last_notified_direction[asset] = sig["direction"]
                    asyncio.create_task(self.notifier.notify_signal(asset, sig))
            elif sig["direction"] == "WAIT":
                self._last_notified_direction.pop(asset, None)

        if self.trade_manager.config.engine == "PRO_OTC":
            ranked = sorted(self.signals.items(), key=lambda kv: kv[1].get("confidence", 0), reverse=True)
            self.asset_rank = {a: i + 1 for i, (a, _) in enumerate(ranked)}

    def _get_server_time(self):
        if self.client and self.client.api and self.client.api.timesync.server_timestamp:
            return float(self.client.api.timesync.server_timestamp)
        return time.time()

    async def auto_trade_loop(self):
        if self.trade_manager.config.execution_mode == "OFF":
            return

        try:
            await self.update_signals()
            await self.fire_entries(dict(self.signals))
        except Exception as e:
            self.add_log(f"[bold red]Auto-trade startup check error:[/] {e}")

        while True:
            try:
                loop_start_mono = time.monotonic()

                now_local = time.time()
                next_boundary = (int(now_local // 60) + 1) * 60

                wait_seconds = max(0.0, min(next_boundary - now_local, 65.0))
                if wait_seconds > 1.0:
                    await asyncio.sleep(wait_seconds - 1.0)

                freeze_target = next_boundary - 0.3
                freeze_deadline_mono = time.monotonic() + 2.0
                while True:
                    remaining = freeze_target - time.time()
                    if remaining <= 0 or time.monotonic() >= freeze_deadline_mono:
                        break
                    await asyncio.sleep(min(remaining, 0.005))

                await self.update_signals()
                frozen_signals = dict(self.signals)

                fire_deadline_mono = time.monotonic() + 2.0
                while True:
                    remaining = next_boundary - time.time()
                    if remaining <= 0 or time.monotonic() >= fire_deadline_mono:
                        break
                    await asyncio.sleep(min(remaining, 0.001))

                entry_call_time = time.time()
                timing_offset_ms = (entry_call_time - next_boundary) * 1000
                await self.fire_entries(frozen_signals, timing_offset_ms=timing_offset_ms)

                elapsed = time.monotonic() - loop_start_mono
                if elapsed > 90:
                    self.add_log(
                        f"[bold yellow]Auto-trade loop iteration took {elapsed:.0f}s "
                        f"(expected ~60s) — check connection stability.[/]"
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.add_log(f"[bold red]Auto-trade scheduler error:[/] {e}")
                await asyncio.sleep(2)

    async def fire_entries(self, frozen_signals=None, timing_offset_ms=None):
        tm = self.trade_manager
        self.autotrade_last_check_time = time.time()
        self.add_log(f"[dim]Auto-trade tick: evaluating {len(self.active_assets)} asset(s)...[/]")
        if not tm.is_active():
            reason = tm.halt_reason if tm.halted else f"mode={tm.config.execution_mode}"
            self.autotrade_last_check = f"skipped — not active ({reason})"
            self.add_log(f"[yellow]Auto-trade tick skipped — not active ({reason}).[/]")
            return
        slots = tm.open_slots()
        if slots <= 0:
            cap = getattr(tm.config, "max_concurrent_trades", 1)
            self.autotrade_last_check = f"skipped — {len(tm.open_assets)}/{cap} positions already open"
            self.add_log(
                f"[dim]Auto-trade tick skipped — {len(tm.open_assets)}/{cap} concurrent positions open "
                f"({tm.trade_count}/{tm.config.max_daily_trades} trades today).[/]"
            )
            return

        if frozen_signals is not None:
            signals = frozen_signals
        else:
            await self.update_signals()
            signals = self.signals

        timing_note = f" | entry offset {timing_offset_ms:+.1f}ms" if timing_offset_ms is not None else ""

        if tm.pending_lock is not None:
            locked_asset = tm.pending_lock["asset"]
            locked_direction = tm.pending_lock["direction"]
            locked_sig = signals.get(locked_asset)
            still_valid = (
                locked_sig is not None
                and locked_sig["direction"] == locked_direction
                and locked_sig["confidence"] >= tm.config.min_confidence
            )
            if still_valid:
                asset, sig = locked_asset, locked_sig
                direction = "call" if sig["direction"] == "BUY" else "put"
                balance = float(self.balance_str.replace(",", "")) if self.balance_str else None
                amount = tm.get_next_stake(asset, balance=balance, signal_confidence=sig["confidence"])
                self.autotrade_last_check = (
                    f"FIRING (martingale continuation) {format_asset_name(asset)} {direction.upper()} "
                    f"${amount:.2f} (conf {sig['confidence']}%){timing_note}"
                )
                self.add_log(f"[dim]  Martingale lock: continuing {format_asset_name(asset)} {direction.upper()}[/]")
                if timing_offset_ms is not None:
                    self.add_log(
                        f"[dim]  Entry call offset: {timing_offset_ms:+.1f}ms from candle boundary "
                        f"(local clock only; actual broker fill time depends on network latency)[/]"
                    )
                tm.mark_open(asset)
                asyncio.create_task(self.execute_trade(asset, direction, amount, sig["confidence"],
                                                         sig.get("indicators", {}), sig.get("votes", {})))
                return
            else:
                self.add_log(
                    f"[dim]  Martingale lock dropped — {format_asset_name(locked_asset)} "
                    f"{locked_direction.upper()} no longer qualifies, resetting escalation.[/]"
                )
                tm.steps[locked_asset] = 0
                tm.pending_lock = None

        candidates = []
        rejection_examples = []
        for asset in self.active_assets:
            sig = signals.get(asset)
            if not sig:
                continue
            if tm.is_asset_open(asset):
                continue
            if sig["direction"] == "WAIT":
                if sig["reasons"] and len(rejection_examples) < 3:
                    rejection_examples.append(f"{format_asset_name(asset)}: {sig['reasons'][0]}")
                continue
            if sig["confidence"] < tm.config.min_confidence:
                self.add_log(
                    f"[dim]  {format_asset_name(asset)} skipped: score {sig['confidence']}% "
                    f"({sig.get('quality', '?')}) < required {tm.config.min_confidence}%[/]"
                )
                continue
            candidates.append((asset, sig))

        if not candidates:
            self.autotrade_last_check = "no asset qualified this candle"
            if rejection_examples:
                self.add_log("[dim]Auto-trade tick: no asset qualified — " + " | ".join(rejection_examples) + "[/]")
            else:
                self.add_log("[dim]Auto-trade tick: no asset qualified this candle.[/]")
            return

        candidates.sort(key=lambda item: item[1]["confidence"], reverse=True)
        picked = candidates[:slots]
        if len(candidates) > len(picked):
            self.add_log(
                f"[dim]  {len(candidates)} assets qualified, {slots} slot(s) free — "
                f"taking the {len(picked)} strongest.[/]"
            )

        balance = float(self.balance_str.replace(",", "")) if self.balance_str else None
        fired_desc = []
        for asset, sig in picked:
            direction = "call" if sig["direction"] == "BUY" else "put"
            amount = tm.get_next_stake(asset, balance=balance, signal_confidence=sig["confidence"])
            fired_desc.append(f"{format_asset_name(asset)} {direction.upper()} ${amount:.2f} ({sig['confidence']}%)")
            tm.mark_open(asset)
            asyncio.create_task(self.execute_trade(asset, direction, amount, sig["confidence"],
                                                     sig.get("indicators", {}), sig.get("votes", {})))
        self.autotrade_last_check = "FIRING " + " + ".join(fired_desc) + timing_note
        if timing_offset_ms is not None:
            self.add_log(
                f"[dim]  Entry call offset: {timing_offset_ms:+.1f}ms from candle boundary "
                f"(local clock only; actual broker fill time depends on network latency)[/]"
            )

    async def execute_trade(self, asset, direction, amount, confidence, indicators=None, votes=None):
        tm = self.trade_manager
        indicators = indicators or {}
        votes = votes or {}
        label = "CALL/BUY" if direction == "call" else "PUT/SELL"
        dir_color = "green" if direction == "call" else "red"
        opened_at = time.time()

        if tm.config.execution_mode == "PAPER":
            self.add_log(
                f"[cyan]PAPER[/] [{dir_color}]{label}[/] {format_asset_name(asset)} "
                f"${amount:.2f} (conf {confidence}%) — simulated, no real order sent"
            )
            tm.mark_closed(asset)
            return

        try:
            self.add_log(
                f"[bold {dir_color}]ENTER[/] {format_asset_name(asset)} [{dir_color}]{label}[/] "
                f"${amount:.2f} (conf {confidence}%)"
            )
            status, buy_info = await self.client.buy(amount, asset, direction, tm.config.duration)
            if not status:
                self.add_log(f"[bold red]Order rejected[/] {format_asset_name(asset)}: {buy_info}")
                tm.mark_closed(asset)
                return

            order_id = buy_info.get("id") if isinstance(buy_info, dict) else buy_info

            try:
                win_status, profit = await asyncio.wait_for(
                    self.client.check_win(order_id), timeout=tm.config.duration + 30
                )
            except asyncio.TimeoutError:
                self.add_log(
                    f"[bold red]check_win timed out[/] {format_asset_name(asset)} "
                    f"(order_id={order_id}) after {tm.config.duration + 30}s — releasing lock. "
                    f"Real result UNKNOWN, not recorded in journal/P&L."
                )
                _log_to_file(
                    f"check_win timeout: asset={asset} order_id={order_id} "
                    f"duration={tm.config.duration}s — outcome not recorded"
                )
                tm.mark_closed(asset)
                return

            won = win_status == "win"
            tm.record_result(asset, direction, amount, confidence, indicators, won, profit, opened_at, votes=votes)
            await self._refresh_balance()

            result_style = "bold green" if won else "bold red"
            self.add_log(
                f"[{result_style}]{'WIN' if won else 'LOSS'}[/] {format_asset_name(asset)} "
                f"→ {profit:+.2f} | session P&L: {tm.session_pnl:+.2f}"
            )
            if tm.halted:
                self.add_log(f"[bold yellow]Auto-trading halted:[/] {tm.halt_reason}")
        except Exception as e:
            self.add_log(f"[bold red]Trade execution error[/] {format_asset_name(asset)}: {e}")
            tm.mark_closed(asset)

    def build_header(self):
        server_time_str = "—"
        if self.client and self.client.api and self.client.api.timesync.server_timestamp:
            server_time_str = datetime.fromtimestamp(
                self.client.api.timesync.server_timestamp, timezone.utc
            ).strftime("%H:%M:%S UTC")

        header_text = Text()
        header_text.append("REALALGO ", style="bold color(208)")
        header_text.append("| ", style="bright_black")
        header_text.append("PAIR: ", style="dim")
        header_text.append(f"{'ALL ACTIVE OTC' if self.asset == 'ALL' else format_asset_name(self.asset)} ", style="bold bright_white")
        header_text.append("| ", style="bright_black")
        header_text.append("MODE: ", style="dim")
        header_text.append(f"{self.account_type} ", style="bold magenta")
        header_text.append("| ", style="bright_black")
        header_text.append("BALANCE: ", style="dim")
        header_text.append(f"${self.balance_str} ", style="bold green")
        header_text.append("| ", style="bright_black")
        header_text.append(f"UPTIME: {int(time.time() - self.start_time)}s ", style="dim")
        header_text.append("| ", style="bright_black")
        header_text.append(f"TIME: {server_time_str}", style="cyan")

        tm = self.trade_manager
        header_text.append("\n")
        mode = tm.config.execution_mode
        mode_style = {"OFF": "dim", "PAPER": "bold cyan", "LIVE": "bold red"}.get(mode, "dim")
        header_text.append("AUTO-TRADE: ", style="dim")
        header_text.append(f"{mode} ", style=mode_style)
        if mode != "OFF":
            header_text.append("| ", style="bright_black")
            header_text.append(f"engine: {tm.config.engine} ", style="dim")
            if tm.config.engine == "TREND_CANDLES":
                header_text.append("| ", style="bright_black")
                strict_label = "ON" if tm.config.strict_confluence else "OFF"
                header_text.append(f"strict: {strict_label} ", style="dim")
            header_text.append("| ", style="bright_black")
            header_text.append(f"min conf: {tm.config.min_confidence}% ", style="dim")
            header_text.append("| ", style="bright_black")
            armed_style = "bold red" if tm.halted else "bold green"
            armed_text = f"HALTED: {tm.halt_reason}" if tm.halted else "ARMED"
            header_text.append(f"{armed_text} ", style=armed_style)
            header_text.append("| ", style="bright_black")
            if self.autotrade_last_check_time:
                ago = int(time.time() - self.autotrade_last_check_time)
                header_text.append(f"last check ({ago}s ago): {self.autotrade_last_check}", style="yellow")
            else:
                header_text.append(f"last check: {self.autotrade_last_check}", style="dim")

        return Panel(header_text, box=box.SIMPLE, border_style="bright_black")

    def build_candles_table(self):
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold bright_white", expand=True)

        table.add_column("Time (1m)", justify="center", style="dim white")
        table.add_column("Open", justify="right")
        table.add_column("High", justify="right", style="dim")
        table.add_column("Low", justify="right", style="dim")
        table.add_column("Close", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Ticks", justify="right", style="magenta")
        table.add_column("Buy % (Live)", justify="right", style="bold yellow")
        table.add_column("1m Range (Min / Max / Avg)", justify="center")
        table.add_column("Buy/Sell Gauge", justify="left")

        tracker = self.trackers[self.asset]
        sorted_keys = sorted(tracker.candles.keys(), reverse=True)
        display_keys = sorted_keys[:self.max_rows]

        for bucket in display_keys:
            c = tracker.candles[bucket]
            time_str = datetime.fromtimestamp(bucket, timezone.utc).strftime("%H:%M")

            close_price = c["close"]
            open_price = c["open"]
            diff = close_price - open_price

            if diff > 0:
                trend_str = "UP"
                trend_style = "bold green"
            elif diff < 0:
                trend_str = "DOWN"
                trend_style = "bold red"
            else:
                trend_str = "FLAT"
                trend_style = "dim white"

            depth_vals = c["depth_values"]
            if depth_vals:
                current_depth = depth_vals[-1]
                min_d = min(depth_vals)
                max_d = max(depth_vals)
                avg_d = sum(depth_vals) / len(depth_vals)
                stats_str = f"{min_d} / {max_d} / {avg_d:.1f}"

                bar_size = min(int(current_depth / 10), 10)
                bar_chars = "#" * bar_size + "." * (10 - bar_size)

                if current_depth > 50:
                    bar_color = "bright_red"
                elif current_depth > 20:
                    bar_color = "bright_yellow"
                else:
                    bar_color = "bright_blue"

                bar_str = f"[{bar_color}]{bar_chars}[/] [dim]({current_depth})[/]"
            else:
                current_depth = "—"
                stats_str = "—"
                bar_str = "[dim]No sentiment data[/]"

            table.add_row(
                time_str, format_price(open_price), format_price(c['high']), format_price(c['low']),
                format_price(close_price), f"[{trend_style}]{trend_str}[/]", str(c["ticks"]),
                str(current_depth), stats_str, bar_str
            )

        return table

    def build_multi_asset_table(self):
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold bright_white", expand=True)

        table.add_column("Asset Pair", justify="left")
        table.add_column("Payout", justify="center", style="yellow")
        table.add_column("Current Price", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("1m Ticks", justify="right", style="magenta")
        table.add_column("Buy % (Live)", justify="right", style="bold yellow")
        table.add_column("1m Range (Min/Max/Avg)", justify="center")
        table.add_column("Buy/Sell Gauge", justify="left")
        table.add_column("Signal", justify="center")

        cat_order = ["Currencies", "Crypto", "Commodities", "Stocks"]
        is_pro_otc = self.trade_manager.config.engine == "PRO_OTC"

        for category in cat_order:
            assets_in_cat = [a for a in self.active_assets if self.categories.get(a, "Stocks") == category]
            assets_in_cat.sort(key=lambda x: self.payouts.get(x, 0), reverse=True)
            assets_in_cat = [a for a in assets_in_cat if self.payouts.get(a, 0) > 0]

            limit = self.max_rows if self.max_rows != 15 else 5
            assets_in_cat = assets_in_cat[:limit]

            if not assets_in_cat:
                continue

            table.add_row(f"[bold color(208)]{category.upper()}[/]", "", "", "", "", "", "", "", "")

            for asset in assets_in_cat:
                tracker = self.trackers[asset]
                payout = self.payouts.get(asset, 0)
                payout_str = f"{payout}%" if payout > 0 else "—"

                c_bucket = tracker.candle_keys[-1] if tracker.candle_keys else None

                price_str = "—"
                trend_str = "FLAT"
                trend_style = "dim white"
                ticks_str = "0"
                current_orders = "—"
                stats_str = "—"
                bar_str = "[dim]Waiting for stream...[/]"

                if c_bucket is not None:
                    c = tracker.candles[c_bucket]
                    close_price = c["close"]
                    open_price = c["open"]
                    diff = close_price - open_price

                    tick_dir = self.last_tick_direction.get(asset, 0)
                    if tick_dir == 1:
                        price_style = "bold green"
                    elif tick_dir == -1:
                        price_style = "bold red"
                    else:
                        price_style = "white"

                    price_str = f"[{price_style}]{format_price(close_price)}[/]"

                    if diff > 0:
                        trend_str = "UP"
                        trend_style = "bold green"
                    elif diff < 0:
                        trend_str = "DOWN"
                        trend_style = "bold red"
                    else:
                        trend_str = "FLAT"
                        trend_style = "dim white"

                    ticks_str = str(c["ticks"])

                    depth_vals = c["depth_values"]
                    if depth_vals:
                        latest_d = depth_vals[-1]
                        current_orders = str(latest_d)
                        min_d = min(depth_vals)
                        max_d = max(depth_vals)
                        avg_d = sum(depth_vals) / len(depth_vals)
                        stats_str = f"{min_d} / {max_d} / {avg_d:.1f}"

                        bar_size = min(int(latest_d / 10), 10)
                        bar_chars = "#" * bar_size + "." * (10 - bar_size)

                        if latest_d > 50:
                            bar_color = "bright_red"
                        elif latest_d > 20:
                            bar_color = "bright_yellow"
                        else:
                            bar_color = "bright_blue"

                        bar_str = f"[{bar_color}]{bar_chars}[/] [dim]({latest_d})[/]"
                    else:
                        bar_str = "[dim]No sentiment data yet[/]"

                sig = self.signals.get(asset)
                if sig and sig["direction"] == "BUY":
                    q = sig.get("quality", "")
                    signal_str = f"[bold green]BUY {sig['confidence']} ({q})[/]"
                elif sig and sig["direction"] == "SELL":
                    q = sig.get("quality", "")
                    signal_str = f"[bold red]SELL {sig['confidence']} ({q})[/]"
                elif sig and sig["direction"] == "WAIT" and sig["confidence"] >= 0 and sig["reasons"] and "Need" not in sig["reasons"][0]:
                    signal_str = "[dim yellow]WAIT[/]"
                else:
                    signal_str = "[dim]...[/]"

                asset_label = format_asset_name(asset)
                if is_pro_otc:
                    rank = self.asset_rank.get(asset)
                    if rank is not None and rank <= 3:
                        asset_label = f"#{rank} {asset_label}"

                table.add_row(
                    f"  {asset_label}", payout_str, price_str, f"[{trend_style}]{trend_str}[/]",
                    ticks_str, current_orders, stats_str, bar_str, signal_str
                )

        return table

    def build_signal_panel(self):
        text = Text()

        if self.asset != "ALL":
            asset, sig = self.asset, self.signals.get(self.asset)
        else:
            candidates = [(a, s) for a, s in self.signals.items() if s and s["direction"] != "WAIT"]
            if candidates:
                asset, sig = max(candidates, key=lambda item: item[1]["confidence"])
            elif self.signals:
                asset, sig = next(iter(self.signals.items()))
            else:
                asset, sig = None, None

        if not sig:
            text.append("Collecting candle history before the first signal is ready...\n", style="dim italic")
            return Panel(text, title="SIGNAL", title_align="left", box=box.SIMPLE, border_style="bright_black")

        direction = sig["direction"]
        if direction == "BUY":
            dir_style, arrow = "bold green", "BUY / CALL"
        elif direction == "SELL":
            dir_style, arrow = "bold red", "SELL / PUT"
        else:
            dir_style, arrow = "bold yellow", "WAIT"

        secs = sig["seconds_to_entry"]
        if secs is None:
            timing_str = "—"
        elif secs <= 2:
            timing_str = "ENTER NOW (candle closing)"
        else:
            timing_str = f"enter in ~{secs}s (at candle close)"

        quality = sig.get("quality", "WAIT")
        quality_label = {"EXCELLENT": "EXCELLENT", "GOOD": "GOOD", "WAIT": "WAIT"}.get(quality, quality)
        quality_style = {"EXCELLENT": "bold green", "GOOD": "bold cyan", "WAIT": "dim yellow"}.get(quality, "dim")

        text.append(f"{format_asset_name(asset)}  ", style="bold bright_white")
        text.append(f"{arrow}  ", style=dir_style)
        text.append(f"confidence: {sig['confidence']}/100 ", style="cyan")
        text.append(Text.from_markup(f"[{quality_style}]{quality_label}[/]  "))
        text.append(f"| {timing_str}\n", style="bold bright_white" if (secs is not None and secs <= 2) else "dim")

        is_session_pattern = "pattern_bias" in sig
        is_pro_otc = "ai_score" in sig

        if is_pro_otc:
            ai_score = sig.get("ai_score", 0)
            ai_max = sig.get("ai_score_max", 100)
            min_score = sig.get("min_ai_score", 66)
            bar_size = round(min(ai_score / ai_max, 1.0) * 10) if ai_max else 0
            bar = "#" * bar_size + "." * (10 - bar_size)
            text.append(f"   {bar}  ", style="")
            text.append(f"AI SCORE {ai_score:.1f}/{ai_max:.0f} (need >= {min_score:.0f})\n", style="bold magenta")
            breakdown = sig.get("score_breakdown") or {}
            if breakdown:
                bstr = " · ".join(f"{k.replace('_',' ').title()} {v}" for k, v in breakdown.items())
                text.append(f"   {bstr}\n", style="dim cyan")
            dom = sig.get("dominance")
            missing = sig.get("missing") or []
            extra_line = f"Mode: {sig.get('strictness', '?')}"
            if dom is not None:
                extra_line += f" | Directional dominance {dom*100:.0f}%"
            if missing:
                extra_line += f" | Not confirming: {', '.join(missing)}"
            text.append(f"   {extra_line}\n", style="dim cyan")
            regime = sig.get("regime", "UNKNOWN")
            adx = sig.get("adx")
            atr_pct = sig.get("atr_pct")
            meta = f"Regime: {regime}"
            if adx is not None:
                meta += f" | ADX {adx}"
            if atr_pct is not None:
                meta += f" | ATR {atr_pct}%"
            text.append(f"   {meta}\n", style="dim")
            mtf = sig.get("mtf_status") or {}
            if mtf:
                mtf_str = ", ".join(f"{k}:{'+' if v > 0 else ('-' if v < 0 else 'o')}" for k, v in mtf.items())
                text.append(f"   MTF: {mtf_str}\n", style="dim")
            rank = self.asset_rank.get(asset)
            if rank is not None:
                text.append(f"   Asset rank: #{rank} of {len(self.asset_rank)} tracked\n", style="dim")
            sl_mult = sig.get("self_learning_multiplier")
            if sl_mult is not None and sl_mult != 1.0:
                text.append(f"   Self-learning adjustment: x{sl_mult}\n", style="dim italic")
        elif is_session_pattern:
            pattern_bias = sig.get("pattern_bias", 0)
            streak_dir = sig.get("streak_dir", 0)
            streak_len = sig.get("streak_len", 0)
            session_weight = sig.get("session_weight")
            hour_utc = sig.get("hour_utc")

            if session_weight is not None:
                bar_size = round(session_weight * 10)
                bar = "#" * bar_size + "." * (10 - bar_size)
                text.append(f"   {bar}  ", style="")
                text.append(f"SESSION {hour_utc:02d}:00 UTC weight {session_weight:.2f}\n", style="bold cyan")
            else:
                text.append("   Session: — (insufficient data)\n", style="dim")

            pattern_str = "bullish" if pattern_bias > 0 else ("bearish" if pattern_bias < 0 else "neutral")
            pattern_style = "bold green" if pattern_bias > 0 else ("bold red" if pattern_bias < 0 else "dim")
            streak_str = f"{streak_len} {'up' if streak_dir > 0 else ('down' if streak_dir < 0 else '—')}"
            text.append(f"   PATTERN {pattern_str} (bias {pattern_bias:+d})  ", style=pattern_style)
            text.append(f"STREAK {streak_str}\n", style="bold magenta")
        else:
            buy_power = sig.get("buy_power")
            sell_power = sig.get("sell_power")
            if buy_power is not None:
                bar_size = round(buy_power / 10)
                bar = "#" * bar_size + "." * (10 - bar_size)
                text.append(f"   {bar}  ", style="")
                text.append(f"BUY POWER {buy_power:.1f}%  ", style="bold green")
                text.append(f"SELL POWER {sell_power:.1f}%\n", style="bold red")
            else:
                text.append("   Power: — (insufficient data)\n", style="dim")

            trend_dir = sig.get("trend", 0)
            trend_quality = sig.get("trend_quality", "none")
            if trend_dir > 0:
                trend_arrow, trend_style_str = "UP", "bold green"
            elif trend_dir < 0:
                trend_arrow, trend_style_str = "DOWN", "bold red"
            else:
                trend_arrow, trend_style_str = "NONE", "dim yellow"
            strict_tag = " [STRICT]" if sig.get("strict_confluence") else ""
            text.append(f"   TREND {trend_arrow} ({trend_quality}){strict_tag}\n", style=trend_style_str)

            nearest_fib = sig.get("nearest_fib_level")
            swing_high = sig.get("fib_swing_high")
            swing_low = sig.get("fib_swing_low")
            up_leg = sig.get("fib_up_leg")
            if nearest_fib is not None:
                label, price = nearest_fib
                text.append(f"   FIB LEVEL BLOCKING: {label} @ {format_price(price)}\n", style="bold red")
            elif swing_high is not None and swing_low is not None:
                text.append(
                    f"   FIB SWING {format_price(swing_low)}-{format_price(swing_high)} "
                    f"({'up-leg' if up_leg else 'down-leg'}) — clear of levels\n",
                    style="bold cyan"
                )
            else:
                text.append("   Fib levels: — (insufficient range)\n", style="dim")

        if sig["reasons"]:
            text.append("   " + " · ".join(sig["reasons"][:5]) + "\n", style="dim")

        if is_pro_otc:
            engine_note = (
                "Pro OTC Engine heuristic (SMC + MTF + trend + momentum + volatility + patterns "
                "+ liquidity + order blocks + FVG, weighted AI score gate — a heuristic score, "
                "not a trained ML model), "
            )
        elif is_session_pattern:
            engine_note = "Session Pattern heuristic (candlestick patterns + streak + hourly OTC session weight), "
        else:
            engine_note = "Trend Candles heuristic (4-candle window: power + trend + Fibonacci retracement/extension gates), "
        text.append(f"   {engine_note}not a guarantee — trade at your own risk.\n", style="italic dim")

        tm = self.trade_manager
        if tm.config.execution_mode == "OFF":
            text.append("   Auto-trade: OFF (signals only)\n", style="dim")
        else:
            mode_style = "bold red" if tm.config.execution_mode == "LIVE" else "bold cyan"
            status = "HALTED" if tm.halted else "ARMED"
            status_style = "bold yellow" if tm.halted else "bold green"
            pnl_style = "bold green" if tm.session_pnl >= 0 else "bold red"
            text.append("   Auto-trade ", style="dim")
            text.append(f"{tm.config.execution_mode} ", style=mode_style)
            text.append(f"{status} ", style=status_style)
            text.append("| trades: ", style="dim")
            text.append(f"{tm.trade_count} ", style="bold")
            text.append("| session P&L: ", style="dim")
            text.append(f"{tm.session_pnl:+.2f}", style=pnl_style)
            if tm.halted:
                text.append(f" | {tm.halt_reason}", style="bold yellow")
            text.append("\n")

        return Panel(text, title="SIGNAL", title_align="left", border_style=dir_style if direction != "WAIT" else "bright_black")

    def build_stats_panel(self):
        tm = self.trade_manager
        stats = tm.journal.stats()
        text = Text()

        if stats["trades"] == 0:
            text.append("No trades recorded yet this session.\n", style="dim italic")
            return Panel(text, title="STATS", title_align="left", box=box.SIMPLE, border_style="bright_black")

        pnl_style = "bold green" if stats["total_pnl"] >= 0 else "bold red"
        text.append("Trades: ", style="dim"); text.append(f"{stats['trades']}  ", style="bold")
        text.append("Win rate: ", style="dim"); text.append(f"{stats['win_rate']}% ", style="bold cyan")
        text.append(f"({stats['wins']}W/{stats['losses']}L)\n", style="dim")

        text.append("P&L: ", style="dim"); text.append(f"{stats['total_pnl']:+.2f}\n", style=pnl_style)

        pf = stats["profit_factor"]
        text.append("Profit factor: ", style="dim")
        text.append(f"{pf}\n" if pf is not None else "—\n", style="bold")

        text.append("Streaks: ", style="dim")
        text.append(f"max win {stats['max_win_streak']} / max loss {stats['max_loss_streak']}\n")

        if stats["best_pair"]:
            bp, bp_pnl = stats["best_pair"]
            wp, wp_pnl = stats["worst_pair"]
            text.append("Best pair: ", style="dim")
            text.append(f"{format_asset_name(bp)} ({bp_pnl:+.2f})  ", style="bold green")
            text.append("Worst: ", style="dim")
            text.append(f"{format_asset_name(wp)} ({wp_pnl:+.2f})\n", style="bold red")

        if stats["best_hour"]:
            hr, hr_pnl = stats["best_hour"]
            text.append("Best hour (UTC): ", style="dim")
            text.append(f"{hr:02d}:00 ({hr_pnl:+.2f})\n", style="bold")

        recent = tm.journal.records[-3:][::-1]
        if recent:
            text.append("\nRecent trades:\n", style="bold dim")
            for r in recent:
                result_style = "bold green" if r["result"] == "WIN" else "bold red"
                time_only = r["time"].split(" ")[-1] if " " in r["time"] else r["time"]
                text.append(f"  {time_only} ", style="dim")
                text.append(f"{format_asset_name(r['asset'])} ", style="bold")
                text.append(f"{r['direction'].upper()} ", style="cyan")
                text.append(f"${r['amount']:.2f} ", style="dim")
                text.append(f"{r['result']} ", style=result_style)
                text.append(f"{r['profit']:+.2f}\n", style=result_style)

        return Panel(text, title="STATS", title_align="left", box=box.SIMPLE, border_style="bright_black")

    def build_logs_panel(self):
        log_text = Text()
        for log in self.logs:
            log_text.append(Text.from_markup(f" {log}\n"))
        return Panel(log_text, title="SYSTEM LOGS", title_align="left", box=box.SIMPLE, border_style="bright_black")

    async def run(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        layout = Layout()
        layout.split(
            Layout(name="header", size=4),
            Layout(name="signal", size=8),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=13),
        )
        layout["footer"].split_row(
            Layout(name="logs", ratio=2),
            Layout(name="stats", ratio=1),
        )

        loading_panel = Panel(
            Text("\n\nConnecting to Quotex and initializing WebSocket streams...\nPlease wait...", justify="center", style="bold yellow"),
            border_style="bright_black"
        )
        layout["body"].update(loading_panel)
        layout["header"].update(self.build_header())
        layout["signal"].update(self.build_signal_panel())
        layout["logs"].update(self.build_logs_panel())
        layout["stats"].update(self.build_stats_panel())

        try:
            with Live(layout, refresh_per_second=4, screen=True) as live:
                self.status = "Logging in"
                self.add_log("Connecting to Quotex API...")
                layout["header"].update(self.build_header())
                layout["logs"].update(self.build_logs_panel())

                with mute_stdout():
                    self.client = Quotex(email=self.email, password=self.password)
                    connected, error = await self.client.connect()

                if not connected:
                    self.status = "Failed"
                    self.add_log(f"[bold red]Connection failed:[/] {error}")
                    layout["header"].update(self.build_header())
                    layout["logs"].update(self.build_logs_panel())
                    await asyncio.sleep(3)
                    raise ConnectionError(f"Quotex connection failed: {error}")

                self.status = "Connected"
                self.add_log("Successfully logged into Quotex.")
                layout["header"].update(self.build_header())
                layout["logs"].update(self.build_logs_panel())

                await self.client.change_account(self.account_type)
                self.add_log(f"Switched account to: [bold magenta]{self.account_type}[/]")
                layout["logs"].update(self.build_logs_panel())

                await self.client.get_all_assets()

                if self.asset == "ALL":
                    self.active_assets = sorted([a for a in self.client.codes_asset.keys() if a.endswith("_otc")])
                    self.add_log(f"Fetched active OTC assets list.")
                    layout["logs"].update(self.build_logs_panel())
                else:
                    resolved_asset = self.asset
                    if resolved_asset not in self.client.codes_asset:
                        otc_asset = resolved_asset + "_otc"
                        if otc_asset in self.client.codes_asset:
                            resolved_asset = otc_asset
                        else:
                            resolved_asset = list(self.client.codes_asset.keys())[0]

                    self.asset = resolved_asset
                    self.active_assets = [self.asset]
                    self.add_log(f"Tracing focus asset: [bold cyan]{format_asset_name(self.asset)}[/]")
                    layout["logs"].update(self.build_logs_panel())

                if self.client.api and self.client.api.account_balance:
                    bal_key = "demoBalance" if self.account_type == "PRACTICE" else "liveBalance"
                    self.balance_str = f"{self.client.api.account_balance.get(bal_key, 0.0):,.2f}"
                    layout["header"].update(self.build_header())

                if self.client.api and self.client.api.instruments:
                    for i in self.client.api.instruments:
                        if len(i) > 18:
                            self.payouts[i[1]] = i[18]
                        elif len(i) > 5:
                            self.payouts[i[1]] = i[5]

                        if len(i) > 3:
                            cat = i[3].lower()
                            if cat in ("forex", "currency"):
                                self.categories[i[1]] = "Currencies"
                            elif cat in ("cryptocurrency", "crypto"):
                                self.categories[i[1]] = "Crypto"
                            elif cat in ("commodity", "commodities", "energy"):
                                self.categories[i[1]] = "Commodities"
                            elif cat in ("stock", "stocks", "indices", "index"):
                                self.categories[i[1]] = "Stocks"
                            else:
                                self.categories[i[1]] = "Stocks"

                if self.asset == "ALL":
                    filtered_assets = []
                    cat_order = ["Currencies", "Crypto", "Commodities", "Stocks"]
                    limit = self.max_rows if self.max_rows != 15 else 5
                    for category in cat_order:
                        cat_assets = [a for a in self.active_assets if self.categories.get(a, "Stocks") == category]
                        cat_assets.sort(key=lambda x: self.payouts.get(x, 0), reverse=True)
                        cat_assets = [a for a in cat_assets if self.payouts.get(a, 0) > 0]
                        filtered_assets.extend(cat_assets[:limit])
                    self.active_assets = filtered_assets
                    self.add_log(f"Optimized list: tracing top {len(self.active_assets)} active pairs.")
                    layout["logs"].update(self.build_logs_panel())

                HISTORY_LOOKBACK_SECONDS = 1000 * 60
                self.add_log(f"Fetching ~1000 candles for {len(self.active_assets)} asset(s)...")
                layout["logs"].update(self.build_logs_panel())

                history_semaphore = asyncio.Semaphore(3)
                history_progress = {"done": 0, "failed": []}
                has_deep_fetch = hasattr(self.client, "get_historical_candles")
                if self.trade_manager.config.engine == "SESSION_PATTERN":
                    min_candles_needed = SessionPatternEngine.MIN_CANDLES
                elif self.trade_manager.config.engine == "PRO_OTC":
                    min_candles_needed = ProOTCEngine.MIN_CANDLES
                else:
                    min_candles_needed = TrendCandleEngine.MIN_CANDLES

                async def _fetch_history(asset):
                    async with history_semaphore:
                        history = None
                        try:
                            if has_deep_fetch:
                                history = await self.client.get_historical_candles(
                                    asset, HISTORY_LOOKBACK_SECONDS, 60,
                                    timeout=45, max_workers=3,
                                )
                            if not history:
                                history = await self.client.get_candles(asset, time.time(), 3 * 3600, 60)
                        except Exception as hist_err:
                            self.add_log(f"[bold red]History fetch error[/] {format_asset_name(asset)}: {hist_err}")
                            _log_to_file(f"History fetch error for {asset}: {hist_err}")

                        if history:
                            self.trackers[asset].pre_populate(history)
                            if len(history) < min_candles_needed:
                                history_progress["failed"].append(f"{format_asset_name(asset)} ({len(history)})")
                        else:
                            history_progress["failed"].append(f"{format_asset_name(asset)} (0)")
                        history_progress["done"] += 1

                await asyncio.gather(*(_fetch_history(a) for a in self.active_assets))
                self.add_log(f"   History loaded: {history_progress['done']}/{len(self.active_assets)}")
                if history_progress["failed"]:
                    shown = ", ".join(history_progress["failed"][:6])
                    more = f" (+{len(history_progress['failed']) - 6} more)" if len(history_progress["failed"]) > 6 else ""
                    self.add_log(
                        f"[bold yellow]Warning:[/] thin/no history for: {shown}{more} — "
                        f"these will need to accumulate live candles before signals qualify."
                    )
                    _log_to_file(f"Thin/no history assets: {history_progress['failed']}")
                layout["logs"].update(self.build_logs_panel())

                self.add_log(f"Subscribing to {len(self.active_assets)} active streams...")
                layout["logs"].update(self.build_logs_panel())
                for idx, asset in enumerate(self.active_assets, 1):
                    self.client.start_candles_stream(asset, 60)
                    self.add_log(f"   Streaming: {format_asset_name(asset)} ({idx}/{len(self.active_assets)})")
                    layout["logs"].update(self.build_logs_panel())
                    await asyncio.sleep(0.4)

                self.status = "Streaming"
                self.add_log("Dashboard fully online.")

                if self.trade_manager.config.execution_mode != "OFF":
                    self._auto_trade_task = asyncio.create_task(self.auto_trade_loop())
                    self.add_log(f"[bold cyan]Auto-trade[/] armed in {self.trade_manager.config.execution_mode} mode "
                                 f"(engine={self.trade_manager.config.engine}, min confidence "
                                 f"{self.trade_manager.config.min_confidence}%).")
                layout["header"].update(self.build_header())
                layout["logs"].update(self.build_logs_panel())

                consecutive_errors = 0
                while True:
                    try:
                        if self.client.api and self.client.api.account_balance:
                            bal_key = "demoBalance" if self.account_type == "PRACTICE" else "liveBalance"
                            self.balance_str = f"{self.client.api.account_balance.get(bal_key, 0.0):,.2f}"

                        self.poll_realtime_data()
                        await self.update_signals()

                        layout["header"].update(self.build_header())
                        layout["signal"].update(self.build_signal_panel())
                        layout["stats"].update(self.build_stats_panel())

                        if self.asset == "ALL":
                            layout["body"].update(self.build_multi_asset_table())
                        else:
                            layout["body"].update(self.build_candles_table())

                        layout["logs"].update(self.build_logs_panel())

                        await asyncio.sleep(0.25)
                        consecutive_errors = 0
                    except (KeyboardInterrupt, asyncio.CancelledError):
                        raise
                    except Exception as loop_err:
                        consecutive_errors += 1
                        self.add_log(f"[bold red]Render error:[/] {loop_err}")
                        await asyncio.sleep(0.5)
                        if consecutive_errors >= 20:
                            raise
        finally:
            if self._auto_trade_task:
                self._auto_trade_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._auto_trade_task
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

    async def shutdown(self):
        self.add_log("Shutting down client connection safely...")
        if self.client:
            await self.client.close()

# --- CLI entry point -----------------------------------------------------

class Backtester:
    @staticmethod
    async def run(client, asset, lookback_seconds, duration=60, min_confidence=65, payout_pct=85,
                  engine="TREND_CANDLES", strict_confluence=False, strictness="BALANCED"):
        history = await client.get_candles(asset, time.time(), lookback_seconds, 60)
        if not history:
            return None
        history = sorted(history, key=lambda c: c["time"])
        tracker = CandleTracker()
        trades = []
        all_signals = []
        equity_curve = [0.0]
        n = len(history)
        duration_candles = max(1, duration // 60)

        for i, candle in enumerate(history):
            bucket = (int(candle["time"]) // 60) * 60
            tracker.candles[bucket] = {
                "timestamp": bucket, "open": float(candle["open"]), "high": float(candle["high"]),
                "low": float(candle["low"]), "close": float(candle["close"]),
                "ticks": 0, "depth_values": [], "is_closed": True,
            }
            tracker.candle_keys.append(bucket)
            tracker.tick_history.append((float(candle["time"]), float(candle["close"])))

            if i + duration_candles >= n:
                continue

            if engine == "SESSION_PATTERN":
                sig = SessionPatternEngine.compute(tracker)
            elif engine == "PRO_OTC":
                sig = ProOTCEngine.compute(tracker, strictness=strictness)
            else:
                sig = TrendCandleEngine.compute(tracker, strict_confluence=strict_confluence)
            if sig["direction"] == "WAIT":
                continue

            entry_close = candle["close"]
            exit_close = history[i + duration_candles]["close"]
            won = (exit_close > entry_close) if sig["direction"] == "BUY" else (exit_close < entry_close)
            profit = payout_pct / 100 if won else -1.0
            record = {
                "time": candle["time"], "direction": sig["direction"],
                "confidence": sig["confidence"], "won": won, "profit": profit,
            }
            all_signals.append(record)
            if sig["confidence"] < min_confidence:
                continue
            trades.append(record)
            equity_curve.append(equity_curve[-1] + profit)

        result = Backtester._summarize(trades, equity_curve)
        result["calibration"] = Backtester._calibration(all_signals, payout_pct)
        result["threshold_sweep"] = Backtester._threshold_sweep(all_signals, payout_pct)
        result["signals_seen"] = len(all_signals)
        result["candles"] = n
        return result

    @staticmethod
    def _calibration(signals, payout_pct):
        """Win rate per score band. If the win rate does NOT climb with the
        score, the score carries no predictive information and raising the
        threshold only reduces trade count, not losses."""
        bands = [(0, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
        out = []
        for lo, hi in bands:
            grp = [x for x in signals if lo <= x["confidence"] < hi]
            if not grp:
                continue
            wins = sum(1 for x in grp if x["won"])
            out.append({
                "band": f"{lo}-{hi - 1}",
                "n": len(grp),
                "win_rate": round(wins / len(grp) * 100, 1),
                "expectancy": round(sum(x["profit"] for x in grp) / len(grp), 4),
            })
        return out

    @staticmethod
    def _threshold_sweep(signals, payout_pct):
        breakeven = 100.0 / (1.0 + payout_pct / 100.0)
        out = []
        for thr in range(50, 96, 5):
            grp = [x for x in signals if x["confidence"] >= thr]
            if len(grp) < 10:
                continue
            wins = sum(1 for x in grp if x["won"])
            wr = wins / len(grp) * 100
            out.append({
                "threshold": thr,
                "trades": len(grp),
                "win_rate": round(wr, 1),
                "edge_vs_breakeven": round(wr - breakeven, 1),
                "total_units": round(sum(x["profit"] for x in grp), 2),
            })
        return out

    @staticmethod
    def _summarize(trades, equity_curve):
        n = len(trades)
        if n == 0:
            return {"trades": 0}
        wins = sum(1 for t in trades if t["won"])
        total_pnl = sum(t["profit"] for t in trades)
        gross_profit = sum(t["profit"] for t in trades if t["profit"] > 0)
        gross_loss = abs(sum(t["profit"] for t in trades if t["profit"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        peak, max_dd = equity_curve[0], 0.0
        for v in equity_curve:
            peak = max(peak, v)
            max_dd = max(max_dd, peak - v)

        return {
            "trades": n,
            "win_rate": round(wins / n * 100, 1),
            "total_pnl_units": round(total_pnl, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
            "max_drawdown_units": round(max_dd, 2),
        }


def main():
    parser = argparse.ArgumentParser(description="Quotex Trend Candles / Session Pattern / Pro OTC Dashboard")
    parser.add_argument("--asset", type=str, default="ALL", help="Asset pair to trace (e.g., EURUSD_otc) or 'ALL'")
    parser.add_argument("--account", type=str, default="PRACTICE", choices=["PRACTICE", "REAL"])
    parser.add_argument("--rows", type=int, default=15)
    parser.add_argument("--no-auto-trade-setup", action="store_true")
    parser.add_argument("--defaults", action="store_true")
    parser.add_argument("--backtest-days", type=int, default=None)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    _log_to_file(f"--- Dashboard starting (asset={args.asset}, account={args.account}) ---")

    if args.backtest_days is not None:
        if args.asset.upper() == "ALL":
            console.print("[bold red]--backtest-days requires a single --asset, not ALL.[/]")
            return
        email, password = prompt_login_credentials()
        console.print(f"[cyan]Logging in and fetching {args.backtest_days} day(s) of history for {args.asset}...[/]")
        with mute_stdout():
            client = Quotex(email=email, password=password)
            connected, error = asyncio.run(client.connect())
        if not connected:
            console.print(f"[bold red]Login failed:[/] {error}")
            return
        engine_choice = Prompt.ask(
            "Signal engine to backtest", choices=["trend_candles", "session_pattern", "pro_otc"], default="trend_candles"
        ).upper()
        strict_choice = False
        strictness_choice = "BALANCED"
        if engine_choice == "TREND_CANDLES":
            strict_choice = Confirm.ask("Backtest with STRICT confluence mode?", default=True)
        elif engine_choice == "PRO_OTC":
            strictness_choice = Prompt.ask(
                "PRO_OTC strictness", choices=["strict", "balanced", "aggressive"], default="balanced"
            ).upper()
        min_conf = IntPrompt.ask("Minimum confidence to count as a trade (0-100)", default=0)
        payout = FloatPrompt.ask("Assumed payout % (used only for this estimate)", default=85.0)
        result = asyncio.run(Backtester.run(
            client, args.asset, args.backtest_days * 86400,
            duration=60, min_confidence=min_conf, payout_pct=payout, engine=engine_choice,
            strict_confluence=strict_choice, strictness=strictness_choice
        ))
        asyncio.run(client.close())
        if not result or result["trades"] == 0:
            console.print("[yellow]No qualifying signals found in that window.[/]")
            return
        breakeven = 100.0 / (1.0 + payout / 100.0)
        console.print(Panel(
            f"Engine: {engine_choice}"
            + (f" ({strictness_choice})" if engine_choice == "PRO_OTC" else "") + "\n"
            f"Candles scanned: {result.get('candles', '?')} | signals produced: {result.get('signals_seen', '?')}\n"
            f"Trades: {result['trades']}\n"
            f"Win rate: {result['win_rate']}%   (break-even at {breakeven:.1f}% for {payout:.0f}% payout)\n"
            f"Total P&L: {result['total_pnl_units']:+.2f} units (stake=1)\n"
            f"Profit factor: {result['profit_factor']}\n"
            f"Max drawdown: {result['max_drawdown_units']:.2f} units",
            title=f"BACKTEST RESULTS — {format_asset_name(args.asset)} ({args.backtest_days}d)",
            border_style="cyan"
        ))

        calib = result.get("calibration") or []
        if calib:
            t = Table(title="SCORE CALIBRATION — does a higher score actually win more?", box=box.SIMPLE)
            t.add_column("Score band"); t.add_column("Signals", justify="right")
            t.add_column("Win rate", justify="right"); t.add_column("Expectancy/trade", justify="right")
            for row in calib:
                colour = "green" if row["expectancy"] > 0 else "red"
                t.add_row(row["band"], str(row["n"]), f"{row['win_rate']}%",
                          f"[{colour}]{row['expectancy']:+.4f}[/]")
            console.print(t)
            rates = [r["win_rate"] for r in calib if r["n"] >= 20]
            if len(rates) >= 2:
                if rates[-1] > rates[0] + 3:
                    console.print("[green]Win rate rises with the score — the score carries usable information.[/]")
                else:
                    console.print(
                        "[yellow]Win rate does NOT rise with the score. Raising the threshold will only "
                        "reduce the number of trades, not the losses — the ranking has no edge on this data.[/]"
                    )

        sweep = result.get("threshold_sweep") or []
        if sweep:
            t2 = Table(title="THRESHOLD SWEEP — frequency vs. accuracy trade-off", box=box.SIMPLE)
            t2.add_column("Min score", justify="right"); t2.add_column("Trades", justify="right")
            t2.add_column("Win rate", justify="right"); t2.add_column("vs break-even", justify="right")
            t2.add_column("Net units", justify="right")
            for row in sweep:
                colour = "green" if row["edge_vs_breakeven"] > 0 else "red"
                t2.add_row(str(row["threshold"]), str(row["trades"]), f"{row['win_rate']}%",
                           f"[{colour}]{row['edge_vs_breakeven']:+.1f}pp[/]",
                           f"[{colour}]{row['total_units']:+.2f}[/]")
            console.print(t2)
            console.print(
                "[dim]Pick the row with a positive edge AND enough trades. If no row is positive, "
                "no threshold setting makes this engine profitable on this asset — the strategy needs "
                "changing, not the filter.[/]"
            )
        return

    if args.no_auto_trade_setup:
        trade_config = TradeConfig()
    else:
        trade_config = setup_trade_config(console, use_defaults=args.defaults)
    trade_manager = TradeManager(trade_config)
    email, password = prompt_login_credentials()

    if args.no_auto_trade_setup:
        notif_config = NotificationConfig()
    else:
        notif_config = setup_notification_config(console)
    notifier = NotificationManager(notif_config, log_fn=_log_to_file)

    retry_delay = 5
    attempt = 0

    while True:
        app = DashboardApp(args.asset, args.account, args.rows, trade_manager=trade_manager,
                            email=email, password=password, notifier=notifier)
        notifier.log_fn = app.add_log
        try:
            asyncio.run(app.run())
            print("\n[*] Dashboard stopped.")
            break

        except KeyboardInterrupt:
            print("\n[*] Ctrl+C detected. Shutting down connection safely...")
            try:
                asyncio.run(app.shutdown())
            except Exception:
                pass
            break

        except SystemExit as e:
            msg = (
                f"pyquotex aborted the process via exit({e.code}). This almost always "
                f"means the Quotex LOGIN itself failed."
            )
            print("\n" + "=" * 70)
            print(f"[!] Login/startup was aborted by pyquotex: {msg}")
            print("=" * 70)
            sys.stdout.flush()
            _log_to_file(f"SystemExit from pyquotex (code={e.code}): {msg}")
            break

        except Exception:
            attempt += 1
            err_text = traceback.format_exc()
            print("\n" + "=" * 70)
            print(f"[!] Unexpected error occurred (attempt {attempt}). Details:")
            print(err_text)
            print("=" * 70)
            sys.stdout.flush()
            _log_to_file(f"Unexpected error (attempt {attempt}):\n{err_text}")
            try:
                asyncio.run(app.shutdown())
            except Exception:
                pass
            print(f"[*] Reconnecting in {retry_delay} seconds... (press Ctrl+C to stop instead)")
            try:
                time.sleep(retry_delay)
            except KeyboardInterrupt:
                print("\n[*] Cancelled by user.")
                break

    print(f"[*] Full error log (if any): {_LOG_FILE_PATH}")
    try:
        input("\n[*] Press Enter to close this window...")
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()