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


# ---- Insert the 11 strategy subclasses here (EMA_RSI_Scalping, Bollinger_RSI_Scalping, etc.) ----
# They are exactly the same as before; omitted for brevity but must be included in the final script.

# ==================== STRATEGY SELECTOR ====================
class StrategyManager:
    # ... (unchanged) ...
    pass

# ==================== USER CONFIG ====================
ALWAYS_INCLUDED_ASSETS = ["USDJPY_otc", "GBPAUD_otc"]

def get_user_config():
    # ... (unchanged) ...
    pass

# ==================== MONEY MANAGEMENT ====================
def get_next_amount(current_amount, base_amount, is_win, win_streak):
    # ... (unchanged) ...
    pass

def check_stop_limits(initial_balance, current_balance, stop_loss, stop_profit):
    # ... (unchanged) ...
    pass

# ==================== BACKGROUND SIGNAL UPDATER ====================
async def background_signal_updater(asset_strategies, client, asset_signals, stop_event):
    """Continuously update price histories and compute signals for all assets."""
    while not stop_event.is_set():
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

        await asyncio.sleep(1)  # Update every second (adjust as needed)


async def fetch_and_update(asset, strategy, client):
    """Fetch candles for ONE asset (with error isolation)."""
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
        # Silently ignore – asset might be temporarily unavailable
        pass


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
        # Remove duplicates
        seen = set()
        asset_list = [x for x in asset_list if not (x in seen or seen.add(x))]

        # ===== BACKGROUND PREPARATION =====
        asset_strategies = {}
        asset_signals = {}   # {asset: (direction, strength)}
        if strategy_manager.active_strategy:
            strategy_class = type(strategy_manager.active_strategy)
            for asset in asset_list:
                asset_strategies[asset] = strategy_class()
        else:
            # Random mode – no pre-fetching
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
        print(f"Balance: ${balance:.2f} | Base Amount: ${base_amount}")
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

            # ===== SELECT NEXT ASSET =====
            next_asset = None
            if asset_strategies:
                # Use pre-computed signals
                candidates = []
                for asset in asset_list:
                    if asset == last_asset:
                        continue
                    signal, strength = asset_signals.get(asset, (None, 0))
                    if signal and strength >= 60:
                        # Quick check if asset is still open
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
                # Random mode
                next_asset = pick_next_asset(asset_list, client, last_asset)
                if next_asset is None:
                    print("⏳ No open asset found – retrying...")
                    await asyncio.sleep(2)
                    continue
                direction = random.choice(["call", "put"])
                print(f"🎲 RANDOM: {direction.upper()} on {next_asset}")

            # Safety check: asset must be open (double-check)
            asset_name, asset_data = await client.get_available_asset(next_asset, force_open=True)
            if not asset_data[2]:
                print(f"⚠️ {next_asset} just closed, skipping...")
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
