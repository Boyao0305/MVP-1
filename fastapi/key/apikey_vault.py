import json
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from key.aes_crypto import encrypt_string, decrypt_string

VAULT_PATH = "key/keyVault.json"
# VAULT_PATH = r"D:\Github\MVP-1\fastapi\key\keyVault.json"
class APIKeyVault:
    def __init__(self, path=VAULT_PATH):
        self.path = path
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump({}, f)

    def _load(self):
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def add_key(self, name: str, plain_key: str):
        data = self._load()
        encrypted = encrypt_string(plain_key)
        data[name] = encrypted
        self._save(data)
        print(f"✅ 密钥 [{name}] 已加密保存")

    def get_key(self, name: str) -> str:
        data = self._load()
        if name not in data:
            raise KeyError(f"❌ 未找到密钥: {name}")
        return decrypt_string(data[name])

    def list_keys(self):
        return list(self._load().keys())

# API = APIKeyVault()
#
# answer = APIKeyVault.add_key(API, name="WechatID", plain_key="...")
