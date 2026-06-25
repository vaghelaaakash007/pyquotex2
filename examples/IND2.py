#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADEIQDEV x AI BOT - Professional Trading System
Termux / Kali Linux Compatible Version
Time Zone: INDIA STANDARD TIME GMT+5:30
"""

import os
import sys

# Termux/Kali compatibility fixes
if os.name == 'posix':
    os.environ['TERM'] = os.environ.get('TERM', 'xterm-256color')
    if 'TERMUX_VERSION' in os.environ:
        os.system('termux-wake-lock 2>/dev/null || true')

# Suppress PIL warnings
import warnings
warnings.filterwarnings('ignore')

import ssl
import asyncio
import logging
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

# --- নতুন লাইব্রেরি ---
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import telegram
from telegram import constants
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageEntityCustomEmoji,
    MessageMediaPhoto,
    MessageMediaDocument,
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize colorama
init(autoreset=True)

# ================= JSONBin কনফিগারেশন (optional) =================
JSONBIN_URL = ""
JSONBIN_API_KEY = ""

# ================= ডিভাইস ভেরিফিকেশন (disabled – runs on any device) =================
def get_device_id():
    try:
        hostname = socket.gethostname()
        username = os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USER', 'unknown')
        device_string = f"{hostname}_{username}_{sys.platform}"
        hash_obj = hashlib.sha256(device_string.encode())
        device_id = f"DEV-{hash_obj.hexdigest()[:16].upper()}"
        return device_id
    except:
        return f"DEV-{str(uuid.uuid4())[:16].upper()}"

def check_device_access():
    # Always grant access
    device_id = get_device_id()
    return True, device_id, "User"

# ================= কনফিগারেশন =================
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

ANALYZE_ALL_PAIRS = False

TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = "-"
SIGNAL_USERNAME = "@Tradeiqdev"
SEND_PHOTO_WITH_SIGNAL = False
CHART_BACKGROUND_IMAGE_PATH = ""

TELEGRAM_API_ID = 0
TELEGRAM_API_HASH = ''
TELEGRAM_PHONE_NUMBER = ''
TELEGRAM_SOURCE_CHANNEL = ""
TELEGRAM_TARGET_CHANNELS = []
PREMIUM_EMOJI_MODE = False
PREMIUM_EMOJI_TARGET = True

SIGNAL_INTERVAL_MIN = 180
SIGNAL_INTERVAL_MAX = 300
def get_next_signal_interval():
    return random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)

TIMEFRAME = 60
CANDLE_FETCH_ATTEMPTS = 3
MAX_CANDLES = 30
MARTINGALE_STEPS = 1
PARTIAL_RESULTS_INTERVAL = 300
SAVE_FILE = "TRADEIQDEV-ss.json"

CUSTOM_PAIRS_MODE = False
CUSTOM_PAIRS_LIST = ["BRLUSD_otc", "USDPKR_otc"]

EMA_PERIOD = 10
RSI_PERIOD = 14
CURRENT_STRATEGY = "EMA_RSI"
MARK_RESULT_CANDLE = False
MIN_SIGNAL_SCORE = 4
AVAILABLE_STRATEGIES = ["EMA_RSI", "Trend", "Bollinger", "Support_Resistance", "Trend_Reverse", "Price_Action", "Supertrend", "FVG_Strategy"]

SUPPORT_RESISTANCE_LINES = False
MOVING_AVERAGE_LINES = False
SUPPORT_RESISTANCE_STRATEGY = False
SHOW_GRID_LINES = True
SHOW_PRICE_SCALE = True
TREND_LINES = False
BACKGROUND_TRANSPARENCY = 50
CHART_TEXT_GLOW = 0
WATERMARK_ON = True
WATERMARK_TEXT = "TRADEIQDEV x AI BOT - TRADEIQDEV TRADER SS PRO"
SIGNAL_HEADER_TEXT = "TRADEIQDEV x AI BOT"
CHART_HEADER_TEXT = "TRADEIQDEV x AI BOT - TRADEIQDEV TRADER SS PRO SIGNAL"

PARABOLIC_SAR_LINES = False
GAP_DRAWING = False
REVERSE_AREA_DRAWING = False
ADVANCED_ANALYSIS = False
CUSTOM_LINK = ""
FVG_GAP_DRAW = False
BOT_ALERT_ON = True
CANDLE_UP_COLOR = (0, 200, 0)
CANDLE_DOWN_COLOR = (255, 50, 50)
EMA_LINE_CHART = False
SUPERTREND_CHART = False
SUPERTREND_STRATEGY = False
SNR_LINES = False

bot_running = False
last_signal_time = 0
trade_results = []
signal_count = 0
signal_queue = deque()
signal_executor = None
current_signal_task = None
last_partial_results_time = 0
start_time = None
next_signal_interval = get_next_signal_interval()
continuous_analysis = True

PAIR_NAMES = {
    "BRLUSD_otc": "BRL/USD", "USDPKR_otc": "USD/PKR", "USDMXN_otc": "USD/MXN",
    "USDARS_otc": "USD/ARS", "USDBDT_otc": "USD/BDT", "USDCOP_otc": "USD/COP",
    "USDINR_otc": "USD/INR", "USDPHP_otc": "USD/PHP", "USDDZD_otc": "USD/DZD",
    "USDIDR_otc": "USD/IDR", "USDNGN_otc": "USD/NGN", "USDTRY_otc": "USD/TRY",
    "USDZAR_otc": "USD/ZAR", "USDEGP_otc": "USD/EGP", "CADCHF_otc": "CAD/CHF"
}

class BangladeshSSLAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount('https://', BangladeshSSLAdapter())
session.verify = False

bot = None
def get_bot():
    global bot
    if bot is None and TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN.strip():
        try:
            bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        except Exception as e:
            print(f"⚠️ Telegram bot init failed: {e}")
            bot = None
    return bot

# ================= Time Zone: INDIA STANDARD TIME GMT+5:30 =================
IST = pytz.timezone('Asia/Kolkata')

def ts_to_dt(ts):
    """Convert timestamp to IST (GMT+5:30) datetime"""
    if ts is None: return None
    try:
        ts = int(ts)
        if ts > 1_000_000_000_000: ts = ts / 1000
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt_utc.astimezone(IST)
    except:
        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(IST)
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

async def telegram_client_task():
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
                if PREMIUM_EMOJI_TARGET:
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telegram_client_task())

def rainbow_text(text):
    return str(text)

def rainbow_line(text):
    return str(text)

def fancy_font(text):
    return str(text)

# ================= Data Management =================
def load_trade_results():
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
                    PARABOLIC_SAR_LINES = settings.get('PARABOLIC_SAR_LINES', PARABOLIC_SAR_LINES)
                    GAP_DRAWING = settings.get('GAP_DRAWING', GAP_DRAWING)
                    REVERSE_AREA_DRAWING = settings.get('REVERSE_AREA_DRAWING', REVERSE_AREA_DRAWING)
                    ADVANCED_ANALYSIS = settings.get('ADVANCED_ANALYSIS', ADVANCED_ANALYSIS)
                    CUSTOM_LINK = settings.get('CUSTOM_LINK', CUSTOM_LINK)
                    FVG_GAP_DRAW = settings.get('FVG_GAP_DRAW', FVG_GAP_DRAW)
                    BOT_ALERT_ON = settings.get('BOT_ALERT_ON', BOT_ALERT_ON)
                    candle_up_color = settings.get('CANDLE_UP_COLOR', CANDLE_UP_COLOR)
                    candle_down_color = settings.get('CANDLE_DOWN_COLOR', CANDLE_DOWN_COLOR)
                    if isinstance(candle_up_color, list) and len(candle_up_color) == 3:
                        CANDLE_UP_COLOR = tuple(candle_up_color)
                    if isinstance(candle_down_color, list) and len(candle_down_color) == 3:
                        CANDLE_DOWN_COLOR = tuple(candle_down_color)
                    EMA_LINE_CHART = settings.get('EMA_LINE_CHART', EMA_LINE_CHART)
                    SUPERTREND_CHART = settings.get('SUPERTREND_CHART', SUPERTREND_CHART)
                    SUPERTREND_STRATEGY = settings.get('SUPERTREND_STRATEGY', SUPERTREND_STRATEGY)
                    SNR_LINES = settings.get('SNR_LINES', SNR_LINES)
                    TELEGRAM_BOT_TOKEN = settings.get('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN)
                    TELEGRAM_CHAT_ID = settings.get('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
                    SIGNAL_USERNAME = settings.get('SIGNAL_USERNAME', SIGNAL_USERNAME)
                    SIGNAL_INTERVAL_MIN = settings.get('SIGNAL_INTERVAL_MIN', SIGNAL_INTERVAL_MIN)
                    SIGNAL_INTERVAL_MAX = settings.get('SIGNAL_INTERVAL_MAX', SIGNAL_INTERVAL_MAX)
                    TELEGRAM_API_ID = settings.get('TELEGRAM_API_ID', TELEGRAM_API_ID)
                    TELEGRAM_API_HASH = settings.get('TELEGRAM_API_HASH', TELEGRAM_API_HASH)
                    TELEGRAM_PHONE_NUMBER = settings.get('TELEGRAM_PHONE_NUMBER', TELEGRAM_PHONE_NUMBER)
                    TELEGRAM_SOURCE_CHANNEL = settings.get('TELEGRAM_SOURCE_CHANNEL', TELEGRAM_SOURCE_CHANNEL)
                    TELEGRAM_TARGET_CHANNELS = settings.get('TELEGRAM_TARGET_CHANNELS', TELEGRAM_TARGET_CHANNELS)
                    PREMIUM_EMOJI_MODE = settings.get('PREMIUM_EMOJI_MODE', PREMIUM_EMOJI_MODE)
                    PREMIUM_EMOJI_TARGET = settings.get('PREMIUM_EMOJI_TARGET', PREMIUM_EMOJI_TARGET)
                else:
                    trade_results = []
            print(rainbow_text(f"✅ Loaded {len(trade_results)} trade results and settings from {SAVE_FILE}"))
            return True
        else:
            print(rainbow_text(f"⚠ No data file found. Starting fresh..."))
            trade_results = []
            return False
    except Exception as e:
        print(rainbow_text(f"Error loading trade results: {e}"))
        trade_results = []
        return False

def save_trade_results():
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
                "CUSTOM_PAIRS_MODE": CUSTOM_PAIRS_MODE,
                "CUSTOM_PAIRS_LIST": CUSTOM_PAIRS_LIST,
                "EMA_PERIOD": EMA_PERIOD,
                "RSI_PERIOD": RSI_PERIOD,
                "CURRENT_STRATEGY": CURRENT_STRATEGY,
                "MARK_RESULT_CANDLE": MARK_RESULT_CANDLE,
                "MIN_SIGNAL_SCORE": MIN_SIGNAL_SCORE,
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
                "PARABOLIC_SAR_LINES": PARABOLIC_SAR_LINES,
                "GAP_DRAWING": GAP_DRAWING,
                "REVERSE_AREA_DRAWING": REVERSE_AREA_DRAWING,
                "ADVANCED_ANALYSIS": ADVANCED_ANALYSIS,
                "CUSTOM_LINK": CUSTOM_LINK,
                "FVG_GAP_DRAW": FVG_GAP_DRAW,
                "BOT_ALERT_ON": BOT_ALERT_ON,
                "CANDLE_UP_COLOR": list(CANDLE_UP_COLOR),
                "CANDLE_DOWN_COLOR": list(CANDLE_DOWN_COLOR),
                "EMA_LINE_CHART": EMA_LINE_CHART,
                "SUPERTREND_CHART": SUPERTREND_CHART,
                "SUPERTREND_STRATEGY": SUPERTREND_STRATEGY,
                "SNR_LINES": SNR_LINES,
                "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
                "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
                "SIGNAL_USERNAME": SIGNAL_USERNAME,
                "SIGNAL_INTERVAL_MIN": SIGNAL_INTERVAL_MIN,
                "SIGNAL_INTERVAL_MAX": SIGNAL_INTERVAL_MAX,
                "TELEGRAM_API_ID": TELEGRAM_API_ID,
                "TELEGRAM_API_HASH": TELEGRAM_API_HASH,
                "TELEGRAM_PHONE_NUMBER": TELEGRAM_PHONE_NUMBER,
                "TELEGRAM_SOURCE_CHANNEL": TELEGRAM_SOURCE_CHANNEL,
                "TELEGRAM_TARGET_CHANNELS": TELEGRAM_TARGET_CHANNELS,
                "PREMIUM_EMOJI_MODE": PREMIUM_EMOJI_MODE,
                "PREMIUM_EMOJI_TARGET": PREMIUM_EMOJI_TARGET
            },
            "last_updated": datetime.now(IST).isoformat(),
            "version": "8.0_Complete_Features_Update"
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        print(rainbow_text(f"✅ Saved {len(trade_results)} trade results and settings to {SAVE_FILE}"))
        return True
    except Exception as e:
        print(rainbow_text(f"Error saving trade results: {e}"))
        return False

def get_today_results():
    today = datetime.now(IST).date()
    today_str = today.isoformat()
    today_results = []
    for result in trade_results:
        if result.get('result') not in ['Profit', 'Loss', 'Break-even']:
            continue
        result_date_str = result.get('date')
        if not result_date_str:
            try:
                if 'timestamp' in result:
                    dt = datetime.fromtimestamp(result['timestamp'], IST)
                    result_date_str = dt.date().isoformat()
                elif 'signal_datetime' in result:
                    dt = datetime.fromisoformat(result['signal_datetime'].replace('Z', '+00:00'))
                    dt = dt.astimezone(IST)
                    result_date_str = dt.date().isoformat()
            except:
                continue
        if result_date_str == today_str:
            today_results.append(result)
    return today_results

def get_statistics(results_list=None):
    if results_list is None:
        results_list = trade_results
    completed_trades = [r for r in results_list if r.get('result') in ['Profit', 'Loss']]
    total = len(completed_trades)
    wins = sum(1 for r in completed_trades if r.get('result') == 'Profit')
    losses = sum(1 for r in completed_trades if r.get('result') == 'Loss')
    accuracy = (wins / total * 100) if total > 0 else 0
    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "accuracy": round(accuracy, 2)
    }

# ================= Telegram Functions =================
async def send_telegram_photo_or_chart(caption, pair=None, candles=None, result=None):
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH
    try:
        if SEND_PHOTO_WITH_SIGNAL and pair and candles:
            image_buffer = create_chart_image(pair, candles, result=result)
            if not image_buffer:
                print(rainbow_text("❌ Chart image creation failed. Sending as text message."))
                return send_telegram_message(caption)
            print(rainbow_text(f"📸 Sending chart for {pair} to Telegram..."))
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
            print(rainbow_text(f"📸 Sending text message to Telegram..."))
            return send_telegram_message(caption)
    except Exception as e:
        print(rainbow_text(f"❌ Failed to send Telegram photo/chart: {e}"))
        return send_telegram_message(caption)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.strip() == "":
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
        print(rainbow_text(f"Failed to send Telegram message: {e}"))
        try:
            alt_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            response = requests.post(alt_url, data=payload, timeout=15, verify=False)
            return response.status_code == 200
        except:
            return False

# ================= Technical Indicators =================
def calculate_parabolic_sar(candles, acceleration=0.02, maximum=0.2):
    if len(candles) < 5:
        return []
    sar_values = []
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    uptrend = True
    sar = low[0]
    ep = high[0]
    af = acceleration
    for i in range(len(candles)):
        sar_values.append(sar)
        if uptrend:
            if low[i] < sar:
                uptrend = False
                sar = ep
                ep = low[i]
                af = acceleration
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + acceleration, maximum)
                sar = sar + af * (ep - sar)
                if i >= 2:
                    sar = min(sar, low[i-1], low[i-2])
        else:
            if high[i] > sar:
                uptrend = True
                sar = ep
                ep = high[i]
                af = acceleration
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + acceleration, maximum)
                sar = sar + af * (ep - sar)
                if i >= 2:
                    sar = max(sar, high[i-1], high[i-2])
    return sar_values

def calculate_gaps(candles):
    if len(candles) < 2:
        return []
    gaps = []
    for i in range(1, len(candles)):
        prev_close = candles[i-1]['close']
        curr_open = candles[i]['open']
        if curr_open > prev_close * 1.001:
            gaps.append({
                'type': 'GAP_UP',
                'start_price': prev_close,
                'end_price': curr_open,
                'candle_index': i
            })
        elif curr_open < prev_close * 0.999:
            gaps.append({
                'type': 'GAP_DOWN',
                'start_price': prev_close,
                'end_price': curr_open,
                'candle_index': i
            })
    return gaps

def detect_reversal_areas(candles, lookback=10):
    if len(candles) < lookback * 2:
        return []
    reversal_areas = []
    for i in range(lookback, len(candles) - lookback):
        current_high = candles[i]['high']
        current_low = candles[i]['low']
        is_swing_high = True
        for j in range(1, lookback + 1):
            if candles[i-j]['high'] > current_high or candles[i+j]['high'] > current_high:
                is_swing_high = False
                break
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
    if not candle_data or len(candle_data) < 20:
        return None, None, None, None, None
    closes = [c['close'] for c in candle_data]
    ma20 = ema(closes, 20) if len(closes) >= 20 else None
    ma50 = ema(closes, 50) if len(closes) >= 50 else None
    rsi = calculate_rsi(closes, 14)
    macd_line, signal_line, macd_histogram = calculate_macd(closes)
    current_price = closes[-1]
    trend = "SIDEWAYS"
    if ma20 and ma50:
        if current_price > ma20 and ma20 > ma50:
            trend = "UP_TREND"
        elif current_price < ma20 and ma20 < ma50:
            trend = "DOWN_TREND"
    reversal_signal = None
    if trend == "UP_TREND" and rsi > 70:
        reversal_signal = "POTENTIAL_DOWN_REVERSAL"
    elif trend == "DOWN_TREND" and rsi < 30:
        reversal_signal = "POTENTIAL_UP_REVERSAL"
    support, resistance = calculate_support_resistance_levels(closes)
    logic = None
    if reversal_signal == "POTENTIAL_DOWN_REVERSAL":
        logic = "Overbought with RSI > 70 in uptrend"
    elif reversal_signal == "POTENTIAL_UP_REVERSAL":
        logic = "Oversold with RSI < 30 in downtrend"
    return trend, reversal_signal, support, resistance, logic

def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    if len(prices) < slow_period:
        return None, None, None
    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)
    if fast_ema is None or slow_ema is None:
        return None, None, None
    macd_line = fast_ema - slow_ema
    macd_prices = [macd_line]
    signal_line = ema(macd_prices, signal_period)
    macd_histogram = macd_line - signal_line if signal_line else None
    return macd_line, signal_line, macd_histogram

def detect_fvg_gaps(candles, threshold=0.001):
    if len(candles) < 3:
        return []
    fvg_gaps = []
    for i in range(1, len(candles) - 1):
        prev_candle = candles[i-1]
        curr_candle = candles[i]
        next_candle = candles[i+1]
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

def calculate_supertrend(candles, period=10, multiplier=3):
    if len(candles) < period:
        return [], []
    high = [c['high'] for c in candles]
    low = [c['low'] for c in candles]
    close = [c['close'] for c in candles]
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
    supertrend = []
    trend = []
    upper_band = (high[0] + low[0]) / 2 + multiplier * atr[0]
    lower_band = (high[0] + low[0]) / 2 - multiplier * atr[0]
    for i in range(len(candles)):
        if i < period:
            supertrend.append(None)
            trend.append(None)
            continue
        hl2 = (high[i] + low[i]) / 2
        upper_band = hl2 + multiplier * atr[i-period]
        lower_band = hl2 - multiplier * atr[i-period]
        if i == period:
            supertrend.append(upper_band)
            trend.append(1)
        else:
            if close[i] > supertrend[-1]:
                current_trend = 1
                supertrend.append(max(lower_band, supertrend[-1]) if trend[-1] == 1 else lower_band)
            else:
                current_trend = -1
                supertrend.append(min(upper_band, supertrend[-1]) if trend[-1] == -1 else upper_band)
            trend.append(current_trend)
    return supertrend, trend

def detect_price_action_patterns(candles):
    if len(candles) < 5:
        return []
    patterns = []
    for i in range(2, len(candles) - 2):
        if (candles[i-1]['close'] < candles[i-1]['open'] and
            candles[i]['close'] > candles[i]['open'] and
            candles[i]['open'] < candles[i-1]['close'] and
            candles[i]['close'] > candles[i-1]['open']):
            patterns.append({
                'type': 'BULLISH_ENGULFING',
                'candle_index': i,
                'strength': (candles[i]['close'] - candles[i-1]['open']) / candles[i-1]['open']
            })
        elif (candles[i-1]['close'] > candles[i-1]['open'] and
              candles[i]['close'] < candles[i]['open'] and
              candles[i]['open'] > candles[i-1]['close'] and
              candles[i]['close'] < candles[i-1]['open']):
            patterns.append({
                'type': 'BEARISH_ENGULFING',
                'candle_index': i,
                'strength': (candles[i-1]['open'] - candles[i]['close']) / candles[i-1]['open']
            })
        elif (candles[i]['close'] > candles[i]['open'] and
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['close'] - candles[i]['open']) and
              (candles[i]['close'] - candles[i]['low']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):
            patterns.append({
                'type': 'HAMMER',
                'candle_index': i,
                'strength': (candles[i]['close'] - candles[i]['low']) / (candles[i]['high'] - candles[i]['low'])
            })
        elif (candles[i]['close'] < candles[i]['open'] and
              (candles[i]['high'] - candles[i]['low']) > 3 * (candles[i]['open'] - candles[i]['close']) and
              (candles[i]['high'] - candles[i]['open']) > 0.6 * (candles[i]['high'] - candles[i]['low'])):
            patterns.append({
                'type': 'SHOOTING_STAR',
                'candle_index': i,
                'strength': (candles[i]['high'] - candles[i]['open']) / (candles[i]['high'] - candles[i]['low'])
            })
    return patterns

def calculate_snr_levels(prices, num_levels=5):
    if len(prices) < 20:
        return []
    local_highs = []
    local_lows = []
    for i in range(2, len(prices) - 2):
        if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
            prices[i] > prices[i+1] and prices[i] > prices[i+2]):
            local_highs.append(prices[i])
        if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
            prices[i] < prices[i+1] and prices[i] < prices[i+2]):
            local_lows.append(prices[i])
    all_levels = local_highs + local_lows
    all_levels.sort()
    clusters = []
    current_cluster = []
    cluster_threshold = (max(prices) - min(prices)) * 0.01
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
    snr_levels = []
    for cluster in clusters:
        if len(cluster) >= 2:
            avg_level = np.mean(cluster)
            strength = len(cluster)
            snr_levels.append({
                'level': avg_level,
                'strength': strength,
                'type': 'RESISTANCE' if avg_level > np.mean(prices) else 'SUPPORT'
            })
    snr_levels.sort(key=lambda x: x['strength'], reverse=True)
    return snr_levels[:num_levels]

# ================= Chart Generation =================
def load_fonts():
    font_paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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
    return ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

def draw_dashed_line(draw, start, end, color, width=1, dash_length=5):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx**2 + dy**2)
    if length == 0:
        return
    dx /= length
    dy /= length
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
    WIDTH, HEIGHT = 900, 500
    BACKGROUND_COLOR = (0, 0, 0)
    GREEN = CANDLE_UP_COLOR
    RED = CANDLE_DOWN_COLOR
    BLUE = (0, 150, 255)
    YELLOW = (255, 255, 0)
    WHITE = (255, 255, 255)
    GRAY = (100, 100, 100)
    DARK_GRAY = (50, 50, 50)
    LIGHT_BLUE = (100, 200, 255)
    DARK_BLUE = (20, 20, 40)
    SUPPORT_COLOR = (0, 255, 0, 200)
    RESISTANCE_COLOR = (255, 0, 0, 200)
    MA_COLORS = [(255, 255, 0), (0, 255, 255), (255, 0, 255)]
    GRID_COLOR = (30, 30, 30, 150)
    TREND_LINE_COLOR = (255, 165, 0, 255)
    PARABOLIC_SAR_COLOR = (255, 0, 255, 200)
    GAP_COLOR = (255, 255, 0, 100)
    REVERSE_AREA_COLOR = (0, 255, 255, 80)
    FVG_COLOR = (255, 165, 0, 80)
    SUPERTREND_UP_COLOR = (0, 255, 0, 150)
    SUPERTREND_DOWN_COLOR = (255, 0, 0, 150)
    EMA_COLOR = (255, 255, 0, 200)
    SNR_COLOR = (255, 165, 0, 150)
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)
    try:
        if CHART_BACKGROUND_IMAGE_PATH and os.path.exists(CHART_BACKGROUND_IMAGE_PATH):
            bg_img = Image.open(CHART_BACKGROUND_IMAGE_PATH).convert("RGBA")
            bg_img = bg_img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            alpha = BACKGROUND_TRANSPARENCY / 100.0
            bg_img_alpha = bg_img.copy()
            bg_img_alpha.putalpha(int(255 * alpha))
            overlay = Image.new('RGBA', (WIDTH, HEIGHT), BACKGROUND_COLOR + (0,))
            temp_img = Image.alpha_composite(overlay, bg_img_alpha)
            img = Image.alpha_composite(img.convert('RGBA'), temp_img).convert('RGB')
            draw = ImageDraw.Draw(img)
            print(rainbow_text(f"✅ Background image loaded (Transparency: {BACKGROUND_TRANSPARENCY}%)"))
        else:
            print(rainbow_text(f"⚠️ Background image not found. Using solid black background."))
    except Exception as e:
        print(rainbow_text(f"❌ Error loading background image: {e}"))
    font_large, font_medium, font_small, font_tiny = load_fonts()
    header_y = 15
    title_text = f"{CHART_HEADER_TEXT}: "
    title_width = draw.textlength(title_text, font=font_large)
    draw.text((20, header_y), title_text, fill=LIGHT_BLUE, font=font_large)
    latest_signal = "BUY" if candles[-1]['close'] > candles[-1]['open'] else "SELL"
    signal_color = GREEN if latest_signal == "BUY" else RED
    draw.text((20 + title_width, header_y), f"{latest_signal}", fill=signal_color, font=font_large)
    bma_y = 50
    bma_texts = ["BMA 9", "BMA 21", "BMA 30", "3IGNAL"]
    bma_colors = [YELLOW, BLUE, RED, GREEN]
    x_pos = 20
    for text, color in zip(bma_texts, bma_colors):
        draw.text((x_pos, bma_y), text, fill=color, font=font_medium)
        x_pos += draw.textlength(text, font=font_medium) + 20
    draw.text((x_pos, bma_y), "EMA: BULLISH", fill=GREEN, font=font_medium)
    CHART_AREA_LEFT = 100
    CHART_AREA_TOP = 80
    CHART_AREA_WIDTH = WIDTH - CHART_AREA_LEFT - 200
    CHART_AREA_HEIGHT = HEIGHT - CHART_AREA_TOP - 120
    draw.rectangle([CHART_AREA_LEFT, CHART_AREA_TOP,
                    CHART_AREA_LEFT + CHART_AREA_WIDTH,
                    CHART_AREA_TOP + CHART_AREA_HEIGHT],
                   outline=DARK_GRAY, width=2)
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
    if SHOW_PRICE_SCALE:
        price_scale_x = CHART_AREA_LEFT - 80
        price_values = np.linspace(min_price, max_price, 8)
        draw.rectangle([price_scale_x - 5, CHART_AREA_TOP - 5,
                        price_scale_x + 75, CHART_AREA_TOP + CHART_AREA_HEIGHT + 5],
                       fill=DARK_BLUE + (150,), outline=GRAY)
        for i, price in enumerate(price_values):
            y_pos = scale_price_to_y(price)
            draw.line([(price_scale_x + 60, y_pos), (price_scale_x + 70, y_pos)],
                     fill=WHITE, width=1)
            price_str = f"{price:.5f}" if price < 1 else f"{price:.4f}"
            draw.text((price_scale_x, y_pos - 8), price_str, fill=WHITE, font=font_tiny)
    if SNR_LINES:
        closes = [c['close'] for c in candles]
        snr_levels = calculate_snr_levels(closes, num_levels=5)
        for level_data in snr_levels:
            y_snr = scale_price_to_y(level_data['level'])
            color = SUPPORT_COLOR if level_data['type'] == 'SUPPORT' else RESISTANCE_COLOR
            draw.line([(CHART_AREA_LEFT, y_snr), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_snr)],
                     fill=color, width=2)
            label_text = f"{level_data['type'][0]}: {level_data['level']:.5f}"
            draw.text((CHART_AREA_LEFT + 5, y_snr - 15),
                     label_text, fill=color, font=font_tiny)
    if SUPERTREND_CHART:
        supertrend_values, trend_values = calculate_supertrend(candles, period=10, multiplier=3)
        if supertrend_values and trend_values:
            supertrend_points = []
            for i, value in enumerate(supertrend_values):
                if value is not None and i < min(len(candles), 50):
                    x_st = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / min(len(candles), 50))
                    y_st = scale_price_to_y(value)
                    supertrend_points.append((x_st, y_st))
            if len(supertrend_points) > 1:
                for j in range(1, len(supertrend_points)):
                    color = SUPERTREND_UP_COLOR if trend_values[j] == 1 else SUPERTREND_DOWN_COLOR
                    draw.line([supertrend_points[j-1], supertrend_points[j]],
                             fill=color, width=2)
    if EMA_LINE_CHART:
        closes = [c['close'] for c in candles]
        ema_value = ema(closes, EMA_PERIOD)
        if ema_value is not None:
            y_ema = scale_price_to_y(ema_value)
            draw.line([(CHART_AREA_LEFT, y_ema), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_ema)],
                     fill=EMA_COLOR, width=3)
            draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_ema - 15),
                     f"EMA{EMA_PERIOD}", fill=EMA_COLOR, font=font_tiny)
    if FVG_GAP_DRAW:
        fvg_gaps = detect_fvg_gaps(candles)
        for gap in fvg_gaps:
            if gap['candle_index'] < min(len(candles), 50):
                x_fvg = CHART_AREA_LEFT + int(gap['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                y_start = scale_price_to_y(gap['start_price'])
                y_end = scale_price_to_y(gap['end_price'])
                draw.rectangle([x_fvg - 10, min(y_start, y_end),
                               x_fvg + 10, max(y_start, y_end)],
                              fill=FVG_COLOR, outline=YELLOW)
                label_text = "FVG"
                draw.text((x_fvg - 15, (y_start + y_end) // 2 - 10),
                         label_text, fill=YELLOW, font=font_tiny)
    if GAP_DRAWING:
        gaps = calculate_gaps(candles)
        for gap in gaps:
            gap_y_start = scale_price_to_y(gap['start_price'])
            gap_y_end = scale_price_to_y(gap['end_price'])
            if gap['candle_index'] < len(candles):
                x_gap = CHART_AREA_LEFT + int(gap['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                draw.rectangle([x_gap - 5, min(gap_y_start, gap_y_end),
                               x_gap + 5, max(gap_y_start, gap_y_end)],
                              fill=GAP_COLOR, outline=YELLOW)
    if REVERSE_AREA_DRAWING:
        reversal_areas = detect_reversal_areas(candles)
        for area in reversal_areas:
            if area['candle_index'] < len(candles):
                x_rev = CHART_AREA_LEFT + int(area['candle_index'] * CHART_AREA_WIDTH / min(len(candles), 50))
                y_rev = scale_price_to_y(area['price'])
                if area['type'] == 'SWING_HIGH':
                    draw.polygon([(x_rev, y_rev - 10), (x_rev - 8, y_rev), (x_rev + 8, y_rev)],
                                fill=RED, outline=RED)
                elif area['type'] == 'SWING_LOW':
                    draw.polygon([(x_rev, y_rev + 10), (x_rev - 8, y_rev), (x_rev + 8, y_rev)],
                                fill=GREEN, outline=GREEN)
    if PARABOLIC_SAR_LINES:
        sar_values = calculate_parabolic_sar(candles)
        if sar_values and len(sar_values) == len(candles):
            sar_points = []
            for i, sar in enumerate(sar_values):
                if i < min(len(candles), 50):
                    x_sar = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / min(len(candles), 50))
                    y_sar = scale_price_to_y(sar)
                    sar_points.append((x_sar, y_sar))
            for point in sar_points:
                draw.ellipse([point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3],
                           fill=PARABOLIC_SAR_COLOR, outline=WHITE)
    if SUPPORT_RESISTANCE_LINES:
        support, resistance, pivot, r1, s1 = calculate_support_resistance(candles)
        if support and resistance:
            y_support = scale_price_to_y(support)
            draw.line([(CHART_AREA_LEFT, y_support), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_support)],
                     fill=SUPPORT_COLOR, width=3)
            draw.text((CHART_AREA_LEFT + 5, y_support - 20),
                     f"S: {support:.5f}", fill=SUPPORT_COLOR, font=font_small)
            y_resistance = scale_price_to_y(resistance)
            draw.line([(CHART_AREA_LEFT, y_resistance), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_resistance)],
                     fill=RESISTANCE_COLOR, width=3)
            draw.text((CHART_AREA_LEFT + 5, y_resistance + 5),
                     f"R: {resistance:.5f}", fill=RESISTANCE_COLOR, font=font_small)
    if MOVING_AVERAGE_LINES:
        ma_values = calculate_moving_averages(candles, periods=[20, 50, 100, 200])
        for i, (period, ma_value) in enumerate(ma_values.items()):
            if ma_value:
                y_ma = scale_price_to_y(ma_value)
                color = MA_COLORS[i % len(MA_COLORS)]
                draw.line([(CHART_AREA_LEFT, y_ma), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_ma)],
                         fill=color, width=3)
                draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_ma - 15),
                         f"MA{period}", fill=color, font=font_tiny)
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
    if SHOW_GRID_LINES:
        for i in range(6):
            y = CHART_AREA_TOP + int(i * CHART_AREA_HEIGHT / 5)
            draw.line([(CHART_AREA_LEFT, y), (CHART_AREA_LEFT + CHART_AREA_WIDTH, y)],
                     fill=GRID_COLOR, width=1)
        num_v_lines = 10
        for i in range(num_v_lines):
            x = CHART_AREA_LEFT + int(i * CHART_AREA_WIDTH / (num_v_lines - 1))
            draw.line([(x, CHART_AREA_TOP), (x, CHART_AREA_TOP + CHART_AREA_HEIGHT)],
                     fill=GRID_COLOR, width=1)
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
        y_high = scale_price_to_y(candle['high'])
        y_low = scale_price_to_y(candle['low'])
        draw.line([(x_center, y_high), (x_center, y_low)],
                 fill=WHITE, width=1)
        is_bullish = candle['close'] > candle['open']
        body_color = GREEN if is_bullish else RED
        y_open = scale_price_to_y(candle['open'])
        y_close = scale_price_to_y(candle['close'])
        y_top = min(y_open, y_close)
        y_bottom = max(y_open, y_close)
        body_height = max(2, y_bottom - y_top)
        draw.rectangle([x_left + 1, y_top, x_right - 1, y_bottom],
                      fill=body_color, outline=body_color)
        draw.rectangle([x_left, y_top, x_right, y_bottom],
                      outline=body_color, width=1)
        if i == actual_num_candles - 1:
            last_candle_center = (x_center, (y_top + y_bottom) // 2)
    latest_price = candles[-1]['close']
    y_price_line = scale_price_to_y(latest_price)
    draw_dashed_line(draw,
                     (CHART_AREA_LEFT, y_price_line),
                     (CHART_AREA_LEFT + CHART_AREA_WIDTH, y_price_line),
                     color=YELLOW, width=2, dash_length=8)
    draw.rectangle([CHART_AREA_LEFT + CHART_AREA_WIDTH - 60, y_price_line - 10,
                    CHART_AREA_LEFT + CHART_AREA_WIDTH, y_price_line + 10],
                   fill=YELLOW)
    draw.text((CHART_AREA_LEFT + CHART_AREA_WIDTH - 55, y_price_line - 7),
              f"{latest_price:.5f}", fill=(0, 0, 0), font=font_tiny)
    info_panel_x = CHART_AREA_LEFT + CHART_AREA_WIDTH + 20
    info_panel_y = CHART_AREA_TOP
    draw.rectangle([info_panel_x - 10, info_panel_y - 10,
                    WIDTH - 20, info_panel_y + 250],
                   fill=DARK_BLUE, outline=GRAY)
    draw.text((info_panel_x, info_panel_y), "BULLTERMINAL", fill=GREEN, font=font_medium)
    draw.text((info_panel_x, info_panel_y + 25), "PRICE TERMINAL", fill=BLUE, font=font_medium)
    price_diffs = [0.0008, 0.0004, 0.0002, 0, -0.0002, -0.0004, -0.0006, -0.0008]
    info_colors = [WHITE, WHITE, WHITE, GREEN, RED, RED, RED, RED]
    for i, (diff, color) in enumerate(zip(price_diffs, info_colors)):
        y_pos = info_panel_y + 55 + (i * 20)
        price_val = latest_price + diff
        draw.text((info_panel_x, y_pos), f"({price_val:.5f})", fill=color, font=font_small)
    draw.text((info_panel_x, info_panel_y + 220), "BULLTERMINAL + 30 CANDLES",
              fill=GREEN, font=font_medium)
    draw.line([(info_panel_x, info_panel_y + 210), (WIDTH - 30, info_panel_y + 210)],
              fill=GRAY, width=1)
    bottom_y = HEIGHT - 40
    draw.rectangle([10, bottom_y - 5, WIDTH - 10, bottom_y + 30],
                  fill=DARK_BLUE, outline=GRAY)
    latest_candle = candles[-1]
    time_str = latest_candle['dt'].strftime('%H:%M:%S')
    draw.text((20, bottom_y), f"TIME: {time_str}", fill=WHITE, font=font_small)
    draw.text((200, bottom_y), f"OPEN: {latest_candle['open']:.5f}", fill=GRAY, font=font_small)
    draw.text((350, bottom_y), f"CLOSE: {latest_candle['close']:.5f}",
              fill=GREEN if latest_candle['signal'] == "CALL" else RED,
              font=font_small)
    draw.text((500, bottom_y), f"HIGH: {latest_candle['high']:.5f}", fill=GREEN, font=font_small)
    draw.text((650, bottom_y), f"LOW: {latest_candle['low']:.5f}", fill=RED, font=font_small)
    signal_box_x = WIDTH - 120
    signal_color = GREEN if latest_candle['signal'] == "CALL" else RED
    draw.rectangle([signal_box_x + 2, bottom_y + 2, signal_box_x + 102, bottom_y + 27],
                  fill=DARK_GRAY)
    draw.rectangle([signal_box_x, bottom_y, signal_box_x + 100, bottom_y + 25],
                  fill=signal_color, outline=WHITE)
    signal_text = f"SIGNAL: {latest_candle['signal']}"
    text_width = draw.textlength(signal_text, font=font_medium)
    text_x = signal_box_x + (100 - text_width) // 2
    draw.text((text_x, bottom_y + 3), signal_text, fill=(0, 0, 0), font=font_medium)
    draw.rectangle([5, 5, WIDTH - 5, HEIGHT - 5], outline=GRAY, width=2)
    corner_size = 15
    draw.line([(5, 5), (5 + corner_size, 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, 5), (5, 5 + corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, 5), (WIDTH - 5 - corner_size, 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, 5), (WIDTH - 5, 5 + corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, HEIGHT - 5), (5 + corner_size, HEIGHT - 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(5, HEIGHT - 5), (5, HEIGHT - 5 - corner_size)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, HEIGHT - 5), (WIDTH - 5 - corner_size, HEIGHT - 5)], fill=LIGHT_BLUE, width=3)
    draw.line([(WIDTH - 5, HEIGHT - 5), (WIDTH - 5, HEIGHT - 5 - corner_size)], fill=LIGHT_BLUE, width=3)
    if MARK_RESULT_CANDLE and result and last_candle_center:
        mark_color = GREEN if result == 'Profit' else RED
        draw.ellipse([last_candle_center[0] - last_candle_radius, last_candle_center[1] - last_candle_radius,
                      last_candle_center[0] + last_candle_radius, last_candle_center[1] + last_candle_radius],
                     outline=mark_color, width=3)
        result_text = "WIN" if result == 'Profit' else "LOSS"
        text_width = draw.textlength(result_text, font=font_medium)
        draw.rectangle([last_candle_center[0] - text_width//2 - 5, last_candle_center[1] - 40,
                        last_candle_center[0] + text_width//2 + 5, last_candle_center[1] - 20],
                       fill=mark_color)
        draw.text((last_candle_center[0] - text_width//2, last_candle_center[1] - 37),
                  result_text, fill=(0, 0, 0), font=font_medium)
    if WATERMARK_ON and WATERMARK_TEXT:
        watermark_text = WATERMARK_TEXT
        watermark_width = draw.textlength(watermark_text, font=font_tiny)
        draw.rectangle([WIDTH - watermark_width - 30, HEIGHT - 25,
                        WIDTH - 10, HEIGHT - 10],
                       fill=(0, 0, 0, 100))
        draw.text((WIDTH - watermark_width - 25, HEIGHT - 22),
                  watermark_text, fill=(255, 255, 255, 150), font=font_tiny)
    buffer = BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    return buffer

def calculate_support_resistance(candles, lookback=20):
    if len(candles) < lookback:
        return None, None, None, None, None
    recent_candles = candles[-lookback:]
    highs = [c['high'] for c in recent_candles]
    lows = [c['low'] for c in recent_candles]
    resistance = max(highs)
    support = min(lows)
    pivot = (resistance + support) / 2
    r1 = 2 * pivot - support
    s1 = 2 * pivot - resistance
    return support, resistance, pivot, r1, s1

def calculate_moving_averages(candles, periods=[20, 50, 100, 200]):
    closes = [c['close'] for c in candles]
    ma_values = {}
    for period in periods:
        if len(closes) >= period:
            ma_values[period] = ema(closes, period)
    return ma_values

# ================= Candle Fetching =================
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

# ================= Signal Processing =================
async def process_signal_background(client, pair, direction, data):
    try:
        await process_signal(client, pair, direction, data)
    except Exception as e:
        print(rainbow_text(f"Background signal error: {e}"))

async def process_signal(client, pair, direction, data):
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH, SIGNAL_USERNAME, SIGNAL_HEADER_TEXT
    global ADVANCED_ANALYSIS, CUSTOM_LINK
    if SEND_PHOTO_WITH_SIGNAL:
        chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
    else:
        chart_candles = None
    try:
        server_now = get_timestamp()
        current_dt = datetime.now(IST)
        next_minute_dt = current_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        entry_ts = int(next_minute_dt.timestamp())
        disp_dt = next_minute_dt
        now_str = disp_dt.strftime("%H：%M")
        _digits = {"0":"𝟶","1":"𝟷","2":"𝟸","3":"𝟹","4":"𝟺","5":"𝟻","6":"𝟼","7":"𝟽","8":"𝟾","9":"𝟿",":":"："}
        formatted_time = "".join(_digits.get(ch, ch) for ch in now_str)
        clean_asset = pair.replace('_', '—').upper()
        direction_symbol = "🔴" if direction == "put" else "🟢"
        direction_text = "𝙿𝚄𝚃" if direction == "put" else "𝙲𝙰𝙻𝙻"
        try:
            if data and len(data) > 0:
                price_val = float(data[-1]['close'])
            else:
                if chart_candles and len(chart_candles) > 0:
                    price_val = float(chart_candles[-1]['close'])
                else:
                    price_val = 0.0
        except Exception as e:
            print(rainbow_text(f"Error getting price: {e}"))
            price_val = 0.0
        price_str = f"{price_val:.5f}"
        price_digits = {"0":"𝟶","1":"𝟷","2":"𝟸","3":"𝟹","4":"𝟺","5":"𝟻","6":"𝟼","7":"𝟽","8":"𝟾","9":"𝟿",".":"."}
        formatted_price = "".join(price_digits.get(ch, ch) for ch in price_str)
        advanced_section = ""
        if ADVANCED_ANALYSIS and data:
            trend, reversal_signal, support_level, resistance_level, logic = analyze_trend_reversal(data)
            trend_text = ""
            if trend == "UP_TREND":
                trend_text = "𝚄𝙿 𝚃𝚁𝙴𝙽𝙳"
            elif trend == "DOWN_TREND":
                trend_text = "𝙳𝙾𝚆𝙽 𝚃𝚁𝙴𝙽𝙳"
            else:
                trend_text = "𝚂𝙸𝙳𝙴𝚆𝚈𝚂"
            resistance_text = f"{resistance_level:.5f}" if resistance_level else "𝙽/𝙰"
            support_text = f"{support_level:.5f}" if support_level else "𝙽/𝙰"
            logic_text = logic if logic else "𝚃𝚛𝚎𝚗𝚍 𝙵𝚘𝚕𝚕𝚘𝚠"
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
        link_section = ""
        if CUSTOM_LINK:
            link_section = f'🔗 <a href="{CUSTOM_LINK}">𝙲𝚁𝙴𝙰𝚃𝙴 𝙰𝙲𝙲𝙾𝚄𝙽𝚃 𝚀𝚇</a>'
        else:
            link_section = "🔗 𝙲𝚁𝙴𝙰𝚃𝙴 𝙰𝙲𝙲𝙾𝚄𝙽𝚃 𝚀𝚇"
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
        await send_telegram_photo_or_chart(msg, pair, chart_candles)
        trade_data = {
            'pair': pair, 'pair_display': clean_asset, 'direction': direction,
            'signal_time': formatted_time,
            'signal_timestamp': entry_ts,
            'price': price_val, 'result': None,
            'profit': None, 'martingale_step': 0, 'timestamp': server_now,
            'date': datetime.now(IST).date().isoformat()
        }
        trade_results.append(trade_data)
        current_time = time.time()
        wait_to_entry_start = max(0, entry_ts - current_time)
        if wait_to_entry_start > 0:
            await asyncio.sleep(wait_to_entry_start)
        await asyncio.sleep(60)
        result_candle = None
        for _ in range(10):
            _data = await get_candles(client, pair, TIMEFRAME)
            if _data and len(_data) >= 1:
                for candle in _data:
                    cand_ts = candle.get('timestamp')
                    if cand_ts and entry_ts <= cand_ts < entry_ts + 60:
                        result_candle = candle
                        break
                    elif not result_candle and candle == _data[-1]:
                        result_candle = candle
                if result_candle:
                    break
            await asyncio.sleep(2)
        if result_candle is None:
            send_telegram_message("⚠️ Could not fetch result candle.")
            if trade_results and trade_results[-1]['timestamp'] == server_now:
                trade_results.pop()
            return
        result_open = float(result_candle.get('open', price_val))
        result_close = float(result_candle.get('close', price_val))
        first_win = (direction == 'put' and result_close < result_open) or (direction == 'call' and result_close > result_open)
        first_equal = abs(result_close - result_open) < 0.00001
        if first_equal:
            trade_results[-1]['result'] = 'Break-even'
            trade_results[-1]['profit'] = 0.0
            save_trade_results()
            print(rainbow_text(f"Trade {clean_asset} at {formatted_time} ended in Break-even."))
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(IST).date().isoformat()]
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
        if SEND_PHOTO_WITH_SIGNAL:
            chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
        else:
            chart_candles = None
        if first_win:
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(IST).date().isoformat()]
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
            trade_results[-1]['profit'] = 10.0
            trade_results[-1]['martingale_step'] = 0
            save_trade_results()
            await asyncio.sleep(120)
            return
        if MARTINGALE_STEPS > 0:
            for martingale_step in range(1, MARTINGALE_STEPS + 1):
                await asyncio.sleep(60)
                mg_candle = None
                waited = 0
                target_ts = entry_ts + 60 * martingale_step
                while waited <= 70:
                    new2 = await get_candles(client, pair, TIMEFRAME)
                    if new2 and len(new2) >= 1:
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
                confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
                today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(IST).date().isoformat()]
                wins_before = sum(1 for t in today_trades if t.get('result') == 'Profit')
                losses_before = sum(1 for t in today_trades if t.get('result') == 'Loss')
                if SEND_PHOTO_WITH_SIGNAL:
                    chart_candles = await get_candles_for_chart(client, pair, TIMEFRAME)
                else:
                    chart_candles = None
                if mg_equal:
                    trade_results[-1]['result'] = 'Break-even'
                    trade_results[-1]['profit'] = 0.0
                    trade_results[-1]['martingale_step'] = martingale_step
                    save_trade_results()
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
                    print(rainbow_text(f"Martingale trade for {clean_asset} at {formatted_time} ended in Break-even (Step {martingale_step})."))
                    break
                elif mg_win:
                    wins_formatted = fancy_font(str(wins_before + 1))
                    losses_formatted = fancy_font(str(losses_before))
                    total_today = wins_before + losses_before + 1
                    win_rate_today = ((wins_before + 1) / total_today * 100) if total_today > 0 else 0
                    win_rate_formatted = fancy_font(f"{win_rate_today:.1f}")
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
                    trade_results[-1]['profit'] = 10.0
                    trade_results[-1]['martingale_step'] = martingale_step
                    save_trade_results()
                    break
                else:
                    if martingale_step == MARTINGALE_STEPS:
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
                        trade_results[-1]['profit'] = -7.0
                        trade_results[-1]['martingale_step'] = martingale_step
                        save_trade_results()
                        break
                    else:
                        continue
        await asyncio.sleep(120)
    except Exception as e:
        print(rainbow_text(f"Error processing signal: {e}"))
        if trade_results and trade_results[-1]['timestamp'] == server_now and trade_results[-1]['result'] is None:
            trade_results.pop()

# ================= Utilities =================
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
    if len(prices) < lookback:
        return None, None
    recent_prices = prices[-lookback:]
    resistance = max(recent_prices)
    support = min(recent_prices)
    return support, resistance

def calculate_moving_averages(candles, periods=[20, 50, 100, 200]):
    closes = [c['close'] for c in candles]
    ma_values = {}
    for period in periods:
        if len(closes) >= period:
            ma_values[period] = ema(closes, period)
    return ma_values

# ================= Strategy Analysis =================
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
        if score < MIN_SIGNAL_SCORE:
            return None, 0.0
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
            if current_price > resistance and prev_price <= resistance:
                return "call", 5
            elif current_price < support and prev_price >= support:
                return "put", 5
            elif abs(current_price - resistance) / resistance < 0.001 and current_price < prev_price:
                return "put", 4
            elif abs(current_price - support) / support < 0.001 and current_price > prev_price:
                return "call", 4
        return None, 0.0
    elif CURRENT_STRATEGY == "Trend_Reverse":
        if len(closes) < 30: return None, 0.0
        ma20 = ema(closes, 20) if len(closes) >= 20 else None
        ma50 = ema(closes, 50) if len(closes) >= 50 else None
        current_price = closes[-1]
        rsi = calculate_rsi(closes, 14)
        support, resistance = calculate_support_resistance_levels(closes, lookback=20)
        sig_dir = None
        score = 0
        logic = ""
        if ma20 and ma50:
            if current_price > ma20 and ma20 > ma50:
                logic = "UP_TREND"
                if rsi > 70 and resistance and abs(current_price - resistance) / resistance < 0.005:
                    sig_dir = "put"
                    score = 5
                    logic = "REVERSAL_AT_RESISTANCE"
                else:
                    sig_dir = "call"
                    score = 4
                    logic = "TREND_CONTINUATION"
            elif current_price < ma20 and ma20 < ma50:
                logic = "DOWN_TREND"
                if rsi < 30 and support and abs(current_price - support) / support < 0.005:
                    sig_dir = "call"
                    score = 5
                    logic = "REVERSAL_AT_SUPPORT"
                else:
                    sig_dir = "put"
                    score = 4
                    logic = "TREND_CONTINUATION"
            else:
                logic = "SIDEWAYS"
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
        if sig_dir and len(candle_data) > 1:
            last_volume = candle_data[-1].get('volume', 0)
            prev_volume = candle_data[-2].get('volume', 0) if len(candle_data) > 1 else 0
            if last_volume > prev_volume * 1.2:
                score += 1
        if sig_dir and score >= MIN_SIGNAL_SCORE:
            return sig_dir, score
        else:
            return None, 0.0
    elif CURRENT_STRATEGY == "Price_Action":
        if len(candle_data) < 5: return None, 0.0
        patterns = detect_price_action_patterns(candle_data)
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price
        sig_dir = None
        score = 0
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
        if not sig_dir:
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
        if len(candle_data) < 20: return None, 0.0
        supertrend_values, trend_values = calculate_supertrend(candle_data, period=10, multiplier=3)
        if supertrend_values and trend_values and supertrend_values[-1] is not None:
            current_price = closes[-1]
            current_supertrend = supertrend_values[-1]
            current_trend = trend_values[-1]
            sig_dir = None
            score = 0
            if current_trend == 1 and current_price > current_supertrend:
                sig_dir = "call"
                score = 5
            elif current_trend == -1 and current_price < current_supertrend:
                sig_dir = "put"
                score = 5
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
        if len(candle_data) < 10: return None, 0.0
        fvg_gaps = detect_fvg_gaps(candle_data)
        current_price = closes[-1]
        sig_dir = None
        score = 0
        recent_fvg = [g for g in fvg_gaps if g['candle_index'] >= len(candle_data) - 5]
        for fvg in recent_fvg:
            if fvg['type'] == 'BULLISH_FVG' and current_price > fvg['end_price']:
                sig_dir = "call"
                score = 5
                break
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
    if len(data) < 5:
        return None
    closes = [c['close'] for c in data]
    price_range = max(closes) - min(closes)
    avg_price = sum(closes) / len(closes)
    if price_range / avg_price > 0.1:
        return None
    direction, score = analyze_market(data)
    if direction and score >= MIN_SIGNAL_SCORE:
        return direction, score, data
    return None

# ================= get_profitable_pairs =================
async def get_profitable_pairs(client, min_profit=70):
    global ANALYZE_ALL_PAIRS, CUSTOM_PAIRS_MODE, CUSTOM_PAIRS_LIST
    if CUSTOM_PAIRS_MODE and CUSTOM_PAIRS_LIST:
        print(rainbow_text(f"✅ Custom Pairs Mode ON. Analyzing {len(CUSTOM_PAIRS_LIST)} custom pairs."))
        return CUSTOM_PAIRS_LIST
    try:
        assets = None
        if hasattr(client, "get_all_assets"):
            r = client.get_all_assets()
            if asyncio.iscoroutine(r): assets = await r
            else: assets = r
        else: assets = None
    except Exception as e:
        print(rainbow_text(f"Error getting assets from API: {e}"))
        assets = None
    if not assets:
        print(rainbow_text("get_all_assets returned None. Using filtered default pairs."))
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
        print(rainbow_text("No pairs found with min_profit, default pairs."))
        if ANALYZE_ALL_PAIRS: pairs = list(PAIR_NAMES.keys())
        else: pairs = [p for p in list(PAIR_NAMES.keys()) if p.lower() not in OTC_PAIRS_TO_EXCLUDE]
    filter_status = "All pairs included" if ANALYZE_ALL_PAIRS else f"Excluding {len(OTC_PAIRS_TO_EXCLUDE)} OTC pairs"
    print(rainbow_text(f"✅ Loaded {len(pairs)} pairs from API (min_profit={min_profit}) - {filter_status}."))
    return pairs

# ================= send_partial_results =================
def send_partial_results():
    global last_partial_results_time
    now = int(time.time())
    if now - last_partial_results_time < PARTIAL_RESULTS_INTERVAL: return
    last_partial_results_time = now
    bd_time = datetime.now(IST)
    today_date = bd_time.strftime("%d．%m．%Y")
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
    msg = "========= 𝙿𝙰𝚁𝚃𝙸𝙰𝙻 𝚁𝙴𝚂𝚄𝙻𝚃𝚂 ==========\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += f"                  📆 — {today_date}\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    msg += "                  📈 𝚁𝙴𝙰𝙻 𝙼𝙰𝚁𝙺𝙴𝚃\n"
    msg += "━━━━━━━━━・━━━━━━━━━\n"
    if not real_trades: msg += "——— 𝙽𝙾 𝚁𝙴𝙰𝙻 𝚂𝙸𝙶𝙽𝙰𝙻𝚂 𝙿𝙻𝙰𝙲𝙴𝙳 ———\n"
    else:
        for trade in real_trades[-20:]:
            time_str = trade.get('signal_time', '𝟶𝟶：𝟶𝟶')
            pair_display = trade.get('pair_display', trade['pair'])
            direction = "𝙱𝚄𝚈" if trade.get('direction') == 'call' else "𝙿𝚄𝚃"
            result_icon = "✅" if trade.get('result') == 'Profit' else "❌"
            martingale_step = trade.get('martingale_step', 0)
            if martingale_step > 0 and trade.get('result') == 'Profit':
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
            time_str = trade.get('signal_time', '𝟶𝟶：𝟶𝟶')
            pair_display = trade.get('pair_display', trade['pair'])
            direction = "𝙱𝚄𝚈" if trade.get('direction') == 'call' else "𝙿𝚄𝚃"
            result_icon = "✅" if trade.get('result') == 'Profit' else "❌"
            martingale_step = trade.get('martingale_step', 0)
            if martingale_step > 0 and trade.get('result') == 'Profit':
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

# ================= Signal Sending (FIXED) =================
async def send_signal_fire_and_forget(client):
    """Sends a signal without blocking the main loop, using proper async concurrency."""
    global signal_count, bot_running
    try:
        pairs = await get_profitable_pairs(client, min_profit=70)
        if not pairs:
            print(rainbow_text("No profitable pairs found. Skipping this cycle."))
            return

        # Limit to first 40 pairs for speed
        pairs = pairs[:40]
        if not pairs:
            return

        # Analyze pairs concurrently with a semaphore to limit concurrency
        sem = asyncio.Semaphore(10)  # Max 10 simultaneous analyses

        async def analyze_with_sem(pair):
            async with sem:
                return await analyze_pair(client, pair)

        # Run all analyses in parallel
        tasks = [analyze_with_sem(pair) for pair in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        best_pair = None
        best_dir = None
        best_score = -1e9
        best_data = None
        viable_pairs = []

        for pair, result in zip(pairs, results):
            if isinstance(result, Exception):
                print(rainbow_text(f"Error analyzing {pair}: {result}"))
                continue
            if result and len(result) == 3:
                direction, score, data = result
                if direction and score > 0:
                    viable_pairs.append((pair, direction, score, data))
                    if score > best_score:
                        best_pair, best_dir, best_score, best_data = pair, direction, score, data

        if not viable_pairs:
            print(rainbow_text("⚠️ No valid signals found. Skipping this cycle."))
            return

        if not best_pair and viable_pairs:
            viable_pairs.sort(key=lambda x: x[2], reverse=True)
            best_pair, best_dir, best_score, best_data = viable_pairs[0]
            print(rainbow_text(f"⚠️ Using best available signal (score: {best_score})"))

        if best_pair and best_dir and best_data:
            asyncio.create_task(process_signal_background(client, best_pair, best_dir, best_data))
            signal_count += 1
            print(rainbow_text(f"✅ Signal #{signal_count} sent for {best_pair} ({best_dir}) with score: {best_score}"))
        else:
            print(rainbow_text("⚠️ No signal meeting minimum score requirements."))
    except Exception as e:
        print(rainbow_text(f"Error in signal fire-and-forget: {e}"))

# ================= Continuous Signal Loop =================
async def continuous_signal_loop(client):
    global bot_running, last_signal_time, next_signal_interval
    while bot_running:
        try:
            now = int(time.time())
            if now - last_signal_time >= next_signal_interval:
                asyncio.create_task(send_signal_fire_and_forget(client))
                last_signal_time = now
                next_signal_interval = get_next_signal_interval()
                print(rainbow_text(f"⏰ Next signal in {next_signal_interval//60} minutes..."))
            await asyncio.sleep(10)
        except Exception as e:
            print(rainbow_text(f"Error in continuous loop: {e}"))
            await asyncio.sleep(10)

# ================= Trading Bot =================
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
                print(rainbow_text(f"Connection attempt {attempt+1} failed: {msg}"))
                if attempt < max_retries - 1: await asyncio.sleep(5)
        except Exception as e:
            print(rainbow_text(f"Connection error on attempt {attempt+1}: {e}"))
            if attempt < max_retries - 1: await asyncio.sleep(5)
    else:
        if BOT_ALERT_ON:
            connection_failed_msg = f"""🔴 *BOT CONNECTION FAILED*

