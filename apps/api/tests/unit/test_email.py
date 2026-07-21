import pytest

from rag_api.domain.errors import EmailValidationError
from rag_api.domain.identity.email import normalize_email


def test_normalize_email_lowercase():
    assert normalize_email("User@Example.COM") == "user@example.com"


def test_normalize_email_strips_whitespace():
    assert normalize_email("  user@example.com  ") == "user@example.com"


def test_normalize_email_rejects_missing_at():
    with pytest.raises(EmailValidationError) as exc:
        normalize_email("not-an-email")
    assert exc.value.code == "invalid_format"


def test_normalize_email_rejects_empty():
    with pytest.raises(EmailValidationError) as exc:
        normalize_email("   ")
    assert exc.value.code == "invalid_format"
