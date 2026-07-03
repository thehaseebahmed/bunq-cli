"""bunq draft payment commands."""

from decimal import Decimal, InvalidOperation

import click

from ..client import BunqAPIError, extract, request
from ..config import load_state

_PAGE_SIZE = 10
_DEFAULT_PAGE = 1
_ALIAS_TYPES = {"iban": "IBAN", "email": "EMAIL", "phone": "PHONE_NUMBER"}
_STATUS_CHOICES = ("PENDING", "ACCEPTED", "REJECTED")


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


def _resolve_alias(iban: str | None, email: str | None, phone: str | None) -> tuple[str, str]:
    given = [(t, v) for t, v in (("iban", iban), ("email", email), ("phone", phone)) if v]
    if len(given) != 1:
        raise click.UsageError("Specify exactly one of --iban, --email, or --phone.")
    kind, value = given[0]
    return _ALIAS_TYPES[kind], value


def _entries_of(draft: dict) -> list[dict]:
    return draft.get("entries") or [{}]


def _fmt_amount(entry: dict) -> str:
    amt = entry.get("amount", {})
    try:
        return f"{amt.get('currency', '')} {Decimal(amt.get('value', '0')):,.2f}"
    except InvalidOperation:
        return "—"


def _counterparty(entry: dict) -> str:
    alias = entry.get("counterparty_alias", {}) or {}
    return alias.get("display_name") or alias.get("iban") or alias.get("value") or "—"


def _print_header() -> None:
    header = f"{'ID':<10}  {'Status':<10}  {'Amount':>14}  {'Counterparty':<28}  Description"
    click.echo(header)
    click.echo("-" * len(header))


def _print_row(draft: dict) -> None:
    first = _entries_of(draft)[0]
    click.echo(
        f"{draft.get('id', ''):<10}  "
        f"{draft.get('status', ''):<10}  "
        f"{_fmt_amount(first):>14}  "
        f"{_counterparty(first)[:28]:<28}  "
        f"{str(first.get('description', ''))[:40]}"
    )


def _print_detail(draft: dict) -> None:
    click.echo(f"ID:                {draft.get('id')}")
    click.echo(f"Status:            {draft.get('status')}")
    click.echo(f"Required accepts:  {draft.get('number_of_required_accepts')}")
    click.echo(f"Created:           {draft.get('created')}")
    click.echo(f"Updated:           {draft.get('updated')}")
    click.echo("Entries:")
    for i, entry in enumerate(_entries_of(draft), start=1):
        click.echo(
            f"  [{i}] {_fmt_amount(entry):>14}  ->  {_counterparty(entry)}"
            f"  — {entry.get('description', '')}"
        )


def _update_status(monetary_account_id: int, draft_payment_id: int, status: str) -> None:
    state = load_state()
    user_id, token, private_pem = _require_session(state)
    path = f"/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{draft_payment_id}"

    try:
        current_resp = request("GET", path, token=token, private_pem=private_pem)
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    current = extract(current_resp, "DraftPayment") or {}
    body = {"status": status}
    if current.get("updated"):
        # bunq's draft-payment object carries previous_updated_timestamp for
        # optimistic-concurrency updates; include it when we have it.
        body["previous_updated_timestamp"] = current["updated"]

    try:
        resp = request("PUT", path, body=body, token=token, private_pem=private_pem)
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    draft = extract(resp, "DraftPayment")
    if draft:
        click.echo(f"Draft payment {draft.get('id')} is now {draft.get('status')}.")
    else:
        click.echo(f"Draft payment {draft_payment_id} -> {status}.")


# ── command groups ───────────────────────────────────────────────────────────

@click.group("payments")
def payments_group() -> None:
    """Manage bunq payments."""


@click.group("draft")
def draft_group() -> None:
    """Manage draft payments (require sender approval before execution)."""


payments_group.add_command(draft_group)


# ── payments draft create ───────────────────────────────────────────────────

@draft_group.command("create")
@click.option("--account-id", "monetary_account_id", required=True, type=int,
              help="Monetary account ID to draft the payment from.")
