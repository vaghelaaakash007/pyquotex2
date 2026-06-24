# examples/trade_bot.py

import asyncio
import random
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from datetime import datetime
import math

email, password = credentials()
client = Quotex(
    email=email,
    password=password,
    lang="pt",
)

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

# ==================== COMPOUNDING STRATEGY ====================
class CompoundingStrategy:
    """
    Strategy with EMA 50, Stochastic RSI, Support/Resistance, candlestick patterns,
    and a 3-step compounding flow.
    """
    def __init__(self, base_amount=10.0, max_chain=3):
        self.base_amount = base_amount
        self.max_chain = max_chain
        self.current_stake = base_amount
        self.win_streak = 0
        self.total_wins = 0
        self.total_losses = 0

    def reset_chain(self):
        """Reset compounding chain to base amount."""
        self.current_stake = self.base_amount
        self.win_streak = 0

    def update_after_trade(self, win, profit=None):
        """
        Update stake and streak after a trade result.
        If win: add profit to stake, increment streak, reset if max_chain reached.
        If loss: reset to base.
        """
        if win:
            self.win_streak += 1
            self.total_wins += 1
            if profit is not None:
                self.current_stake += profit  # compound the profit into the next stake
            else:
                # fallback: assume 80% payout if profit not provided (should be passed)
                self.current_stake *= 1.8
            if self.win_streak >= self.max_chain:
                self.reset_chain()
        else:
            self.total_losses += 1
            self.reset_chain()

    # ---------- Indicator Calculations ----------
    @staticmethod
    def calculate_ema(prices, period):
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def calculate_stochastic_rsi(prices, period=14, smooth_k=3, smooth_d=3):
        """Returns (k, d) values (0-100)."""
        if len(prices) < period + smooth_k + smooth_d:
            return 50, 50
        # Calculate RSI first
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains[-period:]) / period if period else 0
        avg_loss = sum(losses[-period:]) / period if period else 0
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        # Stochastic of RSI
        rsi_values = [rsi]  # simplistic: use only current RSI, but we need a series
        # For proper Stochastic RSI we need a series of RSI values; we'll approximate using a rolling window
        # Instead, we'll compute RSI for each candle in a sliding window (simplified)
        rsi_series = []
        for i in range(period + smooth_k + smooth_d, len(prices)):
            # Compute RSI for window ending at i
            window = prices[i-period:i]
            gains_w = [max(window[j] - window[j-1], 0) for j in range(1, len(window))]
            losses_w = [max(-(window[j] - window[j-1]), 0) for j in range(1, len(window))]
            avg_gain_w = sum(gains_w) / period
            avg_loss_w = sum(losses_w) / period
            if avg_loss_w == 0:
                rsi_val = 100
            else:
                rs_w = avg_gain_w / avg_loss_w
                rsi_val = 100 - (100 / (1 + rs_w))
            rsi_series.append(rsi_val)
        if len(rsi_series) < smooth_k + smooth_d:
            return 50, 50
        # Now compute stochastic of RSI
        lowest_rsi = min(rsi_series[-period:])
        highest_rsi = max(rsi_series[-period:])
        if highest_rsi == lowest_rsi:
            k = 50
        else:
            k = 100 * (rsi_series[-1] - lowest_rsi) / (highest_rsi - lowest_rsi)
        # Smooth K with SMA
        k_smooth = sum(rsi_series[-smooth_k:]) / smooth_k if smooth_k else k
        # D line (SMA of K)
        d = sum(rsi_series[-smooth_d-1:-1]) / smooth_d if smooth_d else k
        return k_smooth, d

    @staticmethod
    def detect_support_resistance(prices, lookback=20, threshold=0.001):
        """Find recent support and resistance levels based on swing points."""
        if len(prices) < lookback:
            return [], []
        supports, resistances = [], []
        # Find local minima and maxima
        for i in range(1, len(prices)-1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                # potential support
                supports.append(prices[i])
            elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                # potential resistance
                resistances.append(prices[i])
        # Filter duplicates within threshold
        def filter_levels(levels, threshold):
            if not levels:
                return []
            levels.sort()
            filtered = [levels[0]]
            for lvl in levels[1:]:
                if abs(lvl - filtered[-1]) / filtered[-1] > threshold:
                    filtered.append(lvl)
            return filtered[-3:]  # last 3 most recent levels
        return filter_levels(supports, threshold), filter_levels(resistances, threshold)

    @staticmethod
    def detect_candlestick_pattern(open_price, high, low, close, prev_open, prev_close):
        """
        Detect bullish/bearish pin bar and engulfing patterns.
        Returns: 'bullish', 'bearish', or None.
        """
        # Pin bar: long wick on one side, small body
        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_range = high - low
        if total_range == 0:
            return None
        # Bullish pin bar: long lower wick, small body, close near high
        if lower_wick > 2 * body and lower_wick > 0.6 * total_range and close > open_price:
            return 'bullish'
        # Bearish pin bar: long upper wick, small body, close near low
        if upper_wick > 2 * body and upper_wick > 0.6 * total_range and close < open_price:
            return 'bearish'
        # Bullish engulfing: current body fully engulfs previous body, close > open
        if (close > open_price and prev_close < prev_open and
            close > prev_open and open_price < prev_close):
            return 'bullish'
        # Bearish engulfing
        if (close < open_price and prev_close > prev_open and
            close < prev_open and open_price > prev_close):
            return 'bearish'
        return None

    def get_signal(self, candles):
        """
        candles: list of dicts with keys 'open', 'high', 'low', 'close'
        Returns: (direction, strength) where direction is 'call' or 'put', strength 0-100.
        """
        if len(candles) < 50:
            return None, 0

        # Extract prices
        closes = [c['close'] for c in candles]
        opens = [c['open'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]

        # Compute indicators
        ema50 = self.calculate_ema(closes, 50)
        current_price = closes[-1]
        stoch_k, stoch_d = self.calculate_stochastic_rsi(closes, 14, 3, 3)
        # Previous stochastic for crossover detection (using last two)
        if len(closes) >= 15:
            prev_k, prev_d = self.calculate_stochastic_rsi(closes[:-1], 14, 3, 3)
        else:
            prev_k, prev_d = stoch_k, stoch_d

        supports, resistances = self.detect_support_resistance(closes, lookback=20)
        # Determine nearest support/resistance
        near_support = any(abs(current_price - s) / current_price < 0.001 for s in supports)
        near_resistance = any(abs(current_price - r) / current_price < 0.001 for r in resistances)

        # Candlestick pattern
        if len(candles) >= 2:
            pattern = self.detect_candlestick_pattern(
                opens[-1], highs[-1], lows[-1], closes[-1],
                opens[-2], closes[-2]
            )
        else:
            pattern = None

        # ----- Entry Conditions -----
        # CALL: price > EMA50, Stochastic oversold (<20) and crossing up, near support, bullish pattern
        call_score = 0
        if current_price > ema50:
            call_score += 25
        if stoch_k < 20 and stoch_k > stoch_d and prev_k <= prev_d:
            call_score += 30
        if near_support:
            call_score += 25
        if pattern == 'bullish':
            call_score += 20

        # PUT: price < EMA50, Stochastic overbought (>80) and crossing down, near resistance, bearish pattern
        put_score = 0
        if current_price < ema50:
            put_score += 25
        if stoch_k > 80 and stoch_k < stoch_d and prev_k >= prev_d:
            put_score += 30
        if near_resistance:
            put_score += 25
        if pattern == 'bearish':
            put_score += 20

        # Decide direction based on higher score and minimum threshold
        if call_score >= 60 and call_score > put_score:
            return 'call', min(call_score, 100)
        elif put_score >= 60 and put_score > call_score:
            return 'put', min(put_score, 100)
        else:
            return None, 0


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
    print("\n" + "="*50)
    print("🎯 TRADING MODE SELECTION")
    print("="*50)
    print("1. 📊 SINGLE ASSET (fixed asset, compounding strategy)")
    print("2. 🎲 SHUFFLE CURRENCIES (random asset each trade, compounding strategy)")
    print("="*50)
    
    trading_mode = None
    while True:
        choice = input("\n👉 Choose mode (1 or 2): ").strip()
        if choice == "1":
            trading_mode = "single"
            break
        elif choice == "2":
            trading_mode = "shuffle"
            break
        else:
            print("❌ 1 or 2 only!")
    
    print("\n" + "="*50)
    print("⚙️  PARAMETERS")
    print("="*50)
    base_amount = float(input("💰 Base amount for compounding (e.g., 10): $"))
    max_chain = int(input("🔗 Max consecutive wins before reset (default 3): ") or 3)
    expiry = int(input("⏱️  Expiry in seconds (60 or 180 recommended): ") or 60)
    max_trades = int(input("🔄 Max trades (0=∞): "))
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
    mode_names = {"single": "Single Asset", "shuffle": "Shuffle Currencies"}
    print(f"Mode: {mode_names[trading_mode]}")
    print(f"Account: {account_type} | Balance: ${balance:.2f}")
    print(f"Trades: {'∞' if max_trades == 0 else max_trades} | Base amount: ${base_amount}")
    print(f"Max chain: {max_chain} wins | Expiry: {expiry}s")
    print("="*50 + "\n")
    
    return {
        'trading_mode': trading_mode,
        'base_amount': base_amount,
        'max_chain': max_chain,
        'expiry': expiry,
        'max_trades': max_trades,
        'stop_loss': stop_loss,
        'stop_profit': stop_profit,
        'account_type': account_type,
        'balance': balance
    }


# ==================== TRADING FUNCTIONS ====================
async def calculate_profit(asset_name, amount, balance):
    payout = client.get_payout_by_asset(asset_name)
    profit = (payout / 100) * amount
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


# ==================== SINGLE ASSET MODE (with Compounding Strategy) ====================
async def single_asset_mode(config):
    """Single asset trading with the compounding strategy."""
    trading_mode = config['trading_mode']
    base_amount = config['base_amount']
    max_chain = config['max_chain']
    expiry = config['expiry']
    max_trades = config['max_trades']
    stop_loss = config['stop_loss']
    stop_profit = config['stop_profit']
    balance = config['balance']
    
    asset = "AUDCAD"  # default, can be changed
    print(f"\n🚀 SINGLE ASSET MODE | Asset: {asset} | Balance: ${balance:.2f}")
    
    # Initialize strategy
    strategy = CompoundingStrategy(base_amount=base_amount, max_chain=max_chain)
    
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    current_stake = strategy.current_stake  # starts at base
    
    # Get asset info
    asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
    if not asset_data[2]:
        print("❌ Asset closed!")
        return initial_balance, balance, 0, 0, 0, 0, 0
    
    while True:
        if max_trades > 0 and trade_count >= max_trades:
            print(f"\n✅ MAX {max_trades} DONE!")
            break
        
        should_stop, reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
        if should_stop:
            print(f"\n{reason}")
            break
        
        if balance < current_stake:
            print(f"\n❌ Balance ${balance:.2f} < Stake ${current_stake:.2f}")
            break
        
        # Fetch candles for strategy
        candles = await client.get_candles(asset_name, None, 60, 5, use_cache=True)
        if not candles:
            print("⏳ No candle data, waiting...")
            await asyncio.sleep(5)
            continue
        # Convert candles to dict if needed (they might be tuples)
        if isinstance(candles[0], dict):
            candle_list = candles
        else:
            # Assume tuple format (open, close, high, low, volume, time)
            candle_list = [{'open': c[0], 'close': c[1], 'high': c[2], 'low': c[3]} for c in candles]
        
        # Get signal
        direction, strength = strategy.get_signal(candle_list)
        if not direction:
            print(f"⏳ No signal (strength {strength:.0f}) - waiting...")
            await asyncio.sleep(3)
            continue
        
        print(f"📊 Signal: {direction.upper()} (strength {strength:.0f}%)")
        
        # Execute trade
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | Stake: ${current_stake:.2f} | {direction.upper()} | Expiry: {expiry}s")
        
        if not await client.check_connect():
            await client.connect()
        
        balance_before = balance
        status, buy_info = await client.buy(current_stake, asset_name, direction, expiry)
        
        if not status:
            print("   ❌ Buy Failed!")
            continue
        
        balance -= current_stake
        result = await check_result(buy_info, direction, asset_name)
        
        if result == "Win":
            balance, profit = await calculate_profit(asset_name, current_stake, balance)
            total_wins += 1
            total_profit += profit
            print(f"   ✅ WIN! +${profit:.2f} | Bal: ${balance:.2f}")
            # Update strategy with win
            strategy.update_after_trade(win=True, profit=profit)
            current_stake = strategy.current_stake
            print(f"   🔄 New stake: ${current_stake:.2f} (win streak: {strategy.win_streak})")
            if strategy.win_streak == 0:
                print("   🔄 Chain reset after max wins.")
        elif result == "Doji":
            print("   ⚪ DOJI - stake returned")
            balance += current_stake  # return stake
            # Doji is not a loss, but we might not count as win; we can keep stake unchanged
            # For compounding, we might treat as neither win nor loss, so we leave stake as is.
            # However, we might want to reset? Usually doji is neutral. We'll keep it.
        else:
            total_losses += 1
            loss_amount = balance_before - balance  # actually we already subtracted stake, so loss = stake
            total_loss_amount += loss_amount
            print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f}")
            strategy.update_after_trade(win=False)
            current_stake = strategy.current_stake
            print(f"   🔄 Reset to base: ${current_stake:.2f}")
        
        await asyncio.sleep(1)  # short pause
    
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount


# ==================== SHUFFLE MODE (with Compounding Strategy) ====================
async def shuffle_mode(config):
    """Shuffle currencies mode with the compounding strategy."""
    trading_mode = config['trading_mode']
    base_amount = config['base_amount']
    max_chain = config['max_chain']
    expiry = config['expiry']
    max_trades = config['max_trades']
    stop_loss = config['stop_loss']
    stop_profit = config['stop_profit']
    balance = config['balance']
    
    print(f"\n🎲 SHUFFLE MODE | Balance: ${balance:.2f}")
    print(f"📋 Assets pool: {', '.join(SHUFFLE_ASSETS)}")
    
    strategy = CompoundingStrategy(base_amount=base_amount, max_chain=max_chain)
    
    initial_balance = balance
    trade_count = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0
    total_loss_amount = 0
    current_stake = strategy.current_stake
    
    while True:
        if max_trades > 0 and trade_count >= max_trades:
            print(f"\n✅ MAX {max_trades} DONE!")
            break
        
        should_stop, reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
        if should_stop:
            print(f"\n{reason}")
            break
        
        if balance < current_stake:
            print(f"\n❌ Balance ${balance:.2f} < Stake ${current_stake:.2f}")
            break
        
        # Pick random asset
        asset = random.choice(SHUFFLE_ASSETS)
        print(f"\n{'='*80}")
        print(f"🎲 Shuffled Asset: {asset}")
        
        # Check if asset is open
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)
        if not asset_data[2]:
            print(f"   ❌ {asset} is closed, skipping...")
            await asyncio.sleep(2)
            continue
        
        # Fetch candles
        candles = await client.get_candles(asset_name, None, 60, 5, use_cache=True)
        if not candles:
            print("   ⏳ No candle data, waiting...")
            await asyncio.sleep(5)
            continue
        if isinstance(candles[0], dict):
            candle_list = candles
        else:
            candle_list = [{'open': c[0], 'close': c[1], 'high': c[2], 'low': c[3]} for c in candles]
        
        # Get signal
        direction, strength = strategy.get_signal(candle_list)
        if not direction:
            print(f"   ⏳ No signal (strength {strength:.0f}) - waiting...")
            await asyncio.sleep(3)
            continue
        
        print(f"   📊 Signal: {direction.upper()} (strength {strength:.0f}%)")
        
        # Execute trade
        trade_count += 1
        print(f"\n📈 TRADE #{trade_count} | Stake: ${current_stake:.2f} | {direction.upper()} | {asset} | Expiry: {expiry}s")
        
        if not await client.check_connect():
            await client.connect()
        
        balance_before = balance
        status, buy_info = await client.buy(current_stake, asset_name, direction, expiry)
        
        if not status:
            print("   ❌ Buy Failed!")
            continue
        
        balance -= current_stake
        result = await check_result(buy_info, direction, asset_name)
        
        if result == "Win":
            balance, profit = await calculate_profit(asset_name, current_stake, balance)
            total_wins += 1
            total_profit += profit
            print(f"   ✅ WIN! +${profit:.2f} | Bal: ${balance:.2f}")
            strategy.update_after_trade(win=True, profit=profit)
            current_stake = strategy.current_stake
            print(f"   🔄 New stake: ${current_stake:.2f} (win streak: {strategy.win_streak})")
            if strategy.win_streak == 0:
                print("   🔄 Chain reset after max wins.")
        elif result == "Doji":
            print("   ⚪ DOJI - stake returned")
            balance += current_stake
        else:
            total_losses += 1
            loss_amount = balance_before - balance
            total_loss_amount += loss_amount
            print(f"   ❌ LOSS! -${loss_amount:.2f} | Bal: ${balance:.2f}")
            strategy.update_after_trade(win=False)
            current_stake = strategy.current_stake
            print(f"   🔄 Reset to base: ${current_stake:.2f}")
        
        await asyncio.sleep(1)
    
    return initial_balance, balance, trade_count, total_wins, total_losses, total_profit, total_loss_amount


# ==================== STOP LIMITS HELPER ====================
def check_stop_limits(initial, current, sl, sp):
    pnl = current - initial
    if sp > 0 and pnl >= sp:
        return True, f"🎯 STOP PROFIT! +${pnl:.2f}"
    if sl > 0 and pnl <= -sl:
        return True, f"🛑 STOP LOSS! -${abs(pnl):.2f}"
    return False, ""


# ==================== MAIN ====================
async def trade_and_monitor():
    config = await get_user_config()
    
    if config is None:
        await cleanup()
        return
    
    trading_mode = config['trading_mode']
    
    try:
        if trading_mode == "shuffle":
            initial, final, trades, wins, losses, profit, loss_amt = await shuffle_mode(config)
        else:
            initial, final, trades, wins, losses, profit, loss_amt = await single_asset_mode(config)
        
        final_pnl = final - initial
        
        print(f"\n{'='*60}")
        print(f"🏁 SESSION SUMMARY")
        print(f"{'='*60}")
        mode_names = {"single": "Single Asset", "shuffle": "Shuffle Currencies"}
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
