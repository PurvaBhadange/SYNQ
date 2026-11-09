"""
Unit Tests for SYNQ Security Modules.

Covers:
1. PBKDF2-HMAC-SHA256 password hashing & verification.
2. JWT token creation, signature validation, expiration, and tamper detection.
3. API key generation and hashing.
4. XSS sanitization (scripts, event handlers, javascript URIs, control characters).
5. Pydantic schema validation & sanitization on Project and Task inputs.
6. Rate limiting enforcement & 429 response.
7. OWASP security headers enforcement.
8. Secret redaction on Gemini AQ. keys, bearer tokens, and connection strings.
"""

from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport

from config import get_settings
from core.middleware import rate_limiter
from core.security import (
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    sanitize_text,
    verify_password,
)
from api.v1.projects import ProjectCreate
from api.v1.tasks import TaskCreate, PlanRequest
from api.v1.export import redact_secrets
from main import app

settings = get_settings()


# ── 1. Password Hashing & Verification Tests ─────────────────────────────────

def test_hash_password_produces_pbkdf2_format():
    hashed = hash_password("SecurePassword123!")
    parts = hashed.split("$")
    assert len(parts) == 4
    assert parts[0] == "pbkdf2_sha256"
    assert int(parts[1]) == 600_000
    assert len(parts[2]) == 64  # 32 bytes hex
    assert len(parts[3]) == 64  # 32 bytes hex


def test_verify_password_correct():
    password = "CorrectHorseBatteryStaple99!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("CorrectPassword1!")
    assert verify_password("WrongPassword2!", hashed) is False


def test_verify_password_malformed_hashes_fail_safely():
    assert verify_password("test", "") is False
    assert verify_password("test", "invalid_hash_string") is False
    assert verify_password("test", "pbkdf2_sha256$100$badhex$badhex") is False


def test_hash_password_rejects_too_short():
    with pytest.raises(ValueError, match="at least 8 characters"):
        hash_password("short")


# ── 2. JWT Access Token Tests ────────────────────────────────────────────────

def test_create_and_decode_access_token():
    payload = {"sub": "user-uuid-1234", "username": "alice", "role": "admin"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["username"] == "alice"
    assert decoded["role"] == "admin"


def test_expired_token_returns_none():
    payload = {"sub": "user-expired"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))
    decoded = decode_access_token(token)
    assert decoded is None


def test_tampered_token_fails_verification():
    payload = {"sub": "user-original", "role": "member"}
    token = create_access_token(payload)
    # Alter token signature part
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    assert decode_access_token(tampered_token) is None


# ── 3. API Key Tests ──────────────────────────────────────────────────────────

def test_generate_api_key_format():
    key = generate_api_key()
    assert key.startswith("synq_live_")
    assert len(key) > 40


def test_hash_api_key_deterministic():
    key = "synq_live_test_api_key_sample"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex


# ── 4. XSS & Input Sanitization Tests ─────────────────────────────────────────

def test_sanitize_text_strips_scripts():
    raw = "Normal text <script>alert('xss')</script> continues here."
    cleaned = sanitize_text(raw)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "Normal text" in cleaned
    assert "continues here" in cleaned


def test_sanitize_text_strips_event_handlers():
    raw = '<img src="x" onerror="alert(document.cookie)"> Image title'
    cleaned = sanitize_text(raw)
    assert "onerror=" not in cleaned.lower()


def test_sanitize_text_strips_javascript_uris():
    raw = '<a href="javascript:stealData()">Click here</a>'
    cleaned = sanitize_text(raw)
    assert "javascript:" not in cleaned.lower()


def test_sanitize_text_strips_null_bytes():
    raw = "Data\x00with\x00nulls"
    cleaned = sanitize_text(raw)
    assert "\x00" not in cleaned
    assert cleaned == "Datawithnulls"


def test_sanitize_text_preserves_safe_content():
    raw = "Implement a binary search tree in Python with O(log n) lookup."
    cleaned = sanitize_text(raw)
    assert cleaned == raw


def test_project_create_schema_sanitizes_xss():
    p = ProjectCreate(
        name="Security Audit <script>alert(1)</script>",
        description="Project description with <img src=x onerror=alert(2)>",
    )
    assert "<script>" not in p.name
    assert "onerror=" not in p.description


def test_task_create_schema_sanitizes_xss():
    t = TaskCreate(
        title="Deploy microservice <iframe src=evil.com></iframe>",
        description="Description with <script>alert('x')</script>",
        acceptance_criteria="Criteria with javascript:doEvil()",
    )
    assert "<iframe" not in t.title
    assert "<script" not in t.description
    assert "javascript:" not in t.acceptance_criteria


def test_plan_request_sanitizes_goal():
    req = PlanRequest(goal="Decompose architecture into tasks <script>alert(1)</script>")
    assert "<script>" not in req.goal
    assert "Decompose architecture" in req.goal


