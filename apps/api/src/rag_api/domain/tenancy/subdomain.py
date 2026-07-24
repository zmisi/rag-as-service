import re

from rag_api.domain.errors import SubdomainValidationError

RESERVED_TENANT_NAMES = frozenset(
    {"www", "admin", "api", "app", "mail", "static", "cdn", "lxzxai"}
)
# Deprecated alias
RESERVED_SUBDOMAINS = RESERVED_TENANT_NAMES

TENANT_NAME_MIN_LENGTH = 3
TENANT_NAME_MAX_LENGTH = 32
SUBDOMAIN_MIN_LENGTH = TENANT_NAME_MIN_LENGTH
SUBDOMAIN_MAX_LENGTH = TENANT_NAME_MAX_LENGTH

_TENANT_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_SUBDOMAIN_PATTERN = _TENANT_NAME_PATTERN


def normalize_tenant_name(raw: str) -> str:
    return raw.strip().lower()


normalize_subdomain = normalize_tenant_name


def validate_tenant_name(raw: str) -> str:
    """Normalize and validate tenant_name (Host label); return canonical lowercase."""
    normalized = normalize_tenant_name(raw)

    if (
        len(normalized) < TENANT_NAME_MIN_LENGTH
        or len(normalized) > TENANT_NAME_MAX_LENGTH
    ):
        raise SubdomainValidationError(
            "invalid_format",
            "tenant_name must be 3–32 characters",
        )

    if not _TENANT_NAME_PATTERN.match(normalized):
        raise SubdomainValidationError(
            "invalid_format",
            "tenant_name must use lowercase letters, digits, and hyphens; "
            "cannot start or end with a hyphen",
        )

    if normalized in RESERVED_TENANT_NAMES:
        raise SubdomainValidationError(
            "reserved",
            "tenant_name is reserved",
        )

    return normalized


validate_subdomain = validate_tenant_name