⚠️ *Status:* Could not connect to Quotex account after multiple attempts
📊 *Attempts:* 5 retries completed
🔧 *Action Required:* Check credentials and internet connection
🔄 *Next Action:* Restart the bot after verifying details

📱 *Contact Support:* @TRADEIQDEV_TRADER2
🕐 *Time:* {datetime.now(IST).strftime('%H:%M:%S')}"""
            send_telegram_message(connection_failed_msg)
        return
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
🕐 *Start Time:* {datetime.now(IST).strftime('%H:%M:%S')}
📅 *Date:* {datetime.now(IST).strftime('%d/%m/%Y')}

🚀 *TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝐏𝐫𝐨𝐟𝐞𝐬𝐬𝐢𝐨𝐧𝐚𝐥 𝐓𝐫𝐚𝐝𝐢𝐧𝐠 𝐒𝐲𝐬𝐭𝐞𝐦*"""
        send_telegram_message(bot_started_msg)
    signal_loop_task = asyncio.create_task(continuous_signal_loop(client))
    while bot_running:
        try:
            if not client.check_connect():
                print(rainbow_text("Connection lost, attempting to reconnect..."))
                success, msg = await client.connect()
                if not success:
                    print(rainbow_text(f"Reconnection failed: {msg}"))
                    await asyncio.sleep(10)
                    continue
            await asyncio.sleep(30)
        except Exception as e:
            print(rainbow_text(f"Error in trading loop: {e}"))
            await asyncio.sleep(10)
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
        print(rainbow_text(f"Error in thread: {e}"))
    finally:
        try:
            loop.close()
        except: pass

