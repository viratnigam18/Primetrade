"""Root conftest — sets dummy credentials so config.py does not exit during test collection."""

import os

os.environ.setdefault("BINANCE_API_KEY", "test_key_for_ci")
os.environ.setdefault("BINANCE_API_SECRET", "test_secret_for_ci")
