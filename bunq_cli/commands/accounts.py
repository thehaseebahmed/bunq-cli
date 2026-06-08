"""bunq accounts commands.

accounts list     — list monetary accounts (active by default)
accounts balance  — show balance for one account or all accounts
"""

from decimal import Decimal, InvalidOperation

import click

from ..client import BunqAPIError, request
from ..config import load_state


# ── helpers ──────────────────────────────────────────────────────────────────

def _require_session(state: dict) -> tuple[str, str, str]:
    missing = [k for k in ("user_id", "session_token", "private_key_pem") if not state.get(k)]
    if missing:
        raise click.ClickException("No active session. Run `bunq session start` first.")
    return str(state["user_id"]), state["session_token"], state["private_key_pem"]


def _unwrap(items: list[dict]) -> list[dict]:
    return [next(iter(item.values())) for item in items if item]


def _paginate_all(path: str, token: str, private_pem: str) -> list[dict]:
    results: list[dict] = []
    older_id: int | None = None

    while True:
        qs = "count=200" + (f"&older_id={older_id}" if older_id else "")
        resp = request("GET", f"{path}?{qs}", token=token, private_pem=private_pem)
        batch = _unwrap(resp.get("Response", []))

        if not batch:
            break

        results.extend(batch)

        if len(batch) < 200:
            break

        older_id = batch[-1].get("id")
        if not older_id:
            break

    return results


def _fmt_balance(acc: dict) -> str:
    bal = acc.get("balance", {})
    try:
        return f"{bal.get('currency', '')} {Decimal(bal.get('value', '0')):,.2f}"
    except InvalidOperation:
        return "—"


# ── command group ─────────────────────────────────────────────────────────────

@click.group("accounts")
def accounts_group() -> None:
    """Manage bunq monetary accounts."""


# ── accounts list ─────────────────────────────────────────────────────────────

@accounts_group.command("list")
@click.option("--include-closed", is_flag=True, default=False,
              help="Include cancelled and closed accounts.")
def accounts_list(include_closed: bool) -> None:
    """List monetary accounts.

    Active accounts are shown by default. Pass --include-closed to also show
    cancelled or otherwise inactive accounts.
    """
    state = load_state()
    user_id, token, private_pem = _require_session(state)

    try:
        accounts = _paginate_all(f"/user/{user_id}/monetary-account", token, private_pem)
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    if not include_closed:
        accounts = [a for a in accounts if a.get("status") == "ACTIVE"]

    if not accounts:
        click.echo("No accounts found.")
        return

    header = f"{'ID':<10}  {'Description':<28}  {'IBAN':<22}  {'Balance':>14}  Status"
    click.echo(header)
    click.echo("-" * len(header))

    for acc in accounts:
        iban = next(
            (a["value"] for a in acc.get("alias", []) if a.get("type") == "IBAN"), "—"
        )
        click.echo(
            f"{acc.get('id', ''):<10}  "
            f"{str(acc.get('description', ''))[:28]:<28}  "
            f"{iban[:22]:<22}  "
            f"{_fmt_balance(acc):>14}  "
            f"{acc.get('status', '')}"
        )


# ── accounts balance ──────────────────────────────────────────────────────────

@accounts_group.command("balance")
@click.argument("account_id", required=False)
@click.option("--all", "all_accounts", is_flag=True, default=False,
              help="Show balance for every active account.")
def accounts_balance(account_id: str | None, all_accounts: bool) -> None:
    """Show the balance for ACCOUNT_ID, or all active accounts with --all."""
    state = load_state()
    user_id, token, private_pem = _require_session(state)

    if not all_accounts and not account_id:
        raise click.UsageError("Provide an ACCOUNT_ID or pass --all.")

    if all_accounts:
        try:
            accounts = _paginate_all(f"/user/{user_id}/monetary-account", token, private_pem)
        except BunqAPIError as exc:
            raise click.ClickException(str(exc))

        accounts = [a for a in accounts if a.get("status") == "ACTIVE"]

        if not accounts:
            click.echo("No active accounts found.")
            return

        header = f"{'ID':<10}  {'Description':<28}  {'Balance':>14}"
        click.echo(header)
        click.echo("-" * len(header))

        for acc in accounts:
            click.echo(
                f"{acc.get('id', ''):<10}  "
                f"{str(acc.get('description', ''))[:28]:<28}  "
                f"{_fmt_balance(acc):>14}"
            )
    else:
        try:
            resp = request(
                "GET", f"/user/{user_id}/monetary-account/{account_id}",
                token=token, private_pem=private_pem,
            )
        except BunqAPIError as exc:
            raise click.ClickException(str(exc))

        accounts = _unwrap(resp.get("Response", []))
        if not accounts:
            raise click.ClickException(f"Account {account_id} not found.")

        acc = accounts[0]
        click.echo(f"Account:  {acc.get('description', '')} ({account_id})")
        click.echo(f"Balance:  {_fmt_balance(acc)}")
