#!/bin/sh

set -e

cd "$(dirname "$0")/.."

# if --fix is passed, set flags
if [ "$1" = "--fix" ]; then
  BLACK_ARGS=""
  RUFF_ARGS="--fix"
else
  BLACK_ARGS="--check"
  RUFF_ARGS=""
fi

black "$BLACK_ARGS" .
ruff check "$RUFF_ARGS" .
pyright
