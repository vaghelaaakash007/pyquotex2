#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADEIQDEV x AI BOT - Professional Trading System
Termux / Kali Linux Compatible Version
"""

import os
import sys

# Termux/Kali compatibility fixes
if os.name == 'posix':
    os.environ['TERM'] = os.environ.get('TERM', 'xterm-256color')
    # Fix for Termux display
    if 'TERMUX_VERSION' in os.environ:
        os.system('termux-wake-lock 2>/dev/null || true')

# Suppress PIL warnings
import warnings
warnings.filterwarnings('ignore')

import ssl
import asyncio
import logging
import os
import threading
import time
import calendar
import uuid
import hashlib
import random
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import numpy as np
import requests
from pyquotex.stable_api import Quotex
from colorama import init, Fore, Back, Style
from collections import deque
import concurrent.futures
import socket
import socks
import urllib3
from urllib3.util.ssl_ import create_urllib3_context
import json
import pytz
from typing import Dict, List, Any
from io import BytesIO
import sys

# --- নতুন লাইব্রেরি যোগ করা হলো ---
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import telegram
from telegram import constants
# --- Telethon লাইব্রেরি যোগ করা হলো ---
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityCustomEmoji,
    MessageMediaPhoto,
    MessageMediaDocument,
)
# --- নতুন লাইব্রেরি যোগ করা হলো ---

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize colorama
init(autoreset=True)

# ================= JSONBin কনফিগারেশন =================
JSONBIN_URL = ""
JSONBIN_API_KEY = ""  # API Key

# ================= ডিভাইস ভেরিফিকেশন =================
def get_device_id():
    """ইউনিক ডিভাইস আইডি জেনারেট করে"""  
    try:
        # মেশিনের হোস্টনেম এবং ইউজারনেম কম্বিনেশন
        hostname = socket.gethostname()
        username = os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USER', 'unknown')
        device_string = f"{hostname}_{username}_{sys.platform}"
        
        # SHA256 হ্যাশ জেনারেট
        hash_obj = hashlib.sha256(device_string.encode())
        device_id = f"DEV-{hash_obj.hexdigest()[:16].upper()}"
        return device_id
    except:
        # Fallback to UUID
        return f"DEV-{str(uuid.uuid4())[:16].upper()}"

def check_device_access():
    """ডিভাইস অ্যাকসেস চেক করে JSONBin থেকে"""
    device_id = get_device_id()
    
    try:
        headers = {
            "X-Master-Key": JSONBIN_API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.get(JSONBIN_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            users = data.get('record', [])
            
            for user in users:
                if user.get('device_id') == device_id:
                    # Check if user is allowed
                    if not user.get('allow_user', False):
                        return False, device_id, "User not allowed"
                    
                    # Check expiration date
                    valid_date_str = user.get('valid_date')
                    if valid_date_str:
                        try:
                            valid_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00'))
                            current_date = datetime.now(timezone.utc)
                            
                            if valid_date > current_date:
                                return True, device_id, user.get('username', 'User')
                            else:
                                return False, device_id, "Subscription expired"
                        except:
                            return False, device_id, "Invalid date format"
                    
                    return True, device_id, user.get('username', 'User')
            
            # Device ID not found
            return False, device_id, "Device not registered"
        
        else:
            # Server error - try local backup
            return check_local_access(device_id)
            
    except Exception as e:
        print(f"JSONBin connection error: {e}")
        # Try local backup
        return check_local_access(device_id)

def check_local_access(device_id):
    """লোকাল ব্যাকআপ ফাইল থেকে অ্যাকসেস চেক করে"""
    try:
        if os.path.exists("access_backup.json"):
            with open("access_backup.json", 'r') as f:
                users = json.load(f)
                
            for user in users:
                if user.get('device_id') == device_id:
                    if not user.get('allow_user', False):
                        return False, device_id, "User not allowed"
                    
                    valid_date_str = user.get('valid_date')
                    if valid_date_str:
                        try:
                            valid_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00'))
                            current_date = datetime.now(timezone.utc)
                            
                            if valid_date > current_date:
                                return True, device_id, user.get('username', 'User')
                            else:
                                return False, device_id, "Subscription expired"
                        except:
                            return False, device_id, "Invalid date format"
                    
                    return True, device_id, user.get('username', 'User')
    except:
        pass
    
    return False, device_id, "No access found"

# ================= নতুন কনফিগারেশন: বাদ দিতে হবে যে OTC পেয়ারগুলো =================
USER_EXCLUDE_LIST = [
    "EURUSD_otc", "EURGBP_otc", "GBPJPY_otc", "CADJPY_otc", "USDJPY_otc",
    "CADCHF_otc", "USDCHF_otc", "EURAUD_otc", "AUDCAD_otc", "GBPCAD_otc",
    "USDCAD_otc", "AUDJPY_otc", "GBPAUD_otc", "EURCHF_otc", "GBPCHF_otc",
    "AUDCHF_otc", "AUDUSD_otc", "EURJPY_otc"
]

OTC_PAIRS_TO_EXCLUDE = set()
for p in USER_EXCLUDE_LIST:
    OTC_PAIRS_TO_EXCLUDE.add(p.lower())
    OTC_PAIRS_TO_EXCLUDE.add(p.upper().replace('_OTC', '-OTC').replace('_otc', '-OTC'))
    OTC_PAIRS_TO_EXCLUDE.add(p.upper().replace('-OTC', '_OTC'))

ANALYZE_ALL_PAIRS = False # False মানে তালিকাভুক্ত OTC পেয়ারগুলো বাদ দেওয়া হবে
# =================================================================================

# --- সিগন্যাল ইমেজ কনফিগারেশন (আপডেট) ---
TELEGRAM_BOT_TOKEN = ""  # Set your bot token here or via settings
TELEGRAM_CHAT_ID = "-"
SIGNAL_USERNAME = "@Tradeiqdev"  # নতুন ভেরিয়েবল
SEND_PHOTO_WITH_SIGNAL = False # False: কাস্টম ফটো, True: মার্কেট চার্ট
CHART_BACKGROUND_IMAGE_PATH = "" # খালি রাখলে সলিড ব্ল্যাক ব্যাকগ্রাউন্ড হবে
# --- সিগন্যাল ইমেজ কনফিগারেশন (আপডেট) ---

# ================= নতুন টেলিগ্রাম ক্লায়েন্ট কনফিগারেশন =================
TELEGRAM_API_ID = 0  # Set your API ID here (get from my.telegram.org)
TELEGRAM_API_HASH = ''  # Set your API Hash here (get from my.telegram.org)
TELEGRAM_PHONE_NUMBER = ''  # Set your phone number here (with country code)
TELEGRAM_SOURCE_CHANNEL = ""  # সোর্স চ্যানেল ইউজারনেম (এখানে @ ছাড়া) - leave empty to disable
TELEGRAM_TARGET_CHANNELS = []  # টার্গেট চ্যানেল আইডি (লিস্ট)
PREMIUM_EMOJI_MODE = False  # ডিফল্ট OFF
PREMIUM_EMOJI_TARGET = True  # নতুন: টার্গেট চ্যানেলে প্রিমিয়াম ইমোজি পাঠানো ON/OFF
# =======================================================================

# ================= IMPORTANT CHANGE: Signal interval now 3-5 minutes =================
SIGNAL_INTERVAL_MIN = 180  # 3 minutes in seconds
SIGNAL_INTERVAL_MAX = 300  # 5 minutes in seconds
# Generate random interval between 3-5 minutes
def get_next_signal_interval():
    return random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
# ====================================================================================

TIMEFRAME = 60
CANDLE_FETCH_ATTEMPTS = 3
MAX_CANDLES = 30 # চার্ট তৈরির জন্য আরও বেশি ক্যান্ডেল
MARTINGALE_STEPS = 1
PARTIAL_RESULTS_INTERVAL = 300
SAVE_FILE = "TRADEIQDEV-ss.json"

# =================== নতুন কাস্টম পেয়ার কনফিগারেশন ===================
CUSTOM_PAIRS_MODE = False
CUSTOM_PAIRS_LIST = ["BRLUSD_otc", "USDPKR_otc"]
# ====================================================================

# =================== নতুন সেটিংস: EMA, RSI, Strategy, Mark Candle ===================
EMA_PERIOD = 10
RSI_PERIOD = 14
CURRENT_STRATEGY = "EMA_RSI"  # ডিফল্ট স্ট্র্যাটেজি
MARK_RESULT_CANDLE = False  # ডিফল্ট OFF
MIN_SIGNAL_SCORE = 4  # মিনিমাম স্কোর ফিল্টার
AVAILABLE_STRATEGIES = ["EMA_RSI", "Trend", "Bollinger", "Support_Resistance", "Trend_Reverse", "Price_Action", "Supertrend", "FVG_Strategy"]  # নতুন স্ট্র্যাটেজি যোগ করা হলো
# ====================================================================================

# ================= নতুন চার্ট সেটিংস =================
SUPPORT_RESISTANCE_LINES = False
MOVING_AVERAGE_LINES = False
SUPPORT_RESISTANCE_STRATEGY = False
SHOW_GRID_LINES = True
SHOW_PRICE_SCALE = True
TREND_LINES = False
BACKGROUND_TRANSPARENCY = 50  # 50% transparency (আগের চেয়ে কম)
CHART_TEXT_GLOW = 0  # গ্লো ইফেক্ট বন্ধ
WATERMARK_ON = True
WATERMARK_TEXT = "TRADEIQDEV x AI BOT - TRADEIQDEV TRADER SS PRO"
SIGNAL_HEADER_TEXT = "TRADEIQDEV x AI BOT"
CHART_HEADER_TEXT = "TRADEIQDEV x AI BOT - TRADEIQDEV TRADER SS PRO SIGNAL"

# ================= নতুন অ্যাডভান্সড ফিচার সেটিংস =================
PARABOLIC_SAR_LINES = False  # প্যারাবলিক SAR লাইন ON/OFF
GAP_DRAWING = False  # GAP ড্রয়িং ON/OFF (FVG গ্যাপ)
REVERSE_AREA_DRAWING = False  # রিভার্স এরিয়া ড্রয়িং ON/OFF
ADVANCED_ANALYSIS = False  # অ্যাডভান্সড অ্যানালাইসিস ON/OFF
CUSTOM_LINK = ""  # কাস্টম লিংক (খালি থাকলে ডিফল্ট টেক্সট)
FVG_GAP_DRAW = False  # নতুন: FVG গ্যাপ ড্রয়িং ON/OFF
BOT_ALERT_ON = True  # নতুন: বট ON/OFF এ্যালার্ট ON/OFF
CANDLE_UP_COLOR = (0, 200, 0)  # নতুন: উপরের ক্যান্ডেল কালার (ডিফল্ট: GREEN)
CANDLE_DOWN_COLOR = (255, 50, 50)  # নতুন: নিচের ক্যান্ডেল কালার (ডিফল্ট: RED)
EMA_LINE_CHART = False  # নতুন: EMA লাইন চার্ট ON/OFF
SUPERTREND_CHART = False  # নতুন: সুপারট্রেন্ড চার্ট ON/OFF
SUPERTREND_STRATEGY = False  # নতুন: সুপারট্রেন্ড স্ট্র্যাটেজি ON/OFF
SNR_LINES = False  # নতুন: SNR লাইন ON/OFF
# ================================================================

bot_running = False
last_signal_time = 0
trade_results = []
signal_count = 0
signal_queue = deque()
signal_executor = None
current_signal_task = None
last_partial_results_time = 0
start_time = None
next_signal_interval = get_next_signal_interval()  # Next signal timing
continuous_analysis = True  # নতুন: ধারাবাহিক অ্যানালাইসিসের জন্য

PAIR_NAMES = {
    "BRLUSD_otc": "BRL/USD", "USDPKR_otc": "USD/PKR", "USDMXN_otc": "USD/MXN",
    "USDARS_otc": "USD/ARS", "USDBDT_otc": "USD/BDT", "USDCOP_otc": "USD/COP",
    "USDINR_otc": "USD/INR", "USDPHP_otc": "USD/PHP", "USDDZD_otc": "USD/DZD",
    "USDIDR_otc": "USD/IDR", "USDNGN_otc": "USD/NGN", "USDTRY_otc": "USD/TRY",
    "USDZAR_otc": "USD/ZAR", "USDEGP_otc": "USD/EGP", "CADCHF_otc": "CAD/CHF"
}

# Custom SSL adapter
class BangladeshSSLAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super(BangladeshSSLAdapter, self).init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount('https://', BangladeshSSLAdapter())
session.verify = False

# Lazy initialization - bot will be created when Telegram functions are actually called
bot = None

def get_bot():
    global bot
    if bot is None and TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN.strip() and TELEGRAM_BOT_TOKEN != "":
        try:
            bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        except Exception as e:
            print(f"⚠️ Telegram bot init failed: {e}")
            bot = None
    return bot

UTC_PLUS_6 = pytz.timezone('Asia/Dhaka')

def ts_to_dt(ts):
    """Convert timestamp to UTC+6 datetime"""
    if ts is None: return None
    try:
        ts = int(ts)
        if ts > 1_000_000_000_000: ts = ts / 1000
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt_utc.astimezone(UTC_PLUS_6)
    except:
        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(UTC_PLUS_6)
        except: return None

# ================= Premium Emoji Mapping =================
PREMIUM_EMOJI_MAP = {
    "1": 6325797905663791037,
    "2": 5472416843438246859,
    "3": 6325437171360600446,
    "4": 6325717349257187998,
    "5": 6257905072693318304,
    "6": 5238052418104610782,
    "7": 6246738501321102898,
    "8": 5310278924616356636,
    "9": 5429381339851796035,
    "10": 6264785189394717307,
    "11": 6267086316907795595,
    "12": 6325667390197600621,
    "13": 6285048454255220485,
    "14": 6267068789146260253,
    "15": 5384513813670279219,

    # ---- Added Emojis ----
    "16": 6264696987946324240,
    "17": 5269337080147748373,
    "18": 5212985021870123409,
    "19": 5188234920639632382,
    "20": 5310278924616356636,
    "21": 5028746137645876535,
    "22": 5971789963639917544,
    "23": 5972177777711910216,
    "24": 5098154789129159560,
    "25": 6275878213746955453,
    "26": 5204284487575285695,

    "27": 6285259732286445237,
    "28": 5215484787325676090,
    "29": 5208880351690112495,
    "30": 5208880351690112495,
    "31": 5208880351690112495,
    "32": 6116349066650589320,
    "33": 5372904134817112673,
    "34": 6118414920150160494,
    "35": 5231489647946768652,

    "36": 5028325978175177540,
    "37": 5215484787325676090,
    "38": 5971936104197131725,
    "39": 5971936104197131725,
    "40": 5971936104197131725,
    "41": 5265204093248364532,
    "42": 6118414920150160494,
    "43": 5231489647946768652,
}

async def convert_to_premium(text, original_entities=None):
    """Convert regular text to premium emoji text"""
    if original_entities is None:
        original_entities = []

    all_entities = list(original_entities)
    offset = 0
    converted_text = ""

    for char in text:
        char_length = len(char.encode('utf-16-le')) // 2
        if char in PREMIUM_EMOJI_MAP:
            all_entities.append(MessageEntityCustomEmoji(
                offset=offset,
                length=char_length,
                document_id=PREMIUM_EMOJI_MAP[char]
            ))
        converted_text += char
        offset += char_length

    return converted_text, all_entities

# ================= টেলিগ্রাম ক্লায়েন্ট ফাংশন =================

async def telegram_client_task():
    """টেলিগ্রাম ক্লায়েন্ট চালু করে সোর্স চ্যানেল থেকে মেসেজ ফরওয়ার্ড করে"""
    global TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER
    global TELEGRAM_SOURCE_CHANNEL, TELEGRAM_TARGET_CHANNELS, PREMIUM_EMOJI_MODE, PREMIUM_EMOJI_TARGET
    
    client = TelegramClient('premium_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(rainbow_text("📱 Telegram login required..."))
            await client.send_code_request(TELEGRAM_PHONE_NUMBER)
            code = input(rainbow_text("📩 Enter the login code from Telegram: "))
            await client.sign_in(TELEGRAM_PHONE_NUMBER, code)

        @client.on(events.NewMessage(chats=TELEGRAM_SOURCE_CHANNEL))
        async def handler(event):
            try:
                print(rainbow_text(f"📨 Received message from @{TELEGRAM_SOURCE_CHANNEL}: {event.raw_text[:50]}..."))

                message_text = event.raw_text
                original_entities = event.message.entities if event.message.entities else []

                if PREMIUM_EMOJI_MODE:
                    converted_text, entities = await convert_to_premium(message_text, original_entities)
                else:
                    converted_text = message_text
                    entities = original_entities

                # যদি PREMIUM_EMOJI_TARGET False হয়, তাহলে শুধুমাত্র টার্গেট চ্যানেলে পাঠানো হবে না
                if PREMIUM_EMOJI_TARGET:
                    # সব টার্গেট চ্যানেলে পাঠাও
                    for target_id in TELEGRAM_TARGET_CHANNELS:
                        if isinstance(event.message.media, (MessageMediaPhoto, MessageMediaDocument)):
                            await client.send_file(
                                target_id,
                                event.message.media,
                                caption=converted_text if converted_text.strip() else None,
                                formatting_entities=entities if converted_text.strip() else None
                            )
                            print(rainbow_text(f"📷 Sent media with caption to {target_id}"))
                        else:
                            if converted_text.strip():
                                await client.send_message(
                                    target_id,
                                    converted_text,
                                    formatting_entities=entities
                                )
                                print(rainbow_text(f"✅ Forwarded text to {target_id}"))
                            else:
                                print(rainbow_text("⚠️ No text to send."))
                else:
                    print(rainbow_text("ℹ️ Premium emoji target is OFF. Skipping target channels."))

            except Exception as e:
                print(rainbow_text(f"❌ Error handling message: {e}"))

        print(rainbow_text(f"👂 Listening for messages from @{TELEGRAM_SOURCE_CHANNEL}..."))
        await client.run_until_disconnected()

    except Exception as e:
        print(rainbow_text(f"❌ Telegram client error: {e}"))
    finally:
        await client.disconnect()

def start_telegram_client():
    """টেলিগ্রাম ক্লায়েন্ট শুরু করে"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telegram_client_task())

# ================= রেইনবো টেক্সট ফাংশন =================

def rainbow_text(text):
    return str(text)

def rainbow_line(text):
    return str(text)

# ================= ফ্যান্সি ফন্ট ফাংশন (আপডেট) =================

def fancy_font(text):
    """Normal font"""
    return str(text)  

# ================= ডাটা ম্যানেজমেন্ট ফাংশন (আপডেট) =================

