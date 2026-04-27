"""Smoke tests for plato-edge.

Run with: pytest tests/
"""

import socket
import struct
import threading
import time

import pytest

from plato_edge import (
    Beacon,
    DeadbandGate,
    Flywheel,
    Tile,
    TileCodec,
    Tracer,
    classify,
)


class TestTileSpec:
    def test_roundtrip(self):
        t = Tile(x=1, y=2, z=3, payload=b"hello", meta={"k": 42})
        data = TileCodec.encode(t)
        t2 = TileCodec.decode(data)
        assert t == t2

    def test_no_meta(self):
        t = Tile(x=0, y=0, z=0, payload=b"")
        data = TileCodec.encode(t)
        t2 = TileCodec.decode(data)
        assert t == t2

    def test_bad_magic(self):
        with pytest.raises(Exception):
            TileCodec.decode(b"XXXX")

    def test_bounds(self):
        from plato_edge.tile_spec import validate_bounds

        tiles = [Tile(x=1, y=1, z=10, payload=b"")]
        validate_bounds(tiles)
        with pytest.raises(Exception):
            validate_bounds([Tile(x=10_000_000, y=0, z=0, payload=b"")])


class TestDeadband:
    def test_default_classify(self):
        assert classify("ALERT: engine failure") == DeadbandGate.P0
        assert classify("WARN: temperature high") == DeadbandGate.P1
        assert classify("debug log line") == DeadbandGate.P2

    def test_custom_gate(self):
        g = DeadbandGate(p0_patterns=[r"URGENT"], p1_patterns=[r"NOTICE"])
        assert g.classify("URGENT") == DeadbandGate.P0
        assert g.classify("NOTICE") == DeadbandGate.P1
        assert g.classify("other") == DeadbandGate.P2

    def test_callbacks(self):
        g = DeadbandGate(p0_patterns=[r"URGENT"])
        called = []
        g.gate("URGENT", p0_cb=lambda x: called.append(x))
        assert len(called) == 1


class TestFlywheel:
    def test_kv(self):
        f = Flywheel()
        f.set("a", 1)
        assert f.get("a") == 1
        assert f.get("missing") is None
        assert f.delete("a")
        assert not f.delete("a")

    def test_ttl(self):
        f = Flywheel()
        f.set("k", "v", ttl=0.01)
        assert f.get("k") == "v"
        time.sleep(0.05)
        assert f.get("k") is None

    def test_pubsub(self):
        f = Flywheel()
        received = []
        f.subscribe("t", lambda m: received.append(m))
        n = f.publish("t", "msg")
        assert n == 1
        assert received == ["msg"]
        f.unsubscribe("t", lambda m: None)
        assert f.unsubscribe("t", lambda m: received.append(m)) is False

    def test_stats(self):
        f = Flywheel()
        f.set("x", 1)
        f.subscribe("y", lambda _: None)
        s = f.stats()
        assert s["kv_count"] == 1
        assert s["topic_count"] == 1


class TestKeeper:
    def test_ping_pong(self):
        received = []

        def on_ping(msg, addr):
            received.append(msg)

        b1 = Beacon(port=37202, identity={"name": "a"}, on_ping=on_ping)
        b2 = Beacon(port=37202, identity={"name": "b"})
        b1.start()
        b2.start()
        time.sleep(0.05)
        try:
            pongs = b2.ping(host="127.0.0.1", timeout=0.5)
            assert len(pongs) >= 1
            assert any(p["type"] == "pong" for p in pongs)
        finally:
            b1.stop()
            b2.stop()

    def test_bad_port(self):
        b = Beacon(port=99999)
        with pytest.raises(OverflowError):
            b.start()


class TestExplain:
    def test_trace_id(self):
        tid = Tracer.trace_id()
        assert isinstance(tid, str)
        assert len(tid) == 24

    def test_span(self):
        tr = Tracer()
        tid, t0 = tr.start("op1")
        time.sleep(0.01)
        tr.end(tid, t0, meta={"status": "ok"})
        spans = tr.spans(tid)
        assert len(spans) == 1
        assert spans[0]["name"] == "op1"
        assert spans[0]["meta"]["status"] == "ok"
        assert spans[0]["t1"] > spans[0]["t0"]

    def test_last_and_drop(self):
        tr = Tracer()
        tid, t0 = tr.start("op")
        tr.end(tid, t0)
        assert tr.last(tid) is not None
        assert tr.drop(tid)
        assert tr.last(tid) is None

    def test_max_spans(self):
        tr = Tracer(max_spans=2)
        tid = tr.trace_id()
        for i in range(5):
            _, t0 = tr.start(f"op{i}", trace_id=tid)
            tr.end(tid, t0)
        assert len(tr.spans(tid)) <= 2
