"""Independent synchronous client for the Fibaro remote-access web protocol."""
from __future__ import annotations
import base64
import http.cookiejar
import json

from .capabilities import ACTIONS
import urllib.error
import urllib.parse
import urllib.request

HOME = "https://home.fibaro.com"
IDENTITY = "https://id.cloud.fibaro.com"
ALLOWED_HOSTS = {"home.fibaro.com", "id.cloud.fibaro.com", "id.yubii.cloud", "remote.yubii.cloud"}


class ProbeError(Exception):
    """Safe error message, containing no request URLs or credentials."""


class AuthenticationError(ProbeError):
    """Credentials rejected or cloud session expired."""


def check_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ProbeError("Unexpected destination in authentication flow; stopped.")


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        # A proxy redirect must not carry hub credentials to another endpoint.
        if req.has_header("Authorization") or req.has_header("X-fibaro-auth"):
            raise ProbeError("Authenticated API request redirected; stopped.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CloudClient:
    def __init__(self, timeout: float = 30):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            RestrictedRedirect(), urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.timeout = timeout
        self.session: dict = {}

    def request(self, url: str, *, data: bytes | None = None,
                headers: dict | None = None, expect_json: bool = True, allow_empty: bool = False):
        check_url(url)
        req = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = response.read(8_000_001)
                if len(payload) > 8_000_000:
                    raise ProbeError("Response exceeds size limit.")
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (401, 403):
                raise AuthenticationError(f"Access rejected (HTTP {status}). No automatic login retry.") from None
            raise ProbeError(f"Server returned HTTP {status}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProbeError("Network/TLS connection failed or timed out.") from None
        if not expect_json:
            return None
        if allow_empty and not payload.strip():
            return None
        try:
            return json.loads(payload)
        except (ValueError, UnicodeError):
            raise ProbeError("Expected JSON; received a login page or other response.") from None

    def login(self, username: str, password: str):
        # Seed both cookie jars and the server-side OAuth authorization request.
        self.request(HOME + "/cmh/api/authorize", expect_json=False)
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Origin": IDENTITY, "Referer": IDENTITY + "/login"}
        for cookie in self.cookies:
            if cookie.name == "XSRF-TOKEN" and cookie.domain.lstrip(".") == "id.cloud.fibaro.com":
                headers["X-XSRF-TOKEN"] = urllib.parse.unquote(cookie.value)
        body = urllib.parse.urlencode({"username": username, "password": password}).encode()
        self.request(IDENTITY + "/login", data=body, headers=headers, expect_json=False)
        return self.refresh_session()

    def refresh_session(self):
        """Re-read session parameters; does NOT claim to renew an expired session."""
        try:
            result = self.request(HOME + "/cmh/api/session")
        except ProbeError as exc:
            if isinstance(exc, AuthenticationError) or str(exc).startswith("Expected JSON"):
                raise AuthenticationError("Cloud session expired or login was not accepted.") from None
            raise
        if not isinstance(result, dict) or not result.get("user") or not result.get("tempKey"):
            raise AuthenticationError("Cloud session is missing. Interactive login or additional verification may be required.")
        self.session = {"user": result["user"], "tempKey": result["tempKey"]}
        return self.session

    def hubs(self):
        result = self.request(HOME + "/cmh/api/hc/list")
        if not isinstance(result, list) or not all(isinstance(h, dict) and h.get("serial") for h in result):
            raise ProbeError("Unexpected hub-list schema; inspect a redacted response before proceeding.")
        return result

    def read_api(self, serial: str, path: str, *, basic_token: str | None = None):
        # Reads and action writes have separate, explicit endpoints.
        if path not in {"/api/settings/info", "/api/loginStatus", "/api/devices", "/api/rooms"}:
            raise ProbeError("Endpoint is outside the read-only allowlist.")
        return self._proxy(serial, path, basic_token=basic_token)

    def call_action(self, serial, device_id, action, args, *, basic_token=None):
        """Send exactly one device action. Never retry an ambiguous write."""
        if type(device_id) is not int or device_id <= 0 or action not in ACTIONS:
            raise ProbeError("Unsupported device action.")
        if not isinstance(args, list) or any(type(arg) not in (int, float, str, bool) for arg in args):
            raise ProbeError("Invalid action arguments.")
        try:
            body = json.dumps({"args": args}, allow_nan=False).encode()
        except (TypeError, ValueError):
            raise ProbeError("Invalid action arguments.") from None
        result = self._proxy(serial, f"/api/devices/{device_id}/action/{action}",
                             basic_token=basic_token, body=body)
        if isinstance(result, dict) and (result.get("error") or result.get("success") is False):
            raise ProbeError("Hub rejected the device action.")
        return result

    def _proxy(self, serial, path, *, basic_token=None, body=None):
        if not self.session:
            raise ProbeError("No cloud session.")
        query = urllib.parse.urlencode({"user": self.session["user"], "hc": serial,
                                       "temp": self.session["tempKey"], "req": path})
        headers = {"Accept": "application/json", "X-Fibaro-Version": "2", "Accept-Language": "en"}
        if basic_token:
            headers["Authorization"] = "Basic " + basic_token
        if body is not None:
            headers["Content-Type"] = "application/json"
            return self.request(HOME + "/newProxyLite?" + query, headers=headers,
                                data=body, allow_empty=True)
        return self.request(HOME + "/newProxyLite?" + query, headers=headers)



def basic_auth(username: str, password: str) -> str:
    if ":" in username:
        raise ProbeError("A Basic Auth username cannot contain a colon.")
    return base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