def start_bot():
    global bot_running, last_partial_results_time, BOT_ALERT_ON
    if bot_running:
        if BOT_ALERT_ON:
            send_telegram_message("ℹ️ Bot is already running")
        return
    bot_running = True
    last_partial_results_time = int(time.time())
    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    telegram_client_started = False
    if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_API_HASH != "" and TELEGRAM_SOURCE_CHANNEL and TELEGRAM_SOURCE_CHANNEL != "":
        telegram_thread = threading.Thread(target=start_telegram_client, daemon=True)
        telegram_thread.start()
        telegram_client_started = True
    if not telegram_client_started:
        print(rainbow_text("ℹ️ Telegram client not configured, skipping (bot will still send signals via Bot API if token is set)"))
    print(rainbow_text("🤖 Bot started successfully!"))

def stop_bot():
    global bot_running, BOT_ALERT_ON
    if not bot_running: return
    bot_running = False
    if BOT_ALERT_ON:
        bot_stopped_msg = f"""🛑 *BOT STOPPED*

📊 *Final Statistics:*
✅ Today's Wins: {sum(1 for r in trade_results if r.get('result') == 'Profit' and r.get('date') == datetime.now(IST).date().isoformat())}
❌ Today's Losses: {sum(1 for r in trade_results if r.get('result') == 'Loss' and r.get('date') == datetime.now(IST).date().isoformat())}
📈 Total Signals Sent: {len([r for r in trade_results if r.get('date') == datetime.now(IST).date().isoformat()])}

🔒 *Status:* Bot has been safely stopped
💾 *Data Saved:* All trade results have been saved
🔄 *Restart:* Use /start to restart the bot

📱 *Contact:* {SIGNAL_USERNAME}
🕐 *Stop Time:* {datetime.now(IST).strftime('%H:%M:%S')}
📅 *Date:* {datetime.now(IST).strftime('%d/%m/%Y')}

🚀 *TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - 𝐓𝐫𝐚𝐝𝐢𝐧𝐠 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 𝐄𝐧𝐝𝐞𝐝*"""
        send_telegram_message(bot_stopped_msg)
    print(rainbow_text("⏹️ Bot stopped"))

