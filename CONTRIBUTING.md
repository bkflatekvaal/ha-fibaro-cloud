# Development and publication

## Local tests

Use Python 3.14 and an isolated environment. The compatibility suite targets real Home Assistant 2026.11.0 classes, with synthetic hub data and mocked cloud I/O. It covers authentication failures, command transport and non-replay, configuration flows, selection, discovery, grouping, registry migrations, and platform setup/unload. It does not establish hardware compatibility.

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q custom_components/fibaro_cloud tests/fibaro_cloud
```

`pytest.ini` sets the repository import path and enables asynchronous fixtures. The test modules also import shared fixtures from `test_ha.py`; use pytest's default import mode. No separate HA pytest plugin is required. Dependencies are listed in `requirements-dev.txt`; these are development dependencies, not integration manifest requirements. Keep the HA pin aligned with any API changes before expanding the supported version range.

The GitHub Actions workflow runs these checks on Linux after a push or pull request. It creates a virtual environment, which HA's command-line configuration check requires. It has read-only repository permissions and does not publish anything. See the repository's Actions tab for the result of each commit.

Tests must never use a production configuration directory or real credentials. Remote network connections are blocked by `tests/fibaro_cloud/conftest.py` so an accidentally unmocked request fails. Loopback connections remain available for asyncio's internal sockets on Windows. Dependency installation needs internet access before testing.

## Isolated HA configuration check

On Windows, the HA command-line entry point is unsupported. The following script calls HA's configuration-validation helper directly and also works in the local development environment:

```sh
python scripts/check_config.py
```

It creates and retains a fresh directory under the operating system's temporary directory, copies the integration there, and checks an empty YAML configuration without creating a cloud entry.

Use a fresh temporary directory in a suitable HA development environment, never your production configuration. For example, in a POSIX shell with the environment above activated:

```sh
CHECK_CONFIG=$(mktemp -d)
mkdir -p "$CHECK_CONFIG/custom_components"
cp -R custom_components/fibaro_cloud "$CHECK_CONFIG/custom_components/"
printf '{}\n' > "$CHECK_CONFIG/configuration.yaml"
python -m homeassistant --script check_config --config "$CHECK_CONFIG"
```

This checks a minimal configuration without a configured cloud entry. It does not log in, issue commands, validate a real hub, or replace the pytest platform/config-flow tests. Do not restart production HA or perform physical controls as part of publication checks.

## Verified during publication preparation

On 2026-11-11, Python 3.14.10 with Home Assistant 2026.11.0, pytest 9.2.0 and pytest-asyncio 1.4.1.post1 on Windows:

- All 52 existing tests passed with remote connections blocked. Five deprecation warnings came from HA / its dependencies.
- Python compilation and project JSON parsing passed.
- The isolated HA configuration helper returned no errors. The standard HA CLI cannot run natively on Windows; GitHub Actions runs that check separately on Linux.
- The publication inventory and synthetic fixtures were reviewed; no private configuration or live data was found. A credential-pattern scan found no matches. This is not a guarantee about external or future files.

No live device commands, production restart, GitHub push, release, or publication was performed.

## Publication checklist

- Review `git status --short`, `git diff`, `git diff --cached`, and `git ls-files`. Only the integration, synthetic tests, and project metadata/documentation belong in the repository.
- `.gitignore` reduces accidental inclusion; it does not sanitize already tracked files or history. Never add `.storage`, secrets, home configuration, logs, databases, backups, tokens, passwords, raw live responses, or local environments. Do not delete the user's local files to prepare a release.
- Keep Python bytecode out of every published commit. A normal deletion commit does not remove historical blobs. Publication preparation creates a fresh local history with the previous Git metadata backed up outside the repository; do not push that old history back into the public repository.
- Run all tests, compile checks, and an isolated HA configuration check. Record the actual versions and outcomes; do not carry forward a historical test result as a current pass.
- Keep live-test claims limited to the user-confirmed HC3 Lite switch and thermostat control. Lights and covers have only simulated-hub validation.
- Repository links use the configured origin, `https://github.com/bkflatekvaal/ha-fibaro-cloud`. Confirm repository visibility and enable Issues before publishing. Suggested description: “Unofficial Home Assistant integration for Fibaro / Yubii Cloud remote hub access.” Suggested topics: `home-assistant`, `fibaro`, `yubii`, `custom-integration`.
- The existing MIT license and named copyright holder are retained. The source describes an independent web client and explicitly says no upstream implementation was copied. There is no third-party source notice in the supplied files, but repository inspection alone cannot establish the provenance of external contributions. Retain any required notices if additional borrowed code is introduced.
- `manifest.json` names `@bkflatekvaal` as maintainer, confirmed by the repository owner during publication preparation.
- Marketplace metadata is prepared, but installation from the public repository has not been validated. The metadata filename remains `hacs.json`, as required by Marketplace. Follow the [Marketplace publishing guide](https://contributors.home-assistant.io/marketplace/guides/integrations/); do not claim catalog inclusion. A catalog submission and its branding requirements are separate work. No unverified minimum HA version is asserted in `hacs.json`.
- Publishing, pushing, releases, and changes to GitHub settings require a separate user request. The user authorized a fresh local history during preparation; this does not authorize publishing it.
