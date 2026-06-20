# examples/trade_bot.py

import asyncio
import signal
import random
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

# ==================== STRATEGY COLLECTION ====================
class ScalpingStrategyBase:
    def __init__(self):
        self.price_history = deque(maxlen=200)
        self.volume_history = deque(maxlen=200)
        self.name = "Base Strategy"
        self.description = ""
        self.win_rate_target = "N/A"
    
    def add_price(self, price, volume=100):
        self.price_history.append(price)
        self.volume_history.append(volume)
    
    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        if len(prices) < period:
            return 0, 0, 0
        sma = sum(prices[-period:]) / period
        variance = sum((x - sma) ** 2 for x in prices[-period:]) / period
        std = variance ** 0.5
        return sma + (std_dev * std), sma, sma - (std_dev * std)
    
    def get_signal(self):
        return None, 0


class EMA_RSI_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "EMA + RSI Scalping"
        self.description = "9 EMA + 21 EMA crossover with RSI confirmation"
        self.win_rate_target = "80-85%"
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        ema_9 = self.calculate_ema(prices, 9)
        ema_21 = self.calculate_ema(prices, 21)
        rsi = self.calculate_rsi(prices, 14)
        current_price = prices[-1]
        
        call_strength = 0
        put_strength = 0
        
        if ema_9 > ema_21:
            call_strength += 30
        if 40 <= rsi <= 60:
            call_strength += 25
        if abs(current_price - ema_9)/current_price < 0.001:
            call_strength += 20
        
        if ema_9 < ema_21:
            put_strength += 30
        if 40 <= rsi <= 60:
            put_strength += 25
        if abs(current_price - ema_9)/current_price < 0.001:
            put_strength += 20
        
        if call_strength >= 75 and call_strength > put_strength:
            return "call", call_strength
        elif put_strength >= 75 and put_strength > call_strength:
            return "put", put_strength
        
        if rsi < 30 and ema_9 > ema_21:
            return "call", 70
        if rsi > 70 and ema_9 < ema_21:
            return "put", 70
        
        return None, 0


class Bollinger_RSI_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Bollinger Bands + RSI"
        self.description = "Bollinger Band rejection with RSI overbought/oversold"
        self.win_rate_target = "82-87%"
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        upper, middle, lower = self.calculate_bollinger_bands(prices, 20, 2)
        rsi = self.calculate_rsi(prices, 14)
        current_price = prices[-1]
        
        if current_price <= lower * 1.001 and rsi < 35:
            return "call", 80
        if current_price >= upper * 0.999 and rsi > 65:
            return "put", 80
        if current_price <= middle and rsi < 30:
            return "call", 75
        if current_price >= middle and rsi > 70:
            return "put", 75
        
        return None, 0


class VWAP_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "VWAP Scalping"
        self.description = "VWAP institutional level trading with pullback"
        self.win_rate_target = "83-88%"
    
    def calculate_vwap(self):
        if len(self.price_history) < 1:
            return 0
        cumulative_pv = 0
        cumulative_v = 0
        for i in range(min(len(self.price_history), len(self.volume_history))):
            cumulative_pv += self.price_history[i] * self.volume_history[i]
            cumulative_v += self.volume_history[i]
        return cumulative_pv / cumulative_v if cumulative_v > 0 else 0
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        vwap = self.calculate_vwap()
        ema_9 = self.calculate_ema(prices, 9)
        current_price = prices[-1]
        price_vs_vwap = (current_price - vwap) / vwap * 100
        
        if price_vs_vwap > 0 and price_vs_vwap < 0.05 and ema_9 > vwap:
            return "call", 85
        if price_vs_vwap < 0 and price_vs_vwap > -0.05 and ema_9 < vwap:
            return "put", 85
        if price_vs_vwap > 0.1 and ema_9 > vwap:
            return "call", 75
        if price_vs_vwap < -0.1 and ema_9 < vwap:
            return "put", 75
        
        return None, 0


class Momentum_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Momentum Scalping"
        self.description = "Strong momentum with RSI and price action"
        self.win_rate_target = "80-85%"
    
    def get_signal(self):
        if len(self.price_history) < 20:
            return None, 0
        
        prices = list(self.price_history)
        rsi = self.calculate_rsi(prices, 7)
        momentum_5 = sum(prices[i] - prices[i-1] for i in range(-5, 0))
        momentum_3 = sum(prices[i] - prices[i-1] for i in range(-3, 0))
        
        if momentum_5 > 0 and momentum_3 > 0 and 40 <= rsi <= 65:
            return "call", 75
        if momentum_5 < 0 and momentum_3 < 0 and 35 <= rsi <= 60:
            return "put", 75
        
        return None, 0


