import asyncio
import time
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

# Auto Bet စနစ်အတွက် Variable များ
AUTO_BET_ENABLED = False
BASE_BET = 10
MULTIPLIERS = [1, 2, 5, 10, 22]  # ၁ဆ, ၂ဆ, ၅ဆ, ၁၀ဆ, ၂၂ဆ
CURRENT_STEP = 0

LAST_BET_ISSUE = None
LAST_BET_TYPE = None 

# Win Rate Track လုပ်ရန် Variable များ
TOTAL_PREDICTIONS = 0
TOTAL_WINS = 0
LAST_PREDICTED_ISSUE = None
LAST_PREDICTED_TYPE = None # 14(Small: 0-5), 15(Big: 6-9)

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS
# ==========================================
async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
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
                print("✅ Login အောင်မြင်ပါသည်။")
                return True
            return False
    except Exception:
        return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return "0.00"
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    json_data = {'signature': '98BA4B555CD283B47C8F9F6C800DF741', 'language': 7, 'timestamp': int(time.time())}
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0: return data.get('data', {}).get('amount', '0.00')
            elif data.get('code') == 401:
                CURRENT_TOKEN = ""
                return await get_user_balance(session)
            return "0.00"
    except Exception: return "0.00"

async def place_bet(session: aiohttp.ClientSession, issue_number: str, select_type: int, bet_amount: int):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN: return False
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    json_data = {
        'typeId': 30, 'issuenumber': issue_number, 'amount': bet_amount,
        'betCount': 1, 'gameType': 2, 'selectType': select_type,
        'language': 7, 'random': '0c0444d8447d4f4994337bbaa035df9f',
        'signature': '27DBBF1E958374943F88D3873DB18F82', 'timestamp': int(time.time()),
    }
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GameBetting', headers=headers, json=json_data) as response:
            data = await response.json()
            return True if data.get('code') == 0 else False
    except Exception: return False

