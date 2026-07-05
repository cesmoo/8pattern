import asyncio
import time
import os
import io
import json
import hashlib
import random
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, InputMediaPhoto

# --- GRAPHICS ---
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import warnings
warnings.filterwarnings("ignore")

# ==========================================
# ⚙️ LOAD ENVIRONMENT
# ==========================================
load_dotenv()

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME", "959680090540")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = os.getenv("OWNER_ID")

# Browser Token
BROWSER_TOKEN = os.getenv("BROWSER_TOKEN", "")

# Debug Mode
DEBUG = True

if not all([BOT_TOKEN, CHANNEL_ID, MONGO_URI, OWNER_ID]):
    print("❌ Error: .env file missing required variables")
    exit()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# MongoDB
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database']
history_collection = db['game_history']
predictions_collection = db['predictions']

# ==========================================
# 🔧 SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None
SESSION_START_ISSUE = None
LAST_NOTIFIED_ISSUE = None

# ==========================================
# 🎯 AUTO BET STATE
# ==========================================
AUTO_BET = {
    "enabled": False,
    "last_bet_issue": None,
    "bet_count": 0,
    "win_count": 0,
    "loss_count": 0,
    "total_profit": 0,
    "current_streak": 0,
    "max_streak": 0,
    "martingale_level": 0,
    "base_amount": 1,
    "max_bets": 0,
    "game_type": "1min",
    "status": "idle"
}

BET_HISTORY = []

# ==========================================
# 🔑 BROWSER CREDENTIALS
# ==========================================

BROWSER_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'ar-origin': 'https://www.777bigwingame.app',
    'cache-control': 'no-cache',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'pragma': 'no-cache',
    'referer': 'https://www.777bigwingame.app/',
    'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
}

BROWSER_API = {
    "random": "65c6e1e7ee8d46bdb81d07e39d6eeec7",
    "signature": "A35A202CF6FD20CCA9C447394918E0DB",
    "timestamp": 1783259041,
}

BROWSER_LOGIN = {
    "username": "959680090540",
    "pwd": "Mitheint11",
    "phonetype": 1,
    "logintype": "mobile",
    "packId": "",
    "deviceId": "51ed4ee0f338a1bb24063ffdfcd31ce6",
    "pixelId": "",
    "fbcId": "",
    "fbc": "",
    "fbp": "",
    "adId": "",
    "language": 0,
    "random": "b8b9169823254921acceced7d17e5a17",
    "signature": "17D6A5871D3981B1F4DCF9DD522E2B1D",
    "timestamp": 1783258460,
}

# ==========================================
# 🐛 DEBUG LOGGER
# ==========================================
def debug_log(message, level="INFO"):
    if DEBUG:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")