def load_trade_results():
    """JSON ফাইল থেকে ডাটা লোড করে"""
    global trade_results, MARTINGALE_STEPS, PARTIAL_RESULTS_INTERVAL, SEND_PHOTO_WITH_SIGNAL
    global CHART_BACKGROUND_IMAGE_PATH, ANALYZE_ALL_PAIRS, CUSTOM_PAIRS_MODE, CUSTOM_PAIRS_LIST
    global EMA_PERIOD, RSI_PERIOD, CURRENT_STRATEGY, MARK_RESULT_CANDLE, MIN_SIGNAL_SCORE
    global SUPPORT_RESISTANCE_LINES, MOVING_AVERAGE_LINES, SUPPORT_RESISTANCE_STRATEGY
    global SHOW_GRID_LINES, SHOW_PRICE_SCALE, TELEGRAM_BOT_TOKEN, TREND_LINES, BACKGROUND_TRANSPARENCY
    global TELEGRAM_CHAT_ID, SIGNAL_USERNAME, SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX
    global TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER
    global TELEGRAM_SOURCE_CHANNEL, TELEGRAM_TARGET_CHANNELS, PREMIUM_EMOJI_MODE, PREMIUM_EMOJI_TARGET
    global CHART_TEXT_GLOW, WATERMARK_ON, WATERMARK_TEXT, SIGNAL_HEADER_TEXT, CHART_HEADER_TEXT
    global PARABOLIC_SAR_LINES, GAP_DRAWING, REVERSE_AREA_DRAWING, ADVANCED_ANALYSIS, CUSTOM_LINK
    global FVG_GAP_DRAW, BOT_ALERT_ON, CANDLE_UP_COLOR, CANDLE_DOWN_COLOR, EMA_LINE_CHART
    global SUPERTREND_CHART, SUPERTREND_STRATEGY, SNR_LINES
    
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

                if isinstance(data, list):
                    trade_results = data
                elif isinstance(data, dict):
                    trade_results = data.get('all_results', [])

                    settings = data.get('settings', {})
                    MARTINGALE_STEPS = settings.get('MARTINGALE_STEPS', MARTINGALE_STEPS)
                    PARTIAL_RESULTS_INTERVAL = settings.get('PARTIAL_RESULTS_INTERVAL', PARTIAL_RESULTS_INTERVAL)
                    SEND_PHOTO_WITH_SIGNAL = settings.get('SEND_MARKET_CHART', settings.get('SEND_PHOTO_WITH_SIGNAL', SEND_PHOTO_WITH_SIGNAL))
                    CHART_BACKGROUND_IMAGE_PATH = settings.get('CHART_BACKGROUND_IMAGE_PATH', CHART_BACKGROUND_IMAGE_PATH)
                    ANALYZE_ALL_PAIRS = settings.get('ANALYZE_ALL_PAIRS', ANALYZE_ALL_PAIRS)
                    
                    # --- নতুন সেটিং লোড ---
                    CUSTOM_PAIRS_MODE = settings.get('CUSTOM_PAIRS_MODE', CUSTOM_PAIRS_MODE)
                    loaded_list = settings.get('CUSTOM_PAIRS_LIST', CUSTOM_PAIRS_LIST)
                    if isinstance(loaded_list, str):
                        CUSTOM_PAIRS_LIST = [p.strip() for p in loaded_list.split(',') if p.strip()]
                    elif isinstance(loaded_list, list):
                        CUSTOM_PAIRS_LIST = loaded_list
                    EMA_PERIOD = settings.get('EMA_PERIOD', EMA_PERIOD)
                    RSI_PERIOD = settings.get('RSI_PERIOD', RSI_PERIOD)
                    CURRENT_STRATEGY = settings.get('CURRENT_STRATEGY', CURRENT_STRATEGY)
                    MARK_RESULT_CANDLE = settings.get('MARK_RESULT_CANDLE', MARK_RESULT_CANDLE)
                    MIN_SIGNAL_SCORE = settings.get('MIN_SIGNAL_SCORE', MIN_SIGNAL_SCORE)
                    
                    # নতুন চার্ট সেটিংস
                    SUPPORT_RESISTANCE_LINES = settings.get('SUPPORT_RESISTANCE_LINES', SUPPORT_RESISTANCE_LINES)
                    MOVING_AVERAGE_LINES = settings.get('MOVING_AVERAGE_LINES', MOVING_AVERAGE_LINES)
                    SUPPORT_RESISTANCE_STRATEGY = settings.get('SUPPORT_RESISTANCE_STRATEGY', SUPPORT_RESISTANCE_STRATEGY)
                    SHOW_GRID_LINES = settings.get('SHOW_GRID_LINES', SHOW_GRID_LINES)
                    SHOW_PRICE_SCALE = settings.get('SHOW_PRICE_SCALE', SHOW_PRICE_SCALE)
                    TREND_LINES = settings.get('TREND_LINES', TREND_LINES)
                    BACKGROUND_TRANSPARENCY = settings.get('BACKGROUND_TRANSPARENCY', BACKGROUND_TRANSPARENCY)
                    CHART_TEXT_GLOW = settings.get('CHART_TEXT_GLOW', CHART_TEXT_GLOW)
                    WATERMARK_ON = settings.get('WATERMARK_ON', WATERMARK_ON)
                    WATERMARK_TEXT = settings.get('WATERMARK_TEXT', WATERMARK_TEXT)
                    SIGNAL_HEADER_TEXT = settings.get('SIGNAL_HEADER_TEXT', SIGNAL_HEADER_TEXT)
                    CHART_HEADER_TEXT = settings.get('CHART_HEADER_TEXT', CHART_HEADER_TEXT)
                    
                    # নতুন অ্যাডভান্সড সেটিংস
                    PARABOLIC_SAR_LINES = settings.get('PARABOLIC_SAR_LINES', PARABOLIC_SAR_LINES)
                    GAP_DRAWING = settings.get('GAP_DRAWING', GAP_DRAWING)
                    REVERSE_AREA_DRAWING = settings.get('REVERSE_AREA_DRAWING', REVERSE_AREA_DRAWING)
                    ADVANCED_ANALYSIS = settings.get('ADVANCED_ANALYSIS', ADVANCED_ANALYSIS)
                    CUSTOM_LINK = settings.get('CUSTOM_LINK', CUSTOM_LINK)
                    
                    # নতুন ফিচার সেটিংস
                    FVG_GAP_DRAW = settings.get('FVG_GAP_DRAW', FVG_GAP_DRAW)
                    BOT_ALERT_ON = settings.get('BOT_ALERT_ON', BOT_ALERT_ON)
                    
                    # ক্যান্ডেল কালার সেটিংস
                    candle_up_color = settings.get('CANDLE_UP_COLOR', CANDLE_UP_COLOR)
                    candle_down_color = settings.get('CANDLE_DOWN_COLOR', CANDLE_DOWN_COLOR)
                    
                    if isinstance(candle_up_color, list) and len(candle_up_color) == 3:
                        CANDLE_UP_COLOR = tuple(candle_up_color)
                    if isinstance(candle_down_color, list) and len(candle_down_color) == 3:
                        CANDLE_DOWN_COLOR = tuple(candle_down_color)
                    
                    # EMA এবং সুপারট্রেন্ড সেটিংস
                    EMA_LINE_CHART = settings.get('EMA_LINE_CHART', EMA_LINE_CHART)
                    SUPERTREND_CHART = settings.get('SUPERTREND_CHART', SUPERTREND_CHART)
                    SUPERTREND_STRATEGY = settings.get('SUPERTREND_STRATEGY', SUPERTREND_STRATEGY)
                    SNR_LINES = settings.get('SNR_LINES', SNR_LINES)
                    
                    # Telegram settings
                    TELEGRAM_BOT_TOKEN = settings.get('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN)
                    TELEGRAM_CHAT_ID = settings.get('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
                    SIGNAL_USERNAME = settings.get('SIGNAL_USERNAME', SIGNAL_USERNAME)
                    SIGNAL_INTERVAL_MIN = settings.get('SIGNAL_INTERVAL_MIN', SIGNAL_INTERVAL_MIN)
                    SIGNAL_INTERVAL_MAX = settings.get('SIGNAL_INTERVAL_MAX', SIGNAL_INTERVAL_MAX)
                    
                    # Telegram client settings
                    TELEGRAM_API_ID = settings.get('TELEGRAM_API_ID', TELEGRAM_API_ID)
                    TELEGRAM_API_HASH = settings.get('TELEGRAM_API_HASH', TELEGRAM_API_HASH)
                    TELEGRAM_PHONE_NUMBER = settings.get('TELEGRAM_PHONE_NUMBER', TELEGRAM_PHONE_NUMBER)
                    TELEGRAM_SOURCE_CHANNEL = settings.get('TELEGRAM_SOURCE_CHANNEL', TELEGRAM_SOURCE_CHANNEL)
                    TELEGRAM_TARGET_CHANNELS = settings.get('TELEGRAM_TARGET_CHANNELS', TELEGRAM_TARGET_CHANNELS)
                    PREMIUM_EMOJI_MODE = settings.get('PREMIUM_EMOJI_MODE', PREMIUM_EMOJI_MODE)
                    PREMIUM_EMOJI_TARGET = settings.get('PREMIUM_EMOJI_TARGET', PREMIUM_EMOJI_TARGET)
                    # --- নতুন সেটিং লোড ---

                else:
                    trade_results = []
            print(rainbow_text(f"✅ 𝙻𝚘𝚊𝚍𝚎𝚍 {len(trade_results)} 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚊𝚗𝚍 𝚜𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚏𝚛𝚘𝚖 {SAVE_FILE}"))
            return True
        else:
            print(rainbow_text(f"⚠ 𝙽𝚘 𝚍𝚊𝚝𝚊 𝚏𝚒𝚕𝚎 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚝𝚊𝚛𝚝𝚒𝚗𝚐 𝚏𝚛𝚎𝚜𝚑..."))
            trade_results = []
            return False
    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚕𝚘𝚊𝚍𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜: {e}"))
        trade_results = []
        return False

def save_trade_results():
    """ডাটা এবং সেটিংস JSON ফাইলে সেভ করে"""
    global ANALYZE_ALL_PAIRS, SEND_PHOTO_WITH_SIGNAL, CUSTOM_PAIRS_MODE, CUSTOM_PAIRS_LIST
    global EMA_PERIOD, RSI_PERIOD, CURRENT_STRATEGY, MARK_RESULT_CANDLE, MIN_SIGNAL_SCORE
    global SUPPORT_RESISTANCE_LINES, MOVING_AVERAGE_LINES, SUPPORT_RESISTANCE_STRATEGY
    global SHOW_GRID_LINES, SHOW_PRICE_SCALE, TELEGRAM_BOT_TOKEN, TREND_LINES, BACKGROUND_TRANSPARENCY
    global TELEGRAM_CHAT_ID, SIGNAL_USERNAME, SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX
    global TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER
    global TELEGRAM_SOURCE_CHANNEL, TELEGRAM_TARGET_CHANNELS, PREMIUM_EMOJI_MODE, PREMIUM_EMOJI_TARGET
    global CHART_TEXT_GLOW, WATERMARK_ON, WATERMARK_TEXT, SIGNAL_HEADER_TEXT, CHART_HEADER_TEXT
    global PARABOLIC_SAR_LINES, GAP_DRAWING, REVERSE_AREA_DRAWING, ADVANCED_ANALYSIS, CUSTOM_LINK
    global FVG_GAP_DRAW, BOT_ALERT_ON, CANDLE_UP_COLOR, CANDLE_DOWN_COLOR, EMA_LINE_CHART
    global SUPERTREND_CHART, SUPERTREND_STRATEGY, SNR_LINES
    
    try:
        data_to_save = {
            "all_results": trade_results,
            "settings": {
                "MARTINGALE_STEPS": MARTINGALE_STEPS,
                "PARTIAL_RESULTS_INTERVAL": PARTIAL_RESULTS_INTERVAL,
                "SEND_MARKET_CHART": SEND_PHOTO_WITH_SIGNAL,
                "CHART_BACKGROUND_IMAGE_PATH": CHART_BACKGROUND_IMAGE_PATH,
                "ANALYZE_ALL_PAIRS": ANALYZE_ALL_PAIRS,
                
                # --- নতুন সেটিং সেভ ---
                "CUSTOM_PAIRS_MODE": CUSTOM_PAIRS_MODE,
                "CUSTOM_PAIRS_LIST": CUSTOM_PAIRS_LIST,
                "EMA_PERIOD": EMA_PERIOD,
                "RSI_PERIOD": RSI_PERIOD,
                "CURRENT_STRATEGY": CURRENT_STRATEGY,
                "MARK_RESULT_CANDLE": MARK_RESULT_CANDLE,
                "MIN_SIGNAL_SCORE": MIN_SIGNAL_SCORE,
                
                # নতুন চার্ট সেটিংস
                "SUPPORT_RESISTANCE_LINES": SUPPORT_RESISTANCE_LINES,
                "MOVING_AVERAGE_LINES": MOVING_AVERAGE_LINES,
                "SUPPORT_RESISTANCE_STRATEGY": SUPPORT_RESISTANCE_STRATEGY,
                "SHOW_GRID_LINES": SHOW_GRID_LINES,
                "SHOW_PRICE_SCALE": SHOW_PRICE_SCALE,
                "TREND_LINES": TREND_LINES,
                "BACKGROUND_TRANSPARENCY": BACKGROUND_TRANSPARENCY,
                "CHART_TEXT_GLOW": CHART_TEXT_GLOW,
                "WATERMARK_ON": WATERMARK_ON,
                "WATERMARK_TEXT": WATERMARK_TEXT,
                "SIGNAL_HEADER_TEXT": SIGNAL_HEADER_TEXT,
                "CHART_HEADER_TEXT": CHART_HEADER_TEXT,
                
                # নতুন অ্যাডভান্সড সেটিংস
                "PARABOLIC_SAR_LINES": PARABOLIC_SAR_LINES,
                "GAP_DRAWING": GAP_DRAWING,
                "REVERSE_AREA_DRAWING": REVERSE_AREA_DRAWING,
                "ADVANCED_ANALYSIS": ADVANCED_ANALYSIS,
                "CUSTOM_LINK": CUSTOM_LINK,
                
                # নতুন ফিচার সেটিংস
                "FVG_GAP_DRAW": FVG_GAP_DRAW,
                "BOT_ALERT_ON": BOT_ALERT_ON,
                
                # ক্যান্ডেল কালার সেটিংস
                "CANDLE_UP_COLOR": list(CANDLE_UP_COLOR),
                "CANDLE_DOWN_COLOR": list(CANDLE_DOWN_COLOR),
                
                # EMA এবং সুপারট্রেন্ড সেটিংস
                "EMA_LINE_CHART": EMA_LINE_CHART,
                "SUPERTREND_CHART": SUPERTREND_CHART,
                "SUPERTREND_STRATEGY": SUPERTREND_STRATEGY,
                "SNR_LINES": SNR_LINES,
                
                # Telegram settings
                "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
                "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
                "SIGNAL_USERNAME": SIGNAL_USERNAME,
                "SIGNAL_INTERVAL_MIN": SIGNAL_INTERVAL_MIN,
                "SIGNAL_INTERVAL_MAX": SIGNAL_INTERVAL_MAX,
                
                # Telegram client settings
                "TELEGRAM_API_ID": TELEGRAM_API_ID,
                "TELEGRAM_API_HASH": TELEGRAM_API_HASH,
                "TELEGRAM_PHONE_NUMBER": TELEGRAM_PHONE_NUMBER,
                "TELEGRAM_SOURCE_CHANNEL": TELEGRAM_SOURCE_CHANNEL,
                "TELEGRAM_TARGET_CHANNELS": TELEGRAM_TARGET_CHANNELS,
                "PREMIUM_EMOJI_MODE": PREMIUM_EMOJI_MODE,
                "PREMIUM_EMOJI_TARGET": PREMIUM_EMOJI_TARGET
                # --- নতুন সেটিং সেভ ---
            },
            "last_updated": datetime.now(pytz.timezone('Asia/Dhaka')).isoformat(),
            "version": "8.0_Complete_Features_Update"
        }

        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)

        print(rainbow_text(f"✅ 𝚂𝚊𝚟𝚎𝚍 {len(trade_results)} 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚊𝚗𝚍 𝚜𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚝𝚘 {SAVE_FILE}"))
        return True
    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚜𝚊𝚟𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜: {e}"))
        return False

def get_today_results():
    """আজকের তারিখের রেজাল্টগুলো রিটার্ন করে (শুধুমাত্র নিশ্চিত রেজাল্ট)"""
    today = datetime.now(pytz.timezone('Asia/Dhaka')).date()
    today_str = today.isoformat()

    today_results = []
    for result in trade_results:
        # শুধুমাত্র নিশ্চিত রেজাল্টগুলো (Profit/Loss/Break-even)
        if result.get('result') not in ['Profit', 'Loss', 'Break-even']:
            continue
            
        result_date_str = result.get('date')
        if not result_date_str:
            try:
                if 'timestamp' in result:
                    dt = datetime.fromtimestamp(result['timestamp'], pytz.timezone('Asia/Dhaka'))
                    result_date_str = dt.date().isoformat()
                elif 'signal_datetime' in result:
                    dt = datetime.fromisoformat(result['signal_datetime'].replace('Z', '+00:00'))
                    dt = dt.astimezone(pytz.timezone('Asia/Dhaka'))
                    result_date_str = dt.date().isoformat()
            except:
                continue

        if result_date_str == today_str:
            today_results.append(result)

    return today_results

def get_statistics(results_list=None):
    """সামগ্রিক স্ট্যাটিস্টিক্স রিটার্ন করে"""
    if results_list is None:
        results_list = trade_results

    # শুধুমাত্র 'Profit' বা 'Loss' রেজাল্টগুলোকে গণনায় নেওয়া হবে
    completed_trades = [r for r in results_list if r.get('result') in ['Profit', 'Loss']]

    total = len(completed_trades)
    wins = sum(1 for r in completed_trades if r.get('result') == 'Profit')
    losses = sum(1 for r in completed_trades if r.get('result') == 'Loss')

    if total > 0:
        accuracy = (wins / total) * 100
    else:
        accuracy = 0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "accuracy": round(accuracy, 2)
    }

# ================= টেলিগ্রাম ফাংশন (আপডেট) =================

async def send_telegram_photo_or_chart(caption, pair=None, candles=None, result=None):
    """Sends a photo (custom or chart) with a caption to Telegram."""
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH

    try:
        if SEND_PHOTO_WITH_SIGNAL and pair and candles:
            # Send Market Chart Image
            image_buffer = create_chart_image(pair, candles, result=result)

            if not image_buffer:
                print(rainbow_text("❌ 𝙲𝚑𝚊𝚛𝚝 𝚒𝚖𝚊𝚐𝚎 𝚌𝚛𝚎𝚊𝚝𝚒𝚘𝚗 𝚏𝚊𝚒𝚕𝚎𝚍. 𝚂𝚎𝚗𝚍𝚒𝚗𝚐 𝚊𝚜 𝚝𝚎𝚡𝚝 𝚖𝚎𝚜𝚜𝚊𝚐𝚎."))
                return send_telegram_message(caption)

            print(rainbow_text(f"📸 𝚂𝚎𝚗𝚍𝚒𝚗𝚐 𝚌𝚑𝚊𝚛𝚝 𝚏𝚘𝚛 {pair} 𝚝𝚘 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖..."))

            bot_instance = get_bot()
            if bot_instance:
                await bot_instance.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=image_buffer,
                caption=caption,
                parse_mode=constants.ParseMode.HTML
            )
            return True

        else:
            # Send as text message
            print(rainbow_text(f"📸 𝚂𝚎𝚗𝚍𝚒𝚗𝚐 𝚝𝚎𝚡𝚝 𝚖𝚎𝚜𝚜𝚊𝚐𝚎 𝚝𝚘 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖..."))
            return send_telegram_message(caption)

    except Exception as e:
        print(rainbow_text(f"❌ 𝙵𝚊𝚒𝚕𝚎𝚍 𝚝𝚘 𝚜𝚎𝚗𝚍 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚙𝚑𝚘𝚝𝚘/𝚌𝚑𝚊𝚛𝚝: {e}"))
        # Fallback: send the caption as a regular message if image fails
        return send_telegram_message(caption)

