"""bunq accounts commands."""

from decimal import Decimal, InvalidOperation

import click

from ..client import BunqAPIError, request
from ..config import load_state

_PAGE_SIZE = 10


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


def _print_header() -> None:
    header = f"{'ID':<10}  {'Description':<28}  {'IBAN':<22}  {'Balance':>14}  Status"
    click.echo(header)
    click.echo("-" * len(header))


def _print_row(acc: dict) -> None:
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


# ── command group ─────────────────────────────────────────────────────────────

@click.group("accounts")
def accounts_group() -> None:
    """Manage bunq monetary accounts."""


# ── accounts list ─────────────────────────────────────────────────────────────

@accounts_group.command("list")
@click.option("--include-closed", is_flag=True, default=False,
              help="Include cancelled and closed accounts.")
@click.option("--all", "all_accounts", is_flag=True, default=False,
              help="Print every account without pagination.")
def accounts_list(include_closed: bool, all_accounts: bool) -> None:
    """List monetary accounts.

    Active accounts are shown by default. Results are paginated; press Enter
    to advance or Ctrl-C to quit. Pass --all to print everything at once.
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

    total = len(accounts)

    if all_accounts:
        _print_header()
        for acc in accounts:
            _print_row(acc)
        return

    # Interactive pagination
    pages = [accounts[i : i + _PAGE_SIZE] for i in range(0, total, _PAGE_SIZE)]
    for page_num, page in enumerate(pages):
        _print_header()
        for acc in page:
            _print_row(acc)

        shown = min((page_num + 1) * _PAGE_SIZE, total)
        if page_num < len(pages) - 1:
            try:
                click.echo(
                    f"\n  {shown}/{total} shown — press Enter for more, Ctrl-C to quit",
                    nl=False,
                )
                input()
                click.echo()
            except (KeyboardInterrupt, EOFError):
                click.echo()
                break
        else:
            click.echo(f"\n  {shown}/{total} shown")
