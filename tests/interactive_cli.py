#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arrow-key interactive CLI (simple-term-menu + Rich)
Conventional-commit style menus; minimal, reliable, pretty output.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from simple_term_menu import TerminalMenu
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
sys.path.append(str(ROOT))

# Optional project imports with safe fallbacks
try:
    from utils.test_helpers import TestConfig, TestLogger  # type: ignore
except Exception:
    class TestConfig:
        def __init__(self):
            self.config = {
                "cluster": {"kubeconfig_path": str(ROOT / "kubeconfig"),
                            "master_ip": "", "worker_ip": "", "edge_ip": ""},
                "suites": {"e2e": {"enabled": True},
                           "protocols": {"enabled": True},
                           "performance": {"enabled": True},
                           "resilience": {"enabled": True}},
            }
        def get(self, key: str, default: str = "") -> str:
            # dotted lookup
            cur = self.config
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return default
            return cur
    class TestLogger:
        def __init__(self, *_): pass
        def info(self, *_, **__): pass
        def error(self, *_, **__): pass

try:
    from run_tests import check_vagrant_vms  # type: ignore
except Exception:
    def check_vagrant_vms() -> bool:
        if not shutil.which("vagrant"):
            return False
        try:
            r = subprocess.run(
                ["vagrant", "status"],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=20
            )
            out = (r.stdout or "").lower()
            return (r.returncode == 0 and
                    ("master" in out and "running" in out) and
                    ("worker" in out and "running" in out) and
                    ("edge"   in out and "running" in out))
        except Exception:
            return False

# constants
console = Console()
cfg = TestConfig()
logger = TestLogger(True)

MAIN_MENU = [
    "🧪 Run Tests",
    "📋 View Status",
    "⚙️  Configuration",
    "❓ Help",
    "🚪 Exit",
]

TEST_TYPES = [
    "🎯 All Tests",
    "🔗 End-to-End",
    "📡 5G Protocol",
    "⚡ Performance",
    "🛡️  Resilience",
    "⬅️ Back",
]

PHASES = ["infrastructure", "5g-core", "ueransim", "e2e", "performance", "resilience"]

LOCAL_KUBECONFIG = ROOT / "kubeconfig"
REMOTE_KUBECONFIG = "/home/vagrant/kubeconfig"   # matches your runner


# -------- small helpers --------
def select_one(title: str, options: List[str]) -> Optional[int]:
    menu = TerminalMenu(
        options,
        title=f"\n{title}\n",
        menu_cursor="> ",
        cycle_cursor=True,
        clear_screen=False,
    )
    return menu.show()

def select_multi(title: str, options: List[str]) -> List[int]:
    menu = TerminalMenu(
        options,
        title=f"\n{title}\n",
        multi_select=True,
        show_multi_select_hint=True,
        multi_select_cursor="[x] ",
        multi_select_select_on_accept=False,
        menu_cursor="> ",
        cycle_cursor=True,
        clear_screen=False,
    )
    return menu.show() or []

def run_subprocess_stream(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> int:
    pretty = " ".join(cmd)
    console.rule(f"[bold green]Running[/bold green] [dim]{pretty}[/dim]")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd or ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env or os.environ.copy(),
        )
        assert proc.stdout
        for line in proc.stdout:
            console.print(line.rstrip())
        proc.wait()
        console.rule(f"[bold]Exit code:[/bold] {proc.returncode}")
        return int(proc.returncode or 0)
    except FileNotFoundError as e:
        console.print(f"[red]Command not found:[/red] {e}")
        return 127
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

