from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from rag_api.domain.errors import PasswordValidationError

MIN_PASSWORD_LENGTH = 8

_hasher = PasswordHasher()


def validate_password_length(password: str) -> None:
    """Raise ``PasswordValidationError`` when ``password`` is shorter than the minimum."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            "too_short",
            f"password must be at least {MIN_PASSWORD_LENGTH} characters",
        )


def hash_password(password: str) -> str:
    """Validate length and return an Argon2 hash suitable for storage."""
    validate_password_length(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether ``password`` matches the stored Argon2 hash."""
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False
