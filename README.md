# SocialPilot AI — Week 5: Social Account Connections

Week 5 builds on the Week 4 calendar and scheduling queue. It adds a polished **Social accounts** workspace and an OAuth connection foundation for Facebook, Instagram (Meta OAuth), and LinkedIn.

## Important scope boundary

This milestone implements the OAuth authorization and encrypted token-storage foundation. **It does not publish posts to external platforms or automatically execute the schedule queue yet.** Week 6 should add platform-specific publishing adapters, account/page selection, media requirements, retry handling, and a background worker. An account appearing as connected means OAuth succeeded; it does not guarantee the provider has approved all publishing permissions.

Instagram publishing specifically requires a professional Instagram account linked to a Facebook Page and the required Meta permissions. Meta/LinkedIn developer app approval and access permissions are controlled by the providers.

## Stack and data preservation

- FastAPI + SQLAlchemy
- **MySQL only** — no SQLite fallback
- Ollama local AI remains configured as before
- Existing Week 1–4 tables/data are retained
- New tables: `social_accounts`, `social_oauth_states`
- Access tokens are encrypted with Fernet before storage. Do not commit `.env` or share token values.

On startup, SQLAlchemy `create_all` creates the new tables if absent; it does not drop existing tables. Use the same database and credentials from Week 4.

## Setup on Windows PowerShell

1. Extract the ZIP into a new folder and copy your working Week 4 `.env` file into it.
2. Keep these existing values unchanged:

```env
OPSPILOT_DB_HOST=127.0.0.1
OPSPILOT_DB_PORT=3306
OPSPILOT_DB_NAME=ai_social_assistant
OPSPILOT_DB_USER=root
OPSPILOT_DB_PASSWORD=your_actual_mysql_password
JWT_SECRET_KEY=your_existing_jwt_secret
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
```

3. Install dependencies (reuse your existing virtual environment if it works):

```powershell
pip install -r requirements.txt
```

4. Generate a Fernet encryption key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the generated key into `SOCIAL_TOKEN_ENCRYPTION_KEY` in `.env`. Keep it secret and stable. **If this key is lost, stored OAuth tokens cannot be decrypted.** Do not rotate it without a token re-encryption plan.

5. Create developer apps with Meta and/or LinkedIn, then fill the matching values from `.env.example`. Leave a platform unconfigured if you do not have its app credentials yet.

6. Configure the exact OAuth redirect URLs in the provider dashboard:

- `http://127.0.0.1:8000/oauth/facebook/callback`
- `http://127.0.0.1:8000/oauth/instagram/callback`
- `http://127.0.0.1:8000/oauth/linkedin/callback`

For live external OAuth, providers may require HTTPS and a public callback URL; localhost is intended for development only. The redirect URI sent by SocialPilot must match the one registered in the developer app exactly.

7. Start the application:

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Sign in with your existing account and open **Social accounts**.

## Week 5 workflow

1. Open Social accounts.
2. Select Connect for a platform whose developer credentials are configured.
3. Complete the provider's official authorization screen.
4. The callback exchanges the authorization code, retrieves basic account identity, encrypts the token, and stores the connection in MySQL.
5. Return to the app and sign in again to refresh the connection list (the current app keeps its access token in memory rather than persisting it in browser storage).
6. Disconnect an account from the Social accounts panel when needed.

OAuth state values expire after 10 minutes and are single-use. The API never returns stored access tokens to the frontend.

## API endpoints

- `GET /api/integrations` — authenticated connection status, without tokens
- `GET /api/integrations/{platform}/connect` — creates a short-lived OAuth state and returns the provider authorization URL
- `GET /oauth/{platform}/callback` — provider OAuth callback
- `DELETE /api/integrations/{platform}` — disconnect and delete the stored token

Supported platform values: `instagram`, `facebook`, `linkedin`.

## Testing

```powershell
python -m compileall app tests
pytest -q
```

This package should be tested against your actual MySQL database. OAuth end-to-end tests additionally require real developer app credentials and provider permissions; without those, the UI will correctly show that setup is needed.

## Next milestone: Week 6

Implement actual provider publishing for approved content, beginning with one platform and its supported post formats. Add a background scheduler/worker, idempotency, retries, delivery status tracking, token refresh/revocation handling, media uploads, and provider-specific permission validation. Keep owner approval mandatory before any external publishing action.
