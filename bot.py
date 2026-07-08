import asyncio
import time
import os
import io
import json
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- 🎨 GRAPHICS LIBRARIES ---
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import warnings
warnings.filterwarnings("ignore")
# ------------------------------------------

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME", "959675323878")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI") 
OWNER_ID = os.getenv("OWNER_ID")

if not all([BOT_TOKEN, CHANNEL_ID, MONGO_URI, OWNER_ID]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# MongoDB Setup
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database'] 
history_collection = db['game_history'] 
predictions_collection = db['predictions'] 
settings_collection = db['settings']
users_collection = db['users']
bets_collection = db['bets']
active_sessions_collection = db['active_sessions']
sudo_collection = db['sudo_users']  # Sudo users list

# ==========================================
# 💎 PREMIUM EMOJI CONSTANTS
# ==========================================
# Premium Emoji IDs (Emoji တစ်ခုအတွက် ID တစ်ခု)
PREMIUM_EMOJI_IDS = {
    "win_check": "5852871561983299073",      # ✅ WIN - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "lose_cross": "5852812849780362931",     # ❌ LOSE - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "order": "5936130851635990622",          # 📝 Order - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "game": "5936130851635990622",           # 🎮 Game - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "chart": "5936130851635990622",          # 📊 Chart - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "money": "5936130851635990622",          # 💰 Money - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "loss": "5936130851635990622",           # 📉 Loss - ဒီနေရာမှာ ID အစစ်ထည့်ပါ
    "brain": "5936130851635990622",
}

def premium_emoji(emoji_key, fallback):
    """Create premium custom emoji with its own ID"""
    emoji_id = PREMIUM_EMOJI_IDS.get(emoji_key, "0")
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

class Emoji:
    # ========== Premium Custom Emojis (၈ ခု) ==========
    WIN_CHECK = premium_emoji("win_check", "✅")       # Premium ✅
    LOSE_CROSS = premium_emoji("lose_cross", "❌")     # Premium ❌
    ORDER = premium_emoji("order", "📝")               # Premium 📝
    GAME_ICON = premium_emoji("game", "🎮")            # Premium 🎮
    CHART_ICON = premium_emoji("chart", "📊")          # Premium 📊
    MONEY_ICON = premium_emoji("money", "💰")          # Premium 💰
    LOSS_ICON = premium_emoji("loss", "📉")            # Premium 📉
    BRAIN = premium_emoji("brain", "🧠")               # Premium 🧠
    BRAIN_STANDARD = "🧠"                              # Standard fallback
    
    # ========== Standard Emojis (Premium မသုံးတဲ့နေရာတွေအတွက်) ==========
    CHECK = "✅"          # ← Standard CHECK ပြန်ထည့်ထား
    CROSS = "❌"          # ← Standard CROSS ပြန်ထည့်ထား
    WARNING = "⚠️"
    INFO = "ℹ️"
    STAR = "⭐"
    CROWN = "👑"
    FIRE = "🔥"
    SPARKLES = "✨"
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"
    SHIELD = "🛡️"
    
    GAME = "🎮"
    DICE = "🎲"
    TARGET = "🎯"
    CONTROLLER = "🕹️"
    
    MONEY = "💰"
    MONEY_BAG = "💵"
    COIN = "🪙"
    CHART_UP = "📈"
    CHART_DOWN = "📉"
    BAR_CHART = "📊"
    BANK = "🏦"
    GEM = "💎"
    GOLD = "🥇"
    SILVER = "🥈"
    BRONZE = "🥉"
    
    ONLINE = "🟢"
    OFFLINE = "🔴"
    IDLE = "🟡"
    
    ROBOT = "🤖"
    PATTERN = "🎯"
    MARTINGALE = "🎲"
    ANTIMARTINGALE = "🔄"
    TREND = "📊"
    FIBONACCI = "🔢"
    GOLDEN = "🎯"
    MOMENTUM = "📈"
    MONTECARLO = "🎲"
    NEURAL = "🧬"
    REVERSAL = "⚡"
    WAVE = "🌊"
    CHAOS = "🎪"
    
    BET = "🎰"
    TICKET = "🎫"
    
    HASH = "#️⃣"
    CLOCK = "⏰"
    HOURGLASS = "⏳"
    BULLSEYE = "🔴"
    GREEN_CIRCLE = "🟢"
    
    UP = "⬆️"
    DOWN = "⬇️"
    LEFT_RIGHT = "↔️"
    
    OWNER = "👑"
    SUDO = "🛡️"
    USER = "👤"
    BANNED = "🚫"

# ==========================================
# 🔧 2. SYSTEM VARIABLES 
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None 
SESSION_START_ISSUE = None 
LAST_NOTIFIED_ISSUE = None 
CURRENT_AI_MODE = "pattern"
BETTING_ENABLED = True
ACTIVE_USERS = set()
PREDICTION_ACTIVE = False
SUDO_USERS = set()  # Set of sudo user IDs

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# 🛡️ 3. PERMISSION SYSTEM
# ==========================================
async def is_authorized(user_id: int) -> bool:
    """Check if user is Owner or Sudo"""
    if str(user_id) == str(OWNER_ID):
        return True
    if user_id in SUDO_USERS:
        return True
    return False

async def check_permission(user_id: int) -> tuple:
    """Get user permission level"""
    if str(user_id) == str(OWNER_ID):
        return True, "owner"
    if user_id in SUDO_USERS:
        return True, "sudo"
    return False, "unauthorized"

async def load_sudo_users():
    """Load sudo users from database"""
    global SUDO_USERS
    cursor = sudo_collection.find({"active": True})
    docs = await cursor.to_list(length=None)
    SUDO_USERS = {doc["user_id"] for doc in docs}
    print(f"{Emoji.SHIELD} Sudo Users Loaded: {len(SUDO_USERS)}")

async def add_sudo_user(user_id: int, added_by: int) -> bool:
    """Add a sudo user"""
    global SUDO_USERS
    
    if str(user_id) == str(OWNER_ID):
        return False
    
    await sudo_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "active": True,
            "added_by": added_by,
            "added_at": datetime.now()
        }},
        upsert=True
    )
    SUDO_USERS.add(user_id)
    return True

async def remove_sudo_user(user_id: int) -> bool:
    """Remove a sudo user"""
    global SUDO_USERS
    
    await sudo_collection.update_one(
        {"user_id": user_id},
        {"$set": {"active": False, "removed_at": datetime.now()}}
    )
    SUDO_USERS.discard(user_id)
    return True

# Permission decorator for commands
def require_auth(func):
    """Decorator to check if user is authorized"""
    async def wrapper(message: types.Message, *args, **kwargs):
        is_auth, level = await check_permission(message.from_user.id)
        if not is_auth:
            await message.reply(
                f"{Emoji.LOCK} <b>Access Denied!</b>\n\n"
                f"{Emoji.INFO} ဤ Bot ကို Owner နှင့် Sudo Users များသာ အသုံးပြုခွင့်ရှိပါသည်။\n\n"
                f"{Emoji.KEY} Owner ထံဆက်သွယ်ပါ။"
            )
            return
        return await func(message, *args, **kwargs)
    return wrapper

def require_owner(func):
    """Decorator to check if user is Owner"""
    async def wrapper(message: types.Message, *args, **kwargs):
        if str(message.from_user.id) != str(OWNER_ID):
            await message.reply(f"{Emoji.CROSS} {Emoji.CROWN} Owner သာ ဤ command ကိုသုံးခွင့်ရှိသည်။")
            return
        return await func(message, *args, **kwargs)
    return wrapper

# ==========================================
# 💰 4. VIRTUAL BALANCE SYSTEM
# ==========================================
async def get_user_balance(user_id: int) -> dict:
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "balance": 100000.0,
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_wagered": 0.0,
            "total_won": 0.0,
            "profit": 0.0,
            "win_streak": 0,
            "lose_streak": 0,
            "best_streak": 0,
            "created_at": datetime.now()
        }
        await users_collection.insert_one(user)
    return user

async def update_balance(user_id: int, amount: float, operation: str = "add") -> dict:
    user = await get_user_balance(user_id)
    
    if operation == "add":
        new_balance = user["balance"] + amount
    elif operation == "subtract":
        new_balance = user["balance"] - amount
    elif operation == "set":
        new_balance = amount
    else:
        new_balance = user["balance"]
    
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"balance": new_balance}}
    )
    
    user["balance"] = new_balance
    return user

async def place_bet(user_id: int, issue_number: str, bet_amount: float, predicted_size: str, ai_mode: str) -> dict:
    user = await get_user_balance(user_id)
    
    if user["balance"] < bet_amount:
        return {"success": False, "message": f"{Emoji.CROSS} လက်ကျန်ငွေ မလုံလောက်ပါ!\n{Emoji.MONEY} Balance: {user['balance']:,.0f} Ks\n{Emoji.MONEY_BAG} လောင်းကြေး: {bet_amount:,.0f} Ks"}
    
    existing_bet = await bets_collection.find_one({"user_id": user_id, "issue_number": issue_number})
    if existing_bet:
        return {"success": False, "message": f"{Emoji.CROSS} Period {issue_number} အတွက် လောင်းပြီးသားဖြစ်ပါသည်!"}
    
    await update_balance(user_id, bet_amount, "subtract")
    
    bet = {
        "user_id": user_id,
        "issue_number": issue_number,
        "bet_amount": bet_amount,
        "predicted_size": predicted_size,
        "ai_mode": ai_mode,
        "actual_size": None,
        "actual_number": None,
        "result": None,
        "payout": 0.0,
        "profit": 0.0,
        "created_at": datetime.now()
    }
    
    await bets_collection.insert_one(bet)
    
    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"total_bets": 1, "total_wagered": bet_amount}}
    )
    
    return {
        "success": True, 
        "message": f"{Emoji.CHECK} လောင်းကြေးထည့်ပြီးပါပြီ!",
        "balance": user['balance'] - bet_amount
    }

