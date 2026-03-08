import asyncio
import time
import os
import aiohttp
import aiosqlite
from dotenv import load_dotenv

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

if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🔧 2. SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""
LAST_PREDICTED_ISSUE = ""
LAST_PREDICTED_RESULT = ""
DB_NAME = "bigwin_history.db"

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# 🗄 3. DATABASE SETUP
# ==========================================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                issue_number TEXT PRIMARY KEY,
                number INTEGER,
                size TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                issue_number TEXT PRIMARY KEY,
                predicted_size TEXT,
                probability REAL,
                actual_size TEXT,
                win_lose TEXT
            )
        ''')
        await db.commit()

# ==========================================
# 🔑 4. ASYNC API FUNCTIONS
# ==========================================
async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME, 
        'pwd': PASSWORD,
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': 'd85ed31c80a9447d9c2eb8e713b6046d',
        'signature': 'EAEF4EF352C07BF7852E39B5AB2F4151',
        'timestamp': int(time.time()),
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/Login', headers=BASE_HEADERS, json=json_data, timeout=10) as response:
            data = await response.json()
            if data.get('code') == 0:
                token_data = data.get('data', {})
                token_str = token_data if isinstance(token_data, str) else token_data.get('token', '')
                CURRENT_TOKEN = f"Bearer {token_str}"
                print("✅ Login အောင်မြင်ပါသည်။\n")
                return True
            return False
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return False

# ==========================================
# 🧠 5. AI PREDICTION & WIN RATE LOGIC
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 50,
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'timestamp': int(time.time()),
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers=headers, json=json_data, timeout=10) as response:
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
                
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute('INSERT OR IGNORE INTO game_history (issue_number, number, size) VALUES (?, ?, ?)', (latest_issue, latest_number, latest_size))
                    
                    # ၁။ ပြီးခဲ့သော ပွဲစဉ်အတွက် Win/Lose စစ်ဆေးခြင်း
                    if LAST_PREDICTED_ISSUE == latest_issue:
                        is_win = (LAST_PREDICTED_RESULT == latest_size)
                        win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                        await db.execute('UPDATE predictions SET actual_size = ?, win_lose = ? WHERE issue_number = ?', (latest_size, win_lose_status, latest_issue))
                        
                        win_lose_text = (
                            f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue}) ရလဒ်:</b> {latest_size}\n"
                            f"📊 <b>ခန့်မှန်းချက် ရလဒ်:</b> <b>{win_lose_status}</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                        )
                    await db.commit()

                    # ၂။ Win Rate Report ပို့ရန် ၅၀ ပြည့်/မပြည့် စစ်ဆေးခြင်း
                    async with db.execute('SELECT COUNT(*) FROM predictions WHERE win_lose IS NOT NULL') as cursor:
                        total_evaluated = (await cursor.fetchone())[0]

                    # အဖြေထွက်ပြီးသော ပွဲစဉ်အရေအတွက်သည် ၅၀ ဆတိုးဖြစ်လျှင် Report ပို့မည်
                    if total_evaluated > 0 and total_evaluated % 50 == 0 and LAST_PREDICTED_ISSUE == latest_issue:
                        async with db.execute('SELECT win_lose FROM predictions WHERE win_lose IS NOT NULL ORDER BY issue_number DESC LIMIT 50') as cursor:
                            last_50_results = await cursor.fetchall()
                        
                        wins = sum(1 for row in last_50_results if "WIN" in row[0])
                        losses = 50 - wins
                        win_rate = (wins / 50) * 100

                        stats_msg = (
                            f"📈 <b>ပွဲစဉ် ၅၀ ပြည့် Win Rate မှတ်တမ်း</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"✅ <b>နိုင်ပွဲ (Wins) :</b> {wins} ပွဲ\n"
                            f"❌ <b>ရှုံးပွဲ (Losses) :</b> {losses} ပွဲ\n"
                            f"📊 <b>Win Rate :</b> <b>{win_rate:.1f}%</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🤖 <i>AI စနစ်၏ နောက်ဆုံး ပွဲ ၅၀ အပေါ် စွမ်းဆောင်ရည် ဖြစ်ပါသည်။</i>"
                        )
                        try:
                            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=stats_msg)
                            print(f"📈 50 Games Stats Sent: {wins}W - {losses}L ({win_rate}%)")
                        except Exception as e:
                            print(f"❌ Telegram Stats Send Error: {e}")

                    # ၃။ AI တွက်ချက်ခြင်းအတွက် ပွဲ ၅၀ ပြန်ဆွဲထုတ်ခြင်း
                    async with db.execute('SELECT size FROM game_history ORDER BY issue_number DESC LIMIT 50') as cursor:
                        history = await cursor.fetchall()
                
                sizes = [row[0] for row in history]
                if not sizes: return

                big_count = sizes.count("BIG")
                small_count = sizes.count("SMALL")
                total_games = len(sizes)
                
                big_prob = (big_count / total_games) * 100
                small_prob = (small_count / total_games) * 100
                
                recent_3 = sizes[:3]
                
                if recent_3 == ["BIG", "BIG", "BIG"]:
                    predicted, base_prob, reason = "BIG 🔴", max(big_prob, 65.0), "Trend အရ အကြီး ၃ ပွဲဆက်တိုက်ထွက်နေ၍"
                elif recent_3 == ["SMALL", "SMALL", "SMALL"]:
                    predicted, base_prob, reason = "SMALL 🟢", max(small_prob, 65.0), "Trend အရ အသေး ၃ ပွဲဆက်တိုက်ထွက်နေ၍"
                else:
                    if big_count < small_count:
                        predicted, base_prob, reason = "BIG 🔴", 100 - small_prob, "အသေးထွက်နှုန်းများနေသဖြင့် အကြီးပြန်ကျနိုင်၍"
                    else:
                        predicted, base_prob, reason = "SMALL 🟢", 100 - big_prob, "အကြီးထွက်နှုန်းများနေသဖြင့် အသေးပြန်ကျနိုင်၍"

                final_prob = min(round(base_prob, 1), 85.0)

                LAST_PREDICTED_ISSUE = next_issue
                LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
                
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute('INSERT INTO predictions (issue_number, predicted_size, probability) VALUES (?, ?, ?)', (next_issue, LAST_PREDICTED_RESULT, final_prob))
                    await db.commit()

                tg_message = (
                    f"🎰 <b>Bigwin 30-Seconds (AI)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{win_lose_text}"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>ခန့်မှန်းချက် :</b> <b>{predicted}</b>\n"
                    f"📈 <b>ဖြစ်နိုင်ခြေ :</b> <b>{final_prob}%</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> <i>{reason}</i>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
                
                try:
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                except Exception as e:
                    pass

            elif data.get('code') == 401:
                CURRENT_TOKEN = ""
                
    except Exception as e:
        print(f"❌ Error: {e}")

# ==========================================
# 🔄 6. BACKGROUND TASK
# ==========================================
async def auto_broadcaster():
    await init_db()
    async with aiohttp.ClientSession() as session:
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5)

# ==========================================
# 🚀 7. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 AI Predictor Bot စတင်နေပါပြီ...\n")
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot ရပ်တန့်သွားပါပြီ။")
