import asyncio
import os
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

# 💡 သတိပြုရန် - အကယ်၍ Login ဝင်ပြီးနောက် ဂိမ်း (ဥပမာ - Win Go) ဆီသို့ တိုက်ရိုက် မရောက်ပါက 
# အောက်ပါလင့်ခ်နေရာတွင် Win Go ဂိမ်း၏ လင့်ခ်အပြည့်အစုံကို ပြောင်းထည့်ပေးပါ။
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
# 🔐 2. UI AUTO LOGIN LOGIC (NATIVE EVENT INJECTION)
# ==========================================
async def login_via_ui(page, username, password):
    print("🔄 ဝဘ်ဆိုဒ်သို့ ချိတ်ဆက်၍ Login ဝင်နေပါသည်...")
    
    try:
        await page.goto("https://www.777bigwingame.app/#/login", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 🔧 Native Event Setter: Vue.js အား လူအစစ်ရိုက်သကဲ့သို့ အတင်းအသိအမှတ်ပြုခိုင်းခြင်း
        native_js = f"""
            function setNativeValue(element, value) {{
                const valueSetter = Object.getOwnPropertyDescriptor(element, 'value').set;
                const prototype = Object.getPrototypeOf(element);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
                
                if (valueSetter && valueSetter !== prototypeValueSetter) {{
                    prototypeValueSetter.call(element, value);
                }} else {{
                    valueSetter.call(element, value);
                }}
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            let phone = document.querySelector('input[name="userNumber"]');
            if (phone) setNativeValue(phone, '{username}');

            let pwd = document.querySelector('.passwordInput__container-input input');
            if (pwd) setNativeValue(pwd, '{password}');
        """
        
        print("🔄 အချက်အလက်များ ထည့်သွင်းနေပါသည်...")
        await page.evaluate(native_js)
        await page.wait_for_timeout(1000)

        print("🔄 Login ခလုတ်ကို နှိပ်နေပါသည်...")
        # Login ခလုတ်အား JavaScript ဖြင့် အတင်းနှိပ်ခိုင်းခြင်း
        await page.evaluate("""
            let btn = document.querySelector('div.signIn__container-button');
            if (btn) btn.click();
        """)
        
        await page.wait_for_timeout(5000)
        
        # URL ပြောင်းမပြောင်း စစ်ဆေးခြင်း
        current_url = page.url
        if "login" in current_url.lower():
            await page.screenshot(path="login_error.png")
            return False
            
        await page.goto(GAME_URL)
        await page.wait_for_timeout(4000) # ဂိမ်းစာမျက်နှာ ပွင့်လာရန် စောင့်မည်
        
        print("✅ UI မှတစ်ဆင့် Login ဝင်ခြင်း အောင်မြင်ပါပြီ။")
        return True

    except Exception as e:
        print(f"❌ Login ဝင်ရာတွင် အမှားအယွင်းရှိပါသည်: {e}")
        await page.screenshot(path="login_error.png")
        return False

# ==========================================
# 🤖 3. PLAYWRIGHT AUTO BET LOGIC (JS FIX)
# ==========================================
async def place_bet(page, bet_type="BIG", step=0):
    try:
        multiplier = MULTIPLIERS[step]
        print(f"🔄 လောင်းကြေးအဆင့်: {step + 1} | Pattern: {bet_type} | Multiplier: {multiplier}x")

        await page.wait_for_selector("div.Betting__C-foot-b", timeout=8000)

        # 1️⃣ အကြီး/အသေး ရွေးရန်
        if bet_type == "BIG":
            await page.evaluate("document.querySelector('div.Betting__C-foot-b').click()")
        else:
            await page.evaluate("document.querySelector('div.Betting__C-foot-s').click()")
        
        await page.wait_for_timeout(1000)

        # 2️⃣ Base Amount '10' ကို ရွေးရန်
        await page.locator("div.Betting__Popup-body-line-item:text-is('10')").first.evaluate("node => node.click()")
        await page.wait_for_timeout(500)

        # 3️⃣ Multiplier ထည့်သွင်းရန် (Native Event ဖြင့်)
        await page.evaluate(f"""
            let inputField = document.querySelector('input#van-field-1-input');
            if(inputField) {{
                const valueSetter = Object.getOwnPropertyDescriptor(inputField, 'value').set;
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(inputField), 'value').set;
                if (valueSetter && valueSetter !== prototypeValueSetter) prototypeValueSetter.call(inputField, '{multiplier}');
                else valueSetter.call(inputField, '{multiplier}');
                inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        """)
        await page.wait_for_timeout(500)

        # 4️⃣ အတည်ပြုရန်
        await page.evaluate("document.querySelector('div.Betting__Popup-foot-s').click()")
        print("✅ လောင်းကြေးတင်ခြင်း အောင်မြင်ပါသည်။")
        
        return True
    except Exception as e:
        print(f"❌ လောင်းကြေးတင်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
        await page.screenshot(path="bet_error.png") 
        return False

async def check_win_status(page):
    try:
        win_popup = page.locator("div.WinningTip__C-body-l1:has-text('ဂုဏ်ယူပါတယ်')")
        if await win_popup.is_visible(timeout=5000):
            await page.evaluate("document.body.click()") 
            return True
        return False
    except:
        return False

# ==========================================
# 🛠️ 4. CUSTOM SETTINGS HANDLERS
# ==========================================
@dp.message(F.text.startswith(".setp"))
async def set_pattern(message: types.Message):
    global CUSTOM_PATTERN, current_pattern_index
    if message.from_user.id != OWNER_ID: return

    try:
        raw_pattern = message.text.replace(".setp", "").replace(" ", "").upper()
        if not raw_pattern: return await message.reply("⚠️ ပုံစံမှားယွင်းနေပါသည်။")

        parts = raw_pattern.split(",")
        new_pattern = []
        for p in parts:
            if p == 'B': new_pattern.append("BIG")
            elif p == 'S': new_pattern.append("SMALL")
            else: return await message.reply(f"❌ Error: 'B' သို့မဟုတ် 'S' ကိုသာ အသုံးပြုပါ။")
        
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
        if not parts: return await message.reply("⚠️ ပုံစံမှားယွင်းနေပါသည်။")
        
        MULTIPLIERS = [int(x) for x in parts]
        current_step = 0
        steps_str = "ဆ, ".join(map(str, MULTIPLIERS)) + "ဆ"
        await message.reply(f"✅ <b>လောင်းကြေးအဆင့်များ ပြင်ဆင်ပြီးပါပြီ။</b>\n🔢 စုစုပေါင်း ({len(MULTIPLIERS)}) ဆင့်: <b>{steps_str}</b>")
    except ValueError:
        await message.reply("❌ Error: ကိန်းဂဏန်းများသာ ကွက်လပ်ခြား၍ ရိုက်ထည့်ပါ။")

# ==========================================
# 🎮 5. TELEGRAM BOT CORE HANDLERS
# ==========================================
@dp.message(Command("autobet"))
async def ask_credentials(message: types.Message, state: FSMContext):
    global is_bot_running
    if message.from_user.id != OWNER_ID: return await message.reply("🚫 <b>Access Denied!</b>")
    if is_bot_running: return await message.reply("⚠️ Auto Bet အလုပ်လုပ်နေဆဲ ဖြစ်ပါသည်။ ရပ်ချင်ပါက /stopbet ကို နှိပ်ပါ။")
    
    await message.reply("🔑 ဖုန်းနံပါတ် နှင့် Password ကို ကွက်လပ်ခြား၍ ရိုက်ထည့်ပါ။ (ဥပမာ - <code>09680090540 Mitheint11</code>)")
    await state.set_state(AutoBetState.waiting_for_credentials)

@dp.message(AutoBetState.waiting_for_credentials)
async def start_autobet_with_creds(message: types.Message, state: FSMContext):
    global is_bot_running, current_step, current_pattern_index

    parts = message.text.strip().split()
    if len(parts) != 2: return await message.reply("❌ ပုံစံမှားယွင်းနေပါသည်။")

    USERNAME, PASSWORD = parts[0], parts[1]
    await state.clear() 

    is_bot_running = True
    current_step, current_pattern_index = 0, 0
    steps_str = ", ".join(map(str, MULTIPLIERS))
    await message.reply(
        f"🚀 <b>Auto Bet စတင်နေပါပြီ...</b>\n"
        f"👤 အကောင့်: <b>{USERNAME}</b>\n"
        f"📈 Multipliers: {steps_str}\n"
        f"💰 Base Amount: 10 ကျပ်\n⚡ <i>(Native Event ဖြင့် ချိတ်ဆက်နေပါသည်...)</i>"
    )

    asyncio.create_task(run_playwright_task(USERNAME, PASSWORD))

async def run_playwright_task(username, password):
    global is_bot_running, current_step, current_pattern_index
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True  
        )
        page = await context.new_page()
        
        try:
            login_success = await login_via_ui(page, username, password)
            if not login_success:
                await bot.send_message(OWNER_ID, "❌ Login Failed! မျက်နှာပြင် အခြေအနေကို စစ်ဆေးနေပါသည်...")
                if os.path.exists("login_error.png"):
                    photo = FSInputFile("login_error.png")
                    await bot.send_photo(OWNER_ID, photo, caption="📸 Login မဝင်နိုင်သော မျက်နှာပြင်")
                    os.remove("login_error.png")
                is_bot_running = False
                return 
            
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
                            await bot.send_message(OWNER_ID, f"🚨 <b>[DANGER] အဆင့် {len(MULTIPLIERS)} ဆင့်လုံး ရှုံးသွားပါပြီ။</b>\n🛑 Auto Bet ရပ်တန့်လိုက်ပါပြီ။")
                            is_bot_running = False
                            break
                        else:
                            await bot.send_message(OWNER_ID, f"❌ <b>ရှုံးပါသည်။</b>\nနောက်ပွဲကို <b>{MULTIPLIERS[current_step]}ဆ</b> ဖြင့် ဆက်လောင်းပါမည်။")
                    
                    current_pattern_index += 1
                else:
                    await bot.send_message(OWNER_ID, "⚠️ Error: လောင်း၍မရပါ။ မျက်နှာပြင် အခြေအနေကို စစ်ဆေးနေပါသည်...")
                    if os.path.exists("bet_error.png"):
                        photo = FSInputFile("bet_error.png")
                        await bot.send_photo(OWNER_ID, photo, caption="📸 လောင်းကြေးတင်ချိန်တွင် ရပ်တန့်နေသော မျက်နှာပြင်")
                        os.remove("bet_error.png")
                    
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
    except KeyboardInterrupt: pass
