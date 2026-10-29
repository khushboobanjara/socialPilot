from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import secrets

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.social_account import OAuthState, SocialAccount
from app.models.user import User


router = APIRouter(tags=["Social account connections"])

PLATFORMS = {"instagram", "facebook", "linkedin"}


# ---------------------------------------------------------
# Token encryption
# ---------------------------------------------------------

def _fernet() -> Fernet:
    key = settings.social_token_encryption_key.strip()

    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Social token encryption is not configured. "
                "Set SOCIAL_TOKEN_ENCRYPTION_KEY in .env."
            ),
        )

    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "SOCIAL_TOKEN_ENCRYPTION_KEY is invalid. "
                "Generate a valid Fernet key and restart the app."
            ),
        ) from exc


# ---------------------------------------------------------
# OAuth configuration
# ---------------------------------------------------------

def _platform_config(platform: str):
    """Return the client ID and secret for the requested platform."""

    if platform == "instagram":
        if not settings.instagram_app_id or not settings.instagram_app_secret:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Instagram Login is not configured. "
                    "Add INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET to .env."
                ),
            )

        return (
            settings.instagram_app_id,
            settings.instagram_app_secret,
        )

    if platform == "facebook":
        if not settings.meta_app_id or not settings.meta_app_secret:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Facebook OAuth is not configured. "
                    "Add META_APP_ID and META_APP_SECRET to .env."
                ),
            )

        return settings.meta_app_id, settings.meta_app_secret

    if platform == "linkedin":
        if (
            not settings.linkedin_client_id
            or not settings.linkedin_client_secret
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    "LinkedIn OAuth is not configured. "
                    "Add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET "
                    "to .env."
                ),
            )

        return (
            settings.linkedin_client_id,
            settings.linkedin_client_secret,
        )

    raise HTTPException(status_code=404, detail="Unsupported platform")


def _callback_uri(platform: str) -> str:
    """Return the registered OAuth callback URL."""

    if platform == "linkedin":
        return settings.linkedin_redirect_uri

    if platform == "instagram":
        return settings.meta_instagram_redirect_uri

    return settings.meta_redirect_uri


# ---------------------------------------------------------
# List connected social accounts
# ---------------------------------------------------------

@router.get("/api/integrations")
def list_integrations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(SocialAccount).where(
            SocialAccount.owner_id == user.id
        )
    ).all()

    connected = {row.platform: row for row in rows}

    result = []

    for platform in ("instagram", "facebook", "linkedin"):
        row = connected.get(platform)

        if platform == "instagram":
            configured = bool(
                settings.instagram_app_id
                and settings.instagram_app_secret
            )

        elif platform == "facebook":
            configured = bool(
                settings.meta_app_id
                and settings.meta_app_secret
            )

        else:
            configured = bool(
                settings.linkedin_client_id
                and settings.linkedin_client_secret
            )

        result.append(
            {
                "platform": platform,
                "configured": configured,
                "connected": bool(
                    row and row.status == "connected"
                ),
                "account_name": row.account_name if row else None,
                "status": (
                    row.status if row else "not_connected"
                ),
                "connected_at": (
                    row.connected_at if row else None
                ),
                "note": (
                    "Instagram Login requires the appropriate "
                    "Instagram account permissions and app configuration."
                    if platform == "instagram"
                    else None
                ),
            }
        )

    return result


# ---------------------------------------------------------
# Start OAuth connection
# ---------------------------------------------------------

@router.get("/api/integrations/{platform}/connect")
def start_connect(
    platform: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if platform not in PLATFORMS:
        raise HTTPException(
            status_code=404,
            detail="Unsupported platform",
        )

    client_id, _ = _platform_config(platform)

    # Fail before redirecting if tokens cannot be stored securely.
    _fernet()

    state = secrets.token_urlsafe(32)

    db.add(
        OAuthState(
            owner_id=user.id,
            platform=platform,
            state=state,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=10)
            ).replace(tzinfo=None),
            used=0,
        )
    )
    db.commit()

    redirect_uri = _callback_uri(platform)

    # LinkedIn OAuth
    if platform == "linkedin":
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "openid profile w_member_social",
        }

        url = (
            "https://www.linkedin.com/oauth/v2/authorization?"
            + urlencode(params)
        )

    # Instagram Login — separate from Facebook Login
    elif platform == "instagram":
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": (
                "instagram_business_basic,"
                "instagram_business_content_publish"
            ),
            "state": state,
        }

        url = (
            "https://www.instagram.com/oauth/authorize?"
            + urlencode(params)
        )

    # Facebook Login
    else:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": (
                "pages_show_list,"
                "pages_read_engagement,"
                "pages_manage_posts"
            ),
        }

        url = (
            f"https://www.facebook.com/"
            f"{settings.meta_graph_version}/dialog/oauth?"
            + urlencode(params)
        )

    return {"authorization_url": url}


