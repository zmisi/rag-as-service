from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    subdomain: str = Field(min_length=1, max_length=32)


class RegisterResponse(BaseModel):
    subdomain: str
    redirect_url: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    subdomain: str
    redirect_url: str
    must_change_password: bool = False
    change_password_url: str | None = None


class MeResponse(BaseModel):
    user_id: str
    email: str
    tenant_id: str | None = None
    subdomain: str | None = None
    role: str | None = None
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class ErrorResponse(BaseModel):
    code: str
    message: str
