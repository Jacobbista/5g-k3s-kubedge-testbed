# 5G K3s KubeEdge Testbed - Test Suite

This directory contains comprehensive test suites for the 5G K3s KubeEdge testbed, providing end-to-end validation, performance testing, and resilience testing.

## Test Suite Overview

The test suite consists of four main components:

1. **End-to-End Tests** (`core/test_e2e.py`) - Complete system integration testing
2. **5G Protocol Tests** (`protocols/test_5g_protocols.py`) - Specific 5G protocol validation
3. **Performance Tests** (`performance/test_performance.py`) - Performance and stress testing
4. **Resilience Tests** (`resilience/test_resilience.py`) - Failure recovery and fault tolerance

## Quick Start

### Prerequisites

- Python 3.8+
- kubectl configured and accessible
- 5G testbed deployed and running

### Prerequisites Check

The test runner automatically checks:

- ✅ Vagrant VMs are running (master, worker, edge)
- ✅ Virtual environment is set up
- ✅ Dependencies are installed
- ✅ Kubernetes cluster is accessible

If any check fails, you'll get a clear error message with instructions.

### Quick Start

```bash
# Start the testbed first
vagrant up

# Launch interactive CLI (recommended)
make                        # Beautiful interactive interface
python3 interactive_cli.py  # Same as above

# Or use command line
make e2e                    # Run specific tests
python3 run_tests.py -s e2e # Full command
```

### Run All Tests

```bash
# Run all test suites
make all

# Run with verbose output
make all VERBOSE=1

# Run specific test suites
make e2e
make protocols
make performance
make resilience
```

### Run Individual Test Suites

```bash
# End-to-end tests
python3 run_tests.py -s e2e

# 5G protocol tests
python3 run_tests.py -s protocols

# Performance tests
python3 run_tests.py -s performance

# Resilience tests
python3 run_tests.py -s resilience
```

## Test Suites

### 1. End-to-End Tests (`core/test_e2e.py`)

Comprehensive integration testing covering the entire system.

**Test Phases:**

- Infrastructure connectivity (ping, SSH)
- Kubernetes cluster health (nodes, pods)
- KubeEdge integration (CloudCore, EdgeCore)
- Overlay network (Multus, OVS, VXLAN)
- 5G Core deployment (AMF, SMF, UPF, etc.)
- Network interfaces (N1, N2, N3, N4, N6e, N6c)
- Protocol connectivity (PFCP, NGAP, GTP-U)
- UERANSIM deployment (gNB, UE)
- MEC deployment
- End-to-end connectivity

**Usage:**

```bash
# Run all E2E tests
make e2e

# Run with verbose output
make e2e VERBOSE=1

# Run specific phases
python3 run_tests.py -p infrastructure,5g-core
```

### 2. 5G Protocol Tests (`protocols/test_5g_protocols.py`)

Specific testing for 5G protocols and network interfaces.

**Protocols Tested:**

- **PFCP (N4)** - SMF ↔ UPF control plane
- **NGAP (N2)** - gNB ↔ AMF signaling
- **GTP-U (N3)** - gNB/UE ↔ UPF data plane
- **NAS (N1)** - UE ↔ AMF non-access stratum

**Key Tests:**

- Protocol port listening (8805, 38412, 2152)
- Network interface IP assignments
- VXLAN tunnel configuration
- OVS bridge setup
- Protocol message exchange
- Performance validation
- Log analysis

**Usage:**

```bash
# Run all protocol tests
make protocols

# Run with verbose output
make protocols VERBOSE=1
```

### 3. Performance Tests (`performance/test_performance.py`)

Performance and stress testing for the 5G testbed.

**Performance Metrics:**

- Network throughput (VXLAN tunnels)
- Latency (end-to-end, interface-specific)
- Packet loss (under load)
- Protocol performance (PFCP, NGAP)
- Concurrent connections
- Sustained load
- Resource usage (CPU, memory)

**Key Tests:**

- VXLAN throughput (iperf3)
- VXLAN latency (ping with different packet sizes)
- Packet loss (high packet rate)
- PFCP performance (connection success rate)
- NGAP performance (SCTP connection rate)
- Concurrent connections (parallel PFCP)
- Sustained load (continuous operation)
- CPU and memory usage
- Interface throughput
- End-to-end performance

**Usage:**

```bash
# Run all performance tests
make performance

# Run with verbose output
make performance VERBOSE=1
```

### 4. Resilience Tests (`resilience/test_resilience.py`)

Failure recovery and fault tolerance testing.

**Resilience Scenarios:**

- Pod restart recovery
- Network interface recovery
- Node failure recovery
- Network partition recovery
- OVS bridge and VXLAN tunnel recovery
- Multus and KubeEdge recovery
- Database recovery
- Stress test cleanup

**Key Tests:**