@click.option("--amount", "amount", required=True, help="Amount, e.g. 12.50")
@click.option("--currency", default="EUR", show_default=True, help="ISO 4217 currency code.")
@click.option("--iban", "recipient_iban", default=None, help="Recipient IBAN.")
@click.option("--email", "recipient_email", default=None, help="Recipient email alias.")
@click.option("--phone", "recipient_phone", default=None, help="Recipient phone number alias.")
@click.option("--name", "recipient_name", default=None, help="Recipient display name (optional).")
@click.option("--description", "description", default="", help="Payment description.")
def draft_create(
    monetary_account_id: int,
    amount: str,
    currency: str,
    recipient_iban: str | None,
    recipient_email: str | None,
    recipient_phone: str | None,
    recipient_name: str | None,
    description: str,
) -> None:
    """Create a draft payment.

    A draft payment must be accepted (via `bunq payments draft accept`) before
    the underlying payment executes. Only a single draft is created per call;
    `number_of_required_accepts` is always 1 — the only value the bunq API
    currently accepts.
    """
    try:
        Decimal(amount)
    except InvalidOperation:
        raise click.BadParameter("must be a valid decimal, e.g. 12.50", param_hint="--amount")

    alias_type, alias_value = _resolve_alias(recipient_iban, recipient_email, recipient_phone)

    state = load_state()
    user_id, token, private_pem = _require_session(state)

    counterparty_alias = {"type": alias_type, "value": alias_value}
    if recipient_name:
        counterparty_alias["name"] = recipient_name

    body = {
        "entries": [{
            "amount": {"value": amount, "currency": currency},
            "counterparty_alias": counterparty_alias,
            "description": description,
        }],
        "number_of_required_accepts": 1,
    }

    try:
        resp = request(
            "POST",
            f"/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment",
            body=body,
            token=token,
            private_pem=private_pem,
        )
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    created = extract(resp, "DraftPayment")
    if not created:
        click.echo("Draft payment created.")
        return

    click.echo(f"Draft payment created. ID: {created.get('id')}  Status: {created.get('status')}")


# ── payments draft list ─────────────────────────────────────────────────────

@draft_group.command("list")
@click.option("--account-id", "monetary_account_id", required=True, type=int,
              help="Monetary account ID to list draft payments for.")
@click.option("--status", "status_filter", type=click.Choice(_STATUS_CHOICES, case_sensitive=False),
              default=None, help="Filter by draft payment status.")
@click.option("--all", "all_drafts", is_flag=True, default=False,
              help="Print every draft payment without pagination.")
@click.option("--page", default=_DEFAULT_PAGE, show_default=True, metavar="N",
              help="Page number to display.")
def draft_list(monetary_account_id: int, status_filter: str | None, all_drafts: bool, page: int) -> None:
    """List draft payments for an account.

    Shown 10 per page by default. Use --page N to navigate, or --all to
    print everything at once.
    """
    if page < 1:
        raise click.BadParameter("must be 1 or greater", param_hint="--page")

    state = load_state()
    user_id, token, private_pem = _require_session(state)

    try:
        drafts = _paginate_all(
            f"/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment", token, private_pem
        )
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    if status_filter:
        drafts = [d for d in drafts if d.get("status") == status_filter.upper()]

    if not drafts:
        click.echo("No draft payments found.")
        return

    if all_drafts:
        _print_header()
        for draft in drafts:
            _print_row(draft)
        return

    total = len(drafts)
    total_pages = max(1, -(-total // _PAGE_SIZE))  # ceiling division

    if page > total_pages:
        raise click.BadParameter(
            f"only {total_pages} page(s) available", param_hint="--page"
        )

    start = (page - 1) * _PAGE_SIZE
    _print_header()
    for draft in drafts[start : start + _PAGE_SIZE]:
        _print_row(draft)

    click.echo(f"\n  Page {page}/{total_pages}")


# ── payments draft get ───────────────────────────────────────────────────────

@draft_group.command("get")
@click.option("--account-id", "monetary_account_id", required=True, type=int,
              help="Monetary account ID the draft payment belongs to.")
@click.argument("draft_payment_id", type=int)
def draft_get(monetary_account_id: int, draft_payment_id: int) -> None:
    """Show details of a single draft payment."""
    state = load_state()
    user_id, token, private_pem = _require_session(state)

    try:
        resp = request(
            "GET",
            f"/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{draft_payment_id}",
            token=token,
            private_pem=private_pem,
        )
    except BunqAPIError as exc:
        raise click.ClickException(str(exc))

    draft = extract(resp, "DraftPayment")
    if not draft:
        raise click.ClickException("Draft payment not found.")

    _print_detail(draft)


# ── payments draft accept / reject ──────────────────────────────────────────

@draft_group.command("accept")
@click.option("--account-id", "monetary_account_id", required=True, type=int,
              help="Monetary account ID the draft payment belongs to.")
@click.argument("draft_payment_id", type=int)
def draft_accept(monetary_account_id: int, draft_payment_id: int) -> None:
    """Accept a pending draft payment, executing the underlying payment(s)."""
    _update_status(monetary_account_id, draft_payment_id, "ACCEPTED")


@draft_group.command("reject")
@click.option("--account-id", "monetary_account_id", required=True, type=int,
              help="Monetary account ID the draft payment belongs to.")
@click.argument("draft_payment_id", type=int)
def draft_reject(monetary_account_id: int, draft_payment_id: int) -> None:
    """Reject a pending draft payment."""
    _update_status(monetary_account_id, draft_payment_id, "REJECTED")
