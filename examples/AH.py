# examples/trade_bot.py

import asyncio
import signal
import random
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex
from collections import deque
from enum import IntEnum

# ==================== ACCOUNT TYPE ENUM ====================
class AccountType(IntEnum):
    REAL = 0
    DEMO = 1

    def __str__(self) -> str:
        return str(self.value)

# Global client (will be set later)
client = None

# ==================== STRATEGY COLLECTION ====================
class ScalpingStrategyBase:
    # ... (all strategy classes remain exactly as before) ...

# ==================== STRATEGY SELECTOR ====================
class StrategyManager:
    # ... (unchanged) ...

# ==================== USER CONFIG ====================
ALWAYS_INCLUDED_ASSETS = ["USDJPY_otc", "GBPAUD_otc"]

def get_user_config():
    # ... (unchanged – includes account type selection) ...

# ==================== MONEY MANAGEMENT ====================
# ... (unchanged) ...

# ==================== ASSET SHUFFLING ====================
# ... (unchanged) ...

# ==================== TRADING FUNCTIONS ====================
# ... (analise_sentiment, calculate_profit, check_result, cleanup unchanged) ...

async def trade_and_monitor():
    global client

    max_trades, base_amount, stop_loss, stop_profit, strategy_manager, asset_list, account_type = get_user_config()
    
    email, password = credentials()
    # Instantiate WITHOUT account_type
    client = Quotex(
        email=email,
        password=password,
        lang="pt",
    )
    
    # Set the account type – try attribute or method
    try:
        if hasattr(client, 'set_account_type'):
            client.set_account_type(account_type)   # method
        elif hasattr(client, 'set_account'):
            client.set_account(account_type)
        else:
            # Direct assignment (works in some versions)
            client.account_type = account_type
    except Exception as e:
        print(f"⚠️ Could not set account type: {e}. Defaulting to DEMO.")
        client.account_type = AccountType.DEMO

    try:
        check_connect, message = await client.connect()
        if check_connect:
            # ===== RESOLVE "ALL" ASSET LIST =====
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
                    print(f"⚠️ Could not fetch all assets: {e}, falling back to AUDCAD")
                    asset_list = ["AUDCAD"]
            
            for pair in ALWAYS_INCLUDED_ASSETS:
                if pair not in asset_list:
                    asset_list.append(pair)
            
            seen = set()
            asset_list = [x for x in asset_list if not (x in seen or seen.add(x))]
            
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
                
                # ===== PICK A NEW ASSET =====
                current_asset = pick_next_asset(asset_list, client, last_asset)
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
                    direction = random.choice(["call", "put"])
                    print(f"🎲 RANDOM direction: {direction.upper()}")
                
                # ===== EXECUTE TRADE =====
                trade_count += 1
                print(f"\n📈 TRADE #{trade_count}")
                print(f"   Asset: {current_asset} | Amount: ${amount} | Direction: {direction.upper()}")
                print(f"   Win Streak: {win_streak}")
                
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
                        amount, win_streak = get_next_amount(amount, base_amount, True, win_streak)
                        print(f"💰 Next Amount: ${amount} | Streak: {win_streak}")

                    elif result == "Doji":
                        print("⚪ DOJI - No change")

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
                        amount, win_streak = get_next_amount(amount, base_amount, False, win_streak)
                        print(f"💰 Next Amount: ${amount} | Streak: {win_streak}")

                else:
                    print("❌ Buy failed (will try next signal)")
                    await asyncio.sleep(2)

        else:
            print("❌ Connection failed")

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
