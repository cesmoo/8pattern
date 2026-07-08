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
active_sessions_collection = db['active_sessions']  # Track active users

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
ACTIVE_USERS = set()  # Set of user IDs who activated with .active
PREDICTION_ACTIVE = False  # Global prediction active status

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        await settings_collection.create_index("key", unique=True)
        await users_collection.create_index("user_id", unique=True)
        await bets_collection.create_index([("user_id", 1), ("issue_number", 1)])
        await active_sessions_collection.create_index("user_id", unique=True)
        
        # Load saved AI mode
        setting = await settings_collection.find_one({"key": "ai_mode"})
        global CURRENT_AI_MODE
        if setting:
            CURRENT_AI_MODE = setting.get("value", "pattern")
        
        # Load betting enabled status
        bet_setting = await settings_collection.find_one({"key": "betting_enabled"})
        global BETTING_ENABLED
        if bet_setting:
            BETTING_ENABLED = bet_setting.get("value", True)
        
        # Load active users from DB
        global ACTIVE_USERS
        active_cursor = active_sessions_collection.find({"active": True})
        active_docs = await active_cursor.to_list(length=None)
        ACTIVE_USERS = {doc["user_id"] for doc in active_docs}
        
        global PREDICTION_ACTIVE
        if ACTIVE_USERS:
            PREDICTION_ACTIVE = True
        
        print(f"🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
        print(f"🎯 Mode: {CURRENT_AI_MODE} | 🎰 Betting: {'ON' if BETTING_ENABLED else 'OFF'}")
        print(f"👥 Active Users: {len(ACTIVE_USERS)} | System: {'🟢 RUNNING' if PREDICTION_ACTIVE else '🔴 IDLE'}")
    except Exception as e:
        print(f"DB Init Error: {e}")

# ==========================================
# 💰 3. VIRTUAL BALANCE SYSTEM
# ==========================================
async def get_user_balance(user_id: int) -> dict:
    """Get user balance and stats"""
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
            "created_at": datetime.now()
        }
        await users_collection.insert_one(user)
    return user

async def update_balance(user_id: int, amount: float, operation: str = "add") -> dict:
    """Update user balance"""
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
    """Place a virtual bet"""
    user = await get_user_balance(user_id)
    
    if user["balance"] < bet_amount:
        return {"success": False, "message": f"❌ လက်ကျန်ငွေ မလုံလောက်ပါ!\n💰 Balance: {user['balance']:,.0f} Ks\n💵 လောင်းကြေး: {bet_amount:,.0f} Ks"}
    
    existing_bet = await bets_collection.find_one({"user_id": user_id, "issue_number": issue_number})
    if existing_bet:
        return {"success": False, "message": f"❌ Period {issue_number} အတွက် လောင်းပြီးသားဖြစ်ပါသည်!"}
    
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
        "created_at": datetime.now()
    }
    
    await bets_collection.insert_one(bet)
    
    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"total_bets": 1, "total_wagered": bet_amount}}
    )
    
    return {
        "success": True, 
        "message": f"✅ လောင်းကြေးထည့်ပြီးပါပြီ!",
        "balance": user['balance'] - bet_amount
    }

async def settle_bets(issue_number: str, actual_size: str, actual_number: int, game_type: str = "WINGO_30S"):
    """Settle all pending bets and send notifications"""
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
                        "profit": profit
                    }
                }
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
                        "profit": profit
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
        
        # Send result notification to user
        await send_bet_result_notification(user_id, bet, actual_size, actual_number, game_type, is_win, payout, profit)
        
        settled_count += 1
    
    return settled_count

