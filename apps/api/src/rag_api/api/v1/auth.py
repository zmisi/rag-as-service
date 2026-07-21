from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from rag_api.api.dependencies.db import get_db
from rag_api.api.dependencies.tenancy import require_apex_host
from rag_api.api.schemas.auth import ErrorResponse, RegisterRequest, RegisterResponse
from rag_api.config import Settings, get_settings
from rag_api.core.exceptions import RegistrationError
from rag_api.services.registration_service import RegistrationService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _wants_redirect(request: Request) -> bool:
    if request.query_params.get("redirect") == "1":
        return True
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _apply_session_cookie(
    response: Response,
    *,
    token: str,
    settings: Settings,
    session_service_max_age: int,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        domain=settings.session_cookie_domain,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=session_service_max_age,
        path="/",
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_apex_host),
):
    service = RegistrationService(db, settings)
    try:
        outcome = service.register(
            email=body.email,
            password=body.password,
            subdomain=body.subdomain,
        )
    except RegistrationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    max_age = settings.session_ttl_days * 24 * 60 * 60

    if _wants_redirect(request):
        redirect = RedirectResponse(
            url=outcome.redirect_url,
            status_code=302,
        )
        _apply_session_cookie(
            redirect,
            token=outcome.session.token,
            settings=settings,
            session_service_max_age=max_age,
        )
        return redirect

    json_response = JSONResponse(
        status_code=201,
        content=RegisterResponse(
            subdomain=outcome.subdomain,
            redirect_url=outcome.redirect_url,
        ).model_dump(),
    )
    _apply_session_cookie(
        json_response,
        token=outcome.session.token,
        settings=settings,
        session_service_max_age=max_age,
    )
    return json_response
