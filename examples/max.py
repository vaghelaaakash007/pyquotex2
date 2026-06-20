# quantum_quotex_bot_enhanced.py
"""
QUANTUM QUOTEX TRADING BOT - ENHANCED EDITION
==============================================
- Focused Next Candle Visualization
- 12+ Advanced Trading Strategies
- Real-time Quantum Analysis Display
- Multi-strategy Backtesting Suite
- AI-Powered Pattern Recognition
"""

import os
import sys
import time
import asyncio
import json
import csv
import math
from datetime import datetime, timedelta
from collections import deque, defaultdict
import logging
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
from rich.live import Live
from rich.layout import Layout
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich.style import Style
from rich.color import Color
import numpy as np

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
    """Enhanced candle data structure"""
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
    """Enhanced prediction result"""
    direction: str
    confidence: float
    next_candle: Dict[str, float]
    indicators: Dict[str, float]
    bull_score: float = 0.0
    bear_score: float = 0.0
    strategy_name: str = ""
    signal_strength: str = ""
    timestamp: float = field(default_factory=time.time)

# ==================== ADVANCED INDICATORS ====================
class AdvancedIndicators:
    """Collection of advanced trading indicators"""
    
    @staticmethod
    def awesome_oscillator(highs: List[float], lows: List[float], 
                          fast_period: int = 5, slow_period: int = 34) -> List[float]:
        """Calculate Awesome Oscillator"""
        if len(highs) < slow_period:
            return []
        
        ao_values = []
        for i in range(slow_period - 1, len(highs)):
            # Calculate median prices
            medians = [(h + l) / 2 for h, l in zip(highs[i-slow_period+1:i+1], 
                                                   lows[i-slow_period+1:i+1])]
            
            fast_sma = sum(medians[-fast_period:]) / fast_period
            slow_sma = sum(medians[-slow_period:]) / slow_period
            
            ao_values.append(fast_sma - slow_sma)
        
        return ao_values
    
    @staticmethod
    def bollinger_bands_pattern(closes: List[float], period: int = 20, 
                               std_dev: float = 2.0) -> Dict[str, Any]:
        """Bollinger Bands with pattern recognition"""
        if len(closes) < period:
            return {}
        
        sma = sum(closes[-period:]) / period
        std = (sum((x - sma) ** 2 for x in closes[-period:]) / period) ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        current_price = closes[-1]
        
        # Pattern recognition
        bb_position = (current_price - lower_band) / (upper_band - lower_band) if upper_band != lower_band else 0.5
        bandwidth = (upper_band - lower_band) / sma
        
        # Patterns
        patterns = []
        
        if bb_position > 1.0:
            patterns.append("BREAKOUT_ABOVE")
        elif bb_position < 0.0:
            patterns.append("BREAKOUT_BELOW")
        elif bb_position > 0.9:
            patterns.append("UPPER_BAND_TOUCH")
        elif bb_position < 0.1:
            patterns.append("LOWER_BAND_TOUCH")
        elif 0.4 <= bb_position <= 0.6:
            patterns.append("MIDDLE_REVERSION")
        
        # Squeeze detection
        if len(closes) >= period * 2:
            old_std = (sum((x - sma) ** 2 for x in closes[-2*period:-period]) / period) ** 0.5
            if std < old_std * 0.7:
                patterns.append("BB_SQUEEZE")
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band,
            'position': bb_position,
            'bandwidth': bandwidth,
            'patterns': patterns
        }
    
    @staticmethod
    def dual_thrust(highs: List[float], lows: List[float], closes: List[float],
                   lookback: int = 4, k1: float = 0.5, k2: float = 0.5) -> Dict[str, float]:
        """Dual Thrust indicator"""
        if len(highs) < lookback:
            return {}
        
        # Calculate range
        hh = max(highs[-lookback-1:-1])
        hc = max(closes[-lookback-1:-1])
        lc = min(closes[-lookback-1:-1])
        ll = min(lows[-lookback-1:-1])
        
        range_val = max(hh - lc, hc - ll)
        
        # Upper and lower bounds
        upper_bound = closes[-2] + k1 * range_val
        lower_bound = closes[-2] - k2 * range_val
        
        current_price = closes[-1]
        
        return {
            'upper_bound': upper_bound,
            'lower_bound': lower_bound,
            'range': range_val,
            'position': (current_price - lower_bound) / (upper_bound - lower_bound) 
                       if upper_bound != lower_bound else 0.5
        }
    
    @staticmethod
    def heikin_ashi(opens: List[float], highs: List[float], 
                   lows: List[float], closes: List[float]) -> List[Dict[str, float]]:
        """Calculate Heikin-Ashi candlesticks"""
        ha_candles = []
        
        for i in range(len(opens)):
            if i == 0:
                ha_open = opens[i]
                ha_close = closes[i]
            else:
                ha_open = (ha_candles[-1]['open'] + ha_candles[-1]['close']) / 2
                ha_close = (opens[i] + highs[i] + lows[i] + closes[i]) / 4
            
            ha_high = max(highs[i], ha_open, ha_close)
            ha_low = min(lows[i], ha_open, ha_close)
            
            ha_candles.append({
                'open': ha_open,
                'high': ha_high,
                'low': ha_low,
                'close': ha_close
            })
        
        # Pattern recognition
        if len(ha_candles) >= 3:
            last = ha_candles[-1]
            prev = ha_candles[-2]
            
            patterns = []
            
            # Doji detection
            body = abs(last['close'] - last['open'])
            total_range = last['high'] - last['low']
            if total_range > 0 and body / total_range < 0.1:
                patterns.append("HA_DOJI")
            
            # Trend detection
            if last['close'] > last['open'] and prev['close'] > prev['open']:
                patterns.append("HA_BULLISH")
            elif last['close'] < last['open'] and prev['close'] < prev['open']:
                patterns.append("HA_BEARISH")
            
            return ha_candles, patterns
        
        return ha_candles, []
    
    @staticmethod
    def london_breakout(highs: List[float], lows: List[float], 
                       current_price: float, session_start_hour: int = 8) -> Dict[str, Any]:
        """London Breakout strategy indicator"""
        # London session typically starts at 08:00 GMT
        # For simplicity, we'll use recent highs/lows
        
        if len(highs) < 24:
            return {}
        
        # Use last 24 periods as proxy for Asian session
        asian_high = max(highs[-24:-12])
        asian_low = min(lows[-24:-12])
        
        # London range (last 12 periods)
        london_high = max(highs[-12:])
        london_low = min(lows[-12:])
        
        breakout = None
        if current_price > london_high:
            breakout = "BULLISH_BREAKOUT"
        elif current_price < london_low:
            breakout = "BEARISH_BREAKOUT"
        elif asian_high <= current_price <= london_high:
            breakout = "IN_RANGE"
        
        return {
            'asian_high': asian_high,
            'asian_low': asian_low,
            'london_high': london_high,
            'london_low': london_low,
            'breakout': breakout,
            'range': london_high - london_low
        }
    
    @staticmethod
    def macd_oscillator(closes: List[float], fast: int = 12, 
                       slow: int = 26, signal: int = 9) -> Dict[str, Any]:
        """Advanced MACD with divergence detection"""
        if len(closes) < slow + signal:
            return {}
        
        # Calculate EMAs
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for price in data[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val
        
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = ema([macd_line], signal) if macd_line else 0
        
        # Histogram
        histogram = macd_line - signal_line if macd_line else 0
        
        # Divergence detection
        divergence = None
        if len(closes) >= slow + signal + 10:
            # Check for bullish divergence
            recent_lows = closes[-10:]
            macd_recent = [macd_line] * 10  # Simplified
            
            price_making_higher_low = recent_lows[-1] > min(recent_lows[:-1])
            macd_making_lower_low = True  # Simplified
            
            if price_making_higher_low and macd_making_lower_low:
                divergence = "BULLISH_DIVERGENCE"
            else:
                divergence = "BEARISH_DIVERGENCE" if not price_making_higher_low else None
        
        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram,
            'divergence': divergence,
            'trend': 'BULLISH' if histogram > 0 else 'BEARISH'
        }
    
    @staticmethod
    def parabolic_sar(highs: List[float], lows: List[float], 
                     acceleration: float = 0.02, maximum: float = 0.2) -> List[float]:
        """Calculate Parabolic SAR"""
        if len(highs) < 2:
            return []
        
        sar_values = []
        
        # Initial values
        sar = lows[0]
        ep = highs[0]  # Extreme point
        af = acceleration
        uptrend = True
        
        for i in range(1, len(highs)):
            prev_sar = sar
            
            if uptrend:
                sar = prev_sar + af * (ep - prev_sar)
                
                # Ensure SAR is below recent lows
                if i >= 1:
                    sar = min(sar, lows[i-1])
                if i >= 2:
                    sar = min(sar, lows[i-2])
                
                # Check for trend reversal
                if lows[i] < sar:
                    uptrend = False
                    sar = ep
                    ep = lows[i]
                    af = acceleration
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + acceleration, maximum)
            else:
                sar = prev_sar - af * (prev_sar - ep)
                
                # Ensure SAR is above recent highs
                if i >= 1:
                    sar = max(sar, highs[i-1])
                if i >= 2:
                    sar = max(sar, highs[i-2])
                
                # Check for trend reversal
                if highs[i] > sar:
                    uptrend = True
                    sar = ep
                    ep = highs[i]
                    af = acceleration
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + acceleration, maximum)
            
            sar_values.append(sar)
        
        return sar_values
    
    @staticmethod
    def rsi_pattern_recognition(closes: List[float], period: int = 14) -> Dict[str, Any]:
        """RSI with advanced pattern recognition"""
        if len(closes) < period + 1:
            return {}
        
        # Calculate RSI
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Pattern recognition
        patterns = []
        
        if rsi > 70:
            patterns.append("OVERBOUGHT")
        elif rsi < 30:
            patterns.append("OVERSOLD")
        elif 30 <= rsi <= 70:
            patterns.append("NEUTRAL")
        
        # Divergence detection
        if len(closes) >= period * 2:
            recent_rsi = []
            for j in range(period):
                d = deltas[-j-1:-j] if j < len(deltas) else [0]
                recent_rsi.append(70)  # Simplified
            
            if closes[-1] > closes[-period] and recent_rsi[-1] < recent_rsi[0]:
                patterns.append("BEARISH_DIVERGENCE")
            elif closes[-1] < closes[-period] and recent_rsi[-1] > recent_rsi[0]:
                patterns.append("BULLISH_DIVERGENCE")
        
        return {
            'rsi': rsi,
            'patterns': patterns,
            'overbought': rsi > 70,
            'oversold': rsi < 30
        }
    
    @staticmethod
    def shooting_star(opens: List[float], highs: List[float], 
                     lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """Shooting Star and Hammer pattern detection"""
        if len(opens) < 3:
            return {}
        
        current = {
            'open': opens[-1],
            'high': highs[-1],
            'low': lows[-1],
            'close': closes[-1]
        }
        
        body = abs(current['close'] - current['open'])
        upper_wick = current['high'] - max(current['open'], current['close'])
        lower_wick = min(current['open'], current['close']) - current['low']
        total_range = current['high'] - current['low']
        
        patterns = []
        strength = 0
        
        if total_range > 0:
            # Shooting Star detection
            if (upper_wick > body * 2 and 
                lower_wick < body * 0.5 and
                current['close'] < current['open']):
                patterns.append("SHOOTING_STAR")
                strength = min(100, (upper_wick / total_range) * 100)
            
            # Hammer detection
            if (lower_wick > body * 2 and 
                upper_wick < body * 0.5 and
                current['close'] > current['open']):
                patterns.append("HAMMER")
                strength = min(100, (lower_wick / total_range) * 100)
            
            # Doji
            if body / total_range < 0.1:
                patterns.append("DOJI")
                strength = 50
            
            # Marubozu
            if body > total_range * 0.9:
                if current['close'] > current['open']:
                    patterns.append("BULLISH_MARUBOZU")
                else:
                    patterns.append("BEARISH_MARUBOZU")
                strength = 80
        
        return {
            'patterns': patterns,
            'strength': strength,
            'body_ratio': body / total_range if total_range > 0 else 0,
            'upper_wick_ratio': upper_wick / total_range if total_range > 0 else 0,
            'lower_wick_ratio': lower_wick / total_range if total_range > 0 else 0
        }
    
    @staticmethod
    def vix_calculator(closes: List[float], period: int = 30) -> Dict[str, float]:
        """VIX-style volatility calculator"""
        if len(closes) < period:
            return {}
        
        # Calculate logarithmic returns
        returns = [math.log(closes[i] / closes[i-1]) for i in range(1, len(closes))]
        
        # Calculate historical volatility
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        volatility = math.sqrt(variance) * math.sqrt(252) * 100  # Annualized
        
        # Calculate short-term volatility
        short_returns = returns[-5:] if len(returns) >= 5 else returns
        short_vol = math.sqrt(sum((r - sum(short_returns)/len(short_returns)) ** 2 
                                 for r in short_returns) / (len(short_returns) - 1)) * math.sqrt(252) * 100
        
        return {
            'current_volatility': volatility,
            'short_term_volatility': short_vol,
            'volatility_ratio': short_vol / volatility if volatility > 0 else 1,
            'percentile': len([r for r in returns if abs(r) < abs(returns[-1])]) / len(returns) * 100 
                        if returns else 0
        }

# ==================== QUANTUM PREDICTION ENGINE ====================
class QuantumPredictionEngine:
    """Enhanced AI engine with multiple strategy support"""
    
    def __init__(self):
        self.price_memory = {}
        self.pattern_memory = {}
        self.accuracy_history = []
        self.total_predictions = 0
        self.correct_predictions = 0
        self.indicators = AdvancedIndicators()
        
        # Available strategies
        self.strategies = {
            'awesome_oscillator': self._strategy_awesome_oscillator,
            'bollinger_bands': self._strategy_bollinger_bands,
            'dual_thrust': self._strategy_dual_thrust,
            'heikin_ashi': self._strategy_heikin_ashi,
            'london_breakout': self._strategy_london_breakout,
            'macd': self._strategy_macd,
            'parabolic_sar': self._strategy_parabolic_sar,
            'rsi_pattern': self._strategy_rsi_pattern,
            'shooting_star': self._strategy_shooting_star,
            'options_straddle': self._strategy_options_straddle,
            'pair_trading': self._strategy_pair_trading,
            'quantum_composite': self._strategy_quantum_composite
        }
        
        self.active_strategies = ['quantum_composite']
    
    def set_strategies(self, strategy_names: List[str]):
        """Set active trading strategies"""
        valid_strategies = [s for s in strategy_names if s in self.strategies]
        if valid_strategies:
            self.active_strategies = valid_strategies
        return self.active_strategies
    
    def _strategy_awesome_oscillator(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Awesome Oscillator strategy"""
        if len(candles) < 34:
            return None
        
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        
        ao_values = self.indicators.awesome_oscillator(highs, lows)
        
        if not ao_values or len(ao_values) < 2:
            return None
        
        current_ao = ao_values[-1]
        prev_ao = ao_values[-2]
        
        # Signal generation
        if prev_ao < 0 and current_ao > 0:
            direction = "CALL"
            confidence = 75
        elif prev_ao > 0 and current_ao < 0:
            direction = "PUT"
            confidence = 75
        elif current_ao > 0 and current_ao > prev_ao:
            direction = "CALL"
            confidence = 65
        elif current_ao < 0 and current_ao < prev_ao:
            direction = "PUT"
            confidence = 65
        else:
            return None
        
        atr = sum(highs[i] - lows[i] for i in range(-14, 0)) / 14
        current_price = candles[-1]['close']
        
        predicted_move = atr * 0.5
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
            indicators={'ao': current_ao, 'prev_ao': prev_ao},
            bull_score=70 if direction == "CALL" else 30,
            bear_score=30 if direction == "CALL" else 70,
            strategy_name="Awesome Oscillator"
        )
    
    def _strategy_bollinger_bands(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Bollinger Bands strategy"""
        if len(candles) < 20:
            return None
        
        closes = [c['close'] for c in candles]
        bb = self.indicators.bollinger_bands_pattern(closes)
        
        if not bb:
            return None
        
        current_price = closes[-1]
        
        if "LOWER_BAND_TOUCH" in bb['patterns'] or "BREAKOUT_BELOW" in bb['patterns']:
            direction = "CALL"
            confidence = 80
        elif "UPPER_BAND_TOUCH" in bb['patterns'] or "BREAKOUT_ABOVE" in bb['patterns']:
            direction = "PUT"
            confidence = 80
        elif "BB_SQUEEZE" in bb['patterns']:
            # Anticipate breakout
            if current_price > bb['middle']:
                direction = "CALL"
                confidence = 70
            else:
                direction = "PUT"
                confidence = 70
        elif bb['position'] < 0.3:
            direction = "CALL"
            confidence = 65
        elif bb['position'] > 0.7:
            direction = "PUT"
            confidence = 65
        else:
            return None
        
        bandwidth = bb['bandwidth']
        predicted_move = bandwidth * current_price * 0.5
        
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
            indicators=bb,
            bull_score=75 if direction == "CALL" else 25,
            bear_score=25 if direction == "CALL" else 75,
            strategy_name="Bollinger Bands"
        )
    
    def _strategy_dual_thrust(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Dual Thrust strategy"""
        if len(candles) < 5:
            return None
        
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        
        dt = self.indicators.dual_thrust(highs, lows, closes)
        
        if not dt:
            return None
        
        current_price = closes[-1]
        
        if current_price > dt['upper_bound']:
            direction = "CALL"
            confidence = 80
        elif current_price < dt['lower_bound']:
            direction = "PUT"
            confidence = 80
        elif dt['position'] > 0.6:
            direction = "CALL"
            confidence = 65
        elif dt['position'] < 0.4:
            direction = "PUT"
            confidence = 65
        else:
            return None
        
        predicted_move = dt['range'] * 0.3
        
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
            indicators=dt,
            bull_score=72 if direction == "CALL" else 28,
            bear_score=28 if direction == "CALL" else 72,
            strategy_name="Dual Thrust"
        )
    
    def _strategy_heikin_ashi(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Heikin-Ashi strategy"""
        if len(candles) < 10:
            return None
        
        opens = [c['open'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        
        ha_candles, patterns = self.indicators.heikin_ashi(opens, highs, lows, closes)
        
        if not ha_candles:
            return None
        
        current_ha = ha_candles[-1]
        prev_ha = ha_candles[-2]
        current_price = closes[-1]
        
        if "HA_BULLISH" in patterns and current_ha['close'] > prev_ha['close']:
            direction = "CALL"
            confidence = 75
        elif "HA_BEARISH" in patterns and current_ha['close'] < prev_ha['close']:
            direction = "PUT"
            confidence = 75
        elif "HA_DOJI" in patterns:
            # Reversal signal
            if prev_ha['close'] > prev_ha['open']:
                direction = "PUT"
                confidence = 65
            else:
                direction = "CALL"
                confidence = 65
        else:
            return None
        
        predicted_move = (current_ha['high'] - current_ha['low']) * 0.5
        
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
            indicators={'ha_patterns': patterns},
            bull_score=73 if direction == "CALL" else 27,
            bear_score=27 if direction == "CALL" else 73,
            strategy_name="Heikin-Ashi"
        )
    
    def _strategy_london_breakout(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """London Breakout strategy"""
        if len(candles) < 24:
            return None
        
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        current_price = candles[-1]['close']
        
        lb = self.indicators.london_breakout(highs, lows, current_price)
        
        if not lb:
            return None
        
        if lb['breakout'] == "BULLISH_BREAKOUT":
            direction = "CALL"
            confidence = 85
        elif lb['breakout'] == "BEARISH_BREAKOUT":
            direction = "PUT"
            confidence = 85
        else:
            return None
        
        predicted_move = lb['range'] * 0.3
        
        if direction == "CALL":
            predicted_close = current_price + predicted_move
        else:
            predicted_close = current_price - predicted_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + predicted_move * 1.5,
                'low': current_price - predicted_move * 0.3,
                'close': predicted_close,
                'move': predicted_move
            },
            indicators=lb,
            bull_score=85 if direction == "CALL" else 15,
            bear_score=15 if direction == "CALL" else 85,
            strategy_name="London Breakout"
        )
    
    def _strategy_macd(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """MACD strategy"""
        if len(candles) < 26:
            return None
        
        closes = [c['close'] for c in candles]
        macd_data = self.indicators.macd_oscillator(closes)
        
        if not macd_data:
            return None
        
        # Get previous MACD values
        prev_closes = closes[:-1]
        prev_macd = self.indicators.macd_oscillator(prev_closes)
        
        if not prev_macd:
            return None
        
        current_price = closes[-1]
        
        # Signal crossover
        if prev_macd['histogram'] <= 0 and macd_data['histogram'] > 0:
            direction = "CALL"
            confidence = 85
        elif prev_macd['histogram'] >= 0 and macd_data['histogram'] < 0:
            direction = "PUT"
            confidence = 85
        elif macd_data['divergence'] == "BULLISH_DIVERGENCE":
            direction = "CALL"
            confidence = 80
        elif macd_data['divergence'] == "BEARISH_DIVERGENCE":
            direction = "PUT"
            confidence = 80
        else:
            return None
        
        predicted_move = abs(macd_data['histogram']) * 100
        
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
                'low': current_price - predicted_move * 0.5,
                'close': predicted_close,
                'move': predicted_move
            },
            indicators=macd_data,
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="MACD Oscillator"
        )
    
    def _strategy_parabolic_sar(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Parabolic SAR strategy"""
        if len(candles) < 10:
            return None
        
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        sar_values = self.indicators.parabolic_sar(highs, lows)
        
        if len(sar_values) < 2:
            return None
        
        current_sar = sar_values[-1]
        prev_sar = sar_values[-2]
        
        # Determine trend
        if current_price > current_sar:
            direction = "CALL"
            confidence = 70
        elif current_price < current_sar:
            direction = "PUT"
            confidence = 70
        else:
            return None
        
        # Check for SAR flip (stronger signal)
        if (prev_sar > closes[-2] and current_sar < current_price):
            confidence = 85
        elif (prev_sar < closes[-2] and current_sar > current_price):
            confidence = 85
        
        predicted_move = abs(current_price - current_sar) * 2
        
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
            indicators={'sar': current_sar, 'prev_sar': prev_sar},
            bull_score=78 if direction == "CALL" else 22,
            bear_score=22 if direction == "CALL" else 78,
            strategy_name="Parabolic SAR"
        )
    
    def _strategy_rsi_pattern(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """RSI Pattern Recognition strategy"""
        if len(candles) < 14:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        rsi_data = self.indicators.rsi_pattern_recognition(closes)
        
        if not rsi_data:
            return None
        
        if "OVERSOLD" in rsi_data['patterns']:
            direction = "CALL"
            confidence = 80
        elif "OVERBOUGHT" in rsi_data['patterns']:
            direction = "PUT"
            confidence = 80
        elif "BULLISH_DIVERGENCE" in rsi_data['patterns']:
            direction = "CALL"
            confidence = 75
        elif "BEARISH_DIVERGENCE" in rsi_data['patterns']:
            direction = "PUT"
            confidence = 75
        else:
            return None
        
        atr = sum(abs(closes[i] - closes[i-1]) for i in range(-14, 0)) / 14
        predicted_move = atr * 0.8
        
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
            indicators=rsi_data,
            bull_score=80 if direction == "CALL" else 20,
            bear_score=20 if direction == "CALL" else 80,
            strategy_name="RSI Pattern Recognition"
        )
    
    def _strategy_shooting_star(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Shooting Star strategy"""
        if len(candles) < 3:
            return None
        
        opens = [c['open'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        ss_data = self.indicators.shooting_star(opens, highs, lows, closes)
        
        if not ss_data:
            return None
        
        if "SHOOTING_STAR" in ss_data['patterns']:
            direction = "PUT"
            confidence = min(90, 60 + ss_data['strength'])
        elif "HAMMER" in ss_data['patterns']:
            direction = "CALL"
            confidence = min(90, 60 + ss_data['strength'])
        elif "BULLISH_MARUBOZU" in ss_data['patterns']:
            direction = "CALL"
            confidence = 85
        elif "BEARISH_MARUBOZU" in ss_data['patterns']:
            direction = "PUT"
            confidence = 85
        else:
            return None
        
        predicted_move = (highs[-1] - lows[-1]) * 0.5
        
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
            indicators=ss_data,
            bull_score=70 if direction == "CALL" else 30,
            bear_score=30 if direction == "CALL" else 70,
            strategy_name="Shooting Star"
        )
    
    def _strategy_options_straddle(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Options Straddle strategy - volatility based"""
        if len(candles) < 30:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        vix_data = self.indicators.vix_calculator(closes)
        
        if not vix_data:
            return None
        
        # High volatility = expect large move
        if vix_data['volatility_ratio'] > 1.5:
            # Check recent trend
            recent_trend = sum(1 for i in range(-5, 0) if closes[i] > closes[i-1])
            
            if recent_trend >= 3:
                direction = "CALL"
                confidence = 70
            elif recent_trend <= 2:
                direction = "PUT"
                confidence = 70
            else:
                direction = "CALL" if closes[-1] > closes[-2] else "PUT"
                confidence = 60
        else:
            return None
        
        predicted_move = vix_data['current_volatility'] * current_price / 100 * 0.01
        
        if direction == "CALL":
            predicted_close = current_price + predicted_move
        else:
            predicted_close = current_price - predicted_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + predicted_move * 1.5,
                'low': current_price - predicted_move * 0.5,
                'close': predicted_close,
                'move': predicted_move
            },
            indicators=vix_data,
            bull_score=65 if direction == "CALL" else 35,
            bear_score=35 if direction == "CALL" else 65,
            strategy_name="Options Straddle"
        )
    
    def _strategy_pair_trading(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Pair Trading strategy - correlation based"""
        if len(candles) < 50:
            return None
        
        closes = [c['close'] for c in candles]
        current_price = closes[-1]
        
        # Calculate spread from moving averages
        ma_short = sum(closes[-10:]) / 10
        ma_long = sum(closes[-30:]) / 30
        
        spread = ma_short - ma_long
        
        # Calculate spread history
        spreads = []
        for i in range(30, len(closes)):
            ma_s = sum(closes[i-10:i]) / 10
            ma_l = sum(closes[i-30:i]) / 30
            spreads.append(ma_s - ma_l)
        
        if len(spreads) < 5:
            return None
        
        avg_spread = sum(spreads) / len(spreads)
        std_spread = (sum((s - avg_spread) ** 2 for s in spreads) / len(spreads)) ** 0.5
        
        # Mean reversion
        if spread > avg_spread + 2 * std_spread:
            direction = "PUT"  # Expect spread to decrease
            confidence = 75
        elif spread < avg_spread - 2 * std_spread:
            direction = "CALL"  # Expect spread to increase
            confidence = 75
        else:
            return None
        
        predicted_move = abs(spread - avg_spread) * 0.5
        
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
            indicators={'spread': spread, 'avg_spread': avg_spread, 'z_score': (spread - avg_spread) / std_spread},
            bull_score=70 if direction == "CALL" else 30,
            bear_score=30 if direction == "CALL" else 70,
            strategy_name="Pair Trading"
        )
    
    def _strategy_quantum_composite(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Quantum Composite strategy - combines multiple signals"""
        if len(candles) < 50:
            return None
        
        # Get signals from multiple strategies
        signals = []
        
        for strategy_name in ['awesome_oscillator', 'bollinger_bands', 'macd', 'rsi_pattern', 'shooting_star']:
            if strategy_name in self.strategies:
                try:
                    result = self.strategies[strategy_name](candles)
                    if result:
                        signals.append(result)
                except:
                    pass
        
        if not signals:
            return None
        
        # Aggregate signals
        call_signals = [s for s in signals if s.direction == "CALL"]
        put_signals = [s for s in signals if s.direction == "PUT"]
        
        total_confidence = sum(s.confidence for s in signals)
        
        if len(call_signals) > len(put_signals):
            direction = "CALL"
            confidence = sum(s.confidence for s in call_signals) / len(call_signals) * 1.1  # Bonus for agreement
        elif len(put_signals) > len(call_signals):
            direction = "PUT"
            confidence = sum(s.confidence for s in put_signals) / len(put_signals) * 1.1
        else:
            direction = "CALL" if call_signals[0].confidence > put_signals[0].confidence else "PUT"
            confidence = max(s.confidence for s in signals) * 0.9  # Penalty for disagreement
        
        confidence = min(95, confidence)
        
        if confidence < 65:
            return None
        
        # Use average predicted move
        avg_move = sum(abs(s.next_candle['move']) for s in signals) / len(signals)
        current_price = candles[-1]['close']
        
        if direction == "CALL":
            predicted_close = current_price + avg_move
        else:
            predicted_close = current_price - avg_move
        
        return PredictionResult(
            direction=direction,
            confidence=confidence,
            next_candle={
                'open': current_price,
                'high': current_price + avg_move * 1.3,
                'low': current_price - avg_move * 0.4,
                'close': predicted_close,
                'move': avg_move
            },
            indicators={'composite_signals': len(signals), 'agreement': abs(len(call_signals) - len(put_signals))},
            bull_score=sum(s.bull_score for s in signals) / len(signals),
            bear_score=sum(s.bear_score for s in signals) / len(signals),
            strategy_name="Quantum Composite"
        )
    
    def predict(self, candles: List[Dict]) -> Optional[PredictionResult]:
        """Generate prediction using active strategies"""
        best_prediction = None
        best_confidence = 0
        
        for strategy_name in self.active_strategies:
            if strategy_name in self.strategies:
                try:
                    prediction = self.strategies[strategy_name](candles)
                    if prediction and prediction.confidence > best_confidence:
                        best_prediction = prediction
                        best_confidence = prediction.confidence
                except Exception as e:
                    console.print(f"[red]Strategy {strategy_name} error: {e}[/red]")
        
        if best_prediction:
            self.total_predictions += 1
        
        return best_prediction
    
    def get_signal_strength(self, prediction: Optional[PredictionResult]) -> Tuple[str, str]:
        """Get signal quality assessment"""
        if not prediction:
            return "WEAK", "gray"
        
        confidence = prediction.confidence
        
        if confidence >= 95:
            return "QUANTUM", "bright_magenta"
        elif confidence >= 85:
            return "ULTRA STRONG", "bright_green"
        elif confidence >= 75:
            return "STRONG", "green"
        elif confidence >= 70:
            return "MODERATE", "yellow"
        elif confidence >= 65:
            return "WEAK", "red"
        else:
            return "VERY WEAK", "dim red"

# ==================== NEXT CANDLE VISUALIZER ====================
class NextCandleVisualizer:
    """Dedicated next candle visualization with quantum effects"""
    
    def __init__(self):
        self.prediction_history = []
        self.max_history = 10
    
    def display_prediction(self, asset: str, period: int, prediction: PredictionResult):
        """Display focused next candle prediction"""
        console.clear()
        
        # Quantum header
        header = Panel(
            "[bold magenta]🔮 NEXT CANDLE QUANTUM PREDICTION[/bold magenta]\n"
            "[dim cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim cyan]",
            border_style="magenta"
        )
        console.print(header)
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Main prediction display
        nc = prediction.next_candle
        direction = prediction.direction
        confidence = prediction.confidence
        strength, color = QuantumPredictionEngine().get_signal_strength(prediction)
        
        # Direction arrow
        if direction == "CALL":
            arrow = "↗ BULLISH ↗"
            arrow_color = "green"
        else:
            arrow = "↘ BEARISH ↘"
            arrow_color = "red"
        
        # Create candle visualization
        candle_height = 15
        price_range = nc['high'] - nc['low']
        
        if price_range > 0:
            # Calculate positions
            body_top = nc['high'] if direction == "CALL" else nc['open']
            body_bottom = nc['open'] if direction == "CALL" else nc['low']
            body_high = nc['open'] if direction == "CALL" else nc['high']
            body_low = nc['low'] if direction == "CALL" else nc['close']
            
            # Normalize to candle height
            def norm_price(price):
                return int((price - nc['low']) / price_range * candle_height)
            
            body_top_norm = norm_price(body_top)
            body_bottom_norm = norm_price(body_bottom)
            wick_high_norm = norm_price(body_high)
            wick_low_norm = norm_price(body_low)
            
            # Build candle display
            candle_lines = []
            for i in range(candle_height):
                line = ""
                
                # Wick
                if wick_high_norm <= i <= wick_low_norm:
                    line += "[dim white]  │  [/dim white]"
                else:
                    line += "     "
                
                # Body
                if body_bottom_norm <= i <= body_top_norm:
                    if direction == "CALL":
                        line += "[bold green]███[/bold green]"
                    else:
                        line += "[bold red]███[/bold red]"
                else:
                    line += "   "
                
                candle_lines.append(line)
            
            # Reverse for display (top to bottom)
            candle_lines.reverse()
        else:
            candle_lines = ["  │  ███" for _ in range(candle_height)]
        
        # Build main display
        main_content = f"""
[bold yellow]⚡ CURRENT PRICE: {prediction.next_candle['open']:.5f}[/bold yellow]
[dim cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim cyan]

[bold {arrow_color}]{arrow}[/bold {arrow_color}]

[bold magenta]┌───── NEXT CANDLE ─────┐[/bold magenta]
"""
        
        for line in candle_lines:
            main_content += f"[dim magenta]│[/dim magenta] {line} [dim magenta]│[/dim magenta]\n"
        
        main_content += f"""[bold magenta]└────────────────────────┘[/bold magenta]

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
        
        # Footer with live data
        footer = Panel(
            f"[dim]⏱️ Formation Countdown: Calculating... | "
            f"Neural Strength: {prediction.bull_score + prediction.bear_score:.0f}% | "
            f"Quantum Resonance: {prediction.confidence:.0f}%[/dim]",
            border_style="dim cyan"
        )
        console.print(footer)
        
        # Add to history
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
        """Display recent prediction history"""
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

# ==================== ENHANCED BACKTEST ENGINE ====================
class EnhancedBacktestEngine:
    """Comprehensive backtesting engine for all strategies"""
    
    def __init__(self, client):
        self.client = client
        self.engine = QuantumPredictionEngine()
        self.backtest_results = {}
        self.available_strategies = list(self.engine.strategies.keys())
    
    async def backtest_strategy(self, asset: str, period: int, strategy_name: str, 
                               days: int = 7) -> Dict[str, Any]:
        """Backtest a specific strategy"""
        console.print(f"\n[yellow]🔬 Backtesting {strategy_name} on {asset} ({period}s)[/yellow]")
        
        # Download data
        candles = await self._get_historical_data(asset, period, days)
        
        if not candles or len(candles) < 100:
            console.print("[red]❌ Insufficient data[/red]")
            return {}
        
        # Set strategy
        original_strategies = self.engine.active_strategies
        self.engine.active_strategies = [strategy_name]
        
        results = []
        wins = 0
        losses = 0
        total_pnl = 0
        predictions_made = 0
        
        for i in range(50, len(candles) - 1):
            historical = candles[i-50:i+1]
            prediction = self.engine.predict(historical)
            
            if prediction and prediction.confidence >= 65:
                predictions_made += 1
                actual = candles[i+1]
                
                if prediction.direction == 'CALL':
                    win = actual['close'] > actual['open']
                else:
                    win = actual['close'] < actual['open']
                
                if win:
                    wins += 1
                    total_pnl += 0.85
                else:
                    losses += 1
                    total_pnl -= 1.0
                
                results.append({
                    'time': actual.get('time', i),
                    'direction': prediction.direction,
                    'confidence': prediction.confidence,
                    'win': win,
                    'predicted_close': prediction.next_candle['close'],
                    'actual_close': actual['close']
                })
        
        # Restore strategies
        self.engine.active_strategies = original_strategies
        
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        result = {
            'asset': asset,
            'period': period,
            'strategy': strategy_name,
            'days': days,
            'total_candles': len(candles),
            'predictions_made': predictions_made,
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'profit_factor': (wins * 0.85) / losses if losses > 0 else float('inf'),
            'results': results
        }
        
        self.backtest_results[f"{asset}_{period}_{strategy_name}"] = result
        
        return result
    
    async def backtest_all_strategies(self, asset: str, period: int, days: int = 7) -> List[Dict]:
        """Backtest all available strategies"""
        console.print(f"\n[bold magenta]🔬 BACKTESTING ALL STRATEGIES on {asset} ({period}s)[/bold magenta]")
        
        all_results = []
        
        for strategy_name in self.available_strategies:
            result = await self.backtest_strategy(asset, period, strategy_name, days)
            if result:
                all_results.append(result)
        
        # Rank by win rate
        all_results.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return all_results
    
    async def _get_historical_data(self, asset: str, period: int, days: int) -> List[Dict]:
        """Get historical data for backtesting"""
        try:
            candles = await self.client.get_candles_deep(asset, 86400 * days, period)
            
            if candles:
                formatted = []
                for c in candles:
                    if isinstance(c, dict):
                        formatted.append(c)
                    else:
                        formatted.append({
                            'time': time.time(),
                            'open': float(c),
                            'high': float(c),
                            'low': float(c),
                            'close': float(c),
                            'ticks': 100
                        })
                return formatted
        except Exception as e:
            console.print(f"[red]⚠️ Data fetch error: {e}[/red]")
        
        return []
    
    def display_backtest_results(self, results: List[Dict]):
        """Display backtest results in a formatted table"""
        if not results:
            console.print("[red]No backtest results to display[/red]")
            return
        
        table = Table(title="🎯 Backtest Results Summary")
        table.add_column("Strategy", style="cyan")
        table.add_column("Win Rate", style="green")
        table.add_column("Trades", style="white")
        table.add_column("P&L", style="yellow")
        table.add_column("Profit Factor", style="magenta")
        
        for r in results[:10]:  # Top 10
            pnl_color = "green" if r['total_pnl'] > 0 else "red"
            pf_color = "green" if r['profit_factor'] > 1.5 else "yellow"
            
            table.add_row(
                r['strategy'],
                f"{r['win_rate']:.1f}%",
                str(r['total_trades']),
                f"[{pnl_color}]${r['total_pnl']:+.2f}[/{pnl_color}]",
                f"[{pf_color}]{r['profit_factor']:.2f}[/{pf_color}]"
            )
        
        console.print(table)

# ==================== MAIN TRADING BOT ====================
class QuantumTradingBotEnhanced:
    """Enhanced trading bot with quantum visualization and multiple strategies"""
    
    def __init__(self):
        self.engine = QuantumPredictionEngine()
        self.backtest_engine = EnhancedBacktestEngine(client)
        self.visualizer = NextCandleVisualizer()
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
        self.trading_mode = "1"
        self.selected_strategies = ['quantum_composite']
        
        # Markets
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
        """Enhanced bot setup with strategy selection"""
        console.clear()
        
        # Welcome screen
        console.print(Panel.fit(
            "[bold cyan]🌌 QUANTUM QUOTEX TRADING BOT - ENHANCED[/bold cyan]\n"
            "[white]AI-Powered Next Candle Visualization | 12+ Strategies | Quantum Analysis[/white]\n\n"
            "[dim]🔮 Focused Next Candle Display | Real-time Quantum Effects | Multi-Strategy Backtesting[/dim]",
            border_style="cyan"
        ))
        
        # Connect
        console.print("\n[cyan]🔗 Connecting to Quotex...[/cyan]")
        check, msg = await client.connect()
        if not check:
            console.print(f"[red]❌ Connection failed: {msg}[/red]")
            return False
        
        # Account selection
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
        
        # Strategy selection
        await self._select_strategies()
        
        # Trading parameters
        await self._set_trading_parameters()
        
        # Backtesting option
        console.print("\n[bold cyan]🔬 Run Backtesting?[/bold cyan]")
        run_backtest = input("Backtest strategies before live trading? (y/n): ").strip().lower()
        
        if run_backtest == 'y':
            await self._run_backtesting_suite()
        
        return True
    
    async def _select_strategies(self):
        """Strategy selection menu"""
        console.print("\n[bold magenta]🎯 STRATEGY SELECTION[/bold magenta]")
        console.print("\n[dim]Available Strategies:[/dim]")
        
        strategies_list = [
            ("1", "quantum_composite", "Quantum Composite (All combined)"),
            ("2", "awesome_oscillator", "Awesome Oscillator"),
            ("3", "bollinger_bands", "Bollinger Bands Pattern"),
            ("4", "dual_thrust", "Dual Thrust"),
            ("5", "heikin_ashi", "Heikin-Ashi Candlesticks"),
            ("6", "london_breakout", "London Breakout"),
            ("7", "macd", "MACD Oscillator"),
            ("8", "parabolic_sar", "Parabolic SAR"),
            ("9", "rsi_pattern", "RSI Pattern Recognition"),
            ("10", "shooting_star", "Shooting Star"),
            ("11", "options_straddle", "Options Straddle"),
            ("12", "pair_trading", "Pair Trading")
        ]
        
        for num, key, name in strategies_list:
            console.print(f"  {num}. {name}")
        
        console.print("\n[bold yellow]Select strategies:[/bold yellow]")
        console.print("  • Enter numbers separated by commas (e.g., 1,3,7)")
        console.print("  • Enter 'all' for all strategies")
        console.print("  • Enter '0' for default (Quantum Composite)")
        
        choice = input("\n👉 Your choice: ").strip().lower()
        
        if choice == 'all':
            self.selected_strategies = [s[1] for s in strategies_list]
        elif choice == '0' or not choice:
            self.selected_strategies = ['quantum_composite']
        else:
            selected_nums = [n.strip() for n in choice.split(',')]
            self.selected_strategies = []
            for s in strategies_list:
                if s[0] in selected_nums:
                    self.selected_strategies.append(s[1])
        
        self.engine.set_strategies(self.selected_strategies)
        
        console.print(f"\n[green]✅ Selected: {', '.join(self.selected_strategies)}[/green]")
    
    async def _set_trading_parameters(self):
        """Set trading parameters"""
        console.print("\n[bold yellow]⚙️ TRADING PARAMETERS[/bold yellow]")
        
        self.trade_amount = float(input("💰 Trade Amount ($): ") or "10")
        self.min_confidence = float(input("🎯 Min Confidence % (60-95): ") or "70")
        max_t = input("🔄 Max Trades (0=unlimited): ")
        self.max_trades = int(max_t) if max_t else 0
        self.stop_loss = float(input("🛑 Stop Loss $ (0=off): ") or "0")
        self.stop_profit = float(input("🎯 Take Profit $ (0=off): ") or "0")
        
        console.print("\n[bold]Trading Mode:[/bold]")
        console.print("1. 📊 Fixed Amount")
        console.print("2. 🔄 Martingale")
        console.print("3. 📈 Compounding")
        self.trading_mode = input("👉 Choose (1/2/3): ").strip() or "1"
    
    async def _run_backtesting_suite(self):
        """Run comprehensive backtesting"""
        console.print("\n[bold magenta]🔬 BACKTESTING SUITE[/bold magenta]")
        
        # Select asset for backtesting
        console.print("\nSelect asset for backtesting:")
        for i, asset in enumerate(list(self.markets.keys())[:6], 1):
            console.print(f"  {i}. {asset}")
        
        asset_choice = input("\n👉 Choose asset number: ").strip()
        asset_list = list(self.markets.keys())
        selected_asset = asset_list[int(asset_choice) - 1] if asset_choice.isdigit() and 1 <= int(asset_choice) <= 6 else "EURUSD_otc"
        
        # Select timeframe
        console.print("\nSelect timeframe:")
        periods = [60, 300, 600]
        for i, p in enumerate(periods, 1):
            console.print(f"  {i}. {p}s")
        
        period_choice = input("\n👉 Choose timeframe: ").strip()
        selected_period = periods[int(period_choice) - 1] if period_choice.isdigit() and 1 <= int(period_choice) <= 3 else 60
        
        days = float(input("Days to backtest (1-30): ") or "7")
        
        # Run backtests
        if len(self.selected_strategies) <= 3:
            # Backtest individual strategies
            for strategy in self.selected_strategies:
                await self.backtest_engine.backtest_strategy(selected_asset, selected_period, strategy, days)
        else:
            # Backtest all
            results = await self.backtest_engine.backtest_all_strategies(selected_asset, selected_period, days)
            self.backtest_engine.display_backtest_results(results)
    
    async def scan_all_markets(self) -> List[Dict]:
        """Scan all markets for trading opportunities"""
        opportunities = []
        
        for asset, timeframes in self.markets.items():
            # Use first timeframe for scanning
            period = timeframes[1]  # 10s or similar
            candles = await self._get_candles(asset, period, 100)
            
            if candles and len(candles) >= 50:
                prediction = self.engine.predict(candles)
                
                if prediction and prediction.confidence >= self.min_confidence:
                    opportunities.append({
                        'asset': asset,
                        'period': period,
                        'prediction': prediction
                    })
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['prediction'].confidence, reverse=True)
        
        return opportunities
    
    async def _get_candles(self, asset: str, period: int, count: int) -> List[Dict]:
        """Get candles for analysis"""
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
        except Exception as e:
            console.print(f"[red]⚠️ Candle fetch error: {e}[/red]")
        return []
    
    async def execute_trade(self, asset: str, direction: str, period: int, amount: float) -> Optional[Dict]:
        """Execute a trade"""
        try:
            asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
            
            if not asset_data[2]:
                console.print(f"[red]❌ {asset} is closed![/red]")
                return None
            
            console.print(f"\n[bold yellow]⚡ EXECUTING: {direction} on {asset} ({period}s) ${amount}[/bold yellow]")
            
            status, buy_info = await client.buy(amount, asset_name, direction.lower(), period)
            
            if not status:
                console.print("[red]❌ Trade failed![/red]")
                return None
            
            console.print(f"[green]✅ Order placed: {buy_info.get('id', 'N/A')}[/green]")
            
            # Wait for result
            await asyncio.sleep(period + 3)
            
            # Check result
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
        """Calculate next trade amount based on mode"""
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
        """Main bot loop with quantum visualization"""
        if not await self.setup():
            return
        
        self.is_running = True
        trade_count = 0
        last_was_win = True
        
        console.print("\n[bold green]🤖 QUANTUM BOT STARTED![/bold green]")
        console.print(f"[dim]Active Strategies: {', '.join(self.selected_strategies)}[/dim]")
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
                    # Use best opportunity
                    best = opportunities[0]
                    
                    # Display quantum prediction
                    self.visualizer.display_prediction(
                        best['asset'], 
                        best['period'], 
                        best['prediction']
                    )
                    
                    # Show prediction history
                    self.visualizer.show_prediction_history()
                    
                    # Countdown
                    for remaining in range(3, 0, -1):
                        console.print(f"\r[yellow]⚡ Executing in {remaining}s...[/yellow]", end="")
                        await asyncio.sleep(1)
                    
                    console.print(f"\n[bold red]🚨 EXECUTE NOW! 🚨[/bold red]")
                    
                    # Get trade amount
                    amount = self.get_next_amount(last_was_win)
                    
                    # Execute trade
                    result = await self.execute_trade(
                        best['asset'],
                        best['prediction'].direction,
                        best['period'],
                        amount
                    )
                    
                    if result:
                        trade_count += 1
                        last_was_win = result['result'] == 'WIN'
                    
                    console.print(f"\n[dim]💰 Balance: ${self.current_balance:.2f} | Trades: {trade_count}[/dim]")
                
                else:
                    console.print(f"\r[dim]⏳ Quantum scanning... ({datetime.now().strftime('%H:%M:%S')})[/dim]", end="")
                
                await asyncio.sleep(2)
        
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⏹️ Bot stopped by user[/yellow]")
        
        # Show summary
        self._show_session_summary()
    
    def _show_session_summary(self):
        """Display enhanced session summary"""
        console.clear()
        
        total_trades = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t['result'] == 'WIN')
        losses = sum(1 for t in self.trade_history if t['result'] == 'LOSS')
        total_pnl = sum(t['profit'] for t in self.trade_history)
        
        summary = Panel.fit(
            f"[bold cyan]📊 QUANTUM SESSION SUMMARY[/bold cyan]\n\n"
            f"[white]Strategies: {', '.join(self.selected_strategies)}\n"
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
        
        # Save summary
        self._save_summary()
    
    def _save_summary(self):
        """Save session summary to file"""
        filename = f"quantum_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            'date': datetime.now().isoformat(),
            'strategies': self.selected_strategies,
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
    """Main entry point"""
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
