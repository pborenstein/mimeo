# Contributing to Mimeo


## Getting Started

### Prerequisites

- Python 3.11 or later
- [uv](https://github.com/astral-sh/uv) package manager
- [gh](https://cli.github.com/) GitHub CLI, authenticated with the `workflow` scope
- Porkbun API credentials for integration testing

### Development Setup

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
uv run mimeo --help
```

### Verify the Setup

```bash
uv run pytest
uv run ruff check mimeo
uv run mypy mimeo
```

All three commands should complete without errors. There is one pre-existing mypy warning in `cli.py` for a heterogeneous dict — this is known and not blocking.

## Code Style

### General

- Follow PEP 8
- Line length: 100 characters (configured in `pyproject.toml`)
- Target: Python 3.11+

### Type Hints

All functions require type hints. The project uses `mypy` in strict mode:

```toml
[tool.mypy]
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Docstrings

Public functions and classes require docstrings in Google style:

```python
def configure_dns(self, domain: str, records: list[DNSRecord]) -> None:
    """Configure DNS records for a domain.

    Args:
        domain: Domain name to configure
        records: List of DNS records to create/update

    Raises:
        RegistrarError: If DNS configuration fails
    """
```

### Naming Conventions

- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_leading_underscore`

### Formatting

The project uses `ruff` for linting. Run before committing:

```bash
uv run ruff check mimeo
uv run ruff check tests
```

## Testing Requirements

### Unit Tests

Write tests for all new functionality using `pytest`. Tests live in `tests/` mirroring the `mimeo/` package structure:

```
tests/
├── test_cli.py
├── test_config.py
├── test_content.py
├── test_models.py
├── test_providers_base.py
├── providers/
│   ├── host/test_github.py
│   └── registrar/test_porkbun.py
└── utils/test_http.py
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific file
uv run pytest tests/test_config.py

# With coverage
uv run pytest --cov=mimeo

# Verbose
uv run pytest -v
```

### Test Coverage Expectations

- New provider implementations: full unit test coverage using mocks
- New CLI commands: test all flags and error paths using Click's `CliRunner`
- New models: test validation in `__post_init__`
- Bug fixes: include a test that reproduces the bug before the fix

### Mocking External Services

Do not make real API calls in unit tests. Use:

- `pytest-mock` (`mocker` fixture) for patching
- `responses` library for HTTP request mocking
- Click's `CliRunner` for CLI command testing

Example pattern for GitHub provider tests:

```python
def test_deploy_site_creates_repo(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    # ... test body
```

## Pull Request Process

### Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Implement changes with tests
4. Run the full validation suite:
   ```bash
   uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
   ```
4. Update documentation if the change affects user-facing behavior
5. Commit with a descriptive message (see format below)
6. Open a pull request against `main`

### Commit Message Format

```
type: short description

Longer explanation of what changed and why.

- Detail 1
- Detail 2

Related: DEC-XXX (if an architectural decision is involved)
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Examples:

```
feat: add --workers option to create command

Allows configuring concurrency for bulk domain provisioning.
Default remains 5 to match existing behavior.
```

```
fix: handle ALIAS records at apex when configuring A records

Porkbun does not allow both ALIAS and A records at the apex.
Delete conflicting ALIAS records before creating new A records.
```

### Review Criteria

Pull requests are evaluated on:

- Tests pass and cover the change
- Type hints present and mypy clean
- No ruff linting errors
- Docstrings on public APIs
- Commit messages are clear and follow the format

## Adding a New Provider

Mimeo uses provider abstractions defined in `mimeo/providers/base.py`. To add a new registrar or host:

### New Registrar

1. Create `mimeo/providers/registrar/<name>.py`
2. Subclass `Registrar` and implement:
   - `configure_dns(domain, records)` — create/update DNS records
   - `verify_dns(domain, records)` — poll until records propagate
3. Add tests in `tests/providers/registrar/test_<name>.py`
4. Document the decision in `docs/DECISIONS.md`

### New Host Provider

1. Create `mimeo/providers/host/<name>.py`
2. Subclass `Host` and implement:
   - `deploy_site(domain, content_path) -> DeployResult` — full deployment
3. Add tests in `tests/providers/host/test_<name>.py`
4. Document the decision in `docs/DECISIONS.md`

## Bug Reports

Include in the report:

- Mimeo version: `mimeo --version`
- Python version: `python --version`
- Operating system
- Command run (redact credentials)
- Full error output
- Output of `mimeo doctor`

