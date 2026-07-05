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

load_dotenv()

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME", "959675323878")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = os.getenv("OWNER_ID")

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

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# 🎯 AUTO BET STATE
# ==========================================
AUTO_BET = {
    "enabled": False,
    "session_id": None,
    "last_bet_issue": None,
    "bet_count": 0,
    "win_count": 0,
    "loss_count": 0,
    "total_profit": 0,
    "current_streak": 0,
    "max_streak": 0,
    "martingale_level": 0,
    "base_amount": 1,
    "current_amount": 1,
    "max_bets": 0,
    "game_type": "1min",
    "interval": 30,
    "status": "idle"
}

BET_HISTORY = []

# ==========================================
# 🔑 API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=2):
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=5.0) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    return {"code": 401, "msg": "Token expired"}
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
            else:
                print(f"❌ Request failed: {e}")
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME,
        'pwd': PASSWORD,
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': hashlib.md5(str(random.random()).encode()).hexdigest(),
        'language': 7,
        'random': hashlib.md5(str(time.time()).encode()).hexdigest(),
        'signature': hashlib.md5(f"{USERNAME}{PASSWORD}{time.time()}".encode()).hexdigest().upper(),
        'timestamp': int(time.time()),
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print("✅ Login successful")
        return True
    print("❌ Login failed")
    return False

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

    MAX_PATTERN_LENGTH = 10
    MIN_PATTERN_LENGTH = 9
    pattern_found = False

    for current_len in range(MAX_PATTERN_LENGTH, MIN_PATTERN_LENGTH - 1, -1):
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

            total_pattern_matches = big_next_count + small_next_count

            if total_pattern_matches > 0:
                big_prob = (big_next_count / total_pattern_matches) * 100
                small_prob = (small_next_count / total_pattern_matches) * 100
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

    final_prob = min(round(base_prob, 1), 98.0)
    return predicted, final_prob, reason

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

    ax_circle.text(0.05, 0.05, "0", color='#7a8294', fontsize=12, fontweight='bold', ha='center')
    ax_circle.text(0.95, 0.05, "100%", color='#7a8294', fontsize=12, fontweight='bold', ha='center')

    fig.text(0.74, 0.85, "SESSION PERFORMANCE TREND", color='#a3a8b5', fontsize=14, fontweight='bold', ha='center')
    fig.lines.extend([plt.Line2D([0.55, 0.93], [0.83, 0.83], color='#2c313c', lw=2, transform=fig.transFigure)])

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
    ax_wm.text(0.5, 0.5, "DEV - WANG LIN", color='#ffffff', fontsize=26, fontweight='bold', style='italic', ha='center', va='center')
    ax_wm.plot([0.1, 0.9], [0.30, 0.30], color='#ffffff', lw=3)
    ax_wm.plot([0.1, 0.9], [0.70, 0.70], color='#ffffff', lw=3)

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
# 🎯 PLACE BET
# ==========================================
async def place_bet(session: aiohttp.ClientSession, predicted_size: str, amount: int):
    global CURRENT_TOKEN

    if not CURRENT_TOKEN:
        if not await login_and_get_token(session):
            return None

    bet_direction = "BIG" if "BIG" in predicted_size else "SMALL"

    headers = BASE_HEADERS.copy()
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
        data = await fetch_with_retry(
            session,
            'https://api.bigwinqaz.com/api/webapi/bet/place',
            headers,
            json_data,
            retries=2
        )
        return data
    except Exception as e:
        print(f"❌ Bet error: {e}")
        return None

