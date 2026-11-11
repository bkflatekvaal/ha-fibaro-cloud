"""Keep the synthetic compatibility suite disconnected from real hubs."""
import socket
from ipaddress import ip_address

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Block remote I/O while allowing asyncio's internal loopback socketpair."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded(original):
        def connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                try:
                    loopback = ip_address(address[0]).is_loopback
                except ValueError:
                    loopback = False
                if not loopback:
                    raise AssertionError("Remote network access is disabled in Fibaro Cloud tests")
            return original(sock, address)
        return connect

    monkeypatch.setattr(socket.socket, "connect", guarded(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(original_connect_ex))
