#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quotex Future Signal Generator — CLI PKT Edition v8
====================================================
EXACT fetch logic from download_data.py + signal analysis.
"""

import os
import sys
import time
import asyncio
import csv
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, ".")

from pyquotex.stable_api import Quotex

logging.basicConfig(level=logging.WARNING)

EMAIL = os.getenv("QUOTEX_EMAIL", "")
PASSWORD = os.getenv("QUOTEX_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("ERROR: Set QUOTEX_EMAIL and QUOTEX_PASSWORD in .env or export them")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# PATTERN ENGINE
# ═══════════════════════════════════════════════════════════════════

class PatternEngine:
    def __init__(self, candles, timeframe, min_accuracy):
        self.candles = candles
        self.timeframe = timeframe
        self.min_accuracy = min_accuracy
        self.patterns = []

    def analyze(self):
        self.detect_heavy_zones()
        self.detect_support_resistance()
        self.detect_trend_momentum()
        return self.patterns

    def detect_heavy_zones(self):
        sizes = [abs(c['close'] - c['open']) for c in self.candles if c.get('open')]
        if not sizes:
            return
        avg_size = statistics.mean(sizes)
        heavy_stats = defaultdict(lambda: {"bull": 0, "bear": 0, "total": 0})
        for c in self.candles:
            size = abs(c['close'] - c['open'])
            if size >= avg_size * 1.5:
                dt = datetime.fromtimestamp(c['time'])
                time_key = dt.strftime("%H:%M")
                heavy_stats[time_key]["total"] += 1
                if c['close'] > c['open']:
                    heavy_stats[time_key]["bull"] += 1
                else:
                    heavy_stats[time_key]["bear"] += 1
        for time_key, stats in heavy_stats.items():
            if stats["total"] >= 5:
                bull_pct = (stats["bull"] / stats["total"]) * 100
                bear_pct = (stats["bear"] / stats["total"]) * 100
                if bull_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "BUY",
                        "confidence": round(bull_pct, 1), "pattern": "Heavy Bull",
                        "reason": f"{stats['bull']}/{stats['total']} heavy GREEN"})
                elif bear_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "SELL",
                        "confidence": round(bear_pct, 1), "pattern": "Heavy Bear",
                        "reason": f"{stats['bear']}/{stats['total']} heavy RED"})

    def detect_support_resistance(self):
        reversal_stats = defaultdict(lambda: {"bull_rev": 0, "bear_rev": 0, "total": 0})
        for i in range(1, len(self.candles) - 1):
            prev = self.candles[i - 1]
            curr = self.candles[i]
            next_c = self.candles[i + 1]
            dt = datetime.fromtimestamp(curr['time'])
            time_key = dt.strftime("%H:%M")
            prev_bear = prev['close'] < prev['open']
            prev_bull = prev['close'] > prev['open']
            next_bull = next_c['close'] > next_c['open']
            next_bear = next_c['close'] < next_c['open']
            if prev_bear and next_bull and curr['close'] >= curr['open']:
                reversal_stats[time_key]["bull_rev"] += 1
                reversal_stats[time_key]["total"] += 1
            elif prev_bull and next_bear and curr['close'] <= curr['open']:
                reversal_stats[time_key]["bear_rev"] += 1
                reversal_stats[time_key]["total"] += 1
        for time_key, stats in reversal_stats.items():
            if stats["total"] >= 5:
                bull_pct = (stats["bull_rev"] / stats["total"]) * 100
                bear_pct = (stats["bear_rev"] / stats["total"]) * 100
                if bull_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "BUY",
                        "confidence": round(bull_pct, 1), "pattern": "Bull Reversal",
                        "reason": f"{stats['bull_rev']}/{stats['total']} bull reversals"})
                elif bear_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "SELL",
                        "confidence": round(bear_pct, 1), "pattern": "Bear Reversal",
                        "reason": f"{stats['bear_rev']}/{stats['total']} bear reversals"})

    def detect_trend_momentum(self):
        trend_stats = defaultdict(lambda: {"bull": 0, "bear": 0, "total": 0})
        for i in range(2, len(self.candles)):
            c1 = self.candles[i - 2]
            c2 = self.candles[i - 1]
            c3 = self.candles[i]
            dt = datetime.fromtimestamp(c3['time'])
            time_key = dt.strftime("%H:%M")
            if c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open']:
                trend_stats[time_key]["bull"] += 1
                trend_stats[time_key]["total"] += 1
            elif c1['close'] < c1['open'] and c2['close'] < c2['open'] and c3['close'] < c3['open']:
                trend_stats[time_key]["bear"] += 1
                trend_stats[time_key]["total"] += 1
        for time_key, stats in trend_stats.items():
            if stats["total"] >= 5:
                bull_pct = (stats["bull"] / stats["total"]) * 100
                bear_pct = (stats["bear"] / stats["total"]) * 100
                if bull_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "BUY",
                        "confidence": round(bull_pct, 1), "pattern": "Bull Momentum",
                        "reason": f"{stats['bull']}/{stats['total']} 3-green streaks"})
                elif bear_pct >= self.min_accuracy:
                    self.patterns.append({"time": time_key, "direction": "SELL",
                        "confidence": round(bear_pct, 1), "pattern": "Bear Momentum",
                        "reason": f"{stats['bear']}/{stats['total']} 3-red streaks"})


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def filter_time_window(patterns, start_time, end_time):
    filtered = []
    start_dt = datetime.strptime(start_time, "%H:%M")
    end_dt = datetime.strptime(end_time, "%H:%M")
    for p in patterns:
        signal_dt = datetime.strptime(p["time"], "%H:%M")
        if start_dt <= signal_dt <= end_dt:
            filtered.append(p)
    return filtered

def remove_clashes(patterns):
    time_groups = defaultdict(list)
    for p in patterns:
        time_groups[p["time"]].append(p)
    best_signals = []
    for group in time_groups.values():
        group.sort(key=lambda x: x["confidence"], reverse=True)
        best_signals.append(group[0])
    best_signals.sort(key=lambda x: x["time"])
    return best_signals

def generate_future_signals(all_pair_patterns, max_signals):
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    all_signals = []
    for pair, patterns in all_pair_patterns.items():
        for p in patterns:
            all_signals.append({
                "date": date_str, "time_pkt": p["time"] + " PKT",
                "pair": pair, "direction": p["direction"],
                "confidence": p["confidence"],
                "confidence_str": f"{p['confidence']:.1f}%",
                "pattern": p["pattern"], "reason": p["reason"]})
    all_signals.sort(key=lambda x: x["confidence"], reverse=True)
    top_signals = all_signals[:max_signals]
    top_signals.sort(key=lambda x: x["time_pkt"])
    return top_signals

def save_signals(signals, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Date', 'Time (PKT)', 'Pair', 'Direction', 'Confidence', 'Pattern', 'Reason'])
        for s in signals:
            writer.writerow([s["date"], s["time_pkt"], s["pair"], s["direction"],
                           s["confidence_str"], s["pattern"], s["reason"]])
    print(f"\n💾 Saved {len(signals)} signals to: {filename}")

def print_banner():
    print("\n" + "="*70)
    print("🚀 QUOTEX FUTURE SIGNAL GENERATOR — CLI PKT Edition v8")
    print("   [EXACT download_data.py fetch logic + signal analysis]")
    print("="*70)

def print_signals(signals):
    print("\n" + "="*70)
    print("🎯 FUTURE SIGNAL LIST — PKT TIME (TODAY)")
    print("="*70)
    print(f"{'Date':<12} {'Time':<12} {'Pair':<15} {'Dir':<6} {'Conf':<8} {'Pattern':<18}")
    print("-"*70)
    for s in signals:
        print(f"{s['date']:<12} {s['time_pkt']:<12} {s['pair']:<15} "
              f"{s['direction']:<6} {s['confidence_str']:<8} {s['pattern']:<18}")
    print("="*70)
    print(f"Total Signals: {len(signals)}")
    print("="*70)


def print_progress(fetched_seconds, total_seconds, candle_count, start_ts):
    """EXACT from download_data.py"""
    pct = min(fetched_seconds / total_seconds, 1.0) if total_seconds > 0 else 0
    bar_len = 35
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    elapsed = time.time() - start_ts
    if pct > 0.01:
        eta_secs = (elapsed / pct) * (1 - pct)
        eta_str = str(timedelta(seconds=int(eta_secs)))
    else:
        eta_str = "calculating..."
    days_fetched = fetched_seconds / 86400
    print(
        f"\r  [{bar}] {pct*100:5.1f}%  "
        f"{days_fetched:.2f} days  "
        f"{candle_count:,} candles  "
        f"⏱ {elapsed:.0f}s  ETA {eta_str}   ",
        end="", flush=True)


# ═══════════════════════════════════════════════════════════════════
# FETCH — EXACTLY LIKE download_data.py (single connection, no retry loop)
# ═══════════════════════════════════════════════════════════════════

async def fetch_pair_data(email, password, pair, days, timeframe):
    """EXACT download_data.py logic — connect once, fetch with progress, close."""
    duration_seconds = int(86400 * days)

    client = Quotex(email=email, password=password, lang="en")
    client.debug_ws_enable = False

    print(f"\n🔌 Connecting for {pair}...")
    check, msg = await client.connect()
    if not check:
        print(f"❌ {pair}: Connection failed — {msg}")
        await client.close()
        return None

    print(f"📊 Fetching {days} days of {pair} ({timeframe}s)...")
    start_time = time.time()

    def on_progress(current, total, label, worker_label):
        print(f"📊 [{worker_label}] {label}: {current}/{total}")

    all_candles = await client.get_candles_deep(
        pair, duration_seconds, timeframe, progress_callback=on_progress)

    print()  # newline after progress bar
    fetch_time = time.time() - start_time

    if all_candles:
        print(f"✅ {pair}: Fetch complete in {fetch_time:.1f}s — {len(all_candles):,} candles.")
    else:
        print(f"❌ {pair}: No data retrieved.")

    await client.close()
    return [c for c in all_candles if c.get('open') is not None] if all_candles else None


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

async def main():
    print_banner()

    print("\n📋 ENTER YOUR SETTINGS:")
    print("-"*40)

    pairs_input = input("Pairs (comma separated, e.g. USDPKR_otc,EURUSD_otc): ").strip()
    pairs = [p.strip() for p in pairs_input.split(",") if p.strip()]
    if not pairs:
        print("❌ No pairs entered. Exiting.")
        return

    while True:
        try:
            history_days = float(input("History days (e.g. 7, 14, 30): ").strip())
            if history_days > 0:
                break
        except ValueError:
            print("Invalid number")

    while True:
        try:
            timeframe = int(input("Timeframe in seconds (60=1m, 300=5m): ").strip())
            if timeframe > 0:
                break
        except ValueError:
            print("Invalid number")

    start_time = input("Start time PKT (HH:MM, e.g. 09:00): ").strip() or "00:00"
    end_time = input("End time PKT (HH:MM, e.g. 18:00): ").strip() or "23:59"

    while True:
        try:
            min_accuracy = float(input("Min accuracy % (e.g. 75, 80, 85): ").strip())
            if 0 < min_accuracy <= 100:
                break
        except ValueError:
            print("Invalid number")

    while True:
        try:
            max_signals = int(input("How many signals you want? (e.g. 10, 15, 20): ").strip())
            if max_signals > 0:
                break
        except ValueError:
            print("Invalid number")

    output_file = input("Output filename (default: future_signals.csv): ").strip() or "future_signals.csv"

    print("\n" + "="*70)
    print("✅ SETTINGS CONFIRMED:")
    print("="*70)
    print(f"Pairs:        {', '.join(pairs)}")
    print(f"History:      {history_days} days")
    print(f"Timeframe:    {timeframe}s")
    print(f"PKT Window:   {start_time} — {end_time}")
    print(f"Min Accuracy: {min_accuracy}%")
    print(f"Signals:      {max_signals}")
    print(f"Output:       {output_file}")
    print("="*70)

    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    print("\n🚀 Starting multi-pair analysis...")
    all_pair_patterns = {}

    for pair in pairs:
        candles = await fetch_pair_data(EMAIL, PASSWORD, pair, history_days, timeframe)
        if candles:
            print(f"🔍 Analyzing {pair}...")
            engine = PatternEngine(candles, timeframe, min_accuracy)
            patterns = engine.analyze()
            patterns = filter_time_window(patterns, start_time, end_time)
            patterns = remove_clashes(patterns)
            all_pair_patterns[pair] = patterns
            print(f"✅ {pair}: {len(patterns)} patterns found")
        else:
            print(f"❌ {pair}: No data to analyze")
        if pair != pairs[-1]:
            print("⏳ Waiting 5s before next pair...")
            await asyncio.sleep(5)

    print(f"\n🎯 Generating top {max_signals} signals for TODAY...")
    signals = generate_future_signals(all_pair_patterns, max_signals)

    if signals:
        print_signals(signals)
        save_signals(signals, output_file)
    else:
        print("\n❌ No signals found. Try lower accuracy or more history.")

    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
