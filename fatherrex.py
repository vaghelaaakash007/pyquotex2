# examples/trade_bot.py

import asyncio
from pyquotex.config import credentials
from pyquotex.stable_api import Quotex

email, password = credentials()
client = Quotex(
    email=email,
    password=password,
    lang="pt",  # Default pt -> Português.
)

# ==================== NEW: User Configuration ====================
def get_user_config():
    """Get trading configuration from user"""
    print("\n" + "="*50)
    print("📋 TRADING CONFIGURATION")
    print("="*50)
    
    # Kitni baar trade leni hai
    max_trades = int(input("\n🔄 Kitni baar trade leni hai? (0 = infinite): "))
    
    # Amount
    base_amount = float(input("💰 Base amount kitna lagana hai? (e.g., 50): "))
    
    # Stop Loss & Stop Profit
    stop_loss = float(input("🛑 Stop Loss kitna? (0 = no stop loss): "))
    stop_profit = float(input("🎯 Stop Profit kitna? (0 = no stop profit): "))
    
    print("\n" + "="*50)
    print("✅ CONFIGURATION SAVED")
    print(f"Max Trades: {'Infinite' if max_trades == 0 else max_trades}")
    print(f"Base Amount: ${base_amount}")
    print(f"Stop Loss: ${stop_loss if stop_loss > 0 else 'Disabled'}")
    print(f"Stop Profit: ${stop_profit if stop_profit > 0 else 'Disabled'}")
    print("="*50 + "\n")
    
    return max_trades, base_amount, stop_loss, stop_profit


# ==================== NEW: Compound Logic ====================
def get_next_amount(current_amount, base_amount, is_win):
    """
    WIN → Double amount
    LOSS → Reset to base amount
    """
    if is_win:
        return current_amount * 2
    else:
        return base_amount


# ==================== NEW: Check Stop Loss / Stop Profit ====================
def check_stop_limits(initial_balance, current_balance, stop_loss, stop_profit):
    """
    Check if stop loss or stop profit hit
    Returns: (should_stop, reason)
    """
    profit_loss = current_balance - initial_balance
    
    # Check Stop Profit
    if stop_profit > 0 and profit_loss >= stop_profit:
        return True, f"🎯 STOP PROFIT HIT! Profit: ${profit_loss:.2f}"
    
    # Check Stop Loss
    if stop_loss > 0 and profit_loss <= -stop_loss:
        return True, f"🛑 STOP LOSS HIT! Loss: ${abs(profit_loss):.2f}"
    
    return False, ""


# ==================== ORIGINAL FUNCTIONS ====================

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
    """
    Calculate the profit based on the payout percentage for the given asset.

    Args:
        asset_name (str): The name of the asset.
        amount (float): The amount of money placed on the asset.
        balance (float): The current balance before the profit is calculated.

    Returns:
        tuple: The updated balance and the profit earned.
    """
    payout = client.get_payout_by_asset(asset_name)
    profit = ((payout / 100) * amount)
    balance += amount + profit
    return balance, profit


async def martingale_apply(amount, asset_name, direction, duration, balance, martingale_quantity):
    """
    Apply the Martingale strategy to the given trade, doubling the amount on each loss until the limit is reached.

    Args:
        amount (float): The initial betting amount.
        asset_name (str): The name of the asset being traded.
        direction (str): The trade direction, either "call" or "put".
        duration (int): The duration of the trade in seconds.
        balance (float): The current balance.
        martingale_quantity (int): The number of times the Martingale strategy can be applied.

    Returns:
        tuple: The updated balance, profit, and success status (True/False).
    """
    while martingale_quantity > 0:
        balance -= amount
        print(f"Betting {amount} on asset {asset_name} in the {direction} direction for {duration}s")
        status, buy_info = await client.buy(amount, asset_name, direction, duration)

        if not status:
            print("ERROR: Could not place the bet.")
            return balance, 0, False

        print(f"New Balance: {balance}")

        await analise_sentiment(asset_name, duration)

        result = await check_result(buy_info, direction, asset_name)  # FIXED: asset_name pass karo

        if result == "Win":
            balance, profit = await calculate_profit(asset_name, amount, balance)
            return balance, profit, True
        elif result == "Doji":
            print("Result: DOJI. No profit or loss.")
            return balance, 0, True

        amount *= 2
        martingale_quantity -= 1

    print("Martingale exhausted. Total loss.")
    return balance, 0, False


