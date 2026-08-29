---
title: Docker FastAPI and Streamlit Integration Patterns
date: 2026-08-29
work_type: bugfix
tags: [fastapi, streamlit, docker, authentication, bcrypt, asyncpg]
confidence: high
references:
  - ai_rfp_excel/app/api/auth.py
  - ai_rfp_excel/app/api/auth_utils.py
  - ai_rfp_excel/frontend/api_client.py
  - ai_rfp_excel/frontend/pages/1_Upload.py
  - ai_rfp_excel/frontend/pages/3_Review.py
  - ai_rfp_excel/app/database/connection.py
---

## Summary

This note documents critical integration patterns and troubleshooting insights across a containerized FastAPI backend and Streamlit frontend stack, covering secure file downloads, authentication compatibility, async database pooling, and API client type safety.

## Reusable Insights

### 1. Docker Container Networking vs. Host Browser DNS
- **Pitfall**: Rendering direct HTML links `<a href="http://api:8000/excel/download/...">` in Streamlit causes `"this site can't be reached"` on host browsers because `api` is an internal Docker bridge DNS name unknown to host operating systems. It also fails to attach required JWT Authorization headers.
- **Pattern**: Use Streamlit's native `st.download_button()` by downloading file bytes server-side in Python (`APIClient.download_file()`) with internal JWT headers, then streaming the bytes directly to the browser through the active Streamlit WebSocket/HTTP session.

```python
# In Streamlit page:
file_bytes = client.download_file(filename)
if file_bytes:
    st.download_button(
        label="📥 Download File",
        data=file_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
```

### 2. Modern Password Hashing with Direct `bcrypt`
- **Pitfall**: `passlib.context.CryptContext` with `bcrypt >= 4.1.0` triggers `AttributeError: module 'bcrypt' has no attribute '__about__'` and crashes on password verification due to unmaintained passlib introspection.
- **Pattern**: Use standard `bcrypt` directly for password hashing and verification:

```python
import bcrypt

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False
```

### 3. Dual-Identifier Authentication Compatibility
- **Pattern**: Allow `email` and `username` interchangeably in the Pydantic login contract and database query to prevent login schema mismatches between UI input fields and backend routes:

```python
class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str

# Query matching either identifier:
identifier = request.email or request.username
result = await db.execute(
    select(User).where((User.email == identifier) | (User.username == identifier))
)
```

### 4. SQLAlchemy 2.0 Async Testing with `NullPool`
- **Pitfall**: When running async pytest suites against PostgreSQL with `asyncpg`, module-level pooled engines retain connection states across distinct test event loops, causing `InterfaceError: cannot perform operation: another operation is in progress`.
- **Pattern**: Configure `create_async_engine` with `poolclass=NullPool` to guarantee each session manages its own dedicated connection lifecycle.

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG,
)
```

### 5. Type-Safe Client Deserialization and Normalization
- **Pattern**: When API endpoints return wrapped dictionary responses (`{"models": [...]}`), normalize dictionary keys in the API client and use `typing.cast` so that downstream Streamlit page components never encounter `TypeError: string indices must be integers` when iterating, and strict `mypy`/`pyright` type checks pass without warnings.

## Validation Strategy
- Ran `python -m ruff check ai_rfp_excel/app ai_rfp_excel/frontend --ignore E501` (Clean)
- Ran `python -m mypy ai_rfp_excel/app ai_rfp_excel/frontend --ignore-missing-imports --explicit-package-bases` (Clean across 69 files)
- Rebuilt containers and verified authenticated login, model catalog dropdowns, and Excel spreadsheet downloads via HTTP 200 responses.
