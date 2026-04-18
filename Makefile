.PHONY: install-dev lint format-check type-check test security build check all

install-dev:
	python -m pip install --upgrade pip
	python -m pip install -e .[dev]

lint:
	ruff check .

format-check:
	black --check .

type-check:
	mypy

test:
	pytest

security:
	pip-audit

build:
	python -m build

twine-check:
	twine check dist/*

check: lint format-check type-check test

all: check security build twine-check