async def settle_bets(issue_number: str, actual_size: str, actual_number: int, game_type: str = "WINGO_30S"):
    pending_bets = await bets_collection.find({"issue_number": issue_number, "result": None}).to_list(length=None)
    
    settled_count = 0
    for bet in pending_bets:
        user_id = bet["user_id"]
        predicted_size = bet["predicted_size"]
        is_win = (predicted_size == actual_size)
        bet_amount = bet["bet_amount"]
        
        if is_win:
            payout = bet_amount * 1.96
            profit = payout - bet_amount
            result = "WIN"
            
            await users_collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "total_wins": 1,
                        "total_won": payout,
                        "profit": profit,
                        "win_streak": 1,
                        "lose_streak": -1
                    }
                }
            )
            
            user = await get_user_balance(user_id)
            if user["win_streak"] > user["best_streak"]:
                await users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"best_streak": user["win_streak"]}}
                )
            
            await update_balance(user_id, payout, "add")
        else:
            payout = 0
            profit = -bet_amount
            result = "LOSE"
            
            await users_collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "total_losses": 1,
                        "profit": profit,
                        "win_streak": -1,
                        "lose_streak": 1
                    }
                }
            )
        
        await bets_collection.update_one(
            {"_id": bet["_id"]},
            {"$set": {
                "actual_size": actual_size,
                "actual_number": actual_number,
                "result": result,
                "payout": payout,
                "profit": profit,
                "settled_at": datetime.now()
            }}
        )
        
        await send_bet_result_notification(user_id, bet, actual_size, actual_number, game_type, is_win, payout, profit)
        settled_count += 1
    
    return settled_count

async def send_bet_result_notification(user_id: int, bet: dict, actual_size: str, actual_number: int, game_type: str, is_win: bool, payout: float, profit: float):
    try:
        user = await get_user_balance(user_id)
        
        color_map = {
            0: "🟣 VIOLET", 1: "🟢 GREEN", 2: "🔴 RED", 
            3: "🟢 GREEN", 4: "🔴 RED", 5: "🟢 GREEN",
            6: "🔴 RED", 7: "🟢 GREEN", 8: "🔴 RED", 9: "🟢 GREEN"
        }
        color = color_map.get(actual_number, "⚪ WHITE")
        
        ai_emoji_map = {
            "pattern": Emoji.PATTERN, "martingale": Emoji.MARTINGALE,
            "anti_martingale": Emoji.ANTIMARTINGALE, "trend_following": Emoji.TREND,
            "fibonacci": Emoji.FIBONACCI, "golden_ratio": Emoji.GOLDEN,
            "momentum": Emoji.MOMENTUM, "monte_carlo": Emoji.MONTECARLO,
            "neural_pattern": Emoji.NEURAL, "quick_reversal": Emoji.REVERSAL,
            "wave_analysis": Emoji.WAVE, "chaos_theory": Emoji.CHAOS,
        }
        
        if is_win:
            message = (
                f"{Emoji.CHECK} <b>WIN!</b> +{profit:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME} <b>{game_type}</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.BAR_CHART} <b>Result:</b> {actual_number} {Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} {actual_size} {color}\n"
                f"{Emoji.MONEY} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.CHART_UP} <b>Profit:</b> +{user['profit']:,.2f} Ks\n"
               # f"{Emoji.FIRE} <b>Win Streak:</b> {user['win_streak']} {'🔥' * min(user['win_streak'], 5)}\n"
                #f"━━━━━━━━━━━━━━━━━━\n"
                #f"{ai_emoji_map.get(bet['ai_mode'], Emoji.ROBOT)} <b>AI:</b> {bet['ai_mode'].upper()}\n"
                #f"{Emoji.MONEY_BAG} <b>Bet:</b> {bet['bet_amount']:,.0f} Ks on {bet['predicted_size']}"
            )
        else:
            message = (
                f"{Emoji.CROSS} <b>LOSE!</b> -{bet['bet_amount']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME} <b>{game_type}</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.BAR_CHART} <b>Result:</b> {actual_number} {Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} {actual_size} {color}\n"
                f"{Emoji.MONEY} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.CHART_DOWN} <b>Profit:</b> {user['profit']:,.2f} Ks\n"
               # f"{Emoji.WARNING} <b>Lose Streak:</b> {user['lose_streak']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
               # f"{ai_emoji_map.get(bet['ai_mode'], Emoji.ROBOT)} <b>AI:</b> {bet['ai_mode'].upper()}\n"
              #  f"{Emoji.MONEY_BAG} <b>Bet:</b> {bet['bet_amount']:,.0f} Ks on {bet['predicted_size']}"
            )
        
        await bot.send_message(chat_id=user_id, text=message)
        
    except Exception as e:
        print(f"Failed to send notification to {user_id}: {e}")

async def get_leaderboard(limit: int = 10) -> list:
    cursor = users_collection.find().sort("balance", -1).limit(limit)
    return await cursor.to_list(length=limit)

# ==========================================
# 🔑 5. ASYNC API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=1):
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=3.0) as response:
                if response.status == 200:
                    return await response.json()
        except Exception:
            await asyncio.sleep(0.2)
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME,
        'pwd': PASSWORD,
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '4fc4413428be43faa1a3f30d9745ae3a',
        'signature': '5458639AF428AC897FDFF1102D82EB9C',
        'timestamp': int(time.time()),
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print(f"{Emoji.CHECK} Login Success\n")
        return True
    return False

# ==========================================
# 🧠 6. ALL AI PREDICTION MODES
# ==========================================
def detect_active_pattern(history_list):
    if len(history_list) < 4:
        return None, None
    
    patterns_to_check = [
        ("BBSS", ["BIG", "BIG", "SMALL", "SMALL"]),
        ("BBS", ["BIG", "BIG", "SMALL"]),
        ("BSS", ["BIG", "SMALL", "SMALL"]),
        ("BSBS", ["BIG", "SMALL", "BIG", "SMALL"]),
        ("SBSB", ["SMALL", "BIG", "SMALL", "BIG"]),
        ("BSB", ["BIG", "SMALL", "BIG"]),
        ("SBS", ["SMALL", "BIG", "SMALL"]),
        ("BBB", ["BIG", "BIG", "BIG"]),
        ("SSS", ["SMALL", "SMALL", "SMALL"]),
    ]
    
    recent = history_list[-15:]
    best_pattern = None
    best_score = 0
    best_next = None
    
    for pattern_name, pattern_seq in patterns_to_check:
        pattern_len = len(pattern_seq)
        match_count = 0
        for i in range(len(recent) - pattern_len + 1):
            if recent[i:i+pattern_len] == pattern_seq:
                match_count += 1
        
        if match_count >= 2:
            pattern_next_map = {
                "BBSS": "BIG", "BBS": "BIG", "BSS": "BIG",
                "BSBS": "BIG", "SBSB": "SMALL",
                "BSB": "BIG", "SBS": "SMALL",
                "BBB": "BIG", "SSS": "SMALL"
            }
            next_pred = pattern_next_map.get(pattern_name, "BIG")
            score = match_count * pattern_len
            if score > best_score:
                best_score = score
                best_pattern = pattern_name
                best_next = next_pred
    
    return best_pattern, best_next

def pattern_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.HOURGLASS} Pattern detection အတွက် data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    active_pattern, next_pred = detect_active_pattern(all_history)
    
    if active_pattern:
        if next_pred == "BIG":
            return "BIG", "BIG (အကြီး) 🔴", 75.0, f"{Emoji.PATTERN} Active Pattern: {active_pattern} {Emoji.UP} BIG"
        else:
            return "SMALL", "SMALL (အသေး) 🟢", 75.0, f"{Emoji.PATTERN} Active Pattern: {active_pattern} {Emoji.DOWN} SMALL"
    else:
        b_count = all_history.count("BIG")
        s_count = all_history.count("SMALL")
        if b_count > s_count:
            return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.INFO} Pattern မတွေ့ - Majority BIG ({b_count}:{s_count})"
        else:
            return "SMALL", "SMALL (အသေး) 🟢", 55.0, f"{Emoji.INFO} Pattern မတွေ့ - Majority SMALL ({b_count}:{s_count})"

def martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", "BIG (အကြီး) 🔴", 60.0, f"{Emoji.MARTINGALE} Martingale: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    recent_10 = all_history[-10:]
    big_count = recent_10.count("BIG")
    small_count = recent_10.count("SMALL")
    
    if big_count > small_count:
        return "SMALL", "SMALL (အသေး) 🟢", 65.0, f"{Emoji.MARTINGALE} Contrarian - BIG:{big_count} SMALL:{small_count} {Emoji.DOWN} SMALL"
    else:
        return "BIG", "BIG (အကြီး) 🔴", 65.0, f"{Emoji.MARTINGALE} Contrarian - BIG:{big_count} SMALL:{small_count} {Emoji.UP} BIG"

def anti_martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", "BIG (အကြီး) 🔴", 60.0, f"{Emoji.ANTIMARTINGALE} Anti-Martingale: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    recent_5 = all_history[-5:]
    big_streak = small_streak = 0
    
    for result in reversed(recent_5):
        if result == "BIG":
            big_streak += 1; small_streak = 0
        else:
            small_streak += 1; big_streak = 0
    
    if big_streak >= 2:
        return "BIG", "BIG (အကြီး) 🔴", 70.0, f"{Emoji.ANTIMARTINGALE} BIG streak {big_streak} {Emoji.UP} Continue BIG"
    elif small_streak >= 2:
        return "SMALL", "SMALL (အသေး) 🟢", 70.0, f"{Emoji.ANTIMARTINGALE} SMALL streak {small_streak} {Emoji.DOWN} Continue SMALL"
    else:
        last = all_history[-1] if all_history else "BIG"
        emoji_display = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji_display}", 60.0, f"{Emoji.ANTIMARTINGALE} Follow last"

