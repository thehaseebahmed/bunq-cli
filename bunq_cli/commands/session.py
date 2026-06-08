import click

from ..client import BunqAPIError, extract, request
from ..config import clear_state, get_api_key, load_state, save_state
from ..crypto import generate_key_pair


@click.group("session")
def session_group() -> None:
    """Manage bunq API sessions."""


@session_group.command("start")
def session_start() -> None:
    """Authenticate with bunq and store a session token.

    Reads BUNQ_API_KEY from the environment. On first run it generates an RSA
    key pair, registers an installation and device, then opens a session.
    Subsequent runs reuse the stored installation and only open a new session.
    """
    try:
        api_key = get_api_key()
    except EnvironmentError as exc:
        raise click.ClickException(str(exc))

    state = load_state()

    # ── 1. Key pair ──────────────────────────────────────────────────────────
    if "private_key_pem" not in state:
        click.echo("Generating RSA-2048 key pair…")
        private_pem, public_pem = generate_key_pair()
        state["private_key_pem"] = private_pem
        state["public_key_pem"] = public_pem
        save_state(state)

    private_pem: str = state["private_key_pem"]
    public_pem: str = state["public_key_pem"]

    # ── 2. Installation ───────────────────────────────────────────────────────
    if "installation_token" not in state:
        click.echo("Registering installation…")
        try:
            resp = request("POST", "/installation", body={"client_public_key": public_pem})
        except BunqAPIError as exc:
            raise click.ClickException(f"Installation failed: {exc}")

        token_obj = extract(resp, "Token")
        server_key_obj = extract(resp, "ServerPublicKey")
        if not token_obj:
            raise click.ClickException("Unexpected response: no Token in installation reply.")

        state["installation_token"] = token_obj["token"]
        if server_key_obj:
            state["server_public_key"] = server_key_obj["server_public_key"]
        save_state(state)

    installation_token: str = state["installation_token"]

    # ── 3. Device registration ────────────────────────────────────────────────
    if not state.get("device_registered"):
        click.echo("Registering device…")
        try:
            request(
                "POST",
                "/device-server",
                body={
                    "description": "bunq-cli",
                    "secret": api_key,
                    "permitted_ips": ["*"],
                },
                token=installation_token,
                private_pem=private_pem,
            )
        except BunqAPIError as exc:
            if exc.status_code in (400, 401):
                # Installation token is stale — wipe state and let the user retry
                click.echo(
                    "Installation token rejected. Clearing stored state — please run again.",
                    err=True,
                )
                clear_state()
                raise click.ClickException(f"Device registration failed: {exc}")
            raise click.ClickException(f"Device registration failed: {exc}")

        state["device_registered"] = True
        save_state(state)

    # ── 4. Session ────────────────────────────────────────────────────────────
    click.echo("Opening session…")
    try:
        resp = request(
            "POST",
            "/session-server",
            body={"secret": api_key},
            token=installation_token,
            private_pem=private_pem,
        )
    except BunqAPIError as exc:
        raise click.ClickException(f"Session creation failed: {exc}")

    token_obj = extract(resp, "Token")
    if not token_obj:
        raise click.ClickException("Unexpected response: no Token in session reply.")

    state["session_token"] = token_obj["token"]

    user = (
        extract(resp, "UserApiKey")
        or extract(resp, "UserPerson")
        or extract(resp, "UserCompany")
    )
    if user:
        state["user_id"] = user.get("id")

    save_state(state)

    user_id = state.get("user_id", "unknown")
    click.echo(f"Session started. User ID: {user_id}")
