from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    login: str
    role: str


class UserResponse(BaseModel):
    id: int
    login: str
    role: str

    class Config:
        from_attributes = True