# ==========================================
# 🎯 AUTO BET HANDLER
# ==========================================
async def auto_bet_handler(session: aiohttp.ClientSession):
    global AUTO_BET, LAST_PROCESSED_ISSUE

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

    # Martingale calculation
    amount = AUTO_BET["base_amount"] * (2 ** AUTO_BET["martingale_level"])

    # Place bet
    result = await place_bet(session, predicted_size, amount)

    if result and result.get('code') == 0:
        AUTO_BET["last_bet_issue"] = issue_number
        AUTO_BET["bet_count"] += 1
        AUTO_BET["current_amount"] = amount

        data = result.get('data', {})
        is_win = data.get('win', False) or data.get('result') == 'win'
        win_amount = data.get('winAmount', 0)

        if is_win:
            AUTO_BET["win_count"] += 1
            AUTO_BET["total_profit"] += win_amount
            AUTO_BET["current_streak"] = 0
            AUTO_BET["martingale_level"] = 0
            status_text = "✅ WIN"
        else:
            AUTO_BET["loss_count"] += 1
            AUTO_BET["total_profit"] -= amount
            AUTO_BET["current_streak"] += 1
            AUTO_BET["martingale_level"] += 1
            status_text = "❌ LOSS"

        if AUTO_BET["current_streak"] > AUTO_BET["max_streak"]:
            AUTO_BET["max_streak"] = AUTO_BET["current_streak"]

        BET_HISTORY.append({
            "issue": issue_number,
            "direction": predicted_size,
            "amount": amount,
            "result": status_text,
            "profit": win_amount if is_win else -amount,
            "timestamp": datetime.now().isoformat()
        })

        # Auto stop conditions
        if AUTO_BET["max_bets"] > 0 and AUTO_BET["bet_count"] >= AUTO_BET["max_bets"]:
            AUTO_BET["enabled"] = False
            AUTO_BET["status"] = "stopped"
            print(f"⏹ AutoBet stopped: Max bets reached ({AUTO_BET['bet_count']})")

        if AUTO_BET["martingale_level"] >= 5:
            AUTO_BET["enabled"] = False
            AUTO_BET["status"] = "stopped"
            print("⏹ AutoBet stopped: 5 consecutive losses!")

        print(f"🎯 [{issue_number}] {status_text} | Amount: {amount} | Profit: {AUTO_BET['total_profit']}")

    else:
        print(f"❌ Bet failed for issue {issue_number}")

# ==========================================
# 🚀 CORE LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE
    global LAST_NOTIFIED_ISSUE

    if not CURRENT_TOKEN:
        if not await login_and_get_token(session):
            return False

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': hashlib.md5(str(time.time()).encode()).hexdigest(),
        'signature': hashlib.md5(f"GetNoaverageEmerdList{time.time()}".encode()).hexdigest().upper(),
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

                pred_doc = await predictions_collection.find_one({"issue_number": latest_issue})
                if pred_doc and pred_doc.get("predicted_size"):
                    db_predicted_size = pred_doc.get("predicted_size")
                    clean_predicted = "BIG" if "BIG" in db_predicted_size else "SMALL"
                    is_win = (clean_predicted == latest_size)
                    win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                    await predictions_collection.update_one(
                        {"issue_number": latest_issue},
                        {"$set": {"actual_size": latest_size, "actual_number": latest_number, "win_lose": win_lose_status}}
                    )

                next_issue = str(int(latest_issue) + 1)

                current_session_count = await predictions_collection.count_documents({
                    "issue_number": {"$gte": SESSION_START_ISSUE},
                    "win_lose": {"$ne": None}
                })

                if current_session_count >= 20:
                    SESSION_START_ISSUE = next_issue

                recent_preds_cursor = predictions_collection.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(15)
                recent_preds = await recent_preds_cursor.to_list(length=15)

                current_lose_streak = 0
                for p in recent_preds:
                    if p.get("win_lose") == "LOSE ❌":
                        current_lose_streak += 1
                    else:
                        break

                if current_lose_streak >= 5 and LAST_NOTIFIED_ISSUE != latest_issue:
                    try:
                        alert_text = (
                            f"🚨 <b>[SYSTEM ALERT] Multiple Losses!</b>\n\n"
                            f"⚠️ Current losing streak: <b>{current_lose_streak} games</b> ❌\n"
                            f"🅿️ Last Period: <code>{latest_issue}</code>\n"
                            f"💡 Consider pausing or reducing bet amount."
                        )
                        await bot.send_message(chat_id=OWNER_ID, text=alert_text)
                        LAST_NOTIFIED_ISSUE = latest_issue
                    except Exception as e:
                        pass

                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)

                try:
                    mem_pred, mem_prob, mem_logic = await asyncio.to_thread(dynamic_history_predict, history_docs)
                    predicted = mem_pred
                    reason = mem_logic
                    final_prob = mem_prob
                except Exception as e:
                    predicted = "BIG (အကြီး) 🔴"
                    final_prob = 55.0
                    reason = "⚠️ AI Processing Error"

                predicted_result_db = "BIG" if "BIG" in predicted else "SMALL"
                await predictions_collection.update_one(
                    {"issue_number": next_issue},
                    {"$set": {"predicted_size": predicted_result_db}},
                    upsert=True
                )

                bet_advice = ""
                if current_lose_streak == 0:
                    bet_advice = "💰 <b>Bet:</b> Base (1x)"
                elif current_lose_streak == 1:
                    bet_advice = "💰 <b>Bet:</b> 2x (Martingale)"
                elif current_lose_streak == 2:
                    bet_advice = "💰 <b>Bet:</b> 4x (Martingale)"
                elif current_lose_streak == 3:
                    bet_advice = "💰 <b>Bet:</b> 8x (Martingale)"
                else:
                    bet_advice = "⚠️ <b>[DANGER] 4+ consecutive losses!</b>\nStop or restart from 1x."

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

                img_buf = await asyncio.to_thread(generate_winrate_chart, session_preds)
                unique_filename = f"winrate_chart_{int(time.time())}.png"
                photo = BufferedInputFile(img_buf.read(), filename=unique_filename)

                sec_left = 30 - (int(time.time()) % 30)
                iss_display = f"{next_issue[:3]}**{next_issue[-4:]}"

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

    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()):
        CURRENT_TOKEN = ""
        return False

    return False

