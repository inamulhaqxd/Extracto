from datetime import datetime, timedelta, timezone
from typing import TypeAlias

import bcrypt
from jose import JWTError, jwt

from ai_rfp_excel.app.config import settings

ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

TokenPayload: TypeAlias = dict[str, str | datetime]


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
    to_encode: TokenPayload = {**data, "exp": expire}
    encoded: str = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded


def decode_access_token(token: str) -> dict[str, str] | None:
    try:
        payload: TokenPayload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return {k: str(v) for k, v in payload.items() if k != "exp"}
    except JWTError:
        return None
