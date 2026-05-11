#!/usr/bin/env python3
"""PyQuotex CLI — Complete Quotex trading API client.

Every public method exposed by "stable_api.Quotex" is reachable from this
CLI. Use "python app.py --help" or "python app.py <command> --help" for
full usage.

Commands
--------
Connection & Auth
    login Connect and show profile + balance Show current balance

Account Management
    set-demo-balance Refill / set demo (practice) balance
    server-time Show synced server timestamp
    settings Apply and retrieve trading-UI settings

Assets & Payouts
    assets List all available assets with open/closed status
    payout Show payout % for all asset
    payout-asset Show payout % for a single asset

Candle / Market Data
    candles Fetch latest candles (up to 199 per request)
    candles-v2 Fetch candles via the v2 API path
    candles-deep Fetch deep historical data (parallel workers)
    history-line Fetch raw historical price-line data
    candle-info Opening / closing / remaining time of current candle
    realtime-price Live price stream for an asset
    realtime-sentiment Live trader-sentiment stream
    realtime-candle Live candle tick stream

Trading
    buy Place an immediate binary option trade
    sell / close an open position early
    pending Place a pending order (executed at a future time)
    check a win/loss result of a trade by ID
    result Look up a trade result from history by operation ID
    signals Fetch current signal data from the signal stream

History Show recent trade history (paged)

Indicator     Calculate a technical indicator (RSI, MACD, BB, …)
    subscribe-indicator Live indicator stream with callback

Monitoring
    monitor Real-time candle price monitor
    strategy Run Triple-Confirmation strategy (demo only)
"""
import argparse
import asyncio
import csv
import logging
import sys
import time
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
)
from rich.table import Table

from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from pyquotex.utils.strategy import TripleConfirmationStrategy

console = Console()
logger = logging.getLogger(__name__)

# Global to track current progress for OTP handling
current_progress: Progress | None = None


# ---------------------------------------------------------------------------
# OTP callback
# ---------------------------------------------------------------------------

