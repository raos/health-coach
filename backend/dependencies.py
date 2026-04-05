import uuid
import jwt
from datetime import datetime, timezone
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from config import settings
from database.engine import get_db
from database.models import User


def verify_token(authorization: str = Header(None)) -> dict:
    """FastAPI dependency — validates Bearer JWT and returns the decoded payload.

    The payload now includes:
        user_id  (str UUID)
        email
        name
        picture
        is_admin (bool)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    return payload


def get_user_id(token: dict = Depends(verify_token)) -> uuid.UUID:
    """Return the authenticated user's UUID. Raises 401 if missing."""
    raw = token.get("user_id")
    if not raw:
        raise HTTPException(status_code=401, detail="Token missing user_id claim.")
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid user_id in token.")


def get_current_user(
    token: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> User:
    """Return the full User ORM row for the authenticated user."""
    user_id = get_user_id(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    # Reject tokens issued before the user's last logout (session revocation)
    if user.last_logout_at:
        iat = token.get("iat")
        if iat:
            issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
            last_logout = user.last_logout_at.replace(tzinfo=timezone.utc)
            if issued_at < last_logout:
                raise HTTPException(status_code=401, detail="Session has been revoked. Please sign in again.")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that enforces is_admin=True."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