def debug_json(data, label="JSON Data"):
    if DEBUG:
        print(f"📦 {label}:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

# ==========================================
# 🔑 TOKEN FUNCTIONS
# ==========================================

def use_browser_token():
    global CURRENT_TOKEN
    if BROWSER_TOKEN:
        CURRENT_TOKEN = f"Bearer {BROWSER_TOKEN}"
        debug_log(f"✅ Using browser token")
        return True
    return False

async def login_with_browser_credentials(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    debug_log("🔐 Login with browser credentials...")
    
    try:
        async with session.post(
            'https://api.bigwinqaz.com/api/webapi/Login',
            headers=BROWSER_HEADERS,
            json=BROWSER_LOGIN,
            timeout=15.0
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data and data.get('code') == 0:
                    token_data = data.get('data', {})
                    token_str = token_data.get('token', '') if isinstance(token_data, dict) else token_data
                    if token_str:
                        CURRENT_TOKEN = f"Bearer {token_str}"
                        debug_log("✅ Login successful!")
                        return True
            debug_log(f"❌ Login failed: {data.get('msg', 'Unknown')}", "ERROR")
            return False
    except Exception as e:
        debug_log(f"❌ Login error: {e}", "ERROR")
        return False

async def ensure_token(session):
    if not CURRENT_TOKEN:
        if use_browser_token():
            return True
        return await login_with_browser_credentials(session)
    return True

# ==========================================
# 🧠 AI PREDICTION
# ==========================================
def dynamic_history_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG (အကြီး) 🔴", 55.0, "⏳ Collecting data..."

    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]

    predicted = "BIG (အကြီး) 🔴"
    base_prob = 55.0
    reason = "Pattern analysis"
    pattern_found = False

    for current_len in range(10, 8, -1):
        if len(all_history) > current_len:
            recent_pattern = all_history[-current_len:]
            big_next_count = 0
            small_next_count = 0

            for i in range(len(all_history) - current_len):
                if all_history[i:i+current_len] == recent_pattern:
                    next_result = all_history[i+current_len]
                    if next_result == 'BIG':
                        big_next_count += 1
                    elif next_result == 'SMALL':
                        small_next_count += 1

            total = big_next_count + small_next_count
            if total > 0:
                big_prob = (big_next_count / total) * 100
                small_prob = (small_next_count / total) * 100
                pattern_str = "-".join(recent_pattern).replace('BIG', 'B').replace('SMALL', 'S')

                if big_prob > small_prob:
                    predicted = "BIG (အကြီး) 🔴"
                    base_prob = big_prob
                    reason = f"[{pattern_str}] BIG follow pattern"
                elif small_prob > big_prob:
                    predicted = "SMALL (အသေး) 🟢"
                    base_prob = small_prob
                    reason = f"[{pattern_str}] SMALL follow pattern"
                else:
                    predicted = "BIG (အကြီး) 🔴"
                    base_prob = 50.0
                    reason = f"[{pattern_str}] Equal probability"
                pattern_found = True
                break

    if not pattern_found:
        b_count = all_history.count("BIG")
        s_count = all_history.count("SMALL")
        predicted = "BIG (အကြီး) 🔴" if s_count > b_count else "SMALL (အသေး) 🟢"
        base_prob = 55.0
        reason = "Majority trend"

    return predicted, min(round(base_prob, 1), 98.0), reason

# ==========================================
# 📊 GRAPH GENERATOR
# ==========================================
def generate_winrate_chart(predictions):
    wins, losses = 0, 0
    bar_colors, dots_list, bar_heights = [], [], []
    history_wr = []

    latest_preds = list(reversed(predictions))[-20:]

    for i, p in enumerate(latest_preds):
        current_played = i + 1
        if 'WIN' in p.get('win_lose', ''):
            wins += 1
            bar_colors.append('#00e5ff')
            dots_list.append(('G', '#1de9b6'))
        else:
            losses += 1
            bar_colors.append('#ff4444')
            dots_list.append(('R', '#ef5350'))

        current_wr = (wins / current_played) * 100
        bar_heights.append(current_wr)
        history_wr.append(current_wr)

    total_played = wins + losses
    win_rate = int((wins / total_played * 100)) if total_played > 0 else 0

    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26')

    fig.text(0.05, 0.90, "AI PERFORMANCE ANALYTICS", color='#ffffff', fontsize=32, fontweight='bold', ha='left')

    ax_circle = fig.add_axes([0.08, 0.42, 0.35, 0.40])
    ax_circle.set_axis_off()
    ax_circle.set_xlim(0, 1)
    ax_circle.set_ylim(0, 1)

    theta_bg = np.linspace(-1.25*np.pi, 0.25*np.pi, 200)
    ax_circle.plot(0.5 + 0.45*np.cos(theta_bg), 0.5 + 0.45*np.sin(theta_bg), color='#2c313c', linewidth=12)

    if win_rate > 0:
        end_angle = 0.25*np.pi - (win_rate/100) * 1.5 * np.pi
        theta_fg = np.linspace(0.25*np.pi, end_angle, 100)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color='#00e5ff', linewidth=12)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color='#00e5ff', linewidth=22, alpha=0.2)

    ax_circle.text(0.5, 0.75, f"{total_played}/20", color='#a3a8b5', fontsize=16, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.65, "TOTAL WINRATE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.48, f"{win_rate}%", color='#00e5ff', fontsize=65, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.32, "PREDICTIONS MADE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')

    badge = patches.FancyBboxPatch((0.35, 0.16), 0.3, 0.08, boxstyle="round,pad=0.03", fc="#164e63", ec="#00e5ff", lw=1.5)
    ax_circle.add_patch(badge)
    ax_circle.text(0.5, 0.20, "FINALISED ✓", color='#00e5ff', fontsize=11, fontweight='bold', ha='center', va='center')

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
    ax_bar.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#7a8294', fontsize=10)
    ax_bar.tick_params(axis='y', length=0, pad=5)
    ax_bar.grid(axis='y', color='#2c313c', linestyle='-', linewidth=1.5)

    if total_played > 0:
        x_pos = np.arange(total_played)
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.8, alpha=0.15, zorder=2, align='center')
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.45, alpha=0.9, zorder=3, align='center')
        ax_bar.plot(x_pos, history_wr, color='#3b82f6', linewidth=2.5, marker='o', markersize=6, markerfacecolor='#1c1f26', markeredgecolor='#00e5ff', markeredgewidth=2, zorder=4)

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

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1c1f26')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==========================================
# 🎯 PLACE BET
# ==========================================
async def place_bet(session: aiohttp.ClientSession, predicted_size: str, amount: int):
    global CURRENT_TOKEN

    if not CURRENT_TOKEN:
        return None

    bet_direction = "BIG" if "BIG" in predicted_size else "SMALL"

    headers = BROWSER_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        "gameType": AUTO_BET["game_type"],
        "amount": amount,
        "direction": bet_direction,
        "language": 7,
        "random": hashlib.md5(str(time.time()).encode()).hexdigest(),
        "signature": hashlib.md5(f"{AUTO_BET['game_type']}{amount}{bet_direction}{time.time()}".encode()).hexdigest().upper(),
        "timestamp": int(time.time())
    }

    try:
        async with session.post(
            'https://api.bigwinqaz.com/api/webapi/bet/place',
            headers=headers,
            json=json_data,
            timeout=10.0
        ) as response:
            if response.status == 200:
                return await response.json()
            return None
    except Exception:
        return None

