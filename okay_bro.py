import asyncio
import time
import os
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio # MongoDB အတွက်

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION (ပြင်ဆင်ရန် အပိုင်း)
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME")
PASSWORD = os.getenv("BIGWIN_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI") # MongoDB URI အသစ်

if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, MONGO_URI]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ (MONGO_URI အပါအဝင်) ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🗄 2. MONGODB SETUP (စနစ်ပိုင်းဆိုင်ရာ)
# ==========================================
# MongoDB သို့ လှမ်းချိတ်ဆက်ခြင်း
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database'] # Database အမည်
history_collection = db['game_history'] # History သိမ်းမည့် Collection
predictions_collection = db['predictions'] # Predictions သိမ်းမည့် Collection

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
    """MongoDB တွင် Duplicate မဖြစ်စေရန် Issue Number ကို Unique Index အဖြစ် သတ်မှတ်ခြင်း"""
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        print("🗄 MongoDB Database ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
    except Exception as e:
        print(f"❌ MongoDB Indexing Error: {e}")

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS
# ==========================================
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
        'random': 'd85ed31c80a9447d9c2eb8e713b6046d',
        'signature': 'EAEF4EF352C07BF7852E39B5AB2F4151',
        'timestamp': 1772969564,
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/Login', headers=BASE_HEADERS, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                token_data = data.get('data', {})
                token_str = token_data if isinstance(token_data, str) else token_data.get('token', '')
                CURRENT_TOKEN = f"Bearer {token_str}"
                print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ။\n")
                return True
            else:
                print(f"❌ Login Failed: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"❌ Login Request Error: {e}")
        return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return "0.00"

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'signature': '98BA4B555CD283B47C8F9F6C800DF741',
        'language': 7,
        'random': 'd36e1e8dadca4bdd8d5f2e08f1b06c56',
        'timestamp': int(time.time()),
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('amount', '0.00')
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                CURRENT_TOKEN = ""
                return await get_user_balance(session) 
            return "0.00"
    except Exception:
        return "0.00"

# ==========================================
# 🧠 4. AI DYNAMIC PREDICT & MONGODB LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10,  
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': '85b82082418845c593a2641ae50af6de',
        'signature': 'E7C0AAF6D1B429E89F83CA6FDBF3D4FC',
        'timestamp': int(time.time()),
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
                
                if latest_issue == LAST_PROCESSED_ISSUE:
                    return 
                    
                LAST_PROCESSED_ISSUE = latest_issue
                next_issue = str(int(latest_issue) + 1)
                
                win_lose_text = ""
                
                # ၁။ မှတ်တမ်းအသစ်ကို MongoDB ထဲသိမ်းမည် (ရှိပြီးသားဆိုလျှင် ကျော်သွားမည် - upsert)
                await history_collection.update_one(
                    {"issue_number": latest_issue},
                    {"$setOnInsert": {"number": latest_number, "size": latest_size}},
                    upsert=True
                )
                
                # ၂။ ရှေ့က ခန့်မှန်းခဲ့တာ မှန်/မမှန် စစ်ဆေးမည်
                if LAST_PREDICTED_ISSUE == latest_issue:
                    is_win = (LAST_PREDICTED_RESULT == latest_size)
                    win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                    
                    await predictions_collection.update_one(
                        {"issue_number": latest_issue},
                        {"$set": {"actual_size": latest_size, "win_lose": win_lose_status}}
                    )
                    
                    win_lose_text = (
                        f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue}) ရလဒ်:</b> {latest_size}\n"
                        f"📊 <b>ခန့်မှန်းချက်:</b> <b>{win_lose_status}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                    )

                # ၃။ ပွဲစဉ် ၅၀ ပြည့်တိုင်း Win Rate Report ပို့မည်
                total_evaluated = await predictions_collection.count_documents({"win_lose": {"$ne": None}})
                if total_evaluated > 0 and total_evaluated % 50 == 0 and LAST_PREDICTED_ISSUE == latest_issue:
                    cursor = predictions_collection.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(50)
                    last_50_results = await cursor.to_list(length=50)
                    
                    wins = sum(1 for doc in last_50_results if "WIN" in doc.get("win_lose", ""))
                    losses = 50 - wins
                    win_rate = (wins / 50) * 100

                    stats_msg = (
                        f"📈 <b>ပွဲစဉ် ၅၀ ပြည့် Win Rate မှတ်တမ်း</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ <b>နိုင်ပွဲ :</b> {wins} ပွဲ\n"
                        f"❌ <b>ရှုံးပွဲ :</b> {losses} ပွဲ\n"
                        f"📊 <b>Win Rate :</b> <b>{win_rate:.1f}%</b>\n"
                    )
                    try:
                        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=stats_msg)
                    except: pass

                # ၄။ AI DYNAMIC LEARNING (Pattern Matching)
                # လေ့လာရန်အတွက် နောက်ဆုံးပွဲစဉ် ၅၀၀၀ ကို ဆွဲထုတ်မည် (များလေ ပိုကောင်းလေဖြစ်၍ 1000 မှ 5000 သို့ တိုးထားပါသည်)
                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)
                history_docs.reverse() # အဟောင်းမှ အသစ်သို့ ပြန်စီမည်
                
                all_history = [doc["size"] for doc in history_docs]
                
                # 10 pattern အထိ ရှာမည်၊ မတွေ့ပါက 9, 8... 3 အထိ လျှော့ရှာမည့် Dynamic စနစ်
                MAX_PATTERN_LENGTH = 10
                MIN_PATTERN_LENGTH = 4
                
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
                        
                        # အနည်းဆုံး သမိုင်းကြောင်းမှာ ၁ ကြိမ် အထက်တွေ့ဖူးမှသာ အတည်ယူမည်
                        if total_pattern_matches > 0:
                            big_prob = (big_next_count / total_pattern_matches) * 100
                            small_prob = (small_next_count / total_pattern_matches) * 100
                            
                            # [B-S-B-B-S-B-S-B-B-S] ဟု တိုတိုရှင်းရှင်းပြရန်
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
                            break # Pattern တစ်ခုတွေ့တာနဲ့ ဆက်မရှာတော့ဘဲ For loop မှ ထွက်မည်
                            
                if not pattern_found:
                    # မည်သည့် Pattern မှ (3 ထိတောင်) မတွေ့ခဲ့လျှင် သို့မဟုတ် Data မပြည့်သေးလျှင်
                    predicted = "BIG (အကြီး) 🔴" if all_history.count("SMALL") > all_history.count("BIG") else "SMALL (အသေး) 🟢"
                    base_prob = 55.0
                    reason = "Pattern အသစ်ဖြစ်နေသဖြင့် သမိုင်းကြောင်းအရ တွက်ချက်ထားသည်"

                final_prob = min(round(base_prob, 1), 85.0)

                # ၅။ နောက်ပွဲစဉ်အတွက် ခန့်မှန်းချက်ကို MongoDB တွင် သိမ်းမည်
                LAST_PREDICTED_ISSUE = next_issue
                LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
                
                # MongoDB တွင် Unique Key Error မတက်စေရန် insert_one အစား update_one (upsert) သုံးထားပါသည်
                await predictions_collection.update_one(
                    {"issue_number": next_issue},
                    {"$set": {
                        "predicted_size": LAST_PREDICTED_RESULT,
                        "probability": final_prob,
                        "actual_size": None,
                        "win_lose": None
                    }},
                    upsert=True
                )

                current_balance = await get_user_balance(session)
                print(f"✅ [NEW] ပွဲစဉ်: {latest_issue} -> 🤖 AI Predict: {predicted}")

                # Telegram သို့ ပို့မည့် Message
                tg_message = (
                    f"🎰 <b>Bigwin 30-Seconds</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{win_lose_text}"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{predicted}</b>\n"
                    f"📈 <b>ဖြစ်နိုင်ခြေ :</b> <b>{final_prob}%</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>\n"
                    f"⚠️ <i>(ခန့်မှန်းချက်သာဖြစ်သဖြင့် ချင့်ချိန်၍ ကစားပါ။)</i>"
                )
                
                try:
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                except Exception as e:
                    print(f"❌ Bot Send Message Error: {e}")
                
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                print("⚠️ Token Expired. ပြန်လည်ဝင်ရောက်နေပါသည်...")
                CURRENT_TOKEN = ""
                
    except Exception as e:
        print(f"❌ Game Data Request Error: {e}")

