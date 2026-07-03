import time

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.redis import get_redis_client
from app.core.security import decode_token
from app.models.employee import Employee, EmployeeRole
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_employee(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_db),
) -> Employee:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token, expected_type="access")
        email: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if email is None:
            raise credentials_exception
        if jti:
            redis = get_redis_client()
            is_blacklisted = await redis.exists(f"blacklist:{jti}")
            if is_blacklisted:
                raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise credentials_exception from None

    stmt = select(Employee).where(Employee.email == email)
    result = await session.execute(stmt)
    employee = result.scalar_one_or_none()

    if employee is None:
        raise credentials_exception
    if not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive account",
        )
    return employee


async def require_admin(
    employee: Employee = Depends(get_current_employee),
) -> Employee:
    if employee.role != EmployeeRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return employee


async def get_auth_service(
    session: AsyncSession = Depends(get_async_db),
) -> AuthService:
    return AuthService(session)


async def get_document_service(
    session: AsyncSession = Depends(get_async_db),
) -> DocumentService:
    return DocumentService(session)


def get_agent_service(
    session: AsyncSession = Depends(get_async_db),
) -> AgentService:
    return AgentService(session)


class RateLimiter:
    def __init__(self, requests: int, window_seconds: int = 60):
        self.requests = requests
        self.window_seconds = window_seconds

    async def __call__(self, employee: Employee = Depends(get_current_employee)):
        redis = get_redis_client()
        current_window = int(time.time() / self.window_seconds)
        key = f"rate_limit:{employee.id}:{current_window}"

        current_count = await redis.incr(key)
        if current_count == 1:
            await redis.expire(key, self.window_seconds * 2)

        if current_count > self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(self.window_seconds)},
            )