# ==========================================
# 🎯 AUTO BET HANDLER
# ==========================================
async def auto_bet_handler(session: aiohttp.ClientSession):
    global AUTO_BET

    if not AUTO_BET["enabled"]:
        return

    pred_cursor = predictions_collection.find().sort("issue_number", -1).limit(1)
    predictions = await pred_cursor.to_list(length=1)

    if not predictions:
        return

    latest_pred = predictions[0]
    issue_number = latest_pred.get("issue_number")
    predicted_size = latest_pred.get("predicted_size", "BIG")

    if AUTO_BET["last_bet_issue"] == issue_number:
        return

    amount = AUTO_BET["base_amount"] * (2 ** AUTO_BET["martingale_level"])

    result = await place_bet(session, predicted_size, amount)

    if result and result.get('code') == 0:
        AUTO_BET["last_bet_issue"] = issue_number
        AUTO_BET["bet_count"] += 1

        data = result.get('data', {})
        is_win = data.get('win', False) or data.get('result') == 'win'
        win_amount = data.get('winAmount', 0)

        if is_win:
            AUTO_BET["win_count"] += 1
            AUTO_BET["total_profit"] += win_amount
            AUTO_BET["current_streak"] = 0
            AUTO_BET["martingale_level"] = 0
        else:
            AUTO_BET["loss_count"] += 1
            AUTO_BET["total_profit"] -= amount
            AUTO_BET["current_streak"] += 1
            AUTO_BET["martingale_level"] += 1

        if AUTO_BET["current_streak"] > AUTO_BET["max_streak"]:
            AUTO_BET["max_streak"] = AUTO_BET["current_streak"]

        debug_log(f"Bet: {issue_number} | {'WIN' if is_win else 'LOSS'} | Profit: {AUTO_BET['total_profit']}")

        if AUTO_BET["max_bets"] > 0 and AUTO_BET["bet_count"] >= AUTO_BET["max_bets"]:
            AUTO_BET["enabled"] = False
            AUTO_BET["status"] = "stopped"

        if AUTO_BET["martingale_level"] >= 5:
            AUTO_BET["enabled"] = False
            AUTO_BET["status"] = "stopped"

