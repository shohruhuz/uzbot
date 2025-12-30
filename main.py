import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from database import users_col, encrypt_pw, decrypt_pw, get_active_account
from emaktab_api import EMaktabAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Bot va Dispatcher sozlamalari
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

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Xush kelibsiz! Botdan foydalanish uchun Login:Parol yuboring:", reply_markup=main_kb())
    await BotState.auth.set()

# --- LOGIN & CAPTCHA JARAYONI ---
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

# --- ADMIN PANEL ---
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    count = users_col.count_documents({})
    await message.answer(f"📊 Statistika:\n👤 Foydalanuvchilar: {count}")

# --- AUTO REFRESH (YASHIRIN) ---
async def auto_refresh():
    # Bu yerda sessiyalarni yangilash kodi bo'ladi
    print("Sessiyalar yangilanmoqda...")

# --- ON STARTUP (XATONI TUZATISH QISMI) ---
async def on_startup(dispatcher):
    # Scheduler faqat loop ishga tushgandan keyin boshlanishi shart
    scheduler.add_job(auto_refresh, 'cron', hour='12,16')
    scheduler.start()
    print("Bot muvaffaqiyatli ishga tushdi!")

if __name__ == '__main__':
    # scheduler.start() ni bu yerdan olib tashladik va on_startup ichiga qo'shdik
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
