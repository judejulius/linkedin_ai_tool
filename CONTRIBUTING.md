# Contributing

Thanks for helping make LinkedIn Learning Journal useful to more people. Bug
reports, documentation fixes, accessible HTML/CSS improvements, and focused Python
changes are welcome. Read [the code of conduct](CODE_OF_CONDUCT.md) before joining
the discussion. Report security issues through [SECURITY.md](SECURITY.md).

## Development setup

Fork the repository, clone your fork, and create a branch for your change. Use
Python 3.10 or newer on Linux/macOS, or WSL on Windows:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/setup.py
python -m unittest discover -s tests -v
```

Tests use fake API responses and temporary databases. Real API keys, LinkedIn
accounts, and paid requests are not needed to run them.

To inspect the UI locally, set the dashboard password and session secret in `.env`:

```bash
gunicorn --bind 127.0.0.1:5678 --workers 1 --threads 4 --timeout 300 'dashboard:create_app()'
```

Open http://localhost:5678 and sign in as `admin`. Start `python scheduler.py run`
in a second terminal only if you intend to generate drafts with your API account.
See [architecture](docs/ARCHITECTURE.md) for the module and request flow.

## Propose a change

For a substantial feature, open an issue describing the user problem and proposed
behavior first. Small fixes can go directly to a pull request. Keep each PR focused
and include the reason for the change, how you verified it, and any migration steps.
For visual changes, include screenshots at desktop and mobile widths using fake data.

## Implementation expectations

- Keep the UI in `frontend/*.html`, styling in `frontend/*.css`, and browser logic in `frontend/*.js`. A Node toolchain
  is not required. Preserve labels, keyboard access, responsive layouts and escaping.
- Keep credentials on the Python side. Never include personal posts, tokens, `.env`,
  databases, or private logs in a commit, issue, screenshot, or test fixture.
- Every publishing path must require approval of the exact draft version. Preserve
  process locking, CSRF checks, duplicate prevention and uncertain-send recovery.
- Add regression tests for changed behavior, especially auth, approval and storage.
  Mock external APIs; tests must not publish or require network access.
- Make database changes compatible with existing deployments and document migrations.
- State limitations honestly. Do not label a fake integration test as a live API test.
- Update public documentation whenever setup or user behavior changes.

## Before opening your PR

```bash
python -m unittest discover -s tests -v
python -m compileall -q dashboard.py scheduler.py linkedin_auth.py scripts
docker compose config --quiet
docker build -t learning-journal-check .
```

Run the Docker checks if Docker is available; otherwise say that they were not run.
The GitHub workflow runs tests and builds the container without live credentials.
Never use `pull_request_target` to execute untrusted contributor code with secrets.

Contributions are accepted under this repository's MIT license. Keep
third-party notices and only submit material you have permission to contribute.
