dev-install:
    pip install -e .[dev]

lint:
    black --check .
    ruff check .
    pyright

lint-fix:
    black . || true
    ruff check --fix . || true
    pyright

