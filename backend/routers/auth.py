import uuid
import secrets
import jwt
import httpx
from urllib.parse import urlencode, quote, parse_qs
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from dependencies import verify_token, require_admin
from database.engine import get_db
from database.models import User, UserProfile, AuditLog, InviteCode, MagicLinkToken

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _issue_jwt(user: User, db: Session = None) -> str:
    """Issue a JWT containing user_id and onboarding_complete."""
    onboarding_complete = True  # default for backwards compat
    if db is not None:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        onboarding_complete = bool(profile.onboarding_complete) if profile else False

    payload = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture or "",
        "is_admin": user.is_admin,
        "onboarding_complete": onboarding_complete,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _get_or_create_user(db: Session, email: str, name: str, picture: str, request: Request | None = None) -> User:
    """Look up existing User by email or create a new one with a UserProfile."""
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
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

    # Auto-create UserProfile with a fresh MCP API key
    if not db.query(UserProfile).filter(UserProfile.user_id == user.id).first():
        from database.encryption import hmac_lookup as _hmac_lookup
        _new_mcp_key = str(uuid.uuid4())
        profile = UserProfile(
            user_id=user.id,
            email=email,
            mcp_api_key=_new_mcp_key,
            mcp_api_key_lookup=_hmac_lookup(_new_mcp_key),
            onboarding_complete=is_admin,  # admin skips onboarding; new users must complete it
            weekly_email_enabled=True,
        )
        db.add(profile)
        db.flush()

    db.add(AuditLog(
        user_id=user.id,
        action="account_created",
        ip_address=request.client.host if request and request.client else None,
    ))
    return user


def _validate_invite(db: Session, code: str) -> InviteCode | None:
    """Return the InviteCode row if the code is valid and available, else None."""
    if not code:
        return None
    invite = db.query(InviteCode).filter(InviteCode.code == code.strip().upper()).first()
    if not invite:
        return None
    if invite.expires_at and invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    if invite.use_count >= invite.max_uses:
        return None
    return invite


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/url")
def get_google_auth_url(invite: str = Query(default="")):
    if not settings.google_client_id:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_CLIENT_ID not configured. Add it to your .env file.",
        )
    # Encode invite code in state so callback can validate it
    state = invite.strip().upper() if invite else ""
    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    })
    return {"url": f"{GOOGLE_AUTH_URL}?{params}"}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(default=""),
    error: str = Query(None),
    db: Session = Depends(get_db),
):
    frontend = settings.frontend_url

    if error or not code:
        return RedirectResponse(
            f"{frontend}/login?error={error or 'access_denied'}",
            status_code=302,
        )

    async with httpx.AsyncClient() as http:
        token_resp = await http.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })

    if token_resp.status_code != 200:
        return RedirectResponse(f"{frontend}/login?error=token_exchange_failed", status_code=302)

    access_token = token_resp.json().get("access_token")

    async with httpx.AsyncClient() as http:
        userinfo_resp = await http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        return RedirectResponse(f"{frontend}/login?error=userinfo_failed", status_code=302)

    userinfo = userinfo_resp.json()
    email: str = userinfo.get("email", "").lower()
    name: str = userinfo.get("name", "")
    picture: str = userinfo.get("picture", "")

    # Legacy single-user gate
    if settings.allowed_email and not settings.admin_email:
        if email != settings.allowed_email.lower():
            return RedirectResponse(f"{frontend}/login?error=unauthorized_email", status_code=302)

    try:
        # Check if this is a new user
        existing_user = db.query(User).filter(User.email == email).first()
        is_new_user = existing_user is None

        # Invite code gate: only check for NEW users; existing users can always log in
        invite_code_str = state.strip().upper() if state else ""
        invite = None
        if is_new_user and invite_code_str:
            invite = _validate_invite(db, invite_code_str)
            if not invite:
                return RedirectResponse(f"{frontend}/login?error=invalid_invite", status_code=302)
        elif is_new_user and not invite_code_str:
            # New user without invite code — only allowed if admin_email matches (bootstrap)
            is_admin = bool(settings.admin_email and email == settings.admin_email.lower())
            if not is_admin:
                return RedirectResponse(f"{frontend}/login?error=invite_required", status_code=302)

        user = _get_or_create_user(db, email, name, picture, request)
        if not user.is_active:
            db.rollback()
            return RedirectResponse(f"{frontend}/login?error=account_disabled", status_code=302)

        # Mark invite as used
        if invite and is_new_user:
            invite.used_by = user.id
            invite.used_at = datetime.now(timezone.utc)
            invite.use_count = (invite.use_count or 0) + 1
            # Record on user profile
            profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            if profile:
                profile.invite_code_used = invite.code

        db.add(AuditLog(
            user_id=user.id,
            action="login",
            ip_address=request.client.host if request.client else None,
            metadata_json={"provider": "google"},
        ))
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(f"{frontend}/login?error=server_error", status_code=302)

    token = _issue_jwt(user, db)
    return RedirectResponse(
        f"{frontend}/auth/callback?token={quote(token, safe='')}",
        status_code=302,
    )


# ── Magic link ────────────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: str
    invite_code: str = ""


