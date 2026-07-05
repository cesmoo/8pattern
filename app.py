import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from playwright.async_api import async_playwright

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "1318826936"))
WEB_TOKEN = os.getenv("WEB_TOKEN") 
GAME_URL = "https://www.777bigwingame.app/"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 🔄 System Variables
MULTIPLIERS = [1, 2, 4, 8, 16, 32, 64] # Default လောင်းကြေးအဆင့်များ
CUSTOM_PATTERN = ["BIG"] # Default Pattern (အမြဲတမ်း အကြီး)
current_step = 0
current_pattern_index = 0
is_bot_running = False

# ==========================================
# 🔐 2. UI AUTO LOGIN LOGIC
# ==========================================
async def login_via_ui(page, username, password):
    print("🔄 ဝဘ်ဆိုဒ်သို့ ချိတ်ဆက်၍ Login ဝင်နေပါသည်...")
    
    # ၁။ Login Page သို့ သွားရန်
    await page.goto("https://www.777bigwingame.app/#/login")
    await page.wait_for_timeout(3000)

    try:
        # ၂။ ဖုန်းနံပါတ် (Username) ရိုက်ထည့်ရန် (Screenshot မှ name="userNumber" ကို အသုံးပြုထားသည်)
        username_input = page.locator('input[name="userNumber"]')
        await username_input.fill(username)
        await page.wait_for_timeout(500)

        # ၃။ Password ရိုက်ထည့်ရန် (Screenshot မှ placeholder="စကားဝှက်" ကို အသုံးပြုထားသည်)
        password_input = page.locator('input[placeholder="စကားဝှက်"]')
        await password_input.fill(password)
        await page.wait_for_timeout(500)

        # ၄။ Login ခလုတ်ကို နှိပ်ရန် (div class="signIn__container-button" ကို အသုံးပြုထားသည်)
        await page.click('div.signIn__container-button')
        
        # Login ဝင်ပြီးနောက် Home Page သို့ ရောက်ရန် စောင့်ဆိုင်းခြင်း
        await page.wait_for_timeout(5000)
        
        # ၅။ Game ရှိရာ စာမျက်နှာသို့ ဆက်သွားရန်
        await page.goto(GAME_URL)
        await page.wait_for_timeout(3000)
        
        print("✅ UI မှတစ်ဆင့် Login ဝင်ခြင်း အောင်မြင်ပါပြီ။")
        return True

    except Exception as e:
        print(f"❌ Login ဝင်ရာတွင် အမှားအယွင်းရှိပါသည်: {e}")
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

        # 2️⃣ Base Amount '10' ကို ရွေးရန် (text-is ကို သုံး၍ တိတိကျကျ ရွေးချယ်ခြင်း)
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
        # စာသားများကို သန့်စင်ပြီး 'B,S,B,B' ပုံစံဖော်ခြင်း
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
        current_pattern_index = 0 # Pattern အသစ်ပြောင်းလျှင် အစမှပြန်စမည်
        
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
            return await message.reply("⚠️ ပုံစံမှားယွင်းနေပါသည်။\nဥပမာ - <code>.set 1 2 4 8 16</code>")
        
        new_multipliers = [int(x) for x in parts]
        MULTIPLIERS = new_multipliers
        current_step = 0 # လောင်းကြေးအသစ်ပြောင်းလျှင် အဆင့် ၁ မှ ပြန်စမည်
        
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
async def start_autobet(message: types.Message):
    global is_bot_running, current_step, current_pattern_index
    
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 <b>Access Denied!</b>")
    
    if is_bot_running:
        return await message.reply("⚠️ Auto Bet အလုပ်လုပ်နေဆဲ ဖြစ်ပါသည်။")
    
    if not WEB_TOKEN:
        return await message.reply("❌ Error: WEB_TOKEN မရှိပါ။")

    is_bot_running = True
    current_step = 0
    current_pattern_index = 0
    
    steps_str = ", ".join(map(str, MULTIPLIERS))
    await message.reply(f"🚀 <b>Auto Bet စတင်နေပါပြီ...</b>\n(Multipliers: {steps_str})\n(Base Amount: 10 ကျပ်)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            await login_via_token(page, WEB_TOKEN)
            
            while is_bot_running:
                # Pattern ထဲမှ လက်ရှိလောင်းရမည့် အကြီး/အသေး ကို ရွေးချယ်ခြင်း
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
                    
                    # နိုင်သည်ဖြစ်စေ ရှုံးသည်ဖြစ်စေ Pattern အစီအစဉ်ကို နောက်တစ်ဆင့်သို့ ပြောင်းမည်
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
    print("🚀 Auto Bet Bot စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
