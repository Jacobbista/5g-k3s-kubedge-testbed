"""
Main test runner for 5G K3s KubeEdge Testbed
"""
import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.test_helpers import TestConfig, TestLogger


def check_vagrant_vms():
    """Check if Vagrant VMs are running"""
    try:
        result = subprocess.run(["vagrant", "status"], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print("❌ Vagrant not available or not in project directory")
            return False
        
        status_output = result.stdout.lower()
        required_vms = ["master", "worker", "edge"]
        
        for vm in required_vms:
            if f"{vm}" not in status_output or "running" not in status_output:
                print(f"❌ VM '{vm}' is not running")
                return False
        
        print("✅ All required Vagrant VMs are running")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Vagrant status check timed out")
        return False
    except FileNotFoundError:
        print("❌ Vagrant command not found")
        return False
    except Exception as e:
        print(f"❌ Failed to check Vagrant VMs: {e}")
        return False


def ensure_venv():
    """Ensure virtual environment is set up and activated"""
    venv_path = Path(__file__).parent / "venv"
    
    if not venv_path.exists():
        print("🔧 Creating virtual environment...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
            print("✅ Virtual environment created successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            raise
    else:
        print("✅ Virtual environment already exists")
    
    # Activate venv and install dependencies
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux
        activate_script = venv_path / "bin" / "activate"
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # Install dependencies if needed
    requirements_file = Path(__file__).parent / "requirements.txt"
    if requirements_file.exists():
        # Check if dependencies are already installed
        print("🔍 Checking dependencies...")
        try:
            # Try to import the main dependencies to see if they're already installed
            check_result = subprocess.run([str(python_path), "-c", 
                                        "import yaml, requests; print('deps_ok')"], 
                                       capture_output=True, text=True, timeout=10)
            if check_result.returncode == 0 and "deps_ok" in check_result.stdout:
                print("✅ Dependencies already installed")
            else:
                print("📦 Installing dependencies...")
                result = subprocess.run([str(pip_path), "install", "-r", str(requirements_file)], 
                                      check=True, capture_output=True, text=True)
                print("✅ Dependencies installed successfully")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("📦 Installing dependencies...")
            result = subprocess.run([str(pip_path), "install", "-r", str(requirements_file)], 
                                  check=True, capture_output=True, text=True)
            print("✅ Dependencies installed successfully")
    else:
        print("⚠️  No requirements.txt found, skipping dependency installation")
    
    return str(python_path)


class TestRunner:
    """Main test runner"""
    
    def __init__(self, verbose: bool = False):
        self.config = TestConfig()
        self.logger = TestLogger(verbose)
        self.verbose = verbose
    
    def run_test_suite(self, suite_name: str) -> bool:
        """Run a specific test suite"""
        self.logger.info(f"Running {suite_name} test suite...")
        
        # Map suite names to their modules
        suite_modules = {
            "e2e": "core.test_e2e",
            "protocols": "protocols.test_5g_protocols",
            "performance": "performance.test_performance",
            "resilience": "resilience.test_resilience"
        }
        
        if suite_name not in suite_modules:
            self.logger.error(f"Unknown test suite: {suite_name}")
            return False
        
        # Check if suite is enabled
        if not self.config.get(f"suites.{suite_name}.enabled", True):
            self.logger.info(f"Test suite {suite_name} is disabled")
            return True
        
        # Run the test suite
        module_path = suite_modules[suite_name]
        script_path = Path(__file__).parent / (module_path.replace(".", "/") + ".py")
        
        if not script_path.exists():
            self.logger.error(f"Test script not found: {script_path}")
            return False
        
        try:
            # Run the test script
            cmd = [sys.executable, str(script_path)]
            if self.verbose:
                cmd.append("-v")
            
            result = subprocess.run(cmd, capture_output=False, text=True)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to run {suite_name} test suite: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all enabled test suites"""
        self.logger.info("Running all test suites...")
        
        suites = ["e2e", "protocols", "performance", "resilience"]
        results = {}
        
        for suite in suites:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Running {suite.upper()} tests")
            self.logger.info(f"{'='*50}")
            
            success = self.run_test_suite(suite)
            results[suite] = success
            
            if success:
                self.logger.success(f"{suite.upper()} tests passed")
            else:
                self.logger.error(f"{suite.upper()} tests failed")
        
        # Summary
        self.logger.info(f"\n{'='*50}")
        self.logger.info("TEST SUMMARY")
        self.logger.info(f"{'='*50}")
        
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        
        for suite, success in results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            self.logger.info(f"{suite.upper():12} {status}")
        
        self.logger.info(f"\nTotal: {passed}/{total} test suites passed")
        
        if passed == total:
            self.logger.success("🎉 All test suites passed!")
            return True
        else:
            self.logger.error("💥 Some test suites failed!")
            return False
    
    def run_phases(self, phases: list) -> bool:
        """Run specific test phases"""
        self.logger.info(f"Running test phases: {', '.join(phases)}")
        
        # Map phases to test suites
        phase_mapping = {
            "infrastructure": ["e2e"],
            "5g-core": ["e2e", "protocols"],
            "ueransim": ["e2e"],
            "e2e": ["e2e", "protocols", "performance"],
            "performance": ["performance"],
            "resilience": ["resilience"]
        }
        
        suites_to_run = set()
        for phase in phases:
            if phase in phase_mapping:
                suites_to_run.update(phase_mapping[phase])
            else:
                self.logger.warning(f"Unknown phase: {phase}")
        
        if not suites_to_run:
            self.logger.error("No valid phases specified")
            return False
        
        # Run the suites
        results = {}
        for suite in suites_to_run:
            success = self.run_test_suite(suite)
            results[suite] = success
        
        # Summary
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        
        self.logger.info(f"\nPhase results: {passed}/{total} test suites passed")
        return passed == total


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="5G K3s KubeEdge Testbed Test Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-s", "--suite", choices=["e2e", "protocols", "performance", "resilience"], 
                       help="Run specific test suite")
    parser.add_argument("-p", "--phases", nargs="+", 
                       choices=["infrastructure", "5g-core", "ueransim", "e2e", "performance", "resilience"],
                       help="Run specific test phases")
    parser.add_argument("--list", action="store_true", help="List available test suites and phases")
    parser.add_argument("--no-venv", action="store_true", help="Skip virtual environment setup")
    
    args = parser.parse_args()
    
    print("🚀 Starting 5G K3s KubeEdge Testbed Test Suite")
    print("=" * 50)
    
    # Check Vagrant VMs first
    if not check_vagrant_vms():
        print("\n💡 Please start the testbed with: vagrant up")
        sys.exit(1)
    
    # Check if kubeconfig exists locally, if not try to get it from VM
    local_kubeconfig = Path(__file__).parent / "kubeconfig"
    
    if not local_kubeconfig.exists():
        print("📋 Getting kubeconfig from master VM...")
        try:
            # Use vagrant ssh to copy kubeconfig
            result = subprocess.run([
                "vagrant", "ssh", "master", "-c", 
                "cat /home/vagrant/kubeconfig"
            ], cwd=Path(__file__).parent.parent, capture_output=True, text=True, check=True)
            
            # Write to local file
            local_kubeconfig.write_text(result.stdout)
            print("✅ Kubeconfig copied successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to get kubeconfig: {e}")
            print("💡 Make sure the testbed is fully deployed")
            print("💡 You can also manually copy kubeconfig from master VM")
            sys.exit(1)
    
    # Update config to use local kubeconfig
    config = TestConfig()
    config.config["cluster"]["kubeconfig_path"] = str(local_kubeconfig)

    # Also export for any code honoring the env var (kubectl, client libs, etc.)
    os.environ["KUBECONFIG"] = str(local_kubeconfig)
    
    # Ensure venv is set up unless explicitly disabled
    if not args.no_venv:
        try:
            ensure_venv()
        except Exception as e:
            print(f"❌ Failed to set up virtual environment: {e}")
            print("💡 Use --no-venv to skip venv setup")
            sys.exit(1)
    
    print("✅ Environment ready, starting tests...")
    print("=" * 50)
    
    runner = TestRunner(verbose=args.verbose)
    
    if args.list:
        print("Available test suites:")
        print("  e2e         - End-to-end integration tests")
        print("  protocols   - 5G protocol tests (PFCP, NGAP, GTP-U, NAS)")
        print("  performance - Performance and stress tests")
        print("  resilience  - Failure recovery and fault tolerance tests")
        print("\nAvailable test phases:")
        print("  infrastructure - Basic infrastructure tests")
        print("  5g-core       - 5G Core network function tests")
        print("  ueransim      - UERANSIM simulator tests")
        print("  e2e           - Complete end-to-end tests")
        print("  performance   - Performance tests")
        print("  resilience    - Resilience tests")
        return
    
    if args.suite:
        success = runner.run_test_suite(args.suite)
    elif args.phases:
        success = runner.run_phases(args.phases)
    else:
        success = runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
