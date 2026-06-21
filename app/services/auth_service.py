import logging

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.employee import Employee
from app.schemas.auth import RegisterRequest, TokenPair

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, data: RegisterRequest) -> Employee:
        stmt = select(Employee).where(Employee.email == data.email)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with email {data.email!r} already exists",
            )

        employee = Employee(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            password_hash=hash_password(data.password),
            position=data.position,
            hire_date=data.hire_date,
        )
        self.session.add(employee)
        await self.session.flush()
        await self.session.refresh(employee)
        logger.info(
            "Registered new employee id=%s email=%s", employee.id, employee.email
        )
        return employee

    async def login(self, email: str, password: str) -> TokenPair:
        invalid_credentials = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        stmt = select(Employee).where(Employee.email == email)
        result = await self.session.execute(stmt)
        employee = result.scalar_one_or_none()

        if employee is None:
            raise invalid_credentials

        if not verify_password(password, employee.password_hash):
            raise invalid_credentials

        if not employee.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is deactivated",
            )

        logger.info("Employee id=%s logged in", employee.id)
        return TokenPair(
            access_token=create_access_token(subject=employee.email),
            refresh_token=create_refresh_token(subject=employee.email),
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            email: str | None = payload.get("sub")
            if email is None:
                raise credentials_exception
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        except jwt.InvalidTokenError:
            raise credentials_exception from None

        stmt = select(Employee).where(Employee.email == email)
        result = await self.session.execute(stmt)
        employee = result.scalar_one_or_none()

        if employee is None:
            raise credentials_exception

        if not employee.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is deactivated",
            )

        logger.info("Employee id=%s refreshed tokens", employee.id)
        return TokenPair(
            access_token=create_access_token(subject=employee.email),
            refresh_token=create_refresh_token(subject=employee.email),
        )
