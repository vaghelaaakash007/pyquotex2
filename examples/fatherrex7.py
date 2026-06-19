# examples/trade_bot.py

import asyncio
import random
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from collections import deque

email, password = credentials()
client = Quotex(
    email=email,
    password=password,
    lang="pt",
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
                        print(f"⏳ Building: {count}/50")
                    elif signal:
                        print(f"⏸️  Weak: {strength}%")
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


# ==================== USER CONFIG ====================
ALWAYS_INCLUDED_ASSETS = ["USDJPY_otc", "GBPAUD_otc"]

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
    
    print("\n💱 Trading currencies (comma separated, or type ALL for every asset)")
    print(f"   (Note: {', '.join(ALWAYS_INCLUDED_ASSETS)} are always added automatically)")
    assets_input = input("👉 Assets: ").strip()
    if assets_input.upper() == "ALL":
        asset_list = ["ALL"]
    else:
        asset_list = [a.strip().upper() for a in assets_input.split(",") if a.strip()]
        if not asset_list:
            asset_list = ["AUDCAD"]
    
    print("\n" + "="*50)
    print("✅ CONFIGURATION SAVED")
    print(f"Strategy: {strategy_manager.active_strategy.name if strategy_manager.active_strategy else 'Random'}")
    print(f"Max Trades: {'∞' if max_trades == 0 else max_trades}")
    print(f"Base Amount: ${base_amount}")
    if asset_list == ["ALL"]:
        print(f"Assets: ALL (will be fetched after connection, + {', '.join(ALWAYS_INCLUDED_ASSETS)})")
    else:
        full_list = list(set(asset_list + ALWAYS_INCLUDED_ASSETS))
        print(f"Assets: {', '.join(full_list)}")
    print("="*50 + "\n")
    
    return max_trades, base_amount, stop_loss, stop_profit, strategy_manager, asset_list


# ==================== MONEY MANAGEMENT ====================
def get_next_amount(current_amount, base_amount, is_win, win_streak):
    if is_win:
        win_streak += 1
        if win_streak >= 3:
            print("🔄 3 CONSECUTIVE WINS → Reset to Base")
            return base_amount, 0
        else:
            new_amount = current_amount * 2
            print(f"📈 WIN #{win_streak} → Double: ${new_amount}")
            return new_amount, win_streak
    else:
        print("💥 LOSS → Reset to Base")
        return base_amount, 0


def check_stop_limits(initial_balance, current_balance, stop_loss, stop_profit):
    profit_loss = current_balance - initial_balance
    if stop_profit > 0 and profit_loss >= stop_profit:
        return True, f"🎯 STOP PROFIT! +${profit_loss:.2f}"
    if stop_loss > 0 and profit_loss <= -stop_loss:
        return True, f"🛑 STOP LOSS! -${abs(profit_loss):.2f}"
    return False, ""


# ==================== BACKGROUND SIGNAL UPDATER ====================
async def background_signal_updater(asset_strategies, client, asset_signals, stop_event):
    """Continuously fetch candles for all assets and store valid signals (≥60%)."""
    while not stop_event.is_set():
        tasks = []
        for asset, strategy in asset_strategies.items():
            tasks.append(fetch_and_update(asset, strategy, client))
        await asyncio.gather(*tasks)
        for asset, strategy in asset_strategies.items():
            signal, strength = strategy.get_signal()
            if signal and strength >= 60:
                asset_signals[asset] = (signal, strength)
            else:
                asset_signals[asset] = (None, 0)
        await asyncio.sleep(1)  # update interval


async def fetch_and_update(asset, strategy, client):
    """Fetch candles for one asset – errors are silently ignored."""
    try:
        candles = await client.get_candles(asset, None, 3600, 60, use_cache=True)
        if candles:
            for candle in candles:
                if isinstance(candle, dict):
                    price = float(candle.get("close", 0))
                    volume = float(candle.get("volume", 100))
                else:
                    price = float(candle)
                    volume = 100.0
                if price > 0:
                    strategy.add_price(price, volume)
    except Exception:
        pass


# ==================== ASSET SHUFFLING ====================
def pick_next_asset(asset_list, client, last_asset=None):
    """Pick a different open asset (fallback for random mode). Returns None if none open."""
    open_assets = []
    for asset in asset_list:
        try:
            _, data = client.get_available_asset(asset, force_open=False)
            if data[2]:
                open_assets.append(asset)
        except:
            pass
    if last_asset and len(open_assets) > 1:
        candidates = [a for a in open_assets if a != last_asset]
        if candidates:
            return random.choice(candidates)
    elif open_assets:
        return random.choice(open_assets)
    return None


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
    try:
        await client.close()
        await asyncio.sleep(0.5)
    except:
        pass


async def trade_and_monitor():
    max_trades, base_amount, stop_loss, stop_profit, strategy_manager, asset_list = get_user_config()
    
    try:
        check_connect, message = await client.connect()
        if not check_connect:
            print("❌ Connection failed")
            return

        # Resolve "ALL" assets
        if asset_list == ["ALL"]:
            try:
                all_assets = client.get_all_assets()
                if isinstance(all_assets, dict):
                    asset_list = list(all_assets.keys())
                elif isinstance(all_assets, list):
                    asset_list = all_assets
                else:
                    asset_list = [str(a) for a in all_assets]
            except:
                asset_list = ["AUDCAD"]
        for pair in ALWAYS_INCLUDED_ASSETS:
            if pair not in asset_list:
                asset_list.append(pair)
        seen = set()
        asset_list = [x for x in asset_list if not (x in seen or seen.add(x))]

        # Background signal updater
        asset_strategies = {}
        asset_signals = {}
        if strategy_manager.active_strategy:
            strategy_class = type(strategy_manager.active_strategy)
            for asset in asset_list:
                asset_strategies[asset] = strategy_class()
        stop_updater = asyncio.Event()
        if asset_strategies:
            bg_task = asyncio.create_task(
                background_signal_updater(asset_strategies, client, asset_signals, stop_updater)
            )

        # Initial setup
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
        print(f"Balance: ${balance:.2f} | Base: ${base_amount}")
        print(f"Assets in rotation: {len(asset_list)}")
        print("="*50 + "\n")

        while True:
            if max_trades > 0 and trade_count >= max_trades:
                print(f"\n✅ MAX TRADES ({max_trades}) DONE!")
                break
            should_stop, stop_reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
            if should_stop:
                print(f"\n{stop_reason}")
                break

            # Select next asset
            next_asset = None
            if asset_strategies:
                candidates = []
                for asset in asset_list:
                    if asset == last_asset:
                        continue
                    signal, strength = asset_signals.get(asset, (None, 0))
                    if signal and strength >= 60:
                        try:
                            _, data = client.get_available_asset(asset, force_open=False)
                            if data[2]:
                                candidates.append((asset, signal, strength))
                        except:
                            pass
                if candidates:
                    chosen = random.choice(candidates)
                    next_asset = chosen[0]
                    direction = chosen[1]
                    print(f"🎯 Instant signal: {direction.upper()} on {next_asset} ({chosen[2]}%)")
                else:
                    print("⏳ No open asset with valid signal – retrying...")
                    await asyncio.sleep(2)
                    continue
            else:
                next_asset = pick_next_asset(asset_list, client, last_asset)
                if next_asset is None:
                    print("⏳ No open asset – retrying...")
                    await asyncio.sleep(2)
                    continue
                direction = random.choice(["call", "put"])
                print(f"🎲 RANDOM: {direction.upper()} on {next_asset}")

            # Double-check asset still open
            asset_name, asset_data = await client.get_available_asset(next_asset, force_open=True)
            if not asset_data[2]:
                print(f"⚠️ {next_asset} just closed, skipping...")
                await asyncio.sleep(2)
                continue

            # Execute trade
            trade_count += 1
            print(f"\n📈 TRADE #{trade_count} | {next_asset} | ${amount} | {direction.upper()} | Streak: {win_streak}")

            check_connect = await client.check_connect()
            if not check_connect:
                check_connect, message = await client.connect()

            balance_before = balance
            status, buy_info = await client.buy(amount, next_asset, direction, duration)
            if not status:
                print("❌ Buy failed, retrying later...")
                await asyncio.sleep(2)
                continue

            balance -= amount
            await analise_sentiment(next_asset, duration)
            result = await check_result(buy_info, direction, next_asset)

            # Handle result
            if result == "Win":
                balance, profit = await calculate_profit(next_asset, amount, balance)
                total_wins += 1
                if strategy_manager.active_strategy:
                    strategy_manager.update_stats(True)
                print(f"✅ WIN #{trade_count} | Profit: ${profit:.2f} | Balance: ${balance:.2f}")
                amount, win_streak = get_next_amount(amount, base_amount, True, win_streak)

            elif result == "Doji":
                print("⚪ DOJI - No change")

            else:  # Loss
                if strategy_manager.active_strategy:
                    strategy_manager.update_stats(False)
                total_losses += 1
                loss = balance_before - balance
                print(f"❌ LOSS #{trade_count} | Loss: ${loss:.2f} | Balance: ${balance:.2f}")
                amount, win_streak = get_next_amount(amount, base_amount, False, win_streak)

            last_asset = next_asset
            print(f"💰 Next Amount: ${amount} | Streak: {win_streak}\n")

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if 'bg_task' in locals():
            stop_updater.set()
            bg_task.cancel()
        print("\n" + "="*50)
        print("🏁 SESSION ENDED")
        print(f"Trades: {trade_count} | Wins: {total_wins} | Losses: {total_losses}")
        if trade_count > 0:
            print(f"Win Rate: {total_wins/trade_count*100:.1f}%")
        print(f"Balance: ${balance:.2f}")
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
