import re

from rag_api.domain.errors import SubdomainValidationError

RESERVED_SUBDOMAINS = frozenset(
    {"www", "admin", "api", "app", "mail", "static", "cdn", "lxzxai"}
)
SUBDOMAIN_MIN_LENGTH = 3
SUBDOMAIN_MAX_LENGTH = 32
_SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def normalize_subdomain(raw: str) -> str:
    return raw.strip().lower()


def validate_subdomain(raw: str) -> str:
    """Normalize and validate subdomain; return canonical lowercase value."""
    normalized = normalize_subdomain(raw)

    if len(normalized) < SUBDOMAIN_MIN_LENGTH or len(normalized) > SUBDOMAIN_MAX_LENGTH:
        raise SubdomainValidationError(
            "invalid_format",
            "subdomain must be 3–32 characters",
        )

    if not _SUBDOMAIN_PATTERN.match(normalized):
        raise SubdomainValidationError(
            "invalid_format",
            "subdomain must use lowercase letters, digits, and hyphens; "
            "cannot start or end with a hyphen",
        )

    if normalized in RESERVED_SUBDOMAINS:
        raise SubdomainValidationError(
            "reserved",
            "subdomain is reserved",
        )

    return normalized
