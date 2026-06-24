import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from colorama import Fore, Style, init
import time
from pyfiglet import Figlet

init(autoreset=True)

# -------------------- LOGIN --------------------
correct_username = "@Tradeiq"
correct_password = "TradingM"

while True:
    username = input("Enter Username: ")
    password = input("Enter Password: ")
    if username == correct_username and password == correct_password:
        print(Fore.GREEN + Style.BRIGHT + "\nLogin Successful ✅\n")
        break
    else:
        print(Fore.RED + "Invalid credentials! Try again.\n")

# -------------------- VIP Banner --------------------
fig = Figlet(font='slant')  # font can be changed to 'big', 'starwars', etc
print(Fore.YELLOW + fig.renderText("TRADEIQ"))
print(Fore.CYAN + Style.BRIGHT + "Developed by Planalto\n")

# -------------------- API Setup --------------------
VIP_NAME = "CQM"
print(Fore.MAGENTA + Style.BRIGHT + f"\n🔥🔥 VIP SIGNAL GENERATOR ({VIP_NAME}) 🔥🔥\n")

API_KEY = "eb2326208921b413a87728832f191f03-d9be68b74884f7d3107b9f05ca305319"
BASE_URL = "https://api-fxpractice.oanda.com/v3/instruments"
ALL_PAIRS = [
    "EUR_USD","GBP_AUD","EUR_AUD","EUR_JPY","GBP_CAD","USD_JPY",
    "EUR_CHF","NZD_CAD","XAU_USD","XAG_USD","USD_CAD","AUD_CAD","GBP_CHF","USD_INR","EUR_GBP","AUD_CHF","CAD_JPY",
    "GBP_JPY","EUR_CAD","AUD_JPY","GBP_NZD","USD_MXN"
]
headers = {"Authorization": f"Bearer {API_KEY}"}

# -------------------- Interactive Inputs --------------------
print("Available Pairs:")
for p in ALL_PAIRS:
    print("-", p)
pair_input = input("\nChoose pairs (ALL or comma separated): ")
pairs = ALL_PAIRS if pair_input.strip().upper() == "ALL" else [p.strip() for p in pair_input.split(",")]

start_time = input("Enter Start time (HH:MM, PKT): ")
end_time   = input("Enter End time (HH:MM, PKT): ")
signal_limit = int(input("Number of signals to show: "))
mode = int(input("Mode (1 = upcoming, 2 = full): "))
min_conf = int(input("Minimum confidence % (e.g., 90): "))

# -------------------- Pair Loading Animation --------------------
print("\nLoading Pairs...")
for pair in pairs:
    print(Fore.MAGENTA + f"Loading {pair}...", end="\r")
    time.sleep(0.5)
print(Fore.GREEN + "All pairs loaded successfully ✅\n")

# -------------------- Data Fetch --------------------
def get_data(pair, total_candles=20000, granularity="M1"):
    max_count = 5000
    all_candles = []
    remaining = total_candles
    end_time_param = None
    while remaining > 0:
        count = min(max_count, remaining)
        url = f"{BASE_URL}/{pair}/candles?granularity={granularity}&count={count}&price=M"
        if end_time_param:
            url += f"&to={end_time_param}"
        r = requests.get(url, headers=headers, timeout=10).json()
        if "candles" not in r or not r["candles"]:
            break
        batch = [{"time": c["time"], "open": float(c["mid"]["o"]), "close": float(c["mid"]["c"])} for c in r["candles"]]
        all_candles = batch + all_candles
        remaining -= len(batch)
        end_time_param = batch[0]["time"]
        if len(batch) < count:
            break
    if not all_candles:
        return pd.DataFrame()
    df = pd.DataFrame(all_candles)
    df["time"] = pd.to_datetime(df["time"]) + timedelta(hours=5)
    df["minute"] = df["time"].dt.strftime("%H:%M")
    df["move"] = abs(df["close"] - df["open"])
    df["dir"] = np.where(df["close"] > df["open"], "CALL", "PUT")
    return df

# -------------------- Analyze --------------------
def analyze(df, start_time, end_time, min_conf=90):
    if df.empty:
        return []
    grouped = df.groupby(["minute","dir"]).size().unstack(fill_value=0)
    grouped["total"] = grouped.sum(axis=1)
    grouped["CALL_WR"] = grouped.get("CALL",0) / grouped["total"] * 100
    grouped["PUT_WR"]  = grouped.get("PUT",0) / grouped["total"] * 100
    volatility = df.groupby("minute")["move"].mean()
    signals = []
    for t in grouped.index:
        if not (start_time <= t <= end_time):
            continue
        if volatility.get(t,0) < volatility.mean():
            continue
        if grouped["CALL_WR"][t] >= min_conf:
            score = round(grouped["CALL_WR"][t]/10 + volatility[t]*1000,2)
            signals.append((t,"CALL",score))
        if grouped["PUT_WR"][t] >= min_conf:
            score = round(grouped["PUT_WR"][t]/10 + volatility[t]*1000,2)
            signals.append((t,"PUT",score))
    # gap filter
    signals.sort(key=lambda x: x[2], reverse=True)
    filtered = []
    seen_minutes = set()
    for s in signals:
        if s[0] not in seen_minutes:
            filtered.append(s)
            seen_minutes.add(s[0])
    return filtered

# -------------------- Generate Signals --------------------
def generate_signals():
    all_signals = []
    for pair in pairs:
        print(Fore.CYAN + f"\nProcessing {pair}...")
        df = get_data(pair, total_candles=20000)
        pair_signals = analyze(df, start_time, end_time, min_conf)
        pair_signals = [(t,pair,d,score) for t,d,score in pair_signals]
        all_signals += pair_signals

    # Ascending time order
    all_signals = sorted(all_signals, key=lambda x: x[0])

    current_time = datetime.now().strftime("%H:%M")
    if mode == 1:
        all_signals = [s for s in all_signals if s[0] > current_time]

    all_signals = all_signals[:signal_limit]

    print(Fore.YELLOW + "\n🔥 VIP FUTURE SIGNALS READY (PKT)\n")
    print(Fore.MAGENTA + f"DATE: {datetime.now().date()}\n")
    for s in all_signals:
        color = Fore.GREEN + Style.BRIGHT if s[2] == "CALL" else Fore.RED + Style.BRIGHT
        pair_color = Fore.CYAN + Style.BRIGHT
        print(f"{s[0]}  {pair_color}{s[1]}  {color}{s[2]}  M1  ⭐{s[3]}")

# -------------------- Run --------------------
generate_signals()
