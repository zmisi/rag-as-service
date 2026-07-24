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
        tenant_name: str,
        user_name: str,
    ) -> RegistrationResult:
        user = self._users.create(
            email=email,
            password_hash=password_hash,
            user_name=user_name,
        )
        tenant = self._tenants.create(tenant_name=tenant_name)
        member = self._members.create(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            member_name=user.user_name,
        )
        return RegistrationResult(user=user, tenant=tenant, member=member)
