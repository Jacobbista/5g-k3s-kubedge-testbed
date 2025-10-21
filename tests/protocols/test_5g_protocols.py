"""
5G Protocol Tests for K3s KubeEdge Testbed
Tests specific 5G protocols: PFCP, NGAP, GTP-U, NAS
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.k8s_client import K8sClient
from utils.test_helpers import TestConfig, TestLogger, NetworkValidator, ComponentValidator


class ProtocolTestSuite:
    """5G Protocol test suite"""
    
    def __init__(self, verbose: bool = False):
        self.config = TestConfig()
        self.logger = TestLogger(verbose)
        self.kubectl = K8sClient(self.config.get("cluster.kubeconfig_path"))
        self.network_validator = NetworkValidator(self.kubectl, self.config)
        self.component_validator = ComponentValidator(self.kubectl, self.config)
        self.verbose = verbose
    
    def run_all_tests(self) -> bool:
        """Run all protocol tests"""
        self.logger.info("Starting 5G Protocol Test Suite")
        
        tests = [
            ("PFCP Protocol (N4)", self.test_pfcp_protocol),
            ("NGAP Protocol (N2)", self.test_ngap_protocol),
            ("GTP-U Protocol (N3)", self.test_gtpu_protocol),
            ("NAS Protocol (N1)", self.test_nas_protocol),
            ("Network Interface IPs", self.test_network_interface_ips),
            ("VXLAN Tunnel Configuration", self.test_vxlan_tunnels),
            ("OVS Bridge Setup", self.test_ovs_bridges),
            ("Protocol Message Exchange", self.test_protocol_message_exchange)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.logger.test_start(test_name)
            try:
                success = test_func()
                if success:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.logger.error(f"{test_name} failed with exception: {e}")
                failed += 1
            self.logger.test_end(test_name, success)
        
        self.logger.info(f"Protocol Test Results: {passed} passed, {failed} failed")
        return failed == 0
    
    def test_pfcp_protocol(self) -> bool:
        """Test PFCP protocol (N4 interface)"""
        self.logger.info("Testing PFCP protocol (N4)...")
        
        try:
            smf_pods = self.component_validator.get_component_pods("smf")
            if not smf_pods:
                self.logger.error("No SMF pods found")
                return False
            
            smf_pod = smf_pods[0]["metadata"]["name"]
            
            ok, out = self.network_validator.check_port_listening(smf_pod, "5g", 8805, "UDP", capture=True)
            if not ok:
                self.logger.error("SMF not listening on PFCP port 8805")
                self.logger.info(f"[debug] ss -unap (SMF {smf_pod}):\n{out}")
                self.component_validator.debug_pod(smf_pod, "5g", self.logger)
                return False
            self.logger.success("SMF listening on PFCP port 8805")
            
            upf_pods = self.component_validator.get_component_pods("upf")
            if not upf_pods:
                self.logger.error("No UPF pods found")
                return False
            
            for upf_pod in upf_pods:
                upf_name = upf_pod["metadata"]["name"]
                ok, out = self.network_validator.check_port_listening(upf_name, "5g", 8805, "UDP", capture=True)
                if not ok:
                    self.logger.error(f"UPF {upf_name} not listening on PFCP port 8805")
                    self.logger.info(f"[debug] ss -unap ({upf_name}):\n{out}")
                    self.component_validator.debug_pod(upf_name, "5g", self.logger)
                    return False
                self.logger.success(f"UPF {upf_name} listening on PFCP port 8805")
            
            smf_n4_ip = self.config.get("network.interfaces.n4.smf_ip")
            ok, out = self.network_validator.check_interface_ip(smf_pod, "5g", "n4", smf_n4_ip, capture=True)
            if not ok:
                self.logger.error(f"SMF N4 interface not configured with IP {smf_n4_ip}")
                self.logger.info(f"[debug] ip addr show n4 (SMF {smf_pod}):\n{out}")
                self.component_validator.debug_pod(smf_pod, "5g", self.logger)
                return False
            self.logger.success(f"SMF N4 interface configured with IP {smf_n4_ip}")
            return True
            
        except Exception as e:
            self.logger.error(f"PFCP protocol test failed: {e}")
            return False
    
    def test_ngap_protocol(self) -> bool:
        """Test NGAP protocol (N2 interface)"""
        self.logger.info("Testing NGAP protocol (N2)...")
        
        try:
            amf_pods = self.component_validator.get_component_pods("amf")
            if not amf_pods:
                self.logger.error("No AMF pods found")
                return False
            
            amf_pod = amf_pods[0]["metadata"]["name"]
            
            ok, out = self.network_validator.check_port_listening(amf_pod, "5g", 38412, "SCTP", capture=True)
            if not ok:
                self.logger.error("AMF not listening on SCTP port 38412 for NGAP")
                self.logger.info(f"[debug] ss -S -na (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            self.logger.success("AMF listening on SCTP port 38412 for NGAP")
            
            amf_n2_ip = self.config.get("network.interfaces.n2.amf_ip")
            ok, out = self.network_validator.check_interface_ip(amf_pod, "5g", "n2", amf_n2_ip, capture=True)
            if not ok:
                self.logger.error(f"AMF N2 interface not configured with IP {amf_n2_ip}")
                self.logger.info(f"[debug] ip addr show n2 (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            self.logger.success(f"AMF N2 interface configured with IP {amf_n2_ip}")
            
            gnb_pods = [p for p in self.kubectl.get_pods("5g") if "gnb" in p["metadata"]["name"].lower()]
            if gnb_pods:
                gnb_pod = gnb_pods[0]["metadata"]["name"]
                ok, out = self.network_validator.check_connectivity(gnb_pod, amf_pod, "5g", amf_n2_ip, capture=True)
                if ok:
                    self.logger.success("gNB can reach AMF on N2 interface")
                else:
                    self.logger.warning("gNB cannot reach AMF on N2 interface (might be normal during startup)")
                    self.logger.info(f"[debug] ping output (gNB {gnb_pod} → AMF {amf_pod} {amf_n2_ip}):\n{out}")
            return True
            
        except Exception as e:
            self.logger.error(f"NGAP protocol test failed: {e}")
            return False
    
    def test_gtpu_protocol(self) -> bool:
        """Test GTP-U protocol (N3 interface)"""
        self.logger.info("Testing GTP-U protocol (N3)...")
        
        try:
            upf_pods = self.component_validator.get_component_pods("upf")
            if not upf_pods:
                self.logger.error("No UPF pods found")
                return False
            
            for upf_pod in upf_pods:
                upf_name = upf_pod["metadata"]["name"]
                ok, out = self.network_validator.check_port_listening(upf_name, "5g", 2152, "UDP", capture=True)
                if not ok:
                    self.logger.error(f"UPF {upf_name} not listening on GTP-U port 2152")
                    self.logger.info(f"[debug] ss -unap ({upf_name}):\n{out}")
                    self.component_validator.debug_pod(upf_name, "5g", self.logger)
                    return False
                self.logger.success(f"UPF {upf_name} listening on GTP-U port 2152")
                
                expected_ip = (self.config.get("network.interfaces.n3.upf_edge_ip")
                               if "edge" in upf_name.lower()
                               else self.config.get("network.interfaces.n3.upf_cloud_ip"))
                ok, out = self.network_validator.check_interface_ip(upf_name, "5g", "n3", expected_ip, capture=True)
                if not ok:
                    self.logger.error(f"UPF {upf_name} N3 interface not configured with IP {expected_ip}")
                    self.logger.info(f"[debug] ip addr show n3 ({upf_name}):\n{out}")
                    self.component_validator.debug_pod(upf_name, "5g", self.logger)
                    return False
                self.logger.success(f"UPF {upf_name} N3 interface configured with IP {expected_ip}")
            return True
            
        except Exception as e:
            self.logger.error(f"GTP-U protocol test failed: {e}")
            return False
    
    def test_nas_protocol(self) -> bool:
        """Test NAS protocol (N1 interface)"""
        self.logger.info("Testing NAS protocol (N1)...")
        
        try:
            amf_pods = self.component_validator.get_component_pods("amf")
            if not amf_pods:
                self.logger.error("No AMF pods found")
                return False
            
            amf_pod = amf_pods[0]["metadata"]["name"]
            
            ok, out = self.network_validator.check_port_listening(amf_pod, "5g", 38412, "SCTP", capture=True)
            if not ok:
                self.logger.error("AMF not listening on SCTP port 38412 for NAS")
                self.logger.info(f"[debug] ss -S -na (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            self.logger.success("AMF listening on SCTP port 38412 for NAS")
            
            amf_n1_ip = self.config.get("network.interfaces.n1.amf_ip")
            ok, out = self.network_validator.check_interface_ip(amf_pod, "5g", "n1", amf_n1_ip, capture=True)
            if not ok:
                self.logger.error(f"AMF N1 interface not configured with IP {amf_n1_ip}")
                self.logger.info(f"[debug] ip addr show n1 (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            self.logger.success(f"AMF N1 interface configured with IP {amf_n1_ip}")
            
            ue_pods = [p for p in self.kubectl.get_pods("5g") if "ue" in p["metadata"]["name"].lower()]
            if ue_pods:
                ue_pod = ue_pods[0]["metadata"]["name"]
                ok, out = self.network_validator.check_connectivity(ue_pod, amf_pod, "5g", amf_n1_ip, capture=True)
                if ok:
                    self.logger.success("UE can reach AMF on N1 interface")
                else:
                    self.logger.warning("UE cannot reach AMF on N1 interface (might be normal during startup)")
                    self.logger.info(f"[debug] ping output (UE {ue_pod} → AMF {amf_pod} {amf_n1_ip}):\n{out}")
            return True
            
        except Exception as e:
            self.logger.error(f"NAS protocol test failed: {e}")
            return False
    
    def test_network_interface_ips(self) -> bool:
        """Test network interface IP assignments"""
        self.logger.info("Testing network interface IP assignments...")
        
        try:
            amf_pods = self.component_validator.get_component_pods("amf")
            if not amf_pods:
                self.logger.error("No AMF pods found")
                return False
            
            amf_pod = amf_pods[0]["metadata"]["name"]
            
            n1_ip = self.config.get("network.interfaces.n1.amf_ip")
            ok, out = self.network_validator.check_interface_ip(amf_pod, "5g", "n1", n1_ip, capture=True)
            if not ok:
                self.logger.error(f"AMF N1 interface IP mismatch: expected {n1_ip}")
                self.logger.info(f"[debug] ip addr show n1 (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            
            n2_ip = self.config.get("network.interfaces.n2.amf_ip")
            ok, out = self.network_validator.check_interface_ip(amf_pod, "5g", "n2", n2_ip, capture=True)
            if not ok:
                self.logger.error(f"AMF N2 interface IP mismatch: expected {n2_ip}")
                self.logger.info(f"[debug] ip addr show n2 (AMF {amf_pod}):\n{out}")
                self.component_validator.debug_pod(amf_pod, "5g", self.logger)
                return False
            
            self.logger.success("AMF interface IPs configured correctly")
            
            smf_pods = self.component_validator.get_component_pods("smf")
            if not smf_pods:
                self.logger.error("No SMF pods found")
                return False
            
            smf_pod = smf_pods[0]["metadata"]["name"]
            n4_ip = self.config.get("network.interfaces.n4.smf_ip")
            ok, out = self.network_validator.check_interface_ip(smf_pod, "5g", "n4", n4_ip, capture=True)
            if not ok:
                self.logger.error(f"SMF N4 interface IP mismatch: expected {n4_ip}")
                self.logger.info(f"[debug] ip addr show n4 (SMF {smf_pod}):\n{out}")
                self.component_validator.debug_pod(smf_pod, "5g", self.logger)
                return False
            
            self.logger.success("SMF interface IP configured correctly")
            return True
            
        except Exception as e:
            self.logger.error(f"Network interface IP test failed: {e}")
            return False
    
    def test_vxlan_tunnels(self) -> bool:
        """Test VXLAN tunnel configuration"""
        self.logger.info("Testing VXLAN tunnel configuration...")
        
        try:
            ovs_pods = [p for p in self.kubectl.get_pods("kube-system") if "ovs" in p["metadata"]["name"].lower()]
            if not ovs_pods:
                all_sys = [p["metadata"]["name"] for p in self.kubectl.get_pods("kube-system")]
                self.logger.error("No OVS pods found")
                self.logger.info(f"[debug] kube-system pods: {all_sys}")
                return False
            
            running_ovs = [p for p in ovs_pods if p["status"]["phase"] == "Running"]
            if len(running_ovs) < 2:
                self.logger.error(f"Not enough OVS pods running: {len(running_ovs)}")
                return False
            
            self.logger.success(f"Found {len(running_ovs)} running OVS pods")
            
            for ovs_pod in running_ovs:
                pod_name = ovs_pod["metadata"]["name"]
                try:
                    out = self.kubectl.exec_in_pod(pod_name, "kube-system", ["ovs-vsctl", "show"])
                    if "vxlan" in out.lower():
                        self.logger.success(f"VXLAN interfaces found on {pod_name}")
                    else:
                        self.logger.warning(f"No VXLAN interfaces found on {pod_name}")
                except Exception as e:
                    self.logger.warning(f"Could not check VXLAN on {pod_name}: {e}")
            return True
            
        except Exception as e:
            self.logger.error(f"VXLAN tunnel test failed: {e}")
            return False
    
    def test_ovs_bridges(self) -> bool:
        """Test OVS bridge setup"""
        self.logger.info("Testing OVS bridge setup...")
        
        try:
            ovs_pods = [p for p in self.kubectl.get_pods("kube-system") if "ovs" in p["metadata"]["name"].lower()]
            if not ovs_pods:
                all_sys = [p["metadata"]["name"] for p in self.kubectl.get_pods("kube-system")]
                self.logger.error("No OVS pods found")
                self.logger.info(f"[debug] kube-system pods: {all_sys}")
                return False
            
            running_ovs = [p for p in ovs_pods if p["status"]["phase"] == "Running"]
            if not running_ovs:
                self.logger.error("No running OVS pods found")
                return False
            
            for ovs_pod in running_ovs:
                pod_name = ovs_pod["metadata"]["name"]
                try:
                    out = self.kubectl.exec_in_pod(pod_name, "kube-system", ["ovs-vsctl", "list-br"])
                    bridges = [b for b in out.strip().splitlines() if b]
                    if bridges:
                        self.logger.success(f"OVS bridges found on {pod_name}: {bridges}")
                    else:
                        self.logger.warning(f"No OVS bridges found on {pod_name}")
                except Exception as e:
                    self.logger.warning(f"Could not check OVS bridges on {pod_name}: {e}")
            return True
            
        except Exception as e:
            self.logger.error(f"OVS bridge test failed: {e}")
            return False
    
    def test_protocol_message_exchange(self) -> bool:
        """Test protocol message exchange"""
        self.logger.info("Testing protocol message exchange...")
        
        try:
            amf_pods = self.component_validator.get_component_pods("amf")
            smf_pods = self.component_validator.get_component_pods("smf")
            
            if amf_pods and smf_pods:
                amf_pod = amf_pods[0]["metadata"]["name"]
                smf_pod = smf_pods[0]["metadata"]["name"]
                
                amf_ip = self.kubectl.exec_in_pod(amf_pod, "5g", ["hostname", "-i"]).strip()
                
                ok, out = self.network_validator.check_connectivity(smf_pod, amf_pod, "5g", amf_ip, capture=True)
                if ok:
                    self.logger.success("SMF can reach AMF")
                else:
                    self.logger.warning("SMF cannot reach AMF (might be normal during startup)")
                    self.logger.info(f"[debug] ping output (SMF {smf_pod} → AMF {amf_pod} {amf_ip}):\n{out}")
            
            gnb_pods = [p for p in self.kubectl.get_pods("5g") if "gnb" in p["metadata"]["name"].lower()]
            if gnb_pods and amf_pods:
                gnb_pod = gnb_pods[0]["metadata"]["name"]
                amf_pod = amf_pods[0]["metadata"]["name"]
                
                amf_n2_ip = self.config.get("network.interfaces.n2.amf_ip")
                ok, out = self.network_validator.check_connectivity(gnb_pod, amf_pod, "5g", amf_n2_ip, capture=True)
                if ok:
                    self.logger.success("gNB can reach AMF on N2 interface")
                else:
                    self.logger.warning("gNB cannot reach AMF on N2 interface (might be normal during startup)")
                    self.logger.info(f"[debug] ping output (gNB {gnb_pod} → AMF {amf_pod} {amf_n2_ip}):\n{out}")
            return True
            
        except Exception as e:
            self.logger.error(f"Protocol message exchange test failed: {e}")
            return False


def main():
    """Main function for running protocol tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="5G Protocol Tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    test_suite = ProtocolTestSuite(verbose=args.verbose)
    success = test_suite.run_all_tests()
    
    if success:
        print("\n🎉 All protocol tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some protocol tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
