"""
Test helper utilities for 5G testbed testing
"""
import os
from pathlib import Path
from typing import Dict, Any, List
import yaml

from .k8s_client import K8sClient


class TestConfig:
    """Test configuration manager with kubeconfig override logic."""

    def __init__(self, config_path: str = "test_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load test configuration from YAML file (graceful fallback if missing/empty)."""
        config_file = Path(__file__).resolve().parent.parent / self.config_path
        if not config_file.exists():
            return {
                "cluster": {
                    "kubeconfig_path": "/home/vagrant/kubeconfig",
                    "master_ip": "",
                    "worker_ip": "",
                    "edge_ip": "",
                },
                "suites": {
                    "e2e": {"enabled": True},
                    "protocols": {"enabled": True},
                    "performance": {"enabled": True},
                    "resilience": {"enabled": True},
                },
            }
        with open(config_file, "r") as f:
            return yaml.safe_load(f) or {}

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Special handling for 'cluster.kubeconfig_path':
        1) If $KUBECONFIG is set and exists, use it
        2) Else if ./tests/kubeconfig exists, use it
        3) Else fall back to YAML value or default
        """
        if key_path == "cluster.kubeconfig_path":
            env_kcfg = os.environ.get("KUBECONFIG")
            if env_kcfg and Path(env_kcfg).exists():
                return env_kcfg
            local_kcfg = Path(__file__).resolve().parent.parent / "tests" / "kubeconfig"
            if local_kcfg.exists():
                return str(local_kcfg)

        keys = key_path.split(".")
        value: Any = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class TestLogger:
    """Test logging utilities"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def info(self, message: str):
        if self.verbose:
            print(f"ℹ️  {message}")

    def success(self, message: str):
        print(f"✅ {message}")

    def warning(self, message: str):
        print(f"⚠️  {message}")

    def error(self, message: str):
        print(f"❌ {message}")

    def test_start(self, test_name: str):
        print(f"\n🧪 Testing: {test_name}")

    def test_end(self, test_name: str, success: bool):
        if success:
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")


class NetworkValidator:
    """Network validation utilities"""

    def __init__(self, kubectl: K8sClient, config: TestConfig):
        self.kubectl = kubectl
        self.config = config

    def check_interface_ip(
        self, pod_name: str, namespace: str, interface: str, expected_ip: str, capture: bool = False
    ):
        """Return True/False; if capture=True return (ok, output)."""
        try:
            out = self.kubectl.exec_in_pod(
                pod_name, namespace, ["ip", "addr", "show", interface]
            )
            ok = expected_ip in out
            return (ok, out) if capture else ok
        except Exception as e:
            return (False, f"ERROR: {e}") if capture else False

    def check_port_listening(
        self, pod_name: str, namespace: str, port: int, protocol: str = "tcp", capture: bool = False
    ):
        """Return True/False; if capture=True return (ok, output)."""
        try:
            if protocol.upper() == "SCTP":
                out = self.kubectl.exec_in_pod(pod_name, namespace, ["ss", "-S", "-na"])
            elif protocol.upper() == "UDP":
                out = self.kubectl.exec_in_pod(pod_name, namespace, ["ss", "-unap"])
            else:
                out = self.kubectl.exec_in_pod(pod_name, namespace, ["ss", "-tnap"])
            ok = str(port) in out
            return (ok, out) if capture else ok
        except Exception as e:
            return (False, f"ERROR: {e}") if capture else False

    def check_connectivity(
        self, pod1_name: str, pod2_name: str, namespace: str, target_ip: str, capture: bool = False
    ):
        """ping - returns True/False; if capture=True return (ok, output)."""
        try:
            out = self.kubectl.exec_in_pod(
                pod1_name, namespace, ["ping", "-c", "3", "-W", "5", target_ip]
            )
            ok = (" 0% packet loss" in out) or ("bytes from" in out) or ("ttl=" in out)
            return (ok, out) if capture else ok
        except Exception as e:
            return (False, f"ERROR: {e}") if capture else False


