from __future__ import annotations

import argparse
from pathlib import Path

from .ui.app import CodeSprawlApp


def run() -> None:
    parser = argparse.ArgumentParser(description="Visualize a repository as a neon code sprawl")
    parser.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    args = parser.parse_args()

    repo_path = Path(args.path).expanduser().resolve()
    app = CodeSprawlApp(repo_path=repo_path)
    app.run()


if __name__ == "__main__":
    run()
