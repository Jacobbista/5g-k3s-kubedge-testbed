#!/usr/bin/env python3
"""Aggregate northbound per-hop log lines into a per-stage latency breakdown.

This is the KELT side of the agreed G6 split: northbound emits one structured
hop line per service per request; KELT joins them by `x-correlator` and turns
each trace into a stage breakdown. The line contract is the machine-readable
schema, authoritative and validated against here (not a prose transcription):

  https://jacobbista.github.io/5g-northbound/schema/hop-log.schema.json
  (Pages = latest; raw+tag pins a release. Contract index:
   https://jacobbista.github.io/5g-northbound/contracts/)

A pinned copy sits next to this file as hop-log.schema.json; every parsed line is
validated against it, and non-conforming lines are dropped and counted. The
schema states span_ms "includes time waited on downstream hops", which is why the
per-stage cost is caller.span - sum(children spans).

Aggregation rules (from the contract):
  - end-to-end        = the root hop's span (the gateway, which contains the rest)
  - per-stage cost    = caller.span - sum(immediate children spans)
  - WAN-free baseline = end-to-end - the adapter->vendor span

Parent/child is inferred from timestamp containment (a child's [t_receive,t_emit]
sits inside its caller's), so the topology is not hardcoded.

  g6_aggregate.py <run-dir-or-hoplog-files...> [--vendor-service vendor]

Reads the `hoplog_*.txt` snapshots a G6_latency.sh run leaves behind (or explicit
files), writes stages.csv + a printed summary. Owner: experiments/exposure/README.md.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from statistics import median


def _validator():
    """A jsonschema validator for the vendored hop-log schema, or None if the
    schema/lib is absent (then lines are accepted on the required-field check)."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hop-log.schema.json")
    try:
        import jsonschema  # type: ignore
        with open(schema_path) as fh:
            return jsonschema.Draft7Validator(json.load(fh))
    except (ImportError, OSError, ValueError):
        return None


def _load_hops(paths: list[str]) -> tuple[list[dict], int]:
    files: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, "hoplog_*.txt"))
        else:
            files.append(p)
    validator = _validator()
    hops: list[dict] = []
    rejected = 0
    for f in files:
        try:
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if '"event"' not in line or "hop" not in line:
                        continue
                    # A pod log line may prefix the JSON; take from the first brace.
                    i = line.find("{")
                    if i < 0:
                        continue
                    try:
                        d = json.loads(line[i:])
                    except json.JSONDecodeError:
                        continue
                    if d.get("event") != "hop":
                        continue
                    if validator is not None:
                        if any(validator.iter_errors(d)):
                            rejected += 1
                            continue
                    elif not all(k in d for k in ("service", "correlator", "t_receive", "t_emit", "span_ms")):
                        rejected += 1
                        continue
                    hops.append(d)
        except OSError:
            continue
    return hops, rejected


def _percentile(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = min(len(s) - 1, int(round(q * (len(s) - 1))))
    return s[k]


def _self_costs(trace: list[dict]) -> tuple[dict, dict, float]:
    """Return (self_ms_by_service, span_ms_by_service, e2e_ms) for one trace."""
    # parent = the smallest-span hop that strictly contains this one.
    def contains(a: dict, b: dict) -> bool:
        return (a is not b and a["t_receive"] <= b["t_receive"]
                and b["t_emit"] <= a["t_emit"] and a["span_ms"] >= b["span_ms"])

    children: dict[int, list[dict]] = {id(h): [] for h in trace}
    roots: list[dict] = []
    for h in trace:
        parents = [p for p in trace if contains(p, h)]
        if not parents:
            roots.append(h)
        else:
            parent = min(parents, key=lambda p: p["span_ms"])
            children[id(parent)].append(h)
    self_ms: dict[str, float] = {}
    span_ms: dict[str, float] = {}
    for h in trace:
        svc = h.get("service", "?")
        kids = sum(c["span_ms"] for c in children[id(h)])
        self_ms[svc] = self_ms.get(svc, 0.0) + max(0.0, h["span_ms"] - kids)
        span_ms[svc] = span_ms.get(svc, 0.0) + h["span_ms"]
    e2e = max((r["span_ms"] for r in roots), default=0.0)
    return self_ms, span_ms, e2e


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    vendor = "vendor"
    if "--vendor-service" in sys.argv:
        vendor = sys.argv[sys.argv.index("--vendor-service") + 1]
    if not args:
        return print(__doc__) or 2

    hops, rejected = _load_hops(args)
    if rejected:
        print(f"warning: {rejected} line(s) did not validate against hop-log.schema.json (dropped)", file=sys.stderr)
    if not hops:
        print("no hop lines found (is the per-hop instrumentation deployed?)", file=sys.stderr)
        return 1

    traces: dict[str, list[dict]] = {}
    for h in hops:
        traces.setdefault(h["correlator"], []).append(h)

    out_dir = args[0] if os.path.isdir(args[0]) else "."
    csv_path = os.path.join(out_dir, "stages.csv")
    services = sorted({h.get("service", "?") for h in hops})
    rows: list[dict] = []
    with open(csv_path, "w") as fh:
        fh.write("correlator,e2e_ms,wan_free_ms," + ",".join(f"{s}_self_ms" for s in services) + "\n")
        for corr, trace in traces.items():
            self_ms, span_ms, e2e = _self_costs(trace)
            wan = sum(v for s, v in span_ms.items() if vendor in s)
            row = {"correlator": corr, "e2e_ms": e2e, "wan_free_ms": max(0.0, e2e - wan)}
            for s in services:
                row[f"{s}_self_ms"] = self_ms.get(s, 0.0)
            rows.append(row)
            fh.write(f"{corr},{e2e:.3f},{row['wan_free_ms']:.3f}," +
                     ",".join(f"{self_ms.get(s, 0.0):.3f}" for s in services) + "\n")

    def stat(key: str) -> str:
        xs = [r[key] for r in rows]
        return f"median {median(xs):7.2f}  p90 {_percentile(xs,0.90):7.2f}  p99 {_percentile(xs,0.99):7.2f}"

    print(f"traces: {len(rows)}   (vendor span matched on service containing '{vendor}')")
    print(f"  end-to-end ms : {stat('e2e_ms')}")
    print(f"  WAN-free   ms : {stat('wan_free_ms')}")
    for s in services:
        print(f"  {s:<20} self ms : {stat(s + '_self_ms')}")
    print(f"\nper-trace → {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