# ==========================================
# ⏱️ SCHEDULER
# ==========================================
async def auto_broadcaster_with_bet():
    await init_db()
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
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
                        await asyncio.sleep(sleep_time)
                        continue
                except Exception as e:
                    print(f"❌ Error: {e}")

            await asyncio.sleep(0.5)

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"❌ MongoDB error: {e}")

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
        "/status - Check System Status\n\n"
        "⚠️ Use at your own risk!"
    )

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
    AUTO_BET["current_amount"] = AUTO_BET["base_amount"]

    msg = (
        f"🚀 <b>AutoBet Started!</b>\n\n"
        f"🎮 Game: {AUTO_BET['game_type']}\n"
        f"💰 Base Amount: {AUTO_BET['base_amount']}\n"
        f"📊 Martingale: 1x → 2x → 4x → 8x → 16x\n"
        f"🛡️ Auto-stop: 5 consecutive losses\n"
        f"🔄 Interval: {AUTO_BET['interval']}s\n"
    )
    await message.reply(msg)

@dp.message(Command("stopbet"))
async def cmd_stopbet(message: types.Message):
    global AUTO_BET

    if not AUTO_BET["enabled"]:
        await message.reply("⚠️ AutoBet is not running.")
        return

    AUTO_BET["enabled"] = False
    AUTO_BET["status"] = "stopped"

    stats = get_bet_stats()
    await message.reply(
        f"⏹ <b>AutoBet Stopped!</b>\n\n"
        f"📊 <b>Session Stats:</b>\n"
        f"  Total Bets: {stats['total']}\n"
        f"  Wins: {stats['wins']} ✅\n"
        f"  Losses: {stats['losses']} ❌\n"
        f"  Win Rate: {stats['win_rate']}%\n"
        f"  Profit: {stats['profit']}\n"
        f"  Max Streak: {stats['max_streak']}\n"
    )

