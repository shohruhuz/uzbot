import os
import asyncio
import threading
import logging
from flask import Flask
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# O'zimiz yaratgan modullar
from database import users_col, encrypt_pw, decrypt_pw, get_active_account
from emaktab_api import EMaktabAPI

# --- LOGGING SOZLAMALARI ---
logging.basicConfig(level=logging.INFO)

# --- FLASK SERVER (Render uchun Health Check) ---
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "Bot is running OK!", 200

# --- BOT SOZLAMALARI ---
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

class BotState(StatesGroup):
    auth = State()
    captcha = State()

# --- TUGMALAR ---
def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📅 Dars Jadvali", "📊 Baholarim", "🛑 Davomat", "📝 Uy vazifalari")
    kb.add("📈 Tahlil & Reyting", "👤 Akkauntlar", "⚙️ Sozlamalar")
    return kb

# --- HANDLERLAR ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Xush kelibsiz! eMaktab botdan foydalanish uchun Login:Parol yuboring:", reply_markup=main_kb())
    await BotState.auth.set()

@dp.message_handler(state=BotState.auth)
async def handle_auth(message: types.Message, state: FSMContext):
    if ":" not in message.text:
        return await message.answer("Xato! Format: Login:Parol")
    
    login, pw = message.text.split(":", 1)
    api = EMaktabAPI(login, pw)
    res = api.login_attempt()
    
    if res['status'] == 'captcha':
        await state.update_data(l=login, p=pw)
        await bot.send_photo(message.chat.id, res['url'], caption="Rasmdagi kodni kiriting:")
        await BotState.captcha.set()
    elif res['status'] == 'success':
        users_col.update_one(
            {"user_id": message.from_user.id},
            {"$push": {"accounts": {"login": login, "password": encrypt_pw(pw), "cookies": res['cookies'], "active": True}}},
            upsert=True
        )
        await message.answer("✅ Kirish muvaffaqiyatli!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Login yoki parol xato.")

@dp.message_handler(state=BotState.captcha)
async def handle_captcha(message: types.Message, state: FSMContext):
    data = await state.get_data()
    api = EMaktabAPI(data['l'], data['p'])
    res = api.login_attempt(captcha_answer=message.text)
    
    if res['status'] == 'success':
        users_col.update_one(
            {"user_id": message.from_user.id},
            {"$push": {"accounts": {"login": data['l'], "password": encrypt_pw(data['p']), "cookies": res['cookies'], "active": True}}},
            upsert=True
        )
        await message.answer("✅ Captcha tasdiqlandi. Kirdingiz!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Kod xato, qaytadan urinib ko'ring (Login:Parol):")
        await BotState.auth.set()

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    count = users_col.count_documents({})
    await message.answer(f"📊 Statistika:\n👤 Foydalanuvchilar: {count}")

# --- ISHGA TUSHIRISH FUNKSIYALARI ---
async def on_startup(dispatcher):
    # Scheduler ishga tushishi
    scheduler.add_job(lambda: print("Sessiyalar yangilanmoqda..."), 'cron', hour='12,16')
    scheduler.start()
    logging.info("Bot ishga tushdi!")

def run_bot_thread():
    # Alohida thread ichida loop yaratish
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

if __name__ == "__main__":
    # 1. Botni alohida oqimda (Thread) boshlaymiz
    threading.Thread(target=run_bot_thread, daemon=True).start()
    
    # 2. Flaskni asosiy oqimda ishga tushiramiz (Render portni shu orqali ko'radi)
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