def run_quick(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def vagrant_remote_file_exists(vm: str, path: str) -> bool:
    if not shutil.which("vagrant"):
        return False
    try:
        # test -f returns 0 if the file exists
        r = run_quick(["vagrant", "ssh", vm, "-c", f"test -f {path} && echo OK || true"], cwd=REPO_ROOT, timeout=15)
        return "OK" in (r.stdout or "")
    except Exception:
        return False

def copy_kubeconfig_from_master() -> bool:
    """Copies remote kubeconfig to local ./tests/kubeconfig like your runner does."""
    try:
        r = run_quick(["vagrant", "ssh", "master", "-c", f"cat {REMOTE_KUBECONFIG}"], cwd=REPO_ROOT, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            LOCAL_KUBECONFIG.write_text(r.stdout)
            return True
    except Exception:
        pass
    return False


# -------- actions --------
def show_status():
    with console.status("[bold]Checking testbed status...[/bold]", spinner="dots"):
        vagrant_ok = check_vagrant_vms()
        venv_ok = (ROOT / "venv").exists()
        local_kcfg_ok = LOCAL_KUBECONFIG.exists()
        remote_kcfg_ok = False
        if not local_kcfg_ok and vagrant_ok:
            # quick peek on remote
            remote_kcfg_ok = vagrant_remote_file_exists("master", REMOTE_KUBECONFIG)

    table = Table(title="📊 Testbed Status", show_lines=True, box=box.SIMPLE)
    table.add_column("Component", style="cyan")
    table.add_column("Status / Details", style="magenta")

    table.add_row("Vagrant VMs", "✅ Running" if vagrant_ok else "❌ Not running")
    table.add_row("Virtualenv", "✅ Present" if venv_ok else "❌ Missing")

    if local_kcfg_ok:
        table.add_row("Kubeconfig (local)", f"✅ Found  [dim]({LOCAL_KUBECONFIG})[/dim]")
    elif remote_kcfg_ok:
        table.add_row("Kubeconfig (remote)", f"ℹ️ Present on master  [dim]({REMOTE_KUBECONFIG})[/dim]")
    else:
        # fall back to whatever TestConfig says (if pointing to remote path, show as not-found locally)
        declared = cfg.get("cluster.kubeconfig_path", str(LOCAL_KUBECONFIG))
        table.add_row("Kubeconfig", f"❌ Not found  [dim]({declared})[/dim]")

    console.print(table)

    # Offer copy if remote exists but local is missing
    if not local_kcfg_ok and remote_kcfg_ok:
        if Confirm.ask("Copy kubeconfig from master to local now?"):
            with console.status("[bold]Copying kubeconfig...[/bold]", spinner="dots"):
                ok = copy_kubeconfig_from_master()
            console.print("[green]✅ Copied.[/green]" if ok else "[red]❌ Copy failed.[/red]")


def show_config():
    # Read values; hide blank ones
    def add_row_safe(tbl, key_label, value):
        val = (value or "").strip()
        if val != "":
            tbl.add_row(key_label, val)

    suites = [
        ("e2e",        cfg.get("suites.e2e.enabled", True)),
        ("protocols",  cfg.get("suites.protocols.enabled", True)),
        ("performance",cfg.get("suites.performance.enabled", True)),
        ("resilience", cfg.get("suites.resilience.enabled", True)),
    ]

    t1 = Table(title="⚙️  Configuration", show_lines=True, box=box.SIMPLE)
    t1.add_column("Setting", style="cyan", no_wrap=True)
    t1.add_column("Value", style="magenta")
    add_row_safe(t1, "Local kubeconfig", str(LOCAL_KUBECONFIG))
    add_row_safe(t1, "Remote kubeconfig", REMOTE_KUBECONFIG)
    add_row_safe(t1, "Repo root", str(REPO_ROOT))
    add_row_safe(t1, "Python", sys.executable)
    add_row_safe(t1, "Kubeconfig (declared)", str(cfg.get("cluster.kubeconfig_path", "")))
    add_row_safe(t1, "Master IP", str(cfg.get("cluster.master_ip", "")))
    add_row_safe(t1, "Worker IP", str(cfg.get("cluster.worker_ip", "")))
    add_row_safe(t1, "Edge IP", str(cfg.get("cluster.edge_ip", "")))

    t2 = Table(title="Test Suites (enabled)", show_lines=False, box=box.SIMPLE)
    t2.add_column("Suite", style="cyan")
    t2.add_column("Enabled", style="magenta")
    for name, enabled in suites:
        t2.add_row(name, "✅ yes" if bool(enabled) else "🚫 no")

    console.print(t1)
    console.print(t2)


def run_tests_flow():
    idx = select_one("Select test type:", TEST_TYPES)
    if idx is None or TEST_TYPES[idx] == "⬅️ Back":
        return

    label = TEST_TYPES[idx]
    args = ["-v"]

    if label.startswith("🔗"):
        args += ["-s", "e2e"]
    elif label.startswith("📡"):
        args += ["-s", "protocols"]
    elif label.startswith("⚡"):
        args += ["-s", "performance"]
    elif label.startswith("🛡️"):
        args += ["-s", "resilience"]
    else:
        chosen = select_multi("Optionally select phases (Space to toggle, Enter to accept):", PHASES)
        if chosen:
            args += ["-p", *[PHASES[i] for i in chosen]]

    cmd = [sys.executable, "run_tests.py", *args]

    # >>> Ensure tests use the local kubeconfig via environment
    test_env = os.environ.copy()
    if LOCAL_KUBECONFIG.exists():
        test_env["KUBECONFIG"] = str(LOCAL_KUBECONFIG)

    with console.status("[bold]Running tests...[/bold]", spinner="dots"):
        code = run_subprocess_stream(cmd, cwd=ROOT, env=test_env)

    console.print(
        "[bold green]🎉 Tests completed successfully![/bold green]"
        if code == 0 else "[bold red]💥 Some tests failed.[/bold red]"
    )


def show_help():
    console.print(Panel.fit(
        """[bold]Controls[/bold]
• Arrow keys to move, Enter to confirm
• For multi-select: Space toggles, Enter accepts
• Esc or q cancels menu

[bold]Status behavior[/bold]
• Shows local kubeconfig if present (tests/kubeconfig).
• If missing but present on master VM, offers to copy it.
• Uses a spinner while checking/copying so the terminal isn't idle.

[bold]Configuration panel[/bold]
• Paths (local/remote kubeconfig, repo root, python)
• Cluster IPs if available from config
• Enabled test suites (e2e, protocols, performance, resilience)
""",
        title="❓ Help", border_style="blue"
    ))


# -------- main loop --------
def main():
    console.print(Panel.fit("🚀 5G K3s KubeEdge Testbed — Interactive CLI", style="bold green"))
    while True:
        idx = select_one("What would you like to do?", MAIN_MENU)
        if idx is None:
            console.print("[bold blue]Goodbye![/bold blue]")
            return
        choice = MAIN_MENU[idx]
        if choice.startswith("🧪"):
            run_tests_flow()
        elif choice.startswith("📋"):
            show_status()
        elif choice.startswith("⚙️"):
            show_config()
        elif choice.startswith("❓"):
            show_help()
        elif choice.startswith("🚪"):
            console.print("[bold blue]Goodbye![/bold blue]")
            return


if __name__ == "__main__":
    main()
