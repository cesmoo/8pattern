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
# 🔧 2. SYSTEM VARIABLES 
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""
LAST_PREDICTED_ISSUE = ""
LAST_PREDICTED_RESULT = ""

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
        print("🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
    except Exception as e:
        print(f"❌ MongoDB Indexing Error: {e}")

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS (မူရင်း အလုပ်လုပ်သော Payload များ ပြန်သုံးထားသည်)
# ==========================================
async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    print("🔐 အကောင့်ထဲသို့ Login ဝင်နေပါသည်...")
    
    # ⚠️ အသေချာဆုံး မူရင်း Login Payload
    json_data = {
        'username': '959680090540',
        'pwd': 'Mitheint11',
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '87f226ed2caa47dbabae1764c9c3958c',
        'signature': '5127867D3DE7581DE6D36591BF3FBA22',
        'timestamp': 1772987092,
    }
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/Login', headers=BASE_HEADERS, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
                CURRENT_TOKEN = f"Bearer {token_str}"
                print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ။\n")
                return True
            else:
                print(f"❌ Login Error: {data.get('msg')}")
                return False
    except Exception as e: 
        print(f"❌ Request Error: {e}")
        return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN: return "0.00"
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    
    # ⚠️ မူရင်း Balance Payload
    json_data = {
        'signature': 'F7A9A2A74E1F1D1DFE048846E49712F8',
        'language': 7,
        'random': '58d9087426f24a54870e243b76743a94',
        'timestamp': 1772984987,
    }
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0: return data.get('data', {}).get('amount', '0.00')
            return "0.00"
    except: return "0.00"

# ==========================================
# 🧠 4. AI DYNAMIC PREDICT LOGIC (Signal Only)
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    # ⚠️ မူရင်း Data Fetching Payload
    json_data = {
        'pageSize': 10,
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': '1ef0a7aca52b4c71975c031dda95150e',
        'signature': '7D26EE375971781D1BC58B7039B409B7',
        'timestamp': 1772985040,
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
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
                
                # နိုင်/ရှုံး စစ်ဆေးခြင်း
                if LAST_PREDICTED_ISSUE == latest_issue:
                    is_win = (LAST_PREDICTED_RESULT == latest_size)
                    win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                    
                    await predictions_collection.update_one({"issue_number": latest_issue}, {"$set": {"actual_size": latest_size, "win_lose": win_lose_status}})
                    
                    win_lose_text = (
                        f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue}) ရလဒ်:</b> {latest_size}\n"
                        f"📊 <b>ခန့်မှန်းချက်:</b> <b>{win_lose_status}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                    )

                # --- AI Pattern (10-Pattern Dynamic Learning) ---
                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)
                history_docs.reverse()
                all_history = [doc["size"] for doc in history_docs]
                
                MAX_PATTERN_LENGTH = 10
                MIN_PATTERN_LENGTH = 3
                pattern_found = False
                
                for current_len in range(MAX_PATTERN_LENGTH, MIN_PATTERN_LENGTH - 1, -1):
                    if len(all_history) > current_len:
                        recent_pattern = all_history[-current_len:]
                        big_next_count = 0
                        small_next_count = 0
                        for i in range(len(all_history) - current_len):
                            if all_history[i:i+current_len] == recent_pattern:
                                next_result = all_history[i+current_len]
                                if next_result == 'BIG': big_next_count += 1
                                elif next_result == 'SMALL': small_next_count += 1
                                    
                        total_pattern_matches = big_next_count + small_next_count
                        if total_pattern_matches > 0:
                            big_prob = (big_next_count / total_pattern_matches) * 100
                            small_prob = (small_next_count / total_pattern_matches) * 100
                            pattern_str = "-".join(recent_pattern).replace('BIG', 'B').replace('SMALL', 'S')
                            
                            if big_prob > small_prob:
                                predicted, base_prob = "BIG (အကြီး) 🔴", big_prob
                                reason = f"[{pattern_str}] လာလျှင် အကြီးဆက်ထွက်လေ့ရှိ၍"
                            elif small_prob > big_prob:
                                predicted, base_prob = "SMALL (အသေး) 🟢", small_prob
                                reason = f"[{pattern_str}] လာလျှင် အသေးဆက်ထွက်လေ့ရှိ၍"
                            else:
                                predicted, base_prob = "BIG (အကြီး) 🔴", 50.0
                                reason = f"[{pattern_str}] အရင်က မျှခြေထွက်ဖူး၍ အကြီးရွေးထားသည်"
                            pattern_found = True
                            break 
                            
                if not pattern_found:
                    predicted = "BIG (အကြီး) 🔴" if all_history.count("SMALL") > all_history.count("BIG") else "SMALL (အသေး) 🟢"
                    base_prob = 55.0
                    reason = "Pattern အသစ်ဖြစ်နေသဖြင့် သမိုင်းကြောင်းအရ တွက်ချက်ထားသည်"

                final_prob = min(round(base_prob, 1), 85.0)

                LAST_PREDICTED_ISSUE = next_issue
                LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
                
                await predictions_collection.update_one({"issue_number": next_issue}, {"$set": {"predicted_size": LAST_PREDICTED_RESULT, "probability": final_prob, "actual_size": None, "win_lose": None}}, upsert=True)

                current_balance = await get_user_balance(session)
                print(f"✅ [NEW] ပွဲစဉ်: {next_issue} | Predict: {predicted}")

                # Telegram သို့ ပို့မည့် Message
                tg_message = (
                    f"🎰 <b>Bigwin 30-Seconds (AI Predictor)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{win_lose_text}"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{predicted}</b>\n"
                    f"📈 <b>ဖြစ်နိုင်ခြေ :</b> <b>{final_prob}%</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>\n"
                    f"⚠️ <i>ခန့်မှန်းချက်သာဖြစ်သဖြင့် ကိုယ်ပိုင်ချင့်ချိန်၍ ကစားပါ။</i>"
                )
                
                try: await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                except: pass
                
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                CURRENT_TOKEN = ""
    except Exception as e: print(f"❌ Game Data Request Error: {e}")

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
    await message.reply("👋 မင်္ဂလာပါ။ Bigwin AI Predictor Bot မှ ကြိုဆိုပါတယ်။\n\nလက်ရှိ အခြေအနေကို ကြည့်ရန် /status ကို နှိပ်ပါ။\nWin Rate ကြည့်ရန် /stats ကို နှိပ်ပါ။")

