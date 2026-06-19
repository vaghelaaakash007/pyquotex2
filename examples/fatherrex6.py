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


# (All strategy classes remain identical – only the base class is shown for brevity,
#  but the full code includes EMA_RSI_Scalping, Bollinger_RSI_Scalping, etc.
#  They are unchanged from your original file.)

# ==================== STRATEGY SELECTOR ====================
class StrategyManager:
    # ... (unchanged, exactly as in your previous version)
    pass

# ==================== USER CONFIG ====================
ALWAYS_INCLUDED_ASSETS = ["USDJPY_otc", "GBPAUD_otc"]

def get_user_config():
    # ... (unchanged, returns max_trades, base_amount, stop_loss, stop_profit, strategy_manager, asset_list)
    pass

# ==================== MONEY MANAGEMENT ====================
def get_next_amount(current_amount, base_amount, is_win, win_streak):
    # ... (unchanged)
    pass

def check_stop_limits(initial_balance, current_balance, stop_loss, stop_profit):
    # ... (unchanged)
    pass

# ==================== BACKGROUND SIGNAL UPDATER ====================
async def background_signal_updater(asset_strategies, client, asset_signals, stop_event):
    """Continuously update price histories and compute signals for all assets."""
    while not stop_event.is_set():
        try:
            # Fetch candles for all assets concurrently
            tasks = []
            for asset, strategy in asset_strategies.items():
                tasks.append(fetch_and_update(asset, strategy, client))
            await asyncio.gather(*tasks)

            # Compute signals and store them
            for asset, strategy in asset_strategies.items():
                signal, strength = strategy.get_signal()
                if signal and strength >= 60:
                    asset_signals[asset] = (signal, strength)
                else:
                    asset_signals[asset] = (None, 0)

        except Exception as e:
            print(f"⚠️ Background updater error: {e}")
        await asyncio.sleep(1)  # Adjust interval as needed


async def fetch_and_update(asset, strategy, client):
    """Fetch candles for one asset and feed them to the strategy."""
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
    except Exception as e:
        # Silently ignore; the asset might be temporarily unavailable
        pass


# ==================== TRADING FUNCTIONS ====================
async def analise_sentiment(asset_name, duration):
    # ... (unchanged)
    pass

async def calculate_profit(asset_name, amount, balance):
    # ... (unchanged)
    pass

async def check_result(buy_data, direction, asset_name=None):
    # ... (unchanged)
    pass

async def cleanup():
    # ... (unchanged)
    pass


async def trade_and_monitor():
    max_trades, base_amount, stop_loss, stop_profit, strategy_manager, asset_list = get_user_config()
    
    try:
        check_connect, message = await client.connect()
        if check_connect:
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
            # Add always-included pairs
            for pair in ALWAYS_INCLUDED_ASSETS:
                if pair not in asset_list:
                    asset_list.append(pair)
            # Remove duplicates
            seen = set()
            asset_list = [x for x in asset_list if not (x in seen or seen.add(x))]

            # ===== BACKGROUND PREPARATION =====
            # Create a strategy instance for each asset (if a strategy is selected)
            asset_strategies = {}
            asset_signals = {}   # will hold (direction, strength) for each asset
            if strategy_manager.active_strategy:
                strategy_class = type(strategy_manager.active_strategy)
                for asset in asset_list:
                    asset_strategies[asset] = strategy_class()
            else:
                # Random mode – no pre-fetching needed
                pass

            # Start background signal updater
            stop_updater = asyncio.Event()
            if asset_strategies:
                bg_task = asyncio.create_task(
                    background_signal_updater(asset_strategies, client, asset_signals, stop_updater)
                )

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
            print(f"Assets in rotation: {len(asset_list)}")
            print("="*50 + "\n")

            while True:
                # Check trade limits
                if max_trades > 0 and trade_count >= max_trades:
                    print(f"\n✅ MAX TRADES ({max_trades}) DONE!")
                    break
                should_stop, stop_reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
                if should_stop:
                    print(f"\n{stop_reason}")
                    break

                # ===== SELECT NEXT ASSET (with instant signal) =====
                next_asset = None
                if asset_strategies:
                    # Pick from assets that have a valid signal (≥60%), not the last asset, and open
                    candidates = []
                    for asset in asset_list:
                        if asset == last_asset:
                            continue
                        signal, strength = asset_signals.get(asset, (None, 0))
                        if signal and strength >= 60:
                            # Verify asset is open (quick check)
                            try:
                                _, data = client.get_available_asset(asset, force_open=False)
                                if data[2]:
                                    candidates.append((asset, signal, strength))
                            except:
                                pass
                    if candidates:
                        # Choose one randomly
                        chosen = random.choice(candidates)
                        next_asset = chosen[0]
                        direction = chosen[1]
                        print(f"🎯 Instant signal: {direction.upper()} on {next_asset} ({chosen[2]}%)")
                    else:
                        # No valid signal yet – wait and retry
                        print(f"⏳ Waiting for a valid signal on any asset...")
                        await asyncio.sleep(2)
                        continue
                else:
                    # Random mode – pick a different open asset
                    next_asset = pick_next_asset(asset_list, client, last_asset)
                    direction = random.choice(["call", "put"])
                    print(f"🎲 RANDOM: {direction.upper()} on {next_asset}")

                # Safety check: asset must be open
                asset_name, asset_data = await client.get_available_asset(next_asset, force_open=True)
                if not asset_data[2]:
                    print(f"⚠️ {next_asset} is closed, skipping...")
                    await asyncio.sleep(2)
                    continue

                # ===== EXECUTE TRADE =====
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

                # ===== HANDLE RESULT =====
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

                last_asset = next_asset   # ensures next trade uses a different one
                print(f"💰 Next Amount: ${amount} | Streak: {win_streak}\n")

        else:
            print("❌ Connection failed")

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


def pick_next_asset(asset_list, client, last_asset=None):
    """Fallback for random mode – pick a different open asset."""
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
    return random.choice(asset_list) if asset_list else "AUDCAD"


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
