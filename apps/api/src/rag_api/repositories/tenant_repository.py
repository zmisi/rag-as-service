from rag_api.db.models.tenant import Tenant
from sqlalchemy import select
from sqlalchemy.orm import Session


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_subdomain(self, subdomain: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.subdomain == subdomain)
        return self._session.scalar(stmt)

    def create(self, subdomain: str, display_name: str | None = None) -> Tenant:
        tenant = Tenant(subdomain=subdomain, display_name=display_name)
        self._session.add(tenant)
        self._session.flush()
        return tenant
