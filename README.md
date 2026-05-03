# Code-Sprawl

Code-Sprawl is a Textual-based terminal application that scans a local repository and renders it as a 2D world.

## What it shows
- Folders as nodes in the world
- Files as smaller nodes
- Node size reflects repository metrics in the viewport
- File age, commit count, complexity, and TODO count in the inspector
- A minimap for the current scope

## Requirements
- Python 3.10 or later
- A local repository path to scan

## Installation
Create a virtual environment, then install the package:

```bash
python -m pip install -e .
```

For development dependencies:

```bash
python -m pip install -e .[dev]
```

## Running
Run against the current directory:

```bash
code-sprawl
```

Run against a specific path:

```bash
code-sprawl C:/path/to/repo
```

If the console script is not on your PATH, use:

```bash
python -m code_sprawl.main
```

## Controls
| Action | Keys |
|---|---|
| Pan camera | Arrow keys |
| Zoom | `Ctrl+Up` / `Ctrl+Down` or `+` / `-` |
| Select next / previous node | `Tab` / `Shift+Tab` |
| Snap camera to selected node | `g` |
| Drill into a folder | `Enter` |
| Go back one folder scope | `b` |
| Fit world bounds | `f` |
| Center camera | `c` |
| Rescan current scope | `r` |
| Quit | `q` |

Mouse:

- Single click: focus a node
- Double click: activate the focused node

## Development checks
Common checks used in this repository:

- `black --check .`
- `ruff check .`
- `pytest`

## Notes
- The application is designed for local repositories.
- Commit-related metrics depend on git history being available for the scanned path.
