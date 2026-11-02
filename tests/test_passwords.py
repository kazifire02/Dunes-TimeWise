"""Cross-runtime compatibility with the hashes already stored by Werkzeug."""

import hashlib

import pytest
from werkzeug.security import generate_password_hash

from passwords import check_password_hash


@pytest.mark.parametrize("method", ["pbkdf2:sha256:1000", "pbkdf2:sha512:1000", "scrypt:32768:8:1"])
def test_worker_fallback_verifies_existing_hashes(monkeypatch, method):
    stored = generate_password_hash("a-strong-test-password", method=method)
    monkeypatch.delattr(hashlib, "pbkdf2_hmac", raising=False)
    monkeypatch.delattr(hashlib, "scrypt", raising=False)
    assert check_password_hash(stored, "a-strong-test-password")
    assert not check_password_hash(stored, "wrong-password")


def test_malformed_hash_is_rejected():
    assert not check_password_hash("bad hash", "password")