def trend_following_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", "BIG (အကြီး) 🔴", 58.0, f"{Emoji.TREND} Trend: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    recent_8 = all_history[-8:]
    recent_4 = all_history[-4:]
    
    big_8 = recent_8.count("BIG") / 8
    big_4 = recent_4.count("BIG") / 4
    trend_direction = big_4 - big_8
    
    if trend_direction > 0.1:
        return "BIG", "BIG (အကြီး) 🔴", 72.0, f"{Emoji.TREND} BIG momentum +{trend_direction*100:.0f}% {Emoji.CHART_UP}"
    elif trend_direction < -0.1:
        return "SMALL", "SMALL (အသေး) 🟢", 72.0, f"{Emoji.TREND} SMALL momentum +{abs(trend_direction)*100:.0f}% {Emoji.CHART_DOWN}"
    else:
        latest = all_history[-1]
        emoji_display = "🔴" if latest == "BIG" else "🟢"
        return latest, f"{latest} ({'အကြီး' if latest == 'BIG' else 'အသေး'}) {emoji_display}", 60.0, f"{Emoji.TREND} Sideways - Follow latest {Emoji.LEFT_RIGHT}"

def fibonacci_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.FIBONACCI} Fibonacci: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    fib_levels = [3, 5, 8, 13, 21]
    
    results = []
    for level in fib_levels:
        if len(all_history) >= level:
            segment = all_history[-level:]
            big_pct = segment.count("BIG") / level
            if 0.38 <= big_pct <= 0.62:
                results.append("BIG" if big_pct < 0.5 else "SMALL")
            elif big_pct > 0.618:
                results.append("SMALL")
            else:
                results.append("BIG")
    
    if results:
        final = max(set(results), key=results.count)
        emoji_display = "🔴" if final == "BIG" else "🟢"
        return final, f"{final} ({'အကြီး' if final == 'BIG' else 'အသေး'}) {emoji_display}", 68.0, f"{Emoji.FIBONACCI} Fib levels: {len(results)} analyzed"
    return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.FIBONACCI} Default"

def golden_ratio_predict(history_docs):
    if len(history_docs) < 12:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.GOLDEN} Golden Ratio: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    lookback = min(21, len(all_history))
    segment = all_history[-lookback:]
    big_count = segment.count("BIG")
    big_ratio = big_count / lookback
    
    if big_ratio > 0.618:
        return "SMALL", "SMALL (အသေး) 🟢", 70.0, f"{Emoji.GOLDEN} BIG ratio {big_ratio*100:.1f}% > 61.8% {Emoji.DOWN} Reversal"
    elif big_ratio < 0.382:
        return "BIG", "BIG (အကြီး) 🔴", 70.0, f"{Emoji.GOLDEN} BIG ratio {big_ratio*100:.1f}% < 38.2% {Emoji.UP} Reversal"
    else:
        latest = all_history[-1]
        emoji_display = "🔴" if latest == "BIG" else "🟢"
        return latest, f"{latest} ({'အကြီး' if latest == 'BIG' else 'အသေး'}) {emoji_display}", 65.0, f"{Emoji.GOLDEN} Golden Zone: {big_ratio*100:.1f}%"

def momentum_predict(history_docs):
    if len(history_docs) < 6:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.MOMENTUM} Momentum: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    momentum_score = 0
    weights = [5, 4, 3, 2, 1]
    
    for i, result in enumerate(all_history[-5:]):
        if result == "BIG":
            momentum_score += weights[i]
        else:
            momentum_score -= weights[i]
    
    if momentum_score > 3:
        return "BIG", "BIG (အကြီး) 🔴", 73.0, f"{Emoji.MOMENTUM} Strong BIG (+{momentum_score}) {Emoji.CHART_UP}"
    elif momentum_score < -3:
        return "SMALL", "SMALL (အသေး) 🟢", 73.0, f"{Emoji.MOMENTUM} Strong SMALL ({momentum_score}) {Emoji.CHART_DOWN}"
    else:
        latest = all_history[-1]
        emoji_display = "🔴" if latest == "BIG" else "🟢"
        return latest, f"{latest} ({'အကြီး' if latest == 'BIG' else 'အသေး'}) {emoji_display}", 58.0, f"{Emoji.MOMENTUM} Weak: {momentum_score}"

def monte_carlo_predict(history_docs):
    if len(history_docs) < 15:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.MONTECARLO} Monte Carlo: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    np.random.seed(int(time.time()))
    simulations = 1000
    big_wins = 0
    big_prob = all_history.count("BIG") / len(all_history)
    
    for _ in range(simulations):
        if np.random.choice(["BIG", "SMALL"], p=[big_prob, 1-big_prob]) == "BIG":
            big_wins += 1
    
    if big_wins > 500:
        prob = (big_wins / simulations) * 100
        return "BIG", "BIG (အကြီး) 🔴", min(prob, 80), f"{Emoji.MONTECARLO} {simulations} sims {Emoji.UP} BIG {prob:.1f}%"
    else:
        prob = ((simulations - big_wins) / simulations) * 100
        return "SMALL", "SMALL (အသေး) 🟢", min(prob, 80), f"{Emoji.MONTECARLO} {simulations} sims {Emoji.DOWN} SMALL {prob:.1f}%"

def neural_pattern_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.NEURAL} Neural Pattern: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    features = []
    for i in range(3, len(all_history)):
        window = all_history[i-3:i]
        big_count = window.count("BIG")
        features.append({"big_ratio": big_count / 3, "next": all_history[i]})
    
    current_big_ratio = all_history[-3:].count("BIG") / 3
    similar_big = similar_small = 0
    
    for f in features:
        if abs(f["big_ratio"] - current_big_ratio) < 0.1:
            if f["next"] == "BIG":
                similar_big += 1
            else:
                similar_small += 1
    
    total = similar_big + similar_small
    if total > 0:
        big_prob = (similar_big / total) * 100
        if big_prob > 50:
            return "BIG", "BIG (အကြီး) 🔴", min(big_prob + 10, 85), f"{Emoji.NEURAL} {total} patterns {Emoji.UP} BIG {big_prob:.0f}%"
        else:
            return "SMALL", "SMALL (အသေး) 🟢", min((100-big_prob) + 10, 85), f"{Emoji.NEURAL} {total} patterns {Emoji.DOWN} SMALL {100-big_prob:.0f}%"
    
    return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.NEURAL} No similar patterns"

def quick_reversal_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.REVERSAL} Quick Reversal: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    recent_5 = all_history[-5:]
    
    alternations = sum(1 for i in range(1, len(recent_5)) if recent_5[i] != recent_5[i-1])
    alt_rate = alternations / (len(recent_5) - 1)
    
    if alt_rate > 0.75:
        last = recent_5[-1]
        predicted = "SMALL" if last == "BIG" else "BIG"
        emoji_display = "🔴" if predicted == "BIG" else "🟢"
        return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji_display}", 72.0, f"{Emoji.REVERSAL} Alt rate {alt_rate*100:.0f}% {Emoji.LEFT_RIGHT} Reversal"
    else:
        last = recent_5[-1]
        emoji_display = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji_display}", 60.0, f"{Emoji.REVERSAL} Alt rate {alt_rate*100:.0f}% Follow"

def wave_analysis_predict(history_docs):
    if len(history_docs) < 8:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.WAVE} Wave Analysis: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    waves = []
    current = all_history[0]
    count = 1
    
    for result in all_history[1:]:
        if result == current:
            count += 1
        else:
            waves.append((current, count))
            current = result
            count = 1
    waves.append((current, count))
    
    if len(waves) >= 3:
        last_wave = waves[-1]
        prev_wave = waves[-2]
        
        if last_wave[1] >= 3 and prev_wave[0] != last_wave[0]:
            emoji_display = "🔴" if last_wave[0] == "BIG" else "🟢"
            return last_wave[0], f"{last_wave[0]} ({'အကြီး' if last_wave[0] == 'BIG' else 'အသေး'}) {emoji_display}", 70.0, f"{Emoji.WAVE} Impulse: {last_wave[1]} consecutive {Emoji.UP}"
        elif last_wave[1] <= 2:
            predicted = "SMALL" if last_wave[0] == "BIG" else "BIG"
            emoji_display = "🔴" if predicted == "BIG" else "🟢"
            return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji_display}", 68.0, f"{Emoji.WAVE} Correction expected {Emoji.DOWN}"
    
    latest = all_history[-1]
    emoji_display = "🔴" if latest == "BIG" else "🟢"
    return latest, f"{latest} ({'အကြီး' if latest == 'BIG' else 'အသေး'}) {emoji_display}", 58.0, f"{Emoji.WAVE} Default"

def chaos_theory_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{Emoji.CHAOS} Chaos Theory: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    def calc_entropy(segment):
        total = len(segment)
        big_p = segment.count("BIG") / total
        small_p = segment.count("SMALL") / total
        entropy = 0
        for p in [big_p, small_p]:
            if p > 0:
                entropy -= p * np.log2(p)
        return entropy
    
    entropy_3 = calc_entropy(all_history[-3:])
    entropy_5 = calc_entropy(all_history[-5:])
    entropy_10 = calc_entropy(all_history[-10:])
    
    if entropy_3 > entropy_5 > entropy_10:
        last = all_history[-3:][-1]
        predicted = "SMALL" if last == "BIG" else "BIG"
        emoji_display = "🔴" if predicted == "BIG" else "🟢"
        return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji_display}", 67.0, f"{Emoji.CHAOS} Increasing entropy {Emoji.LEFT_RIGHT} Reversal"
    elif entropy_3 < entropy_5:
        majority = "BIG" if all_history[-5:].count("BIG") > all_history[-5:].count("SMALL") else "SMALL"
        emoji_display = "🔴" if majority == "BIG" else "🟢"
        return majority, f"{majority} ({'အကြီး' if majority == 'BIG' else 'အသေး'}) {emoji_display}", 65.0, f"{Emoji.CHAOS} Pattern forming {Emoji.SPARKLES}"
    
    latest = all_history[-1]
    emoji_display = "🔴" if latest == "BIG" else "🟢"
    return latest, f"{latest} ({'အကြီး' if latest == 'BIG' else 'အသေး'}) {emoji_display}", 55.0, f"{Emoji.CHAOS} Stable entropy"