# ==========================================
# 🚀 CORE LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE

    if not CURRENT_TOKEN:
        if not await ensure_token(session):
            return False

    headers = BROWSER_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10,
        'pageNo': 1,
        'typeId': 30,
        'language': 0,
        'random': BROWSER_API['random'],
        'signature': BROWSER_API['signature'],
        'timestamp': BROWSER_API['timestamp'],
    }

    try:
        async with session.post(
            'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList',
            headers=headers,
            json=json_data,
            timeout=10.0
        ) as response:
            if response.status == 200:
                data = await response.json()
                
                if data and data.get('code') == 0:
                    records = data.get("data", {}).get("list", [])
                    
                    if records:
                        latest_record = records[0]
                        latest_issue = str(latest_record["issueNumber"])
                        latest_number = int(latest_record["number"])
                        latest_size = "BIG" if latest_number >= 5 else "SMALL"

                        is_new_issue = False
                        if not LAST_PROCESSED_ISSUE:
                            is_new_issue = True
                        elif int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                            is_new_issue = True

                        if is_new_issue:
                            debug_log(f"🆕 New issue: {latest_issue} | Number: {latest_number} | Size: {latest_size}")
                            LAST_PROCESSED_ISSUE = latest_issue
                            
                            if not SESSION_START_ISSUE:
                                SESSION_START_ISSUE = latest_issue

                            # Save history
                            await history_collection.update_one(
                                {"issue_number": latest_issue},
                                {"$setOnInsert": {
                                    "number": latest_number,
                                    "size": latest_size,
                                    "time_context": "CURRENT"
                                }},
                                upsert=True
                            )

                            # Check previous prediction
                            pred_doc = await predictions_collection.find_one({"issue_number": latest_issue})
                            if pred_doc and pred_doc.get("predicted_size"):
                                clean_predicted = "BIG" if "BIG" in pred_doc.get("predicted_size", "") else "SMALL"
                                is_win = (clean_predicted == latest_size)
                                win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                                
                                await predictions_collection.update_one(
                                    {"issue_number": latest_issue},
                                    {"$set": {
                                        "actual_size": latest_size,
                                        "actual_number": latest_number,
                                        "win_lose": win_lose_status
                                    }}
                                )
                                debug_log(f"📊 Prediction result: {win_lose_status}")

                            next_issue = str(int(latest_issue) + 1)

                            # Get history for prediction
                            cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                            history_docs = await cursor.to_list(length=5000)

                            # Make prediction
                            try:
                                predicted, final_prob, reason = await asyncio.to_thread(
                                    dynamic_history_predict, history_docs
                                )
                            except Exception as e:
                                debug_log(f"❌ Prediction error: {e}", "ERROR")
                                predicted = "BIG (အကြီး) 🔴"
                                final_prob = 55.0
                                reason = "⚠️ AI Processing Error"

                            # Save prediction
                            predicted_result_db = "BIG" if "BIG" in predicted else "SMALL"
                            await predictions_collection.update_one(
                                {"issue_number": next_issue},
                                {"$set": {"predicted_size": predicted_result_db}},
                                upsert=True
                            )

                            # Get session predictions
                            pred_cursor = predictions_collection.find({
                                "issue_number": {"$gte": SESSION_START_ISSUE},
                                "win_lose": {"$ne": None}
                            }).sort("issue_number", -1)
                            session_preds = await pred_cursor.to_list(length=20)

                            # Build table
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

                            # Generate chart
                            img_buf = await asyncio.to_thread(generate_winrate_chart, session_preds)
                            photo = BufferedInputFile(img_buf.read(), filename=f"chart_{int(time.time())}.png")

                            sec_left = 30 - (int(time.time()) % 30)
                            iss_display = f"{next_issue[:3]}**{next_issue[-4:]}"

                            # Bet advice
                            bet_advice = "💰 <b>Bet:</b> Base (1x)"
                            recent_preds_cursor = predictions_collection.find(
                                {"win_lose": {"$ne": None}}
                            ).sort("issue_number", -1).limit(15)
                            recent_preds = await recent_preds_cursor.to_list(length=15)
                            
                            current_lose_streak = 0
                            for p in recent_preds:
                                if p.get("win_lose") == "LOSE ❌":
                                    current_lose_streak += 1
                                else:
                                    break

                            if current_lose_streak == 0:
                                bet_advice = "💰 <b>Bet:</b> Base (1x)"
                            elif current_lose_streak == 1:
                                bet_advice = "💰 <b>Bet:</b> 2x (Martingale)"
                            elif current_lose_streak == 2:
                                bet_advice = "💰 <b>Bet:</b> 4x (Martingale)"
                            elif current_lose_streak == 3:
                                bet_advice = "💰 <b>Bet:</b> 8x (Martingale)"
                            else:
                                bet_advice = "⚠️ <b>[DANGER] 4+ consecutive losses!</b>"

                            tg_caption = (
                                f"<b>🏆 WIN GO (30 SECONDS)</b>\n"
                                f"⏰ Next Result In: <b>{sec_left}s</b>\n\n"
                                f"{table_str}\n"
                                f"🅿️ <b>Period:</b> {iss_display}\n"
                                f"🤖 <b>AI Prediction: {predicted}</b>\n"
                                f"📈 <b>Probability: {final_prob}%</b>\n"
                                f"💡 <b>Reason:</b>\n{reason}\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"{bet_advice}"
                            )

                            # Send message
                            if MAIN_MESSAGE_ID:
                                try:
                                    media = InputMediaPhoto(media=photo, caption=tg_caption, parse_mode="HTML")
                                    await bot.edit_message_media(chat_id=CHANNEL_ID, message_id=MAIN_MESSAGE_ID, media=media)
                                except Exception:
                                    msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                                    MAIN_MESSAGE_ID = msg.message_id
                            else:
                                msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                                MAIN_MESSAGE_ID = msg.message_id

                            return True
            return False
    except Exception as e:
        debug_log(f"❌ API error: {e}", "ERROR")
        return False

