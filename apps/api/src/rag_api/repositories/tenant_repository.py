from rag_api.db.models.tenant import (
    CHARGE_MODE_FREE,
    TENANT_STATUS_ACTIVE,
    Tenant,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_tenant_name(self, tenant_name: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.tenant_name == tenant_name)
        return self._session.scalar(stmt)

    # Temporary alias during F08 transition
    find_by_subdomain = find_by_tenant_name

    def create(
        self,
        tenant_name: str,
        *,
        status: str = TENANT_STATUS_ACTIVE,
        charge_mode: str = CHARGE_MODE_FREE,
    ) -> Tenant:
        tenant = Tenant(
            tenant_name=tenant_name,
            status=status,
            charge_mode=charge_mode,
        )
        self._session.add(tenant)
        self._session.flush()
        return tenant