async def send_bet_result_notification(user_id: int, bet: dict, actual_size: str, actual_number: int, game_type: str, is_win: bool, payout: float, profit: float):
    """Send detailed bet result to user"""
    try:
        user = await get_user_balance(user_id)
        
        # Color determination
        color_map = {
            0: "🟣 VIOLET", 1: "🟢 GREEN", 2: "🔴 RED", 
            3: "🟢 GREEN", 4: "🔴 RED", 5: "🟢 GREEN",
            6: "🔴 RED", 7: "🟢 GREEN", 8: "🔴 RED", 9: "🟢 GREEN"
        }
        color = color_map.get(actual_number, "⚪ WHITE")
        
        if is_win:
            # WIN notification
            message = (
                f"✅ <b>WIN!</b> +{profit:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎮 <b>{game_type}</b> : <code>{bet['issue_number']}</code>\n"
                f"📊 <b>Result:</b> {actual_number} • {actual_size} • {color}\n"
                f"💰 <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"📈 <b>Profit:</b> +{user['profit']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🤖 AI: {bet['ai_mode'].upper()}\n"
                f"💵 Bet: {bet['bet_amount']:,.0f} Ks on {bet['predicted_size']}"
            )
        else:
            # LOSE notification
            message = (
                f"❌ <b>LOSE!</b> -{bet['bet_amount']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎮 <b>{game_type}</b> : <code>{bet['issue_number']}</code>\n"
                f"📊 <b>Result:</b> {actual_number} • {actual_size} • {color}\n"
                f"💰 <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"📉 <b>Profit:</b> {user['profit']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🤖 AI: {bet['ai_mode'].upper()}\n"
                f"💵 Bet: {bet['bet_amount']:,.0f} Ks on {bet['predicted_size']}"
            )
        
        await bot.send_message(chat_id=user_id, text=message)
        
    except Exception as e:
        print(f"Failed to send notification to {user_id}: {e}")

async def get_leaderboard(limit: int = 10) -> list:
    """Get top users by balance"""
    cursor = users_collection.find().sort("balance", -1).limit(limit)
    return await cursor.to_list(length=limit)

# ==========================================
# 🔑 4. ASYNC API FUNCTIONS
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
        print("✅ Login အောင်မြင်ပါသည်။\n")
        return True
    return False

# ==========================================
# 🧠 5. PATTERN DETECTION & AI LOGIC
# ==========================================
def detect_active_pattern(history_list):
    if len(history_list) < 4:
        return None, "No Pattern"
    
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
        ("BB", ["BIG", "BIG"]),
        ("SS", ["SMALL", "SMALL"]),
    ]
    
    recent = history_list[-10:]
    
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
                "BBB": "BIG", "SSS": "SMALL",
                "BB": "BIG", "SS": "SMALL"
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
        return "BIG", "BIG (အကြီး) 🔴", 55.0, "⏳ Pattern detection အတွက် data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    active_pattern, next_pred = detect_active_pattern(all_history)
    
    if active_pattern:
        if next_pred == "BIG":
            predicted_size = "BIG"
            predicted_display = "BIG (အကြီး) 🔴"
            prob = 75.0
            reason = f"🎯 Active Pattern: {active_pattern} → နောက်ထွက်မည့်ဟာ: BIG"
        else:
            predicted_size = "SMALL"
            predicted_display = "SMALL (အသေး) 🟢"
            prob = 75.0
            reason = f"🎯 Active Pattern: {active_pattern} → နောက်ထွက်မည့်ဟာ: SMALL"
    else:
        b_count = all_history.count("BIG")
        s_count = all_history.count("SMALL")
        if b_count > s_count:
            predicted_size = "BIG"
            predicted_display = "BIG (အကြီး) 🔴"
        else:
            predicted_size = "SMALL"
            predicted_display = "SMALL (အသေး) 🟢"
        prob = 55.0
        reason = "🔍 Pattern မတွေ့ပါ - အများစုထွက်ရာကို ရွေးထားသည်"
    
    return predicted_size, predicted_display, prob, reason

def martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", "BIG (အကြီး) 🔴", 60.0, "🎲 Martingale: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    recent_10 = all_history[-10:]
    big_count = recent_10.count("BIG")
    small_count = recent_10.count("SMALL")
    
    if big_count > small_count:
        predicted_size = "SMALL"
        predicted_display = "SMALL (အသေး) 🟢"
        prob = 65.0
        reason = f"🎲 Martingale: BIG {big_count}vs SMALL {small_count} → SMALL ထွက်ရန်အလားအလာများ"
    else:
        predicted_size = "BIG"
        predicted_display = "BIG (အကြီး) 🔴"
        prob = 65.0
        reason = f"🎲 Martingale: BIG {big_count}vs SMALL {small_count} → BIG ထွက်ရန်အလားအလာများ"
    
    return predicted_size, predicted_display, prob, reason

def anti_martingale_predict(history_docs):
    if len(history_docs) < 5:
        return "BIG", "BIG (အကြီး) 🔴", 60.0, "🔄 Anti-Martingale: Data စုဆောင်းဆဲ..."
    
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    recent_5 = all_history[-5:]
    big_streak = 0
    small_streak = 0
    
    for result in reversed(recent_5):
        if result == "BIG":
            big_streak += 1
            small_streak = 0
        else:
            small_streak += 1
            big_streak = 0
    
    if big_streak >= 2:
        predicted_size = "BIG"
        predicted_display = "BIG (အကြီး) 🔴"
        prob = 70.0
        reason = f"🔄 Anti-Martingale: BIG {big_streak} ပွဲဆက်ထွက်နေ → BIG ဆက်ထွက်ရန်"
    elif small_streak >= 2:
        predicted_size = "SMALL"
        predicted_display = "SMALL (အသေး) 🟢"
        prob = 70.0
        reason = f"🔄 Anti-Martingale: SMALL {small_streak} ပွဲဆက်ထွက်နေ → SMALL ဆက်ထွက်ရန်"
    else:
        last_result = all_history[-1] if all_history else "BIG"
        if last_result == "BIG":
            predicted_size = "BIG"
            predicted_display = "BIG (အကြီး) 🔴"
        else:
            predicted_size = "SMALL"
            predicted_display = "SMALL (အသေး) 🟢"
        prob = 60.0
        reason = "🔄 Anti-Martingale: နောက်ဆုံးထွက်သည့်အတိုင်း လိုက်ထိုးသည်"
    
    return predicted_size, predicted_display, prob, reason

def get_prediction(history_docs, mode):
    if mode == "pattern":
        return pattern_predict(history_docs)
    elif mode == "martingale":
        return martingale_predict(history_docs)
    elif mode == "anti_martingale":
        return anti_martingale_predict(history_docs)
    else:
        return pattern_predict(history_docs)

# ==========================================
# 🎨 6. GRAPH GENERATOR
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

    if ai_mode == "pattern":
        accent_color = '#00e5ff'
        mode_label = "PATTERN AI"
    elif ai_mode == "martingale":
        accent_color = '#ff9800'
        mode_label = "MARTINGALE AI"
    else:
        accent_color = '#9c27b0'
        mode_label = "ANTI-MARTINGALE AI"

    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26') 
    
    fig.text(0.05, 0.93, f"🎯 {mode_label} PERFORMANCE", color='#ffffff', fontsize=28, fontweight='bold', ha='left')
    fig.text(0.05, 0.88, f"MODE: {ai_mode.upper()}", color=accent_color, fontsize=16, fontweight='bold', ha='left')

    if user_data:
        balance = user_data.get('balance', 0)
        total_wins = user_data.get('total_wins', 0)
        total_losses = user_data.get('total_losses', 0)
        fig.text(0.95, 0.93, f"💰 {balance:,.0f} Ks", color='#ffd700', fontsize=14, fontweight='bold', ha='right')
        fig.text(0.95, 0.88, f"✅{total_wins} ❌{total_losses}", color='#a3a8b5', fontsize=12, fontweight='bold', ha='right')

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
    ax_circle.text(0.5, 0.20, f"{mode_label} ✓", color=accent_color, fontsize=11, fontweight='bold', ha='center', va='center')
    
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
    circ_win = plt.Circle((0.85, 0.5), 0.22, color='none', ec='#004d40', lw=3)
    ax_win.add_patch(circ_win)
    ax_win.text(0.85, 0.5, "✓", color='#004d40', fontsize=28, fontweight='bold', ha='center', va='center')

    ax_lose = fig.add_axes([0.35, 0.22, 0.28, 0.16])
    ax_lose.set_axis_off()
    ax_lose.set_xlim(0, 1)
    ax_lose.set_ylim(0, 1)
    rect_lose = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#ef5350", ec="none")
    ax_lose.add_patch(rect_lose)
    ax_lose.text(0.1, 0.75, "TOTAL LOSSES:", color='#4d0000', fontsize=16, fontweight='bold', va='center')
    ax_lose.text(0.1, 0.35, f"{losses}", color='#ffffff', fontsize=48, fontweight='bold', va='center')
    shield = patches.RegularPolygon((0.85, 0.5), numVertices=6, radius=0.25, orientation=np.pi/6, color='none', ec='#4d0000', lw=3)
    ax_lose.add_patch(shield)

    ax_wm = fig.add_axes([0.65, 0.22, 0.30, 0.16])
    ax_wm.set_axis_off()
    ax_wm.text(0.5, 0.5, "VIRTUAL BET", color='#ffd700', fontsize=22, fontweight='bold', style='italic', ha='center', va='center')
    ax_wm.plot([0.1, 0.9], [0.30, 0.30], color='#ffd700', lw=3)
    ax_wm.plot([0.1, 0.9], [0.70, 0.70], color='#ffd700', lw=3)

    fig.text(0.05, 0.16, "FULL PREDICTION TIMELINE (Oldest to Latest)", color='#a3a8b5', fontsize=12, fontweight='bold', ha='left')
    
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
# 🚀 7. CORE LOGIC
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
            latest_parity = "EVEN" if latest_number % 2 == 0 else "ODD"
            
            is_new_issue = False
            if not LAST_PROCESSED_ISSUE:
                is_new_issue = True
            elif int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                is_new_issue = True
            
            if is_new_issue:
                LAST_PROCESSED_ISSUE = latest_issue
                if not SESSION_START_ISSUE:
                    SESSION_START_ISSUE = latest_issue
                
                await history_collection.update_one(
                    {"issue_number": latest_issue}, 
                    {"$setOnInsert": {
                        "number": latest_number, "size": latest_size, 
                        "parity": latest_parity, "time_context": "CURRENT"
                    }}, upsert=True
                )
                
                # Settle bets and send notifications to active users
                settled = await settle_bets(latest_issue, latest_size, latest_number, "WINGO_30S")
                if settled > 0:
                    print(f"💰 Settled {settled} bets for issue {latest_issue} - Result: {latest_number} ({latest_size})")
                
                pred_doc = await predictions_collection.find_one({"issue_number": latest_issue})
                if pred_doc and pred_doc.get("predicted_size"):
                    db_predicted_size = pred_doc.get("predicted_size")
                    clean_predicted = "BIG" if "BIG" in db_predicted_size else "SMALL"
                    is_win = (clean_predicted == latest_size)
                    win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                    await predictions_collection.update_one(
                        {"issue_number": latest_issue}, 
                        {"$set": {
                            "actual_size": latest_size, 
                            "actual_number": latest_number, 
                            "win_lose": win_lose_status,
                            "ai_mode": pred_doc.get("ai_mode", CURRENT_AI_MODE)
                        }}
                    )

                next_issue = str(int(latest_issue) + 1)
                
                # Session Check 
                current_session_count = await predictions_collection.count_documents({
                    "issue_number": {"$gte": SESSION_START_ISSUE}, 
                    "win_lose": {"$ne": None}
                })
                
                if current_session_count >= 20: 
                    SESSION_START_ISSUE = next_issue
                
                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)

                # Get prediction
                try:
                    predicted_size, predicted_display, final_prob, reason = await asyncio.to_thread(get_prediction, history_docs, CURRENT_AI_MODE)
                except Exception as e:
                    predicted_size = "BIG"
                    predicted_display = "BIG (အကြီး) 🔴"
                    final_prob = 55.0
                    reason = f"⚠️ AI Processing Error"
                
                await predictions_collection.update_one(
                    {"issue_number": next_issue}, 
                    {"$set": {
                        "predicted_size": predicted_size,
                        "ai_mode": CURRENT_AI_MODE
                    }}, 
                    upsert=True
                )

                # Auto-bet for active users
                for user_id in list(ACTIVE_USERS):
                    try:
                        user = await get_user_balance(user_id)
                        # Get user's recent bets to determine streak
                        recent_bets = await bets_collection.find({
                            "user_id": user_id
                        }).sort("created_at", -1).limit(10).to_list(length=10)
                        
                        lose_streak = 0
                        for bet in recent_bets:
                            if bet["result"] == "LOSE":
                                lose_streak += 1
                            else:
                                break
                        
                        # Default martingale sequence: 100-300-900-2700-8100
                        martingale_seq = [100, 300, 900, 2700, 8100]
                        if lose_streak >= len(martingale_seq):
                            bet_amount = martingale_seq[-1]
                        else:
                            bet_amount = martingale_seq[lose_streak]
                        
                        # Check if user has enough balance
                        if user["balance"] >= bet_amount:
                            bet_result = await place_bet(user_id, next_issue, bet_amount, predicted_size, CURRENT_AI_MODE)
                            if bet_result["success"]:
                                # Send order confirmation
                                order_msg = (
                                    f"📝 <b>Order Placed!</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🎮 <b>WINGO_30S</b> : <code>{next_issue}</code>\n"
                                    f"📊 <b>Order:</b> {predicted_size} | {bet_amount:,.0f} Ks\n"
                                    f"🧠 <b>Strategy:</b> {CURRENT_AI_MODE.upper()} AI Prediction\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"💡 <i>ရလဒ်ထွက်သည်နှင့် အကြောင်းကြားပေးပါမည်...</i>"
                                )
                                try:
                                    await bot.send_message(chat_id=user_id, text=order_msg)
                                except:
                                    pass
                    except Exception as e:
                        print(f"Auto-bet error for user {user_id}: {e}")

                # Channel update (keep channel posting)
                await update_channel_post(next_issue, predicted_display, final_prob, reason)
                
                return True 
        return False
        
    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()): 
        CURRENT_TOKEN = ""
        return False