# ==========================================
# ⏱️ SCHEDULER
# ==========================================
async def auto_broadcaster_with_bet():
    debug_log("🚀 Starting Auto Broadcaster...")
    await init_db()
    
    async with aiohttp.ClientSession() as session:
        if not await ensure_token(session):
            debug_log("❌ Failed to get token", "ERROR")
            return
        
        debug_log("✅ Token ready!")
        
        while True:
            current_time = time.time()
            sec_passed = int(current_time) % 30
            
            if 5 <= sec_passed <= 28:
                try:
                    is_processed = await check_game_and_predict(session)
                    if is_processed:
                        if AUTO_BET["enabled"]:
                            await auto_bet_handler(session)
                        
                        sleep_time = 30 - (int(time.time()) % 30)
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                        continue
                except Exception as e:
                    debug_log(f"❌ Error: {e}", "ERROR")
                    await asyncio.sleep(2)
            
            await asyncio.sleep(0.5)

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        debug_log("✅ MongoDB connected")
    except Exception as e:
        debug_log(f"❌ MongoDB error: {e}", "ERROR")

# ==========================================
# 🤖 TELEGRAM COMMANDS
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 <b>Welcome to AI Prediction Bot!</b>\n\n"
        "📌 <b>Commands:</b>\n"
        "/autobet - Start Auto Bet\n"
        "/stopbet - Stop Auto Bet\n"
        "/betstat - Show Statistics\n"
        "/betsettings - Change Settings\n"
        "/status - Check System Status\n"
        "/debug - Toggle Debug Mode"
    )

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    global DEBUG
    DEBUG = not DEBUG
    await message.reply(f"🐛 Debug mode: {'ON' if DEBUG else 'OFF'}")

@dp.message(Command("autobet"))
async def cmd_autobet(message: types.Message):
    global AUTO_BET
    if AUTO_BET["enabled"]:
        await message.reply("⚠️ AutoBet is already running.")
        return

    AUTO_BET["enabled"] = True
    AUTO_BET["status"] = "running"
    AUTO_BET["bet_count"] = 0
    AUTO_BET["win_count"] = 0
    AUTO_BET["loss_count"] = 0
    AUTO_BET["total_profit"] = 0
    AUTO_BET["current_streak"] = 0
    AUTO_BET["martingale_level"] = 0

    await message.reply(
        f"🚀 <b>AutoBet Started!</b>\n\n"
        f"🎮 Game: {AUTO_BET['game_type']}\n"
        f"💰 Base Amount: {AUTO_BET['base_amount']}\n"
        f"🛡️ Auto-stop: 5 consecutive losses"
    )

