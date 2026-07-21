import pytest

from rag_api.domain.errors import PasswordValidationError
from rag_api.domain.identity.password import (
    hash_password,
    validate_password_length,
    verify_password,
)


def test_validate_password_length_accepts_minimum():
    validate_password_length("12345678")


def test_validate_password_length_rejects_short():
    with pytest.raises(PasswordValidationError) as exc:
        validate_password_length("1234567")
    assert exc.value.code == "too_short"


def test_hash_password_returns_argon2_hash():
    hashed = hash_password("12345678")
    assert hashed.startswith("$argon2")


def test_hash_password_rejects_short():
    with pytest.raises(PasswordValidationError):
        hash_password("short")


def test_verify_password_matches():
    password = "secure-password"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_mismatch():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False
