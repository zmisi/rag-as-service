from dataclasses import dataclass

from rag_api.db.models import Tenant, TenantMember, User
from rag_api.repositories.tenant_member_repository import TenantMemberRepository
from rag_api.repositories.tenant_repository import TenantRepository
from rag_api.repositories.user_repository import UserRepository
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    user: User
    tenant: Tenant
    member: TenantMember


class RegistrationRepository:
    """Creates user, tenant, and owner membership in the caller's transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tenants = TenantRepository(session)
        self._members = TenantMemberRepository(session)

    def register_owner(
        self,
        email: str,
        password_hash: str,
        subdomain: str,
        display_name: str | None = None,
    ) -> RegistrationResult:
        user = self._users.create(email=email, password_hash=password_hash)
        tenant = self._tenants.create(
            subdomain=subdomain,
            display_name=display_name,
        )
        member = self._members.create(
            tenant_id=tenant.id,
            user_id=user.id,
        )
        return RegistrationResult(user=user, tenant=tenant, member=member)
