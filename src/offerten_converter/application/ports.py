"""Abstract interfaces (ports) for external dependencies.

Application layer defines these; infrastructure layer implements them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


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
