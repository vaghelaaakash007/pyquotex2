# quantum_quotex_bot_5sec.py
"""
QUANTUM QUOTEX BOT - 5 SECOND VERSION (ONLY OTC)
=================================================
- ONLY 5-SECOND CANDLES
- IMMEDIATE EXECUTION ON SIGNAL
- NO DUPLICATE TRADES PER CANDLE
- UTC+5:30 TIMEZONE
- ONLY OTC PAIRS (from screenshots)
- FIXED: time_mode="TIMER" for 5-second trades
"""

import os
import sys
import time
import asyncio
import json
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pyquotex.stable_api import Quotex
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# ==================== CONFIGURATION ====================
EMAIL = os.getenv("QUOTEX_EMAIL", "")
PASSWORD = os.getenv("QUOTEX_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("Enter Quotex credentials:")
    EMAIL = input("Email: ").strip()
    PASSWORD = input("Password: ").strip()

console = Console()
client = Quotex(email=EMAIL, password=PASSWORD, lang="en")

# ==================== TIMEZONE SETUP ====================
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

def get_india_time():
    return datetime.now(INDIA_TZ)

def get_timestamp_india():
    return int(get_india_time().timestamp())

def get_current_candle_start(period: int = 5) -> int:
    current_time = get_timestamp_india()
    return int(current_time / period) * period

# ==================== DATA STRUCTURES ====================
@dataclass
class PredictionResult:
    direction: str
    confidence: float
    next_candle: Dict[str, float]
    indicators: Dict[str, float]
    strategy_name: str = ""
    timestamp: float = field(default_factory=time.time)

# ==================== INDICATORS ====================
class AdvancedIndicators:
    @staticmethod
    def calculate_smma(series: List[float], n: int) -> List[float]:
        if len(series) < n:
            return []
        output = [sum(series[:n]) / n]
        for i in range(n, len(series)):
            temp = output[-1] * (n - 1) + series[i]
            output.append(temp / n)
        return output
    
    @staticmethod
    def calculate_rsi_smma(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up = [d if d > 0 else 0 for d in deltas]
        down = [-d if d < 0 else 0 for d in deltas]
        smma_up = AdvancedIndicators.calculate_smma(up, period)
        smma_down = AdvancedIndicators.calculate_smma(down, period)
        if not smma_up or not smma_down:
            return 50.0
        rs = smma_up[-1] / smma_down[-1] if smma_down[-1] != 0 else 100.0
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        if len(closes) < period:
            return None, None, None
        ma = sum(closes[-period:]) / period
        variance = sum((x - ma) ** 2 for x in closes[-period:]) / period
        std = variance ** 0.5
        upper = ma + (std_dev * std)
        lower = ma - (std_dev * std)
        return ma, upper, lower
    
    @staticmethod
    def calculate_atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        if len(high) < period + 1:
            return []
        tr = []
        for i in range(1, len(high)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr.append(max(hl, hc, lc))
        atr = [sum(tr[:period]) / period]
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        return atr

# ==================== PREDICTION ENGINE ====================
class QuantumPredictionEngine:
    def __init__(self):
        self.indicators = AdvancedIndicators()
        self.total_predictions = 0
        
        self.strategies = {
            'ema_rsi': self._strategy_ema_rsi,
            'bollinger_reversal': self._strategy_bollinger_reversal,
            'breakout': self._strategy_breakout,
        }
        
        self.active_strategies = ['ema_rsi', 'bollinger_reversal', 'breakout']
    
    def set_strategies(self, strategy_names: List[str]):
        valid_strategies = [s for s in strategy_names if s in self.strategies]
        if valid_strategies:
            self.active_strategies = valid_strategies
        return self.active_strategies
    
    def _strategy_ema_rsi(self, candles: List[Dict]) -> Optional[PredictionResult]:
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        ema = self._calculate_ema(closes, 10)
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        
        if ema is None:
            return None
        
        direction = None
        confidence = 0
        
        if current_price > ema and 40 < rsi < 70:
            direction = "CALL"
            confidence = 78
        elif current_price > ema and rsi < 30:
            direction = "CALL"
            confidence = 82
        elif current_price < ema and 30 < rsi < 60:
            direction = "PUT"
            confidence = 78
        elif current_price < ema and rsi > 70:
            direction = "PUT"
            confidence = 82
        
        if not direction:
            return None
        
        atr = self._calculate_atr(candles)
        predicted_move = atr * 0.5 if atr else (current_price * 0.001)
        
        if direction == "CALL":
            predicted_close = current_price + predicted_move
        else:
            predicted_close = current_price - predicted_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + predicted_move * 1.2,
                'low': current_price - predicted_move * 0.5,
                'close': predicted_close,
            },
            indicators={'ema': ema, 'rsi': rsi},
            strategy_name="EMA_RSI"
        )
    
    def _strategy_bollinger_reversal(self, candles: List[Dict]) -> Optional[PredictionResult]:
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        ma, upper, lower = self.indicators.calculate_bollinger(closes)
        
        if ma is None:
            return None
        
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        current_candle = candles[-1]
        
        direction = None
        confidence = 0
        
        if current_price < lower * 1.003:
            if current_candle['close'] > current_candle['open']:
                direction = "CALL"
                confidence = 82
            elif rsi < 30:
                direction = "CALL"
                confidence = 75
            else:
                direction = "CALL"
                confidence = 68
        elif current_price > upper * 0.997:
            if current_candle['close'] < current_candle['open']:
                direction = "PUT"
                confidence = 82
            elif rsi > 70:
                direction = "PUT"
                confidence = 75
            else:
                direction = "PUT"
                confidence = 68
        
        if not direction:
            return None
        
        predicted_move = (upper - lower) * 0.3 if upper and lower else (current_price * 0.001)
        
        if direction == "CALL":
            predicted_close = current_price + predicted_move
        else:
            predicted_close = current_price - predicted_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + predicted_move * 1.3,
                'low': current_price - predicted_move * 0.4,
                'close': predicted_close,
            },
            indicators={'ma': ma, 'upper': upper, 'lower': lower, 'rsi': rsi},
            strategy_name="Bollinger Reversal"
        )
    
    def _strategy_breakout(self, candles: List[Dict]) -> Optional[PredictionResult]:
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        current_price = closes[-1]
        
        high_20 = max(highs[-20:])
        low_20 = min(lows[-20:])
        range_20 = high_20 - low_20
        
        ma, upper, lower = self.indicators.calculate_bollinger(closes)
        
        direction = None
        confidence = 0
        
        if current_price > high_20 * 0.998:
            if candles[-1]['close'] < candles[-1]['open']:
                direction = "PUT"
                confidence = 80
            else:
                direction = "PUT"
                confidence = 70
        elif current_price < low_20 * 1.002:
            if candles[-1]['close'] > candles[-1]['open']:
                direction = "CALL"
                confidence = 80
            else:
                direction = "CALL"
                confidence = 70
        elif ma and upper and current_price > upper * 0.995:
            direction = "PUT"
            confidence = 72
        elif ma and lower and current_price < lower * 1.005:
            direction = "CALL"
            confidence = 72
        
        if not direction:
            return None
        
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        if direction == "CALL" and rsi > 75:
            confidence -= 10
        elif direction == "PUT" and rsi < 25:
            confidence -= 10
        
        predicted_move = range_20 * 0.3 if range_20 else (current_price * 0.001)
        
        if direction == "CALL":
            predicted_close = current_price + predicted_move
        else:
            predicted_close = current_price - predicted_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + predicted_move * 1.3,
                'low': current_price - predicted_move * 0.4,
                'close': predicted_close,
            },
            indicators={'upper': upper, 'lower': lower, 'rsi': rsi},
            strategy_name="Breakout"
        )
    
    def _calculate_ema(self, closes: List[float], period: int) -> float:
        if len(closes) < period:
            return None
        alpha = 2 / (period + 1)
        ema_val = sum(closes[:period]) / period
        for price in closes[period:]:
            ema_val = price * alpha + ema_val * (1 - alpha)
        return ema_val
    
    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0
        tr = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            hl = high - low
            hc = abs(high - prev_close)
            lc = abs(low - prev_close)
            tr.append(max(hl, hc, lc))
        if not tr:
            return 0
        atr = sum(tr[-period:]) / period
        return atr
    
    def predict(self, candles: List[Dict]) -> Optional[PredictionResult]:
        if not candles or len(candles) < 20:
            return None
        
        best_prediction = None
        best_confidence = 0
        
        strategies = self.active_strategies.copy()
        random.shuffle(strategies)
        
        for strategy_name in strategies:
            if strategy_name in self.strategies:
                try:
                    prediction = self.strategies[strategy_name](candles)
                    if prediction and prediction.confidence > best_confidence:
                        best_prediction = prediction
                        best_confidence = prediction.confidence
                except Exception as e:
                    pass
        
        if best_prediction:
            self.total_predictions += 1
        
        return best_prediction
    
    def get_signal_strength(self, prediction: Optional[PredictionResult]) -> Tuple[str, str]:
        if not prediction:
            return "WEAK", "gray"
        confidence = prediction.confidence
        if confidence >= 90:
            return "QUANTUM", "bright_magenta"
        elif confidence >= 85:
            return "ULTRA STRONG", "bright_green"
        elif confidence >= 78:
            return "STRONG", "green"
        elif confidence >= 72:
            return "MODERATE", "yellow"
        elif confidence >= 65:
            return "WEAK", "red"
        else:
            return "VERY WEAK", "dim red"

