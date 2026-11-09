"""
SYNQ Core Security Utilities.

Provides:
- Cryptographic password hashing & constant-time verification using PBKDF2-HMAC-SHA256.
- JWT access token generation & signature verification.
- Secure API key generation and hashing for automated agent access.
- Strict input sanitization for XSS prevention.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import html
import re
import secrets
from typing import Any, Dict, Optional

from config import get_settings
from jose import JWTError, jwt

settings = get_settings()

# NIST / OWASP recommended PBKDF2-HMAC-SHA256 iterations
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 32

# Common XSS attack vectors
XSS_PATTERNS = [
    re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*object[^>]*>.*?<\s*/\s*object\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*embed[^>]*>.*?<\s*/\s*embed\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*style[^>]*>.*?<\s*/\s*style\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"on[a-z]+\s*=", re.IGNORECASE),  # onload=, onerror=, onclick=
]


# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Hash a password securely using PBKDF2-HMAC-SHA256 with 600,000 iterations.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against stored hash using constant-time comparison to prevent timing attacks.
    """
    if not plain_password or not hashed_password:
        return False

    parts = hashed_password.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])

        candidate_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(expected_hash, candidate_hash)
    except Exception:
        return False


# ── JWT Tokens ───────────────────────────────────────────────────────────────

def get_signing_secret() -> str:
    """Resolve secret key, avoiding known default placeholders in production."""
    secret = settings.secret_key
    if not secret or secret in ("change-me-in-production", "synq-dev-secret-change-in-production"):
        if settings.is_production:
            raise RuntimeError(
                "SECRET_KEY is using an insecure default in production. "
                "Set a strong SECRET_KEY in your environment variables."
            )
        return "synq-dev-internal-secret-key-32bytes-secure!"
    return secret


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"iat": now, "exp": expire})
    secret = get_signing_secret()
    return jwt.encode(to_encode, secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a signed JWT access token."""
    try:
        secret = get_signing_secret()
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


# ── API Keys ─────────────────────────────────────────────────────────────────

def generate_api_key() -> str:
    """Generate a high-entropy API key for machine-to-machine / agent authentication."""
    token = secrets.token_urlsafe(32)
    return f"synq_live_{token}"


def hash_api_key(api_key: str) -> str:
    """Store SHA-256 hash of API key in database (never store raw keys)."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


# ── Input Sanitization & XSS Prevention ─────────────────────────────────────

def sanitize_text(text: Optional[str], max_length: int = 5000) -> Optional[str]:
    """
    Sanitize text input:
    - Neutralize dangerous HTML tags, javascript: URIs, and inline event handlers (onerror=, onload=).
    - Strip ASCII control characters and null bytes.
    - Trim excessive whitespace and cap maximum length.
    - Preserves safe markdown, punctuation, and code snippets.
    """
    if text is None:
        return None

    # Remove null bytes and dangerous control characters (except newline, tab, carriage return)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Neutralize active XSS script blocks and event handlers
    for pattern in XSS_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Escape raw angle brackets around potential standalone tags, but preserve normal characters
    cleaned = re.sub(r"<(?![a-zA-Z0-9_\-/\s])", "&lt;", cleaned)

    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


def sanitize_filename_or_id(val: str, max_length: int = 120) -> str:
    """Sanitize identifier or file label against traversal and injection."""
    if not val:
        return "unnamed"
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", val.strip())
    cleaned = re.sub(r"\.\.+", ".", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned[:max_length] or "unnamed"
