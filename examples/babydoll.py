# examples/trade_bot.py

import asyncio
import signal
import random
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from collections import deque

email, password = credentials()

# ==================== ACCOUNT TYPE SELECTION ====================
print("\n" + "="*50)
print("🔐 ACCOUNT TYPE SELECTION")
print("="*50)
print("1 - Real Account")
print("2 - Demo Account")
account_choice = input("Enter 1 or 2: ").strip()
is_demo = (account_choice == "2")   # Default to Real if invalid
account_type_str = "Demo" if is_demo else "Real"
print(f"✅ Selected: {account_type_str} account")
print("="*50 + "\n")

client = Quotex(
    email=email,
    password=password,
    lang="pt",
    is_demo=is_demo
)

# ==================== STRATEGY COLLECTION ====================
class ScalpingStrategyBase:
    """Base class for all scalping strategies"""
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
            print("\n📋 OPTIONS:")
            print("  • 1-11 = Select strategy")
            print("  • info 1 = Strategy details")
            print("  • compare = Compare all")
            print("  • 0 = Random signals")
            
            choice = input("\n👉 Choice: ").strip().lower()
            
            if choice == '0':
                self.active_strategy = None
                print("✅ Random signals mode")
                return None
            
            elif choice.startswith('info'):
                parts = choice.split()
                if len(parts) == 2 and parts[1] in self.strategies:
                    s = self.strategies[parts[1]]
                    print(f"\n📖 {s.name}\n   {s.description}\n   Target: {s.win_rate_target}")
                else:
                    print("❌ Invalid!")
            
            elif choice == 'compare':
                print("\n📊 COMPARISON:")
                for k, s in self.strategies.items():
                    print(f"  {k}. {s.name} - {s.win_rate_target}")
            
            elif choice in self.strategies:
                self.active_strategy = self.strategies[choice]
                print(f"\n✅ SELECTED: {self.active_strategy.name}")
                self.strategy_stats = {"signals": 0, "wins": 0, "losses": 0, "calls": 0, "puts": 0}
                return self.active_strategy
            else:
                print("❌ Invalid!")
    
    async def get_signal(self, asset_name, client):
        if not self.active_strategy:
            direction = random.choice(["call", "put"])
            print(f"🎲 RANDOM: {direction.upper()}")
            return direction, 50
        
        try:
            candles = await client.get_candles(asset_name, None, 3600, 60, use_cache=True)
            
            if candles and len(candles) > 0:
                for candle in candles:
                    if isinstance(candle, dict):
                        price = float(candle.get("close", 0))
                        volume = float(candle.get("volume", 100))
                    else:
                        price = float(candle)
                        volume = 100.0
                    if price > 0:
                        self.active_strategy.add_price(price, volume)
                
                signal, strength = self.active_strategy.get_signal()
                
                if signal and strength >= 60:
                    self.strategy_stats["signals"] += 1
                    if signal == "call":
                        self.strategy_stats["calls"] += 1
                    else:
                        self.strategy_stats["puts"] += 1
                    print(f"🎯 {signal.upper()} | {strength}%")
                    return signal, strength
                else:
                    count = len(self.active_strategy.price_history)
                    if count < 50:
                        print(f"⏳ Building candle history: {count}/50")
                    elif signal:
                        print(f"⏸️  Weak signal: {strength}% (need ≥60%)")
                    else:
                        print(f"📊 No signal yet for {asset_name}")
        except Exception as e:
            print(f"⚠️  {e}")
        
        return None, 0
    
    def update_stats(self, is_win):
        if is_win:
            self.strategy_stats["wins"] += 1
        else:
            self.strategy_stats["losses"] += 1
    
    def show_performance(self):
        if not self.active_strategy:
            return
        stats = self.strategy_stats
        if stats["signals"] > 0:
            wr = (stats["wins"] / stats["signals"]) * 100
            print(f"\n📊 {self.active_strategy.name}")
            print(f"   Signals: {stats['signals']} ({stats.get('calls',0)}C/{stats.get('puts',0)}P)")
            print(f"   Wins: {stats['wins']} | Losses: {stats['losses']}")
            print(f"   Win Rate: {wr:.1f}%")


