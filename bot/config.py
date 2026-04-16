"""Environment configuration and application constants."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = "https://testnet.binancefuture.com"
TIMEOUT: int = 10
MAX_RETRIES: int = 3
RECV_WINDOW: int = 5000
LOG_FILE: str = "logs/trading_bot.log"
LOG_MAX_BYTES: int = 5 * 1024 * 1024
LOG_BACKUP_COUNT: int = 3


class _Settings:
    """Singleton holding validated runtime configuration."""

    def __init__(self) -> None:
        self.api_key: str = self._require("BINANCE_API_KEY")
        self.api_secret: str = self._require("BINANCE_API_SECRET")
        self.base_url: str = BASE_URL
        self.timeout: int = TIMEOUT
        self.max_retries: int = MAX_RETRIES
        self.recv_window: int = RECV_WINDOW

    @staticmethod
    def _require(name: str) -> str:
        """Read a mandatory environment variable or exit immediately.

        Args:
            name: Environment variable name.

        Returns:
            The variable's value.
        """
        value = os.getenv(name)
        if not value:
            sys.stderr.write(
                f"Fatal: environment variable {name} is not set. "
                "Copy .env.example to .env and fill in your credentials.\n"
            )
            sys.exit(1)
        return value


def _load_settings() -> _Settings:
    """Construct settings; called once at import time."""
    return _Settings()


settings: _Settings = _load_settings()
