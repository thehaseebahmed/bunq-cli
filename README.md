# bunq-cli

A command-line interface (CLI) and skill set that allows an LLM assistant to interact with the [bunq API](https://doc.bunq.com/).

bunq is a mobile bank that exposes a rich REST API. This project wraps that API in a developer-friendly CLI so that both humans and LLM agents can perform banking operations — checking balances, listing transactions, making payments, and more — without needing to write code directly against the API.

## Features (planned)

- Authenticate with the bunq API (API key + device registration)
- List monetary accounts and balances
- Fetch recent transactions
- Initiate payments
- Manage bunq cards
- Structured JSON output suitable for LLM tool use

## Requirements

- Python 3.10+
- A bunq account and API key ([sandbox](https://beta.doc.bunq.com/basics/sandbox) or production)

## Installation

```bash
# Clone the repository
git clone https://github.com/thehaseebahmed/bunq-cli.git
cd bunq-cli

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

## Usage

```bash
bunq          # prints "Hello, Bunq" (more commands coming soon)
bunq --help   # show available commands
```

## Development

```bash
pip install -e ".[dev]"
```

## License

MIT