@dp.message(Command("status"))
async def check_status(message: types.Message):
    loading_msg = await message.reply("🔄 အချက်အလက်များ ဆွဲယူနေပါသည်...")
    async with aiohttp.ClientSession() as session:
        balance = await get_user_balance(session)
        status_text = (
            f"📊 <b>Account Status</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔹 <b>Account :</b> <code>{USERNAME}</code>\n"
            f"🔹 <b>Balance :</b> <code>{balance}</code> Ks\n"
            f"🔹 <b>Bot Status :</b> 🟢 Signal Active"
        )
        await loading_msg.edit_text(status_text)

@dp.message(Command("stats"))
async def check_stats(message: types.Message):
    loading_msg = await message.reply("🔄 အချက်အလက်များ ဆွဲယူနေပါသည်...")
    try:
        total = await predictions_collection.count_documents({"win_lose": {"$ne": None}})
            
        if total == 0:
            await loading_msg.edit_text("⚠️ ယခုလောလောဆယ် Win Rate တွက်ချက်ရန် အချက်အလက် မရှိသေးပါ။ ခဏစောင့်ပေးပါ။")
            return

        cursor = predictions_collection.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(50)
        last_50_results = await cursor.to_list(length=50)
        
        wins = sum(1 for doc in last_50_results if "WIN" in doc.get("win_lose", ""))
        total_eval = len(last_50_results)
        losses = total_eval - wins
        win_rate = (wins / total_eval) * 100 if total_eval > 0 else 0

        stats_msg = (
            f"📈 <b>နောက်ဆုံး ပွဲစဉ် ({total_eval}) ခုအတွက် မှတ်တမ်း</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>နိုင်ပွဲ :</b> {wins} ပွဲ\n"
            f"❌ <b>ရှုံးပွဲ :</b> {losses} ပွဲ\n"
            f"📊 <b>Win Rate :</b> <b>{win_rate:.1f}%</b>\n"
        )
        await loading_msg.edit_text(stats_msg)
    except Exception as e:
        await loading_msg.edit_text(f"❌ Database အမှားအယွင်း ဖြစ်ပေါ်ခဲ့ပါသည်။ ({e})")

async def main():
    print("🚀 Aiogram Bigwin Bot (AI Signal Mode) စတင်နေပါပြီ...\n")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