class Support_Resistance_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Support/Resistance Rejection"
        self.description = "Key level rejection with RSI confirmation"
        self.win_rate_target = "84-89%"
    
    def find_levels(self, prices):
        if len(prices) < 50:
            return [], []
        supports, resistances = [], []
        for i in range(2, len(prices) - 2):
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                resistances.append(prices[i])
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                supports.append(prices[i])
        return supports[-3:], resistances[-3:]
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        supports, resistances = self.find_levels(prices)
        rsi = self.calculate_rsi(prices, 14)
        current_price = prices[-1]
        
        for support in supports:
            if abs(current_price - support)/current_price < 0.0005 and rsi < 45:
                return "call", 85
        for resistance in resistances:
            if abs(current_price - resistance)/current_price < 0.0005 and rsi > 55:
                return "put", 85
        
        return None, 0


class EMA_Pullback_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "EMA Pullback Scalping"
        self.description = "Pullback to 9/21 EMA in strong trend"
        self.win_rate_target = "85-90%"
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        ema_9 = self.calculate_ema(prices, 9)
        ema_21 = self.calculate_ema(prices, 21)
        ema_50 = self.calculate_ema(prices, 50)
        current_price = prices[-1]
        
        if ema_9 > ema_21 > ema_50:
            pullback_9 = abs(current_price - ema_9) / current_price
            pullback_21 = abs(current_price - ema_21) / current_price
            if pullback_9 < 0.0008:
                return "call", 85
            if pullback_21 < 0.001 and current_price > ema_21:
                return "call", 80
        
        if ema_9 < ema_21 < ema_50:
            pullback_9 = abs(current_price - ema_9) / current_price
            pullback_21 = abs(current_price - ema_21) / current_price
            if pullback_9 < 0.0008:
                return "put", 85
            if pullback_21 < 0.001 and current_price < ema_21:
                return "put", 80
        
        return None, 0


class Stochastic_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Stochastic + Trend"
        self.description = "Stochastic crossover with trend filter"
        self.win_rate_target = "78-83%"
    
    def calculate_stochastic(self, prices, k_period=14):
        if len(prices) < k_period:
            return 50, 50
        highest = max(prices[-k_period:])
        lowest = min(prices[-k_period:])
        if highest == lowest:
            return 50, 50
        k = 100 * (prices[-1] - lowest) / (highest - lowest)
        return k, k
    
    def get_signal(self):
        if len(self.price_history) < 20:
            return None, 0
        
        prices = list(self.price_history)
        ema_21 = self.calculate_ema(prices, 21)
        k, d = self.calculate_stochastic(prices)
        current_price = prices[-1]
        
        if k < 20 and current_price > ema_21:
            return "call", 75
        if k > 80 and current_price < ema_21:
            return "put", 75
        
        return None, 0


class Price_Action_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Price Action Scalping"
        self.description = "Pin bars, engulfing patterns with trend"
        self.win_rate_target = "82-87%"
    
    def get_signal(self):
        if len(self.price_history) < 10:
            return None, 0
        
        prices = list(self.price_history)
        ema_21 = self.calculate_ema(prices, 21)
        current_price = prices[-1]
        
        if len(prices) >= 3:
            prev_change = prices[-2] - prices[-3]
            curr_change = prices[-1] - prices[-2]
            
            if prev_change < 0 and curr_change > abs(prev_change) * 1.5:
                if current_price > ema_21:
                    return "call", 78
            if prev_change > 0 and abs(curr_change) > prev_change * 1.5:
                if current_price < ema_21:
                    return "put", 78
        
        return None, 0


class MACD_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "MACD Scalping"
        self.description = "MACD crossover with trend confirmation"
        self.win_rate_target = "80-85%"
    
    def calculate_macd(self, prices):
        if len(prices) < 26:
            return 0, 0, 0
        ema_12 = self.calculate_ema(prices, 12)
        ema_26 = self.calculate_ema(prices, 26)
        macd_line = ema_12 - ema_26
        signal_line = macd_line * 0.9
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def get_signal(self):
        if len(self.price_history) < 50:
            return None, 0
        
        prices = list(self.price_history)
        macd, signal, histogram = self.calculate_macd(prices)
        rsi = self.calculate_rsi(prices, 14)
        
        if macd > signal and histogram > 0 and 40 <= rsi <= 65:
            return "call", 75
        if macd < signal and histogram < 0 and 35 <= rsi <= 60:
            return "put", 75
        
        return None, 0