async def update_channel_post(next_issue, predicted_display, final_prob, reason):
    """Update channel with prediction"""
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
        
        tg_caption = (
            f"<b>🏆 WIN GO (30 SECONDS)</b>\n"
            f"⏰ Next Result In: <b>{sec_left}s</b>\n\n"
            f"{table_str}\n"
            f"🅿️ <b>Period:</b> {iss_display}\n"
            f"🤖 <b>AI ခန့်မှန်းချက် : {predicted_display}</b>\n"
            f"📈 <b>ဖြစ်နိုင်ခြေ : {final_prob}%</b>\n"
            f"💡 <b>အကြောင်းပြချက် :</b>\n{reason}"
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
# ⏱️ 8. TIME TRIGGER SCHEDULER
# ==========================================
async def auto_broadcaster():
    await init_db() 
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
# 🤖 9. COMMANDS
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    
    await message.reply(
        f"👋 <b>မင်္ဂလာပါ! WIN GO AI Bot မှကြိုဆိုပါတယ်။</b>\n\n"
        f"💰 <b>သင့်လက်ကျန်:</b> {user['balance']:,.0f} Ks\n"
        f"🟢 <b>Active Status:</b> {'✅ Active' if is_active else '❌ Inactive'}\n\n"
        f"🤖 <b>AI Mode များ:</b>\n"
        f"🎯 Pattern AI - Pattern အတိုင်း Auto-Switch\n"
        f"🎲 Martingale AI - ရှုံးတိုင်း 2x တိုး\n"
        f"🔄 Anti-Martingale AI - နိုင်တိုင်း 2x တိုး\n\n"
        f"📋 <b>Commands:</b>\n"
        f"<code>.active</code> - Auto-bet စတင်ရန်\n"
        f"<code>.stop</code> - Auto-bet ရပ်ရန်\n"
        f"<code>.bet 100</code> - Manual လောင်းရန်\n"
        f"<code>.bal</code> - လက်ကျန်ကြည့်ရန်\n"
        f"<code>.addbal 50000</code> - ငွေထည့်ရန်\n"
        f"/mode - AI Mode ပြောင်းရန်\n"
        f"/status - အခြေအနေကြည့်ရန်\n"
        f"/top - Top 10 ချမ်းသာသူများ"
    )

@dp.message(lambda message: message.text and message.text.lower() == '.active')
async def activate_user(message: types.Message):
    global ACTIVE_USERS, PREDICTION_ACTIVE
    
    user_id = message.from_user.id
    
    if user_id in ACTIVE_USERS:
        await message.reply("✅ သင့်အကောင့်သည် Auto-Bet Active ဖြစ်ပြီးသားပါ!")
        return
    
    ACTIVE_USERS.add(user_id)
    PREDICTION_ACTIVE = True
    
    # Save to DB
    await active_sessions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"active": True, "activated_at": datetime.now(), "ai_mode": CURRENT_AI_MODE}},
        upsert=True
    )
    
    user = await get_user_balance(user_id)
    
    await message.reply(
        f"✅ <b>Auto-Bet Activated!</b>\n\n"
        f"🎮 <b>Game:</b> WINGO 30S\n"
        f"🤖 <b>AI Mode:</b> {CURRENT_AI_MODE.upper()}\n"
        f"💰 <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"💵 <b>Bet Sequence:</b> 100 → 300 → 900 → 2,700 → 8,100\n\n"
        f"📊 ရလဒ်ထွက်တိုင်း Private Message ပို့ပေးပါမည်။\n"
        f"🛑 ရပ်ရန်: <code>.stop</code>"
    )

