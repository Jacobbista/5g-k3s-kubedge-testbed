# Exposure campaigns (G3 / G5 / G6)

These measure the CAMARA exposure pipeline **against the live cluster
deployment** (gateway → engine → adapters running as pods, phase 10), on top of
the real 5G core. The "mock" in G6 is the mock-vendor *condition* - an adapter
with the external vendor call removed - and it still runs inside the cluster.

The gateway base URL is derived at run time (`gateway_url` in `../lib/common.sh`),
never hardcoded.

**Contract authority.** The request/response contract is owned upstream as a
machine-readable profile in `5g-northbound`
(`spec/private-profile/`: OpenAPI Overlays over the pinned CAMARA r3.2 base +
an AsyncAPI 3.0 doc for `/positions/stream`; `make profile-spec` emits the
profiled spec, CI asserts the overlays apply). KELT tests **verify the live
deployment against that spec**. Confirm request bodies
and paths against the deployment's own OpenAPI (`"$(gateway_url)"/docs`), which
is generated from the same profile. Direction: drive `G3_conformance.sh` from
the profiled OpenAPI (schema-validate responses) rather than hand-coded codes.

Since the profile-conformance push (northbound `4559708`), the old divergences
are **implemented as conformant**, so G3/G5 shift from *recording mismatches* to
*verifying conformance* (see the table below). The conformant gateway (v0.9.0) is
deployed and the live checks pass (e.g. a public identifier returns 422
`UNSUPPORTED_IDENTIFIER`, and every response carries `x-correlator`).

| Campaign | Needs code? | Status here |
|---|---|---|
| G3 conformance (`G3_conformance.sh`) | client only | runnable; verifies conformance against the profiled OpenAPI |
| G5 fidelity | recorded exchanges only | manual/recorded (see below) |
| G5 source failure (`G5_failure.sh`) | no new instrumentation | runnable; uses `kubectl` to stop a vendor / drop an adapter |
| G6 latency (`G6_latency.sh`) | driver + **aggregation** ours; per-hop logs theirs | driver records end-to-end + the `x-correlator` join key. northbound's per-hop logs ship in v0.9.0; the stage split is the **aggregation of those logs by `x-correlator`** via `g6_aggregate.py` (role split, below). |
| C10 streaming (`G6_streaming.sh`) | WS client, ≥10 min | runnable skeleton: `stream_lag.py` measures freshness (fix->client) and update rate; see below |

## G5 fidelity (recorded, not a script)

Compare the recorded vendor response against the API response for the *same*
estimate (coordinates after room-local conversion, uncertainty carried not
floored-away, timestamp = moment of the estimate, source/kind match the
registry, altitude/vertical accuracy carried when present). This is a
recorded-exchange comparison, done once by hand. Remaining known loss to record:
the interface floors radius at 1 m, so a sub-metre source fix is reported at 1 m.
(`maxAge` is now honoured with a per-asset cache, no longer a divergence; verify
it holds.)

## G6 role split (agreed with northbound)

- **northbound**: per-hop structured logs (each service logs receive/emit ts +
  the `x-correlator`) and correlator propagation across gateway → engine →
  adapter, delivered in v0.9.0. The line contract is machine-readable:
  https://jacobbista.github.io/5g-northbound/schema/hop-log.schema.json
  (index: https://jacobbista.github.io/5g-northbound/contracts/).
- **KELT**: the load driver (here) and the **aggregation**. `g6_aggregate.py`
  joins the per-hop logs by `x-correlator` into a per-stage breakdown. It
  validates every line against the pinned schema (`hop-log.schema.json`, vendored
  next to it from Pages) and derives the hierarchy from timestamp containment, so
  the topology is not hardcoded. The driver captures `x-correlator` per request
  as the join key and snapshots the pod logs each run; feed those to
  `g6_aggregate.py <run-dir>`.

The first requests pay one-time costs (httpx connection-pool init, first DNS
resolution, first JWKS fetch) that are not steady-state, so report the **warm**
path: run the campaign at volume (default 1000 at ~5/s), discard the earliest
requests with `g6_aggregate.py <run-dir> --warmup N`, and read the median / p90 /
p99 it prints, never a single early sample.

No mock-vendor is deployed in the cluster. The **WAN-free number** is the full
trace **minus the adapter→vendor span** (subtraction, no extra pod); the call to
the real Wittra cloud is a genuine WAN round-trip, still measured but kept
separate. A deterministic WAN-free repro lives in the **local `make demo`** only:
the vendor-adapter repointed at the schema-driven mock-vendor via
`WITTRA_BASE_URL`. It is not a testbed component.

Cache is `maxAge`-aware: `maxAge=0` bypasses the cache and measures the real
pipeline (the `fresh` condition); a cache hit is ~0 and reported as a separate
trivial number. Measure the fresh path for pipeline latency.

## C10 streaming (freshness, not push latency)

`G6_streaming.sh [duration_s]` opens the CAMARA stream
(`WS /positions/stream?token=<jwt>` on the gateway, over its NodePort) and runs
`stream_lag.py` to record, per pushed position,

    lag = client-receive-time  -  payload `timestamp`

plus the update rate, over a long run (default 600 s). The `timestamp` is the
source fix time passed through by the gateway verbatim, so the lag is **freshness
fix->client** (fix age + fusion + cadence + network), a different measure from the
retrieve hop-log — hence its own tool, not the aggregator. The flow comes from the
**synthetic-adapter** walker (`demo-001`); wittra rides the same stream but is not
the C10 source, so filter by the `source` column the client writes.

Run on the cluster host so the receive clock is close to the fix clock. The
`timestamp` is stamped inside the adapter's node VM; the VMs discipline that clock
with chrony (observed RMS offset < 0.1 ms against NTP), so the host<->VM
contribution to the lag is sub-millisecond. Each run snapshots `chronyc tracking`
into `clock_sync.txt` as evidence of that bound.
