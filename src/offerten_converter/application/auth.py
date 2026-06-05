"""Authentication use cases.

Pure orchestration over the UserRepository and PasswordHasher ports – no
framework, no bcrypt/jwt imports here.
"""

from __future__ import annotations

from offerten_converter.application.ports import PasswordHasher, UserRepository
from offerten_converter.domain.entities import User


class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher):
        self._users = users
        self._hasher = hasher

    @staticmethod
    def _normalise_email(email: str) -> str:
        return email.strip().lower()

    def authenticate(self, email: str, password: str) -> User | None:
        """Return the user if email+password are valid and the user is active."""
        user = self._users.get_by_email(self._normalise_email(email))
        if user is None or not user.is_active:
            return None
        if not self._hasher.verify(password, user.password_hash):
            return None
        return user

    def create_user(self, email: str, name: str, password: str) -> User:
        """Create a user with a hashed password. Email is normalised to lowercase."""
        return self._users.create(
            self._normalise_email(email), name, self._hasher.hash(password)
        )
