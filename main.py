import os
import asyncio
import threading
import logging
import time
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# O'zimiz yaratgan modullar
from database import users_col, encrypt_pw, decrypt_pw, get_active_account
from emaktab_api import EMaktabAPI

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FLASK (Health Check) ---
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "Bot is alive!", 200

# --- BOT SOZLAMALARI ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

class BotState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()
    captcha = State()

def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📅 Dars Jadvali", "📊 Baholarim")
    kb.add("🛑 Davomat", "📝 Uy vazifalari")
    kb.add("📈 Tahlil & Reyting", "👤 Akkauntlar")
    kb.add("⚙️ Sozlamalar")
    return kb

# --- ASOSIY HANDLERLAR ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    user = users_col.find_one({"user_id": message.from_user.id})
    
    if user and user.get("accounts"):
        await message.answer(
            f"Xush kelibsiz, {message.from_user.first_name}! 👋\nMa'lumotlar yuklanmoqda...",
            reply_markup=main_kb()
        )
    else:
        await message.answer(
            f"Salom {message.from_user.first_name}! Botdan foydalanish uchun eMaktab **loginini** kiriting:"
        )
        await BotState.waiting_for_login.set()

@dp.message_handler(state=BotState.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    await state.update_data(l=message.text.strip())
    await message.answer("Endi **parolingizni** kiriting:")
    await BotState.waiting_for_password.set()

@dp.message_handler(state=BotState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    login = data['l']
    
    await message.answer("⏳ eMaktab tizimiga ulanilmoqda...")
    
    loop = asyncio.get_event_loop()
    api = EMaktabAPI(login, password)
    # Login jarayonini asinxron bajarish
    res = await loop.run_in_executor(None, api.login_attempt)
    
    if res['status'] == 'captcha':
        await state.update_data(p=password)
        await message.answer("⚠️ **Iltimos, inson ekanligingizni isbotlang!**")
        await bot.send_photo(message.chat.id, res['url'], caption="Rasmda ko'rsatilgan kodni kiriting:")
        await BotState.captcha.set()
    elif res['status'] == 'success':
        save_to_db(message.from_user.id, login, password, res['cookies'])
        await message.answer("✅ Muvaffaqiyatli kirdingiz!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Login yoki parol xato. Qaytadan **loginni** kiriting:")
        await BotState.waiting_for_login.set()

@dp.message_handler(state=BotState.captcha)
async def handle_captcha(message: types.Message, state: FSMContext):
    captcha_answer = message.text.strip()
    data = await state.get_data()
    loop = asyncio.get_event_loop()
    
    api = EMaktabAPI(data['l'], data['p'])
    res = await loop.run_in_executor(None, api.login_attempt, captcha_answer)
    
    if res['status'] == 'success':
        save_to_db(message.from_user.id, data['l'], data['p'], res['cookies'])
        await message.answer("✅ Akkaunt muvaffaqiyatli ulandi!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Kod xato. Loginni qaytadan kiriting:")
        await BotState.waiting_for_login.set()

# --- REAL FUNKSIYALAR TUGMALARI ---

@dp.message_handler(lambda m: m.text == "📅 Dars Jadvali")
async def get_timetable(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return await message.answer("Avval akkaunt ulang.")
    
    wait_msg = await message.answer("⏳ Jadval yuklanmoqda...")
    loop = asyncio.get_event_loop()
    
    # MUHIM: Xatolikni oldini olish uchun 3 ta argument
    api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
    api.cookies = acc['cookies'] # Cookies alohida o'zlashtiriladi
    
    data = await loop.run_in_executor(None, api.get_schedule)
    await wait_msg.delete()
    await message.answer(f"📅 **Sizning dars jadvalingiz:**\n\n{data}")

@dp.message_handler(lambda m: m.text == "📊 Baholarim")
async def get_grades(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return
    
    wait_msg = await message.answer("⏳ Baholar tahlil qilinmoqda...")
    loop = asyncio.get_event_loop()
    
    api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
    api.cookies = acc['cookies']
    
    grades = await loop.run_in_executor(None, api.get_grades)
    await wait_msg.delete()
    await message.answer(f"📊 **Oxirgi baholaringiz:**\n\n{grades}")

@dp.message_handler(lambda m: m.text == "🛑 Davomat")
async def get_attendance(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return
    
    wait_msg = await message.answer("⏳ Davomat tekshirilmoqda...")
    loop = asyncio.get_event_loop()
    
    api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
    api.cookies = acc['cookies']
    
    report = await loop.run_in_executor(None, api.get_attendance)
    await wait_msg.delete()
    await message.answer(f"🛑 **Davomat hisoboti:**\n\n{report}")

# --- ADMIN STATS ---
@dp.message_handler(commands=['admin_stats'])
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    count = users_col.count_documents({})
    await message.answer(f"📊 **Bot statistikasi:**\n\nJami foydalanuvchilar: {count}")

def save_to_db(user_id, login, password, cookies):
    users_col.update_one(
        {"user_id": user_id},
        {"$push": {"accounts": {
            "login": login, "password": encrypt_pw(password), 
            "cookies": cookies, "active": True
        }}}, upsert=True
    )

# --- ISHGA TUSHIRISH ---
async def on_startup(dispatcher):
    if not scheduler.running: scheduler.start()
    logger.info("Bot tizimi muvaffaqiyatli ishga tushdi!")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=port)
