# Code-Sprawl

A fun neon Terminal UI that turns a local repository into a tiny "living city".

## What it shows
- Folders as districts
- Files as buildings
- LoC as building height
- File age as condition
- Python complexity as technical debt heat
- TODO count as weather signal

## Quick start
1. Create and activate a virtual environment
2. Install deps:
   - `pip install -e .`
3. Run in the current repo:
   - `code-sprawl`
4. Run against another repo:
   - `code-sprawl C:/path/to/repo`

## Controls
- Arrow keys pan camera
- `Ctrl+Up` / `Ctrl+Down` or `+` / `-` zoom
- Click a blob/file to select, double-click or `Enter` to drill/open
- `b` to go back one folder scope
- `f` to fit world, `c` to center camera
- `r` to rescan, `q` to quit

## Next upgrades
- True commit timeline time-travel slider
- Animated traffic between hot files
- GitHub Actions district health
- Debt monster mini-game

## Quality gates (CI/CD)

This project includes full GitHub Actions automation:

- CI workflow: linting, formatting checks, type checking, test matrix, coverage artifact, packaging validation
- Security workflow: dependency vulnerability audit (`pip-audit`) and CodeQL static analysis
- Release workflow: build + publish on version tags (`v*`) using `PYPI_API_TOKEN`

Workflows live in [.github/workflows/ci.yml](.github/workflows/ci.yml), [.github/workflows/codeql.yml](.github/workflows/codeql.yml), and [.github/workflows/release.yml](.github/workflows/release.yml).

## Local QA commands

Install development tooling:

- `python -m pip install -e .[dev]`

Run checks manually:

- `ruff check .`
- `black --check .`
- `mypy`
- `pytest`
- `pip-audit`

Or use the Makefile:

- `make check` (lint + format + types + tests)
- `make all` (check + security + build + package validation)

## Pre-commit hooks

Enable hooks locally:

- `pre-commit install`

Config is in [.pre-commit-config.yaml](.pre-commit-config.yaml).
