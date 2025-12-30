import requests
import time
from datetime import datetime

class EMaktabAPI:
    def __init__(self, login=None, password=None, cookies=None):
        self.login = login
        self.password = password
        self.session = requests.Session()
        if cookies:
            self.session.cookies.update(cookies)
        
        self.api_url = "https://api.emaktab.uz/v1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

    def login_attempt(self, captcha_answer=None):
        """Tizimga kirish va cookielarni olish"""
        login_url = "https://login.emaktab.uz/login"
        payload = {"login": self.login, "password": self.password}
        if captcha_answer:
            payload["captchaAnswer"] = captcha_answer
            payload["isCaptchaRequired"] = "True"

        try:
            response = self.session.post(login_url, data=payload, headers=self.headers, timeout=15)
            if "captcha" in response.text.lower() and not captcha_answer:
                return {"status": "captcha", "url": f"https://login.emaktab.uz/captcha/image?v={int(time.time())}"}

            if ".ASPXAUTH" in self.session.cookies.get_dict():
                return {"status": "success", "cookies": self.session.cookies.get_dict()}
            return {"status": "error", "message": "Login yoki parol xato."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_me(self):
        """Foydalanuvchi ma'lumotlarini (ID-larni) olish"""
        try:
            res = self.session.get(f"{self.api_url}/authorizations", headers=self.headers)
            return res.json() if res.status_code == 200 else None
        except:
            return None

    def get_schedule(self):
        """Bugungi dars jadvalini olish"""
        try:
            # Bugungi sanani olish
            today = datetime.now().strftime("%Y-%m-%d")
            # Eslatma: Haqiqiy API so'rovida eduGroup va personId kerak
            # Hozircha umumiy mantiq:
            res = self.session.get(f"{self.api_url}/persons/me/schedules?startDate={today}&endDate={today}", headers=self.headers)
            
            data = res.json() if res.status_code == 200 else []
            
            if not data or 'days' not in data or not data['days'][0].get('lessons'):
                return "🗓 **Bugun dars jadvali yo'q.**\nDam olish kuningiz mazmunli o'tsin! 😊"

            msg = "📚 **Bugungi dars jadvalingiz:**\n\n"
            lessons = data['days'][0]['lessons']
            for i, lesson in enumerate(lessons, 1):
                subject = lesson.get('subject', {}).get('name', 'Nomaʼlum dars')
                msg += f"{i}. {subject}\n"
            return msg
        except:
            return "❌ Jadvalni yuklashda xatolik yuz berdi."

    def get_grades(self):
        """Bugungi baholarni olish"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            res = self.session.get(f"{self.api_url}/persons/me/marks/{today}/{today}", headers=self.headers)
            
            data = res.json() if res.status_code == 200 else []

            if not data:
                return "📊 **Bugun hali baho olmadingiz.**\nHarakatdan to'xtamang! 💪"

            msg = "🌟 **Bugungi baholaringiz:**\n\n"
            for g in data:
                subject = g.get('subjectName', 'Dars nomi')
                value = g.get('value', 'Baho')
                msg += f"🔹 {subject}: {value}\n"
            return msg
        except:
            return "❌ Baholarni yuklashda xatolik."
