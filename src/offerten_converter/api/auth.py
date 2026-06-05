"""Auth API: login, current-user endpoint, and the get_current_user dependency.

The router is mounted WITHOUT the global token guard so /login stays public.
get_current_user is exported here so phase 1c can protect the main router.
"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from offerten_converter.application.auth import AuthService
from offerten_converter.domain.entities import User
from offerten_converter.infrastructure.db.engine import get_db
from offerten_converter.infrastructure.security import (
    BcryptPasswordHasher,
    create_access_token,
    decode_access_token,
)
from offerten_converter.infrastructure.sql_user_repo import SqlUserRepository

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


# --- schemas --------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- wiring ---------------------------------------------------------------

def _auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(SqlUserRepository(db), BcryptPasswordHasher())


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the logged-in user from the Bearer JWT, or raise 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nicht authentifiziert",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise unauthorized from None

    user = SqlUserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


# --- endpoints ------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, svc: AuthService = Depends(_auth_service)) -> TokenResponse:
    user = svc.authenticate(body.email, body.password)
    if user is None or user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-Mail oder Passwort falsch",
        )
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, name=user.name),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    assert user.id is not None
    return UserOut(id=user.id, email=user.email, name=user.name)
