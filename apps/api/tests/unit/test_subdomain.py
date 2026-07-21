import pytest

from rag_api.domain.errors import SubdomainValidationError
from rag_api.domain.tenancy.subdomain import normalize_subdomain, validate_subdomain


def test_normalize_subdomain_lowercase():
    assert normalize_subdomain("Acme-Co") == "acme-co"


def test_validate_subdomain_accepts_valid():
    assert validate_subdomain("acme-co") == "acme-co"
    assert validate_subdomain("Acme-Co") == "acme-co"
    assert validate_subdomain("a1b") == "a1b"


def test_validate_subdomain_rejects_too_short():
    with pytest.raises(SubdomainValidationError) as exc:
        validate_subdomain("ab")
    assert exc.value.code == "invalid_format"


def test_validate_subdomain_rejects_leading_hyphen():
    with pytest.raises(SubdomainValidationError) as exc:
        validate_subdomain("-acme")
    assert exc.value.code == "invalid_format"


def test_validate_subdomain_rejects_trailing_hyphen():
    with pytest.raises(SubdomainValidationError) as exc:
        validate_subdomain("acme-")
    assert exc.value.code == "invalid_format"


def test_validate_subdomain_rejects_uppercase_after_normalize_invalid_chars():
    with pytest.raises(SubdomainValidationError):
        validate_subdomain("acme_co")


@pytest.mark.parametrize(
    "reserved",
    ["www", "admin", "api", "app", "mail", "static", "cdn", "lxzxai"],
)
def test_validate_subdomain_rejects_reserved(reserved: str):
    with pytest.raises(SubdomainValidationError) as exc:
        validate_subdomain(reserved)
    assert exc.value.code == "reserved"
