import asyncio
import time
import os
import json
import hashlib
import uuid
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
TOTAL_SKIPS = 0

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
        print("🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။ (AI Data Enrichment Enabled)")
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
# 🧠 4. 🚀 MULTI-FACTOR AI & DATA ENRICHMENT
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    global CURRENT_WIN_STREAK, CURRENT_LOSE_STREAK, LONGEST_WIN_STREAK, LONGEST_LOSE_STREAK, TOTAL_PREDICTIONS, TOTAL_SKIPS
    
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
    latest_parity = "EVEN" if latest_number % 2 == 0 else "ODD" # မ/စုံ သတ်မှတ်ခြင်း
    
    if latest_issue == LAST_PROCESSED_ISSUE: return 
    LAST_PROCESSED_ISSUE = latest_issue
    next_issue = str(int(latest_issue) + 1)
    win_lose_text = ""
    
    # သိမ်းဆည်းရာတွင် Number နှင့် Parity(မ/စုံ) ကိုပါ တွဲသိမ်းမည်
    await history_collection.update_one(
        {"issue_number": latest_issue}, 
        {"$setOnInsert": {"number": latest_number, "size": latest_size, "parity": latest_parity}}, 
        upsert=True
    )
    
    # --- နိုင်/ရှုံး စစ်ဆေးခြင်း ---
    if LAST_PREDICTED_ISSUE == latest_issue and LAST_PREDICTED_RESULT != "SKIP":
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
            f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue})</b> ရလဒ်: {latest_number} ({latest_size})\n"
            f"📊 <b>ခန့်မှန်းချက်: {win_lose_status}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
    elif LAST_PREDICTED_ISSUE == latest_issue and LAST_PREDICTED_RESULT == "SKIP":
        TOTAL_SKIPS += 1
        win_lose_text = (
            f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue})</b> ရလဒ်: {latest_number} ({latest_size})\n"
            f"🛡 <b>စောင့်ကြည့်ခြင်း: အောင်မြင်ပါသည်</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    # ==============================================================
    # 🧠 TRUE AI: Multi-Factor Correlation Engine
    # ==============================================================
    cursor = history_collection.find().sort("issue_number", -1).limit(5000)
    history_docs = await cursor.to_list(length=5000)
    history_docs.reverse() # အဟောင်းမှ အသစ်သို့
    
    # Data များကို အမျိုးအစားခွဲခြား ဆွဲထုတ်မည်
    all_sizes = [doc.get("size") for doc in history_docs]
    all_numbers = [doc.get("number") for doc in history_docs]
    all_parities = [doc.get("parity", "EVEN" if int(doc.get("number",0))%2==0 else "ODD") for doc in history_docs]
    
    predicted = "BIG (အကြီး) 🔴"
    base_prob = 50.0
    reason = "Data မလုံလောက်သေးပါ"
    is_skip = False

    if len(all_sizes) > 100:
        big_score = 0.0
        small_score = 0.0
        reasons_list = []

        # ---------------------------------------------------------
        # FACTOR 1: Number-to-Size Correlation (ဂဏန်းဆက်စပ်မှု)
        # နောက်ဆုံးထွက်ခဲ့သော ဂဏန်း (ဥပမာ- '8') ထွက်ပြီးတိုင်း နောက်ပွဲတွင် အကြီး/အသေး ဘာထွက်လေ့ရှိသနည်း
        # ---------------------------------------------------------
        last_num = all_numbers[-1]
        b_after_num = 0
        s_after_num = 0
        for i in range(len(all_numbers) - 1):
            if all_numbers[i] == last_num:
                if all_sizes[i+1] == 'BIG': b_after_num += 1
                elif all_sizes[i+1] == 'SMALL': s_after_num += 1
        
        tot_num_cases = b_after_num + s_after_num
        if tot_num_cases > 5:
            b_num_prob = b_after_num / tot_num_cases
            s_num_prob = s_after_num / tot_num_cases
            big_score += b_num_prob * 25  # Maximum 25 points
            small_score += s_num_prob * 25
            if max(b_num_prob, s_num_prob) > 0.65:
                reasons_list.append(f"Number '{last_num}' Correlation")

        # ---------------------------------------------------------
        # FACTOR 2: Parity Pattern (မ/စုံ ပုံစံကို ကြည့်ပြီး အကြီး/အသေး တွက်ချက်ခြင်း)
        # ---------------------------------------------------------
        if len(all_parities) > 3:
            recent_parity_pattern = all_parities[-3:]
            b_after_parity = 0
            s_after_parity = 0
            for i in range(len(all_parities) - 3):
                if all_parities[i:i+3] == recent_parity_pattern:
                    if all_sizes[i+3] == 'BIG': b_after_parity += 1
                    elif all_sizes[i+3] == 'SMALL': s_after_parity += 1
            
            tot_parity_cases = b_after_parity + s_after_parity
            if tot_parity_cases > 5:
                b_par_prob = b_after_parity / tot_parity_cases
                s_par_prob = s_after_parity / tot_parity_cases
                big_score += b_par_prob * 20  # Maximum 20 points
                small_score += s_par_prob * 20
                if max(b_par_prob, s_par_prob) > 0.65:
                    reasons_list.append("Odd/Even Matrix")

        # ---------------------------------------------------------
        # FACTOR 3: Deep Size Pattern Matching
        # ---------------------------------------------------------
        pattern_found = False
        for length in range(8, 2, -1):
            if len(all_sizes) > length:
                recent_sz_pattern = all_sizes[-length:]
                b_count, s_count = 0, 0
                for i in range(len(all_sizes) - length):
                    if all_sizes[i:i+length] == recent_sz_pattern:
                        if all_sizes[i+length] == 'BIG': b_count += 1
                        elif all_sizes[i+length] == 'SMALL': s_count += 1
                
                tot_sz_matches = b_count + s_count
                if tot_sz_matches >= 2:
                    b_sz_prob = b_count / tot_sz_matches
                    s_sz_prob = s_count / tot_sz_matches
                    # အလေးပေးမှု (Pattern ရှည်လေ အမှတ်ပိုရလေ)
                    weight = 20 + (length * 2) 
                    big_score += b_sz_prob * weight
                    small_score += s_sz_prob * weight
                    
                    if max(b_sz_prob, s_sz_prob) > 0.6:
                        reasons_list.append(f"{length}-Pattern Sync")
                    pattern_found = True
                    break # အကောင်းဆုံးတစ်ခု တွေ့လျှင် ရပ်မည်
        
        # ---------------------------------------------------------
        # FACTOR 4: Momentum & Streak Breaker (ရေစီးကြောင်းနှင့် ပြတ်တောက်နိုင်ခြေ)
        # ---------------------------------------------------------
        recent_15 = all_sizes[-15:]
        b_mom = recent_15.count('BIG') / 15.0
        s_mom = recent_15.count('SMALL') / 15.0
        big_score += b_mom * 15
        small_score += s_mom * 15

        current_streak_len = 1
        last_color = all_sizes[-1]
        for i in range(2, 10):
            if len(all_sizes) >= i and all_sizes[-i] == last_color:
                current_streak_len += 1
            else:
                break
                
        if current_streak_len >= 5:
            reasons_list.append(f"{current_streak_len}-Streak Risk Limit")
            # ဆက်တိုက်ထွက်လွန်းပါက ပြောင်းပြန်ဘက်ကို အမှတ်တိုးပေးမည် (Reversal Prediction)
            if last_color == 'BIG':
                small_score += current_streak_len * 4
            else:
                big_score += current_streak_len * 4

        # ---------------------------------------------------------
        # FINAL AI SCORING DECISION
        # ---------------------------------------------------------
        total_score = big_score + small_score
        if total_score > 0:
            final_b_prob = (big_score / total_score) * 100
            final_s_prob = (small_score / total_score) * 100
            
            if final_b_prob > final_s_prob:
                best_choice = "BIG"
                base_prob = final_b_prob
            else:
                best_choice = "SMALL"
                base_prob = final_s_prob
                
            # Conflict / High Risk Detection (ရမှတ်များ ကပ်နေပါက)
            score_difference = abs(final_b_prob - final_s_prob)
            if score_difference < 12.0: # ကွာဟချက် ၁၂% အောက်ဆိုလျှင် သေချာမှုမရှိပါ
                is_skip = True
                
            predicted = "BIG (အကြီး) 🔴" if best_choice == "BIG" else "SMALL (အသေး) 🟢"
            
            # အကြောင်းပြချက်များကို ပေါင်းစပ်မည်
            unique_reasons = list(set(reasons_list))
            reason = f"🧠 AI Analysis: [{', '.join(unique_reasons[:3])}]" if unique_reasons else "📊 Statistical Optimization"
        else:
            is_skip = True

    # Probability Limiting
    final_prob = min(max(round(base_prob, 1), 50.0), 96.0)

    # 🛑 Skip Override
    if is_skip or final_prob < 58.0:
        predicted = "SKIP (စောင့်ပါ) ⏳"
        final_prob = 0.0
        reason = "⚠️ Algorithm များ အချင်းချင်း ဆန့်ကျင်နေသဖြင့် ငွေကြေးအန္တရာယ်ကို ရှောင်လွှဲခြင်း"
        LAST_PREDICTED_RESULT = "SKIP"
        tier_icon = "⚠️"
        tier_text = "RISK ALERT / မထိုးပါနှင့်"
    else:
        LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
        # Determine Signal Tier
        if final_prob >= 78.0:
            tier_icon, tier_text = "🔥", "VIP MULTI-FACTOR SIGNAL"
        elif final_prob >= 65.0:
            tier_icon, tier_text = "💎", "HIGH CONFIDENCE"
        else:
            tier_icon, tier_text = "🟢", "NORMAL PREDICTION"

    await predictions_collection.update_one({"issue_number": next_issue}, {"$set": {"predicted_size": LAST_PREDICTED_RESULT, "probability": final_prob, "actual_size": None, "win_lose": None}}, upsert=True)

    # --- 💰 Martingale Recommendation ---
    suggested_multiplier = 2 ** CURRENT_LOSE_STREAK if CURRENT_LOSE_STREAK <= 5 else 1
    bet_advice = f"💰 <b>အကြံပြုလောင်းကြေး:</b> {suggested_multiplier}x (အခြေခံကြေး၏ {suggested_multiplier}ဆ)" if not is_skip else "💰 <b>အကြံပြုချက်:</b> ယခုပွဲကို လောင်းကြေး မထည့်ပါနှင့်"

    current_balance = await get_user_balance(session)
    print(f"✅ [NEW] {next_issue} | {predicted} | WR: {final_prob}% | W:{CURRENT_WIN_STREAK}/L:{CURRENT_LOSE_STREAK}")

    # --- 🎨 PRO TELEGRAM MESSAGE FORMATTING ---
    tg_message = (
        f"🎰 <b>Bigwin TRUE AI Predictor</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{win_lose_text}"
        f"🎯 <b>နောက်ပွဲစဉ်အမှတ်:</b> <code>{next_issue}</code>\n"
        f"{tier_icon} <b>Signal Type: {tier_text}</b>\n"
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
        f"┗ Total Played : {TOTAL_PREDICTIONS} (Skips: {TOTAL_SKIPS})\n"
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
    await message.reply("👋 မင်္ဂလာပါ။ Bigwin True AI Predictor မှ ကြိုဆိုပါတယ်။\n\nဂဏန်း (၀-၉)၊ မ/စုံ နှင့် ရေစီးကြောင်းများကို ပေါင်းစပ်သုံးသပ်ပြီး အကောင်းဆုံး Signal များကိုသာ ပို့ပေးပါမည်။")

async def main():
    print("🚀 Aiogram Bigwin Bot (TRUE AI Multi-Factor Edition) စတင်နေပါပြီ...\n")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
