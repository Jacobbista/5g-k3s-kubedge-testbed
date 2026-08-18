#!/usr/bin/env python3
"""Run ONE probe plan headlessly and wait for it to finish.

The probe's plan executor is driven only over Socket.IO (`start_plan` event),
so this is the minimal glue: connect, emit `start_plan`, block until the
`plan_complete` event, exit 0 on success and non-zero otherwise. Repetitions,
provenance and result collection are the runner's job (run-campaign.sh), not
this file's.

Run it with the PROBE's virtualenv python, which already ships the Socket.IO
client (a dependency of Flask-SocketIO):

    5g-probe/venv/bin/python experiments/network/lib/start_plan.py \
        --plan <slug> --namespace <ue-netns> --target <upf-ip>

Owner: docs/tools/5g-probe.md (the probe), experiments/README.md.
"""
from __future__ import annotations

import argparse
import sys
import threading

try:
    import socketio  # python-socketio, bundled with the probe venv
except ImportError:  # pragma: no cover
    sys.exit("python-socketio not found — run this with 5g-probe/venv/bin/python")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="plan slug as returned by POST /api/plans")
    ap.add_argument("--namespace", required=True, help="UE network namespace to run in")
    ap.add_argument("--target", required=True, help="target IP (UPF anchor)")
    ap.add_argument("--url", default="http://127.0.0.1:5000")
    ap.add_argument("--timeout", type=float, default=1800.0, help="hard cap in seconds")
    args = ap.parse_args()

    done = threading.Event()
    result = {"status": "timeout", "message": "no plan_complete within timeout"}
    sio = socketio.Client(reconnection=False)

    @sio.on("plan_complete")
    def _on_complete(data):  # noqa: ANN001
        result.update(data or {})
        done.set()

    try:
        sio.connect(args.url, wait_timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(f"connect failed: {exc}", file=sys.stderr)
        return 2

    sio.emit("start_plan", {
        "plan_name": args.plan,
        "namespace": args.namespace,
        "target_ip": args.target,
    })

    finished = done.wait(timeout=args.timeout)
    try:
        sio.disconnect()
    except Exception:  # noqa: BLE001
        pass

    status = str(result.get("status", "")).lower()
    print(f"plan_complete: status={status} message={result.get('message', '')}", file=sys.stderr)
    if not finished:
        return 3
    return 0 if status in ("success", "completed", "ok", "done") else 1


if __name__ == "__main__":
    raise SystemExit(main())