# ==================== FIXED: check_result function ====================
async def check_result(buy_data, direction, asset_name=None):
    """
    Check the result of the trade based on real-time price and direction.

    Args:
        buy_data (dict): Information about the trade, including open price and close timestamp.
        direction (str): The direction of the trade, either "call" or "put".
        asset_name (str): The asset name to get real-time price.

    Returns:
        str: The result of the trade ("Win", "Loss", or "Doji").
    """
    # FIX: 'asset' key nahi milti to asset_name parameter use karo
    if asset_name is None:
        asset_name = buy_data.get('asset')  # Try to get from buy_data
    
    # Agar dono me se kuch nahi mila to error
    if asset_name is None:
        print("ERROR: Asset name not found!")
        return 'Loss'
    
    open_price = buy_data.get('openPrice')
    
    # Agar open_price bhi None ho to check_win use karo
    if open_price is None:
        print("No open price found, using check_win instead...")
        try:
            win_status, profit = await client.check_win(buy_data["id"])
            if win_status == "win":
                print("Result: WIN")
                return 'Win'
            elif win_status == "loss":
                print("Result: LOSS")
                return 'Loss'
            else:
                print("Result: DOJI")
                return 'Doji'
        except Exception as e:
            print(f"check_win error: {e}")
            return 'Loss'

    while True:
        try:
            prices = await client.get_realtime_price(asset_name)

            if not prices:
                await asyncio.sleep(0.5)
                continue

            current_price = prices[-1]['price']

            print(f"\nCurrent Price: {current_price}, Open Price: {open_price}")

            if (direction == "call" and current_price > open_price) or (
                    direction == "put" and current_price < open_price):
                print("Result: WIN")
                return 'Win'
            elif (direction == "call" and current_price <= open_price) or (
                    direction == "put" and current_price >= open_price):
                print("Result: LOSS")
                return 'Loss'
            else:
                print("Result: DOJI")
                return 'Doji'
                
        except Exception as e:
            print(f"Error getting price: {e}, retrying...")
            await asyncio.sleep(1)
            continue


