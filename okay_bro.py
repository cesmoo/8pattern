import asyncio
import time
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==========================================
# ⚙️ 1. CONFIGURATION (ဤနေရာတွင် တိုက်ရိုက်ပြင်ပါ)
# ==========================================
USERNAME = "959680090540" # သင့်အကောင့်
PASSWORD = "Mitheint11"     # သင့် Password

# သင့် Bot Token နှင့် Channel ID ကို အောက်တွင် အတိအကျ ထည့်ပါ (⚠️ မဖြစ်မနေ ထည့်ရန်)
TELEGRAM_BOT_TOKEN = "8682629146:AAGQwoKW0DM6LPeY4rQMjv_X41hkNfuQ6D0" 
TELEGRAM_CHANNEL_ID = "-1003803022333" # ဥပမာ -1001234567890

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🔧 2. SYSTEM & AUTO-BET VARIABLES
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

# 🤖 Auto-Bet Settings
AUTO_BET_ENABLED = False
MULTIPLIERS = [1, 2, 5, 10, 22] 
BASE_BET = 10                   
CURRENT_STEP = 0

LAST_BET_ISSUE = ""
LAST_BET_CHOICE = "" 
LAST_BET_AMOUNT = 0

# 📈 AI Win Rate Tracking
LAST_AI_ISSUE = ""
LAST_AI_CHOICE = ""
WIN_HISTORY = [] 

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
    'random': '026e324cf3d14440b8c261ad356610a6',
    'signature': '842781239D9D89DCEF83A2E5480C7890',
    'timestamp': 1772963120,
}

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/Login', headers=BASE_HEADERS, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                token_str = data.get('data', {}).get('token', '') if isinstance(data.get('data'), dict) else data.get('data')
                CURRENT_TOKEN = f"Bearer {token_str}"
                print("✅ Login အောင်မြင်ပါသည်။\n")
                return True
            else:
                print(f"❌ Login Failed: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"❌ Login Error: {e}")
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
        'timestamp': 1772963120,
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('amount', '0.00')
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                CURRENT_TOKEN = ""
                return await get_user_balance(session)
    except Exception: pass
    return "0.00"

async def place_bet(session: aiohttp.ClientSession, issue: str, choice: str, total_amount: int):
    global CURRENT_TOKEN
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    
    select_id = 14 if choice == "BIG" else 15 
    bet_count = total_amount // 10
    
    json_data = {
        'typeId': 30,
        'issuenumber': issue,
        'amount': 10,               
        'betCount': bet_count,      
        'gameType': 2,
        'selectType': select_id,
        'language': 7,
        'random': 'efbf9e069bbf49119c4a4bf43ce15be6', 
        'signature': 'DFF30F1B1BAAE6512A07B1E0F5CF6A86',
        'timestamp': 1772966960, 
    }
    
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GameBetting', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                print(f"💸 [BET SUCCESS] ပွဲစဉ် {issue} တွင် {choice} ကို {total_amount} Ks လောင်းလိုက်ပါပြီ။")
                return True
            else:
                print(f"❌ [BET FAILED] ပွဲစဉ် {issue} လောင်းရန်မအောင်မြင်ပါ: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"❌ [BET ERROR] {e}")
        return False

async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, CURRENT_STEP, LAST_BET_ISSUE, LAST_BET_CHOICE, LAST_BET_AMOUNT
    global LAST_AI_ISSUE, LAST_AI_CHOICE, WIN_HISTORY
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 30, 
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': '85b82082418845c593a2641ae50af6de',
        'signature': 'E7C0AAF6D1B429E89F83CA6FDBF3D4FC',
        'timestamp': 1772962173, 
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers=headers, json=json_data) as response:
            data = await response.json()
            
            if data.get('code') == 0:
                records = data.get("data", {}).get("list", [])
                if not records: return
                
                latest_issue = str(records[0]["issueNumber"])
                
                if latest_issue == LAST_PROCESSED_ISSUE:
                    return 
                    
                LAST_PROCESSED_ISSUE = latest_issue
                latest_num = int(records[0]["number"])
                next_issue = str(int(latest_issue) + 1)
                actual_result = "BIG" if latest_num >= 5 else "SMALL"
                
                # ---------------------------------------------
                # 📈 1. AI Win Rate Tracking
                # ---------------------------------------------
                if LAST_AI_ISSUE == latest_issue:
                    WIN_HISTORY.append(1 if actual_result == LAST_AI_CHOICE else 0)
                    if len(WIN_HISTORY) > 20: WIN_HISTORY.pop(0)

                win_rate_msg = ""
                if len(WIN_HISTORY) > 0:
                    t_played = len(WIN_HISTORY)
                    t_won = sum(WIN_HISTORY)
                    t_lost = t_played - t_won
                    win_pct = (t_won / t_played) * 100
                    win_rate_msg = f"📈 <b>Win Rate (Last {t_played}):</b> <code>{win_pct:.0f}%</code> ({t_won}W - {t_lost}L)\n"
                else:
                    win_rate_msg = f"📈 <b>Win Rate:</b> <code>တွက်ချက်နေဆဲ...</code>\n"

                # ---------------------------------------------
                # 🏆 2. Check Auto-Bet Result
                # ---------------------------------------------
                bet_result_msg = ""
                if AUTO_BET_ENABLED and LAST_BET_ISSUE == latest_issue:
                    if actual_result == LAST_BET_CHOICE:
                        CURRENT_STEP = 0
                        bet_result_msg = f"🎉 <b>လောင်းကြေးရလဒ်:</b> အရင်ပွဲ နိုင်ပါသည်! အစ (10Ks) မှ ပြန်စပါမည်။\n"
                    else:
                        CURRENT_STEP += 1
                        if CURRENT_STEP >= len(MULTIPLIERS):
                            CURRENT_STEP = 0 
                            bet_result_msg = f"💔 <b>လောင်းကြေးရလဒ်:</b> အမြင့်ဆုံးအဆင့်အထိ ရှုံးသွားသဖြင့် အစမှ ပြန်စပါမည်။\n"
                        else:
                            bet_result_msg = f"📉 <b>လောင်းကြေးရလဒ်:</b> ရှုံးပါသည်။ နောက်တစ်ဆင့် ({MULTIPLIERS[CURRENT_STEP]}ဆ) သို့ တက်ပါမည်။\n"

                # ---------------------------------------------
                # 🧠 3. Advanced AI Predict
                # ---------------------------------------------
                history = ["B" if int(item["number"]) >= 5 else "S" for item in records]
                latest_result = history[0]

                current_streak = 1
                for i in range(1, len(history)):
                    if history[i] == latest_result: current_streak += 1
                    else: break

                is_ping_pong = len(history) >= 4 and history[0] != history[1] and history[1] != history[2] and history[2] != history[3]

                ai_raw_choice = ""
                reason = ""

                if current_streak >= 3:
                    ai_raw_choice = "BIG" if latest_result == "B" else "SMALL"
                    reason = f"လမ်းကြောင်းအားကောင်းနေသဖြင့် ({current_streak} ကြိမ်ဆက်) လိုက်မည်"
                elif is_ping_pong:
                    ai_raw_choice = "BIG" if latest_result == "S" else "SMALL"
                    reason = "ဘယ်ညာ (Ping-Pong) ပုံစံထွက်နေသဖြင့် ပြောင်းလောင်းမည်"
                else:
                    f_same = sum(1 for i in range(len(history)-1) if history[i+1] == latest_result and history[i] == latest_result)
                    f_diff = sum(1 for i in range(len(history)-1) if history[i+1] == latest_result and history[i] != latest_result)

                    if f_same > f_diff:
                        ai_raw_choice = "BIG" if latest_result == "B" else "SMALL"
                        reason = "သမိုင်းကြောင်းအရ ထပ်တူထွက်လေ့ရှိသဖြင့် လိုက်မည်"
                    elif f_diff > f_same:
                        ai_raw_choice = "BIG" if latest_result == "S" else "SMALL"
                        reason = "သမိုင်းကြောင်းအရ ပြောင်းထွက်လေ့ရှိသဖြင့် ဆန့်ကျင်ဘက်လောင်းမည်"
                    else:
                        b_c, s_c = history.count("B"), history.count("S")
                        ai_raw_choice = "BIG" if s_c > b_c else "SMALL"
                        reason = "Probability အရ ကျန်နေသောဘက်သို့ လောင်းမည်"

                display_predict = "BIG (အကြီး) 🔴" if ai_raw_choice == "BIG" else "SMALL (အသေး) 🟢"
                LAST_AI_ISSUE = next_issue
                LAST_AI_CHOICE = ai_raw_choice

                # ---------------------------------------------
                # 💸 4. Execute Auto-Bet
                # ---------------------------------------------
                bet_info_msg = ""
                if AUTO_BET_ENABLED:
                    amount = BASE_BET * MULTIPLIERS[CURRENT_STEP]
                    await place_bet(session, next_issue, ai_raw_choice, amount) 
                    
                    LAST_BET_ISSUE = next_issue
                    LAST_BET_CHOICE = ai_raw_choice
                    LAST_BET_AMOUNT = amount
                    bet_info_msg = f"⚙️ <b>Auto-Bet :</b> <code>{amount} Ks</code> လောင်းထားပါသည်။\n"
                
                current_balance = await get_user_balance(session)
                
                # ---------------------------------------------
                # 💬 5. Telegram Broadcast
                # ---------------------------------------------
                print(f"✅ [NEW] ပွဲစဉ်: {latest_issue} -> 🤖 Predict: {display_predict}")

                tg_message = (
                    f"🎰 <b>Bigwin 30s | Pro-AI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{display_predict}</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{win_rate_msg}"
                    f"{bet_result_msg}"
                    f"{bet_info_msg}"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>\n"
                )
                
                try: await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                except Exception as e: print(f"❌ Bot Error: {e}")
                
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                print("⚠️ Token Expired.")
                CURRENT_TOKEN = ""
                
    except Exception as e:
        print(f"❌ Game Request Error: {e}")

# ==========================================
# 🔄 4. BACKGROUND TASK
# ==========================================
async def auto_broadcaster():
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5)

