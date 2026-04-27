# plato-edge

Edge-optimized Cocapn fleet packages for ARM64 devices with limited resources.

## Target Hardware

- NVIDIA Jetson Orin (ARM64)
- 24 GB RAM shared with GPU
- Python 3.8+ (system default on JetPack)

## Design Goals

| Goal | Constraint |
|------|------------|
| Zero external dependencies | `stdlib` only |
| Installed size | < 50 KB total |
| Runtime memory | < 10 MB RSS combined |
| Network | Works fully offline after install |
| ML frameworks | No `numpy`, `scipy`, `torch`, etc. |

## Modules

### `plato_edge.tile_spec`

Lightweight tile format for spatial/data tiling.

- Compact binary encoding (~22-byte header + payload)
- Optional metadata as NUL-delimited key/value pairs
- Bounds validation with configurable limits
- No optional dependencies

```python
from plato_edge import Tile, TileCodec

tile = Tile(x=1, y=2, z=3, payload=b"hello", meta={"k": 42})
data = TileCodec.encode(tile)
tile2 = TileCodec.decode(data)
```

### `plato_edge.deadband`

P0/P1/P2 priority gate using minimal regex.

- No NLP, no heavy text processing
- Configurable regex patterns per priority level
- Fast default patterns for `ALERT`, `WARN`, `HEARTBEAT`, etc.

```python
from plato_edge import classify, DeadbandGate

level = classify("ALERT: engine failure")  # -> DeadbandGate.P0
```

### `plato_edge.flywheel`

In-memory pub/sub and key-value cache.

- Thread-safe with fine-grained locking
- Optional per-key TTL
- Automatic eviction when capacity limits are reached
- No persistence — everything is in-memory

```python
from plato_edge import Flywheel

fw = Flywheel(max_kv=4096, max_queue=256)
fw.set("key", "value", ttl=60.0)
fw.subscribe("topic", lambda msg: print(msg))
fw.publish("topic", "hello")
```

### `plato_edge.keeper`

UDP discovery beacon replacing HTTP-based service discovery.

- Zero-dependency UDP broadcast/multicast
- JSON ping/pong protocol
- Threaded listener with daemon thread

```python
from plato_edge import Beacon

with Beacon(port=37201, identity={"role": "camera"}) as b:
    peers = b.ping(host="255.255.255.255", timeout=1.0)
```

### `plato_edge.explain`

Stripped explainability — trace IDs only, no full audit log.

- 24-character hex trace IDs (time + random)
- In-memory span tracking with nanosecond resolution
- Automatic span eviction when limit is reached

```python
from plato_edge import Tracer

tr = Tracer(max_spans=1024)
tid, t0 = tr.start("inference")
# ... work ...
tr.end(tid, t0, meta={"status": "ok"})
print(tr.spans(tid))
```

## Installation

```bash
pip install plato-edge
```

## Development

```bash
python -m pytest tests/
```

## License

MIT
