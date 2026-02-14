"""Command-line interface for Mimeo."""

import click
from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="Mimeo")
def main():
    """A tool to generate websites quickly"""
    pass


@main.command()
def hello():
    """Example command - replace with your CLI logic."""
    print(f"Mimeo v{__version__}")
    print("Ready to go!")


if __name__ == "__main__":
    main()