- Pod restart recovery (AMF, SMF, UPF)
- Network interface recovery (N1, N2, N3, N4)
- Node failure simulation (worker/edge)
- Network partition simulation
- OVS bridge recreation
- VXLAN tunnel recreation
- Multus DaemonSet restart
- KubeEdge CloudCore/EdgeCore restart
- MongoDB restart
- Stress test cleanup

**Usage:**

```bash
# Run all resilience tests
make resilience

# Run with verbose output
make resilience VERBOSE=1
```

## Configuration

### Test Configuration (`test_config.yaml`)

The test suite uses a YAML configuration file for centralized configuration:

```yaml
# Global test configuration
global:
  verbose: false
  timeout: 300
  retry_attempts: 3

# Test suite configurations
suites:
  e2e:
    enabled: true
    timeout: 1800

  protocols:
    enabled: true
    timeout: 600

  performance:
    enabled: true
    timeout: 1200

  resilience:
    enabled: true
    timeout: 1800

# Network configuration (from ansible/group_vars/all.yml)
network:
  interfaces:
    n1:
      amf_ip: "10.201.0.100"
      subnet: "10.201.0.0/24"
    # ... more interfaces

# Performance thresholds
performance:
  throughput:
    min_mbps: 10
    target_mbps: 100
  latency:
    max_ms: 50
    target_ms: 10
```

### Environment Variables

You can override configuration using environment variables:

```bash
# Test configuration
export VERBOSE=true
export TEST_TIMEOUT=600

# Performance configuration
export TEST_DURATION=120
export PARALLEL_CONNECTIONS=20
```

## Test Results

### Output Format

Test results are displayed with color-coded output:

- ✅ **Success** - Test passed
- ❌ **Error** - Test failed
- ⚠️ **Warning** - Test completed with warnings
- ℹ️ **Info** - Informational message

### Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Troubleshooting

### Common Issues

#### 1. kubectl Not Found

```bash
# Check kubectl configuration
kubectl get nodes

# Check kubeconfig
kubectl config current-context
```

#### 2. Cluster Not Accessible

```bash
# Check cluster connectivity
kubectl get nodes

# Verify kubeconfig path
ls -la /home/vagrant/kubeconfig
```

#### 3. Test Timeouts

```bash
# Increase timeout in test_config.yaml
# Or set environment variable
export TEST_TIMEOUT=1200
```

#### 4. Performance Test Failures

```bash
# Check if iperf3 is available
kubectl -n 5g exec deploy/amf -- which iperf3

# Install iperf3 if needed
kubectl -n 5g exec deploy/amf -- apt-get update && apt-get install -y iperf3
```

### Debug Mode

Enable verbose output for debugging:

```bash
# Run with verbose output
make all VERBOSE=1

# Or use debug target
make debug
```

### Test-Specific Debugging

```bash
# E2E tests
python3 run_tests.py -s e2e -v

# Protocol tests
python3 run_tests.py -s protocols -v

# Performance tests
python3 run_tests.py -s performance -v

# Resilience tests
python3 run_tests.py -s resilience -v
```

## Continuous Integration

### GitHub Actions

Example workflow for CI/CD:

```yaml
name: 5G Testbed Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup testbed
        run: |
          vagrant up
          vagrant ssh ansible -c "cd /home/vagrant/ansible-ro && ansible-playbook phases/00-main-playbook.yml"

      - name: Run tests
        run: |
          cd tests
          make install
          make all
```

### Jenkins Pipeline

Example Jenkinsfile:

```groovy
pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh 'vagrant up'
                sh 'vagrant ssh ansible -c "cd /home/vagrant/ansible-ro && ansible-playbook phases/00-main-playbook.yml"'
            }
        }

        stage('Tests') {
            steps {
                dir('tests') {
                    sh 'make install'
                    sh 'make all'
                }
            }
        }
    }
}
```

## Contributing

### Adding New Tests

1. **Identify the test category** (E2E, Protocol, Performance, Resilience)
2. **Add test function** to the appropriate script
3. **Update test execution** in the main test function
4. **Add documentation** for the new test
5. **Update configuration** if needed

### Test Function Template

```python
def test_new_feature(self) -> bool:
    """Test new feature"""
    self.logger.info("Testing new feature...")

    try:
        # Test implementation
        if condition:
            self.logger.success("New feature test passed")
            return True
        else:
            self.logger.error("New feature test failed")
            return False
    except Exception as e:
        self.logger.error(f"New feature test failed: {e}")
        return False
```

### Test Standards

- **Naming**: Use descriptive test names
- **Logging**: Include informative log messages
- **Error Handling**: Provide clear error messages
- **Documentation**: Document test purpose and expected behavior
- **Configuration**: Make tests configurable via test_config.yaml

## License

This test suite is part of the 5G K3s KubeEdge Testbed project and is licensed under the MIT License.

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the test logs for specific error messages
3. Check the main project documentation
4. Open an issue in the project repository

## Changelog

### v1.0.0 (2024-12-01)

- Initial release
- End-to-end test suite
- 5G protocol test suite
- Performance test suite
- Resilience test suite
- Configuration system
- Comprehensive documentation
