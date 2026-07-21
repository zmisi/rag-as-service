import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.api.cookies import apply_session_cookie, clear_session_cookie
from rag_api.api.dependencies.auth import (
    get_session_user,
    parse_subdomain,
    require_known_host,
)
from rag_api.api.dependencies.db import get_db
from rag_api.api.dependencies.tenancy import require_apex_host
from rag_api.api.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
)
from rag_api.config import Settings, get_settings
from rag_api.core.exceptions import LoginError, RegistrationError
from rag_api.db.models import Tenant, TenantMember, User
from rag_api.services.login_service import LoginService
from rag_api.services.registration_service import RegistrationService
from rag_api.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _wants_redirect(request: Request) -> bool:
    if request.query_params.get("redirect") == "1":
        return True
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _host_header(request: Request) -> str:
    x_forwarded_host = request.headers.get("x-forwarded-host") or ""
    if x_forwarded_host:
        return x_forwarded_host.split(",")[0].strip()
    return request.headers.get("host", "")


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

    if _wants_redirect(request):
        redirect = RedirectResponse(
            url=outcome.redirect_url,
            status_code=302,
        )
        apply_session_cookie(
            redirect,
            token=outcome.session.token,
            settings=settings,
        )
        return redirect

    json_response = JSONResponse(
        status_code=201,
        content=RegisterResponse(
            subdomain=outcome.subdomain,
            redirect_url=outcome.redirect_url,
        ).model_dump(),
    )
    apply_session_cookie(
        json_response,
        token=outcome.session.token,
        settings=settings,
    )
    return json_response


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_apex_host),
):
    service = LoginService(db, settings)
    try:
        outcome = service.login(email=body.email, password=body.password)
    except LoginError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    if _wants_redirect(request):
        redirect = RedirectResponse(url=outcome.redirect_url, status_code=302)
        apply_session_cookie(redirect, token=outcome.session.token, settings=settings)
        return redirect

    json_response = JSONResponse(
        status_code=200,
        content=LoginResponse(
            subdomain=outcome.subdomain,
            redirect_url=outcome.redirect_url,
        ).model_dump(),
    )
    apply_session_cookie(json_response, token=outcome.session.token, settings=settings)
    return json_response


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_known_host),
):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        SessionService(db, settings).revoke_session(token)
        db.commit()
        logger.info("logout_success")
    else:
        logger.info("logout_no_cookie")

    response = Response(status_code=204)
    clear_session_cookie(response, settings=settings)
    return response


@router.get("/me", response_model=MeResponse)
def auth_me(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_session_user),
):
    raw_host = _host_header(request)
    subdomain = parse_subdomain(raw_host)
    if subdomain is None:
        return MeResponse(user_id=str(user.id), email=user.email)

    tenant = db.scalar(select(Tenant).where(Tenant.subdomain == subdomain))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    member = db.scalar(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant.id,
            TenantMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Not a tenant member")

    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        tenant_id=str(tenant.id),
        subdomain=tenant.subdomain,
        role=member.role,
    )
