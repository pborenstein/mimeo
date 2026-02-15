"""Command-line interface for Mimeo."""

import tempfile
from pathlib import Path

import click

from . import __version__
from .config import Config
from .content import generate_minimal_site
from .exceptions import ConfigurationError, HostError, RegistrarError
from .providers.host.github import GitHubHost
from .providers.registrar.porkbun import PorkbunRegistrar


@click.group()
@click.version_option(version=__version__, prog_name="Mimeo")
def main() -> None:
    """A tool to generate websites quickly"""
    pass


@main.command()
@click.argument("domain")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
def create(domain: str, config: Path | None) -> None:
    """Create and deploy a minimal landing page for DOMAIN.

    This command will:
    1. Generate a minimal landing page
    2. Deploy to GitHub Pages
    3. Configure DNS records
    4. Set up custom domain

    Example:
        mimeo create example.com
    """
    try:
        # Load configuration
        click.echo("Loading configuration...")
        cfg = Config.load(config)

        # Create temporary directory for site content
        with tempfile.TemporaryDirectory() as temp_dir:
            content_path = Path(temp_dir)

            # Generate site content
            click.echo(f"Generating site for {domain}...")
            generate_minimal_site(domain, content_path)

            # Deploy to GitHub Pages
            click.echo("Deploying to GitHub Pages...")
            with GitHubHost(default_org=cfg.github_username) as host:
                site_url = host.deploy_site(domain, content_path)
                click.secho(f"✓ Deployed to {site_url}", fg="green")

            # Configure DNS
            click.echo("Configuring DNS records...")
            dns_records = PorkbunRegistrar.github_pages_records(
                domain, cfg.github_username
            )
            with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
                registrar.configure_dns(domain, dns_records)
                click.secho("✓ DNS records configured", fg="green")

                # Verify DNS propagation
                click.echo("Verifying DNS propagation (this may take a moment)...")
                verified = registrar.verify_dns(domain, dns_records, max_attempts=10, delay=5)
                if verified:
                    click.secho("✓ DNS records verified", fg="green")
                else:
                    click.secho(
                        "⚠ DNS records created but not yet propagated. "
                        "This may take up to 24 hours.",
                        fg="yellow",
                    )

        # Success message
        click.echo()
        click.secho("=" * 60, fg="green")
        click.secho("Site successfully deployed!", fg="green", bold=True)
        click.secho("=" * 60, fg="green")
        click.echo()
        click.echo(f"URL: {site_url}")
        click.echo(f"Repository: https://github.com/{cfg.github_username}/{domain}")
        click.echo()
        click.echo("Note: It may take a few minutes for GitHub Pages to build and")
        click.echo("deploy your site, and up to 24 hours for DNS to fully propagate.")

    except ConfigurationError as e:
        click.secho(f"Configuration error: {e}", fg="red", err=True)
        raise click.Abort()
    except HostError as e:
        click.secho(f"Deployment error: {e}", fg="red", err=True)
        raise click.Abort()
    except RegistrarError as e:
        click.secho(f"DNS configuration error: {e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
