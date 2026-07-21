from uuid import UUID

from rag_api.db.models.tenant import Tenant
from rag_api.db.models.tenant_member import ROLE_OWNER, TenantMember
from sqlalchemy import select
from sqlalchemy.orm import Session


class TenantMemberRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        tenant_id: UUID,
        user_id: UUID,
        role: str = ROLE_OWNER,
    ) -> TenantMember:
        member = TenantMember(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
        )
        self._session.add(member)
        self._session.flush()
        return member

    def find_primary_tenant_for_user(self, user_id: UUID) -> Tenant | None:
        """Phase 1: first owner membership by join time."""
        stmt = (
            select(Tenant)
            .join(TenantMember, TenantMember.tenant_id == Tenant.id)
            .where(
                TenantMember.user_id == user_id,
                TenantMember.role == ROLE_OWNER,
            )
            .order_by(TenantMember.create_at.asc())
            .limit(1)
        )
        return self._session.scalar(stmt)
