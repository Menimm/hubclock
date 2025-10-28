# Repository Guidelines

## Project Structure & Module Organization
- Place runtime code in `src/hubclock/`; create feature folders such as `src/hubclock/scheduling/` and share cross-cutting helpers from `src/hubclock/common/`.
- Mirror that layout in `tests/`, keeping one test module per source module (for example, `tests/scheduling/test_shift_rules.py`).
- Use `scripts/` for automation and `docs/` (with `docs/assets/`) for design notes, diagrams, and configuration templates.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create the local environment; reuse it instead of ad-hoc installs.
- `pip install -r requirements.txt -r requirements-dev.txt` — install runtime and tooling dependencies whenever requirements change.
- `pytest` (optionally `pytest -m integration`) — run fast suites by default and opt in to slower checks when touching integrations.
- `ruff check src tests && ruff format src tests` — keep linting and formatting consistent before every push.

## Coding Style & Naming Conventions
- Write for Python 3.11+, embracing type hints and rejecting untyped public APIs.
- Follow PEP 8 (4 spaces, `snake_case` functions, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants) and rely on `ruff` for enforcement.
- Keep modules cohesive; document integration points with concise docstrings and curate exports via package `__all__`.

## Testing Guidelines
- Use `pytest` with `pytest-cov`; add fixtures in `tests/conftest.py` and scope them to the smallest needed surface.
- Name tests by behavior (`test_scheduler_handles_dst_gap`) and assert on observable outcomes rather than internals.
- Keep coverage above 90% for scheduling logic, add regression tests for every bug fix, and mark slow cases with `@pytest.mark.integration`.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `chore:`) and add a scope when a change is limited (`feat(scheduling): ...`).
- Keep commits atomic, capture the "why" in the body, and call out tickets with `Refs #123` when applicable.
- Include summaries, testing notes (`pytest`, `ruff check`), and artifacts (screenshots, logs) in every PR; request a reviewer and merge only after checks pass.

## Security & Configuration Tips
- Keep secrets in `.env.local`; document required keys in `docs/configuration.md` and commit example templates only.
- Validate inbound payloads (webhooks, CSV imports) before processing, and prefer structured error messages for logging.
- Review dependency bumps with `pip-compile --upgrade` in dedicated PRs; note breaking changes in the changelog and rotate API tokens quarterly.
