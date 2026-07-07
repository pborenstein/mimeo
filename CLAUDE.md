# Mimeo Development Guide

Development guide for AI-assisted sessions on this project.

## Project Overview

Provision and manage custom-domain sites on GitHub Pages

### Key Principles

- Minimize manual steps - everything should be automated via APIs
- Start simple with Porkbun + GitHub Pages, design for extensibility
- No cost or very low cost hosting solutions
- CLI-first design for scriptability

### Technology Stack

- **Language**: Python >=3.11
- **Package Manager**: uv
- **Testing**: pytest
- **Type Checking**: mypy
- **Linting**: ruff

## Python Environment

### Setup

```bash
# Install dependencies
uv sync

# Verify installation
uv run python --version
uv run mimeo --help
```

### Running Commands

```bash
# Run the CLI
uv run mimeo [args]

# Run tests
uv run pytest

# Type checking
uv run mypy mimeo

# Linting
uv run ruff check mimeo
```

## Development Workflow

### Session Pickup

At the start of each session:

1. Read `docs/IMPLEMENTATION.md` for current phase and tasks
2. Review recent entries in phase chronicle file
3. Check `docs/DECISIONS.md` for relevant architectural decisions

Use the `/plinth:session-pickup` command to automate this.

### Session Wrapup

At the end of each session:

1. Update task status in `docs/IMPLEMENTATION.md`
2. Create chronicle entry in current phase file
3. Document new decisions in `docs/DECISIONS.md`
4. Commit changes with comprehensive message

Use the `/plinth:session-wrapup` command to automate this.

### Planning Approach

"Plan like waterfall, implement in agile"

- Maintain detailed upfront planning in IMPLEMENTATION.md
- Implement iteratively in small steps
- Document decisions and learnings as you go
- Update the plan when reality diverges

## Documentation System

| File | Purpose |
|------|---------|
| `docs/CONTEXT.md` | Current session state (hot state, 30-50 lines) |
| `docs/IMPLEMENTATION.md` | Phase-based implementation plan and task tracking |
| `docs/DECISIONS.md` | Architectural decision registry |
| `docs/chronicles/phase-X-name.md` | Detailed session-by-session history |

## Session Checklist

**Start of Session**:
- [ ] Read IMPLEMENTATION.md current phase
- [ ] Review recent chronicle entries
- [ ] Understand current task context

**During Session**:
- [ ] Update task checkboxes as work progresses
- [ ] Note decisions that need documentation
- [ ] Track problems and solutions

**End of Session**:
- [ ] Update IMPLEMENTATION.md task status
- [ ] Create chronicle entry with session details
- [ ] Document new decisions in DECISIONS.md
- [ ] Commit with descriptive message

## What NOT to Do

- Don't skip documentation updates
- Don't make architectural decisions without documenting rationale
- Don't create code without updating task tracking
- Don't commit without comprehensive commit messages
- Don't add emojis to files
- Don't use pip or poetry (use uv only)

## Code Style

- Follow PEP 8
- Type hints on all functions
- Docstrings for public APIs
- Keep functions focused and small
- Write tests for new functionality

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_module.py

# Run with coverage
uv run pytest --cov=mimeo
```

## Common Tasks

### Adding a New Feature

1. Update IMPLEMENTATION.md with feature tasks
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Create chronicle entry
6. Commit changes

### Fixing a Bug

1. Write test that reproduces bug
2. Fix the bug
3. Verify test passes
4. Document in chronicle entry
5. Commit with "fix:" prefix

### Refactoring

1. Document current architecture in DECISIONS.md
2. Explain refactoring rationale
3. Make changes incrementally
4. Keep tests passing throughout
5. Document new architecture
6. Create comprehensive chronicle entry

## Git Workflow

### Commit Message Format

```
type: short description

Longer explanation of what changed and why.

- Detail 1
- Detail 2

Related: DEC-XXX (if architectural decision involved)
```

**Types**: feat, fix, docs, refactor, test, chore

### Branch Strategy

[Define your branching strategy here]

## Questions?

Check the documentation system first:

1. **Implementation questions**: See IMPLEMENTATION.md
2. **Historical context**: See appropriate phase chronicle file
3. **Architectural decisions**: See DECISIONS.md
4. **Getting started**: See README.md
