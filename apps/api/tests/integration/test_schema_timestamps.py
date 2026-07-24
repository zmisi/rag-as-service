import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine


@pytest.mark.integration
def test_users_timestamps_on_insert_and_update(db_engine: Engine) -> None:
    user_id = uuid.uuid4()
    email = f"schema-test-{user_id}@example.com"

    with db_engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO rag_service.users (id, email, password_hash)
                VALUES (:id, :email, :password_hash)
                RETURNING create_at, update_at
                """
            ),
            {"id": user_id, "email": email, "password_hash": "hash-v1"},
        ).one()
        create_at, update_at = row.create_at, row.update_at
        assert create_at is not None
        assert update_at is not None

    time.sleep(0.05)

    with db_engine.begin() as conn:
        updated = conn.execute(
            text(
                """
                UPDATE rag_service.users
                SET password_hash = :password_hash
                WHERE id = :id
                RETURNING create_at, update_at
                """
            ),
            {"id": user_id, "password_hash": "hash-v2"},
        ).one()
        assert updated.create_at == create_at
        assert updated.update_at >= update_at

    with db_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM rag_service.users WHERE user_id = :id"),
            {"id": user_id},
        )


@pytest.mark.integration
def test_sessions_timestamps_on_insert_and_update(db_engine: Engine) -> None:
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    email = f"session-test-{user_id}@example.com"
    token_hash = f"token-{session_id}"

    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO rag_service.users (id, email, password_hash)
                VALUES (:id, :email, :password_hash)
                """
            ),
            {"id": user_id, "email": email, "password_hash": "hash"},
        )
        row = conn.execute(
            text(
                """
                INSERT INTO rag_service.sessions
                  (id, user_id, token_hash, expires_at)
                VALUES
                  (:id, :user_id, :token_hash, now() + interval '14 days')
                RETURNING create_at, update_at
                """
            ),
            {
                "id": session_id,
                "user_id": user_id,
                "token_hash": token_hash,
            },
        ).one()
        create_at, update_at = row.create_at, row.update_at
        assert create_at is not None
        assert update_at is not None

    time.sleep(0.05)

    with db_engine.begin() as conn:
        updated = conn.execute(
            text(
                """
                UPDATE rag_service.sessions
                SET expires_at = expires_at + interval '1 day'
                WHERE id = :id
                RETURNING create_at, update_at
                """
            ),
            {"id": session_id},
        ).one()
        assert updated.create_at == create_at
        assert updated.update_at >= update_at

    with db_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM rag_service.sessions WHERE id = :id"),
            {"id": session_id},
        )
        conn.execute(
            text("DELETE FROM rag_service.users WHERE user_id = :id"),
            {"id": user_id},
        )
