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
    tenant_name = f"repo-{suffix}"
    user_name = f"repo{suffix}"

    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=email,
            password_hash="hashed-password",
            tenant_name=tenant_name,
            user_name=user_name,
        )

    assert result.user.email == email
    assert result.user.user_name == user_name
    assert result.tenant.tenant_name == tenant_name
    assert result.member.role == ROLE_OWNER
    assert result.member.user_id == result.user.user_id
    assert result.member.tenant_id == result.tenant.tenant_id
    assert result.member.member_name == user_name

    users = UserRepository(db_session)
    tenants = TenantRepository(db_session)
    assert users.find_by_email(email) is not None
    assert tenants.find_by_tenant_name(tenant_name) is not None


@pytest.mark.integration
def test_register_owner_rolls_back_on_failure(db_session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"rollback-{suffix}@example.com"
    tenant_name = f"rb-{suffix}"

    RegistrationRepository(db_session).register_owner(
        email=email,
        password_hash="hashed-password",
        tenant_name=tenant_name,
        user_name=f"rb{suffix}",
    )
    db_session.commit()

    with pytest.raises(Exception):
        RegistrationRepository(db_session).register_owner(
            email=email,
            password_hash="other-hash",
            tenant_name=f"other-{suffix}",
            user_name=f"other{suffix}",
        )
        db_session.commit()
    db_session.rollback()

    # Original owner row remains (no second user with same email).
    users = list(
        db_session.execute(
            text("SELECT email FROM rag_service.users WHERE email = :email"),
            {"email": email},
        ).all()
    )
    assert len(users) <= 1
