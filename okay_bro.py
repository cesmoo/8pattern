import asyncio
import time
import datetime
import os
from dotenv import load_dotenv
import aiohttp

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

# Data များ မှန်ကန်စွာ ပါဝင်ခြင်း ရှိမရှိ စစ်ဆေးခြင်း
if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🔧 2. SYSTEM VARIABLES (စနစ်ပိုင်းဆိုင်ရာ)
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS (API ခေါ်ယူခြင်း)
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
                return await get_user_balance(session) # Retry
            return "0.00"
    except Exception:
        return "0.00"

async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE
    
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
                
                latest_issue = str(records[0]["issueNumber"])
                
                if latest_issue == LAST_PROCESSED_ISSUE:
                    return # ပွဲစဉ်အသစ် မဟုတ်သေးပါ
                    
                LAST_PROCESSED_ISSUE = latest_issue
                next_issue = str(int(latest_issue) + 1)
                
                # AI Logic
                recent_numbers = [int(item["number"]) for item in records]
                big_count = sum(1 for n in recent_numbers if n >= 5)
                small_count = sum(1 for n in recent_numbers if n < 5)
                
                last_3_big = all(n >= 5 for n in recent_numbers[:3])
                last_3_small = all(n < 5 for n in recent_numbers[:3])
                
                if last_3_big:
                    predicted, reason = "BIG (အကြီး) 🔴", "Trend အရ အကြီး ဆက်တိုက်ထွက်နေ၍"
                elif last_3_small:
                    predicted, reason = "SMALL (အသေး) 🟢", "Trend အရ အသေး ဆက်တိုက်ထွက်နေ၍"
                else:
                    predicted = "BIG (အကြီး) 🔴" if small_count > big_count else "SMALL (အသေး) 🟢"
                    reason = "Probability အရ ထွက်ရန် အခွင့်အရေးများ၍"

                current_balance = await get_user_balance(session)
                
                print(f"✅ [NEW] ပွဲစဉ်: {latest_issue} -> 🤖 AI Predict: {predicted}")

                tg_message = (
                    f"🎰 <b>Bigwin 30-Seconds</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{predicted}</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>\n"
                    f"⚠️ <i>(ခန့်မှန်းချက်သာဖြစ်သဖြင့် ချင့်ချိန်၍ ကစားပါ။)</i>"
                )
                
                # Telegram သို့ ပို့ခြင်း
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
# 🔄 4. BACKGROUND TASK (Channel သို့ Auto ပို့ပေးမည့် Loop)
# ==========================================
async def auto_broadcaster():
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5) # ၅ စက္ကန့်တစ်ခါ အမြဲစစ်ဆေးမည်

# ==========================================
# 🤖 5. BOT HANDLERS (Bot ကို အသုံးပြုသူမှ ခိုင်းစေရန်)
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။ Bigwin AI Predictor Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "စနစ်က နောက်ကွယ်မှာ အလိုအလျောက် အလုပ်လုပ်နေပြီး Channel ထဲကို ခန့်မှန်းချက်များ ပို့ပေးနေပါတယ်။\n\n"
        "လက်ရှိ အကောင့်လက်ကျန်ကို သိလိုပါက /status ကို နှိပ်ပါ။"
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

# ==========================================
# 🚀 6. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Aiogram Bigwin Bot စတင်နေပါပြီ...\n")
    
    # Background Task ကို Event Loop ထဲသို့ ထည့်ခြင်း
    asyncio.create_task(auto_broadcaster())
    
    # Bot ကို Run ခြင်း
    await dp.start_polling(bot)

if __name__ == '__main__':
    # aiohttp သုံးရန်အတွက် Run ပုံစံ
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
