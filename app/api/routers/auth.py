from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_auth_service, get_current_employee
from app.models.employee import Employee
from app.schemas.auth import EmployeeRead, RefreshRequest, RegisterRequest, TokenPair
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new employee account",
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> EmployeeRead:
    employee = await service.register(body)
    return EmployeeRead.model_validate(employee)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Login and receive access + refresh tokens",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await service.login(
        email=form_data.username,
        password=form_data.password,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh tokens",
)
async def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await service.refresh_tokens(body.refresh_token)


@router.get(
    "/me",
    response_model=EmployeeRead,
    summary="Get current authenticated employee profile",
)
async def get_me(
    current_employee: Employee = Depends(get_current_employee),
) -> EmployeeRead:
    return EmployeeRead.model_validate(current_employee)