class Liquidity_Grab_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Liquidity Grab Scalping"
        self.description = "Stop hunt + reversal (Smart Money Concept)"
        self.win_rate_target = "83-88%"
    
    def get_signal(self):
        if len(self.price_history) < 30:
            return None, 0
        
        prices = list(self.price_history)
        current_price = prices[-1]
        recent_high = max(prices[-20:])
        recent_low = min(prices[-20:])
        
        if current_price < recent_low * 1.0003:
            if len(prices) >= 3 and prices[-1] > prices[-2]:
                return "call", 82
        if current_price > recent_high * 0.9997:
            if len(prices) >= 3 and prices[-1] < prices[-2]:
                return "put", 82
        
        return None, 0


class Tick_Scalping(ScalpingStrategyBase):
    def __init__(self):
        super().__init__()
        self.name = "Tick Scalping"
        self.description = "Quick tick momentum for 5-30 second trades"
        self.win_rate_target = "75-80%"
    
    def get_signal(self):
        if len(self.price_history) < 10:
            return None, 0
        
        prices = list(self.price_history)
        up_ticks = sum(1 for i in range(-6, 0) if prices[i] > prices[i-1])
        down_ticks = sum(1 for i in range(-6, 0) if prices[i] < prices[i-1])
        
        if up_ticks >= 5:
            return "call", 72
        if down_ticks >= 5:
            return "put", 72
        
        return None, 0


# ==================== ASSET LIST FOR SHUFFLE ====================
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


# ==================== MULTI-MARKET SCANNER (ADD-ON) ====================
class MultiMarketScanner:
    """Scans multiple markets simultaneously for signals"""
    
    def __init__(self):
        self.markets = {
            # OTC Markets (24/7)
            "AUDCAD_otc": [5, 10, 30, 60],
            "EURUSD_otc": [5, 10, 30, 60],
            "GBPUSD_otc": [5, 10, 30, 60],
            "USDJPY_otc": [5, 10, 30, 60],
            "AUDUSD_otc": [5, 10, 30, 60],
            "EURGBP_otc": [5, 10, 30, 60],
            # Live Markets
            "AUDCAD": [5, 10, 30, 60],
            "EURUSD": [5, 10, 30, 60],
        }
        self.price_cache = {}
        self.active_trades = []
    
    async def get_quick_prices(self, asset, count=30):
        """Quick price fetch"""
        try:
            candles = await client.get_candles(asset, None, 60, 5, use_cache=True)
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
        """Fast signal detection"""
        if len(prices) < 15:
            return None, 0
        
        current = prices[-1]
        
        # Simple momentum check
        momentum = sum(prices[i] - prices[i-1] for i in range(-5, 0))
        
        # RSI fast check
        changes = [prices[i] - prices[i-1] for i in range(-10, 0)]
        gains = sum(c for c in changes if c > 0)
        losses = sum(abs(c) for c in changes if c < 0)
        
        if losses == 0:
            rsi = 100
        else:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
        
        # Signal logic
        if momentum > 0.0001 and rsi < 65 and rsi > 30:
            return "call", min(abs(momentum) * 5000, 90)
        elif momentum < -0.0001 and rsi > 35 and rsi < 70:
            return "put", min(abs(momentum) * 5000, 90)
        
        return None, 0
    
    async def scan_all(self):
        """Scan all markets"""
        signals = []
        
        tasks = []
        for asset in self.markets:
            tasks.append(self.get_quick_prices(asset))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for asset, prices in zip(self.markets.keys(), results):
            if isinstance(prices, list) and len(prices) > 15:
                direction, strength = self.quick_signal_check(prices)
                
                if direction and strength >= 60:
                    # Find best timeframe
                    for tf in self.markets[asset]:
                        signals.append({
                            "asset": asset,
                            "timeframe": tf,
                            "direction": direction,
                            "strength": strength,
                            "price": prices[-1]
                        })
                        break  # One signal per asset
        
        # Sort by strength
        signals.sort(key=lambda x: x["strength"], reverse=True)
        return signals


