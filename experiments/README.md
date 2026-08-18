# experiments/ - reproducible measurement campaigns

The thesis measurements as declarative, re-runnable sequences on top of the
platform's own tools: the 5G probe, Prometheus, and the deployed CAMARA gateway.
Each campaign orders those tools, runs the repetitions, and captures provenance;
the raw samples land under `runs/`.

Everything runs against the **live cluster** on the real 5G core - no compose, no
mock repo. The northbound stack is a provisioning phase here (phase 10); the only
"mock" is the G6 mock-vendor *condition*, still in-cluster.

**Scope: fidelity, not accuracy.** The question is whether a source value
survives the pipeline, never how good the positioning technology is. No
UWB-vs-WiFi, no ground truth, no NEF/LMF.

## Layout

```
provenance.sh          date, commit, image versions, flags from the live deployment
lib/common.sh          shared plumbing; addresses/ports/versions derived, not hardcoded
network/               G2 throughput + latency, on the UE host through the modem
  plans/*.json         campaigns in the probe's native plan format
  run-campaign.sh      install plan -> provenance -> reps -> collect raw bundles
  lib/start_plan.py    Socket.IO glue to run one plan headlessly
footprint/             C8 resource footprint, Prometheus queries against the cluster
exposure/              G3/G5/G6, HTTP against the deployed gateway (see its README)
runs/<campaign>/<utc>/ plan.json + provenance.json + raw bundles, one dir per run
```

## Two hosts

- **UE / probe host** owns the modem netns and runs `network/`. Needs the probe
  server up (`../5g-probe/run-probe.sh`) and `KELT_UE_NS` set.
- **Cluster reach** (kubectl + Prometheus + gateway) runs `footprint/` and
  `exposure/`. From the host these go through the master VM (`sudo k3s kubectl`);
  set `KELT_KUBECTL` to run on-node.

## Order

1. `footprint/C8_footprint.sh idle` and G5 source failure - cheap, need nothing new.
2. G3 conformance and G5 fidelity - recorded exchanges only.
3. `network/run-campaign.sh` for C1 throughput, then C2 / C3 latency.
4. G6 - the per-hop log line and correlator propagation ship in northbound
   v0.9.0; drive the load and aggregate with `exposure/g6_aggregate.py`.
5. G5 attach-a-source (needs a second source), G1 rebuild (when the machine is free).

Under time pressure, cut the second throughput endpoint and the bidirectional
latency case; keep G5 fidelity and the G6 mock condition.

## Running a campaign

```bash
# network (UE host, probe server running)
KELT_UE_NS=ue1 experiments/network/run-campaign.sh C1_throughput       # reps=5
KELT_UE_NS=ue1 experiments/network/run-campaign.sh C2_latency_idle     # reps=3
KELT_UE_NS=ue1 KELT_C3_LOAD=both experiments/network/run-campaign.sh C3_latency_load

# footprint (per condition, after it has been active >= 5 min)
experiments/footprint/C8_footprint.sh idle

# exposure (see experiments/exposure/README.md)
```

Each run writes a self-contained directory under `runs/`: the plan, the raw
samples, `provenance.json` (date, commit, image versions, deployment flags), and
the condition. A fresh timestamped directory every time, so a re-run never
overwrites. Sample sizes, durations, and offered rates live in the `plans/*.json`
(`_note` and the per-experiment fields). Secrets pass by environment and stay out
of `runs/`.
