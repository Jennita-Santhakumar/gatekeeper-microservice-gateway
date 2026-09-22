"""Unit tests for core.security: JWT round-trip and password hashing."""

from __future__ import annotations

import time

import pytest

from core.security import (
    TokenError,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_different_hash_than_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$2b$")


def test_verify_password_accepts_correct_password():
    hashed = hash_password("s3cret-password")
    assert verify_password("s3cret-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("s3cret-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_handles_garbage_hash_gracefully():
    assert verify_password("anything", "not-a-real-hash") is False


def test_create_and_decode_token_round_trip():
    token = create_access_token(user_id=42, email="a@example.com")
    claims = decode_token(token)
    assert claims["sub"] == "42"
    assert claims["email"] == "a@example.com"
    assert "jti" in claims and claims["jti"]


def test_each_token_has_unique_jti():
    token1 = create_access_token(user_id=1)
    token2 = create_access_token(user_id=1)
    assert decode_token(token1)["jti"] != decode_token(token2)["jti"]


def test_decode_token_rejects_garbage():
    with pytest.raises(TokenError):
        decode_token("not.a.jwt")


def test_decode_token_rejects_expired_token():
    token = create_access_token(user_id=1, expiry_minutes=0)
    time.sleep(1.2)
    with pytest.raises(TokenError):
        decode_token(token)