class ComponentValidator:
    """5G component validation utilities"""

    def __init__(self, kubectl: K8sClient, config: TestConfig):
        self.kubectl = kubectl
        self.config = config

    def get_component_pods(self, component_name: str, namespace: str = "5g") -> List[Dict[str, Any]]:
        """Get pods for a specific component."""
        pods = self.kubectl.get_pods(namespace)
        return [pod for pod in pods if component_name in pod["metadata"]["name"].lower()]

    def is_component_ready(self, component_name: str, namespace: str = "5g") -> bool:
        """Check if all pods for a component are running."""
        pods = self.get_component_pods(component_name, namespace)
        if not pods:
            return False
        return all(pod["status"]["phase"] == "Running" for pod in pods)

    def get_component_interfaces(self, component_name: str, namespace: str = "5g") -> List[str]:
        """List non-loopback interfaces from the first pod of the component."""
        pods = self.get_component_pods(component_name, namespace)
        if not pods:
            return []
        try:
            out = self.kubectl.exec_in_pod(
                pods[0]["metadata"]["name"],
                namespace,
                ["ip", "link", "show"],
            )
            interfaces: List[str] = []
            for line in out.split("\n"):
                if ":" in line and not line.startswith(" "):
                    iface = line.split(":", 2)[1].strip()
                    if iface and not iface.startswith("lo"):
                        interfaces.append(iface)
            return interfaces
        except Exception:
            return []
            
    def debug_pod(self, pod_name: str, namespace: str, logger) -> None:
        """
        Compact diagnostics:
        - one-line status (phase, restarts, conditions)
        - last 12 log lines (first app container)
        - last 6 events (reason/message trimmed)
        """
        try:
            pods = self.kubectl.get_pods(namespace)
            p = next((x for x in pods if x["metadata"]["name"] == pod_name), None)
            if not p:
                logger.info(f"[debug] Pod {pod_name} not found in {namespace}")
                return

            phase = p["status"].get("phase")
            restarts = sum((cs.get("restart_count", 0) or 0) for cs in p["status"].get("container_statuses") or [])
            conds = p["status"].get("conditions", [])
            cond_str = ", ".join([f'{c.get("type")}={c.get("status")}' for c in conds]) if conds else "n/a"
            logger.info(f"[debug] {pod_name}: phase={phase}, restarts={restarts}, conditions=[{cond_str}]")

            # logs (first app container)
            try:
                spec = p.get("spec", {})
                containers = (spec.get("containers") or [])
                c_name = containers[0]["name"] if containers else None
                if c_name:
                    logs = self.kubectl.get_pod_logs(pod_name, namespace, container=c_name, tail_lines=200)
                    lines = logs.strip().splitlines()
                    tail = "\n".join(lines[-12:])
                    logger.info(f"[debug] logs (last 12 lines, {c_name}):\n{tail}")
            except Exception as e:
                logger.info(f"[debug] logs error: {e}")

            # last events
            try:
                events = self.kubectl.get_pod_events(pod_name, namespace)
                # sort by lastTimestamp/firstTimestamp best effort
                def _ts(ev):
                    meta = ev.get("last_timestamp") or ev.get("event_time") or ev.get("first_timestamp") or ""
                    return meta
                events = sorted(events, key=_ts)[-6:]
                short = []
                for ev in events:
                    reason = ev.get("reason", "")
                    msg = (ev.get("message", "") or "").strip().replace("\n", " ")
                    if len(msg) > 180:
                        msg = msg[:180] + "…"
                    short.append(f"- {reason}: {msg}")
                if short:
                    logger.info("[debug] last events:\n" + "\n".join(short))
            except Exception as e:
                logger.info(f"[debug] events error: {e}")
        except Exception as e:
            logger.info(f"[debug] debug_pod error: {e}")

