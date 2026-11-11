"""No live network calls or real device fixtures."""
from unittest.mock import Mock

import pytest

from custom_components.fibaro_cloud.cloud import AuthenticationError, CloudClient, ProbeError, basic_auth
from custom_components.fibaro_cloud.runtime import CloudConnection
from custom_components.fibaro_cloud.readings import number, project_devices

CONFIG = dict(cloud_username="cloud", cloud_password="dummy", hub_username="local", hub_password="dummy", hub_serial="TEST")


def client():
    result = Mock(session={"user": "test", "tempKey": "dummy"})
    result.read_api.side_effect = [{"serialNumber": "TEST"}, []]
    return result


def test_expired_session_reauth_once():
    api = client()
    api.refresh_session.side_effect = AuthenticationError("Expired")
    assert CloudConnection(CONFIG, api).snapshot()["device_count"] == 0
    api.login.assert_called_once_with("cloud", "dummy")


def test_failed_relogin_not_retried():
    api = client()
    api.refresh_session.side_effect = AuthenticationError("Expired")
    api.login.side_effect = AuthenticationError("Rejected")
    with pytest.raises(AuthenticationError):
        CloudConnection(CONFIG, api).snapshot()
    api.login.assert_called_once()
    api.read_api.assert_not_called()


@pytest.mark.parametrize("error", [ProbeError("Network"), AuthenticationError("Hub rejected")])
def test_hub_failure_never_replays(error):
    api = client()
    api.read_api.side_effect = error
    with pytest.raises(ProbeError):
        CloudConnection(CONFIG, api).snapshot()
    api.login.assert_not_called()
    api.read_api.assert_called_once()


def test_network_failure_never_logs_in():
    api = client()
    api.refresh_session.side_effect = ProbeError("Network")
    with pytest.raises(ProbeError):
        CloudConnection(CONFIG, api).snapshot()
    api.login.assert_not_called()


def test_identity_mismatch():
    api = client()
    api.read_api.side_effect = [{"serialNumber": "OTHER"}, []]
    with pytest.raises(ProbeError, match="does not match"):
        CloudConnection(CONFIG, api).snapshot()


def test_proxy_encoding_and_allowlist():
    api = CloudClient()
    api.session = {"user": "a&b", "tempKey": "x+y"}
    api.request = Mock(return_value=[])
    api.read_api("TEST", "/api/devices", basic_token=basic_auth("a", "b"))
    url = api.request.call_args.args[0]
    from urllib.parse import urlsplit, parse_qs
    assert parse_qs(urlsplit(url).query) == {"user": ["a&b"], "temp": ["x+y"], "hc": ["TEST"], "req": ["/api/devices"]}
    with pytest.raises(ProbeError):
        api.read_api("TEST", "/api/devices/1/action/turnOn")
    assert api.request.call_count == 1


@pytest.mark.parametrize("value", [None, True, "", "NaN", "inf", {}, []])
def test_bad_numbers(value):
    assert number(value) is None


def test_projection():
    devices = [dict(id=1, name="Test", type="com.fibaro.temperatureSensor", properties=dict(value="21.5", unit="C", batteryLevel=255, secret="omit")), dict(id=2, enabled=False, properties={"power": 4})]
    projected = project_devices(devices)
    assert list(projected) == [1]
    assert projected[1]["readings"]["value"] == dict(kind="temperature", value=21.5, unit="°C")
    assert projected[1]["readings"]["batteryLevel"]["value"] is None
    assert "secret" not in repr(projected)
    devices[0]["properties"].pop("unit")
    assert "value" not in project_devices(devices)[1]["readings"]


def test_device_count_counts_physical_devices_instead_of_api_objects():
    api = client()
    raw = [
        {'id': 1, 'parentId': 0, 'type': 'com.fibaro.zwavePrimaryController'},
        {'id': 10, 'parentId': 1, 'properties': {'batteryLevel': 80}},
        {'id': 11, 'parentId': 10, 'type': 'com.fibaro.temperatureSensor',
         'properties': {'value': 20, 'unit': 'C', 'batteryLevel': 80}},
        {'id': 12, 'parentId': 10, 'type': 'com.fibaro.humiditySensor',
         'properties': {'value': 50, 'batteryLevel': 80}},
        {'id': 20, 'parentId': 1, 'properties': {}},
        {'id': 21, 'parentId': 20, 'properties': {'power': 10}},
    ]
    api.read_api.side_effect = [{'serialNumber': 'TEST'}, raw]
    snapshot = CloudConnection(CONFIG, api).snapshot()
    assert snapshot['device_count'] == 2
    assert snapshot['fibaro_object_count'] == 6
    assert sum(len(d['readings']) for d in snapshot['devices'].values()) == 4
