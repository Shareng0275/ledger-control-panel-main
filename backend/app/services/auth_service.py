import re
import uuid
from typing import Optional
from fastapi import HTTPException, status
import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import AuditLog, Membership, MembershipRole, Organization, RefreshToken, User
from app.schemas.auth import (
    MembershipResponse,
    RegisterRequest,
    TokenResponse,
    UserMeResponse,
    UserResponse,
)
from app.utils.timezone import ensure_utc, utc_now


def generate_slug(name: str) -> str:
    """Generate a clean URL-friendly slug from an organization name."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    slug = re.sub(r"[-\s]+", "-", clean)
    return slug or "org"


class AuthService:
    @staticmethod
    async def register_user(
        db: AsyncSession,
        register_data: RegisterRequest,
        ip_address: Optional[str] = None,
    ) -> User:
        """Register a new user, create an organization, and assign admin membership."""
        normalized_email = register_data.email.strip().lower()

        # Check for existing email
        stmt = select(User).where(func.lower(User.email) == normalized_email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        # Hash password securely with Argon2
        hashed_pwd = hash_password(register_data.password)

        # Create user
        user = User(
            id=uuid.uuid4(),
            email=normalized_email,
            password_hash=hashed_pwd,
            full_name=register_data.full_name.strip(),
            is_active=True,
        )
        db.add(user)

        # Create Organization
        org_name = register_data.organization_name.strip() if register_data.organization_name else f"{user.full_name}'s Org"
        base_slug = generate_slug(org_name)
        slug = base_slug

        # Ensure slug uniqueness
        counter = 1
        while True:
            slug_stmt = select(Organization).where(Organization.slug == slug)
            slug_res = await db.execute(slug_stmt)
            if not slug_res.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        organization = Organization(
            id=uuid.uuid4(),
            name=org_name,
            slug=slug,
        )
        db.add(organization)

        # Assign Admin Membership
        membership = Membership(
            id=uuid.uuid4(),
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.ADMIN,
        )
        db.add(membership)

        # Append audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization.id,
            actor_id=user.id,
            action="user.registered",
            entity_type="User",
            entity_id=user.id,
            details={"email": normalized_email, "role": "admin"},
            ip_address=ip_address,
        )
        db.add(audit)

        await db.flush()
        return user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Authenticate user with email and password."""
        normalized_email = email.strip().lower()
        stmt = select(User).where(func.lower(User.email) == normalized_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        return user

    @staticmethod
    async def create_tokens_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        user: Optional[User] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """Issue an access token and stateful rotated refresh token."""
        access_token = create_access_token(user_id=user_id)
        raw_refresh, refresh_hash, expires_at = create_refresh_token(user_id=user_id)

        token_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            is_revoked=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(token_record)
        await db.flush()

        if user is None:
            user_stmt = select(User).where(User.id == user_id)
            res = await db.execute(user_stmt)
            user = res.scalar_one_or_none()

        user_dto = UserResponse.model_validate(user) if user else None

        return TokenResponse(
            access_token=access_token,
            token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_dto,
        )

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """Validate and rotate an existing refresh token."""
        try:
            payload = decode_token(raw_refresh_token, expected_type="refresh")
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = uuid.UUID(payload["sub"])
        token_digest = hash_token(raw_refresh_token)

        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_digest)
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        now = utc_now()
        if not token_record or token_record.is_revoked or ensure_utc(token_record.expires_at) < now:
            # If revoked token is reused, log potential token theft
            if token_record and token_record.is_revoked:
                logger.warning(f"Revoked refresh token reuse detected for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Invalidate old token (Rotation)
        token_record.is_revoked = True

        # Check user is still active
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        # Issue new token pair
        return await AuthService.create_tokens_for_user(
            db=db,
            user_id=user.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    @staticmethod
    async def revoke_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> None:
        """Revoke a refresh token upon logout."""
        token_digest = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_digest)
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()
        if token_record:
            token_record.is_revoked = True
            await db.flush()

    @staticmethod
    async def get_user_me(db: AsyncSession, user_id: uuid.UUID) -> UserMeResponse:
        """Fetch user details along with all active organization memberships."""
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.memberships).selectinload(Membership.organization)
            )
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        memberships_data: list[MembershipResponse] = []
        for m in user.memberships:
            if m.organization:
                memberships_data.append(
                    MembershipResponse(
                        id=m.id,
                        organization_id=m.organization_id,
                        organization_name=m.organization.name,
                        organization_slug=m.organization.slug,
                        role=m.role,
                        created_at=m.created_at,
                    )
                )

        return UserMeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            memberships=memberships_data,
        )
