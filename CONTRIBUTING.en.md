# Contributing to CortexWatcher

Thank you for your interest in helping! Follow these rules to speed up reviews and keep quality high.

## Style
- Python 3.11 with typing and docstrings.
- Formatting: `black`.
- Linting: `ruff`.
- Type checks: `mypy --strict`.
- Comments and documentation should remain in Ukrainian unless otherwise required.

## Branches and commits
- Name branches `codex/YYYYMMDD-short-description`.
- Commit message format: `type: short summary [#ID]`.
- Provide detailed descriptions and impact notes for large changes.

## Tests
- Any logic change must be covered by tests (`pytest`, `pytest-asyncio`).
- Minimum module coverage: 80%.

## Pull Request
- Describe what changed and why.
- Link to the related task.
- Include a checklist (tests, linters, secrets).
- Update `CHANGELOG.md` for release changes.

## Security
- Do not commit secrets to the repository.
- Use `.env` and `.env.example` for configuration.
- Report vulnerabilities via `SECURITY.md`.

Thanks for contributing!