async def on_otp(message: str) -> str:
    """Callback to handle OTP input, pausing progress spinners if active."""
    if current_progress:
        current_progress.stop()
        try:
            pin = console.input(f"[bold yellow]🔐 {message}[/]")
            return pin
        finally:
            current_progress.start()
    else:
        return console.input(f"[bold yellow]🔐 {message}[/]")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyquotex",
        description="⚡ PyQuotex — Complete Quotex trading API CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pyquotex login --demo\n"
            "  pyquotex balance --live\n"
            "  pyquotex assets\n"
            "  pyquotex payout\n"
            "  pyquotex payout-asset --asset EURUSD --timeframe 1\n"
            "  pyquotex candles --asset EURUSD --period 60 --count 10\n"
            "  pyquotex candles-v2 --asset EURUSD --period 60\n"
            "  pyquotex candles-deep --asset EURUSD --seconds 3600 --workers 5\n"
            "  pyquotex history-line --asset EURUSD --offset 3600\n"
            "  pyquotex candle-info --asset EURUSD --period 60\n"
            "  pyquotex realtime-price --asset EURUSD\n"
            "  pyquotex realtime-sentiment --asset EURUSD\n"
            "  pyquotex realtime-candle --asset EURUSD --period 60\n"
            "  pyquotex buy --asset EURUSD --amount 5 --direction call --duration 60 --check-win\n"
            "  pyquotex sell --id TRADE_ID\n"
            "  pyquotex pending --asset EURUSD --amount 10 --direction call --duration 60\n"
            "  pyquotex check --id TRADE_ID\n"
            "  pyquotex result --id OPERATION_ID\n"
            "  pyquotex history --pages 2\n"
            "  pyquotex signals\n"
            "  pyquotex indicator --asset EURUSD --name RSI --period 14\n"
            "  pyquotex server-time\n"
            "  pyquotex set-demo-balance --amount 10000\n"
            "  pyquotex settings --asset EURUSD --period 60\n"
            "  pyquotex monitor --asset EURUSD\n"
            "  pyquotex strategy --asset EURUSD --auto-trade\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── helpers ─────────────────────────────────────────────────────────────
    def _add_account_flags(p: argparse.ArgumentParser) -> None:
        g = p.add_mutually_exclusive_group()
        g.add_argument("--demo", action="store_true", default=True,
                       help="Use demo account (default)")
        g.add_argument("--live", action="store_true",
                       help="Use live account")

    def _add_asset_flag(p: argparse.ArgumentParser,
                        default: str = "EURUSD") -> None:
        p.add_argument("--asset", default=default,
                       help=f"Asset symbol (default: {default})")

    # ── test-all ─────────────────────────────────────────────────────────────
    sub.add_parser("test-all", help="Run all tests")

    # ── login ────────────────────────────────────────────────────────────────
    p = sub.add_parser("login", help="Test connection and show profile + balance")
    _add_account_flags(p)

    # ── balance ──────────────────────────────────────────────────────────────
    p = sub.add_parser("balance", help="Show account balance")
    _add_account_flags(p)

    # ── server-time ──────────────────────────────────────────────────────────
    sub.add_parser("server-time",
                   help="Show the current synced server timestamp")

    # ── set-demo-balance ─────────────────────────────────────────────────────
    p = sub.add_parser("set-demo-balance",
                       help="Refill or set demo (practice) account balance")
    p.add_argument("--amount", type=float, default=10000.0,
                   help="Amount to set (default: 10000)")

    # ── settings ─────────────────────────────────────────────────────────────
    p = sub.add_parser("settings",
                       help="Apply trading-UI settings and show result")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    p.add_argument("--mode", choices=["TIMER", "TURBO"], default="TIMER",
                   help="Time mode (default: TIMER)")
    p.add_argument("--deal", type=int, default=5,
                   help="Default deal amount (default: 5)")
    _add_account_flags(p)

    # ── assets ───────────────────────────────────────────────────────────────
    sub.add_parser("assets", help="List all available assets")

    # ── payout ───────────────────────────────────────────────────────────────
    sub.add_parser("payout", help="Show payout %% for all assets")

    # ── payout-asset ─────────────────────────────────────────────────────────
    p = sub.add_parser("payout-asset",
                       help="Show payout %% for a specific asset")
    _add_asset_flag(p)
    p.add_argument("--timeframe", default="1",
                   choices=["1", "5", "24", "all"],
                   help="Timeframe in minutes, or 'all' (default: 1)")

    # ── candles ──────────────────────────────────────────────────────────────
    p = sub.add_parser("candles", help="Fetch latest candle data (≤199)")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    p.add_argument("--count", type=int, default=10,
                   help="Number of candles to display (default: 10)")
    _add_account_flags(p)

    # ── candles-v2 ───────────────────────────────────────────────────────────
    p = sub.add_parser("candles-v2",
                       help="Fetch candles via the v2 API path")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    _add_account_flags(p)

    # ── candles-deep ─────────────────────────────────────────────────────────
    p = sub.add_parser("candles-deep",
                       help="Fetch deep historical candle data (parallel workers)")
    _add_asset_flag(p)
    p.add_argument("--seconds", type=int, default=3600,
                   help="Total history window in seconds (default: 3600)")
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    p.add_argument("--workers", type=int, default=5,
                   help="Parallel workers 2-10 (default: 5). "
                        "WARNING: >10 may cause a ban.")
    p.add_argument("--output", metavar="FILE",
                   help="Save results to a CSV file")
    _add_account_flags(p)

    # ── history-line ─────────────────────────────────────────────────────────
    p = sub.add_parser("history-line",
                       help="Fetch raw historical price-line data")
    _add_asset_flag(p)
    p.add_argument("--offset", type=int, default=3600,
                   help="History window in seconds (default: 3600)")
    _add_account_flags(p)

    # ── candle-info ──────────────────────────────────────────────────────────
    p = sub.add_parser("candle-info",
                       help="Show opening / closing / remaining time of current candle")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    _add_account_flags(p)

    # ── realtime-price ───────────────────────────────────────────────────────
    p = sub.add_parser("realtime-price",
                       help="Stream live price data for an asset")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    _add_account_flags(p)

    # ── realtime-sentiment ───────────────────────────────────────────────────
    p = sub.add_parser("realtime-sentiment",
                       help="Stream live trader-sentiment data")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    _add_account_flags(p)

    # ── realtime-candle ──────────────────────────────────────────────────────
    p = sub.add_parser("realtime-candle",
                       help="Stream live processed candle ticks")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    _add_account_flags(p)

    # ── buy ──────────────────────────────────────────────────────────────────
    p = sub.add_parser("buy", help="Place an immediate binary option trade")
    _add_asset_flag(p)
    p.add_argument("--amount", type=float, default=1.0,
                   help="Trade amount (default: 1.0)")
    p.add_argument("--direction", choices=["call", "put"], default="call",
                   help="call = UP, put = DOWN (default: call)")
    p.add_argument("--duration", type=int, default=60,
                   help="Duration in seconds (default: 60)")
    p.add_argument("--check-win", action="store_true",
                   help="Wait for the trade to settle and show win/loss")
    _add_account_flags(p)

    # ── sell ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("sell", help="Sell / close an open position early")
    p.add_argument("--id", dest="trade_id", required=True,
                   help="Trade ID to sell")
    _add_account_flags(p)

    # ── pending ──────────────────────────────────────────────────────────────
    p = sub.add_parser("pending",
                       help="Place a pending order (executed at a future time)")
    _add_asset_flag(p)
    p.add_argument("--amount", type=float, default=1.0,
                   help="Trade amount (default: 1.0)")
    p.add_argument("--direction", choices=["call", "put"], default="call",
                   help="call = UP, put = DOWN (default: call)")
    p.add_argument("--duration", type=int, default=60,
                   help="Duration in seconds (default: 60)")
    p.add_argument("--open-time", dest="open_time", default=None,
                   help="Exact open time HH:MM (optional, defaults to next candle)")
    _add_account_flags(p)

    # ── check ────────────────────────────────────────────────────────────────
    p = sub.add_parser("check",
                       help="Check win/loss result of a trade by ID")
    p.add_argument("--id", dest="trade_id", required=True,
                   help="Trade ID to check")
    _add_account_flags(p)

    # ── result ───────────────────────────────────────────────────────────────
    p = sub.add_parser("result",
                       help="Look up trade result from history by operation ID")
    p.add_argument("--id", dest="operation_id", required=True,
                   help="Operation ID to look up")
    _add_account_flags(p)

    # ── history ──────────────────────────────────────────────────────────────
    p = sub.add_parser("history", help="Show recent trade history (paged)")
    p.add_argument("--pages", type=int, default=1,
                   help="Number of history pages (default: 1)")
    _add_account_flags(p)

    # ── signals ──────────────────────────────────────────────────────────────
    sub.add_parser("signals",
                   help="Fetch current signal data from the signals stream")

    # ── indicator ────────────────────────────────────────────────────────────
    p = sub.add_parser("indicator",
                       help="Calculate a technical indicator (RSI, MACD, BB, …)")
    _add_asset_flag(p)
    p.add_argument("--name",
                   choices=["RSI", "MACD", "BOLLINGER",
                            "STOCHASTIC", "ADX", "ATR", "SMA", "EMA", "ICHIMOKU"],
                   default="RSI",
                   help="Indicator name (default: RSI)")
    p.add_argument("--period", type=int, default=14,
                   help="Indicator period (default: 14)")
    p.add_argument("--timeframe", type=int, default=60,
                   help="Candle timeframe in seconds (default: 60)")
    _add_account_flags(p)

    # ── monitor ──────────────────────────────────────────────────────────────
    p = sub.add_parser("monitor",
                       help="Real-time price monitor for an asset")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")

    # ── strategy ─────────────────────────────────────────────────────────────
    p = sub.add_parser("strategy",
                       help="Run Triple-Confirmation strategy (DEMO recommended)")
    _add_asset_flag(p)
    p.add_argument("--period", type=int, default=60,
                   help="Candle period in seconds (default: 60)")
    p.add_argument("--auto-trade", action="store_true",
                   help="Automatically place trades on signals (DEMO only)")

    return parser


