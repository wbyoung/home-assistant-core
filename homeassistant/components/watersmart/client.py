"""WaterSmart client to connect & scrape data."""

from __future__ import annotations

import functools
import re

import aiohttp
from bs4 import BeautifulSoup

ACCOUNT_NUMBER_RE = re.compile(r"[\d-]+")


def _authenticated(func):
    @functools.wraps(func)
    async def _pre_authenticate(self, *args, **kwargs):
        await self._authenticate_if_needed()
        return await func(self, *args, **kwargs)

    return _pre_authenticate


class AuthenticationError(Exception):
    """Authentication Error."""

    def __init__(self, errors=None) -> None:
        """Initialize."""
        self._errors = errors


class WaterSmartClient:
    """WaterSmart Client."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession = None,
    ) -> None:
        """Initialize."""
        self._hostname = hostname
        self._username = username
        self._password = password
        self._session = session or aiohttp.ClientSession()
        self._account_number = None
        self._authenticated = False

    @_authenticated
    async def async_get_account_number(self) -> str:
        """Authenticate the client."""

        return self._account_number

    @_authenticated
    async def async_get_hourly_data(self):
        """Get hourly water usage data."""

        session = self._session
        hostname = self._hostname
        response = await session.get(
            f"https://{hostname}.watersmart.com/index.php/rest/v1/Chart/RealTimeChart"
        )
        response_json = await response.json()
        data = response_json["data"]

        return data["series"]

    async def _authenticate_if_needed(self) -> None:
        if not self._authenticated:
            await self._authenticate()
        self._authenticated = True

    async def _authenticate(self) -> None:
        session = self._session
        hostname = self._hostname
        login_response = await session.post(
            f"https://{hostname}.watersmart.com/index.php/welcome/login?forceEmail=1",
            data={
                "token": "",
                "email": self._username,
                "password": self._password,
            },
        )
        login_response_text = await login_response.text()
        soup = BeautifulSoup(login_response_text, "html.parser")
        errors = [error.text.strip() for error in soup.select(".error-message")]
        errors = [error for error in errors if error]

        if len(errors):
            raise AuthenticationError(errors)

        account = soup.find(id="account-navigation")
        account_number_title = account.find(
            lambda node: node.string == "Account Number"
        )
        account_section = account_number_title.parent
        account_number_title.extract()

        account_number = account_section.text.strip()

        if not ACCOUNT_NUMBER_RE.match(account_number):
            account_number = None

        self._account_number = account_number
