# routers/sms_auth.py  — async-ready drop-in for your uploaded file

import os, time, json, asyncio, random, string
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
import models
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from jose import jwt
from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis
# ---- Aliyun SMS SDK (sync; we'll offload to thread) ----
from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
from alibabacloud_dysmsapi20170525 import models as sms_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from key.apikey_vault import APIKeyVault
from sqlalchemy.ext.asyncio import AsyncSession
from database import SessionLocal
from sqlalchemy import func, select
from functions.auth import (
    authenticate_user,
    register_user,
    change_number,
    recover_password,
    create_access_token,
    create_refresh_token,
    get_current_user,


)
from tools.logger import logger
async def get_db():
    async with SessionLocal() as session:
        yield session


router = APIRouter(prefix="/test")
APIKeyVault = APIKeyVault()

ALIYUN_ACCESS_KEY_ID     = APIKeyVault.get_key("ALIYUN_ACCESS_KEY_ID")
ALIYUN_ACCESS_KEY_SECRET = APIKeyVault.get_key("ALIYUN_ACCESS_KEY_SECRET")
ALIYUN_SMS_SIGN_NAME     = APIKeyVault.get_key("ALIYUN_SMS_SIGN_NAME")
ALIYUN_SMS_TEMPLATE_CODE = APIKeyVault.get_key("ALIYUN_SMS_TEMPLATE_CODE")
WechatID     = APIKeyVault.get_key("WechatID")
WechatSECRET = APIKeyVault.get_key("WechatSECRET")


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
    # if await r.exists(_rate_key(phone)):
    #     ttl = await r.ttl(_rate_key(phone))
    #     raise HTTPException(429, detail=f"Too many requests. Retry in {max(ttl,0)}s.")

    # hourly_key = f"sms:hourly:{phone}:{int(time.time()//3600)}"
    # count = await r.incr(hourly_key)
    # if count == 1:
    #     await r.expire(hourly_key, 3600)
    # if count > 5:
    #     raise HTTPException(429, detail="Too many SMS today. Try later.")

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


class VerifyCodeIn(BaseModel):
    phone: str
    code: str

# @router.post("/auth/verify_code", response_model=TokenOut)
# async def verify_code(phone: str, code: str):
#     """
#     Step 2: verify OTP; create/fetch user; issue JWT. (fully async)
#     """
#     print(phone)
#
#     phone = _norm_cn_phone(phone)
#     key = _code_key(phone)
#
#     saved = await r.get(key)
#     print(saved)
#     print(code)
#     if not saved:
#         raise HTTPException(400, detail="Invalid or expired code")
#
#     # Normalize both sides to str for safe comparison
#     if str(saved) != str(code):
#         raise HTTPException(400, detail="Invalid or expired code")
#
#     await r.delete(key)
#     return {"verified": True}
#
#
#
# @router.post("/auth/verify_code")
# async def verify_code2(body: VerifyCodeIn):
#     """
#     Step 2: verify OTP; create/fetch user; issue JWT. (fully async)
#     """
#     code = body.code
#     phone = _norm_cn_phone(body.phone)
#     key = _code_key(phone)
#
#     saved = await r.get(key)
#     print(str(saved))
#     print(str(code))
#     if not saved:
#         raise HTTPException(400, detail="code doesn't exist")
#
#     # Normalize both sides to str for safe comparison
#     if str(saved) != str(code):
#         raise HTTPException(400, detail="Invalid or expired code")
#
#     await r.delete(key)
#     return {"verified": True}
#
class WeChatLoginRequest(BaseModel):
    code: str

@router.post("/login/wechat")
async def wechat_login(payload: WeChatLoginRequest, db: AsyncSession = Depends(get_db)):
    url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": WechatID,
        "secret": WechatSECRET,
        "code": payload.code,
        "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "errcode" in data:
        raise HTTPException(400, data.get("errmsg"))

    openid = data["openid"]

    user = (
        await db.execute(select(models.User).where(models.User.openid == openid))
    ).scalars().first()
    if not user:
        user = models.User(
            membership=0,
            consecutive_learning=0,
            openid=openid,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        setting = models.Learning_setting(
            user_id=user.id,
            chosed_word_book_id=1,
        )
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
        access_token = create_access_token(user_id=user.id, role="user")
        refresh_token = create_refresh_token(user_id=user.id)
        return {"status": "register", "access_token": access_token, "refresh_token": refresh_token}
    else:
        access_token = create_access_token(user_id=user.id, role="user")
        refresh_token = create_refresh_token(user_id=user.id)
        logger.success(f"logintest 登录成功，user_id={user.id}, username={getattr(user, 'username', '<unknown>')}")
        return {"status": "login", "access_token": access_token, "refresh_token": refresh_token}
