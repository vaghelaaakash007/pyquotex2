import asyncio
import logging
from typing import Any, Callable

from ._api._constants import DEFAULT_TIMEOUT
from ._api.account import AccountMixin
from ._api.history import HistoryMixin
from ._api.realtime import RealtimeMixin
from ._api.trading import TradingMixin
from .api import QuotexAPI
from .config import (
    load_session,
    update_session,
    resource_path
)
from .global_value import AuthStatus
from .utils.account_type import AccountType
from .utils.optimization import OptimizedQuotexMixin

logger = logging.getLogger(__name__)

# Migration note (refactor/architecture Phase 2):
# Several streaming-loop yields (await asyncio.sleep(0.2)) remain in this
# file. They are NOT polling-for-completion patterns — they are pacing for
# continuous data flow inside start_*_stream methods. Migrating them to
# event-driven waits would change semantics (the streams are infinite loops,
# not one-shot waits). The deferred TODOs on individual methods document
# the specific WS-producer gaps where event-driven migration IS desired
# but blocked by a missing producer.


class Quotex(AccountMixin, TradingMixin, HistoryMixin, RealtimeMixin, OptimizedQuotexMixin):

    def __init__(
            self,
            email: str,
            password: str,
            host: str = "qxbroker.com",
            lang: str = "pt",
            user_agent: str = "Quotex/1.0",
            root_path: str = ".",
            user_data_dir: str = "browser",
            asset_default: str = "EURUSD",
            period_default: int = 60,
            proxies: dict[str, str] | None = None,
            on_otp_callback: Callable | None = None
    ):
        """
        Initializes the Quotex stable API wrapper.

        Args:
            email (str): User email.
            password (str): User password.
            host (str): Broker hostname. Defaults to "qxbroker.com".
            lang (str): Language code. Defaults to "pt".
            user_agent (str): Browser User-Agent. Defaults to "Quotex/1.0".
            root_path (str): Root directory for local storage. Defaults to ".".
            user_data_dir (str): Directory for browser profile data.
                Defaults to "browser".
            asset_default (str): Default asset to use. Defaults to "EURUSD".
            period_default (int): Default candle period in seconds.
                Defaults to 60.
            proxies (dict, optional): Proxy configuration.
            on_otp_callback (callable, optional): Callback for 2FA/OTP input.
        """
        self.size = [
            5, 10, 15, 30, 60, 120, 300, 600, 900, 1800,
            3600, 7200, 14400, 86400
        ]
        self.email = email
        self.password = password
        self.host = host
        self.lang = lang
        self.proxies = proxies
        self.resource_path = root_path
        self.user_data_dir = user_data_dir
        self.asset_default = asset_default
        self.period_default = period_default
        self.subscribe_candle: list[str] = []
        self.subscribe_candle_all_size: list[str] = []
        self.subscribe_mood: list[str] = []
        self.account_is_demo: int = AccountType.DEMO
        self.suspend: float = 0.2
        self.codes_asset: dict[str, str] = {}
        self.api: QuotexAPI | None = None
        self.duration: int | None = None
        self.websocket_client: Any = None
        self.websocket_thread: Any = None
        self.debug_ws_enable: bool = False
        self.resource_path = resource_path(root_path)
        session = load_session(self.email, user_agent)
        self.session_data = session
        self.on_otp_callback = on_otp_callback

    @property
    def websocket(self) -> Any:
        """Property to get websocket.
        :returns: The active WebSocket instance.
        """
        return self.api.websocket if self.api else None

    @staticmethod
    async def _check_connect(state: Any) -> bool:
        """Check connection using the per-instance state object.

        Waits up to ~2s for the state to settle on AUTHENTICATED; returns
        as soon as the predicate is satisfied (event-driven path) or False
        on timeout. Replaces an unconditional ``await asyncio.sleep(2)``.
        """
        from pyquotex._api._waits import wait_until
        try:
            await wait_until(
                lambda: state.auth_status == AuthStatus.AUTHENTICATED,
                timeout=2,
                poll_interval=0.05,
            )
            return True
        except asyncio.TimeoutError:
            return state.auth_status == AuthStatus.AUTHENTICATED

    async def check_connect(self) -> bool:
        """Check connection using the current API's state."""
        if self.api is None:
            return False
        return await self._check_connect(self.api.state)

    def set_session(
            self,
            user_agent: str,
            cookies: str | None = None,
            ssid: str | None = None
    ) -> None:
        """
        Manually sets the session data.

        Args:
            user_agent (str): The User-Agent string.
            cookies (str, optional): The raw cookie string.
            ssid (str, optional): The SSID token.
        """
        session = {
            "cookies": cookies,
            "token": ssid,
            "user_agent": user_agent
        }
        self.session_data = update_session(self.email, session)

    async def re_subscribe_stream(self) -> None:
        """Re-subscribes to all active candle and mood streams."""
        try:
            for ac in self.subscribe_candle:
                sp = ac.split(",")
                await self.start_candles_one_stream(sp[0], int(sp[1]))
        except Exception as e:
            logger.warning("Failed to re-subscribe candle stream: %s", e)
        try:
            for ac in self.subscribe_candle_all_size:
                await self.start_candles_all_size_stream(ac)
        except Exception as e:
            logger.warning("Failed to re-subscribe all_size stream: %s", e)
        try:
            for ac in self.subscribe_mood:
                await self.start_mood_stream(ac)
        except Exception as e:
            logger.warning("Failed to re-subscribe mood stream: %s", e)

    async def get_instruments(
            self, timeout: int = DEFAULT_TIMEOUT
    ) -> list[Any]:
        """Get instruments using a true event-driven approach."""
        if not self.api or not await self.check_connect():
            return []

        if self.api.instruments and len(self.api.instruments) > 0:
            return self.api.instruments

        try:
            # Request instruments explicitly
            await self.api.get_instruments()
            # Wait for WebSocket event signaling instruments arrival
            await self.api.event_registry.wait_event(
                'instruments_ready', timeout=timeout
            )

            if not self.api.instruments:
                # Try one last wait if empty — event-driven up to 2s
                from pyquotex._api._waits import wait_until
                try:
                    await wait_until(
                        lambda: bool(
                            self.api and self.api.instruments
                        ),
                        timeout=2,
                        poll_interval=0.1,
                    )
                except asyncio.TimeoutError:
                    pass

            return self.api.instruments or []
        except TimeoutError:
            logger.error(
                "Timeout waiting for instruments after %ds", timeout
            )
            return []

    def get_all_asset_name(self) -> list[list[str]] | None:
        """
        Retrieves names of all available assets.

        Returns:
            list: List of assets with ID and display name.
        """
        if self.api and self.api.instruments:
            return [
                [i[1], i[2].replace("\n", "")]
                for i in self.api.instruments
            ]
        return None

    async def get_available_asset(
            self, asset_name: str, force_open: bool = False
    ) -> tuple[str, Any]:
        """
        Retrieves detailed information for an asset if it is currently open.

        Args:
            asset_name (str): Asset name.
            force_open (bool, optional): Try to find the OTC version if closed.
                Defaults to False.

        Returns:
            tuple: (Final asset name, Asset status info).
        """
        _, asset_open = await self.check_asset_open(asset_name)
        if force_open and (not asset_open or not asset_open[2]):
            condition_otc = "otc" not in asset_name
            refactor_asset = asset_name.replace("_otc", "")
            asset_name = (
                f"{asset_name}_otc" if condition_otc else refactor_asset
            )
            _, asset_open = await self.check_asset_open(asset_name)

        return asset_name, asset_open

    async def check_asset_open(
            self, asset_name: str
    ) -> tuple[list[Any] | None, tuple[Any, Any, Any]]:
        """
        Checks if a specific asset is currently available for trading.

        Args:
            asset_name (str): The name of the asset.

        Returns:
            tuple: (Raw instrument data, Formatted status info).
        """
        instruments = await self.get_instruments()
        for i in instruments:
            if asset_name == i[1]:
                if self.api:
                    self.api.current_asset = asset_name
                return i, (i[0], i[2].replace("\n", ""), i[14])

        return None, (None, None, None)

    async def get_all_assets(self) -> dict[str, str]:
        """
        Retrieves a mapping of all asset names to their internal codes.

        Returns:
            dict: Mapping of asset names to codes.
        """
        instruments = await self.get_instruments()
        for i in instruments:
            if i[0] != "":
                self.codes_asset[i[1]] = i[0]

        return self.codes_asset

    def get_payment(self) -> dict[str, Any]:
        """Retrieves the payout/payment percentages for all instruments."""
        if self.api is None:
            return {}

        assets_data = {}
        for i in self.api.instruments:
            assets_data[i[2].replace("\n", "")] = {
                "turbo_payment": i[18],
                "payment": i[5],
                "profit": {
                    "1M": i[-9],
                    "5M": i[-8]
                },
                "open": i[14]
            }

        return assets_data

    def get_payout_by_asset(
            self, asset_name: str, timeframe: str = "1"
    ) -> float | dict[str, Any] | None:
        """Retrieves the payout percentage for a specific asset and
        timeframe."""
        if self.api is None:
            return None

        assets_data = {}
        for i in self.api.instruments:
            if asset_name == i[1]:
                assets_data[i[1].replace("\n", "")] = {
                    "turbo_payment": i[18],
                    "payment": i[5],
                    "profit": {
                        "24H": i[-10],
                        "1M": i[-9],
                        "5M": i[-8]
                    },
                    "open": i[14]
                }
                break

        data = assets_data.get(asset_name)
        if data is None:
            return None

        if timeframe == "all":
            return data.get("profit")

        profit = data.get("profit")
        if profit:
            return profit.get(f"{timeframe}M")
        return None

    async def close(self) -> bool:
        """Closes the API connection and stops all tasks."""
        if self.api:
            return await self.api.close()
        return True
