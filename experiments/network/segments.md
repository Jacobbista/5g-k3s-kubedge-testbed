# Latency segments — decomposing the RTT budget

The headline campaigns (C1–C3) measure ONE segment end-to-end: UE → UPF anchor
`10.45.0.1`. This file schematises the path into isolable segments so the RTT
budget can be attributed — the transport equivalent of the dashboard's sniffer
capture points, and the way to show the impact of **virtualisation and
orchestration** on the intra-cluster legs.

Two families, two vantage points.

## A. 5G transport (from the UE netns, via the probe)

Reuse `run-campaign.sh C2_latency_idle` with a target override
(`KELT_TARGET=<ip>`); the probe accepts any reachable IP. Differences between
targets isolate a segment.

| Segment | Target (from UE netns) | Isolates | Note |
|---|---|---|---|
| **Uu** (radio) | gNB RAN IP `192.168.6.101` | UE↔gNB air interface | dominant + variance; owner: docs/deployment/physical-ran.md |
| **Uu + N3 + UPF** | UPF anchor `10.45.0.1` | full radio+backhaul+UPF (headline) | this is C2 as-is |
| **N3 + UPF** | — | backhaul + UPF processing | derived: (→UPF) − (→gNB) |
| **N6** (post-UPF) | a host behind the UPF on the DN | decapsulated N6 leg | needs the MEC iperf/ping server (2nd series); else skip |

## B. Virtualisation & orchestration (from netshoot pods, via `latency-segments.sh`)

These quantify the overhead the container platform adds on top of the raw host
network. Each row is measured from an ephemeral netshoot pod so it is
reproducible and self-cleaning.

| Segment | How | Isolates |
|---|---|---|
| **host baseline** | node → node (InternalIP) | the underlying network floor |
| **pod → pod, same node** | netshoot(worker) → podIP(worker) | container CNI only |
| **pod → pod, cross node** | netshoot(master) → podIP(worker) | CNI **+ VXLAN overlay** (overlay cost = this − host baseline) |
| **pod → ClusterIP** | netshoot → service ClusterIP (TCP connect) | kube-proxy / iptables (svc cost = this − podIP) |
| **pod → NodePort / front-door** | netshoot → nodeIP:nodePort (TCP connect) | ingress hop (nodeport cost = this − ClusterIP) |
| **pipeline legs** | netshoot → gateway/engine/adapter podIPs | the network legs the CAMARA request crosses |
| **n6m Multus leg** *(opt)* | netshoot → an n6m IP (10.208.0.x) | the secondary Multus data-network path |

Note on scale: intra-cluster legs are typically sub-millisecond. They matter for
the *virtualisation-overhead* story (how much K8s/overlay/kube-proxy adds), not
as a large share of a CAMARA request — the application stage split (northbound
log line) and the external vendor round trip dominate that. Report both, and say
which is which.

Owner: experiments/README.md. The application-stage split of a CAMARA request
(gateway/engine/adapter processing) is NOT here — it is in-process time only the
services can emit; see experiments/exposure/README.md.