# ================= Manual Result =================
def send_manual_result():
    global SEND_PHOTO_WITH_SIGNAL, CHART_BACKGROUND_IMAGE_PATH, SIGNAL_USERNAME
    pending_trades = [t for t in trade_results if t.get('result') is None]
    if not pending_trades:
        print(rainbow_text("❌ No pending signals to send result for."))
        return
    print("\n" + "="*52)
    print(rainbow_text("📊 Send trade result manually"))
    print("="*52)
    for i, trade in enumerate(pending_trades[-5:], 1):
        pair_display = trade.get('pair_display', trade['pair'])
        print(rainbow_text(f"{i}. {pair_display} - {trade['direction']} - {trade['signal_time']} - ⏳ Pending"))
    last_trade = pending_trades[-1]
    last_trade_index = trade_results.index(last_trade)
    print(rainbow_text("\n𝟷. ✅ Send winning result (Sure Shot) for last pending signal"))
    print(rainbow_text("𝟸. ❌ Send losing result (Sure Shot Loss) for last pending signal"))
    print(rainbow_text("𝟹. ↩️ Back to main menu"))
    choice = input(rainbow_text("Choose option: ")).strip()
    if choice in ("1", "2"):
        pair_display = last_trade.get('pair_display', last_trade['pair'])
        temp_trades = [t for i, t in enumerate(trade_results) if i < last_trade_index and t.get('result') in ['Profit', 'Loss']]
        today_trades_before = [t for t in temp_trades if t.get('date') == datetime.now(IST).date().isoformat()]
        today_stats = get_statistics(today_trades_before)
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
        trade_results[last_trade_index]['result'] = result
        trade_results[last_trade_index]['profit'] = 10.0 if result == "Profit" else -7.0
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
        asyncio.run(send_telegram_photo_or_chart(result_msg, last_trade['pair'], None, result=result))
        print(rainbow_text(f"✅ Manual {result} trade report sent for {pair_display}"))
    elif choice == "3":
        return
    else:
        print(rainbow_text("❌ Invalid option"))

