import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import TypeAlias

import bcrypt

from ai_rfp_excel.app.config import settings

ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

TokenPayload: TypeAlias = dict[str, str | datetime]


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict[str, str], expires_delta: timedelta | None = None) -> str:
    expire: datetime = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {**data, "exp": int(expire.timestamp())}
    header = {"alg": "HS256", "typ": "JWT"}

    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}"
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    s_b64 = _b64url_encode(sig)
    return f"{msg}.{s_b64}"


def decode_access_token(token: str) -> dict[str, str] | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, s_b64 = parts
        msg = f"{h_b64}.{p_b64}"
        expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = _b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp and int(datetime.now(timezone.utc).timestamp()) > exp:
            return None
        return {k: str(v) for k, v in payload.items() if k != "exp"}
    except Exception:
        return None
