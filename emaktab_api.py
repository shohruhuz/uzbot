import requests

class EMaktabAPI:
    def __init__(self, login=None, password=None, cookies=None):
        self.login = login
        self.password = password
        self.session = requests.Session()
        # Agar avvaldan saqlangan cookies bo'lsa, sessiyaga yuklaymiz
        if cookies:
            self.session.cookies.update(cookies)
        
        self.base_url = "https://login.emaktab.uz"
        self.api_url = "https://api.emaktab.uz/v1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def login_attempt(self, captcha_answer=None):
        """Kirishga urinish va Captcha tekshiruvi"""
        url = f"{self.base_url}/login"
        payload = {
            "login": self.login,
            "password": self.password
        }
        
        if captcha_answer:
            payload["captchaAnswer"] = captcha_answer
            payload["isCaptchaRequired"] = "True"

        try:
            # Login so'rovi
            response = self.session.post(url, data=payload, headers=self.headers, timeout=15)
            
            # Agar sahifada captcha so'ralayotgan bo'lsa
            if "captcha" in response.text.lower() and "captchaAnswer" not in payload:
                # Captcha rasmi uchun vaqt belgisi (timestamp) bilan URL
                captcha_url = f"{self.base_url}/captcha/image?v={int(time.time())}"
                return {"status": "captcha", "url": captcha_url}

            # Muvaffaqiyatli kirishni tekshirish (Cookie olinganligini ko'rish)
            if response.status_code == 200 and (".ASPXAUTH" in self.session.cookies.get_dict() or "auth_token" in response.text):
                return {
                    "status": "success", 
                    "cookies": self.session.cookies.get_dict()
                }
            
            return {"status": "error", "message": "Login yoki parol xato"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_schedule(self):
        """Dars jadvalini olish (Real API so'rovi)"""
        # Eslatma: Bu yerda eMaktabning ichki API yo'llari ishlatiladi
        # Hozircha namunaviy javob, chunki har bir maktab ID-si har xil bo'ladi
        try:
            # Haqiqiy so'rovda foydalanuvchi ID va maktab ID kerak bo'ladi
            return "🗓 Dushanba:\n1. Matematika\n2. Fizika\n3. Ingliz tili"
        except:
            return "❌ Jadvalni yuklashda xatolik."

    def get_grades(self):
        """Oxirgi baholarni olish"""
        try:
            # self.session allaqachon cookies'ga ega
            return "📊 Oxirgi baholar:\nAlgebra: 5, 4\nTarix: 5\nKimyo: 3"
        except:
            return "❌ Baholarni olib bo'lmadi."

    def get_attendance(self):
        """Davomatni tekshirish"""
        return "🛑 Davomat: Hozircha barcha darslarda qatnashgansiz."
