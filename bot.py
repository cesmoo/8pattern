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
MANUAL_TOKEN = os.getenv("MANUAL_TOKEN", "")

# Debug Mode
DEBUG = True  # True ဆိုရင် အသေးစိတ် log တွေပြမယ်

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
LOGIN_ATTEMPTS = 0
MAX_LOGIN_ATTEMPTS = 5

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
# 🐛 DEBUG LOGGER
# ==========================================
def debug_log(message, level="INFO"):
    """Debug messages ကို ပြသပေးတယ်"""
    if DEBUG:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")

def debug_json(data, label="JSON Data"):
    """JSON data ကို လှပစွာ ပြသပေးတယ်"""
    if DEBUG:
        print(f"📦 {label}:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

# ==========================================
# 🔑 API FUNCTIONS WITH DEBUG
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=3):
    """API request ကို retry နဲ့ ပို့တယ်"""
    debug_log(f"🌐 Fetching: {url}")
    debug_log(f"📤 Request data: {json.dumps(json_data, indent=2)}")
    
    for attempt in range(retries):
        try:
            debug_log(f"🔄 Attempt {attempt + 1}/{retries}")
            
            async with session.post(url, headers=headers, json=json_data, timeout=10.0) as response:
                debug_log(f"📡 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    debug_log(f"✅ Request successful")
                    debug_json(data, "Response Data")
                    return data
                elif response.status == 401:
                    debug_log("❌ 401 Unauthorized - Token expired")
                    return {"code": 401, "msg": "Token expired"}
                else:
                    debug_log(f"⚠️ Response status: {response.status}")
                    try:
                        data = await response.json()
                        debug_json(data, "Error Response")
                    except:
                        pass
                    
        except asyncio.TimeoutError:
            debug_log(f"⏰ Timeout on attempt {attempt + 1}")
        except Exception as e:
            debug_log(f"❌ Request error: {e}", "ERROR")
            
        if attempt < retries - 1:
            wait_time = (attempt + 1) * 2
            debug_log(f"⏳ Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    debug_log("❌ All retries failed", "ERROR")
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    """Login လုပ်ပြီး Token ရယူတယ်"""
    global CURRENT_TOKEN, LOGIN_ATTEMPTS
    
    debug_log("🔐 ===== STARTING LOGIN PROCESS =====")
    LOGIN_ATTEMPTS += 1
    
    if LOGIN_ATTEMPTS > MAX_LOGIN_ATTEMPTS:
        debug_log(f"❌ Too many login attempts ({MAX_LOGIN_ATTEMPTS})", "ERROR")
        return False
    
    username = os.getenv("BIGWIN_USERNAME", "959675323878")
    password = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
    
    debug_log(f"👤 Username: {username}")
    debug_log(f"🔑 Password: {'*' * len(password)}")
    
    timestamp = int(time.time())
    random_str = hashlib.md5(str(timestamp).encode()).hexdigest()
    signature = hashlib.md5(f"{username}{password}{timestamp}".encode()).hexdigest().upper()
    
    json_data = {
        'username': '959680090540',
        'pwd': 'Mitheint11',
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'pixelId': '',
        'fbcId': '',
        'fbc': '',
        'fbp': '',
        'adId': '',
        'language': 0,
        'random': 'b8b9169823254921acceced7d17e5a17',
        'signature': '17D6A5871D3981B1F4DCF9DD522E2B1D',
        'timestamp': 1783258460,
    }
    
    debug_json(json_data, "Login Request")
    
    try:
        async with session.post(
            'https://api.bigwinqaz.com/api/webapi/Login',
            headers=BASE_HEADERS,
            json=json_data,
            timeout=15.0
        ) as response:
            
            debug_log(f"📡 Login response status: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                debug_json(data, "Login Response")
                
                if data and data.get('code') == 0:
                    token_data = data.get('data', {})
                    
                    if isinstance(token_data, str):
                        token_str = token_data
                    else:
                        token_str = token_data.get('token', '')
                    
                    if token_str:
                        CURRENT_TOKEN = f"Bearer {token_str}"
                        debug_log(f"✅ Login successful!")
                        debug_log(f"🔐 Token: {CURRENT_TOKEN[:50]}...")
                        LOGIN_ATTEMPTS = 0
                        return True
                    else:
                        debug_log("❌ No token in response", "ERROR")
                        return False
                else:
                    msg = data.get('msg', 'Unknown error')
                    debug_log(f"❌ Login failed: {msg}", "ERROR")
                    return False
            else:
                debug_log(f"❌ HTTP Error: {response.status}", "ERROR")
                return False
                
    except asyncio.TimeoutError:
        debug_log("❌ Login timeout", "ERROR")
        return False
    except Exception as e:
        debug_log(f"❌ Login error: {e}", "ERROR")
        return False

async def get_token_manual():
    """Manual Token ကို .env ကနေ ဖတ်တယ်"""
    global CURRENT_TOKEN
    
    manual_token = os.getenv("MANUAL_TOKEN", "")
    
    if manual_token:
        CURRENT_TOKEN = f"Bearer {manual_token}"
        debug_log(f"✅ Manual token loaded: {CURRENT_TOKEN[:50]}...")
        return True
    
    debug_log("ℹ️ No manual token found in .env")
    return False

async def ensure_valid_token(session: aiohttp.ClientSession):
    """Token ကို စစ်ဆေးပြီး မရှိရင် ရယူတယ်"""
    global CURRENT_TOKEN
    
    debug_log("🔍 Checking token validity...")
    
    # Manual Token အရင်စစ်တယ်
    if not CURRENT_TOKEN:
        debug_log("ℹ️ No token found, checking manual token...")
        if await get_token_manual():
            debug_log("✅ Manual token loaded")
            return True
    
    # Token ရှိရင် validity စစ်တယ်
    if CURRENT_TOKEN:
        debug_log("🔍 Testing existing token...")
        try:
            headers = BASE_HEADERS.copy()
            headers['authorization'] = CURRENT_TOKEN
            
            json_data = {
                'pageSize': 1,
                'pageNo': 1,
                'typeId': 30,
                'language': 7,
                'random': hashlib.md5(str(time.time()).encode()).hexdigest(),
                'signature': hashlib.md5(f"test{time.time()}".encode()).hexdigest().upper(),
                'timestamp': int(time.time()),
            }
            
            async with session.post(
                'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList',
                headers=headers,
                json=json_data,
                timeout=5.0
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') != 401:
                        debug_log("✅ Token is valid")
                        return True
                    else:
                        debug_log("🔄 Token expired")
                        CURRENT_TOKEN = ""
                else:
                    debug_log(f"⚠️ Token check failed: {response.status}")
                    CURRENT_TOKEN = ""
                    
        except Exception as e:
            debug_log(f"⚠️ Token check error: {e}")
            CURRENT_TOKEN = ""
    
    # Token မရှိရင် Login လုပ်တယ်
    debug_log("🔄 Attempting login to get new token...")
    return await login_and_get_token(session)

# ==========================================
# 🧠 AI PREDICTION
# ==========================================
def dynamic_history_predict(history_docs):
    """သမိုင်းကြောင်းကို ခွဲခြမ်းစိတ်ဖြာပြီး ခန့်မှန်းတယ်"""
    debug_log("🧠 Starting AI prediction...")
    
    if len(history_docs) < 10:
        debug_log("⏳ Not enough data (need 10+ records)")
        return "BIG (အကြီး) 🔴", 55.0, "⏳ Collecting data..."

    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    debug_log(f"📊 Analyzing {len(all_history)} history records")
    debug_log(f"📊 Recent pattern: {all_history[-10:]}")

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
                
                debug_log(f"📊 Pattern '{pattern_str}': BIG={big_prob}%, SMALL={small_prob}%")

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
        debug_log(f"📊 No pattern found. BIG={b_count}, SMALL={s_count}")
        predicted = "BIG (အကြီး) 🔴" if s_count > b_count else "SMALL (အသေး) 🟢"
        base_prob = 55.0
        reason = "Majority trend"

    final_prob = min(round(base_prob, 1), 98.0)
    debug_log(f"🎯 Prediction: {predicted} ({final_prob}%)")
    debug_log(f"💡 Reason: {reason}")
    
    return predicted, final_prob, reason

# ==========================================
# 📊 GRAPH GENERATOR
# ==========================================
def generate_winrate_chart(predictions):
    """Win rate chart ကိုဆွဲတယ်"""
    debug_log("📊 Generating chart...")
    
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

    debug_log(f"📊 Chart: {wins}W/{losses}L = {win_rate}%")

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
    
    debug_log("✅ Chart generated successfully")
    return buf

# ==========================================
# 🎯 PLACE BET
# ==========================================
async def place_bet(session: aiohttp.ClientSession, predicted_size: str, amount: int):
    """Bet ထိုးတယ်"""
    global CURRENT_TOKEN

    debug_log(f"🎯 Placing bet: {predicted_size}, Amount: {amount}")

    if not CURRENT_TOKEN:
        debug_log("❌ No token, cannot place bet", "ERROR")
        if not await ensure_valid_token(session):
            return None

    bet_direction = "BIG" if "BIG" in predicted_size else "SMALL"
    debug_log(f"🎯 Direction: {bet_direction}")

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

    debug_json(json_data, "Bet Request")

    try:
        data = await fetch_with_retry(
            session,
            'https://api.bigwinqaz.com/api/webapi/bet/place',
            headers,
            json_data,
            retries=2
        )
        
        if data and data.get('code') == 0:
            debug_log("✅ Bet placed successfully")
            debug_json(data, "Bet Response")
        else:
            debug_log(f"❌ Bet failed: {data}", "ERROR")
            
        return data
        
    except Exception as e:
        debug_log(f"❌ Bet error: {e}", "ERROR")
        return None

# ==========================================
# 🎯 AUTO BET HANDLER
# ==========================================
async def auto_bet_handler(session: aiohttp.ClientSession):
    """Auto Bet ကို စီမံခန့်ခွဲတယ်"""
    global AUTO_BET, LAST_PROCESSED_ISSUE

    if not AUTO_BET["enabled"]:
        debug_log("ℹ️ AutoBet is disabled")
        return

    debug_log("🎯 AutoBet handler running...")

    pred_cursor = predictions_collection.find().sort("issue_number", -1).limit(1)
    predictions = await pred_cursor.to_list(length=1)

    if not predictions:
        debug_log("ℹ️ No predictions found")
        return

    latest_pred = predictions[0]
    issue_number = latest_pred.get("issue_number")
    predicted_size = latest_pred.get("predicted_size", "BIG")

    debug_log(f"📊 Latest prediction: {issue_number} -> {predicted_size}")

    if AUTO_BET["last_bet_issue"] == issue_number:
        debug_log(f"ℹ️ Already bet on issue {issue_number}")
        return

    # Martingale calculation
    amount = AUTO_BET["base_amount"] * (2 ** AUTO_BET["martingale_level"])
    debug_log(f"💰 Bet amount: {amount} (Level: {AUTO_BET['martingale_level']})")

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
            debug_log(f"✅ WIN! Amount: {win_amount}")
        else:
            AUTO_BET["loss_count"] += 1
            AUTO_BET["total_profit"] -= amount
            AUTO_BET["current_streak"] += 1
            AUTO_BET["martingale_level"] += 1
            status_text = "❌ LOSS"
            debug_log(f"❌ LOSS! Amount: {amount}")

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
            debug_log(f"⏹ AutoBet stopped: Max bets reached ({AUTO_BET['bet_count']})")

        if AUTO_BET["martingale_level"] >= 5:
            AUTO_BET["enabled"] = False
            AUTO_BET["status"] = "stopped"
            debug_log("⏹ AutoBet stopped: 5 consecutive losses!")

        debug_log(f"📊 Stats: Bets={AUTO_BET['bet_count']}, Profit={AUTO_BET['total_profit']}")

    else:
        debug_log(f"❌ Bet failed for issue {issue_number}", "ERROR")

# ==========================================
# 🚀 CORE LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    """Game data ကိုစစ်ပြီး Prediction လုပ်တယ်"""
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE
    global LAST_NOTIFIED_ISSUE

    debug_log("🔍 Checking game and prediction...")

    if not CURRENT_TOKEN:
        debug_log("🔄 No token, getting one...")
        if not await ensure_valid_token(session):
            debug_log("❌ Failed to get token", "ERROR")
            return False

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10,
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': hashlib.md5(str(time.time()).encode()).hexdigest(),
        'signature': hashlib.md5(f"GetNoaverageEmerdList{time.time()}".encode()).hexdigest().upper(),
        'timestamp': int(time.time()),
    }

    data = await fetch_with_retry(
        session,
        'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList',
        headers,
        json_data
    )

    if data and data.get('code') == 0:
        records = data.get("data", {}).get("list", [])
        debug_log(f"📊 Found {len(records)} records")

        if records:
            latest_record = records[0]
            latest_issue = str(latest_record["issueNumber"])
            latest_number = int(latest_record["number"])
            latest_size = "BIG" if latest_number >= 5 else "SMALL"
            latest_parity = "EVEN" if latest_number % 2 == 0 else "ODD"

            debug_log(f"📊 Latest: Issue={latest_issue}, Number={latest_number}, Size={latest_size}")

            is_new_issue = False
            if not LAST_PROCESSED_ISSUE:
                is_new_issue = True
            elif int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                is_new_issue = True

            if is_new_issue:
                debug_log(f"🆕 New issue detected: {latest_issue}")
                LAST_PROCESSED_ISSUE = latest_issue
                if not SESSION_START_ISSUE:
                    SESSION_START_ISSUE = latest_issue

                # Save history
                await history_collection.update_one(
                    {"issue_number": latest_issue},
                    {"$setOnInsert": {
                        "number": latest_number,
                        "size": latest_size,
                        "parity": latest_parity,
                        "time_context": "CURRENT"
                    }},
                    upsert=True
                )
                debug_log(f"💾 Saved history: {latest_issue}")

                # Check prediction result
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
                            "win_lose": win_lose_status
                        }}
                    )
                    debug_log(f"📊 Prediction result: {win_lose_status}")

                next_issue = str(int(latest_issue) + 1)

                # Session check
                current_session_count = await predictions_collection.count_documents({
                    "issue_number": {"$gte": SESSION_START_ISSUE},
                    "win_lose": {"$ne": None}
                })

                if current_session_count >= 20:
                    SESSION_START_ISSUE = next_issue
                    debug_log(f"🔄 New session started: {SESSION_START_ISSUE}")

                # Check losing streak
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

                debug_log(f"📊 Current losing streak: {current_lose_streak}")

                # Alert for 5+ losses
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
                        debug_log(f"📨 Alert sent to owner")
                    except Exception as e:
                        debug_log(f"❌ Alert error: {e}", "ERROR")

                # Get history for prediction
                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)
                debug_log(f"📊 Loaded {len(history_docs)} history records")

                # Make prediction
                try:
                    mem_pred, mem_prob, mem_logic = await asyncio.to_thread(
                        dynamic_history_predict, history_docs
                    )
                    predicted = mem_pred
                    reason = mem_logic
                    final_prob = mem_prob
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
                debug_log(f"💾 Saved prediction: {next_issue} -> {predicted_result_db}")

                # Bet advice
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

                # Get session predictions
                pred_cursor = predictions_collection.find({
                    "issue_number": {"$gte": SESSION_START_ISSUE},
                    "win_lose": {"$ne": None}
                }).sort("issue_number", -1)

                session_preds = await pred_cursor.to_list(length=20)
                debug_log(f"📊 Found {len(session_preds)} session predictions")

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
                unique_filename = f"winrate_chart_{int(time.time())}.png"
                photo = BufferedInputFile(img_buf.read(), filename=unique_filename)

                # Prepare message
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

                # Send/update message
                if MAIN_MESSAGE_ID:
                    try:
                        media = InputMediaPhoto(media=photo, caption=tg_caption, parse_mode="HTML")
                        await bot.edit_message_media(
                            chat_id=CHANNEL_ID,
                            message_id=MAIN_MESSAGE_ID,
                            media=media
                        )
                        debug_log(f"📨 Updated message: {MAIN_MESSAGE_ID}")
                    except Exception as e:
                        debug_log(f"⚠️ Edit error: {e}")
                        msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                        MAIN_MESSAGE_ID = msg.message_id
                        debug_log(f"📨 New message: {MAIN_MESSAGE_ID}")
                else:
                    msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                    MAIN_MESSAGE_ID = msg.message_id
                    debug_log(f"📨 First message: {MAIN_MESSAGE_ID}")

                return True
        else:
            debug_log("ℹ️ No records found")
            return False
    else:
        debug_log(f"❌ API error: {data}", "ERROR")
        if data and data.get('code') == 401:
            debug_log("🔄 Token expired, clearing...")
            CURRENT_TOKEN = ""
        return False

    return False

