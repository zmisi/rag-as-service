from rag_api.domain.errors import EmailValidationError


def normalize_email(raw: str) -> str:
    """Return lowercase email for storage and lookup."""
    normalized = raw.strip().lower()
    if not normalized or "@" not in normalized:
        raise EmailValidationError("invalid_format", "email format is invalid")
    return normalized
