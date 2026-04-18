# Code-Sprawl

A fun neon Terminal UI that turns a local repository into an interactive 2D world.

## Highlights
- Full-screen world viewport with animated folder "blobs"
- Free camera pan and zoom controls
- Folder drill-down navigation and scope backtracking
- File and folder inspector with repo metrics
- Minimap for spatial orientation

## Requirements
- Python 3.10+
- Git repository (local)

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

## Development setup
Install development dependencies:

- `python -m pip install -e .[dev]`

Enable pre-commit hooks:

- `pre-commit install`

Local quality checks:

- `ruff check .`
- `black --check .`
- `mypy`
- `pytest`

Convenience commands:

- `make check` (lint + format-check + type-check + tests)
- `make all` (check + security audit + build + package checks)

## CI/CD pipelines
GitHub Actions workflows are included for full automation:

- `CI` workflow: linting, formatting checks, type checks, test matrix, coverage artifact, package build validation
- `CodeQL` workflow: static security analysis for Python
- `Release` workflow: build + publish on tags matching `v*` (requires `PYPI_API_TOKEN` secret)

Workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/release.yml`

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
