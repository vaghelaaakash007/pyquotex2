"""
================================================================
NAIF Pro v7.0 SMART — All-in-One Terminal Edition (Quotex)
================================================================
A complete trading bot in a single file for Quotex.

Features:
    ⚡ 30+ Strategies (Joker, Momentum, RSI, Bollinger, AB Pattern,
       OTC Fortress, Smart Voting, MTF Confirmation, Engulfing,
       SuperTrend Flip, Donchian Break, Aroon Trend, etc.)
    🧠 Smart Self-Learning Voting System (per-strategy win-rate)
    🔭 Multi-Timeframe confirmation (M1 + M5 + M15)
    📋 Numbered interactive menu (number or partial-name search)
    📈 Live Dashboard with real-time updates
    📊 Strategy Performance Stats (auto-persisted)
    📡 Telegram notifications + Screenshots
    💾 CSV logging of every trade
    🎛️ Martingale: OFF / CLASSIC / FIBONACCI / CUSTOM / MANUAL / ANTI
    🕐 Trading Scheduler (start/end hours + weekdays)
    🎯 Asset filtering (OTC-only, min payout, rotation modes)
    💰 Session SL/TP guards

⚠️ WARNINGS ⚠️
    1. Binary options are HIGH RISK — 70-90% of traders lose money
    2. The pyquotex library is UNOFFICIAL — may violate Quotex ToS
    3. ALWAYS test on PRACTICE account first
    4. Past results do NOT guarantee future profits
    5. Martingale will eventually bust an account

Installation:
    pip install rich requests mss pillow pyquotex

Usage:
    python naif_pro_v7.py
================================================================
"""

import os

import sys
import time
import math
import re
import json
import csv
import io
import asyncio
import logging
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any, Callable, Deque
from collections import deque
from pathlib import Path
from getpass import getpass
from enum import Enum
import requests

from rich.console import Console, Group

from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
try:
    import mss
    from PIL import Image
    SCREENSHOT_AVAILABLE = True
finally:
    pass
if Exception:
    Exception
    mss = None
    Image = None
    SCREENSHOT_AVAILABLE = False
try:
    from pyquotex.stable_api import Quotex
    try:
        from pyquotex.config import credentials as _credentials_source
    finally:
        pass
finally:
    if Exception:
        Exception
        __exception__
        __exception__
        _credentials_source = None
QUOTEX_AVAILABLE = True
if Exception:
    Exception
    Quotex = None
    _credentials_source = None
    QUOTEX_AVAILABLE = False
CONFIG_PATH = "naif_v7_config.json"
STRATEGY_STATS_FILE = "naif_strategy_performance.json"
TRADES_CSV_DEFAULT_PREFIX = "naif_trades_"
APP_NAME = "NAIF Pro v7.0 SMART"
APP_VERSION = "7.0.0"
console = Console(record=False, force_terminal=True, soft_wrap=False)
def print_banner():
    banner = "\n    ╔══════════════════════════════════════════════════════════════════╗\n    ║                                                                  ║\n    ║    🤖  NAIF Pro v7.0 SMART  —  Quotex Trading Bot                ║\n    ║                                                                  ║\n    ║    ⚡ 30+ Strategies      🧠 Smart Self-Learning Voting          ║\n    ║    🔭 Multi-Timeframe     📋 Numbered Menu + Search              ║\n    ║    📡 Telegram + 📸 Shot  💾 CSV Logging                          ║\n    ║    🎛️ 6 Martingale Modes  🕐 Trading Scheduler                   ║\n    ║                                                                  ║\n    ║          ⚠  Use PRACTICE account for testing                     ║\n    ║                                                                  ║\n    ╚══════════════════════════════════════════════════════════════════╝\n    "
    console.print(banner, style="bold cyan")
def clear_screen():
    if os.name == "nt":
        os.system("cls")
        return
    ##ERROR##("clear")
def numbered_picker(title: str, options, current=None, description: str="", columns: int=1, show_descriptions: bool=False, descriptions: dict=None, allow_cancel: bool=True):
    n = len(options)
    if n == 0:
        console.print("[red]No options available.[/red]")
        return
    elif not columns == 1 and n > 20 and show_descriptions:
        columns = 2
    
    tbl = Table(title=f"[bold cyan]{title}[/bold cyan]", box=box.ROUNDED, show_lines=False, title_style="bold cyan", border_style="cyan", expand=False)
    
    while show_descriptions:
        tbl.add_column("#", style="bold yellow", justify="right", width=5)
        tbl.add_column("Name", style="bold cyan", no_wrap=False)
        tbl.add_column("Description", style="white", no_wrap=False)
        for i, opt in enumerate(options, 1):
            desc = ""
            if descriptions and opt in descriptions:
                desc = descriptions[opt]
            marker = ""
            tbl.add_row(str(i), f"{marker}{opt}", desc)
    
    if columns == 2:
        tbl.add_column("#", style="bold yellow", justify="right", width=5)
        tbl.add_column("Name", style="bold cyan", no_wrap=True)
        tbl.add_column("#", style="bold yellow", justify="right", width=5)
        tbl.add_column("Name", style="bold cyan", no_wrap=True)
        half = (n + 1) // 2
        for i in range(half):
            left_idx = i
            right_idx = i + half
            left_opt = ""
            right_opt = ""
            left_marker = ""
            right_marker = ""
            left_num = ""
            right_num = ""
            tbl.add_row(left_num, f"{left_marker}{left_opt}", right_num, f"{right_marker}{right_opt}")
    
    else:
        tbl.add_column("#", style="bold yellow", justify="right", width=5)
        tbl.add_column("Option", style="bold cyan")
        for i, opt in enumerate(options, 1):
            marker = ""
            tbl.add_row(str(i), f"{marker}{opt}")
    console.print(tbl)
    
    if description:
        console.print(f"\n[dim]{description}[/dim]")
    
    elif current is not None:
        try:
            current_idx = options.index(current) + 1
            console.print(f"\n[dim]Current selection:[/dim] [bold cyan]{current}[/bold cyan] [dim](#{current_idx})[/dim]")
        finally:
            pass
        if ValueError:
            ValueError
        hint_lines = [f"[dim]► Enter a number from 1 to {n}[/dim]",
            
            "[dim]► Or type the name (full or partial — e.g. 'rsi' to search)[/dim]"]
        if allow_cancel:
            hint_lines.append("[dim]► Press Enter, or type [bold]'b'[/bold]/[bold]'back'[/bold] to go back[/dim]")
    
    for ln in hint_lines:
        console.print(ln)
    console.print()
    try:
        pass
    finally:
        pass
    user_input = "➤ "(f"{title} (number or name): __exception__")
    if (EOFError, KeyboardInterrupt):
        (EOFError, KeyboardInterrupt)
        input
        input
    return
    if user_input is None:
        return
    user_input = user_input.strip()
    while not user_input:
        if allow_cancel:
            return
        console.print("[red]Please enter a value.[/red]")
    if allow_cancel and user_input.lower() in ("b", "back", "q", "quit", "esc", "exit", "0"):
        console.print("[dim]↩ Going back...[/dim]")
        time.sleep(0.3)
        return
    while user_input.isdigit():
        num = int(user_input)
    console.print(f"[red]✗ Number must be between 1 and {n}.[/red]")
    for opt in options:
        pass
    upper_q = user_input.upper()
    matches = [opt for opt in options if upper_q in opt.upper()]
    for i, m in enumerate(matches[:30], 1):
        global_idx = options.index(m) + 1
        extra = ""
        if descriptions and m in descriptions:
            extra = f" [dim]— {descriptions[m][:60]}[/dim]"
        console.print(f"  [bold yellow]{i:>3}.[/bold yellow] [cyan]{m}[/cyan] [dim](#{global_idx})[/dim]{extra}")
    with num:
        pass
    
    return sel
def numbered_yes_no(prompt: str, default_yes: bool=True) -> bool:
    options = ["No", "Yes"]
    
    current = options[0]
    
    result = numbered_picker(title=prompt, options=options, current=current, description="", allow_cancel=True)
    if result is None:
        return default_yes
    
    return result == "Yes"
def ask_number(prompt: str, default: float, min_val: float=None, max_val: float=None, is_int: bool=False) -> float:
    suffix = f" [dim](default {default})[/dim]"
    
    if min_val is not None or max_val is not None:
        range_str = f"[{"-∞"} … {"+∞"}]"
        suffix += f" [dim]{range_str}[/dim]"
    suffix += " [dim](Enter=keep default)[/dim]"
    
    console.print(f"[bold cyan]{prompt}[/bold cyan]{suffix}")
    
    try:
        pass
    finally:
        raw = __exception__()
    if (EOFError, KeyboardInterrupt):
        (EOFError, KeyboardInterrupt)
        input("➤ ").strip
        input("➤ ").strip
    return
    if raw and raw.lower() in ("b", "back", "q", "quit"):
        return default
    try:
        val = float(raw)
        while min_val is not None and val < min_val:
            console.print(f"[red]✗ Value must be ≥ {min_val}[/red]")
        
        while max_val is not None and val > max_val:
            console.print(f"[red]✗ Value must be ≤ {max_val}[/red]")
        
    finally:
        return val
        if ValueError:
            ValueError
            console.print("[red]✗ Please enter a valid number.[/red]")
def ask_text(prompt: str, default: str="") -> str:
    suffix = ""
    
    console.print(f"[bold cyan]{prompt}[/bold cyan]{suffix}")
    try:
        pass
    finally:
        raw = __exception__()
    if (EOFError, KeyboardInterrupt):
        (EOFError, KeyboardInterrupt)
        input("➤ ").strip
        input("➤ ").strip
    return
    if not raw:
        pass
    return default
def press_any_key(prompt: str="Press Enter to continue..."):
    try:
        input(f"\n[dim]{prompt}[/dim]\n")
    finally:
        return
        if (EOFError, KeyboardInterrupt):
            (EOFError, KeyboardInterrupt)
        return
def print_section(title: str, border_style: str="cyan"):
    console.print(Panel.fit(f"[bold]{title}[/bold]", border_style=border_style))
class TelegramBot:
    """Telegram notifier — sends trade entries + results + screenshots."""
    def __init__(self):
        self.enabled = False
        self.token = ""
        self.chat_id = ""
    
    def setup_interactive(self):
        print_section("📡 TELEGRAM SETUP")
        
        choice = numbered_picker(title="Telegram Notifications", options=["Enable", "Disable"], current="Disable", description="If enabled, you'll get a Telegram message on every trade entry and result.", allow_cancel=True)
        if choice == "Enable":
            self.token = ask_text("Bot Token", self.token)
            self.chat_id = ask_text("Chat ID", self.chat_id)
            if self.token and self.chat_id:
                self.enabled = True
                if self.test():
                    console.print("[green]✅ Telegram connected successfully.[/green]")
                    return
                console.print("[yellow]⚠ Telegram test failed — check token/chat_id.[/yellow]")
                return
            self.enabled = False
            console.print("[red]❌ Missing token or chat ID — Telegram disabled.[/red]")
            return
        self.enabled = False
        
        console.print("[dim]❌ Telegram disabled.[/dim]")
    
    def test(self) -> bool:
        if not self.enabled:
            return False
        try:
            r = requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", data={"chat_id": self.chat_id, "text": f"🤖 <b>{APP_NAME}</b> connected!\n⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}", "parse_mode": "HTML"}, timeout=10)
        finally:
            return r.status_code == 200
            if Exception:
                Exception
            return False
    
    def send(self, text: str):
        if not self.enabled:
            return
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", data={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        finally:
            return
            if Exception:
                Exception
                e = None
                try:
                    pass
                finally:
                    __exception__
                return
    
    def send_photo(self, path: str, caption: str=""):
        if not self.enabled and path and os.path.exists(path):
            return
        try:
            with open(path, "rb") as f:
                pass
            requests.post(f"https://api.telegram.org/bot{self.token}/sendPhoto", data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": f}, timeout=20)
        finally:
            ##ERROR##(None, None, None)
            return
        return
        if Exception:
            Exception
            e = None
            try:
                pass
            finally:
                __exception__
            return
class ScreenshotManager:
    """Captures the primary monitor at trade entry/result."""
    def __init__(self):
        self.enabled = False
        self.save_dir = "naif_screenshots"
    
    def setup_interactive(self):
        print_section("📸 SCREENSHOT SETUP")
        if not SCREENSHOT_AVAILABLE:
            console.print("[yellow]⚠ Screenshot disabled: mss or PIL not installed[/yellow]")
            console.print("[dim]To enable: pip install mss pillow[/dim]")
            self.enabled = False
            return
        choice = numbered_picker(title="Screenshot at Entry/Result", options=["Enable", "Disable"], current="Disable", description="Save a screenshot of the primary monitor on every trade.", allow_cancel=True)
        
        self.enabled = choice == "Enable"
        if self.enabled:
            os.makedirs(self.save_dir, exist_ok=True)
            console.print(f"[green]✅ Screenshots will be saved to '{self.save_dir}/'[/green]")
            return
        console.print("[dim]❌ Screenshots disabled.[/dim]")
    
    def take(self, prefix: str="shot") -> Optional[str]:
        if not self.enabled and SCREENSHOT_AVAILABLE:
            return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = os.path.join(self.save_dir, f"{prefix}_{timestamp}.png")
            with mss.mss() as sct:
                monitor = sct.monitors[1]
        finally:
            sct_img = __exception__
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            img.save(name)
            sct.grab(monitor)(None, None, None)
            return name
        
        return name
        if Exception:
            Exception
            e = None
            try:
                pass
            finally:
                __exception__
            return
class CSVLogger:
    """Logs every trade to a CSV file."""
    def __init__(self):
        self.enabled = False
        self.file_path = f"{TRADES_CSV_DEFAULT_PREFIX}{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"
    
    def setup_interactive(self):
        print_section("💾 CSV LOG SETUP")
        
        choice = numbered_picker(title="CSV Trade Logging", options=["Enable", "Disable"], current="Disable", description="Save every trade (entry + result) to a CSV file.", allow_cancel=True)
        
        self.enabled = choice == "Enable"
        
        if self.enabled:
            try:
                with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                writer.writerow(["timestamp", "asset", "direction", "amount", "duration_s", "payout_pct", "result", "profit", "balance", "order_id", "strategy", "confidence", "mg_step"])
            finally:
                None(None, __exception__, __exception__)
        
        console.print(f"[green]✅ CSV logging enabled → {self.file_path}[/green]")
        if Exception:
            Exception
            e = None
            try:
                console.print(f"[red]✗ Failed to create CSV: {e}[/red]")
                self.enabled = False
            finally:
                pass
            return
            console.print("[dim]❌ CSV logging disabled.[/dim]")
            return
    
    def log(self, data: Dict):
        if not self.enabled:
            return
        try:
            with open(self.file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
            data.get("timestamp", datetime.now().isoformat())([data.get("asset", ""),
    data.get("direction", ""),
    data.get("amount", 0),
    data.get("duration", 0),
    data.get("payout", 0),
    data.get,
    "result",
    data.get("profit", 0),
    data.get("balance", 0),
    data.get("order_id", ""),
    data.get("strategy", ""),
    data.get("confidence", 0),
    data.get("mg_step", 0)])
        finally:
            writer.writerow(None, None, None)
            return
        return
        if Exception:
            Exception
            e = None
            try:
                pass
            finally:
                __exception__
            return
class TradingScheduler:
    """Restricts trading to specific hours and weekdays."""
    def __init__(self):
        self.enabled = False
        self.start_hour = 9
        self.end_hour = 22
        self.weekdays = [0, 1, 2, 3, 4, 5, 6]
    
    def setup_interactive(self):
        print_section("🕐 TRADING SCHEDULER")
        
        choice = numbered_picker(title="Limit trading to specific hours?", options=["Enable", "Disable"], current="Disable", description="When disabled, the bot trades 24/7.", allow_cancel=True)
        
        self.enabled = choice == "Enable"
        if self.enabled:
            self.start_hour = int(ask_number("Start hour (0-23)", self.start_hour, 0, 23, is_int=True))
            self.end_hour = int(ask_number("End hour (0-23)", self.end_hour, 0, 23, is_int=True))
            weekday_choice = numbered_picker(title="Active weekdays", options=["All days (0-6)", "Weekdays only (Mon-Fri)", "Weekends only (Sat-Sun)", "Custom"], current="All days (0-6)", allow_cancel=True)
            if weekday_choice == "Weekdays only (Mon-Fri)":
                self.weekdays = [0, 1, 2, 3, 4]
            elif weekday_choice == "Weekends only (Sat-Sun)":
                self.weekdays = [5, 6]
            elif weekday_choice == "Custom":
                raw = ask_text("Weekdays as comma-separated (0=Mon..6=Sun), e.g. '0,1,2,3,4'", "0,1,2,3,4")
                try:
                    self.weekdays = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
                finally:
                    pass
                if Exception:
                    Exception
                    self.weekdays = [0, 1, 2, 3, 4, 5, 6]
                self.weekdays = [0, 1, 2, 3, 4, 5, 6]
                console.print(f"[green]✅ Schedule: {self.start_hour:02d}:00 → {self.end_hour:02d}:00 on weekdays {self.weekdays}[/green]")
                return
                console.print("[dim]❌ Scheduler disabled — trading 24/7.[/dim]")
                return
    
    def is_active_now(self) -> Tuple[(bool, str)]:
        if not self.enabled:
            return (True, "")
        now = datetime.now()
        if now.weekday() not in self.weekdays:
            return (False, f"Today (weekday {now.weekday()}) not in schedule {self.weekdays}")
        h = now.hour
        
        if self.start_hour <= self.end_hour:
            match h:
                case _ as ok if self.start_hour <= h < self.end_hour and h >= self.start_hour and h < self.end_hour:
                    return (False, f"Hour {h:02d}:00 outside schedule {self.start_hour:02d}-{self.end_hour:02d}")
        
        return (True, "")
def is_bull(candle: Dict) -> bool:
    return candle["close"] > candle["open"]
def is_bear(candle: Dict) -> bool:
    return candle["close"] < candle["open"]
def candle_body(candle: Dict) -> float:
    return abs(candle["close"] - candle["open"])
def candle_range(candle: Dict) -> float:
    return candle["high"] - candle["low"]
def candle_body_pct(candle: Dict) -> float:
    rng = candle_range(candle)
    if rng > 0:
        return candle_body(candle) / rng
    
    return 0.0
def ema(series: List[float], span: int) -> List[float]:
    if series and span <= 1:
        return series[:]
    k = 2 / (span + 1)
    out = [series[0]]
    m = series[0]
    
    for i in range(1, len(series)):
        m = series[i] * k + m * (1 - k)
        out.append(m)
    return out
def sma(series: List[float], length: int) -> List[float]:
    out = []
    s = 0.0
    
    for i, v in enumerate(series):
        s += v
        if i >= length:
            s -= series[i - length]
        out.append(s / min(i + 1, length))
    return out
def wma(series: List[float], length: int) -> List[float]:
    out = []
    
    for i in range(len(series)):
        start = max(0, i - length + 1)
        seg = series[start:i + 1]
        weights = list(range(1, len(seg) + 1))
        s = sum((v * w for v, w in zip(seg, weights)))
        wsum = sum(weights)
        out.append(seg[-1])
    return out
def rsi(series: List[float], length: int=14) -> List[float]:
    if len(series) < length + 1:
        return [50.0] * len(series)
    gains = []
    losses = []
    
    for i in range(1, len(series)):
        ch = series[i] - series[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    alpha = 1.0 / length
    def w(vals):
        if not vals:
            return []
        s = vals[0]
        out = [s]
        
        for v in vals[1:]:
            s = s * (1 - alpha) + v * alpha
            out.append(s)
        return out
    
    ag = w(gains)
    
    al = w(losses)
    out = [50.0] * length
    
    for g, l in zip(ag, al):
        rs = g / 1e-12
        out.append(100 - 100 / (1 + rs))
    return out[:len(series)]
def macd_line(series: List[float], fast=12, slow=26, signal=9) -> Tuple[(List[float], List[float])]:
    if len(series) < slow + signal + 5:
        return ([0.0] * len(series), [0.0] * len(series))
    ef = ema(series, fast)
    es = ema(series, slow)
    m = [a - b for a, b in zip(ef, es)]
    s = ema(m, signal)
    return (m, s)
def rolling_std(series: List[float], length: int) -> List[float]:
    out = []
    
    for i in range(len(series)):
        start = max(0, i - length + 1)
        seg = series[start:i + 1]
        m = sum(seg) / len(seg)
        var = sum(((x - m)**2 for x in seg)) / max(1, len(seg) - 1)
        out.append(math.sqrt(var))
    return out
def bollinger(series: List[float], length: int=20, mult: float=2.0):
    ma = sma(series, length)
    sd = rolling_std(series, length)
    up = [m + mult * s for m, s in zip(ma, sd)]
    dn = [m - mult * s for m, s in zip(ma, sd)]
    return (dn, ma, up)
def atr(high: List[float], low: List[float], close: List[float], length: int=14) -> List[float]:
    n = len(close)
    out = []
    prev = close[0]
    
    for i in range(n):
        if i == 0:
            tr = high[i] - low[i]
        else:
            tr = max(high[i] - low[i], abs(high[i] - prev), abs(low[i] - prev))
        prev = close[i]
        out.append(tr)
    return ema(out, length)
def keltner(high: List[float], low: List[float], close: List[float], length: int=20, mult: float=1.5):
    mid = ema(close, length)
    a = atr(high, low, close, length)
    up = [m + mult * x for m, x in zip(mid, a)]
    dn = [m - mult * x for m, x in zip(mid, a)]
    return (dn, mid, up)
def donchian(high: List[float], low: List[float], length: int=20):
    n = len(high)
    up = [0.0] * n
    dn = [0.0] * n
    mid = [0.0] * n
    for i in range(n):
        s = max(0, i - length + 1)
        hh = max(high[s:i + 1])
        ll = min(low[s:i + 1])
        up[i] = hh
        dn[i] = ll
        mid[i] = (hh + ll) / 2.0
    
    return (dn, mid, up)
def stochastic_kd(high: List[float], low: List[float], close: List[float], length: int=14, smooth: int=3) -> Tuple[(List[float], List[float])]:
    n = len(close)
    if n < length + 2:
        return ([50.0] * n, [50.0] * n)
    k_vals = []
    
    for i in range(n):
        start = max(0, i - length + 1)
        hh = max(high[start:i + 1])
        ll = min(low[start:i + 1])
        k = 100.0 * (close[i] - ll) / (hh - ll)
        k_vals.append(k)
    def sm(vals, s):
        out = []
        acc = 0.0
        
        for i, v in enumerate(vals):
            acc += v
            if i >= s:
                acc -= vals[i - s]
            out.append(acc / min(i + 1, s))
        return out
    
    k_sm = sm(k_vals, smooth)
    
    d_sm = sm(k_sm, smooth)
    return (k_sm, d_sm)
def cci(high: List[float], low: List[float], close: List[float], length: int=20) -> List[float]:
    tp = [(h + l + c) / 3.0 for h, l, c in zip(high, low, close)]
    sma_tp = sma(tp, length)
    n = len(tp)
    out = [0.0] * n
    for i in range(n):
        s = max(0, i - length + 1)
        seg = tp[s:i + 1]
        m = sum(seg) / len(seg)
        mad = sum((abs(x - m) for x in seg)) / len(seg)
        denom = 1e-9
        out[i] = (tp[i] - sma_tp[i]) / denom
    
    return out
def momentum_roc(series: List[float], period: int=10) -> List[float]:
    out = []
    n = len(series)
    
    for i in range(n):
        j = i - period
        out.append(series[i] - series[j])
    return out
def williams_r(high: List[float], low: List[float], close: List[float], length: int=14) -> List[float]:
    n = len(close)
    out = [0.0] * n
    for i in range(n):
        s = max(0, i - length + 1)
        hh = max(high[s:i + 1])
        ll = min(low[s:i + 1])
        if hh == ll:
            out[i] = -50.0
        out[i] = -100.0 * (hh - close[i]) / (hh - ll)
    
    return out
def parabolic_sar(high: List[float], low: List[float], step: float=0.02, max_step: float=0.2) -> List[float]:
    n = len(high)
    if n < 5:
        return [0.0] * n
    sar = [0.0] * n
    bull = True
    af = step
    ep = high[0]
    sar[0] = low[0]
    
    for i in range(1, n):
        prev = sar[i - 1]
        if bull:
            sar[i] = prev + af * (ep - prev)
            sar[i] = min(sar[i], low[i - 1])
            if low[i] < sar[i]:
                bull = False
                sar[i] = ep
                af = step
                ep = low[i]
            else:
                sar[i] = prev + af * (ep - prev)
                sar[i] = max(sar[i], high[i - 1])
                if high[i] > sar[i]:
                    bull = True
                    sar[i] = ep
                    af = step
                    ep = high[i]
        elif bull and high[i] > ep:
            ep = high[i]
            af = min(max_step, af + step)
        elif bull and low[i] < ep:
            ep = low[i]
            af = min(max_step, af + step)
    return sar
def aroon_up_down(high: List[float], low: List[float], length: int=14) -> Tuple[(List[float], List[float])]:
    n = len(high)
    up = [0.0] * n
    dn = [0.0] * n
    for i in range(n):
        start = max(0, i - length + 1)
        segH = high[start:i + 1]
        segL = low[start:i + 1]
        idxH = segH.index(max(segH))
        idxL = segL.index(min(segL))
        up[i] = 100.0 * (len(segH) - 1 - idxH) / max(1, length - 1)
        dn[i] = 100.0 * (len(segL) - 1 - idxL) / max(1, length - 1)
    
    return (up, dn)
def adx(high: List[float], low: List[float], close: List[float], length: int=14):
    n = len(close)
    if n < length + 2:
        return ([0.0] * n, [0.0] * n, [0.0] * n)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = high[i] - high[i - 1]
        dn = low[i - 1] - low[i]
        plus_dm[i] = 0.0
        minus_dm[i] = 0.0
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    def wilder(vals, length):
        out = [0.0] * n
        s = sum(vals[1:length + 1])
        while length < n:
            out[length] = s
            for i in range(length + 1, n):
                out[i] = out[i - 1] - out[i - 1] / length + vals[i]
            for i in range(0, length):
                out[i] = out[length]
            return out
        for i in range(n):
            out[i] = s
        
        return out
    
    atr_w = wilder(tr, length)
    
    pDM = wilder(plus_dm, length)
    mDM = wilder(minus_dm, length)
    plus_di = [100.0 * pDM[i] / atr_w[i] for i in range(n)]
    minus_di = [100.0 * mDM[i] / atr_w[i] for i in range(n)]
    dx = [0.0] * n
    for i in range(n):
        denom = max(1e-9, plus_di[i] + minus_di[i])
        dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / denom
    adx_line = ema(dx, length)
    return (adx_line, plus_di, minus_di)
def supertrend(high: List[float], low: List[float], close: List[float], length: int=10, mult: float=3.0) -> Tuple[(List[float], List[bool])]:
    n = len(close)
    if n < length + 2:
        return ([0.0] * n, [True] * n)
    a = atr(high, low, close, length)
    hl2 = [(h + l) / 2 for h, l in zip(high, low)]
    upper = [hl2[i] + mult * a[i] for i in range(n)]
    lower = [hl2[i] - mult * a[i] for i in range(n)]
    final_upper = upper[:]
    final_lower = lower[:]
    for i in range(1, n):
        if not upper[i] < final_upper[i - 1]:
            pass
        final_upper[i] = final_upper[i - 1]
        if not lower[i] > final_lower[i - 1]:
            pass
        final_lower[i] = final_lower[i - 1]
    st = [0.0] * n
    bull = [True] * n
    for i in range(n):
        if i == 0:
            st[i] = final_upper[i]
            bull[i] = True
        elif st[i - 1] == final_upper[i - 1] and close[i] <= final_upper[i]:
            st[i] = final_upper[i]
            bull[i] = False
        elif st[i - 1] == final_upper[i - 1] and close[i] > final_upper[i]:
            st[i] = final_lower[i]
            bull[i] = True
        elif st[i - 1] == final_lower[i - 1] and close[i] >= final_lower[i]:
            st[i] = final_lower[i]
            bull[i] = True
        elif st[i - 1] == final_lower[i - 1] and close[i] < final_lower[i]:
            st[i] = final_upper[i]
            bull[i] = False
        st[i] = final_upper[i]
        bull[i] = True
    
    return (st, bull)
def heikin_ashi(candles: List[Dict]):
    n = len(candles)
    ha_o = [0.0] * n
    ha_h = [0.0] * n
    ha_l = [0.0] * n
    ha_c = [0.0] * n
    for i, c in enumerate(candles):
        o, h, l, cl = (c["open"], c["high"], c["low"], c["close"])
        ha_c[i] = (o + h + l + cl) / 4.0
        if i == 0:
            ha_o[i] = (o + cl) / 2.0
        else:
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2.0
        ha_h[i] = max(h, ha_o[i], ha_c[i])
        ha_l[i] = min(l, ha_o[i], ha_c[i])
    
    return (ha_o, ha_h, ha_l, ha_c)
def bulls_bears_power(high: List[float], low: List[float], close: List[float], ema_len: int=13) -> Tuple[(List[float], List[float])]:
    e = ema(close, ema_len)
    
    bulls = [h - e[i] for i, h in enumerate(high)]
    bears = [l - e[i] for i, l in enumerate(low)]
    return (bulls, bears)
def zigzag_pivots(high: List[float], low: List[float], dev: float=0.5) -> List[int]:
    n = len(high)
    piv = [0] * n
    if n < 10:
        return piv
    last = low[0]
    last_idx = 0
    trend = 1
    
    for i in range(1, n):
        up = (high[i] - last) / max(1e-9, abs(last)) * 100.0
        dn = (last - low[i]) / max(1e-9, abs(last)) * 100.0
        if trend >= 0:
            if up >= dev:
                last = high[i]
                last_idx = i
                trend = 1
            elif dn >= dev:
                piv[last_idx] = 1
                last = low[i]
                last_idx = i
                trend = -1
        elif dn >= dev:
            last = low[i]
            last_idx = i
            trend = -1
        elif up >= dev:
            piv[last_idx] = -1
            last = high[i]
            last_idx = i
            trend = 1
    return piv
def detect_patterns(candles: List[Dict]) -> int:
    if len(candles) < 3:
        return 0
    score = 0
    last = candles[-1]
    prev = candles[-2]
    
    if is_bull(last) and is_bear(prev) and last["open"] <= prev["close"] and last["close"] >= prev["open"]:
        score += 2
    
    elif is_bear(last) and is_bull(prev) and last["open"] >= prev["close"] and last["close"] <= prev["open"]:
        score -= 2
    body = candle_body(last)
    
    rng = candle_range(last)
    
    if rng > 0:
        upper_shadow = last["high"] - max(last["open"], last["close"])
        lower_shadow = min(last["open"], last["close"]) - last["low"]
        if lower_shadow > 2 * body and upper_shadow < body:
            score += 1
        elif upper_shadow > 2 * body and lower_shadow < body:
            score -= 1
    return score
def _prep_ohlc(candles: List[Dict], n: int=200):
    c = candles
    
    O = [x["open"] for x in c]
    H = [x["high"] for x in c]
    L = [x["low"] for x in c]
    C = [x["close"] for x in c]
    return (O, H, L, C, c)
STRATEGY_REGISTRY: Dict[(str, Callable)] = {}
VOTING_EXCLUDE = {"MARKET_LIQUIDITY", "SMART_VOTE_MTF", "SMART_VOTE", "MARKET_DIRECTION"}
STRATEGY_CATEGORIES: Dict[(str, str)] = {}
def register_strategy(name: str, fn: Callable, category: str="GENERAL"):
    STRATEGY_REGISTRY[name] = fn; STRATEGY_CATEGORIES[name] = category
def S_JOKER(candles: List[Dict]):
    if len(candles) < 200:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    e50 = ema(C, 50)
    e200 = ema(C, 200)
    rsi_prev = rsi(C[:-1], 14)
    rsi_now = rsi(C, 14)
    if len(rsi_prev) < 1 or len(rsi_now) < 1:
        return (None, 0.0)
    idx = -1
    if e50[idx] > e200[idx] and rsi_prev[-1] < 45 and rsi_now[idx] > rsi_prev[-1]:
        return ("CALL", 0.85)
    elif e50[idx] < e200[idx] and rsi_prev[-1] > 55 and rsi_now[idx] < rsi_prev[-1]:
        return ("PUT", 0.85)
    
    return (None, 0.0)
def S_MOMENTUM(candles: List[Dict]):
    if len(candles) < 15:
        return (None, 0.0)
    last = candles[-1]
    rng = candle_range(last)
    if rng == 0:
        return (None, 0.0)
    strength_pct = candle_body(last) / rng
    if strength_pct <= 0.6:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    rsi_prev = rsi(C[:-1], 14)
    rsi_now = rsi(C, 14)
    if len(rsi_prev) < 1 or len(rsi_now) < 1:
        return (None, 0.0)
    elif is_bull(last) and rsi_now[-1] > rsi_prev[-1]:
        return ("CALL", min(1.0, strength_pct + 0.1))
    elif is_bear(last) and rsi_now[-1] < rsi_prev[-1]:
        return ("PUT", min(1.0, strength_pct + 0.1))
    
    return (None, 0.0)
def S_RSI_EXTREME(candles: List[Dict]):
    if len(candles) < 35:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    rsi_prev = rsi(C[:-1], 14)
    rsi_now = rsi(C, 14)
    e20 = ema(C, 20)
    last_price = C[-1]
    if not rsi_prev and rsi_now and e20:
        return (None, 0.0)
    elif rsi_prev[-1] < 35 and rsi_now[-1] > rsi_prev[-1] and last_price > e20[-1]:
        return ("CALL", 0.82)
    elif rsi_prev[-1] > 65 and rsi_now[-1] < rsi_prev[-1] and last_price < e20[-1]:
        return ("PUT", 0.82)
    
    return (None, 0.0)
def S_BOLLINGER_REVERSAL(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    dn, ma, up = bollinger(C, 20, 2.0)
    rsi_now = rsi(C, 14)
    last_price = C[-1]
    if not dn and up and rsi_now:
        return (None, 0.0)
    elif last_price <= dn[-1] and rsi_now[-1] < 40:
        return ("CALL", 0.83)
    elif last_price >= up[-1] and rsi_now[-1] > 60:
        return ("PUT", 0.83)
    
    return (None, 0.0)
def S_AB_PATTERN(candles: List[Dict]):
    if len(candles) < 8:
        return (None, 0.0)
    elif is_bull(candles[-1]) and is_bull(candles[-2]) and is_bear(candles[-3]) and is_bull(candles[-4]):
        return ("CALL", 0.78)
    elif is_bear(candles[-1]) and is_bear(candles[-2]) and is_bull(candles[-3]) and is_bear(candles[-4]):
        return ("PUT", 0.78)
    
    return (None, 0.0)
def _ema_cross(fast: int, slow: int):
    def fn(candles):
        if len(candles) < slow + 5:
            return (None, 0.0)
        C = [c["close"] for c in candles]
        ef = ema(C, fast)
        es = ema(C, slow)
        if ef[-2] <= es[-2] and ef[-1] > es[-1]:
            return ("CALL", 0.8)
        elif ef[-2] >= es[-2] and ef[-1] < es[-1]:
            return ("PUT", 0.8)
        
        return (None, 0.0)
    
    return fn
def _ema_pullback(period: int):
    def fn(candles):
        if len(candles) < period * 3:
            return (None, 0.0)
        O, H, L, C, _ = _prep_ohlc(candles, period * 3)
        e = ema(C, period)
        if len(e) < 3:
            return (None, 0.0)
        elif C[-2] <= e[-2] and C[-1] > e[-1]:
            return ("CALL", 0.75)
        elif C[-2] >= e[-2] and C[-1] < e[-1]:
            return ("PUT", 0.75)
        
        return (None, 0.0)
    
    return fn
def S_MACD_CROSS(candles: List[Dict]):
    if len(candles) < 40:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    m, s = macd_line(C)
    if len(m) < 3:
        return (None, 0.0)
    elif m[-2] <= s[-2] and m[-1] > s[-1]:
        return ("CALL", 0.8)
    elif m[-2] >= s[-2] and m[-1] < s[-1]:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_MACD_ZERO(candles: List[Dict]):
    if len(candles) < 40:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    m, _ = macd_line(C)
    if len(m) < 3:
        return (None, 0.0)
    elif m[-2] <= 0 and m[-1] > 0:
        return ("CALL", 0.75)
    elif m[-2] >= 0 and m[-1] < 0:
        return ("PUT", 0.75)
    
    return (None, 0.0)
def S_SUPERTREND_FLIP(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 200)
    _, bull = supertrend(H, L, C, 10, 3.0)
    if len(bull) < 3:
        return (None, 0.0)
    elif bull[-2] and bull[-1]:
        return ("CALL", 0.85)
    elif not bull[-2] and bull[-1]:
        return ("PUT", 0.85)
    
    return (None, 0.0)
def S_HA_TREND(candles: List[Dict]):
    if len(candles) < 50:
        return (None, 0.0)
    O, H, L, C, c = _prep_ohlc(candles, 120)
    ha_o, ha_h, ha_l, ha_c = heikin_ashi(c)
    _, bull = supertrend(H, L, C, 10, 3.0)
    if ha_c[-1] > ha_o[-1] and bull[-1]:
        return ("CALL", 0.8)
    elif not ha_c[-1] < ha_o[-1] and bull[-1]:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_ADX_TREND(candles: List[Dict]):
    if len(candles) < 40:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 200)
    adx_line, di_plus, di_minus = adx(H, L, C, 14)
    if adx_line[-1] < 25:
        return (None, 0.0)
    strength = min(1.0, adx_line[-1] / 50.0)
    if di_plus[-1] > di_minus[-1]:
        return ("CALL", strength)
    elif di_minus[-1] > di_plus[-1]:
        return ("PUT", strength)
    
    return (None, 0.0)
def S_PSAR_FLIP(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 150)
    ps = parabolic_sar(H, L)
    if len(ps) < 3:
        return (None, 0.0)
    was_below_prev = ps[-2] < C[-2]
    
    is_below_now = ps[-1] < C[-1]
    if was_below_prev and is_below_now:
        return ("CALL", 0.78)
    elif not was_below_prev and is_below_now:
        return ("PUT", 0.78)
    
    return (None, 0.0)
def S_STOCH_CROSS(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 120)
    k, d = stochastic_kd(H, L, C, 14, 3)
    if len(k) < 3:
        return (None, 0.0)
    elif k[-2] < d[-2] and k[-1] > d[-1] and k[-1] < 30:
        return ("CALL", 0.8)
    elif k[-2] > d[-2] and k[-1] < d[-1] and k[-1] > 70:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_CCI_EXTREME(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 160)
    cc = cci(H, L, C, 20)
    if not cc:
        return (None, 0.0)
    elif cc[-1] <= -150:
        return ("CALL", 0.78)
    elif cc[-1] >= 150:
        return ("PUT", 0.78)
    
    return (None, 0.0)
def S_WILLIAMS_R(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 100)
    wr = williams_r(H, L, C, 14)
    if not wr:
        return (None, 0.0)
    elif wr[-1] <= -80 and wr[-2] <= -80 and wr[-1] > wr[-2]:
        return ("CALL", 0.77)
    elif wr[-1] >= -20 and wr[-2] >= -20 and wr[-1] < wr[-2]:
        return ("PUT", 0.77)
    
    return (None, 0.0)
def S_RSI_DIVERGENCE(candles: List[Dict]):
    if len(candles) < 40:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    L_arr = [c["low"] for c in candles]
    H_arr = [c["high"] for c in candles]
    rsi_v = rsi(C, 14)
    look = 15
    if len(C) < look:
        return (None, 0.0)
    recent_low_idx = len(C) - 1 - L_arr[-look:].index(min(L_arr[-look:]))
    
    earlier_low_idx = recent_low_idx - look // 2
    if earlier_low_idx < 0:
        return (None, 0.0)
    elif L_arr[recent_low_idx] < L_arr[earlier_low_idx] and rsi_v[recent_low_idx] > rsi_v[earlier_low_idx] and rsi_v[-1] < 40:
        return ("CALL", 0.8)
    recent_high_idx = len(C) - 1 - H_arr[-look:].index(max(H_arr[-look:]))
    earlier_high_idx = recent_high_idx - look // 2
    if earlier_high_idx < 0:
        return (None, 0.0)
    elif H_arr[recent_high_idx] > H_arr[earlier_high_idx] and rsi_v[recent_high_idx] < rsi_v[earlier_high_idx] and rsi_v[-1] > 60:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def _donchian_break(length: int):
    def fn(candles):
        if len(candles) < length + 5:
            return (None, 0.0)
        O, H, L, C, _ = _prep_ohlc(candles, length * 3)
        dn, mid, up = donchian(H, L, length)
        if not up:
            return (None, 0.0)
        elif C[-1] > up[-2]:
            return ("CALL", 0.82)
        elif C[-1] < dn[-2]:
            return ("PUT", 0.82)
        
        return (None, 0.0)
    
    return fn
def _keltner_break(mult: float):
    def fn(candles):
        if len(candles) < 30:
            return (None, 0.0)
        O, H, L, C, _ = _prep_ohlc(candles, 150)
        dn, mid, up = keltner(H, L, C, 20, mult)
        if C[-1] > up[-1]:
            return ("CALL", 0.8)
        elif C[-1] < dn[-1]:
            return ("PUT", 0.8)
        
        return (None, 0.0)
    
    return fn
def _bb_squeeze(ratio: float):
    def fn(candles):
        if len(candles) < 30:
            return (None, 0.0)
        C = [c["close"] for c in candles]
        O, H, L, _C, _ = _prep_ohlc(candles, 100)
        dn, ma, up = bollinger(C, 20, 2.0)
        kdn, kmid, kup = keltner(H, L, _C, 20, 1.5)
        if not up:
            return (None, 0.0)
        bbw = up[-1] - dn[-1]
        kcw = kup[-1] - kdn[-1]
        if bbw < kcw * ratio:
            if C[-1] > ma[-1] and C[-1] > C[-2]:
                return ("CALL", 0.76)
            elif C[-1] < ma[-1] and C[-1] < C[-2]:
                return ("PUT", 0.76)
        
        return (None, 0.0)
    
    return fn
def S_ATR_BREAKOUT(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 180)
    center = ema(C, 21)
    a = atr(H, L, C, 14)
    up = [m + 1.5 * x for m, x in zip(center, a)]
    dn = [m - 1.5 * x for m, x in zip(center, a)]
    if C[-1] > up[-1]:
        return ("CALL", 0.81)
    elif C[-1] < dn[-1]:
        return ("PUT", 0.81)
    
    return (None, 0.0)
def S_AROON_TREND(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 100)
    a_up, a_dn = aroon_up_down(H, L, 14)
    if a_up[-1] > 70 and a_dn[-1] < 30:
        return ("CALL", 0.78)
    elif a_dn[-1] > 70 and a_up[-1] < 30:
        return ("PUT", 0.78)
    
    return (None, 0.0)
def S_ENGULFING(candles: List[Dict]):
    if len(candles) < 5:
        return (None, 0.0)
    last = candles[-1]
    prev = candles[-2]
    if is_bull(last) and is_bear(prev) and last["open"] <= prev["close"] and last["close"] >= prev["open"] and candle_body(last) > candle_body(prev) * 1.1:
        return ("CALL", 0.8)
    elif is_bear(last) and is_bull(prev) and last["open"] >= prev["close"] and last["close"] <= prev["open"] and candle_body(last) > candle_body(prev) * 1.1:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_THREE_SOLDIERS(candles: List[Dict]):
    if len(candles) < 5:
        return (None, 0.0)
    last3 = candles[-3:]
    if all((is_bull(c) for c in last3)) and all((candle_body(c) / max(candle_range(c), 1e-9) > 0.5 for c in last3)):
        return ("CALL", 0.78)
    elif all((is_bear(c) for c in last3)) and all((candle_body(c) / max(candle_range(c), 1e-9) > 0.5 for c in last3)):
        return ("PUT", 0.78)
    
    return (None, 0.0)
def S_HAMMER(candles: List[Dict]):
    if len(candles) < 6:
        return (None, 0.0)
    last = candles[-1]
    rng = candle_range(last)
    if rng == 0:
        return (None, 0.0)
    body = candle_body(last)
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]
    if lower > 2 * body and upper < body and all((is_bear(c) for c in candles[-4:-1])):
        return ("CALL", 0.79)
    elif upper > 2 * body and lower < body and all((is_bull(c) for c in candles[-4:-1])):
        return ("PUT", 0.79)
    
    return (None, 0.0)
def S_PINBAR(candles: List[Dict]):
    if len(candles) < 5:
        return (None, 0.0)
    last = candles[-1]
    rng = candle_range(last)
    if rng == 0:
        return (None, 0.0)
    body = candle_body(last)
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]
    if lower > 2.5 * body and lower > upper * 2:
        return ("CALL", 0.76)
    elif upper > 2.5 * body and upper > lower * 2:
        return ("PUT", 0.76)
    
    return (None, 0.0)
def S_INSIDE_BAR(candles: List[Dict]):
    if len(candles) < 4:
        return (None, 0.0)
    mom = candles[-2]
    inside = candles[-1]
    if inside["high"] <= mom["high"] and inside["low"] >= mom["low"]:
        if is_bull(inside):
            return ("CALL", 0.72)
        elif is_bear(inside):
            return ("PUT", 0.72)
    
    return (None, 0.0)
def S_OTC_FORTRESS(candles: List[Dict]):
    if len(candles) < 200:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 250)
    e_fast = ema(C, 34)
    e_slow = ema(C, 144)
    rsi_v = rsi(C, 14)
    dn, ma, up = bollinger(C, 20, 2.0)
    adx_line, di_plus, di_minus = adx(H, L, C, 14)
    score_call = 0.0
    score_put = 0.0
    
    if e_fast[-1] > e_slow[-1]:
        score_call += 0.5
    else:
        score_put += 0.5
    
    if adx_line[-1] >= 18:
        if di_plus[-1] > di_minus[-1]:
            score_call += 0.5
        else:
            score_put += 0.5
    
    elif C[-1] < dn[-1] and rsi_v[-1] < 35:
        score_call += 1.0
    
    elif C[-1] > up[-1] and rsi_v[-1] > 65:
        score_put += 1.0
    elif candle_body_pct(candles[-1]) < 0.25:
        return (None, 0.0)
    elif score_call >= 1.5 and score_call > score_put:
        return ("CALL", min(1.0, score_call / 2.0))
    elif score_put >= 1.5 and score_put > score_call:
        return ("PUT", min(1.0, score_put / 2.0))
    
    return (None, 0.0)
