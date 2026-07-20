import uuid

APEX_HOST_HEADERS = {"Host": "lxzxai.com"}
JSON_HEADERS = {**APEX_HOST_HEADERS, "Accept": "application/json"}


def unique_subdomain(prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    value = f"{prefix}-{suffix}".lower()
    return value[:32]
