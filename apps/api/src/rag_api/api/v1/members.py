from fastapi import APIRouter, Depends, HTTPException

from rag_api.api.dependencies.auth import AuthContext, require_tenant_admin
from rag_api.api.dependencies.db import get_db
from rag_api.api.schemas.auth import ErrorResponse
from rag_api.api.schemas.members import (
    CreateMemberRequest,
    CreateMemberResponse,
    MemberSummary,
)
from rag_api.core.exceptions import RegistrationError
from rag_api.services.member_service import MemberService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberSummary])
def list_members(
    auth: AuthContext = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """List tenant members for the current admin context."""
    pairs = MemberService(db).list_members(auth.tenant_id)
    return [
        MemberSummary(
            member_id=str(member.member_id),
            user_id=str(user.user_id),
            email=user.email,
            member_name=member.member_name,
            role=member.role,
            active=member.active,
        )
        for member, user in pairs
    ]

@router.post(
    "",
    response_model=CreateMemberResponse,
    status_code=201,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_member(
    body: CreateMemberRequest,
    auth: AuthContext = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
):
    """Create a tenant member and return the generated temporary password."""
    try:
        outcome = MemberService(db).create_member(
            tenant_id=auth.tenant_id,
            member_name=body.member_name,
            email=body.email,
            role=body.role,
        )
    except RegistrationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    return CreateMemberResponse(
        member_id=str(outcome.member.member_id),
        user_id=str(outcome.user.user_id),
        email=outcome.user.email,
        member_name=outcome.member.member_name,
        role=outcome.member.role,
        temporary_password=outcome.temporary_password,
        must_change_password=outcome.user.must_change_password,
    )
