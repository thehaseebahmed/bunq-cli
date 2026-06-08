import json
import os
from pathlib import Path

BASE_URLS = {
    "sandbox": "https://public-api.sandbox.bunq.com",
    "production": "https://api.bunq.com",
}


def get_state_dir() -> Path:
    """Return the state directory, honouring BUNQ_STATE_DIR if set."""
    raw = os.environ.get("BUNQ_STATE_DIR", "").strip()
    return Path(raw) if raw else Path.home() / ".bunq"


def _state_file() -> Path:
    return get_state_dir() / "state.json"


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
    f = _state_file()
    if not f.exists():
        return {}
    with f.open() as fh:
        return json.load(fh)


def save_state(state: dict) -> None:
    f = _state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("w") as fh:
        json.dump(state, fh, indent=2)
    f.chmod(0o600)


def clear_state() -> None:
    f = _state_file()
    if f.exists():
        f.unlink()
