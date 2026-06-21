import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_db
from app.core.security import decode_token
from app.models.employee import Employee
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
        if email is None:
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


async def get_auth_service(
    session: AsyncSession = Depends(get_async_db),
) -> AuthService:
    return AuthService(session)


async def get_document_service(
    session: AsyncSession = Depends(get_async_db),
) -> DocumentService:
    return DocumentService(session)
