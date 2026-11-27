# Authentication, diagnostics and limitations

## Authentication lifecycle

The client uses the remote-access web endpoints `home.fibaro.com/cmh/api/authorize`, `/cmh/api/session`, `/cmh/api/hc/list`, `id.cloud.fibaro.com/login` and `home.fibaro.com/newProxyLite`. The redirect allowlist also includes `id.yubii.cloud` and `remote.yubii.cloud`. These are undocumented web endpoints with no verified public API contract; cloud changes can break access.

Login seeds the authorization flow, obtains cookies and an XSRF token, and submits the cloud username/password. `/cmh/api/session` supplies `user` and `tempKey` for proxy requests. Local hub credentials are separately sent as Basic authentication over HTTPS to authorize hub API access. Authenticated proxy redirects never forward hub credentials.

Home Assistant stores both credential pairs and the selected hub serial in the config entry. Password fields are masked in forms. Cookies and session keys live only in memory and are cleared before a fresh login. Restarting HA requires a fresh login with saved credentials. The integration does not encrypt HA's configuration or backups.

`refresh_session()` reads the current cookie-backed session; it is not an OAuth refresh-token exchange. The implementation exposes no refresh token, and research did not establish a documented refresh endpoint for this protocol. Automatic renewal therefore uses the existing login flow. MFA, CAPTCHA and interactive verification are not automated.

## Renewal, concurrency and errors

An executor-side lock serializes polling, session checks, login and commands for each connection. Every operation checks the session first. An expired session triggers login using stored credentials. If a hub read fails authentication after that check, the snapshot can be read once more, with at most one fresh login per operation. This covers expiry between the session check and the read. HTTP 401/403 from the proxy cannot reliably distinguish cloud expiry from rejected hub credentials; a persistent failure after the bounded login attempt falls back to manual reauth.

Rejected authentication is latched for the connection so queued jobs cannot repeatedly submit credentials. Reload or successful manual reauth creates a new connection. Temporary login failures impose a 60-second cooldown. Network/TLS failures, HTTP 429/5xx and malformed responses remain connection errors rather than invalid credentials. Known login redirects and missing sessions are treated as authentication failures; arbitrary HTML is not assumed to be a login page.

Reads are safe to repeat; commands are never replayed. After command authentication failure, the integration checks whether the session expired or changed. If renewal succeeds, the command still reports failure and asks the user to check device state. If the session remains unchanged and valid, the authentication/permission failure falls back to reauth. A timed-out command may already have executed.

The coordinator maps authentication errors to HA reauth and temporary errors to update failures. The manual reauth form validates both credential pairs with a snapshot before updating the entry and reloading it. Options and selected hub identity are retained.

## Polling and entities

Polling runs every 60 seconds. Each snapshot reads hub information and the full device list even if few devices are selected. There is no push subscription or configurable polling interval. Requests have a 30-second timeout each. Successful commands trigger an immediate refresh and another approximately two seconds later; states are hub-confirmed rather than optimistic.

The device-count sensor counts supported main devices, including unselected ones. Its `selected_devices` attribute counts selected main-device IDs and `fibaro_api_objects` counts raw API objects. These totals may differ. Invalid battery readings such as `255` are unknown. Existing registry migrations retain entity IDs where possible and consolidate duplicate battery entities.

## Diagnostics and Git hygiene

The diagnostics export contains status/counts and masked configuration values. `SENSITIVE_KEYS` includes cloud and hub credentials, account identifiers including `account_id`, serial numbers, names, locations, authorization headers, cookies, XSRF tokens, session keys and refresh tokens. Every config entry and option value is masked, including future unknown fields. Raw hub responses, client objects, error objects and request URLs are never exported.

Diagnostics masking does not sanitize arbitrary logs or Git commits. Do not commit `.storage`, configuration, backups, credentials, cookies or live responses. The ignore rules cover common private artifacts but do not protect already tracked files. Review the complete diff and file inventory before publication. Synthetic tests must use dummy data and block live network calls.

Transport errors are sanitized and the client does not log credentials or payloads. Review third-party logs before sharing. No live login, session-expiry or device-control validation is implied by the automated tests; see [CONTRIBUTING.md](../CONTRIBUTING.md) for the test environment and publication checks.

## Verification of automatic renewal (2026-11-27)

- 82 tests passed with Home Assistant 2026.11.0 and Python 3.14.8, with remote network calls blocked. Five deprecation warnings came from dependencies.
- Coverage includes simultaneous successful/rejected logins, expiry during reads, bounded retries, temporary login cooldown, non-replay of commands, HTTP/network error classification, manual reauth and diagnostics masking.
- Python compilation, the isolated HA configuration check and Git whitespace checks passed. On this Windows machine, pytest required a fresh `--basetemp` directory because its default temporary directory was inaccessible.
- A targeted credential/token-pattern and Python literal scan checked 41 working-tree files and 38 historical Git blobs without findings. This is a limited check, not a guarantee that arbitrary future files are safe to publish.
- No production credentials, live hub commands, deployment or GitHub push were used. Without the original failure logs or a live expiry reproduction, the precise cause of the user's reauth prompt remains unconfirmed.
