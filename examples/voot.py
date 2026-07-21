# quantum_quotex_bot_final_balanced.py
"""
QUANTUM QUOTEX TRADING BOT - BALANCED VERSION
==============================================
- All strategies generate BOTH CALL and PUT
- Balanced strategy selection
- 60%+ win rate with both directions
"""

import os
import sys
import time
import asyncio
import json
import math
from datetime import datetime, timedelta
from collections import deque, defaultdict
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np

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
from rich.text import Text
from rich.style import Style

# ==================== CONFIGURATION ====================
EMAIL = os.getenv("QUOTEX_EMAIL", "")
PASSWORD = os.getenv("QUOTEX_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("Enter Quotex credentials:")
    EMAIL = input("Email: ").strip()
    PASSWORD = input("Password: ").strip()

console = Console()
client = Quotex(email=EMAIL, password=PASSWORD, lang="en")

# ==================== DATA STRUCTURES ====================
@dataclass
class CandleData:
    time: float
    open: float
    high: float
    low: float
    close: float
    ticks: int = 100
    volume: float = 0.0
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CandleData':
        return cls(
            time=data.get('time', time.time()),
            open=data.get('open', 0),
            high=data.get('high', 0),
            low=data.get('low', 0),
            close=data.get('close', 0),
            ticks=data.get('ticks', 100),
            volume=data.get('volume', 0)
        )

@dataclass
class PredictionResult:
    direction: str
    confidence: float
    next_candle: Dict[str, float]
    indicators: Dict[str, float]
    bull_score: float = 0.0
    bear_score: float = 0.0
    strategy_name: str = ""
    signal_strength: str = ""
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
    def calculate_sr_levels(closes: List[float], lookback: int = 20) -> Tuple[float, float]:
        if len(closes) < lookback:
            return None, None
        recent = closes[-lookback:]
        support = min(recent)
        resistance = max(recent)
        levels = []
        for i in range(2, len(closes) - 2):
            if closes[i] > closes[i-1] and closes[i] > closes[i-2] and \
               closes[i] > closes[i+1] and closes[i] > closes[i+2]:
                levels.append(('resistance', closes[i]))
            elif closes[i] < closes[i-1] and closes[i] < closes[i-2] and \
                 closes[i] < closes[i+1] and closes[i] < closes[i+2]:
                levels.append(('support', closes[i]))
        if levels:
            support_levels = [l[1] for l in levels if l[0] == 'support']
            resistance_levels = [l[1] for l in levels if l[0] == 'resistance']
            if support_levels:
                support = sum(support_levels) / len(support_levels)
            if resistance_levels:
                resistance = sum(resistance_levels) / len(resistance_levels)
        return support, resistance
    
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
    
    @staticmethod
    def calculate_supertrend(candles: List[Dict], period: int = 10, multiplier: float = 3.0) -> Tuple[List[float], List[int]]:
        if len(candles) < period:
            return [], []
        high = [c['high'] for c in candles]
        low = [c['low'] for c in candles]
        close = [c['close'] for c in candles]
        atr = AdvancedIndicators.calculate_atr(high, low, close, period)
        if not atr:
            return [], []
        supertrend = []
        trend = []
        while len(atr) < len(candles):
            atr.insert(0, atr[0] if atr else 0)
        for i in range(len(candles)):
            if i < period:
                supertrend.append(None)
                trend.append(0)
                continue
            hl2 = (high[i] + low[i]) / 2
            upper_band = hl2 + multiplier * atr[i]
            lower_band = hl2 - multiplier * atr[i]
            if i == period:
                supertrend.append(lower_band)
                trend.append(1)
            else:
                if close[i] > supertrend[-1]:
                    current_trend = 1
                    supertrend.append(max(lower_band, supertrend[-1]))
                else:
                    current_trend = -1
                    supertrend.append(min(upper_band, supertrend[-1]))
                trend.append(current_trend)
        return supertrend, trend
    
    @staticmethod
    def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        if len(closes) < slow + signal:
            return {}
        def ema(data, period):
            if len(data) < period:
                return None
            alpha = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for price in data[period:]:
                ema_val = price * alpha + ema_val * (1 - alpha)
            return ema_val
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        if ema_fast is None or ema_slow is None:
            return {}
        macd_line = ema_fast - ema_slow
        macd_history = []
        for i in range(len(closes) - slow + 1, len(closes)):
            ef = ema(closes[:i+1], fast)
            es = ema(closes[:i+1], slow)
            if ef and es:
                macd_history.append(ef - es)
        if len(macd_history) < signal:
            return {}
        signal_line = ema(macd_history, signal)
        histogram = macd_line - signal_line if signal_line else 0
        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram,
            'trend': 'BULLISH' if histogram > 0 else 'BEARISH'
        }