def show_partial_results():
    if not trade_results:
        print(rainbow_text("📊 No trades yet"))
        return
    bd_time = datetime.now(IST)
    today_date = bd_time.strftime("%d．%m．%Y")
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
    print(rainbow_text("📊 Partial results"))
    print("="*52)
    print(rainbow_text(f"📅 Date: {today_date}"))
    print(rainbow_text(f"📈 Total signals sent: {len(trade_results)}"))
    print(rainbow_text(f"📊 Today's trades (Confirmed): {len(today_trades)}"))
    print(rainbow_text(f"📉 OTC trades (Confirmed): {len(otc_trades)}"))
    print(rainbow_text(f"📈 Real trades (Confirmed): {len(real_trades)}"))
    if otc_trades:
        otc_total = otc_wins + otc_losses
        otc_win_rate = (otc_wins / otc_total * 100) if otc_total > 0 else 0
        print(rainbow_text(f"\n📊 OTC Market Statistics:"))
        print(rainbow_text(f"✅ Winning trades: {otc_wins}"))
        print(rainbow_text(f"❌ Losing trades: {otc_losses}"))
        print(rainbow_text(f"📊 Win rate: {otc_win_rate:.1f}%"))
    if real_trades:
        real_total = real_wins + real_losses
        real_win_rate = (real_wins / real_total * 100) if real_total > 0 else 0
        print(rainbow_text(f"\n📊 Real Market Statistics:"))
        print(rainbow_text(f"✅ Winning trades: {real_wins}"))
        print(rainbow_text(f"❌ Losing trades: {real_losses}"))
        print(rainbow_text(f"📊 Win rate: {real_win_rate:.1f}%"))
    input(rainbow_text("\nPress Enter to continue..."))

