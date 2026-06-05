"""Abstract interfaces (ports) for external dependencies.

Application layer defines these; infrastructure layer implements them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from offerten_converter.domain.entities import Offer, OfferStatus, User


class AIExtractor(ABC):
    """Port for AI-based product line item extraction."""

    @abstractmethod
    def call(self, user_content: str, system_prompt: str) -> str:
        """Send prompt to AI and return raw text response."""
        ...


class ProfileRepository(ABC):
    """Port for supplier profile persistence."""

    @abstractmethod
    def list_profiles(self) -> list[str]: ...

    @abstractmethod
    def load(self, name: str) -> dict | None: ...

    @abstractmethod
    def save(self, name: str, typical_currency: str, typical_discount: float,
             column_hints: str) -> Path: ...

    @abstractmethod
    def delete(self, name: str) -> bool: ...


class ExcelWriter(ABC):
    """Port for building Excel output files."""

    @abstractmethod
    def build(self, df: pd.DataFrame, supplier_name: str, created_by: str,
              target_currency: str, valid_days: int) -> bytes: ...


class MarketPricePort(ABC):
    """Port for fetching current market prices by EAN."""

    @abstractmethod
    def fetch_price(self, ean: str) -> float | None:
        """Return lowest market price for the given EAN, or None if not found."""
        ...


class UserRepository(ABC):
    """Port for application-user persistence."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def create(self, email: str, name: str, password_hash: str,
               must_change_password: bool = False) -> User: ...

    @abstractmethod
    def set_password(self, user_id: int, password_hash: str) -> User | None:
        """Update the password hash and clear the must-change flag."""
        ...

    @abstractmethod
    def list_users(self) -> list[User]: ...


class PasswordHasher(ABC):
    """Port for hashing and verifying passwords."""

    @abstractmethod
    def hash(self, plain: str) -> str: ...

    @abstractmethod
    def verify(self, plain: str, hashed: str) -> bool: ...


class OfferRepository(ABC):
    """Port for archived-offer persistence."""

    @abstractmethod
    def create(self, offer: Offer, original_bytes: bytes, generated_bytes: bytes) -> Offer:
        """Persist a new offer with its line items and both file blobs."""
        ...

    @abstractmethod
    def get(self, offer_id: int) -> Offer | None:
        """Return the offer with its line items (no file blobs)."""
        ...

    @abstractmethod
    def list(
        self,
        *,
        jahr: int | None = None,
        marke: str | None = None,
        lieferant: str | None = None,
        status: OfferStatus | None = None,
        query: str | None = None,
    ) -> list[Offer]:
        """Return matching offers (metadata only, newest first)."""
        ...

    @abstractmethod
    def get_original_file(self, offer_id: int) -> tuple[bytes, str] | None:
        """Return (bytes, filename) of the original supplier file, or None."""
        ...

    @abstractmethod
    def get_generated_file(self, offer_id: int) -> tuple[bytes, str] | None:
        """Return (bytes, filename) of the generated AMP offer, or None."""
        ...

    @abstractmethod
    def update_status(self, offer_id: int, status: OfferStatus) -> Offer | None: ...
