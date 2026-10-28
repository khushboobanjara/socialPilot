from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import secrets

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.social_account import OAuthState, SocialAccount
from app.models.user import User

router = APIRouter(tags=["Social account connections"])
PLATFORMS = {"instagram", "facebook", "linkedin"}


def _fernet() -> Fernet:
    key = settings.social_token_encryption_key.strip()
    if not key:
        raise HTTPException(503, "Social token encryption is not configured. Set SOCIAL_TOKEN_ENCRYPTION_KEY in .env before connecting accounts.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(503, "SOCIAL_TOKEN_ENCRYPTION_KEY is invalid. Generate a Fernet key and restart the app.") from exc


def _platform_config(platform: str):
    if platform in ("facebook", "instagram"):
        if not settings.meta_app_id or not settings.meta_app_secret:
            raise HTTPException(503, "Meta OAuth is not configured. Add META_APP_ID and META_APP_SECRET to .env.")
        return settings.meta_app_id, settings.meta_app_secret
    if platform == "linkedin":
        if not settings.linkedin_client_id or not settings.linkedin_client_secret:
            raise HTTPException(503, "LinkedIn OAuth is not configured. Add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET to .env.")
        return settings.linkedin_client_id, settings.linkedin_client_secret
    raise HTTPException(404, "Unsupported platform")


def _callback_uri(platform: str) -> str:
    if platform == "linkedin": return settings.linkedin_redirect_uri
    if platform == "instagram": return settings.meta_instagram_redirect_uri
    return settings.meta_redirect_uri


@router.get("/api/integrations")
def list_integrations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(SocialAccount).where(SocialAccount.owner_id == user.id)).all()
    connected = {r.platform: r for r in rows}
    result = []
    for platform in ("instagram", "facebook", "linkedin"):
        row = connected.get(platform)
        configured = bool((settings.linkedin_client_id and settings.linkedin_client_secret) if platform == "linkedin" else (settings.meta_app_id and settings.meta_app_secret))
        result.append({"platform": platform, "configured": configured, "connected": bool(row and row.status == "connected"),
            "account_name": row.account_name if row else None, "status": row.status if row else "not_connected",
            "connected_at": row.connected_at if row else None,
            "note": "Instagram publishing requires a professional Instagram account linked to a Facebook Page and approved Meta permissions." if platform == "instagram" else None})
    return result


@router.get("/api/integrations/{platform}/connect")
def start_connect(platform: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unsupported platform")
    client_id, _ = _platform_config(platform)
    _fernet()  # Fail before redirecting if tokens could not be stored securely.
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(owner_id=user.id, platform=platform, state=state,
                      expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).replace(tzinfo=None), used=0))
    db.commit()
    redirect_uri = _callback_uri(platform)
    if platform == "linkedin":
        params = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
                  "state": state, "scope": "openid profile w_member_social"}
        url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)
    else:
        scopes = ("pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish"
                  if platform == "instagram" else "pages_show_list,pages_read_engagement,pages_manage_posts")
        params = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state,
                  "response_type": "code", "scope": scopes}
        url = f"https://www.facebook.com/{settings.meta_graph_version}/dialog/oauth?" + urlencode(params)
    return {"authorization_url": url}


@router.get("/oauth/{platform}/callback", response_class=HTMLResponse)
async def oauth_callback(platform: str, request: Request, code: str | None = None, state: str | None = None,
                         error: str | None = None, error_description: str | None = None,
                         db: Session = Depends(get_db)):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unsupported platform")
    if error:
        return HTMLResponse(_callback_page(False, f"Authorization was declined: {error_description or error}"), status_code=400)
    if not code or not state:
        return HTMLResponse(_callback_page(False, "Missing authorization code or state."), status_code=400)
    state_row = db.scalar(select(OAuthState).where(OAuthState.state == state, OAuthState.platform == platform))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not state_row or state_row.used or state_row.expires_at < now:
        return HTMLResponse(_callback_page(False, "This authorization link is invalid or expired. Return to SocialPilot AI and try again."), status_code=400)
    state_row.used = 1
    db.commit()
    try:
        client_id, client_secret = _platform_config(platform)
        redirect_uri = _callback_uri(platform)
        async with httpx.AsyncClient(timeout=20.0) as client:
            if platform == "linkedin":
                token_response = await client.post("https://www.linkedin.com/oauth/v2/accessToken", data={
                    "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                    "client_id": client_id, "client_secret": client_secret})
            else:
                token_response = await client.get(f"https://graph.facebook.com/{settings.meta_graph_version}/oauth/access_token", params={
                    "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "code": code})
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data["access_token"]
            if platform == "linkedin":
                profile_response = await client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
            else:
                profile_response = await client.get(f"https://graph.facebook.com/{settings.meta_graph_version}/me", params={"fields": "id,name", "access_token": access_token})
            profile_response.raise_for_status()
            profile = profile_response.json()
        expires = token_data.get("expires_in")
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=int(expires))).replace(tzinfo=None) if expires else None
        row = db.scalar(select(SocialAccount).where(SocialAccount.owner_id == state_row.owner_id, SocialAccount.platform == platform))
        encrypted = _fernet().encrypt(access_token.encode("utf-8")).decode("ascii")
        if row is None:
            row = SocialAccount(owner_id=state_row.owner_id, platform=platform, remote_account_id=str(profile.get("id") or profile.get("sub") or ""),
                account_name=str(profile.get("name") or profile.get("name") or profile.get("email") or f"{platform.title()} account"),
                encrypted_access_token=encrypted, token_expires_at=expiry, status="connected")
            db.add(row)
        else:
            row.remote_account_id = str(profile.get("id") or profile.get("sub") or "")
            row.account_name = str(profile.get("name") or profile.get("email") or f"{platform.title()} account")
            row.encrypted_access_token = encrypted
            row.token_expires_at = expiry
            row.status = "connected"
            row.connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        message = f"{platform.title()} account authorization succeeded for {row.account_name}. You can close this page and sign in again to refresh the dashboard."
        return HTMLResponse(_callback_page(True, message))
    except HTTPException as exc:
        db.rollback()
        return HTMLResponse(_callback_page(False, str(exc.detail)), status_code=503)
    except (httpx.HTTPError, KeyError, ValueError, InvalidToken) as exc:
        db.rollback()
        return HTMLResponse(_callback_page(False, f"Connection could not be completed ({type(exc).__name__}). Check app settings, redirect URI, permissions, and provider logs."), status_code=502)


def _callback_page(success: bool, message: str) -> str:
    color = "#34d399" if success else "#fb7185"
    safe = (message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SocialPilot AI connection</title><style>body{{margin:0;background:#080a13;color:#e8eaf6;font:16px system-ui;display:grid;place-items:center;min-height:100vh}}main{{max-width:560px;margin:24px;padding:32px;background:#12152a;border:1px solid #ffffff18;border-radius:20px}}h1{{font-size:24px}}p{{color:#b9c0df;line-height:1.7}}strong{{color:{color}}}a{{color:#aab7ff}}</style></head><body><main><h1>SocialPilot AI</h1><p><strong>{'Connection status' if success else 'Connection needs attention'}</strong></p><p>{safe}</p><p><a href="/">Return to SocialPilot AI</a></p></main></body></html>'''


@router.delete("/api/integrations/{platform}")
def disconnect(platform: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unsupported platform")
    row = db.scalar(select(SocialAccount).where(SocialAccount.owner_id == user.id, SocialAccount.platform == platform))
    if row is None:
        raise HTTPException(404, "No connected account found for this platform")
    db.delete(row)
    db.commit()
    return {"status": "disconnected", "platform": platform}