def send_telegram_message(message):
    """Sends a text message to Telegram (synchronous using requests/session)."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.strip() == "" or TELEGRAM_BOT_TOKEN == "":
        print(rainbow_text("⚠️ Telegram Bot Token not set. Message not sent."))
        print(rainbow_text(f"   Message: {message[:100]}..."))
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }

        response = session.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(rainbow_text(f"𝙵𝚊𝚒𝚕𝚎𝚍 𝚝𝚘 𝚜𝚎𝚗𝚍 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚖𝚎𝚜𝚜𝚊𝚐𝚎: {e}"))
        try:
            alt_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            response = requests.post(alt_url, data=payload, timeout=15, verify=False)
            return response.status_code == 200
        except:
            return False

# ================= নতুন টেকনিক্যাল ইন্ডিকেটর ফাংশন =================

def calculate_parabolic_sar(candles, acceleration=0.02, maximum=0.2):
    """প্যারাবলিক SAR ইন্ডিকেটর ক্যালকুলেট করে"""
    if len(candles) < 5:
        return []
    
    sar_values = []
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    
    # Initial values
    uptrend = True
    sar = low[0]
    ep = high[0]
    af = acceleration
    
    for i in range(len(candles)):
        # Store current SAR
        sar_values.append(sar)
        
        if uptrend:
            # Check for SAR reversal
            if low[i] < sar:
                uptrend = False
                sar = ep
                ep = low[i]
                af = acceleration
            else:
                # Update SAR
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + acceleration, maximum)
                
                sar = sar + af * (ep - sar)
                
                # Ensure SAR is below the low of the previous two candles
                if i >= 2:
                    sar = min(sar, low[i-1], low[i-2])
        else:
            # Downtrend
            if high[i] > sar:
                uptrend = True
                sar = ep
                ep = high[i]
                af = acceleration
            else:
                # Update SAR
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + acceleration, maximum)
                
                sar = sar + af * (ep - sar)
                
                # Ensure SAR is above the high of the previous two candles
                if i >= 2:
                    sar = max(sar, high[i-1], high[i-2])
    
    return sar_values

def calculate_gaps(candles):
    """গ্যাপ এলাকা ডিটেক্ট করে"""
    if len(candles) < 2:
        return []
    
    gaps = []
    for i in range(1, len(candles)):
        prev_close = candles[i-1]['close']
        curr_open = candles[i]['open']
        
        # Check for gap up
        if curr_open > prev_close * 1.001:  # 0.1% gap threshold
            gaps.append({
                'type': 'GAP_UP',
                'start_price': prev_close,
                'end_price': curr_open,
                'candle_index': i
            })
        # Check for gap down
        elif curr_open < prev_close * 0.999:  # 0.1% gap threshold
            gaps.append({
                'type': 'GAP_DOWN',
                'start_price': prev_close,
                'end_price': curr_open,
                'candle_index': i
            })
    
    return gaps

def detect_reversal_areas(candles, lookback=10):
    """রিভার্স এলাকা ডিটেক্ট করে"""
    if len(candles) < lookback * 2:
        return []
    
    reversal_areas = []
    
    # Find swing highs and lows
    for i in range(lookback, len(candles) - lookback):
        current_high = candles[i]['high']
        current_low = candles[i]['low']
        
        # Check for swing high
        is_swing_high = True
        for j in range(1, lookback + 1):
            if candles[i-j]['high'] > current_high or candles[i+j]['high'] > current_high:
                is_swing_high = False
                break
        
        # Check for swing low
        is_swing_low = True
        for j in range(1, lookback + 1):
            if candles[i-j]['low'] < current_low or candles[i+j]['low'] < current_low:
                is_swing_low = False
                break
        
        if is_swing_high:
            reversal_areas.append({
                'type': 'SWING_HIGH',
                'price': current_high,
                'candle_index': i,
                'timestamp': candles[i]['dt'] if 'dt' in candles[i] else None
            })
        
        if is_swing_low:
            reversal_areas.append({
                'type': 'SWING_LOW',
                'price': current_low,
                'candle_index': i,
                'timestamp': candles[i]['dt'] if 'dt' in candles[i] else None
            })
    
    return reversal_areas

def analyze_trend_reversal(candle_data):
    """ট্রেন্ড রিভার্স অ্যানালাইসিস করে"""
    if not candle_data or len(candle_data) < 20:
        return None, None, None, None, None
    
    closes = [c['close'] for c in candle_data]
    
    # Calculate moving averages for trend detection
    ma20 = ema(closes, 20) if len(closes) >= 20 else None
    ma50 = ema(closes, 50) if len(closes) >= 50 else None
    
    # Calculate RSI for overbought/oversold conditions
    rsi = calculate_rsi(closes, 14)
    
    # Calculate MACD
    macd_line, signal_line, macd_histogram = calculate_macd(closes)
    
    # Detect trend
    current_price = closes[-1]
    trend = "SIDEWAYS"
    
    if ma20 and ma50:
        if current_price > ma20 and ma20 > ma50:
            trend = "UP_TREND"
        elif current_price < ma20 and ma20 < ma50:
            trend = "DOWN_TREND"
    
    # Detect potential reversal
    reversal_signal = None
    if trend == "UP_TREND" and rsi > 70:
        reversal_signal = "POTENTIAL_DOWN_REVERSAL"
    elif trend == "DOWN_TREND" and rsi < 30:
        reversal_signal = "POTENTIAL_UP_REVERSAL"
    
    # Calculate support and resistance levels
    support, resistance = calculate_support_resistance_levels(closes)
    
    # Determine signal logic
    logic = None
    if reversal_signal == "POTENTIAL_DOWN_REVERSAL":
        logic = "Overbought with RSI > 70 in uptrend"
    elif reversal_signal == "POTENTIAL_UP_REVERSAL":
        logic = "Oversold with RSI < 30 in downtrend"
    
    return trend, reversal_signal, support, resistance, logic

def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    """MACD ইন্ডিকেটর ক্যালকুলেট করে"""
    if len(prices) < slow_period:
        return None, None, None
    
    # Calculate EMAs
    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)
    
    if fast_ema is None or slow_ema is None:
        return None, None, None
    
    # MACD Line
    macd_line = fast_ema - slow_ema
    
    # Signal Line (EMA of MACD Line)
    macd_prices = [macd_line]  # Simplified
    signal_line = ema(macd_prices, signal_period)
    
    # MACD Histogram
    macd_histogram = macd_line - signal_line if signal_line else None
    
    return macd_line, signal_line, macd_histogram

# ================= নতুন FVG গ্যাপ ডিটেকশন ফাংশন =================

def detect_fvg_gaps(candles, threshold=0.001):
    """FVG (Fair Value Gap) গ্যাপ ডিটেক্ট করে"""
    if len(candles) < 3:
        return []
    
    fvg_gaps = []
    
    for i in range(1, len(candles) - 1):
        prev_candle = candles[i-1]
        curr_candle = candles[i]
        next_candle = candles[i+1]
        
        # Bullish FVG: Current candle high > previous candle low and next candle low > current candle low
        if (curr_candle['high'] > prev_candle['low'] and 
            next_candle['low'] > curr_candle['low'] and
            abs(curr_candle['high'] - prev_candle['low']) / prev_candle['low'] > threshold):
            
            fvg_gaps.append({
                'type': 'BULLISH_FVG',
                'start_price': prev_candle['low'],
                'end_price': curr_candle['high'],
                'candle_index': i,
                'strength': (curr_candle['high'] - prev_candle['low']) / prev_candle['low']
            })
        
        # Bearish FVG: Current candle low < previous candle high and next candle high < current candle high
        if (curr_candle['low'] < prev_candle['high'] and 
            next_candle['high'] < curr_candle['high'] and
            abs(prev_candle['high'] - curr_candle['low']) / prev_candle['high'] > threshold):
            
            fvg_gaps.append({
                'type': 'BEARISH_FVG',
                'start_price': prev_candle['high'],
                'end_price': curr_candle['low'],
                'candle_index': i,
                'strength': (prev_candle['high'] - curr_candle['low']) / prev_candle['high']
            })
    
    return fvg_gaps

# ================= নতুন সুপারট্রেন্ড ক্যালকুলেশন ফাংশন =================

def calculate_supertrend(candles, period=10, multiplier=3):
    """সুপারট্রেন্ড ইন্ডিকেটর ক্যালকুলেট করে"""
    if len(candles) < period:
        return [], []
    
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    close = [c['close'] for c in candles]
    
    # Calculate ATR
    def calculate_atr(high, low, close, period):
        tr = []
        for i in range(1, len(high)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr.append(max(hl, hc, lc))
        
        atr = [sum(tr[:period]) / period]
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        
        return atr
    
    atr = calculate_atr(high, low, close, period)
    
    # Calculate Supertrend
    supertrend = []
    trend = []
    
    # Initial values
    upper_band = (high[0] + low[0]) / 2 + multiplier * atr[0]
    lower_band = (high[0] + low[0]) / 2 - multiplier * atr[0]
    
    for i in range(len(candles)):
        if i < period:
            supertrend.append(None)
            trend.append(None)
            continue
        
        # Basic bands
        hl2 = (high[i] + low[i]) / 2
        upper_band = hl2 + multiplier * atr[i-period]
        lower_band = hl2 - multiplier * atr[i-period]
        
        # Adjust bands based on trend
        if i == period:
            supertrend.append(upper_band)
            trend.append(1)  # Uptrend
        else:
            if close[i] > supertrend[-1]:
                current_trend = 1  # Uptrend
                supertrend.append(max(lower_band, supertrend[-1]) if trend[-1] == 1 else lower_band)
            else:
                current_trend = -1  # Downtrend
                supertrend.append(min(upper_band, supertrend[-1]) if trend[-1] == -1 else upper_band)
            
            trend.append(current_trend)
    
    return supertrend, trend

# ================= নতুন প্রাইস অ্যাকশন ডিটেকশন ফাংশন =================

def detect_price_action_patterns(candles):
    """প্রাইস অ্যাকশন প্যাটার্ন ডিটেক্ট করে"""
    if len(candles) < 5:
        return []
    
    patterns = []
    
    for i in range(2, len(candles) - 2):
        # Bullish Engulfing
        if (candles[i-1]['close'] < candles[i-1]['open'] and  # Previous bearish
            candles[i]['close'] > candles[i]['open'] and       # Current bullish
            candles[i]['open'] < candles[i-1]['close'] and     # Opens below previous close
            candles[i]['close'] > candles[i-1]['open']):       # Closes above previous open
            
            patterns.append({
                'type': 'BULLISH_ENGULFING',
                'candle_index': i,
                'strength': (candles[i]['close'] - candles[i-1]['open']) / candles[i-1]['open']
            })
        
        # Bearish Engulfing
        elif (candles[i-1]['close'] > candles[i-1]['open'] and  # Previous bullish
              candles[i]['close'] < candles[i]['open'] and       # Current bearish
              candles[i]['open'] > candles[i-1]['close'] and     # Opens above previous close
              candles[i]['close'] < candles[i-1]['open']):       # Closes below previous open
            
            patterns.append({
                'type': 'BEARISH_ENGULFING',
                'candle_index': i,
                'strength': (candles[i-1]['open'] - candles[i]['close']) / candles[i-1]['open']
            })
        
        # Hammer
        elif (candles[i]['close'] > candles[i]['open'] and  # Bullish
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['close'] - candles[i]['open']) and  # Long lower wick
              (candles[i]['close'] - candles[i]['low']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):  # Close near high
            
            patterns.append({
                'type': 'HAMMER',
                'candle_index': i,
                'strength': (candles[i]['close'] - candles[i]['low']) / (candles[i]['high'] - candles[i]['low'])
            })
        
        # Shooting Star
        elif (candles[i]['close'] < candles[i]['open'] and  # Bearish
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['open'] - candles[i]['close']) and  # Long upper wick
              (candles[i]['high'] - candles[i]['open']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):  # Open near low
            
            patterns.append({
                'type': 'SHOOTING_STAR',
                'candle_index': i,
                'strength': (candles[i]['high'] - candles[i]['open']) / (candles[i]['high'] - candles[i]['low'])
            })
    
    return patterns

# ================= SNR লেভেল ক্যালকুলেশন =================

def calculate_snr_levels(prices, num_levels=5):
    """SNR (Support and Resistance) লেভেল ক্যালকুলেট করে"""
    if len(prices) < 20:
        return []
    
    # Find local highs and lows
    local_highs = []
    local_lows = []
    
    for i in range(2, len(prices) - 2):
        if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and 
            prices[i] > prices[i+1] and prices[i] > prices[i+2]):
            local_highs.append(prices[i])
        
        if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and 
            prices[i] < prices[i+1] and prices[i] < prices[i+2]):
            local_lows.append(prices[i])
    
    # Combine and sort levels
    all_levels = local_highs + local_lows
    all_levels.sort()
    
    # Cluster nearby levels
    clusters = []
    current_cluster = []
    cluster_threshold = (max(prices) - min(prices)) * 0.01  # 1% threshold
    
    for level in all_levels:
        if not current_cluster:
            current_cluster.append(level)
        elif abs(level - np.mean(current_cluster)) < cluster_threshold:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    
    if current_cluster:
        clusters.append(current_cluster)
    
    # Calculate average for each cluster
    snr_levels = []
    for cluster in clusters:
        if len(cluster) >= 2:  # Only consider clusters with at least 2 points
            avg_level = np.mean(cluster)
            strength = len(cluster)
            snr_levels.append({
                'level': avg_level,
                'strength': strength,
                'type': 'RESISTANCE' if avg_level > np.mean(prices) else 'SUPPORT'
            })
    
    # Sort by strength and return top levels
    snr_levels.sort(key=lambda x: x['strength'], reverse=True)
    return snr_levels[:num_levels]

# ================= এডভান্সড চার্ট জেনারেশন ফাংশন (আপডেটেড) =================

def load_fonts():
    """ট্রি ফন্ট লোড করে - Termux/Kali compatible"""
    font_paths = [
        # Linux system fonts
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # Termux fonts
        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Kali fonts
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]

    def find_font(bold=False):
        for path in font_paths:
            if os.path.exists(path):
                if bold and 'Bold' in path:
                    return path
                elif not bold and 'Bold' not in path:
                    return path
        # Return any available font
        for path in font_paths:
            if os.path.exists(path):
                return path
        return None

    try:
        bold_font = find_font(bold=True) or find_font()
        regular_font = find_font(bold=False) or find_font()

        if bold_font and regular_font:
            font_large = ImageFont.truetype(bold_font, 24)
            font_medium = ImageFont.truetype(regular_font, 16)
            font_small = ImageFont.truetype(regular_font, 12)
            font_tiny = ImageFont.truetype(regular_font, 10)
            return font_large, font_medium, font_small, font_tiny
    except Exception as e:
        print(f"Font loading error: {e}")

    # Default font as last resort
    return ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

def draw_dashed_line(draw, start, end, color, width=1, dash_length=5):
    """Draw a dashed line manually"""
    x1, y1 = start
    x2, y2 = end
    
    # Calculate line length and direction
    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx**2 + dy**2)
    
    if length == 0:
        return
    
    # Normalize direction
    dx /= length
    dy /= length
    
    # Draw dashed segments
    drawn_length = 0
    while drawn_length < length:
        dash_start = (x1 + dx * drawn_length, y1 + dy * drawn_length)
        dash_end_length = min(dash_length, length - drawn_length)
        dash_end = (x1 + dx * (drawn_length + dash_end_length), 
                   y1 + dy * (drawn_length + dash_end_length))
        
        draw.line([dash_start, dash_end], fill=color, width=width)
        drawn_length += dash_length * 2

def create_chart_image(pair: str, candles: List[Dict], result=None) -> BytesIO:
    global MARK_RESULT_CANDLE, SUPPORT_RESISTANCE_LINES, MOVING_AVERAGE_LINES, SHOW_GRID_LINES, SHOW_PRICE_SCALE, TREND_LINES, BACKGROUND_TRANSPARENCY, CHART_TEXT_GLOW, WATERMARK_ON, WATERMARK_TEXT, CHART_HEADER_TEXT
    global PARABOLIC_SAR_LINES, GAP_DRAWING, REVERSE_AREA_DRAWING, FVG_GAP_DRAW, CANDLE_UP_COLOR, CANDLE_DOWN_COLOR, EMA_LINE_CHART, SUPERTREND_CHART, SNR_LINES
    
    if not candles:
        return None

    # চার্ট সাইজ
    WIDTH, HEIGHT = 900, 500
    
    # চার্ট কালার থিম - সলিড ব্ল্যাক ব্যাকগ্রাউন্ড এবং স্পষ্ট কালার
    BACKGROUND_COLOR = (0, 0, 0)  # সলিড ব্ল্যাক (Blood black behind)
    GREEN = CANDLE_UP_COLOR  # কাস্টমাইজড কালার ব্যবহার
    RED = CANDLE_DOWN_COLOR  # কাস্টমাইজড কালার ব্যবহার
    BLUE = (0, 150, 255)
    YELLOW = (255, 255, 0)
    WHITE = (255, 255, 255)
    GRAY = (100, 100, 100)
    DARK_GRAY = (50, 50, 50)
    LIGHT_BLUE = (100, 200, 255)
    DARK_BLUE = (20, 20, 40)
    SUPPORT_COLOR = (0, 255, 0, 200)  # More visible support line
    RESISTANCE_COLOR = (255, 0, 0, 200)  # More visible resistance line
    MA_COLORS = [(255, 255, 0), (0, 255, 255), (255, 0, 255)]
    GRID_COLOR = (30, 30, 30, 150)  # সূক্ষ্ম গ্রিড (সাবটল)
    TREND_LINE_COLOR = (255, 165, 0, 255)  # Solid orange for trend lines
    PARABOLIC_SAR_COLOR = (255, 0, 255, 200)  # Magenta for Parabolic SAR
    GAP_COLOR = (255, 255, 0, 100)  # Yellow with transparency for gaps
    REVERSE_AREA_COLOR = (0, 255, 255, 80)  # Cyan with transparency for reversal areas
    FVG_COLOR = (255, 165, 0, 80)  # Orange with transparency for FVG gaps
    SUPERTREND_UP_COLOR = (0, 255, 0, 150)  # Green for uptrend
    SUPERTREND_DOWN_COLOR = (255, 0, 0, 150)  # Red for downtrend
    EMA_COLOR = (255, 255, 0, 200)  # Yellow for EMA line
    SNR_COLOR = (255, 165, 0, 150)  # Orange for SNR lines
    
    # Create base image with solid background
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    # *** ব্যাকগ্রাউন্ড ইমেজ লোড (সিম্পলিফাইড) ***
    # যদি পাথ খালি থাকে, সলিড ব্ল্যাক ব্যাকগ্রাউন্ড থাকবে।
    try:
        if CHART_BACKGROUND_IMAGE_PATH and os.path.exists(CHART_BACKGROUND_IMAGE_PATH):
            bg_img = Image.open(CHART_BACKGROUND_IMAGE_PATH).convert("RGBA")
            # রিসাইজ করে চার্টের মাপের সমান করা
            bg_img = bg_img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            
            # ট্রান্সপারেন্সি প্রয়োগ - বেশি ট্রান্সপারেন্সি যাতে চার্ট স্পষ্ট দেখা যায়
            alpha = BACKGROUND_TRANSPARENCY / 100.0
            bg_img_alpha = bg_img.copy()
            bg_img_alpha.putalpha(int(255 * alpha))
            
            # একটি ট্রান্সপারেন্ট ওভারলে তৈরি করা
            overlay = Image.new('RGBA', (WIDTH, HEIGHT), BACKGROUND_COLOR + (0,))
            
            # মূল ইমেজের সাথে ব্যাকগ্রাউন্ড ছবিটি মিশ্রিত করা
            temp_img = Image.alpha_composite(overlay, bg_img_alpha)
            img = Image.alpha_composite(img.convert('RGBA'), temp_img).convert('RGB')
            draw = ImageDraw.Draw(img)
            
            print(rainbow_text(f"✅ 𝙱𝚊𝚌𝚔𝚐𝚛𝚐𝚞𝚍 𝚒𝚖𝚊𝚐𝚎 𝚕𝚘𝚊𝚍𝚎𝚍 (𝚃𝚛𝚊𝚗𝚜𝚙𝚊𝚛𝚎𝚌𝚢: {BACKGROUND_TRANSPARENCY}%)"))
        else:
            print(rainbow_text(f"⚠️ 𝙱𝚊𝚌𝚔𝚐𝚛𝚐𝚞𝚍 𝚒𝚖𝚊𝚐𝚎 𝚗𝚘𝚝 চ�𝚘𝚞𝚗𝚍. 𝚄𝚜𝚒𝚝𝚐 𝚂𝚑𝚕𝚒𝚍 𝙱𝚕𝚊𝚌𝚔 ঙ�𝚊𝚌𝚔𝚐𝚛𝚐𝚞𝚗𝚍."))
    except Exception as e:
        print(rainbow_text(f"❌ 𝙴𝚛𝚛𝚘𝚛 𝚕𝚘𝚊𝚍𝚒𝚗𝚐 চ�𝚊𝚌𝚔𝚐𝚛𝚐𝚞𝚗𝚍 চ�𝚖𝚊𝚐𝚎: {e}"))

    # ফন্ট লোড (ছোট ফন্ট সাইজ যাতে সব টেক্সট ফিট হয়)
    font_large, font_medium, font_small, font_tiny = load_fonts()

    # --- হেডার সেকশন (স্পষ্ট এবং বড়) ---
    header_y = 15
    
    # Top title
    title_text = f"{CHART_HEADER_TEXT}: "
    title_width = draw.textlength(title_text, font=font_large)
    draw.text((20, header_y), title_text, fill=LIGHT_BLUE, font=font_large)
    
    # Signal
    latest_signal = "BUY" if candles[-1]['close'] > candles[-1]['open'] else "SELL"
    signal_color = GREEN if latest_signal == "BUY" else RED
    draw.text((20 + title_width, header_y), f"{latest_signal}", fill=signal_color, font=font_large)
    
    # --- BMA ইন্ডিকেটর সেকশন ---
    bma_y = 50
    bma_texts = ["BMA 9", "BMA 21", "BMA 30", "3IGNAL"]
    bma_colors = [YELLOW, BLUE, RED, GREEN]
    
    x_pos = 20
    for text, color in zip(bma_texts, bma_colors):
        draw.text((x_pos, bma_y), text, fill=color, font=font_medium)
        x_pos += draw.textlength(text, font=font_medium) + 20
    
    # EMA বুলিশ টেক্সট
    draw.text((x_pos, bma_y), "EMA: BULLISH", fill=GREEN, font=font_medium)
    
    # --- চার্ট এরিয়া ডিফাইন ---
    CHART_AREA_LEFT = 100
    CHART_AREA_TOP = 80
    CHART_AREA_WIDTH = WIDTH - CHART_AREA_LEFT - 200
    CHART_AREA_HEIGHT = HEIGHT - CHART_AREA_TOP - 120
    
    # Draw chart border with solid color
    draw.rectangle([CHART_AREA_LEFT, CHART_AREA_TOP, 
                    CHART_AREA_LEFT + CHART_AREA_WIDTH, 
                    CHART_AREA_TOP + CHART_AREA_HEIGHT], 
                   outline=DARK_GRAY, width=2)
    
    # প্রাইস স্কেলিং
    all_prices = [c['high'] for c in candles] + [c['low'] for c in candles]
    min_price = min(all_prices) * 0.9998
    max_price = max(all_prices) * 1.0002
    price_range = max_price - min_price

    if price_range == 0:
        price_range = max_price * 0.001

    def scale_price_to_y(price):
        return CHART_AREA_TOP + CHART_AREA_HEIGHT - int(
            (price - min_price) / price_range * CHART_AREA_HEIGHT
        )
    
    # --- প্রাইস স্কেল সেকশন (বাম পাশে) ---
    if SHOW_PRICE_SCALE:
        price_scale_x = CHART_AREA_LEFT - 80
        price_values = np.linspace(min_price, max_price, 8)
        
        # Draw price scale background
        draw.rectangle([price_scale_x - 5, CHART_AREA_TOP - 5, 
                        price_scale_x + 75, CHART_AREA_TOP + CHART_AREA_HEIGHT + 5], 
                      fill=DARK_BLUE + (150,), outline=GRAY)
        
        for i, price in enumerate(price_values):
            y_pos = scale_price_to_y(price)
            # Draw small marker
            draw.line([(price_scale_x + 60, y_pos), (price_scale_x + 70, y_pos)], 
                     fill=WHITE, width=1)
            # Format price
            price_str = f"{price:.5f}" if price < 1 else f"{price:.4f}"
            draw.text((price_scale_x, y_pos - 8), price_str, fill=WHITE, font=font_tiny)
    
    # --- SNR লাইন ড্রয়িং (নতুন) ---
    if SNR_LINES:
        closes = [c['close'] for c in candles]
        snr_levels = calculate_snr_levels(closes, num_levels=5)
        
        for level_data in snr_levels:
            y_snr = scale_price_to_y(level_data['level'])
            color = SUPPORT_COLOR if level_data['type'] == 'SUPPORT' else RESISTANCE_COLOR
            
            # Draw SNR line
            draw.line([(CHART_AREA_LEFT, y_snr), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_snr)], 
                     fill=color, width=2)
            
            # Draw label
            label_text = f"{level_data['type'][0]}: {level_data['level']:.5f}"
            draw.text((CHART_AREA_LEFT + 5, y_snr - 15), 
                     label_text, fill=color, font=font_tiny)
    
    # --- সুপারট্রেন্ড লাইন ড্রয়িং (নতুন) ---
    if SUPERTREND_CHART:
        supertrend_values, trend_values = calculate_supertrend(candles, period=10, multiplier=3)
        
        if supertrend_values and trend_values:
            supertrend_points = []
            for i, value in enumerate(supertrend_values):
                if value is not None and i < min(len(candles), 50):
                    x_st = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / min(len(candles), 50))
                    y_st = scale_price_to_y(value)
                    supertrend_points.append((x_st, y_st))
            
            # Draw Supertrend line
            if len(supertrend_points) > 1:
                for j in range(1, len(supertrend_points)):
                    color = SUPERTREND_UP_COLOR if trend_values[j] == 1 else SUPERTREND_DOWN_COLOR
                    draw.line([supertrend_points[j-1], supertrend_points[j]], 
                             fill=color, width=2)
    
    # --- EMA লাইন ড্রয়িং (নতুন) ---
    if EMA_LINE_CHART:
        closes = [c['close'] for c in candles]
        ema_value = ema(closes, EMA_PERIOD)
        
        if ema_value is not None:
            y_ema = scale_price_to_y(ema_value)
            draw.line([(CHART_AREA_LEFT, y_ema), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_ema)], 
                     fill=EMA_COLOR, width=3)
            
            # Label at right end
            draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_ema - 15), 
                     f"EMA{EMA_PERIOD}", fill=EMA_COLOR, font=font_tiny)
    
    # --- FVG গ্যাপ ড্রয়িং (নতুন) ---
    if FVG_GAP_DRAW:
        fvg_gaps = detect_fvg_gaps(candles)
        for gap in fvg_gaps:
            if gap['candle_index'] < min(len(candles), 50):
                x_fvg = CHART_AREA_LEFT + int(gap['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                y_start = scale_price_to_y(gap['start_price'])
                y_end = scale_price_to_y(gap['end_price'])
                
                # Draw FVG area
                draw.rectangle([x_fvg - 10, min(y_start, y_end),
                               x_fvg + 10, max(y_start, y_end)],
                              fill=FVG_COLOR, outline=YELLOW)
                
                # Draw label
                label_text = "FVG"
                draw.text((x_fvg - 15, (y_start + y_end) // 2 - 10), 
                         label_text, fill=YELLOW, font=font_tiny)
    
    # --- GAP ড্রয়িং (নতুন) ---
    if GAP_DRAWING:
        gaps = calculate_gaps(candles)
        for gap in gaps:
            gap_y_start = scale_price_to_y(gap['start_price'])
            gap_y_end = scale_price_to_y(gap['end_price'])
            
            # Calculate x position for gap
            if gap['candle_index'] < len(candles):
                x_gap = CHART_AREA_LEFT + int(gap['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                
                # Draw gap area
                draw.rectangle([x_gap - 5, min(gap_y_start, gap_y_end),
                               x_gap + 5, max(gap_y_start, gap_y_end)],
                              fill=GAP_COLOR, outline=YELLOW)
    
    # --- রিভার্স এরিয়া ড্রয়িং (নতুন) ---
    if REVERSE_AREA_DRAWING:
        reversal_areas = detect_reversal_areas(candles)
        for area in reversal_areas:
            if area['candle_index'] < len(candles):
                x_rev = CHART_AREA_LEFT + int(area['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                y_rev = scale_price_to_y(area['price'])
                
                # Draw reversal marker
                if area['type'] == 'SWING_HIGH':
                    # Triangle pointing down for swing high
                    draw.polygon([(x_rev, y_rev - 10), (x_rev - 8, y_rev), (x_rev + 8, y_rev)],
                                fill=RED, outline=RED)
                elif area['type'] == 'SWING_LOW':
                    # Triangle pointing up for swing low
                    draw.polygon([(x_rev, y_rev + 10), (x_rev - 8, y_rev), (x_rev + 8, y_rev)],
                                fill=GREEN, outline=GREEN)
    
    # --- প্যারাবলিক SAR লাইন (নতুন) ---
    if PARABOLIC_SAR_LINES:
        sar_values = calculate_parabolic_sar(candles)
        if sar_values and len(sar_values) == len(candles):
            sar_points = []
            for i, sar in enumerate(sar_values):
                if i < min(len(candles), 50):  # Limit to visible candles
                    x_sar = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / min(len(candles), 50))
                    y_sar = scale_price_to_y(sar)
                    sar_points.append((x_sar, y_sar))
            
            # Draw SAR points
            for point in sar_points:
                draw.ellipse([point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3],
                           fill=PARABOLIC_SAR_COLOR, outline=WHITE)
    
    # --- সাপোর্ট/রেজিস্ট্যান্স লাইন (স্পষ্ট করে) ---
    if SUPPORT_RESISTANCE_LINES:
        support, resistance, pivot, r1, s1 = calculate_support_resistance(candles)
        
        if support and resistance:
            # Support Line (thicker and more visible)
            y_support = scale_price_to_y(support)
            draw.line([(CHART_AREA_LEFT, y_support), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_support)], 
                     fill=SUPPORT_COLOR, width=3)
            draw.text((CHART_AREA_LEFT + 5, y_support - 20), 
                     f"S: {support:.5f}", fill=SUPPORT_COLOR, font=font_small)
            
            # Resistance Line (thicker and more visible)
            y_resistance = scale_price_to_y(resistance)
            draw.line([(CHART_AREA_LEFT, y_resistance), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_resistance)], 
                     fill=RESISTANCE_COLOR, width=3)
            draw.text((CHART_AREA_LEFT + 5, y_resistance + 5), 
                     f"R: {resistance:.5f}", fill=RESISTANCE_COLOR, font=font_small)
    
    # --- মুভিং এভারেজ লাইন (স্পষ্ট) ---
    if MOVING_AVERAGE_LINES:
        ma_values = calculate_moving_averages(candles, periods=[20, 50, 100, 200])
        
        for i, (period, ma_value) in enumerate(ma_values.items()):
            if ma_value:
                y_ma = scale_price_to_y(ma_value)
                color = MA_COLORS[i % len(MA_COLORS)]
                draw.line([(CHART_AREA_LEFT, y_ma), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_ma)], 
                         fill=color, width=3)
                
                # Label at right end
                draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_ma - 15), 
                         f"MA{period}", fill=color, font=font_tiny)
    
    # --- ট্রেন্ড লাইন (স্পষ্ট) ---
    if TREND_LINES and len(candles) > 10:
        x_vals = list(range(len(candles)))
        y_vals = [c['close'] for c in candles]
        if len(y_vals) > 1:
            x1 = CHART_AREA_LEFT
            y1 = scale_price_to_y(y_vals[0])
            x2 = CHART_AREA_LEFT + CHART_AREA_WIDTH
            y2 = scale_price_to_y(y_vals[-1])
            draw.line([(x1, y1), (x2, y2)], fill=TREND_LINE_COLOR, width=3)
            draw.text((x2 - 50, y2 - 20), "TREND", fill=TREND_LINE_COLOR, font=font_small)
    
    # --- গ্রিড লাইন (স্পষ্ট) ---
    if SHOW_GRID_LINES:
        # হরিজন্টাল গ্রিড লাইন
        for i in range(6):
            y = CHART_AREA_TOP + int(i * CHART_AREA_HEIGHT / 5)
            draw.line([(CHART_AREA_LEFT, y), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y)], 
                     fill=GRID_COLOR, width=1)
        
        # ভার্টিকাল গ্রিড লাইন
        num_v_lines = 10 
        for i in range(num_v_lines):
            x = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / (num_v_lines - 1))
            draw.line([(x, CHART_AREA_TOP), (x, CHART_AREA_TOP + CHART_AREA_HEIGHT)], 
                     fill=GRID_COLOR, width=1)
    
    # --- ক্যান্ডেল আঁকা (স্পষ্ট) ---
    ideal_candle_width = 10
    ideal_spacing = 5
    
    num_candles_to_show = min(len(candles), 50)
    total_width_for_candles = num_candles_to_show * (ideal_candle_width + ideal_spacing) - ideal_spacing
    
    if total_width_for_candles > CHART_AREA_WIDTH:
        scale_factor = CHART_AREA_WIDTH / total_width_for_candles
        candle_width = int(ideal_candle_width * scale_factor)
        spacing = int(ideal_spacing * scale_factor)
    else:
        candle_width = ideal_candle_width
        spacing = ideal_spacing
        
    candle_width = max(3, candle_width) 
    
    actual_num_candles = min(len(candles), num_candles_to_show)
    
    start_x_offset = CHART_AREA_LEFT + (candle_width // 2)

    last_candle_center = None
    last_candle_radius = candle_width // 2 + 8

    for i in range(actual_num_candles):
        distance_from_left = i * (candle_width + spacing)
        
        x_center = start_x_offset + distance_from_left
        x_left = x_center - (candle_width // 2)
        x_right = x_center + (candle_width // 2)
        
        if x_center > CHART_AREA_LEFT + CHART_AREA_WIDTH:
             break
        
        candle = candles[i]
        
        # হাই-লো উইক
        y_high = scale_price_to_y(candle['high'])
        y_low = scale_price_to_y(candle['low'])
        
        # Wick (thin line connecting high to low)
        draw.line([(x_center, y_high), (x_center, y_low)], 
                 fill=WHITE, width=1)
        
        # ক্যান্ডেল বডি - কাস্টমাইজড কালার ব্যবহার
        is_bullish = candle['close'] > candle['open']
        body_color = GREEN if is_bullish else RED
        
        y_open = scale_price_to_y(candle['open'])
        y_close = scale_price_to_y(candle['close'])
        
        y_top = min(y_open, y_close)
        y_bottom = max(y_open, y_close)
        body_height = max(2, y_bottom - y_top) 
        
        # Regular candle body
        draw.rectangle([x_left + 1, y_top, x_right - 1, y_bottom], 
                      fill=body_color, outline=body_color)
        
        # Draw thin border around candle
        draw.rectangle([x_left, y_top, x_right, y_bottom], 
                      outline=body_color, width=1)
        
        # লাস্ট ক্যান্ডেল সেন্টার সেভ
        if i == actual_num_candles - 1:
            last_candle_center = (x_center, (y_top + y_bottom) // 2)
    
    # --- বর্তমান প্রাইস লাইন (dashed) ---
    latest_price = candles[-1]['close']
    y_price_line = scale_price_to_y(latest_price)
    
    # Draw dashed current price line
    draw_dashed_line(draw, 
                     (CHART_AREA_LEFT, y_price_line), 
                     (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_price_line), 
                     color=YELLOW, width=2, dash_length=8)
    
    # Draw price label at right end (solid background)
    draw.rectangle([CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_price_line - 10,
                    CHART_AREA_LEFT + CHART_AREA_WIDTH, y_price_line + 10],
                   fill=YELLOW)
    draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 55, y_price_line - 7),
              f"{latest_price:.5f}", fill=(0, 0, 0), font=font_tiny)
    
    # --- RIGHT SIDE INFO PANEL ---
    info_panel_x = CHART_AREA_LEFT + CHART_AREA_WIDTH + 20
    info_panel_y = CHART_AREA_TOP
    
    # Panel background with solid color
    draw.rectangle([info_panel_x - 10, info_panel_y - 10, 
                    WIDTH - 20, info_panel_y + 250], 
                   fill=DARK_BLUE, outline=GRAY)
    
    # BULL TERMINAL title
    draw.text((info_panel_x, info_panel_y), "BULLTERMINAL", fill=GREEN, font=font_medium)
    draw.text((info_panel_x, info_panel_y + 25), "PRICE TERMINAL", fill=BLUE, font=font_medium)
    
    # Sample price values (with clear colors)
    price_diffs = [0.0008, 0.0004, 0.0002, 0, -0.0002, -0.0004, -0.0006, -0.0008]
    info_colors = [WHITE, WHITE, WHITE, GREEN, RED, RED, RED, RED]
    
    for i, (diff, color) in enumerate(zip(price_diffs, info_colors)):
        y_pos = info_panel_y + 55 + (i * 20)
        price_val = latest_price + diff
        draw.text((info_panel_x, y_pos), f"({price_val:.5f})", fill=color, font=font_small)
    
    # BULLTERMINAL + 30 CANDLES
    draw.text((info_panel_x, info_panel_y + 220), "BULLTERMINAL + 30 CANDLES", 
              fill=GREEN, font=font_medium)
    
    # Draw a separator line
    draw.line([(info_panel_x, info_panel_y + 210), (WIDTH - 30, info_panel_y + 210)], 
              fill=GRAY, width=1)
    
    # --- বটম স্ট্যাটাস বার (স্পষ্ট) ---
    bottom_y = HEIGHT - 40
    
    # Bottom bar background
    draw.rectangle([10, bottom_y - 5, WIDTH - 10, bottom_y + 30], 
                  fill=DARK_BLUE, outline=GRAY)
    
    latest_candle = candles[-1]
    
    # টাইম স্ট্যাম্প
    time_str = latest_candle['dt'].strftime('%H:%M:%S')
    draw.text((20, bottom_y), f"TIME: {time_str}", fill=WHITE, font=font_small)
    
    # প্রাইস ইনফো
    draw.text((200, bottom_y), f"OPEN: {latest_candle['open']:.5f}", fill=GRAY, font=font_small)
    draw.text((350, bottom_y), f"CLOSE: {latest_candle['close']:.5f}", 
              fill=GREEN if latest_candle['signal'] == "CALL" else RED, 
              font=font_small)
    draw.text((500, bottom_y), f"HIGH: {latest_candle['high']:.5f}", fill=GREEN, font=font_small)
    draw.text((650, bottom_y), f"LOW: {latest_candle['low']:.5f}", fill=RED, font=font_small)
    
    # সিগন্যাল বক্স
    signal_box_x = WIDTH - 120
    signal_color = GREEN if latest_candle['signal'] == "CALL" else RED
    
    # Signal box with solid background
    draw.rectangle([signal_box_x + 2, bottom_y + 2, signal_box_x + 102, bottom_y + 27], 
                  fill=DARK_GRAY)
    draw.rectangle([signal_box_x, bottom_y, signal_box_x + 100, bottom_y + 25], 
                  fill=signal_color, outline=WHITE)
    
    signal_text = f"SIGNAL: {latest_candle['signal']}"
    text_width = draw.textlength(signal_text, font=font_medium)
    text_x = signal_box_x + (100 - text_width) // 2
    draw.text((text_x, bottom_y + 3), signal_text, fill=(0, 0, 0), font=font_medium)
    
    # Main border
    draw.rectangle([5, 5, WIDTH - 5, HEIGHT - 5], outline=GRAY, width=2)
    
    # Corner accents
    corner_size = 15
    draw.line([(5, 5), (5 + corner_size, 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, 5), (5, 5 + corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, 5), (WIDTH - 5 - corner_size, 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, 5), (WIDTH - 5, 5 + corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, HEIGHT - 5), (5 + corner_size, HEIGHT - 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, HEIGHT - 5), (5, HEIGHT - 5 - corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, HEIGHT - 5), (WIDTH - 5 - corner_size, HEIGHT - 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, HEIGHT - 5), (WIDTH - 5, HEIGHT - 5 - corner_size)], fill=LIGHT_BLUE, width=3)
    
    # --- Mark Result Candle if ON and result is provided ---
    if MARK_RESULT_CANDLE and result and last_candle_center:
        mark_color = GREEN if result == 'Profit' else RED
        # Draw circle around last candle
        draw.ellipse([last_candle_center[0] - last_candle_radius, last_candle_center[1] - last_candle_radius,
                      last_candle_center[0] + last_candle_radius, last_candle_center[1] + last_candle_radius],
                     outline=mark_color, width=3)
        
        # Add result text with solid background
        result_text = "WIN" if result == 'Profit' else "LOSS"
        text_width = draw.textlength(result_text, font=font_medium)
        draw.rectangle([last_candle_center[0] - text_width//2 - 5, last_candle_center[1] - 40,
                        last_candle_center[0] + text_width//2 + 5, last_candle_center[1] - 20],
                       fill=mark_color)
        draw.text((last_candle_center[0] - text_width//2, last_candle_center[1] - 37), 
                  result_text, fill=(0, 0, 0), font=font_medium)
    
    # Add watermark if enabled
    if WATERMARK_ON and WATERMARK_TEXT:
        watermark_text = WATERMARK_TEXT
        watermark_width = draw.textlength(watermark_text, font=font_tiny)
        draw.rectangle([WIDTH - watermark_width - 30, HEIGHT - 25,
                        WIDTH - 10, HEIGHT - 10], 
                       fill=(0, 0, 0, 100))
        draw.text((WIDTH - watermark_width - 25, HEIGHT - 22), 
                  watermark_text, fill=(255, 255, 255, 150), font=font_tiny)
    
    # ইমেজ সেভ
    buffer = BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    return buffer

def calculate_support_resistance(candles, lookback=20):
    """সাপোর্ট এবং রেজিস্ট্যান্স লেভেল ক্যালকুলেট করে"""
    if len(candles) < lookback:
        return None, None, None, None, None
    
    recent_candles = candles[-lookback:]
    highs = [c['high'] for c in recent_candles]
    lows = [c['low'] for c in recent_candles]
    
    # Simple support and resistance
    resistance = max(highs)
    support = min(lows)
    
    # Additional levels (optional)
    pivot = (resistance + support) / 2
    r1 = 2 * pivot - support
    s1 = 2 * pivot - resistance
    
    return support, resistance, pivot, r1, s1

def calculate_moving_averages(candles, periods=[20, 50, 100, 200]):
    """মুভিং এভারেজ ক্যালকুলেট করে"""
    closes = [c['close'] for c in candles]
    ma_values = {}
    
    for period in periods:
        if len(closes) >= period:
            ma_values[period] = ema(closes, period)
    
    return ma_values

# ================= ক্যান্ডেল ফেচিং ফাংশন =================

async def safe_fetch(q, pair, period):
    try:
        r = await q.get_candles(pair, time.time(), MAX_CANDLES, period)
        if r:
            return r
    except:
        pass

    try:
        r = await q.get_candle_v2(pair, period, MAX_CANDLES)
        if r:
            return r
    except:
        pass
    return None

async def get_candles_for_chart(q: Quotex, pair: str, period: int):
    raw = await safe_fetch(q, pair, period)

    if not raw:
        return []

    candles = []
    for r in raw:
        ts = r.get("time") or r.get("timestamp") or r.get("t") or r.get("date")
        dt = ts_to_dt(ts)
        if dt is None:
            continue

        open_price = float(r.get("open") or r.get("o", 0))
        close_price = float(r.get("close") or r.get("c", 0))

        signal = "CALL" if close_price > open_price else "PUT"

        candles.append({
            "dt": dt,
            "open": open_price,
            "high": float(r.get("high") or r.get("h", 0)),
            "low": float(r.get("low") or r.get("l", 0)),
            "close": close_price,
            "volume": int(r.get("volume") or r.get("v", 0)),
            "signal": signal
        })

    candles.sort(key=lambda x: x["dt"])

    if len(candles) > MAX_CANDLES:
        candles = candles[-MAX_CANDLES:]

    return candles

# ================= সিগন্যাল প্রক্রিয়াকরণ ফাংশন (আপডেট: MTG রেজাল্ট + অ্যাডভান্সড অ্যানালাইসিস) =================
async def process_signal_background(client, pair, direction, data):
    """Background task - handles signal result without blocking main loop"""
    try:
        await process_signal(client, pair, direction, data)
    except Exception as e:
        print(rainbow_text(f"𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚜𝚒𝚐𝚗𝚊𝚕 𝚎𝚛𝚛𝚘𝚛: {e}"))

async def process_signal(client, pair, direction, data):
    """Process a signal, generate chart, and handle martingale"""
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH, SIGNAL_USERNAME, SIGNAL_HEADER_TEXT
    global ADVANCED_ANALYSIS, CUSTOM_LINK

    # --- চার্ট ডেটা আনা ---
    if SEND_PHOTO_WITH_SIGNAL:
        chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
    else:
        chart_candles = None
    # --- চার্ট ডেটা আনা ---

    # **সিগন্যাল পাঠানোর আগে JSON-এ সেভ করা হবে না**
    try:
        server_now = get_timestamp()
        
        # পরবর্তী ক্যান্ডেলের সময় নির্ধারণ (বর্তমান সময়ের পরবর্তী মিনিটের শুরু)
        current_dt = datetime.now(pytz.timezone('Asia/Dhaka'))
        next_minute_dt = current_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        entry_ts = int(next_minute_dt.timestamp())  # এন্ট্রি ক্যান্ডেলের শুরু

        # প্রদর্শনের সময় (UTC+6) ফরম্যাট করুন
        disp_dt = next_minute_dt
        now_str = disp_dt.strftime("%H：%M")

        _digits = {"0":"𝟶","1":"𝟷","2":"𝟸","3":"𝟹","4":"𝟺","5":"𝟻","6":"𝟼","7":"𝟽","8":"𝟾","9":"𝟿",":":"："}
        formatted_time = "".join(_digits.get(ch, ch) for ch in now_str)

        clean_asset = pair.replace('_', '—').upper()

        direction_symbol = "🔴" if direction == "put" else "🟢"
        direction_text = "𝙿𝚄𝚃" if direction == "put" else "𝙲𝙰𝙻𝙻"

        # Get correct price from the last candle data
        try:
            # Make sure we're using the correct price from the analyzed data
            if data and len(data) > 0:
                price_val = float(data[-1]['close'])  # সঠিক পেয়ারের লাস্ট ক্লোজ প্রাইস
            else:
                # Fallback to current chart data if available
                if chart_candles and len(chart_candles) > 0:
                    price_val = float(chart_candles[-1]['close'])
                else:
                    price_val = 0.0
        except Exception as e:
            print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚐𝚎𝚝𝚝𝚒𝚗𝚐 𝚙𝚛𝚒𝚌𝚎: {e}"))
            price_val = 0.0

        price_str = f"{price_val:.5f}"
        price_digits = {"0":"𝟶","1":"𝟷","2":"𝟸","3":"𝟹","4":"𝟺","5":"𝟻","6":"𝟼","7":"𝟽","8":"𝟾","9":"𝟿",".":"."}
        formatted_price = "".join(price_digits.get(ch, ch) for ch in price_str)

        # অ্যাডভান্সড অ্যানালাইসিস সেকশন
        advanced_section = ""
        if ADVANCED_ANALYSIS and data:
            # ট্রেন্ড অ্যানালাইসিস
            trend, reversal_signal, support_level, resistance_level, logic = analyze_trend_reversal(data)
            
            # ট্রেন্ড টেক্সট ফরম্যাট
            trend_text = ""
            if trend == "UP_TREND":
                trend_text = "𝚄𝙿 𝚃𝚁𝙴𝙽𝙳"
            elif trend == "DOWN_TREND":
                trend_text = "𝙳𝙾𝚆𝙽 𝚃𝚁𝙴𝙽𝙳"
            else:
                trend_text = "𝚂𝙸𝙳𝙴𝚆𝚈𝚂"
            
            # রেজিস্ট্যান্স এবং সাপোর্ট ফরম্যাট
            resistance_text = f"{resistance_level:.5f}" if resistance_level else "𝙽/𝙰"
            support_text = f"{support_level:.5f}" if support_level else "𝙽/𝙰"
            
            # লজিক টেক্সট
            logic_text = logic if logic else "𝚃𝚛𝚎𝚗𝚍 𝙵𝚘𝚕𝚕𝚘𝚠"
            
            # যদি রিভার্স সিগন্যাল থাকে
            if reversal_signal == "POTENTIAL_DOWN_REVERSAL":
                direction_text = "𝙿𝚄𝚃 (𝚁𝙴𝚅𝚄𝚁𝚂𝙴)"
                logic_text = "𝚁𝚎𝚟𝚎𝚛𝚜𝚊𝚕 𝚊𝚝 𝚁𝚎𝚜𝚒𝚜𝚝𝚊𝚗𝚌𝚎"
            elif reversal_signal == "POTENTIAL_UP_REVERSAL":
                direction_text = "𝙲𝙰𝙻𝙻 (𝚁𝙴𝚅𝚄𝚁𝚂𝙴)"
                logic_text = "𝚁𝚎𝚟𝚎𝚛𝚜𝚊𝚕 𝚊𝚝 𝚂𝚞𝚙𝚙𝚘𝚛𝚝"
            
            advanced_section = f"""
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
📈 »» {trend_text}
🔺 »» 𝚁𝙴𝚂𝙸𝚂𝚃𝙰𝙽𝙲𝙴 {resistance_text}
🔹 »» SUPPORT {support_text}
⚖️ »» {logic_text}
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝"""
        
        # কাস্টম লিংক সেকশন
        link_section = ""
        if CUSTOM_LINK:
            # HTML লিংক ফরম্যাট
            link_section = f'🔗 <a href="{CUSTOM_LINK}">𝙲𝚁𝙴𝙰𝚃𝙴 𝙰𝙲𝙲𝙾𝚄𝙽𝚃 𝚀𝚇</a>'
        else:
            link_section = "🔗 𝙲𝚁𝙴𝙰𝚃𝙴 𝙰𝙲𝙲𝙾𝚄𝙽𝚃 𝚀𝚇"

        # Signal format with customizable username and header
        header_border = "☲☲☲☲"
        msg = f"""{header_border}【 {fancy_font(SIGNAL_HEADER_TEXT)} 】{header_border}

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
💎 »» {fancy_font(clean_asset)}
⏰ »» {formatted_time}
⏳ »» 𝙼1
{direction_symbol} »» {direction_text}
🎯 »» {formatted_price}
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝{advanced_section}
{link_section}
🚀 𝙲𝙾𝙽𝚃𝚃𝚊𝚛: {fancy_font(SIGNAL_USERNAME)}

