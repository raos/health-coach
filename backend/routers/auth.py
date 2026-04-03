import uuid
import jwt
import httpx
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from config import settings
from dependencies import verify_token
from database.engine import get_db
from database.models import User, UserProfile, AuditLog

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _issue_jwt(user: User) -> str:
    """Issue a JWT containing user_id so every protected route can scope queries."""
    payload = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture or "",
        "is_admin": user.is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _get_or_create_user(db: Session, email: str, name: str, picture: str, request: Request | None = None) -> User:
    """Look up existing User by email or create a new one."""
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Update name/picture in case they changed on Google
        user.name = name
        user.picture = picture
        db.flush()
        return user

    is_admin = bool(settings.admin_email and email == settings.admin_email.lower())
    user = User(
        id=uuid.uuid4(),
        email=email,
        name=name,
        picture=picture,
        auth_provider="google",
        is_active=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.flush()

    # Log the account creation
    db.add(AuditLog(
        user_id=user.id,
        action="account_created",
        ip_address=request.client.host if request and request.client else None,
    ))
    return user


@router.get("/google/url")
def get_google_auth_url():
    if not settings.google_client_id:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_CLIENT_ID not configured. Add it to your .env file.",
        )
    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return {"url": f"{GOOGLE_AUTH_URL}?{params}"}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db),
):
    frontend = settings.frontend_url

    if error or not code:
        return RedirectResponse(
            f"{frontend}/login?error={error or 'access_denied'}",
            status_code=302,
        )

    # Exchange authorization code for access token
    async with httpx.AsyncClient() as http:
        token_resp = await http.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })

    if token_resp.status_code != 200:
        return RedirectResponse(
            f"{frontend}/login?error=token_exchange_failed",
            status_code=302,
        )

    access_token = token_resp.json().get("access_token")

    # Fetch Google user info
    async with httpx.AsyncClient() as http:
        userinfo_resp = await http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        return RedirectResponse(
            f"{frontend}/login?error=userinfo_failed",
            status_code=302,
        )

    userinfo = userinfo_resp.json()
    email: str = userinfo.get("email", "").lower()
    name: str = userinfo.get("name", "")
    picture: str = userinfo.get("picture", "")

    # Legacy single-user gate (kept for compat; admin_email takes precedence)
    if settings.allowed_email and not settings.admin_email:
        if email != settings.allowed_email.lower():
            return RedirectResponse(
                f"{frontend}/login?error=unauthorized_email",
                status_code=302,
            )

    # Get or create the User row
    try:
        user = _get_or_create_user(db, email, name, picture, request)
        if not user.is_active:
            db.rollback()
            return RedirectResponse(
                f"{frontend}/login?error=account_disabled",
                status_code=302,
            )
        db.add(AuditLog(
            user_id=user.id,
            action="login",
            ip_address=request.client.host if request.client else None,
            metadata_json={"provider": "google"},
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            f"{frontend}/login?error=server_error",
            status_code=302,
        )

    token = _issue_jwt(user)

    return RedirectResponse(
        f"{frontend}/auth/callback?token={quote(token, safe='')}",
        status_code=302,
    )


@router.get("/me")
def get_me(user: dict = Depends(verify_token)):
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "is_admin": user.get("is_admin", False),
    }


@router.post("/logout")
def logout(
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Invalidate future tokens by setting last_logout_at on the User row."""
    user_id = user.get("user_id")
    if user_id:
        db_user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if db_user:
            db_user.last_logout_at = datetime.utcnow()
            db.add(AuditLog(
                user_id=db_user.id,
                action="logout",
            ))
            db.commit()
    return {"status": "ok"}
