import hashlib
import secrets


def generate_session_token() -> str:
    """Create a URL-safe random token for a new browser session."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest stored for session lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
