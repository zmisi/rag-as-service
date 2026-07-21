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


class MeResponse(BaseModel):
    user_id: str
    email: str
    tenant_id: str | None = None
    subdomain: str | None = None
    role: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
