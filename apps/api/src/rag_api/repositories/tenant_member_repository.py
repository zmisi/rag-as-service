from uuid import UUID

from rag_api.db.models.tenant_member import ROLE_OWNER, TenantMember
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
