# Technology Stack

**Analysis Date:** 2026-03-10

## Languages

**Primary:**
- Python 3.11+ - All library code, tests, build scripts

## Runtime

**Environment:**
- Python 3.11+ (minimum), 3.13 used in pre-commit config

**Package Manager:**
- pip with venv (`venv/` and `.venv/` both present)
- Lockfile: Not present (requirements.txt pins without hashes)

## Frameworks

**Core:**
- None — pure Python library (no web framework)
- `aiohttp` — async HTTP client, the primary I/O mechanism throughout `vw_connection.py`

**Testing:**
- `pytest` >=7.0.0 — test runner
- `pytest-asyncio` — async test support (strict mode, configured in `pyproject.toml`)
- `pytest-cov` >=3.0.0 — coverage reporting
- `pytest-subtests` — subtest support
- `aioresponses` >=0.7.4 — mock aiohttp responses in unit tests
- `freezegun` >=1.0.0 — datetime mocking

**Build/Dev:**
- `setuptools` >=65 — package build backend
- `wheel` >=0.37.0 — wheel packaging
- `setuptools_scm` >=6.0 — version derived from git tags, written to `volkswagencarnet/version.py`
- `pre-commit` — pre-commit hooks for code quality
- `ruff` — code formatting (referenced in `CLAUDE.md`, not listed in requirements-test.txt)
- `mypy` v1.15.0 — type checking via pre-commit hook (targets `vw_connection.py` and `vw_vehicle.py`)
- `pyupgrade` v2.31.0 — auto-upgrades to Python 3.7+ syntax
- `detect-secrets` v1.5.0 — prevents committing secrets, baseline in `.secrets.baseline`

## Key Dependencies

**Critical:**
- `aiohttp` — all HTTP requests (GET/POST/PUT), session management, timeouts; used throughout `volkswagencarnet/vw_connection.py`
- `beautifulsoup4` — HTML parsing of OAuth login forms, state token extraction; used in `vw_connection.py`
- `lxml` — parser backend for BeautifulSoup (faster than html.parser)
- `pyjwt` — JWT decode/verify for IDK tokens, RS256 algorithm; used in `vw_connection.py`

**Infrastructure:**
- `cryptography` — JWT signature verification support (test dependency, may also support RS256 in runtime)

## Configuration

**Environment:**
- No `.env` loading library used — credentials passed directly as constructor arguments to `Connection(session, username, password, country)`
- Testing credentials stored in `tests/credentials.py.sample` (sample only)
- `testing_creds.env` file present at project root (not read by library code — for manual testing only)

**Build:**
- `pyproject.toml` — build system config, pytest options, `setuptools_scm` config
- `setup.cfg` — package metadata, install_requires, pycodestyle, coverage, mypy settings
- `.pre-commit-config.yaml` — pre-commit hooks configuration

**Pytest configuration** (`pyproject.toml`):
- `asyncio_mode = "strict"` — all async tests must be explicitly marked
- `testpaths = ["tests"]`
- `norecursedirs = ["tests/e2e"]` — e2e tests excluded from default run

## Platform Requirements

**Development:**
- Python 3.11+
- Virtual environment required (system Python is PEP 668 externally managed)
- Use `venv/bin/python` or `.venv/bin/python` for commands

**Production:**
- No server required — this is a client library
- Intended for use as a dependency (e.g., Home Assistant integration)
- Deployed via PyPI as `volkswagencarnet` package
- Versioned from git tags via `setuptools_scm`

---

*Stack analysis: 2026-03-10*