# ---------------------------------------------------------
# OAuth callback
# ---------------------------------------------------------

@router.get(
    "/oauth/{platform}/callback",
    response_class=HTMLResponse,
)
async def oauth_callback(
    platform: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    if platform not in PLATFORMS:
        raise HTTPException(
            status_code=404,
            detail="Unsupported platform",
        )

    if error:
        return HTMLResponse(
            _callback_page(
                False,
                f"Authorization was declined: "
                f"{error_description or error}",
            ),
            status_code=400,
        )

    if not code or not state:
        return HTMLResponse(
            _callback_page(
                False,
                "Missing authorization code or state.",
            ),
            status_code=400,
        )

    # Validate OAuth state to prevent callback forgery.
    state_row = db.scalar(
        select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.platform == platform,
        )
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if (
        not state_row
        or state_row.used
        or state_row.expires_at < now
    ):
        return HTMLResponse(
            _callback_page(
                False,
                (
                    "This authorization link is invalid or expired. "
                    "Return to SocialPilot AI and try again."
                ),
            ),
            status_code=400,
        )

    # Mark the state as used before exchanging the code.
    state_row.used = 1
    db.commit()

    try:
        client_id, client_secret = _platform_config(platform)
        redirect_uri = _callback_uri(platform)

        async with httpx.AsyncClient(timeout=30.0) as client:

            # -------------------------------------------------
            # LinkedIn token exchange and profile
            # -------------------------------------------------
            if platform == "linkedin":
                token_response = await client.post(
                    "https://www.linkedin.com/oauth/v2/accessToken",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": client_id,
                        "client_secret": client_secret,
                    },
                )

                token_response.raise_for_status()
                token_data = token_response.json()

                access_token = token_data["access_token"]

                profile_response = await client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={
                        "Authorization": f"Bearer {access_token}"
                    },
                )

                profile_response.raise_for_status()
                profile = profile_response.json()

            # -------------------------------------------------
            # Instagram Login token exchange and profile
            # -------------------------------------------------
            elif platform == "instagram":

                # Exchange authorization code for a short-lived token.
                token_response = await client.post(
                    "https://api.instagram.com/oauth/access_token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                )

                token_response.raise_for_status()
                short_token_data = token_response.json()

                short_access_token = short_token_data["access_token"]

                # Exchange for a long-lived Instagram access token.
                long_token_response = await client.get(
                    "https://graph.instagram.com/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": client_secret,
                        "access_token": short_access_token,
                    },
                )

                long_token_response.raise_for_status()
                long_token_data = long_token_response.json()

                access_token = long_token_data["access_token"]

                # Keep expiry information from the long-lived token
                # response when the provider supplies it.
                token_data = {
                    **short_token_data,
                    **long_token_data,
                }

                # Retrieve the Instagram profile.
                profile_response = await client.get(
                    "https://graph.instagram.com/me",
                    params={
                        "fields": "user_id,username",
                        "access_token": access_token,
                    },
                )

                profile_response.raise_for_status()
                profile = profile_response.json()

                # Normalize profile fields for database storage.
                profile["id"] = (
                    profile.get("user_id")
                    or profile.get("id")
                    or long_token_data.get("user_id")
                    or short_token_data.get("user_id")
                    or ""
                )

                profile["name"] = (
                    profile.get("username")
                    or "Instagram account"
                )

            # -------------------------------------------------
            # Facebook token exchange and profile
            # -------------------------------------------------
            else:
                token_response = await client.get(
                    (
                        "https://graph.facebook.com/"
                        f"{settings.meta_graph_version}/oauth/access_token"
                    ),
                    params={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                )

                token_response.raise_for_status()
                token_data = token_response.json()

                access_token = token_data["access_token"]

                profile_response = await client.get(
                    (
                        "https://graph.facebook.com/"
                        f"{settings.meta_graph_version}/me"
                    ),
                    params={
                        "fields": "id,name",
                        "access_token": access_token,
                    },
                )

                profile_response.raise_for_status()
                profile = profile_response.json()

        # -----------------------------------------------------
        # Calculate token expiry
        # -----------------------------------------------------
        expires = token_data.get("expires_in")

        expiry = (
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(expires))
            ).replace(tzinfo=None)
            if expires
            else None
        )

        # -----------------------------------------------------
        # Encrypt access token before saving it
        # -----------------------------------------------------
        encrypted = _fernet().encrypt(
            access_token.encode("utf-8")
        ).decode("ascii")

        remote_account_id = str(
            profile.get("id")
            or profile.get("sub")
            or ""
        )

        account_name = str(
            profile.get("name")
            or profile.get("username")
            or profile.get("email")
            or f"{platform.title()} account"
        )

        # -----------------------------------------------------
        # Create or update the connected account
        # -----------------------------------------------------
        row = db.scalar(
            select(SocialAccount).where(
                SocialAccount.owner_id == state_row.owner_id,
                SocialAccount.platform == platform,
            )
        )

        if row is None:
            row = SocialAccount(
                owner_id=state_row.owner_id,
                platform=platform,
                remote_account_id=remote_account_id,
                account_name=account_name,
                encrypted_access_token=encrypted,
                token_expires_at=expiry,
                status="connected",
            )

            db.add(row)

        else:
            row.remote_account_id = remote_account_id
            row.account_name = account_name
            row.encrypted_access_token = encrypted
            row.token_expires_at = expiry
            row.status = "connected"
            row.connected_at = (
                datetime.now(timezone.utc).replace(tzinfo=None)
            )

        db.commit()

        message = (
            f"{platform.title()} account authorization succeeded "
            f"for {row.account_name}. "
            "You can close this page and return to SocialPilot AI."
        )

        return HTMLResponse(
            _callback_page(True, message)
        )

    except HTTPException as exc:
        db.rollback()

        return HTMLResponse(
            _callback_page(False, str(exc.detail)),
            status_code=503,
        )

    except httpx.HTTPStatusError as exc:
        db.rollback()

        # Log only the provider status code, not tokens or secrets.
        status_code = exc.response.status_code

        return HTMLResponse(
            _callback_page(
                False,
                (
                    "The provider rejected the OAuth request "
                    f"(HTTP {status_code}). Check the app configuration, "
                    "redirect URI, permissions, and provider settings."
                ),
            ),
            status_code=502,
        )

    except (
        httpx.HTTPError,
        KeyError,
        ValueError,
        InvalidToken,
    ) as exc:
        db.rollback()

        return HTMLResponse(
            _callback_page(
                False,
                (
                    "Connection could not be completed "
                    f"({type(exc).__name__}). Check the OAuth settings "
                    "and provider configuration."
                ),
            ),
            status_code=502,
        )

    except Exception:
        db.rollback()

        return HTMLResponse(
            _callback_page(
                False,
                (
                    "An unexpected error occurred while saving "
                    "the social account. Check the application logs."
                ),
            ),
            status_code=500,
        )