def S_OTC_HEIKEN(candles: List[Dict]):
    if len(candles) < 40:
        return (None, 0.0)
    ha_o, ha_h, ha_l, ha_c = heikin_ashi(candles)
    if ha_c[-1] > ha_o[-1] and ha_c[-2] < ha_o[-2] and ha_c[-3] < ha_o[-3]:
        return ("CALL", 0.77)
    elif ha_c[-1] < ha_o[-1] and ha_c[-2] > ha_o[-2] and ha_c[-3] > ha_o[-3]:
        return ("PUT", 0.77)
    
    return (None, 0.0)
def S_OTC_TRIPLE_MA(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    m5 = sma(C, 5)
    m10 = sma(C, 10)
    m20 = sma(C, 20)
    if m5[-1] > m10[-1] > m20[-1]:
        pass
    if m5[-2] <= m10[-2]:
        return ("CALL", 0.79)
    elif m5[-1] < m10[-1] < m20[-1]:
        pass
    else:
        return (None, 0.0)
    if m5[-2] >= m10[-2]:
        return ("PUT", 0.79)
    
    return (None, 0.0)
def S_OTC_BB_RSI(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    dn, ma, up = bollinger(C, 20, 2.5)
    rsi_v = rsi(C, 14)
    if C[-1] < dn[-1] and rsi_v[-1] < 30 and is_bull(candles[-1]):
        return ("CALL", 0.81)
    elif C[-1] > up[-1] and rsi_v[-1] > 70 and is_bear(candles[-1]):
        return ("PUT", 0.81)
    
    return (None, 0.0)
def S_PRICE_ACTION(candles: List[Dict]):
    if len(candles) < 10:
        return (None, 0.0)
    recent = candles[-5:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    hh = all((highs[i] >= highs[i - 1] for i in range(1, len(highs))))
    
    ll = all((lows[i] <= lows[i - 1] for i in range(1, len(lows))))
    last = candles[-1]
    if hh and is_bull(last) and candle_body_pct(last) > 0.5:
        return ("CALL", 0.74)
    elif ll and is_bear(last) and candle_body_pct(last) > 0.5:
        return ("PUT", 0.74)
    
    return (None, 0.0)
def S_RANGE_FADE(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 80)
    adx_line, _, _ = adx(H, L, C, 14)
    if adx_line[-1] > 20:
        return (None, 0.0)
    recent_high = max(H[-20:])
    recent_low = min(L[-20:])
    rng = recent_high - recent_low
    if rng == 0:
        return (None, 0.0)
    pos = (C[-1] - recent_low) / rng
    if pos <= 0.15:
        return ("CALL", 0.72)
    elif pos >= 0.85:
        return ("PUT", 0.72)
    
    return (None, 0.0)
def S_BULLS_BEARS_POWER(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    O, H, L, C, _ = _prep_ohlc(candles, 80)
    bulls, bears = bulls_bears_power(H, L, C, 13)
    e = ema(C, 13)
    if bulls[-1] > 0 and bears[-1] < 0 and bulls[-1] > abs(bears[-1]) and C[-1] > e[-1]:
        return ("CALL", 0.73)
    elif bulls[-1] < 0 and bears[-1] < 0 and abs(bears[-1]) > bulls[-1] and C[-1] < e[-1]:
        return ("PUT", 0.73)
    
    return (None, 0.0)
register_strategy("JOKER", S_JOKER, "CORE")
register_strategy("MOMENTUM", S_MOMENTUM, "CORE")
register_strategy("RSI_EXTREME", S_RSI_EXTREME, "CORE")
register_strategy("BOLLINGER_REVERSAL", S_BOLLINGER_REVERSAL, "CORE")
register_strategy("AB_PATTERN", S_AB_PATTERN, "CORE")
register_strategy("EMA_CROSS_9_21", _ema_cross(9, 21), "TREND")
register_strategy("EMA_CROSS_12_26", _ema_cross(12, 26), "TREND")
register_strategy("EMA_CROSS_21_50", _ema_cross(21, 50), "TREND")
register_strategy("EMA_CROSS_50_200", _ema_cross(50, 200), "TREND")
register_strategy("EMA_PULLBACK_21", _ema_pullback(21), "TREND")
register_strategy("EMA_PULLBACK_50", _ema_pullback(50), "TREND")
register_strategy("MACD_CROSS", S_MACD_CROSS, "TREND")
register_strategy("MACD_ZERO", S_MACD_ZERO, "TREND")
register_strategy("SUPERTREND_FLIP", S_SUPERTREND_FLIP, "TREND")
register_strategy("HEIKIN_ASHI_TREND", S_HA_TREND, "TREND")
register_strategy("ADX_TREND", S_ADX_TREND, "TREND")
register_strategy("PSAR_FLIP", S_PSAR_FLIP, "TREND")
register_strategy("STOCH_CROSS", S_STOCH_CROSS, "REVERSAL")
register_strategy("CCI_EXTREME", S_CCI_EXTREME, "REVERSAL")
register_strategy("WILLIAMS_R", S_WILLIAMS_R, "REVERSAL")
register_strategy("RSI_DIVERGENCE", S_RSI_DIVERGENCE, "REVERSAL")
register_strategy("DONCHIAN_BREAK_20", _donchian_break(20), "BREAKOUT")
register_strategy("DONCHIAN_BREAK_50", _donchian_break(50), "BREAKOUT")
register_strategy("KELTNER_BREAK_15", _keltner_break(1.5), "BREAKOUT")
register_strategy("KELTNER_BREAK_20", _keltner_break(2.0), "BREAKOUT")
register_strategy("BB_SQUEEZE", _bb_squeeze(0.7), "BREAKOUT")
register_strategy("ATR_BREAKOUT", S_ATR_BREAKOUT, "BREAKOUT")
register_strategy("AROON_TREND", S_AROON_TREND, "BREAKOUT")
register_strategy("ENGULFING", S_ENGULFING, "PATTERN")
register_strategy("THREE_SOLDIERS", S_THREE_SOLDIERS, "PATTERN")
register_strategy("HAMMER", S_HAMMER, "PATTERN")
register_strategy("PINBAR", S_PINBAR, "PATTERN")
register_strategy("INSIDE_BAR", S_INSIDE_BAR, "PATTERN")
register_strategy("OTC_FORTRESS", S_OTC_FORTRESS, "OTC")
register_strategy("OTC_HEIKEN", S_OTC_HEIKEN, "OTC")
register_strategy("OTC_TRIPLE_MA", S_OTC_TRIPLE_MA, "OTC")
register_strategy("OTC_BB_RSI", S_OTC_BB_RSI, "OTC")
register_strategy("PRICE_ACTION", S_PRICE_ACTION, "PRICE_ACTION")
register_strategy("RANGE_FADE", S_RANGE_FADE, "PRICE_ACTION")
register_strategy("BULLS_BEARS_POWER", S_BULLS_BEARS_POWER, "PRICE_ACTION")
def get_all_strategy_names() -> List[str]:
    return list(STRATEGY_REGISTRY.keys())
def get_strategies_by_category(category: str) -> List[str]:
    return [n for n, c in STRATEGY_CATEGORIES.items() if c == category]
def get_strategy_color(name: str) -> str:
    cat = STRATEGY_CATEGORIES.get(name, "GENERAL")
    return {"CORE": "bright_yellow", "TREND": "green", "REVERSAL": "magenta", "BREAKOUT": "cyan", "PATTERN": "blue", "OTC": "bright_red", "PRICE_ACTION": "white"}.get(cat, "white")
def S_VWAP_REVERSION(candles, period=20):
    if len(candles) < period + 5:
        return (None, 0.0)
    closes = [c["close"] for c in candles[-period:]]
    avg = sum(closes) / len(closes)
    px = closes[-1]
    diff_pct = 0
    if diff_pct < -0.25:
        return ("CALL", min(1.0, abs(diff_pct) * 2.0))
    elif diff_pct > 0.25:
        return ("PUT", min(1.0, abs(diff_pct) * 2.0))
    
    return (None, 0.0)
def S_TRIPLE_EMA(candles):
    if len(candles) < 25:
        return (None, 0.0)
    closes = [c["close"] for c in candles]
    e5_list = ema(closes, 5)
    e13_list = ema(closes, 13)
    e21_list = ema(closes, 21)
    if not e5_list and e13_list and e21_list:
        return (None, 0.0)
    e5 = e5_list[-1]
    e13 = e13_list[-1]
    e21 = e21_list[-1]
    last = closes[-1]
    match e13:
        case _ if e5 > e13 > e21 and last > e5:
            return ("CALL", 0.85)
        case _ if e5 < e13 < e21:
            return (None, 0.0)
    
    match e13:
        case _:
            return ("PUT", 0.85)
    return (None, 0.0)
def S_FRACTAL_REVERSAL(candles, lookback=5):
    if len(candles) < lookback * 2 + 2:
        return (None, 0.0)
    mid_idx = -3
    
    win = candles[mid_idx - lookback // 2:mid_idx + lookback // 2 + 1]
    if len(win) < lookback:
        return (None, 0.0)
    mid = candles[mid_idx]
    highs = [c["high"] for c in win]
    lows = [c["low"] for c in win]
    if mid["high"] == max(highs) and candles[-1]["close"] < candles[-2]["close"]:
        return ("PUT", 0.7)
    elif mid["low"] == min(lows) and candles[-1]["close"] > candles[-2]["close"]:
        return ("CALL", 0.7)
    
    return (None, 0.0)
def S_ROC_MOMENTUM(candles, period=10):
    if len(candles) < period + 2:
        return (None, 0.0)
    cur = candles[-1]["close"]
    prev = candles[-1 - period]["close"]
    if prev == 0:
        return (None, 0.0)
    roc_val = (cur - prev) / prev * 100
    if roc_val > 0.15 and candles[-1]["close"] > candles[-2]["close"]:
        return ("CALL", min(1.0, abs(roc_val) * 3))
    elif roc_val < -0.15 and candles[-1]["close"] < candles[-2]["close"]:
        return ("PUT", min(1.0, abs(roc_val) * 3))
    
    return (None, 0.0)
def S_HARAMI(candles):
    if len(candles) < 5:
        return (None, 0.0)
    prev = candles[-2]
    cur = candles[-1]
    if is_bear(prev) and is_bull(cur) and cur["high"] < prev["open"] and cur["low"] > prev["close"]:
        return ("CALL", 0.75)
    elif is_bull(prev) and is_bear(cur) and cur["high"] < prev["close"] and cur["low"] > prev["open"]:
        return ("PUT", 0.75)
    
    return (None, 0.0)
def S_MORNING_STAR(candles):
    if len(candles) < 5:
        return (None, 0.0)
    c1 = candles[-3]; c2 = candles[-2]; c3 = candles[-1]
    if is_bear(c1) and abs(c2["close"] - c2["open"]) < candle_body(c1) * 0.4 and is_bull(c3) and c3["close"] > (c1["open"] + c1["close"]) / 2:
        return ("CALL", 0.8)
    elif is_bull(c1) and abs(c2["close"] - c2["open"]) < candle_body(c1) * 0.4 and is_bear(c3) and c3["close"] < (c1["open"] + c1["close"]) / 2:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_DOJI_REVERSAL(candles):
    if len(candles) < 8:
        return (None, 0.0)
    cur = candles[-1]
    body = abs(cur["close"] - cur["open"])
    rng = cur["high"] - cur["low"]
    if rng == 0:
        return (None, 0.0)
    elif body / rng > 0.15:
        return (None, 0.0)
    recent_closes = [c["close"] for c in candles[-8:-1]]
    if cur["close"] >= max(recent_closes):
        return ("PUT", 0.65)
    elif cur["close"] <= min(recent_closes):
        return ("CALL", 0.65)
    
    return (None, 0.0)
def S_BB_BOUNCE(candles, period=20):
    if len(candles) < period + 3:
        return (None, 0.0)
    closes = [c["close"] for c in candles]
    dn, mid, up = bollinger(closes, period, 2.0)
    if not dn and up:
        return (None, 0.0)
    lower = dn[-1]
    upper = up[-1]
    prev = candles[-2]
    cur = candles[-1]
    if prev["low"] <= lower and cur["close"] > cur["open"] and cur["close"] > prev["close"]:
        return ("CALL", 0.8)
    elif prev["high"] >= upper and cur["close"] < cur["open"] and cur["close"] < prev["close"]:
        return ("PUT", 0.8)
    
    return (None, 0.0)
def S_RSI_CROSS_50(candles, period=14):
    if len(candles) < period + 3:
        return (None, 0.0)
    closes = [c["close"] for c in candles]
    rsi_list = rsi(closes, period)
    if rsi_list and len(rsi_list) < 2:
        return (None, 0.0)
    rsi_prev = rsi_list[-2]
    rsi_cur = rsi_list[-1]
    if rsi_prev < 50 and rsi_cur > 50 and rsi_cur < 70:
        return ("CALL", 0.7)
    elif rsi_prev > 50 and rsi_cur < 50 and rsi_cur > 30:
        return ("PUT", 0.7)
    
    return (None, 0.0)
def S_STOCHASTIC_DIVERGENCE(candles):
    if len(candles) < 30:
        return (None, 0.0)
    try:
        win_now = candles[-20:]
        h_now = [c["high"] for c in win_now]
        l_now = [c["low"] for c in win_now]
        c_now = [c["close"] for c in win_now]
        win_before = candles[-30:-10]
        h_before = [c["high"] for c in win_before]
        l_before = [c["low"] for c in win_before]
        c_before = [c["close"] for c in win_before]
        kd_now = stochastic_kd(h_now, l_now, c_now, 14, 3)
        kd_before = stochastic_kd(h_before, l_before, c_before, 14, 3)
        if not kd_now and kd_now[0] and kd_before and kd_before[0]:
            pass
    finally:
        return (None, 0.0)
        k_now_list, d_now_list = kd_now
        k_before_list, d_before_list = kd_before
        if not k_now_list and k_before_list:
            pass
        return (None, 0.0)
        k_now = k_now_list[-1]
        k_before = k_before_list[-1]
        closes_now = [c["close"] for c in candles[-3:]]
        closes_before = [c["close"] for c in candles[-14:-11]]
        if min(closes_now) < min(closes_before) and k_now > k_before and k_now < 30:
            pass
        return ("CALL", 0.75)
        if max(closes_now) > max(closes_before) or k_now < k_before or k_now > 70:
            pass
        return ("PUT", 0.75)
        return (None, 0.0)
        if Exception:
            Exception
        return (None, 0.0)
def S_TREND_STRENGTH(candles, period=14):
    if len(candles) < period + 5:
        return (None, 0.0)
    try:
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        closes = [c["close"] for c in candles]
        adx_list = adx(highs, lows, closes, period)
        if not adx_list:
            pass
    finally:
        return (None, 0.0)
        adx_val = adx_list[-1]
        if adx_val < 20:
            pass
        return (None, 0.0)
        e5_list = ema(closes, 5)
        e20_list = ema(closes, 20)
        if not e5_list and e20_list:
            pass
        return (None, 0.0)
        e5 = e5_list[-1]
        e20 = e20_list[-1]
        strength = min(1.0, adx_val / 40)
        if e5 > e20:
            pass
        return ("CALL", strength)
        if e5 < e20:
            pass
        return ("PUT", strength)
        return (None, 0.0)
        if Exception:
            Exception
        return (None, 0.0)
def S_TWO_CANDLE_MOMENTUM(candles):
    if len(candles) < 8:
        return (None, 0.0)
    c1 = candles[-2]
    c2 = candles[-1]
    r1 = c1["high"] - c1["low"]
    r2 = c2["high"] - c2["low"]
    if r1 == 0 or r2 == 0:
        return (None, 0.0)
    avg_range = sum((c["high"] - c["low"] for c in candles[-10:])) / 10
    if avg_range == 0:
        return (None, 0.0)
    elif is_bull(c1) and is_bull(c2) and r1 > avg_range * 1.0 and r2 > avg_range * 1.0 and body_pct(c2) > 0.6:
        return ("CALL", 0.75)
    elif is_bear(c1) and is_bear(c2) and r1 > avg_range * 1.0 and r2 > avg_range * 1.0 and body_pct(c2) > 0.6:
        return ("PUT", 0.75)
    
    return (None, 0.0)
def S_PIVOT_POINT(candles):
    if len(candles) < 20:
        return (None, 0.0)
    prev_high = max((c["high"] for c in candles[-20:-1]))
    prev_low = min((c["low"] for c in candles[-20:-1]))
    prev_close = candles[-2]["close"]
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high
    cur = candles[-1]
    if cur["low"] <= s1 and cur["close"] > s1 and is_bull(cur):
        return ("CALL", 0.7)
    elif cur["high"] >= r1 and cur["close"] < r1 and is_bear(cur):
        return ("PUT", 0.7)
    
    return (None, 0.0)
def S_VOLATILITY_BREAKOUT(candles, period=14):
    if len(candles) < period + 5:
        return (None, 0.0)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    atr_list = atr(highs, lows, closes, period)
    if not atr_list:
        return (None, 0.0)
    atr_val = atr_list[-1]
    if atr_val <= 0:
        return (None, 0.0)
    cur = candles[-1]
    body = abs(cur["close"] - cur["open"])
    if body > atr_val * 1.5:
        if is_bull(cur):
            return ("CALL", min(1.0, body / atr_val / 3))
        elif is_bear(cur):
            return ("PUT", min(1.0, body / atr_val / 3))
    
    return (None, 0.0)
def S_TWEEZER(candles):
    if len(candles) < 5:
        return (None, 0.0)
    c1 = candles[-2]
    c2 = candles[-1]
    tol = abs(c1["close"] - c1["open"]) * 0.1 + 1e-9
    if abs(c1["low"] - c2["low"]) < tol and is_bear(c1) and is_bull(c2):
        return ("CALL", 0.7)
    elif abs(c1["high"] - c2["high"]) < tol and is_bull(c1) and is_bear(c2):
        return ("PUT", 0.7)
    
    return (None, 0.0)
def S_GAP_FILL(candles):
    if len(candles) < 10:
        return (None, 0.0)
    prev_close = candles[-2]["close"]
    cur_open = candles[-1]["open"]
    cur_close = candles[-1]["close"]
    gap = cur_open - prev_close
    avg_body = sum((candle_body(c) for c in candles[-10:-1])) / 9
    if avg_body == 0:
        return (None, 0.0)
    elif gap > avg_body * 0.5 and cur_close < cur_open:
        return ("PUT", min(1.0, gap / avg_body / 3))
    elif gap < -avg_body * 0.5 and cur_close > cur_open:
        return ("CALL", min(1.0, abs(gap) / avg_body / 3))
    
    return (None, 0.0)
def S_TRIPLE_TOP_BOTTOM(candles):
    if len(candles) < 20:
        return (None, 0.0)
    highs = [c["high"] for c in candles[-15:]]
    lows = [c["low"] for c in candles[-15:]]
    top = max(highs)
    bot = min(lows)
    tol = (top - bot) * 0.02
    if tol == 0:
        return (None, 0.0)
    top_touches = sum((1 for h in highs))
    
    bot_touches = sum((1 for l in lows))
    cur = candles[-1]
    if top_touches >= 3 and is_bear(cur) and cur["close"] < top * 0.999:
        return ("PUT", 0.8)
    elif bot_touches >= 3 and is_bull(cur) and cur["close"] > bot * 1.001:
        return ("CALL", 0.8)
    
    return (None, 0.0)
def S_OTC_QUIET_ZONE(candles):
    if len(candles) < 25:
        return (None, 0.0)
    win = candles[-20:-1]
    ranges = [c["high"] - c["low"] for c in win]
    avg_rng = sum(ranges) / len(ranges)
    avg_rng_big = avg_rng
    if avg_rng < avg_rng_big * 0.7:
        cur = candles[-1]
        cur_rng = cur["high"] - cur["low"]
        if cur_rng > avg_rng * 2.0:
            if is_bull(cur):
                return ("CALL", 0.8)
            elif is_bear(cur):
                return ("PUT", 0.8)
    
    return (None, 0.0)
def S_FIBONACCI_RETRACEMENT(candles):
    if len(candles) < 30:
        return (None, 0.0)
    win = candles[-30:]
    swing_high = max((c["high"] for c in win))
    swing_low = min((c["low"] for c in win))
    rng = swing_high - swing_low
    if rng == 0:
        return (None, 0.0)
    closes = [c["close"] for c in candles]
    
    e10 = ema(closes, 10)
    e25 = ema(closes, 25)
    if e10 is None or e25 is None:
        return (None, 0.0)
    cur = candles[-1]
    if e10 > e25:
        fib_50 = swing_high - rng * 0.5
        fib_618 = swing_high - rng * 0.618
        if fib_618 <= cur["low"] <= fib_50:
            pass
        
    elif is_bull(cur):
        return ("CALL", 0.75)
    elif e10 < e25:
        fib_50 = swing_low + rng * 0.5
        fib_618 = swing_low + rng * 0.618
        if fib_50 <= cur["high"] <= fib_618:
            pass
        else:
            return (None, 0.0)
        if is_bear(cur):
            return ("PUT", 0.75)
    
    return (None, 0.0)
def S_KELTNER_PULLBACK(candles, period=20):
    if len(candles) < period + 5:
        return (None, 0.0)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    kelt = keltner(highs, lows, closes, period, 2.0)
    if not kelt and kelt[0]:
        return (None, 0.0)
    up_list, mid_list, dn_list = kelt
    mid = mid_list[-1]
    e5_list = ema(closes, 5)
    e20_list = ema(closes, 20)
    if not e5_list and e20_list:
        return (None, 0.0)
    e5 = e5_list[-1]
    e20 = e20_list[-1]
    cur = candles[-1]
    if e5 > e20:
        match mid:
            case _ if cur["low"] <= mid <= cur["high"]:
                return ("CALL", 0.75)
            case _ if cur["low"] <= mid and cur["low"] <= mid <= cur["high"]:
                return (None, 0.0)
    if is_bear(cur):
        return ("PUT", 0.75)
    
    return (None, 0.0)
def S_SR_REVERSAL(candles):
    if len(candles) < 25:
        return (None, 0.0)
    win = candles[-20:-1]
    res = max((c["high"] for c in win))
    sup = min((c["low"] for c in win))
    rng = res - sup
    if rng == 0:
        return (None, 0.0)
    cur = candles[-1]
    threshold = rng * 0.05
    if abs(cur["low"] - sup) < threshold and is_bull(cur):
        return ("CALL", 0.7)
    elif abs(cur["high"] - res) < threshold and is_bear(cur):
        return ("PUT", 0.7)
    
    return (None, 0.0)
def S_TIME_OF_DAY_BIAS(candles):
    if len(candles) < 8:
        return (None, 0.0)
    closes = [c["close"] for c in candles[-6:]]
    if len(closes) < 6:
        return (None, 0.0)
    n_up = sum((1 for i in range(1, len(closes))))
    n_dn = sum((1 for i in range(1, len(closes))))
    cur = candles[-1]
    if n_up >= 4 and is_bull(cur):
        return ("CALL", 0.65)
    elif n_dn >= 4 and is_bear(cur):
        return ("PUT", 0.65)
    
    return (None, 0.0)
def S_CCI_TURN(candles, period=20):
    if len(candles) < period + 3:
        return (None, 0.0)
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    cci_list = cci(highs, lows, closes, period)
    if cci_list and len(cci_list) < 2:
        return (None, 0.0)
    cci_prev = cci_list[-2]
    cci_now = cci_list[-1]
    if cci_prev < -150 and cci_now > cci_prev and cci_now < -50:
        return ("CALL", 0.75)
    elif cci_prev > 150 and cci_now < cci_prev and cci_now > 50:
        return ("PUT", 0.75)
    
    return (None, 0.0)
def S_RANGE_BREAKOUT(candles, lookback=15):
    if len(candles) < lookback + 3:
        return (None, 0.0)
    win = candles[-lookback - 1:-1]
    hi = max((c["high"] for c in win))
    lo = min((c["low"] for c in win))
    cur = candles[-1]
    rng = hi - lo
    if rng == 0:
        return (None, 0.0)
    elif cur["close"] > hi and is_bull(cur) and candle_body(cur) > rng * 0.2:
        return ("CALL", 0.8)
    elif cur["close"] < lo and is_bear(cur) and candle_body(cur) > rng * 0.2:
        return ("PUT", 0.8)
    
    return (None, 0.0)
register_strategy("VWAP_REVERSION", S_VWAP_REVERSION, "REVERSAL")
register_strategy("TRIPLE_EMA", S_TRIPLE_EMA, "TREND")
register_strategy("FRACTAL_REVERSAL", S_FRACTAL_REVERSAL, "REVERSAL")
register_strategy("ROC_MOMENTUM", S_ROC_MOMENTUM, "CORE")
register_strategy("HARAMI", S_HARAMI, "PATTERN")
register_strategy("MORNING_STAR", S_MORNING_STAR, "PATTERN")
register_strategy("DOJI_REVERSAL", S_DOJI_REVERSAL, "PATTERN")
register_strategy("BB_BOUNCE", S_BB_BOUNCE, "REVERSAL")
register_strategy("RSI_CROSS_50", S_RSI_CROSS_50, "TREND")
register_strategy("STOCHASTIC_DIVERGENCE", S_STOCHASTIC_DIVERGENCE, "REVERSAL")
register_strategy("TREND_STRENGTH", S_TREND_STRENGTH, "TREND")
register_strategy("TWO_CANDLE_MOMENTUM", S_TWO_CANDLE_MOMENTUM, "CORE")
register_strategy("PIVOT_POINT", S_PIVOT_POINT, "PRICE_ACTION")
register_strategy("VOLATILITY_BREAKOUT", S_VOLATILITY_BREAKOUT, "BREAKOUT")
register_strategy("TWEEZER", S_TWEEZER, "PATTERN")
register_strategy("GAP_FILL", S_GAP_FILL, "REVERSAL")
register_strategy("TRIPLE_TOP_BOTTOM", S_TRIPLE_TOP_BOTTOM, "REVERSAL")
register_strategy("OTC_QUIET_ZONE", S_OTC_QUIET_ZONE, "OTC")
register_strategy("FIBONACCI_RETRACEMENT", S_FIBONACCI_RETRACEMENT, "PRICE_ACTION")
register_strategy("KELTNER_PULLBACK", S_KELTNER_PULLBACK, "TREND")
register_strategy("SR_REVERSAL", S_SR_REVERSAL, "PRICE_ACTION")
register_strategy("TIME_OF_DAY_BIAS", S_TIME_OF_DAY_BIAS, "CORE")
register_strategy("CCI_TURN", S_CCI_TURN, "REVERSAL")
register_strategy("RANGE_BREAKOUT", S_RANGE_BREAKOUT, "BREAKOUT")
def detect_market_regime(candles: List[Dict]) -> Dict[(str, Any)]:
    if len(candles) < 30:
        return {"regime": "UNKNOWN", "trend_dir": None, "strength": 0.0, "adx": 0.0, "atr_pct": 0.0, "is_trending": False, "is_ranging": False}
    H = [c["high"] for c in candles]
    
    L = [c["low"] for c in candles]
    C = [c["close"] for c in candles]
    
    try:
        adx_result = adx(H, L, C, 14)
        if isinstance(adx_result, tuple) and len(adx_result) >= 1:
            adx_list = adx_result[0]
        else:
            adx_list = adx_result
        adx_v = 0.0
    finally:
        pass
    if Exception:
        Exception
        adx_v = 0.0
    try:
        atr_vals = atr(H, L, C, 14)
        atr_v = 0.0
        atr_pct = 0.0
    finally:
        pass
    if Exception:
        Exception
        atr_pct = 0.0
    try:
        e20 = ema(C, 20)
        e50 = e20
        if e20 and e50:
            trend_dir = None
            if len(e20) >= 10:
                slope = 0.0
                slope_strength = min(1.0, abs(slope) * 1000)
            else:
                slope_strength = 0.0
        else:
            trend_dir = None
            slope_strength = 0.0
    finally:
        pass
    if Exception:
        Exception
        trend_dir = None
        slope_strength = 0.0
    is_trending = adx_v >= 22.0
    is_ranging = adx_v < 18.0
    is_volatile = atr_pct >= 0.15
    if is_trending:
        regime = "TRENDING"
    elif is_ranging:
        regime = "RANGING"
    elif is_volatile:
        regime = "VOLATILE"
    else:
        regime = "NEUTRAL"
    return {"regime": regime, "trend_dir": trend_dir, "strength": slope_strength, "adx": adx_v, "atr_pct": atr_pct, "is_trending": is_trending, "is_ranging": is_ranging, "is_volatile": is_volatile}
def S_SMART_TREND(candles: List[Dict]):
    if len(candles) < 60:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    e8 = ema(C, 8)
    e21 = ema(C, 21)
    e55 = ema(C, 55)
    if not e8 and e21 and e55:
        return (None, 0.0)
    last_price = C[-1]
    if e8[-1] > e21[-1] > e55[-1]:
        pass
    gap1 = (e8[-1] - e21[-1]) / e21[-1]
    
    gap2 = (e21[-1] - e55[-1]) / e55[-1]
    if gap1 > 0 and gap2 > 0:
        dist = abs(last_price - e8[-1]) / e8[-1]
        if dist < 0.003:
            strength = 0.65 + min(0.3, (gap1 + gap2) * 50)
            return ("CALL", min(0.95, strength))
        elif last_price > e8[-1] and C[-1] > C[-2]:
            return ("CALL", 0.65)
    elif e8[-1] < e21[-1] < e55[-1]:
        pass
    else:
        return (None, 0.0)
    gap1 = (e21[-1] - e8[-1]) / e21[-1]
    
    gap2 = (e55[-1] - e21[-1]) / e55[-1]
    if gap1 > 0 and gap2 > 0:
        dist = abs(last_price - e8[-1]) / e8[-1]
        if dist < 0.003:
            strength = 0.65 + min(0.3, (gap1 + gap2) * 50)
            return ("PUT", min(0.95, strength))
        elif last_price < e8[-1] and C[-1] < C[-2]:
            return ("PUT", 0.65)
    
    return (None, 0.0)
def S_SMART_MOMENTUM(candles: List[Dict]):
    if len(candles) < 20:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    rsi_v = rsi(C, 14)
    if rsi_v and len(rsi_v) < 3:
        return (None, 0.0)
    r_now = rsi_v[-1]
    
    r_prev = rsi_v[-2]
    r_2ago = rsi_v[-3]
    last = candles[-1]
    
    body = candle_body(last)
    rng = candle_range(last)
    body_pct = 0.0
    if r_now > 50 and r_now > r_prev and is_bull(last) and body_pct > 0.5:
        strength = 0.6 + min(0.3, (r_now - 50) / 100)
        if r_prev < 50:
            strength += 0.1
        return ("CALL", min(0.95, strength))
    elif r_now < 50 and r_now < r_prev and is_bear(last) and body_pct > 0.5:
        strength = 0.6 + min(0.3, (50 - r_now) / 100)
        if r_prev > 50:
            strength += 0.1
        return ("PUT", min(0.95, strength))
    
    return (None, 0.0)
def S_SMART_RANGE(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    dn, ma, up = bollinger(C, 20, 2.0)
    rsi_v = rsi(C, 14)
    if not dn and up and rsi_v:
        return (None, 0.0)
    last_price = C[-1]
    
    bb_width = 0.0
    if bb_width < 0.004:
        return (None, 0.0)
    pct_to_lower = 0.5
    if pct_to_lower < 0.15 and rsi_v[-1] < 40:
        strength = 0.65 + min(0.25, (0.15 - pct_to_lower) * 2 + (40 - rsi_v[-1]) / 100)
        return ("CALL", min(0.95, strength))
    elif pct_to_lower > 0.85 and rsi_v[-1] > 60:
        strength = 0.65 + min(0.25, (pct_to_lower - 0.85) * 2 + (rsi_v[-1] - 60) / 100)
        return ("PUT", min(0.95, strength))
    
    return (None, 0.0)
def S_SMART_BREAKOUT(candles: List[Dict]):
    if len(candles) < 25:
        return (None, 0.0)
    H = [c["high"] for c in candles]
    L = [c["low"] for c in candles]
    C = [c["close"] for c in candles]
    lookback = 20
    
    recent_high = max(H[-lookback - 1:-1])
    recent_low = min(L[-lookback - 1:-1])
    last_price = C[-1]
    last = candles[-1]
    body = candle_body(last)
    
    rng = candle_range(last)
    body_pct = 0.0
    if last_price > recent_high and is_bull(last) and body_pct > 0.6:
        excess = (last_price - recent_high) / recent_high
        strength = 0.7 + min(0.25, excess * 1000)
        return ("CALL", min(0.95, strength))
    elif last_price < recent_low and is_bear(last) and body_pct > 0.6:
        excess = (recent_low - last_price) / recent_low
        strength = 0.7 + min(0.25, excess * 1000)
        return ("PUT", min(0.95, strength))
    
    return (None, 0.0)
def S_SMART_REVERSAL(candles: List[Dict]):
    if len(candles) < 10:
        return (None, 0.0)
    last = candles[-1]
    prev = candles[-2]
    prev2 = candles[-3]
    if is_bear(prev) and is_bear(prev2) and is_bull(last) and last["close"] > prev["open"]:
        body = candle_body(last)
        rng = candle_range(last)
        body_pct = 0.0
        if body_pct > 0.5:
            strength = 0.65 + min(0.25, body_pct * 0.3)
            return ("CALL", strength)
    elif is_bull(prev) and is_bull(prev2) and is_bear(last) and last["close"] < prev["open"]:
        body = candle_body(last)
        rng = candle_range(last)
        body_pct = 0.0
        if body_pct > 0.5:
            strength = 0.65 + min(0.25, body_pct * 0.3)
            return ("PUT", strength)
    
    return (None, 0.0)
def S_SMART_PULLBACK(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    e20 = ema(C, 20)
    e50 = None
    rsi_v = rsi(C, 14)
    if not e20 and rsi_v:
        return (None, 0.0)
    last_price = C[-1]
    
    prev_price = C[-2]
    uptrend = False
    
    downtrend = False
    
    if e50:
        if e20[-1] > e50[-1] and e20[-1] > e20[-5]:
            uptrend = True
        elif e20[-1] < e50[-1] and e20[-1] < e20[-5]:
            downtrend = True
        elif e20[-1] > e20[-5]:
            uptrend = True
        elif e20[-1] < e20[-5]:
            downtrend = True
    
    elif uptrend and rsi_v[-1] < 55:
        dist_to_ema = (last_price - e20[-1]) / e20[-1]
        match dist_to_ema:
            case _ as strength if -0.005 <= dist_to_ema <= 0.002 and last_price > prev_price:
                return ("CALL", min(0.9, strength))
            case 45 as dist_to_ema if -0.002 <= dist_to_ema and -0.002 <= dist_to_ema <= 0.005:
                return (None, 0.0)
    if downtrend:
        pass
    match dist_to_ema:
        case _ as strength:
            return ("PUT", min(0.9, strength))
    return (None, 0.0)
def S_SMART_VOLATILITY(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    H = [c["high"] for c in candles]
    L = [c["low"] for c in candles]
    C = [c["close"] for c in candles]
    try:
        atr_v = atr(H, L, C, 14)
    finally:
        pass
    if Exception:
        Exception
    return (None, 0.0)
    if len(atr_v) < 10:
        return (None, 0.0)
    recent_atr = sum(atr_v[-3:]) / 3
    older_atr = sum(atr_v[-10:-3]) / 7
    if recent_atr <= older_atr * 1.1:
        return (None, 0.0)
    last = candles[-1]
    body = candle_body(last)
    rng = candle_range(last)
    body_pct = 0.0
    if body_pct < 0.55:
        return (None, 0.0)
    expansion = recent_atr / older_atr
    if is_bull(last):
        strength = 0.65 + min(0.25, (expansion - 1.1) * 0.5)
        return ("CALL", strength)
    elif is_bear(last):
        strength = 0.65 + min(0.25, (expansion - 1.1) * 0.5)
        return ("PUT", strength)
    
    return (None, 0.0)
def S_PRICE_ABOVE_BELOW_VWAP(candles: List[Dict]):
    if len(candles) < 30:
        return (None, 0.0)
    C = [c["close"] for c in candles]
    ref = sum(C[-20:]) / 20
    
    last = candles[-1]
    deviation = (C[-1] - ref) / ref
    
    body = candle_body(last)
    rng = candle_range(last)
    body_pct = 0.0
    if body_pct < 0.5:
        return (None, 0.0)
    elif C[-1] > ref and is_bull(last):
        strength = 0.6 + min(0.3, deviation * 100)
        return ("CALL", strength)
    elif C[-1] < ref and is_bear(last):
        strength = 0.6 + min(0.3, abs(deviation) * 100)
        return ("PUT", strength)
    
    return (None, 0.0)
def S_LAST_3_CONSENSUS(candles: List[Dict]):
    if len(candles) < 5:
        return (None, 0.0)
    last3 = candles[-3:]
    bulls = sum((1 for c in last3))
    bears = sum((1 for c in last3))
    if bulls >= 2 and is_bull(last3[-1]):
        bodies = [0 for c in last3]
        avg_body = sum(bodies) / 3
        if avg_body > 0.4:
            strength = 0.55 + min(0.3, avg_body * 0.5)
            return ("CALL", strength)
    elif bears >= 2 and is_bear(last3[-1]):
        bodies = [0 for c in last3]
        avg_body = sum(bodies) / 3
        if avg_body > 0.4:
            strength = 0.55 + min(0.3, avg_body * 0.5)
            return ("PUT", strength)
    
    return (None, 0.0)
register_strategy("SMART_TREND", S_SMART_TREND, "SMART")
register_strategy("SMART_MOMENTUM", S_SMART_MOMENTUM, "SMART")
register_strategy("SMART_RANGE", S_SMART_RANGE, "SMART")
register_strategy("SMART_BREAKOUT", S_SMART_BREAKOUT, "SMART")
register_strategy("SMART_REVERSAL", S_SMART_REVERSAL, "SMART")
register_strategy("SMART_PULLBACK", S_SMART_PULLBACK, "SMART")
register_strategy("SMART_VOLATILITY", S_SMART_VOLATILITY, "SMART")
register_strategy("VWAP_BIAS", S_PRICE_ABOVE_BELOW_VWAP, "SMART")
register_strategy("LAST_3_CONSENSUS", S_LAST_3_CONSENSUS, "SMART")
TREND_FOLLOWING_STRATEGIES = {"SMART_PULLBACK", "ADX_TREND", "SMART_BREAKOUT", "ICHIMOKU", "EMA_CROSS_8_21", "DONCHIAN_BREAK", "SUPERTREND_FLIP", "SMART_TREND", "ATR_BREAKOUT", "AROON_TREND", "MACD_CROSS", "HEIKIN_ASHI_TREND", "KELTNER_BREAK_15", "EMA_CROSS_5_20", "KELTNER_BREAK_20", "SMART_MOMENTUM", "TRIPLE_EMA"}
RANGE_TRADING_STRATEGIES = {"VWAP_REVERSION", "BOLLINGER_REVERSAL", "CCI_REVERSAL", "SMART_RANGE", "STOCH_CROSS", "WILLIAMS_R", "OTC_BB_RSI", "RSI_EXTREME", "SMART_REVERSAL", "RANGE_FADE"}
UNIVERSAL_STRATEGIES = {"LAST_3_CONSENSUS", "JOKER", "PINBAR", "MOMENTUM", "THREE_SOLDIERS", "ENGULFING", "AB_PATTERN", "HAMMER", "INSIDE_BAR", "SMART_VOLATILITY", "VWAP_BIAS"}
def get_regime_appropriate_strategies(regime: str) -> set:
    if regime == "TRENDING":
        return TREND_FOLLOWING_STRATEGIES | UNIVERSAL_STRATEGIES
    elif regime == "RANGING":
        return RANGE_TRADING_STRATEGIES | UNIVERSAL_STRATEGIES
    
    return set(STRATEGY_REGISTRY.keys())
PATTERN_MEMORY_FILE = "naif_pattern_memory.json"
TREND_GROUP = {"SMART_PULLBACK", "ADX_TREND", "ICHIMOKU", "EMA_PULLBACK_21", "EMA_CROSS_8_21", "SUPERTREND_FLIP", "SMART_TREND", "EMA_CROSS_9_21", "MACD_ZERO", "AROON_TREND", "EMA_PULLBACK_8", "MACD_CROSS", "HEIKIN_ASHI_TREND", "EMA_CROSS_5_20", "EMA_CROSS_12_26", "TRIPLE_EMA", "EMA_PULLBACK_13"}
MOMENTUM_GROUP = {"ROC_MOMENTUM", "LAST_3_CONSENSUS", "RSI_CROSS_50", "CCI_TURN", "CCI_REVERSAL", "CCI_EXTREME", "MOMENTUM", "STOCH_CROSS", "WILLIAMS_R", "BULLS_BEARS_POWER", "TWO_CANDLE_MOMENTUM", "RSI_EXTREME", "SMART_MOMENTUM"}
STRUCTURE_GROUP = {"SMART_BREAKOUT", "JOKER", "MORNING_STAR", "INSIDE_BAR", "SMART_REVERSAL", "HARAMI", "VWAP_REVERSION", "BOLLINGER_REVERSAL", "OTC_BB_RSI", "OTC_FORTRESS", "KELTNER_BREAK_20", "HAMMER", "OTC_TRIPLE_MA", "BB_BOUNCE", "VWAP_BIAS", "PRICE_ACTION", "DONCHIAN_BREAK", "OTC_HEIKEN", "PINBAR", "ATR_BREAKOUT", "SMART_RANGE", "THREE_SOLDIERS", "ENGULFING", "KELTNER_BREAK_15", "AB_PATTERN", "SMART_VOLATILITY", "RANGE_FADE", "FRACTAL_REVERSAL"}
def check_confluence(voters_list, direction: str) -> Dict[(str, Any)]:
    has_trend = False
    
    has_momentum = False
    has_structure = False
    
    for name, _, _ in voters_list:
        if name in TREND_GROUP:
            has_trend = True
        elif name in MOMENTUM_GROUP:
            has_momentum = True
        elif name in STRUCTURE_GROUP:
            has_structure = True
    
    score = int(has_trend) + int(has_momentum) + int(has_structure)
    return {"has_trend": has_trend, "has_momentum": has_momentum, "has_structure": has_structure, "confluence_score": score, "is_high_quality": score >= 3, "is_acceptable": score >= 2}
_PATTERN_MEM: Optional[Dict] = None
def _load_pattern_memory() -> Dict:
    global _PATTERN_MEM
    if _PATTERN_MEM is not None:
        return _PATTERN_MEM
    try:
        if os.path.exists(PATTERN_MEMORY_FILE):
            with open(PATTERN_MEMORY_FILE, "r", encoding="utf-8") as f:
                _PATTERN_MEM = json.load(f)
    finally:
        None(None, __exception__, __exception__)
        return _PATTERN_MEM
    
    return _PATTERN_MEM
    
    _PATTERN_MEM = {}
    return _PATTERN_MEM
    
    if Exception:
        Exception
        _PATTERN_MEM = {}
    return _PATTERN_MEM
def _save_pattern_memory():
    try:
        if _PATTERN_MEM is None:
            pass
    finally:
        return
        with open(PATTERN_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_PATTERN_MEM, f, indent=2)
        ##ERROR##(None, None, None)
        return
    return
    if Exception:
        Exception
    return
def record_pattern_outcome(asset: str, strategy_label: str, direction: str, won: bool):
    mem = _load_pattern_memory()
    
    asset_key = asset.replace(" ", "_").replace("/", "_")
    
    key = f"{asset_key}|{strategy_label}|{direction}"
    if key not in mem:
        mem[key] = {"wins": 0, "losses": 0, "last_seen": 0}
    elif won:
        mem[key]["wins"] += 1
    else:
        mem[key]["losses"] += 1
    
    mem[key]["last_seen"] = int(time.time())
    
    _save_pattern_memory()
def get_pattern_winrate(asset: str, strategy_label: str, direction: str, min_trades: int=5) -> Tuple[(float, int)]:
    mem = _load_pattern_memory()
    
    asset_key = asset.replace(" ", "_").replace("/", "_")
    key = f"{asset_key}|{strategy_label}|{direction}"
    entry = mem.get(key)
    if not entry:
        return (0.5, 0)
    wins = entry.get("wins", 0)
    
    losses = entry.get("losses", 0)
    total = wins + losses
    if total < min_trades:
        return (0.5, total)
    
    return (wins / total, total)
def get_asset_overall_winrate(asset: str) -> Tuple[(float, int)]:
    mem = _load_pattern_memory()
    
    asset_key = asset.replace(" ", "_").replace("/", "_")
    total_wins = 0
    
    total_losses = 0
    
    for key, data in mem.items():
        if key.startswith(asset_key + "|"):
            total_wins += data.get("wins", 0)
            total_losses += data.get("losses", 0)
    
    total = total_wins + total_losses
    if total == 0:
        return (0.5, 0)
    
    return (total_wins / total, total)
class AntiTiltState:
    """Tracks recent losses to prevent tilt-trading."""
    
    def __init__(self, max_consecutive_losses: int=3, cooldown_after_losses_minutes: int=30, daily_loss_pct_limit: float=5.0, cooldown_after_single_loss_candles: int=2):
        self.max_consecutive_losses = max_consecutive_losses
        
        self.cooldown_after_losses_minutes = cooldown_after_losses_minutes
        self.daily_loss_pct_limit = daily_loss_pct_limit
        self.cooldown_after_single_loss_candles = cooldown_after_single_loss_candles
        self.consecutive_losses = 0
        
        self.last_loss_time = 0
        self.cooldown_until = 0
        self.day_start_balance = 0.0
        self.day_start_date = ""
        self.last_loss_minute = ""
    
    def set_day_start(self, balance: float):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.day_start_date:
            self.day_start_balance = balance
            self.day_start_date = today
            return
    
    def can_trade(self, current_balance: float, current_minute: str) -> Tuple[(bool, str)]:
        now = time.time()
        if self.cooldown_until > now:
            mins = int(((self.cooldown_until) - now) / 60) + 1
            return (False, f"Anti-tilt cooldown: {mins}min remaining ({self.consecutive_losses} losses)")
        elif self.last_loss_minute and current_minute:
            try:
                from datetime import datetime as _dt
                fmt = "%Y-%m-%d %H:%M"
                last_dt = _dt.strptime(self.last_loss_minute, fmt)
                cur_dt = _dt.strptime(current_minute, fmt)
            finally:
                minutes_passed = cur_dt - last_dt.total_seconds(__exception__() / 60)
                if minutes_passed < self.cooldown_after_single_loss_candles:
                    remaining = (self.cooldown_after_single_loss_candles) - minutes_passed
                return (False, f"Post-loss cooldown: wait {remaining} candle(s)")
            if Exception:
                Exception
                int
                int
            elif self.day_start_balance > 0:
                loss_pct = ((self.day_start_balance) - current_balance) / (self.day_start_balance) * 100
                if loss_pct >= self.daily_loss_pct_limit:
                    return (False, f"Daily loss limit hit ({loss_pct:.1f}% — stopping for today)")
        
        return (True, "")
    
    def register_trade_result(self, won: bool, current_minute: str=""):
        if won:
            self.consecutive_losses = 0
            self.last_loss_minute = ""
            return
        match self:
            case _:
                pass
def check_volatility_gate(candles: List[Dict], min_atr_pct: float=0.04, max_atr_pct: float=0.5) -> Tuple[(bool, str, float)]:
    if len(candles) < 20:
        return (True, "", 0.0)
    H = [c["high"] for c in candles]
    
    L = [c["low"] for c in candles]
    C = [c["close"] for c in candles]
    try:
        atr_vals = atr(H, L, C, 14)
        if atr_vals and C[-1] == 0:
            pass
    finally:
        return (True, "", 0.0)
        atr_v = atr_vals[-1]
        atr_pct = atr_v / C[-1] * 100
    if Exception:
        Exception
        __exception__
        __exception__
    return (True, "", 0.0)
    if atr_pct < min_atr_pct:
        return (False, f"ATR too low ({atr_pct:.3f}% < {min_atr_pct}%)", atr_pct)
    elif atr_pct > max_atr_pct:
        return (False, f"ATR too high ({atr_pct:.2f}% > {max_atr_pct}%) — chaotic market", atr_pct)
    
    return (True, "", atr_pct)
def check_time_of_day(broker_offset_hours: int=0) -> Tuple[(bool, str)]:
    now = datetime.now()
    
    hour = now.hour
    minute = now.minute
    match hour:
        case _ if 8 <= hour <= 22 and minute <= 1 and minute == 30:
            return (False, f"Top-of-hour news risk ({hour:02d}:{minute:02d})")
    
    weekday = now.weekday()
    
    match hour:
        case 4 if hour >= 22:
            return (False, "Friday weekend approach — illiquid OTC")
    
    match hour:
        case 6 if hour < 22:
            return (False, "Sunday pre-open — low liquidity")
    return (True, "")
def apply_quality_filters(signal: str, score: float, voters: List[Tuple[(str, float, float)]], candles: List[Dict], asset: str, strategy_label: str, payout_pct: int, min_payout: int, anti_tilt: Optional["AntiTiltState"]=None, current_balance: float=0.0, current_minute: str="", require_confluence: bool=True, require_volatility_gate: bool=True, require_time_filter: bool=True, min_pattern_winrate: float=0.5, use_pattern_memory: bool=True) -> Tuple[(bool, str, Dict)]:
    info = {"confluence": None, "volatility": None, "time_filter": None, "anti_tilt": None, "pattern_winrate": None}
    if payout_pct < min_payout:
        return (False, f"Payout too low ({payout_pct}% < {min_payout}%)", info)
    elif anti_tilt is not None:
        can, reason = anti_tilt.can_trade(current_balance, current_minute)
        info["anti_tilt"] = {"can_trade": can, "reason": reason}
        if not can:
            return (False, f"Anti-tilt: {reason}", info)
    elif require_time_filter:
        ok, reason = check_time_of_day()
        info["time_filter"] = {"ok": ok, "reason": reason}
        if not ok:
            return (False, f"Time filter: {reason}", info)
    elif require_volatility_gate:
        ok, reason, atr_pct = check_volatility_gate(candles)
        info["volatility"] = {"ok": ok, "reason": reason, "atr_pct": atr_pct}
        if not ok:
            return (False, f"Volatility: {reason}", info)
    elif require_confluence and voters:
        winning_voters = [v for v in voters]
        conf = check_confluence(winning_voters, signal)
        info["confluence"] = conf
        if not conf["is_acceptable"]:
            pass
        else:
            return (False, f"Low confluence ({conf["confluence_score"]}/3): trend={conf["has_trend"]}, momentum={conf["has_momentum"]}, structure={conf["has_structure"]}",
                
                info)
    elif use_pattern_memory:
        pat_wr, pat_n = get_pattern_winrate(asset, strategy_label, signal, min_trades=5)
        info["pattern_winrate"] = {"winrate": pat_wr, "trades": pat_n}
        if pat_n >= 5 and pat_wr < min_pattern_winrate:
            return (False, f"Bad pattern history: {pat_wr * 100:.0f}% on {asset}/{strategy_label}/{signal} ({pat_n} trades)",
                
                info)
    
    return (True, "", info)
_STRATEGY_STATS_CACHE: Optional[Dict] = None
def _load_strategy_stats() -> Dict:
    global _STRATEGY_STATS_CACHE
    if _STRATEGY_STATS_CACHE is not None:
        return _STRATEGY_STATS_CACHE
    try:
        if os.path.exists(STRATEGY_STATS_FILE):
            with open(STRATEGY_STATS_FILE, "r", encoding="utf-8") as f:
                _STRATEGY_STATS_CACHE = json.load(f)
    finally:
        None(None, __exception__, __exception__)
        return _STRATEGY_STATS_CACHE
    
    return _STRATEGY_STATS_CACHE
    
    _STRATEGY_STATS_CACHE = {}
    return _STRATEGY_STATS_CACHE
    
    if Exception:
        Exception
        _STRATEGY_STATS_CACHE = {}
    return _STRATEGY_STATS_CACHE
def _save_strategy_stats():
    try:
        if _STRATEGY_STATS_CACHE is None:
            pass
    finally:
        return
        with open(STRATEGY_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(_STRATEGY_STATS_CACHE, f, indent=2)
        ##ERROR##(None, None, None)
        return
    return
    if Exception:
        Exception
    return
def get_strategy_winrate(name: str, min_trades: int=5) -> float:
    stats = _load_strategy_stats()
    
    entry = stats.get(name)
    if not entry:
        return 0.5
    wins = int(entry.get("wins", 0))
    losses = int(entry.get("losses", 0))
    total = wins + losses
    if total < min_trades:
        return 0.5
    
    return wins / total
def get_strategy_total_trades(name: str) -> int:
    stats = _load_strategy_stats()
    entry = stats.get(name, {})
    return int(entry.get("wins", 0)) + int(entry.get("losses", 0))
def record_strategy_outcome(name: str, signal: str, won: bool):
    stats = _load_strategy_stats()
    if name not in stats:
        stats[name] = {"wins": 0, "losses": 0, "signal_history": []}
    elif won:
        stats[name]["wins"] = int(stats[name].get("wins", 0)) + 1
    else:
        stats[name]["losses"] = int(stats[name].get("losses", 0)) + 1
    hist = stats[name].setdefault("signal_history", [])
    hist.append([int(time.time()), signal, bool(won)])
    if len(hist) > 200:
        del hist[:-200]
    _save_strategy_stats()
def record_all_strategies_outcome(candles_snapshot: List[Dict], final_signal: str, won: bool):
    for name, fn in STRATEGY_REGISTRY.items():
        if name in VOTING_EXCLUDE:
            pass
        try:
            sig, _strength = fn(candles_snapshot)
            if sig is None:
                pass
        finally:
            agreed = sig == final_signal
            if __exception__ and won and not agreed:
                pass
            strategy_was_right = not won
            record_strategy_outcome(name, sig, strategy_was_right)
            if Exception:
                Exception
                agreed
                agreed
            return
def resample_candles(candles: List[Dict], factor: int) -> Optional[List[Dict]]:
    if candles and len(candles) < factor + 5:
        return
    n = len(candles)
    usable = n // factor * factor
    if usable < factor * 5:
        return
    sub = candles[-usable:]
    out = []
    
    for i in range(0, usable, factor):
        group = sub[i:i + factor]
        out.append({"open": group[0]["open"], "high": max((c["high"] for c in group)), "low": min((c["low"] for c in group)), "close": group[-1]["close"]})
    return out
def run_voting_on_candles(candles: List[Dict], strategy_names: Optional[List[str]]=None, apply_regime_filter: bool=True):
    if strategy_names is None:
        strategy_names = [n for n in STRATEGY_REGISTRY if n not in VOTING_EXCLUDE]
    elif apply_regime_filter and len(candles) >= 30:
        try:
            regime_info = detect_market_regime(candles)
            regime = regime_info.get("regime", "UNKNOWN")
            if regime in ("TRENDING", "RANGING"):
                appropriate = get_regime_appropriate_strategies(regime)
                filtered = [n for n in strategy_names if n in appropriate]
                if len(filtered) >= 5:
                    strategy_names = filtered
        if Exception:
            Exception
        call_voters = []
        put_voters = []
        for name in strategy_names:
            fn = STRATEGY_REGISTRY.get(name)
            if not fn:
                pass
            try:
                sig, strength = fn(candles)
                if sig is None:
                    pass
            finally:
                wr = get_strategy_winrate(name)
                if sig == "CALL":
                    call_voters.append((name, strength, wr))
                elif sig == "PUT":
                    put_voters.append((name, strength, wr))
                elif Exception:
                    Exception
                return (call_voters, put_voters)
def smart_vote(candles_m1: List[Dict], candles_m5: Optional[List[Dict]]=None, candles_m15: Optional[List[Dict]]=None, min_agree: int=5, use_weights: bool=True, use_mtf: bool=True, mtf_strict: bool=False, enabled_strategies: Optional[List[str]]=None) -> Tuple[(Optional[str], float, Dict)]:
    details = {"call_count": 0, "put_count": 0, "call_voters": [], "put_voters": [], "winning_side": None, "mtf_m5_agrees": None, "mtf_m15_agrees": None, "score": 0.0, "reason": "", "regime": "UNKNOWN", "regime_adx": 0.0}
    
    try:
        regime_info = detect_market_regime(candles_m1)
    finally:
        "regime"[__exception__] = details
        details["regime_adx"] = regime_info.get("adx", 0.0)
    if Exception:
        Exception
        regime_info.get("regime", "UNKNOWN")
        regime_info.get("regime", "UNKNOWN")
    call_voters, put_voters = run_voting_on_candles(candles_m1, enabled_strategies)
    details["call_count"] = len(call_voters)
    details["put_count"] = len(put_voters)
    details["call_voters"] = call_voters
    details["put_voters"] = put_voters
    total = len(call_voters) + len(put_voters)
    if total == 0:
        details["reason"] = "No strategies voted"
        return (None,
            0.0, details)
    def weighted_score(voters):
        if not voters:
            return 0.0
        elif not use_weights:
            return sum((s for _, s, _ in voters))
        
        return sum((s * (0.5 + w) for _, s, w in voters))
    call_score = weighted_score(call_voters)
    put_score = weighted_score(put_voters)
    if call_score > put_score and len(call_voters) >= min_agree:
        winning = "CALL"
        voters = call_voters
        my_score = call_score
        opp_score = put_score
    elif put_score > call_score and len(put_voters) >= min_agree:
        winning = "PUT"
        voters = put_voters
        my_score = put_score
        opp_score = call_score
    else:
        details["reason"] = f"Not enough agreement: CALL={len(call_voters)} PUT={len(put_voters)} (need ≥{min_agree})"
        return (None,
            0.0, details)
    mtf_bonus = 0.0
    if use_mtf:
        if candles_m5 and len(candles_m5) > 20:
            m5_call, m5_put = run_voting_on_candles(candles_m5, enabled_strategies)
            m5_side = None
            agrees_m5 = m5_side == winning
            details["mtf_m5_agrees"] = agrees_m5
            mtf_bonus += -0.3
            if not mtf_strict and agrees_m5:
                details["reason"] = f"MTF strict reject: M5 says {m5_side} but M1 says {winning}"
                details["winning_side"] = None
                return (None,
                    0.0, details)
        elif candles_m15 and len(candles_m15) > 20:
            m15_call, m15_put = run_voting_on_candles(candles_m15, enabled_strategies)
            m15_side = None
            agrees_m15 = m15_side == winning
            details["mtf_m15_agrees"] = agrees_m15
            mtf_bonus += -0.4
    consensus_ratio = len(voters) / total
    
    avg_strength = my_score / max(1, len(voters))
    
    final_score = consensus_ratio * 2.0 + avg_strength * 1.5 + 0.5 + mtf_bonus
    
    final_score = max(0.0, min(5.0, final_score))
    details["winning_side"] = winning; details["score"] = final_score; details["reason"] = f"{winning}: {len(voters)}/{total} voters (weighted={my_score:.2f} vs {opp_score:.2f}), MTF bonus={mtf_bonus:+.2f}"; return (winning, final_score, details)
def detect_market_direction(candles: List[Dict]) -> Dict:
    if len(candles) < 50:
        return {"direction": "unknown", "strength": 0.0}
    C = [c["close"] for c in candles[-50:]]
    e20 = ema(C, 20)
    e50 = None
    slope = (C[-1] - C[0]) / max(abs(C[0]), 1e-9)
    if slope > 0.001 and e20[-1] > e20[-10]:
        return {"direction": "UPTREND", "strength": min(1.0, abs(slope) * 100)}
    elif slope < -0.001 and e20[-1] < e20[-10]:
        return {"direction": "DOWNTREND", "strength": min(1.0, abs(slope) * 100)}
    
    return {"direction": "SIDEWAYS", "strength": 0.3}
def detect_market_liquidity(candles: List[Dict]) -> Dict:
    if len(candles) < 30:
        return {"level": "unknown", "atr_pct": 0.0}
    O, H, L, C, _ = _prep_ohlc(candles, 50)
    a = atr(H, L, C, 14)
    avg_price = sum(C[-20:]) / 20
    atr_pct = 0
    if atr_pct > 0.3:
        return {"level": "HIGH", "atr_pct": atr_pct}
    elif atr_pct < 0.1:
        return {"level": "LOW", "atr_pct": atr_pct}
    
    return {"level": "MEDIUM", "atr_pct": atr_pct}
class MartingaleMode(str, Enum):
    OFF = "OFF"
    CLASSIC = "CLASSIC"
    FIBONACCI = "FIBONACCI"
    CUSTOM_SEQUENCE = "CUSTOM_SEQUENCE"
    MANUAL = "MANUAL"
    ANTI = "ANTI"
@dataclass
class MartingaleConfig:
    mode: str = "OFF"
    base_amount: float = 5.0
    multiplier: float = 2.0
    max_steps: int = 3
    min_amount: float = 1.0
    max_amount: float = 500.0
    fib_start_index: int = 1
    fib_scale: float = 1.0
    custom_sequence: List[float] = field(default_factory=list)
    sequence_is_multiplier: bool = False
    reset_on_win: bool = True
    round_to: int = 2
    manual_step_index: Optional[int] = None
class MartingaleManager:
    """
        Handles all Martingale modes:
          - OFF:             never escalate
          - CLASSIC:         base * mult^step
          - FIBONACCI:       fib(start + step - 1) * base * scale
          - CUSTOM_SEQUENCE: pre-defined list (values or multipliers)
          - MANUAL:          user is asked after every loss
          - ANTI:            grows on WIN, resets on LOSS
        """
    def __init__(self, cfg: MartingaleConfig):
        self.cfg = cfg
        self._current_step = 0
        self._fib_cache = self._calc_fib_list(60)
    
    @property
    def current_step(self) -> int:
        return self._current_step
    
    def current_amount(self, balance: Optional[float]=None) -> float:
        amount = self._amount_for_step(self._current_step)
        
        if balance is not None:
            amount = min(amount, max(balance, 0.0))
        amount = max(self.cfg.min_amount, min(self.cfg.max_amount, amount))
        return round(amount, self.cfg.round_to)
    
    def register_result(self, win: bool):
        mode = self.cfg.mode
        if mode == "OFF":
            self._reset()
            return
        elif mode == "ANTI":
            if win:
                self._inc_step()
                return
            self._reset()
            return
        elif win:
            if self.cfg.reset_on_win:
                self._reset()
                return
            self._inc_step()
            return
        elif mode == "MANUAL":
            step = self._read_manual_step()
            self._current_step = max(0, min(step, self.cfg.max_steps))
            return
        self._inc_step()
    
    def set_manual_step(self, step_index: int):
        self.cfg.manual_step_index = step_index
    
    def reset(self):
        self._reset()
    
    def _amount_for_step(self, step: int) -> float:
        base = self.cfg.base_amount
        if step <= 0:
            return base
        m = self.cfg.mode
        if m == "CLASSIC":
            return base * (self.cfg.multiplier)**step
        elif m == "FIBONACCI":
            idx = max(1, (self.cfg.fib_start_index) + step - 1)
            fib_n = self._fib_value(idx)
            return base * fib_n * max(0.0, self.cfg.fib_scale)
        elif m == "ANTI":
            return base * (self.cfg.multiplier)**step
        elif m == "CUSTOM_SEQUENCE":
            if not self.cfg.custom_sequence:
                return base
            seq_idx = min(step, len(self.cfg.custom_sequence)) - 1
            seq_val = self.cfg.custom_sequence[seq_idx]
            if self.cfg.sequence_is_multiplier:
                return base * seq_val
            return float(seq_val)
        elif m == "MANUAL":
            return base * (self.cfg.multiplier)**step
        
        return base
    
    def _inc_step(self):
        self._current_step = min((self._current_step) + 1, self.cfg.max_steps)
    
    def _reset(self):
        self._current_step = 0
        self.cfg.manual_step_index = None
    
    def _read_manual_step(self) -> int:
        if self.cfg.manual_step_index is not None:
            step = int(self.cfg.manual_step_index)
            self.cfg.manual_step_index = None
            return step
        
        try:
            raw = input(f"➤ Enter martingale STEP after loss (0..{self.cfg.max_steps}): ").strip()
            if raw == "":
                if self.cfg.max_steps >= 1:
                    pass
                return 1
        finally:
            return 0
            step = int(raw)
        if Exception:
            Exception
    
    def _calc_fib_list(self, n: int) -> List[int]:
        a, b = (1, 1)
        out = [a, b]
        
        for _ in range(n):
            a = b
            b = a + b
            out.append(b)
        return out
    
    def _fib_value(self, idx: int) -> int:
        if idx < len(self._fib_cache):
            return self._fib_cache[idx]
        elif len(self._fib_cache) <= idx:
            self._fib_cache.append(self._fib_cache[-1] + self._fib_cache[-2])
            if not len(self._fib_cache) <= idx:
                pass
        
        return self._fib_cache[idx]
def _coerce_mg_mode(val) -> str:
    if isinstance(val, MartingaleMode):
        return val.value
    try:
        pass
    finally:
        return str(val).upper[__exception__()].value
    if Exception:
        Exception
        MartingaleMode
        MartingaleMode
    return
@dataclass
class RiskParams:
    sizing_mode: str = "fixed"
    fixed_amount: float = 5.0
    risk_percent: float = 1.0
    min_amount: float = 1.0
    max_amount: float = 200.0
def next_amount(balance: float, rp: RiskParams) -> float:
    if rp.sizing_mode == "percent":
        amt = balance * max(0.0, rp.risk_percent) / 100.0
    else:
        amt = rp.fixed_amount
    return round(max(rp.min_amount, min(rp.max_amount, amt)), 2)
@dataclass
class BotConfig:
    """Persistent bot configuration (saved to JSON)."""
    account: str = "PRACTICE"
    asset_mode: str = "AUTO"
    selected_asset: str = ""
    only_otc: bool = False
    min_payout: int = 80
    top_n: int = 8
    rotation_mode: str = "hybrid"
    duration_s: int = 60
    one_trade_only: bool = True
    entry_offset_ms: int = 0
    sizing_mode: str = "fixed"
    fixed_amount: float = 5.0
    risk_percent: float = 1.0
    min_amount: float = 1.0
    max_amount: float = 200.0
    session_tp: float = 0.0
    session_sl: float = 0.0
    enabled_strategies: List[str] = field(default_factory=(lambda: ["SMART_TREND", "SMART_MOMENTUM", "SMART_RANGE", "SMART_BREAKOUT", "SMART_REVERSAL", "SMART_PULLBACK", "SMART_VOLATILITY", "VWAP_BIAS", "LAST_3_CONSENSUS", "JOKER", "MOMENTUM", "RSI_EXTREME", "BOLLINGER_REVERSAL", "AB_PATTERN", "ROC_MOMENTUM", "TWO_CANDLE_MOMENTUM", "TIME_OF_DAY_BIAS", "EMA_CROSS_9_21", "EMA_CROSS_12_26", "MACD_CROSS", "SUPERTREND_FLIP", "HEIKIN_ASHI_TREND", "ADX_TREND", "TRIPLE_EMA", "RSI_CROSS_50", "STOCH_CROSS", "CCI_EXTREME", "WILLIAMS_R", "BB_BOUNCE", "CCI_TURN", "ENGULFING", "PINBAR", "INSIDE_BAR", "OTC_FORTRESS", "OTC_TRIPLE_MA"]))
    voting_enabled: bool = True
    voting_min_agree: int = 2
    voting_use_weights: bool = True
    voting_use_mtf: bool = True
    voting_min_score: float = 1.0
    mtf_m5: bool = True
    mtf_m15: bool = False
    mtf_strict: bool = True
    quality_filters_enabled: bool = True
    require_confluence: bool = True
    require_volatility_gate: bool = True
    require_time_filter: bool = True
    min_atr_pct: float = 0.04
    max_atr_pct: float = 0.5
    use_pattern_memory: bool = True
    min_pattern_winrate: float = 0.5
    anti_tilt_enabled: bool = True
    max_consecutive_losses: int = 3
    cooldown_after_losses_minutes: int = 30
    daily_loss_pct_limit: float = 5.0
    cooldown_after_single_loss_candles: int = 2
    mg_mode: str = "OFF"
    mg_multiplier: float = 2.0
    mg_max_steps: int = 3
    mg_base: float = 5.0
    mg_min: float = 1.0
    mg_max: float = 500.0
    mg_fib_start: int = 1
    mg_fib_scale: float = 1.0
    mg_custom_sequence: List[float] = field(default_factory=list)
    mg_seq_is_multiplier: bool = False
    mg_reset_on_win: bool = True
    mg_round_to: int = 2
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    screenshot_enabled: bool = False
    csv_enabled: bool = False
    schedule_enabled: bool = False
    schedule_start_hour: int = 9
    schedule_end_hour: int = 22
    schedule_weekdays: List[int] = field(default_factory=(lambda: [0, 1, 2, 3, 4, 5, 6]))
    dashboard_enabled: bool = True
    otc_threshold: float = 2.6
    otc_min_body_pct: float = 0.22
    
    @classmethod
    def load(cls) -> "BotConfig":
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                fields = set(cls.__annotations__.keys())
                data = {k: v for k, v in raw.items() if k in fields}
            finally:
                return cls()
                if Exception:
                    Exception
                    e = None
                    try:
                        console.print(f"[yellow]⚠ Failed to load config: {e}. Using defaults.[/yellow]")
                    finally:
                        pass
                    return cls()
                    return cls()
    
    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                pass
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        finally:
            ##ERROR##(None, None, None)
            return
        return
        if Exception:
            Exception
            e = None
            try:
                pass
            finally:
                __exception__
            return
@dataclass
class TradeResult:
    timestamp: str
    asset: str
    direction: str
    amount: float
    duration_s: int
    payout_pct: float
    result: str; profit: float = 0.0
    balance: float = 0.0
    order_id: str = ""
    strategy: str = ""
    confidence: float = 0.0
    mg_step: int = 0
    entry_price: float = 0.0
    exit_price: float = 0.0
@dataclass
class Statistics:
    wins: int = 0
    losses: int = 0
    draws: int = 0
    fails: int = 0
    total_pnl: float = 0.0
    current_balance: float = 0.0
    start_balance: float = 0.0
    max_loss_streak: int = 0
    max_win_streak: int = 0
    current_loss_streak: int = 0
    current_win_streak: int = 0
    trades: List[TradeResult] = field(default_factory=list)
    recent_results: Deque = field(default_factory=(lambda: deque(maxlen=30)))
    
    @property
    def total_trades(self) -> int:
        return (self.wins) + (self.losses)
    
    @property
    def winrate(self) -> float:
        if self.total_trades:
            return (self.wins) / (self.total_trades) * 100
        
        return 0.0
    
    @property
    def recent_winrate(self) -> float:
        if not self.recent_results:
            return 0.0
        
        return sum(self.recent_results) / len(self.recent_results) * 100
    
    def add_trade(self, tr: TradeResult):
        self.trades.append(tr)
        
        if tr.result == "WIN":
            self.wins += 1
            self.recent_results.append(True)
            self.current_win_streak += 1
            self.current_loss_streak = 0
            match self:
                case _ if tr.result == "LOSS" and self.current_loss_streak > self.max_loss_streak and tr.result == "DRAW" and tr.result == "FAIL" and len(self.trades) > 500:
                    pass
        
        else:
            self.losses += 1
            self.current_loss_streak += 1
            self.current_win_streak = 0
            self.max_loss_streak = self.current_loss_streak
        
        self.draws += 1
        
        self.fails += 1
        self.total_pnl += tr.profit
        
        self.current_balance = tr.balance
        
        self.trades = self.trades[-500:]
    
    def update_pending(self, order_id: str, result: str, profit: float, balance: float):
        for i in range(len(self.trades) - 1, -1, -1):
            t = self.trades[i]
            if t.order_id == order_id and t.result == "PENDING":
                t.result = result
                t.profit = profit
                t.balance = balance
                if result == "WIN":
                    self.wins += 1
                    self.recent_results.append(True)
                    self.current_win_streak += 1
                    self.current_loss_streak = 0
                    match self:
                        case _ if result == "LOSS" and self.current_loss_streak > self.max_loss_streak and result == "DRAW":
                            return True
                else:
                    self.losses += 1
                    self.current_loss_streak += 1
                    self.current_win_streak = 0
                    self.max_loss_streak = self.current_loss_streak
            else:
                self.draws += 1
            self.total_pnl += profit
            self.current_balance = balance
        return False
CURRENCY_CODES = {"JPY", "HUF", "DZD", "INR", "MYR", "IDR", "NGN", "CNY", "PKR", "PHP", "AED", "EUR", "CAD", "GBP", "THB", "CHF", "BRL", "KRW", "PEN", "ARS", "NZD", "SGD", "AUD", "CZK", "RUB", "PLN", "DKK", "USD", "EGP", "CLP", "ILS", "BDT", "HKD", "NOK", "COP", "SEK", "SAR", "ZAR", "CNH", "TRY", "MXN"}
def is_otc_name(name: str) -> bool:
    s = name.lower()
    if not "(otc)" in s:
        pass
    
    return "_otc" in s
def looks_like_fx_pair(name: str) -> bool:
    s = name.upper().replace(" ", "")
    
    m = re.search("([A-Z]{3})[\\/\\-\\_\\s]?([A-Z]{3})", s)
    if not m:
        return False
    a = m.group(1); b = m.group(2)
    if a in CURRENCY_CODES:
        pass
    
    return b in CURRENCY_CODES
def include_asset(name: str) -> bool:
    return looks_like_fx_pair(name)
def _parse_percent(v) -> Optional[int]:
    if v is None:
        return
    try:
        if isinstance(v, str):
            pass
    finally:
        return v.strip().rstrip("%"(__exception__).strip())
    return int(v)
    if Exception:
        Exception
        int
        int
    return
async def get_profile_info(client) -> Dict[(str, Any)]:
    out = {"profile_id": None, "nick_name": None, "demo_balance": 0.0, "live_balance": 0.0, "country": None, "country_name": None, "avatar": None, "offset": None}
    try:
        await client.get_profile()
        profile = await client.get_profile()
        if profile is None:
            pass
    finally:
        return out
        for attr in ("profile_id", "nick_name", "demo_balance", "live_balance", "country", "country_name", "avatar", "offset"):
            try:
                val = getattr(profile, attr, None)
            finally:
                if None is not __exception__:
                    out[attr] = val
                elif Exception:
                    Exception
                    val
                    val
            return out
            if Exception:
                Exception
                e = None
                try:
                    pass
                finally:
                    __exception__
                return out
def _read_raw_instruments(client) -> List[List]:
    try:
        if hasattr(client, "api") or client.api is not None:
            insts = getattr(client.api, "instruments", None)
            if insts:
                pass
            return list(insts)
    finally:
        return []
        return []
        return []
        if Exception:
            Exception
        return []
def get_payment_map(client) -> Dict:
    try:
        if not client.get_payment():
            pass
    finally:
        return {}
        if Exception:
            Exception
        return
async def ensure_instruments_loaded(client, timeout: float=30.0) -> bool:
    raw = _read_raw_instruments(client)
    if raw:
        return True
    try:
        if hasattr(client, "get_instruments"):
            await asyncio.wait_for(client.get_instruments(), timeout=timeout)
            await asyncio.wait_for(client.get_instruments(), timeout=timeout)
    finally:
        pass
    if Exception:
        Exception
    raw = _read_raw_instruments(client)
    return bool(raw)
def get_all_assets_status_sync(client) -> List[Dict[(str, Any)]]:
    out = []
    
    instruments = _read_raw_instruments(client)
    if not instruments:
        return out
    for i in instruments:
        try:
            if isinstance(i, (list, tuple)) and len(i) < 15:
                pass
        finally:
            symbol = str(i[1])
            display = str(i[2]).replace("\n", "").strip()
            is_open = bool(i[14])
            payout_1m = 0
            payout_5m = 0
            try:
                payout_1m = _parse_percent(i[-9]) or 0
            finally:
                payout_5m = i(-8[__exception__]) or 0
            if (IndexError, TypeError):
                (IndexError, TypeError)
                __exception__
                __exception__
            is_fx_sym = looks_like_fx_pair(symbol)
            is_fx_disp = looks_like_fx_pair(display)
            if not is_fx_sym:
                pass
            is_fx = is_fx_disp
            is_otc = is_otc_name(symbol) or is_otc_name(display)
            out.append({"symbol": symbol, "display_name": display, "name": display, "is_open": is_open, "payout_1m": payout_1m, "payout_5m": payout_5m, "is_otc": is_otc, "is_fx": is_fx, "is_tradable": is_fx})
            if Exception:
                Exception
                _parse_percent
                _parse_percent
            return out
async def get_all_assets_status(client) -> List[Dict[(str, Any)]]:
    result = get_all_assets_status_sync(client)
    if result:
        return result
    try:
        if hasattr(client, "get_instruments"):
            await asyncio.wait_for(client.get_instruments(), timeout=20.0)
            await asyncio.wait_for(client.get_instruments(), timeout=20.0)
    finally:
        return get_all_assets_status_sync(client)
        if Exception:
            Exception
        return get_all_assets_status_sync(client)
async def filter_assets(client, only_otc: bool=False, min_payout: int=70, open_only: bool=True, fx_only: bool=True, tradable_only: bool=True) -> List[Dict[(str, Any)]]:
    await get_all_assets_status(client)
    
    all_assets = await get_all_assets_status(client)
    
    out = []
    
    for a in all_assets:
        if not open_only and a["is_open"]:
            pass
        elif not tradable_only and a.get("is_tradable", a.get("is_fx", False)):
            pass
        elif not fx_only and a["is_fx"]:
            pass
        elif not only_otc and a["is_otc"]:
            pass
        elif a["payout_1m"] < min_payout:
            pass
        out.append(a)
    out.sort(key=(lambda x: -x["payout_1m"]))
    return out
async def verify_asset_open(client, asset_symbol: str) -> Tuple[(bool, str)]:
    try:
        await client.get_available_asset(asset_symbol, force_open=True)
        asset_name, asset_data = await client.get_available_asset(asset_symbol, force_open=True)
        if asset_data:
            pass
    finally:
        if 3 < __exception__:
            pass
        return (False, asset_symbol)
    is_open = bool(asset_data[2])
    return (is_open, asset_name)
    if Exception:
        Exception
        len(asset_data)
        len(asset_data)
    return
async def connect_quotex(client, attempts: int=5) -> Tuple[(bool, str)]:
    try:
        await client.connect()
        check, reason = await client.connect()
    finally:
        if __exception__:
            pass
        return (True, str(reason))
    if Exception:
        Exception
        e = check
        check
        try:
            check = False
        finally:
            reason = f": e{__exception__}"
        for i in range(attempts):
            try:
                session_file = Path("session.json")
            finally:
                if __exception__:
                    session_file.unlink()
            if Exception:
                Exception
                session_file.exists()
                session_file.exists()
            await asyncio.sleep(2.0)
            await asyncio.sleep(2.0)
            try:
                await client.connect()
                check, reason = await client.connect()
                if check:
                    pass
            finally:
                __exception__
                return (True, str(reason))
            if Exception:
                Exception
                e = None
                try:
                    pass
                finally:
                    reason = f": {e}__exception__"
                return (False, str(reason))
async def ensure_account(client, account: str):
    acc = account.upper()
    
    if acc not in ("PRACTICE", "REAL"):
        acc = "PRACTICE"
    try:
        if hasattr(client, "set_account_mode"):
            try:
                client.set_account_mode(acc)
            finally:
                pass
            if Exception:
                Exception
            await client.change_account(acc)
            await client.change_account(acc)
            return
            if Exception:
                Exception
                e = None
                try:
                    console.print(f"[yellow]⚠ change_account({acc}) failed: {e}[/yellow]")
                finally:
                    pass
                return
async def wait_until_next_candle(timeframe_seconds: int=60, offset_ms: int=0) -> float:
    now = time.time()
    seconds_into = now % timeframe_seconds
    wait_seconds = timeframe_seconds - seconds_into
    wait_seconds += offset_ms / 1000.0
    if wait_seconds > 0:
        if wait_seconds > 0.05:
            await asyncio.sleep(wait_seconds - 0.03)
            await asyncio.sleep(wait_seconds - 0.03)
            target = now + wait_seconds
            if time.time() < target:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                if not time.time() < target:
                    pass
            return wait_seconds
        await asyncio.sleep(wait_seconds)
        await asyncio.sleep(wait_seconds)
    
    return wait_seconds
def seconds_until_next_candle(timeframe_seconds: int=60) -> float:
    now = time.time()
    seconds_into = now % timeframe_seconds
    return timeframe_seconds - seconds_into
async def sleep_until_second_zero():
    now = time.time()
    sec = int(now % 60)
    if sec == 0:
        return
    
    await asyncio.sleep(max(0.02, 1.0 - now - int(now)))
    await asyncio.sleep(max(0.02, 1.0 - now - int(now)))
def _norm_candle_shape(raw, min_required: int=30) -> Optional[List[Dict]]:
    if not raw and isinstance(raw, list):
        return
    out = []
    for c in raw:
        if isinstance(c, dict):
            if all((k in c for k in ("open", "high", "low", "close"))):
                try:
                    out.append({"open": float(c["open"]), "high": float(c["high"]), "low": float(c["low"]), "close": float(c["close"]), "time": float(c.get("time", 0))})
                finally:
                    if (ValueError, TypeError):
                        (ValueError, TypeError)
                    elif all((k in c for k in ("o", "h", "l", "c"))):
                        try:
                            out.append({"open": float(c["o"]), "high": float(c["h"]), "low": float(c["l"]), "close": float(c["c"]), "time": float(c.get("time", 0))})
                        finally:
                            if (ValueError, TypeError):
                                (ValueError, TypeError)
                            elif isinstance(c, (list, tuple)) and len(c) >= 5:
                                try:
                                    out.append({"time": float(c[0]), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4])})
                                finally:
                                    if (ValueError, TypeError):
                                        (ValueError, TypeError)
                                    elif len(out) >= min_required:
                                        return out
                                    return
async def fetch_candles_by_symbol(client, symbol: str, period_sec: int=60, count: int=200, timeout: float=3.0) -> Optional[List[Dict]]:
    try:
        end_from_time = time.time()
        offset = count * period_sec
        await asyncio.wait_for(client.get_candles(symbol, end_from_time, offset, period_sec), timeout=timeout)
        raw = await asyncio.wait_for(client.get_candles(symbol, end_from_time, offset, period_sec), timeout=timeout)
    finally:
        return _norm_candle_shape(raw)
        if (asyncio.TimeoutError,
            asyncio.CancelledError):
            (asyncio.TimeoutError,
                asyncio.CancelledError)
            try:
                if hasattr(client, "api") or client.api or hasattr(client.api, "candles"):
                    client.api.candles.candles_data = None
            finally:
                pass
            return
            return
    return
    
    if Exception:
        Exception
    
    if Exception:
        Exception
def candle_name_variants(display: str) -> List[str]:
    s = display.strip()
    
    pure = re.sub("\\s*\\(OTC\\)\\s*", "", s, flags=re.IGNORECASE).strip()
    base = pure.replace(" ", "")
    noslash = base.replace("/", "")
    us = base.replace("/", "_")
    out = []
    
    if is_otc_name(s):
        out += [f"{noslash}_otc", f"{us}_otc", f"{base}_otc"]
    out += [noslash, us, base, pure, s]
    seen = set()
    ret = []
    
    for n in out:
        if n not in seen:
            seen.add(n)
            ret.append(n)
    return ret
async def fetch_candles_safe(client, display_or_symbol: str, tf_key: str, count: int, timeout: float=12.0) -> Optional[List[Dict]]:
    period = {"1m": 60, "m1": 60, "5m": 300, "m5": 300, "15m": 900, "m15": 900}.get(tf_key.lower(), 60)
    await fetch_candles_by_symbol(client, display_or_symbol, period, count, timeout)
    
    out = await fetch_candles_by_symbol(client, display_or_symbol, period, count, timeout)
    if out:
        return out
    for name in candle_name_variants(display_or_symbol):
        if name == display_or_symbol:
            pass
        await fetch_candles_by_symbol(client, name, period, count, timeout)
        out = await fetch_candles_by_symbol(client, name, period, count, timeout)
        if out:
            return out
async def fetch_candles(client, asset: str, period_sec: int=60, count: int=200, timeout: float=12.0) -> Optional[List[Dict]]:
    await fetch_candles_by_symbol(client, asset, period_sec, count, timeout); return await fetch_candles_by_symbol(client, asset, period_sec, count, timeout)
async def parallel_fetch_candles(client, assets: List[str], period_sec: int=60, count: int=200, timeout: float=12.0, max_concurrent: int=6) -> Dict[(str, Optional[List[Dict]])]:
    sem = asyncio.Semaphore(max_concurrent)
    
    async def _one(symbol: str):
        async with sem:
            await fetch_candles_by_symbol(client, symbol, period_sec, count, timeout)
            candles = await fetch_candles_by_symbol(client, symbol, period_sec, count, timeout)
        await ##ERROR##(None, None, None)
        await ##ERROR##(None, None, None); return (symbol, candles); await ###FIXME###
        if not await None:
            pass
    
    tasks = [_one(a) for a in assets]
    await asyncio.gather(return_exceptions=True, *tasks)
    
    results = await asyncio.gather(return_exceptions=True, *tasks)
    out = {}
    for r in results:
        if isinstance(r, Exception):
            pass
        asset, candles = r
        out[asset] = candles
    
    return out
def trade_symbol_candidates(asset_display: str) -> List[str]:
    s = asset_display.strip()
    
    pure = re.sub("\\s*\\(OTC\\)\\s*", "", s, flags=re.IGNORECASE).strip()
    base = pure.replace(" ", "")
    noslash = base.replace("/", "")
    us = base.replace("/", "_")
    out = []
    
    if is_otc_name(s):
        out += [f"{noslash}_otc", f"{us}_otc"]
    out += [noslash, us, s, pure]
    seen = set()
    ret = []
    
    for n in out:
        if n not in seen:
            seen.add(n)
            ret.append(n)
    return ret
async def place_order(client, asset: str, direction: str, amount: float, duration_s: int) -> Tuple[(bool, Dict)]:
    direction_l = direction.lower()
    
    last_err = {"error": "no attempts succeeded"}
    def _reset_buy_state():
        try:
            if hasattr(client, "api") or client.api:
                client.api.buy_id = None
                client.api.buy_successful = None
        finally:
            return
            return
            return
            if Exception:
                Exception
            return
    
    for mode in ("TIME", "TIMER"):
        _reset_buy_state()
        try:
            await asyncio.wait_for(client.buy(amount, asset, direction_l, duration_s, time_mode=mode), timeout=15.0)
            result = await asyncio.wait_for(client.buy(amount, asset, direction_l, duration_s, time_mode=mode), timeout=15.0)
            if isinstance(result, tuple) and len(result) >= 2:
                ok = result[0]
                info = result[1]
            else:
                ok = bool(result)
                info = result
            if ok:
                if not isinstance(info, dict):
                    info = {"id": str(info)}
                elif "id" not in info:
                    for k in ("ticket", "orderId", "request_id", "order_id"):
                        pass
        finally:
            if info in __exception__:
                info["id"] = str(info[k])
                k
            elif "id" not in info:
                try:
                    rid = getattr(client.api, "buy_id", None)
                    if rid:
                        info["id"] = str(rid)
                finally:
                    pass
                if Exception:
                    Exception
                return (True, info)
                last_err = {"error": f"{mode}info if isinstance(info, dict) else ": "{info}"}
                if asyncio.TimeoutError:
                    asyncio.TimeoutError
                    last_err = {"error": f"{mode}: buy() timed out after 15s"}
                    _reset_buy_state()
                elif Exception:
                    Exception
                    e = None
                    try:
                        pass
                    finally:
                        last_err = {{mode}: f": {type(e).__name__}: {e}__exception__"}
                        _reset_buy_state()
                    return (False, last_err)
async def check_result(client, order_id: str, duration_s: int=60, max_extra_wait: float=30.0) -> Tuple[(str, float)]:
    profit = 0.0
    
    total_timeout = float(duration_s) + max_extra_wait
    try:
        await asyncio.wait_for(client.check_win(order_id), timeout=total_timeout)
        ok = await asyncio.wait_for(client.check_win(order_id), timeout=total_timeout)
        return
        if Exception:
            Exception
            e = ("LOSS", profit)
            ("LOSS", profit)
            try:
                try:
                    pass
                finally:
                    profit = client.get_profit()(__exception__)
                if Exception:
                    Exception
                    float
                    float
            finally:
                profit = 0.0
            return __exception__
    except:
        pass
def resolve_credentials() -> Tuple[(str, str)]:
    email = None
    password = None
    
    try:
        from pyquotex.config import credentials
        result = credentials()
        if result:
            if callable(result):
                result = result()
            elif isinstance(result, (list, tuple)) and len(result) >= 2:
                email = result[0]
                password = result[1]
            elif isinstance(result, dict):
                email = result.get("email") or result.get("user")
                password = result.get("password") or result.get("pass")
    if Exception:
        Exception
    elif not email:
        email = os.getenv("QUOTEX_EMAIL")
    
    if not password:
        password = os.getenv("QUOTEX_PASSWORD")
    
    elif not email:
        console.print("[bold cyan]📧 Quotex email:[/bold cyan]")
        try:
            pass
        finally:
            email = __exception__()
        if (EOFError, KeyboardInterrupt):
            (EOFError, KeyboardInterrupt)
            input("➤ ").strip
            input("➤ ").strip
            email = ""
        elif not password:
            console.print("[bold cyan]🔒 Quotex password (hidden):[/bold cyan]")
            try:
                pass
            finally:
                password = __exception__
            if Exception:
                Exception
                getpass("➤ ")
                getpass("➤ ")
                password = ""
            elif not email and password:
                raise RuntimeError("Missing credentials")
    return (email, password)
class _CleanStdout(io.TextIOBase):
    def __init__(self, original, drop_substrings, burst_s=0.35):
        self._orig = original
        if not drop_substrings:
            pass
        self._drop = []
        self._until = 0.0
        self._burst = float(burst_s)
    
    def write(self, s: str):
        try:
            now = time.monotonic()
            if now < self._until:
                pass
        finally:
            return 0
            for sub in self._drop:
                if __exception__ and sub in s:
                    self._until = now + (self._burst)
                    sub
                return 0
        if Exception:
            Exception
        return self._orig.write(s)
    
    def flush(self):
        try:
            pass
        finally:
            return __exception__()
        if Exception:
            Exception
            self._orig.flush
            self._orig.flush
        return
    
    def isatty(self):
        try:
            pass
        finally:
            return __exception__()
        if Exception:
            Exception
            self._orig.isatty
            self._orig.isatty
        return True
    
    def writable(self):
        return True
    
    @property
    def encoding(self):
        try:
            pass
        finally:
            return self._orig.encoding
            if Exception:
                Exception
            return "utf-8"
_NOISE_STDOUT = None
_NOISE_STDERR = None
def enable_noise_filter():
    global _NOISE_STDOUT
    global _NOISE_STDERR
    subs = ['42["orders/open"', "ta agarrado", "Tá agarrado", "{}"]
    
    _NOISE_STDOUT = _CleanStdout(sys.__stdout__, subs)
    sys.stdout = _NOISE_STDOUT
    try:
        _NOISE_STDERR = _CleanStdout(sys.__stderr__, subs)
    finally:
        sys.stderr = _NOISE_STDERR
        return
    if Exception:
        Exception
        __exception__
        __exception__
    return
def noise_burst(seconds: float=1.5):
    try:
        now = time.monotonic()
        if _NOISE_STDOUT:
            _NOISE_STDOUT._until = max(_NOISE_STDOUT._until, now + seconds)
    finally:
        if __exception__:
            _NOISE_STDERR._until = max(_NOISE_STDERR._until, now + seconds)
        return
    return
    if Exception:
        Exception
        _NOISE_STDERR
        _NOISE_STDERR
    return
def get_payout_percent(client, asset: str, tf_key: str="1M") -> Optional[int]:
    try:
        data = client.get_payment() or {}
        d = data.get(asset)
        if d:
            pass
    finally:
        if not __exception__("profit", {}):
            pass
        return d.get({}.get(tf_key.upper()))
    return
    if Exception:
        Exception
        _parse_percent
        _parse_percent
    return
async def discover_assets(client, tf_key: str="1M", only_otc: bool=False, min_payout: int=70, fx_only: bool=True) -> List[Dict]:
    out = []
    await filter_assets(client, only_otc=only_otc, min_payout=min_payout, open_only=True, fx_only=fx_only, tradable_only=True)
    
    filtered = await filter_assets(client, only_otc=only_otc, min_payout=min_payout, open_only=True, fx_only=fx_only, tradable_only=True)
    
    for a in filtered:
        out.append({"asset": a["symbol"], "display_name": a["display_name"], "open": a["is_open"], "otc": a["is_otc"], "payout": a["payout_1m"]})
    return out
def tg_session_start_message(profile_info: Dict, config: "BotConfig", balance: float) -> str:
    profile_id = profile_info.get("profile_id", "—")
    nick_name = profile_info.get("nick_name") or "—"
    if not profile_info.get("country_name") and profile_info.get("country"):
        pass
    country = "—"
    return "".join(["🚀 <b>", {APP_NAME}, " STARTED</b>\n\n👤 <b>Trader:</b> ",
    
    {nick_name}, "\n🆔 <b>ID:</b> <code>",
    
    {profile_id}, "</code>\n🌍 <b>Country:</b> ",
    
    {country}, "\n🏦 <b>Account:</b> ",
    
    {config.account}, "\n💼 <b>Balance:</b> $",
    
    {balance:,.2f}, "\n⏱️ <b>Duration:</b> ",
    
    {config.duration_s}, "s\n💰 <b>Stake:</b> $",
    
    {config.fixed_amount:.2f}, " (",
    
    {config.sizing_mode}, ")\n🎛️ <b>Martingale:</b> ",
    
    {config.mg_mode}, "\n🎯 <b>Strategies:</b> ",
    
    {len(config.enabled_strategies)}, " enabled\n🧠 <b>Smart Voting:</b> ",
    
    {"OFF"}, "\n🔭 <b>MTF:</b> ",
    
    {"OFF"}, "\n🔍 <b>Scanner:</b> top ",
    
    {config.top_n}, " assets in parallel\n📊 <b>OTC only:</b> ",
    
    {"NO"}, "\n💎 <b>Min payout:</b> ",
    
    {config.min_payout}, "%"])
def tg_trade_open_message(asset: str, direction: str, amount: float, duration: int, payout: int, strategy: str, confidence: float, balance: float, entry_price: float=0.0, mg_step: int=0, order_id: str="") -> str:
    dir_emoji = "🔴"
    
    mg_text = ""
    short_id = order_id
    return f"📊 <b>NEW TRADE OPENED</b>{mg_text}\n\n{dir_emoji} <b>{direction.upper()}</b> | <b>{asset}</b>\n💵 <b>Stake:</b> ${amount:.2f}\n⏱️ <b>Duration:</b> {duration}s\n💎 <b>Payout:</b> {payout}%\n🎯 <b>Strategy:</b> {strategy}\n🔥 <b>Confidence:</b> {confidence:.2f}\n📍 <b>Entry:</b> {entry_price:.5f}\n🆔 <b>Order ID:</b> <code>{short_id}</code>\n🏦 <b>Balance:</b> ${balance:,.2f}\n\n⏳ <i>Waiting for result...</i>"
def tg_trade_result_message(asset: str, direction: str, result: str, profit: float, balance: float, strategy: str, wins: int, losses: int, total_pnl: float, entry_price: float=0.0, exit_price: float=0.0, mg_step: int=0, order_id: str="") -> str:
    if result == "WIN":
        emoji = "✅"
        color_word = "🎉 WIN"
    
    elif result == "LOSS":
        emoji = "❌"
        color_word = "💔 LOSS"
    
    elif result == "DRAW":
        emoji = "⚪"
        color_word = "🤝 DRAW"
    else:
        emoji = "⚠️"
        color_word = "❓ UNKNOWN"
    
    total = wins + losses
    
    winrate = 0
    pnl_emoji = "📉"
    mg_text = ""
    short_id = order_id
    return "".join([{emoji}, " <b>", {color_word}, "</b>", {mg_text}, "\n\n📊 <b>",
    
    {asset}, "</b> | <b>",
    
    {direction.upper()}, "</b>\n💰 <b>P/L:</b> $",
    
    {profit:+.2f}, "\n📍 <b>Entry → Exit:</b> ",
    
    {entry_price:.5f}, " → ",
    
    {exit_price:.5f}, "\n🎯 <b>Strategy:</b> ",
    
    {strategy}, "\n🆔 <b>Order:</b> <code>",
    
    {short_id}, "</code>\n🏦 <b>Balance:</b> $",
    
    {balance:,.2f}, "\n\n📊 <b>SESSION STATS</b>\n   Wins: ",
    
    {wins}, " | Losses: ",
    
    {losses}, "\n   Winrate: ",
    
    {winrate:.1f}, "%\n   ",
    
    {pnl_emoji}, " Total P/L: $",
    
    {total_pnl:+.2f}])
def tg_session_summary(stats: "Statistics") -> str:
    total = (stats.wins) + (stats.losses)
    wr = 0
    pnl_emoji = "📉"
    return f"🛑 <b>SESSION ENDED</b>\n\n📊 Trades: {total}\n✅ Wins: {stats.wins}\n❌ Losses: {stats.losses}\n⚪ Draws: {stats.draws}\n⚠️  Fails: {stats.fails}\n🎯 Winrate: {wr:.1f}%\n🔥 Max win streak: {stats.max_win_streak}\n💔 Max loss streak: {stats.max_loss_streak}\n{pnl_emoji} Total P/L: ${stats.total_pnl:+.2f}\n🏦 Final balance: ${stats.current_balance:,.2f}"
STRATEGY_DESCRIPTIONS = {"JOKER": "🃏 Multi-indicator confluence",
    
    "MOMENTUM": "⚡ Pure momentum follow",
    
    "RSI_EXTREME": "📊 RSI 70/30 reversal",
    
    "BOLLINGER_REVERSAL": "🎯 BB touch & bounce",
    
    "AB_PATTERN": "🅰️🅱️ A-B-A reversal",
    
    "EMA_CROSS_9_21": "📈 EMA 9/21 cross",
    
    "EMA_CROSS_12_26": "📈 EMA 12/26 cross",
    
    "EMA_CROSS_21_50": "📈 EMA 21/50 cross",
    
    "EMA_CROSS_50_200": "📈 Golden/Death cross",
    
    "EMA_PULLBACK_21": "📉 EMA 21 pullback",
    
    "EMA_PULLBACK_50": "📉 EMA 50 pullback",
    
    "MACD_CROSS": "📊 MACD signal cross",
    
    "MACD_ZERO": "📊 MACD zero cross",
    
    "SUPERTREND_FLIP": "🔄 SuperTrend flip",
    
    "HEIKIN_ASHI_TREND": "🕯️ HA trend",
    
    "ADX_TREND": "💪 ADX > 25",
    
    "PSAR_FLIP": "📍 PSAR flip",
    
    "STOCH_CROSS": "🎰 Stochastic K/D",
    
    "CCI_EXTREME": "📐 CCI > 200/-200",
    
    "WILLIAMS_R": "🌊 Williams %R",
    
    "RSI_DIVERGENCE": "↔️ RSI divergence",
    
    "DONCHIAN_BREAK_20": "🚀 Donchian 20 break",
    
    "DONCHIAN_BREAK_50": "🚀 Donchian 50 break",
    
    "KELTNER_BREAK_15": "🌪️ Keltner 15 break",
    
    "KELTNER_BREAK_20": "🌪️ Keltner 20 break",
    
    "BB_SQUEEZE": "🔨 BB squeeze break",
    
    "ATR_BREAKOUT": "💥 ATR breakout",
    
    "AROON_TREND": "🏹 Aroon trend",
    
    "ENGULFING": "🕯️ Engulfing pattern",
    
    "THREE_SOLDIERS": "⚔️ 3 soldiers/crows",
    
    "HAMMER": "🔨 Hammer pattern",
    
    "PINBAR": "📌 Pinbar rejection",
    
    "INSIDE_BAR": "📦 Inside bar break",
    
    "OTC_FORTRESS": "🏰 OTC fortress",
    
    "OTC_HEIKEN": "🕯️ OTC HA smoothed",
    
    "OTC_TRIPLE_MA": "📊 OTC triple MA",
    
    "OTC_BB_RSI": "🎯 OTC BB + RSI",
    
    "PRICE_ACTION": "💎 Price action",
    
    "RANGE_FADE": "📏 Range fade",
    
    "BULLS_BEARS_POWER": "🐂🐻 Bulls/Bears",
    
    "VWAP_REVERSION": "📊 VWAP revert",
    
    "TRIPLE_EMA": "🎲 EMA stack",
    
    "FRACTAL_REVERSAL": "🌀 Fractal pivot",
    
    "ROC_MOMENTUM": "⚡ ROC momentum",
    
    "HARAMI": "🤰 Harami inside",
    
    "MORNING_STAR": "🌟 Morning/Evening",
    
    "DOJI_REVERSAL": "✚ Doji reversal",
    
    "BB_BOUNCE": "🎯 BB bounce",
    
    "RSI_CROSS_50": "📍 RSI 50 cross",
    
    "STOCHASTIC_DIVERGENCE": "↔️ Stoch divergence",
    
    "TREND_STRENGTH": "💪 ADX strength",
    "TWO_CANDLE_MOMENTUM": "🚀 2-candle push", "PIVOT_POINT": "🎯 Pivot bounce", "VOLATILITY_BREAKOUT": "💥 ATR expansion", "TWEEZER": "👐 Tweezer top/bottom", "GAP_FILL": "📐 Gap fill", "TRIPLE_TOP_BOTTOM": "🔱 Triple top/bottom", "OTC_QUIET_ZONE": "🤫 OTC quiet break", "FIBONACCI_RETRACEMENT": "🌀 Fib 38/50/61", "KELTNER_PULLBACK": "🌪️ Keltner pullback", "SR_REVERSAL": "📏 S/R reversal", "TIME_OF_DAY_BIAS": "🕐 Time-of-day bias", "CCI_TURN": "🔄 CCI turn", "RANGE_BREAKOUT": "📐 Range break"}
class LiveDashboard:
    """Professional live-updating dashboard.
        
        Features:
          - Trader profile (name + ID)
          - Account, balance, W/L, winrate, PnL
          - Open Trade panel with countdown progress bar
          - Scanning panel showing assets being probed
          - Recent trades table WITH ORDER ID
          - Events feed
          - All updates 4Hz via rich.Live
        """
    def __init__(self, config=None, stats=None):
        self.config = config
        self.stats = stats
        self.mode = "TRADING"
        
        self.profile_id = None
        
        self.nick_name = None
        self.account = "PRACTICE"
        
        self.balance = 0.0
        self.universe = 0
        self.connection_status = "🟢 Connected"
        self.current_asset = ""
        
        self.last_signal_info = ""
        self.scanning_assets = []
        
        self.scan_progress = {}
        self.scan_signals = []
        self.countdown_label = ""
        
        self.countdown_until = 0.0
        self.countdown_total = 0.0
        self.current_trade = None
        
        self.event_log = []
        
        self.max_events = 10
        self.session_start = datetime.now()
    
    def log_event(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.event_log.append((ts, message))
        if len(self.event_log) > self.max_events:
            self.event_log.pop(0)
            return
    
    def update_signal(self, asset: str, direction: Optional[str], confidence: float=0.0, strategy: str=""):
        self.current_asset = asset
        if direction:
            color = "red"
            self.last_signal_info = f"[bold {color}]{direction.upper()}[/] | conf {confidence:.2f} | {strategy}"
            return
        self.last_signal_info = "[dim]No signal[/dim]"
    
    def set_scanning(self, assets: List[str]):
        self.scanning_assets = list(assets)
        
        self.scan_progress = {a: "..." for a in assets}
        self.scan_signals = []
    
    def update_scan_status(self, asset: str, status: str):
        self.scan_progress[asset] = status
    
    def add_scan_signal(self, asset: str, direction: str, score: float, strategy: str):
        self.scan_signals.append((asset, direction, score, strategy))
    
    def clear_scanning(self):
        self.scanning_assets = []
        self.scan_progress = {}
        self.scan_signals = []
    
    def set_countdown(self, label: str, seconds: float):
        self.countdown_label = label
        self.countdown_until = time.time() + max(0.0, float(seconds))
        self.countdown_total = max(0.1, float(seconds))
    
    def clear_countdown(self):
        self.countdown_label = ""
        self.countdown_until = 0.0
        self.countdown_total = 0.0
    
    def open_trade(self, asset: str, direction: str, stake: float, duration_seconds: int, entry_price: float=0.0, order_id: str=""):
        now = time.time()
        
        self.current_trade = {"asset": asset, "direction": direction.upper(), "stake": float(stake), "start_at": now, "expire_at": now + float(duration_seconds), "duration": float(duration_seconds), "entry_price": float(entry_price), "order_id": order_id}
    
    def close_trade(self):
        self.current_trade = None
    
    def update(self, **kwargs):
        for k, v in kwargs.items():
            if k == "status":
                self.connection_status = v
            elif k == "hint":
                if v:
                    self.log_event(v)
            elif k == "balance":
                self.balance = v
            elif hasattr(self, k):
                setattr(self, k, v)
    
    def draw(self, stats=None, force=False):
        if stats is not None:
            self.stats = stats
            return
    
    def __rich__(self):
        return self.render()
    
    def render(self):
        now = time.time()
        
        duration = datetime.now() - (self.session_start)
        
        h = int(duration.total_seconds() // 3600)
        m = int(duration.total_seconds() % 3600 // 60)
        s = int(duration.total_seconds() % 60)
        dur_str = f"{h:02d}:{m:02d}:{s:02d}"
        stats_tbl = Table.grid(padding=(0, 2), expand=True)
        
        stats_tbl.add_column(style="cyan", justify="right")
        stats_tbl.add_column(style="bold")
        stats_tbl.add_column(style="cyan", justify="right")
        stats_tbl.add_column(style="bold")
        trader_disp = self.nick_name or "—"
        
        id_disp = "—"
        stats_tbl.add_row("Trader:", trader_disp, "ID:", id_disp)
        bal_color = "white"
        
        mode_color = "red"
        
        stats_tbl.add_row("Balance:", f"[{bal_color}]${self.balance:,.2f}[/]", "Account:", f"[{mode_color}]{self.account}[/]")
        
        s2 = self.stats
        
        if s2:
            pnl_color = "red"
            stats_tbl.add_row("W / L:", f"[green]{s2.wins}[/] / [red]{s2.losses}[/]", "P&L:", f"[{pnl_color}]${s2.total_pnl:+.2f}[/]")
            wr_color = "red"
            stats_tbl.add_row("Winrate:", f"[{wr_color}]{s2.winrate:.1f}%[/]", "Max LStreak:", f"[red]{s2.max_loss_streak}[/]")
        
        universe_disp = "—"
        
        stats_tbl.add_row("Session:", dur_str, "Open Assets:", universe_disp)
        if not self.current_asset:
            pass
        stats_tbl.add_row("Status:", self.connection_status, "Current:", "—")
        
        countdown_panel = None
        
        if self.countdown_until > now and self.countdown_label:
            remaining = (self.countdown_until) - now
            total_secs = getattr(self, "countdown_total", remaining + 0.1)
            bar_width = 40
            pct_done = max(0.0, min(1.0, 1.0 - remaining / total_secs))
            filled = int(bar_width * pct_done)
            bar = "█" * filled + "░" * (bar_width - filled)
            countdown_panel = Panel(f"[cyan]{self.countdown_label}[/cyan]\n[yellow]{bar}[/yellow]   [bold yellow]{remaining:5.1f}s[/bold yellow]   [dim]{pct_done * 100:.0f}% of {total_secs:.0f}s[/dim]", border_style="yellow", title="⏱  Countdown", title_align="left")
        
        open_trade_panel = None
        
        if self.current_trade:
            t = self.current_trade
            elapsed = max(0.0, now - t["start_at"])
            remaining = max(0.0, t["expire_at"] - now)
            total = max(t["duration"], 0.1)
            bar_width = 50
            pct = min(1.0, elapsed / total)
            filled = int(bar_width * pct)
            if pct < 0.5:
                bar_color = "green"
            elif pct < 0.85:
                bar_color = "yellow"
            else:
                bar_color = "red"
            bar = "█" * filled + "░" * (bar_width - filled)
            dir_color = "red"
            short_id = t.get("order_id", "")
            if len(short_id) > 16:
                short_id = short_id[:13] + "..."
            ot_tbl = Table.grid(padding=(0, 2), expand=True)
            ot_tbl.add_column(style="cyan", justify="right")
            ot_tbl.add_column(style="bold")
            ot_tbl.add_column(style="cyan", justify="right")
            ot_tbl.add_column(style="bold")
            ot_tbl.add_row("Asset:", t["asset"], "Direction:", f"[{dir_color}]{t["direction"]}[/]")
            ot_tbl.add_row("Stake:", f"${t["stake"]:.2f}", "Entry:", "—")
            ot_tbl.add_row("Order ID:", "—", "Elapsed:", f"[bold]{elapsed:5.1f}s[/]")
            ot_tbl.add_row("Duration:", f"{int(total)}s", "⏳ Remaining:", f"[bold yellow]{remaining:5.1f}s[/]")
            open_trade_panel = Panel(Group(ot_tbl, "", f"[{bar_color}]{bar}[/{bar_color}]  [bold]{pct * 100:5.1f}%[/bold] [dim]of {total:.0f}s[/dim]"), border_style=dir_color, title="📍 OPEN TRADE — Live Countdown", title_align="left")
        
        scan_panel = None
        
        if not self.scanning_assets and self.current_trade:
            done = sum((1 for v in self.scan_progress.values()))
            total = len(self.scanning_assets)
            scan_pct = done / max(total, 1) * 100
            bar_width = 50
            filled = int(bar_width * done / max(total, 1))
            scan_bar = "█" * filled + "░" * (bar_width - filled)
            scan_tbl = Table.grid(padding=(0, 1), expand=True)
            scan_tbl.add_column(style="cyan", width=18)
            scan_tbl.add_column(style="white")
            scan_tbl.add_column(style="cyan", width=18)
            scan_tbl.add_column(style="white")
            items = []
            for a in self.scanning_assets:
                status = self.scan_progress.get(a, "...")
                if status == "...":
                    disp = "[dim]scanning...[/dim]"
                elif status.startswith("✓"):
                    disp = f"[green]{status}[/green]"
                elif status.startswith("✗"):
                    disp = f"[dim red]{status}[/dim red]"
                else:
                    disp = status
                items.append((a, disp))
            for i in range(0, len(items), 2):
                left = items[i]
                right = ("", "")
                scan_tbl.add_row(left[0], left[1], right[0], right[1])
            while self.scan_signals:
                sig_text = ""
                top_sigs = sorted(self.scan_signals, key=(lambda x: -x[2]))[:5]
                for asset, direction, score, strat in top_sigs:
                    color = "red"
                    sig_text += f"  ✓ [{color}]{direction}[/] {asset} ({strat}) [yellow]{score:.2f}[/]\n"
                scan_content = Group(f"[cyan]{scan_bar}[/cyan]  [bold]{done}/{total}[/bold] [dim]({scan_pct:.0f}%)[/dim]", "", scan_tbl, "", f"[bold]Signals found ({len(self.scan_signals)}):[/bold]\n{sig_text}")
            scan_content = Group(f"[cyan]{scan_bar}[/cyan]  [bold]{done}/{total}[/bold] [dim]({scan_pct:.0f}%)[/dim]", "", scan_tbl)
            scan_panel = Panel(scan_content, border_style="cyan", title=f"🔍 SCANNING {total} ASSETS — {done} done", title_align="left")
        
        trades_tbl = Table(title="📊 Recent Trades", title_style="bold cyan", box=box.ROUNDED, show_lines=False, expand=True)
        
        trades_tbl.add_column("#", style="dim", justify="right", width=4)
        
        trades_tbl.add_column("Time", style="dim", width=10)
        trades_tbl.add_column("Asset", style="cyan", no_wrap=True)
        trades_tbl.add_column("Dir", justify="center", width=5)
        trades_tbl.add_column("Stake", justify="right", width=8)
        trades_tbl.add_column("Strategy", width=14, no_wrap=True)
        trades_tbl.add_column("Order ID", style="dim", width=14, no_wrap=True)
        trades_tbl.add_column("Result", justify="center", width=8)
        trades_tbl.add_column("P&L", justify="right", width=10)
        trades_tbl.add_column("MG", justify="center", width=4)
        recent = []
        
        if self.stats and self.stats.trades:
            recent = self.stats.trades[-8:]
        
        elif recent:
            n_total = len(self.stats.trades)
            start_idx = n_total - len(recent) + 1
            for i, tr in enumerate(recent):
                rc = "dim"
                dc = "red"
                if tr.result == "WIN":
                    result_disp = "✅ WIN"
                elif tr.result == "LOSS":
                    result_disp = "❌ LOSS"
                elif tr.result == "DRAW":
                    result_disp = "⚪ DRAW"
                else:
                    result_disp = "⚠ FAIL"
                time_str = tr.timestamp[11:19] if len(tr.timestamp) > 19 else tr.timestamp
                oid = tr.order_id or "—"
                if len(oid) > 12:
                    oid = oid[:11] + "…"
                elif not tr.strategy:
                    pass
                trades_tbl.add_row(str(start_idx + i), time_str, tr.asset[:14], f"[{dc}]{tr.direction.upper()}[/]", f"${tr.amount:.2f}", "—"[:14], oid, f"[{rc}]{result_disp}[/]", f"[{rc}]${tr.profit:+.2f}[/]", "—")
        
        else:
            trades_tbl.add_row("—", "—", "—", "—", "—", "—", "—", "—", "—", "—")
        
        signal_tbl = Table.grid()
        
        signal_tbl.add_column()
        if not self.last_signal_info:
            pass
        signal_tbl.add_row(f"[cyan]Last Signal:[/cyan] {"—"}")
        events_tbl = Table.grid(padding=(0, 1))
        
        events_tbl.add_column(style="dim", width=10)
        events_tbl.add_column()
        
        while self.event_log:
            for ts, msg in self.event_log[-self.max_events:]:
                events_tbl.add_row(f"[dim]{ts}[/dim]", msg)
        
        events_tbl.add_row("[dim]—[/dim]", "[dim]Waiting for activity…[/dim]")
        
        events_panel = Panel(events_tbl, title="📡 Events", title_align="left", border_style="dim")
        
        if self.mode == "SCAN_ONLY":
            hint_text = "Press Ctrl+C to return to main menu (or twice quickly to exit)"
        else:
            hint_text = "Press Ctrl+C to stop trading and return to main menu (or twice quickly to exit)"
        
        hint = Text(hint_text, style="dim italic", justify="center")
        parts = [stats_tbl]
        
        if countdown_panel:
            parts.append(countdown_panel)
        
        elif open_trade_panel:
            parts.append(open_trade_panel)
        
        elif scan_panel:
            parts.append(scan_panel)
        parts.append(signal_tbl)
        
        if self.mode != "SCAN_ONLY":
            parts.append(trades_tbl)
        parts.append(events_panel)
        parts.append(hint)
        content = Group(*parts)
        
        title_suffix = "Live Dashboard"
        return Panel(content, title=f"🤖 {APP_NAME} — {title_suffix}", border_style="cyan", padding=(0, 1))
class Trader:
    """Main trading orchestrator with:
          - PARALLEL asset scanner (asyncio.gather)
          - Live dashboard showing scanning progress + countdown
          - Order ID tracking
          - Self-learning per-strategy win-rate
          - Documented pyquotex API only
        """
    
    def __init__(self, client, config: "BotConfig", tg: "TelegramBot", screenshot: "ScreenshotManager", csv_log: "CSVLogger", scheduler: "TradingScheduler"):
        self.client = client
        
        self.config = config
        self.tg = tg
        self.screenshot = screenshot
        self.csv_log = csv_log
        self.scheduler = scheduler
        self.stats = Statistics()
        
        self.dash = LiveDashboard(config, self.stats)
        self.trade_is_open = False
        self.last_trade_minute = None
        self.profile_info = {}
        self._asset_universe = []
        
        self._universe_refresh_ts = 0.0
        self._universe_ttl_s = 60.0
        
        mg_cfg = MartingaleConfig(mode=_coerce_mg_mode(config.mg_mode), base_amount=config.mg_base, multiplier=config.mg_multiplier, max_steps=config.mg_max_steps, min_amount=config.mg_min, max_amount=config.mg_max, fib_start_index=config.mg_fib_start, fib_scale=config.mg_fib_scale, custom_sequence=list(config.mg_custom_sequence), sequence_is_multiplier=config.mg_seq_is_multiplier, reset_on_win=config.mg_reset_on_win, round_to=config.mg_round_to)
        
        self.mg = MartingaleManager(mg_cfg)
        
        self.anti_tilt = AntiTiltState(max_consecutive_losses=config.max_consecutive_losses, cooldown_after_losses_minutes=config.cooldown_after_losses_minutes, daily_loss_pct_limit=config.daily_loss_pct_limit, cooldown_after_single_loss_candles=config.cooldown_after_single_loss_candles)
    
    async def run(self):
        cfg = self.config
        await ensure_account(self.client, cfg.account)
        await ensure_account(self.client, cfg.account)
        
        try:
            await asyncio.wait_for(ensure_instruments_loaded(self.client, timeout=15.0), timeout=20.0)
            await asyncio.wait_for(ensure_instruments_loaded(self.client, timeout=15.0), timeout=20.0)
        finally:
            pass
        if Exception:
            Exception
        await get_profile_info(self.client)
        self.profile_info = await get_profile_info(self.client)
        self.dash.profile_id = self.profile_info.get("profile_id")
        self.dash.nick_name = self.profile_info.get("nick_name")
        try:
            await self.client.get_balance()
            bal = await self.client.get_balance()
            self.stats.current_balance = float(bal)
        finally:
            self.stats.start_balance = float(bal)
            self.dash.balance = self.stats.current_balance
        if Exception:
            Exception
            e = __exception__
            __exception__
            try:
                self.dash.log_event(f"⚠ Balance fetch: {e}")
            finally:
                pass
            self.dash.account = cfg.account
            self.dash.log_event(f"🚀 Trading started on {cfg.account}")
            if self.dash.profile_id:
                self.dash.log_event(f"👤 {self.dash.nick_name} (ID: {self.dash.profile_id})")
        
        if cfg.anti_tilt_enabled:
            self.anti_tilt.set_day_start(self.stats.current_balance)
            self.dash.log_event(f"🛡 Quality filters ON • Anti-tilt: max {cfg.max_consecutive_losses} losses → {cfg.cooldown_after_losses_minutes}min pause")
        await self._refresh_asset_universe()
        await self._refresh_asset_universe()
        if self.tg.enabled:
            try:
                self.tg.send(tg_session_start_message(self.profile_info, cfg, self.stats.current_balance))
            finally:
                pass
            if Exception:
                Exception
            stopped_by_user = False
            try:
                try:
                    with Live(self.dash, refresh_per_second=4, console=console, transient=False, screen=False) as live:
                        await self._main_loop(live)
                finally:
                    __exception__
                    await self._main_loop(live)(None, None, None)
            if (KeyboardInterrupt, asyncio.CancelledError):
                (KeyboardInterrupt, asyncio.CancelledError)
                stopped_by_user = True
                self.dash.log_event("⏹ Stopped by user (Ctrl+C) — returning to menu…")
            elif Exception:
                Exception
                e = None
                try:
                    self.dash.log_event(f"✗ Error: {type(e).__name__}: {e}")
                    console.print(f"\n[red]Trading error:[/red] {e}")
                finally:
                    pass
                try:
                    if self.tg.enabled:
                        pass
                finally:
                    pass
                __exception__(tg_session_summary(self.stats))
                if Exception:
                    Exception
                    self.tg.send
                    self.tg.send
                elif stopped_by_user:
                    console.print("\n[yellow]⏹ Trading stopped — back to main menu[/yellow]")
                    return
        
        try:
            if self.tg.enabled:
                pass
        finally:
            pass
        __exception__(tg_session_summary(self.stats))
        if Exception:
            Exception
            self.tg.send
            self.tg.send
        elif stopped_by_user:
            console.print("\n[yellow]⏹ Trading stopped — back to main menu[/yellow]")
    
    async def _refresh_asset_universe(self):
        now = time.time()
        if now - (self._universe_refresh_ts) < self._universe_ttl_s and self._asset_universe:
            return
        cfg = self.config
        try:
            await filter_assets(self.client, only_otc=cfg.only_otc, min_payout=cfg.min_payout, open_only=True, fx_only=False, tradable_only=False)
            assets = await filter_assets(self.client, only_otc=cfg.only_otc, min_payout=cfg.min_payout, open_only=True, fx_only=False, tradable_only=False)
            self._asset_universe = assets
            self._universe_refresh_ts = now
            self.dash.universe = len(assets)
            if assets:
                otc = sum((1 for a in assets))
        finally:
            fx = __exception__
            non_fx = len(assets) - fx
            self.dash.log_event(f"🔄 Universe: {len(assets)} open ({otc} OTC, {fx} FX, {non_fx} other), top payout {assets[0]["payout_1m"]}%")
            return
        self.dash.log_event("⚠ No assets open — try lowering min_payout")
        return
        if Exception:
            Exception
            e = sum((1 for a in assets))
            sum((1 for a in assets))
            try:
                pass
            finally:
                __exception__
            return
    
    async def _main_loop(self, live):
        cfg = self.config
        
        active, reason = self.scheduler.is_active_now()
        while not active:
            self.dash.connection_status = "⏸ Paused (schedule)"
            self.dash.log_event(f"⏸ {reason}")
            await asyncio.sleep(30)
            await asyncio.sleep(30)
        self.dash.connection_status = "🟢 Connected"
        
        pnl = self.stats.total_pnl
        if cfg.session_tp > 0 and pnl >= cfg.session_tp:
            self.dash.log_event(f"🎯 Session TP hit: ${pnl:+.2f}")
            if self.tg.enabled:
                self.tg.send(f"🎯 <b>Session TP hit!</b>\nPnL: ${pnl:+.2f}")
            return
        elif cfg.session_sl > 0 and pnl <= -cfg.session_sl:
            self.dash.log_event(f"🛑 Session SL hit: ${pnl:+.2f}")
            if self.tg.enabled:
                self.tg.send(f"🛑 <b>Session SL hit!</b>\nPnL: ${pnl:+.2f}")
            return
        cur_min = datetime.now().strftime("%Y-%m-%d %H:%M")
        while cfg.one_trade_only and self.last_trade_minute == cur_min:
            await asyncio.sleep(2)
            await asyncio.sleep(2)
        
        await self._refresh_asset_universe()
        await self._refresh_asset_universe()
        while not self._asset_universe:
            self.dash.log_event("⚠ No assets in universe — relax filters")
            await asyncio.sleep(10)
            await asyncio.sleep(10)
        
        await self._find_signal_parallel()
        
        found = await self._find_signal_parallel()
        while not found:
            self.dash.clear_scanning()
            await asyncio.sleep(3)
            await asyncio.sleep(3)
        
        if len(found) >= 7:
            asset_symbol, direction, payout, strategy, confidence, candles, asset_display = found
        
        else:
            asset_symbol, direction, payout, strategy, confidence, candles = found[:6]
            asset_display = asset_symbol
        self.dash.update_signal(asset_display, direction, confidence, strategy)
        if not self.stats.current_balance:
            pass
        base_amount = next_amount(balance=self.stats.start_balance, rp=RiskParams(sizing_mode=cfg.sizing_mode, fixed_amount=cfg.fixed_amount, risk_percent=cfg.risk_percent, min_amount=cfg.min_amount, max_amount=cfg.max_amount))
        
        if self.mg.cfg.mode != "OFF" and self.mg.current_step > 0:
            amount = self.mg.current_amount(balance=self.stats.current_balance)
        
        else:
            amount = base_amount
            self.mg.cfg.base_amount = base_amount
        wait_s = seconds_until_next_candle(60)
        
        if wait_s < 3.0 and wait_s > 0.1:
            self.dash.log_event(f"⏱ Only {wait_s:.1f}s — wait next candle")
            await asyncio.sleep(wait_s + 0.3)
            await asyncio.sleep(wait_s + 0.3)
            wait_s = seconds_until_next_candle(60)
        self.dash.set_countdown(f"⏳ Waiting candle boundary on {asset_display}", wait_s)
        await wait_until_next_candle(60, offset_ms=cfg.entry_offset_ms)
        await wait_until_next_candle(60, offset_ms=cfg.entry_offset_ms)
        
        self.dash.clear_countdown()
        self.dash.clear_scanning()
        self.dash.log_event(f"🎯 Placing {direction} on {asset_display} ${amount:.2f}")
        
        noise_burst(2.0)
        
        entry_price = 0.0
        
        try:
            await place_order(self.client, asset_symbol, direction, amount, cfg.duration_s)
            ok, info = await place_order(self.client, asset_symbol, direction, amount, cfg.duration_s)
        finally:
            pass
        if Exception:
            Exception
            e = None
            try:
                ok = False
                info = {"error": f"place_order exception: {type(e).__name__}: {e}"}
            finally:
                pass
            while not ok:
                if isinstance(info, dict):
                    err = info.get("error", str(info))
                else:
                    err = "no response from server"
                self.dash.log_event(f"❌ Order failed: {err}")
                self.stats.fails += 1
                fail_record = TradeResult(timestamp=datetime.now().isoformat(timespec="seconds"), asset=asset_display, direction=direction, amount=amount, duration_s=cfg.duration_s, payout_pct=payout, result="FAIL", profit=0.0, balance=self.stats.current_balance, order_id="—", strategy=strategy, confidence=confidence, mg_step=self.mg.current_step, entry_price=entry_price, exit_price=entry_price)
                self.stats.add_trade(fail_record)
                await asyncio.sleep(2)
                await asyncio.sleep(2)
            order_id = ""
            if isinstance(info, dict):
                if not info.get("id") and info.get("ticket") and info.get("orderId") and info.get("order_id"):
                    pass
                order_id = str("")
        
        if not order_id:
            order_id = f"order_{int(time.time())}"
        self.trade_is_open = True
        
        self.last_trade_minute = cur_min
        self.dash.open_trade(asset_display, direction, amount, cfg.duration_s, entry_price, order_id)
        
        short_oid = order_id
        self.dash.log_event(f"✅ OPENED {direction} {asset_display} ${amount:.2f} (ID: {short_oid})")
        
        if self.tg.enabled:
            self.tg.send(tg_trade_open_message(asset=asset_display, direction=direction, amount=amount, duration=cfg.duration_s, payout=payout, strategy=strategy, confidence=confidence, balance=self.stats.current_balance, entry_price=entry_price, mg_step=self.mg.current_step, order_id=order_id))
            chart_path = self._render_chart_image(candles, asset_display, direction, strategy)
            if chart_path:
                self.tg.send_photo(chart_path, f"📊 Entry — {asset_display} {direction}")
        
        elif Exception:
            Exception
        
        self.dash.set_countdown("⏳ Trade running — waiting result", float(cfg.duration_s))
        await check_result(self.client, order_id, duration_s=cfg.duration_s, max_extra_wait=30.0)
        
        state, profit = await check_result(self.client, order_id, duration_s=cfg.duration_s, max_extra_wait=30.0)
        
        self.dash.clear_countdown()
        
        self.dash.close_trade()
        await fetch_candles_by_symbol(self.client, asset_symbol, 60, 5, timeout=4.0)
        
        exit_candles = await fetch_candles_by_symbol(self.client, asset_symbol, 60, 5, timeout=4.0)
        exit_price = entry_price
        
        if Exception:
            Exception
            exit_price = entry_price
        await self.client.get_balance()
        
        new_bal = await self.client.get_balance()
        self.stats.current_balance = float(new_bal)
        self.dash.balance = self.stats.current_balance
        
        if Exception:
            Exception
            new_bal = self.stats.current_balance
        
        trade_record = TradeResult(timestamp=datetime.now().isoformat(timespec="seconds"), asset=asset_display, direction=direction, amount=amount, duration_s=cfg.duration_s, payout_pct=payout, result=state, profit=profit, balance=new_bal, order_id=order_id, strategy=strategy, confidence=confidence, mg_step=self.mg.current_step, entry_price=entry_price, exit_price=exit_price)
        
        self.stats.add_trade(trade_record)
        
        self.mg.register_result(win=state == "WIN")
        
        if cfg.anti_tilt_enabled and state in ("WIN", "LOSS"):
            self.anti_tilt.register_trade_result(won=state == "WIN", current_minute=datetime.now().strftime("%Y-%m-%d %H:%M"))
            if state == "LOSS" and self.anti_tilt.consecutive_losses >= cfg.max_consecutive_losses:
                self.dash.log_event(f"⛔ Anti-tilt activated: {self.anti_tilt.consecutive_losses} losses → pause {cfg.cooldown_after_losses_minutes}min")
        
        elif cfg.use_pattern_memory and state in ("WIN", "LOSS"):
            record_pattern_outcome(asset=asset_display, strategy_label=strategy, direction=direction.upper(), won=state == "WIN")
        
        elif Exception:
            Exception
        
        elif cfg.voting_enabled and state in ("WIN", "LOSS"):
            record_all_strategies_outcome(candles, direction.upper(), state == "WIN")
        elif Exception:
            Exception
        
        elif self.csv_log.enabled:
            self._log_csv(trade_record)
        
        elif state == "WIN":
            icon = "✅"
        
        elif state == "LOSS":
            icon = "❌"
        
        elif state == "DRAW":
            icon = "⚪"
        else:
            icon = "⚠"
        
        self.dash.log_event(f"{icon} {state} {asset_display} ${profit:+.2f} • Bal ${new_bal:.2f} (WR {self.stats.winrate:.1f}%)")
        
        if self.tg.enabled:
            self.tg.send(tg_trade_result_message(asset=asset_display, direction=direction, result=state, profit=profit, balance=new_bal, strategy=strategy, wins=self.stats.wins, losses=self.stats.losses, total_pnl=self.stats.total_pnl, entry_price=entry_price, exit_price=exit_price, mg_step=self.mg.current_step, order_id=order_id))
            result_chart = self._render_result_chart(trade_record, self.stats.trades[-10:])
            if result_chart:
                self.tg.send_photo(result_chart, f"📊 Result — {state}")
        
        elif Exception:
            Exception
        
        self.trade_is_open = False
        await asyncio.sleep(1.0)
        await asyncio.sleep(1.0)
    
    async def _fetch_and_analyze_one(self, asset_dict: Dict, fetch_m5: bool, fetch_m15: bool) -> Optional[Tuple]:
        cfg = self.config
        
        symbol = asset_dict["symbol"]
        display = asset_dict.get("display_name", symbol)
        payout = asset_dict["payout_1m"]
        progress_key = display
        try:
            await fetch_candles_by_symbol(self.client, symbol, 60, 200, timeout=2.5)
            m1 = await fetch_candles_by_symbol(self.client, symbol, 60, 200, timeout=2.5)
            if m1 and len(m1) < 30:
                await fetch_candles_safe(self.client, display, "1m", 200, timeout=2.0)
                m1 = await fetch_candles_safe(self.client, display, "1m", 200, timeout=2.0)
            elif m1 and len(m1) < 30:
                self.dash.update_scan_status(progress_key, "✗ no candles")
        finally:
            return
            m5 = None
            m15 = None
            if fetch_m5:
                await fetch_candles_by_symbol(self.client, symbol, 300, 100, timeout=2.5)
                m5 = await fetch_candles_by_symbol(self.client, symbol, 300, 100, timeout=2.5)
            elif fetch_m15:
                await fetch_candles_by_symbol(self.client, symbol, 900, 80, timeout=2.5)
                m15 = await fetch_candles_by_symbol(self.client, symbol, 900, 80, timeout=2.5)
            elif cfg.voting_enabled:
                sig, score, details = smart_vote(candles_m1=m1, candles_m5=m5, candles_m15=m15, min_agree=cfg.voting_min_agree, use_weights=cfg.voting_use_weights, use_mtf=cfg.voting_use_mtf, mtf_strict=cfg.mtf_strict, enabled_strategies=cfg.enabled_strategies)
                regime = details.get("regime", "?")
                regime_short = {"TRENDING": "TR", "RANGING": "RG", "VOLATILE": "VL", "NEUTRAL": "NE"}.get(regime, "?")
                if sig and score >= cfg.voting_min_score:
                    strat_label = f"V({details.get("call_count", 0)}C/{details.get("put_count", 0)}P)"
                    if cfg.quality_filters_enabled:
                        winning_voters = details.get("put_voters", [])
                        accept, reason, qinfo = apply_quality_filters(signal=sig, score=score, voters=winning_voters, candles=m1, asset=display, strategy_label=strat_label, payout_pct=payout, min_payout=cfg.min_payout, anti_tilt=None, current_balance=self.stats.current_balance, current_minute=datetime.now().strftime("%Y-%m-%d %H:%M"), require_confluence=cfg.require_confluence, require_volatility_gate=cfg.require_volatility_gate, require_time_filter=cfg.require_time_filter, min_pattern_winrate=cfg.min_pattern_winrate, use_pattern_memory=cfg.use_pattern_memory)
                        details["quality_info"] = qinfo
                        details["quality_accepted"] = accept
                        details["quality_reason"] = reason
                        if not accept:
                            short_reason = reason
                            self.dash.update_scan_status(progress_key, f"⊗ {sig} {short_reason}")
                        return
                    self.dash.update_scan_status(progress_key, f"✓ {sig} {score:.2f} [{regime_short}]")
                    self.dash.add_scan_signal(progress_key, sig, score, strat_label)
                return (symbol, sig, payout, strat_label, score, m1, display)
                c = details.get("call_count", 0)
                p = details.get("put_count", 0)
                if c > 0 or p > 0:
                    self.dash.update_scan_status(progress_key, f"⊘ {c}C/{p}P [{regime_short}]")
                return
                self.dash.update_scan_status(progress_key, f"⊘ no signal [{regime_short}]")
            return
            best_sig, best_strength, best_strat = (None, 0.0, "")
            for strat_name in cfg.enabled_strategies:
                fn = STRATEGY_REGISTRY.get(strat_name)
                if not fn:
                    pass
                try:
                    pass
                finally:
                    pass
                __exception__ = ()
                if Exception:
                    Exception
                    fn(m1)
                    fn(m1)
                elif sig and strength > best_strength:
                    best_sig = sig
                    best_strength = strength
                    best_strat = strat_name
                elif best_sig:
                    self.dash.update_scan_status(progress_key, f"✓ {best_sig} {best_strength:.2f}")
                    self.dash.add_scan_signal(progress_key, best_sig, best_strength, best_strat)
                return (symbol, best_sig, payout, best_strat, best_strength, m1, display)
                self.dash.update_scan_status(progress_key, "⊘ no signal")
                return
                if Exception:
                    Exception
                    e = None
                    try:
                        self.dash.update_scan_status(progress_key, "✗ err")
                    finally:
                        pass
                    return
    
    async def _find_signal_parallel(self) -> Optional[Tuple]:
        cfg = self.config
        
        if cfg.asset_mode == "MANUAL" and cfg.selected_asset:
            await verify_asset_open(self.client, cfg.selected_asset)
            is_open, name = await verify_asset_open(self.client, cfg.selected_asset)
            if not is_open:
                self.dash.log_event(f"⚠ {cfg.selected_asset} is CLOSED")
                return
            payout = get_payout_percent(self.client, name, "1M") or 80
            candidates = [{"symbol": name, "display_name": name, "payout_1m": payout, "is_otc": is_otc_name(name), "is_fx": True, "is_open": True, "is_tradable": True}]
        
        else:
            candidates = self._asset_universe[:max(1, cfg.top_n)]
        if not candidates:
            return
        candidate_displays = [c.get("display_name", c["symbol"]) for c in candidates]
        
        self.dash.set_scanning(candidate_displays)
        self.dash.log_event(f"🔍 Sequential scan of {len(candidates)} assets…")
        valid = []
        
        for asset_dict in candidates:
            await self._fetch_and_analyze_one(asset_dict, cfg.mtf_m5, cfg.mtf_m15)
            result = await self._fetch_and_analyze_one(asset_dict, cfg.mtf_m5, cfg.mtf_m15)
            if result is not None:
                valid.append(result)
        if not valid:
            self.dash.log_event(f"❌ No signal from {len(candidates)} assets")
            return
        valid.sort(key=(lambda x: x[4]), reverse=True)
        
        best = valid[0]
        best_display = best[0]
        try:
            regime_info = detect_market_regime(best[5])
            regime = regime_info.get("regime", "?")
        finally:
            adx_v = "adx"(__exception__, 0.0)
            regime_tag = f"[{regime} ADX={adx_v:.0f}]"
        if Exception:
            Exception
            regime_info.get
            regime_info.get
            regime_tag = ""
        self.dash.log_event(f"🎯 BEST: {best_display} {best[1]} • conf {best[4]:.2f} • {best[3]} {regime_tag}")
        return best
    
    def _render_chart_image(self, candles: List[Dict], asset: str, direction: str, strategy: str) -> Optional[str]:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            n = min(50, len(candles))
            c = candles[-n:]
            fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
            for i, candle in enumerate(c):
                o = candle["open"]
                h = candle["high"]
                l = candle["low"]
                cl = candle["close"]
                color = "#ef5350"
                ax.plot([i, i], [l, h], color=color, linewidth=0.7)
                ax.add_patch(plt.Rectangle((i - 0.3, min(o, cl)), 0.6, 0.0001, color=color, alpha=0.95))
            last_close = c[-1]["close"]
            arrow_color = "red"
            arrow_sym = "↓"
        finally:
            f"{arrow_sym} {direction.upper()}"((n - 1, last_close), xy=n - 5, xytext=(last_close, direction.upper() * 0.9992), fontsize=14, color=arrow_color, fontweight="bold", arrowprops=dict(arrowstyle="->", color=arrow_color, lw=2))
            ax.set_title(f"{asset} • {strategy} • {datetime.now().strftime("%H:%M:%S")}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Candle #", fontsize=10)
            ax.set_ylabel("Price", fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_facecolor("#1a1a1a")
            fig.patch.set_facecolor("#0a0a0a")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_color("gray")
            ax.title.set_color("white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            out_dir = Path("naif_charts")
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"entry_{asset.replace("/", "_")}_{int(time.time())}.png"
            plt.tight_layout()
            plt.savefig(out_path, facecolor=fig.get_facecolor())
            plt.close(fig)
            return str(out_path)
        if ImportError:
            ImportError
        return
        if Exception:
            Exception
            ax.annotate
            ax.annotate
        return
    
    def _render_result_chart(self, last_trade: "TradeResult", recent_trades: List["TradeResult"]) -> Optional[str]:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            if not recent_trades:
                pass
        finally:
            return
            fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
            cumulative = []
            running = 0.0
            for t in recent_trades:
                running += t.profit
                cumulative.append(running)
            colors = []
            for t in recent_trades:
                if t.result == "WIN":
                    colors.append("#26a69a")
                elif t.result == "LOSS":
                    colors.append("#ef5350")
                colors.append("#888888")
            x = list(range(1, len(recent_trades) + 1))
            ax.bar(x, [t.profit for t in recent_trades], color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
            ax2 = ax.twinx()
            ax2.plot(x, cumulative, color="gold", linewidth=2.5, marker="o", markersize=6, label="Cumulative P&L")
            ax2.set_ylabel("Cumulative P&L ($)", fontsize=10, color="gold")
            ax2.tick_params(colors="gold")
            __exception__(f"Recent P&L • Last: {last_trade.result} ${last_trade.profit:+.2f}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Trade #", fontsize=10)
            ax.set_ylabel("Trade P&L ($)", fontsize=10)
            ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.7)
            ax.grid(True, alpha=0.3, axis="y")
            ax.set_facecolor("#1a1a1a")
            fig.patch.set_facecolor("#0a0a0a")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_color("gray")
            ax.title.set_color("white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            out_dir = Path("naif_charts")
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"result_{int(time.time())}.png"
            plt.tight_layout()
            plt.savefig(out_path, facecolor=fig.get_facecolor())
            plt.close(fig)
            return str(out_path)
            if ImportError:
                ImportError
            return
            if Exception:
                Exception
                ax.set_title
                ax.set_title
            return
    
    def _log_csv(self, t: "TradeResult"):
        self.csv_log.log({"timestamp": t.timestamp, "asset": t.asset, "direction": t.direction, "amount": t.amount, "duration": t.duration_s, "payout": t.payout_pct, "result": t.result, "profit": t.profit, "balance": t.balance, "order_id": t.order_id, "strategy": t.strategy, "confidence": t.confidence, "mg_step": t.mg_step, "entry_price": t.entry_price, "exit_price": t.exit_price})
def settings_menu(config: BotConfig, tg: TelegramBot, screenshot: ScreenshotManager, csv_log: CSVLogger, scheduler: TradingScheduler):
    clear_screen()
    print_banner()
    _show_current_settings(config)
    
    choice = numbered_picker(title="⚙️  SETTINGS", options=["🏦 Account (PRACTICE / REAL)", "📊 Asset Selection (AUTO / MANUAL)", "🎯 Strategies (enable/disable)", "🧠 Smart Voting + MTF", "💰 Risk / Position Sizing", "🎛️ Martingale System", "🛡️ Session Guards (TP / SL)", "⏱️ Trade Duration & Frequency", "📡 Telegram Notifications", "📸 Screenshots", "💾 CSV Trade Log", "🕐 Trading Scheduler", "💾 Save & Return", "🔙 Return without saving"], description="Configure all bot settings. Choose by number or name.", allow_cancel=True, columns=1)
    if choice is None or choice == "🔙 Return without saving":
        return
    elif choice == "💾 Save & Return":
        config.save()
        console.print("[green]✅ Settings saved.[/green]")
        time.sleep(0.8)
        return
    
    elif choice == "🏦 Account (PRACTICE / REAL)":
        _settings_account(config)
    
    elif choice == "📊 Asset Selection (AUTO / MANUAL)":
        _settings_asset(config)
    
    elif choice == "🎯 Strategies (enable/disable)":
        _settings_strategies(config)
    
    elif choice == "🧠 Smart Voting + MTF":
        _settings_voting(config)
    
    elif choice == "💰 Risk / Position Sizing":
        _settings_risk(config)
    
    elif choice == "🎛️ Martingale System":
        _settings_martingale(config)
    
    elif choice == "🛡️ Session Guards (TP / SL)":
        _settings_session_guards(config)
    
    elif choice == "⏱️ Trade Duration & Frequency":
        _settings_duration(config)
    
    elif choice == "📡 Telegram Notifications":
        tg.setup_interactive()
        config.telegram_enabled = tg.enabled
        config.telegram_token = tg.token
        config.telegram_chat_id = tg.chat_id
    
    elif choice == "📸 Screenshots":
        screenshot.setup_interactive()
        config.screenshot_enabled = screenshot.enabled
    
    elif choice == "💾 CSV Trade Log":
        csv_log.setup_interactive()
        config.csv_enabled = csv_log.enabled
    
    elif choice == "🕐 Trading Scheduler":
        scheduler.setup_interactive()
        config.schedule_enabled = scheduler.enabled
        config.schedule_start_hour = scheduler.start_hour
        config.schedule_end_hour = scheduler.end_hour
        config.schedule_weekdays = list(scheduler.weekdays)
def _show_current_settings(c: BotConfig):
    tbl = Table(title="Current Settings", box=box.SIMPLE, show_lines=False, expand=False, border_style="cyan")
    
    tbl.add_column("Setting", style="bold")
    tbl.add_column("Value", style="cyan")
    enabled_count = len(c.enabled_strategies)
    
    mg_str = f"{c.mg_mode} (×{c.mg_multiplier}, max {c.mg_max_steps} steps)"
    
    asset_str = f"AUTO (top {c.top_n}, OTC={"off"})"
    
    sizing_str = f"PERCENT {c.risk_percent:.1f}% of balance"
    
    guards = []
    
    if c.session_tp:
        guards.append(f"TP=${c.session_tp:.0f}")
    elif c.session_sl:
        guards.append(f"SL=${c.session_sl:.0f}")
    guards_str = "off"
    tbl.add_row("Account", c.account)
    
    tbl.add_row("Asset Mode", asset_str)
    tbl.add_row("Strategies", f"{enabled_count} enabled")
    tbl.add_row("Smart Voting", f"{"OFF"} (min_agree={c.voting_min_agree}, min_score={c.voting_min_score})")
    tbl.add_row("MTF", f"M5={"off"} • M15={"off"}")
    tbl.add_row("Sizing", sizing_str)
    tbl.add_row("Martingale", mg_str)
    tbl.add_row("Duration", f"{c.duration_s}s")
    tbl.add_row("Session Guards", guards_str)
    tbl.add_row("Telegram", "OFF")
    tbl.add_row("Screenshots", "OFF")
    tbl.add_row("CSV Log", "OFF")
    tbl.add_row("Scheduler", "OFF (24/7)")
    console.print(tbl)
    
    console.print()
def _settings_account(c: BotConfig):
    choice = numbered_picker(title="🏦 Account Type", options=["PRACTICE (Demo)", "REAL (Live)"], current="REAL (Live)", description="⚠️ REAL mode trades with real money — use at your own risk.", allow_cancel=True)
    
    if choice == "REAL (Live)":
        confirm = numbered_yes_no("⚠️ Are you SURE you want REAL money mode?", default_yes=False)
        if confirm:
            c.account = "REAL"
            console.print("[red]🔴 Account set to REAL (Live).[/red]")
        else:
            c.account = "PRACTICE"
            console.print("[green]🟢 Kept PRACTICE mode.[/green]")
    
    elif choice == "PRACTICE (Demo)":
        c.account = "PRACTICE"
        console.print("[green]🟢 Account set to PRACTICE (Demo).[/green]")
    time.sleep(0.8)
def _settings_asset(c: BotConfig):
    print_section("📊 Asset Selection Mode")
    
    choice = numbered_picker(title="Asset Selection", options=["AUTO — bot scans assets and picks the best",
    "MANUAL — bot trades only your chosen asset"], current="MANUAL — bot trades only your chosen asset", allow_cancel=True)
    
    if choice and "AUTO" in choice:
        c.asset_mode = "AUTO"
        c.only_otc = numbered_yes_no("Trade OTC assets only?", default_yes=c.only_otc)
        c.min_payout = int(ask_number("Minimum payout %", c.min_payout, 50, 100, is_int=True))
        c.top_n = int(ask_number("Scan top N assets", c.top_n, 1, 50, is_int=True))
        rotation = numbered_picker(title="Rotation Mode", options=["hybrid", "best", "random", "roundrobin"], current=c.rotation_mode, description="hybrid: prefer best but rotate. best: always highest-score. random: shuffle order. roundrobin: cycle through.", allow_cancel=True)
        if rotation:
            c.rotation_mode = rotation
        elif choice and "MANUAL" in choice:
            c.asset_mode = "MANUAL"
            suggested = c.selected_asset or "EURUSD_otc"
            c.selected_asset = ask_text("Asset name (e.g. EURUSD, EURUSD_otc, GBPUSD)", suggested)
            console.print(f"[green]✅ Manual asset: {c.selected_asset}[/green]")
    time.sleep(0.8)
def _settings_strategies(c: BotConfig):
    clear_screen()
    print_section("🎯 Strategy Selection")
    all_names = get_all_strategy_names()
    
    enabled = set(c.enabled_strategies)
    
    for cat in ("CORE", "TREND", "REVERSAL", "BREAKOUT", "PATTERN", "OTC", "PRICE_ACTION"):
        names_in_cat = get_strategies_by_category(cat)
        if not names_in_cat:
            pass
        color = {"CORE": "bright_yellow", "TREND": "green", "REVERSAL": "magenta", "BREAKOUT": "cyan", "PATTERN": "blue", "OTC": "bright_red", "PRICE_ACTION": "white"}.get(cat, "white")
        console.print(f"\n[bold {color}]── {cat} ──[/bold {color}]")
        for name in names_in_cat:
            mark = "[red]✗[/red]"
            wr = get_strategy_winrate(name)
            total = get_strategy_total_trades(name)
            wr_str = "[dim](new)[/dim]"
            desc = STRATEGY_DESCRIPTIONS.get(name, "")[:65]
            console.print(f"  {mark} [cyan]{name:<22}[/cyan] {wr_str}  [dim]{desc}[/dim]")
    
    console.print()
    
    action = numbered_picker(title="Action", options=["Toggle a strategy (by name)", "Enable ALL", "Disable ALL", "Enable CORE only (5 default)", "Enable category...", "Disable category...", "🔙 Done"], allow_cancel=True)
    if action is None or action == "🔙 Done":
        return
    
    elif action == "Toggle a strategy (by name)":
        name = numbered_picker(title="Toggle which strategy?", options=all_names, allow_cancel=True, columns=2)
        if name:
            if name in enabled:
                enabled.discard(name)
                console.print(f"[red]✗ Disabled {name}[/red]")
            else:
                enabled.add(name)
                console.print(f"[green]✓ Enabled {name}[/green]")
            c.enabled_strategies = sorted(enabled)
            time.sleep(0.5)
        elif action == "Enable ALL":
            c.enabled_strategies = sorted(all_names)
            console.print(f"[green]✅ Enabled all {len(all_names)} strategies.[/green]")
            time.sleep(0.6)
        elif action == "Disable ALL":
            c.enabled_strategies = []
            console.print("[yellow]⚠ All strategies disabled. Enable at least one before trading![/yellow]")
            time.sleep(1.0)
        elif action == "Enable CORE only (5 default)":
            c.enabled_strategies = sorted(get_strategies_by_category("CORE"))
            console.print("[green]✅ Only CORE strategies enabled.[/green]")
            time.sleep(0.6)
        elif action == "Enable category...":
            cat = numbered_picker(title="Enable which category?", options=["CORE", "TREND", "REVERSAL", "BREAKOUT", "PATTERN", "OTC", "PRICE_ACTION"], allow_cancel=True)
            if cat:
                added = get_strategies_by_category(cat)
                enabled.update(added)
                c.enabled_strategies = sorted(enabled)
                console.print(f"[green]✅ Enabled {len(added)} strategies in {cat}.[/green]")
                time.sleep(0.6)
            elif action == "Disable category...":
                cat = numbered_picker(title="Disable which category?", options=["CORE", "TREND", "REVERSAL", "BREAKOUT", "PATTERN", "OTC", "PRICE_ACTION"], allow_cancel=True)
                if cat:
                    removed = get_strategies_by_category(cat)
                    enabled.difference_update(removed)
                    c.enabled_strategies = sorted(enabled)
                    console.print(f"[yellow]✗ Disabled {len(removed)} strategies in {cat}.[/yellow]")
                    time.sleep(0.6)
def _settings_voting(c: BotConfig):
    print_section("🧠 Smart Voting + Multi-Timeframe")
    
    choice = numbered_picker(title="Smart Voting Mode", options=["ON — Use multi-strategy voting + self-learning",
    "OFF — Use first-hit strategy mode (faster, less safe)"], current="OFF — Use first-hit strategy mode (faster, less safe)", description="Voting weighs each strategy by its historical winrate.", allow_cancel=True)
    if choice is None:
        return
    c.voting_enabled = "ON" in choice
    
    if c.voting_enabled:
        c.voting_min_agree = int(ask_number("Minimum agreeing strategies (recommended: 3-5)", c.voting_min_agree, 1, 30, is_int=True))
        c.voting_min_score = ask_number("Minimum voting score 0..5 (recommended: 2.0)", c.voting_min_score, 0.0, 5.0)
        c.voting_use_weights = numbered_yes_no("Use win-rate weighting?", default_yes=c.voting_use_weights)
        c.voting_use_mtf = numbered_yes_no("Use Multi-Timeframe confirmation?", default_yes=c.voting_use_mtf)
        if c.voting_use_mtf:
            c.mtf_m5 = numbered_yes_no("Confirm on M5?", default_yes=c.mtf_m5)
            c.mtf_m15 = numbered_yes_no("Confirm on M15?", default_yes=c.mtf_m15)
    console.print("[green]✅ Voting configured.[/green]")
    time.sleep(0.6)
def _settings_risk(c: BotConfig):
    print_section("💰 Risk / Position Sizing")
    
    choice = numbered_picker(title="Sizing Mode", options=["FIXED — same $ amount per trade",
    "PERCENT — % of current balance per trade"], current="PERCENT — % of current balance per trade", allow_cancel=True)
    if choice is None:
        return
    
    elif "FIXED" in choice:
        c.sizing_mode = "fixed"
        c.fixed_amount = ask_number("Fixed amount per trade ($)", c.fixed_amount, 1, 10_000)
    
    else:
        c.sizing_mode = "percent"
        c.risk_percent = ask_number("Risk per trade (% of balance)", c.risk_percent, 0.1, 100)
    c.min_amount = ask_number("Minimum trade amount ($)", c.min_amount, 1, 10_000)
    c.max_amount = ask_number("Maximum trade amount ($)", c.max_amount, c.min_amount, 50_000)
    console.print("[green]✅ Risk parameters saved.[/green]")
    time.sleep(0.6)
def _settings_martingale(c: BotConfig):
    print_section("🎛️ Martingale System")
    
    mode = numbered_picker(title="Martingale Mode", options=["OFF — never escalate (safest)", "CLASSIC — base × multiplier^step", "FIBONACCI — Fibonacci sequence", "CUSTOM_SEQUENCE — your own sequence", "MANUAL — bot asks you after each loss", "ANTI — grow on WIN, reset on LOSS"], current={"OFF": "OFF — never escalate (safest)", "CLASSIC": "CLASSIC — base × multiplier^step", "FIBONACCI": "FIBONACCI — Fibonacci sequence", "CUSTOM_SEQUENCE": "CUSTOM_SEQUENCE — your own sequence", "MANUAL": "MANUAL — bot asks you after each loss", "ANTI": "ANTI — grow on WIN, reset on LOSS"}.get(c.mg_mode, "OFF — never escalate (safest)"), description="⚠️ Martingale CAN bust your account. Use small max_steps.", allow_cancel=True)
    if mode is None:
        return
    elif "OFF" in mode:
        c.mg_mode = "OFF"
        console.print("[green]✅ Martingale OFF.[/green]")
        time.sleep(0.6)
        return
    
    elif "CLASSIC" in mode:
        c.mg_mode = "CLASSIC"
    
    elif "FIBONACCI" in mode:
        c.mg_mode = "FIBONACCI"
        c.mg_fib_start = int(ask_number("Fibonacci start index (recommended: 1)", c.mg_fib_start, 1, 30, is_int=True))
        c.mg_fib_scale = ask_number("Fibonacci scale factor", c.mg_fib_scale, 0.1, 10.0)
    
    elif "CUSTOM_SEQUENCE" in mode:
        c.mg_mode = "CUSTOM_SEQUENCE"
        raw = ask_text("Sequence (comma-separated, e.g. '1,2.5,6,15')", "1,2.5,6,15")
        try:
            c.mg_custom_sequence = [float(x.strip()) for x in raw.split(",") if x.strip()]
        finally:
            pass
        if Exception:
            Exception
            c.mg_custom_sequence = [1.0, 2.5, 6.0, 15.0]
        c.mg_seq_is_multiplier = numbered_yes_no("Are these multipliers (×base) instead of absolute $?", default_yes=c.mg_seq_is_multiplier)
        if "MANUAL" in mode:
            c.mg_mode = "MANUAL"
        elif "ANTI" in mode:
            c.mg_mode = "ANTI"
    c.mg_base = ask_number("Base amount ($)", c.mg_base, 1, 10_000)
    
    c.mg_multiplier = ask_number("Multiplier (used for CLASSIC/MANUAL/ANTI)", c.mg_multiplier, 1.01, 10.0)
    c.mg_max_steps = int(ask_number("Max steps (recommended ≤ 3)", c.mg_max_steps, 1, 10, is_int=True))
    c.mg_min = ask_number("Min trade amount", c.mg_min, 1, 10_000)
    c.mg_max = ask_number("Max trade amount", c.mg_max, c.mg_min, 50_000)
    c.mg_reset_on_win = numbered_yes_no("Reset step on WIN?", default_yes=c.mg_reset_on_win)
    console.print(f"[green]✅ Martingale: {c.mg_mode} (×{c.mg_multiplier}, max {c.mg_max_steps}).[/green]")
    time.sleep(0.8)
def _settings_session_guards(c: BotConfig):
    print_section("🛡️ Session Guards (TP / SL)")
    console.print("[dim]Set to 0 to disable a guard.[/dim]")
    c.session_tp = ask_number("Session Take Profit ($)", c.session_tp, 0, 100_000)
    c.session_sl = ask_number("Session Stop Loss ($)", c.session_sl, 0, 100_000)
    console.print(f"[green]✅ Guards: TP=${c.session_tp:.0f} / SL=${c.session_sl:.0f}[/green]")
    time.sleep(0.6)
def _settings_duration(c: BotConfig):
    print_section("⏱️ Trade Duration & Frequency")
    c.duration_s = int(ask_number("Trade duration (seconds)", c.duration_s, 30, 3600, is_int=True))
    c.one_trade_only = numbered_yes_no("One trade at a time?", default_yes=c.one_trade_only)
    console.print(f"[green]✅ Duration={c.duration_s}s, one_trade_only={c.one_trade_only}[/green]")
    time.sleep(0.6)
async def main_menu(client, config: BotConfig, tg: TelegramBot, screenshot: ScreenshotManager, csv_log: CSVLogger, scheduler: TradingScheduler):
    last_stats = None
    
    clear_screen()
    print_banner()
    _print_short_status(config, last_stats)
    
    choice = numbered_picker(title="🎮 MAIN MENU", options=["🚀 START LIVE TRADING", "👁️  SCAN-ONLY MODE (no trading)", "⚙️  Settings", "📈 Strategy Performance Stats", "📋 Show Recent Trades", "💾 Export Trades to CSV (now)", "🎯 Strategy List & Descriptions", "🧪 Test Telegram", "🧪 Test Screenshot", "🔍 Browse All Assets (Open/Closed)", "❓ Help", "🚪 Exit"], description="Choose an action by number or type its name.", columns=1, allow_cancel=False)
    if choice is None or choice == "🚪 Exit":
        console.print("[cyan]Goodbye! 👋[/cyan]")
        return
    
    while choice == "🚀 START LIVE TRADING":
        confirm = numbered_yes_no(f"Start LIVE trading on {config.account}?", default_yes=True)
        if not confirm:
            pass
        elif not config.enabled_strategies:
            console.print("[red]✗ No strategies enabled! Go to Settings → Strategies first.[/red]")
            press_any_key()
        clear_screen()
        trader = Trader(client, config, tg, screenshot, csv_log, scheduler)
        import sys as _sys
        this_module = _sys.modules[__name__]
        trader_task = asyncio.create_task(trader.run())
        this_module._CURRENT_TRADING_TASK = trader_task
        try:
            try:
                await trader_task
                await trader_task
            finally:
                last_stats = trader.stats
            if (KeyboardInterrupt, asyncio.CancelledError):
                (KeyboardInterrupt, asyncio.CancelledError)
                __exception__
                __exception__
                console.print("\n[yellow]⏹ Trading stopped by user — returning to main menu.[/yellow]")
                last_stats = trader.stats
            elif Exception:
                Exception
                e = None
                try:
                    console.print(f"\n[red]✗ Trading error: {e}[/red]")
                    import traceback
                finally:
                    traceback.print_exc()
                    last_stats = trader.stats
                this_module._CURRENT_TRADING_TASK = None
                this_module._CURRENT_TRADING_TASK = None
                press_any_key()
                if choice == "👁️  SCAN-ONLY MODE (no trading)":
                    confirm = numbered_yes_no("Start SCAN-ONLY mode? (no real trades — just analysis)", default_yes=True)
                    if not confirm:
                        pass
                    elif not config.enabled_strategies:
                        console.print("[red]✗ No strategies enabled! Go to Settings → Strategies first.[/red]")
                        press_any_key()
                    clear_screen()
                    import sys as _sys
                    this_module = _sys.modules[__name__]
                    scan_task = asyncio.create_task(_scan_only_mode(client, config))
                    this_module._CURRENT_TRADING_TASK = scan_task
                    try:
                        try:
                            await scan_task
                            await scan_task
                        finally:
                            pass
                        if (KeyboardInterrupt, asyncio.CancelledError):
                            (KeyboardInterrupt, asyncio.CancelledError)
                            __exception__
                            __exception__
                            console.print("\n[yellow]⏹ Scan stopped — returning to main menu.[/yellow]")
                        elif Exception:
                            Exception
                            e = None
                    finally:
                        try:
                            console.print(f"\n[red]✗ Scan error: {e}[/red]")
                            import traceback
                            traceback.print_exc()
                    this_module._CURRENT_TRADING_TASK = None
                    this_module._CURRENT_TRADING_TASK = None
                    press_any_key()
                    if choice == "⚙️  Settings":
                        settings_menu(config, tg, screenshot, csv_log, scheduler)
                    elif choice == "📈 Strategy Performance Stats":
                        show_strategy_performance()
                        press_any_key()
                    elif choice == "📋 Show Recent Trades":
                        if last_stats and last_stats.trades:
                            limit = int(ask_number("How many recent trades to show?", 30, 1, 500, is_int=True))
                            show_recent_trades(last_stats, limit=limit)
                        else:
                            console.print("[yellow]⚠ No trades yet in this session.[/yellow]")
                        press_any_key()
                    elif choice == "💾 Export Trades to CSV (now)":
                        press_any_key()
                    elif choice == "🎯 Strategy List & Descriptions":
                        show_all_strategies()
                        press_any_key()
                    elif choice == "🧪 Test Telegram":
                        if tg.enabled:
                            if tg.test():
                                console.print("[green]✅ Telegram test message sent.[/green]")
                            else:
                                console.print("[red]✗ Telegram test failed — check token/chat_id.[/red]")
                        else:
                            console.print("[yellow]⚠ Telegram is not enabled. Configure it in Settings first.[/yellow]")
                        press_any_key()
                    elif choice == "🧪 Test Screenshot":
                        if not SCREENSHOT_AVAILABLE:
                            console.print("[red]✗ Screenshot library not available (pip install mss pillow).[/red]")
                        elif screenshot.enabled:
                            path = screenshot.take("test")
                            if path:
                                console.print(f"[green]✅ Screenshot saved: {path}[/green]")
                            else:
                                console.print("[red]✗ Screenshot capture failed.[/red]")
                        else:
                            console.print("[yellow]⚠ Screenshots disabled. Enable in Settings first.[/yellow]")
                        press_any_key()
                    elif choice == "🔍 Browse All Assets (Open/Closed)":
                        await _browse_assets(client)
                        await _browse_assets(client)
                        press_any_key()
                    elif choice == "❓ Help":
                        show_help()
                        press_any_key()
async def _scan_only_mode(client, config):
    from datetime import datetime
    await get_profile_info(client)
    
    profile_info = await get_profile_info(client)
    await ensure_account(client, config.account)
    await ensure_account(client, config.account)
    
    try:
        await client.get_balance()
        balance = await client.get_balance()
    finally:
        pass
    if Exception:
        Exception
        balance = 0.0
    dash = LiveDashboard(config, Statistics())
    dash.mode = "SCAN_ONLY"
    dash.profile_id = profile_info.get("profile_id")
    dash.nick_name = profile_info.get("nick_name")
    dash.account = config.account
    dash.balance = balance
    dash.connection_status = "🟢 Scanning (no trading)"
    universe = []
    last_refresh = 0.0
    dash.log_event("👁️ SCAN-ONLY mode started — no real trades")
    dash.log_event("ℹ️ Press Ctrl+C to return to main menu")
    try:
        with Live(dash, refresh_per_second=4, console=console, transient=False, screen=False) as live:
            now = time.time()
        if not now - last_refresh > 60.0 or universe:
            try:
                await filter_assets(client, only_otc=config.only_otc, min_payout=config.min_payout, open_only=True, fx_only=False, tradable_only=False)
                universe = await filter_assets(client, only_otc=config.only_otc, min_payout=config.min_payout, open_only=True, fx_only=False, tradable_only=False)
                last_refresh = now
                dash.universe = len(universe)
                if universe:
                    otc = sum((1 for a in universe))
                    fx = sum((1 for a in universe))
                    dash.log_event(f"🔄 Universe: {len(universe)} ({otc} OTC, {fx} FX)")
            finally:
                pass
            if Exception:
                Exception
                e = None
                try:
                    pass
                finally:
                    __exception__
                while not universe:
                    await asyncio.sleep(5)
                    await asyncio.sleep(5)
                candidates = universe[:max(1, config.top_n)]
                candidate_displays = [c.get("display_name", c["symbol"]) for c in candidates]
                dash.set_scanning(candidate_displays)
                dash.log_event(f"🔍 Scanning {len(candidates)} assets…")
                signals_found = []
                for ad in candidates:
                    symbol = ad["symbol"]
                    display = ad.get("display_name", symbol)
                    payout = ad["payout_1m"]
                    try:
                        await fetch_candles_by_symbol(client, symbol, 60, 200, timeout=2.5)
                        m1 = await fetch_candles_by_symbol(client, symbol, 60, 200, timeout=2.5)
                        if m1 and len(m1) < 30:
                            await fetch_candles_safe(client, display, "1m", 200, timeout=2.0)
                            m1 = await fetch_candles_safe(client, display, "1m", 200, timeout=2.0)
                        elif m1 and len(m1) < 30:
                            dash.update_scan_status(display, "✗ no candles")
                    finally:
                        m5 = None
                        if config.mtf_m5:
                            await fetch_candles_by_symbol(client, symbol, 300, 100, timeout=2.5)
                            m5 = await fetch_candles_by_symbol(client, symbol, 300, 100, timeout=2.5)
                        m15 = None
                        if config.mtf_m15:
                            await fetch_candles_by_symbol(client, symbol, 900, 80, timeout=2.5)
                            m15 = await fetch_candles_by_symbol(client, symbol, 900, 80, timeout=2.5)
                        elif config.voting_enabled:
                            sig, score, details = smart_vote(candles_m1=m1, candles_m5=m5, candles_m15=m15, min_agree=config.voting_min_agree, use_weights=config.voting_use_weights, use_mtf=config.voting_use_mtf, enabled_strategies=config.enabled_strategies)
                            if sig and score >= config.voting_min_score:
                                strat = f"V({details.get("call_count", 0)}C/{details.get("put_count", 0)}P)"
                                dash.update_scan_status(display, f"✓ {sig} {score:.2f}")
                                __exception__
                                signals_found.append((display, sig, score, strat, payout))
                            else:
                                c = details.get("call_count", 0)
                                p = details.get("put_count", 0)
                                if c > 0 or p > 0:
                                    dash.update_scan_status(display, f"⊘ {c}C/{p}P weak")
                                else:
                                    dash.update_scan_status(display, "⊘ no signal")
                        else:
                            best_sig, best_strength, best_strat = (None, 0.0, "")
                            for strat_name in config.enabled_strategies:
                                fn = STRATEGY_REGISTRY.get(strat_name)
                                if not fn:
                                    pass
                                try:
                                    pass
                                finally:
                                    pass
                                __exception__ = ()
                                if Exception:
                                    Exception
                                    fn(m1)
                                    fn(m1)
                                elif sig and strength > best_strength:
                                    best_sig = sig
                                    best_strength = strength
                                    best_strat = strat_name
                                elif best_sig:
                                    dash.update_scan_status(display, f"✓ {best_sig} {best_strength:.2f}")
                                    dash.add_scan_signal(display, best_sig, best_strength, best_strat)
                                    signals_found.append((display, best_sig, best_strength, best_strat, payout))
                                else:
                                    dash.update_scan_status(display, "⊘ no signal")
                                finally:
                                    if Exception:
                                        Exception
                                        e = None
                                        try:
                                            dash.update_scan_status(display, "✗ err")
                                        finally:
                                            pass
                                    next_scan_wait = 5.0
                                    dash.clear_scanning()
                                    dash.set_countdown("⏳ Next scan cycle in", next_scan_wait)
                                    t_end = time.time() + next_scan_wait
                                    if time.time() < t_end:
                                        await asyncio.sleep(0.1)
                                        await asyncio.sleep(0.1)
                                        if not time.time() < t_end:
                                            dash.clear_countdown()
                                    elif not True:
                                        pass
                                console.print("\n[yellow]⏹ Scan-only mode ended[/yellow]")
                                return
                                console.print("\n[yellow]⏹ Scan-only mode ended[/yellow]")
async def _browse_assets(client):
    console.print("\n[cyan]🔍 Loading platform instruments...[/cyan]")
    
    try:
        await ensure_instruments_loaded(client, timeout=30.0)
        loaded = await ensure_instruments_loaded(client, timeout=30.0)
        if not loaded:
            pass
    finally:
        __exception__("[red]✗ Could not load instruments from platform.[/red]")
        console.print("[yellow]Try reconnecting (exit and restart the bot).[/yellow]")
        return
    if Exception:
        Exception
        e = console.print
        console.print
        try:
            pass
        finally:
            __exception__
        return
        console.print("[cyan]🔍 Fetching assets list...[/cyan]")
        try:
            await get_all_assets_status(client)
            assets = await get_all_assets_status(client)
        finally:
            pass
        if Exception:
            Exception
            e = console.print(f"[red]✗ Error loading instruments: {e}[/red]")
            console.print(f"[red]✗ Error loading instruments: {e}[/red]")
            try:
                pass
            finally:
                __exception__
            return
            if not assets:
                console.print("[yellow]⚠ No assets returned from platform.[/yellow]")
                console.print("[dim]This may mean instruments aren't fully synced yet — wait a few seconds and try again.[/dim]")
                return
            assets.sort(key=(lambda a: (not a["is_open"], -a["payout_1m"])))
            open_assets = [a for a in assets if a["is_open"]]
            closed_assets = [a for a in assets if not a["is_open"]]
            tbl = Table(title=f"📊 Platform Assets — {len(open_assets)} OPEN / {len(closed_assets)} CLOSED", title_style="bold cyan", box=box.ROUNDED, show_lines=False, expand=True)
            tbl.add_column("#", style="dim", justify="right", width=4)
            tbl.add_column("Symbol", style="cyan", no_wrap=True)
            tbl.add_column("Display", style="white")
            tbl.add_column("Type", justify="center", width=8)
            tbl.add_column("Status", justify="center", width=10)
            tbl.add_column("1M %", justify="right", width=7)
            tbl.add_column("5M %", justify="right", width=7)
            for i, a in enumerate(assets[:50], 1):
                type_str = "—"
                type_color = "dim"
                status_emoji = "🔴 CLOSED"
                status_color = "red"
                p1 = a["payout_1m"]
                p5 = a["payout_5m"]
                p1_color = "red"
                tbl.add_row(str(i), a["symbol"], a["name"][:30], f"[{type_color}]{type_str}[/]", f"[{status_color}]{status_emoji}[/]", "—", "—")
            console.print(tbl)
            if len(assets) > 50:
                console.print(f"[dim]... and {len(assets) - 50} more assets[/dim]")
    otc_open = sum((1 for a in open_assets))
    
    fx_open = sum((1 for a in open_assets))
    
    summary = Panel(f"[green]🟢 Open:[/green] {len(open_assets)} ([yellow]OTC: {otc_open}[/yellow], [cyan]FX: {fx_open}[/cyan])\n[red]🔴 Closed:[/red] {len(closed_assets)}\n[bold cyan]Total:[/bold cyan] {len(assets)} assets", title="📈 Summary", border_style="cyan")
    
    console.print(summary)
def await_coroutine(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pass
    finally:
        __exception__
        return
    loop.run_until_complete(coro)
    return
    if RuntimeError:
        RuntimeError
        asyncio.ensure_future(coro)
        asyncio.ensure_future(coro)
        asyncio.run(coro)
    return
def _print_short_status(c: BotConfig, last_stats: Optional[Statistics]):
    enabled_count = len(c.enabled_strategies)
    
    mode_color = "red"
    
    parts = [f"[bold]Account:[/bold] [{mode_color}]{c.account}[/{mode_color}]",
        
        f"[bold]Strategies:[/bold] [cyan]{enabled_count}[/cyan]",
        f"[bold]Voting:[/bold] {"[dim]OFF[/dim]"}",
        f"[bold]MG:[/bold] {c.mg_mode}"]
    
    if last_stats and last_stats.total_trades:
        wr_color = "red"
        pnl_color = "red"
        parts.append(f"[bold]Last session:[/bold] [{wr_color}]{last_stats.winrate:.0f}% WR[/{wr_color}]")
        parts.append(f"[bold]P/L:[/bold] [{pnl_color}]${last_stats.total_pnl:+.2f}[/{pnl_color}]")
    console.print(Panel(Text.from_markup("   ".join(parts)), border_style="cyan"))
def show_strategy_performance():
    print_section("📈 Strategy Performance — Self-Learning Stats")
    
    stats = _load_strategy_stats()
    if not stats:
        console.print("[yellow]⚠ No performance data yet. Run some trades first![/yellow]")
        return
    rows = []
    
    for name in get_all_strategy_names():
        if name in stats:
            wins = int(stats[name].get("wins", 0))
            losses = int(stats[name].get("losses", 0))
            total = wins + losses
            wr = 0.0
            cat = STRATEGY_CATEGORIES.get(name, "GENERAL")
            rows.append((name, cat, wins, losses, total, wr))
        rows.append((name, STRATEGY_CATEGORIES.get(name, "GENERAL"), 0, 0, 0, 0.0))
    
    rows.sort(key=(lambda x: (-x[4], -x[5])))
    
    tbl = Table(title="Per-Strategy Performance (auto-saved)", box=box.HEAVY, show_lines=False, expand=True, border_style="cyan", row_styles=["none", "dim"])
    
    tbl.add_column("#", justify="right", style="bold yellow", width=4)
    
    tbl.add_column("Strategy", style="cyan")
    tbl.add_column("Category", style="white")
    tbl.add_column("Wins", justify="right", style="green")
    tbl.add_column("Losses", justify="right", style="red")
    tbl.add_column("Total", justify="right", style="bold")
    tbl.add_column("Winrate %", justify="right", style="bold")
    tbl.add_column("Status", justify="center")
    
    for name, cat, w, l, t, wr in enumerate(rows, 1):
        if t < 5:
            wr_color = "dim"
            status = "[dim]🆕 new[/dim]"
            wr_str = "[dim]-[/dim]"
        elif wr >= 65:
            wr_color = "bright_green"
            status = "🔥 strong"
            wr_str = f"[{wr_color}]{wr:.1f}%[/{wr_color}]"
        elif wr >= 55:
            wr_color = "green"
            status = "✅ good"
            wr_str = f"[{wr_color}]{wr:.1f}%[/{wr_color}]"
        elif wr >= 45:
            wr_color = "yellow"
            status = "⚠ avg"
            wr_str = f"[{wr_color}]{wr:.1f}%[/{wr_color}]"
        else:
            wr_color = "red"
            status = "❌ weak"
            wr_str = f"[{wr_color}]{wr:.1f}%[/{wr_color}]"
        cat_color = get_strategy_color(name)
        tbl.add_row(str(i), f"[{cat_color}]{name}[/{cat_color}]", cat, str(w), str(l), str(t), wr_str, status)
    
    console.print(tbl)
    
    console.print(f"\n[dim]💾 Saved to: {STRATEGY_STATS_FILE}[/dim]")
def show_recent_trades(stats: Statistics, limit: int=30):
    print_section(f"📋 Last {limit} Trades")
    if not stats.trades:
        console.print("[yellow]No trades yet.[/yellow]")
        return
    tbl = Table(title=f"Trades ({len(stats.trades)} total)", box=box.HEAVY, show_lines=False, expand=True, border_style="cyan", row_styles=["none", "dim"])
    
    for col in ("Time", "Asset", "Action", "Amount", "Payout", "Strategy", "Status", "P/L", "Balance", "MG"):
        tbl.add_column(col)
    for t in stats.trades[-limit:]:
        action = f"[yellow]{"[red]PUT ▼[/red]" if t.direction.upper() == "PUT" else t.direction}[/yellow]"
        status = {"WIN": "[green]✅ WIN[/green]", "LOSS": "[red]❌ LOSS[/red]", "DRAW": "[yellow]🤝 DRAW[/yellow]", "PENDING": "[cyan]⏳[/cyan]", "FAIL": "[magenta]⛔[/magenta]", "UNKNOWN": "[yellow]?[/yellow]"}.get(t.result, t.result)
        pl_color = "red"
        pl = f"[{pl_color}]{t.profit:+.2f}[/{pl_color}]"
        try:
            pass
        finally:
            tm = t.timestamp[None[__exception__:8] if "T" in t.timestamp else None:8]
        if Exception:
            Exception
            t.timestamp.split("T")[1]
            t.timestamp.split("T")[1]
            tm = t.timestamp[:8]
        tbl.add_row(tm, t.asset, action, f"${t.amount:.2f}", f"{t.payout_pct:.0f}%", t.strategy[:14], status, pl, f"${t.balance:.2f}", "-")
        console.print(tbl)
        return
def export_trades_csv(stats: Statistics):
    fname = f"naif_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"
    
    try:
        with open(fname, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "asset", "direction", "amount", "duration_s", "payout_pct", "result", "profit", "balance", "order_id", "strategy", "confidence", "mg_step"])
        for t in stats.trades:
            writer.writerow([t.timestamp,
    t.asset,
    t.direction,
    t.amount,
    t.duration_s,
    t.payout_pct,
    t.result,
    t.profit,
    t.balance,
    t.order_id,
    t.strategy,
    t.confidence,
    t.mg_step])
    finally:
        ##ERROR##(None, None, None)
    
    console.print(f"[green]✅ Exported {len(stats.trades)} trades to: {fname}[/green]")
    if Exception:
        Exception
        e = None
        try:
            pass
        finally:
            __exception__
        return
def show_all_strategies():
    print_section("🎯 All Available Strategies")
    
    for cat in ("CORE", "TREND", "REVERSAL", "BREAKOUT", "PATTERN", "OTC", "PRICE_ACTION"):
        names = get_strategies_by_category(cat)
        if not names:
            pass
        color = {"CORE": "bright_yellow", "TREND": "green", "REVERSAL": "magenta", "BREAKOUT": "cyan", "PATTERN": "blue", "OTC": "bright_red", "PRICE_ACTION": "white"}.get(cat, "white")
        console.print(f"\n[bold {color}]══════ {cat} ({len(names)}) ══════[/bold {color}]")
        for name in names:
            desc = STRATEGY_DESCRIPTIONS.get(name, "")
            wr = get_strategy_winrate(name)
            total = get_strategy_total_trades(name)
            wr_str = "[dim](no data yet)[/dim]"
            console.print(f"  [bold {color}]•[/bold {color}] [{color}]{name:<22}[/{color}] {wr_str}")
            console.print(f"    [dim]{desc}[/dim]")
    
    console.print(f"\n[bold]Total: {len(get_all_strategy_names())} strategies registered.[/bold]")
def show_help():
    clear_screen()
    print_banner()
    
    help_text = "\n[bold cyan]📖 HELP — NAIF Pro v7.0 SMART[/bold cyan]\n\n[bold yellow]── Quick Start ──[/bold yellow]\n  1. Configure your account (PRACTICE first!) in Settings → Account\n  2. Pick strategies (CORE 5 are enabled by default) in Settings → Strategies\n  3. Set sizing & martingale in Settings → Risk and Martingale\n  4. (Optional) Enable Telegram for live notifications\n  5. Return to Main Menu → START LIVE TRADING\n\n[bold yellow]── How the Bot Works ──[/bold yellow]\n  • Every minute, the bot scans assets (AUTO mode) or your chosen asset (MANUAL mode)\n  • It runs all enabled strategies on the candles\n  • If Smart Voting is ON: strategies VOTE — winner needs ≥min_agree votes\n  • Each strategy's vote is WEIGHTED by its historical winrate (self-learning)\n  • Multi-Timeframe confirmation checks M5 and M15 agreement\n  • A trade is placed only if the score ≥ min_score\n\n[bold yellow]── Self-Learning System ──[/bold yellow]\n  • After every trade closes, the bot replays each strategy\n  • Strategies that AGREED with a winning side get +1 win\n  • Strategies that DISAGREED with a losing side get +1 win (correct rejection)\n  • Stats persist in: [cyan]{stats_file}[/cyan]\n  • Better-performing strategies get higher vote weights over time\n\n[bold yellow]── Martingale Modes ──[/bold yellow]\n  • OFF:        never escalate (safest, recommended for beginners)\n  • CLASSIC:    base × multiplier^step (most common)\n  • FIBONACCI:  uses Fibonacci sequence (slower escalation)\n  • CUSTOM_SEQUENCE: your own sequence\n  • MANUAL:     bot asks you after each loss\n  • ANTI:       grows on WIN, resets on LOSS (trail winners)\n\n[bold yellow]── Tips ──[/bold yellow]\n  ✓ ALWAYS start on PRACTICE account\n  ✓ Keep max_steps ≤ 3 — Martingale can bust your account\n  ✓ Enable Smart Voting for better signal quality\n  ✓ Run for several days to let self-learning kick in\n  ✓ Use Session SL/TP to lock profits / limit losses\n\n[bold red]── ⚠ Warnings ──[/bold red]\n  • Binary options are HIGH RISK — 70-90% of traders lose money\n  • pyquotex is UNOFFICIAL and may violate Quotex Terms of Service\n  • Past results do NOT guarantee future profits\n  • Never trade with money you can't afford to lose\n\n[bold yellow]── Files Created ──[/bold yellow]\n  • [cyan]{config_file}[/cyan]   — your settings (auto-saved)\n  • [cyan]{stats_file}[/cyan]   — strategy performance (auto-updated)\n  • [cyan]naif_trades_*.csv[/cyan]                        — trade log (if enabled)\n  • [cyan]naif_screenshots/[/cyan]                       — screenshots (if enabled)\n".format(stats_file=STRATEGY_STATS_FILE, config_file=CONFIG_PATH)
    
    console.print(help_text)
async def interactive_main():
    enable_noise_filter()
    
    clear_screen()
    
    print_banner()
    
    if not QUOTEX_AVAILABLE:
        console.print(Panel("[bold red]✗ pyquotex is not installed[/bold red]\n\nInstall it with:\n  [cyan]pip install pyquotex[/cyan]\n\nOr clone from:\n  [cyan]https://github.com/cleitonleonel/pyquotex[/cyan]", title="⚠ Missing Dependency", border_style="red"))
        try:
            input("\nPress Enter to exit...")
        finally:
            return
            if (EOFError, KeyboardInterrupt):
                (EOFError, KeyboardInterrupt)
            return
            config = BotConfig.load()
            console.print(f"[dim]✓ Config loaded from: {CONFIG_PATH}[/dim]")
            try:
                email, password = resolve_credentials()
            finally:
                pass
            if KeyboardInterrupt:
                KeyboardInterrupt
                console.print("\n[yellow]Cancelled.[/yellow]")
            return
            if Exception:
                Exception
                e = None
                try:
                    pass
                finally:
                    __exception__
                return
                console.print(Panel(f"[cyan]Connecting to Quotex...[/cyan]\nAccount: [bold yellow]{config.account}[/bold yellow]", border_style="cyan"))
                try:
                    client = Quotex(email=email, password=password, lang="pt")
                    try:
                        if config.account.upper() == "PRACTICE":
                            pass
                    finally:
                        "PRACTICE"(__exception__)
                    client.set_account_mode("REAL")
                    if Exception:
                        Exception
                        client.set_account_mode
                        client.set_account_mode
                    elif Exception:
                        Exception
                        e = console.print(f"[red]✗ Could not resolve credentials: {e}[/red]")
                        console.print(f"[red]✗ Could not resolve credentials: {e}[/red]")
                        try:
                            console.print(f"[red]✗ Could not create Quotex client: {e}[/red]")
                            try:
                                pass
                            finally:
                                __exception__
                        finally:
                            if (EOFError, KeyboardInterrupt):
                                (EOFError, KeyboardInterrupt)
                                __exception__
                                input("\nPress Enter to exit...")
                        return
                    await connect_quotex(client, attempts=3)
                    success, reason = await connect_quotex(client, attempts=3)
                    if not success:
                        console.print(f"[red]✗ Connection failed: {reason}[/red]")
                        console.print("[yellow]Check:[/yellow]")
                        console.print("  • Email + password are correct")
                        console.print("  • Internet connection")
                        console.print("  • Try deleting [cyan]session.json[/cyan] file")
                        try:
                            input("\nPress Enter to exit...")
                        finally:
                            return
                            if (EOFError, KeyboardInterrupt):
                                (EOFError, KeyboardInterrupt)
                                input("\nPress Enter to exit...")
                                input("\nPress Enter to exit...")
                            return
                            console.print(f"[green]✓ Connected successfully![/green]  [dim]{reason}[/dim]")
                            console.print("[cyan]⏳ Loading platform instruments...[/cyan]")
                            await ensure_instruments_loaded(client, timeout=30.0)
                            instruments_loaded = await ensure_instruments_loaded(client, timeout=30.0)
                            if not instruments_loaded:
                                console.print("[yellow]⚠ Could not pre-load instruments — will retry on demand[/yellow]")
                            else:
                                console.print("[green]✓ Instruments loaded![/green]")
                            await ensure_account(client, config.account)
                            await ensure_account(client, config.account)
                            console.print(f"[green]✓ Active account: {config.account}[/green]")
                            await get_profile_info(client)
                            profile_info = await get_profile_info(client)
                            profile_id = profile_info.get("profile_id")
                            nick_name = profile_info.get("nick_name")
                            demo_balance = profile_info.get("demo_balance", 0)
                            live_balance = profile_info.get("live_balance", 0)
                            if not profile_info.get("country_name") and profile_info.get("country"):
                                pass
                            country = "—"
                            if not nick_name:
                                pass
                            elif not profile_id:
                                pass
                            profile_panel = Panel(f"[bold cyan]👤 Trader:[/bold cyan] {"N/A"}\n[bold cyan]🆔 ID:[/bold cyan] [bold yellow]{"N/A"}[/]\n[bold cyan]🌍 Country:[/bold cyan] {country}\n[bold cyan]💼 DEMO Balance:[/bold cyan] [green]${demo_balance:,.2f}[/]\n[bold cyan]💰 REAL Balance:[/bold cyan] [yellow]${live_balance:,.2f}[/]", title="🎯 Account Information", border_style="cyan")
                            console.print(profile_panel)
                            try:
                                await client.get_balance()
                                balance = await client.get_balance()
                                console.print(f"[bold green]✓ Active balance: ${balance:,.2f}[/bold green]")
                            finally:
                                pass
                            if Exception:
                                Exception
                                e = None
                                try:
                                    console.print(f"[yellow]⚠ Could not fetch balance: {e}[/yellow]")
                                finally:
                                    pass
                                tg = TelegramBot()
                                if config.telegram_enabled and config.telegram_token and config.telegram_chat_id:
                                    tg.token = config.telegram_token
                                    tg.chat_id = config.telegram_chat_id
                                    tg.enabled = True
                                    console.print("[green]✓ Telegram notifications: ENABLED[/green]")
                                    try:
                                        if not nick_name:
                                            pass
                                    finally:
                                        pass
                                    "✅ <b>Bot Connected</b>\n👤 "(f"{"Trader"}\n🆔 ID: <code>profile_id{__exception__}</code>\n🏦 Account: {config.account}")
                                    if Exception:
                                        Exception
                                        tg.send
                                        tg.send
                                    console.print("[dim]ℹ Telegram notifications: disabled (configure in Settings)[/dim]")
                                    screenshot = ScreenshotManager()
                                    if config.screenshot_enabled and SCREENSHOT_AVAILABLE:
                                        screenshot.enabled = True
                                        console.print("[green]✓ Screenshots: ENABLED[/green]")
                                    elif not config.screenshot_enabled and SCREENSHOT_AVAILABLE:
                                        console.print("[yellow]⚠ Screenshots enabled in config but mss/PIL not installed[/yellow]")
                                    else:
                                        console.print("[dim]ℹ Screenshots: disabled[/dim]")
                            csv_log = CSVLogger()
                            if config.csv_enabled:
                                csv_log.enabled = True
                                csv_log.start_new_session()
                                console.print(f"[green]✓ CSV logging: ENABLED → {csv_log.path}[/green]")
                            else:
                                console.print("[dim]ℹ CSV logging: disabled[/dim]")
                            scheduler = TradingScheduler()
                            if config.schedule_enabled:
                                scheduler.enabled = True
                                scheduler.start_hour = config.schedule_start_hour
                                scheduler.end_hour = config.schedule_end_hour
                                scheduler.days = list(config.schedule_weekdays)
                                console.print(f"[green]✓ Schedule: {config.schedule_start_hour:02d}:00 → {config.schedule_end_hour:02d}:00[/green]")
                            else:
                                console.print("[dim]ℹ Schedule: always active[/dim]")
                            console.print("\n[dim]Press Enter to continue to main menu...[/dim]")
                            try:
                                input()
                            finally:
                                pass
                            if (EOFError, KeyboardInterrupt):
                                (EOFError, KeyboardInterrupt)
                            try:
                                try:
                                    pass
                                finally:
                                    pass
                                await client(config, tg, screenshot, csv_log, scheduler, __exception__)
                                await client(config, tg, screenshot, csv_log, scheduler, __exception__)
                                if KeyboardInterrupt:
                                    KeyboardInterrupt
                                    main_menu
                                    main_menu
                                    console.print("\n[yellow]Interrupted by user.[/yellow]")
                                elif Exception:
                                    Exception
                                    e = None
                                    try:
                                        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
                                        import traceback
                                        traceback.print_exc()
                                    finally:
                                        pass
                                    for closer in ("close", "close_connection", "disconnect", "logout"):
                                        try:
                                            fn = getattr(client, closer, None)
                                            if fn is None:
                                                pass
                                        finally:
                                            res = fn()
                                            if asyncio.iscoroutine(res):
                                                await res
                                                await res
                                            console.print("[dim]✓ Disconnected from Quotex.[/dim]")
                                            return
                                            if Exception:
                                                Exception
                                            return
                                            for closer in ("close", "close_connection", "disconnect", "logout"):
                                                try:
                                                    fn = getattr(client, closer, None)
                                                    if fn is None:
                                                        pass
                                                finally:
                                                    res = fn()
                                                    if __exception__.iscoroutine(res):
                                                        await res
                                                        await res
                                                    console.print("[dim]✓ Disconnected from Quotex.[/dim]")
                                                    asyncio
                                                    if Exception:
                                                        Exception
_CURRENT_TRADING_TASK = None
def _install_sigint_handler(loop):
    import signal
    
    last_press = [0.0]
    def handler(signum, frame):
        now = time.time()
        
        if now - last_press[0] < 1.5:
            console.print("\n[red]⏹ Double Ctrl+C → exiting…[/red]")
            try:
                for task in asyncio.all_tasks(loop):
                    pass
            finally:
                __exception__.cancel()
                raise KeyboardInterrupt()
            if Exception:
                Exception
                task
                task
            raise KeyboardInterrupt()
            last_press[0] = now
            if not _CURRENT_TRADING_TASK and _CURRENT_TRADING_TASK.done():
                console.print("\n[yellow]⏹ Ctrl+C → returning to main menu… (press again to exit)[/yellow]")
                _CURRENT_TRADING_TASK.cancel()
                return
            raise KeyboardInterrupt()
    
    try:
        pass
    finally:
        signal.SIGINT(handler, __exception__)
        return
    if Exception:
        Exception
        signal.signal
        signal.signal
    return
def _run_main():
    try:
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            finally:
                pass
            if Exception:
                Exception
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _install_sigint_handler(loop)
            try:
                loop.run_until_complete(interactive_main())
            finally:
                try:
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    for t in pending:
                        pass
                finally:
                    __exception__
                    if pending:
                        loop.run_until_complete(asyncio.gather(return_exceptions=True, *pending))
                if Exception:
                    Exception
                    t.cancel()
                    t.cancel()
                try:
                    loop.close()
                finally:
                    return
                if Exception:
                    Exception
                    __exception__
                    __exception__
                return
                try:
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    for t in pending:
                        pass
                finally:
                    __exception__
                    if pending:
                        loop.run_until_complete(asyncio.gather(return_exceptions=True, *pending))
                if Exception:
                    Exception
                    t.cancel()
                    t.cancel()
                try:
                    pass
                finally:
                    __exception__
                if Exception:
                    Exception
                    loop.close()
                    loop.close()
                elif KeyboardInterrupt:
                    KeyboardInterrupt
                    console.print("\n[yellow]Goodbye! 👋[/yellow]")
                return
                if Exception:
                    Exception
                    e = None
                    try:
                        console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        pass
                    return
if __name__ == "__main__":
    _run_main()
    return
return
