from uuid import UUID

from rag_api.db.models.tenant import TENANT_STATUS_ACTIVE, Tenant
from rag_api.db.models.tenant_member import (
    MEMBER_ACTIVE,
    ROLE_MEMBER,
    TenantMember,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class TenantMemberRepository:
    """Persistence for tenant membership rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        tenant_id: UUID,
        user_id: UUID,
        member_name: str,
        role: str = ROLE_MEMBER,
        *,
        active: int = MEMBER_ACTIVE,
    ) -> TenantMember:
        """Insert a tenant membership and return the flushed row."""
        member = TenantMember(
            tenant_id=tenant_id,
            user_id=user_id,
            member_name=member_name,
            role=role,
            active=active,
        )
        self._session.add(member)
        self._session.flush()
        return member

    def find_primary_tenant_for_user(self, user_id: UUID) -> Tenant | None:
        """Return the first active tenant membership by join time."""
        stmt = (
            select(Tenant)
            .join(TenantMember, TenantMember.tenant_id == Tenant.tenant_id)
            .where(
                TenantMember.user_id == user_id,
                TenantMember.active == MEMBER_ACTIVE,
                Tenant.status == TENANT_STATUS_ACTIVE,
            )
            .order_by(TenantMember.create_at.asc())
            .limit(1)
        )
        return self._session.scalar(stmt)

    def find_member(self, tenant_id: UUID, user_id: UUID) -> TenantMember | None:
        """Find a tenant membership by tenant and user."""
        stmt = select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user_id,
        )
        return self._session.scalar(stmt)
