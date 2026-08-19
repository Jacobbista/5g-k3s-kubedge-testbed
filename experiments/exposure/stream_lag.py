#!/usr/bin/env python3
"""C10 streaming delivery lag — measure how fresh the pushed positions are.

The CAMARA stream (WS /positions/stream on the gateway) pushes an array of
positions; each carries a `timestamp` that is the source fix time (northbound:
res.primary.fused.timestamp), passed through by the gateway verbatim. So

    lag = client-receive-time  -  payload timestamp

is the end-to-end freshness of a fix (fix -> fusion -> cadence -> network ->
client), NOT a request/response trace. That is a different measure from the
retrieve hop-log, so it lives in its own tool (this one), not the aggregator.

Stdlib only (no `websockets` dependency): a minimal RFC 6455 client that reads
server text frames over plain ws:// (the same-host NodePort surface). It does not
do TLS; for a wss:// front-door use a websockets-based client instead.

CLOCK: the timestamp is minted inside a cluster VM (the adapter pod) and the
arrival is stamped on the host, so the lag spans two clocks. Capture the host<->VM
offset around the run (G6_streaming.sh does) and treat it as a systematic bound.

    stream_lag.py <ws-url-with-?token=...> <duration_s> <out.csv>
"""
import base64
import json
import os
import socket
import struct
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit


def _connect(url: str) -> socket.socket:
    u = urlsplit(url)
    if u.scheme != "ws":
        raise SystemExit(f"only ws:// is supported by this stdlib client (got {u.scheme}://)")
    host, port = u.hostname, u.port or 80
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    s = socket.create_connection((host, port), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    # Read the handshake response head.
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(1024)
        if not chunk:
            raise SystemExit("connection closed during handshake")
        buf += chunk
    if b" 101 " not in buf.split(b"\r\n", 1)[0]:
        raise SystemExit("handshake not upgraded:\n" + buf.split(b"\r\n\r\n", 1)[0].decode(errors="replace"))
    return s


def _recv_exact(s: socket.socket, n: int) -> bytes:
    out = b""
    while len(out) < n:
        chunk = s.recv(n - len(out))
        if not chunk:
            raise ConnectionError("closed")
        out += chunk
    return out


def _read_message(s: socket.socket) -> tuple[str, bytes]:
    """Return (opcode_kind, payload) for one full message, reassembling fragments.
    kind is 'text' | 'close' | 'other'; ping is answered here and skipped."""
    data = b""
    first_op = None
    while True:
        hdr = _recv_exact(s, 2)
        b0, b1 = hdr[0], hdr[1]
        fin = b0 & 0x80
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack(">H", _recv_exact(s, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _recv_exact(s, 8))[0]
        mask = _recv_exact(s, 4) if masked else b""
        payload = _recv_exact(s, length) if length else b""
        if masked:
            payload = bytes(pb ^ mask[i % 4] for i, pb in enumerate(payload))
        if opcode == 0x9:  # ping -> pong (client frames are masked)
            _send_frame(s, 0xA, payload)
            continue
        if opcode == 0x8:  # close
            return "close", payload
        if opcode in (0x1, 0x2, 0x0):
            if first_op is None:
                first_op = opcode
            data += payload
            if fin:
                return ("text" if first_op == 0x1 else "other"), data
        # else control frame we ignore


def _send_frame(s: socket.socket, opcode: int, payload: bytes) -> None:
    mask = os.urandom(4)
    masked = bytes(pb ^ mask[i % 4] for i, pb in enumerate(payload))
    header = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header += bytes([0x80 | n])
    elif n < 65536:
        header += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", n)
    s.sendall(header + mask + masked)


def _parse_ts(v: str) -> datetime:
    # ISO 8601, may carry +00:00 or Z and microseconds.
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def _percentile(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def main() -> int:
    if len(sys.argv) < 4:
        return print(__doc__) or 2
    url, duration, out_csv = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    sock = _connect(url)
    lags: list[float] = []
    msgs = positions = 0
    started = time.time()
    with open(out_csv, "w") as fh:
        fh.write("recv_utc,device_id,source,est_timestamp,lag_ms\n")
        while time.time() - started < duration:
            try:
                kind, payload = _read_message(sock)
            except (ConnectionError, socket.timeout):
                break
            if kind == "close":
                break
            if kind != "text":
                continue
            recv = datetime.now(timezone.utc)
            try:
                items = json.loads(payload.decode())
            except Exception:
                continue
            if isinstance(items, dict):
                items = [items]
            msgs += 1
            for it in items or []:
                ts = it.get("timestamp") or it.get("lastLocationTime")
                if not ts:
                    continue
                try:
                    lag_ms = (recv - _parse_ts(ts)).total_seconds() * 1000.0
                except Exception:
                    continue
                positions += 1
                lags.append(lag_ms)
                fh.write(f"{recv.isoformat()},{it.get('device_id') or it.get('assetId','?')},"
                         f"{(it.get('sources') or [it.get('source')])[0] if (it.get('sources') or it.get('source')) else '?'},"
                         f"{ts},{lag_ms:.1f}\n")
    elapsed = max(1e-9, time.time() - started)
    summary = {
        "duration_s": round(elapsed, 1),
        "messages": msgs,
        "positions": positions,
        "update_rate_msg_s": round(msgs / elapsed, 3),
        "update_rate_pos_s": round(positions / elapsed, 3),
        "lag_ms": {
            "median": round(_percentile(lags, 0.5), 1),
            "p90": round(_percentile(lags, 0.9), 1),
            "p99": round(_percentile(lags, 0.99), 1),
            "n": len(lags),
        },
    }
    out_json = os.path.splitext(out_csv)[0].replace("samples", "summary") + ".json"
    if out_json == out_csv:
        out_json = out_csv + ".summary.json"
    with open(out_json, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"per-sample → {out_csv}\nsummary → {out_json}")
    return 0 if positions else 1


if __name__ == "__main__":
    raise SystemExit(main())