@dp.message(Command("stopbet"))
async def cmd_stopbet(message: types.Message):
    global AUTO_BET
    if not AUTO_BET["enabled"]:
        await message.reply("⚠️ AutoBet is not running.")
        return

    AUTO_BET["enabled"] = False
    AUTO_BET["status"] = "stopped"
    await message.reply("⏹ <b>AutoBet Stopped!</b>")

@dp.message(Command("betstat"))
async def cmd_betstat(message: types.Message):
    stats = get_bet_stats()
    await message.reply(
        f"📊 <b>AutoBet Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Profit: {stats['profit']}\n"
        f"🎯 Total Bets: {stats['total']}\n"
        f"✅ Wins: {stats['wins']}\n"
        f"❌ Losses: {stats['losses']}\n"
        f"📈 Win Rate: {stats['win_rate']}%\n"
        f"🔥 Max Streak: {stats['max_streak']}\n"
        f"🔄 Martingale Level: {stats['martingale_level']}"
    )

@dp.message(Command("betsettings"))
async def cmd_betsettings(message: types.Message):
    global AUTO_BET
    args = message.text.split()
    if len(args) < 3:
        await message.reply(
            "⚙️ <b>Usage:</b>\n"
            "/betsettings game 1min\n"
            "/betsettings amount 1\n"
            "/betsettings max 10\n\n"
            f"📌 Current: Game={AUTO_BET['game_type']}, Amount={AUTO_BET['base_amount']}"
        )
        return    setting = args[1].lower()
    value = args[2]

    if setting == "game":
        if value in ["1min", "3min", "5min", "30s", "trx"]:
            AUTO_BET["game_type"] = value
            await message.reply(f"✅ Game changed to: {value}")
    elif setting == "amount":
        try:
            amount = int(value)
            if amount >= 1:
                AUTO_BET["base_amount"] = amount
                await message.reply(f"✅ Amount changed to: {amount}")
        except ValueError:
            await message.reply("❌ Invalid amount")
    elif setting == "max":
        try:
            AUTO_BET["max_bets"] = int(value)
            await message.reply(f"✅ Max bets: {AUTO_BET['max_bets'] or 'Unlimited'}")
        except ValueError:
            await message.reply("❌ Invalid number")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    stats = get_bet_stats()
    await message.reply(
        f"📊 <b>System Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔐 Token: {'✅ Valid' if CURRENT_TOKEN else '❌ Missing'}\n"
        f"🐛 Debug: {'🟢 ON' if DEBUG else '🔴 OFF'}\n"
        f"🎯 AutoBet: {'🟢 Running' if AUTO_BET['enabled'] else '🔴 Stopped'}\n"
        f"🎮 Game: {AUTO_BET['game_type']}\n"
        f"💰 Amount: {AUTO_BET['base_amount']}\n"
        f"📈 Bets: {stats['total']}\n"
        f"💵 Profit: {stats['profit']}"
    )

def get_bet_stats():
    total = AUTO_BET["bet_count"]
    wins = AUTO_BET["win_count"]
    losses = AUTO_BET["loss_count"]
    win_rate = round((wins / total * 100) if total > 0 else 0, 1)
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "profit": AUTO_BET["total_profit"],
        "current_streak": AUTO_BET["current_streak"],
        "max_streak": AUTO_BET["max_streak"],
        "martingale_level": AUTO_BET["martingale_level"],
        "status": AUTO_BET["status"]
    }

# ==========================================
# 🚀 MAIN
# ==========================================
async def main():
    print("=" * 60)
    print("🚀 AI Prediction + AutoBet Bot Starting...")
    print(f"🐛 Debug Mode: {'ON' if DEBUG else 'OFF'}")
    print("=" * 60)
    
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster_with_bet())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ Bot stopped.")
