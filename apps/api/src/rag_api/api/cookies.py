from fastapi import Response

from rag_api.config import Settings


def cookie_max_age_seconds(settings: Settings) -> int:
    return settings.session_ttl_days * 24 * 60 * 60


def apply_session_cookie(
    response: Response,
    *,
    token: str,
    settings: Settings,
) -> None:
    kwargs: dict = {
        "key": settings.session_cookie_name,
        "value": token,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "max_age": cookie_max_age_seconds(settings),
        "path": "/",
    }
    if settings.session_cookie_domain:
        kwargs["domain"] = settings.session_cookie_domain
    response.set_cookie(**kwargs)


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    if settings.session_cookie_domain:
        response.delete_cookie(
            key=settings.session_cookie_name,
            domain=settings.session_cookie_domain,
            path="/",
        )
    else:
        response.delete_cookie(
            key=settings.session_cookie_name,
            path="/",
        )
