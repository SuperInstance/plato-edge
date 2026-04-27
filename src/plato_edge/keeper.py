"""plato_edge.keeper — UDP discovery beacon.

Zero-dependency, pure Python stdlib. Replaces HTTP-based discovery.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class BeaconError(RuntimeError):
    """Beacon operation error."""


class Beacon:
    """UDP discovery beacon for local fleet coordination."""

    __slots__ = (
        "_port",
        "_ttl",
        "_sock",
        "_thread",
        "_running",
        "_identity",
        "_on_ping",
    )

    def __init__(
        self,
        port: int = 37201,
        ttl: int = 2,
        identity: Optional[Dict[str, Any]] = None,
        on_ping: Optional[Callable[[Dict[str, Any], Tuple[str, int]], None]] = None,
    ) -> None:
        self._port = port
        self._ttl = ttl
        self._identity = dict(identity) if identity else {}
        self._on_ping = on_ping
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _get_socket(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self._ttl)
            self._sock = s
        return self._sock

    def start(self, bind: str = "0.0.0.0") -> None:
        """Start listening for pings."""
        if self._running:
            return
        self._running = True
        sock = self._get_socket()
        sock.bind((bind, self._port))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the beacon."""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while self._running:
            try:
                data, addr = self._sock.recvfrom(2048)  # type: ignore[union-attr]
            except OSError:
                break
            if not self._running:
                break
            msg = _decode(data)
            if msg is None:
                continue
            if msg.get("type") == "ping":
                reply = {
                    "type": "pong",
                    "ts": time.time(),
                    "id": self._identity,
                }
                self._send(reply, addr[0], addr[1])
                if self._on_ping:
                    try:
                        self._on_ping(msg, addr)
                    except Exception:
                        pass
            elif msg.get("type") == "pong" and self._on_ping:
                try:
                    self._on_ping(msg, addr)
                except Exception:
                    pass

    def ping(
        self,
        host: str = "255.255.255.255",
        timeout: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Broadcast a ping and collect pongs."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        msg = {"type": "ping", "ts": time.time()}
        data = _encode(msg)
        if data is None:
            raise BeaconError("failed to encode ping")
        sock.sendto(data, (host, self._port))
        responses: List[Dict[str, Any]] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                rdata, _ = sock.recvfrom(2048)
            except socket.timeout:
                break
            rmsg = _decode(rdata)
            if rmsg and rmsg.get("type") == "pong":
                responses.append(rmsg)
        sock.close()
        return responses

    def _send(self, msg: Dict[str, Any], host: str, port: int) -> None:
        data = _encode(msg)
        if data is None or self._sock is None:
            return
        try:
            self._sock.sendto(data, (host, port))
        except OSError:
            pass

    def __enter__(self) -> Beacon:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()


def _encode(msg: Dict[str, Any]) -> Optional[bytes]:
    try:
        return json.dumps(msg, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return None


def _decode(data: bytes) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except (TypeError, ValueError):
        return None
