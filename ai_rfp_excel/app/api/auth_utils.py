from datetime import datetime, timedelta, timezone
from typing import TypeAlias

from jose import JWTError, jwt
from passlib.context import CryptContext

from ai_rfp_excel.app.config import settings

pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

TokenPayload: TypeAlias = dict[str, str | datetime]


def hash_password(password: str) -> str:
    hashed: str = pwd_context.hash(password)
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    result: bool = pwd_context.verify(plain_password, hashed_password)
    return result


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
