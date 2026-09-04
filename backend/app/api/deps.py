import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models import Membership, MembershipRole, Organization, User

http_bearer = HTTPBearer(auto_error=True)

# Role hierarchy definition: higher ranks have access to lower rank permissions
ROLE_HIERARCHY = {
    MembershipRole.ADMIN: 3,
    MembershipRole.ANALYST: 2,
    MembershipRole.VIEWER: 1,
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Extract and validate JWT access token from Authorization header.
    Returns authenticated active User entity.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token, expected_type="access")
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_current_membership(
    x_organization_id: Optional[str] = Header(
        None,
        alias="X-Organization-Id",
        description="Target Organization UUID context",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Membership:
    """
    Multi-Tenant Security Dependency:
    Validates that the authenticated user has active membership in the target organization.
    Prevents Insecure Direct Object Reference (IDOR) across tenant boundaries.
    """
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Organization-Id' header.",
        )

    try:
        org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 'X-Organization-Id' header format. Must be a valid UUID.",
        )

    stmt = (
        select(Membership)
        .where(
            Membership.organization_id == org_id,
            Membership.user_id == current_user.id,
        )
        .options(selectinload(Membership.organization))
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have membership in this organization.",
        )

    return membership


def require_roles(*allowed_roles: MembershipRole) -> Callable:
    """
    Role-Based Access Control (RBAC) Dependency Factory.
    Enforces role hierarchy (Admin >= Analyst >= Viewer) or exact role matching.
    """
    async def role_checker(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        user_rank = ROLE_HIERARCHY.get(membership.role, 0)
        min_required_rank = min(ROLE_HIERARCHY.get(r, 0) for r in allowed_roles) if allowed_roles else 0

        # Allow if user role satisfies minimum rank or is explicitly in allowed_roles
        if membership.role not in allowed_roles and user_rank < min_required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires one of: {[r.value for r in allowed_roles]}.",
            )
        return membership

    return role_checker