@dp.message(lambda message: message.text and message.text.lower() == '.stop')
async def deactivate_user(message: types.Message):
    global ACTIVE_USERS, PREDICTION_ACTIVE
    
    user_id = message.from_user.id
    
    if user_id not in ACTIVE_USERS:
        await message.reply("❌ သင့်အကောင့်သည် Auto-Bet Active မဖြစ်သေးပါ! <code>.active</code> ဖြင့်စတင်ပါ။")
        return
    
    ACTIVE_USERS.discard(user_id)
    
    # Update DB
    await active_sessions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"active": False, "stopped_at": datetime.now()}},
        upsert=True
    )
    
    if not ACTIVE_USERS:
        PREDICTION_ACTIVE = False
    
    user = await get_user_balance(user_id)
    
    await message.reply(
        f"🛑 <b>Auto-Bet Stopped!</b>\n\n"
        f"💰 <b>Final Balance:</b> {user['balance']:,.0f} Ks\n"
        f"📈 <b>Total Profit:</b> {user['profit']:,.2f} Ks\n\n"
        f"🔄 ပြန်စရန်: <code>.active</code>"
    )

@dp.message(Command("mode"))
async def change_mode(message: types.Message):
    global CURRENT_AI_MODE
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Pattern AI", callback_data="mode_pattern"),
        InlineKeyboardButton(text="🎲 Martingale AI", callback_data="mode_martingale"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Anti-Martingale AI", callback_data="mode_anti_martingale")
    )
    
    current_mode_name = {
        "pattern": "🎯 Pattern AI (Auto-Switch)",
        "martingale": "🎲 Martingale AI",
        "anti_martingale": "🔄 Anti-Martingale AI"
    }
    
    await message.reply(
        f"🤖 <b>AI Mode ပြောင်းလဲရန်</b>\n\n"
        f"📌 လက်ရှိ Mode: <b>{current_mode_name.get(CURRENT_AI_MODE, 'Unknown')}</b>\n\n"
        f"👇 အောက်မှ ရွေးချယ်ပါ:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("mode_"))
async def process_mode_selection(callback: types.CallbackQuery):
    global CURRENT_AI_MODE
    
    mode_map = {
        "mode_pattern": "pattern",
        "mode_martingale": "martingale",
        "mode_anti_martingale": "anti_martingale"
    }
    
    selected_mode = mode_map.get(callback.data)
    if selected_mode:
        CURRENT_AI_MODE = selected_mode
        
        await settings_collection.update_one(
            {"key": "ai_mode"},
            {"$set": {"value": selected_mode}},
            upsert=True
        )
        
        mode_names = {
            "pattern": "🎯 Pattern AI (Auto-Switch)",
            "martingale": "🎲 Martingale AI",
            "anti_martingale": "🔄 Anti-Martingale AI"
        }
        
        await callback.message.edit_text(
            f"✅ <b>AI Mode ပြောင်းလဲပြီးပါပြီ!</b>\n\n"
            f"🤖 လက်ရှိ Mode: <b>{mode_names[selected_mode]}</b>\n\n"
            f"🔄 ပြန်ပြောင်းရန်: /mode"
        )
        await callback.answer(f"✅ {mode_names[selected_mode]} သို့ပြောင်းပြီးပါပြီ!")

@dp.message(Command("status"))
async def show_status(message: types.Message):
    global CURRENT_AI_MODE, LAST_PROCESSED_ISSUE, ACTIVE_USERS, PREDICTION_ACTIVE
    
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    
    mode_names = {
        "pattern": "🎯 Pattern AI",
        "martingale": "🎲 Martingale AI",
        "anti_martingale": "🔄 Anti-Martingale AI"
    }
    
    pending_bets = await bets_collection.count_documents({
        "user_id": message.from_user.id,
        "result": None
    })
    
    recent_bets = await bets_collection.find({
        "user_id": message.from_user.id
    }).sort("created_at", -1).limit(5).to_list(length=5)
    
    recent_bets_str = ""
    if recent_bets:
        for bet in recent_bets:
            result_emoji = "⏳" if bet["result"] is None else ("✅" if bet["result"] == "WIN" else "❌")
            recent_bets_str += f"{result_emoji} {bet['issue_number']}: {bet['bet_amount']:,.0f} Ks on {bet['predicted_size']}\n"
    else:
        recent_bets_str = "မရှိသေးပါ"
    
    status_text = (
        f"📊 <b>SYSTEM STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AI Mode:</b> {mode_names.get(CURRENT_AI_MODE, 'Unknown')}\n"
        f"🅿️ <b>Last Processed:</b> {LAST_PROCESSED_ISSUE or 'N/A'}\n"
        f"🟢 <b>System Active:</b> {'✅' if PREDICTION_ACTIVE else '❌'}\n"
        f"👥 <b>Active Users:</b> {len(ACTIVE_USERS)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>YOUR STATS</b>\n"
        f"🟢 <b>Status:</b> {'✅ Active' if is_active else '❌ Inactive'}\n"
        f"💰 <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"🎯 <b>Total Bets:</b> {user['total_bets']}\n"
        f"✅ <b>Wins:</b> {user['total_wins']} | ❌ <b>Losses:</b> {user['total_losses']}\n"
        f"📈 <b>Profit:</b> {user['profit']:,.2f} Ks\n"
        f"⏳ <b>Pending:</b> {pending_bets}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Recent:</b>\n{recent_bets_str}"
    )
    
    await message.reply(status_text)

@dp.message(Command("top"))
async def show_leaderboard(message: types.Message):
    leaderboard = await get_leaderboard(10)
    
    if not leaderboard:
        await message.reply("📊 ဒေတာမရှိသေးပါ။")
        return
    
    top_text = "🏆 <b>TOP 10 ချမ်းသာသူများ</b>\n"
    top_text += "━━━━━━━━━━━━━━━━━━\n"
    
    for i, user in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        win_rate = (user['total_wins'] / user['total_bets'] * 100) if user['total_bets'] > 0 else 0
        profit_emoji = "📈" if user.get('profit', 0) > 0 else "📉"
        top_text += f"{medal} <code>{user['user_id']}</code>\n"
        top_text += f"   💰 {user['balance']:,.0f} Ks | {profit_emoji} {user.get('profit', 0):,.0f} | 📊 {win_rate:.1f}%\n"
    
    await message.reply(top_text)

# ==========================================
# 💰 10. VIRTUAL BETTING COMMANDS
# ==========================================
@dp.message(lambda message: message.text and message.text.startswith('.bet'))
async def place_bet_command(message: types.Message):
    global LAST_PROCESSED_ISSUE, CURRENT_AI_MODE
    
    if not BETTING_ENABLED:
        await message.reply("❌ Virtual Betting ကို ယာယီပိတ်ထားပါသည်။")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(
                "❌ <b>အသုံးပြုနည်း:</b>\n"
                "<code>.bet 100</code> - တစ်ဆင့်ထိုးရန်\n"
                "<code>.bet 100-300-900</code> - Martingale ထိုးရန်"
            )
            return
        
        bet_params = parts[1]
        
        if '-' in bet_params:
            bet_amounts = [float(x.strip()) for x in bet_params.split('-')]
            recent_bets = await bets_collection.find({
                "user_id": message.from_user.id
            }).sort("created_at", -1).limit(10).to_list(length=10)
            
            lose_streak = 0
            for bet in recent_bets:
                if bet["result"] == "LOSE":
                    lose_streak += 1
                else:
                    break
            
            if lose_streak >= len(bet_amounts):
                bet_amount = bet_amounts[-1]
            else:
                bet_amount = bet_amounts[lose_streak]
            
            streak_info = f"📉 ရှုံးပွဲဆက်: {lose_streak} → လောင်းကြေး: {bet_amount:,.0f} Ks"
        else:
            bet_amount = float(bet_params)
            streak_info = ""
        
        if not LAST_PROCESSED_ISSUE:
            await message.reply("❌ ဂိမ်းဒေတာမရသေးပါ။ ခဏစောင့်ပါ။")
            return
        
        next_issue = str(int(LAST_PROCESSED_ISSUE) + 1)
        
        cursor = history_collection.find().sort("issue_number", -1).limit(5000)
        history_docs = await cursor.to_list(length=5000)
        predicted_size, _, _, _ = get_prediction(history_docs, CURRENT_AI_MODE)
        
        result = await place_bet(
            message.from_user.id,
            next_issue,
            bet_amount,
            predicted_size,
            CURRENT_AI_MODE
        )
        
        if result["success"]:
            order_msg = (
                f"📝 <b>Order Placed!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎮 <b>WINGO_30S</b> : <code>{next_issue}</code>\n"
                f"📊 <b>Order:</b> {predicted_size} | {bet_amount:,.0f} Ks\n"
                f"🧠 <b>Strategy:</b> {CURRENT_AI_MODE.upper()} AI Prediction\n"
                f"{streak_info}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>ရလဒ်ထွက်သည်နှင့် အကြောင်းကြားပေးပါမည်...</i>"
            )
            await message.reply(order_msg)
        else:
            await message.reply(result["message"])
        
    except ValueError:
        await message.reply("❌ ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(lambda message: message.text and message.text.startswith('.bal'))
async def check_balance(message: types.Message):
    user = await get_user_balance(message.from_user.id)
    is_active = message.from_user.id in ACTIVE_USERS
    
    total_bets = user['total_bets']
    if total_bets > 0:
        win_rate = (user['total_wins'] / total_bets) * 100
    else:
        win_rate = 0
    
    profit_emoji = "📈" if user['profit'] > 0 else "📉" if user['profit'] < 0 else "➖"
    
    await message.reply(
        f"💰 <b>သင့်အကောင့်</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Status:</b> {'✅ Active' if is_active else '❌ Inactive'}\n"
        f"💵 <b>Balance:</b> {user['balance']:,.2f} Ks\n"
        f"🎯 <b>Total Bets:</b> {total_bets}\n"
        f"✅ <b>Wins:</b> {user['total_wins']} | ❌ <b>Losses:</b> {user['total_losses']}\n"
        f"📊 <b>Win Rate:</b> {win_rate:.1f}%\n"
        f"💎 <b>Wagered:</b> {user['total_wagered']:,.0f} Ks\n"
        f"🏆 <b>Won:</b> {user['total_won']:,.0f} Ks\n"
        f"{profit_emoji} <b>Profit:</b> {user['profit']:,.2f} Ks\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <code>.addbal 50000</code> - ငွေထည့်ရန်"
    )

@dp.message(lambda message: message.text and message.text.startswith('.addbal'))
async def add_balance(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌ <b>အသုံးပြုနည်း:</b> <code>.addbal 50000</code>")
            return
        
        amount = float(parts[1])
        if amount <= 0:
            await message.reply("❌ ငွေပမာဏသည် 0 ထက်ကြီးရပါမည်။")
            return
        
        if amount > 1000000:
            await message.reply("❌ တစ်ကြိမ်လျှင် ၁,၀၀၀,၀၀၀ Ks ထက်မပိုပါ။")
            return
        
        user = await update_balance(message.from_user.id, amount, "add")
        
        await message.reply(
            f"✅ <b>ငွေထည့်ပြီးပါပြီ!</b>\n\n"
            f"💵 ထည့်ငွေ: +{amount:,.0f} Ks\n"
            f"💰 လက်ကျန်ငွေ: {user['balance']:,.0f} Ks"
        )
        
    except ValueError:
        await message.reply("❌ ဂဏန်းများသာ ထည့်ပါ။")

@dp.message(Command("mybets"))
async def show_my_bets(message: types.Message):
    recent_bets = await bets_collection.find({
        "user_id": message.from_user.id
    }).sort("created_at", -1).limit(10).to_list(length=10)
    
    if not recent_bets:
        await message.reply("📋 လောင်းထားမှုမရှိသေးပါ။")
        return
    
    bet_text = "📋 <b>လောင်းကြေးမှတ်တမ်း</b>\n"
    bet_text += "━━━━━━━━━━━━━━━━━━\n"
    
    for bet in recent_bets:
        if bet["result"] is None:
            status = "⏳ Pending"
        elif bet["result"] == "WIN":
            status = f"✅ +{bet['profit']:,.0f} Ks"
        else:
            status = f"❌ -{bet['bet_amount']:,.0f} Ks"
        
        bet_text += f"🅿️ {bet['issue_number']}: {bet['bet_amount']:,.0f}K on {bet['predicted_size']} → {status}\n"
    
    await message.reply(bet_text)

@dp.message(Command("togglebet"))
async def toggle_betting(message: types.Message):
    global BETTING_ENABLED
    
    if str(message.from_user.id) != str(OWNER_ID):
        await message.reply("❌ Owner သာ ဤ command ကိုသုံးခွင့်ရှိသည်။")
        return
    
    BETTING_ENABLED = not BETTING_ENABLED
    
    await settings_collection.update_one(
        {"key": "betting_enabled"},
        {"$set": {"value": BETTING_ENABLED}},
        upsert=True
    )
    
    status = "🟢 ON" if BETTING_ENABLED else "🔴 OFF"
    await message.reply(f"🎰 Virtual Betting: <b>{status}</b>")

async def main():
    print("🚀 WIN GO AI Bot (Private Auto-Bet System) စတင်နေပါပြီ...\n")
    print("💰 Virtual Balance System Activated!")
    print("🤖 Auto-Bet: .active | .stop")
    print("📊 Commands: .bet .bal .addbal .top .mybets")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
