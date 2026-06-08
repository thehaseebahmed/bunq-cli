import json
import os
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "bunq-cli"
_STATE_FILE = _CONFIG_DIR / "state.json"

BASE_URLS = {
    "sandbox": "https://public-api.sandbox.bunq.com",
    "production": "https://api.bunq.com",
}


def get_api_key() -> str:
    key = os.environ.get("BUNQ_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("BUNQ_API_KEY environment variable is not set.")
    return key


def get_environment() -> str:
    env = os.environ.get("BUNQ_ENVIRONMENT", "sandbox").strip().lower()
    if env not in BASE_URLS:
        raise EnvironmentError(
            f"BUNQ_ENVIRONMENT must be 'sandbox' or 'production', got: {env!r}"
        )
    return env


def get_base_url() -> str:
    return BASE_URLS[get_environment()]


def load_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    with _STATE_FILE.open() as f:
        return json.load(f)


def save_state(state: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with _STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)
    _STATE_FILE.chmod(0o600)


def clear_state() -> None:
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
