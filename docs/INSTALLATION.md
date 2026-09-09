# Installation

## Prerequisites

- Python >=3.11
- [uv](https://github.com/astral-sh/uv) — package manager
- [gh](https://cli.github.com/) — GitHub CLI, authenticated (`gh auth login`)
- Porkbun API key and secret
- GitHub account configured in `gh`

### GitHub token scope requirement

The `gh` token must have the `workflow` scope to push the GitHub Actions workflow file. Re-authenticate with the correct scope if needed:

```bash
gh auth login --scopes workflow
```

## Install

### Development (from source)

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
uv run mimeo --help
```

### Global CLI install

```bash
uv tool install .
mimeo --help
```

## Configuration

Create `~/.config/mimeo/config.toml`:

```toml
[porkbun]
api_key = "pk1_..."
secret_key = "sk1_..."

[github]
default_org = "your-github-username"
```

See [config.toml.example](../config.toml.example) for the full annotated template including environment variable overrides.

### Environment variable overrides

All settings can be provided via environment variables (take precedence over the config file):

```bash
export MIMEO_PORKBUN_API_KEY="pk1_..."
export MIMEO_PORKBUN_SECRET="sk1_..."
export MIMEO_GITHUB_USERNAME="your-username"
```

## Verify setup

```bash
mimeo doctor
```

Checks Python version, `gh` installation and authentication, `workflow` token scope, and config file validity.
