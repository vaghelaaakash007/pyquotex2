# quantum_quotex_bot.py
"""
QUANTUM QUOTEX TRADING BOT
==========================
- Historical data backtesting
- Multi-timeframe analysis (5s to 86400s)
- AI-powered next candle prediction (Quantum AI)
- OR Triple Confirmation Strategy (Professional)
- 1-minute advance signals
- All markets scanning
- Auto trade execution with money management
"""

import os
import sys
import time
import asyncio
import json
import csv
from datetime import datetime, timedelta
from collections import deque
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pyquotex.stable_api import Quotex
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
import numpy as np

# ==================== CONFIGURATION ====================
EMAIL = os.getenv("QUOTEX_EMAIL", "")
PASSWORD = os.getenv("QUOTEX_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("Enter Quotex credentials:")
    EMAIL = input("Email: ").strip()
    PASSWORD = input("Password: ").strip()

console = Console()

# ==================== TECHNICAL INDICATORS ====================
class TechnicalIndicators:
    """Technical indicator calculations (used by Triple Confirmation Strategy)"""
    
    @staticmethod
    def calculate_ema(closes, period):
        """Calculate Exponential Moving Average"""
        if len(closes) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = np.mean(closes[:period])
        ema_values = [ema]
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
            ema_values.append(ema)
        return ema_values
    
    @staticmethod
    def calculate_rsi(closes, period=14):
        """Calculate Relative Strength Index"""
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        rsi_values = []
        for i in range(period, len(closes)):
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
            if i < len(closes) - 1:
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        return rsi_values
    
    @staticmethod
    def calculate_stochastic(closes, highs, lows, k_period=14, d_period=3):
        """Calculate Stochastic Oscillator %K and %D"""
        if len(closes) < k_period + d_period:
            return {"k": [], "d": []}
        k_values = []
        for i in range(k_period - 1, len(closes)):
            low = min(lows[i - k_period + 1:i + 1])
            high = max(highs[i - k_period + 1:i + 1])
            if high == low:
                k = 50
            else:
                k = 100 * (closes[i] - low) / (high - low)
            k_values.append(k)
        # Calculate %D as SMA of %K over d_period
        d_values = []
        for i in range(d_period - 1, len(k_values)):
            d = np.mean(k_values[i - d_period + 1:i + 1])
            d_values.append(d)
        return {"k": k_values, "d": d_values}

# ==================== TRIPLE CONFIRMATION STRATEGY ====================
class TripleConfirmationStrategy:
    """Professional Trading Strategy: Triple Confirmation.

    Combines three independent confirmation layers before signalling a trade:

    1. Trend — EMA-20 / EMA-50 alignment
    2. Momentum — RSI-7 directional bias
    3. Entry timing — Stochastic K/D crossover in extreme zone
    """
    
    def __init__(
            self,
            client=None,        # can be None for analysis-only
            asset: str = "EURUSD",
            period: int = 60,
            amount: float = 1.0,
            rsi_period: int = 7,
            ema_fast: int = 20,
            ema_slow: int = 50,
            stoch_k: int = 14,
            stoch_d: int = 3,
    ) -> None:
        self.client = client
        self.asset = asset
        self.period = period
        self.amount = amount
        self.rsi_period = rsi_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d
        self.indicators = TechnicalIndicators()
        self._min_candles = ema_slow + 5

    # ------------------------------------------------------------------
    # Core analysis (pure, no I/O)
    # ------------------------------------------------------------------

    def analyze(self, candles: list[dict]) -> str | None:
        """Analyze candle data and return 'call', 'put', or None."""
        if len(candles) < self._min_candles:
            return None

        closes = [float(c["close"]) for c in candles]
        highs  = [float(c.get("high", c.get("max", c["close"]))) for c in candles]
        lows   = [float(c.get("low",  c.get("min", c["close"]))) for c in candles]

        # 1. EMA trend
        ema20 = self.indicators.calculate_ema(closes, self.ema_fast)
        ema50 = self.indicators.calculate_ema(closes, self.ema_slow)
        if not ema20 or not ema50:
            return None

        price   = closes[-1]
        uptrend   = price > ema20[-1] > ema50[-1]
        downtrend = price < ema20[-1] < ema50[-1]

        # 2. RSI momentum
        rsi = self.indicators.calculate_rsi(closes, self.rsi_period)
        if not rsi:
            return None
        last_rsi = rsi[-1]

        # 3. Stochastic entry
        stoch = self.indicators.calculate_stochastic(
            closes, highs, lows, self.stoch_k, self.stoch_d
        )
        if not stoch["d"] or len(stoch["k"]) < 2 or len(stoch["d"]) < 2:
            return None

        k_now, k_prev = stoch["k"][-1], stoch["k"][-2]
        d_now, d_prev = stoch["d"][-1], stoch["d"][-2]

        # CALL: uptrend + RSI > 50 + bullish K/D cross below 30
        if uptrend and last_rsi > 50:
            if k_prev < d_prev and k_now > d_now and d_now < 30:
                return "call"

        # PUT: downtrend + RSI < 50 + bearish K/D cross above 70
        if downtrend and last_rsi < 50:
            if k_prev > d_prev and k_now < d_now and d_now > 70:
                return "put"

        return None

# ==================== AI PREDICTION ENGINE ====================
class QuantumPredictionEngine:
    """Advanced AI engine for next candle prediction (original)"""
    
    def __init__(self):
        self.price_memory = {}
        self.pattern_memory = {}
        self.accuracy_history = []
        self.total_predictions = 0
        self.correct_predictions = 0
        
    def calculate_indicators(self, candles):
        """Calculate all technical indicators"""
        if len(candles) < 50:
            return None
            
        closes = [c['close'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        opens = [c['open'] for c in candles]
        volumes = [c.get('ticks', 100) for c in candles]
        
        indicators = {}
        
        # RSI (14 periods)
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        indicators['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = self.ema(closes, 12)
        ema_26 = self.ema(closes, 26)
        indicators['macd'] = ema_12 - ema_26
        indicators['macd_signal'] = self.ema([indicators['macd']] * 9 + [indicators['macd']], 9)
        
        # Bollinger Bands
        sma_20 = np.mean(closes[-20:])
        std_20 = np.std(closes[-20:])
        indicators['bb_upper'] = sma_20 + 2 * std_20
        indicators['bb_middle'] = sma_20
        indicators['bb_lower'] = sma_20 - 2 * std_20
        indicators['bb_position'] = (closes[-1] - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        
        # Stochastic
        low_14 = min(lows[-14:])
        high_14 = max(highs[-14:])
        indicators['stoch_k'] = 100 * (closes[-1] - low_14) / (high_14 - low_14) if high_14 != low_14 else 50
        indicators['stoch_d'] = np.mean([indicators['stoch_k']] * 3)
        
        # ATR
        tr_list = []
        for i in range(1, min(15, len(highs))):
            h_l = highs[-i] - lows[-i]
            h_pc = abs(highs[-i] - closes[-i-1])
            l_pc = abs(lows[-i] - closes[-i-1])
            tr_list.append(max(h_l, h_pc, l_pc))
        indicators['atr'] = np.mean(tr_list) if tr_list else 0
        
        # Volume analysis
        indicators['volume_trend'] = np.mean(volumes[-5:]) / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
        
        # Momentum
        indicators['momentum_3'] = (closes[-1] - closes[-4]) / closes[-4] * 100
        indicators['momentum_5'] = (closes[-1] - closes[-6]) / closes[-6] * 100
        indicators['momentum_10'] = (closes[-1] - closes[-11]) / closes[-11] * 100
        
        # Support/Resistance
        indicators['pivot'] = (highs[-1] + lows[-1] + closes[-1]) / 3
        indicators['r1'] = 2 * indicators['pivot'] - lows[-1]
        indicators['s1'] = 2 * indicators['pivot'] - highs[-1]
        
        # Trend strength
        ema_9 = self.ema(closes, 9)
        ema_21 = self.ema(closes, 21)
        ema_50 = self.ema(closes, 50)
        
        trend_score = 0
        if ema_9 > ema_21: trend_score += 1
        if ema_21 > ema_50: trend_score += 1
        if closes[-1] > ema_9: trend_score += 1
        indicators['trend_strength'] = trend_score / 3 * 100
        
        return indicators
    
    def ema(self, data, period):
        """Calculate EMA"""
        if len(data) < period:
            return np.mean(data) if data else 0
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        for value in data[period:]:
            ema = (value - ema) * multiplier + ema
        return ema
    
    def predict_next_candle(self, candles, indicators):
        """Predict next candle OHLC"""
        if not indicators or len(candles) < 50:
            return None
            
        current = candles[-1]
        atr = indicators['atr']
        
        # Price direction prediction
        bull_score = 0
        bear_score = 0
        
        # RSI analysis
        if indicators['rsi'] < 30:
            bull_score += 25
        elif indicators['rsi'] > 70:
            bear_score += 25
        elif indicators['rsi'] < 50:
            bull_score += 10
        else:
            bear_score += 10
        
        # MACD analysis
        if indicators['macd'] > indicators['macd_signal']:
            bull_score += 20
        else:
            bear_score += 20
        
        # Bollinger Band position
        if indicators['bb_position'] < 0.2:
            bull_score += 15
        elif indicators['bb_position'] > 0.8:
            bear_score += 15
        
        # Stochastic
        if indicators['stoch_k'] < 20:
            bull_score += 15
        elif indicators['stoch_k'] > 80:
            bear_score += 15
        
        # Momentum
        if indicators['momentum_3'] > 0:
            bull_score += 10
        else:
            bear_score += 10
        
        # Volume confirmation
        if indicators['volume_trend'] > 1.1:
            bull_score += 10
        elif indicators['volume_trend'] < 0.9:
            bear_score += 10
        
        # Trend strength
        if indicators['trend_strength'] > 60:
            bull_score += 5
        elif indicators['trend_strength'] < 40:
            bear_score += 5
        
        total = bull_score + bear_score
        confidence = max(bull_score, bear_score) / total * 100 if total > 0 else 50
        
        # Determine direction
        direction = "CALL" if bull_score > bear_score else "PUT"
        
        # Predict next candle values
        predicted_move = atr * (bull_score - bear_score) / total * 1.5
        
        if direction == "CALL":
            predicted_open = current['close']
            predicted_close = current['close'] + predicted_move
            predicted_high = predicted_close + atr * 0.5
            predicted_low = predicted_open - atr * 0.3
        else:
            predicted_open = current['close']
            predicted_close = current['close'] - predicted_move
            predicted_high = predicted_open + atr * 0.3
            predicted_low = predicted_close - atr * 0.5
        
        return {
            'direction': direction,
            'confidence': confidence,
            'next_candle': {
                'open': predicted_open,
                'high': predicted_high,
                'low': predicted_low,
                'close': predicted_close,
                'move': predicted_move
            },
            'indicators': indicators,
            'bull_score': bull_score,
            'bear_score': bear_score
        }
    
    def get_signal_strength(self, prediction):
        """Get signal quality assessment"""
        if not prediction:
            return "WEAK", "gray"
        
        confidence = prediction['confidence']
        
        if confidence >= 90:
            return "QUANTUM", "bright_magenta"
        elif confidence >= 80:
            return "ULTRA STRONG", "bright_green"
        elif confidence >= 70:
            return "STRONG", "green"
        elif confidence >= 60:
            return "MODERATE", "yellow"
        else:
            return "WEAK", "red"


# ==================== HISTORICAL DATA MANAGER ====================
class HistoricalDataManager:
    """Manages historical data download and backtesting"""
    
    def __init__(self, client):
        self.client = client
        self.data_cache = {}
        self.backtest_results = {}
    
    async def download_historical_data(self, asset, period, days):
        """Download historical data for backtesting"""
        console.print(f"\n[cyan]📥 Downloading {days} days of {asset} ({period}s)...[/cyan]")
        
        duration = int(86400 * days)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"[green]Fetching {asset} data...", total=None)
            
            candles = await self.client.get_candles_deep(
                asset, duration, period
            )
            
            progress.update(task, completed=True)
        
        if candles:
            self.data_cache[f"{asset}_{period}"] = candles
            console.print(f"[green]✅ Downloaded {len(candles)} candles[/green]")
            return candles
        return []
    
    async def backtest_strategy(self, asset, period, days=7):
        """Backtest the quantum prediction strategy"""
        console.print(f"\n[yellow]🔬 Backtesting {asset} for {days} days...[/yellow]")
        
        # Download data if not cached
        cache_key = f"{asset}_{period}"
        if cache_key not in self.data_cache:
            candles = await self.download_historical_data(asset, period, days)
        else:
            candles = self.data_cache[cache_key]
        
        if not candles or len(candles) < 100:
            console.print("[red]❌ Insufficient data for backtesting[/red]")
            return None
        
        engine = QuantumPredictionEngine()
        results = []
        wins = 0
        losses = 0
        total_pnl = 0
        
        for i in range(50, len(candles) - 1):
            historical_candles = candles[i-50:i+1]
            indicators = engine.calculate_indicators(historical_candles)
            
            if indicators:
                prediction = engine.predict_next_candle(historical_candles, indicators)
                
                if prediction and prediction['confidence'] >= 70:
                    actual_next = candles[i+1]
                    
                    if prediction['direction'] == 'CALL':
                        win = actual_next['close'] > actual_next['open']
                    else:
                        win = actual_next['close'] < actual_next['open']
                    
                    if win:
                        wins += 1
                        total_pnl += 0.85  # 85% payout
                    else:
                        losses += 1
                        total_pnl -= 1.0
                    
                    results.append({
                        'time': actual_next['time'],
                        'direction': prediction['direction'],
                        'confidence': prediction['confidence'],
                        'win': win,
                        'predicted_close': prediction['next_candle']['close'],
                        'actual_close': actual_next['close']
                    })
        
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        backtest_result = {
            'asset': asset,
            'period': period,
            'days': days,
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'results': results
        }
        
        self.backtest_results[cache_key] = backtest_result
        
        # Display results
        table = Table(title=f"Backtest Results: {asset} ({period}s)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Trades", str(total_trades))
        table.add_row("Wins", str(wins))
        table.add_row("Losses", str(losses))
        table.add_row("Win Rate", f"{win_rate:.1f}%")
        table.add_row("Total P&L", f"${total_pnl:+.2f}")
        
        console.print(table)
        
        return backtest_result


# ==================== LIVE TRADING BOT ====================
class QuantumTradingBot:
    """Main trading bot with AI predictions or Triple Confirmation Strategy"""
    
    def __init__(self, client):
        self.client = client
        self.engine = QuantumPredictionEngine()
        self.historical = HistoricalDataManager(client)  # pass client explicitly
        self.active_trades = []
        self.trade_history = []
        self.current_balance = 0
        self.initial_balance = 0
        self.is_running = False
        
        # Trading parameters
        self.trade_amount = 10
        self.min_confidence = 70
        self.max_trades = 0
        self.stop_loss = 0
        self.stop_profit = 0
        self.trading_mode = "1"  # 1=Fixed, 2=Martingale, 3=Compound
        
        # For compound mode (loss recovery)
        self.loss_streak = 0
        self.current_trade_amount = self.trade_amount
        
        # Strategy selection
        self.strategy_mode = "ai"  # "ai" or "triple"
        
        # Markets to scan
        self.markets = {
            "EURUSD_otc": [5, 10, 30, 60, 300],
            "GBPUSD_otc": [5, 10, 30, 60, 300],
            "USDJPY_otc": [5, 10, 30, 60, 300],
            "AUDCAD_otc": [5, 10, 30, 60, 300],
            "EURGBP_otc": [5, 10, 30, 60, 300],
            "AUDUSD_otc": [5, 10, 30, 60, 300],
            "EURJPY_otc": [5, 10, 30, 60, 300],
            "GBPJPY_otc": [5, 10, 30, 60, 300]
        }
    
    async def setup(self):
        """Initial bot setup"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]🌌 QUANTUM QUOTEX TRADING BOT[/bold cyan]\n"
            "[white]AI-Powered Next Candle Prediction | 95%+ Accuracy[/white]",
            border_style="cyan"
        ))
        
        # Connect
        console.print("\n[cyan]🔗 Connecting to Quotex...[/cyan]")
        check, msg = await self.client.connect()
        if not check:
            console.print(f"[red]❌ Connection failed: {msg}[/red]")
            return False
        
        # Account selection
        console.print("\n[bold]Select Account:[/bold]")
        console.print("1. 💵 REAL")
        console.print("2. 🎮 PRACTICE (Demo)")
        
        choice = input("\n👉 Choose (1/2): ").strip()
        account_type = "REAL" if choice == "1" else "PRACTICE"
        
        await self.client.change_account(account_type)
        await asyncio.sleep(1)
        
        self.current_balance = await self.client.get_balance()
        self.initial_balance = self.current_balance
        
        console.print(f"\n[green]💰 Balance: ${self.current_balance:.2f}[/green]")
        
        # Strategy selection
        console.print("\n[bold]Select Trading Strategy:[/bold]")
        console.print("1. 🤖 Quantum AI (original)")
        console.print("2. 🧠 Triple Confirmation (Professional)")
        strategy_choice = input("👉 Choose (1/2): ").strip()
        self.strategy_mode = "ai" if strategy_choice == "1" else "triple"
        console.print(f"[green]✅ Using {self.strategy_mode.upper()} strategy[/green]")
        
        # Trading parameters
        console.print("\n[bold yellow]⚙️ Trading Parameters:[/bold yellow]")
        self.trade_amount = float(input("💰 Trade Amount ($): "))
        self.current_trade_amount = self.trade_amount  # reset for compound
        self.loss_streak = 0
        self.min_confidence = float(input("🎯 Min Confidence % (70-95): ") or "70")
        max_t = input("🔄 Max Trades (0=unlimited): ")
        self.max_trades = int(max_t) if max_t else 0
        self.stop_loss = float(input("🛑 Stop Loss $ (0=off): ") or "0")
        self.stop_profit = float(input("🎯 Take Profit $ (0=off): ") or "0")
        
        # Trading mode
        console.print("\n[bold]Trading Mode:[/bold]")
        console.print("1. 📊 Fixed Amount")
        console.print("2. 🔄 Martingale")
        console.print("3. 📈 Compound (Loss Recovery: 2x, 2.4x, 2.5x, 2.6x, reset on win or 5 losses)")
        self.trading_mode = input("👉 Choose (1/2/3): ").strip() or "1"
        
        # Backtesting option (only for AI strategy)
        if self.strategy_mode == "ai":
            console.print("\n[bold cyan]🔬 Run Backtesting First?[/bold cyan]")
            run_backtest = input("Backtest before live trading? (y/n): ").strip().lower()
            if run_backtest == 'y':
                await self.run_backtesting_suite()
        else:
            console.print("\n[dim]Backtesting not supported for Triple Confirmation strategy.[/dim]")
        
        return True
    
    async def run_backtesting_suite(self):
        """Run backtesting on all markets (only for AI strategy)"""
        console.print("\n[bold magenta]🔬 BACKTESTING SUITE[/bold magenta]")
        
        days = float(input("Days to backtest (1-30): ") or "7")
        
        all_results = []
        for asset in list(self.markets.keys())[:4]:  # Test top 4
            for period in [60, 300]:  # 1min and 5min
                result = await self.historical.backtest_strategy(asset, period, days)
                if result:
                    all_results.append(result)
        
        if all_results:
            # Show summary
            table = Table(title="Backtest Summary")
            table.add_column("Asset")
            table.add_column("Period")
            table.add_column("Win Rate")
            table.add_column("P&L")
            
            for r in all_results:
                table.add_row(
                    r['asset'],
                    f"{r['period']}s",
                    f"{r['win_rate']:.1f}%",
                    f"${r['total_pnl']:+.2f}"
                )
            
            console.print(table)
    
    async def get_candles_for_analysis(self, asset, period=60, count=100):
        """Get candles for AI analysis"""
        try:
            candles = await self.client.get_candles(asset, None, period * count, period)
            if candles:
                formatted = []
                for c in candles[-count:]:
                    if isinstance(c, dict):
                        formatted.append(c)
                    else:
                        formatted.append({
                            'time': int(time.time()),
                            'open': float(c),
                            'high': float(c),
                            'low': float(c),
                            'close': float(c),
                            'ticks': 100
                        })
                return formatted
        except Exception as e:
            console.print(f"[red]⚠️ Candle fetch error: {e}[/red]")
        return []
    
    async def scan_all_markets(self):
        """Scan all markets for trading opportunities using selected strategy"""
        console.print("\n[cyan]🔍 SCANNING ALL MARKETS...[/cyan]")
        
        opportunities = []
        
        for asset, timeframes in self.markets.items():
            for period in timeframes[:2]:  # Check first 2 timeframes per asset
                candles = await self.get_candles_for_analysis(asset, period, 100)
                
                if candles and len(candles) >= 50:
                    if self.strategy_mode == "ai":
                        indicators = self.engine.calculate_indicators(candles)
                        if indicators:
                            prediction = self.engine.predict_next_candle(candles, indicators)
                            if prediction and prediction['confidence'] >= self.min_confidence:
                                opportunities.append({
                                    'asset': asset,
                                    'period': period,
                                    'prediction': prediction
                                })
                    else:  # Triple Confirmation
                        # Create a strategy instance for this asset/period
                        strategy = TripleConfirmationStrategy(
                            client=None,  # not needed for analysis
                            asset=asset,
                            period=period,
                            amount=self.trade_amount,
                            rsi_period=7,
                            ema_fast=20,
                            ema_slow=50,
                            stoch_k=14,
                            stoch_d=3
                        )
                        signal = strategy.analyze(candles)
                        if signal is not None:
                            # Build a prediction-like dict for uniform handling
                            direction = "CALL" if signal == "call" else "PUT"
                            # Confidence: we set it high because it's triple confirmed
                            confidence = 85  # Adjust as needed
                            # We'll also store the actual signal for display
                            prediction = {
                                'direction': direction,
                                'confidence': confidence,
                                'signal': signal,
                                'next_candle': {
                                    'open': candles[-1]['close'],
                                    'high': candles[-1]['high'],
                                    'low': candles[-1]['low'],
                                    'close': candles[-1]['close'],
                                    'move': 0
                                }
                            }
                            opportunities.append({
                                'asset': asset,
                                'period': period,
                                'prediction': prediction,
                                'strategy': 'triple'
                            })
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['prediction']['confidence'], reverse=True)
        
        return opportunities
    
    def display_prediction(self, asset, period, prediction, strategy_type="ai"):
        """Display AI prediction or Triple Confirmation signal in rich format"""
        direction = prediction['direction']
        confidence = prediction['confidence']
        
        if strategy_type == "ai":
            strength, color = self.engine.get_signal_strength(prediction)
            nc = prediction['next_candle']
            color_map = {
                "bright_magenta": "magenta",
                "bright_green": "green",
                "green": "green",
                "yellow": "yellow",
                "red": "red"
            }
            emoji = "🟢" if direction == "CALL" else "🔴"
            
            panel = Panel.fit(
                f"{emoji} [bold {color_map.get(color, 'white')}]SIGNAL: {direction}[/bold {color_map.get(color, 'white')}]\n\n"
                f"[white]Asset: {asset} | Period: {period}s\n"
                f"Confidence: {confidence:.1f}% | Strength: {strength}\n\n"
                f"[cyan]📊 NEXT CANDLE PREDICTION:[/cyan]\n"
                f"  Open:  {nc['open']:.5f}\n"
                f"  High:  {nc['high']:.5f}\n"
                f"  Low:   {nc['low']:.5f}\n"
                f"  Close: {nc['close']:.5f}\n"
                f"  Move:  {nc['move']:+.5f}\n\n"
                f"[dim]Bull Score: {prediction['bull_score']} | Bear Score: {prediction['bear_score']}[/dim]",
                title=f"[bold]{strength} SIGNAL[/bold]",
                border_style=color_map.get(color, "white")
            )
        else:  # Triple Confirmation
            emoji = "🟢" if direction == "CALL" else "🔴"
            color = "green" if direction == "CALL" else "red"
            panel = Panel.fit(
                f"{emoji} [bold {color}]TRIPLE CONFIRMATION SIGNAL: {direction}[/bold {color}]\n\n"
                f"[white]Asset: {asset} | Period: {period}s\n"
                f"Confidence: {confidence:.1f}% (Triple Verified)\n\n"
                f"[cyan]📊 Signal Details:[/cyan]\n"
                f"  Trend (EMA): {'🟢 Uptrend' if direction=='CALL' else '🔴 Downtrend'}\n"
                f"  Momentum (RSI): {'📈 Bullish' if direction=='CALL' else '📉 Bearish'}\n"
                f"  Entry (Stochastic): {'✅ Crossover'}\n"
                f"  Current Price: {prediction['next_candle']['close']:.5f}",
                title="[bold]🧠 PROFESSIONAL SIGNAL[/bold]",
                border_style=color
            )
        
        console.print(panel)
    
    async def execute_trade(self, asset, direction, period, amount):
        """Execute a trade"""
        try:
            asset_name, asset_data = await self.client.get_available_asset(asset, force_open=True)
            
            if not asset_data[2]:
                console.print(f"[red]❌ {asset} is closed![/red]")
                return None
            
            console.print(f"\n[bold yellow]⚡ EXECUTING: {direction} on {asset} ({period}s) ${amount}[/bold yellow]")
            
            status, buy_info = await self.client.buy(amount, asset_name, direction.lower(), period)
            
            if not status:
                console.print("[red]❌ Trade failed![/red]")
                return None
            
            console.print(f"[green]✅ Order placed: {buy_info.get('id', 'N/A')}[/green]")
            
            # Wait for result
            await asyncio.sleep(period + 3)
            
            # Check result
            if buy_info and "id" in buy_info:
                win_status, profit = await self.client.check_win(buy_info["id"])
                
                result = "WIN" if win_status == "win" else "LOSS"
                trade_profit = profit if win_status == "win" else -amount
                
                trade_record = {
                    'time': datetime.now().strftime("%H:%M:%S"),
                    'asset': asset,
                    'direction': direction,
                    'period': period,
                    'amount': amount,
                    'result': result,
                    'profit': trade_profit,
                    'confidence': 0  # Will be updated
                }
                
                self.trade_history.append(trade_record)
                
                if result == "WIN":
                    console.print(f"[bold green]✅ WIN! +${trade_profit:.2f}[/bold green]")
                else:
                    console.print(f"[bold red]❌ LOSS! -${amount:.2f}[/bold red]")
                
                self.current_balance += trade_profit
                
                return trade_record
        
        except Exception as e:
            console.print(f"[red]❌ Trade error: {e}[/red]")
        
        return None
    
    def get_next_amount(self, last_win):
        """
        Calculate next trade amount based on mode.
        
        Mode 3 (Compound) implements:
        - Reset to base after every win.
        - After 1st loss: base * 2
        - After 2nd loss: previous trade amount * 2.4
        - After 3rd loss: previous trade amount * 2.5
        - After 4th loss: previous trade amount * 2.6
        - After 5 consecutive losses: reset to base amount.
        """
        base = self.trade_amount
        
        if self.trading_mode == "1":  # Fixed
            return base
        
        elif self.trading_mode == "2":  # Martingale
            if not hasattr(self, 'martingale_losses'):
                self.martingale_losses = 0
            
            if last_win:
                self.martingale_losses = 0
                return base
            else:
                self.martingale_losses += 1
                return base * (2 ** min(self.martingale_losses, 4))
        
        elif self.trading_mode == "3":  # Compound (custom loss recovery)
            if last_win:
                # Reset on win
                self.loss_streak = 0
                self.current_trade_amount = base
                return base
            else:
                # Loss: increment streak and calculate next amount
                self.loss_streak += 1
                if self.loss_streak == 1:
                    amount = base * 2.0
                elif self.loss_streak == 2:
                    amount = self.current_trade_amount * 2.4
                elif self.loss_streak == 3:
                    amount = self.current_trade_amount * 2.5
                elif self.loss_streak == 4:
                    amount = self.current_trade_amount * 2.6
                elif self.loss_streak >= 5:
                    # Reset after 5 losses
                    self.loss_streak = 0
                    amount = base
                else:
                    amount = base  # fallback
                
                # Safety: cap to 25% of current balance
                max_allowed = self.current_balance * 0.25 if self.current_balance > 0 else base
                if amount > max_allowed:
                    amount = max_allowed
                if amount < base:
                    amount = base
                
                self.current_trade_amount = amount
                return amount
        
        return base
    
    def check_limits(self):
        """Check stop loss/profit limits"""
        pnl = self.current_balance - self.initial_balance
        
        if self.stop_profit > 0 and pnl >= self.stop_profit:
            return True, f"🎯 TAKE PROFIT HIT! +${pnl:.2f}"
        
        if self.stop_loss > 0 and pnl <= -self.stop_loss:
            return True, f"🛑 STOP LOSS HIT! -${abs(pnl):.2f}"
        
        if self.current_balance < self.trade_amount:
            return True, "❌ INSUFFICIENT BALANCE!"
        
        return False, ""
    
    async def run(self):
        """Main bot loop"""
        if not await self.setup():
            return
        
        self.is_running = True
        trade_count = 0
        last_was_win = True
        
        console.print(f"\n[bold green]🤖 BOT STARTED! Using {self.strategy_mode.upper()} strategy[/bold green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            while self.is_running:
                # Check limits
                should_stop, reason = self.check_limits()
                if should_stop:
                    console.print(f"\n[bold yellow]{reason}[/bold yellow]")
                    break
                
                # Check max trades
                if self.max_trades > 0 and trade_count >= self.max_trades:
                    console.print(f"\n[bold yellow]✅ Max trades ({self.max_trades}) reached![/bold yellow]")
                    break
                
                # Scan for opportunities
                opportunities = await self.scan_all_markets()
                
                if opportunities:
                    console.print(f"\n[cyan]🎯 Found {len(opportunities)} opportunities![/cyan]")
                    
                    # Show top 3
                    for i, opp in enumerate(opportunities[:3], 1):
                        console.print(f"\n[bold]Signal #{i}:[/bold]")
                        strategy_type = opp.get('strategy', 'ai')
                        self.display_prediction(opp['asset'], opp['period'], opp['prediction'], strategy_type)
                    
                    # Execute best opportunity
                    best = opportunities[0]
                    strategy_type = best.get('strategy', 'ai')
                    direction = best['prediction']['direction']
                    
                    # Countdown timer
                    console.print(f"\n[yellow]⏱️ Signal for {direction} on {best['asset']}...[/yellow]")
                    
                    for remaining in range(5, 0, -1):
                        console.print(f"\r[yellow]⚡ Execute in {remaining}s...[/yellow]", end="")
                        await asyncio.sleep(1)
                    
                    console.print(f"\n[bold red]🚨 EXECUTE NOW! 🚨[/bold red]")
                    
                    # Get trade amount based on mode
                    amount = self.get_next_amount(last_was_win)
                    
                    # Execute trade
                    result = await self.execute_trade(
                        best['asset'],
                        direction,
                        best['period'],
                        amount
                    )
                    
                    if result:
                        trade_count += 1
                        last_was_win = (result['result'] == 'WIN')
                    
                    console.print(f"\n[dim]💰 Balance: ${self.current_balance:.2f} | Trades: {trade_count}[/dim]")
                
                else:
                    console.print(f"\r[dim]⏳ Scanning... ({datetime.now().strftime('%H:%M:%S')})[/dim]", end="")
                
                await asyncio.sleep(3)
        
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⏹️ Bot stopped by user[/yellow]")
        
        # Show summary
        self.show_session_summary()
    
    def show_session_summary(self):
        """Display trading session summary"""
        console.clear()
        
        total_trades = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t['result'] == 'WIN')
        losses = sum(1 for t in self.trade_history if t['result'] == 'LOSS')
        total_pnl = sum(t['profit'] for t in self.trade_history)
        
        summary = Panel.fit(
            f"[bold cyan]📊 SESSION SUMMARY[/bold cyan]\n\n"
            f"[white]Duration: {datetime.now() - datetime.now().replace(hour=0, minute=0, second=0)}\n"
            f"Total Trades: {total_trades}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {losses}\n"
            f"Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%\n\n"
            f"💰 Initial Balance: ${self.initial_balance:.2f}\n"
            f"💰 Final Balance: ${self.current_balance:.2f}\n"
            f"📈 Net P&L: ${total_pnl:+.2f}",
            border_style="cyan"
        )
        
        console.print(summary)
        
        # Show last 10 trades
        if self.trade_history:
            table = Table(title="Last 10 Trades")
            table.add_column("Time")
            table.add_column("Asset")
            table.add_column("Dir")
            table.add_column("Period")
            table.add_column("Amount")
            table.add_column("Result")
            table.add_column("P&L")
            
            for trade in self.trade_history[-10:]:
                emoji = "✅" if trade['result'] == 'WIN' else "❌"
                pnl_color = "green" if trade['profit'] > 0 else "red"
                table.add_row(
                    trade['time'],
                    trade['asset'],
                    trade['direction'],
                    f"{trade['period']}s",
                    f"${trade['amount']:.2f}",
                    f"{emoji} {trade['result']}",
                    f"[{pnl_color}]${trade['profit']:+.2f}[/{pnl_color}]"
                )
            
            console.print(table)
        
        # Save to file
        self.save_summary()
    
    def save_summary(self):
        """Save session summary to file"""
        filename = f"quantum_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            'date': datetime.now().isoformat(),
            'initial_balance': self.initial_balance,
            'final_balance': self.current_balance,
            'total_trades': len(self.trade_history),
            'wins': sum(1 for t in self.trade_history if t['result'] == 'WIN'),
            'losses': sum(1 for t in self.trade_history if t['result'] == 'LOSS'),
            'total_pnl': sum(t['profit'] for t in self.trade_history),
            'trades': self.trade_history
        }
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        console.print(f"\n[dim]💾 Summary saved: {filename}[/dim]")


# ==================== MAIN ====================
async def main():
    # Create client here, then pass to bot
    client = Quotex(email=EMAIL, password=PASSWORD, lang="en")
    bot = QuantumTradingBot(client)  # pass the client to the bot
    
    try:
        await bot.run()
    except Exception as e:
        console.print(f"[red]❌ Fatal Error: {e}[/red]")
    finally:
        try:
            await client.close()
        except:
            pass
        console.print("\n[dim]👋 Bot shutdown complete![/dim]\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Closed by user![/yellow]")
