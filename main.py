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
def health():
    return "Bot is running!", 200

# --- BOT SOZLAMALARI ---
TOKEN = os.getenv("BOT_TOKEN")
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
            f"Xush kelibsiz, {message.from_user.first_name}! 👋\nMenyudan kerakli bo'limni tanlang:",
            reply_markup=main_kb()
        )
    else:
        await message.answer(f"Salom {message.from_user.first_name}! Botdan foydalanish uchun eMaktab **loginini** kiriting:")
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
    res = await loop.run_in_executor(None, api.login_attempt)
    
    if res['status'] == 'captcha':
        await state.update_data(p=password)
        await bot.send_photo(message.chat.id, res['url'], caption="⚠️ **Captcha!** Rasmda ko'rsatilgan kodni kiriting:")
        await BotState.captcha.set()
    elif res['status'] == 'success':
        save_to_db(message.from_user.id, login, password, res['cookies'])
        await message.answer("✅ Muvaffaqiyatli kirdingiz!", reply_markup=main_kb())
        await state.finish()
    else:
        await message.answer("❌ Login yoki parol xato. Qaytadan kiriting:")
        await BotState.waiting_for_login.set()

# --- REAL FUNKSIYALAR TUGMALARI (Bo'sh ma'lumot tekshiruvi bilan) ---

@dp.message_handler(lambda m: m.text == "📅 Dars Jadvali")
async def get_timetable(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return
    
    wait_msg = await message.answer("⏳ Jadval yuklanmoqda...")
    try:
        loop = asyncio.get_event_loop()
        api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
        api.cookies = acc['cookies']
        
        data = await loop.run_in_executor(None, api.get_schedule)
        await wait_msg.delete()
        
        # Agar dars bo'lmasa (API dan bo'sh yoki xabar kelsa)
        if not data or "yo'q" in data.lower():
            await message.answer("🗓 **Bugun dars jadvali yo'q.**\nDam olish kuningiz mazmunli o'tsin! 😊")
        else:
            await message.answer(f"📅 **Sizning dars jadvalingiz:**\n\n{data}")
    except Exception as e:
        await wait_msg.edit_text("❌ Jadvalni yuklashda xatolik yuz berdi.")

@dp.message_handler(lambda m: m.text == "📊 Baholarim")
async def get_grades(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return
    
    wait_msg = await message.answer("⏳ Baholar tahlil qilinmoqda...")
    try:
        loop = asyncio.get_event_loop()
        api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
        api.cookies = acc['cookies']
        
        grades = await loop.run_in_executor(None, api.get_grades)
        await wait_msg.delete()
        
        if not grades or "yo'q" in grades.lower():
            await message.answer("📊 **Bugun hali baho olmadingiz.**\nHarakatdan to'xtamang! 💪")
        else:
            await message.answer(f"📊 **Bugungi baholaringiz:**\n\n{grades}")
    except Exception as e:
        await wait_msg.edit_text("❌ Baholarni yuklashda xatolik yuz berdi.")

@dp.message_handler(lambda m: m.text == "🛑 Davomat")
async def get_attendance(message: types.Message):
    acc = get_active_account(message.from_user.id)
    if not acc: return
    
    wait_msg = await message.answer("⏳ Davomat tekshirilmoqda...")
    try:
        loop = asyncio.get_event_loop()
        api = EMaktabAPI(acc['login'], decrypt_pw(acc['password']))
        api.cookies = acc['cookies']
        
        report = await loop.run_in_executor(None, api.get_attendance)
        await wait_msg.delete()
        
        if not report or "yo'q" in report.lower() or "✅" in report:
            await message.answer("✅ **Sizda bugun dars qoldirish holatlari yo'q.**\nBarakalla! 👏")
        else:
            await message.answer(f"🛑 **Davomat hisoboti:**\n\n{report}")
    except Exception as e:
        await wait_msg.edit_text("❌ Ma'lumot olishda xatolik.")

# --- QOLGAN FUNKSIYALAR ---

def save_to_db(user_id, login, password, cookies):
    users_col.update_one(
        {"user_id": user_id},
        {"$push": {"accounts": {
            "login": login, "password": encrypt_pw(password), 
            "cookies": cookies, "active": True
        }}}, upsert=True
    )

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=port)