# ---------------------------------------------------------------------------
# Connection helper with exponential backoff
# ---------------------------------------------------------------------------

async def connect_with_retry(
        client: Quotex,
        is_demo: bool,
        max_attempts: int = 5,
) -> bool:
    """Connect to Quotex with exponential backoff on failure."""
    if await client.check_connect():
        return True

    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        with Progress(
                SpinnerColumn(),
                TextColumn(
                    f"[cyan]Connecting (attempt {attempt}/{max_attempts})…"
                ),
                transient=True,
                console=console,
        ) as prog:
            global current_progress
            current_progress = prog
            prog.add_task("connect")
            client.account_is_demo = 1 if is_demo else 0
            try:
                check, reason = await client.connect()
            finally:
                current_progress = None

        if check:
            console.print(f"[bold green]✓[/] Connected — {reason}")
            return True

        console.print(
            f"[yellow]⚠ Connection failed:[/] {reason}. "
            f"Retrying in {delay:.0f}s…"
        )
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30)

    console.print("[bold red]✗ Could not connect after maximum attempts.[/]")
    return False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _is_demo(args: argparse.Namespace) -> bool:
    if hasattr(args, "live") and args.live:
        return False
    return True


def _balance_table(profile: Any) -> Table:
    table = Table(
        title="💰 [bold]Account Balance[/]",
        show_header=True,
        header_style="bold bright_white on magenta",
        box=box.ROUNDED,
        border_style="magenta",
        row_styles=["none", "dim"],
        padding=(0, 1),
    )
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("Balance", justify="right", style="bold green")
    table.add_column("Currency", style="bright_white")
    table.add_row(
        "Demo", f"{profile.demo_balance:,.2f}", profile.currency_symbol or ""
    )
    table.add_row(
        "Live", f"{profile.live_balance:,.2f}", profile.currency_symbol or ""
    )
    return table


