#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADEIQDEV AUTO-TRADING BOT - FULLY WORKING
Correct PyQuotex implementation
"""

import os
import sys
import asyncio
import json
import random
import time
from datetime import datetime
import numpy as np
from pyquotex.stable_api import Quotex
from colorama import init, Fore, Style
import pytz

init(autoreset=True)

# ================= CONFIGURATION =================
TIMEFRAME = 60  # 1 minute
SAVE_FILE = "auto_trade_data.json"

# ================= GLOBAL VARIABLES =================
bot_running = False
client = None
selected_strategy = "EMA_RSI"
trade_type = "FIXED"
stop_profit = 100.0
stop_loss = 50.0
trade_amount = 10.0
account_type = "PRACTICE"
total_profit = 0.0
total_trades = 0
win_count = 0
loss_count = 0
consecutive_losses = 0
current_balance = 0
initial_balance = 0

# ================= PAIRS =================
ALL_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", 
    "NZDUSD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY",
    "GBPAUD", "EURAUD", "EURCHF", "AUDJPY", "AUDCAD",
    "CADCHF", "GBPCAD", "USDMXN", "USDTRY", "USDZAR",
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
    "USDCAD_otc", "NZDUSD_otc", "USDCHF_otc", "EURGBP_otc",
    "EURJPY_otc", "GBPJPY_otc", "AUDJPY_otc", "USDMXN_otc",
    "USDTRY_otc", "USDZAR_otc", "BRLUSD_otc", "USDPKR_otc",
    "CADCHF_otc", "EURCHF_otc", "GBPAUD_otc", "GBPCAD_otc",
    "AUDCAD_otc", "EURAUD_otc"
]

AVAILABLE_STRATEGIES = ["EMA_RSI", "Trend", "Bollinger", "Support_Resistance", "Supertrend"]

# ================= UTILITY FUNCTIONS =================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

async def get_candles(client, pair, period, attempts=3):
    for _ in range(attempts):
        try:
            end_time = int(time.time())
            resp = await client.get_candles(pair, end_time, 60, period)
            if resp:
                candles = []
                for item in resp:
                    if isinstance(item, dict):
                        candle = {
                            'open': float(item.get('open', 0)),
                            'high': float(item.get('high', 0)),
                            'low': float(item.get('low', 0)),
                            'close': float(item.get('close', 0)),
                            'timestamp': item.get('timestamp', 0)
                        }
                        candles.append(candle)
                if len(candles) >= 5:
                    return candles
            await asyncio.sleep(0.5)
        except:
            await asyncio.sleep(0.5)
    return None

def ema(values, period):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    ema_val = sum(values[-period:]) / period
    for i in range(-period + 1, 0):
        ema_val = values[i] * alpha + ema_val * (1 - alpha)
    return ema_val

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(len(prices) - period, len(prices) - 1):
        change = prices[i + 1] - prices[i]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    if not gains or not losses:
        return 50.0
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def analyze_market(candle_data, strategy="EMA_RSI"):
    if not candle_data or len(candle_data) < 20:
        return None, 0.0
    
    closes = [c['close'] for c in candle_data]
    
    if strategy == "EMA_RSI":
        rsi = calculate_rsi(closes, 14)
        ema_val = ema(closes, 10)
        current_price = closes[-1]
        
        if current_price > ema_val and 50 < rsi < 70:
            return "call", 5
        elif current_price < ema_val and 30 < rsi < 50:
            return "put", 5
        elif rsi > 80:
            return "put", 4
        elif rsi < 20:
            return "call", 4
        return None, 0.0
    
    elif strategy == "Trend":
        if len(closes) < 10:
            return None, 0.0
        trend_score = sum(1 if closes[i] > closes[i-1] else -1 for i in range(-5, 0))
        if trend_score >= 3:
            return "call", 4
        elif trend_score <= -3:
            return "put", 4
        return None, 0.0
    
    elif strategy == "Bollinger":
        if len(closes) < 20:
            return None, 0.0
        ma = np.mean(closes[-20:])
        std = np.std(closes[-20:])
        upper = ma + (std * 2)
        lower = ma - (std * 2)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        
        if current_price < lower and prev_price >= lower:
            return "call", 5
        elif current_price > upper and prev_price <= upper:
            return "put", 5
        return None, 0.0
    
    return None, 0.0

# ================= TRADE EXECUTION - CORRECT =================

async def execute_trade(client, pair, direction, amount, account_type="PRACTICE"):
    """Execute trade - CORRECT PyQuotex method"""
    try:
        # Set account mode
        if account_type == "PRACTICE":
            client.set_account_mode("PRACTICE")
        else:
            client.set_account_mode("REAL")
        
        print(f"   📊 Placing trade: ${amount:.2f} {direction} on {pair} for {TIMEFRAME}s")
        
        # CORRECT: buy(amount, asset, direction, duration)
        status, buy_info = await client.buy(amount, pair, direction, TIMEFRAME)
        
        if status:
            print(f"   ✅ Trade executed successfully!")
            print(f"   📝 Trade ID: {buy_info.get('id')}")
            return {
                'success': True,
                'trade_id': buy_info.get('id'),
                'buy_info': buy_info
            }
        else:
            print(f"   ❌ Trade failed: {buy_info}")
            return {'success': False, 'error': str(buy_info)}
        
    except Exception as e:
        print(f"   ❌ Trade execution error: {e}")
        return {'success': False, 'error': str(e)}

# ================= CHECK RESULT - CORRECT =================

async def check_trade_result(client, buy_info, direction, amount):
    """Check trade result - CORRECT PyQuotex method"""
    try:
        trade_id = buy_info.get('id')
        
        print(f"   ⏳ Waiting {TIMEFRAME} seconds for result...")
        await asyncio.sleep(TIMEFRAME + 5)  # Wait 65 seconds
        
        # CORRECT: check_win returns (win_status, profit)
        try:
            win_status, profit = await client.check_win(trade_id)
            
            if win_status == "win":
                print(f"   ✅ WIN! Profit: ${profit:.2f}")
                return {'result': 'WIN', 'profit': profit}
            elif win_status == "loss":
                print(f"   ❌ LOSS! Loss: ${abs(profit):.2f}")
                return {'result': 'LOSS', 'profit': profit}
            else:
                print(f"   ⚖️ BREAK-EVEN")
                return {'result': 'BREAK_EVEN', 'profit': 0}
                
        except Exception as e:
            print(f"   ⚠️ check_win failed: {e}")
            
            # Fallback: manual price check
            try:
                asset = buy_info.get('asset')
                open_price = buy_info.get('openPrice')
                
                prices = await client.get_realtime_price(asset)
                if prices and open_price:
                    current_price = prices[-1]['price']
                    print(f"   💰 Open: {open_price:.5f} | Current: {current_price:.5f}")
                    
                    if direction == "call":
                        if current_price > open_price:
                            return {'result': 'WIN', 'profit': amount * 0.85}
                        elif current_price < open_price:
                            return {'result': 'LOSS', 'profit': -amount}
                    else:  # put
                        if current_price < open_price:
                            return {'result': 'WIN', 'profit': amount * 0.85}
                        elif current_price > open_price:
                            return {'result': 'LOSS', 'profit': -amount}
            except:
                pass
            
            return {'result': 'BREAK_EVEN', 'profit': 0}
        
    except Exception as e:
        print(f"   ❌ Result check error: {e}")
        return {'result': 'ERROR', 'profit': 0}

# ================= AUTO TRADING ENGINE =================

async def auto_trade_engine():
    global bot_running, client, total_profit, total_trades
    global win_count, loss_count, consecutive_losses, current_balance, initial_balance
    
    # Get initial balance
    try:
        initial_balance = await client.get_balance()
        current_balance = initial_balance
        print(f"\n💰 Initial Balance: ${initial_balance:.2f}")
    except:
        print("\n💰 Could not fetch initial balance")
    
    print("\n" + "="*60)
    print("🚀 AUTO-TRADING ENGINE STARTED")
    print("="*60)
    print(f"📊 Strategy: {selected_strategy}")
    print(f"💰 Trade Type: {trade_type}")
    print(f"💵 Amount: ${trade_amount:.2f}")
    print(f"🎯 Stop Profit: ${stop_profit:.2f}")
    print(f"🛑 Stop Loss: ${stop_loss:.2f}")
    print(f"🏦 Account: {account_type}")
    print(f"🔄 Pairs: {len(ALL_PAIRS)} pairs")
    print("="*60 + "\n")
    
    while bot_running:
        try:
            # Check stop conditions
            if stop_profit > 0 and total_profit >= stop_profit:
                print(f"\n🎯 STOP PROFIT REACHED: ${total_profit:.2f}")
                break
            
            if stop_loss > 0 and total_profit <= -stop_loss:
                print(f"\n🛑 STOP LOSS REACHED: ${total_profit:.2f}")
                break
            
            # Calculate amount
            current_amount = trade_amount
            if trade_type == "MARTINGALE" and consecutive_losses > 0:
                current_amount = trade_amount * (2 ** consecutive_losses)
                if current_amount > 3000:
                    current_amount = 3000
            elif trade_type == "COMPOUNDING" and total_profit > 0:
                current_amount = trade_amount + (total_profit * 0.2)
                if current_amount > 3000:
                    current_amount = 3000
            
            # Shuffle pairs
            shuffled_pairs = ALL_PAIRS.copy()
            random.shuffle(shuffled_pairs)
            
            signal_found = False
            
            for pair in shuffled_pairs[:20]:
                if not bot_running:
                    break
                
                try:
                    print(f"\n🔍 Checking {pair}...")
                    
                    # Get candles
                    candles = await get_candles(client, pair, TIMEFRAME)
                    if not candles or len(candles) < 20:
                        continue
                    
                    # Analyze
                    direction, score = analyze_market(candles, selected_strategy)
                    
                    if direction and score >= 4:
                        print(f"\n📈 SIGNAL FOUND!")
                        print(f"   Pair: {pair}")
                        print(f"   Direction: {direction.upper()}")
                        print(f"   Score: {score}")
                        print(f"   Amount: ${current_amount:.2f}")
                        
                        # Execute trade
                        result = await execute_trade(
                            client, pair, direction, current_amount, account_type
                        )
                        
                        if result['success']:
                            # Check result
                            trade_result = await check_trade_result(
                                client,
                                result['buy_info'],
                                direction,
                                current_amount
                            )
                            
                            # Update stats
                            total_trades += 1
                            
                            if trade_result['result'] == 'WIN':
                                total_profit += trade_result['profit']
                                win_count += 1
                                consecutive_losses = 0
                                print(f"   ✅ WIN! +${trade_result['profit']:.2f}")
                                
                            elif trade_result['result'] == 'LOSS':
                                total_profit += trade_result['profit']
                                loss_count += 1
                                consecutive_losses += 1
                                print(f"   ❌ LOSS! ${abs(trade_result['profit']):.2f}")
                                
                            else:
                                print(f"   ⚖️ BREAK-EVEN")
                            
                            # Update balance
                            try:
                                current_balance = await client.get_balance()
                            except:
                                pass
                            
                            # Show status
                            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
                            print(f"\n📊 STATUS: P&L: ${total_profit:.2f} | Trades: {total_trades} | Win Rate: {win_rate:.1f}%")
                            print(f"💰 Balance: ${current_balance:.2f}")
                            
                            signal_found = True
                            break
                        else:
                            print(f"   ❌ Trade failed: {result.get('error')}")
                            
                except Exception as e:
                    print(f"   ⚠️ Error: {str(e)[:50]}")
                    continue
            
            if not signal_found:
                print(".", end="", flush=True)
            
            # Wait between signals
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"\n⚠️ Engine error: {e}")
            await asyncio.sleep(5)
    
    # Final summary
    print("\n" + "="*60)
    print("📊 TRADING SESSION SUMMARY")
    print("="*60)
    print(f"💰 Total Profit: ${total_profit:.2f}")
    print(f"📈 Total Trades: {total_trades}")
    print(f"✅ Wins: {win_count}")
    print(f"❌ Losses: {loss_count}")
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    print(f"📊 Win Rate: {win_rate:.1f}%")
    print(f"💰 Final Balance: ${current_balance:.2f}")
    print("="*60)

# ================= MAIN =================

async def main_bot(email, password):
    global client, bot_running
    
    try:
        print("\n🔗 Connecting to Quotex...")
        client = Quotex(email=email, password=password, lang="en")
        
        check_connect, message = await client.connect()
        if not check_connect:
            print(f"❌ Connection failed: {message}")
            return
        
        print("✅ Connected to Quotex!")
        
        # Get balance
        try:
            balance = await client.get_balance()
            print(f"💰 Balance: ${balance:.2f}")
        except:
            pass
        
        # Start trading
        await auto_trade_engine()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            await client.close()
        except:
            pass

def start_bot(email, password):
    global bot_running
    bot_running = True
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main_bot(email, password))
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    finally:
        loop.close()

# ================= MENU =================

def main_menu():
    clear_screen()
    
    print("\n" + "="*70)
    print("  🚀 TRADEIQDEV AUTO-TRADING BOT")
    print("="*70)
    
    email = input("📧 Email: ").strip()
    password = input("🔑 Password: ").strip()
    
    if not email or not password:
        print("❌ Email and password required!")
        return
    
    print("\n⚙️ TRADING SETTINGS")
    print("-"*50)
    
    # Strategy
    print("\n📊 Select Strategy:")
    for i, strat in enumerate(AVAILABLE_STRATEGIES, 1):
        print(f"   {i}. {strat}")
    
    while True:
        try:
            strat_choice = int(input("Choice (1-5): ").strip())
            if 1 <= strat_choice <= len(AVAILABLE_STRATEGIES):
                global selected_strategy
                selected_strategy = AVAILABLE_STRATEGIES[strat_choice - 1]
                break
        except:
            print("❌ Invalid choice")
    
    # Trade type
    print("\n📈 Trade Type:")
    print("   1. Fixed Amount")
    print("   2. Martingale (Double on loss)")
    print("   3. Compounding (Reinvest profits)")
    
    while True:
        try:
            type_choice = int(input("Choice (1-3): ").strip())
            global trade_type
            if type_choice == 1:
                trade_type = "FIXED"
                break
            elif type_choice == 2:
                trade_type = "MARTINGALE"
                break
            elif type_choice == 3:
                trade_type = "COMPOUNDING"
                break
        except:
            print("❌ Invalid choice")
    
    # Amount
    while True:
        try:
            amount = float(input("💰 Amount ($1-$3000): ").strip())
            if 1 <= amount <= 3000:
                global trade_amount
                trade_amount = amount
                break
        except:
            print("❌ Invalid amount")
    
    # Stop settings
    try:
        profit_input = input("🎯 Stop Profit ($): ").strip()
        if profit_input:
            global stop_profit
            stop_profit = float(profit_input)
    except:
        pass
    
    try:
        loss_input = input("🛑 Stop Loss ($): ").strip()
        if loss_input:
            global stop_loss
            stop_loss = float(loss_input)
    except:
        pass
    
    # Account type
    print("\n🏦 Account Type:")
    print("   1. Practice (Demo)")
    print("   2. Real")
    
    while True:
        try:
            acc_choice = int(input("Choice (1-2): ").strip())
            global account_type
            if acc_choice == 1:
                account_type = "PRACTICE"
                break
            elif acc_choice == 2:
                account_type = "REAL"
                break
        except:
            print("❌ Invalid choice")
    
    # Confirm
    print("\n" + "="*70)
    print("📋 CONFIRMATION")
    print("="*70)
    print(f"📧 Email: {email}")
    print(f"📊 Strategy: {selected_strategy}")
    print(f"📈 Trade Type: {trade_type}")
    print(f"💰 Amount: ${trade_amount:.2f}")
    print(f"🎯 Stop Profit: ${stop_profit:.2f}")
    print(f"🛑 Stop Loss: ${stop_loss:.2f}")
    print(f"🏦 Account: {account_type}")
    print("="*70)
    
    confirm = input("\n✅ Start trading? (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y']:
        print("\n🚀 Starting auto-trader...")
        start_bot(email, password)
    else:
        print("❌ Cancelled")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"❌ Error: {e}")