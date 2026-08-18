#!/usr/bin/env python3
"""Turn a Prometheus instant-query JSON (stdin) into CSV rows:
    <layer>,<namespace>,<pod>,<metric>,<value>

Usage: _promcsv.py <layer> <metric>   (reads query JSON on stdin)
Owner: experiments/footprint/C8_footprint.sh.
"""
import json
import sys


def main() -> int:
    layer, metric = sys.argv[1], sys.argv[2]
    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 1
    for r in doc.get("data", {}).get("result", []):
        m = r.get("metric", {})
        ns = m.get("namespace", "")
        pod = m.get("pod", "")
        val = (r.get("value") or [None, ""])[1]
        print(f"{layer},{ns},{pod},{metric},{val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
