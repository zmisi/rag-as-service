import logging
from dataclasses import dataclass

from rag_api.config import Settings, get_settings
from rag_api.core.exceptions import LoginError
from rag_api.domain.identity.email import normalize_email
from rag_api.domain.identity.password import verify_password
from rag_api.repositories.tenant_member_repository import TenantMemberRepository
from rag_api.repositories.user_repository import UserRepository
from rag_api.services.session_service import SessionIssueResult, SessionService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoginOutcome:
    subdomain: str
    session: SessionIssueResult
    redirect_url: str


class LoginService:
    def __init__(
        self,
        db_session: Session,
        settings: Settings | None = None,
    ) -> None:
        self._session = db_session
        self._settings = settings or get_settings()
        self._users = UserRepository(db_session)
        self._members = TenantMemberRepository(db_session)
        self._sessions = SessionService(db_session, self._settings)

    def login(self, email: str, password: str) -> LoginOutcome:
        normalized_email = normalize_email(email)
        user = self._users.find_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            logger.info(
                "login_failed_invalid_credentials",
                extra={"email": normalized_email},
            )
            raise LoginError(
                "invalid_credentials",
                "邮箱或密码错误",
                401,
            )

        tenant = self._members.find_primary_tenant_for_user(user.id)
        if tenant is None:
            logger.info(
                "login_failed_no_tenant",
                extra={"user_id": str(user.id), "email": normalized_email},
            )
            raise LoginError("no_tenant", "user has no tenant", 403)

        session_issue = self._sessions.create_session(user.id)
        self._session.commit()

        redirect_url = f"https://{tenant.subdomain}.{self._settings.apex_host}/"
        logger.info(
            "login_success",
            extra={
                "user_id": str(user.id),
                "tenant_id": str(tenant.id),
                "subdomain": tenant.subdomain,
            },
        )
        return LoginOutcome(
            subdomain=tenant.subdomain,
            session=session_issue,
            redirect_url=redirect_url,
        )