def clear_screen():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system("clear 2>/dev/null || printf \"\033c\" || tput clear 2>/dev/null")

# ================= Settings Menu =================
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
        print(rainbow_text("⚙️ SETTINGS MENU"))
        print("="*60)
        colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
        options = [
            f"𝟷. Martingale Steps: {MARTINGALE_STEPS}",
            f"𝟸. Partial Results Interval: {PARTIAL_RESULTS_INTERVAL} seconds ({PARTIAL_RESULTS_INTERVAL//60} minutes)",
            f"𝟹. Signal Photo Mode: {'✅ ' if SEND_PHOTO_WITH_SIGNAL else '❌ '} {'Market Chart Photo' if SEND_PHOTO_WITH_SIGNAL else 'Text Only'}",
            f"𝟺. Chart Background Photo Path: {CHART_BACKGROUND_IMAGE_PATH[:40]}...",
            f"𝟻. Analyze All Pairs: {'✅ ON' if ANALYZE_ALL_PAIRS else '❌ OFF (Exclude List Applied)'}",
            f"𝟼. Custom Pair Mode: {'✅ ON' if CUSTOM_PAIRS_MODE else '❌ OFF'} ({'CUSTOM PAIRS ONLY' if CUSTOM_PAIRS_MODE else 'AUTO FIND PAIRS'})",
            f"𝟽. Set Custom Pairs List: [{', '.join(CUSTOM_PAIRS_LIST[:2])}{'...' if len(CUSTOM_PAIRS_LIST) > 2 else ''}]",
            f"𝟾. EMA Period: {EMA_PERIOD}",
            f"𝟿. RSI Period: {RSI_PERIOD}",
            f"𝟷𝟶. Current Strategy: {CURRENT_STRATEGY}",
            f"𝟷𝟷. Mark Result Candle: {'✅ ON' if MARK_RESULT_CANDLE else '❌ OFF'}",
            f"𝟷𝟸. Minimum Signal Score: {MIN_SIGNAL_SCORE}",
            f"𝟷𝟹. Support/Resistance Lines: {'✅ ON' if SUPPORT_RESISTANCE_LINES else '❌ OFF'}",
            f"𝟷𝟺. Moving Average Lines: {'✅ ON' if MOVING_AVERAGE_LINES else '❌ OFF'}",
            f"𝟷𝟻. Support/Resistance Strategy: {'✅ ON' if SUPPORT_RESISTANCE_STRATEGY else '❌ OFF'}",
            f"𝟷𝟼. Show Grid Lines: {'✅ ON' if SHOW_GRID_LINES else '❌ OFF'}",
            f"𝟷𝟽. Show Price Scale: {'✅ ON' if SHOW_PRICE_SCALE else '❌ OFF'}",
            f"𝟷𝟾. Trend Lines: {'✅ ON' if TREND_LINES else '❌ OFF'}",
            f"𝟷𝟿. Background Transparency: {BACKGROUND_TRANSPARENCY}%",
            f"𝟸𝟶. Chart Text Glow: {CHART_TEXT_GLOW}%",
            f"𝟸𝟷. Watermark: {'✅ ON' if WATERMARK_ON else '❌ OFF'}",
            f"𝟸𝟸. Watermark Text: {WATERMARK_TEXT[:30]}...",
            f"𝟸𝟹. Signal Header Text: {SIGNAL_HEADER_TEXT[:30]}...",
            f"𝟸𝟺. Chart Header Text: {CHART_HEADER_TEXT[:30]}...",
            f"𝟸𝟻. Telegram Bot Token: {TELEGRAM_BOT_TOKEN[:15]}...",
            f"𝟸𝟼. Telegram Chat ID: {TELEGRAM_CHAT_ID}",
            f"𝟸𝟽. Signal Username: {SIGNAL_USERNAME}",
            f"𝟸𝟾. Signal Interval Min: {SIGNAL_INTERVAL_MIN} seconds",
            f"𝟸𝟿. Signal Interval Max: {SIGNAL_INTERVAL_MAX} seconds",
            f"𝟹𝟶. Telegram API ID: {TELEGRAM_API_ID}",
            f"𝟹𝟷. Telegram API Hash: {TELEGRAM_API_HASH[:10]}...",
            f"𝟹𝟸. Telegram Phone Number: {TELEGRAM_PHONE_NUMBER}",
            f"𝟹𝟹. Telegram Source Channel: {TELEGRAM_SOURCE_CHANNEL}",
            f"𝟹𝟺. Telegram Target Channels: {TELEGRAM_TARGET_CHANNELS}",
            f"𝟹𝟻. Premium Emoji Mode: {'✅ ON' if PREMIUM_EMOJI_MODE else '❌ OFF'}",
            f"𝟹𝟼. Premium Emoji Target: {'✅ ON' if PREMIUM_EMOJI_TARGET else '❌ OFF'}",
            f"𝟹𝟽. 🌀 Parabolic SAR Lines: {'✅ ON' if PARABOLIC_SAR_LINES else '❌ OFF'}",
            f"𝟹𝟾. 📊 GAP Drawing: {'✅ ON' if GAP_DRAWING else '❌ OFF'}",
            f"𝟹𝟿. 🔄 Reverse Area Drawing: {'✅ ON' if REVERSE_AREA_DRAWING else '❌ OFF'}",
            f"𝟺𝟶. 📈 Advanced Analysis: {'✅ ON' if ADVANCED_ANALYSIS else '❌ OFF'}",
            f"𝟺𝟷. 🔗 Custom Link: {CUSTOM_LINK[:30] if CUSTOM_LINK else 'NOT SET'}",
            f"𝟺𝟸. 🌀 FVG Gap Draw: {'✅ ON' if FVG_GAP_DRAW else '❌ OFF'}",
            f"𝟺𝟹. 🔔 Bot ON/OFF Alert: {'✅ ON' if BOT_ALERT_ON else '❌ OFF'}",
            f"𝟺𝟺. 🎨 Candle Up Color: RGB{CANDLE_UP_COLOR}",
            f"𝟺𝟻. 🎨 Candle Down Color: RGB{CANDLE_DOWN_COLOR}",
            f"𝟺𝟼. 📈 EMA Line Chart: {'✅ ON' if EMA_LINE_CHART else '❌ OFF'}",
            f"𝟺𝟽. 📊 Supertrend Chart: {'✅ ON' if SUPERTREND_CHART else '❌ OFF'}",
            f"𝟺𝟾. 🎯 Supertrend Strategy: {'✅ ON' if SUPERTREND_STRATEGY else '❌ OFF'}",
            f"𝟺𝟿. 📐 SNR Lines: {'✅ ON' if SNR_LINES else '❌ OFF'}",
            f"𝟻𝟶. Send Partial Results Now",
            f"𝟻𝟷. PARTIAL RESET (Reset Today's Trade History)",
            f"𝟻𝟸. Save Settings",
            f"𝟻𝟹. Back to Main Menu"
        ]
        for i, option in enumerate(options):
            color = colors[i % len(colors)]
            print(color + fancy_font(option))
        print("="*60)
        choice = input(rainbow_text("Choose option: ")).strip()
        if choice == "1":
            try:
                steps = int(input(fancy_font("Enter number of martingale steps (0-3): ")))
                if 0 <= steps <= 3:
                    MARTINGALE_STEPS = steps
                    print(rainbow_text(f"✅ Martingale steps set to {steps}"))
                else:
                    print(rainbow_text("❌ Invalid input. Must be between 0 and 3"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "2":
            try:
                interval = int(input(fancy_font("Enter partial results interval in minutes (1-60): ")))
                if 1 <= interval <= 60:
                    PARTIAL_RESULTS_INTERVAL = interval * 60
                    print(rainbow_text(f"✅ Partial results interval set to {interval} minutes"))
                else:
                    print(rainbow_text("❌ Invalid input. Must be between 1 and 60"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "3":
            SEND_PHOTO_WITH_SIGNAL = not SEND_PHOTO_WITH_SIGNAL
            new_mode = 'Market Chart Photo' if SEND_PHOTO_WITH_SIGNAL else 'Text Only'
            print(rainbow_text(f"✅ Signal Photo Mode is now {new_mode}"))
        elif choice == "4":
            new_path = input(fancy_font(f"Enter new chart background photo path: ")).strip()
            if new_path:
                CHART_BACKGROUND_IMAGE_PATH = new_path
                print(rainbow_text(f"✅ Chart Background Photo path set to: {CHART_BACKGROUND_IMAGE_PATH}"))
            else:
                print(rainbow_text("⚠️ Path not changed."))
        elif choice == "5":
            ANALYZE_ALL_PAIRS = not ANALYZE_ALL_PAIRS
            status = 'ON' if ANALYZE_ALL_PAIRS else 'OFF (Exclude List Applied)'
            print(rainbow_text(f"✅ Analyze All Pairs is now {status}"))
        elif choice == "6":
            CUSTOM_PAIRS_MODE = not CUSTOM_PAIRS_MODE
            new_mode = 'CUSTOM PAIRS ONLY' if CUSTOM_PAIRS_MODE else 'AUTO FIND PAIRS'
            print(rainbow_text(f"✅ Custom Pair Mode is now {new_mode}"))
        elif choice == "7":
            current_list_str = ", ".join(CUSTOM_PAIRS_LIST)
            new_pairs_str = input(fancy_font(f"Enter pairs (e.g., BRLUSD_otc,USDPKR_otc) (Current: {current_list_str}): ")).strip()
            if new_pairs_str:
                new_list = [p.strip() for p in new_pairs_str.split(',') if p.strip()]
                if new_list:
                    CUSTOM_PAIRS_LIST = new_list
                    print(rainbow_text(f"✅ Custom Pairs List updated to: {', '.join(CUSTOM_PAIRS_LIST)}"))
                else:
                    print(rainbow_text("❌ Input was empty or only separators."))
            else:
                print(rainbow_text("⚠️ Custom Pairs List not changed."))
        elif choice == "8":
            try:
                period = int(input(fancy_font(f"Enter EMA period (Current: {EMA_PERIOD}): ")))
                if period > 0:
                    EMA_PERIOD = period
                    print(rainbow_text(f"✅ EMA Period set to {period}"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "9":
            try:
                period = int(input(fancy_font(f"Enter RSI period (Current: {RSI_PERIOD}): ")))
                if period > 0:
                    RSI_PERIOD = period
                    print(rainbow_text(f"✅ RSI Period set to {period}"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "10":
            print(rainbow_text("Available Strategies: " + ", ".join(AVAILABLE_STRATEGIES)))
            new_strategy = input(fancy_font(f"Enter strategy name (Current: {CURRENT_STRATEGY}): ")).strip()
            if new_strategy in AVAILABLE_STRATEGIES:
                CURRENT_STRATEGY = new_strategy
                print(rainbow_text(f"✅ Strategy set to {new_strategy}"))
            else:
                print(rainbow_text("❌ Invalid strategy"))
        elif choice == "11":
            MARK_RESULT_CANDLE = not MARK_RESULT_CANDLE
            status = 'ON' if MARK_RESULT_CANDLE else 'OFF'
            print(rainbow_text(f"✅ Mark Result Candle is now {status}"))
        elif choice == "12":
            try:
                score = int(input(fancy_font(f"Enter minimum signal score (1-5) (Current: {MIN_SIGNAL_SCORE}): ")))
                if 1 <= score <= 5:
                    MIN_SIGNAL_SCORE = score
                    print(rainbow_text(f"✅ Minimum Signal Score set to {score}"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "13":
            SUPPORT_RESISTANCE_LINES = not SUPPORT_RESISTANCE_LINES
            status = 'ON' if SUPPORT_RESISTANCE_LINES else 'OFF'
            print(rainbow_text(f"✅ Support/Resistance Lines is now {status}"))
        elif choice == "14":
            MOVING_AVERAGE_LINES = not MOVING_AVERAGE_LINES
            status = 'ON' if MOVING_AVERAGE_LINES else 'OFF'
            print(rainbow_text(f"✅ Moving Average Lines is now {status}"))
        elif choice == "15":
            SUPPORT_RESISTANCE_STRATEGY = not SUPPORT_RESISTANCE_STRATEGY
            status = 'ON' if SUPPORT_RESISTANCE_STRATEGY else 'OFF'
            print(rainbow_text(f"✅ Support/Resistance Strategy is now {status}"))
        elif choice == "16":
            SHOW_GRID_LINES = not SHOW_GRID_LINES
            status = 'ON' if SHOW_GRID_LINES else 'OFF'
            print(rainbow_text(f"✅ Show Grid Lines is now {status}"))
        elif choice == "17":
            SHOW_PRICE_SCALE = not SHOW_PRICE_SCALE
            status = 'ON' if SHOW_PRICE_SCALE else 'OFF'
            print(rainbow_text(f"✅ Show Price Scale is now {status}"))
        elif choice == "18":
            TREND_LINES = not TREND_LINES
            status = 'ON' if TREND_LINES else 'OFF'
            print(rainbow_text(f"✅ Trend Lines is now {status}"))
        elif choice == "19":
            try:
                transparency = int(input(fancy_font(f"Enter background transparency (0-100)% (Current: {BACKGROUND_TRANSPARENCY}%): ")))
                if 0 <= transparency <= 100:
                    BACKGROUND_TRANSPARENCY = transparency
                    print(rainbow_text(f"✅ Background Transparency set to {transparency}%"))
                else:
                    print(rainbow_text("❌ Invalid input. Must be between 0 and 100"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "20":
            try:
                glow = int(input(fancy_font(f"Enter chart text glow (0-100)% (Current: {CHART_TEXT_GLOW}%): ")))
                if 0 <= glow <= 100:
                    CHART_TEXT_GLOW = glow
                    print(rainbow_text(f"✅ Chart Text Glow set to {glow}%"))
                else:
                    print(rainbow_text("❌ Invalid input. Must be between 0 and 100"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "21":
            WATERMARK_ON = not WATERMARK_ON
            status = 'ON' if WATERMARK_ON else 'OFF'
            print(rainbow_text(f"✅ Watermark is now {status}"))
        elif choice == "22":
            new_text = input(fancy_font(f"Enter new watermark text (Current: {WATERMARK_TEXT}): ")).strip()
            if new_text:
                WATERMARK_TEXT = new_text
                print(rainbow_text(f"✅ Watermark Text updated to: {WATERMARK_TEXT}"))
            else:
                print(rainbow_text("⚠️ Watermark Text not changed."))
        elif choice == "23":
            new_text = input(fancy_font(f"Enter new signal header text (Current: {SIGNAL_HEADER_TEXT}): ")).strip()
            if new_text:
                SIGNAL_HEADER_TEXT = new_text
                print(rainbow_text(f"✅ Signal Header Text updated to: {SIGNAL_HEADER_TEXT}"))
            else:
                print(rainbow_text("⚠️ Signal Header Text not changed."))
        elif choice == "24":
            new_text = input(fancy_font(f"Enter new chart header text (Current: {CHART_HEADER_TEXT}): ")).strip()
            if new_text:
                CHART_HEADER_TEXT = new_text
                print(rainbow_text(f"✅ Chart Header Text updated to: {CHART_HEADER_TEXT}"))
            else:
                print(rainbow_text("⚠️ Chart Header Text not changed."))
        elif choice == "25":
            new_token = input(fancy_font(f"Enter new Telegram Bot Token: ")).strip()
            if new_token:
                TELEGRAM_BOT_TOKEN = new_token
                global bot
                bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
                print(rainbow_text("✅ Telegram Bot Token updated"))
            else:
                print(rainbow_text("⚠️ Token not changed."))
        elif choice == "26":
            new_chat_id = input(fancy_font(f"Enter new Telegram Chat ID (Current: {TELEGRAM_CHAT_ID}): ")).strip()
            if new_chat_id:
                TELEGRAM_CHAT_ID = new_chat_id
                print(rainbow_text("✅ Telegram Chat ID updated"))
            else:
                print(rainbow_text("⚠️ Chat ID not changed."))
        elif choice == "27":
            new_username = input(fancy_font(f"Enter new Signal Username (Current: {SIGNAL_USERNAME}): ")).strip()
            if new_username:
                SIGNAL_USERNAME = new_username
                print(rainbow_text(f"✅ Signal Username updated to {SIGNAL_USERNAME}"))
            else:
                print(rainbow_text("⚠️ Username not changed."))
        elif choice == "28":
            try:
                new_min = int(input(fancy_font(f"Enter new Signal Interval Min in seconds (Current: {SIGNAL_INTERVAL_MIN}): ")))
                if 60 <= new_min <= 1800:
                    SIGNAL_INTERVAL_MIN = new_min
                    print(rainbow_text(f"✅ Signal Interval Min set to {new_min} seconds"))
                else:
                    print(rainbow_text("❌ Invalid input. Must be between 60 and 1800"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "29":
            try:
                new_max = int(input(fancy_font(f"Enter new Signal Interval Max in seconds (Current: {SIGNAL_INTERVAL_MAX}): ")))
                if 60 <= new_max <= 1800 and new_max >= SIGNAL_INTERVAL_MIN:
                    SIGNAL_INTERVAL_MAX = new_max
                    print(rainbow_text(f"✅ Signal Interval Max set to {new_max} seconds"))
                else:
                    print(rainbow_text(f"❌ Invalid input. Must be between {SIGNAL_INTERVAL_MIN} and 1800"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "30":
            try:
                new_id = int(input(fancy_font(f"Enter Telegram API ID (Current: {TELEGRAM_API_ID}): ")))
                TELEGRAM_API_ID = new_id
                print(rainbow_text("✅ Telegram API ID updated"))
            except:
                print(rainbow_text("❌ Invalid input"))
        elif choice == "31":
            new_hash = input(fancy_font(f"Enter Telegram API Hash: ")).strip()
            if new_hash:
                TELEGRAM_API_HASH = new_hash
                print(rainbow_text("✅ Telegram API Hash updated"))
            else:
                print(rainbow_text("⚠️ Hash not changed."))
        elif choice == "32":
            new_phone = input(fancy_font(f"Enter Telegram Phone Number (Current: {TELEGRAM_PHONE_NUMBER}): ")).strip()
            if new_phone:
                TELEGRAM_PHONE_NUMBER = new_phone
                print(rainbow_text("✅ Telegram Phone Number updated"))
            else:
                print(rainbow_text("⚠️ Phone number not changed."))
        elif choice == "33":
            new_source = input(fancy_font(f"Enter Telegram Source Channel (Current: {TELEGRAM_SOURCE_CHANNEL}): ")).strip()
            if new_source:
                TELEGRAM_SOURCE_CHANNEL = new_source
                print(rainbow_text("✅ Telegram Source Channel updated"))
            else:
                print(rainbow_text("⚠️ Source channel not changed."))
        elif choice == "34":
            new_targets_str = input(fancy_font(f"Enter Telegram Target Channels (comma separated) (Current: {TELEGRAM_TARGET_CHANNELS}): ")).strip()
            if new_targets_str:
                try:
                    new_targets = [int(x.strip()) for x in new_targets_str.split(',')]
                    TELEGRAM_TARGET_CHANNELS = new_targets
                    print(rainbow_text(f"✅ Telegram Target Channels updated to {TELEGRAM_TARGET_CHANNELS}"))
                except:
                    print(rainbow_text("❌ Invalid input. Enter comma separated channel IDs."))
            else:
                print(rainbow_text("⚠️ Target channels not changed."))
        elif choice == "35":
            PREMIUM_EMOJI_MODE = not PREMIUM_EMOJI_MODE
            status = 'ON' if PREMIUM_EMOJI_MODE else 'OFF'
            print(rainbow_text(f"✅ Premium Emoji Mode is now {status}"))
        elif choice == "36":
            PREMIUM_EMOJI_TARGET = not PREMIUM_EMOJI_TARGET
            status = 'ON' if PREMIUM_EMOJI_TARGET else 'OFF'
            print(rainbow_text(f"✅ Premium Emoji Target is now {status}"))
        elif choice == "37":
            PARABOLIC_SAR_LINES = not PARABOLIC_SAR_LINES
            status = 'ON' if PARABOLIC_SAR_LINES else 'OFF'
            print(rainbow_text(f"✅ Parabolic SAR Lines is now {status}"))
        elif choice == "38":
            GAP_DRAWING = not GAP_DRAWING
            status = 'ON' if GAP_DRAWING else 'OFF'
            print(rainbow_text(f"✅ GAP Drawing is now {status}"))
        elif choice == "39":
            REVERSE_AREA_DRAWING = not REVERSE_AREA_DRAWING
            status = 'ON' if REVERSE_AREA_DRAWING else 'OFF'
            print(rainbow_text(f"✅ Reverse Area Drawing is now {status}"))
        elif choice == "40":
            ADVANCED_ANALYSIS = not ADVANCED_ANALYSIS
            status = 'ON' if ADVANCED_ANALYSIS else 'OFF'
            print(rainbow_text(f"✅ Advanced Analysis is now {status}"))
        elif choice == "41":
            new_link = input(fancy_font(f"Enter new Custom Link (Current: {CUSTOM_LINK}): ")).strip()
            if new_link:
                CUSTOM_LINK = new_link
                print(rainbow_text(f"✅ Custom Link updated to: {CUSTOM_LINK}"))
            else:
                CUSTOM_LINK = ""
                print(rainbow_text("✅ Custom Link cleared"))
        elif choice == "42":
            FVG_GAP_DRAW = not FVG_GAP_DRAW
            status = 'ON' if FVG_GAP_DRAW else 'OFF'
            print(rainbow_text(f"✅ FVG Gap Draw is now {status}"))
        elif choice == "43":
            BOT_ALERT_ON = not BOT_ALERT_ON
            status = 'ON' if BOT_ALERT_ON else 'OFF'
            print(rainbow_text(f"✅ Bot ON/OFF Alert is now {status}"))
        elif choice == "44":
            try:
                color_input = input(fancy_font(f"Enter Up Candle Color as R,G,B (Current: {CANDLE_UP_COLOR}): ")).strip()
                if color_input:
                    r, g, b = map(int, color_input.split(','))
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        CANDLE_UP_COLOR = (r, g, b)
                        print(rainbow_text(f"✅ Up Candle Color set to RGB({r},{g},{b})"))
                    else:
                        print(rainbow_text("❌ Invalid color values. Must be between 0 and 255"))
            except:
                print(rainbow_text("❌ Invalid format. Use format: R,G,B"))
        elif choice == "45":
            try:
                color_input = input(fancy_font(f"Enter Down Candle Color as R,G,B (Current: {CANDLE_DOWN_COLOR}): ")).strip()
                if color_input:
                    r, g, b = map(int, color_input.split(','))
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        CANDLE_DOWN_COLOR = (r, g, b)
                        print(rainbow_text(f"✅ Down Candle Color set to RGB({r},{g},{b})"))
                    else:
                        print(rainbow_text("❌ Invalid color values. Must be between 0 and 255"))
            except:
                print(rainbow_text("❌ Invalid format. Use format: R,G,B"))
        elif choice == "46":
            EMA_LINE_CHART = not EMA_LINE_CHART
            status = 'ON' if EMA_LINE_CHART else 'OFF'
            print(rainbow_text(f"✅ EMA Line Chart is now {status}"))
        elif choice == "47":
            SUPERTREND_CHART = not SUPERTREND_CHART
            status = 'ON' if SUPERTREND_CHART else 'OFF'
            print(rainbow_text(f"✅ Supertrend Chart is now {status}"))
        elif choice == "48":
            SUPERTREND_STRATEGY = not SUPERTREND_STRATEGY
            status = 'ON' if SUPERTREND_STRATEGY else 'OFF'
            print(rainbow_text(f"✅ Supertrend Strategy is now {status}"))
        elif choice == "49":
            SNR_LINES = not SNR_LINES
            status = 'ON' if SNR_LINES else 'OFF'
            print(rainbow_text(f"✅ SNR Lines is now {status}"))
        elif choice == "50":
            send_partial_results()
            print(rainbow_text("✅ Partial results sent"))
        elif choice == "51":
            confirm = input(rainbow_text("⚠️ Are you sure you want to reset ALL of Today's trade results? (yes/no): ")).lower()
            if confirm == 'yes':
                global trade_results
                today_date_str = datetime.now(IST).date().isoformat()
                trade_results = [r for r in trade_results if r.get('date') != today_date_str]
                save_trade_results()
                print(rainbow_text("✅ Today's trade results have been reset."))
            else:
                print(rainbow_text("⚠️ Reset cancelled."))
        elif choice == "52":
            save_trade_results()
            print(rainbow_text("✅ Settings and trade results saved"))
        elif choice == "53":
            clear_screen()
            break
        else:
            print(rainbow_text("❌ Invalid option"))
        input(rainbow_text("\nPress Enter to continue..."))
        clear_screen()

# ================= Main Menu =================
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
    clear_screen()
    print("\n" + "="*60)
    print(rainbow_text("🤖 TRADEIQDEV TRADER 𝐱 𝐀𝙸 𝐁𝐎𝐓"))
    print("="*60)
    print(rainbow_text("="*60))
    print(rainbow_text("✅ ACCESS GRANTED"))
    print(rainbow_text("👤 Welcome to TRADEIQDEV TRADER"))
    print(rainbow_text("="*60))
    time.sleep(1)
    load_trade_results()
    while True:
        try:
            clear_screen()
            print("\n" + "="*60)
            print(rainbow_text("🤖 TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - Professional Trading System"))
            print("="*60)
            confirmed_trades = [r for r in trade_results if r.get('result') in ['Profit', 'Loss']]
            today_trades = [r for r in confirmed_trades if r.get('date') == datetime.now(IST).date().isoformat()]
            today_stats = get_statistics(today_trades)
            colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
            stats = [
                f"📊 Total Signals (Confirmed): {len(confirmed_trades)}",
                f"📈 Today's Trades (Confirmed): {today_stats['total_trades']}",
                f"✅ Today's Wins: {today_stats['wins']}",
                f"❌ Today's Losses: {today_stats['losses']}",
                f"📊 Today's Accuracy: {today_stats['accuracy']}%",
                f"⚙️ Martingale: {MARTINGALE_STEPS} step(s)",
                f"🖼️ Photo Send: {'Market Chart' if SEND_PHOTO_WITH_SIGNAL else 'Text Only'}",
                f"🌐 Pair Mode: {'CUSTOM PAIRS ONLY' if CUSTOM_PAIRS_MODE else ('ALL PAIRS' if ANALYZE_ALL_PAIRS else 'EXCLUDE OTC LIST')}",
                f"🎯 Strategy: {CURRENT_STRATEGY}",
                f"🌀 Parabolic SAR: {'ON' if PARABOLIC_SAR_LINES else 'OFF'}",
                f"📊 GAP Drawing: {'ON' if GAP_DRAWING else 'OFF'}",
                f"🌀 FVG Gap Draw: {'ON' if FVG_GAP_DRAW else 'OFF'}",
                f"🔄 Reverse Area: {'ON' if REVERSE_AREA_DRAWING else 'OFF'}",
                f"📈 Advanced Analysis: {'ON' if ADVANCED_ANALYSIS else 'OFF'}",
                f"🎨 Custom Candle Colors: {'ON' if CANDLE_UP_COLOR != (0, 200, 0) or CANDLE_DOWN_COLOR != (255, 50, 50) else 'OFF'}",
                f"📈 EMA Line Chart: {'ON' if EMA_LINE_CHART else 'OFF'}",
                f"📊 Supertrend Chart: {'ON' if SUPERTREND_CHART else 'OFF'}",
                f"🎯 Supertrend Strategy: {'ON' if SUPERTREND_STRATEGY else 'OFF'}",
                f"📐 SNR Lines: {'ON' if SNR_LINES else 'OFF'}",
                f"🔔 Bot Alert: {'ON' if BOT_ALERT_ON else 'OFF'}",
                f"🔗 Custom Link: {'SET' if CUSTOM_LINK else 'NOT SET'}",
                f"📱 Telegram Mode: {'Premium Emoji' if PREMIUM_EMOJI_MODE else 'Regular'}",
                f"🎯 Premium Target: {'ON' if PREMIUM_EMOJI_TARGET else 'OFF'}",
                f"⏱️ Signal Interval: {SIGNAL_INTERVAL_MIN//60}-{SIGNAL_INTERVAL_MAX//60} mins",
                f"📈 Trend Lines: {'ON' if TREND_LINES else 'OFF'}",
                f"🎨 Background Transparency: {BACKGROUND_TRANSPARENCY}%",
                f"✨ Chart Text Glow: {CHART_TEXT_GLOW}%",
                f"💧 Watermark: {'ON' if WATERMARK_ON else 'OFF'}",
                f"📝 Signal Header: {SIGNAL_HEADER_TEXT[:20]}..."
            ]
            for i, stat in enumerate(stats):
                color = colors[i % len(colors)]
                print(color + fancy_font(stat))
            print("="*60)
            menu_options = []
            if not bot_running:
                menu_options.append(f"𝟷. ▶️ Start Bot")
            menu_options.extend([
                f"𝟸. 📊 Send Manual Trade Result",
                f"𝟹. 📈 Show Partial Results",
                f"𝟺. ⚙️ Settings"
            ])
            if bot_running:
                menu_options.append(f"𝟻. ⏹️ Stop Bot")
            menu_options.append(f"𝟼. 🚪 Exit")
            for i, option in enumerate(menu_options):
                color = colors[i % len(colors)]
                print(color + fancy_font(option))
            print("="*60)
            choice = input(rainbow_text("Choose option: ")).strip()
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
                print(rainbow_text("👋 Goodbye! Trade results saved to TRADEIQDEV.json"))
                break
            else:
                print(rainbow_text("❌ Invalid option"))
            input(rainbow_text("\nPress Enter to continue..."))
        except EOFError:
            stop_bot()
            save_trade_results()
            break
        except KeyboardInterrupt:
            stop_bot()
            save_trade_results()
            break
        except Exception as e:
            print(rainbow_text(f"Error in menu: {e}"))
            continue

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            os.system("chcp 65001 > nul")
        else:
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['LC_ALL'] = 'C.UTF-8'
        clear_screen()
        print(rainbow_text("="*70))
        print(rainbow_text("     🤖 TRADEIQDEV 𝐱 𝐀𝙸 𝐁𝐎𝐓 - Professional Trading System"))
        print(rainbow_text("              Version 8.0 - Complete Features Update"))
        print(rainbow_text("="*70))
        print(rainbow_text("📱 Device Verification in progress..."))
        main_menu()
    except Exception as e:
        print(rainbow_text(f"A critical error occurred: {e}"))
        import traceback
        traceback.print_exc()