async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE
    global AUTO_BET_ENABLED, CURRENT_STEP, LAST_BET_ISSUE, LAST_BET_TYPE
    global TOTAL_PREDICTIONS, TOTAL_WINS, LAST_PREDICTED_ISSUE, LAST_PREDICTED_TYPE
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    # Markov Chain အတွက် ပွဲ ၃၀ စာ ဆွဲယူမည်
    json_data = {'pageSize': 30, 'pageNo': 1, 'typeId': 30, 'language': 7, 'timestamp': int(time.time())}

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers=headers, json=json_data) as response:
            data = await response.json()
            
            if data.get('code') == 0:
                records = data.get("data", {}).get("list", [])
                if not records or len(records) < 4: return
                
                latest_issue = str(records[0]["issueNumber"])
                if latest_issue == LAST_PROCESSED_ISSUE: return 
                LAST_PROCESSED_ISSUE = latest_issue
                next_issue = str(int(latest_issue) + 1)
                
                # ----------------------------------------------------
                # 📊 ပြီးခဲ့သည့် AI Prediction Win Rate စစ်ဆေးခြင်း
                # ----------------------------------------------------
                if LAST_PREDICTED_ISSUE:
                    record = next((r for r in records if str(r['issueNumber']) == LAST_PREDICTED_ISSUE), None)
                    if record:
                        TOTAL_PREDICTIONS += 1
                        winning_num = int(record['number'])
                        is_small = winning_num <= 5 # 0 မှ 5 အထိ အသေး
                        is_big = winning_num > 5    # 6 မှ 9 အထိ အကြီး
                        
                        if (LAST_PREDICTED_TYPE == 14 and is_small) or (LAST_PREDICTED_TYPE == 15 and is_big):
                            TOTAL_WINS += 1
                        
                        # ပွဲ ၂၀ ပြည့်တိုင်း Channel သို့ Report တင်ခြင်း
                        if TOTAL_PREDICTIONS > 0 and TOTAL_PREDICTIONS % 20 == 0:
                            win_rate = (TOTAL_WINS / TOTAL_PREDICTIONS) * 100
                            report_msg = (
                                f"📈 <b>AI Win Rate Report (Last {TOTAL_PREDICTIONS} Rounds)</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"🎯 စုစုပေါင်း ခန့်မှန်းမှု : {TOTAL_PREDICTIONS} ပွဲ\n"
                                f"🏆 မှန်ကန်မှု (Wins) : {TOTAL_WINS} ပွဲ\n"
                                f"📉 မှားယွင်းမှု (Losses) : {TOTAL_PREDICTIONS - TOTAL_WINS} ပွဲ\n"
                                f"📊 <b>Win Rate : {win_rate:.1f}%</b>\n"
                                f"━━━━━━━━━━━━━━━━━━"
                            )
                            try:
                                await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=report_msg)
                            except Exception as e:
                                print(f"Channel Report Error: {e}")

                # ----------------------------------------------------
                # 🏆 Auto Bet (Martingale) အနိုင်/အရှုံး စစ်ဆေးခြင်း
                # ----------------------------------------------------
                bet_result_msg = "စောင့်ဆိုင်းဆဲ..."
                if LAST_BET_ISSUE and AUTO_BET_ENABLED:
                    record = next((r for r in records if str(r['issueNumber']) == LAST_BET_ISSUE), None)
                    if record:
                        winning_num = int(record['number'])
                        won = (LAST_BET_TYPE == 14 and winning_num <= 5) or (LAST_BET_TYPE == 15 and winning_num > 5)
                        if won:
                            CURRENT_STEP = 0 
                            bet_result_msg = "✅ အရင်ပွဲ နိုင်ပါသည်။ အစမှပြန်ထိုးပါမည်။"
                        else:
                            CURRENT_STEP += 1 
                            if CURRENT_STEP >= len(MULTIPLIERS): CURRENT_STEP = 0 
                            bet_result_msg = "❌ အရင်ပွဲ ရှုံးပါသည်။ အဆတိုး၍ ထိုးပါမည်။"
                    LAST_BET_ISSUE = None 

                # ----------------------------------------------------
                # 🧠 Advanced Algorithm (Markov Chain + Streaks + Ping-Pong)
                # ----------------------------------------------------
                recent_numbers = [int(item["number"]) for item in records]
                recent_types = ["SMALL" if n <= 5 else "BIG" for n in recent_numbers]
                
                latest_type = recent_types[0] # နောက်ဆုံးထွက်ထားသော ရလဒ်
                predicted_raw = ""
                reason = ""

                # Rule 1: Streak Detection (၃ ကြိမ်ဆက်တိုက် ထွက်နေလျှင် လမ်းကြောင်းမချိုးပါ)
                if recent_types[0] == recent_types[1] == recent_types[2]:
                    predicted_raw = recent_types[0]
                    reason = f"Streak Detection ({predicted_raw} လမ်းကြောင်းရှည် ဖြစ်နေ၍)"

                # Rule 2: Ping-Pong Pattern (အကြီး-အသေး-အကြီး-အသေး အလှည့်ကျ)
                elif recent_types[0] != recent_types[1] and recent_types[1] != recent_types[2] and recent_types[2] != recent_types[3]:
                    # B-S-B-S ဖြစ်နေလျှင် ရှေ့ကဟာ (ဆန့်ကျင်ဘက်) ကို ပြန်လိုက်မည်
                    predicted_raw = recent_types[1]
                    reason = "Ping-Pong Pattern (အလှည့်ကျပုံစံ ဖြစ်ပေါ်နေ၍)"

                # Rule 3: Transition Probability (Markov Chain)
                else:
                    next_is_big = 0
                    next_is_small = 0
                    
                    # ပွဲ ၃၀ အတွင်း လက်ရှိရလဒ် (latest_type) ပြီးနောက် ဘာဆက်ထွက်လေ့ရှိသလဲ တွက်ချက်ခြင်း
                    for i in range(1, len(recent_types)):
                        if recent_types[i] == latest_type:
                            if recent_types[i-1] == "BIG":
                                next_is_big += 1
                            else:
                                next_is_small += 1
                                
                    total_transitions = next_is_big + next_is_small
                    
                    if next_is_big > next_is_small:
                        predicted_raw = "BIG"
                        prob_percent = int((next_is_big / total_transitions) * 100) if total_transitions > 0 else 50
                        reason = f"Markov Chain ({latest_type} ပြီးနောက် BIG လာရန် {prob_percent}% ရှိ၍)"
                    elif next_is_small > next_is_big:
                        predicted_raw = "SMALL"
                        prob_percent = int((next_is_small / total_transitions) * 100) if total_transitions > 0 else 50
                        reason = f"Markov Chain ({latest_type} ပြီးနောက် SMALL လာရန် {prob_percent}% ရှိ၍)"
                    else:
                        # တူညီနေပါက Balance အရ ပြန်ရွေးချယ်ခြင်း
                        predicted_raw = "BIG" if recent_types.count("SMALL") > recent_types.count("BIG") else "SMALL"
                        reason = "Statistical Balance (အချိုးအဆ ချိန်ညှိမှုအရ)"

                # Final Prediction Mapping
                select_type_for_bet = 15 if predicted_raw == "BIG" else 14
                predicted = "BIG (အကြီး) 🔴" if predicted_raw == "BIG" else "SMALL (အသေး) 🟢"

                LAST_PREDICTED_ISSUE = next_issue
                LAST_PREDICTED_TYPE = select_type_for_bet

                # ----------------------------------------------------
                # 🚀 Auto Bet ထိုးခြင်း
                # ----------------------------------------------------
                bet_status_msg = "ပိတ်ထားပါသည် 🔴"
                current_bet_amount = 0
                
                if AUTO_BET_ENABLED:
                    current_bet_amount = BASE_BET * MULTIPLIERS[CURRENT_STEP]
                    bet_success = await place_bet(session, next_issue, select_type_for_bet, current_bet_amount)
                    if bet_success:
                        LAST_BET_ISSUE = next_issue
                        LAST_BET_TYPE = select_type_for_bet
                        bet_status_msg = f"အောင်မြင်ပါသည် ({current_bet_amount} Ks) 🟢"
                    else:
                        bet_status_msg = "ကျရှုံးပါသည် ⚠️"

                current_balance = await get_user_balance(session)
                win_rate_display = f"{(TOTAL_WINS/TOTAL_PREDICTIONS*100):.1f}%" if TOTAL_PREDICTIONS > 0 else "0.0%"

                # Channel သို့ ပို့မည့် Message
                tg_message = (
                    f"🎰 <b>Bigwin 30-Seconds</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>နောက်ပွဲစဉ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{predicted}</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 <b>ရှေ့ပွဲရလဒ် :</b> {bet_result_msg}\n"
                    f"💸 <b>Auto Bet :</b> {bet_status_msg}\n"
                    f"📈 <b>Current Win Rate :</b> {win_rate_display}\n"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>"
                )
                
                try:
                    # သတ်မှတ်ထားသော Channel ID သို့သာ ပို့မည်
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                    print(f"✅ AI Predict: {predicted_raw} -> Channel သို့ ပို့ပြီးပါပြီ။")
                except Exception as e:
                    print(f"❌ Channel Send Error: {e}")
                
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                CURRENT_TOKEN = ""
    except Exception as e:
        pass # API Errors များကို ကျော်သွားမည်