# ==================== VISUALIZER ====================
class NextCandleVisualizer:
    def __init__(self):
        self.prediction_history = []
        self.max_history = 10
    
    def display_prediction(self, asset: str, period: int, prediction: PredictionResult):
        console.clear()
        header = Panel(
            "[bold magenta]🔮 5-SECOND QUANTUM PREDICTION[/bold magenta]",
            border_style="magenta"
        )
        console.print(header)
        
        nc = prediction.next_candle
        direction = prediction.direction
        confidence = prediction.confidence
        strength, color = QuantumPredictionEngine().get_signal_strength(prediction)
        
        arrow = "↗ BULLISH ↗" if direction == "CALL" else "↘ BEARISH ↘"
        arrow_color = "green" if direction == "CALL" else "red"
        
        india_time = get_india_time().strftime("%H:%M:%S")
        
        main_content = f"""
[bold yellow]⚡ CURRENT PRICE: {prediction.next_candle['open']:.5f}[/bold yellow]

[bold {arrow_color}]{arrow}[/bold {arrow_color}]

[bold cyan]OHLC:[/bold cyan]
  [green]O: {nc['open']:.5f}[/green]    [bright_cyan]H: {nc['high']:.5f}[/bright_cyan]
  [yellow]L: {nc['low']:.5f}[/yellow]    [magenta]C: {nc['close']:.5f}[/magenta]

[bold {color}]{confidence:.0f}% - {strength}[/bold {color}]
[dim]Strategy: {prediction.strategy_name}[/dim]
[dim]🕐 IST: {india_time}[/dim]
"""
        
        main_panel = Panel(
            main_content,
            title=f"[bold]{asset} | {period}s[/bold]",
            border_style=color,
            padding=(1, 2)
        )
        console.print(main_panel)
        
        self.prediction_history.append({
            'time': india_time,
            'asset': asset,
            'direction': direction,
            'confidence': confidence,
            'strategy': prediction.strategy_name
        })
        if len(self.prediction_history) > self.max_history:
            self.prediction_history.pop(0)
    
    def show_prediction_history(self):
        if not self.prediction_history:
            return
        table = Table(title="📊 Recent Predictions", style="dim")
        table.add_column("Time (IST)", style="cyan")
        table.add_column("Asset", style="white")
        table.add_column("Direction", style="yellow")
        table.add_column("Confidence", style="magenta")
        table.add_column("Strategy", style="green")
        for pred in self.prediction_history[-5:]:
            dir_color = "green" if pred['direction'] == "CALL" else "red"
            table.add_row(
                pred['time'],
                pred['asset'],
                f"[{dir_color}]{pred['direction']}[/{dir_color}]",
                f"{pred['confidence']:.0f}%",
                pred['strategy']
            )
        console.print(table)

