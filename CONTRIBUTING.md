# Contributing to CherryPick

Thanks for your interest in improving CherryPick. This document covers the
basics for getting a change merged.

## Getting Started

```bash
# Clone the repo
git clone https://github.com/sltcnb/CherryPick.git
cd CherryPick

# Install the project with development extras
pip install -e ".[dev]"

# Install pre-commit hooks (ruff lint/format, whitespace/EOF checks)
pip install pre-commit
pre-commit install
```

## Development Workflow

1. Create a branch off `main` for your change.
2. Make focused, incremental commits with clear messages
   (imperative mood, e.g. `fix: handle missing MFT gracefully`).
3. Run the checks below locally before opening a PR.
4. Open a pull request describing what changed and why.

## Running Tests

```bash
pytest -q
```

Tests cover the chunked upload logic, bundle/manifest signing, the collector
registry, source abstraction, and stub collectors. Please add or update tests
for any behavioral change.

## Linting and Formatting

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and
formatting:

```bash
ruff check .
ruff format .
```

`pre-commit` runs the same checks (plus trailing-whitespace/EOF/YAML checks)
automatically on `git commit` once installed.

## Adding a Collector

Collectors are one-file-per-collector and self-register with the auto-
discovery registry in `collectors/`. Look at an existing collector of similar
complexity as a template, and make sure any new artifact category is reflected
in `capabilities.yaml` (the single source of truth for collectable categories).

## Guidelines for Changes

- Keep collection/forensic logic changes conservative: this tool is used to
  gather evidence, so behavior changes should be well-tested and clearly
  explained in the PR description.
- Avoid introducing new required dependencies where a lazy/optional import
  will do — see `pyproject.toml`'s `[project.optional-dependencies]`.
- Don't weaken the default security posture (e.g. TLS verification, bundle
  signing) without an explicit, documented opt-out and a loud warning, matching
  the existing pattern for `CHERRYPICK_INSECURE_TLS`.

## Reporting Security Issues

Please see [SECURITY.md](SECURITY.md) — do not file security issues as public
GitHub issues.
