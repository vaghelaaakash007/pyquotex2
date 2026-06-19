# examples/trade_bot.py

import asyncio
import random
from collections import deque
from enum import IntEnum

# ===== Handle credentials import gracefully =====
try:
    from pyquotex.config import credentials
except ImportError:
    # Fallback: ask user for credentials interactively
    def credentials():
        print("\n🔐 Please enter your Quotex credentials:")
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        return email, password
else:
    # If import succeeded, we can use it directly
    pass

# Continue with the rest of the imports
from pyquotex.stable_api import Quotex


# ==================== ACCOUNT TYPE ENUM ====================
class AccountType(IntEnum):
    REAL = 0
    DEMO = 1

    def __str__(self) -> str:
        return str(self.value)


# Global client
client = None


# ==================== STRATEGY COLLECTION ====================
# ... (all strategy classes unchanged) ...


# ==================== STRATEGY SELECTOR ====================
class StrategyManager:
    # ... (unchanged) ...


# ==================== USER CONFIG ====================
def get_user_config():
    # ... (unchanged) ...


# ==================== MONEY MANAGEMENT ====================
# ... (unchanged) ...


# ==================== ASSET SELECTION ====================
async def select_assets(client):
    # ... (unchanged) ...


# ==================== TRADING FUNCTIONS ====================
# ... (analise_sentiment, calculate_profit, check_result, cleanup unchanged) ...


# ==================== MAIN TRADING LOOP ====================
async def trade_and_monitor():
    global client

    max_trades, base_amount, stop_loss, stop_profit, strategy_manager = get_user_config()

    # Get credentials – either from pyquotex.config or via input
    email, password = credentials()
    client = Quotex(email=email, password=password, lang="pt")

    try:
        # --- First connection (verify credentials) ---
        check_connect, message = await client.connect()
        if not check_connect:
            print("❌ Connection failed")
            return

        print("✅ Connected successfully (initial).")

        # --- Account type selection ---
        print("\n🏦 ACCOUNT TYPE:")
        print("  1. REAL")
        print("  2. DEMO")
        while True:
            acc_choice = input("👉 Choose (1 or 2): ").strip()
            if acc_choice == "1":
                account_type = AccountType.REAL
                print("✅ Real account selected")
                break
            elif acc_choice == "2":
                account_type = AccountType.DEMO
                print("✅ Demo account selected")
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")

        # --- Disconnect and apply account type ---
        await client.close()
        await asyncio.sleep(1)

        try:
            if hasattr(client, 'set_account_type'):
                client.set_account_type(account_type)
            elif hasattr(client, 'set_account'):
                client.set_account(account_type)
            else:
                client.account_type = account_type
            print(f"✅ Account type set to {account_type.name}")
        except Exception as e:
            print(f"⚠️ Could not set account type: {e}. Defaulting to DEMO.")
            client.account_type = AccountType.DEMO

        # --- Reconnect with chosen account ---
        check_connect, message = await client.connect()
        if not check_connect:
            print("❌ Reconnection failed")
            return

        print(f"✅ Reconnected with {account_type.name} account.")

        # --- Asset selection (now with payouts) ---
        asset_list = await select_assets(client)

        # --- Initialise trading variables ---
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

        print("\n" + "=" * 50)
        print("📊 SESSION STARTED")
        print("=" * 50)
        print(f"Balance: ${balance:.2f}")
        print(f"Base Amount: ${base_amount}")
        print(f"Current Amount: ${amount}")
        print(f"Win Streak: {win_streak}")
        print(f"Assets in rotation: {len(asset_list)}")
        print("=" * 50 + "\n")

        # --- Main trading loop ---
        while True:
            if max_trades > 0 and trade_count >= max_trades:
                print(f"\n✅ MAX TRADES ({max_trades}) DONE!")
                break

            should_stop, stop_reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
            if should_stop:
                print(f"\n{stop_reason}")
                break

            print(f"{'=' * 100}")

            current_asset = pick_next_asset(asset_list, client, last_asset)
            if current_asset != last_asset and strategy_manager.active_strategy:
                strategy_manager.active_strategy.price_history.clear()
                strategy_manager.active_strategy.volume_history.clear()
                print(f"🔄 Switching to {current_asset} – history reset")
            else:
                print(f"🔄 Using {current_asset} again (only available asset)")
            last_asset = current_asset

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

            trade_count += 1
            print(f"\n📈 TRADE #{trade_count}")
            print(f"   Asset: {current_asset} | Amount: ${amount} | Direction: {direction.upper()}")
            print(f"   Win Streak: {win_streak}")

            asset_name, asset_data = await client.get_available_asset(current_asset, force_open=True)
            if not asset_data[2]:
                print(f"⚠️ {current_asset} is now closed, skipping...")
                await asyncio.sleep(2)
                continue

            if not await client.check_connect():
                await client.connect()

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

                    print(f"\n{'─' * 50}")
                    print(f"✅ WIN #{trade_count}")
                    print(f"   Profit: ${profit:.2f}")
                    print(f"   Balance: ${balance:.2f}")
                    print(f"   P/L: ${balance - initial_balance:.2f}")
                    print(f"   Wins: {total_wins} | Losses: {total_losses}")
                    if trade_count > 0:
                        print(f"   Win Rate: {total_wins / trade_count * 100:.1f}%")
                    print(f"{'─' * 50}")

                    amount, win_streak = get_next_amount(amount, base_amount, True, win_streak)
                    print(f"💰 Next Amount: ${amount} | Streak: {win_streak}")

                elif result == "Doji":
                    print("⚪ DOJI - No change (asset will switch anyway)")

                else:
                    if strategy_manager.active_strategy:
                        strategy_manager.update_stats(False)
                    total_losses += 1
                    loss = balance_before - balance

                    print(f"\n{'─' * 50}")
                    print(f"❌ LOSS #{trade_count}")
                    print(f"   Loss: ${loss:.2f}")
                    print(f"   Balance: ${balance:.2f}")
                    print(f"   P/L: ${balance - initial_balance:.2f}")
                    print(f"   Wins: {total_wins} | Losses: {total_losses}")
                    if trade_count > 0:
                        print(f"   Win Rate: {total_wins / trade_count * 100:.1f}%")
                    print(f"{'─' * 50}")

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
        print("\n" + "=" * 50)
        print("🏁 SESSION ENDED")
        print("=" * 50)
        print(f"Trades: {trade_count}")
        print(f"Wins: {total_wins} | Losses: {total_losses}")
        if trade_count > 0:
            print(f"Win Rate: {total_wins / trade_count * 100:.1f}%")
        print(f"Balance: ${balance:.2f}")
        print(f"P/L: ${balance - initial_balance:.2f}")

        if strategy_manager.active_strategy:
            strategy_manager.show_performance()
        print("=" * 50)

        await cleanup()


def pick_next_asset(asset_list, client, last_asset=None):
    # ... (unchanged) ...


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
