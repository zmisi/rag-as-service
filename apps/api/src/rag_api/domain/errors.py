"""Domain validation errors (no I/O)."""


class DomainValidationError(Exception):
    """Base class for domain validation failures."""

    code: str

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class SubdomainValidationError(DomainValidationError):
    pass


class EmailValidationError(DomainValidationError):
    pass


class PasswordValidationError(DomainValidationError):
    pass
