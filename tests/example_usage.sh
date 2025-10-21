#!/bin/bash
# Example usage of the 5G testbed test suite

echo "5G K3s KubeEdge Testbed - Test Suite Examples"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "test_config.yaml" ]; then
    echo "Error: Please run this script from the tests/ directory"
    exit 1
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl not found. Please install kubectl and configure it."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl get nodes &> /dev/null; then
    echo "Error: Cannot access Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Install dependencies
echo "Installing test dependencies..."
make install

echo ""
echo "Available test commands:"
echo "========================"
echo ""

echo "1. Run all tests:"
echo "   make all"
echo "   make all VERBOSE=1"
echo ""

echo "2. Run specific test suites:"
echo "   make e2e                    # End-to-end tests"
echo "   make protocols              # 5G protocol tests"
echo "   make performance            # Performance tests"
echo "   make resilience             # Resilience tests"
echo ""

echo "3. Run specific test phases:"
echo "   python3 run_tests.py -p infrastructure,5g-core"
echo "   python3 run_tests.py -p ueransim"
echo "   python3 run_tests.py -p e2e"
echo ""

echo "4. Run with verbose output:"
echo "   make e2e VERBOSE=1"
echo "   python3 run_tests.py -s protocols -v"
echo ""

echo "5. List available tests:"
echo "   make list"
echo "   python3 run_tests.py --list"
echo ""

echo "6. Clean up:"
echo "   make clean"
echo ""

echo "7. Show configuration:"
echo "   make config"
echo "   make validate-config"
echo ""

echo "8. Show status:"
echo "   make status"
echo ""

echo "Example test run:"
echo "================="
echo ""

# Run a quick test
echo "Running a quick end-to-end test..."
make e2e VERBOSE=1

echo ""
echo "Test suite examples completed!"
echo "For more information, see README.md"