# ==========================================
# 🎯 AI MODE DICTIONARY
# ==========================================
AI_MODES = {
    "pattern": {"func": pattern_predict, "name": f"{Emoji.PATTERN} Pattern AI", "desc": "Pattern Auto-Switch Detection"},
    "martingale": {"func": martingale_predict, "name": f"{Emoji.MARTINGALE} Martingale AI", "desc": "Contrarian - ရှုံးတိုင်း 2x"},
    "anti_martingale": {"func": anti_martingale_predict, "name": f"{Emoji.ANTIMARTINGALE} Anti-Martingale AI", "desc": "Trend Follow - နိုင်တိုင်း 2x"},
    "trend_following": {"func": trend_following_predict, "name": f"{Emoji.TREND} Trend Following AI", "desc": "Moving Average Trend Analysis"},
    "fibonacci": {"func": fibonacci_predict, "name": f"{Emoji.FIBONACCI} Fibonacci AI", "desc": "Fibonacci Retracement Levels"},
    "golden_ratio": {"func": golden_ratio_predict, "name": f"{Emoji.GOLDEN} Golden Ratio AI", "desc": "61.8% Golden Ratio Rule"},
    "momentum": {"func": momentum_predict, "name": f"{Emoji.MOMENTUM} Momentum AI", "desc": "Weighted Momentum Analysis"},
    "monte_carlo": {"func": monte_carlo_predict, "name": f"{Emoji.MONTECARLO} Monte Carlo AI", "desc": "1000x Probability Simulation"},
    "neural_pattern": {"func": neural_pattern_predict, "name": f"{Emoji.NEURAL} Neural Pattern AI", "desc": "Pattern Similarity Search"},
    "quick_reversal": {"func": quick_reversal_predict, "name": f"{Emoji.REVERSAL} Quick Reversal AI", "desc": "Rapid Reversal Detection"},
    "wave_analysis": {"func": wave_analysis_predict, "name": f"{Emoji.WAVE} Wave Analysis AI", "desc": "Elliott Wave Principle"},
    "chaos_theory": {"func": chaos_theory_predict, "name": f"{Emoji.CHAOS} Chaos Theory AI", "desc": "Entropy & Chaos Analysis"},
}

def get_prediction(history_docs, mode):
    mode_info = AI_MODES.get(mode)
    if mode_info:
        return mode_info["func"](history_docs)
    return AI_MODES["pattern"]["func"](history_docs)

# ==========================================
# 🎨 7. GRAPH GENERATOR
# ==========================================
def generate_winrate_chart(predictions, ai_mode="pattern", user_data=None):
    wins, losses = 0, 0
    bar_colors, dots_list, bar_heights = [], [], []
    history_wr = []
    
    latest_preds = list(reversed(predictions))[-20:]
    
    for i, p in enumerate(latest_preds): 
        current_played = i + 1
        
        if 'WIN' in p.get('win_lose', ''):
            wins += 1
            bar_colors.append('#00e5ff')
            dots_list.append(('W', '#1de9b6'))
        else:
            losses += 1
            bar_colors.append('#ff4444')
            dots_list.append(('L', '#ef5350'))
            
        current_wr = (wins / current_played) * 100
        bar_heights.append(current_wr) 
        history_wr.append(current_wr)
            
    total_played = wins + losses
    win_rate = int((wins / total_played * 100)) if total_played > 0 else 0

    mode_colors = {
        "pattern": '#00e5ff', "martingale": '#ff9800', "anti_martingale": '#9c27b0',
        "trend_following": '#2196f3', "fibonacci": '#4caf50', "golden_ratio": '#ffd700',
        "momentum": '#f44336', "monte_carlo": '#607d8b', "neural_pattern": '#e91e63',
        "quick_reversal": '#ff5722', "wave_analysis": '#00bcd4', "chaos_theory": '#795548'
    }
    
    accent_color = mode_colors.get(ai_mode, '#00e5ff')
    mode_name = AI_MODES.get(ai_mode, {}).get("name", f"{Emoji.ROBOT} AI")

    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26') 
    
    fig.text(0.05, 0.93, f"🏆 {mode_name} PERFORMANCE", color='#ffffff', fontsize=26, fontweight='bold', ha='left')
    fig.text(0.05, 0.88, f"MODE: {ai_mode.upper()}", color=accent_color, fontsize=14, fontweight='bold', ha='left')

    if user_data:
        balance = user_data.get('balance', 0)
        profit = user_data.get('profit', 0)
        profit_color = '#1de9b6' if profit > 0 else '#ef5350' if profit < 0 else '#ffd700'
        fig.text(0.95, 0.93, f"💰 {balance:,.0f} Ks", color='#ffd700', fontsize=14, fontweight='bold', ha='right')
        fig.text(0.95, 0.88, f"P/L: {profit:,.0f}", color=profit_color, fontsize=11, fontweight='bold', ha='right')

    ax_circle = fig.add_axes([0.08, 0.42, 0.35, 0.40])
    ax_circle.set_axis_off()
    ax_circle.set_xlim(0, 1)
    ax_circle.set_ylim(0, 1)
    
    theta_bg = np.linspace(-1.25*np.pi, 0.25*np.pi, 200)
    ax_circle.plot(0.5 + 0.45*np.cos(theta_bg), 0.5 + 0.45*np.sin(theta_bg), color='#2c313c', linewidth=12)
    
    if win_rate > 0:
        end_angle = 0.25*np.pi - (win_rate/100) * 1.5 * np.pi
        theta_fg = np.linspace(0.25*np.pi, end_angle, 100)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color=accent_color, linewidth=12)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color=accent_color, linewidth=22, alpha=0.2)
            
    ax_circle.text(0.5, 0.75, f"{total_played}/20", color='#a3a8b5', fontsize=16, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.65, "TOTAL WINRATE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.48, f"{win_rate}%", color=accent_color, fontsize=65, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.32, "PREDICTIONS MADE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')
    
    badge = patches.FancyBboxPatch((0.30, 0.16), 0.40, 0.08, boxstyle="round,pad=0.03", fc="#164e63", ec=accent_color, lw=1.5)
    ax_circle.add_patch(badge)
    ax_circle.text(0.5, 0.20, f"ACTIVE ✓", color=accent_color, fontsize=11, fontweight='bold', ha='center', va='center')
    
    ax_circle.text(0.05, 0.05, "0", color='#7a8294', fontsize=12, fontweight='bold', ha='center')
    ax_circle.text(0.95, 0.05, "100%", color='#7a8294', fontsize=12, fontweight='bold', ha='center')

    fig.text(0.74, 0.85, "SESSION PERFORMANCE TREND", color='#a3a8b5', fontsize=14, fontweight='bold', ha='center')
    
    ax_bar = fig.add_axes([0.55, 0.47, 0.38, 0.33])
    ax_bar.set_facecolor('#1c1f26')
    ax_bar.set_xlim(-0.5, 19.5)
    ax_bar.set_ylim(0, 105) 
    
    ax_bar.spines['top'].set_visible(False)
    ax_bar.spines['right'].set_visible(False)
    ax_bar.spines['left'].set_visible(False)
    ax_bar.spines['bottom'].set_visible(False)
    
    ax_bar.set_yticks([0, 25, 50, 75, 100])
    ax_bar.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#7a8294', fontsize=10, fontweight='bold') 
    ax_bar.tick_params(axis='y', length=0, pad=5)
    ax_bar.grid(axis='y', color='#2c313c', linestyle='-', linewidth=1.5)
    
    if total_played > 0:
        x_pos = np.arange(total_played)
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.8, alpha=0.15, zorder=2, align='center')
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.45, alpha=0.9, zorder=3, align='center')
        ax_bar.plot(x_pos, history_wr, color=accent_color, linewidth=2.5, marker='o', markersize=6, markerfacecolor='#1c1f26', markeredgecolor=accent_color, markeredgewidth=2, zorder=4)
        
    ax_bar.set_xticks(np.arange(20))
    ax_bar.set_xticklabels([str(i+1) for i in range(20)], color='#7a8294', fontsize=10)

    ax_win = fig.add_axes([0.05, 0.22, 0.28, 0.16])
    ax_win.set_axis_off()
    ax_win.set_xlim(0, 1)
    ax_win.set_ylim(0, 1)
    rect_win = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#1de9b6", ec="none")
    ax_win.add_patch(rect_win)
    ax_win.text(0.1, 0.75, "TOTAL WINS:", color='#004d40', fontsize=16, fontweight='bold', va='center')
    ax_win.text(0.1, 0.35, f"{wins}", color='#000000', fontsize=48, fontweight='bold', va='center')

    ax_lose = fig.add_axes([0.35, 0.22, 0.28, 0.16])
    ax_lose.set_axis_off()
    ax_lose.set_xlim(0, 1)
    ax_lose.set_ylim(0, 1)
    rect_lose = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#ef5350", ec="none")
    ax_lose.add_patch(rect_lose)
    ax_lose.text(0.1, 0.75, "TOTAL LOSSES:", color='#4d0000', fontsize=16, fontweight='bold', va='center')
    ax_lose.text(0.1, 0.35, f"{losses}", color='#ffffff', fontsize=48, fontweight='bold', va='center')

    ax_wm = fig.add_axes([0.65, 0.22, 0.30, 0.16])
    ax_wm.set_axis_off()
    ax_wm.text(0.5, 0.5, "VIRTUAL BET", color='#ffd700', fontsize=22, fontweight='bold', style='italic', ha='center', va='center')
    ax_wm.plot([0.1, 0.9], [0.30, 0.30], color='#ffd700', lw=3)
    ax_wm.plot([0.1, 0.9], [0.70, 0.70], color='#ffd700', lw=3)

    fig.text(0.05, 0.16, "FULL PREDICTION TIMELINE", color='#a3a8b5', fontsize=12, fontweight='bold', ha='left')
    
    ax_time = fig.add_axes([0.05, 0.05, 0.9, 0.08])
    ax_time.set_axis_off()
    ax_time.set_xlim(-0.5, 19.5)
    ax_time.set_ylim(0, 1)
    
    if len(dots_list) > 0:
        for i, (char, color) in enumerate(dots_list):
            ax_time.scatter(i, 0.5, s=800, c=color, edgecolors='none', zorder=4, alpha=0.3) 
            ax_time.scatter(i, 0.5, s=400, c=color, edgecolors='none', zorder=5, alpha=1.0)
            ax_time.text(i, 0.5, char, color='#ffffff', fontsize=14, fontweight='bold', ha='center', va='center', zorder=6)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1c1f26') 
    buf.seek(0)
    plt.close(fig)
    return buf

