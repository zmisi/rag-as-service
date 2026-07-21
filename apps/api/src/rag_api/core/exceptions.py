"""Application-level exceptions."""

from rag_api.domain.errors import DomainValidationError


class RegistrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def registration_error_from_domain(exc: DomainValidationError) -> RegistrationError:
    status_code = 400
    if exc.code == "reserved":
        status_code = 400
    return RegistrationError(exc.code, str(exc), status_code)


class LoginError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
