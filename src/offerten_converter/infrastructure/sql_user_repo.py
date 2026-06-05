"""SQLAlchemy-backed implementation of the UserRepository port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from offerten_converter.application.ports import UserRepository
from offerten_converter.domain.entities import User
from offerten_converter.infrastructure.db.models import UserModel


def _to_domain(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        password_hash=row.password_hash,
        is_active=row.is_active,
        must_change_password=row.must_change_password,
        created_at=row.created_at,
    )


class SqlUserRepository(UserRepository):
    """User persistence using a SQLAlchemy session (one per request)."""

    def __init__(self, session: Session):
        self._s = session

    def get_by_email(self, email: str) -> User | None:
        row = self._s.scalar(select(UserModel).where(UserModel.email == email))
        return _to_domain(row) if row is not None else None

    def get_by_id(self, user_id: int) -> User | None:
        row = self._s.get(UserModel, user_id)
        return _to_domain(row) if row is not None else None

    def create(self, email: str, name: str, password_hash: str,
               must_change_password: bool = False) -> User:
        row = UserModel(
            email=email,
            name=name,
            password_hash=password_hash,
            is_active=True,
            must_change_password=must_change_password,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return _to_domain(row)

    def set_password(self, user_id: int, password_hash: str) -> User | None:
        row = self._s.get(UserModel, user_id)
        if row is None:
            return None
        row.password_hash = password_hash
        row.must_change_password = False
        self._s.commit()
        self._s.refresh(row)
        return _to_domain(row)

    def list_users(self) -> list[User]:
        rows = self._s.scalars(select(UserModel).order_by(UserModel.email)).all()
        return [_to_domain(r) for r in rows]