# ==========================================
# 🔄 4. BACKGROUND TASK (အမြဲ Run နေမည့် Loop)
# ==========================================
async def auto_broadcaster():
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5) 

# ==========================================
# 🤖 5. BOT PRIVATE HANDLERS (Admin သုံးရန်)
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။ Bigwin AI & Auto Bet Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "🔹 /status - အကောင့်လက်ကျန်နှင့် အခြေအနေကြည့်ရန်\n"
        "🔹 /winrate - AI ၏ အနိုင်ရနှုန်းစစ်ရန်\n"
        "🔹 /autobet on - Auto Bet ဖွင့်ရန်\n"
        "🔹 /autobet off - Auto Bet ပိတ်ရန်"
    )

@dp.message(Command("autobet"))
async def toggle_autobet(message: types.Message):
    global AUTO_BET_ENABLED
    args = message.text.split()
    if len(args) > 1 and args[1].lower() == "on":
        AUTO_BET_ENABLED = True
        await message.reply("✅ <b>Auto Bet စနစ် ဖွင့်လိုက်ပါပြီ။</b> နောက်ပွဲမှစ၍ အလိုအလျောက် ထိုးပါမည်။")
    elif len(args) > 1 and args[1].lower() == "off":
        AUTO_BET_ENABLED = False
        await message.reply("❌ <b>Auto Bet စနစ် ပိတ်လိုက်ပါပြီ။</b>")
    else:
        status = "ဖွင့် 🟢" if AUTO_BET_ENABLED else "ပိတ် 🔴"
        await message.reply(f"လက်ရှိ Auto Bet: <b>{status}</b>\nသုံးရန်: <code>/autobet on</code> သို့ <code>/autobet off</code>")

