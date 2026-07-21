import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.db.models import ROLE_OWNER
from rag_api.repositories import RegistrationRepository, TenantRepository, UserRepository


@pytest.mark.integration
def test_register_owner_creates_user_tenant_and_member(db_session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"repo-test-{suffix}@example.com"
    subdomain = f"repo-{suffix}"

    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=email,
            password_hash="hashed-password",
            subdomain=subdomain,
        )

    assert result.user.email == email
    assert result.tenant.subdomain == subdomain
    assert result.member.role == ROLE_OWNER
    assert result.member.user_id == result.user.id
    assert result.member.tenant_id == result.tenant.id

    users = UserRepository(db_session)
    tenants = TenantRepository(db_session)
    assert users.find_by_email(email) is not None
    assert tenants.find_by_subdomain(subdomain) is not None


@pytest.mark.integration
def test_register_owner_rolls_back_on_failure(db_session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"rollback-{suffix}@example.com"
    subdomain = f"rb-{suffix}"

    with db_session.begin():
        RegistrationRepository(db_session).register_owner(
            email=email,
            password_hash="hashed-password",
            subdomain=subdomain,
        )

    with pytest.raises(Exception):
        with db_session.begin():
            RegistrationRepository(db_session).register_owner(
                email=email,
                password_hash="other-hash",
                subdomain=f"other-{suffix}",
            )

    count = db_session.execute(
        text("SELECT count(*) FROM rag_service.users WHERE email = :email"),
        {"email": email},
    ).scalar_one()
    assert count == 1
