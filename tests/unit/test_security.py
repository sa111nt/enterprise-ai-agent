import pytest
import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "secure_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes(self):
        pwd = "same_password"
        hash1 = hash_password(pwd)
        hash2 = hash_password(pwd)
        assert hash1 != hash2  # Argon2 uses random salt


class TestJWT:
    def test_access_token_creation_and_decode(self):
        token = create_access_token(subject="user@example.com")
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "access"

    def test_refresh_token_creation_and_decode(self):
        token = create_refresh_token(subject="user@example.com")
        payload = decode_token(token, expected_type="refresh")
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(subject="user@example.com")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token, expected_type="refresh")

    def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token(subject="user@example.com")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token, expected_type="access")