@dp.message(Command("winrate"))
async def check_winrate(message: types.Message):
    if TOTAL_PREDICTIONS == 0:
        await message.reply("⚠️ ယခုမှ စတင်ထားသဖြင့် မှတ်တမ်း မရှိသေးပါ။ ခဏစောင့်ပေးပါ။")
        return
    win_rate = (TOTAL_WINS / TOTAL_PREDICTIONS) * 100
    await message.reply(
        f"📈 <b>AI Win Rate Data</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 စုစုပေါင်း ခန့်မှန်းမှု : {TOTAL_PREDICTIONS} ပွဲ\n"
        f"🏆 မှန်ကန်မှု (Wins) : {TOTAL_WINS} ပွဲ\n"
        f"📊 <b>Win Rate : {win_rate:.1f}%</b>"
    )

@dp.message(Command("status"))
async def check_status(message: types.Message):
    loading_msg = await message.reply("🔄 Data ဆွဲယူနေပါသည်...")
    async with aiohttp.ClientSession() as session:
        balance = await get_user_balance(session)
        autobet_status = "Active 🟢" if AUTO_BET_ENABLED else "Inactive 🔴"
        next_bet_amount = BASE_BET * MULTIPLIERS[CURRENT_STEP]
        win_rate = f"{(TOTAL_WINS/TOTAL_PREDICTIONS*100):.1f}%" if TOTAL_PREDICTIONS > 0 else "0.0%"
        
        status_text = (
            f"📊 <b>System Status</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔹 <b>Account :</b> <code>{USERNAME}</code>\n"
            f"🔹 <b>Balance :</b> <code>{balance}</code> Ks\n"
            f"🔹 <b>Auto Bet :</b> {autobet_status}\n"
            f"🔹 <b>Next Bet :</b> <code>{next_bet_amount}</code> Ks ({MULTIPLIERS[CURRENT_STEP]} ဆ)\n"
            f"🔹 <b>AI Win Rate:</b> {win_rate}"
        )
        await loading_msg.edit_text(status_text)

# ==========================================
# 🚀 6. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Aiogram Bigwin Bot စတင်နေပါပြီ...\n")
    # Background Task ကို အလုပ်လုပ်စေခြင်း
    asyncio.create_task(auto_broadcaster())
    # User Command များကို နားထောင်ခြင်း
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("\nBot ကို ရပ်တန့်လိုက်ပါသည်။")
