import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# 加载 .env 或 key.env 中的 AES 密钥
if "AES_SECRET_KEY" not in os.environ:
    # load_dotenv(dotenv_path="D:/Github/MVP-1/fastapi/key/key.env")
    load_dotenv(dotenv_path="key/key.env")

key = os.getenv("AES_SECRET_KEY")

if not key:
    raise ValueError("❌ 未找到 AES_SECRET_KEY：请设置环境变量或 key.env")
# 创建 Fernet 加解密器
cipher = Fernet(key.encode())


def encrypt_string(plain_text: str) -> str:
    """
    加密字符串，返回 base64 编码的密文字符串
    """
    encrypted = cipher.encrypt(plain_text.encode())
    return encrypted.decode()


def decrypt_string(cipher_text: str) -> str:
    """
    解密 base64 编码的密文字符串，返回原始明文
    """
    decrypted = cipher.decrypt(cipher_text.encode())
    return decrypted.decode()

# ALIYUN_ACCESS_KEY_ID      = "LTAI5tS5Ko53xegPWVAqMkEo"
# ALIYUN_ACCESS_KEY_SECRET  = "3vwo9wBBjpEckPng40NbznusMigl6j"
# ALIYUN_SMS_SIGN_NAME      = "北京玛斯特天达系统工程"
# ALIYUN_SMS_TEMPLATE_CODE  = "SMS_324517197"
#
# a = encrypt_string(ALIYUN_ACCESS_KEY_ID)
# print(a)
# b = encrypt_string(ALIYUN_ACCESS_KEY_SECRET)
# print(b)
# c = encrypt_string(ALIYUN_SMS_SIGN_NAME)
# print(c)
# d = encrypt_string(ALIYUN_SMS_TEMPLATE_CODE)
# print(d)
#