# ---------------------------------------------------------
# OAuth callback result page
# ---------------------------------------------------------

def _callback_page(success: bool, message: str) -> str:
    color = "#34d399" if success else "#fb7185"

    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>SocialPilot AI connection</title>
        <style>
            body {{
                margin: 0;
                background: #080a13;
                color: #e8eaf6;
                font: 16px system-ui;
                display: grid;
                place-items: center;
                min-height: 100vh;
            }}
            main {{
                max-width: 560px;
                margin: 24px;
                padding: 32px;
                background: #12152a;
                border: 1px solid #ffffff18;
                border-radius: 20px;
            }}
            h1 {{
                font-size: 24px;
            }}
            p {{
                color: #b9c0df;
                line-height: 1.7;
            }}
            strong {{
                color: {color};
            }}
            a {{
                color: #aab7ff;
            }}
        </style>
    </head>
    <body>
        <main>
            <h1>SocialPilot AI</h1>
            <p>
                <strong>
                    {"Connection successful" if success else "Connection needs attention"}
                </strong>
            </p>
            <p>{safe}</p>
            <p><a href="/">Return to SocialPilot AI</a></p>
        </main>
    </body>
    </html>
    """


# ---------------------------------------------------------
# Disconnect social account
# ---------------------------------------------------------

@router.delete("/api/integrations/{platform}")
def disconnect(
    platform: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if platform not in PLATFORMS:
        raise HTTPException(
            status_code=404,
            detail="Unsupported platform",
        )

    row = db.scalar(
        select(SocialAccount).where(
            SocialAccount.owner_id == user.id,
            SocialAccount.platform == platform,
        )
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No connected account found for this platform",
        )

    db.delete(row)
    db.commit()

    return {
        "status": "disconnected",
        "platform": platform,
    }