# ==========================================
# 🚀 8. CORE LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE
    global LAST_NOTIFIED_ISSUE, CURRENT_AI_MODE, ACTIVE_USERS, PREDICTION_ACTIVE
    
    if not PREDICTION_ACTIVE:
        return False
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return False

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': '9ef85244056948ba8dcae7aee7758bf4', 
        'signature': '2EDB8C2B5264F62EC53116916A9EC05C',
        'timestamp': int(time.time()),
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data)
    
    if data and data.get('code') == 0:
        records = data.get("data", {}).get("list", [])
        
        if records:
            latest_record = records[0]
            latest_issue = str(latest_record["issueNumber"])
            latest_number = int(latest_record["number"])
            latest_size = "BIG" if latest_number >= 5 else "SMALL"
            
            is_new_issue = False
            if not LAST_PROCESSED_ISSUE or int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                is_new_issue = True
            
            if is_new_issue:
                LAST_PROCESSED_ISSUE = latest_issue
                if not SESSION_START_ISSUE:
                    SESSION_START_ISSUE = latest_issue
                
                await history_collection.update_one(
                    {"issue_number": latest_issue}, 
                    {"$setOnInsert": {"number": latest_number, "size": latest_size}},
                    upsert=True
                )
                
                settled = await settle_bets(latest_issue, latest_size, latest_number, "WINGO_30S")
                if settled > 0:
                    print(f"💰 Settled {settled} bets for {latest_issue} - {latest_number} ({latest_size})")
                
                next_issue = str(int(latest_issue) + 1)
                
                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)

                predicted_size, predicted_display, final_prob, reason = await asyncio.to_thread(get_prediction, history_docs, CURRENT_AI_MODE)
                
                await predictions_collection.update_one(
                    {"issue_number": next_issue}, 
                    {"$set": {"predicted_size": predicted_size, "ai_mode": CURRENT_AI_MODE}}, 
                    upsert=True
                )

                for user_id in list(ACTIVE_USERS):
                    try:
                        user = await get_user_balance(user_id)
                        recent_bets = await bets_collection.find({"user_id": user_id}).sort("created_at", -1).limit(10).to_list(length=10)
                        
                        lose_streak = 0
                        for bet in recent_bets:
                            if bet["result"] == "LOSE":
                                lose_streak += 1
                            else:
                                break
                        
                        martingale_seq = [100, 300, 900, 2700, 8100]
                        bet_amount = martingale_seq[min(lose_streak, len(martingale_seq)-1)]
                        
                        if user["balance"] >= bet_amount:
                            bet_result = await place_bet(user_id, next_issue, bet_amount, predicted_size, CURRENT_AI_MODE)
                            if bet_result["success"]:
                                ai_emoji = AI_MODES.get(CURRENT_AI_MODE, {}).get("name", "").split()[0]
                                order_msg = (
                                    #f"📝 <b>Order Placed!</b>\n"
                                   # f"━━━━━━━━━━━━━━━━━━\n"
                                    f"{Emoji.GAME} <b>WINGO_30S</b> : <code>{next_issue}</code>\n"
                                    f"{Emoji.BAR_CHART} <b>Order:</b> {predicted_size} | {bet_amount:,.0f} Ks\n"
                                    f"{Emoji.BRAIN} <b>Strategy:</b> {ai_emoji} {CURRENT_AI_MODE.upper()}\n"
                                   # f"━━━━━━━━━━━━━━━━━━\n"
                                    #f"{Emoji.INFO} <i>ရလဒ်ထွက်သည်နှင့် အကြောင်းကြားပေးပါမည်...</i>"
                                )
                                try:
                                    await bot.send_message(chat_id=user_id, text=order_msg)
                                except:
                                    pass
                    except Exception as e:
                        print(f"Auto-bet error for {user_id}: {e}")

                await update_channel_post(next_issue, predicted_display, final_prob, reason)
                return True 
        return False
        
    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()): 
        CURRENT_TOKEN = ""
        return False

async def update_channel_post(next_issue, predicted_display, final_prob, reason):
    global MAIN_MESSAGE_ID, CURRENT_AI_MODE, SESSION_START_ISSUE
    
    try:
        pred_cursor = predictions_collection.find({
            "issue_number": {"$gte": SESSION_START_ISSUE},
            "win_lose": {"$ne": None}
        }).sort("issue_number", -1)
        
        session_preds = await pred_cursor.to_list(length=20) 
        
        table_str = "<code>Period    | Result  | W/L\n"
        table_str += "----------|---------|----\n"
        for p in session_preds[:10]: 
            iss = p.get('issue_number', '0000000')
            iss_short = f"{iss[:3]}**{iss[-4:]}" 
            act_size = p.get('actual_size', 'BIG')
            act_num = p.get('actual_number', 0)
            res_str = f"{act_num}-{act_size}"
            wl_str = "✅" if "WIN" in p.get("win_lose", "") else "❌"
            table_str += f"{iss_short:<10}| {res_str:<7} | {wl_str}\n"
        table_str += "</code>"

        img_buf = await asyncio.to_thread(generate_winrate_chart, session_preds, CURRENT_AI_MODE)
        photo = BufferedInputFile(img_buf.read(), filename=f"chart_{int(time.time())}.png")
        
        sec_left = 30 - (int(time.time()) % 30)
        iss_display = f"{next_issue[:3]}**{next_issue[-4:]}"
        
        ai_emoji = AI_MODES.get(CURRENT_AI_MODE, {}).get("name", "")
        
        tg_caption = (
            f"<b>🏆 WIN GO (30 SECONDS)</b>\n"
            f"{Emoji.CLOCK} Next Result In: <b>{sec_left}s</b>\n\n"
            f"{table_str}\n"
            f"{Emoji.GAME} <b>Period:</b> {iss_display}\n"
            f"{ai_emoji} <b>AI ခန့်မှန်းချက် : {predicted_display}</b>\n"
            f"{Emoji.BAR_CHART} <b>ဖြစ်နိုင်ခြေ : {final_prob}%</b>\n"
            f"{Emoji.INFO} <b>အကြောင်းပြချက် :</b>\n{reason}"
        )
        
        if MAIN_MESSAGE_ID:
            try:
                media = InputMediaPhoto(media=photo, caption=tg_caption, parse_mode="HTML")
                await bot.edit_message_media(chat_id=CHANNEL_ID, message_id=MAIN_MESSAGE_ID, media=media)
            except:
                msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                MAIN_MESSAGE_ID = msg.message_id
        else:
            msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
            MAIN_MESSAGE_ID = msg.message_id
    except Exception as e:
        print(f"Channel update error: {e}")

# ==========================================
# ⏱️ 9. SCHEDULER
# ==========================================
async def auto_broadcaster():
    await init_db()
    await load_sudo_users()
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            current_time = time.time()
            sec_passed = int(current_time) % 30
            
            if PREDICTION_ACTIVE and 5 <= sec_passed <= 28:
                try:
                    is_processed = await check_game_and_predict(session)
                    if is_processed:
                        sleep_time = 30 - (int(time.time()) % 30)
                        await asyncio.sleep(sleep_time)
                        continue 
                except Exception as e:
                    pass
            
            await asyncio.sleep(0.5) 

# ==========================================
# 🤖 10. COMMANDS
# ==========================================
@dp.message(Command("start"))
@require_auth
async def send_welcome(message: types.Message):
    is_auth, level = await check_permission(message.from_user.id)
    level_emoji = Emoji.OWNER if level == "owner" else Emoji.SUDO
    
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    
    await message.reply(
        f"{Emoji.SPARKLES} <b>WIN GO AI Bot v3.0</b> {Emoji.SPARKLES}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{level_emoji} <b>Level:</b> {level.upper()}\n"
        f"{Emoji.MONEY} <b>လက်ကျန်:</b> {user['balance']:,.0f} Ks\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Status:</b> {'✅ Active' if is_active else '❌ Inactive'}\n\n"
        f"{Emoji.ROBOT} <b>AI Modes (၁၂ မျိုး):</b>\n"
        f"{Emoji.PATTERN} Pattern | {Emoji.MARTINGALE} Martingale | {Emoji.ANTIMARTINGALE} Anti-Martingale\n"
        f"{Emoji.TREND} Trend Follow | {Emoji.FIBONACCI} Fibonacci | {Emoji.GOLDEN} Golden Ratio\n"
        f"{Emoji.MOMENTUM} Momentum | {Emoji.MONTECARLO} Monte Carlo | {Emoji.NEURAL} Neural\n"
        f"{Emoji.REVERSAL} Quick Reversal | {Emoji.WAVE} Wave | {Emoji.CHAOS} Chaos\n\n"
        f"{Emoji.GAME} <b>Commands:</b>\n"
        f"<code>.active</code> - Auto-bet စတင်ရန်\n"
        f"<code>.stop</code> - Auto-bet ရပ်ရန်\n"
        f"<code>.bet 100</code> - Manual လောင်းရန်\n"
        f"<code>.bal</code> - လက်ကျန်ကြည့်ရန်\n"
        f"<code>.addbal 50000</code> - ငွေထည့်ရန်\n"
        f"<code>.withdraw 50000</code> - ငွေပြန်နှုတ်ရန်\n"
        f"/mode - AI Mode ပြောင်းရန်\n"
        f"/compare - AI Mode နှိုင်းယှဉ်ရန်\n"
        f"/status - အခြေအနေကြည့်ရန်\n"
        f"/top - {Emoji.CROWN} Top 10"
    )

