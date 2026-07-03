# bunq-cli

A command-line interface (CLI) and skill set that allows an LLM assistant to interact with the [bunq API](https://doc.bunq.com/).

bunq is a mobile bank that exposes a rich REST API. This project wraps that API in a developer-friendly CLI so that both humans and LLM agents can perform banking operations — checking balances, listing transactions, making payments, and more — without needing to write code directly against the API.

## Requirements

- Python 3.10+
- A bunq account and API key ([sandbox](https://beta.doc.bunq.com/basics/sandbox) or production)

## Usage

### Without installation (uvx)

[uv](https://docs.astral.sh/uv/) can run bunq-cli in a throwaway environment with no prior setup:

```bash
uvx --from "git+https://github.com/thehaseebahmed/bunq-cli" bunq
```

State (RSA keys, tokens) is still persisted between invocations in `~/.bunq/`.

### Install from git (pip)

```bash
pip install "git+https://github.com/thehaseebahmed/bunq-cli"
bunq --help
```

### Install for development

```bash
git clone https://github.com/thehaseebahmed/bunq-cli.git
cd bunq-cli
pip install -e .
```

## Configuration

All configuration is via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `BUNQ_API_KEY` | Yes | — | Your bunq API key |
| `BUNQ_ENVIRONMENT` | No | `sandbox` | `sandbox` or `production` |
| `BUNQ_STATE_DIR` | No | `~/.bunq` | Directory for storing session state |

## Commands

### `bunq session start`

Authenticate with the bunq API and store a session token.

On first run, generates an RSA key pair, registers an installation and device,
then opens a session. Subsequent runs reuse the stored installation and only
open a fresh session.

```bash
bunq session start
```

### `bunq accounts list`

List monetary accounts. Active accounts are shown by default, 10 per page.

```bash
bunq accounts list              # page 1 of active accounts
bunq accounts list --page 2     # navigate to a specific page
bunq accounts list --all        # all active accounts at once
bunq accounts list --include-closed         # include cancelled/closed accounts
bunq accounts list --include-closed --all   # every account, no pagination
```

> Name search is not supported — the bunq API does not expose server-side filtering on the accounts endpoint.

### `bunq payments draft create`

Create a draft payment. A draft payment must be accepted (see
`bunq payments draft accept` below) before the underlying payment executes —
useful for shared/multi-user accounts that require approval.

```bash
bunq payments draft create --account-id 123 --iban NL00BUNQ0123456789 \
    --amount 12.50 --currency EUR --description "Dinner split"
bunq payments draft create --account-id 123 --email friend@example.com --amount 5.00
```

> Each call creates a single draft payment, and `number_of_required_accepts`
> is always 1 — the only value the bunq API accepts today.

### `bunq payments draft list`

List draft payments for an account. Shown 10 per page by default.

```bash
bunq payments draft list --account-id 123
bunq payments draft list --account-id 123 --status PENDING --all
```

### `bunq payments draft get`

Show full details of a single draft payment, including all entries.

```bash
bunq payments draft get --account-id 123 456
```

### `bunq payments draft accept` / `bunq payments draft reject`

Accept or reject a pending draft payment. Accepting executes the underlying
payment(s).

```bash
bunq payments draft accept --account-id 123 456
bunq payments draft reject --account-id 123 456
```

> Both commands require the draft to still be in `PENDING` status.

## Development

```bash
pip install -e ".[dev]"
```

## License

MIT
