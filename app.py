import asyncio
import os
import aiohttp # API ခေါ်ရန် လိုအပ်ပါသည်
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from playwright.async_api import async_playwright

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
GAME_URL = "https://www.777bigwingame.app/"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher() 

# --- 🔄 System Variables ---
MULTIPLIERS = [1, 2, 4, 8, 16, 32, 64] 
CUSTOM_PATTERN = ["BIG"] 
current_step = 0
current_pattern_index = 0
is_bot_running = False

class AutoBetState(StatesGroup):
    waiting_for_credentials = State()

# ==========================================
# ⚡ 2. API LOGIN & TOKEN INJECTION LOGIC
# ==========================================
async def login_via_api_and_inject(page, username, password):
    print("🔄 API မှတစ်ဆင့် Token လှမ်းယူနေပါသည်...")
    
    api_url = 'https://api.bigwinqaz.com/api/webapi/Login'
    headers = {
        'authority': 'api.bigwinqaz.com',
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://www.777bigwingame.app',
        'referer': 'https://www.777bigwingame.app/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    }
    
    # API ၏ လိုအပ်ချက်အရ ပုံသေ Data အချို့ ထည့်သွင်းထားသည်
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
         'random': 'bdc3a948fef649dbaecf29e745b25bdc',
         'signature': '124FF22337DA9BE52300EE6C313B71B0',
         'timestamp': 1783239813,
    }

    try:
        # ၁။ API မှတစ်ဆင့် Login ဝင်ခြင်း
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=json_data, timeout=10.0) as response:
                data = await response.json()
                
        if data and data.get('code') == 0:
            # Token ကို ထုတ်ယူခြင်း
            token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
            print("✅ API Token ရရှိပါပြီ။ Browser သို့ ထည့်သွင်းနေပါသည်...")
            
            # ၂။ ရရှိလာသော Token ကို Browser ၏ Local Storage ထဲသို့ ထည့်သွင်းခြင်း
            await page.goto(GAME_URL, wait_until="networkidle")
            
            await page.evaluate(f"""
                localStorage.setItem('token', '{token_str}');
                let vuexData = JSON.parse(localStorage.getItem('vuex') || '{{}}');
                vuexData.token = '{token_str}';
                localStorage.setItem('vuex', JSON.stringify(vuexData));
            """)
            
            # ၃။ Token ဝင်သွားစေရန် စာမျက်နှာကို Refresh လုပ်ခြင်း
            await page.reload(wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            print("✅ API + Token Injection ဖြင့် Login ဝင်ခြင်း အောင်မြင်ပါပြီ။")
            return True
        else:
            print(f"❌ API Login Failed: {data.get('msg', 'Unknown Error')}")
            return False

    except Exception as e:
        print(f"❌ API ခေါ်ယူရာတွင် အမှားအယွင်းရှိပါသည်: {e}")
        return False

# ==========================================
# 🤖 3. PLAYWRIGHT AUTO BET LOGIC
# ==========================================
async def place_bet(page, bet_type="BIG", step=0):
    try:
        multiplier = MULTIPLIERS[step]
        print(f"🔄 လောင်းကြေးအဆင့်: {step + 1} | Pattern: {bet_type} | Multiplier: {multiplier}x")

        # 1️⃣ အကြီး/အသေး ရွေးရန်
        if bet_type == "BIG":
            await page.click("div.Betting__C-foot-b") 
        else:
            await page.click("div.Betting__C-foot-s") 
        
        await page.wait_for_timeout(1000)

        # 2️⃣ Base Amount '10' ကို ရွေးရန်
        await page.click("div.Betting__Popup-body-line-item:text-is('10')")

        # 3️⃣ Multiplier ထည့်သွင်းရန်
        input_field = page.locator("input#van-field-1-input")
        await input_field.fill(str(multiplier))
        await page.wait_for_timeout(500)

        # 4️⃣ အတည်ပြုရန်
        await page.click("div.Betting__Popup-foot-s")
        print("✅ လောင်းကြေးတင်ခြင်း အောင်မြင်ပါသည်။")
        
        return True
    except Exception as e:
        print(f"❌ လောင်းကြေးတင်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
        return False

async def check_win_status(page):
    try:
        win_popup = page.locator("div.WinningTip__C-body-l1:has-text('ဂုဏ်ယူပါတယ်')")
        if await win_popup.is_visible(timeout=5000):
            await page.mouse.click(10, 10) 
            return True
        return False
    except:
        return False

# ==========================================
# 🛠️ 4. CUSTOM SETTINGS HANDLERS (.set & .setp)
# ==========================================
@dp.message(F.text.startswith(".setp"))
async def set_pattern(message: types.Message):
    global CUSTOM_PATTERN, current_pattern_index
    
    if message.from_user.id != OWNER_ID: return

    try:
        raw_pattern = message.text.replace(".setp", "").replace(" ", "").upper()
        if not raw_pattern:
            return await message.reply("⚠️ ပုံစံမှားယွင်းနေပါသည်။\nဥပမာ - <code>.setp B,S,B,B,B,B,S,S</code>")

        parts = raw_pattern.split(",")
        new_pattern = []
        for p in parts:
            if p == 'B': new_pattern.append("BIG")
            elif p == 'S': new_pattern.append("SMALL")
            else:
                return await message.reply(f"❌ Error: 'B' သို့မဟုတ် 'S' ကိုသာ အသုံးပြုပါ။ (တွေ့ရှိသောစာသား: {p})")
        
        CUSTOM_PATTERN = new_pattern
        current_pattern_index = 0
        
        pattern_str = " ➡️ ".join(["အကြီး" if x=="BIG" else "အသေး" for x in CUSTOM_PATTERN])
        await message.reply(f"✅ <b>Pattern ပြင်ဆင်ပြီးပါပြီ။</b>\n🔄 အစီအစဉ်: [ {pattern_str} ]")
    except Exception as e:
        await message.reply("❌ Pattern သတ်မှတ်ရာတွင် အမှားရှိနေပါသည်။")

@dp.message(F.text.startswith(".set "))
async def set_multipliers(message: types.Message):
    global MULTIPLIERS, current_step
    
    if message.from_user.id != OWNER_ID: return

    try:
        parts = message.text.replace(".set", "").strip().split()
        if not parts:
            return await message.reply("⚠️ ပုံစံမှားယွင်းနေပါသည်။\nဥပမာ - <code>.set 1 2 4 8 16 32 64</code>")
        
        new_multipliers = [int(x) for x in parts]
        MULTIPLIERS = new_multipliers
        current_step = 0
        
        steps_str = "ဆ, ".join(map(str, MULTIPLIERS)) + "ဆ"
        await message.reply(
            f"✅ <b>လောင်းကြေးအဆင့်များ ပြင်ဆင်ပြီးပါပြီ။</b>\n"
            f"🔢 စုစုပေါင်း ({len(MULTIPLIERS)}) ဆင့်: <b>{steps_str}</b>\n\n"
            f"💡 <i>(Base 10 ကို ရွေးချယ်ထားသောကြောင့် ၁၀ဆ ဟုသတ်မှတ်ပါက စုစုပေါင်း ၁၀၀ ကျပ် ဖိုး လောင်းမည်ဖြစ်သည်။)</i>"
        )
    except ValueError:
        await message.reply("❌ Error: ကိန်းဂဏန်းများသာ ကွက်လပ်ခြား၍ ရိုက်ထည့်ပါ။")

# ==========================================
# 🎮 5. TELEGRAM BOT CORE HANDLERS
# ==========================================
@dp.message(Command("autobet"))
async def ask_credentials(message: types.Message, state: FSMContext):
    global is_bot_running
    
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 <b>Access Denied!</b>")
    
    if is_bot_running:
        return await message.reply("⚠️ Auto Bet အလုပ်လုပ်နေဆဲ ဖြစ်ပါသည်။ ရပ်ချင်ပါက /stopbet ကို နှိပ်ပါ။")
    
    await message.reply(
        "🔑 ကျေးဇူးပြု၍ Login ဝင်မည့် <b>ဖုန်းနံပါတ်</b> နှင့် <b>Password</b> ကို ကွက်လပ်ခြား၍ ရိုက်ထည့်ပါ။\n\n"
        "ဥပမာ - <code>09680090540 Mitheint11</code>"
    )
    await state.set_state(AutoBetState.waiting_for_credentials)

@dp.message(AutoBetState.waiting_for_credentials)
async def start_autobet_with_creds(message: types.Message, state: FSMContext):
    global is_bot_running, current_step, current_pattern_index

    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.reply("❌ ပုံစံမှားယွင်းနေပါသည်။ ဖုန်းနံပါတ် နှင့် Password ကိုသာ ကွက်လပ်ခြား၍ ရိုက်ထည့်ပါ။\nဥပမာ - <code>09680090540 Mitheint11</code>")

    USERNAME = parts[0]
    PASSWORD = parts[1]
    
    await state.clear() 

    is_bot_running = True
    current_step = 0
    current_pattern_index = 0
    
    steps_str = ", ".join(map(str, MULTIPLIERS))
    await message.reply(
        f"🚀 <b>Auto Bet စတင်နေပါပြီ...</b>\n"
        f"👤 အကောင့်: <b>{USERNAME}</b>\n"
        f"📈 Multipliers: {steps_str}\n"
        f"💰 Base Amount: 10 ကျပ်\n"
        f"⚡ <i>(API ဖြင့် အမြန် Login ဝင်နေပါသည်...)</i>"
    )

    asyncio.create_task(run_playwright_task(USERNAME, PASSWORD))

# --- 🚀 Playwright Background Task ---
async def run_playwright_task(username, password):
    global is_bot_running, current_step, current_pattern_index
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            viewport={'width': 390, 'height': 844}, 
            is_mobile=True,
            has_touch=True  
        )
        page = await context.new_page()
        
        try:
            # ⚡ UI အစား API ကို အသုံးပြု၍ Login ဝင်ခြင်း
            login_success = await login_via_api_and_inject(page, username, password)
            
            if not login_success:
                error_msg = "❌ API Login Failed! စကားဝှက်မှားနေခြင်း ဖြစ်နိုင်ပါသည်။"
                await bot.send_message(OWNER_ID, error_msg)
                
                # အခြေအနေကို စစ်ဆေးရန် Screenshot ပို့ပေးမည်
                await page.screenshot(path="api_error.png")
                photo = FSInputFile("api_error.png")
                await bot.send_photo(OWNER_ID, photo, caption="📸 API ဖြင့်ချိတ်ဆက်မှု မအောင်မြင်သော မျက်နှာပြင်")
                if os.path.exists("api_error.png"): os.remove("api_error.png")
                
                is_bot_running = False
                return 
            
            # Login အောင်မြင်ပါက Game စတင်မည်
            while is_bot_running:
                current_bet_type = CUSTOM_PATTERN[current_pattern_index % len(CUSTOM_PATTERN)]
                display_type = "အကြီး (BIG) 🔴" if current_bet_type == "BIG" else "အသေး (SMALL) 🟢"
                current_multiplier = MULTIPLIERS[current_step]

                bet_success = await place_bet(page, bet_type=current_bet_type, step=current_step)
                
                if bet_success:
                    total_kyats = current_multiplier * 10
                    await bot.send_message(OWNER_ID, f"🎲 {display_type} သို့ <b>{total_kyats} ကျပ်</b> ({current_multiplier}ဆ) ဖြင့် လောင်းထားပါသည်။\n⏳ ရလဒ်စောင့်နေပါသည်...")
                    
                    await asyncio.sleep(30) 
                    is_win = await check_win_status(page)
                    
                    if is_win:
                        await bot.send_message(OWNER_ID, "🎉 <b>နိုင်ပါသည်!</b>\n🔄 Multiplier ကို အစမှ ပြန်လောင်းပါမည်။")
                        current_step = 0 
                    else:
                        current_step += 1 
                        
                        if current_step >= len(MULTIPLIERS):
                            await bot.send_message(OWNER_ID, f"🚨 <b>[DANGER] သတ်မှတ်ထားသော အဆင့် {len(MULTIPLIERS)} ဆင့်လုံး ရှုံးသွားပါပြီ။</b>\n🛑 Auto Bet ရပ်တန့်လိုက်ပါပြီ။")
                            is_bot_running = False
                            break
                        else:
                            await bot.send_message(OWNER_ID, f"❌ <b>ရှုံးပါသည်။</b>\nနောက်ပွဲကို <b>{MULTIPLIERS[current_step]}ဆ</b> ဖြင့် ဆက်လောင်းပါမည်။")
                    
                    current_pattern_index += 1
                else:
                    await bot.send_message(OWNER_ID, "⚠️ Error: လောင်း၍မရပါ။ ၅ စက္ကန့်အကြာ ပြန်စမ်းပါမည်။")
                    await asyncio.sleep(5)
                
                await asyncio.sleep(5) 

        finally:
            await browser.close()
            is_bot_running = False
            await bot.send_message(OWNER_ID, "🔌 Browser ပိတ်လိုက်ပါပြီ။")

@dp.message(Command("stopbet"))
async def stop_autobet(message: types.Message):
    global is_bot_running
    if message.from_user.id != OWNER_ID: return
    
    is_bot_running = False
    await message.reply("🛑 <b>Auto Bet ကို ရပ်တန့်ရန် အမိန့်ပေးလိုက်ပါပြီ။</b> (လက်ရှိပွဲပြီးလျှင် ရပ်ပါမည်)")

async def main():
    print("🚀 Wang Lin Game Store Auto Bet Bot စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
