"""Async client for the Cotherm/Linkio cloud API used by the Dux HP app."""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .const import API_BASE, NODE_BASE, SESSION_CHECK_INTERVAL

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class DuxError(Exception):
    """Base error."""


class DuxAuthError(DuxError):
    """Login rejected."""


class DuxConnectionError(DuxError):
    """Network or server problem (temporary)."""


# Network errors, timeouts and unreadable responses are all treated as temporary.
# aiohttp's total timeout raises TimeoutError, which is not an aiohttp.ClientError.
_TRANSIENT = (aiohttp.ClientError, TimeoutError, ValueError)


class DuxApi:
    """Minimal client: login, session check, read and write registers."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        hub_id: str,
        api_base: str = API_BASE,
        node_base: str = NODE_BASE,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.hub_id = hub_id
        self._api_base = api_base
        self._node_base = node_base
        self._token: str | None = None
        self._last_session_check: float | None = None

    @property
    def _data_url(self) -> str:
        return (
            f"{self._api_base}hubs/{self.hub_id}"
            "/plugins/esp32/modules/esp32/devices/0/data"
        )

    async def login(self) -> None:
        """Log in and store the bearer token."""
        try:
            async with self._session.post(
                f"{self._api_base}customers/connect/",
                json={"email": self._email, "password": self._password},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise DuxAuthError(f"Login rejected (HTTP {resp.status})")
                if resp.status >= 300:
                    raise DuxConnectionError(f"Login failed (HTTP {resp.status})")
                body = await resp.json(content_type=None)
        except _TRANSIENT as err:
            raise DuxConnectionError(f"Login request failed: {err!r}") from err

        token = None
        if isinstance(body, dict):
            token = body.get("token") or (body.get("customer") or {}).get("token")
        if not token:
            raise DuxConnectionError("Login response contained no token")
        self._token = token
        self._last_session_check = None

    async def _request(
        self, method: str, url: str, payload: Any = None, retry: bool = True
    ) -> Any:
        if self._token is None:
            await self.login()
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with self._session.request(
                method, url, json=payload, headers=headers, timeout=_TIMEOUT
            ) as resp:
                if resp.status in (401, 403):
                    if retry:
                        _LOGGER.debug("Token rejected, logging in again")
                        self._token = None
                        return await self._request(method, url, payload, retry=False)
                    # Refused even with a brand-new token, so the password is fine:
                    # treat as a temporary server problem, not a credentials problem.
                    raise DuxConnectionError(
                        f"Server refused request after fresh login (HTTP {resp.status})"
                    )
                if resp.status >= 300:
                    text = await resp.text()
                    raise DuxConnectionError(f"HTTP {resp.status}: {text[:200]}")
                return await resp.json(content_type=None)
        except _TRANSIENT as err:
            raise DuxConnectionError(f"Request failed: {err!r}") from err

    def reset(self) -> None:
        """Forget the token and session so the next call starts afresh."""
        self._token = None
        self._last_session_check = None

    async def session_check(self, force: bool = False) -> None:
        """Call the session check the app makes before polling."""
        now = time.monotonic()
        if (
            not force
            and self._last_session_check is not None
            and now - self._last_session_check < SESSION_CHECK_INTERVAL
        ):
            return
        try:
            await self._request(
                "POST", f"{self._node_base}/api/session/check", {"hub": self.hub_id}
            )
        except DuxConnectionError as err:
            # Not essential for reading; don't let it block a poll. Try again next time.
            _LOGGER.debug("Session check failed (continuing): %s", err)
            return
        self._last_session_check = now

    async def read_registers(self, registers: list[int]) -> dict[int, float]:
        """Read registers. Returns {register_id: value}."""
        await self.session_check()
        ids = ",".join(str(r) for r in registers)
        body = await self._request("GET", f"{self._data_url}?register={ids}")
        result: dict[int, float] = {}
        items = body.get("data") if isinstance(body, dict) else None
        for item in items or []:
            try:
                result[int(item["register"])] = item["value"]
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Ignoring unexpected item %s", item)
        return result

    async def write_registers(self, values: dict[int, int]) -> None:
        """Write registers in a single command, as the app does."""
        await self.session_check()
        payload = {
            "action": "command",
            "data": [{"register": reg, "value": val} for reg, val in values.items()],
        }
        _LOGGER.debug("Writing %s", payload)
        await self._request("POST", self._data_url, payload)