@dp.message(Command("betstat"))
async def cmd_betstat(message: types.Message):
    stats = get_bet_stats()
    msg = (
        f"📊 <b>AutoBet Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Profit:</b> {stats['profit']}\n"
        f"🎯 <b>Total Bets:</b> {stats['total']}\n"
        f"✅ <b>Wins:</b> {stats['wins']}\n"
        f"❌ <b>Losses:</b> {stats['losses']}\n"
        f"📈 <b>Win Rate:</b> {stats['win_rate']}%\n"
        f"🔥 <b>Max Streak:</b> {stats['max_streak']}\n"
        f"📉 <b>Current Streak:</b> {stats['current_streak']}\n"
        f"🔄 <b>Martingale Level:</b> {stats['martingale_level']}\n"
    )
    await message.reply(msg)

@dp.message(Command("betsettings"))
async def cmd_betsettings(message: types.Message):
    global AUTO_BET

    args = message.text.split()
    if len(args) < 3:
        await message.reply(
            "⚙️ <b>Usage:</b>\n"
            "/betsettings game 1min\n"
            "/betsettings amount 1\n"
            "/betsettings max 10\n"
            "/betsettings interval 30\n\n"
            f"📌 <b>Current Settings:</b>\n"
            f"  Game: {AUTO_BET['game_type']}\n"
            f"  Base Amount: {AUTO_BET['base_amount']}\n"
            f"  Max Bets: {AUTO_BET['max_bets'] or 'Unlimited'}\n"
            f"  Interval: {AUTO_BET['interval']}s\n"
        )
        return

    setting = args[1].lower()
    value = args[2]

    if setting == "game":
        if value in ["1min", "3min", "5min", "30s", "trx"]:
            AUTO_BET["game_type"] = value
            await message.reply(f"✅ Game changed to: {value}")
        else:
            await message.reply("❌ Invalid game. Use: 1min, 3min, 5min, 30s, trx")

    elif setting == "amount":
        try:
            amount = int(value)
            if amount >= 1:
                AUTO_BET["base_amount"] = amount
                await message.reply(f"✅ Base amount changed to: {amount}")
            else:
                await message.reply("❌ Amount must be >= 1")
        except ValueError:
            await message.reply("❌ Invalid amount")

    elif setting == "max":
        try:
            max_bets = int(value)
            AUTO_BET["max_bets"] = max_bets
            await message.reply(f"✅ Max bets changed to: {max_bets if max_bets > 0 else 'Unlimited'}")
        except ValueError:
            await message.reply("❌ Invalid number")

    elif setting == "interval":
        try:
            interval = int(value)
            if interval >= 10:
                AUTO_BET["interval"] = interval
                await message.reply(f"✅ Interval changed to: {interval}s")
            else:
                await message.reply("❌ Interval must be >= 10 seconds")
        except ValueError:
            await message.reply("❌ Invalid interval")

    else:
        await message.reply(f"❌ Unknown setting: {setting}")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    stats = get_bet_stats()
    msg = (
        f"📊 <b>System Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔐 <b>Token:</b> {'✅ Valid' if CURRENT_TOKEN else '❌ Missing'}\n"
        f"🎯 <b>AutoBet:</b> {'🟢 Running' if AUTO_BET['enabled'] else '🔴 Stopped'}\n"
        f"📊 <b>Status:</b> {stats['status'].upper()}\n"
        f"🎮 <b>Game:</b> {AUTO_BET['game_type']}\n"
        f"💰 <b>Base Amount:</b> {AUTO_BET['base_amount']}\n"
        f"📈 <b>Total Bets:</b> {stats['total']}\n"
        f"💵 <b>Profit:</b> {stats['profit']}\n"
        f"📉 <b>Win Rate:</b> {stats['win_rate']}%\n"
    )
    await message.reply(msg)

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
    print("🚀 AI Prediction + AutoBet Bot Starting...")
    print(f"📊 Game: {AUTO_BET['game_type']}")
    print(f"💰 Base Amount: {AUTO_BET['base_amount']}")
    print("=" * 50)

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster_with_bet())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ Bot stopped.")
