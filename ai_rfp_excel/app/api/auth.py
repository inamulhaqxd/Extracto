import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.auth_utils import (
    create_access_token,
    hash_password,
    verify_password,
)
from ai_rfp_excel.app.api.deps import get_current_user, require_admin
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where((User.email == request.email) | (User.username == request.username)))
    existing: User | None = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists",
        )

    count_result = await db.execute(select(func.count(User.id)))
    user_count: int | None = count_result.scalar()
    is_admin: bool = user_count == 0

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        is_admin=is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token: str = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    identifier = request.email or request.username
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email or username is required",
        )

    result = await db.execute(select(User).where((User.email == identifier) | (User.username == identifier)))
    user: User | None = result.scalars().first()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token: str = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)) -> MessageResponse:
    return MessageResponse(message="Successfully logged out")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        user_uuid = uuid.UUID(request.user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = hash_password(request.new_password)
    db.add(user)
    await db.commit()

    return MessageResponse(message=f"Password reset for user {user.username}")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
    )
