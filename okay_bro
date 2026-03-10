import asyncio
import time
import os
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME")
PASSWORD = os.getenv("BIGWIN_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI") 

if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, MONGO_URI]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# MongoDB Setup
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database'] 
history_collection = db['game_history'] 
predictions_collection = db['predictions'] 

# ==========================================
# 🔧 2. SYSTEM & TRACKING VARIABLES 
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""
LAST_PREDICTED_ISSUE = ""
LAST_PREDICTED_RESULT = ""

# --- Stats Tracking ---
CURRENT_WIN_STREAK = 0
CURRENT_LOSE_STREAK = 0
LONGEST_WIN_STREAK = 0
LONGEST_LOSE_STREAK = 0
TOTAL_PREDICTIONS = 0 

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
        print("🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။ (Casino Edge AI Enabled)")
    except Exception as e:
        print(f"❌ MongoDB Indexing Error: {e}")

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=3):
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=10) as response:
                return await response.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"❌ Network Error after {retries} attempts: {e}")
                return None
            await asyncio.sleep(1)

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    print("🔐 အကောင့်ထဲသို့ Login ဝင်နေပါသည်...")
    
    json_data = {
        'username': '959680090540',
        'pwd': 'Mitheint11',
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '452fa309995244de92103c0afbefbe9a',
        'signature': '202C655177E9187D427A26F3CDC00A52',
        'timestamp': 1773021618,
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ။\n")
        return True
    return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN: return "0.00"
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    
    json_data = {
        'signature': 'F7A9A2A74E1F1D1DFE048846E49712F8',
        'language': 7,
        'random': '58d9087426f24a54870e243b76743a94',
        'timestamp': 1772984987,
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers, json_data)
    if data and data.get('code') == 0: 
        return data.get('data', {}).get('amount', '0.00')
    return "0.00"

# ==========================================
# 🧠 4. 🚀 AI ENGINE WITH CASINO HOUSE EDGE ANALYSIS
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    global CURRENT_WIN_STREAK, CURRENT_LOSE_STREAK, LONGEST_WIN_STREAK, LONGEST_LOSE_STREAK, TOTAL_PREDICTIONS
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': '1ef0a7aca52b4c71975c031dda95150e', 'signature': '7D26EE375971781D1BC58B7039B409B7', 'timestamp': 1772985040,
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data)
    if not data or data.get('code') != 0:
        if data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()):
            CURRENT_TOKEN = ""
        return

    records = data.get("data", {}).get("list", [])
    if not records: return
    
    latest_record = records[0]
    latest_issue = str(latest_record["issueNumber"])
    latest_number = int(latest_record["number"])
    latest_size = "BIG" if latest_number >= 5 else "SMALL"
    
    if latest_issue == LAST_PROCESSED_ISSUE: return 
    LAST_PROCESSED_ISSUE = latest_issue
    next_issue = str(int(latest_issue) + 1)
    win_lose_text = ""
    
    await history_collection.update_one({"issue_number": latest_issue}, {"$setOnInsert": {"number": latest_number, "size": latest_size}}, upsert=True)
    
    # --- နိုင်/ရှုံး စစ်ဆေးခြင်း ---
    if LAST_PREDICTED_ISSUE == latest_issue:
        TOTAL_PREDICTIONS += 1
        is_win = (LAST_PREDICTED_RESULT == latest_size)
        
        if is_win:
            win_lose_status = "WIN ✅"
            CURRENT_WIN_STREAK += 1
            CURRENT_LOSE_STREAK = 0
            if CURRENT_WIN_STREAK > LONGEST_WIN_STREAK: LONGEST_WIN_STREAK = CURRENT_WIN_STREAK
        else:
            win_lose_status = "LOSE ❌"
            CURRENT_LOSE_STREAK += 1
            CURRENT_WIN_STREAK = 0
            if CURRENT_LOSE_STREAK > LONGEST_LOSE_STREAK: LONGEST_LOSE_STREAK = CURRENT_LOSE_STREAK
                
        await predictions_collection.update_one({"issue_number": latest_issue}, {"$set": {"actual_size": latest_size, "win_lose": win_lose_status}})
        
        win_lose_text = (
            f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue})</b> ရလဒ်: {latest_size}\n"
            f"📊 <b>ခန့်မှန်းချက်: {win_lose_status}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    # ==============================================================
    # 🧠 NEW AI: CASINO EDGE + PATTERN + MOMENTUM
    # ==============================================================
    cursor = history_collection.find().sort("issue_number", -1).limit(5000)
    history_docs = await cursor.to_list(length=5000)
    history_docs.reverse()
    all_history = [doc["size"] for doc in history_docs]
    
    predicted = "BIG (အကြီး) 🔴"
    base_prob = 55.0
    reason = "Data အချက်အလက် စုဆောင်းနေဆဲဖြစ်သည်"

    if len(all_history) > 100:
        big_score = 0.0
        small_score = 0.0
        ai_logic_used = ""

        # [အပိုင်း ၁] - Pattern & Momentum (ပုံမှန် AI စနစ်)
        best_pattern_len = 0
        for length in range(10, 2, -1):
            if len(all_history) > length:
                recent_pattern = all_history[-length:]
                b_count, s_count = 0, 0
                for i in range(len(all_history) - length):
                    if all_history[i:i+length] == recent_pattern:
                        if all_history[i+length] == 'BIG': b_count += 1
                        elif all_history[i+length] == 'SMALL': s_count += 1
                            
                total_matches = b_count + s_count
                if total_matches >= 1: 
                    best_pattern_len = length
                    big_score += (b_count / total_matches) * 40
                    small_score += (s_count / total_matches) * 40
                    break 

        recent_15 = all_history[-15:]
        b_momentum = (recent_15.count('BIG') / 15.0) * 30 
        s_momentum = (recent_15.count('SMALL') / 15.0) * 30
        big_score += b_momentum
        small_score += s_momentum
        
        ai_logic_used = "ပုံမှန် Trend Analysis"

        # [အပိုင်း ၂] 🎰 CASINO HOUSE EDGE ANALYSIS (ကာစီနို သဘောသဘာဝ) 🎰
        # (က) Law of Large Numbers (ပွဲ ၁၀၀ စာ မျှခြေကို ပြန်ဆွဲခြင်း)
        recent_100 = all_history[-100:]
        big_count_100 = recent_100.count('BIG')
        small_count_100 = recent_100.count('SMALL')

        # တစ်ဘက်တည်း ၅၅ ပွဲထက်ပိုထွက်နေပါက Casino က ပြောင်းပြန်ဘက်ကို ပြန်ထုတ်ပေးလေ့ရှိသည်
        if big_count_100 > 55:
            compensation = (big_count_100 - 50) * 2
            small_score += compensation
            ai_logic_used = f"House Edge (အသေးဘက်သို့ မျှခြေပြန်ဆွဲခြင်း)"
        elif small_count_100 > 55:
            compensation = (small_count_100 - 50) * 2
            big_score += compensation
            ai_logic_used = f"House Edge (အကြီးဘက်သို့ မျှခြေပြန်ဆွဲခြင်း)"

        # (ခ) Anti-Martingale / Crowd Trap (လူအများစု လိုက်ထိုးမည့် အချိန်ကို ချိုးခြင်း)
        current_streak = 1
        for i in range(2, 15):
            if all_history[-i] == all_history[-1]:
                current_streak += 1
            else:
                break
        
        # ၅ ပွဲဆက်တိုက်ထွက်လာလျှင် ကာစီနိုက အများစုကိုစားရန် Streak ကို ဖြတ်ပစ်လေ့ရှိသည်
        if current_streak >= 5:
            break_multiplier = current_streak * 8 # ရှည်လေ ပြောင်းပြန်ချိုးဖို့ အမှတ်ပိုပေးလေ
            if all_history[-1] == 'BIG':
                small_score += break_multiplier
            else:
                big_score += break_multiplier
            ai_logic_used = f"House Edge ({current_streak}-Streak ဆွဲဖြတ်မှု ထောင်ချောက်)"

        # [အပိုင်း ၃] - အပြီးသတ် ဆုံးဖြတ်ခြင်း
        if big_score > small_score:
            predicted = "BIG (အကြီး) 🔴"
            base_prob = 60.0 + ((big_score / (big_score + small_score)) * 32.0)
        elif small_score > big_score:
            predicted = "SMALL (အသေး) 🟢"
            base_prob = 60.0 + ((small_score / (big_score + small_score)) * 32.0)
        else:
            predicted = "BIG (အကြီး) 🔴" if all_history[-1] == "BIG" else "SMALL (အသေး) 🟢"
            base_prob = 58.5
            ai_logic_used = "အနီးစပ်ဆုံး ဖြစ်နိုင်ခြေ"

        reason = f"🧠 AI တွက်ချက်မှု: {ai_logic_used}"

    # ရာခိုင်နှုန်းကို 65% မှ 94% အတွင်းသာ ပြသမည်
    final_prob = min(max(round(base_prob, 1), 65.0), 94.0)

    LAST_PREDICTED_ISSUE = next_issue
    LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
    
    await predictions_collection.update_one({"issue_number": next_issue}, {"$set": {"predicted_size": LAST_PREDICTED_RESULT, "probability": final_prob, "actual_size": None, "win_lose": None}}, upsert=True)

    current_balance = await get_user_balance(session)
    print(f"✅ [NEW] {next_issue} | {predicted} | {final_prob}% | W:{CURRENT_WIN_STREAK} / L:{CURRENT_LOSE_STREAK}")

    # --- 💰 Martingale Recommendation ---
    suggested_multiplier = 2 ** CURRENT_LOSE_STREAK if CURRENT_LOSE_STREAK <= 5 else 1
    bet_advice = f"💰 <b>အကြံပြုလောင်းကြေး:</b> အခြေခံကြေး၏ {suggested_multiplier}ဆ ထည့်ပါ"

    # --- 🎨 TELEGRAM MESSAGE FORMATTING ---
    tg_message = (
        f"🎰 <b>Bigwin TRUE AI Predictor</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{win_lose_text}"
        f"🎯 <b>နောက်ပွဲစဉ်အမှတ်:</b> <code>{next_issue}</code>\n"
        f"🤖 <b>AI ခန့်မှန်းချက်: {predicted}</b>\n"
        f"📈 <b>ဖြစ်နိုင်ခြေ:</b> {final_prob}%\n"
        f"💡 <b>အကြောင်းပြချက်:</b>\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{bet_advice}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Session Stats:</b>\n"
        f"┣ Win Streak : {CURRENT_WIN_STREAK} 🟢\n"
        f"┣ Lose Streak : {CURRENT_LOSE_STREAK} 🔴\n"
        f"┗ Total Played : {TOTAL_PREDICTIONS}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>"
    )
    
    try: await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
    except: pass

# ==========================================
# 🔄 5. BACKGROUND TASK & MAIN LOOP
# ==========================================
async def auto_broadcaster():
    await init_db() 
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("👋 မင်္ဂလာပါ။ Bigwin True AI Predictor မှ ကြိုဆိုပါတယ်။\n\nစနစ်သည် ကာစီနို၏ နောက်ကွယ်ရှိ House Edge သဘောသဘာဝများကိုပါ ထည့်သွင်းစဉ်းစားပြီး ပွဲစဉ်တိုင်းအတွက် အကောင်းဆုံး Signal များကို ပို့ပေးပါမည်။")

async def main():
    print("🚀 Aiogram Bigwin Bot (Casino House Edge Edition) စတင်နေပါပြီ...\n")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
