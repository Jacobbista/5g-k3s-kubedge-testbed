# shellcheck shell=bash
# Shared plumbing for the KELT measurement campaigns.
#
# Design rule (AGENTS.md "Hard constraints"): nothing here hardcodes an address,
# port, version, or image. Dynamic facts (node IP, NodePort, image tags, git
# commits) are read from the LIVE deployment at run time; the few names that
# identify owner-declared objects (namespaces) sit in one block below with a
# pointer to the document/file that owns them, and every one is overridable by an
# environment variable so a differently-named deployment still works.
#
# Owner docs: experiments/README.md (runbook + scope), docs/tools/5g-probe.md
# (the probe), ansible/group_vars/all.yml (the deployment values).

set -euo pipefail

EXP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$EXP_ROOT/.." && pwd)"
RUNS_DIR="${KELT_EXP_RUNS_DIR:-$EXP_ROOT/runs}"

# ── Owner-declared names (override via env; owners noted inline) ───────────────
CORE_NS="${KELT_CORE_NS:-5g}"                       # all.yml: namespace_5g
EXPOSURE_NS_RE="${KELT_EXPOSURE_NS_RE:-positioning|camara|mec}"  # phase 10 + demo (mec)
CAMARA_NS="${KELT_CAMARA_NS:-camara}"               # all.yml: camara_namespace
MONITORING_NS="${KELT_MONITORING_NS:-monitoring}"  # phase 07: monitoring_namespace

# UPF PDU anchor for the probe. Owner: 5g-probe/probe/config.py
# (FIVEG_PROBE_UPF_TARGET) and all.yml UPF ogstun gateway.
UPF_TARGET="${FIVEG_PROBE_UPF_TARGET:-10.45.0.1}"

# kubectl access. Inside a VM Kubernetes is K3s (AGENTS.md): use `sudo k3s
# kubectl`. From the host we reach it through the master VM. Override KELT_KUBECTL
# to run on-node or against another kubeconfig.
kubectl() {
  if [ -n "${KELT_KUBECTL:-}" ]; then
    # shellcheck disable=SC2086
    $KELT_KUBECTL "$@"
  else
    # `vagrant ssh -c` takes ONE command string, so each argument is shell-escaped
    # with %q and rebuilt: a bare "$*" would flatten quoting and break any jsonpath
    # carrying quotes/spaces (e.g. node InternalIP, the image range). The login
    # shell also prints the testbed banner ("[Testbed] Profile: ...") on stdout
    # ahead of the output, so strip it or it contaminates every parsed value.
    local remote="sudo k3s kubectl" a
    for a in "$@"; do remote+=" $(printf '%q' "$a")"; done
    vagrant ssh master -c "$remote" 2>/dev/null | sed '/^\[Testbed\]/d'
  fi
}

# First reachable node IP (NodePort services answer on any node).
node_ip() {
  kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' \
    | tr -d '\r' | awk '{print $1}'
}

# NodePort of a service: svc_nodeport <namespace> <service> [port-index]
svc_nodeport() {
  local ns="$1" svc="$2" idx="${3:-0}"
  kubectl get svc -n "$ns" "$svc" -o jsonpath="{.spec.ports[$idx].nodePort}" | tr -d '\r'
}

# Base URL of the deployed CAMARA gateway (derived, never hardcoded).
# Override with KELT_GATEWAY_URL when a front-door hostname is preferred.
gateway_url() {
  if [ -n "${KELT_GATEWAY_URL:-}" ]; then echo "$KELT_GATEWAY_URL"; return; fi
  local svc="${KELT_CAMARA_SVC:-camara-gateway}"
  echo "http://$(node_ip):$(svc_nodeport "$CAMARA_NS" "$svc")"
}

# A fresh, timestamped run directory for a campaign: new_run_dir C1_throughput
# Uses a caller-supplied UTC stamp so the layout stays reproducible/testable.
new_run_dir() {
  local campaign="$1" stamp="${2:-$(date -u +%Y%m%dT%H%M%SZ)}"
  local d="$RUNS_DIR/$campaign/$stamp"
  mkdir -p "$d"
  echo "$d"
}

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
