"""Constants for the Minijob-Manager integration."""

from datetime import timedelta

DOMAIN = "minijob_manager"

IAM_BASE = "https://iam.minijob-manager.de/realms/minijobzentrale/protocol/openid-connect"
AUTH_URL = f"{IAM_BASE}/auth"
TOKEN_URL = f"{IAM_BASE}/token"
API_BASE = "https://api.minijob-manager.de/ext"
CLIENT_ID = "MJZLogin"
REDIRECT_URI = "https://www.minijob-manager.de/startseite"
PORTAL_ORIGIN = "https://www.minijob-manager.de"

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_REFRESH_EXPIRES_AT = "refresh_expires_at"

# Refresh tokens live 30 minutes (SSO idle); polling must be more frequent.
UPDATE_INTERVAL = timedelta(minutes=10)

# Monthly Minijob earnings limit (2026). Yearly limit is 12x this value.
MINIJOB_MONTHLY_LIMIT = 603.0