# ==========================================
# 🤖 5. BOT HANDLERS
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။ Bigwin Pro-AI Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "/status - အခြေအနေကြည့်ရန်\n"
        "/autoon - အလိုအလျောက်လောင်းမည်\n"
        "/autooff - အလိုအလျောက်လောင်းခြင်း ပိတ်မည်"
    )

@dp.message(Command("autoon"))
async def turn_auto_on(message: types.Message):
    global AUTO_BET_ENABLED, CURRENT_STEP
    AUTO_BET_ENABLED = True
    CURRENT_STEP = 0 
    await message.reply("✅ <b>Auto-Bet ဖွင့်လိုက်ပါပြီ!</b>\nနောက်ပွဲစဉ်မှစ၍ အလိုအလျောက် လောင်းကြေးထပ်ပါမည်။")

@dp.message(Command("autooff"))
async def turn_auto_off(message: types.Message):
    global AUTO_BET_ENABLED
    AUTO_BET_ENABLED = False
    await message.reply("❌ <b>Auto-Bet ပိတ်လိုက်ပါပြီ!</b>")

@dp.message(Command("status"))
async def check_status(message: types.Message):
    async with aiohttp.ClientSession() as session:
        balance = await get_user_balance(session)
        auto_status = "🟢 ဖွင့်ထားသည်" if AUTO_BET_ENABLED else "🔴 ပိတ်ထားသည်"
        current_mult = MULTIPLIERS[CURRENT_STEP] if AUTO_BET_ENABLED else 0
        
        status_text = (
            f"📊 <b>System Status</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔹 <b>Account :</b> <code>{USERNAME}</code>\n"
            f"🔹 <b>Balance :</b> <code>{balance}</code> Ks\n"
            f"🔹 <b>Auto-Bet :</b> {auto_status}\n"
            f"🔹 <b>Current Step:</b> {current_mult} ဆ\n"
        )
        await message.reply(status_text)

# ==========================================
# 🚀 6. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Aiogram Bigwin Pro-AI Bot စတင်နေပါပြီ...\n")
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ရပ်တန့်လိုက်ပါသည်။")
