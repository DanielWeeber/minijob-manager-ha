"""Async client for the Minijob-Manager portal (Keycloak OIDC + JSON backend)."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import (
    API_BASE,
    AUTH_URL,
    CLIENT_ID,
    PORTAL_ORIGIN,
    REDIRECT_URI,
    TOKEN_URL,
)

_FORM_ACTION = re.compile(r'<form[^>]*id="form"[^>]*action="([^"]+)"')
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class MinijobError(Exception):
    """Base error."""


class MinijobAuthError(MinijobError):
    """Credentials or code rejected / session expired."""


class MinijobConnectionError(MinijobError):
    """Portal not reachable or unexpected response."""


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(72)[:96]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def parse_form_action(page: str) -> str | None:
    """Return the action URL of the Keycloak login form."""
    match = _FORM_ACTION.search(page)
    return html.unescape(match.group(1)) if match else None


def gp_id_from_token(access_token: str) -> str:
    """Business partner id the portal expects in the `gp-id` header."""
    try:
        payload = access_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return str(claims["gprollen"][0]["geschaeftspartnerId"])
    except (IndexError, KeyError, ValueError) as err:
        raise MinijobAuthError("No business partner in token") from err


def tokens_from_response(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a token endpoint response to storable values."""
    now = time.time()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": now + int(data["expires_in"]),
        "refresh_expires_at": now + int(data.get("refresh_expires_in", 1800)),
    }


class MinijobLogin:
    """Interactive login: password step, then e-mail OTP step."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session  # must have its own cookie jar
        self._verifier, self._challenge = _pkce()
        self._otp_action: str | None = None

    async def start(self, username: str, password: str) -> None:
        """Submit username/password; the portal then e-mails an OTP."""
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": secrets.token_hex(16),
            "response_mode": "fragment",
            "response_type": "code",
            "scope": "openid",
            "nonce": secrets.token_hex(16),
            "prompt": "login",
            "code_challenge": self._challenge,
            "code_challenge_method": "S256",
        }
        try:
            async with self._session.get(
                f"{AUTH_URL}?{urlencode(params)}", timeout=_TIMEOUT
            ) as resp:
                page = await resp.text()
            action = parse_form_action(page)
            if not action:
                raise MinijobConnectionError("Login form not found")
            async with self._session.post(
                action,
                data={"username": username, "password": password, "submit": ""},
                headers={"Origin": "https://iam.minijob-manager.de"},
                allow_redirects=False,
                timeout=_TIMEOUT,
            ) as resp:
                page = await resp.text()
                status = resp.status
        except aiohttp.ClientError as err:
            raise MinijobConnectionError(str(err)) from err
        if status == 302:
            raise MinijobConnectionError("Unexpected login without OTP step")
        if 'name="code_1"' not in page:
            raise MinijobAuthError("Invalid username or password")
        self._otp_action = parse_form_action(page)
        if not self._otp_action:
            raise MinijobConnectionError("OTP form not found")

    async def finish(self, code: str) -> dict[str, Any]:
        """Submit the OTP and exchange the authorization code for tokens."""
        if not self._otp_action:
            raise MinijobConnectionError("Login not started")
        code = code.strip().replace(" ", "")
        data = {f"code_{i + 1}": c for i, c in enumerate(code)}
        data.update({"code_sum": code, "submit": ""})
        try:
            async with self._session.post(
                self._otp_action,
                data=data,
                headers={"Origin": "https://iam.minijob-manager.de"},
                allow_redirects=False,
                timeout=_TIMEOUT,
            ) as resp:
                location = resp.headers.get("Location", "")
                status = resp.status
            if status != 302 or "code=" not in location:
                raise MinijobAuthError("Invalid OTP code")
            auth_code = parse_qs(urlparse(location).fragment).get("code", [""])[0]
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": self._verifier,
                },
                headers={"Origin": PORTAL_ORIGIN},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    raise MinijobAuthError("Token exchange failed")
                return tokens_from_response(await resp.json())
        except aiohttp.ClientError as err:
            raise MinijobConnectionError(str(err)) from err


class MinijobClient:
    """Authenticated API client; refreshes tokens transparently."""

    def __init__(
        self, session: aiohttp.ClientSession, tokens: dict[str, Any]
    ) -> None:
        self._session = session
        self.tokens = dict(tokens)

    async def _refresh(self) -> None:
        try:
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.tokens["refresh_token"],
                    "client_id": CLIENT_ID,
                },
                headers={"Origin": PORTAL_ORIGIN},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401):
                    raise MinijobAuthError("Session expired, new login required")
                if resp.status != 200:
                    raise MinijobConnectionError(f"Token refresh HTTP {resp.status}")
                self.tokens = tokens_from_response(await resp.json())
        except aiohttp.ClientError as err:
            raise MinijobConnectionError(str(err)) from err

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET an /ext endpoint."""
        if time.time() > self.tokens["expires_at"] - 60:
            await self._refresh()
        try:
            async with self._session.get(
                f"{API_BASE}/{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self.tokens['access_token']}",
                    "Accept": "application/json",
                    "Origin": PORTAL_ORIGIN,
                    "gp-id": gp_id_from_token(self.tokens["access_token"]),
                },
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise MinijobAuthError("Unauthorized")
                if resp.status != 200:
                    raise MinijobConnectionError(f"{path}: HTTP {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise MinijobConnectionError(str(err)) from err

    async def get_all_pages(self, path: str, params: dict[str, Any]) -> list[Any]:
        """Collect all `content` items of a paginated endpoint."""
        items: list[Any] = []
        offset = 0
        while True:
            page = await self.get(path, {**params, "limit": 100, "offset": offset})
            content = page.get("content", [])
            items.extend(content)
            if page.get("last", True) or not content:
                return items
            offset += len(content)
