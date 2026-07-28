import logging
import secrets
import string
from dataclasses import dataclass

from rag_api.core.exceptions import RegistrationError
from rag_api.db.models import ROLE_ADMIN, ROLE_MEMBER, TenantMember, User
from rag_api.domain.identity.email import normalize_email
from rag_api.domain.identity.password import hash_password
from rag_api.repositories.tenant_member_repository import TenantMemberRepository
from rag_api.repositories.user_repository import UserRepository
from rag_api.services.registration_service import derive_user_name
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PASSWORD_ALPHABET = string.ascii_letters + string.digits
_ALLOWED_ROLES = {ROLE_MEMBER, ROLE_ADMIN}


@dataclass(frozen=True, slots=True)
class CreateMemberOutcome:
    """Successful tenant-member creation result."""

    member: TenantMember
    user: User
    temporary_password: str | None


class MemberService:
    """Manage tenant members inside a single tenant scope."""

    def __init__(self, db_session: Session) -> None:
        self._session = db_session
        self._users = UserRepository(db_session)
        self._members = TenantMemberRepository(db_session)

    def list_members(self, tenant_id) -> list[tuple[TenantMember, User]]:
        """Return active and inactive members for the tenant."""
        stmt = (
            select(TenantMember, User)
            .join(User, User.user_id == TenantMember.user_id)
            .where(TenantMember.tenant_id == tenant_id)
            .order_by(TenantMember.create_at.asc())
        )
        return list(self._session.execute(stmt).all())

    def create_member(
        self,
        *,
        tenant_id,
        member_name: str,
        email: str,
        role: str,
    ) -> CreateMemberOutcome:
        """Create a tenant member and temp password for newly created users."""
        cleaned_name = member_name.strip()
        if not cleaned_name:
            raise RegistrationError("invalid_member_name", "member_name is required", 400)
        if role not in _ALLOWED_ROLES:
            raise RegistrationError("invalid_role", "role must be member or admin", 400)

        normalized_email = normalize_email(email)
        user = self._users.find_by_email(normalized_email)
        temporary_password: str | None = None

        if user is None:
            temporary_password = _generate_temporary_password()
            desired_user_name = derive_user_name(normalized_email, cleaned_name)
            candidate = desired_user_name
            suffix = 0
            while self._users.find_by_user_name(candidate):
                suffix += 1
                base = desired_user_name[: max(1, 32 - len(str(suffix)) - 1)]
                candidate = f"{base}_{suffix}"
            user = self._users.create(
                email=normalized_email,
                password_hash=hash_password(temporary_password),
                user_name=candidate,
                must_change_password=True,
            )

        existing_member = self._members.find_member(tenant_id, user.user_id)
        if existing_member is not None:
            raise RegistrationError("member_exists", "email already belongs to this tenant", 409)

        try:
            member = self._members.create(
                tenant_id=tenant_id,
                user_id=user.user_id,
                member_name=cleaned_name,
                role=role,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            logger.info(
                "member_create_integrity_error",
                extra={"tenant_id": str(tenant_id), "email": normalized_email},
            )
            detail = str(exc.orig).lower()
            if "member_name" in detail:
                raise RegistrationError(
                    "member_name_taken", "member_name already exists in tenant", 409
                ) from exc
            raise RegistrationError("member_conflict", "member creation conflict", 409) from exc

        logger.info(
            "member_created",
            extra={
                "tenant_id": str(tenant_id),
                "user_id": str(user.user_id),
                "member_id": str(member.member_id),
                "role": role,
            },
        )
        return CreateMemberOutcome(
            member=member,
            user=user,
            temporary_password=temporary_password,
        )


def _generate_temporary_password(length: int = 12) -> str:
    """Generate a temporary password that satisfies the minimum length."""
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
