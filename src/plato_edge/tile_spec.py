"""plato_edge.tile_spec — lightweight tile format with minimal validation.

No optional dependencies. Pure Python, stdlib only.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple, Union


class TileError(ValueError):
    """Invalid tile data or encoding."""


# Header: magic(4) + version(1) + flags(1) + x(4) + y(4) + z(4) + payload_len(4)
_HEADER_FMT = "<4sBBiiiI"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_MAGIC = b"PLTO"
_VERSION = 1

# Maximum payload to prevent unbounded memory use on malformed input.
_MAX_PAYLOAD = 16 * 1024  # 16 KiB per tile


class Tile:
    """A single spatial tile."""

    __slots__ = ("x", "y", "z", "payload", "meta")

    def __init__(
        self,
        x: int,
        y: int,
        z: int,
        payload: bytes = b"",
        meta: Optional[Dict[str, Union[str, int, float]]] = None,
    ) -> None:
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.payload = bytes(payload)
        self.meta: Dict[str, Union[str, int, float]] = dict(meta) if meta else {}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tile x={self.x} y={self.y} z={self.z} len={len(self.payload)}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Tile):
            return NotImplemented
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
            and self.payload == other.payload
            and self.meta == other.meta
        )

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z, self.payload))


class TileCodec:
    """Encode/decode Tiles to/from compact bytes."""

    @staticmethod
    def encode(tile: Tile) -> bytes:
        """Serialize *tile* to bytes."""
        if len(tile.payload) > _MAX_PAYLOAD:
            raise TileError(f"payload exceeds {_MAX_PAYLOAD} bytes")

        # Simple meta encoding: key\0value\0 pairs, values as str.
        meta_bytes = bytearray()
        for k, v in tile.meta.items():
            if "\x00" in k:
                raise TileError("meta key may not contain NUL")
            meta_bytes.extend(k.encode("utf-8", "replace"))
            meta_bytes.append(0)
            meta_bytes.extend(str(v).encode("utf-8", "replace"))
            meta_bytes.append(0)

        flags = 0
        if meta_bytes:
            flags |= 0x01

        header = struct.pack(
            _HEADER_FMT,
            _MAGIC,
            _VERSION,
            flags,
            tile.x,
            tile.y,
            tile.z,
            len(tile.payload),
        )
        parts: List[bytes] = [header, tile.payload]
        if meta_bytes:
            parts.append(bytes(meta_bytes))
        return b"".join(parts)

    @staticmethod
    def decode(data: bytes) -> Tile:
        """Deserialize bytes to a Tile."""
        if len(data) < _HEADER_SIZE:
            raise TileError("data too short for header")

        magic, version, flags, x, y, z, payload_len = struct.unpack(
            _HEADER_FMT, data[:_HEADER_SIZE]
        )
        if magic != _MAGIC:
            raise TileError("bad magic")
        if version != _VERSION:
            raise TileError(f"unsupported version {version}")
        if payload_len > _MAX_PAYLOAD:
            raise TileError(f"payload length {payload_len} exceeds max")

        expected = _HEADER_SIZE + payload_len
        if flags & 0x01:
            # variable-length meta; we just need at least the payload
            if len(data) < expected:
                raise TileError("truncated payload")
        else:
            if len(data) != expected:
                raise TileError("length mismatch")

        payload = data[_HEADER_SIZE : _HEADER_SIZE + payload_len]
        meta: Dict[str, Union[str, int, float]] = {}
        if flags & 0x01:
            meta_raw = data[_HEADER_SIZE + payload_len :]
            meta = _parse_meta(meta_raw)

        return Tile(x, y, z, payload, meta)


def _parse_meta(raw: bytes) -> Dict[str, Union[str, int, float]]:
    """Parse NUL-delimited key/value pairs."""
    out: Dict[str, Union[str, int, float]] = {}
    parts = raw.split(b"\x00")
    # split on NUL produces trailing empty string; ignore it.
    it = iter(parts[:-1] if not parts[-1] else parts)
    for key in it:
        try:
            val = next(it)
        except StopIteration:
            break
        k = key.decode("utf-8", "replace")
        v_str = val.decode("utf-8", "replace")
        out[k] = _coerce(v_str)
    return out


def _coerce(s: str) -> Union[str, int, float]:
    """Best-effort type coercion for meta values."""
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def validate_bounds(tiles: List[Tile], max_dim: int = 1_000_000) -> None:
    """Quick bounds check for a batch of tiles."""
    for t in tiles:
        if not (-max_dim <= t.x <= max_dim):
            raise TileError(f"x out of bounds: {t.x}")
        if not (-max_dim <= t.y <= max_dim):
            raise TileError(f"y out of bounds: {t.y}")
        if t.z < 0 or t.z > 32:
            raise TileError(f"z out of bounds: {t.z}")