# ==========================================
# ⏱️ SCHEDULER WITH DEBUG
# ==========================================
async def auto_broadcaster_with_bet():
    """Main scheduler with debug"""
    global AUTO_BET, LOGIN_ATTEMPTS
    
    debug_log("🚀 ===== STARTING AUTO BROADCASTER =====")
    await init_db()
    
    async with aiohttp.ClientSession() as session:
        # Get token
        token_ok = await ensure_valid_token(session)
        if not token_ok:
            debug_log("❌ Failed to get token", "ERROR")
        
        while True:
            current_time = time.time()
            sec_passed = int(current_time) % 30
            
            # Debug: Show timing
            if sec_passed == 0:
                debug_log(f"⏰ New cycle: {datetime.now().strftime('%H:%M:%S')}")
            
            # Token check every minute
            if int(current_time) % 60 == 0:
                debug_log("🔄 Periodic token check...")
                await ensure_valid_token(session)
            
            # Main execution window
            if 5 <= sec_passed <= 28:
                debug_log(f"⏰ Execution window: {sec_passed}s")
                
                try:
                    is_processed = await check_game_and_predict(session)
                    if is_processed:
                        debug_log("✅ Prediction processed")
                        
                        # Auto bet if enabled
                        if AUTO_BET["enabled"]:
                            debug_log("🎯 AutoBet is enabled, placing bet...")
                            await auto_bet_handler(session)
                        
                        # Skip to next cycle
                        sleep_time = 30 - (int(time.time()) % 30)
                        if sleep_time > 0:
                            debug_log(f"⏳ Sleeping {sleep_time}s until next cycle")
                            await asyncio.sleep(sleep_time)
                        continue
                except Exception as e:
                    debug_log(f"❌ Error in main loop: {e}", "ERROR")
                    await asyncio.sleep(2)
            
            await asyncio.sleep(0.5)

