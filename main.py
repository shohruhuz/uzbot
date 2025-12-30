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

# --- FLASK ---
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "OK", 200

# --- BOT ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler()

class BotState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()
    captcha = State()

def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📅 Dars Jadvali", "📊 Baholarim", "🛑 Davomat", "📝 Uy vazifalari")
    kb.add("📈 Tahlil & Reyting", "👤 Akkauntlar", "⚙️ Sozlamalar")
    return kb

# --- HANDLERLAR ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        f"👋 Salom {message.from_user.first_name}! Botga xush kelibsiz.\n\n"
        "Iltimos, eMaktab **login** (foydalanuvchi nomi) ni kiriting:"
    )
    await BotState.waiting_for_login.set()

@dp.message_handler(state=BotState.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    await state.update_data(l=message.text.strip())
    await message.answer("Endi, eMaktab **parolingizni** kiriting:")
    await BotState.waiting_for_password.set()

@dp.message_handler(state=BotState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    login = data['l']
    
    msg = await message.answer("⏳ eMaktabga ulanilmoqda...")
    
    api = EMaktabAPI(login, password)
    res = api.login_attempt()
    
    if res['status'] == 'captcha':
        await state.update_data(p=password)
        await message.answer("⚠️ **Iltimos, inson ekanligingizni isbotlang!**")
        await bot.send_photo(
            message.chat.id, 
            res['url'], 
            caption="Rasmda ko'rsatilgan kodni kiriting:"
        )
        await BotState.captcha.set()
    elif res['status'] == 'success':
        save_to_db(message.from_user.id, login, password, res['cookies'])
        await message.answer("✅ Muvaffaqiyatli kirdingiz!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Login yoki parol xato. Qaytadan **loginni** yuboring:")
        await BotState.waiting_for_login.set()

@dp.message_handler(state=BotState.captcha)
async def handle_captcha(message: types.Message, state: FSMContext):
    captcha_answer = message.text.strip()
    data = await state.get_data()
    
    api = EMaktabAPI(data['l'], data['p'])
    res = api.login_attempt(captcha_answer=captcha_answer)
    
    if res['status'] == 'success':
        save_to_db(message.from_user.id, data['l'], data['p'], res['cookies'])
        await message.answer("✅ Captcha tasdiqlandi. Akkaunt ulandi!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Kod noto'g'ri. Iltimos, qaytadan **loginni** kiriting:")
        await BotState.waiting_for_login.set()

def save_to_db(user_id, login, password, cookies):
    users_col.update_one(
        {"user_id": user_id},
        {"$push": {"accounts": {
            "login": login, 
            "password": encrypt_pw(password), 
            "cookies": cookies, 
            "active": True
        }}},
        upsert=True
    )

# --- ISHGA TUSHIRISH LOGIKASI ---

async def on_startup(dispatcher):
    if not scheduler.running:
        scheduler.start()
    logger.info("Bot tizimi ishga tushdi!")

def run_bot():
    """Botni xatoliklarga chidamli (robust) usulda ishga tushirish"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            logger.info("Polling boshlanmoqda...")
            executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
        except Exception as e:
            logger.error(f"Pollingda xatolik: {e}")
            # Conflict yoki internet uzilsa 5 soniya kutib qayta urinadi
            time.sleep(5)

if __name__ == "__main__":
    # Render uchun port
    port = int(os.environ.get("PORT", 10000))
    
    # 1. Botni parallel oqimda ishga tushirish
    threading.Thread(target=run_bot, daemon=True).start()
    
    # 2. Flaskni asosiy oqimda ishga tushirish (Render portni ko'rishi uchun)
    logger.info(f"Veb-server {port}-portda ishga tushdi.")
    flask_app.run(host="0.0.0.0", port=port)
