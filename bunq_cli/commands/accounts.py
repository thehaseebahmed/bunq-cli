"""bunq accounts commands.

accounts list  — list monetary accounts (active by default)
accounts balance <id>  — show balance, optionally reconstructed at a cutoff date
"""

from datetime import date
from decimal import Decimal, InvalidOperation

import click

from ..client import BunqAPIError, request
from ..config import load_state


# ── helpers ──────────────────────────────────────────────────────────────────

def _require_session(state: dict) -> tuple[str, str, str]:
    """Return (user_id, session_token, private_pem) or raise ClickException."""
    missing = [k for k in ("user_id", "session_token", "private_key_pem") if not state.get(k)]
    if missing:
        raise click.ClickException("No active session. Run `bunq session start` first.")
    return str(state["user_id"]), state["session_token"], state["private_key_pem"]


def _unwrap(items: list[dict]) -> list[dict]:
    """Strip the type-key wrapper from each item in a bunq Response list."""
    return [next(iter(item.values())) for item in items if item]


def _paginate_all(path: str, token: str, private_pem: str) -> list[dict]:
    """Fetch every page from a bunq list endpoint, return unwrapped objects."""
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


def _payments_since(
    user_id: str,
    account_id: str,
    cutoff: date,
    token: str,
    private_pem: str,
) -> list[dict]:
    """Return all Payment objects created strictly after *cutoff*.

    Paginates backwards from most-recent and stops as soon as a payment on or
    before the cutoff is encountered.  Note: only Payment-type transactions are
    included; other balance-affecting events (interest, fees, card settlements
    that post separately) are not captured here.
    """
    path_prefix = f"/user/{user_id}/monetary-account/{account_id}"
    accumulated: list[dict] = []
    older_id: int | None = None

    while True:
        qs = "count=200" + (f"&older_id={older_id}" if older_id else "")
        resp = request("GET", f"{path_prefix}/payment?{qs}", token=token, private_pem=private_pem)
        batch = [item["Payment"] for item in resp.get("Response", []) if "Payment" in item]

        if not batch:
            break

        reached_cutoff = False
        for payment in batch:
            # bunq datetime format: "2024-01-15 10:30:00.123456"
            created = date.fromisoformat(payment["created"][:10])
            if created <= cutoff:
                reached_cutoff = True
                break
            accumulated.append(payment)

        if reached_cutoff or len(batch) < 200:
            break

        older_id = batch[-1]["id"]

    return accumulated


# ── command group ─────────────────────────────────────────────────────────────

@click.group("accounts")
def accounts_group() -> None:
    """Manage bunq monetary accounts."""


# ── accounts list ─────────────────────────────────────────────────────────────

@accounts_group.command("list")
@click.option(
    "--include-closed",
    is_flag=True,
    default=False,
    help="Include cancelled and closed accounts.",
)
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
            (alias["value"] for alias in acc.get("alias", []) if alias.get("type") == "IBAN"),
            "—",
        )
        bal = acc.get("balance", {})
        try:
            bal_str = f"{bal.get('currency', '')} {Decimal(bal.get('value', '0')):,.2f}"
        except InvalidOperation:
            bal_str = "—"

        click.echo(
            f"{acc.get('id', ''):<10}  "
            f"{str(acc.get('description', ''))[:28]:<28}  "
            f"{iban[:22]:<22}  "
            f"{bal_str:>14}  "
            f"{acc.get('status', '')}"
        )


# ── accounts balance ──────────────────────────────────────────────────────────

@accounts_group.command("balance")
@click.argument("account_id")
@click.option(
    "--cutoff",
    "cutoff_str",
    metavar="YYYY-MM-DD",
    default=None,
    help=(
        "Reconstruct balance as of this date. "
        "Calculated by reversing Payment transactions since the date; "
        "other event types (interest, fees) are not included."
    ),
)
def accounts_balance(account_id: str, cutoff_str: str | None) -> None:
    """Show the balance for ACCOUNT_ID.

    Without --cutoff, shows the live current balance.  With --cutoff, works
    backwards from the current balance using payment transactions to estimate
    the balance at the given date.
    """
    state = load_state()
    user_id, token, private_pem = _require_session(state)

    cutoff: date | None = None
    if cutoff_str:
        try:
            cutoff = date.fromisoformat(cutoff_str)
        except ValueError:
            raise click.ClickException(
                f"Invalid date {cutoff_str!r} — expected YYYY-MM-DD."
            )

    try:
        resp = request(
            "GET",
            f"/user/{user_id}/monetary-account/{account_id}",
            token=token,
            private_pem=private_pem,
        )
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    accounts = _unwrap(resp.get("Response", []))
    if not accounts:
        raise click.ClickException(f"Account {account_id} not found.")

    acc = accounts[0]
    bal = acc.get("balance", {})
    currency = bal.get("currency", "?")
    current = Decimal(bal.get("value", "0"))
    description = acc.get("description", "")

    click.echo(f"Account:  {description} ({account_id})")

    if cutoff is None:
        click.echo(f"Balance:  {currency} {current:,.2f}")
        return

    click.echo(f"Fetching payments since {cutoff}…")
    try:
        payments = _payments_since(user_id, account_id, cutoff, token, private_pem)
    except BunqAPIError as exc:
        raise click.ClickException(f"Failed to fetch payments: {exc}")

    delta = sum(Decimal(p["amount"]["value"]) for p in payments)
    at_cutoff = current - delta

    click.echo(f"Balance at {cutoff}:  {currency} {at_cutoff:,.2f}")
    click.echo(
        f"  current balance : {currency} {current:,.2f}\n"
        f"  payments reversed: {len(payments)} transaction(s) totalling {currency} {delta:,.2f}\n"
        f"  note: only Payment-type events are included; "
        f"fees and interest are not captured."
    )