@dp.message(lambda message: message.text and message.text.lower() == '.active')
@require_auth
async def activate_user(message: types.Message):
    global ACTIVE_USERS, PREDICTION_ACTIVE
    
    user_id = message.from_user.id
    
    if user_id in ACTIVE_USERS:
        await message.reply(f"{Emoji.CHECK} သင့်အကောင့်သည် Auto-Bet Active ဖြစ်ပြီးသားပါ!")
        return
    
    ACTIVE_USERS.add(user_id)
    PREDICTION_ACTIVE = True
    
    await active_sessions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"active": True, "activated_at": datetime.now(), "ai_mode": CURRENT_AI_MODE}},
        upsert=True
    )
    
    user = await get_user_balance(user_id)
    ai_emoji = AI_MODES.get(CURRENT_AI_MODE, {}).get("name", "")
    
    await message.reply(
        f"{Emoji.CHECK} <b>Auto-Bet Activated!</b>\n\n"
        f"{Emoji.GAME} <b>Game:</b> WINGO 30S\n"
        f"{ai_emoji} <b>AI Mode:</b> {CURRENT_AI_MODE.upper()}\n"
        f"{Emoji.MONEY} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{Emoji.MONEY_BAG} <b>Bet Sequence:</b> 100 {Emoji.UP} 300 {Emoji.UP} 900 {Emoji.UP} 2,700 {Emoji.UP} 8,100\n\n"
        f"{Emoji.INFO} ရလဒ်ထွက်တိုင်း Private Message ပို့ပေးပါမည်။\n"
        f"{Emoji.OFFLINE} ရပ်ရန်: <code>.stop</code>"
    )

@dp.message(lambda message: message.text and message.text.lower() == '.stop')
@require_auth
async def deactivate_user(message: types.Message):
    global ACTIVE_USERS, PREDICTION_ACTIVE
    
    user_id = message.from_user.id
    
    if user_id not in ACTIVE_USERS:
        await message.reply(f"{Emoji.CROSS} Auto-Bet Active မဖြစ်သေးပါ! <code>.active</code> ဖြင့်စတင်ပါ။")
        return
    
    ACTIVE_USERS.discard(user_id)
    
    await active_sessions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"active": False, "stopped_at": datetime.now()}},
        upsert=True
    )
    
    if not ACTIVE_USERS:
        PREDICTION_ACTIVE = False
    
    user = await get_user_balance(user_id)
    profit_emoji = Emoji.CHART_UP if user['profit'] > 0 else Emoji.CHART_DOWN
    
    await message.reply(
        f"{Emoji.OFFLINE} <b>Auto-Bet Stopped!</b>\n\n"
        f"{Emoji.MONEY} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{profit_emoji} <b>Profit:</b> {user['profit']:,.2f} Ks\n"
        f"{Emoji.FIRE} <b>Best Streak:</b> {user.get('best_streak', 0)}\n\n"
        f"{Emoji.ONLINE} ပြန်စရန်: <code>.active</code>"
    )

@dp.message(Command("mode"))
@require_auth
async def change_mode(message: types.Message):
    global CURRENT_AI_MODE
    
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.PATTERN} Pattern", callback_data="mode_pattern"),
        InlineKeyboardButton(text=f"{Emoji.MARTINGALE} Martingale", callback_data="mode_martingale"),
    )
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.ANTIMARTINGALE} Anti-Martingale", callback_data="mode_anti_martingale"),
        InlineKeyboardButton(text=f"{Emoji.TREND} Trend Follow", callback_data="mode_trend_following"),
    )
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.FIBONACCI} Fibonacci", callback_data="mode_fibonacci"),
        InlineKeyboardButton(text=f"{Emoji.GOLDEN} Golden Ratio", callback_data="mode_golden_ratio"),
    )
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.MOMENTUM} Momentum", callback_data="mode_momentum"),
        InlineKeyboardButton(text=f"{Emoji.MONTECARLO} Monte Carlo", callback_data="mode_monte_carlo"),
    )
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.NEURAL} Neural Pattern", callback_data="mode_neural_pattern"),
        InlineKeyboardButton(text=f"{Emoji.REVERSAL} Quick Reversal", callback_data="mode_quick_reversal"),
    )
    builder.row(
        InlineKeyboardButton(text=f"{Emoji.WAVE} Wave Analysis", callback_data="mode_wave_analysis"),
        InlineKeyboardButton(text=f"{Emoji.CHAOS} Chaos Theory", callback_data="mode_chaos_theory"),
    )
    
    current_mode_name = AI_MODES.get(CURRENT_AI_MODE, {}).get("name", "Unknown")
    
    await message.reply(
        f"{Emoji.ROBOT} <b>AI Mode ပြောင်းလဲရန်</b>\n\n"
        f"📌 လက်ရှိ Mode: <b>{current_mode_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 အောက်မှ ရွေးချယ်ပါ:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def process_mode_selection(callback: types.CallbackQuery):
    global CURRENT_AI_MODE
    
    is_auth, _ = await check_permission(callback.from_user.id)
    if not is_auth:
        await callback.answer(f"{Emoji.LOCK} Access Denied!", show_alert=True)
        return
    
    mode_key = callback.data.replace("mode_", "")
    
    if mode_key in AI_MODES:
        CURRENT_AI_MODE = mode_key
        await settings_collection.update_one({"key": "ai_mode"}, {"$set": {"value": mode_key}}, upsert=True)
        mode_name = AI_MODES[mode_key]["name"]
        
        await callback.message.edit_text(
            f"{Emoji.CHECK} <b>AI Mode ပြောင်းလဲပြီးပါပြီ!</b>\n\n"
            f"{Emoji.ROBOT} လက်ရှိ Mode: <b>{mode_name}</b>\n"
            f"{Emoji.INFO} <b>Strategy:</b> {AI_MODES[mode_key]['desc']}\n\n"
            f"{Emoji.ONLINE} ပြန်ပြောင်းရန်: /mode"
        )
        await callback.answer(f"{Emoji.CHECK} ပြောင်းလဲပြီးပါပြီ!")

@dp.message(Command("compare"))
@require_auth
async def compare_ai_modes(message: types.Message):
    cursor = history_collection.find().sort("issue_number", -1).limit(100)
    history_docs = await cursor.to_list(length=100)
    
    if len(history_docs) < 20:
        await message.reply(f"{Emoji.CROSS} နှိုင်းယှဉ်ရန် ဒေတာအလုံအလောက်မရှိသေးပါ။")
        return
    
    test_docs = history_docs[:80]
    results = {}
    
    for mode_key, mode_info in AI_MODES.items():
        correct = total = 0
        for i in range(len(test_docs) - 10):
            segment = test_docs[i+10:i:-1]
            if len(segment) >= 10:
                try:
                    pred_size, _, _, _ = mode_info["func"](segment)
                    if pred_size == test_docs[i].get("size", "BIG"):
                        correct += 1
                    total += 1
                except:
                    pass
        accuracy = (correct / total * 100) if total > 0 else 0
        results[mode_key] = {"name": mode_info["name"], "accuracy": accuracy, "correct": correct, "total": total}
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]["accuracy"], reverse=True)
    
    compare_text = f"{Emoji.BAR_CHART} <b>AI MODE COMPARISON</b>\n"
    compare_text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (mode_key, data) in enumerate(sorted_results, 1):
        medal = Emoji.GOLD if i == 1 else Emoji.SILVER if i == 2 else Emoji.BRONZE if i == 3 else f"{i}."
        current = f" {Emoji.STAR}" if mode_key == CURRENT_AI_MODE else ""
        compare_text += f"{medal} {data['name']}{current}\n"
        compare_text += f"   {Emoji.BAR_CHART} {data['accuracy']:.1f}% ({data['correct']}/{data['total']})\n"
    
    compare_text += f"\n━━━━━━━━━━━━━━━━━━\n{Emoji.INFO} အကောင်းဆုံး Mode: /mode"
    await message.reply(compare_text)

@dp.message(Command("status"))
@require_auth
async def show_status(message: types.Message):
    is_auth, level = await check_permission(message.from_user.id)
    level_emoji = Emoji.OWNER if level == "owner" else Emoji.SUDO
    
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    
    pending_bets = await bets_collection.count_documents({"user_id": message.from_user.id, "result": None})
    recent_bets = await bets_collection.find({"user_id": message.from_user.id}).sort("created_at", -1).limit(5).to_list(length=5)
    
    recent_str = ""
    for bet in recent_bets:
        emoji = "⏳" if bet["result"] is None else (Emoji.CHECK if bet["result"] == "WIN" else Emoji.CROSS)
        recent_str += f"{emoji} {bet['issue_number']}: {bet['bet_amount']:,.0f}K on {bet['predicted_size']}\n"
    
    profit_emoji = Emoji.CHART_UP if user['profit'] > 0 else Emoji.CHART_DOWN if user['profit'] < 0 else "➖"
    
    await message.reply(
        f"{Emoji.BAR_CHART} <b>SYSTEM STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{level_emoji} <b>Level:</b> {level.upper()}\n"
        f"{AI_MODES.get(CURRENT_AI_MODE, {}).get('name', 'Unknown')}\n"
        f"{Emoji.GAME} Last: {LAST_PROCESSED_ISSUE or 'N/A'}\n"
        f"{Emoji.ONLINE if PREDICTION_ACTIVE else Emoji.OFFLINE} System: {'Active' if PREDICTION_ACTIVE else 'Idle'}\n"
        f"👥 Users: {len(ACTIVE_USERS)} | {Emoji.SHIELD} Sudo: {len(SUDO_USERS)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Status:</b> {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.MONEY} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{Emoji.CHECK} Wins: {user['total_wins']} | {Emoji.CROSS} Losses: {user['total_losses']}\n"
        f"{profit_emoji} <b>Profit:</b> {user['profit']:,.2f} Ks\n"
        f"{Emoji.FIRE} Best Streak: {user.get('best_streak', 0)}\n"
        f"⏳ Pending: {pending_bets}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.GAME} <b>Recent:</b>\n{recent_str or 'မရှိသေးပါ'}"
    )