# ==========================================
# 🔄 5. BACKGROUND TASK
# ==========================================
async def auto_broadcaster():
    await init_db() 
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5)

# ==========================================
# 🤖 6. BOT HANDLERS 
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။ Bigwin AI Predictor Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "စနစ်က နောက်ကွယ်မှာ အလိုအလျောက် အလုပ်လုပ်နေပြီး Channel ထဲကို ခန့်မှန်းချက်များ ပို့ပေးနေပါတယ်။\n\n"
        "လက်ရှိ အကောင့်လက်ကျန်ကို သိလိုပါက /status \n"
        "📊 Win Rate မှတ်တမ်းကို ကြည့်လိုပါက /stats ကို နှိပ်ပါ။"
    )

@dp.message(Command("status"))
async def check_status(message: types.Message):
    loading_msg = await message.reply("🔄 အချက်အလက်များ ဆွဲယူနေပါသည်...")
    async with aiohttp.ClientSession() as session:
        balance = await get_user_balance(session)
        
        status_text = (
            f"📊 <b>System Status</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔹 <b>Account :</b> <code>{USERNAME}</code>\n"
            f"🔹 <b>Balance :</b> <code>{balance}</code> Ks\n"
            f"🔹 <b>Last Issue:</b> <code>{LAST_PROCESSED_ISSUE}</code>\n"
            f"🔹 <b>Bot Status:</b> 🟢 Active"
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
        await loading_msg.edit_text(f"❌ Database မှတ်တမ်း ယူရာတွင် အမှားအယွင်း ဖြစ်ပေါ်ခဲ့ပါသည်။ ({e})")

# ==========================================
# 🚀 7. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Aiogram Bigwin Bot (MongoDB + AI Pattern) စတင်နေပါပြီ...\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