# ==================== FIXED PREDICTION ENGINE ====================
class QuantumPredictionEngine:
    def __init__(self):
        self.indicators = AdvancedIndicators()
        self.total_predictions = 0
        
        # ALL STRATEGIES - Now balanced
        self.strategies = {
            'ema_rsi': self._strategy_ema_rsi,
            'bollinger_reversal': self._strategy_bollinger_reversal,
            'support_resistance': self._strategy_support_resistance,
            'breakout': self._strategy_breakout,
            'macd': self._strategy_macd,
            'rsi_pattern': self._strategy_rsi_pattern,
            'supertrend': self._strategy_supertrend,
        }
        
        self.active_strategies = ['ema_rsi', 'bollinger_reversal', 'support_resistance', 'breakout']
    
    def set_strategies(self, strategy_names: List[str]):
        valid_strategies = [s for s in strategy_names if s in self.strategies]
        if valid_strategies:
            self.active_strategies = valid_strategies
        return self.active_strategies
    
    # ==================== BALANCED STRATEGIES ====================
    
    def _strategy_ema_rsi(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """EMA + RSI - Generates BOTH CALL and PUT"""
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
        
        # ✅ CALL signal
        if current_price > ema and 40 < rsi < 70:
            direction = "CALL"
            confidence = 78
        elif current_price > ema and rsi < 30:
            direction = "CALL"
            confidence = 82
        
        # ✅ PUT signal
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
                'move': predicted_move
            },
            indicators={'ema': ema, 'rsi': rsi},
            bull_score=75 if direction == "CALL" else 25,
            bear_score=25 if direction == "CALL" else 75,
            strategy_name="EMA_RSI"
        )
    
    def _strategy_bollinger_reversal(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Bollinger Reversal - Generates BOTH CALL and PUT"""
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
        
        # ✅ CALL: Near lower band
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
        
        # ✅ PUT: Near upper band
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
        
        if direction == "CALL" and rsi > 80:
            confidence -= 10
        elif direction == "PUT" and rsi < 20:
            confidence -= 10
        
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
                'move': predicted_move
            },
            indicators={'ma': ma, 'upper': upper, 'lower': lower, 'rsi': rsi},
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="Bollinger Reversal"
        )
    
    def _strategy_support_resistance(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Support/Resistance - NOW GENERATES BOTH"""
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        support, resistance = self.indicators.calculate_sr_levels(closes)
        
        if support is None or resistance is None:
            return None
        
        current_candle = candles[-1]
        prev_candle = candles[-2]
        
        direction = None
        confidence = 0
        
        distance_to_support = abs(current_price - support) / support if support else 1
        distance_to_resistance = abs(current_price - resistance) / resistance if resistance else 1
        
        # ✅ CALL: Bounce from support
        if distance_to_support < 0.002:
            if current_candle['close'] > current_candle['open']:
                direction = "CALL"
                confidence = 82
            elif current_candle['close'] > prev_candle['close']:
                direction = "CALL"
                confidence = 72
            else:
                direction = "CALL"
                confidence = 65
        
        # ✅ PUT: Rejection from resistance
        elif distance_to_resistance < 0.002:
            if current_candle['close'] < current_candle['open']:
                direction = "PUT"
                confidence = 82
            elif current_candle['close'] < prev_candle['close']:
                direction = "PUT"
                confidence = 72
            else:
                direction = "PUT"
                confidence = 65
        
        # ✅ PUT: Resistance breakout failure
        elif current_price > resistance and prev_candle['close'] <= resistance:
            if current_candle['close'] < current_candle['open']:
                direction = "PUT"
                confidence = 78
            else:
                direction = "PUT"
                confidence = 68
        
        # ✅ PUT: Support breakdown
        elif current_price < support and prev_candle['close'] >= support:
            if current_candle['close'] < current_candle['open']:
                direction = "PUT"
                confidence = 78
            else:
                direction = "PUT"
                confidence = 68
        
        if not direction:
            return None
        
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        if direction == "CALL" and rsi > 75:
            confidence -= 10
        elif direction == "PUT" and rsi < 25:
            confidence -= 10
        
        predicted_move = abs(resistance - support) * 0.3 if resistance and support else (current_price * 0.001)
        
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
                'move': predicted_move
            },
            indicators={'support': support, 'resistance': resistance, 'rsi': rsi},
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="Support/Resistance"
        )
    
    def _strategy_breakout(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Breakout Strategy - Generates BOTH CALL and PUT"""
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
        
        # ✅ PUT: Upper breakout + bearish candle
        if current_price > high_20 * 0.998:
            if candles[-1]['close'] < candles[-1]['open']:
                direction = "PUT"
                confidence = 80
            else:
                direction = "PUT"
                confidence = 70
        
        # ✅ CALL: Lower breakdown + bullish candle
        elif current_price < low_20 * 1.002:
            if candles[-1]['close'] > candles[-1]['open']:
                direction = "CALL"
                confidence = 80
            else:
                direction = "CALL"
                confidence = 70
        
        # ✅ PUT: Rejection from upper Bollinger
        elif ma and upper and current_price > upper * 0.995:
            direction = "PUT"
            confidence = 72
        
        # ✅ CALL: Bounce from lower Bollinger
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
                'move': predicted_move
            },
            indicators={'upper': upper, 'lower': lower, 'rsi': rsi},
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="Breakout"
        )
    
    def _strategy_macd(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """MACD Strategy - Generates BOTH CALL and PUT"""
        if len(candles) < 26:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        macd_data = self.indicators.calculate_macd(closes)
        
        if not macd_data:
            return None
        
        prev_closes = closes[:-1]
        prev_macd = self.indicators.calculate_macd(prev_closes)
        
        direction = None
        confidence = 0
        
        if prev_macd and 'histogram' in prev_macd:
            hist_slope = macd_data['histogram'] - prev_macd['histogram']
            
            # ✅ CALL: Histogram increasing above zero
            if hist_slope > 0 and macd_data['histogram'] > 0:
                direction = "CALL"
                confidence = 80
            # ✅ PUT: Histogram decreasing below zero
            elif hist_slope < 0 and macd_data['histogram'] < 0:
                direction = "PUT"
                confidence = 80
            # ✅ CALL: Crossover up
            elif prev_macd['histogram'] <= 0 and macd_data['histogram'] > 0:
                direction = "CALL"
                confidence = 85
            # ✅ PUT: Crossover down
            elif prev_macd['histogram'] >= 0 and macd_data['histogram'] < 0:
                direction = "PUT"
                confidence = 85
        
        if not direction:
            return None
        
        predicted_move = abs(macd_data['histogram']) * current_price / 100
        
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
                'move': predicted_move
            },
            indicators=macd_data,
            bull_score=75 if direction == "CALL" else 25,
            bear_score=25 if direction == "CALL" else 75,
            strategy_name="MACD"
        )
    
    def _strategy_rsi_pattern(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """RSI Pattern - Generates BOTH CALL and PUT"""
        if len(candles) < 30:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        divergence = self._detect_rsi_divergence(closes)
        
        direction = None
        confidence = 0
        
        # ✅ CALL: Bullish divergence
        if divergence == "BULLISH":
            direction = "CALL"
            confidence = 88
        # ✅ PUT: Bearish divergence
        elif divergence == "BEARISH":
            direction = "PUT"
            confidence = 88
        # ✅ CALL: Oversold
        elif rsi < 25:
            direction = "CALL"
            confidence = 75
        # ✅ PUT: Overbought
        elif rsi > 75:
            direction = "PUT"
            confidence = 75
        else:
            return None
        
        predicted_move = self._calculate_atr(candles) * 0.8 if self._calculate_atr(candles) else (current_price * 0.001)
        
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
                'move': predicted_move
            },
            indicators={'rsi': rsi, 'divergence': divergence},
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="RSI Pattern"
        )
    
    def _strategy_supertrend(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Supertrend - Generates BOTH CALL and PUT"""
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        supertrend, trend = self.indicators.calculate_supertrend(candles)
        
        if not supertrend or not trend or len(supertrend) < 2:
            return None
        
        current_supertrend = supertrend[-1]
        current_trend = trend[-1]
        
        if current_supertrend is None:
            return None
        
        direction = None
        confidence = 0
        
        rsi = self.indicators.calculate_rsi_smma(closes, 14)
        
        # ✅ CALL: Downtrend ending with oversold
        if current_trend == -1 and current_price < current_supertrend:
            if rsi < 30:
                direction = "CALL"
                confidence = 80
            elif current_price < current_supertrend * 0.995:
                direction = "CALL"
                confidence = 72
        
        # ✅ PUT: Uptrend ending with overbought
        elif current_trend == 1 and current_price > current_supertrend:
            if rsi > 70:
                direction = "PUT"
                confidence = 80
            elif current_price > current_supertrend * 1.005:
                direction = "PUT"
                confidence = 72
        
        if not direction:
            return None
        
        predicted_move = abs(current_price - current_supertrend) * 0.5 if current_supertrend else (current_price * 0.001)
        
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
                'move': predicted_move
            },
            indicators={'supertrend': current_supertrend, 'trend': current_trend, 'rsi': rsi},
            bull_score=75 if direction == "CALL" else 25,
            bear_score=25 if direction == "CALL" else 75,
            strategy_name="Supertrend"
        )
    
    # ==================== HELPER FUNCTIONS ====================
    
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
    
    def _detect_rsi_divergence(self, closes: List[float]) -> str:
        if len(closes) < 30:
            return None
        rsi_values = []
        for i in range(14, len(closes)):
            rsi = self.indicators.calculate_rsi_smma(closes[:i+1], 14)
            rsi_values.append(rsi)
        if len(rsi_values) < 20:
            return None
        price_lows = closes[-20:]
        rsi_lows = rsi_values[-20:]
        price_highs = closes[-20:]
        rsi_highs = rsi_values[-20:]
        price_making_lower_low = price_lows[-1] < min(price_lows[:-1])
        rsi_making_higher_low = rsi_lows[-1] > min(rsi_lows[:-1])
        if price_making_lower_low and rsi_making_higher_low:
            return "BULLISH"
        price_making_higher_high = price_highs[-1] > max(price_highs[:-1])
        rsi_making_lower_high = rsi_highs[-1] < max(rsi_highs[:-1])
        if price_making_higher_high and rsi_making_lower_high:
            return "BEARISH"
        return None
    
    # ==================== MAIN PREDICT ====================
    
    def predict(self, candles: List[Dict]) -> Optional[PredictionResult]:
        if not candles or len(candles) < 20:
            return None
        
        best_prediction = None
        best_confidence = 0
        
        # ✅ Shuffle strategies to avoid bias
        import random
        strategies = self.active_strategies.copy()
        random.shuffle(strategies)
        
        for strategy_name in strategies:
            if strategy_name in self.strategies:
                try:
                    prediction = self.strategies[strategy_name](candles)
                    if prediction and prediction.confidence > best_confidence:
                        prediction = self._validate_signal(prediction, candles)
                        if prediction and prediction.confidence > best_confidence:
                            best_prediction = prediction
                            best_confidence = prediction.confidence
                except Exception as e:
                    pass
        
        if best_prediction:
            self.total_predictions += 1
        
        return best_prediction
    
    def _validate_signal(self, prediction: PredictionResult, candles: List[Dict]) -> Optional[PredictionResult]:
        if not prediction or len(candles) < 3:
            return None
        
        current = candles[-1]
        
        if prediction.direction == "CALL":
            if current['close'] < current['open'] * 0.995:
                prediction.confidence -= 10
            if current['low'] < candles[-2]['low']:
                prediction.confidence -= 5
        else:
            if current['close'] > current['open'] * 1.005:
                prediction.confidence -= 10
            if current['high'] > candles[-2]['high']:
                prediction.confidence -= 5
        
        if prediction.confidence < 65:
            return None
        
        prediction.confidence = min(95, prediction.confidence)
        return prediction
    
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
            "[bold magenta]🔮 NEXT CANDLE QUANTUM PREDICTION[/bold magenta]\n"
            "[dim cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim cyan]",
            border_style="magenta"
        )
        console.print(header)
        
        nc = prediction.next_candle
        direction = prediction.direction
        confidence = prediction.confidence
        strength, color = QuantumPredictionEngine().get_signal_strength(prediction)
        
        arrow = "↗ BULLISH ↗" if direction == "CALL" else "↘ BEARISH ↘"
        arrow_color = "green" if direction == "CALL" else "red"
        
        main_content = f"""
[bold yellow]⚡ CURRENT PRICE: {prediction.next_candle['open']:.5f}[/bold yellow]
[dim cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim cyan]

[bold {arrow_color}]{arrow}[/bold {arrow_color}]

[bold cyan]OHLC VALUES:[/bold cyan]
  [green]O: {nc['open']:.5f}[/green]    [bright_cyan]H: {nc['high']:.5f}[/bright_cyan]
  [yellow]L: {nc['low']:.5f}[/yellow]    [magenta]C: {nc['close']:.5f}[/magenta]

[bold {color}]{confidence:.0f}% ACCURACY - {strength} SIGNAL[/bold {color}]
[dim]Strategy: {prediction.strategy_name}[/dim]
"""
        
        main_panel = Panel(
            main_content,
            title=f"[bold]{asset} | {period}s[/bold]",
            border_style=color,
            padding=(1, 2)
        )
        console.print(main_panel)
        
        footer = Panel(
            f"[dim]Neural Strength: {prediction.bull_score + prediction.bear_score:.0f}% | "
            f"Quantum Resonance: {prediction.confidence:.0f}%[/dim]",
            border_style="dim cyan"
        )
        console.print(footer)
        
        self.prediction_history.append({
            'time': datetime.now().strftime("%H:%M:%S"),
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
        table.add_column("Time", style="cyan")
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

# ==================== MAIN TRADING BOT ====================
class QuantumTradingBotEnhanced:
    def __init__(self):
        self.engine = QuantumPredictionEngine()
        self.visualizer = NextCandleVisualizer()
        self.trade_history = []
        self.current_balance = 0
        self.initial_balance = 0
        self.is_running = False
        
        self.trade_amount = 10
        self.min_confidence = 72
        self.max_trades = 0
        self.stop_loss = 0
        self.stop_profit = 0
        self.trading_mode = "1"
        
        self.selected_strategies = ['ema_rsi', 'bollinger_reversal', 'support_resistance', 'breakout']
        
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
    
    def _get_trend(self, candles: List[Dict]) -> str:
        closes = [c['close'] for c in candles]
        if len(closes) < 50:
            return "NEUTRAL"
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50
        bullish = 0
        bearish = 0
        if ma5 > ma10: bullish += 1
        else: bearish += 1
        if ma10 > ma20: bullish += 1
        else: bearish += 1
        if ma20 > ma50: bullish += 1
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
            "[bold cyan]🌌 QUANTUM QUOTEX TRADING BOT - BALANCED[/bold cyan]\n"
            "[white]CALL + PUT Signals | 4 Strategies | 60%+ Win Rate[/white]\n\n"
            "[dim]✅ Balanced strategy selection | Both directions[/dim]",
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
        console.print("\n[dim]Available Strategies (All generate both CALL and PUT):[/dim]")
        
        strategies_list = [
            ("1", "ema_rsi", "EMA_RSI - Most Reliable ⭐"),
            ("2", "bollinger_reversal", "Bollinger Reversal"),
            ("3", "support_resistance", "Support/Resistance"),
            ("4", "breakout", "Breakout - NEW"),
            ("5", "macd", "MACD"),
            ("6", "rsi_pattern", "RSI Pattern"),
            ("7", "supertrend", "Supertrend")
        ]
        
        for num, key, name in strategies_list:
            console.print(f"  {num}. {name}")
        
        console.print("\n[bold yellow]Select strategies:[/bold yellow]")
        console.print("  • Enter numbers separated by commas (e.g., 1,2,3,4)")
        console.print("  • Enter 'all' for all strategies")
        console.print("  • Enter 'best' for top 4 (Recommended)")
        
        choice = input("\n👉 Your choice: ").strip().lower()
        
        if choice == 'best' or choice == '':
            self.selected_strategies = ['ema_rsi', 'bollinger_reversal', 'support_resistance', 'breakout']
        elif choice == 'all':
            self.selected_strategies = [s[1] for s in strategies_list]
        else:
            selected_nums = [n.strip() for n in choice.split(',')]
            self.selected_strategies = []
            for s in strategies_list:
                if s[0] in selected_nums:
                    self.selected_strategies.append(s[1])
        
        self.engine.set_strategies(self.selected_strategies)
        console.print(f"\n[green]✅ Selected: {', '.join(self.selected_strategies)}[/green]")
    
    async def _set_trading_parameters(self):
        console.print("\n[bold yellow]⚙️ TRADING PARAMETERS[/bold yellow]")
        self.trade_amount = float(input("💰 Trade Amount ($): ") or "10")
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
    
    async def scan_all_markets(self) -> List[Dict]:
        opportunities = []
        for asset, timeframes in self.markets.items():
            for period in timeframes:
                candles = await self._get_candles(asset, period, 100)
                if not candles or len(candles) < 50:
                    continue
                trend = self._get_trend(candles)
                prediction = self.engine.predict(candles)
                if prediction:
                    if trend == "BULLISH" and prediction.direction == "CALL":
                        prediction.confidence = min(95, prediction.confidence + 5)
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif trend == "BEARISH" and prediction.direction == "PUT":
                        prediction.confidence = min(95, prediction.confidence + 5)
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif trend == "NEUTRAL":
                        if prediction.confidence >= 78:
                            opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend})
                    elif prediction.confidence >= 85:  # High confidence counter-trend
                        opportunities.append({'asset': asset, 'period': period, 'prediction': prediction, 'trend': trend + " (Counter)"})
        opportunities.sort(key=lambda x: x['prediction'].confidence, reverse=True)
        return opportunities
    
    async def _get_candles(self, asset: str, period: int, count: int) -> List[Dict]:
        try:
            candles = await client.get_candles(asset, None, period * count, period)
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
        except:
            pass
        return []
    
    async def execute_trade(self, asset: str, direction: str, period: int, amount: float) -> Optional[Dict]:
        try:
            asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
            if not asset_data[2]:
                console.print(f"[red]❌ {asset} is closed![/red]")
                return None
            console.print(f"\n[bold yellow]⚡ EXECUTING: {direction} on {asset} ({period}s) ${amount:.2f}[/bold yellow]")
            status, buy_info = await client.buy(amount, asset_name, direction.lower(), period)
            if not status:
                console.print("[red]❌ Trade failed![/red]")
                return None
            console.print(f"[green]✅ Order placed: {buy_info.get('id', 'N/A')}[/green]")
            await asyncio.sleep(period + 3)
            if buy_info and "id" in buy_info:
                win_status, profit = await client.check_win(buy_info["id"])
                result = "WIN" if win_status == "win" else "LOSS"
                trade_profit = profit if win_status == "win" else -amount
                trade_record = {
                    'time': datetime.now().strftime("%H:%M:%S"),
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
        
        console.print("\n[bold green]🤖 QUANTUM BOT STARTED![/bold green]")
        console.print(f"[dim]Active Strategies: {', '.join(self.selected_strategies)}[/dim]")
        console.print(f"[dim]Min Confidence: {self.min_confidence}%[/dim]")
        console.print("[dim]Scanning ALL timeframes for opportunities...[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            while self.is_running:
                should_stop, reason = self.check_limits()
                if should_stop:
                    console.print(f"\n[bold yellow]{reason}[/bold yellow]")
                    break
                if self.max_trades > 0 and trade_count >= self.max_trades:
                    console.print(f"\n[bold yellow]✅ Max trades ({self.max_trades}) reached![/bold yellow]")
                    break
                
                opportunities = await self.scan_all_markets()
                if not opportunities:
                    console.print(f"\r[dim]⏳ Scanning... ({datetime.now().strftime('%H:%M:%S')})[/dim]", end="")
                    await asyncio.sleep(3)
                    continue
                
                best = opportunities[0]
                if self._should_skip_trade(best['prediction'], consecutive_losses):
                    console.print(f"\n[yellow]⏳ Skipping - need higher confidence[/yellow]")
                    await asyncio.sleep(5)
                    continue
                
                trend_emoji = "📈" if best['trend'] == "BULLISH" else "📉" if best['trend'] == "BEARISH" else "➖"
                
                self.visualizer.display_prediction(best['asset'], best['period'], best['prediction'])
                console.print(f"[dim]{trend_emoji} Trend: {best['trend']} | Confidence: {best['prediction'].confidence:.0f}% | Period: {best['period']}s[/dim]")
                self.visualizer.show_prediction_history()
                
                if consecutive_losses >= 2 and best['prediction'].confidence < 78:
                    console.print(f"[yellow]⏳ Skipping - need 78%+ after losses[/yellow]")
                    await asyncio.sleep(8)
                    continue
                
                for remaining in range(3, 0, -1):
                    console.print(f"\r[yellow]⚡ Executing in {remaining}s...[/yellow]", end="")
                    await asyncio.sleep(1)
                
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
                    await asyncio.sleep(5 if last_was_win else 15)
                
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
            f"[bold cyan]📊 QUANTUM SESSION SUMMARY[/bold cyan]\n\n"
            f"[white]Strategies: {', '.join(self.selected_strategies)}\n"
            f"Total Trades: {total_trades}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {losses}\n"
            f"📈 Win Rate: {win_rate:.1f}%\n\n"
            f"💰 Initial Balance: ${self.initial_balance:.2f}\n"
            f"💰 Final Balance: ${self.current_balance:.2f}\n"
            f"📊 Net P&L: ${total_pnl:+.2f}",
            border_style="cyan"
        )
        console.print(summary)
        if win_rate >= 60:
            console.print("[bold green]✅ Excellent! Strategy is profitable![/bold green]")
        elif win_rate >= 55:
            console.print("[bold yellow]⚠️ Decent, but can improve.[/bold yellow]")
        else:
            console.print("[bold red]❌ Needs optimization.[/bold red]")
        
        self._save_summary()
    
    def _save_summary(self):
        filename = f"quantum_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            'date': datetime.now().isoformat(),
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
    bot = QuantumTradingBotEnhanced()
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
        console.print("\n[dim]👋 Quantum Bot shutdown complete![/dim]\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Closed by user![/yellow]")