@dp.message(Command("top"))
@require_auth
async def show_leaderboard(message: types.Message):
    leaderboard = await get_leaderboard(10)
    
    if not leaderboard:
        await message.reply(f"{Emoji.INFO} ဒေတာမရှိသေးပါ။")
        return
    
    top_text = f"{Emoji.CROWN} <b>TOP 10 ချမ်းသာသူများ</b>\n"
    top_text += "━━━━━━━━━━━━━━━━━━\n"
    
    for i, user in enumerate(leaderboard, 1):
        medal = Emoji.GOLD if i == 1 else Emoji.SILVER if i == 2 else Emoji.BRONZE if i == 3 else f"{i}."
        wr = (user['total_wins'] / user['total_bets'] * 100) if user['total_bets'] > 0 else 0
        profit_e = Emoji.CHART_UP if user.get('profit', 0) > 0 else Emoji.CHART_DOWN
        top_text += f"{medal} <code>{user['user_id']}</code>\n"
        top_text += f"   {Emoji.MONEY} {user['balance']:,.0f} Ks | {profit_e} {user.get('profit', 0):,.0f} | {Emoji.BAR_CHART} {wr:.1f}%\n"
    
    await message.reply(top_text)

@dp.message(lambda message: message.text and message.text.startswith('.bet'))
@require_auth
async def place_bet_command(message: types.Message):
    global LAST_PROCESSED_ISSUE, CURRENT_AI_MODE
    
    if not BETTING_ENABLED:
        await message.reply(f"{Emoji.OFFLINE} Virtual Betting ပိတ်ထားပါသည်။")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>.bet 100</code> or <code>.bet 100-300-900</code>")
            return
        
        bet_params = parts[1]
        
        if '-' in bet_params:
            bet_amounts = [float(x.strip()) for x in bet_params.split('-')]
            recent_bets = await bets_collection.find({"user_id": message.from_user.id}).sort("created_at", -1).limit(10).to_list(length=10)
            lose_streak = sum(1 for b in recent_bets if b.get("result") == "LOSE")
            bet_amount = bet_amounts[min(lose_streak, len(bet_amounts)-1)]
            streak_info = f"📉 Streak: {lose_streak} {Emoji.UP} {bet_amount:,.0f} Ks"
        else:
            bet_amount = float(bet_params)
            streak_info = ""
        
        if not LAST_PROCESSED_ISSUE:
            await message.reply(f"{Emoji.CROSS} ဒေတာမရသေးပါ။")
            return
        
        next_issue = str(int(LAST_PROCESSED_ISSUE) + 1)
        cursor = history_collection.find().sort("issue_number", -1).limit(5000)
        history_docs = await cursor.to_list(length=5000)
        predicted_size, _, _, _ = get_prediction(history_docs, CURRENT_AI_MODE)
        
        result = await place_bet(message.from_user.id, next_issue, bet_amount, predicted_size, CURRENT_AI_MODE)
        
        if result["success"]:
            ai_emoji = AI_MODES.get(CURRENT_AI_MODE, {}).get("name", "").split()[0]
            await message.reply(
               # f"📝 <b>Order Placed!</b>\n"
                #f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME} <b>WINGO_30S</b> : <code>{next_issue}</code>\n"
                f"{Emoji.BAR_CHART} <b>Order:</b> {predicted_size} | {bet_amount:,.0f} Ks\n"
                f"{Emoji.BRAIN} <b>Strategy:</b> {ai_emoji} {CURRENT_AI_MODE.upper()}\n"
                f"{streak_info}\n"
               # f"━━━━━━━━━━━━━━━━━━\n"
               # f"{Emoji.INFO} <i>ရလဒ်ထွက်သည်နှင့် အကြောင်းကြားပေးပါမည်...</i>"
            )
        else:
            await message.reply(result["message"])
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(lambda message: message.text and message.text.startswith('.bal'))
@require_auth
async def check_balance(message: types.Message):
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    wr = (user['total_wins'] / user['total_bets'] * 100) if user['total_bets'] > 0 else 0
    profit_e = Emoji.CHART_UP if user['profit'] > 0 else Emoji.CHART_DOWN if user['profit'] < 0 else "➖"
    
    await message.reply(
        f"{Emoji.MONEY} <b>သင့်အကောင့်</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Status:</b> {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.MONEY_BAG} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
        f"{Emoji.GAME} <b>Total Bets:</b> {user['total_bets']}\n"
        f"{Emoji.CHECK} Wins: {user['total_wins']} | {Emoji.CROSS} Losses: {user['total_losses']}\n"
        f"{Emoji.BAR_CHART} <b>Win Rate:</b> {wr:.1f}%\n"
        f"{Emoji.GEM} Wagered: {user['total_wagered']:,.0f} Ks\n"
        f"{Emoji.COIN} Won: {user['total_won']:,.0f} Ks\n"
        f"{profit_e} <b>Profit:</b> {user['profit']:,.2f} Ks\n"
        f"{Emoji.FIRE} Best Streak: {user.get('best_streak', 0)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.INFO} <code>.addbal 50000</code> | <code>.withdraw 50000</code>"
    )

@dp.message(lambda message: message.text and message.text.startswith('.addbal'))
@require_auth
async def add_balance(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>.addbal 50000</code>")
            return
        
        amount = float(parts[1])
        if amount <= 0 or amount > 1000000:
            await message.reply(f"{Emoji.CROSS} 1 - 1,000,000 Ks အတွင်းသာထည့်ပါ။")
            return
        
        user = await update_balance(message.from_user.id, amount, "add")
        await message.reply(
            f"{Emoji.CHECK} <b>ငွေထည့်ပြီးပါပြီ!</b>\n\n"
            f"{Emoji.MONEY_BAG} +{amount:,.0f} Ks\n"
            f"{Emoji.MONEY} Balance: {user['balance']:,.0f} Ks"
        )
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(lambda message: message.text and message.text.startswith('.withdraw'))
@require_auth
async def withdraw_balance(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>.withdraw 50000</code> or <code>.withdraw all</code>")
            return
        
        user = await get_user_balance(message.from_user.id)
        
        if parts[1].lower() == "all":
            amount = user['balance']
            if amount <= 0:
                await message.reply(f"{Emoji.CROSS} နှုတ်ယူရန် လက်ကျန်ငွေမရှိပါ!")
                return
        else:
            amount = float(parts[1])
            if amount <= 0:
                await message.reply(f"{Emoji.CROSS} ငွေပမာဏသည် 0 ထက်ကြီးရပါမည်။")
                return
        
        if amount > user['balance']:
            await message.reply(f"{Emoji.CROSS} လက်ကျန်ငွေ မလုံလောက်ပါ!")
            return
        
        await update_balance(message.from_user.id, amount, "subtract")
        updated_user = await get_user_balance(message.from_user.id)
        
        await message.reply(
            f"{Emoji.CHECK} <b>ငွေပြန်နှုတ်ပြီးပါပြီ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{Emoji.MONEY_BAG} နှုတ်ယူငွေ: <b>-{amount:,.0f} Ks</b>\n"
            f"{Emoji.MONEY} လက်ကျန်ငွေ: <b>{updated_user['balance']:,.0f} Ks</b>"
        )
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(Command("mybets"))
@require_auth
async def show_my_bets(message: types.Message):
    bets = await bets_collection.find({"user_id": message.from_user.id}).sort("created_at", -1).limit(10).to_list(length=10)
    
    if not bets:
        await message.reply(f"{Emoji.INFO} မှတ်တမ်းမရှိသေးပါ။")
        return
    
    text = f"{Emoji.GAME} <b>လောင်းကြေးမှတ်တမ်း</b>\n━━━━━━━━━━━━━━━━━━\n"
    for bet in bets:
        if bet["result"] is None:
            status = "⏳ Pending"
        elif bet["result"] == "WIN":
            status = f"{Emoji.CHECK} +{bet['profit']:,.0f} Ks"
        else:
            status = f"{Emoji.CROSS} -{bet['bet_amount']:,.0f} Ks"
        text += f"{bet['issue_number']}: {bet['bet_amount']:,.0f}K on {bet['predicted_size']} {Emoji.UP} {status}\n"
    
    await message.reply(text)

# ==========================================
# 🛡️ 11. OWNER & SUDO MANAGEMENT COMMANDS
# ==========================================

@dp.message(Command("addsudo"))
@require_owner
async def add_sudo_command(message: types.Message):
    """Owner အတွက် - Sudo User ထည့်ရန်"""
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/addsudo [user_id]</code>")
            return
        
        target_id = int(parts[1])
        
        if str(target_id) == str(OWNER_ID):
            await message.reply(f"{Emoji.CROSS} Owner ကို Sudo ထည့်၍မရပါ!")
            return
        
        if target_id in SUDO_USERS:
            await message.reply(f"{Emoji.CROSS} ဤ User သည် Sudo ဖြစ်ပြီးသားပါ!")
            return
        
        success = await add_sudo_user(target_id, message.from_user.id)
        
        if success:
            await message.reply(
                f"{Emoji.CHECK} <b>Sudo User ထည့်ပြီးပါပြီ!</b>\n\n"
                f"{Emoji.SHIELD} User: <code>{target_id}</code>\n"
                f"{Emoji.INFO} ယခု Bot ကိုအသုံးပြုခွင့်ရပါပြီ။"
            )
            
            try:
                await bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"{Emoji.SPARKLES} <b>Congratulations!</b>\n\n"
                        f"{Emoji.SHIELD} သင့်အား Sudo User အဖြစ်ထည့်သွင်းလိုက်ပါပြီ!\n"
                        f"{Emoji.KEY} ယခု Bot ကိုအသုံးပြုခွင့်ရပါပြီ။\n\n"
                        f"{Emoji.INFO} /start ဖြင့်စတင်ပါ။"
                    )
                )
            except:
                pass
        else:
            await message.reply(f"{Emoji.CROSS} ထည့်၍မရပါ!")
            
    except ValueError:
        await message.reply(f"{Emoji.CROSS} User ID ဂဏန်းသာထည့်ပါ။")

