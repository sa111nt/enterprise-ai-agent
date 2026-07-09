import datetime

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest


class TestRegisterRequest:
    def test_valid(self):
        data = RegisterRequest(
            email="test@example.com",
            password="secure_pw",
            first_name="John",
            last_name="Doe",
            position="Engineer",
            hire_date=datetime.date(2024, 1, 1),
        )
        assert data.email == "test@example.com"

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="short",
                first_name="John",
                last_name="Doe",
                position="Engineer",
                hire_date=datetime.date(2024, 1, 1),
            )

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="not-an-email",
                password="secure_pw",
                first_name="John",
                last_name="Doe",
                position="Engineer",
                hire_date=datetime.date(2024, 1, 1),
            )

    def test_empty_first_name_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="secure_pw",
                first_name="",
                last_name="Doe",
                position="Engineer",
                hire_date=datetime.date(2024, 1, 1),
            )


class TestLoginRequest:
    def test_valid(self):
        data = LoginRequest(email="test@example.com", password="pw123456")
        assert data.email == "test@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="bad", password="pw123456")


class TestRefreshRequest:
    def test_valid(self):
        data = RefreshRequest(refresh_token="some.jwt.token")
        assert data.refresh_token == "some.jwt.token"
