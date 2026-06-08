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

List monetary accounts. Active accounts are shown by default. Results are
paginated — press Enter to advance or Ctrl-C to quit.

```bash
bunq accounts list                 # active accounts, paginated
bunq accounts list --all           # all active accounts at once
bunq accounts list --include-closed        # include cancelled/closed accounts
bunq accounts list --include-closed --all  # all accounts, no pagination
```

## Development

```bash
pip install -e ".[dev]"
```

## License

MIT
