# Technology Stack

**Analysis Date:** 2026-02-10

## Languages

**Primary:**
- Python 3.11+ - Core library implementation (all files in `volkswagencarnet/`)

## Runtime

**Environment:**
- Python 3.11+ (minimum specified in `setup.cfg`)
- Virtual environment via venv (recommended in CLAUDE.md)
- CPython 3.13.5 (actual environment detected)

**Package Manager:**
- pip (via requirements.txt)
- setuptools >= 65 (build system)
- Lockfile: `requirements.txt`, `requirements-test.txt` (frozen, manually maintained)

## Frameworks

**Core:**
- aiohttp - Async HTTP client for API communication (`volkswagen.carnet/vw_connection.py`)

**Testing:**
- pytest >= 7.0.0 - Test runner and framework
- pytest-asyncio - Async test support
- pytest-cov >= 3.0.0 - Code coverage reporting
- pytest-subtests - Subtest support for parameterized tests

**Build/Dev:**
- setuptools_scm >= 6.0 - Automatic versioning from git tags (writes to `volkswagencarnet/version.py`)
- pre-commit - Git hook framework (`setup.cfg` and `.pre-commit-config.yaml`)
- ruff - Code formatting tool (mentioned in CLAUDE.md for `ruff format`)

**Utilities:**
- beautifulsoup4 - HTML parsing for OAuth form extraction (`vw_connection.py`)
- lxml - XML parsing library (dependency of beautifulsoup4)
- PyJWT - JWT token validation for OAuth tokens (`vw_connection.py`)

**Testing Dependencies:**
- freezegun >= 1.0.0 - Time mocking for testing

## Key Dependencies

**Critical:**
- aiohttp [all async HTTP] - All API communication, OAuth flows, token management
- pyjwt [token validation] - Validates JWT tokens from OAuth identity provider
- beautifulsoup4 [HTML parsing] - Extracts state tokens and form fields during OAuth login
- lxml [XML parsing] - HTML parsing backend

**Infrastructure:**
- setuptools_scm [versioning] - Automatic semantic versioning from git tags (stores in `version.py`)

## Configuration

**Environment:**
- Region auto-detection from `country` parameter (maps to EMEA or NA via `vw_const.py`)
- EMEA (default): Base API `https://emea.bff.cariad.digital`, Client ID `a24fba63-34b3-4d43-b181-942111e6bda8@apps_vw-dilab_com`
- North America: Base API `https://b-h-s.spr.us00.p.con-veh.net`, Client ID `b680e751-7e1f-4008-8ec1-3a528183d215@apps_vw-dilab_com` (2026 confirmed)
- Identity endpoint (NA only): `https://identity.na.vwgroup.io`
- No .env file used - credentials passed at runtime

**Build:**
- `setup.cfg` - Setuptools configuration, Python requirements, code style (max 120 chars)
- `pyproject.toml` - PEP 517 build backend (setuptools), pytest configuration
- `.pre-commit-config.yaml` - Git hooks for:
  - JSON/YAML/TOML validation
  - No commits to main/master branches
  - Python 3.7+ syntax upgrade via pyupgrade
  - mypy type checking
  - Trailing whitespace cleanup

## Platform Requirements

**Development:**
- Python 3.11+ (3.13.5 tested)
- venv (project uses virtual environment)
- pip >= 20.0 (for installing from requirements.txt)
- Pre-commit hooks (optional, recommended in CLAUDE.md)

**Production:**
- Python 3.11+ runtime
- aiohttp-compatible async environment (used in Home Assistant via `vw_dashboard.py`)
- HTTPS connectivity to Volkswagen API endpoints (EMEA and NA)

## Code Quality Standards

**Formatting:**
- Max line length: 120 characters (configured in `setup.cfg`)
- Ignores E722 (do not enforce bare except)
- Linting via ruff (format checks in pre-commit)
- Type checking via mypy (in pre-commit)

**Testing Coverage:**
- Coverage configured in `setup.cfg` to track branch coverage
- Omits `tests/*` and `volkswagencarnet/version.py` from coverage
- Test discovery: files matching `*_test.py` in `tests/` directory

---

*Stack analysis: 2026-02-10*