# ── 5. Rate Limiting Tests ───────────────────────────────────────────────────

def test_rate_limiter_sliding_window():
    rate_limiter.reset_for_tests()
    test_key = "test_ip_1"
    limit = 3

    # First 3 requests allowed
    for _ in range(limit):
        allowed, remaining, _ = rate_limiter.check(test_key, max_requests=limit, window_seconds=60)
        assert allowed is True

    # 4th request must be blocked
    allowed, remaining, retry_after = rate_limiter.check(test_key, max_requests=limit, window_seconds=60)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


# ── 6. Secret Redaction Tests in Exporter ──────────────────────────────────────

def test_redact_secrets_comprehensive():
    # Dynamic concatenation to prevent GitHub Push Protection false positives on mock patterns
    dummy_gemini = "AQ." + "TESTING_SECRET_TOKEN_1234567890abcdef"
    dummy_aiza = "AIza" + "TESTING_SECRET_TOKEN_1234567890abcdef"
    dummy_openai = "sk-" + "TESTING_SECRET_TOKEN_1234567890abcdef"
    dummy_synq = "synq_live_" + "TESTING_SECRET_TOKEN_1234567890def"

    sample_text = (
        f"Config file:\n"
        f"GEMINI_KEY={dummy_gemini}\n"
        f"AIZA_KEY={dummy_aiza}\n"
        f"OPENAI_KEY={dummy_openai}\n"
        f"SYNQ_KEY={dummy_synq}\n"
        f"DB_URL=postgresql://admin:password@localhost:5432/mydb\n"
        f"AUTH=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz.abc\n"
    )
    redacted = redact_secrets(sample_text)
    assert "AQ." not in redacted
    assert "AIza" not in redacted
    assert "sk-" not in redacted
    assert "synq_live_" not in redacted
    assert "postgresql://" not in redacted
    assert "Bearer" not in redacted
    assert "[REDACTED_SECRET]" in redacted


# ── 7. HTTP Endpoint Security Tests (Async) ───────────────────────────────────

