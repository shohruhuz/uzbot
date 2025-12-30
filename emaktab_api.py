import requests

class EMaktabAPI:
    def __init__(self, login=None, password=None):
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://api.emaktab.uz/v1"
        self.headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)"}

    def login_attempt(self, captcha_answer=None):
        url = "https://login.emaktab.uz/login"
        data = {"login": self.login, "password": self.password}
        if captcha_answer:
            data["captchaAnswer"] = captcha_answer
        
        response = self.session.post(url, data=data, headers=self.headers)
        if "captcha" in response.text.lower():
            # Captcha rasmi manzili
            return {"status": "captcha", "url": "https://login.emaktab.uz/captcha/image"}
        
        if response.status_code == 200:
            return {"status": "success", "cookies": self.session.cookies.get_dict()}
        return {"status": "error"}

    def get_marks(self, cookies):
        res = self.session.get(f"{self.base_url}/marks", cookies=cookies)
        return res.json() if res.status_code == 200 else None
