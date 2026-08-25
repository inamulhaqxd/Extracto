import pytest
from app.api.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_password_hash_uniqueness():
    password = "testpassword123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    assert hash1 != hash2


def test_jwt_token():
    data = {"sub": "user123"}
    token = create_access_token(data)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user123"


def test_jwt_token_invalid():
    decoded = decode_access_token("invalidtoken")
    assert decoded is None


def test_jwt_token_expired():
    from datetime import timedelta
    from app.api.auth import create_access_token, decode_access_token

    data = {"sub": "user123"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))

    decoded = decode_access_token(token)
    assert decoded is None