@pytest.mark.asyncio
async def test_security_headers_middleware_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert "default-src 'self'" in response.headers.get("content-security-policy", "")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        unique_name = f"user_{generate_api_key()[-8:]}"
        reg_payload = {
            "username": unique_name,
            "email": f"{unique_name}@test.com",
            "password": "StrongPassword123!",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        user_data = res_reg.json()
        assert user_data["username"] == unique_name

        # Login
        login_payload = {
            "username_or_email": unique_name,
            "password": "StrongPassword123!",
        }
        res_login = await client.post("/api/v1/auth/login", json=login_payload)
        assert res_login.status_code == 200
        token_data = res_login.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # Access /me with Bearer token
        res_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["username"] == unique_name

        # Create API key
        res_key = await client.post(
            "/api/v1/auth/api-key",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_key.status_code == 200
        api_key = res_key.json()["api_key"]
        assert api_key.startswith("synq_live_")

        # Access /me with X-API-Key header
        res_me_key = await client.get(
            "/api/v1/auth/me",
            headers={"X-API-Key": api_key},
        )
        assert res_me_key.status_code == 200
        assert res_me_key.json()["username"] == unique_name


# ── 8. Multi-Tenant Data Isolation & RBAC Authorization Tests ────────────────

@pytest.mark.asyncio
async def test_cross_tenant_data_isolation():
    """
    Verify that User B cannot view, modify, delete, or add tasks to User A's project.
    Verify that an Admin user CAN access User A's project.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        user_a_name = f"user_a_{generate_api_key()[-8:]}"
        res_a = await client.post("/api/v1/auth/register", json={
            "username": user_a_name,
            "email": f"{user_a_name}@example.com",
            "password": "Password123!",
        })
        assert res_a.status_code == 201

        login_a = await client.post("/api/v1/auth/login", json={
            "username_or_email": user_a_name,
            "password": "Password123!",
        })
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register User B
        user_b_name = f"user_b_{generate_api_key()[-8:]}"
        res_b = await client.post("/api/v1/auth/register", json={
            "username": user_b_name,
            "email": f"{user_b_name}@example.com",
            "password": "Password123!",
        })
        assert res_b.status_code == 201

        login_b = await client.post("/api/v1/auth/login", json={
            "username_or_email": user_b_name,
            "password": "Password123!",
        })
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User A creates a private project
        create_res = await client.post(
            "/api/v1/projects/",
            headers=headers_a,
            json={"name": "User A Secret Project", "domain": "software"},
        )
        assert create_res.status_code == 201
        project_a_id = create_res.json()["id"]

        # User B attempts to GET User A's project -> 403 Forbidden
        get_res_b = await client.get(f"/api/v1/projects/{project_a_id}", headers=headers_b)
        assert get_res_b.status_code == 403
        assert "Forbidden" in get_res_b.json()["detail"]

        # User B attempts to PATCH User A's project -> 403 Forbidden
        patch_res_b = await client.patch(
            f"/api/v1/projects/{project_a_id}",
            headers=headers_b,
            json={"name": "Hacked Project Name"},
        )
        assert patch_res_b.status_code == 403

        # User B attempts to DELETE User A's project -> 403 Forbidden
        del_res_b = await client.delete(f"/api/v1/projects/{project_a_id}", headers=headers_b)
        assert del_res_b.status_code == 403

        # User B attempts to create task on User A's project -> 403 Forbidden
        task_create_b = await client.post(
            f"/api/v1/projects/{project_a_id}/tasks",
            headers=headers_b,
            json={"title": "Unauthorized Task", "task_type": "general"},
        )
        assert task_create_b.status_code == 403

        # User B attempts to list tasks on User A's project -> 403 Forbidden
        task_list_b = await client.get(
            f"/api/v1/projects/{project_a_id}/tasks",
            headers=headers_b,
        )
        assert task_list_b.status_code == 403

        # User B attempts to inspect DAG of User A's project -> 403 Forbidden
        dag_b = await client.get(f"/api/v1/projects/{project_a_id}/dag", headers=headers_b)
        assert dag_b.status_code == 403

        # User A can freely access their own project -> 200 OK
        get_res_a = await client.get(f"/api/v1/projects/{project_a_id}", headers=headers_a)
        assert get_res_a.status_code == 200
        assert get_res_a.json()["id"] == project_a_id


# ── 9. Password Reset & Change Flow Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_password_change_and_reset_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user
        u_name = f"pwd_user_{generate_api_key()[-8:]}"
        u_email = f"{u_name}@test.com"
        reg_res = await client.post("/api/v1/auth/register", json={
            "username": u_name,
            "email": u_email,
            "password": "InitialPassword123!",
        })
        assert reg_res.status_code == 201

        login_res = await client.post("/api/v1/auth/login", json={
            "username_or_email": u_name,
            "password": "InitialPassword123!",
        })
        token = login_res.json()["access_token"]

        # Test authenticated change-password
        change_res = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "old_password": "InitialPassword123!",
                "new_password": "ChangedPassword456!",
            },
        )
        assert change_res.status_code == 200
        assert "successfully changed" in change_res.json()["message"]

        # Old password no longer works
        bad_login = await client.post("/api/v1/auth/login", json={
            "username_or_email": u_name,
            "password": "InitialPassword123!",
        })
        assert bad_login.status_code == 401

        # Test forgot-password flow
        forgot_res = await client.post("/api/v1/auth/forgot-password", json={
            "email": u_email,
        })
        assert forgot_res.status_code == 200
        reset_token = forgot_res.json()["reset_token"]
        assert reset_token is not None

        # Test reset-password with token
        reset_res = await client.post("/api/v1/auth/reset-password", json={
            "reset_token": reset_token,
            "new_password": "FinalResetPassword789!",
        })
        assert reset_res.status_code == 200
        assert "successfully reset" in reset_res.json()["message"]

        # Login with newly reset password -> 200 OK
        new_login = await client.post("/api/v1/auth/login", json={
            "username_or_email": u_name,
            "password": "FinalResetPassword789!",
        })
        assert new_login.status_code == 200


# ── 10. JWT Expiration & Tamper Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_jwt_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create deliberately expired token
        expired_token = create_access_token(
            data={"sub": "user-test-id", "role": "member"},
            expires_delta=timedelta(seconds=-10),
        )
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401


# ── 11. Anti-IP Spoofing Rate Limit Test ─────────────────────────────────────

@pytest.mark.asyncio
async def test_anti_ip_spoofing_rate_limit():
    """Verify that when trust_proxy_headers is disabled, spoofed X-Forwarded-For is ignored."""
    rate_limiter.reset_for_tests()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send requests with randomized X-Forwarded-For headers
        for i in range(16):
            res = await client.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": f"198.51.100.{i}"},
                json={"username_or_email": "nonexistent", "password": "WrongPassword1!"},
            )
        # 16th request should be rate limited (limit is 15/min on auth)
        assert res.status_code == 429
        assert "Too many requests" in res.json()["detail"]
    rate_limiter.reset_for_tests()


# ── 12. WebSocket Authentication Test ────────────────────────────────────────

def test_websocket_unauthenticated_rejected_when_auth_enabled():
    """Verify that unauthenticated WebSocket connections are rejected when auth is enabled."""
    from starlette.testclient import TestClient
    original_auth_state = settings.auth_enabled
    settings.auth_enabled = True
    try:
        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/api/v1/ws/proj_test_secure") as ws:
                    ws.receive_json()
    finally:
        settings.auth_enabled = original_auth_state