# ==================== ASSET SELECTION (with live payouts) ====================
async def get_asset_selection(client):
    """Present a menu of predefined assets with live payouts and return selected list."""
    predefined_assets = ["USDBDT_otc", "USDBRL_otc", "USDJPY_otc", "AUDUSD_otc"]
    print("\n" + "="*50)
    print("💱 ASSET SELECTION")
    print("="*50)
    
    # Fetch payouts for each asset
    payouts = {}
    for asset in predefined_assets:
        try:
            payout = client.get_payout_by_asset(asset)
            payouts[asset] = payout if payout is not None else "N/A"
        except:
            payouts[asset] = "N/A"
    
    # Display menu
    for idx, asset in enumerate(predefined_assets, start=1):
        payout_str = f"{payouts[asset]}%" if payouts[asset] != "N/A" else "N/A"
        print(f"{idx}. {asset} (Payout: {payout_str})")
    print("5. ALL (all available assets)")
    
    choice = input("\n👉 Enter your choice (1-5, or comma-separated like 1,2,3): ").strip()
    
    if choice.upper() == "ALL" or choice == "5":
        return ["ALL"]
    else:
        # Split by comma
        parts = [p.strip() for p in choice.split(',') if p.strip()]
        selected = []
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(predefined_assets):
                    selected.append(predefined_assets[idx-1])
        if not selected:
            print("⚠️ Invalid selection. Defaulting to ALL.")
            return ["ALL"]
        return selected


# ==================== USER CONFIG (strategy, limits, money) ====================
def get_user_config():
    print("\n" + "="*50)
    print("📋 TRADING CONFIGURATION")
    print("="*50)
    
    strategy_manager = StrategyManager()
    strategy_manager.select_strategy()
    
    max_trades = int(input("\n🔄 Max trades (0=infinite): "))
    base_amount = float(input("💰 Base amount: $"))
    stop_loss = float(input("🛑 Stop Loss (0=off): $"))
    stop_profit = float(input("🎯 Stop Profit (0=off): $"))
    
    print("\n" + "="*50)
    print("✅ CONFIGURATION SAVED")
    print(f"Strategy: {strategy_manager.active_strategy.name if strategy_manager.active_strategy else 'Random'}")
    print(f"Max Trades: {'∞' if max_trades == 0 else max_trades}")
    print(f"Base Amount: ${base_amount}")
    print("="*50 + "\n")
    
    return max_trades, base_amount, stop_loss, stop_profit, strategy_manager


# ==================== MONEY MANAGEMENT ====================
def get_next_amount(current_amount, base_amount, is_win, win_streak):
    """
    WIN  -> Double amount
    LOSS -> Reset to base amount
    If 3 consecutive wins -> Reset amount to base amount
    """
    if is_win:
        win_streak += 1
        
        if win_streak >= 3:
            print("🔄 3 CONSECUTIVE WINS → Reset to Base")
            return base_amount, 0  # Reset amount AND win streak
        else:
            new_amount = current_amount * 2
            print(f"📈 WIN #{win_streak} → Double: ${new_amount}")
            return new_amount, win_streak
    else:
        print("💥 LOSS → Reset to Base")
        return base_amount, 0  # Reset amount AND win streak


def check_stop_limits(initial_balance, current_balance, stop_loss, stop_profit):
    profit_loss = current_balance - initial_balance
    
    if stop_profit > 0 and profit_loss >= stop_profit:
        return True, f"🎯 STOP PROFIT! +${profit_loss:.2f}"
    if stop_loss > 0 and profit_loss <= -stop_loss:
        return True, f"🛑 STOP LOSS! -${abs(profit_loss):.2f}"
    
    return False, ""


# ==================== ASSET SHUFFLING ====================
def pick_next_asset(asset_list, client, last_asset=None):
    """
    Pick a different open asset than the last one (if possible).
    If only one asset is available, return that one.
    """
    open_assets = []
    for asset in asset_list:
        try:
            name, data = client.get_available_asset(asset, force_open=False)
            if data[2]:   # index 2 = is_open
                open_assets.append(asset)
        except:
            pass

    if last_asset and len(open_assets) > 1:
        candidates = [a for a in open_assets if a != last_asset]
        if candidates:
            return random.choice(candidates)
    elif open_assets:
        return random.choice(open_assets)
    
    # Fallback: if nothing open, return any from the list (will be skipped later)
    return random.choice(asset_list) if asset_list else "AUDCAD"