async def init_db():
    """Initialize MongoDB"""
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        debug_log("✅ MongoDB connected and indexes created")
    except Exception as e:
        debug_log(f"❌ MongoDB error: {e}", "ERROR")

# ==========================================
# 🤖 TELEGRAM COMMANDS
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    debug_log(f"📨 /start from {message.from_user.id}")
    await message.reply(
        "👋 <b>Welcome to AI Prediction Bot!</b>\n\n"
        "📌 <b>Commands:</b>\n"
        "/autobet - Start Auto Bet\n"
        "/stopbet - Stop Auto Bet\n"
        "/betstat - Show Statistics\n"
        "/betsettings - Change Settings\n"
        "/status - Check System Status\n"
        "/debug - Toggle Debug Mode\n\n"
        "⚠️ Use at your own risk!"
    )

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    global DEBUG
    DEBUG = not DEBUG
    debug_log(f"🐛 Debug mode: {'ON' if DEBUG else 'OFF'}")
    await message.reply(f"🐛 Debug mode: {'ON' if DEBUG else 'OFF'}")

@dp.message(Command("autobet"))
async def cmd_autobet(message: types.Message):
    global AUTO_BET
    
    debug_log(f"📨 /autobet from {message.from_user.id}")

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
    
    debug_log(f"📨 /stopbet from {message.from_user.id}")

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
    debug_log(f"📨 /betstat from {message.from_user.id}")
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
    
    debug_log(f"📨 /betsettings from {message.from_user.id}")

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
    debug_log(f"📨 /status from {message.from_user.id}")
    stats = get_bet_stats()
    msg = (
        f"📊 <b>System Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔐 <b>Token:</b> {'✅ Valid' if CURRENT_TOKEN else '❌ Missing'}\n"
        f"🐛 <b>Debug:</b> {'🟢 ON' if DEBUG else '🔴 OFF'}\n"
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
    print("=" * 60)
    print("🚀 AI Prediction + AutoBet Bot Starting...")
    print(f"🐛 Debug Mode: {'ON' if DEBUG else 'OFF'}")
    print(f"📊 Game: {AUTO_BET['game_type']}")
    print(f"💰 Base Amount: {AUTO_BET['base_amount']}")
    print("=" * 60)
    
    debug_log("🔧 Bot initialization started")
    
    await bot.delete_webhook(drop_pending_updates=True)
    debug_log("✅ Webhook cleared")
    
    asyncio.create_task(auto_broadcaster_with_bet())
    debug_log("✅ Scheduler started")
    
    debug_log("🚀 Bot is ready!")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ Bot stopped by user.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
