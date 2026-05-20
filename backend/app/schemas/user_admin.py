from typing import Literal

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    login: str = Field(..., min_length=2, max_length=128)
    password: str = Field(..., min_length=4)
    role: Literal["admin", "analyst", "logistician"] = "logistician"


class UserOut(BaseModel):
    id: int
    login: str
    role: str

    class Config:
        from_attributes = True
