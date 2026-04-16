"""Integration tests for file-based supplier profile repository."""

import pytest

from offerten_converter.infrastructure.file_profile_repo import (
    FileProfileRepository,
    profile_to_hints,
)


@pytest.fixture
def repo(tmp_path):
    return FileProfileRepository(profiles_dir=tmp_path)


class TestFileProfileRepository:
    def test_save_and_load(self, repo):
        repo.save("Test Supplier", "EUR", 5.0, "sku=Art.Nr")
        profile = repo.load("Test Supplier")
        assert profile is not None
        assert profile["name"] == "Test Supplier"
        assert profile["typical_currency"] == "EUR"
        assert profile["typical_discount"] == 5.0
        assert profile["column_hints"] == "sku=Art.Nr"

    def test_list_empty(self, repo):
        assert repo.list_profiles() == []

    def test_list_after_save(self, repo):
        repo.save("Alpha", "EUR", 0.0, "")
        repo.save("Beta", "USD", 10.0, "")
        profiles = repo.list_profiles()
        assert len(profiles) == 2
        assert "alpha" in profiles
        assert "beta" in profiles

    def test_delete(self, repo):
        repo.save("ToDelete", "CHF", 0.0, "")
        assert repo.delete("ToDelete") is True
        assert repo.load("ToDelete") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("NoSuchProfile") is False

    def test_load_nonexistent(self, repo):
        assert repo.load("ghost") is None


class TestProfileToHints:
    def test_full_profile(self):
        profile = {
            "typical_currency": "EUR",
            "typical_discount": 5.0,
            "column_hints": "sku=Artikelnum",
        }
        result = profile_to_hints(profile)
        assert "EUR" in result
        assert "5.0%" in result
        assert "Artikelnum" in result

    def test_empty_profile(self):
        assert profile_to_hints({}) == ""