# ---------------------------------------------------------------------------
# Command implementations — moved to pyquotex.cli.commands.*
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _print_candles_table(
        candles: list[dict],
        asset: str,
        period: int,
        title: str | None = None,
) -> None:
    """Render a Rich table of candle data."""
    tbl_title = title or f"🕯️  [bold]Candles — {asset} ({period}s)[/]"
    table = Table(
        title=tbl_title,
        box=box.ROUNDED,
        border_style="bright_blue",
        show_header=True,
        header_style="bold bright_white on blue",
        row_styles=["none", "dim"],
    )
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right", style="green")
    table.add_column("Low", justify="right", style="red")
    table.add_column("Close", justify="right", style="bold")
    table.add_column("Dir", justify="center")

    for c in candles:
        ts = c.get("time", c.get("timestamp", 0))
        try:
            ts_str = datetime.fromtimestamp(int(ts)).strftime("%m-%d %H:%M:%S")
        except Exception:
            ts_str = str(ts)
        o = c.get("open", 0)
        h = c.get("max", c.get("high", 0))
        lo = c.get("min", c.get("low", 0))
        cl = c.get("close", 0)
        direction = (
            "[green]▲[/]" if float(cl) >= float(o)
            else "[red]▼[/]"
        )
        table.add_row(
            ts_str,
            f"{float(o):.5f}",
            f"{float(h):.5f}",
            f"{float(lo):.5f}",
            f"{float(cl):.5f}",
            direction,
        )
    console.print(table)


def _save_candles_csv(candles: list[dict], filepath: str) -> None:
    """Save the candles list to a CSV file."""
    if not candles:
        return
    fieldnames = list(candles[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candles)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

COMMAND_MAP: dict[str, Any] = {
    "login": cmd_login,
    "balance": cmd_balance,
    "server-time": cmd_server_time,
    "set-demo-balance": cmd_set_demo_balance,
    "settings": cmd_settings,
    "assets": cmd_assets,
    "payout": cmd_payout,
    "payout-asset": cmd_payout_asset,
    "candles": cmd_candles,
    "candles-v2": cmd_candles_v2,
    "candles-deep": cmd_candles_deep,
    "history-line": cmd_history_line,
    "candle-info": cmd_candle_info,
    "realtime-price": cmd_realtime_price,
    "realtime-sentiment": cmd_realtime_sentiment,
    "realtime-candle": cmd_realtime_candle,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "pending": cmd_pending,
    "check": cmd_check,
    "result": cmd_result,
    "signals": cmd_signals,
    "history": cmd_history,
    "indicator": cmd_indicator,
    "monitor": cmd_monitor,
    "strategy": cmd_strategy,
    "test-all": cmd_test_all,
}


async def main() -> None:
    parser = make_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    email, password = credentials()
    client = Quotex(
        email=email,
        password=password,
        on_otp_callback=on_otp,
    )

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        console.print(f"[red]Unknown command: {args.command}[/]")
        parser.print_help()
        return

    try:
        await handler(client, args)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