@dp.message(Command("delsudo"))
@require_owner
async def remove_sudo_command(message: types.Message):
    """Owner အတွက် - Sudo User ဖယ်ရှားရန်"""
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/delsudo [user_id]</code>")
            return
        
        target_id = int(parts[1])
        
        if target_id not in SUDO_USERS:
            await message.reply(f"{Emoji.CROSS} ဤ User သည် Sudo မဟုတ်ပါ!")
            return
        
        await remove_sudo_user(target_id)
        
        await message.reply(
            f"{Emoji.CHECK} <b>Sudo User ဖယ်ရှားပြီးပါပြီ!</b>\n\n"
            f"{Emoji.BANNED} User: <code>{target_id}</code>\n"
            f"{Emoji.INFO} ယခု Bot ကိုအသုံးပြုခွင့်မရတော့ပါ။"
        )
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=(
                    f"{Emoji.WARNING} <b>Notice!</b>\n\n"
                    f"{Emoji.BANNED} သင့်အား Sudo User မှဖယ်ရှားလိုက်ပါပြီ။\n"
                    f"{Emoji.INFO} ယခု Bot ကိုအသုံးပြုခွင့်မရတော့ပါ။"
                )
            )
        except:
            pass
            
    except ValueError:
        await message.reply(f"{Emoji.CROSS} User ID ဂဏန်းသာထည့်ပါ။")

@dp.message(Command("sudolist"))
@require_owner
async def list_sudo_users(message: types.Message):
    """Owner အတွက် - Sudo Users စာရင်းကြည့်ရန်"""
    global SUDO_USERS
    
    if not SUDO_USERS:
        await message.reply(f"{Emoji.INFO} Sudo Users မရှိသေးပါ။")
        return
    
    sudo_list = f"{Emoji.SHIELD} <b>SUDO USERS LIST</b>\n"
    sudo_list += "━━━━━━━━━━━━━━━━━━\n"
    
    for i, user_id in enumerate(SUDO_USERS, 1):
        sudo_list += f"{i}. <code>{user_id}</code>\n"
    
    sudo_list += f"━━━━━━━━━━━━━━━━━━\n"
    sudo_list += f"📊 Total: <b>{len(SUDO_USERS)}</b> Sudo Users\n"
    sudo_list += f"\n{Emoji.INFO} <code>/addsudo [id]</code> | <code>/delsudo [id]</code>"
    
    await message.reply(sudo_list)

@dp.message(Command("setbal"))
@require_owner
async def set_balance(message: types.Message):
    """Owner အတွက် - ငွေပမာဏ သတ်မှတ်ရန်"""
    try:
        parts = message.text.split()
        
        if len(parts) == 2:
            amount = float(parts[1])
            if amount < 0:
                await message.reply(f"{Emoji.CROSS} 0 သို့မဟုတ် အပေါင်းကိန်းဖြစ်ရပါမည်။")
                return
            user = await update_balance(message.from_user.id, amount, "set")
            await message.reply(f"{Emoji.CHECK} လက်ကျန်ငွေ: <b>{user['balance']:,.0f} Ks</b>")
        elif len(parts) == 3:
            target_id = int(parts[1])
            amount = float(parts[2])
            if amount < 0:
                await message.reply(f"{Emoji.CROSS} 0 သို့မဟုတ် အပေါင်းကိန်းဖြစ်ရပါမည်။")
                return
            user = await update_balance(target_id, amount, "set")
            await message.reply(f"{Emoji.CHECK} User <code>{target_id}</code>\nလက်ကျန်: <b>{user['balance']:,.0f} Ks</b>")
        else:
            await message.reply(f"{Emoji.INFO} <code>/setbal 50000</code> or <code>/setbal [id] 50000</code>")
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(Command("give"))
@require_owner
async def give_money(message: types.Message):
    """Owner အတွက် - အခြားသူကိုငွေထည့်ပေးရန်"""
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply(f"{Emoji.INFO} <code>/give [user_id] [amount]</code>")
            return
        
        target_id = int(parts[1])
        amount = float(parts[2])
        
        if amount <= 0:
            await message.reply(f"{Emoji.CROSS} 0 ထက်ကြီးရပါမည်။")
            return
        
        receiver = await update_balance(target_id, amount, "add")
        
        await message.reply(
            f"{Emoji.CHECK} <b>ငွေထည့်ပေးပြီးပါပြီ!</b>\n\n"
            f"👤 User: <code>{target_id}</code>\n"
            f"{Emoji.MONEY_BAG} +{amount:,.0f} Ks\n"
            f"{Emoji.MONEY} Balance: {receiver['balance']:,.0f} Ks"
        )
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎁 <b>ငွေထည့်ပေးခြင်းခံရပါသည်!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{Emoji.MONEY_BAG} +{amount:,.0f} Ks\n"
                    f"{Emoji.MONEY} Balance: {receiver['balance']:,.0f} Ks\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{Emoji.CROWN} Owner မှ ထည့်ပေးခြင်းဖြစ်ပါသည်။"
                )
            )
        except:
            pass
    except ValueError:
        await message.reply(f"{Emoji.CROSS} <code>/give [user_id] [amount]</code>")

@dp.message(Command("reset"))
@require_owner
async def reset_user_stats(message: types.Message):
    """Owner အတွက် - User statistics ပြန်လည်သတ်မှတ်ရန်"""
    try:
        parts = message.text.split()
        
        if len(parts) == 1:
            target_id = message.from_user.id
        elif len(parts) == 2:
            target_id = int(parts[1])
        else:
            await message.reply(f"{Emoji.INFO} <code>/reset</code> or <code>/reset [user_id]</code>")
            return
        
        await users_collection.update_one(
            {"user_id": target_id},
            {"$set": {
                "total_bets": 0, "total_wins": 0, "total_losses": 0,
                "total_wagered": 0.0, "total_won": 0.0, "profit": 0.0,
                "win_streak": 0, "lose_streak": 0, "best_streak": 0
            }}
        )
        
        await bets_collection.delete_many({"user_id": target_id})
        user = await get_user_balance(target_id)
        
        await message.reply(
            f"{Emoji.CHECK} <b>Statistics ပြန်လည်သတ်မှတ်ပြီးပါပြီ!</b>\n\n"
            f"👤 User: <code>{target_id}</code>\n"
            f"{Emoji.MONEY} Balance: <b>{user['balance']:,.0f} Ks</b>\n"
            f"{Emoji.INFO} Stats & Bet History ဖျက်လိုက်ပါပြီ။"
        )
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(Command("broadcast"))
@require_owner
async def broadcast_message(message: types.Message):
    """Owner အတွက် - Active users အားလုံးကို message ပို့ရန်"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/broadcast [message]</code>")
            return
        
        broadcast_text = parts[1]
        
        # Get all users who have used the bot
        all_users = await users_collection.find().to_list(length=None)
        user_ids = [u["user_id"] for u in all_users]
        
        success = 0
        failed = 0
        
        for uid in user_ids:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"{Emoji.SPARKLES} <b>BROADCAST</b> {Emoji.SPARKLES}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"{broadcast_text}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"{Emoji.CROWN} Owner Message"
                    )
                )
                success += 1
            except:
                failed += 1
            await asyncio.sleep(0.05)
        
        await message.reply(
            f"{Emoji.CHECK} <b>Broadcast Sent!</b>\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}"
        )
        
    except Exception as e:
        await message.reply(f"{Emoji.CROSS} Error: {str(e)}")

@dp.message(Command("togglebet"))
@require_owner
async def toggle_betting(message: types.Message):
    global BETTING_ENABLED
    
    BETTING_ENABLED = not BETTING_ENABLED
    await settings_collection.update_one(
        {"key": "betting_enabled"},
        {"$set": {"value": BETTING_ENABLED}},
        upsert=True
    )
    
    status = f"{Emoji.ONLINE} ON" if BETTING_ENABLED else f"{Emoji.OFFLINE} OFF"
    await message.reply(f"{Emoji.BET} Virtual Betting: <b>{status}</b>")

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        await settings_collection.create_index("key", unique=True)
        await users_collection.create_index("user_id", unique=True)
        await bets_collection.create_index([("user_id", 1), ("issue_number", 1)])
        await active_sessions_collection.create_index("user_id", unique=True)
        await sudo_collection.create_index("user_id", unique=True)
        
        setting = await settings_collection.find_one({"key": "ai_mode"})
        global CURRENT_AI_MODE
        if setting:
            CURRENT_AI_MODE = setting.get("value", "pattern")
        
        bet_setting = await settings_collection.find_one({"key": "betting_enabled"})
        global BETTING_ENABLED
        if bet_setting:
            BETTING_ENABLED = bet_setting.get("value", True)
        
        global ACTIVE_USERS
        active_cursor = active_sessions_collection.find({"active": True})
        active_docs = await active_cursor.to_list(length=None)
        ACTIVE_USERS = {doc["user_id"] for doc in active_docs}
        
        global PREDICTION_ACTIVE
        if ACTIVE_USERS:
            PREDICTION_ACTIVE = True
        
        print(f"{Emoji.CHECK} MongoDB Connected")
        print(f"{Emoji.ROBOT} Mode: {CURRENT_AI_MODE} | {Emoji.BET} Betting: {'ON' if BETTING_ENABLED else 'OFF'}")
        print(f"👥 Active: {len(ACTIVE_USERS)} | {Emoji.SHIELD} Sudo: {len(SUDO_USERS)}")
    except Exception as e:
        print(f"DB Init Error: {e}")

async def main():
    print(f"\n{Emoji.SPARKLES} WIN GO AI Bot v3.0 - Owner & Sudo System {Emoji.SPARKLES}")
    print(f"{Emoji.CROWN} Owner: {OWNER_ID}")
    print(f"{Emoji.LOCK} Only Owner & Sudo Users can access this bot!")
    print(f"{Emoji.ROBOT} 12 AI Modes | {Emoji.MONEY} Virtual Balance | {Emoji.SHIELD} Permission System\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print(f"\n{Emoji.OFFLINE} Bot Stopped")