@router.post("/magic-link/send")
async def send_magic_link(payload: MagicLinkRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    # Check for existing user
    existing_user = db.query(User).filter(User.email == email).first()
    is_new_user = existing_user is None

    if is_new_user:
        invite = _validate_invite(db, payload.invite_code)
        allowed = {e.strip().lower() for e in settings.allowed_email.split(",") if e.strip()}
        is_privileged = (
            (settings.admin_email and email == settings.admin_email.lower()) or
            email in allowed
        )
        if not invite and not is_privileged:
            raise HTTPException(status_code=403, detail="A valid invite code is required to create an account.")

    # Generate a short-lived token
    raw_token = secrets.token_urlsafe(32)
    ml = MagicLinkToken(
        id=uuid.uuid4(),
        email=email,
        token=raw_token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        used=False,
    )
    db.add(ml)
    db.commit()

    # Send email via Resend
    magic_url = f"{settings.frontend_url}/auth/magic-link?token={raw_token}"
    try:
        from services.email_service import send_html_email
        html = f"""
        <p>Click the link below to sign in to <b>Health Coach</b>. This link expires in 15 minutes.</p>
        <p><a href="{magic_url}" style="background:#4f46e5;color:#fff;padding:12px 24px;
           border-radius:8px;text-decoration:none;font-weight:600;">Sign in to <b>Health Coach</b></a></p>
        <p style="color:#6b7280;font-size:12px;">If you didn't request this, ignore this email.</p>
        """
        send_html_email(to_address=email, subject="Sign in to Health Coach", html=html)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")

    return {"status": "sent"}


@router.get("/magic-link/verify")
def verify_magic_link(token: str = Query(...), db: Session = Depends(get_db)):
    ml = db.query(MagicLinkToken).filter(MagicLinkToken.token == token).first()
    frontend = settings.frontend_url
    if not ml or ml.used or ml.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return RedirectResponse(f"{frontend}/login?error=invalid_magic_link", status_code=302)

    ml.used = True
    db.flush()

    # Get or create user
    email = ml.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        user = existing
        user.auth_provider = "magic_link"
    else:
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=email.split("@")[0],
            auth_provider="magic_link",
            is_active=True,
            is_admin=bool(settings.admin_email and email == settings.admin_email.lower()),
        )
        db.add(user)
        db.flush()
        if not db.query(UserProfile).filter(UserProfile.user_id == user.id).first():
            from database.encryption import hmac_lookup as _hmac_lookup
            _new_mcp_key = str(uuid.uuid4())
            db.add(UserProfile(
                user_id=user.id,
                email=email,
                mcp_api_key=_new_mcp_key,
                mcp_api_key_lookup=_hmac_lookup(_new_mcp_key),
                onboarding_complete=user.is_admin,
                weekly_email_enabled=True,
            ))
            db.flush()

    db.add(AuditLog(
        user_id=user.id,
        action="login",
        metadata_json={"provider": "magic_link"},
    ))
    db.commit()

    jwt_token = _issue_jwt(user, db)
    return RedirectResponse(
        f"{frontend}/auth/callback?token={quote(jwt_token, safe='')}",
        status_code=302,
    )


# ── Invite code management (admin) ───────────────────────────────────────────

class InviteCodeCreate(BaseModel):
    code: str = ""       # if empty, auto-generate
    max_uses: int = 1
    expires_days: int = 0  # 0 = no expiry


@router.post("/invite-codes")
def create_invite_code(
    payload: InviteCodeCreate,
    admin_user: "User" = Depends(require_admin),
    db: Session = Depends(get_db),
):
    code = payload.code.strip().upper() if payload.code.strip() else secrets.token_hex(4).upper()
    if db.query(InviteCode).filter(InviteCode.code == code).first():
        raise HTTPException(status_code=409, detail="Invite code already exists.")
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_days) if payload.expires_days else None
    invite = InviteCode(
        id=uuid.uuid4(),
        code=code,
        created_by=admin_user.id,
        max_uses=payload.max_uses,
        use_count=0,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return _invite_dict(invite)


@router.get("/invite-codes")
def list_invite_codes(
    admin_user: "User" = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invites = db.query(InviteCode).order_by(InviteCode.id).all()
    return [_invite_dict(i) for i in invites]


@router.get("/validate-invite")
def validate_invite(code: str = Query(...), db: Session = Depends(get_db)):
    """Public: check if an invite code is valid (don't consume it)."""
    invite = _validate_invite(db, code)
    return {"valid": invite is not None}


def _invite_dict(invite: InviteCode) -> dict:
    return {
        "id": str(invite.id),
        "code": invite.code,
        "max_uses": invite.max_uses,
        "use_count": invite.use_count,
        "uses_remaining": max(0, invite.max_uses - (invite.use_count or 0)),
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "used_by": str(invite.used_by) if invite.used_by else None,
        "used_at": invite.used_at.isoformat() if invite.used_at else None,
    }


# ── Me + Logout ───────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(user: dict = Depends(verify_token)):
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "is_admin": user.get("is_admin", False),
        "onboarding_complete": user.get("onboarding_complete", True),
    }


@router.post("/logout")
def logout(
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user_id = user.get("user_id")
    if user_id:
        db_user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if db_user:
            db_user.last_logout_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(AuditLog(user_id=db_user.id, action="logout"))
            db.commit()
    return {"status": "ok"}


@router.post("/refresh-token")
def refresh_token(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Re-issue a JWT — useful after onboarding completion to update onboarding_complete claim."""
    db_user = db.query(User).filter(User.id == uuid.UUID(token_data["user_id"])).first()
    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=403, detail="Account not active.")
    return {"token": _issue_jwt(db_user, db)}
