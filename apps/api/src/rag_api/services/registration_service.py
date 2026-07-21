import logging
from dataclasses import dataclass

from rag_api.config import Settings, get_settings
from rag_api.core.exceptions import RegistrationError, registration_error_from_domain
from rag_api.domain.errors import DomainValidationError
from rag_api.domain.identity.email import normalize_email
from rag_api.domain.identity.password import hash_password
from rag_api.domain.tenancy.subdomain import validate_subdomain
from rag_api.repositories.registration_repository import RegistrationRepository
from rag_api.repositories.tenant_repository import TenantRepository
from rag_api.repositories.user_repository import UserRepository
from rag_api.services.session_service import SessionIssueResult, SessionService
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RegistrationOutcome:
    subdomain: str
    session: SessionIssueResult
    redirect_url: str


class RegistrationService:
    def __init__(
        self,
        db_session: Session,
        settings: Settings | None = None,
    ) -> None:
        self._session = db_session
        self._settings = settings or get_settings()
        self._users = UserRepository(db_session)
        self._tenants = TenantRepository(db_session)
        self._registration = RegistrationRepository(db_session)
        self._sessions = SessionService(db_session, self._settings)

    def register(self, email: str, password: str, subdomain: str) -> RegistrationOutcome:
        try:
            normalized_email = normalize_email(email)
            normalized_subdomain = validate_subdomain(subdomain)
        except DomainValidationError as exc:
            logger.info(
                "registration_validation_failed",
                extra={"reason": exc.code, "email": email, "subdomain": subdomain},
            )
            raise registration_error_from_domain(exc) from exc

        password_hash = hash_password(password)

        if self._users.find_by_email(normalized_email):
            logger.info(
                "registration_failed_email_taken",
                extra={"email": normalized_email},
            )
            raise RegistrationError("email_taken", "email already registered", 409)

        if self._tenants.find_by_subdomain(normalized_subdomain):
            logger.info(
                "registration_failed_subdomain_taken",
                extra={"subdomain": normalized_subdomain},
            )
            raise RegistrationError("subdomain_taken", "subdomain already taken", 409)

        try:
            result = self._registration.register_owner(
                email=normalized_email,
                password_hash=password_hash,
                subdomain=normalized_subdomain,
            )
            session_issue = self._sessions.create_session(result.user.id)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            logger.info(
                "registration_failed_integrity",
                extra={"email": normalized_email, "subdomain": normalized_subdomain},
            )
            raise _map_integrity_error(exc) from exc

        redirect_url = (
            f"https://{normalized_subdomain}.{self._settings.apex_host}/admin"
        )
        logger.info(
            "registration_success",
            extra={
                "user_id": str(result.user.id),
                "tenant_id": str(result.tenant.id),
                "subdomain": normalized_subdomain,
            },
        )
        return RegistrationOutcome(
            subdomain=normalized_subdomain,
            session=session_issue,
            redirect_url=redirect_url,
        )


def _map_integrity_error(exc: IntegrityError) -> RegistrationError:
    detail = str(exc.orig).lower()
    if "users_email_key" in detail or "email" in detail:
        return RegistrationError("email_taken", "email already registered", 409)
    if "tenants_subdomain_key" in detail or "subdomain" in detail:
        return RegistrationError("subdomain_taken", "subdomain already taken", 409)
    return RegistrationError("conflict", "registration conflict", 409)
