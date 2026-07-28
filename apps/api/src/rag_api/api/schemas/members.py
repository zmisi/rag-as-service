from pydantic import BaseModel, EmailStr, Field


class CreateMemberRequest(BaseModel):
    member_name: str = Field(min_length=1, max_length=64)
    email: EmailStr
    role: str


class CreateMemberResponse(BaseModel):
    member_id: str
    user_id: str
    email: str
    member_name: str
    role: str
    temporary_password: str | None = None
    must_change_password: bool


class MemberSummary(BaseModel):
    member_id: str
    user_id: str
    email: str
    member_name: str
    role: str
    active: int