{header_border} 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】{header_border}"""

        # প্রাথমিক সিগন্যাল পাঠানোর লজিক
        await send_telegram_photo_or_chart(msg, pair, chart_candles)

        # ট্রেড ডেটা তৈরি, কিন্তু JSON এ সেভ হবে না।
        trade_data = {
            'pair': pair, 'pair_display': clean_asset, 'direction': direction,
            'signal_time': formatted_time,  # পরবর্তী ক্যান্ডেলের সময় ব্যবহার করুন
            'signal_timestamp': entry_ts,  # টাইমস্ট্যাম্প যোগ করুন
            'price': price_val, 'result': None,
            'profit': None, 'martingale_step': 0, 'timestamp': server_now,
            'date': datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()
        }
        trade_results.append(trade_data) # শুধু মেমোরিতে যোগ করা হলো

        # এন্ট্রি ক্যান্ডেলের শুরু পর্যন্ত অপেক্ষা
        current_time = time.time()
        wait_to_entry_start = max(0, entry_ts - current_time)
        if wait_to_entry_start > 0:
            await asyncio.sleep(wait_to_entry_start)

        # এখন এন্ট্রি ক্যান্ডেল (22:53) চলছে, এর শেষ পর্যন্ত অপেক্ষা (60 সেকেন্ড)
        await asyncio.sleep(60)

        # এন্ট্রি ক্যান্ডেলের ডেটা নেওয়া (22:53 ক্যান্ডেল) - এটাই রেজাল্ট ক্যান্ডেল
        result_candle = None
        for _ in range(10):  # আরও বেশি চেষ্টা
            _data = await get_candles(client, pair, TIMEFRAME)
            if _data and len(_data) >= 1:
                # সবচেয়ে শেষ ক্যান্ডেলটি নেব, যেটি এই মিনিটের ক্যান্ডেল (এন্ট্রি ক্যান্ডেল)
                for candle in _data:
                    cand_ts = candle.get('timestamp')
                    # টাইমস্ট্যাম্প entry_ts (22:53:00) এর কাছাকাছি ক্যান্ডেল খুঁজছি
                    if cand_ts and entry_ts <= cand_ts < entry_ts + 60:
                        result_candle = candle
                        break
                    # অথবা শেষ ক্যান্ডেলটি নেব
                    elif not result_candle and candle == _data[-1]:
                        result_candle = candle
                if result_candle:
                    break
            await asyncio.sleep(2)

        if result_candle is None:
            send_telegram_message("⚠️ 𝙲𝚘𝚞𝚍 𝚗𝚘𝚝  𝚛𝚎𝚜𝚞𝚕𝚝 𝚌𝚊𝚗𝚍𝚕𝚎.")
            # যদি রেজাল্ট ক্যান্ডেল না পাওয়া যায়, তবে মেমোরি থেকে সরিয়ে দেওয়া হবে
            if trade_results and trade_results[-1]['timestamp'] == server_now:
                trade_results.pop()
            return

        result_open = float(result_candle.get('open', price_val))
        result_close = float(result_candle.get('close', price_val))

        # রেজাল্ট নির্ধারণ (22:53 ক্যান্ডেল)
        first_win = (direction == 'put' and result_close < result_open) or (direction == 'call' and result_close > result_open)
        first_equal = abs(result_close - result_open) < 0.00001

        if first_equal:
            trade_results[-1]['result'] = 'Break-even'
            trade_results[-1]['profit'] = 0.0
            # **এখন সেভ করি কারণ রেজাল্ট নিশ্চিত**
            save_trade_results()
            print(rainbow_text(f"𝚃𝚛𝚊𝚍𝚎  {clean_asset} 𝚊𝚝 {formatted_time} 𝚎𝚗𝚍𝚎𝚍 𝚒𝚗 𝙱𝚛𝚎𝚊𝚔-𝚎𝚟𝚎𝚗."))
            # ব্রেক-ইভেন রেজাল্ট মেসেজ
            # শুধুমাত্র নিশ্চিত ট্রেড গণনা
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()]
            
            wins_before = sum(1 for t in today_trades if t.get('result') == 'Profit')
            losses_before = sum(1 for t in today_trades if t.get('result') == 'Loss')
            
            wins_formatted = fancy_font(str(wins_before))
            losses_formatted = fancy_font(str(losses_before))
            total_today = wins_before + losses_before
            win_rate_today = (wins_before / total_today * 100) if total_today > 0 else 0
            win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")

            result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
⚖️ {fancy_font(clean_asset)} ┃ 🕓{formatted_time}|
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
⚖️⚖️⚖️ 𝙱𝚁𝙴𝙰𝙺-𝙴𝚅𝙴𝚅 ⚖️⚖️⚖️
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝚘𝚜𝚜:{losses_formatted} ◈ ({win_rate_formatted}％)
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌𝚝: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

            await send_telegram_photo_or_chart(result_msg, pair, chart_candles, result='Break-even')
            await asyncio.sleep(120)
            return

        # --- চার্ট ডেটা আপডেট ---
        if SEND_PHOTO_WITH_SIGNAL:
            chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
        else:
            chart_candles = None
        # --- চার্ট ডেটা আপডেট ---

        if first_win:
            # WIN লজিক (22:53 ক্যান্ডেলে উইন)
            # শুধুমাত্র নিশ্চিত ট্রেড গণনা
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()]
            
            # বর্তমান ট্রেড যোগ করার আগের স্ট্যাটস
            wins_before = sum(1 for t in today_trades if t.get('result') == 'Profit')
            losses_before = sum(1 for t in today_trades if t.get('result') == 'Loss')
            
            wins_formatted = fancy_font(str(wins_before + 1))
            losses_formatted = fancy_font(str(losses_before))
            total_today = wins_before + losses_before + 1
            win_rate_today = ((wins_before + 1) / total_today * 100) if total_today > 0 else 0
            win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")

            result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
💰 {fancy_font(clean_asset)} ┃ 🕓{formatted_time}|
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
✅✅✅ 𝚂𝚄𝚁𝙴 𝚂𝙷𝙾𝚃 ✅✅✅
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝚘𝚜𝚜:{losses_formatted} ◈ ({win_rate_formatted}％)
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌𝚝: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

            await send_telegram_photo_or_chart(result_msg, pair, chart_candles, result='Profit')

            trade_results[-1]['result'] = 'Profit'
            trade_results[-1]['profit'] = 10.0  # ফিক্সড ভ্যালু
            trade_results[-1]['martingale_step'] = 0
            save_trade_results() # **ফলাফল নিশ্চিত হওয়ার পর সেভ**
            await asyncio.sleep(120)
            return

        # Martingale logic (22:54, 22:55, ইত্যাদি ক্যান্ডেল চেক)
        if MARTINGALE_STEPS > 0:
            for martingale_step in range(1, MARTINGALE_STEPS + 1):
                # পরবর্তী ক্যান্ডেলের জন্য অপেক্ষা
                await asyncio.sleep(60)

                mg_candle = None
                waited = 0
                # এই মার্টিংগেল স্টেপের ক্যান্ডেলের শুরু: entry_ts + 60 * martingale_step
                # কারণ প্রথম রেজাল্টের জন্য আমরা entry_ts (22:53) এর ক্যান্ডেল চেক করেছি
                # দ্বিতীয় মার্টিংগেলের জন্য entry_ts + 60 (22:54)
                # তৃতীয়টির জন্য entry_ts + 120 (22:55), ইত্যাদি
                target_ts = entry_ts + 60 * martingale_step
                while waited <= 70:
                    new2 = await get_candles(client, pair, TIMEFRAME)
                    if new2 and len(new2) >= 1:
                        # আমরা এমন একটি ক্যান্ডেল খুঁজছি যার টাইমস্ট্যাম্প target_ts এর কাছাকাছি
                        for c2 in new2:
                            ts3 = c2.get('timestamp', 0)
                            if ts3 and target_ts <= ts3 < target_ts + 60:
                                mg_candle = c2
                                break
                        if mg_candle:
                            break
                    await asyncio.sleep(2)
                    waited += 2

                if mg_candle is None:
                    break

                mg_open = float(mg_candle.get('open', result_close))
                mg_close = float(mg_candle.get('close', result_close))
                mg_win = (direction == 'call' and mg_close > mg_open) or (direction == 'put' and mg_close < mg_open)
                mg_equal = abs(mg_close - mg_open) < 0.00001

                # শুধুমাত্র নিশ্চিত ট্রেড গণনা
                confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
                today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()]
                
                wins_before = sum(1 for t in today_trades if t.get('result') == 'Profit')
                losses_before = sum(1 for t in today_trades if t.get('result') == 'Loss')

                # --- চার্ট ডেটা আপডেট ---
                if SEND_PHOTO_WITH_SIGNAL:
                    chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
                else:
                    chart_candles = None
                # --- চার্ট ডেটা আপডেট ---

                if mg_equal:
                    trade_results[-1]['result'] = 'Break-even'
                    trade_results[-1]['profit'] = 0.0
                    trade_results[-1]['martingale_step'] = martingale_step
                    # **এখন সেভ করি কারণ রেজাল্ট নিশ্চিত**
                    save_trade_results()
                    
                    # ব্রেক-ইভেন রেজাল্ট মেসেজ
                    wins_formatted = fancy_font(str(wins_before))
                    losses_formatted = fancy_font(str(losses_before))
                    total_today = wins_before + losses_before
                    win_rate_today = (wins_before / total_today * 100) if total_today > 0 else 0
                    win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")
                    
                    mtg_symbol = f"𝙼𝚃𝙶{martingale_step}" if martingale_step <= 3 else f"𝙼𝚃𝙶{martingale_step}"
                    
                    result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
⚖️ {fancy_font(clean_asset)} ┃ 🕓{formatted_time} |
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
⚖️⚖️⚖️ {mtg_symbol} 𝙱𝚁𝙴𝙰𝙺-𝙴𝚅𝙴𝙽 ⚖️⚖️⚖️
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝚘𝚜𝚜:{losses_formatted} ◈ ({win_rate_formatted}％)
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌𝚝: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

                    await send_telegram_photo_or_chart(result_msg, pair, chart_candles, result='Break-even')
                    
                    print(rainbow_text(f"𝙼𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎 𝚝𝚛𝚊𝚍𝚎 𝚏𝚘𝚛 {clean_asset} 𝚊𝚝 {formatted_time} 𝚎𝚗𝚍𝚎𝚍 𝚒𝚗 𝙱𝚛𝚎𝚊𝚔-𝚎𝚟𝚎𝚗 (𝚂𝚝𝚎𝙥 {martingale_step})."))
                    break
                elif mg_win:
                    # MARTINGALE WIN লজিক (MTG¹, MTG², etc.)
                    wins_formatted = fancy_font(str(wins_before + 1))
                    losses_formatted = fancy_font(str(losses_before))
                    total_today = wins_before + losses_before + 1
                    win_rate_today = ((wins_before + 1) / total_today * 100) if total_today > 0 else 0
                    win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")
                    
                    # MTG স্টেপ অনুযায়ী টেক্সট
                    mtg_symbol = f"𝙼𝚃𝙶{martingale_step}" if martingale_step <= 3 else f"𝙼𝚃𝙶{martingale_step}"

                    result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
💰 {fancy_font(clean_asset)} ┃ 🕓{formatted_time} |
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
✅✅✅ {mtg_symbol} 𝚆𝙸𝙽 ✅✅✅
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝚘𝚜𝚜:{losses_formatted} ◈ ({win_rate_formatted}％)
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌𝚝: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

                    await send_telegram_photo_or_chart(result_msg, pair, chart_candles, result='Profit')

                    trade_results[-1]['result'] = 'Profit'
                    trade_results[-1]['profit'] = 10.0  # ফিক্সড ভ্যালু
                    trade_results[-1]['martingale_step'] = martingale_step
                    save_trade_results() # **ফলাফল নিশ্চিত হওয়ার পর সেভ**
                    break
                else:
                    # Final loss after all martingale steps
                    if martingale_step == MARTINGALE_STEPS:
                        # MARTINGALE LOSS লজিক
                        wins_formatted = fancy_font(str(wins_before))
                        losses_formatted = fancy_font(str(losses_before + 1))
                        total_today = wins_before + losses_before + 1
                        win_rate_today = (wins_before / total_today * 100) if total_today > 0 else 0
                        win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")

                        result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
📉 {fancy_font(clean_asset)} ┃ 🕓{formatted_time} |
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
✖️✖️✖️ 𝚃𝙾T𝙰𝙻 𝙻𝙾𝚂𝚂 (𝙼𝚃𝙶{martingale_step}) ✖️✖️✖️
╔═━━━━━━━ ◥◣◆◢◤ ━━━━━━━═╗
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝙾𝚂𝚂:{losses_formatted} ◈ ({win_rate_formatted}％)
╚═━━━━━━━ ◢◤◆◥◣ ━━━━━━━═╝
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌t: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

                        await send_telegram_photo_or_chart(result_msg, pair, chart_candles, result='Loss')

                        trade_results[-1]['result'] = 'Loss'
                        trade_results[-1]['profit'] = -7.0  # ফিক্সড ভ্যালু
                        trade_results[-1]['martingale_step'] = martingale_step
                        save_trade_results() # **ফলাফল নিশ্চিত হওয়ার পর সেভ**
                        break
                    else:
                        # পরবর্তী মার্টিংগেল স্টেপের জন্য চালিয়ে যাও
                        continue

        await asyncio.sleep(120)

    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚙𝚛𝚘𝚌𝚎𝚜𝚜𝚒𝚗𝚐 : {e}"))
        # যদি কোনো এরর হয়, তবে মেমোরি থেকে সরিয়ে দেওয়া হলো
        if trade_results and trade_results[-1]['timestamp'] == server_now and trade_results[-1]['result'] is None:
            trade_results.pop()
# ================= ইউটিলিটি ফাংশন =================

def get_timestamp():
    return int(time.time())

def extract_ts(item):
    for k in ("timestamp","time","t","at","date"):
        if k in item:
            try:
                v = item[k]
                if isinstance(v, str) and v.isdigit():
                    return int(v)
                if isinstance(v, (int,float)):
                    return int(v)
            except:
                pass
    return None

def normalize(resp):
    if resp is None: return None
    if isinstance(resp, dict):
        for key in ("candles","data","result","values"):
            if key in resp and isinstance(resp[key], (list,tuple)):
                lst = resp[key]
                break
        else: lst = None
    elif isinstance(resp, (list,tuple)): lst = resp
    else: lst = None
    if not lst: return None
    out = []
    for item in lst:
        if not isinstance(item, dict): continue
        ts = extract_ts(item)
        if 'open' in item and 'high' in item and 'low' in item and 'close' in item:
            try:
                out.append({'open': float(item['open']), 'high': float(item['high']), 'low': float(item['low']), 'close': float(item['close']), 'timestamp': ts})
                continue
            except: pass
        if 'o' in item and 'h' in item and 'l' in item and 'c' in item:
            try:
                out.append({'open': float(item['o']), 'high': float(item['h']), 'low': float(item['l']), 'close': float(item['c']), 'timestamp': ts})
                continue
            except: pass
        vals = list(item.values())
        if len(vals) >= 4:
            try:
                out.append({'open': float(vals[0]), 'high': float(vals[1]), 'low': float(vals[2]), 'close': float(vals[3]), 'timestamp': ts})
                continue
            except: pass
    if not out: return None
    return out

async def try_fetch(client, asset, period):
    try:
        end_time = int(time.time())
        try:
            r = await client.get_candles(asset, end_time, 60, period)
            return r
        except: pass
        try:
            r = await client.get_candles(asset, period)
            return r
        except: pass
        try:
            r = await client.get_candles(asset, end_time, period)
            return r
        except: pass
        try:
            func = getattr(client, "get_candles", None)
            if func:
                r = func(asset, period)
                if asyncio.iscoroutine(r): r = await r
                return r
        except: pass
        try:
            func2 = getattr(client, "get_realtime_candles", None)
            if func2:
                r = func2(asset, period)
                if asyncio.iscoroutine(r): r = await r
                return r
        except: pass
        try:
            func3 = getattr(client, "get_candle_v2", None)
            if func3:
                r = func3(asset, period, 100)
                if asyncio.iscoroutine(r): r = await r
                return r
        except: pass
    except: pass
    return None

async def get_candles(client, asset, period, attempts=CANDLE_FETCH_ATTEMPTS):
    for _ in range(attempts):
        resp = await try_fetch(client, asset, period)
        norm = normalize(resp)
        if norm and len(norm) >= 5: return norm
        await asyncio.sleep(0.25)
    return None

def ema(values, period):
    if len(values) < period: return None
    alpha = 2.0 / (period + 1.0)
    ema_val = sum(values[-period:]) / period
    for i in range(-period + 1, 0):
        ema_val = values[i] * alpha + ema_val * (1 - alpha)
    return ema_val

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    gains = []; losses = []
    for i in range(len(prices)-period, len(prices)-1):
        change = prices[i+1] - prices[i]
        if change > 0: gains.append(change); losses.append(0)
        else: gains.append(0); losses.append(abs(change))
    if not gains or not losses: return 50.0
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_bollinger(prices, period=20, std_dev=2):
    if len(prices) < period: return None, None, None
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    return ma, upper, lower

def calculate_support_resistance_levels(prices, lookback=20):
    """সাপোর্ট এবং রেজিস্ট্যান্স লেভেল ক্যালকুলেট করে"""
    if len(prices) < lookback:
        return None, None
    
    recent_prices = prices[-lookback:]
    resistance = max(recent_prices)
    support = min(recent_prices)
    
    return support, resistance

def calculate_moving_averages(candles, periods=[20, 50, 100, 200]):
    """মুভিং এভারেজ ক্যালকুলেট করে"""
    closes = [c['close'] for c in candles]
    ma_values = {}
    
    for period in periods:
        if len(closes) >= period:
            ma_values[period] = ema(closes, period)
    
    return ma_values

# ================= নতুন স্ট্র্যাটেজি অ্যানালাইসিস ফাংশন =================

def analyze_market(candle_data):
    global CURRENT_STRATEGY, EMA_PERIOD, RSI_PERIOD, MIN_SIGNAL_SCORE, SUPPORT_RESISTANCE_STRATEGY, SUPERTREND_STRATEGY
    if not candle_data or len(candle_data) < max(EMA_PERIOD, RSI_PERIOD): 
        return None, 0.0
    
    closes = [c['close'] for c in candle_data]

    if CURRENT_STRATEGY == "EMA_RSI":
        rsi = calculate_rsi(closes, RSI_PERIOD)
        ema_val = ema(closes, EMA_PERIOD)
        current_price = closes[-1]

        sig_dir = None
        score = 0

        if current_price > ema_val and 50 < rsi < 70:
            sig_dir = "call"; score = 5
        elif current_price < ema_val and 30 < rsi < 50:
            sig_dir = "put"; score = 5
        elif rsi > 80:
            sig_dir = "put"; score = 4
        elif rsi < 20:
            sig_dir = "call"; score = 4
        
        # Check if signal meets minimum score
        if score < MIN_SIGNAL_SCORE: 
            return None, 0.0
        
        # Additional confirmation: check recent trend
        if len(closes) >= 3:
            recent_trend = sum(1 for i in range(-3, 0) if closes[i] > closes[i-1])
            if sig_dir == "call" and recent_trend < 2:
                score -= 1
            elif sig_dir == "put" and recent_trend > 1:
                score -= 1
        
        if score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        else:
            return None, 0.0

    elif CURRENT_STRATEGY == "Trend":
        if len(closes) < 10: return None, 0.0
        trend_score = sum(1 if closes[i] > closes[i-1] else -1 for i in range(-5, 0))
        if trend_score >= 3: return "call", 4
        elif trend_score <= -3: return "put", 4
        return None, 0.0

    elif CURRENT_STRATEGY == "Bollinger":
        if len(closes) < 20: return None, 0.0
        ma, upper, lower = calculate_bollinger(closes)
        if ma is None: return None, 0.0
        
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        
        if current_price < lower and prev_price >= lower:
            return "call", 5
        elif current_price > upper and prev_price <= upper:
            return "put", 5
        return None, 0.0

    elif CURRENT_STRATEGY == "Support_Resistance" and SUPPORT_RESISTANCE_STRATEGY:
        if len(closes) < 20: return None, 0.0
        support, resistance = calculate_support_resistance_levels(closes)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        
        if support and resistance:
            # Resistance breakout with confirmation
            if current_price > resistance and prev_price <= resistance:
                # Check volume or other confirmation
                return "call", 5
            # Support breakdown with confirmation
            elif current_price < support and prev_price >= support:
                return "put", 5
            # Resistance rejection with strong bearish candle
            elif abs(current_price - resistance) / resistance < 0.001 and current_price < prev_price:
                return "put", 4
            # Support bounce with strong bullish candle
            elif abs(current_price - support) / support < 0.001 and current_price > prev_price:
                return "call", 4
        
        return None, 0.0

    elif CURRENT_STRATEGY == "Trend_Reverse":
        # ট্রেন্ড+রিভার্স স্ট্র্যাটেজি
        if len(closes) < 30: return None, 0.0
        
        # ট্রেন্ড ডিটেকশন
        ma20 = ema(closes, 20) if len(closes) >= 20 else None
        ma50 = ema(closes, 50) if len(closes) >= 50 else None
        current_price = closes[-1]
        
        # RSI for overbought/oversold
        rsi = calculate_rsi(closes, 14)
        
        # Support and Resistance levels
        support, resistance = calculate_support_resistance_levels(closes, lookback=20)
        
        sig_dir = None
        score = 0
        logic = ""
        
        if ma20 and ma50:
            # Uptrend detected
            if current_price > ma20 and ma20 > ma50:
                logic = "UP_TREND"
                # Check for overbought reversal
                if rsi > 70 and resistance and abs(current_price - resistance) / resistance < 0.005:
                    sig_dir = "put"  # Potential reversal from resistance
                    score = 5
                    logic = "REVERSAL_AT_RESISTANCE"
                else:
                    # Trend continuation
                    sig_dir = "call"
                    score = 4
                    logic = "TREND_CONTINUATION"
            
            # Downtrend detected
            elif current_price < ma20 and ma20 < ma50:
                logic = "DOWN_TREND"
                # Check for oversold reversal
                if rsi < 30 and support and abs(current_price - support) / support < 0.005:
                    sig_dir = "call"  # Potential reversal from support
                    score = 5
                    logic = "REVERSAL_AT_SUPPORT"
                else:
                    # Trend continuation
                    sig_dir = "put"
                    score = 4
                    logic = "TREND_CONTINUATION"
            
            # Sideways market
            else:
                logic = "SIDEWAYS"
                # Range trading strategy
                if resistance and support:
                    range_mid = (resistance + support) / 2
                    if current_price > range_mid and rsi < 60:
                        sig_dir = "call"
                        score = 3
                        logic = "RANGE_BOUNCE_FROM_MID"
                    elif current_price < range_mid and rsi > 40:
                        sig_dir = "put"
                        score = 3
                        logic = "RANGE_DROP_FROM_MID"
        
        # Additional confirmation with volume if available
        if sig_dir and len(candle_data) > 1:
            last_volume = candle_data[-1].get('volume', 0)
            prev_volume = candle_data[-2].get('volume', 0) if len(candle_data) > 1 else 0
            
            # Volume confirmation
            if last_volume > prev_volume * 1.2:
                score += 1  # Increase score with volume confirmation
        
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        else:
            return None, 0.0

    elif CURRENT_STRATEGY == "Price_Action":
        """প্রাইস অ্যাকশন স্ট্র্যাটেজি"""
        if len(candle_data) < 5: return None, 0.0
        
        patterns = detect_price_action_patterns(candle_data)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        
        sig_dir = None
        score = 0
        
        # Check for recent patterns
        recent_patterns = [p for p in patterns if p['candle_index'] >= len(candle_data) - 3]
        
        for pattern in recent_patterns:
            if pattern['type'] in ['BULLISH_ENGULFING', 'HAMMER']:
                sig_dir = "call"
                score = 5
                break
            elif pattern['type'] in ['BEARISH_ENGULFING', 'SHOOTING_STAR']:
                sig_dir = "put"
                score = 5
                break
        
        # If no pattern found, use simple price action
        if not sig_dir:
            # Bullish if higher high and higher low
            if len(closes) >= 3:
                if closes[-1] > closes[-2] > closes[-3]:
                    sig_dir = "call"
                    score = 4
                elif closes[-1] < closes[-2] < closes[-3]:
                    sig_dir = "put"
                    score = 4
        
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        else:
            return None, 0.0

    elif CURRENT_STRATEGY == "Supertrend" and SUPERTREND_STRATEGY:
        """সুপারট্রেন্ড স্ট্র্যাটেজি"""
        if len(candle_data) < 20: return None, 0.0
        
        supertrend_values, trend_values = calculate_supertrend(candle_data, period=10, multiplier=3)
        
        if supertrend_values and trend_values and supertrend_values[-1] is not None:
            current_price = closes[-1]
            current_supertrend = supertrend_values[-1]
            current_trend = trend_values[-1]
            
            sig_dir = None
            score = 0
            
            # Bullish signal when price crosses above supertrend in uptrend
            if current_trend == 1 and current_price > current_supertrend:
                sig_dir = "call"
                score = 5
            # Bearish signal when price crosses below supertrend in downtrend
            elif current_trend == -1 and current_price < current_supertrend:
                sig_dir = "put"
                score = 5
            # Trend continuation signals
            elif current_trend == 1 and current_price > current_supertrend * 1.001:
                sig_dir = "call"
                score = 4
            elif current_trend == -1 and current_price < current_supertrend * 0.999:
                sig_dir = "put"
                score = 4
            
            if sig_dir and score >= MIN_SIGNAL_SCORE:
                return sig_dir, score
        
        return None, 0.0

    elif CURRENT_STRATEGY == "FVG_Strategy":
        """FVG স্ট্র্যাটেজি"""
        if len(candle_data) < 10: return None, 0.0
        
        fvg_gaps = detect_fvg_gaps(candle_data)
        current_price = closes[-1]
        
        sig_dir = None
        score = 0
        
        # Check for recent FVG gaps
        recent_fvg = [g for g in fvg_gaps if g['candle_index'] >= len(candle_data) - 5]
        
        for fvg in recent_fvg:
            # Bullish FVG: Price above FVG zone suggests bullish continuation
            if fvg['type'] == 'BULLISH_FVG' and current_price > fvg['end_price']:
                sig_dir = "call"
                score = 5
                break
            # Bearish FVG: Price below FVG zone suggests bearish continuation
            elif fvg['type'] == 'BEARISH_FVG' and current_price < fvg['end_price']:
                sig_dir = "put"
                score = 5
                break
        
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        else:
            return None, 0.0

    return None, 0.0

async def analyze_pair(client, pair):
    data = await get_candles(client, pair, TIMEFRAME)
    if not data or len(data) < 20: 
        return None
    
    # Additional validation: check if we have recent data
    if len(data) < 5:
        return None
    
    # Check if data is valid (no extreme spikes)
    closes = [c['close'] for c in data]
    price_range = max(closes) - min(closes)
    avg_price = sum(closes) / len(closes)
    
    # Filter out pairs with too much volatility or abnormal prices
    if price_range / avg_price > 0.1:  # More than 10% range in recent candles
        return None
    
    direction, score = analyze_market(data)
    if direction and score >= MIN_SIGNAL_SCORE: 
        return direction, score, data
    return None

# ================= get_profitable_pairs ফাংশন (আপডেট) =================

async def get_profitable_pairs(client, min_profit=70):
    global ANALYZE_ALL_PAIRS, CUSTOM_PAIRS_MODE, CUSTOM_PAIRS_LIST

    if CUSTOM_PAIRS_MODE and CUSTOM_PAIRS_LIST:
        print(rainbow_text(f"✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛𝚜 𝙼𝚘𝚍𝚎 𝙾𝙽. 𝙰𝚗𝚊𝚕𝚢S {len(CUSTOM_PAIRS_LIST)} 𝚌𝚞𝚜𝚝𝚖 𝙿𝚊𝚒𝚛𝚜."))
        return CUSTOM_PAIRS_LIST

    # যদি Custom Pairs Mode OFF থাকে, তবে স্বাভাবিক লজিক ব্যবহার করা হবে
    try:
        assets = None
        if hasattr(client, "get_all_assets"):
            r = client.get_all_assets()
            if asyncio.iscoroutine(r): assets = await r
            else: assets = r
        else: assets = None
    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚐𝚎𝚝𝚝𝚒𝚗𝚐 𝚊𝚜𝚎𝚝𝚜 𝚏𝚛𝚘𝚖 𝙰𝙿𝙸: {e}"))
        assets = None

    if not assets:
        print(rainbow_text("𝚐𝚎𝚍_𝚊𝚕𝚕_𝚊𝚓𝚜𝚎𝚍 𝚛𝚎𝚝𝚞𝚗𝚎𝚍  𝚝𝚘𝚝𝚎. 𝚄𝚜𝚒𝚗𝚐 𝚏𝚒𝚕𝚝𝚎𝚍 𝚍𝚎𝚏𝚊𝚞𝚕𝚝 𝙿𝚊𝚛𝚛𝚜."))
        if ANALYZE_ALL_PAIRS: return list(PAIR_NAMES.keys())
        else: return [p for p in list(PAIR_NAMES.keys()) if p.lower() not in OTC_PAIRS_TO_EXCLUDE]

    def normalize_profit(v):
        try: v_f = float(v)
        except Exception: return 0.0
        if v_f >= 300: return v_f - 300
        if 0 < v_f <= 1: return v_f * 100.0
        return v_f

    pairs = []

    def should_exclude(pair_name):
        if ANALYZE_ALL_PAIRS: return False
        pair_check_name = pair_name.lower().replace('-otc', '_otc')
        if pair_check_name in OTC_PAIRS_TO_EXCLUDE: return True
        if pair_name.upper().replace('_OTC', '-OTC') in OTC_PAIRS_TO_EXCLUDE: return True
        return False

    if isinstance(assets, dict):
        for name, raw in assets.items():
            if should_exclude(name): continue
            payout = 0.0
            if isinstance(raw, (int, float, str)): payout = normalize_profit(raw)
            elif isinstance(raw, dict):
                if 'payout' in raw: payout = normalize_profit(raw.get('payout'))
                elif 'profit' in raw: payout = normalize_profit(raw.get('profit'))
                elif 'yield' in raw: payout = normalize_profit(raw.get('yield'))
                else:
                    found = None
                    for val in raw.values():
                        try:
                            found = float(val)
                            break
                        except: continue
                    payout = normalize_profit(found if found is not None else 0.0)
            else: payout = 0.0

            if payout >= min_profit: pairs.append(name)
    elif isinstance(assets, (list, tuple)):
        for a in assets:
            name = None; payout = 0.0
            if isinstance(a, str): name = a
            elif isinstance(a, dict):
                name = a.get('name') or a.get('displayName') or a.get('title') or a.get('asset_name') or None
                for key in ('payout','profit','yield','return'):
                    if key in a:
                        payout = normalize_profit(a.get(key))
                        break

            if name:
                if should_exclude(name): continue
                if isinstance(a, str) or payout >= min_profit: pairs.append(name)

    pairs = list(dict.fromkeys(pairs))

    if not pairs:
        print(rainbow_text("𝙽𝚘 𝚙𝚊𝚒𝚛𝚜 𝚏𝚘𝚞𝚗𝚍 𝚠𝚒𝚝𝚑 𝚖𝚒𝚗_𝚙𝚛𝚘𝚒𝚝, 𝚍𝚎𝚏𝚊𝚞𝚕𝚝 𝙿𝚊𝚒𝚛𝚜."))
        if ANALYZE_ALL_PAIRS: pairs = list(PAIR_NAMES.keys())
        else: pairs = [p for p in list(PAIR_NAMES.keys()) if p.lower() not in OTC_PAIRS_TO_EXCLUDE]

    filter_status = "𝙰𝚕𝚕 𝚙চ�𝚒𝚛𝚜 𝚒𝚗𝚌𝚕𝚞𝚍" if ANALYZE_ALL_PAIRS else f"𝙴𝚡𝚌𝚕𝚞𝚍𝚒𝚗𝚐 {len(OTC_PAIRS_TO_EXCLUDE)} 𝙾𝚃𝙲 𝚙𝚊𝚒𝚛𝚜"
    print(rainbow_text(f"✅ 𝙻𝚘𝚊𝚍𝚎𝚍 {len(pairs)} 𝚙𝚊𝚒𝚛𝚜 𝚏𝚛𝚘𝚖 𝙰𝙿𝙸 (𝚖𝚒𝚛_𝚙𝚛𝚘𝚒𝚝={min_profit}) - {filter_status}."))
    return pairs

# ================= send_partial_results ফাংশন (আপডেট: MTG স্টেপ সহ) =================

def send_partial_results():
    """Send partial results in the specified format with MTG steps"""
    global last_partial_results_time

    now = int(time.time())
    if now - last_partial_results_time < PARTIAL_RESULTS_INTERVAL: return

    last_partial_results_time = now

    bd_time = datetime.now(pytz.timezone('Asia/Dhaka'))
    today_date = bd_time.strftime("%d．%m．%Y")

    # শুধুমাত্র নিশ্চিত ট্রেড (Profit/Loss/Break-even)
    confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss', 'Break-even']]
    today_trades = [r for r in confirmed_trades if r.get('date') == bd_time.date().isoformat()]

    otc_trades = [t for t in today_trades if 'OTC' in t.get('pair_display', '').upper() or '_otc' in t.get('pair', '').lower()]
    real_trades = [t for t in today_trades if not ('OTC' in t.get('pair_display', '').upper() or '_otc' in t.get('pair', '').lower())]

    def count_wins_losses(trades):
        wins = sum(1 for t in trades if t.get('result') == 'Profit')
        losses = sum(1 for t in trades if t.get('result') == 'Loss')
        return wins, losses

    otc_wins, otc_losses = count_wins_losses(otc_trades)
    real_wins, real_losses = count_wins_losses(real_trades)

    # Build partial results message
    msg = "========= 𝙿𝙰𝚁𝚃𝙸𝙰𝙻 𝚁𝙴𝚂𝚄𝙻𝚃𝚂 ==========\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += f"                  📆 — {today_date}\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += "                  📈 𝚁𝙴𝙰𝙻 𝙼𝙰𝚁𝙺𝙴𝚃\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"

    if not real_trades: msg += "——— 𝙽𝙾 𝚁𝙴𝙰𝙻 𝚂𝙸𝙶𝙽𝙰𝙻𝚂 𝙿𝙻𝙰𝙲𝙴𝙳 ———\n"
    else:
        for trade in real_trades[-20:]:
            # সরাসরি signal_time ব্যবহার করুন যা সিগন্যাল জেনারেট হওয়ার সময়
            time_str = trade.get('signal_time', '𝟶𝟶：𝟶𝟶')
            pair_display = trade.get('pair_display', trade['pair'])
            direction = "𝙱𝚄𝚈" if trade.get('direction') == 'call' else "𝙿𝚄𝚃"
            result_icon = "✅" if trade.get('result') == 'Profit' else "❌"
            # MTG স্টেপ দেখাবে
            martingale_step = trade.get('martingale_step', 0)
            if martingale_step > 0 and trade.get('result') == 'Profit':
                # MTG স্টেপ সংখ্যা যোগ করব
                if martingale_step == 1:
                    result_icon = "✅¹"
                elif martingale_step == 2:
                    result_icon = "✅²"
                elif martingale_step == 3:
                    result_icon = "✅³"
                else:
                    result_icon = f"✅{martingale_step}"
            msg += f"⧉ {time_str} - {fancy_font(pair_display)} - {fancy_font(direction)} {result_icon}\n"

    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += "                  📉 𝙾𝚃𝙲 𝙼𝙰𝚁𝙺𝙴𝚃\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"

    if not otc_trades: msg += "——— 𝙽𝙾 𝙾𝚃𝙲 𝚂𝙸𝙶𝙽𝙰𝙻𝚂 𝙿𝙻𝙰𝙲𝙴𝙳 ———\n"
    else:
        for trade in otc_trades[-20:]:
            # সরাসরি signal_time ব্যবহার করুন যা সিগন্যাল জেনারেট হওয়ার সময়
            time_str = trade.get('signal_time', '𝟶𝟶：𝟶𝟶')
            pair_display = trade.get('pair_display', trade['pair'])
            direction = "𝙱𝚄𝚈" if trade.get('direction') == 'call' else "𝙿𝚄𝚃"
            result_icon = "✅" if trade.get('result') == 'Profit' else "❌"
            # MTG স্টেপ দেখাবে
            martingale_step = trade.get('martingale_step', 0)
            if martingale_step > 0 and trade.get('result') == 'Profit':
                # MTG স্টেপ সংখ্যা যোগ করব
                if martingale_step == 1:
                    result_icon = "✅¹"
                elif martingale_step == 2:
                    result_icon = "✅²"
                elif martingale_step == 3:
                    result_icon = "✅³"
                else:
                    result_icon = f"✅{martingale_step}"
            msg += f"⧉ {time_str} - {fancy_font(pair_display)} - {fancy_font(direction)} {result_icon}\n"

    msg += "━━━━━━━━━・━━━━━━━━━\n"

    overall_stats = get_statistics(today_trades)
    msg += f" 🧮 𝙿𝙻𝙰𝙲𝙴𝚁 : {fancy_font(str(overall_stats['total_trades']))} 𝘅 {fancy_font(str(overall_stats['losses']))} ◈ ({fancy_font(format(overall_stats['accuracy'], ' .1f').strip())}٪)\n"

    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += f" 🚀 𝚆𝙸𝙽 : {fancy_font(str(overall_stats['wins']))} ┃ 𝙻𝙾𝚂𝚂 : {fancy_font(str(overall_stats['losses']))} ┃ ◈ ({fancy_font(format(overall_stats['accuracy'], ' .1f').strip())}٪)\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += " 📳 𝚃𝙴𝚁𝙼𝚄𝚇 𝙿𝙰𝚁𝚃𝙸𝙰𝙻 𝚂𝙴𝙽𝙳"

    send_telegram_message(msg)

# ================= send_signal ফাংশন =================

async def send_signal(client):
    """Manual signal trigger - also fires and forgets"""
    global last_signal_time, signal_count, bot_running, current_signal_task, last_partial_results_time, next_signal_interval, SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX, continuous_analysis

    now = int(time.time())

    if now - last_partial_results_time >= PARTIAL_RESULTS_INTERVAL:
        send_partial_results()

    # Check if it's time for the next signal
    if now - last_signal_time < next_signal_interval: 
        return False  # Not time yet

    last_signal_time = now
    next_signal_interval = get_next_signal_interval()

    if not bot_running: 
        return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_pair = {}
        pairs = await get_profitable_pairs(client, min_profit=70)
        if not pairs:
            print(rainbow_text("𝙽𝚘 𝚙𝚛𝚘𝚏𝚒𝚝𝚊𝚋𝚕𝚎 𝚙𝚊𝚒𝚛𝚜 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚔𝚒𝚙𝚙𝚒𝚗𝚐 𝚝𝚑𝚒𝚜 𝚌𝚢𝚌𝚕𝚎."))
            # Continue analysis after delay
            await asyncio.sleep(10)
            return

        for pair in pairs[:40]:
            future = executor.submit(
                asyncio.run,
                analyze_pair(client, pair)
            )
            future_to_pair[future] = pair

        best_pair = None
        best_dir = None
        best_score = -1e9
        best_data = None
        viable_pairs = []

        for future in concurrent.futures.as_completed(future_to_pair):
            if not bot_running: 
                break
            pair = future_to_pair[future]
            try:
                result = future.result()
                if result and len(result) == 3:
                    direction, score, data = result
                    if direction and score > 0:
                        viable_pairs.append((pair, direction, score, data))
                        if score > best_score:
                            best_pair, best_dir, best_score, best_data = pair, direction, score, data
            except Exception as e:
                print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚙𝚛𝚘𝚌𝚎𝚜𝚜𝚒𝚗𝚐 𝚙𝚊𝚒𝚛 {pair}: {e}"))
                continue

        # Only send signal if we have a valid analysis
        if not viable_pairs:
            print(rainbow_text("⚠️ 𝙽𝚘 𝚟𝚊𝚕𝚒𝚍 𝚜𝚒𝚐𝚗𝚊𝚕𝚜 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚔𝚒𝚙𝚙𝚒𝚗𝚐 𝚝𝚑𝚒𝚜 𝚌𝚢𝚌𝚕𝚎."))
            # Continue analysis after delay
            await asyncio.sleep(10)
            return

        if not best_pair and viable_pairs:
            viable_pairs.sort(key=lambda x: x[2], reverse=True)
            best_pair, best_dir, best_score, best_data = viable_pairs[0]
            print(rainbow_text(f"⚠️ 𝚄𝚜𝚒𝚗𝚐 𝚋𝚎𝚜𝚝 𝚊𝚟𝚊𝚒𝚕𝚊𝚋𝚕𝚎 𝚜𝚒𝚐𝚗𝚊𝚕 (𝚜𝚌𝚘𝚛𝚎: {best_score})"))

        if best_pair and best_dir and best_data:
            # Launch as background task - don't wait for result
            asyncio.create_task(process_signal_background(client, best_pair, best_dir, best_data))
            signal_count += 1
            print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 #{signal_count} 𝚜𝚎𝚗𝚝 𝚏𝚘𝚛 {best_pair} ({best_dir}) 𝚠𝚒𝚝𝚑 𝚜𝚌𝚘𝚛𝚎: {best_score}"))
        else:
            print(rainbow_text("⚠️ 𝙽𝚘 𝚜𝚒𝚐𝚗𝚊𝚕 𝚖𝚎𝚎𝚝𝚒𝚗𝚐 𝚖𝚒𝚗𝚒𝚖𝚞𝚖 𝚜𝚌𝚘𝚛𝚎 𝚛𝚎𝚚𝚞𝚒𝚛𝚎𝚖𝚎𝚗𝚝𝚜."))
            await asyncio.sleep(10)

# ================= ট্রেডিং বট ফাংশন =================


# ================= Continuous Signal Loop =================
async def continuous_signal_loop(client):
    """Continuously generates signals at set intervals - sends signals independently"""
    global bot_running, last_signal_time, next_signal_interval, current_signal_task

    while bot_running:
        try:
            now = int(time.time())

            # Check if it's time for next signal
            if now - last_signal_time >= next_signal_interval:
                # Fire and forget - don't wait for result
                # Create new task that runs independently
                asyncio.create_task(send_signal_fire_and_forget(client))
                last_signal_time = now
                next_signal_interval = get_next_signal_interval()
                print(rainbow_text(f"⏰ Next signal in {next_signal_interval//60} minutes..."))

            await asyncio.sleep(10)  # Check every 10 seconds
        except Exception as e:
            print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚒𝚗 𝚌𝚘𝚗𝚝𝚒𝚗𝚞𝚘𝚞𝚜 𝚕𝚘𝚘𝚙: {e}"))
            await asyncio.sleep(10)

async def send_signal_fire_and_forget(client):
    """Sends a signal without blocking the main loop"""
    global signal_count
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_pair = {}
            pairs = await get_profitable_pairs(client, min_profit=70)
            if not pairs:
                print(rainbow_text("𝙽𝚘 𝚙𝚛𝚘𝚏𝚒𝚝𝚊𝚋𝚕𝚎 𝚙𝚊𝚒𝚛𝚜 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚔𝚒𝚙𝚙𝚒𝚗𝚐 𝚝𝚑𝚒𝚜 𝚌𝚢𝚌𝚕𝚎."))
                return

            for pair in pairs[:40]:
                future = executor.submit(
                    asyncio.run,
                    analyze_pair(client, pair)
                )
                future_to_pair[future] = pair

            best_pair = None
            best_dir = None
            best_score = -1e9
            best_data = None
            viable_pairs = []

            for future in concurrent.futures.as_completed(future_to_pair):
                if not bot_running: 
                    break
                pair = future_to_pair[future]
                try:
                    result = future.result()
                    if result and len(result) == 3:
                        direction, score, data = result
                        if direction and score > 0:
                            viable_pairs.append((pair, direction, score, data))
                            if score > best_score:
                                best_pair, best_dir, best_score, best_data = pair, direction, score, data
                except Exception as e:
                    print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚙𝚛𝚘𝚌𝚎𝚜𝚜𝚒𝚗𝚐 𝚙𝚊𝚒𝚛 {pair}: {e}"))
                    continue

            if not viable_pairs:
                print(rainbow_text("⚠️ 𝙽𝚘 𝚟𝚊𝚕𝚒𝚍 𝚜𝚒𝚐𝚗𝚊𝚕𝚜 𝚏𝚘𝚞𝚗𝚍. 𝚂𝚔𝚒𝚙𝚙𝚒𝚗𝚐 𝚝𝚑𝚒𝚜 𝚌𝚢𝚌𝚕𝚎."))
                return

            if not best_pair and viable_pairs:
                viable_pairs.sort(key=lambda x: x[2], reverse=True)
                best_pair, best_dir, best_score, best_data = viable_pairs[0]
                print(rainbow_text(f"⚠️ 𝚄𝚜𝚒𝚗𝚐 𝚋𝚎𝚜𝚝 𝚊𝚟𝚊𝚒𝚕𝚊𝚋𝚕𝚎 𝚜𝚒𝚐𝚗𝚊𝚕 (𝚜𝚌𝚘𝚛𝚎: {best_score})"))

            if best_pair and best_dir and best_data:
                # Launch signal processing as independent background task
                asyncio.create_task(process_signal_background(client, best_pair, best_dir, best_data))
                signal_count += 1
                print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 #{signal_count} 𝚜𝚎𝚗𝚝 𝚏𝚘𝚛 {best_pair} ({best_dir}) 𝚠𝚒𝚝𝚑 𝚜𝚌𝚘𝚛𝚎: {best_score}"))
            else:
                print(rainbow_text("⚠️ 𝙽𝚘 𝚜𝚒𝚐𝚗𝚊𝚕 𝚖𝚎𝚎𝚝𝚒𝚗𝚐 𝚖𝚒𝚗𝚒𝚖𝚞𝚖 𝚜𝚌𝚘𝚛𝚎 𝚛𝚎𝚚𝚞𝚒𝚛𝚎𝚖𝚎𝚗𝚝𝚜."))
    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚒𝚗 𝚜𝚒𝚐𝚗𝚊𝚕 𝚏𝚒𝚛𝚎-𝚊𝚗𝚍-𝚏𝚘𝚛𝚐𝚎𝚝: {e}"))

async def trading_bot():
    global last_signal_time, start_time, next_signal_interval, BOT_ALERT_ON
    email = "qtrader874@gmail.com"
    password = "@quotextrader123"

    start_time = int(time.time())
    next_signal_interval = get_next_signal_interval()

    client = Quotex(email=email, password=password, lang="en")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            success, msg = await client.connect()
            if success: break
            else:
                print(rainbow_text(f"𝙲𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚊𝚝𝚝𝚎𝚖𝚙𝚝 {attempt+1} 𝚏𝚊𝚒𝚕𝚎𝚍: {msg}"))
                if attempt < max_retries - 1: await asyncio.sleep(5)
        except Exception as e:
            print(rainbow_text(f"𝙲𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚎𝚛𝚛𝚘𝚛 𝚘𝚗 𝚊𝚝𝚝𝚎𝚖𝚙𝚝 {attempt+1}: {e}"))
            if attempt < max_retries - 1: await asyncio.sleep(5)
    else:
        # Enhanced Telegram message for connection failure
        if BOT_ALERT_ON:
            connection_failed_msg = """🔴 *BOT CONNECTION FAILED*

