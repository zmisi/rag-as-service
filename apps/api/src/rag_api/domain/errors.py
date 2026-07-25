"""Domain validation errors (no I/O)."""


class DomainValidationError(Exception):
    """Base class for domain validation failures."""

    code: str

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class SubdomainValidationError(DomainValidationError):
    """Tenant subdomain (``tenant_name``) failed format or reserved-name checks."""


class EmailValidationError(DomainValidationError):
    """Email address failed domain validation rules."""


class PasswordValidationError(DomainValidationError):
    """Password failed domain validation rules."""
