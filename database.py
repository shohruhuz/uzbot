import os
from pymongo import MongoClient
from cryptography.fernet import Fernet

# Environment variables
SECRET_KEY = os.getenv("SECRET_KEY", Fernet.generate_key().decode()).encode()
cipher = Fernet(SECRET_KEY)
client = MongoClient(os.getenv("MONGO_URL"))
db = client['emaktab_pro_bot']
users_col = db['users']

def encrypt_pw(password):
    return cipher.encrypt(password.encode()).decode()

def decrypt_pw(encrypted_password):
    return cipher.decrypt(encrypted_password.encode()).decode()

def get_active_account(user_id):
    user = users_col.find_one({"user_id": user_id})
    if user and 'accounts' in user:
        return next((acc for acc in user['accounts'] if acc.get('active')), None)
    return None
