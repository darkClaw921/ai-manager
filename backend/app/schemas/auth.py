"""Authentication schemas: login, token, refresh, register."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Login request body."""

    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="Authenticated user info")


class RefreshRequest(BaseModel):
    """Refresh token request body."""

    refresh_token: str = Field(..., description="JWT refresh token")


class RegisterRequest(BaseModel):
    """Registration request body for new managers."""

    email: EmailStr = Field(..., description="Manager email")
    password: str = Field(..., min_length=6, description="Manager password")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")


class RegisterResponse(BaseModel):
    """Registration response with JWT tokens and user info."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="Created manager info")
