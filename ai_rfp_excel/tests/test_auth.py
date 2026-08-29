from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from ai_rfp_excel.app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_first_user_becomes_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={
            "username": "admin",
            "email": "admin@test.com",
            "password": "admin123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["is_admin"] is True
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_second_user_is_not_admin(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    response = await client.post(
        "/auth/register",
        json={"username": "user1", "email": "user1@test.com", "password": "user123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    response = await client.post(
        "/auth/register",
        json={"username": "admin2", "email": "admin@test.com", "password": "pass123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_fails(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@test.com", "password": "pass123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient) -> None:
    reg = await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    token = reg.json()["access_token"]
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    reg = await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    token = reg.json()["access_token"]
    response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_by_admin(client: AsyncClient) -> None:
    reg = await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]

    response = await client.post(
        "/auth/reset-password",
        json={"user_id": user_id, "new_password": "newpass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    login_resp = await client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "newpass123"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_non_admin_fails(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "admin", "email": "admin@test.com", "password": "admin123"},
    )
    user_reg = await client.post(
        "/auth/register",
        json={"username": "user1", "email": "user1@test.com", "password": "user123"},
    )
    user_token = user_reg.json()["access_token"]
    await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    response = await client.post(
        "/auth/reset-password",
        json={"user_id": "some-id", "new_password": "newpass"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