async def trade_and_monitor():
    """
    Main function to manage trading and monitor the results.
    It connects to the client, places bets, and applies the Martingale strategy if necessary.

    Returns:
        None
    """
    # ==================== NEW: Get User Config ====================
    max_trades, base_amount, stop_loss, stop_profit = get_user_config()
    
    check_connect, message = await client.connect()
    if check_connect:
        amount = base_amount  # Use user-defined base amount
        asset = "AUDCAD"
        direction = "call"
        duration = 60  # in seconds
        balance = await client.get_balance()
        initial_balance = balance
        martingale_quantity = 2
        
        # ==================== NEW: Trade Counter ====================
        trade_count = 0
        total_wins = 0
        total_losses = 0
        
        print("\n" + "="*50)
        print("📊 SESSION STARTED")
        print("="*50)
        print(f"Initial Balance: ${balance:.2f}")
        print(f"Base Amount: ${amount:.2f}")
        print(f"Max Trades: {'Infinite' if max_trades == 0 else max_trades}")
        print(f"Stop Loss: ${stop_loss:.2f}" if stop_loss > 0 else "Stop Loss: Disabled")
        print(f"Stop Profit: ${stop_profit:.2f}" if stop_profit > 0 else "Stop Profit: Disabled")
        print("="*50 + "\n")
        
        asset_name, asset_data = await client.get_available_asset(asset, force_open=True)

        if asset_data[2]:
            print("OK: Asset is open.")

            while True:
                # ==================== NEW: Check Max Trades ====================
                if max_trades > 0 and trade_count >= max_trades:
                    print("\n" + "="*50)
                    print(f"✅ MAX TRADES ({max_trades}) REACHED!")
                    print("="*50)
                    break
                
                # ==================== NEW: Check Stop Loss / Profit ====================
                should_stop, stop_reason = check_stop_limits(initial_balance, balance, stop_loss, stop_profit)
                if should_stop:
                    print("\n" + "="*50)
                    print(stop_reason)
                    print("="*50)
                    break
                
                print(f"{100 * '='}")
                
                # ==================== NEW: Show Trade Info ====================
                trade_count += 1
                print(f"\n📈 TRADE #{trade_count} | Amount: ${amount:.2f} | Direction: {direction.upper()}")
                
                check_connect = await client.check_connect()
                if not check_connect:
                    check_connect, message = await client.connect()

                print(f"Betting {amount} on asset {asset_name} in the {direction} direction for {duration}s")
                
                # ==================== NEW: Track balance before trade ====================
                balance_before_trade = balance
                
                status, buy_info = await client.buy(amount, asset_name, direction, duration)
                print(status, buy_info)
                
                if status:
                    balance -= amount
                    print(f"New Balance: {balance}")

                    await analise_sentiment(asset_name, duration)

                    # FIXED: asset_name pass karo
                    result = await check_result(buy_info, direction, asset_name)

                    if result == "Win":
                        balance, profit = await calculate_profit(asset_name, amount, balance)
                        total_wins += 1
                        
                        # ==================== NEW: Show Profit ====================
                        print("\n" + "-"*50)
                        print(f"✅ TRADE #{trade_count} RESULT: WIN")
                        print(f"💰 Profit: ${profit:.2f}")
                        print(f"💵 Balance: ${balance:.2f}")
                        print(f"📊 Overall P/L: ${balance - initial_balance:.2f}")
                        print(f"📈 Stats: {total_wins}W / {total_losses}L | Win Rate: {(total_wins/trade_count*100):.1f}%")
                        print("-"*50)
                        
                        # ==================== NEW: Compound - Double amount on win ====================
                        amount = get_next_amount(amount, base_amount, is_win=True)
                        print(f"🔄 Next Trade Amount: ${amount:.2f} (Doubled on WIN)")
                        
                        continue

                    if result == "Doji":
                        print("Result: DOJI. No profit or loss.")
                        print(f"💵 Balance unchanged: ${balance:.2f}")
                        continue

                    # Loss case - apply martingale
                    balance, profit, success = await martingale_apply(
                        amount * 2,
                        asset_name,
                        direction,
                        duration,
                        balance,
                        martingale_quantity
                    )

                    if success:
                        total_wins += 1
                        print(f"Profit after Martingale: ${profit:.2f}")
                        
                        # ==================== NEW: After martingale win ====================
                        print(f"\n✅ MARTINGALE SUCCESS - Trade #{trade_count}")
                        print(f"💰 Profit: ${profit:.2f}")
                        print(f"💵 Balance: ${balance:.2f}")
                        print(f"📊 Overall P/L: ${balance - initial_balance:.2f}")
                        
                        # ==================== NEW: Compound - Double on win ====================
                        amount = get_next_amount(amount, base_amount, is_win=True)
                        print(f"🔄 Next Trade Amount: ${amount:.2f} (Doubled on WIN)")
                    else:
                        total_losses += 1
                        
                        # ==================== NEW: Show Loss Details ====================
                        loss_amount = initial_balance - balance
                        print(f"Accumulated Loss: ${loss_amount:.2f}")
                        
                        print("\n" + "-"*50)
                        print(f"❌ TRADE #{trade_count} RESULT: LOSS")
                        print(f"💸 Loss: ${loss_amount:.2f}")
                        print(f"💵 Balance: ${balance:.2f}")
                        print(f"📊 Overall P/L: ${balance - initial_balance:.2f}")
                        print(f"📈 Stats: {total_wins}W / {total_losses}L | Win Rate: {(total_wins/trade_count*100):.1f}%")
                        print("-"*50)
                        
                        # ==================== NEW: Compound - Reset on loss ====================
                        amount = get_next_amount(amount, base_amount, is_win=False)
                        print(f"🔄 Next Trade Amount: ${amount:.2f} (Reset to base on LOSS)")

                    print(f"New Balance: {balance}")

                else:
                    print("Operation failed.")

                await asyncio.sleep(1)

        else:
            print("ERROR: Asset is closed.")

    else:
        print("Could not connect to the client.")

    # ==================== NEW: Final Summary ====================
    print("\n" + "="*50)
    print("🏁 SESSION ENDED - FINAL SUMMARY")
    print("="*50)
    print(f"Total Trades: {trade_count}")
    print(f"Wins: {total_wins}")
    print(f"Losses: {total_losses}")
    print(f"Win Rate: {(total_wins/trade_count*100):.1f}%" if trade_count > 0 else "Win Rate: 0%")
    print(f"Initial Balance: ${initial_balance:.2f}")
    print(f"Final Balance: ${balance:.2f}")
    print(f"Total P/L: ${balance - initial_balance:.2f}")
    print("="*50)
    
    print("Exiting...")
    client.close()


async def main():
    """
    Entry point for the program. It starts the trading and monitoring process.

    Returns:
        None
    """
    await trade_and_monitor()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nClosing the program.")
    finally:
        loop.close()