# ==================== MAIN BOT ====================
class QuantumTradingBot5Sec:
    def __init__(self):
        self.engine = QuantumPredictionEngine()
        self.visualizer = NextCandleVisualizer()
        self.trade_history = []
        self.current_balance = 0
        self.initial_balance = 0
        self.is_running = False
        
        self.trade_amount = 2
        self.min_confidence = 72
        self.max_trades = 0
        self.stop_loss = 0
        self.stop_profit = 0
        self.trading_mode = "1"
        
        self.selected_strategies = ['ema_rsi', 'bollinger_reversal', 'breakout']
        
        # ✅ ONLY OTC PAIRS (from screenshots)
        self.markets = {
            # ===== FOREX OTC (from screenshots) =====
            "GBPNZD_otc": [5],
            "NZDCAD_otc": [5],
            "NZDCHF_otc": [5],
            "NZDJPY_otc": [5],
            "NZDUSD_otc": [5],
            "USDARS_otc": [5],
            "USDBDT_otc": [5],
            "USDBRL_otc": [5],
            "USDCOP_otc": [5],
            "USDDZD_otc": [5],
            "USDEGP_otc": [5],
            "USDIDR_otc": [5],
            "USDINR_otc": [5],
            "USDMXN_otc": [5],
            "USDNGN_otc": [5],
            "USDPHP_otc": [5],
            "USDPKR_otc": [5],
            "USDZAR_otc": [5],
        }
        
        self.last_trade_candle = {}
        self.signal_count = 0
        self.scan_count = 0
    
    def _get_candle_key(self, asset: str, period: int) -> str:
        current_time = get_timestamp_india()
        candle_start = int(current_time / period) * period
        return f"{asset}_{period}_{candle_start}"
    
    def _is_trade_already_taken(self, asset: str, period: int) -> bool:
        key = self._get_candle_key(asset, period)
        return key in self.last_trade_candle
    
    def _mark_trade_taken(self, asset: str, period: int):
        key = self._get_candle_key(asset, period)
        self.last_trade_candle[key] = datetime.now(INDIA_TZ).isoformat()
        if len(self.last_trade_candle) > 100:
            keys = list(self.last_trade_candle.keys())
            for k in keys[:-100]:
                del self.last_trade_candle[k]
    
    def _get_trend(self, candles: List[Dict]) -> str:
        closes = [c['close'] for c in candles]
        if len(closes) < 20:
            return "NEUTRAL"
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        bullish = 0
        bearish = 0
        if ma5 > ma10: bullish += 1
        else: bearish += 1
        if ma10 > ma20: bullish += 1
        else: bearish += 1
        current = closes[-1]
        if current > ma5: bullish += 1
        else: bearish += 1
        if current > ma20: bullish += 1
        else: bearish += 1
        if bullish >= 3:
            return "BULLISH"
        elif bearish >= 3:
            return "BEARISH"
        return "NEUTRAL"
    
    def _should_skip_trade(self, prediction: PredictionResult, consecutive_losses: int) -> bool:
        if prediction.confidence < self.min_confidence:
            return True
        if consecutive_losses >= 2 and prediction.confidence < 78:
            return True
        if consecutive_losses >= 3 and prediction.confidence < 82:
            return True
        strength, _ = self.engine.get_signal_strength(prediction)
        if strength in ["WEAK", "VERY WEAK"]:
            return True
        return False
    
    async def setup(self):
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]🚀 5-SECOND QUANTUM BOT (ONLY OTC)[/bold cyan]\n"
            "[white]ONLY 5-SECOND CANDLES | IMMEDIATE EXECUTION[/white]\n"
            "[white]UTC+5:30 (India Time) | ONLY OTC PAIRS[/white]\n"
            "[green]✅ FIXED: time_mode='TIMER' for 5s trades[/green]\n"
            "[dim]📊 Total OTC Pairs: 18 (from screenshots)[/dim]",
            border_style="cyan"
        ))
        
        console.print("\n[cyan]🔗 Connecting to Quotex...[/cyan]")
        check, msg = await client.connect()
        if not check:
            console.print(f"[red]❌ Connection failed: {msg}[/red]")
            return False
        
        console.print("\n[bold]Select Account:[/bold]")
        console.print("1. 💵 REAL")
        console.print("2. 🎮 PRACTICE (Demo)")
        choice = input("\n👉 Choose (1/2): ").strip()
        account_type = "REAL" if choice == "1" else "PRACTICE"
        
        await client.change_account(account_type)
        await asyncio.sleep(1)
        
        self.current_balance = await client.get_balance()
        self.initial_balance = self.current_balance
        
        console.print(f"\n[green]💰 Balance: ${self.current_balance:.2f}[/green]")
        
        await self._select_strategies()
        await self._set_trading_parameters()
        
        return True
    
    async def _select_strategies(self):
        console.print("\n[bold magenta]🎯 STRATEGY SELECTION[/bold magenta]")
        console.print("\n[dim]Available Strategies:[/dim]")
        console.print("  1. EMA_RSI - Most Reliable ⭐")
        console.print("  2. Bollinger Reversal")
        console.print("  3. Breakout")
        console.print("  4. All")
        console.print("  5. Best (Recommended)")
        
        choice = input("\n👉 Your choice (1-5): ").strip()
        
        if choice == "1":
            self.selected_strategies = ['ema_rsi']
        elif choice == "2":
            self.selected_strategies = ['bollinger_reversal']
        elif choice == "3":
            self.selected_strategies = ['breakout']
        elif choice == "4":
            self.selected_strategies = ['ema_rsi', 'bollinger_reversal', 'breakout']
        else:
            self.selected_strategies = ['ema_rsi', 'bollinger_reversal', 'breakout']
        
        self.engine.set_strategies(self.selected_strategies)
        console.print(f"\n[green]✅ Selected: {', '.join(self.selected_strategies)}[/green]")
    
    async def _set_trading_parameters(self):
        console.print("\n[bold yellow]⚙️ TRADING PARAMETERS[/bold yellow]")
        self.trade_amount = float(input("💰 Trade Amount ($): ") or "2")
        self.min_confidence = float(input("🎯 Min Confidence % (72-95): ") or "72")
        max_t = input("🔄 Max Trades (0=unlimited): ")
        self.max_trades = int(max_t) if max_t else 0
        self.stop_loss = float(input("🛑 Stop Loss $ (0=off): ") or "0")
        self.stop_profit = float(input("🎯 Take Profit $ (0=off): ") or "0")
        console.print("\n[bold]Trading Mode:[/bold]")
        console.print("1. 📊 Fixed Amount")
        console.print("2. 🔄 Martingale")
        console.print("3. 📈 Compounding")
        self.trading_mode = input("👉 Choose (1/2/3): ").strip() or "1"
    
    async def _get_candles(self, asset: str, period: int, count: int) -> List[Dict]:
        try:
            candles = await client.get_candles(asset, None, period * count, period)
            if not candles:
                return []
            
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
                    })
            return formatted
        except Exception as e:
            return []
    
    async def scan_all_markets(self) -> List[Dict]:
        opportunities = []
        self.scan_count += 1
        
        for asset, timeframes in self.markets.items():
            for period in timeframes:
                candles = await self._get_candles(asset, period, 100)
                
                if not candles or len(candles) < 30:
                    continue
                
                # ✅ Check if already traded this candle
                if self._is_trade_already_taken(asset, period):
                    continue
                
                trend = self._get_trend(candles)
                prediction = self.engine.predict(candles)
                
                if prediction:
                    self.signal_count += 1
                    
                    if trend == "BULLISH" and prediction.direction == "CALL":
                        prediction.confidence = min(95, prediction.confidence + 5)
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif trend == "BEARISH" and prediction.direction == "PUT":
                        prediction.confidence = min(95, prediction.confidence + 5)
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif trend == "NEUTRAL":
                        if prediction.confidence >= 72:
                            opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif prediction.confidence >= 82:
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend + " (Counter)"})
        
        opportunities.sort(key=lambda x: x['prediction'].confidence, reverse=True)
        return opportunities
    
    async def execute_trade(self, asset: str, direction: str, period: int, amount: float) -> Optional[Dict]:
        try:
            # ✅ Double check - not already taken
            if self._is_trade_already_taken(asset, period):
                return None
            
            asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
            if not asset_data[2]:
                console.print(f"[red]❌ {asset} is closed![/red]")
                return None
            
            console.print(f"\n[bold yellow]⚡ EXECUTING: {direction} on {asset} (5s) ${amount:.2f}[/bold yellow]")
            
            # ✅ FIX: time_mode="TIMER" for 5-second trades
            status, buy_info = await client.buy(
                amount, 
                asset_name, 
                direction.lower(), 
                period, 
                time_mode="TIMER"  # ⬅️ FIXED: Added time_mode parameter
            )
            
            if not status:
                console.print("[red]❌ Trade failed![/red]")
                console.print(f"[red]Error: {buy_info}[/red]")
                return None
            
            console.print(f"[green]✅ Order placed: {buy_info.get('id', 'N/A')}[/green]")
            
            # ✅ Mark trade taken
            self._mark_trade_taken(asset, period)
            
            # ✅ Wait for result (5s + 3s buffer)
            await asyncio.sleep(period + 3)
            
            if buy_info and "id" in buy_info:
                win_status, profit = await client.check_win(buy_info["id"])
                result = "WIN" if win_status == "win" else "LOSS"
                trade_profit = profit if win_status == "win" else -amount
                
                trade_record = {
                    'time': datetime.now(INDIA_TZ).strftime("%H:%M:%S"),
                    'asset': asset,
                    'direction': direction,
                    'period': period,
                    'amount': amount,
                    'result': result,
                    'profit': trade_profit
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
            import traceback
            traceback.print_exc()
        
        return None
    
    def get_next_amount(self, last_win: bool) -> float:
        base = self.trade_amount
        if self.trading_mode == "1":
            return base
        elif self.trading_mode == "2":
            if not hasattr(self, 'martingale_losses'):
                self.martingale_losses = 0
            if last_win:
                self.martingale_losses = 0
                return base
            else:
                self.martingale_losses += 1
                return base * (2 ** min(self.martingale_losses, 4))
        elif self.trading_mode == "3":
            if not hasattr(self, 'compound_wins'):
                self.compound_wins = 0
            if last_win:
                self.compound_wins += 1
                if self.compound_wins >= 3:
                    self.compound_wins = 0
                    return base
                return min(base * (1.5 ** self.compound_wins), self.current_balance * 0.25)
            else:
                self.compound_wins = 0
                return base
        return base
    
    def check_limits(self) -> Tuple[bool, str]:
        pnl = self.current_balance - self.initial_balance
        if self.stop_profit > 0 and pnl >= self.stop_profit:
            return True, f"🎯 TAKE PROFIT HIT! +${pnl:.2f}"
        if self.stop_loss > 0 and pnl <= -self.stop_loss:
            return True, f"🛑 STOP LOSS HIT! -${abs(pnl):.2f}"
        if self.current_balance < self.trade_amount:
            return True, "❌ INSUFFICIENT BALANCE!"
        return False, ""
    
    async def run(self):
        if not await self.setup():
            return
        
        self.is_running = True
        trade_count = 0
        last_was_win = True
        consecutive_wins = 0
        consecutive_losses = 0
        
        console.print("\n[bold green]🤖 5-SECOND BOT STARTED![/bold green]")
        console.print(f"[dim]Active Strategies: {', '.join(self.selected_strategies)}[/dim]")
        console.print(f"[dim]Min Confidence: {self.min_confidence}%[/dim]")
        console.print(f"[dim]OTC Pairs: {len(self.markets)} pairs[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            while self.is_running:
                should_stop, reason = self.check_limits()
                if should_stop:
                    console.print(f"\n[bold yellow]{reason}[/bold yellow]")
                    break
                if self.max_trades > 0 and trade_count >= self.max_trades:
                    console.print(f"\n[bold yellow]✅ Max trades reached![/bold yellow]")
                    break
                
                opportunities = await self.scan_all_markets()
                
                if not opportunities:
                    console.print(f"\r[dim]⏳ Scanning 5s... ({get_india_time().strftime('%H:%M:%S')}) | Signals: {self.signal_count} | Scans: {self.scan_count}[/dim]", end="")
                    await asyncio.sleep(1)
                    continue
                
                best = opportunities[0]
                
                if self._is_trade_already_taken(best['asset'], best['period']):
                    await asyncio.sleep(1)
                    continue
                
                if self._should_skip_trade(best['prediction'], consecutive_losses):
                    console.print(f"\n[yellow]⏳ Skipping - need higher confidence[/yellow]")
                    await asyncio.sleep(2)
                    continue
                
                # ✅ Show prediction
                self.visualizer.display_prediction(best['asset'], best['period'], best['prediction'])
                console.print(f"[dim]Trend: {best['trend']} | Confidence: {best['prediction'].confidence:.0f}%[/dim]")
                self.visualizer.show_prediction_history()
                
                # ✅ IMMEDIATE EXECUTION - No countdown!
                console.print(f"\n[bold red]🚨 EXECUTE NOW! 🚨[/bold red]")
                
                amount = self.get_next_amount(last_was_win)
                if best['prediction'].confidence >= 85:
                    amount = min(amount * 1.5, self.current_balance * 0.1)
                
                result = await self.execute_trade(best['asset'], best['prediction'].direction, best['period'], amount)
                
                if result:
                    trade_count += 1
                    last_was_win = result['result'] == 'WIN'
                    if last_was_win:
                        consecutive_wins += 1
                        consecutive_losses = 0
                    else:
                        consecutive_losses += 1
                        consecutive_wins = 0
                    await asyncio.sleep(3 if last_was_win else 5)
                
                console.print(f"\n[dim]💰 Balance: ${self.current_balance:.2f} | Trades: {trade_count} | Streak: {'W'*consecutive_wins}{'L'*consecutive_losses}[/dim]")
        
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⏹️ Bot stopped by user[/yellow]")
        
        self._show_session_summary()
    
    def _show_session_summary(self):
        console.clear()
        total_trades = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t['result'] == 'WIN')
        losses = sum(1 for t in self.trade_history if t['result'] == 'LOSS')
        total_pnl = sum(t['profit'] for t in self.trade_history)
        win_rate = (wins/total_trades*100) if total_trades > 0 else 0
        
        summary = Panel.fit(
            f"[bold cyan]📊 5-SECOND SESSION SUMMARY[/bold cyan]\n\n"
            f"[white]Strategies: {', '.join(self.selected_strategies)}\n"
            f"Total Trades: {total_trades}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {losses}\n"
            f"📈 Win Rate: {win_rate:.1f}%\n\n"
            f"💰 Initial: ${self.initial_balance:.2f}\n"
            f"💰 Final: ${self.current_balance:.2f}\n"
            f"📊 P&L: ${total_pnl:+.2f}",
            border_style="cyan"
        )
        console.print(summary)
        if win_rate >= 60:
            console.print("[bold green]✅ Excellent![/bold green]")
        elif win_rate >= 55:
            console.print("[bold yellow]⚠️ Decent[/bold yellow]")
        else:
            console.print("[bold red]❌ Needs optimization[/bold red]")
        
        self._save_summary()
    
    def _save_summary(self):
        filename = f"5sec_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            'date': datetime.now(INDIA_TZ).isoformat(),
            'timezone': 'UTC+5:30',
            'strategies': self.selected_strategies,
            'initial_balance': self.initial_balance,
            'final_balance': self.current_balance,
            'total_trades': len(self.trade_history),
            'wins': sum(1 for t in self.trade_history if t['result'] == 'WIN'),
            'losses': sum(1 for t in self.trade_history if t['result'] == 'LOSS'),
            'win_rate': (sum(1 for t in self.trade_history if t['result'] == 'WIN') / len(self.trade_history) * 100) if self.trade_history else 0,
            'total_pnl': sum(t['profit'] for t in self.trade_history),
            'trades': self.trade_history
        }
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        console.print(f"\n[dim]💾 Summary saved: {filename}[/dim]")

async def main():
    bot = QuantumTradingBot5Sec()
    try:
        await bot.run()
    except Exception as e:
        console.print(f"[red]❌ Fatal Error: {e}[/red]")
        import traceback
        traceback.print_exc()
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
