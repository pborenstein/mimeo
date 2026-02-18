# Mimeo Documentation

Navigation index for all Mimeo documentation files.

## Documentation Map

| Document | Audience | Purpose |
|:---------|:---------|:--------|
| [../README.md](../README.md) | All | Quick start, command reference, installation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Developers | Component map, data flows, ASCII workflow diagrams |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Operators | Failure diagnosis and remediation by category |
| [LIST_COMMAND.md](LIST_COMMAND.md) | Operators | `mimeo list` format reference and scripting examples |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Contributors | Phase tracker, current tasks, completed work |
| [DECISIONS.md](DECISIONS.md) | Contributors | Architectural decision registry (DEC-001 through DEC-014) |
| [CONTEXT.md](CONTEXT.md) | Contributors | Current session state, active tasks, blockers |
| [ABSTRACT.md](ABSTRACT.md) | Background | Original project motivation and requirements |

## Contributor Entry Points

**Starting a session:**

1. Read [IMPLEMENTATION.md](IMPLEMENTATION.md) for current phase and open tasks
2. Read [CONTEXT.md](CONTEXT.md) for recent session state
3. Check [DECISIONS.md](DECISIONS.md) for any relevant prior decisions

**Understanding the codebase:**

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) for component map and workflow diagrams
2. Read [../CONTRIBUTING.md](../CONTRIBUTING.md) for coding standards and PR process

**Debugging a deployment:**

1. Run `mimeo doctor` first
2. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) organized by failure category

## Supplementary Material

| Location | Contents |
|:---------|:---------|
| [chronicles/](chronicles/) | Session-by-session history, one file per phase |
| [archive/](archive/) | Historical documents (superseded plans) |
| [../scripts/](../scripts/) | Smoke test and utility scripts; see [../scripts/README.md](../scripts/README.md) |
| [../config.toml.example](../config.toml.example) | Annotated configuration template |

## Phase Status

Current phase: **Phase 6 — Hardening**

| Phase | Status |
|:------|:-------|
| Phase 0: Research and Design | Complete |
| Phase 1: Core Infrastructure | Complete |
| Phase 2: Porkbun Integration | Complete |
| Phase 3: GitHub Pages Integration | Complete |
| Phase 4: Content Generation | Complete |
| Phase 5: CLI Integration | Complete |
| Phase 6: Hardening | In progress |

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for detailed task breakdown.
