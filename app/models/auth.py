from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    password: str
    passwordConfirm: str
    name: str


class TokenResponse(BaseModel):
    token: str
    user: dict
