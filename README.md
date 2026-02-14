# Mimeo

A tool to generate websites quickly

## Vision

Mimeo automates the provisioning of landing pages for registered domains. Instead of manual configuration across registrars and hosting providers, Mimeo handles DNS setup and site deployment through a single CLI command.

The problem: Over 70 domains sitting unused because the "paperwork" of setting up even a simple landing page is tedious. The solution: Automate the entire workflow from domain to deployed site.

## Current Status

**Phase**: Phase 0 - Research & Design

Initial project setup. Next steps include implementing the core CLI workflow and integrating with Porkbun API and GitHub Pages.

## Features

- Single command to provision landing pages for domains
- Automated DNS configuration via Porkbun API
- GitHub Pages deployment with custom domains
- Template-based content generation
- No manual steps required

## Quick Start

### Prerequisites

- Python >=3.11
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd Mimeo

# Install dependencies
uv sync

# Run the application
uv run mimeo --help
```

## Development

See [CLAUDE.md](./CLAUDE.md) for development guide and AI session instructions.

See [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) for phase-based implementation tracking.

## Project Structure

```
Mimeo/
├── mimeo/     # Main package
│   └── cli.py            # CLI entry point
├── tests/                # Test suite
├── docs/                 # Documentation
│   ├── CONTEXT.md        # Current session state
│   ├── IMPLEMENTATION.md # Phase tracking
│   ├── DECISIONS.md      # Architectural decisions
│   └── chronicles/       # Session history
├── pyproject.toml        # Project configuration
└── README.md             # This file
```

## License

[Add license information]
