import requests
import time

class EMaktabAPI:
    def __init__(self, login=None, password=None, cookies=None):
        self.login = login
        self.password = password
        self.session = requests.Session()
        if cookies:
            self.session.cookies.update(cookies)
        
        # Brauzer simulyatsiyasi (User-Agent)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://login.emaktab.uz/login"
        }

    def login_attempt(self, captcha_answer=None):
        try:
            login_url = "https://login.emaktab.uz/login"
            
            # 1. Oldin login sahifasini yuklab cookies va sessiyani tayyorlaymiz
            self.session.get(login_url, headers=self.headers, timeout=10)

            # 2. Yuboriladigan ma'lumotlar
            payload = {
                "login": self.login,
                "password": self.password,
                "isCaptchaRequired": "False"
            }

            if captcha_answer:
                payload["captchaAnswer"] = captcha_answer
                payload["isCaptchaRequired"] = "True"

            # 3. POST so'rovi orqali login qilish
            response = self.session.post(login_url, data=payload, headers=self.headers, timeout=15)

            # Captcha tekshiruvi
            if "captcha" in response.text.lower() and not captcha_answer:
                captcha_url = f"https://login.emaktab.uz/captcha/image?v={int(time.time())}"
                return {"status": "captcha", "url": captcha_url}

            # 4. Muvaffaqiyatli kirishni .ASPXAUTH cookie orqali aniqlaymiz
            cookies_dict = self.session.cookies.get_dict()
            if ".ASPXAUTH" in cookies_dict:
                return {
                    "status": "success", 
                    "cookies": cookies_dict
                }
            
            return {"status": "error", "message": "Login yoki parol xato."}

        except Exception as e:
            return {"status": "error", "message": f"Ulanish xatosi: {str(e)}"}
