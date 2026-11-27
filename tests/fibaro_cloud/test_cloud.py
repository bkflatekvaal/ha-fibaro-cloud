"""Synthetic transport failures must not expose secrets or trigger false reauth."""
import io
import http.client
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from custom_components.fibaro_cloud.cloud import (
    AuthenticationError, CloudClient, ProbeError, RestrictedRedirect,
)


def response(payload, url="https://home.fibaro.com/cmh/api/session"):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.geturl.return_value = url
    result.read.return_value = payload
    return result


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503])
def test_http_classification_and_safe_errors(status, caplog):
    api = CloudClient()
    api.opener.open = Mock(side_effect=HTTPError(
        "https://home.fibaro.com/?temp=SECRET", status, "SECRET", {}, io.BytesIO(b"SECRET")))
    with pytest.raises(ProbeError) as error:
        api.refresh_session()
    assert isinstance(error.value, AuthenticationError) == (status in (401, 403))
    assert "SECRET" not in str(error.value) + caplog.text
    assert error.value.__suppress_context__


@pytest.mark.parametrize("failure", [URLError("SECRET"), TimeoutError("SECRET"),
                                        http.client.IncompleteRead(b"SECRET")])
def test_transport_errors_are_temporary(failure):
    api = CloudClient()
    api.opener.open = Mock(side_effect=failure)
    with pytest.raises(ProbeError) as error:
        api.refresh_session()
    assert not isinstance(error.value, AuthenticationError)
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("payload", [b'<html>Gateway unavailable</html>', b'[]', b'{', b'{"user":"test"}', b'{"error":"maintenance"}'])
def test_malformed_session_is_not_invalid_credentials(payload):
    api = CloudClient()
    api.opener.open = Mock(return_value=response(payload))
    with pytest.raises(ProbeError) as error:
        api.refresh_session()
    assert not isinstance(error.value, AuthenticationError)


@pytest.mark.parametrize("url,payload", [
    ("https://id.yubii.cloud/login", b'<html>Sign in</html>'),
    ("https://home.fibaro.com/cmh/api/session", b'{}'),
])
def test_missing_session_or_known_login_redirect_is_auth(url, payload):
    api = CloudClient()
    api.opener.open = Mock(return_value=response(payload, url))
    with pytest.raises(AuthenticationError):
        api.refresh_session()


@pytest.mark.parametrize("url,auth", [
    ("https://id.yubii.cloud/login", True),
    ("https://home.fibaro.com/unexpected", False),
    ("https://example.com/login", False),
])
def test_proxy_redirect_never_forwards_hub_password(url, auth):
    req = Request("https://home.fibaro.com/newProxyLite?temp=SECRET", headers={"Authorization": "Basic SECRET"})
    with pytest.raises(ProbeError) as error:
        RestrictedRedirect().redirect_request(req, None, 302, "", {}, url)
    assert isinstance(error.value, AuthenticationError) == auth
    assert "SECRET" not in str(error.value)


def test_login_discards_old_session_and_cookies():
    api = CloudClient()
    api.session = {"user": "old", "tempKey": "old"}
    api.cookies = Mock()
    api.request = Mock(side_effect=[None, None, {"user": "new", "tempKey": "new"}])
    api.cookies.__iter__ = Mock(return_value=iter([]))
    assert api.login("dummy", "dummy") == {"user": "new", "tempKey": "new"}
    api.cookies.clear.assert_called_once()
