#!/bin/sh
uv run --extra dev ruff check . && uv run --extra dev ruff format --check . && uv run --extra dev pytest -q
