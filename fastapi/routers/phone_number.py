# routers/sms_auth.py  — async-ready drop-in for your uploaded file

import os, time, json, asyncio, random, string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from jose import jwt

import redis.asyncio as redis
# ---- Aliyun SMS SDK (sync; we'll offload to thread) ----
from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
from alibabacloud_dysmsapi20170525 import models as sms_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from key.apikey_vault import APIKeyVault
router = APIRouter(prefix="/api")
APIKeyVault = APIKeyVault()
# -------- Settings (use env-vars; fail fast if missing) ----------

ALIYUN_ACCESS_KEY_ID     = APIKeyVault.get_key("ALIYUN_ACCESS_KEY_ID")
ALIYUN_ACCESS_KEY_SECRET = APIKeyVault.get_key("ALIYUN_ACCESS_KEY_SECRET")
ALIYUN_SMS_SIGN_NAME     = APIKeyVault.get_key("ALIYUN_SMS_SIGN_NAME")
ALIYUN_SMS_TEMPLATE_CODE = APIKeyVault.get_key("ALIYUN_SMS_TEMPLATE_CODE")

# ALIYUN_ACCESS_KEY_ID      = "LTAI5tS5Ko53xegPWVAqMkEo"
# ALIYUN_ACCESS_KEY_SECRET  = "3vwo9wBBjpEckPng40NbznusMigl6j"
# ALIYUN_SMS_SIGN_NAME      = "北京玛斯特天达系统工程"
# ALIYUN_SMS_TEMPLATE_CODE  = "SMS_324517197"

# JWT_SECRET  = os.getenv("JWT_SECRET", "change-me")
# JWT_ISS     = os.getenv("JWT_ISS", "my-app")
# JWT_AUD     = os.getenv("JWT_AUDIENCE", "my-users")
# JWT_EXPIRE  = int(os.getenv("JWT_EXPIRE_MIN", "15"))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

r = redis.from_url(REDIS_URL, decode_responses=True)

def _aliyun_client() -> DysmsapiClient:
    if not (ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET and ALIYUN_SMS_SIGN_NAME and ALIYUN_SMS_TEMPLATE_CODE):
        raise HTTPException(500, detail="Aliyun SMS not configured; set ALIYUN_* env vars.")
    cfg = open_api_models.Config(
        access_key_id=ALIYUN_ACCESS_KEY_ID,
        access_key_secret=ALIYUN_ACCESS_KEY_SECRET,
    )
    cfg.endpoint = "dysmsapi.aliyuncs.com"
    return DysmsapiClient(cfg)

# Cache a client instance
ALIYUN_CLIENT = None

# --------- Fake DB (placeholder) -----------
# FAKE_USERS: dict[str, dict] = {}  # phone -> dict

# --------- Schemas ----------
class SendCodeIn(BaseModel):
    phone: str = Field(..., description="E.164 or CN format, e.g. +8613711112222 or 13711112222")

class VerifyCodeIn(BaseModel):
    phone: str
    code: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int

# ---------- Helpers ----------
def _norm_cn_phone(phone: str) -> str:
    p = phone.strip().replace(" ", "")
    if p.startswith("+"):
        return p
    if len(p) == 11 and p.isdigit():
        return "+86" + p
    raise HTTPException(422, detail="Invalid phone format")

def _gen_code(n=6) -> str:
    return "".join(random.choices(string.digits, k=n))

def _jwt_issue(subject: str) -> TokenOut:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE)
    payload = {
        "sub": subject,
        "iss": JWT_ISS,
        "aud": JWT_AUD,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "scope": "user",
    }
    tok = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return TokenOut(access_token=tok, expires_in=JWT_EXPIRE * 60)

def _rate_key(phone: str) -> str:
    return f"sms:rate:{phone}"

def _code_key(phone: str) -> str:
    return f"sms:code:{phone}"

# ---------- Endpoints (async) ----------
@router.post("/auth/send_code")
async def send_code(body: SendCodeIn):
    """
    Step 1: create + send OTP; rate limit by phone. (fully async)
    """
    global ALIYUN_CLIENT
    phone = _norm_cn_phone(body.phone)

    # Simple rate limit: allow 1 SMS / 60s, max 5 per rolling hour
    if await r.exists(_rate_key(phone)):
        ttl = await r.ttl(_rate_key(phone))
        raise HTTPException(429, detail=f"Too many requests. Retry in {max(ttl,0)}s.")

    hourly_key = f"sms:hourly:{phone}:{int(time.time()//3600)}"
    count = await r.incr(hourly_key)
    if count == 1:
        await r.expire(hourly_key, 3600)
    if count > 5:
        raise HTTPException(429, detail="Too many SMS today. Try later.")

    code = _gen_code(6)
    # Store with 5-minute TTL; mark single-use
    await r.setex(_code_key(phone), 300, code)
    # Set 60-sec cooldown
    await r.setex(_rate_key(phone), 60, "1")

    # Build / send Aliyun request (offloaded to thread to avoid blocking)
    params = {"code": code}
    try:
        if ALIYUN_CLIENT is None:
            ALIYUN_CLIENT = _aliyun_client()
        req = sms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=ALIYUN_SMS_SIGN_NAME,
            template_code=ALIYUN_SMS_TEMPLATE_CODE,
            template_param=json.dumps(params, ensure_ascii=False),
        )
        runtime = util_models.RuntimeOptions()
        resp = await asyncio.to_thread(ALIYUN_CLIENT.send_sms_with_options, req, runtime)
        if getattr(resp.body, "code", None) != "OK":
            await r.delete(_code_key(phone))  # clear dangling code
            raise HTTPException(502, detail=f"Aliyun error: {resp.body.code} - {resp.body.message}")
    except HTTPException:
        raise
    except Exception as e:
        await r.delete(_code_key(phone))
        raise HTTPException(502, detail=f"SMS provider failure: {e}")

    return {"ok": True, "cooldown_seconds": 60}

# @router.post("/auth/verify_code", response_model=TokenOut)
def verify_code(phone: str, code: str):
    """
    Step 2: verify OTP; create/fetch user; issue JWT. (fully async)
    """
    phone = _norm_cn_phone(phone)
    key = _code_key(phone)
    saved = r.get(key)
    if not saved or saved != code:
        raise HTTPException(400, detail="Invalid or expired code")

    # Invalidate code (single-use)
    r.delete(key)
    return "verified"
    # Upsert user (placeholder logic)
    # user = FAKE_USERS.get(phone)
    # if not user:
    #     user = {"phone": phone, "created_at": time.time()}
    #     FAKE_USERS[phone] = user

    # Issue JWT (subject = phone or your internal user_id)
    # return _jwt_issue(subject=phone)
