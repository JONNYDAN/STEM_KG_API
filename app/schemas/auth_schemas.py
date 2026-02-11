from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class UserCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    role: Optional[str] = "user"
    group: Optional[List[str]] = []
    photoURL: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: str
    password: str

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: str
    staffCode: str
    name: str
    username: str
    role: str
    group: List[str]
    photoURL: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    success: bool
    data: dict

    model_config = ConfigDict(from_attributes=True)