# ==================== STRATEGY SELECTOR ====================
class StrategyManager:
    def __init__(self):
        self.strategies = {
            "1": EMA_RSI_Scalping(),
            "2": Bollinger_RSI_Scalping(),
            "3": VWAP_Scalping(),
            "4": Momentum_Scalping(),
            "5": Support_Resistance_Scalping(),
            "6": EMA_Pullback_Scalping(),
            "7": Stochastic_Scalping(),
            "8": Price_Action_Scalping(),
            "9": MACD_Scalping(),
            "10": Liquidity_Grab_Scalping(),
            "11": Tick_Scalping()
        }
        self.active_strategy = None
        self.strategy_stats = {}
    
    def show_strategies(self):
        print("\n" + "="*60)
        print("📊 AVAILABLE SCALPING STRATEGIES")
        print("="*60)
        print(f"{'#':<4} {'Strategy Name':<30} {'Win Rate':<12}")
        print("-"*60)
        for key, strategy in self.strategies.items():
            print(f"{key:<4} {strategy.name:<30} {strategy.win_rate_target:<12}")
        print("="*60)
    
    def select_strategy(self):
        self.show_strategies()
        while True:
            print("\n📋 Select 1-11 or 0 for random:")
            choice = input("👉 ").strip()
            if choice == '0':
                self.active_strategy = None
                return None
            elif choice in self.strategies:
                self.active_strategy = self.strategies[choice]
                print(f"✅ {self.active_strategy.name}")
                return self.active_strategy
            else:
                print("❌ Invalid!")


# ==================== MODE SELECTOR ====================
def select_trading_mode():
    """Choose between Single Asset, Multi-Market, and Shuffle Currencies"""
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


# ==================== CONNECT + ACCOUNT ====================
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


async def get_user_config():
    print("\n" + "="*50)
    print("📋 TRADING CONFIGURATION")
    print("="*50)
    
    account_type = select_account()
    
    # Mode selection
    trading_mode = select_trading_mode()
    
    strategy_manager = None
    if trading_mode in ["single", "shuffle"]:
        strategy_manager = StrategyManager()
        strategy_manager.select_strategy()
    
    print("\n" + "="*50)
    print("⚙️  PARAMETERS")
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
    print("="*50 + "\n")
    
    return max_trades, base_amount, stop_loss, stop_profit, strategy_manager, trading_mode


# ==================== MONEY MANAGEMENT (UPDATED) ====================
def get_next_amount_with_loss(base_amount, is_win, win_streak, loss_streak):
    """
    Money management rules:
    - Wins: 
        * 1st win in a row: amount = base * 1.5
        * 2nd consecutive win: reset to base (win_streak=0)
    - Losses:
        * 1st loss: amount = base * 2.4
        * 2nd & 3rd losses: keep amount = base * 2.4
        * 4th consecutive loss: reset to base, loss_streak=0
    """
    if is_win:
        win_streak += 1
        loss_streak = 0
        if win_streak >= 2:
            return base_amount, 0, 0
        else:
            return base_amount * 1.5, win_streak, 0
    else:
        loss_streak += 1
        win_streak = 0
        if loss_streak == 4:
            # Reset after 4 losses
            return base_amount, 0, 0
        else:
            # First, second, or third loss: use 2.4x multiplier
            return base_amount * 2.4, 0, loss_streak


def check_stop_limits(initial, current, sl, sp):
    pnl = current - initial
    if sp > 0 and pnl >= sp:
        return True, f"🎯 STOP PROFIT! +${pnl:.2f}"
    if sl > 0 and pnl <= -sl:
        return True, f"🛑 STOP LOSS! -${abs(pnl):.2f}"
    return False, ""


# ==================== TRADING FUNCTIONS ====================
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
            if (direction == "call" and current_price > open_price) or \
               (direction == "put" and current_price < open_price):
                return 'Win'
            elif (direction == "call" and current_price <= open_price) or \
                 (direction == "put" and current_price >= open_price):
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


