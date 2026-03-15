import jwt
import httpx
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import RedirectResponse

from config import settings
from dependencies import verify_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


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
    code: str = Query(None),
    error: str = Query(None),
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

    # Restrict to a specific Google account if ALLOWED_EMAIL is set
    if settings.allowed_email and email != settings.allowed_email.lower():
        return RedirectResponse(
            f"{frontend}/login?error=unauthorized_email",
            status_code=302,
        )

    # Issue a JWT
    payload = {
        "sub": email,
        "email": email,
        "name": userinfo.get("name", ""),
        "picture": userinfo.get("picture", ""),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # 302 redirect with URL-encoded token so it survives intact
    return RedirectResponse(
        f"{frontend}/auth/callback?token={quote(token, safe='')}",
        status_code=302,
    )


@router.get("/me")
def get_me(user: dict = Depends(verify_token)):
    return {
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
    }
