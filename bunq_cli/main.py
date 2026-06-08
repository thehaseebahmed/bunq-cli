import click

from .commands.session import session_group


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """bunq-cli — a command-line interface for the bunq API."""
    if ctx.invoked_subcommand is None:
        click.echo("Hello, Bunq")


cli.add_command(session_group)