# ==================== TRADING FUNCTIONS ====================

async def analise_sentiment(asset_name, duration):
    count = duration
    while count > 0:
        market_mood = await client.get_realtime_sentiment(asset_name)
        sentiment = market_mood.get('sentiment')
        if sentiment:
            print(f"\rSell: {sentiment.get('sell')} Buy: {sentiment.get('buy')}", end="")
        await asyncio.sleep(0.5)
        count -= 1


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
            print(f"💰 Current: {current_price} | Open: {open_price}")

            if (direction == "call" and current_price > open_price) or \
               (direction == "put" and current_price < open_price):
                return 'Win'
            elif (direction == "call" and current_price <= open_price) or \
                 (direction == "put" and current_price >= open_price):
                return 'Loss'
            else:
                return 'Doji'
                
        except Exception as e:
            print(f"⚠️  {e}")
            await asyncio.sleep(1)


async def cleanup():
    """Properly close all connections"""
    try:
        await client.close()
        await asyncio.sleep(0.5)
    except:
        pass


async def trade_and_monitor():
    # ===== CONNECT FIRST =====
    check_connect, message = await client.connect()
    if not check_connect:
        print("❌ Connection failed")
        return
    
    # ===== ASSET SELECTION (with live payouts) =====
    asset_list = await get_asset_selection(client)
    
    # ===== RESOLVE "ALL" =====
    if asset_list == ["ALL"]:
        try:
            all_assets = client.get_all_assets()
            if isinstance(all_assets, dict):
                asset_list = list(all_assets.keys())
            elif isinstance(all_assets, list):
                asset_list = all_assets
            else:
                asset_list = [str(a) for a in all_assets]
        except Exception as e:
            print(f"⚠️ Could not fetch all assets: {e}, falling back to predefined list")
            asset_list = ["USDBDT_otc", "USDBRL_otc", "USDJPY_otc", "AUDUSD_otc"]
    
    # Remove duplicates while preserving order
    seen = set()
    asset_list = [x for x in asset_list if not (x in seen or seen.add(x))]
    
    # ===== CONFIGURATION (strategy, limits, money) =====
    max_trades, base_amount, stop_loss, stop_profit, strategy_manager = get_user_config()
    
    try:
        # ===== INITIAL SETUP =====
        amount = base_amount
        direction = "call"
        duration = 60
        balance = await client.get_balance()
        initial_balance = balance
        
        trade_count = 0
        total_wins = 0
        total_losses = 0
        win_streak = 0
        
        last_asset = None
        
        print("\n" + "="*50)
        print("📊 SESSION STARTED")
        print("="*50)
        print(f"Balance: ${balance:.2f}")
        print(f"Base Amount: ${base_amount}")
        print(f"Current Amount: ${amount}")
        print(f"Win Streak: {win_streak}")
        print(f"Assets in rotation: {len(asset_list)}")
        print("="*50 + "\n")

        while True:
            # ===== CHECK LIMITS =====
            if max_trades > 0 and trade_count >= max_trades:
                print(f"\n✅ MAX TRADES ({max_trades}) DONE!")
                break
            
            should_stop, stop_reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
            if should_stop:
                print(f"\n{stop_reason}")
                break
            
            print(f"{'='*100}")
            
            # ===== PICK A NEW ASSET (different from last) =====
            current_asset = pick_next_asset(asset_list, client, last_asset)
            
            # Reset strategy history if the asset changed
            if current_asset != last_asset and strategy_manager.active_strategy:
                strategy_manager.active_strategy.price_history.clear()
                strategy_manager.active_strategy.volume_history.clear()
                print(f"🔄 Switching to {current_asset} – history reset")
            else:
                print(f"🔄 Using {current_asset} again (only available asset)")
            
            last_asset = current_asset
            
            # ===== GET SIGNAL =====
            if strategy_manager.active_strategy:
                signal_direction, signal_strength = await strategy_manager.get_signal(current_asset, client)
                if signal_direction and signal_strength >= 60:
                    direction = signal_direction
                else:
                    print(f"⏩ Skipping trade – waiting for valid signal on {current_asset}\n")
                    await asyncio.sleep(3)
                    continue
            else:
                # Random mode – always generate a signal
                direction = random.choice(["call", "put"])
                print(f"🎲 RANDOM direction: {direction.upper()}")
            
            # ===== EXECUTE TRADE =====
            trade_count += 1
            print(f"\n📈 TRADE #{trade_count}")
            print(f"   Asset: {current_asset} | Amount: ${amount} | Direction: {direction.upper()}")
            print(f"   Win Streak: {win_streak}")
            
            # Verify asset still open
            asset_name, asset_data = await client.get_available_asset(current_asset, force_open=True)
            if not asset_data[2]:
                print(f"⚠️ {current_asset} is now closed, skipping...")
                await asyncio.sleep(2)
                continue
            
            check_connect = await client.check_connect()
            if not check_connect:
                check_connect, message = await client.connect()

            balance_before = balance
            status, buy_info = await client.buy(amount, asset_name, direction, duration)
            
            if status:
                balance -= amount
                await analise_sentiment(asset_name, duration)
                result = await check_result(buy_info, direction, asset_name)

                # ===== WIN CASE =====
                if result == "Win":
                    balance, profit = await calculate_profit(asset_name, amount, balance)
                    total_wins += 1
                    
                    if strategy_manager.active_strategy:
                        strategy_manager.update_stats(True)
                    
                    print(f"\n{'─'*50}")
                    print(f"✅ WIN #{trade_count}")
                    print(f"   Profit: ${profit:.2f}")
                    print(f"   Balance: ${balance:.2f}")
                    print(f"   P/L: ${balance - initial_balance:.2f}")
                    print(f"   Wins: {total_wins} | Losses: {total_losses}")
                    if trade_count > 0:
                        print(f"   Win Rate: {total_wins/trade_count*100:.1f}%")
                    print(f"{'─'*50}")
                    
                    # ===== UPDATE AMOUNT & WIN STREAK =====
                    amount, win_streak = get_next_amount(amount, base_amount, True, win_streak)
                    print(f"💰 Next Amount: ${amount} | Streak: {win_streak}")

                # ===== DOJI CASE =====
                elif result == "Doji":
                    print("⚪ DOJI - No change (asset will switch anyway)")

                # ===== LOSS CASE (NO MARTINGALE) =====
                else:
                    if strategy_manager.active_strategy:
                        strategy_manager.update_stats(False)
                    
                    total_losses += 1
                    loss = balance_before - balance
                    
                    print(f"\n{'─'*50}")
                    print(f"❌ LOSS #{trade_count}")
                    print(f"   Loss: ${loss:.2f}")
                    print(f"   Balance: ${balance:.2f}")
                    print(f"   P/L: ${balance - initial_balance:.2f}")
                    print(f"   Wins: {total_wins} | Losses: {total_losses}")
                    if trade_count > 0:
                        print(f"   Win Rate: {total_wins/trade_count*100:.1f}%")
                    print(f"{'─'*50}")
                    
                    # ===== RESET AMOUNT & WIN STREAK ON LOSS =====
                    amount, win_streak = get_next_amount(amount, base_amount, False, win_streak)
                    print(f"💰 Next Amount: ${amount} | Streak: {win_streak}")

            else:
                print("❌ Buy failed (will try next signal)")
                await asyncio.sleep(2)

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("\n" + "="*50)
        print("🏁 SESSION ENDED")
        print("="*50)
        print(f"Trades: {trade_count}")
        print(f"Wins: {total_wins} | Losses: {total_losses}")
        if trade_count > 0:
            print(f"Win Rate: {total_wins/trade_count*100:.1f}%")
        print(f"Balance: ${balance:.2f}")
        print(f"P/L: ${balance - initial_balance:.2f}")
        
        if strategy_manager.active_strategy:
            strategy_manager.show_performance()
        print("="*50)
        
        await cleanup()


async def main():
    try:
        await trade_and_monitor()
    finally:
        await cleanup()
        pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Closed")