⚠️ *Status:* Could not connect to Quotex account after multiple attempts
📊 *Attempts:* 5 retries completed
🔧 *Action Required:* Check credentials and internet connection
🔄 *Next Action:* Restart the bot after verifying details

📱 *Contact Support:* @TRADEIQDEV_TRADER2
🕐 *Time:* """ + datetime.now(pytz.timezone('Asia/Dhaka')).strftime("%H:%M:%S")
            send_telegram_message(connection_failed_msg)
        return

    # Enhanced Telegram message for successful bot start
    if BOT_ALERT_ON:
        bot_started_msg = f"""✅ *BOT STARTED SUCCESSFULLY*

🎯 *Status:* Bot is now running and ready to send signals
📊 *Mode:* {'Custom Pairs Only' if CUSTOM_PAIRS_MODE else ('All Pairs' if ANALYZE_ALL_PAIRS else 'Exclude OTC List')}
⚙️ *Strategy:* {CURRENT_STRATEGY}
🔢 *Martingale Steps:* {MARTINGALE_STEPS}
🖼️ *Chart Mode:* {'Market Chart Photo' if SEND_PHOTO_WITH_SIGNAL else 'Text Only'}
⏱️ *Signal Interval:* {SIGNAL_INTERVAL_MIN//60}-{SIGNAL_INTERVAL_MAX//60} minutes
📈 *Advanced Analysis:* {'ON' if ADVANCED_ANALYSIS else 'OFF'}
🔗 *Custom Link:* {'SET' if CUSTOM_LINK else 'NOT SET'}
🌀 *FVG Gap Draw:* {'ON' if FVG_GAP_DRAW else 'OFF'}
📊 *Supertrend Chart:* {'ON' if SUPERTREND_CHART else 'OFF'}
🎨 *Custom Candle Colors:* {'ON' if CANDLE_UP_COLOR != (0, 200, 0) or CANDLE_DOWN_COLOR != (255, 50, 50) else 'OFF'}

📱 *Contact:* {SIGNAL_USERNAME}
🕐 *Start Time:* {datetime.now(pytz.timezone('Asia/Dhaka')).strftime("%H:%M:%S")}
📅 *Date:* {datetime.now(pytz.timezone('Asia/Dhaka')).strftime("%d/%m/%Y")}

🚀 *TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝐏𝐫𝐨𝐟𝐞𝐬𝐬𝐢𝐨𝐧𝐚𝐥 𝐓𝐫𝐚𝐝𝐢𝐧𝐠 𝐒𝐲𝐬𝐭𝐞𝐦*"""
        
        send_telegram_message(bot_started_msg)

    # Start continuous signal loop
    signal_loop_task = asyncio.create_task(continuous_signal_loop(client))

    while bot_running:
        try:
            if not client.check_connect():
                print(rainbow_text("𝙲𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚕𝚘𝚜𝚝, 𝚊𝚝𝚝𝚎𝚖𝚙𝚝𝚒𝚗𝚐 𝚝𝚘 𝚛𝚎𝚌𝚘𝚗𝚗𝚎𝚌𝚝..."))
                success, msg = await client.connect()
                if not success:
                    print(rainbow_text(f"𝚁𝚎𝚌𝚘𝚗𝚗𝚎𝚌𝚝𝚒𝚘𝚗 𝚏𝚊𝚒𝚕𝚎𝚍: {msg}"))
                    await asyncio.sleep(10)
                    continue

            await asyncio.sleep(30)  # Main loop just keeps connection alive
        except Exception as e:
            print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚒𝚗 𝚝𝚛𝚊𝚍𝚒𝚗𝚐 𝚕𝚘𝚘𝚙: {e}"))
            await asyncio.sleep(10)

    # Cancel signal loop when bot stops
    if signal_loop_task and not signal_loop_task.done():
        signal_loop_task.cancel()
        try:
            await signal_loop_task
        except asyncio.CancelledError:
            pass

def _thread_target():
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(trading_bot())
    except Exception as e:
        print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚒𝚗 𝚝𝚑𝚛𝚎𝚊𝚍: {e}"))
    finally:
        try:
            loop.close()
        except: pass

def start_bot():
    global bot_running, last_partial_results_time, BOT_ALERT_ON
    if bot_running:
        if BOT_ALERT_ON:
            send_telegram_message("ℹ️ 𝙱𝚘𝚝 𝚒𝚜 𝚊𝚕𝚛𝚎𝚊𝚍𝚢 𝚛𝚞𝚗𝚗𝚒𝚗𝚐")
        return
    bot_running = True
    last_partial_results_time = int(time.time())
    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    # টেলিগ্রাম ক্লায়েন্ট শুরু করুন (completely optional)
    telegram_client_started = False
    if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_API_HASH != "" and TELEGRAM_SOURCE_CHANNEL and TELEGRAM_SOURCE_CHANNEL != "":
        telegram_thread = threading.Thread(target=start_telegram_client, daemon=True)
        telegram_thread.start()
        telegram_client_started = True

    if not telegram_client_started:
        print(rainbow_text("ℹ️ Telegram client not configured, skipping (bot will still send signals via Bot API if token is set)"))
    print(rainbow_text("🤖 𝙱𝚘𝚝 𝚜𝚝𝚊𝚛𝚝𝚎𝚍 𝚜𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢!"))

def stop_bot():
    global bot_running, BOT_ALERT_ON
    if not bot_running: return
    bot_running = False
    
    # Enhanced Telegram message for bot stop
    if BOT_ALERT_ON:
        bot_stopped_msg = f"""🛑 *BOT STOPPED*

📊 *Final Statistics:*
✅ Today's Wins: {sum(1 for r in trade_results if r.get('result') == 'Profit' and r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat())}
❌ Today's Losses: {sum(1 for r in trade_results if r.get('result') == 'Loss' and r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat())}
📈 Total Signals Sent: {len([r for r in trade_results if r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()])}

🔒 *Status:* Bot has been safely stopped
💾 *Data Saved:* All trade results have been saved
🔄 *Restart:* Use /start to restart the bot

📱 *Contact:* {SIGNAL_USERNAME}
🕐 *Stop Time:* {datetime.now(pytz.timezone('Asia/Dhaka')).strftime("%H:%M:%S")}
📅 *Date:* {datetime.now(pytz.timezone('Asia/Dhaka')).strftime("%d/%m/%Y")}

🚀 *TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝐓𝐫𝐚𝐝𝐢𝐧𝐠 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 𝐄𝐧𝐝𝐞𝐝*"""
        
        send_telegram_message(bot_stopped_msg)
    print(rainbow_text("⏹️ 𝙱𝚘𝚟 𝚜𝚝𝚘𝚙𝚙𝚎𝚍"))

# ================= ম্যানুয়াল রেজাল্ট ফাংশন =================

def send_manual_result():
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH, SIGNAL_USERNAME
    
    # Only consider trades that are currently pending (result is None)
    pending_trades = [t for t in trade_results if t.get('result') is None]

    if not pending_trades:
        print(rainbow_text("❌ 𝙽𝚘 𝚙𝚎𝚗𝚍𝚒𝚗𝚐 𝚜𝚒𝚐𝚗𝚊𝚕𝚜 𝚝𝚘 𝚜𝚎𝚗𝚍 𝚛𝚎𝚜𝚞𝚕𝚝 𝚏𝚘𝚛."))
        return

    print("\n" + "="*52)
    print(rainbow_text("📊 𝚂𝚎𝚗𝚍 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝 𝚖𝚊𝚗𝚞𝚊𝚕𝚕𝚢"))
    print("="*52)

    # Show the last 5 pending trades
    for i, trade in enumerate(pending_trades[-5:], 1):
        pair_display = trade.get('pair_display', trade['pair'])
        print(rainbow_text(f"{i}. {pair_display} - {trade['direction']} - {trade['signal_time']} - ⏳ 𝙿𝚎𝚗𝚍𝚒𝚗𝚐"))

    last_trade = pending_trades[-1]
    last_trade_index = trade_results.index(last_trade) # Find the index in the main list

    print(rainbow_text("\n𝟷. ✅ 𝚂𝚎𝚗𝚍 𝚠𝚒𝚗𝚗𝚒𝚗𝚐 𝚛𝚎𝚜𝚞𝚕𝚝 (𝚂𝚞𝚛𝚎 𝚂𝚑𝚘𝚝) 𝚏𝚘𝚛 𝚕𝚊𝚜𝚝 𝚙𝚎𝚗𝚍𝚒𝚗𝚐 𝚜𝚒𝚐𝚗𝚊𝚕"))
    print(rainbow_text("𝟸. ❌ 𝚂𝚎𝚗𝚍 𝚕𝚘𝚜𝚒𝚗𝚐 𝚛𝚎𝚜𝚞𝚕𝚝 (𝚂𝚞𝚛𝚎 𝚂𝚑𝚘𝚝 𝙻𝚘𝚜𝚜) 𝚏𝚘𝚛 𝚕𝚊𝚜𝚝 𝚙𝚎𝚗𝚍𝚒𝚗𝚐 𝚜𝚒𝚐𝚗𝚊𝚕"))
    print(rainbow_text("𝟹. ↩️ 𝙱𝚊𝚌𝚔 𝚝𝚘 𝚖𝚊𝚒𝚗 𝚖𝚎𝚗𝚞"))

    choice = input(rainbow_text("𝙲𝚑𝚘𝚘𝚜𝚎 𝚘𝚙𝚝𝚒𝚘𝚗: ")).strip()

    if choice in ("1", "2"):
        pair_display = last_trade.get('pair_display', last_trade['pair'])

        # Get stats BEFORE updating the last trade's result
        temp_trades = [t for i, t in enumerate(trade_results) if i < last_trade_index and t.get('result') in ['Profit', 'Loss']]
        today_trades_before = [t for t in temp_trades if t.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()]
        today_stats = get_statistics(today_trades_before) # Stats before current trade is counted

        wins = today_stats['wins']
        losses = today_stats['losses']

        if choice == "1":
            result = "Profit"
            wins += 1
            result_text = "✅✅✅ 𝚂𝚄𝚁𝙴 𝚂𝙷𝙾𝚃 ✅✅✅"
        elif choice == "2":
            result = "Loss"
            losses += 1
            result_text = "✖️✖️✖️ 𝙻𝙾𝚂𝚂 ✖️✖️✖️"

        # Update the trade in the main list
        trade_results[last_trade_index]['result'] = result
        trade_results[last_trade_index]['profit'] = 10.0 if result == "Profit" else -7.0  # ফিক্সড ভ্যালু
        trade_results[last_trade_index]['martingale_step'] = 0
        save_trade_results()

        wins_formatted = fancy_font(str(wins))
        losses_formatted = fancy_font(str(losses))
        total_today = wins + losses
        win_rate_today = (wins / total_today * 100) if total_today > 0 else 0
        win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")

        result_msg = f"""𒆜☲☲☲ 𝚁╎𝙴╎𝚂╎𝚄╎𝙻╎𝚃 ☲☲☲☲𒆜

╭━━━━━━━【⛨】━━━━━━━╮
{'💰' if result == 'Profit' else '📉'} {fancy_font(pair_display)} ┃ 🕓{last_trade['signal_time']}|
╰━━━━━━━【⛨】━━━━━━━╯
{result_text}

╭━━━━━━━【⛨】━━━━━━━╮
🔥 𝚆𝚒𝚗:{wins_formatted} | ☃️ 𝙻𝚘𝚜𝚜:{losses_formatted} ◈ ({win_rate_formatted}％)
╰━━━━━━━【⛨】━━━━━━━╯
📊 𝚃𝙾𝙳𝙰𝚈: {wins_formatted}W/{losses_formatted}L ({win_rate_formatted}％)
🌐 𝙲𝚘𝚗𝚝𝚊𝚌𝚝: {fancy_font(SIGNAL_USERNAME)}

☲☲☲_ 【 𝐀𝙸 𝐒𝙸𝙶𝙽𝙰𝐋 𝐐𝚇 】☲☲☲☲"""

        # ম্যানুয়াল ফলাফল পাঠানোর লজিক
        asyncio.run(send_telegram_photo_or_chart(result_msg, last_trade['pair'], None, result=result))

        print((rainbow_text(f"✅ 𝙼𝚊𝚗𝚞𝚊𝚕 {result} 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚙𝚘𝚛𝚝 𝚜𝚎𝚗𝚝 𝚏𝚘𝚛 {pair_display}")))

    elif choice == "3":
        return
    else:
        print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚘𝚙𝚝𝚒𝚘𝚕"))

def show_partial_results():
    if not trade_results:
        print(rainbow_text("📊 𝙽𝚘 𝚝𝚛𝚊𝚍𝚎𝚜 𝚢𝚎𝚝"))
        return

    bd_time = datetime.now(pytz.timezone('Asia/Dhaka'))
    today_date = bd_time.strftime("%d．%m．%Y")

    # Only include confirmed trades
    confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
    today_trades = [r for r in confirmed_trades if r.get('date') == bd_time.date().isoformat()]

    otc_trades = [t for t in today_trades if 'OTC' in t.get('pair_display', '').upper() or '_otc' in t.get('pair', '').lower()]
    real_trades = [t for t in today_trades if not ('OTC' in t.get('pair_display', '').upper() or '_otc' in t.get('pair', '').lower())]

    def count_wins_losses(trades):
        wins = sum(1 for t in trades if t.get('result') == 'Profit')
        losses = sum(1 for t in trades if t.get('result') == 'Loss')
        return wins, losses

    otc_wins, otc_losses = count_wins_losses(otc_trades)
    real_wins, real_losses = count_wins_losses(real_trades)

    print("\n" + "="*52)
    print(rainbow_text("📊 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚛𝚎𝚜𝚞𝚕𝚝𝚜"))
    print("="*52)
    print(rainbow_text(f"📅 𝙳𝚊𝚝𝚎: {today_date}"))
    print(rainbow_text(f"📈 𝚃𝚘𝚝𝚊𝚕 𝚜𝚒𝚐𝚗𝚊𝚕𝚜 𝚜𝚎𝚗𝚝: {len(trade_results)}"))
    print(rainbow_text(f"📊 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚝𝚛𝚊𝚍𝚎𝚜 (𝙲𝚘𝚗𝚏𝚒𝚛𝚖𝚎𝚍): {len(today_trades)}"))
    print(rainbow_text(f"📉 𝙾𝚃𝙲 𝚝𝚛𝚊𝚍𝚎𝚜 (𝙲𝚘𝚗𝚏𝚒𝚛𝚖𝚎𝚚): {len(otc_trades)}"))
    print(rainbow_text(f"📈 𝚁𝚎𝚊𝚕 𝚝𝚛𝚊𝚍𝚎𝚜 (𝙲𝚘𝚗𝚏𝚒𝚛𝚖𝚎𝚍): {len(real_trades)}"))

    if otc_trades:
        otc_total = otc_wins + otc_losses
        otc_win_rate = (otc_wins / otc_total * 100) if otc_total > 0 else 0
        print(rainbow_text(f"\n📊 𝙾𝚃𝙲 𝙼𝚊𝚛𝚔𝚎𝚝 𝚂𝚝𝚊𝚝𝚒𝚜𝚝𝚒𝚌𝚜:"))
        print(rainbow_text(f"✅ 𝚆𝚒𝚗𝚗𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎𝚜: {otc_wins}"))
        print(rainbow_text(f"❌ 𝙻𝚘𝚜𝚜𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎𝚜: {otc_losses}"))
        print(rainbow_text(f"📊 𝚆𝚒𝚗 𝚛𝚊𝚝𝚎: {otc_win_rate:.1f}%"))

    if real_trades:
        real_total = real_wins + real_losses
        real_win_rate = (real_wins / real_total * 100) if real_total > 0 else 0
        print(rainbow_text(f"\n📊 𝚁𝚎𝚊𝚕 𝙼𝚊𝚛𝚔𝚎𝚟 𝚂𝚝𝚊𝚝𝚒𝚜𝚝𝚒𝚌𝚜:"))
        print(rainbow_text(f"✅ 𝚆𝚒𝚗𝚗𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎𝚜: {real_wins}"))
        print(rainbow_text(f"❌ 𝙻𝚘𝚜𝚜𝚒𝚗𝚐 𝚝𝚛𝚊𝚍𝚎𝚜: {real_losses}"))
        print(rainbow_text(f"📊 𝚆𝚒𝚗 𝚛𝚊𝚝𝚎: {real_win_rate:.1f}%"))

    input(rainbow_text("\n𝙿𝚛𝚎𝚜𝚜 𝙴𝚗𝚝𝚎𝚛 𝚝𝚘 𝚌𝚘𝚗𝚝𝚒𝚗𝚞𝚎..."))

# ================= ক্লিন স্ক্রিন ফাংশন =================

def clear_screen():
    """ক্লিন স্ক্রিন ফাংশন - Termux/Kali compatible"""
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system("clear 2>/dev/null || printf \"\033c\" || tput clear 2>/dev/null")

# ================= সেটিংস মেনু (আপডেট) =================

def settings_menu():
    global MARTINGALE_STEPS, PARTIAL_RESULTS_INTERVAL, SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH
    global ANALYZE_ALL_PAIRS, CUSTOM_PAIRS_MODE, CUSTOM_PAIRS_LIST, EMA_PERIOD, RSI_PERIOD
    global CURRENT_STRATEGY, MARK_RESULT_CANDLE, MIN_SIGNAL_SCORE, SUPPORT_RESISTANCE_LINES
    global MOVING_AVERAGE_LINES, SUPPORT_RESISTANCE_STRATEGY, SHOW_GRID_LINES, SHOW_PRICE_SCALE
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SIGNAL_USERNAME, SIGNAL_INTERVAL_MIN
    global SIGNAL_INTERVAL_MAX, TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER
    global TELEGRAM_SOURCE_CHANNEL, TELEGRAM_TARGET_CHANNELS, PREMIUM_EMOJI_MODE, PREMIUM_EMOJI_TARGET
    global TREND_LINES, BACKGROUND_TRANSPARENCY, CHART_TEXT_GLOW, WATERMARK_ON, WATERMARK_TEXT
    global SIGNAL_HEADER_TEXT, CHART_HEADER_TEXT
    global PARABOLIC_SAR_LINES, GAP_DRAWING, REVERSE_AREA_DRAWING, ADVANCED_ANALYSIS, CUSTOM_LINK
    global FVG_GAP_DRAW, BOT_ALERT_ON, CANDLE_UP_COLOR, CANDLE_DOWN_COLOR, EMA_LINE_CHART
    global SUPERTREND_CHART, SUPERTREND_STRATEGY, SNR_LINES

    while True:
        clear_screen()
        print("\n" + "="*60)
        print(rainbow_text("⚙️ 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 𝙼𝙴𝙽𝚄"))
        print("="*60)
        
        colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
        
        options = [
            f"𝟷. 𝙼𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎 𝚂𝚝𝚎𝚙𝚜: {MARTINGALE_STEPS}",
            f"𝟸. 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚁𝚎𝚜𝚞𝚕𝚝𝚜 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕: {PARTIAL_RESULTS_INTERVAL} 𝚜𝚎𝚌𝚘𝚗𝚍𝚜 ({PARTIAL_RESULTS_INTERVAL//60} 𝚖𝚒𝚗𝚞𝚝𝚎𝚜)",
            f"𝟹. 𝚂𝚒𝚐𝚗𝚊𝚕 𝙿𝚑𝚘𝚝𝚘 𝙼𝚘𝚍𝚎: {'✅ ' if SEND_PHOTO_WITH_SIGNAL else '❌ '} {'𝙼𝚊𝚛𝚔𝚎𝚝 𝙲𝚑𝚊𝚛𝚝 𝙿𝚑𝚘𝚝𝚘' if SEND_PHOTO_WITH_SIGNAL else '𝚃𝚎𝚡𝚝 𝙾𝚗𝚕𝚢'}",
            f"𝟺. 𝙲𝚑𝚊𝚛𝚝 𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝙿𝚑𝚘𝚝𝚘 𝙿𝚊𝚝𝚑: {CHART_BACKGROUND_IMAGE_PATH[:40]}...",
            f"𝟻. 𝙰𝚗𝚊𝚕𝚢𝚣𝚎 𝙰𝚕𝚕 𝙿𝚊𝚒𝚛𝚜: {'✅ 𝙾𝙽' if ANALYZE_ALL_PAIRS else '❌ 𝙾𝙵𝙵 (𝙴𝚡𝚌𝚕𝚞𝚍𝚎 𝙻𝚒𝚜𝚝 𝙰𝚙𝚙𝚕𝚒𝚎𝚡)'}",
            f"𝟼. 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛 𝙼𝚘𝚍𝚎: {'✅ 𝙾𝙽' if CUSTOM_PAIRS_MODE else '❌ 𝙾𝙵𝙵'} ({'𝙲𝚄𝚂𝚃𝙾𝙼 𝙿𝙰𝙸𝚁𝚂 𝙾𝙽𝙻𝚈' if CUSTOM_PAIRS_MODE else '𝙰𝚄𝚃𝙾 𝙵𝙸𝙽𝙳 𝙿𝙰𝙸𝚁𝚂'})",
            f"𝟽. 𝚂𝚎𝚝 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛𝚜 𝙻𝚒𝚜𝚝: [{', '.join(CUSTOM_PAIRS_LIST[:2])}{'...' if len(CUSTOM_PAIRS_LIST) > 2 else ''}]",
            f"𝟾. 𝙴𝙼𝙰 𝙿𝚎𝚛𝚒𝚘𝚍: {EMA_PERIOD}",
            f"𝟿. 𝚁𝚂𝙸 𝙿𝚎𝚛𝚒𝚘𝚍: {RSI_PERIOD}",
            f"𝟷𝟶. 𝙲𝚞𝚛𝚛𝚎𝚗𝚝 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢: {CURRENT_STRATEGY}",
            f"𝟷𝟷. 𝙼𝚊𝚛𝚔 𝚁𝚎𝚜𝚞𝚕𝚝 𝙲𝚊𝚗𝚍𝚕𝚎: {'✅ 𝙾𝙽' if MARK_RESULT_CANDLE else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟸. 𝙼𝚒??𝚒𝚖𝚞𝚖 𝚂𝚒𝚐𝚗𝚊𝚕 𝚂𝚌𝚘𝚛𝚎: {MIN_SIGNAL_SCORE}",
            f"𝟷𝟹. 𝚂𝚞𝚙𝚙𝚘𝚛𝚝/𝚁𝚎𝚜𝚒𝚜𝚝𝚊𝚗𝚌𝚎 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if SUPPORT_RESISTANCE_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟺. 𝙼𝚘𝚟𝚒𝚗𝚐 𝙰𝚟𝚎𝚛𝚊𝚐𝚎 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if MOVING_AVERAGE_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟻. 𝚂𝚞𝚙𝚙𝚘𝚛𝚝/𝚁𝚎𝚜𝚒𝚜𝚝𝚊𝚗𝚌𝚎 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚒: {'✅ 𝙾𝙽' if SUPPORT_RESISTANCE_STRATEGY else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟼. 𝚂𝚑𝚘𝚠 𝙶𝚛𝚒𝚍 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if SHOW_GRID_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟽. 𝚂𝚑𝚘𝚠 𝙿𝚛𝚒𝚌𝚎 𝚂𝚌𝚊𝚕𝚎: {'✅ 𝙾𝙽' if SHOW_PRICE_SCALE else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟾. 𝚃𝚛𝚎𝚗𝚍 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if TREND_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟷𝟿. 𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚃𝚛𝚊𝚗𝚜𝚙𝚊𝚛𝚎𝚗𝚌𝚢: {BACKGROUND_TRANSPARENCY}%",
            f"𝟸𝟶. 𝙲𝚑𝚊𝚛𝚝 𝚃𝚎𝚡𝚝 𝙶𝚕𝚘𝚠: {CHART_TEXT_GLOW}%",
            f"𝟸𝟷. 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔: {'✅ 𝙾𝙽' if WATERMARK_ON else '❌ 𝙾𝙵𝙵'}",
            f"𝟸𝟸. 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔 𝚃𝚎𝚡𝚝: {WATERMARK_TEXT[:30]}...",
            f"𝟸𝟹. 𝚂𝚒𝚐𝚗𝚊𝚕 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝: {SIGNAL_HEADER_TEXT[:30]}...",
            f"𝟸𝟺. 𝙲𝚑𝚊𝚛𝚝 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝: {CHART_HEADER_TEXT[:30]}...",
            f"𝟸𝟻. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗: {TELEGRAM_BOT_TOKEN[:15]}...",
            f"𝟸𝟼. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙲𝚑𝚊𝚝 𝙸𝙳: {TELEGRAM_CHAT_ID}",
            f"𝟸𝟽. 𝚂𝚒𝚐𝚗𝚊𝚕 𝚄𝚜𝚎𝚛𝚗𝚊𝚖𝚎: {SIGNAL_USERNAME}",
            f"𝟸𝟾. 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼??𝚗: {SIGNAL_INTERVAL_MIN} 𝚜𝚎𝚌𝚘𝚗𝚍𝚜",
            f"𝟸𝟿. 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼𝚊𝚡: {SIGNAL_INTERVAL_MAX} 𝚜𝚎𝚌𝚘𝚗𝚍𝚜",
            f"𝟹𝟶. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙸𝙳: {TELEGRAM_API_ID}",
            f"𝟹𝟷. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙷𝚊𝚜𝚑: {TELEGRAM_API_HASH[:10]}...",
            f"𝟹𝟸. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙿𝚑𝚘𝚗𝚎 𝙽𝚞𝚖𝚋𝚎𝚛: {TELEGRAM_PHONE_NUMBER}",
            f"𝟹𝟹. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕: {TELEGRAM_SOURCE_CHANNEL}",
            f"𝟹𝟺. 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚃𝚊𝚛𝚐𝚎𝚝 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜: {TELEGRAM_TARGET_CHANNELS}",
            f"𝟹𝟻. 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝙴𝚖𝚘𝚓𝚒 𝙼𝚘𝚍𝚎: {'✅ 𝙾𝙽' if PREMIUM_EMOJI_MODE else '❌ 𝙾𝙵𝙵'}",
            f"𝟹𝟼. 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝙴𝚖𝚘𝚓𝚒 𝚃𝚊𝚛𝚐𝚎𝚝: {'✅ 𝙾𝙽' if PREMIUM_EMOJI_TARGET else '❌ 𝙾𝙵𝙵'}",
            f"𝟹𝟽. 🌀 𝙿𝚊𝚛𝚊𝚋𝚘𝚕𝚒𝚌 𝚂𝙰𝚁 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if PARABOLIC_SAR_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟹𝟾. 📊 𝙶𝙰𝙿 𝙳𝚛𝚊𝚠𝚒𝚗𝚐: {'✅ 𝙾𝙽' if GAP_DRAWING else '❌ 𝙾𝙵𝙵'}",
            f"𝟹𝟿. 🔄 𝚁𝚎𝚟𝚎𝚛𝚜𝚎 𝙰𝚛𝚎𝚊 𝙳𝚛𝚊𝚠𝚒𝚗𝚐: {'✅ 𝙾𝙽' if REVERSE_AREA_DRAWING else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟶. 📈 𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚍 𝙰𝚗𝚊𝚕𝚢𝚜𝚒𝚜: {'✅ 𝙾𝙽' if ADVANCED_ANALYSIS else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟷. 🔗 𝙲𝚞𝚜𝚝𝚘𝚖 𝙻𝚒𝚗𝚔: {CUSTOM_LINK[:30] if CUSTOM_LINK else '𝙽𝙾𝚃 𝚂𝙴𝚃'}",
            f"𝟺𝟸. 🌀 𝙵𝚅𝙶 𝙶𝚊𝚙 𝙳𝚛𝚊𝚠: {'✅ 𝙾𝙽' if FVG_GAP_DRAW else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟹. 🔔 𝙱𝚘𝚝 𝙾𝙽/𝙾𝙵𝙵 𝙰𝚕𝚎𝚛𝚝: {'✅ 𝙾𝙽' if BOT_ALERT_ON else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟺. 🎨 𝙲𝚊𝚗𝚍𝚕𝚎 𝚄𝚙 𝙲𝚘𝚕𝚘𝚛: RGB{CANDLE_UP_COLOR}",
            f"𝟺𝟻. 🎨 𝙲𝚊𝚗𝚍𝚕𝚎 𝙳𝚘𝚠𝚗 𝙲𝚘𝚕𝚘𝚛: RGB{CANDLE_DOWN_COLOR}",
            f"𝟺𝟼. 📈 𝙴𝙼𝙰 𝙻𝚒𝚗𝚎 𝙲𝚑𝚊𝚛𝚝: {'✅ 𝙾𝙽' if EMA_LINE_CHART else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟽. 📊 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝙲𝚑𝚊𝚛𝚝: {'✅ 𝙾𝙽' if SUPERTREND_CHART else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟾. 🎯 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢: {'✅ 𝙾𝙽' if SUPERTREND_STRATEGY else '❌ 𝙾𝙵𝙵'}",
            f"𝟺𝟿. 📐 𝚂𝙽𝚁 𝙻𝚒𝚗𝚎𝚜: {'✅ 𝙾𝙽' if SNR_LINES else '❌ 𝙾𝙵𝙵'}",
            f"𝟻𝟶. 𝚂𝚎𝚗𝚍 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚁𝚎𝚜𝚞𝚕𝚝𝚜 𝙽𝚘𝚠",
            f"𝟻𝟷. 𝙿𝙰𝚁𝚃𝙸𝙰𝙻 𝚁𝙴𝚂𝙴𝚃 (𝚁𝚎𝚜𝚎𝚝 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚃𝚛𝚊𝚍𝚎 𝙷𝚒𝚜𝚝𝚘𝚛𝚢)",
            f"𝟻𝟸. 𝚂𝚊𝚟𝚎 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜",
            f"𝟻𝟹. 𝙱𝚊𝚌𝚔 𝚝𝚘 𝙼𝚊𝚒𝚗 𝙼𝚎𝚗𝚞"
        ]
        
        for i, option in enumerate(options):
            color = colors[i % len(colors)]
            print(color + fancy_font(option))
        
        print("="*60)

        choice = input(rainbow_text("𝙲𝚑𝚘𝚘𝚜𝚎 𝚘𝚙𝚝𝚒𝚘𝚗: ")).strip()

        if choice == "1":
            try:
                steps = int(input(fancy_font("𝙴𝚗𝚝𝚎𝚛 𝚗𝚞𝚖𝚋𝚎𝚛 𝚘𝚏 𝚖𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎 𝚜𝚝𝚎𝚙𝚜 (𝟶-𝟹): ")))
                if 0 <= steps <= 3: 
                    MARTINGALE_STEPS = steps
                    print(rainbow_text(f"✅ 𝙼𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎 𝚜𝚝𝚎𝚙𝚜 𝚜𝚎𝚝 𝚝𝚘 {steps}"))
                else: 
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟶 𝚊𝚗𝚍 𝟹"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "2":
            try:
                interval = int(input(fancy_font("𝙴𝚗𝚝𝚎𝚛 𝚙𝚊𝚛𝚝𝚒𝚊𝚕 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚒𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝚒𝚗 𝚖𝚒𝚗𝚞𝚝𝚎𝚜 (𝟷-𝟼𝟶): ")))
                if 1 <= interval <= 60: 
                    PARTIAL_RESULTS_INTERVAL = interval * 60
                    print(rainbow_text(f"✅ 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚒𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝚜𝚎𝚝 𝚝𝚘 {interval} 𝚖𝚒𝚗𝚞𝚝𝚎𝚜"))
                else: 
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟷 𝚊𝚗𝚍 𝟼𝟶"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "3":
            SEND_PHOTO_WITH_SIGNAL = not SEND_PHOTO_WITH_SIGNAL
            new_mode = '𝙼𝚊𝚛𝚔𝚎𝚝 𝙲𝚑𝚊𝚛𝚝 𝙿𝚑𝚘𝚝𝚘' if SEND_PHOTO_WITH_SIGNAL else '𝚃𝚎𝚡𝚝 𝙾𝚗𝚕𝚢'
            print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙿𝚑𝚘𝚝𝚘 𝙼𝚘𝚍𝚎 𝚒𝚜 𝚗𝚘𝚠 {new_mode}"))
        elif choice == "4":
            new_path = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚌𝚑𝚊𝚛𝚝 𝚋𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚙𝚑𝚘𝚝𝚘 𝚙𝚊𝚝𝚑: ")).strip()
            if new_path: 
                CHART_BACKGROUND_IMAGE_PATH = new_path
                print(rainbow_text(f"✅ 𝙲𝚑𝚊𝚛𝚝 𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝙿𝚑𝚘𝚝𝚘 𝚙𝚊𝚝𝚑 𝚜𝚎𝚝 𝚝𝚘: {CHART_BACKGROUND_IMAGE_PATH}"))
            else: 
                print(rainbow_text("⚠️ 𝙿𝚊𝚝𝚑 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "5":
            ANALYZE_ALL_PAIRS = not ANALYZE_ALL_PAIRS
            status = '𝙾𝙽' if ANALYZE_ALL_PAIRS else '𝙾𝙵𝙵 (𝙴𝚡𝚌𝚕𝚞𝚍𝚎 𝙻𝚒𝚜𝚝 𝙰𝚙𝚙𝚕𝚒𝚎𝚡)'
            print(rainbow_text(f"✅ 𝙰𝚗𝚊𝚕𝚢𝚣𝚎 𝙰𝚕𝚕 𝙿𝚊𝚒𝚛𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "6":
            CUSTOM_PAIRS_MODE = not CUSTOM_PAIRS_MODE
            new_mode = '𝙲𝚄𝚂𝚃𝙾𝙼 𝙿𝙰𝙸𝚁𝚂 𝙾𝙽𝙻𝚈' if CUSTOM_PAIRS_MODE else '𝙰𝚄𝚃𝙾 𝙵𝙸𝙽𝙳 𝙿𝙰𝙸𝚁𝚂'
            print(rainbow_text(f"✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛 𝙼𝚘𝚍𝚎 𝚒𝚜 𝚗𝚘𝚠 {new_mode}"))
        elif choice == "7":
            current_list_str = ", ".join(CUSTOM_PAIRS_LIST)
            new_pairs_str = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚙𝚊𝚒𝚛𝚜 (𝚎.𝚐., 𝙱𝚁𝙻𝚄𝚂𝙳_𝚘𝚝𝚌,𝚄𝚂𝙳𝙿𝙺𝚁_𝚘𝚝𝚌) (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {current_list_str}): ")).strip()
            if new_pairs_str:
                new_list = [p.strip() for p in new_pairs_str.split(',') if p.strip()]
                if new_list:
                    CUSTOM_PAIRS_LIST = new_list
                    print(rainbow_text(f"✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛𝚜 𝙻𝚒𝚜𝚝 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘: {', '.join(CUSTOM_PAIRS_LIST)}"))
                else:
                    print(rainbow_text("❌ 𝙸𝚗𝚙𝚞𝚝 𝚠𝚊?? 𝚎𝚖𝚙𝚝𝚢 𝚘𝚛 𝚘𝚗𝚕𝚢 𝚜𝚎𝚙𝚊𝚛𝚊𝚝𝚘𝚛𝚜."))
            else:
                print(rainbow_text("⚠️ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙿𝚊𝚒𝚛𝚜 𝙻𝚒𝚜𝚝 𝚗𝚘𝚛 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "8":
            try:
                period = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝙴𝙼𝙰 𝚙𝚎𝚛𝚒𝚘𝚍 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {EMA_PERIOD}): ")))
                if period > 0: 
                    EMA_PERIOD = period
                    print(rainbow_text(f"✅ 𝙴𝙼𝙰 𝙿𝚎𝚛𝚒𝚘𝚍 𝚜𝚎𝚟 𝚝𝚘 {period}"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "9":
            try:
                period = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚁𝚂𝙸 𝚙𝚎𝚛𝚒𝚘𝚍 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {RSI_PERIOD}): ")))
                if period > 0: 
                    RSI_PERIOD = period
                    print(rainbow_text(f"✅ 𝚁𝚂𝙸 𝙿𝚎𝚛𝚒𝚘𝚍 𝚜𝚎𝚝 𝚝𝚘 {period}"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "10":
            print(rainbow_text("𝙰𝚟𝚊𝚒𝚕𝚊𝚋𝚕𝚎 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚒𝚎𝚜: " + ", ".join(AVAILABLE_STRATEGIES)))
            new_strategy = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚜𝚝𝚛𝚊𝚝𝚎𝚐𝚢 𝚗𝚊𝚖𝚎 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CURRENT_STRATEGY}): ")).strip()
            if new_strategy in AVAILABLE_STRATEGIES:
                CURRENT_STRATEGY = new_strategy
                print(rainbow_text(f"✅ 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢 𝚜𝚎𝚝 𝚝𝚘 {new_strategy}"))
            else:
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚜𝚝𝚛𝚊𝚝𝚎𝚐𝚢"))
        elif choice == "11":
            MARK_RESULT_CANDLE = not MARK_RESULT_CANDLE
            status = '𝙾𝙽' if MARK_RESULT_CANDLE else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙼𝚊𝚛𝚔 𝚁𝚎𝚜𝚞𝚕𝚝 𝙲𝚊𝚗𝚍𝚕𝚎 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "12":
            try:
                score = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚖𝚒𝚗𝚒𝚖𝚞𝚖 𝚜𝚒𝚐𝚗𝚊𝚕 𝚜𝚌𝚘𝚛𝚎 (𝟷-𝟻) (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {MIN_SIGNAL_SCORE}): ")))
                if 1 <= score <= 5: 
                    MIN_SIGNAL_SCORE = score
                    print(rainbow_text(f"✅ 𝙼𝚒𝚗𝚒𝚖𝚞𝚖 𝚂𝚒𝚐𝚗𝚊𝚕 𝚂𝚌𝚘𝚛𝚎 𝚜𝚎𝚝 𝚝𝚘 {score}"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚟"))
        elif choice == "13":
            SUPPORT_RESISTANCE_LINES = not SUPPORT_RESISTANCE_LINES
            status = '𝙾𝙽' if SUPPORT_RESISTANCE_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚞𝚙𝚙𝚘𝚛𝚝/𝚁𝚎𝚜𝚒𝚜𝚝𝚊𝚗𝚌𝚎 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "14":
            MOVING_AVERAGE_LINES = not MOVING_AVERAGE_LINES
            status = '𝙾𝙽' if MOVING_AVERAGE_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙼𝚘𝚟𝚒𝚗𝚐 𝙰𝚟𝚎𝚛𝚊𝚐𝚎 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "15":
            SUPPORT_RESISTANCE_STRATEGY = not SUPPORT_RESISTANCE_STRATEGY
            status = '𝙾𝙽' if SUPPORT_RESISTANCE_STRATEGY else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚞𝚙𝚙𝚘𝚛𝚝/𝚁𝚎𝚜𝚒𝚜𝚝𝚊𝚗𝚌𝚎 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "16":
            SHOW_GRID_LINES = not SHOW_GRID_LINES
            status = '𝙾𝙽' if SHOW_GRID_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚑𝚘𝚠 𝙶𝚛𝚒𝚍 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "17":
            SHOW_PRICE_SCALE = not SHOW_PRICE_SCALE
            status = '𝙾𝙽' if SHOW_PRICE_SCALE else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚑𝚘𝚠 𝙿𝚛𝚒𝚌𝚎 𝚂𝚌𝚊𝚕𝚎 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "18":
            TREND_LINES = not TREND_LINES
            status = '𝙾𝙽' if TREND_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚃𝚛𝚎𝚗𝚍 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "19":
            try:
                transparency = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚋𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚝𝚛𝚊𝚗𝚜𝚙𝚊𝚛𝚎𝚗𝚌𝚢 (𝟶-𝟷𝟶𝟶)% (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {BACKGROUND_TRANSPARENCY}%): ")))
                if 0 <= transparency <= 100:
                    BACKGROUND_TRANSPARENCY = transparency
                    print(rainbow_text(f"✅ 𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚃𝚛𝚊𝚗𝚜𝚙𝚊𝚛𝚎𝚗𝚌𝚢 𝚜𝚎𝚝 𝚝𝚘 {transparency}%"))
                else:
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟶 𝚊𝚗𝚍 𝟷𝟶𝟶"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "20":
            try:
                glow = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚌𝚑𝚊𝚛𝚝 𝚝𝚎𝚡𝚝 𝚐𝚕𝚘𝚠 (𝟶-𝟷𝟶𝟶)% (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CHART_TEXT_GLOW}%): ")))
                if 0 <= glow <= 100:
                    CHART_TEXT_GLOW = glow
                    print(rainbow_text(f"✅ 𝙲𝚑𝚊𝚛𝚝 𝚃𝚎𝚡𝚝 𝙶𝚕𝚘𝚠 𝚜𝚎𝚝 𝚝𝚘 {glow}%"))
                else:
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟶 𝚊𝚗𝚍 𝟷𝟶𝟶"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "21":
            WATERMARK_ON = not WATERMARK_ON
            status = '𝙾𝙽' if WATERMARK_ON else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "22":
            new_text = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚠𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔 𝚝𝚎𝚡𝚝 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {WATERMARK_TEXT}): ")).strip()
            if new_text:
                WATERMARK_TEXT = new_text
                print(rainbow_text(f"✅ 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔 𝚃𝚎𝚡𝚝 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘: {WATERMARK_TEXT}"))
            else:
                print(rainbow_text("⚠️ 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔 𝚃𝚎𝚡𝚝 𝚗𝚘𝚛 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "23":
            new_text = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚜𝚒𝚐𝚗𝚊𝚕 𝚑𝚎𝚊𝚍𝚎𝚛 𝚝𝚎𝚡𝚝 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {SIGNAL_HEADER_TEXT}): ")).strip()
            if new_text:
                SIGNAL_HEADER_TEXT = new_text
                print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘: {SIGNAL_HEADER_TEXT}"))
            else:
                print(rainbow_text("⚠️ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝 𝚗𝚘𝚛 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "24":
            new_text = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚌𝚑𝚊𝚛𝚝 𝚑𝚎𝚊𝚍𝚎𝚛 𝚝𝚎𝚡𝚝 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CHART_HEADER_TEXT}): ")).strip()
            if new_text:
                CHART_HEADER_TEXT = new_text
                print(rainbow_text(f"✅ 𝙲𝚑𝚊𝚛𝚝 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘: {CHART_HEADER_TEXT}"))
            else:
                print(rainbow_text("⚠️ 𝙲𝚑𝚊𝚛𝚟 𝙷𝚎𝚊𝚍𝚎𝚛 𝚃𝚎𝚡𝚝 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "25":
            new_token = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗: ")).strip()
            if new_token:
                TELEGRAM_BOT_TOKEN = new_token
                global bot
                bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙱𝚘𝚝 𝚃𝚘𝚔𝚎𝚗 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            else:
                print(rainbow_text("⚠️ 𝚃𝚘𝚔𝚎𝚗 𝚗𝚘𝚛 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "26":
            new_chat_id = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙲𝚑𝚊𝚝 𝙸𝙳 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {TELEGRAM_CHAT_ID}): ")).strip()
            if new_chat_id:
                TELEGRAM_CHAT_ID = new_chat_id
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙲𝚑𝚊𝚝 𝙸𝙳 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            else:
                print(rainbow_text("⚠️ 𝙲𝚑𝚊𝚝 𝙸𝙳 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "27":
            new_username = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚂𝚒𝚐𝚗𝚊𝚕 𝚄𝚜𝚎𝚛𝚗𝚊𝚖𝚎 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {SIGNAL_USERNAME}): ")).strip()
            if new_username:
                SIGNAL_USERNAME = new_username
                print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 𝚄𝚜𝚎𝚛𝚗𝚊𝚖𝚎 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘 {SIGNAL_USERNAME}"))
            else:
                print(rainbow_text("⚠️ 𝚄𝚜𝚎𝚛𝚗𝚊𝚖𝚎 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "28":
            try:
                new_min = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼𝚒𝚗 𝚒𝚗 𝚜𝚎𝚌𝚘𝚗𝚍𝚜 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {SIGNAL_INTERVAL_MIN}): ")))
                if 60 <= new_min <= 1800:  # 1 minute to 30 minutes
                    SIGNAL_INTERVAL_MIN = new_min
                    print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼𝚒𝚗 𝚜𝚎𝚝 𝚝𝚘 {new_min} 𝚜𝚎𝚌𝚘𝚗𝚍𝚜"))
                else:
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟼𝟶 𝚊𝚗𝚍 𝟷𝟾𝟶𝟶"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "29":
            try:
                new_max = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼𝚊𝚡 𝚒𝚗 𝚜𝚎𝚌𝚘𝚣𝚗𝚍𝚜 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {SIGNAL_INTERVAL_MAX}): ")))
                if 60 <= new_max <= 1800 and new_max >= SIGNAL_INTERVAL_MIN:
                    SIGNAL_INTERVAL_MAX = new_max
                    print(rainbow_text(f"✅ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕 𝙼𝚊𝚡 𝚜𝚎𝚝 𝚝𝚘 {new_max} 𝚜𝚎𝚌𝚘𝚗𝚍𝚜"))
                else:
                    print(rainbow_text(f"❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙼𝚞𝚜𝚟 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 {SIGNAL_INTERVAL_MIN} 𝚊𝚗𝚍 𝟷𝟾𝟶𝟶"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "30":
            try:
                new_id = int(input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙸𝙳 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {TELEGRAM_API_ID}): ")))
                TELEGRAM_API_ID = new_id
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙸𝙳 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            except: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝"))
        elif choice == "31":
            new_hash = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙷𝚊𝚜𝚑: ")).strip()
            if new_hash:
                TELEGRAM_API_HASH = new_hash
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙰𝙿𝙸 𝙷𝚊𝚜𝚑 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            else:
                print(rainbow_text("⚠️ 𝙷𝚊𝚜𝚑 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "32":
            new_phone = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙿𝚑𝚘𝚗𝚎 𝙽𝚞𝚖𝚋𝚎𝚛 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {TELEGRAM_PHONE_NUMBER}): ")).strip()
            if new_phone:
                TELEGRAM_PHONE_NUMBER = new_phone
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙿𝚑𝚘𝚗𝚎 𝙽𝚞𝚖𝚋𝚎𝚛 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            else:
                print(rainbow_text("⚠️ 𝙿𝚑𝚘𝚗𝚎 𝚗𝚞𝚖𝚋𝚎𝚛 𝚗𝚘𝚛 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "33":
            new_source = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {TELEGRAM_SOURCE_CHANNEL}): ")).strip()
            if new_source:
                TELEGRAM_SOURCE_CHANNEL = new_source
                print(rainbow_text("✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚑𝚊𝚗𝚗𝚎𝚕 𝚞𝚙𝚍𝚊𝚝𝚎𝚍"))
            else:
                print(rainbow_text("⚠️ 𝚂𝚘𝚞𝚛𝚌𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "34":
            new_targets_str = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚃𝚊𝚛𝚐𝚎𝚝 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜 (𝚌𝚘𝚖𝚖𝚊 𝚜𝚎𝚙𝚊𝚛𝚊𝚝𝚎𝚍) (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {TELEGRAM_TARGET_CHANNELS}): ")).strip()
            if new_targets_str:
                try:
                    new_targets = [int(x.strip()) for x in new_targets_str.split(',')]
                    TELEGRAM_TARGET_CHANNELS = new_targets
                    print(rainbow_text(f"✅ 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝚃𝚊𝚛𝚐𝚎𝚟 𝙲𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝚞𝚙𝚍𝚊𝚟𝚎𝚍 𝚝𝚘 {TELEGRAM_TARGET_CHANNELS}"))
                except:
                    print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚒𝚗𝚙𝚞𝚝. 𝙴𝚗𝚝𝚎𝚛 𝚌𝚘𝚖𝚖𝚊 𝚜𝚎𝚙𝚊𝚛𝚊𝚝𝚎𝚍 𝚌𝚑𝚊𝚗𝚗𝚎𝚕 𝙸𝙳𝚜."))
            else:
                print(rainbow_text("⚠️ 𝚃𝚊𝚛𝚐𝚎𝚟 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 𝚗𝚘𝚝 𝚌𝚑𝚊𝚗𝚐𝚎𝚍."))
        elif choice == "35":
            PREMIUM_EMOJI_MODE = not PREMIUM_EMOJI_MODE
            status = '𝙾𝙽' if PREMIUM_EMOJI_MODE else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝙴𝚖𝚘𝚓𝚒 𝙼𝚘𝚍𝚎 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "36":
            PREMIUM_EMOJI_TARGET = not PREMIUM_EMOJI_TARGET
            status = '𝙾𝙽' if PREMIUM_EMOJI_TARGET else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝙴𝚖𝚘𝚓𝚒 𝚃𝚊𝚛𝚐𝚎𝚝 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "37":
            PARABOLIC_SAR_LINES = not PARABOLIC_SAR_LINES
            status = '𝙾𝙽' if PARABOLIC_SAR_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙿𝚊𝚛𝚊𝚋𝚘𝚕𝚒𝚌 𝚂𝙰𝚁 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "38":
            GAP_DRAWING = not GAP_DRAWING
            status = '𝙾𝙽' if GAP_DRAWING else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙶𝙰𝙿 𝙳𝚛𝚊𝚠𝚒𝚗𝚐 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "39":
            REVERSE_AREA_DRAWING = not REVERSE_AREA_DRAWING
            status = '𝙾𝙽' if REVERSE_AREA_DRAWING else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚁𝚎𝚟𝚎𝚛𝚜𝚎 𝙰𝚛𝚎𝚊 𝙳𝚛𝚊𝚠𝚒𝚗𝚐 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "40":
            ADVANCED_ANALYSIS = not ADVANCED_ANALYSIS
            status = '𝙾𝙽' if ADVANCED_ANALYSIS else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚍 𝙰𝚗𝚊𝚕𝚢𝚜𝚒𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "41":
            new_link = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚗𝚎𝚠 𝙲𝚞𝚜𝚝𝚘𝚖 𝙻𝚒𝚗𝚔 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CUSTOM_LINK}): ")).strip()
            if new_link:
                CUSTOM_LINK = new_link
                print(rainbow_text(f"✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙻𝚒𝚗𝚔 𝚞𝚙𝚍𝚊𝚝𝚎𝚍 𝚝𝚘: {CUSTOM_LINK}"))
            else:
                CUSTOM_LINK = ""
                print(rainbow_text("✅ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙻𝚒𝚗𝚔 𝚌𝚕𝚎𝚊𝚛𝚎𝚍"))
        elif choice == "42":
            FVG_GAP_DRAW = not FVG_GAP_DRAW
            status = '𝙾𝙽' if FVG_GAP_DRAW else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙵𝚅𝙶 𝙶𝚊𝚙 𝙳𝚛𝚊𝚠 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "43":
            BOT_ALERT_ON = not BOT_ALERT_ON
            status = '𝙾𝙽' if BOT_ALERT_ON else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙱𝚘𝚝 𝙾𝙽/𝙾𝙵𝙵 𝙰𝚕𝚎𝚛𝚝 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "44":
            try:
                color_input = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝚄𝚙 𝙲𝚊𝚗𝚍𝚕𝚎 𝙲𝚘𝚕𝚘𝚛 𝚊𝚜 𝚁,𝙶,𝙱 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CANDLE_UP_COLOR}): ")).strip()
                if color_input:
                    r, g, b = map(int, color_input.split(','))
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        CANDLE_UP_COLOR = (r, g, b)
                        print(rainbow_text(f"✅ 𝚄𝚙 𝙲𝚊𝚗𝚍𝚕𝚎 𝙲𝚘𝚕𝚘𝚛 𝚜𝚎𝚝 𝚝𝚘 RGB({r},{g},{b})"))
                    else:
                        print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚌𝚘𝚕𝚘𝚛 𝚟𝚊𝚕𝚞𝚎𝚜. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟶 𝚊𝚗𝚍 𝟸𝟻𝟻"))
            except:
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚏𝚘𝚛𝚖𝚊𝚝. 𝚄𝚜𝚎 𝚏𝚘𝚛𝚖𝚊𝚝: 𝚁,𝙶,𝙱"))
        elif choice == "45":
            try:
                color_input = input(fancy_font(f"𝙴𝚗𝚝𝚎𝚛 𝙳𝚘𝚠𝚗 𝙲𝚊𝚗𝚍𝚕𝚎 𝙲𝚘𝚕𝚘𝚛 𝚊𝚜 𝚁,𝙶,𝙱 (𝙲𝚞𝚛𝚛𝚎𝚗𝚝: {CANDLE_DOWN_COLOR}): ")).strip()
                if color_input:
                    r, g, b = map(int, color_input.split(','))
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        CANDLE_DOWN_COLOR = (r, g, b)
                        print(rainbow_text(f"✅ 𝙳𝚘𝚠𝚗 𝙲𝚊𝚗𝚍𝚕𝚎 𝙲𝚘𝚕𝚘𝚛 𝚜𝚎𝚝 𝚝𝚘 RGB({r},{g},{b})"))
                    else:
                        print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚌𝚘𝚕𝚘𝚛 𝚟𝚊𝚕𝚞𝚎𝚜. 𝙼𝚞𝚜𝚝 𝚋𝚎 𝚋𝚎𝚝𝚠𝚎𝚎𝚗 𝟶 𝚊𝚗𝚍 𝟸𝟻𝟻"))
            except:
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚏𝚘𝚛𝚖𝚊𝚝. 𝚄𝚜𝚎 𝚏𝚘𝚛𝚖𝚊𝚝: 𝚁,𝙶,𝙱"))
        elif choice == "46":
            EMA_LINE_CHART = not EMA_LINE_CHART
            status = '𝙾𝙽' if EMA_LINE_CHART else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝙴𝙼𝙰 𝙻𝚒𝚗𝚎 𝙲𝚑𝚊𝚛𝚝 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "47":
            SUPERTREND_CHART = not SUPERTREND_CHART
            status = '𝙾𝙽' if SUPERTREND_CHART else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝙲𝚑𝚊𝚛𝚝 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "48":
            SUPERTREND_STRATEGY = not SUPERTREND_STRATEGY
            status = '𝙾𝙽' if SUPERTREND_STRATEGY else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "49":
            SNR_LINES = not SNR_LINES
            status = '𝙾𝙽' if SNR_LINES else '𝙾𝙵𝙵'
            print(rainbow_text(f"✅ 𝚂𝙽𝚁 𝙻𝚒𝚗𝚎𝚜 𝚒𝚜 𝚗𝚘𝚠 {status}"))
        elif choice == "50":
            send_partial_results()
            print(rainbow_text("✅ 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚜𝚎𝚗𝚝"))
        elif choice == "51":
            # --- PARTIAL RESET লজিক ---
            confirm = input(rainbow_text("⚠️ 𝙰𝚛𝚎 𝚢𝚘𝚞 𝚜𝚞𝚛𝚎 𝚢𝚘𝚞 𝚠𝚊𝚗𝚝 𝚝𝚘 𝚛𝚎𝚜𝚎𝚝 𝙰𝙻𝙻 𝚘𝚏 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜? (𝚢𝚎𝚜/𝚗𝚘): ")).lower()
            if confirm == 'yes':
                global trade_results
                today_date_str = datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()
                
                # আজকের রেজাল্টগুলো বাদ দিয়ে বাকিগুলো রাখা হবে
                trade_results = [r for r in trade_results if r.get('date') != today_date_str]
                
                save_trade_results()
                print(rainbow_text("✅ 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚑𝚊𝚟𝚎 𝚋𝚎𝚎𝚗 𝚛𝚎𝚜𝚎𝚝."))
            else:
                print(rainbow_text("⚠️ 𝚁𝚎𝚜𝚎𝚝 𝚌𝚊𝚗𝚌𝚎𝚕𝚕𝚎𝚍."))
        elif choice == "52":
            save_trade_results()
            print(rainbow_text("✅ 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝚊𝚗𝚍 𝚝𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚜𝚊𝚟𝚎𝚍"))
        elif choice == "53":
            clear_screen()
            break
        else:
            print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚘𝚙𝚝𝚒𝚘𝚗"))
        
        input(rainbow_text("\n𝙿𝚛𝚎𝚜𝚜 𝙴𝚗𝚝𝚎𝚛 𝚝𝚘 𝚌𝚘𝚗𝚝𝚒𝚗𝚞𝚎..."))
        clear_screen()

# ================= প্রধান মেনু (RAINBOW UI) =================


# Signal handling for graceful shutdown on Linux/Termux
import signal

def signal_handler(sig, frame):
    print("\n🛑 Signal received, shutting down gracefully...")
    global bot_running
    bot_running = False
    save_trade_results()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main_menu():
    # প্রথমে ডিভাইস ভেরিফিকেশন চেক
    clear_screen()
    print("\n" + "="*60)
    print(rainbow_text("🤖 TRADEIQDEV TRADER 𝐱 𝐀𝙸 𝐁𝐎𝐓"))
    print("="*60)
    
        # Device verification DISABLED - runs on any device
    print(rainbow_text("="*60))
    print(rainbow_text("✅ 𝐀𝐂𝐂𝐄𝐒𝐒 𝐆𝐑𝐀𝐍𝐓𝐄𝐃"))
    print(rainbow_text("👤 𝚆𝚎𝚕𝚌𝚘𝚖𝚎 𝚝𝚘 TRADEIQDEV TRADER"))
    print(rainbow_text("="*60))

    time.sleep(1)

    load_trade_results()

    while True:
        try:
            clear_screen()
            print("\n" + "="*60)
            print(rainbow_text("🤖 TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝙿𝚛𝚘𝚏𝚎𝚜𝚜𝚒𝚘𝚗𝚊𝚕 𝚃𝚛𝚊𝚍𝚒𝚗𝚐 𝚂𝚢𝚜𝚝𝚎𝚖"))
            print("="*60)

            # Only confirmed trades count for stats
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(pytz.timezone('Asia/Dhaka')).date().isoformat()]
            today_stats = get_statistics(today_trades)

            # রেইনবো কালারে স্ট্যাটিস্টিক্স
            colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
            
            stats = [
                f"📊 𝚃𝚘𝚝𝚊𝚕 𝚂𝚒𝚐𝚗𝚊𝚕𝚜 (𝙲𝚘𝚗𝚏𝚒𝚛𝚖𝚎𝚍): {len(confirmed_trades)}",
                f"📈 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚃𝚛𝚊𝚍𝚎𝚜 (𝙲𝚘𝚗𝚏𝚒𝚛𝚖𝚎𝚍): {today_stats['total_trades']}",
                f"✅ 𝚃𝚘𝚍𝚊𝚢'𝚜 𝚆𝚒𝚗𝚜: {today_stats['wins']}",
                f"❌ 𝚃𝚘𝚍𝚊𝚢'𝚜 𝙻𝚘𝚜𝚜𝚎𝚜: {today_stats['losses']}",
                f"📊 𝚃𝚘𝚍𝚊𝚢'𝚜 𝙰𝚌𝚌𝚞𝚛𝚊𝚌𝚢: {today_stats['accuracy']}%",
                f"⚙️ 𝙼𝚊𝚛𝚝𝚒𝚗𝚐𝚊𝚕𝚎: {MARTINGALE_STEPS} 𝚜𝚝𝚎𝚙(𝚜)",
                f"🖼️ 𝙿𝚑𝚘𝚝𝚘 𝚂𝚎𝚗𝚍: {'𝙼𝚊𝚛𝚔𝚎𝚝 𝙲𝚑𝚊𝚛𝚝' if SEND_PHOTO_WITH_SIGNAL else '𝚃𝚎𝚡𝚝 𝙾𝚗𝚕𝚢'}",
                f"🌐 𝙿𝚊𝚒𝚛 𝙼𝚘𝚍𝚎: {'𝙲𝚄𝚂𝚃𝙾𝙼 𝙿𝙰𝙸𝚁𝚂 𝙾𝙽𝙻𝚈' if CUSTOM_PAIRS_MODE else ('𝙰𝙻𝙻 𝙿𝙰𝙸𝚁𝚂' if ANALYZE_ALL_PAIRS else '𝙴𝚇𝙲𝙻𝚄𝙳𝙴 𝙾𝚃𝙲 𝙻𝙸𝚂𝚃')}",
                f"🎯 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢: {CURRENT_STRATEGY}",
                f"🌀 𝙿𝚊𝚛𝚊𝚋𝚘𝚕𝚒𝚌 𝚂𝙰𝚁: {'𝙾𝙽' if PARABOLIC_SAR_LINES else '𝙾𝙵𝙵'}",
                f"📊 𝙶𝙰𝙿 𝙳𝚛𝚊𝚠𝚒𝚗𝚐: {'𝙾𝙽' if GAP_DRAWING else '𝙾𝙵𝙵'}",
                f"🌀 𝙵𝚅𝙶 𝙶𝚊𝚙 𝙳𝚛𝚊𝚠: {'𝙾𝙽' if FVG_GAP_DRAW else '𝙾𝙵𝙵'}",
                f"🔄 𝚁𝚎𝚟𝚎𝚛𝚜𝚎 𝙰𝚛𝚎𝚊: {'𝙾𝙽' if REVERSE_AREA_DRAWING else '𝙾𝙵𝙵'}",
                f"📈 𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚍 𝙰𝚗𝚊𝚕𝚢𝚜𝚒𝚜: {'𝙾𝙽' if ADVANCED_ANALYSIS else '𝙾𝙵𝙵'}",
                f"🎨 𝙲𝚞𝚜𝚝𝚘𝚖 𝙲𝚊𝚗𝚍𝚕𝚎 𝙲𝚘𝚕𝚘𝚛𝚜: {'𝙾𝙽' if CANDLE_UP_COLOR != (0, 200, 0) or CANDLE_DOWN_COLOR != (255, 50, 50) else '𝙾𝙵𝙵'}",
                f"📈 𝙴𝙼𝙰 𝙻𝚒𝚗𝚎 𝙲𝚑𝚊𝚛𝚝: {'𝙾𝙽' if EMA_LINE_CHART else '𝙾𝙵𝙵'}",
                f"📊 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝙲𝚑𝚊𝚛𝚝: {'𝙾𝙽' if SUPERTREND_CHART else '𝙾𝙵𝙵'}",
                f"🎯 𝚂𝚞𝚙𝚎𝚛𝚝𝚛𝚎𝚗𝚍 𝚂𝚝𝚛𝚊𝚝𝚎𝚐𝚢: {'𝙾𝙽' if SUPERTREND_STRATEGY else '𝙾𝙵𝙵'}",
                f"📐 𝚂𝙽𝚁 𝙻𝚒𝚗𝚎𝚜: {'𝙾𝙽' if SNR_LINES else '𝙾𝙵𝙵'}",
                f"🔔 𝙱𝚘𝚝 𝙰𝚕𝚎𝚛𝚝: {'𝙾𝙽' if BOT_ALERT_ON else '𝙾𝙵𝙵'}",
                f"🔗 𝙲𝚞𝚜𝚝𝚘𝚖 𝙻𝚒𝚗𝚔: {'𝚂𝙴𝚃' if CUSTOM_LINK else '𝙽𝙾𝚃 𝚂𝙴𝚃'}",
                f"📱 𝚃𝚎𝚕𝚎𝚐𝚛𝚊𝚖 𝙼𝚘𝚍𝚎: {'𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝙴𝚖𝚘𝚓𝚒' if PREMIUM_EMOJI_MODE else '𝚁𝚎𝚐𝚞𝚕𝚊𝚛'}",
                f"🎯 𝙿𝚛𝚎𝚖𝚒𝚞𝚖 𝚃𝚊𝚛𝚐𝚎𝚝: {'𝙾𝙽' if PREMIUM_EMOJI_TARGET else '𝙾𝙵𝙵'}",
                f"⏱️ 𝚂𝚒𝚐𝚗𝚊𝚕 𝙸𝚗𝚝𝚎𝚛𝚟𝚊𝚕: {SIGNAL_INTERVAL_MIN//60}-{SIGNAL_INTERVAL_MAX//60} 𝚖𝚒𝚗𝚜",
                f"📈 𝚃𝚛𝚎𝚗𝚍 𝙻𝚒𝚗𝚎𝚜: {'𝙾𝙽' if TREND_LINES else '𝙾𝙵𝙵'}",
                f"🎨 𝙱𝚊𝚌𝚔𝚐𝚛𝚘𝚞𝚗𝚍 𝚃𝚛𝚊𝚗𝚜𝚙𝚊𝚛𝚎𝚗𝚌𝚢: {BACKGROUND_TRANSPARENCY}%",
                f"✨ 𝙲𝚑𝚊𝚛𝚝 𝚃𝚎𝚡𝚝 𝙶𝚕𝚘𝚠: {CHART_TEXT_GLOW}%",
                f"💧 𝚆𝚊𝚝𝚎𝚛𝚖𝚊𝚛𝚔: {'𝙾𝙽' if WATERMARK_ON else '𝙾??𝙵'}",
                f"📝 𝚂𝚒𝚐𝚗𝚊𝚕 𝙷𝚎𝚊𝚍𝚎𝚛: {SIGNAL_HEADER_TEXT[:20]}..."
            ]
            
            for i, stat in enumerate(stats):
                color = colors[i % len(colors)]
                print(color + fancy_font(stat))
            
            print("="*60)

            # রেইনবো কালারে মেনু অপশন
            menu_options = []
            if not bot_running: 
                menu_options.append(f"𝟷. ▶️ 𝚂𝚝𝚊𝚛𝚝 𝙱𝚘𝚝")
            
            menu_options.extend([
                f"𝟸. 📊 𝚂𝚎𝚗𝚍 𝙼𝚊𝚗𝚞𝚊𝚕 𝚃𝚛𝚊𝚍𝚎 𝚁𝚎𝚜𝚞𝚕𝚝",
                f"𝟹. 📈 𝚂𝚑𝚘𝚠 𝙿𝚊𝚛𝚝𝚒𝚊𝚕 𝚁𝚎𝚜𝚞𝚕𝚝𝚜",
                f"𝟺. ⚙️ 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜"
            ])
            
            if bot_running: 
                menu_options.append(f"𝟻. ⏹️ 𝚂𝚝𝚘𝚙 𝙱𝚘𝚝")
            
            menu_options.append(f"𝟼. 🚪 𝙴𝚡𝚒𝚝")
            
            for i, option in enumerate(menu_options):
                color = colors[i % len(colors)]
                print(color + fancy_font(option))
            
            print("="*60)

            choice = input(rainbow_text("𝙲𝚑𝚘𝚘𝚜𝚎 𝚘𝚙𝚝𝚒𝚘𝚗: ")).strip()

            if choice == "1" and not bot_running: 
                start_bot()
            elif choice == "2": 
                send_manual_result()
            elif choice == "3": 
                show_partial_results()
            elif choice == "4": 
                settings_menu()
            elif choice == "5" and bot_running: 
                stop_bot()
            elif choice == "6": 
                stop_bot()
                save_trade_results()
                print(rainbow_text("👋 𝙶𝚘𝚘𝚍𝚋𝚢𝚎! 𝚃𝚛𝚊𝚍𝚎 𝚛𝚎𝚜𝚞𝚕𝚝𝚜 𝚜𝚊𝚟𝚎𝚍 𝚝𝚘 TRADEIQDEV.𝚓𝚜𝚘𝚗"))
                break
            else: 
                print(rainbow_text("❌ 𝙸𝚗𝚟𝚊𝚕𝚒𝚍 𝚘𝚙𝚝𝚒𝚘𝚗"))
            
            input(rainbow_text("\n𝙿𝚛𝚎𝚜𝚜 𝙴𝚗𝚝𝚎𝚛 𝚝𝚘 𝚌𝚘𝚗𝚝𝚒𝚗𝚞𝚎..."))
            
        except EOFError: 
            stop_bot()
            save_trade_results()
            break
        except KeyboardInterrupt: 
            stop_bot()
            save_trade_results()
            break
        except Exception as e: 
            print(rainbow_text(f"𝙴𝚛𝚛𝚘𝚛 𝚒𝚗 𝚖𝚎𝚗𝚞: {e}"))
            continue

if __name__ == "__main__":
    try:
        # UTF-8 encoding সেট করুন
        if sys.platform == "win32":
            os.system("chcp 65001 > nul")
        else:
            # Unix/Linux/Termux - ensure UTF-8 locale
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['LC_ALL'] = 'C.UTF-8' 
        
        # Clear screen
        clear_screen()
        
        # Display welcome banner
        print(rainbow_text("="*70))
        print(rainbow_text("     🤖 TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝙿𝚛𝚘𝚏𝚎𝚜𝚜𝚒𝚘𝚗𝚊𝚕 𝚃𝚛𝚊𝚍𝚒𝚗𝚐 𝚂𝚢𝚜𝚝𝚎𝚖"))
        print(rainbow_text("              𝚅𝚎𝚛𝚜𝚒𝚘𝚗 𝟾.𝟶 - 𝙲𝚘𝚖𝚙𝚕𝚎𝚝𝚎 𝙵𝚎𝚊𝚝𝚞𝚛𝚎𝚜 𝚄𝚙𝚍𝚊𝚝𝚎"))
        print(rainbow_text("="*70))
        print(rainbow_text("📱 𝙳𝚎𝚟𝚒𝚌𝚎 𝚅𝚎𝚛𝚒𝚏𝚒𝚌𝚊𝚝𝚒𝚘𝚗 𝚒𝚗 𝚙𝚛𝚘𝚐𝚛𝚎𝚜𝚜..."))
        
        main_menu()
    except Exception as e:
        print(rainbow_text(f"𝙰 𝚌𝚛𝚒𝚝𝚒𝚌𝚊𝚕 𝚎𝚛𝚛𝚘𝚛 𝚘𝚌𝚌𝚞𝚛𝚛𝚎𝚍: {e}"))
        import traceback
        traceback.print_exc()