# ==================== SINGLE ASSET MODE ====================
async def single_asset_mode(config):
    """Original single asset trading with updated money management"""
    max_trades, base_amount, stop_loss, stop_profit, strategy_manager, _ = config
    
    amount = base_amount
    asset = "AUDCAD"
    direction = "call"
    duration = 60
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    win_streak = 0
    loss_streak = 0
    
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
        
        if strategy_manager and strategy_manager.active_strategy:
            # Get price data for the strategy
            candles = await client.get_candles(asset_name, None, 60, 5, use_cache=True)
            if candles:
                prices = []
                for c in candles:
                    if isinstance(c, dict):
                        prices.append(float(c.get("close", 0)))
                    else:
                        prices.append(float(c))
                prices = [p for p in prices if p > 0]
                
                # Feed prices to strategy
                for price in prices:
                    strategy_manager.active_strategy.add_price(price)
                
                # Get signal
                sig_dir, sig_str = strategy_manager.active_strategy.get_signal()
                
                if sig_dir and sig_str >= 60:
                    direction = sig_dir
                    print(f"   📊 Signal: {sig_dir.upper()} ({sig_str:.0f}%) - {strategy_manager.active_strategy.name}")
                else:
                    print(f"   ⏳ No signal ({sig_str:.0f}%)")
                    await asyncio.sleep(3)
                    continue
            else:
                print("   ❌ Failed to get price data")
                await asyncio.sleep(3)
                continue
        
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | ${amount} | {direction.upper()} | Streak: W{win_streak} L{loss_streak}")
        
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
            amount, win_streak, loss_streak = get_next_amount_with_loss(base_amount, True, win_streak, loss_streak)
            if win_streak == 0:
                print(f"   🔄 2 WINS RESET → ${amount:.2f}")
            else:
                print(f"   📈 ×1.5 → ${amount:.2f}")
            continue
        
        if result == "Doji":
            print("   ⚪ DOJI")
            balance += amount
            continue
        
        total_losses += 1
        loss_amount = balance_before - balance
        total_loss_amount += loss_amount
        print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
        amount, win_streak, loss_streak = get_next_amount_with_loss(base_amount, False, win_streak, loss_streak)
        if loss_streak == 0:
            print(f"   🔄 4 LOSS RESET → ${amount:.2f}")
        elif loss_streak == 1:
            print(f"   📈 ×2.4 (first loss) → ${amount:.2f}")
        else:
            print(f"   📈 ×2.4 (loss #{loss_streak}) → ${amount:.2f}")
    
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount


# ==================== SHUFFLE MODE ====================
async def shuffle_mode(config):
    """Shuffle currencies mode: random asset each trade, full strategy analysis"""
    max_trades, base_amount, stop_loss, stop_profit, strategy_manager, _ = config
    
    amount = base_amount
    duration = 60
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    win_streak = 0
    loss_streak = 0
    
    print(f"\n🎲 SHUFFLE MODE | Balance: ${balance:.2f}")
    print(f"📋 Assets pool: {', '.join(SHUFFLE_ASSETS)}")
    print(f"🔀 Random asset each trade, full strategy analysis\n")
    
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
        
        # 🎲 PICK RANDOM ASSET
        asset = random.choice(SHUFFLE_ASSETS)
        print(f"\n{'='*80}")
        print(f"🎲 Shuffled Asset: {asset}")
        
        # Get asset info and check if open
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if not asset_data[2]:
            print(f"   ❌ {asset} is closed, skipping...")
            await asyncio.sleep(2)
            continue
        
        # Fetch price data for analysis
        candles = await client.get_candles(asset_name, None, 60, 5, use_cache=True)
        if not candles:
            print("   ❌ No candle data, skipping...")
            await asyncio.sleep(2)
            continue
        
        prices = []
        for c in candles:
            if isinstance(c, dict):
                prices.append(float(c.get("close", 0)))
            else:
                prices.append(float(c))
        prices = [p for p in prices if p > 0]
        
        if len(prices) < 50:
            print(f"   ⚠️  Only {len(prices)} data points, need more...")
            await asyncio.sleep(2)
            continue
        
        # Feed prices to strategy
        strat = strategy_manager.active_strategy if strategy_manager else None
        if strat:
            strat.price_history.clear()
            for price in prices:
                strat.add_price(price)
            
            sig_dir, sig_str = strat.get_signal()
        else:
            sig_dir, sig_str = None, 0
        
        # Quick analysis display
        rsi = strat.calculate_rsi(prices, 14) if strat else 50
        ema9 = strat.calculate_ema(prices, 9) if strat else prices[-1]
        trend = "BULLISH 📈" if prices[-1] > ema9 else "BEARISH 📉"
        print(f"   📊 Analysis: Price={prices[-1]:.5f} | RSI={rsi:.1f} | EMA9={ema9:.5f} | Trend={trend}")
        
        if sig_dir and sig_str >= 60:
            direction = sig_dir
            print(f"   🎯 SIGNAL: {sig_dir.upper()} ({sig_str:.0f}%) - {strat.name if strat else ''}")
        else:
            print(f"   ⏳ No valid signal ({sig_str:.0f}% strength)")
            await asyncio.sleep(2)
            continue
        
        # Execute trade
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | ${amount} | {direction.upper()} | {asset} | Streak: W{win_streak} L{loss_streak}")
        
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
            amount, win_streak, loss_streak = get_next_amount_with_loss(base_amount, True, win_streak, loss_streak)
            if win_streak == 0:
                print(f"   🔄 2 WINS RESET → ${amount:.2f}")
            else:
                print(f"   📈 ×1.5 → ${amount:.2f}")
        elif result == "Doji":
            print("   ⚪ DOJI")
            balance += amount
        else:
            total_losses += 1
            loss_amount = balance_before - balance
            total_loss_amount += loss_amount
            print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f} | {total_wins}W/{total_losses}L")
            amount, win_streak, loss_streak = get_next_amount_with_loss(base_amount, False, win_streak, loss_streak)
            if loss_streak == 0:
                print(f"   🔄 4 LOSS RESET → ${amount:.2f}")
            elif loss_streak == 1:
                print(f"   📈 ×2.4 (first loss) → ${amount:.2f}")
            else:
                print(f"   📈 ×2.4 (loss #{loss_streak}) → ${amount:.2f}")
        
        await asyncio.sleep(1)
    
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount


# ==================== MULTI-MARKET MODE ====================
async def multi_market_mode(config):
    """Multi-market scanning & trading"""
    max_trades, base_amount, stop_loss, stop_profit, _, _ = config
    
    scanner = MultiMarketScanner()
    balance = await client.get_balance()
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    active_tasks = set()
    
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
            
            # Scan all markets
            signals = await scanner.scan_all()
            
            if signals:
                print(f"\n🔍 Found {len(signals)} signals:")
                for i, sig in enumerate(signals[:5], 1):
                    emoji = "🟢" if sig["direction"] == "call" else "🔴"
                    print(f"  {i}. {sig['asset']:<15} {sig['timeframe']}s {emoji} {sig['direction']:<4} {sig['strength']:.0f}%")
                
                # Execute top signals
                for signal in signals[:3]:
                    active_count = len([t for t in active_tasks if not t.done()])
                    if active_count >= 5:
                        break
                    
                    if balance < base_amount:
                        print("❌ Low balance!")
                        break
                    
                    # Create trade
                    task = asyncio.create_task(
                        execute_multi_trade(signal, base_amount, scanner)
                    )
                    active_tasks.add(task)
                    trade_count += 1
            else:
                print("⏳ No signals...")
            
            # Check completed trades
            done = {t for t in active_tasks if t.done()}
            for task in done:
                try:
                    result = await task
                    if result:
                        if result["win"]:
                            total_wins += 1
                            total_profit += result.get("profit", 0)
                            balance += result.get("profit", 0)
                        else:
                            total_losses += 1
                            loss = result.get("loss", base_amount)
                            total_loss_amount += loss
                except:
                    pass
                active_tasks.remove(task)
            
            active = len([t for t in active_tasks if not t.done()])
            print(f"📊 Running: {active} | {total_wins}W/{total_losses}L | Bal: ${balance:.2f}")
            await asyncio.sleep(2)
    
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
        for task in active_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*active_tasks, return_exceptions=True)
    
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount


async def execute_multi_trade(signal, base_amount, scanner):
    """Execute one multi-market trade"""
    asset = signal["asset"]
    direction = signal["direction"]
    duration = signal["timeframe"]
    
    print(f"\n🔴 {asset} | {direction.upper()} | {duration}s | ${base_amount}")
    
    try:
        status, buy_info = await client.buy(base_amount, asset, direction, duration)
        
        if not status:
            return None
        
        await asyncio.sleep(duration + 2)
        
        if buy_info and "id" in buy_info:
            win_status, profit = await client.check_win(buy_info["id"])
            if win_status == "win":
                print(f"   ✅ WIN! +${profit:.2f}")
                return {"win": True, "profit": profit}
            else:
                print(f"   ❌ LOSS! -${base_amount:.2f}")
                return {"win": False, "loss": base_amount}
        
        return None
    except:
        return None


# ==================== MAIN ====================
async def trade_and_monitor():
    config = await get_user_config()
    
    if config is None:
        await cleanup()
        return
    
    _, _, _, _, _, trading_mode = config
    
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
