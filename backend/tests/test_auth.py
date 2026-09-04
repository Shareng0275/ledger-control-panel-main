from datetime import timedelta
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, hash_password, verify_password


@pytest.mark.asyncio
async def test_password_hashing_security():
    """Verify Argon2 hashing produces secure hashes and verifies correctly."""
    plain = "SuperSecretPassword123!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert hashed.startswith("$argon2")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient):
    """Test user registration returns token pair and creates admin organization."""
    payload = {
        "email": "finance.lead@acme.com",
        "password": "SecurePassword123!",
        "full_name": "Finance Lead",
        "organization_name": "ACME Holdings",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(async_client: AsyncClient):
    """Test registering with an existing email returns 400."""
    payload = {
        "email": "duplicate@acme.com",
        "password": "SecurePassword123!",
        "full_name": "User One",
    }
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_login_flow(async_client: AsyncClient):
    """Test user login with valid and invalid credentials."""
    register_payload = {
        "email": "login.user@acme.com",
        "password": "CorrectPassword123!",
        "full_name": "Login User",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert reg_res.status_code == 201

    # Valid Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "login.user@acme.com", "password": "CorrectPassword123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Invalid Password
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "login.user@acme.com", "password": "WrongPassword123!"},
    )
    assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_get_me_profile(async_client: AsyncClient):
    """Test GET /api/v1/auth/me returns profile and organization memberships."""
    payload = {
        "email": "me.user@acme.com",
        "password": "SecurePassword123!",
        "full_name": "Profile User",
        "organization_name": "Global Corp",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=payload)
    token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["email"] == "me.user@acme.com"
    assert user_info["full_name"] == "Profile User"
    assert user_info["is_active"] is True
    assert "password_hash" not in user_info
    assert len(user_info["memberships"]) == 1
    assert user_info["memberships"][0]["organization_name"] == "Global Corp"
    assert user_info["memberships"][0]["role"] == "admin"


@pytest.mark.asyncio
async def test_refresh_token_rotation(async_client: AsyncClient):
    """Test that refresh token rotation provides new tokens and invalidates the old one."""
    payload = {
        "email": "rotate.user@acme.com",
        "password": "SecurePassword123!",
        "full_name": "Rotation User",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=payload)
    old_refresh_token = reg_res.json()["refresh_token"]

    # Rotate Refresh Token
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    new_refresh_token = new_tokens["refresh_token"]
    assert new_refresh_token != old_refresh_token

    # Attempting to use old refresh token again must fail (revoked / reuse detection)
    reuse_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert reuse_res.status_code == 401

    # New refresh token works
    second_refresh = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    assert second_refresh.status_code == 200


@pytest.mark.asyncio
async def test_logout_revocation(async_client: AsyncClient):
    """Test logout invalidates the active refresh token."""
    payload = {
        "email": "logout.user@acme.com",
        "password": "SecurePassword123!",
        "full_name": "Logout User",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=payload)
    refresh_token = reg_res.json()["refresh_token"]

    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # Refresh after logout should fail
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(async_client: AsyncClient):
    """Test expired access token is rejected with 401."""
    import uuid
    expired_token = create_access_token(
        user_id=uuid.uuid4(),
        expires_delta=timedelta(seconds=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
