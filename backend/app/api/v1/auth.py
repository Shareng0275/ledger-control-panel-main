from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserMeResponse,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user & create initial organization",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user = await AuthService.register_user(
        db=db,
        register_data=payload,
        ip_address=ip_address,
    )

    tokens = await AuthService.create_tokens_for_user(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access & refresh tokens",
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user = await AuthService.authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )

    tokens = await AuthService.create_tokens_for_user(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    
    # Audit log login event
    await AuditService.log_login(
        db=db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()

    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and obtain new token pair",
)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    new_tokens = await AuthService.rotate_refresh_token(
        db=db,
        raw_refresh_token=payload.refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return new_tokens


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke active refresh token session",
)
async def logout(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    ip_address = request.client.host if request.client else None
    token_record = await AuthService.revoke_refresh_token(
        db=db,
        raw_refresh_token=payload.refresh_token,
    )
    if token_record:
        await AuditService.log_logout(
            db=db,
            user_id=token_record.user_id,
            ip_address=ip_address,
        )
        await db.commit()

    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile & memberships",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserMeResponse:
    return await AuthService.get_user_me(db=db, user_id=current_user.id)
